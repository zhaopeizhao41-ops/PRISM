"""
现实行动实验存储。

行动实验是推演结果落地后的用户记录，不调用 LLM，也不会自动写回个人画像。
数据按项目隔离保存于 uploads/projects/{project_id}/action_experiments.json。
"""

import json
import os
import tempfile
import threading
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..models.project import ProjectManager
from ..utils.logger import get_logger

logger = get_logger('prism.action_experiment.store')
_locks: dict[str, threading.RLock] = {}
_locks_guard = threading.Lock()


def _project_lock(project_id: str) -> threading.RLock:
    with _locks_guard:
        return _locks.setdefault(project_id, threading.RLock())


class ActionExperimentStore:
    """项目级行动实验文件存储，采用原子替换避免半写入文件。"""

    @classmethod
    def _path(cls, project_id: str) -> str:
        return os.path.join(
            ProjectManager._get_project_dir(project_id),
            'action_experiments.json',
        )

    @classmethod
    def _read(cls, project_id: str) -> List[Dict[str, Any]]:
        path = cls._path(project_id)
        if not os.path.exists(path):
            return []
        try:
            with _project_lock(project_id), open(path, 'r', encoding='utf-8') as f:
                payload = json.load(f)
            experiments = payload.get('experiments', []) if isinstance(payload, dict) else payload
            return [item for item in experiments if isinstance(item, dict)]
        except (OSError, json.JSONDecodeError) as exc:
            logger.error('读取行动实验失败: project=%s, %s', project_id, exc)
            return []

    @classmethod
    def _write(cls, project_id: str, experiments: List[Dict[str, Any]]) -> None:
        path = cls._path(project_id)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        fd, tmp = tempfile.mkstemp(
            prefix='.action-experiments-',
            suffix='.tmp',
            dir=os.path.dirname(path),
        )
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                json.dump(
                    {'schema_version': 1, 'experiments': experiments},
                    f,
                    ensure_ascii=False,
                    indent=2,
                )
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, path)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

    @classmethod
    def list(cls, project_id: str) -> List[Dict[str, Any]]:
        experiments = cls._read(project_id)
        return sorted(
            experiments,
            key=lambda item: item.get('created_at') or '',
            reverse=True,
        )

    @classmethod
    def get(cls, project_id: str, experiment_id: str) -> Optional[Dict[str, Any]]:
        return next(
            (item for item in cls._read(project_id)
             if item.get('experiment_id') == experiment_id),
            None,
        )

    @classmethod
    def create(cls, project_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        now = datetime.now().isoformat()
        experiment = {
            'experiment_id': f"exp_{uuid.uuid4().hex[:12]}",
            'project_id': project_id,
            'schema_version': 1,
            'title': payload['title'],
            'horizon_days': payload['horizon_days'],
            'goal': payload['goal'],
            'minimum_action': payload['minimum_action'],
            'success_metric': payload['success_metric'],
            'stop_condition': payload.get('stop_condition', ''),
            'expected_cost': payload.get('expected_cost', ''),
            'review_date': payload['review_date'],
            'source_session_id': payload.get('source_session_id'),
            'source_summary': payload.get('source_summary', ''),
            'status': 'planned',
            'retrospective': None,
            'created_at': now,
            'updated_at': now,
        }
        with _project_lock(project_id):
            experiments = cls._read(project_id)
            experiments.append(experiment)
            cls._write(project_id, experiments)
        return experiment

    @classmethod
    def update(
        cls,
        project_id: str,
        experiment_id: str,
        changes: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        with _project_lock(project_id):
            experiments = cls._read(project_id)
            target = next(
                (item for item in experiments
                 if item.get('experiment_id') == experiment_id),
                None,
            )
            if target is None:
                return None
            target.update(changes)
            target['updated_at'] = datetime.now().isoformat()
            cls._write(project_id, experiments)
            return target

    @classmethod
    def delete(cls, project_id: str, experiment_id: str) -> bool:
        with _project_lock(project_id):
            experiments = cls._read(project_id)
            remaining = [
                item for item in experiments
                if item.get('experiment_id') != experiment_id
            ]
            if len(remaining) == len(experiments):
                return False
            cls._write(project_id, remaining)
            return True
