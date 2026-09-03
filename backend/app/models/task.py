"""
任务状态管理
用于跟踪长时间运行的任务（如图谱构建）
"""

import uuid
import threading
import json
import os
import tempfile
from contextlib import contextmanager
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, Any, Optional
from dataclasses import dataclass, field

from ..utils.locale import t
from ..config import Config


class TaskStatus(str, Enum):
    """任务状态枚举"""
    PENDING = "pending"          # 等待中
    PROCESSING = "processing"    # 处理中
    COMPLETED = "completed"      # 已完成
    FAILED = "failed"            # 失败
    CANCELLED = "cancelled"
    STALE = "stale"


@dataclass
class Task:
    """任务数据类"""
    task_id: str
    task_type: str
    status: TaskStatus
    created_at: datetime
    updated_at: datetime
    progress: int = 0              # 总进度百分比 0-100
    message: str = ""              # 状态消息
    result: Optional[Dict] = None  # 任务结果
    error: Optional[str] = None    # 错误信息
    metadata: Dict = field(default_factory=dict)  # 额外元数据
    progress_detail: Dict = field(default_factory=dict)  # 详细进度信息
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "progress": self.progress,
            "message": self.message,
            "progress_detail": self.progress_detail,
            "result": self.result,
            "error": self.error,
            "metadata": self.metadata,
        }


