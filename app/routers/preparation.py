"""面试前准备路由"""
import asyncio
import tempfile
import os
import uuid
import json
from datetime import datetime
from fastapi import APIRouter, UploadFile, File
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional

from app.services.file_parser import extract_text, clean_text
from app.services.analyzer import analyze_preparation

router = APIRouter(prefix="/api/preparation", tags=["面试前准备"])

RESUME_STORAGE_DIR = os.path.join(os.path.dirname(__file__), "storage", "resumes")
os.makedirs(RESUME_STORAGE_DIR, exist_ok=True)


class AnalyzeReq(BaseModel):
    jd_text: Optional[str] = None
    resume_text: Optional[str] = None
    auto_save_resume: bool = False  # 上传时是否自动保存简历


METADATA_FILE = os.path.join(RESUME_STORAGE_DIR, "_metadata.json")


def _load_metadata() -> dict:
    if os.path.exists(METADATA_FILE):
        with open(METADATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"resumes": []}


def _save_metadata(meta: dict):
    with open(METADATA_FILE, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)


class SaveResumeReq(BaseModel):
    text: str
    filename: Optional[str] = "未命名简历"


@router.post("/saved-resumes")
def save_resume(req: SaveResumeReq):
    """保存简历到本地存储，供后续使用"""
    meta = _load_metadata()
    resume_id = str(uuid.uuid4())[:8]
    record = {
        "id": resume_id,
        "filename": req.filename,
        "text": req.text,
        "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "char_count": len(req.text),
    }
    meta["resumes"].insert(0, record)  # 最新在前
    # 最多保留20份
    meta["resumes"] = meta["resumes"][:20]
    _save_metadata(meta)
    return {"id": resume_id, "saved_at": record["saved_at"]}


@router.get("/saved-resumes")
def list_saved_resumes():
    """列出所有已保存的简历"""
    meta = _load_metadata()
    return [
        {"id": r["id"], "filename": r["filename"], "saved_at": r["saved_at"], "char_count": r["char_count"]}
        for r in meta["resumes"]
    ]


@router.delete("/saved-resumes/{resume_id}")
def delete_saved_resume(resume_id: str):
    """删除已保存的简历"""
    meta = _load_metadata()
    original = len(meta["resumes"])
    meta["resumes"] = [r for r in meta["resumes"] if r["id"] != resume_id]
    if len(meta["resumes"]) == original:
        return JSONResponse({"error": "简历不存在"}, status_code=404)
    _save_metadata(meta)
    return {"ok": True}


@router.get("/saved-resumes/{resume_id}")
def get_saved_resume(resume_id: str):
    """获取指定简历的完整内容"""
    meta = _load_metadata()
    for r in meta["resumes"]:
        if r["id"] == resume_id:
            return {"id": r["id"], "filename": r["filename"], "text": r["text"], "saved_at": r["saved_at"]}
    return JSONResponse({"error": "简历不存在"}, status_code=404)


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

    if not resume_text.strip():
        return JSONResponse({"error": "请上传或粘贴简历内容"}, status_code=400)

    jd_clean = clean_text(jd_text)
    resume_clean = clean_text(resume_text)

    # 自动保存简历
    if req.auto_save_resume and resume_clean:
        try:
            meta = _load_metadata()
            # 检查是否内容完全相同，已保存则不重复存
            duplicate = any(r["text"] == resume_clean for r in meta["resumes"])
            if not duplicate:
                resume_id = str(uuid.uuid4())[:8]
                record = {
                    "id": resume_id,
                    "filename": "简历",
                    "text": resume_clean,
                    "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "char_count": len(resume_clean),
                }
                meta["resumes"].insert(0, record)
                meta["resumes"] = meta["resumes"][:20]
                _save_metadata(meta)
        except Exception:
            pass  # 保存失败不影响主流程

    # 在线程池执行，避免阻塞事件循环
    result = await asyncio.to_thread(analyze_preparation, jd_clean, resume_clean)
    return result
