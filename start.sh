#!/bin/zsh
set -euo pipefail

cd /Users/apple/interview-system

if [[ ! -d .venv ]]; then
  /Users/apple/.local/bin/python3.11 -m venv .venv
fi

source .venv/bin/activate
exec uvicorn app.main:app --host 0.0.0.0 --port 8000