
import os
import tempfile
import logging
import html
import shutil
import re
from typing import List, Optional

from fastapi import FastAPI, Request, UploadFile, File, Depends, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, field_validator

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

# Reuse bot components
from bot.database.database import get_session
from bot.services.pdf_parser import PDFParser
from bot.services.analyzer import Analyzer
from bot.database.models import QualFile, QualPos, QualIssue

# Setup logging to console
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="QualAnalyze Web Interface")

templates = Jinja2Templates(directory="web/templates")
FRONTEND_DIST_DIR = os.path.join("frontend", "dist")
FRONTEND_ASSETS_DIR = os.path.join(FRONTEND_DIST_DIR, "assets")

if os.path.isdir(FRONTEND_ASSETS_DIR):
    app.mount("/assets", StaticFiles(directory=FRONTEND_ASSETS_DIR), name="assets")


class SlipFormulaLookupRequest(BaseModel):
    size: str

    @field_validator("size")
    @classmethod
    def validate_size(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Укажите размер стеклопакета")
        return value


def parse_size_input(size_value: str) -> tuple[int, int]:
    normalized = re.sub(r"\s+", "", size_value.lower())
    match = re.fullmatch(r"(\d{2,5})[*xх×](\d{2,5})", normalized)
    if not match:
        raise HTTPException(
            status_code=400,
            detail="Введите размер в формате 1520*2730"
        )

    width = int(match.group(1))
    height = int(match.group(2))

    if width <= 0 or height <= 0:
        raise HTTPException(status_code=400, detail="Размеры должны быть больше нуля")

    return width, height


async def ensure_database_available(session: AsyncSession) -> None:
    try:
        await session.execute(text("SELECT 1"))
    except Exception as exc:
        logger.error("Database availability check failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=503, detail="База данных недоступна")

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    frontend_index = os.path.join(FRONTEND_DIST_DIR, "index.html")
    if os.path.exists(frontend_index):
        return FileResponse(frontend_index)
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/api/slip-formulas")
async def get_slip_formulas(
    payload: SlipFormulaLookupRequest,
    session: AsyncSession = Depends(get_session)
):
    width, height = parse_size_input(payload.size)
    await ensure_database_available(session)

    analyzer = Analyzer(session)
    result = await analyzer.get_slip_formulas_by_size(width, height)

    if not result["found"]:
        return JSONResponse(content={
            "status": "not_found",
            "message": f"Для размера {width}x{height} правило не найдено",
            **result
        })

    return JSONResponse(content={
        "status": "success",
        **result
    })

@app.post("/api/check")
async def check_file(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session)
):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")

    temp_path = None
    try:
        await ensure_database_available(session)

        # 1. Save uploaded file to temp
        fd, temp_path = tempfile.mkstemp(suffix=".pdf")
        os.close(fd)
        
        # Write the uploaded file to the temp file
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # 2. Parse PDF
        try:
            full_text = PDFParser.extract_text(temp_path)
            items = PDFParser.parse_text(full_text)
        except Exception as e:
            logger.error(f"Parsing error: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"PDF Parsing failed: {str(e)}")

        if not items:
            return JSONResponse(content={
                "status": "warning", 
                "message": "Не удалось извлечь позиции из файла. Вышлите pdf файл из StartОкна: Печать/Резерв/3.4 Заполнения",
                "file_name": file.filename,
                "total_items": 0,
                "issues_count": 0,
                "report_data": []
            })

        # 3. Analyze
        analyzer = Analyzer(session)
        await analyzer.load_films()
        
        report_lines = []
        issues_count = 0
        
        # Save File Record (mark as uploaded from web)
        qfile = QualFile(
            file_name=file.filename,
            file_path="web_upload",
            tg_username="web_user",
            tg_chatid=0,
            full_raw=full_text[:50000]
        )
        session.add(qfile)
        await session.flush()
        
        for item in items:
            # Skip slip analysis for single glazing (no spacer frame in formula)
            formula_source = item["position_formula"]
            if not analyzer.has_spacer(formula_source):
                qpos = QualPos(
                    file_id=qfile.id,
                    position_num=item["position_num"],
                    position_formula=item["position_formula"],
                    position_width=item["position_width"],
                    position_hight=item["position_hight"],
                    is_oytside=item["is_oytside"],
                    article_json=item
                )
                session.add(qpos)
                await session.flush()
                continue

            # Parse Formula Elements
            elements = analyzer.parse_formula(item["position_formula"], item["is_oytside"])
            
            w = item["position_width"]
            h = item["position_hight"]
            
            # Check Slip
            slip_errors = await analyzer.check_slip(w, h, elements)
            
            # Save Position
            qpos = QualPos(
                file_id=qfile.id,
                position_num=item["position_num"],
                position_formula=item["position_formula"],
                position_width=w,
                position_hight=h,
                is_oytside=item["is_oytside"],
                article_json=item
            )
            session.add(qpos)
            await session.flush() 
            
            if slip_errors:
                issues_count += 1
                
                # Structure error for JSON response
                error_details = []
                for err in slip_errors:
                    issue = QualIssue(
                        pos_id=qpos.id,
                        issue_code="SLIP_MISMATCH",
                        message=err,
                        severity="error"
                    )
                    session.add(issue)
                    error_details.append(err)

                report_lines.append({
                    "pos_num": item["position_num"],
                    "size": f"{w}x{h}",
                    "formula": item["position_formula"],
                    "is_outside": item["is_oytside"],
                    "errors": error_details
                })

        await session.commit()
        
        return JSONResponse(content={
            "status": "success" if issues_count == 0 else "issues_found",
            "file_name": file.filename,
            "total_items": len(items),
            "issues_count": issues_count,
            "report_data": report_lines
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Processing failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")
    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)
