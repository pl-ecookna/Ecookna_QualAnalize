
import os
import tempfile
import logging
import html
import shutil
from typing import List, Optional

from fastapi import FastAPI, Request, UploadFile, File, Depends, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from sqlalchemy.ext.asyncio import AsyncSession

# Reuse bot components
from bot.database.database import get_session
from bot.services.pdf_parser import PDFParser
from bot.services.analyzer import Analyzer
from bot.database.models import QualFile, QualPos, QualIssue

# Setup logging to console
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="QualAnalyze Web Interface")

# Mount static files if needed (e.g. for css/js)
# app.mount("/static", StaticFiles(directory="web/static"), name="static")

templates = Jinja2Templates(directory="web/templates")

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/api/check")
async def check_file(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session)
):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")

    temp_path = None
    try:
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
                "message": "Не удалось извлечь позиции из файла. Возможно формат отличается от ожидаемого.",
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
                position_raskl=item["position_raskl"],
                position_width=w,
                position_hight=h,
                position_count=item["position_count"],
                position_area=item["position_area"],
                position_mass=item["position_mass"],
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
                    "errors": error_details,
                    "raskl": item["position_raskl"]
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
