"""
人生分支存储
存储于项目目录：uploads/projects/{project_id}/branches/
- branches.json   最新一批分支（含 source_model_version 关联）
- history/        历史批次归档（按时间戳命名）
"""

import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..models.project import ProjectManager
from ..utils.logger import get_logger

logger = get_logger('prism.branch.store')


class BranchStore:
    """人生分支文件式存储（沿用项目目录惯例）"""

    @classmethod
    def _branches_dir(cls, project_id: str) -> str:
        return os.path.join(ProjectManager._get_project_dir(project_id), 'branches')

    @classmethod
    def _current_path(cls, project_id: str) -> str:
        return os.path.join(cls._branches_dir(project_id), 'branches.json')

    @classmethod
    def save(cls, project_id: str, data: Dict[str, Any]) -> None:
        """保存最新批次，并把上一批归档到 history/"""
        branches_dir = cls._branches_dir(project_id)
        history_dir = os.path.join(branches_dir, 'history')
        os.makedirs(history_dir, exist_ok=True)

        current_path = cls._current_path(project_id)
        if os.path.exists(current_path):
            with open(current_path, 'r', encoding='utf-8') as f:
                previous = json.load(f)
            created = previous.get("created_at", "").replace(":", "").replace("-", "")[:15]
            if created:
                archive_path = os.path.join(history_dir, f"{created}.json")
                with open(archive_path, 'w', encoding='utf-8') as f:
                    json.dump(previous, f, ensure_ascii=False, indent=2)

        payload = dict(data)
        payload["created_at"] = datetime.now().isoformat()
        with open(current_path, 'w', encoding='utf-8') as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

        logger.info(
            f"保存分支批次: project={project_id}, branches={payload.get('branch_count')}"
        )

    @classmethod
    def get_current(cls, project_id: str) -> Optional[Dict[str, Any]]:
        """获取最新分支批次"""
        path = cls._current_path(project_id)
        if not os.path.exists(path):
            return None
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            logger.error(f"读取分支失败: {path}, {e}")
            return None
