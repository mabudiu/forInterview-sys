"""文件解析服务：支持 PDF、DOCX、图片(OCR)"""
import re
from io import BytesIO
from typing import Optional

import fitz  # PyMuPDF
from docx import Document
import pytesseract
from PIL import Image


def extract_text_from_pdf(file_bytes: bytes) -> str:
    """从 PDF 提取文本"""
    text_parts = []
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    for page in doc:
        t = page.get_text()
        if t.strip():
            text_parts.append(t)
    doc.close()
    return "\n".join(text_parts)


def extract_text_from_docx(file_bytes: bytes) -> str:
    """从 DOCX 提取文本"""
    doc = Document(BytesIO(file_bytes))
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    return "\n".join(paragraphs)


def extract_text_from_image(file_bytes: bytes) -> str:
    """从图片(PNG/JPG)通过 OCR 提取文本"""
    img = Image.open(BytesIO(file_bytes))
    text = pytesseract.image_to_string(img, lang="chi+eng")
    return text


def extract_text(file_bytes: bytes, filename: str) -> str:
    """根据文件扩展名自动分发"""
    ext = filename.lower().split(".")[-1]
    if ext == "pdf":
        return extract_text_from_pdf(file_bytes)
    elif ext in ("docx", "doc"):
        return extract_text_from_docx(file_bytes)
    elif ext in ("png", "jpg", "jpeg", "gif", "bmp"):
        return extract_text_from_image(file_bytes)
    else:
        return file_bytes.decode("utf-8", errors="replace")


def clean_text(text: str) -> str:
    """简单清洗：去除多余空白"""
    lines = [l.strip() for l in text.splitlines()]
    return "\n".join(l for l in lines if l)
