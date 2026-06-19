from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.ai_routes import router as ai_router
from app.api.routes import router

# 加载 backend/.env（若存在）
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

app = FastAPI(
    title="万能视频下载 API",
    description="基于 yt-dlp 封装的轻量视频下载服务",
    version="1.0.0",
)

# 开发期允许前端跨域访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
app.include_router(ai_router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
