from __future__ import annotations

import logging
from pathlib import Path

from dotenv import load_dotenv

# 必须在导入 settings 之前加载 .env
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.ai_routes import router as ai_router
from app.api.auth_routes import router as auth_router
from app.api.billing_routes import router as billing_router
from app.api.routes import router

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
app.include_router(auth_router)
app.include_router(billing_router)


@app.get("/health")
def health() -> dict:
    import os

    return {
        "status": "ok",
        "pid": os.getpid(),
        "version": "1.1.0",
        "features": ["download", "ai", "auth", "billing"],
    }
