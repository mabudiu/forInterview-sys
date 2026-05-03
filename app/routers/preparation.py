"""面试前准备路由"""
import asyncio
import tempfile
import os
from fastapi import APIRouter, UploadFile, File
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional

from app.services.file_parser import extract_text, clean_text
from app.services.analyzer import analyze_preparation

router = APIRouter(prefix="/api/preparation", tags=["面试前准备"])


class AnalyzeReq(BaseModel):
    jd_text: Optional[str] = None
    resume_text: Optional[str] = None


@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    suffix = os.path.splitext(file.filename or "tmp")[1].lower()
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        text = extract_text(open(tmp_path, "rb").read(), file.filename or "tmp")
        text = clean_text(text)
    finally:
        os.unlink(tmp_path)

    return {"text": text, "filename": file.filename}


@router.post("/analyze")
async def analyze(req: AnalyzeReq):
    jd_text = req.jd_text or ""
    resume_text = req.resume_text or ""

    if not jd_text.strip() and not resume_text.strip():
        return JSONResponse({"error": "请提供JD文本或简历文本内容"}, status_code=400)

    jd_clean = clean_text(jd_text)
    resume_clean = clean_text(resume_text)

    # 在线程池执行，避免阻塞事件循环
    result = await asyncio.to_thread(analyze_preparation, jd_clean, resume_clean)
    return result
