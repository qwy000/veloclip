"""进程内任务表与临时目录管理（无数据库的轻量方案）。"""
from __future__ import annotations

import shutil
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# 所有任务的临时输出根目录
DOWNLOAD_ROOT = Path(__file__).resolve().parents[2] / "downloads"
DOWNLOAD_ROOT.mkdir(parents=True, exist_ok=True)

# 任务超过该时长（秒）后，其临时文件可被清理
TASK_TTL_SECONDS = 30 * 60


@dataclass
class Task:
    task_id: str
    status: str = "queued"  # queued | downloading | processing | finished | error | cancelled
    percent: float = 0.0
    speed: Optional[str] = None
    eta: Optional[str] = None
    filepath: Optional[str] = None
    filename: Optional[str] = None
    error: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    _cancel_event: threading.Event = field(default_factory=threading.Event)

    @property
    def is_cancelled(self) -> bool:
        return self._cancel_event.is_set()

    def cancel(self) -> None:
        self._cancel_event.set()

    @property
    def workdir(self) -> Path:
        return DOWNLOAD_ROOT / self.task_id


class TaskStore:
    def __init__(self) -> None:
        self._tasks: dict[str, Task] = {}
        self._lock = threading.Lock()

    def create(self, task_id: str) -> Task:
        with self._lock:
            task = Task(task_id=task_id)
            task.workdir.mkdir(parents=True, exist_ok=True)
            self._tasks[task_id] = task
            return task

    def get(self, task_id: str) -> Optional[Task]:
        with self._lock:
            return self._tasks.get(task_id)

    def update(self, task_id: str, **fields) -> None:
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return
            for key, value in fields.items():
                setattr(task, key, value)

    def cleanup_expired(self) -> None:
        """删除过期任务的临时目录，释放磁盘。"""
        now = time.time()
        with self._lock:
            expired = [
                t for t in self._tasks.values()
                if now - t.created_at > TASK_TTL_SECONDS
            ]
            for task in expired:
                shutil.rmtree(task.workdir, ignore_errors=True)
                self._tasks.pop(task.task_id, None)

    def remove(self, task_id: str) -> None:
        with self._lock:
            task = self._tasks.pop(task_id, None)
        if task:
            shutil.rmtree(task.workdir, ignore_errors=True)


store = TaskStore()
