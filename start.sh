#!/bin/zsh
set -euo pipefail

cd /Users/apple/interview-system

if [[ ! -d .venv ]]; then
  /Users/apple/.local/bin/python3.11 -m venv .venv
fi

# 显式用 venv 的 Python，避免用错系统 Python（必须用 venv 里的 PyMuPDF/pytesseract/docx）
exec /Users/apple/interview-system/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000