class TaskManager:
    """
    任务管理器
    线程安全的任务状态管理
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        """单例模式"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._tasks: Dict[str, Task] = {}
                    cls._instance._cancel_events: Dict[str, threading.Event] = {}
                    cls._instance._task_lock = threading.Lock()
                    cls._instance._load_persisted()
        return cls._instance

    @property
    def _task_path(self) -> str:
        path = os.path.join(Config.UPLOAD_FOLDER, "tasks.json")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        return path

    def _load_persisted(self) -> None:
        with self._task_lock:
            self._merge_persisted_locked()

    @contextmanager
    def _file_lock(self):
        """Serialize task-file replacement across worker processes."""
        lock_path = self._task_path + ".lock"
        os.makedirs(os.path.dirname(lock_path), exist_ok=True)
        with open(lock_path, "a+b") as lock_file:
            lock_file.seek(0)
            if os.name == "nt":
                import msvcrt
                lock_file.write(b"0")
                lock_file.flush()
                lock_file.seek(0)
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_LOCK, 1)
            else:
                import fcntl
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                if os.name == "nt":
                    import msvcrt
                    lock_file.seek(0)
                    msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

    def _merge_persisted_locked(self) -> None:
        """Merge newer disk records without clobbering local updates."""
        try:
            with open(self._task_path, "r", encoding="utf-8") as f:
                records = json.load(f)
        except (OSError, ValueError, json.JSONDecodeError):
            return
        for record in records if isinstance(records, list) else []:
            try:
                task_id = record["task_id"]
                disk_updated = datetime.fromisoformat(record["updated_at"])
                local = self._tasks.get(task_id)
                if local and local.updated_at >= disk_updated:
                    continue
                self._tasks[task_id] = Task(
                    task_id=task_id, task_type=record.get("task_type", ""),
                    status=TaskStatus(record.get("status", "failed")),
                    created_at=datetime.fromisoformat(record["created_at"]),
                    updated_at=disk_updated,
                    progress=record.get("progress", 0), message=record.get("message", ""),
                    result=record.get("result"), error=record.get("error"),
                    metadata=record.get("metadata") or {}, progress_detail=record.get("progress_detail") or {},
                )
                self._cancel_events.setdefault(task_id, threading.Event())
                if self._tasks[task_id].status == TaskStatus.CANCELLED:
                    self._cancel_events[task_id].set()
            except (KeyError, ValueError, TypeError):
                continue

    def _persist_locked(self) -> None:
        path = self._task_path
        with self._file_lock():
            self._merge_persisted_locked()
            fd, tmp = tempfile.mkstemp(prefix=".tasks-", suffix=".tmp", dir=os.path.dirname(path))
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump([task.to_dict() for task in self._tasks.values()], f, ensure_ascii=False, indent=2)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(tmp, path)
            finally:
                if os.path.exists(tmp):
                    os.unlink(tmp)
    
    def create_task(self, task_type: str, metadata: Optional[Dict] = None) -> str:
        """
        创建新任务
        
        Args:
            task_type: 任务类型
            metadata: 额外元数据
            
        Returns:
            任务ID
        """
        task_id = str(uuid.uuid4())
        now = datetime.now()
        
        task = Task(
            task_id=task_id,
            task_type=task_type,
            status=TaskStatus.PENDING,
            created_at=now,
            updated_at=now,
            metadata=metadata or {}
        )
        
        with self._task_lock:
            self._tasks[task_id] = task
            self._cancel_events[task_id] = threading.Event()
            self._persist_locked()
        
        return task_id
    
    def get_task(self, task_id: str) -> Optional[Task]:
        """获取任务"""
        with self._task_lock:
            task = self._tasks.get(task_id)
            if task and task.status in {TaskStatus.PENDING, TaskStatus.PROCESSING}:
                if datetime.now() - task.updated_at > timedelta(minutes=30):
                    task.status = TaskStatus.STALE
                    task.message = "任务超过心跳期限"
                    task.error = "stale task"
                    self._persist_locked()
            return task
    
    def update_task(
        self,
        task_id: str,
        status: Optional[TaskStatus] = None,
        progress: Optional[int] = None,
        message: Optional[str] = None,
        result: Optional[Dict] = None,
        error: Optional[str] = None,
        progress_detail: Optional[Dict] = None
    ):
        """
        更新任务状态
        
        Args:
            task_id: 任务ID
            status: 新状态
            progress: 进度
            message: 消息
            result: 结果
            error: 错误信息
            progress_detail: 详细进度信息
        """
        with self._task_lock:
            task = self._tasks.get(task_id)
            if task:
                # A cancelled task is terminal. Background workers may still
                # return from an in-flight API call, but must not resurrect it.
                if task.status in {
                    TaskStatus.CANCELLED,
                    TaskStatus.STALE,
                    TaskStatus.FAILED,
                    TaskStatus.COMPLETED,
                }:
                    return False
                task.updated_at = datetime.now()
                if status is not None:
                    task.status = status
                if progress is not None:
                    task.progress = progress
                if message is not None:
                    task.message = message
                if result is not None:
                    task.result = result
                if error is not None:
                    task.error = error
                if progress_detail is not None:
                    task.progress_detail = progress_detail
                self._persist_locked()
                return True
        return False

    def cancel_task(self, task_id: str, reason: str = "任务已取消") -> Optional[Task]:
        """Request cancellation and publish a terminal cancelled state."""
        with self._task_lock:
            task = self._tasks.get(task_id)
            if not task:
                return None
            if task.status in {TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.STALE, TaskStatus.CANCELLED}:
                return task
            task.status = TaskStatus.CANCELLED
            task.updated_at = datetime.now()
            task.message = reason
            task.error = reason
            self._cancel_events.setdefault(task_id, threading.Event()).set()
            self._persist_locked()
            return task

    def is_cancelled(self, task_id: str) -> bool:
        """Return whether a worker should stop at its next safe checkpoint."""
        with self._task_lock:
            task = self._tasks.get(task_id)
            return bool(task and task.status == TaskStatus.CANCELLED)

    def recover_interrupted_tasks(self, max_idle_seconds: int = 120) -> int:
        """Mark active tasks with no recent heartbeat as stale at startup."""
        cutoff = datetime.now() - timedelta(seconds=max_idle_seconds)
        recovered = 0
        with self._task_lock:
            for task in self._tasks.values():
                if task.status in {TaskStatus.PENDING, TaskStatus.PROCESSING} and task.updated_at < cutoff:
                    task.status = TaskStatus.STALE
                    task.message = "服务重启后任务未恢复"
                    task.error = "interrupted task"
                    recovered += 1
            if recovered:
                self._persist_locked()
        return recovered
    
    def complete_task(self, task_id: str, result: Dict):
        """标记任务完成"""
        self.update_task(
            task_id,
            status=TaskStatus.COMPLETED,
            progress=100,
            message=t('progress.taskComplete'),
            result=result
        )
    
    def fail_task(self, task_id: str, error: str):
        """标记任务失败"""
        self.update_task(
            task_id,
            status=TaskStatus.FAILED,
            message=t('progress.taskFailed'),
            error=error
        )
    
    def list_tasks(self, task_type: Optional[str] = None) -> list:
        """列出任务"""
        with self._task_lock:
            tasks = list(self._tasks.values())
            if task_type:
                tasks = [t for t in tasks if t.task_type == task_type]
            return [t.to_dict() for t in sorted(tasks, key=lambda x: x.created_at, reverse=True)]
    
    def cleanup_old_tasks(self, max_age_hours: int = 24):
        """清理旧任务"""
        from datetime import timedelta
        cutoff = datetime.now() - timedelta(hours=max_age_hours)
        
        with self._task_lock:
            old_ids = [
                tid for tid, task in self._tasks.items()
                if task.created_at < cutoff and task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED, TaskStatus.STALE]
            ]
            for tid in old_ids:
                del self._tasks[tid]
                self._cancel_events.pop(tid, None)
            self._persist_locked()

