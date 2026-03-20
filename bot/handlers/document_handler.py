import logging
import os
import tempfile
import html
from aiogram import Router, types, F, Bot
from aiogram.filters import MagicData
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.database import get_session
from bot.services.pdf_parser import PDFParser
from bot.services.analyzer import Analyzer
from bot.database.models import QualFile, QualPos, QualIssue

router = Router()
logger = logging.getLogger(__name__)

async def process_pdf(bot: Bot, message: types.Message, file_id: str, file_name: str):
    """
    Downloads and processes the PDF file.
    """
    status_msg = await message.answer(f"Скачиваю и обрабатываю файл {file_name}...")
    
    # Create session manually since we are in a helper function, 
    # or use dependency injection if framework supported it easily inside handler.
    # For simplicity, we use the generator as context manager if possible or just manual instantiation
    from bot.database.database import async_session
    session = async_session()
    
    temp_path = None
    try:
        # 1. Download File
        file_info = await bot.get_file(file_id)
        
        # Create temp file
        fd, temp_path = tempfile.mkstemp(suffix=".pdf")
        os.close(fd)
        
        await bot.download_file(file_info.file_path, temp_path)
        
        # 2. Parse PDF
        await status_msg.edit_text("Извлекаю текст и позиции...")
        try:
            full_text = PDFParser.extract_text(temp_path)
            items = PDFParser.parse_text(full_text)
        except Exception as e:
            logger.error(f"Parsing error: {e}", exc_info=True)
            await status_msg.edit_text(f"Ошибка при обработке PDF: {e}")
            return

        if not items:
            await status_msg.edit_text("Не удалось извлечь позиции из файла. Вышлите pdf файл из StartОкна: Печать/Резерв/3.4 Заполнения")
            return

        # 3. Analyze
        await status_msg.edit_text(f"Найдено {len(items)} позиций. Анализирую...")
        
        analyzer = Analyzer(session)
        await analyzer.load_films()
        await analyzer.load_articles()
        
        # Determine Report Data
        report_lines = []
        issues_count = 0
        
        # Save File Record
        qfile = QualFile(
            file_name=file_name,
            file_path=file_id, # store tg file id or path? Telegram IDs are temporaryish usually, but okay for history ref
            tg_username=message.from_user.username,
            tg_chatid=message.chat.id,
            full_raw=full_text[:50000] # limit size
        )
        session.add(qfile)
        await session.flush() # get ID
        
        for item in items:
            # Skip slip analysis for single glazing (no spacer frame in formula)
            formula_source = item.get("raw_formula") or item.get("position_formula") or ""
            if not analyzer.has_spacer(formula_source):
                # Still save position, but do not run slip checks or create issues
                qpos = QualPos(
                    file_id=qfile.id,
                    position_num=item["position_num"],
                    position_formula=item["position_formula"],
                    position_raskl=item["position_raskl"],
                    position_width=item["position_width"],
                    position_hight=item["position_hight"],
                    position_count=item["position_count"],
                    position_area=item["position_area"],
                    position_mass=item["position_mass"],
                    is_oytside=item["is_oytside"],
                    # JSONB for debug
                    article_json=item
                )
                session.add(qpos)
                await session.flush()
                continue

            # Parse Formula Elements
            elements = analyzer.parse_formula(item["position_formula"], item["is_oytside"])
            
            # Validate
            # We assume width/height are mostly correct integers
            w = item["position_width"]
            h = item["position_hight"]
            
            # Check Slip
            slip_errors = await analyzer.check_slip(w, h, elements)
            
            # Save Position
            qpos = QualPos(
                file_id=qfile.id,
                position_num=item["position_num"],
                position_formula=item["position_formula"],
                position_raskl=item["position_raskl"],
                position_width=w,
                position_hight=h,
                position_count=item["position_count"],
                position_area=item["position_area"],
                position_mass=item["position_mass"],
                is_oytside=item["is_oytside"],
                # JSONB for debug
                article_json=item
            )
            session.add(qpos)
            await session.flush() # get ID details
            
            if slip_errors:
                issues_count += 1
                
                # Format Error Message for Report
                # Escape values to prevent HTML parsing errors
                safe_pos_num = html.escape(str(item['position_num']))
                pos_header = f"Позиция №{safe_pos_num} ({w}x{h})"
                
                opening_scheme = "Наружу ↗️" if item["is_oytside"] else "Внутрь ↙️"
                safe_formula = html.escape(item['position_formula'])
                form_info = f"Формула: {safe_formula}\nОткрывание: {opening_scheme}"
                if item["is_oytside"]:
                    form_info += " (формула перевернута)"
                
                # Escape error messages which may check contain "<" or ">"
                error_txt = "\n".join([f"⛔️ {html.escape(err)}" for err in slip_errors])
                
                block = f"<b>{pos_header}</b>\n{form_info}\n{error_txt}\n"
                report_lines.append(block)
                
                # Save Issue to DB
                for err in slip_errors:
                    issue = QualIssue(
                        pos_id=qpos.id,
                        issue_code="SLIP_MISMATCH", # Generic code for now
                        message=err,
                        severity="error"
                    )
                    session.add(issue)

        await session.commit()
        
        # 4. Send Report
        # Ensure filename is also escaped for the report header
        final_text = generate_report_text(html.escape(file_name), len(items), report_lines, issues_count)
        
        await status_msg.edit_text(final_text, parse_mode="HTML")

    except Exception as e:
        logger.error(f"Processing failed: {e}", exc_info=True)
        await status_msg.edit_text(f"Произошла критическая ошибка: {e}")
    finally:
        await session.close()
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)


def generate_report_text(file_name: str, total_items: int, report_lines: list, issues_count: int) -> str:
    """Generates the final report text."""
    if not report_lines:
        return (
            f"✅ Файл <b>{file_name}</b> проверен.\n"
            f"Всего позиций: {total_items}\n"
            "Ошибок не обнаружено."
        )
    else:
        header = f"⚠️ В файле <b>{file_name}</b> обнаружены проблемы ({issues_count} поз.):\n\n"
        full_report = header + "\n".join(report_lines)
        
        if len(full_report) > 4000:
            return full_report[:4000] + "\n\n... (отчет обрезан)"
        else:
            return full_report


@router.message(F.document)
async def handle_document(message: types.Message, bot: Bot):
    doc = message.document
    if doc.mime_type == "application/pdf" or doc.file_name.lower().endswith(".pdf"):
        # Run processing asynchronously 
        # (in real app maybe background task, but here just await call is okay for MVP)
        await process_pdf(bot, message, doc.file_id, doc.file_name)
    else:
        await message.reply("Пожалуйста, отправьте файл в формате PDF.")
