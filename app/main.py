"""FastAPI 主入口"""
import os
from pathlib import Path

from dotenv import load_dotenv

# 显式加载项目根目录的 .env 文件
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse

from app.routers import preparation, mockInterview, review

app = FastAPI(title="Interview System", version="1.0.0")
app.mount("/static", StaticFiles(directory=Path(__file__).resolve().parent / "static"), name="static")

# 注册路由
app.include_router(preparation.router)
app.include_router(mockInterview.router)
app.include_router(review.router)


@app.get("/")
async def root():
    """重定向到前端页面"""
    return RedirectResponse(url="/static/index.html")


if __name__ == "__main__":
    import uvicorn
    from app.config import HOST, PORT
    uvicorn.run("app.main:app", host=HOST, port=PORT, reload=True)
