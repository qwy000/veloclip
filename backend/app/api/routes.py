from __future__ import annotations

import uuid
from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.core.tasks import store
from app.models.schemas import (
    DownloadRequest,
    DownloadResponse,
    InfoRequest,
    InfoResponse,
    ProgressResponse,
)
from app.services import downloader

router = APIRouter(prefix="/api")

# 下载为阻塞操作，放入线程池，避免阻塞事件循环
_executor = ThreadPoolExecutor(max_workers=4)


@router.post("/info", response_model=InfoResponse)
def get_info(req: InfoRequest) -> InfoResponse:
    url = req.url.strip()
    if not url:
        raise HTTPException(status_code=400, detail="请输入视频链接")
    # 借正常解析请求顺带清理过期临时文件（无数据库的轻量清理策略）
    store.cleanup_expired()
    try:
        return downloader.extract_info(url)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=422, detail=downloader._friendly_error(str(exc)))


@router.post("/download", response_model=DownloadResponse)
def start_download(req: DownloadRequest) -> DownloadResponse:
    url = req.url.strip()
    if not url:
        raise HTTPException(status_code=400, detail="请输入视频链接")
    store.cleanup_expired()
    task_id = uuid.uuid4().hex
    store.create(task_id)
    _executor.submit(downloader.run_download, task_id, url, req.quality)
    return DownloadResponse(task_id=task_id)


@router.get("/progress/{task_id}", response_model=ProgressResponse)
def get_progress(task_id: str) -> ProgressResponse:
    task = store.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在或已过期")
    return ProgressResponse(
        status=task.status,
        percent=task.percent,
        speed=task.speed,
        eta=task.eta,
        filename=task.filename,
        error=task.error,
    )


@router.post("/cancel/{task_id}")
def cancel_download(task_id: str):
    task = store.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在或已过期")
    task.cancel()
    store.update(task_id, status="cancelled", error="下载已取消")
    return {"status": "ok"}


@router.get("/file/{task_id}")
def get_file(task_id: str):
    task = store.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在或已过期")
    if task.status != "finished" or not task.filepath:
        raise HTTPException(status_code=409, detail="文件尚未准备好")
    return FileResponse(
        path=task.filepath,
        filename=task.filename,
        media_type="application/octet-stream",
    )
