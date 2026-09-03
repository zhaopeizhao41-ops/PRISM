"""
推演会话存储
存储于项目目录：uploads/projects/{project_id}/evolutions/
- {session_id}.json   每个推演会话一个文件（含 stage_history / forks / user_events）
"""

import json
import os
import threading
import tempfile
from typing import Any, Dict, List, Optional

from ..models.project import ProjectManager
from ..utils.logger import get_logger

logger = get_logger('prism.evolution.store')
_locks: dict[str, threading.RLock] = {}
_locks_guard = threading.Lock()


def _session_lock(project_id: str, session_id: str) -> threading.RLock:
    key = f"{project_id}:{session_id}"
    with _locks_guard:
        return _locks.setdefault(key, threading.RLock())


class EvolutionStore:
    """推演会话文件式存储（沿用项目目录惯例）"""

    @classmethod
    def _sessions_dir(cls, project_id: str) -> str:
        return os.path.join(
            ProjectManager._get_project_dir(project_id), 'evolutions'
        )

    @classmethod
    def _session_path(cls, project_id: str, session_id: str) -> str:
        return os.path.join(cls._sessions_dir(project_id), f"{session_id}.json")

    @classmethod
    def save(cls, session: Dict[str, Any]) -> None:
        project_id = session["project_id"]
        os.makedirs(cls._sessions_dir(project_id), exist_ok=True)
        path = cls._session_path(project_id, session["session_id"])
        lock = _session_lock(project_id, session["session_id"])
        with lock:
            session.setdefault("schema_version", 2)
            session.setdefault("revision", 0)
            session["revision"] = int(session.get("revision", 0)) + 1
            fd, tmp = tempfile.mkstemp(prefix=".evo-", suffix=".tmp", dir=cls._sessions_dir(project_id))
            try:
                with os.fdopen(fd, 'w', encoding='utf-8') as f:
                    json.dump(session, f, ensure_ascii=False, indent=2)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(tmp, path)
            finally:
                if os.path.exists(tmp):
                    os.unlink(tmp)
        logger.debug(f"保存推演会话: {session['session_id']}")

    @classmethod
    def get(cls, project_id: str, session_id: str) -> Optional[Dict[str, Any]]:
        path = cls._session_path(project_id, session_id)
        if not os.path.exists(path):
            return None
        try:
            lock = _session_lock(project_id, session_id)
            with lock, open(path, 'r', encoding='utf-8') as f:
                session = json.load(f)
            # Lazy compatibility migration. The caller may save the enriched
            # object later; existing files are not rewritten on read.
            session.setdefault("schema_version", 1)
            session.setdefault("revision", 0)
            session.setdefault("breaker_episodes", {})
            session.setdefault("stage_runs", {})
            session.setdefault("legacy", session.get("schema_version", 1) < 2)
            return session
        except (OSError, json.JSONDecodeError) as e:
            logger.error(f"读取推演会话失败: {path}, {e}")
            return None

    @classmethod
    def list_sessions(cls, project_id: str) -> List[Dict[str, Any]]:
        """列出项目的全部会话（按创建时间倒序，返回摘要）"""
        sessions_dir = cls._sessions_dir(project_id)
        if not os.path.isdir(sessions_dir):
            return []
        sessions = []
        for filename in os.listdir(sessions_dir):
            if not (filename.startswith('evo_') and filename.endswith('.json')):
                continue
            try:
                with open(os.path.join(sessions_dir, filename), 'r', encoding='utf-8') as f:
                    session = json.load(f)
                sessions.append({
                    "session_id": session.get("session_id"),
                    "source_branch_archetype": session.get("source_branch_archetype"),
                    "source_branch_positioning": session.get("source_branch_positioning"),
                    "status": session.get("status"),
                    "stage_count": len(session.get("stage_plan") or []),
                    "stages_done": len(session.get("stage_history") or []),
                    "source_model_version": session.get("source_model_version"),
                    "created_at": session.get("created_at"),
                })
            except (OSError, json.JSONDecodeError) as e:
                logger.warning(f"跳过损坏的会话文件: {filename}, {e}")
        sessions.sort(key=lambda s: s.get("created_at") or "", reverse=True)
        return sessions
