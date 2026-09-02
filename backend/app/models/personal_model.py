"""
个人模型存储
版本化快照存储于项目目录：uploads/projects/{project_id}/personal_models/
- personal_model.json   当前版本（分支层唯一消费入口）
- versions/v{n}.json    历史版本归档
"""

import json
import os
import shutil
from typing import Any, Dict, List, Optional

from ..models.project import ProjectManager
from ..utils.logger import get_logger

logger = get_logger('prism.profile.model_store')


class PersonalModelStore:
    """个人模型版本化存储（仿 ProjectManager 的文件式存储惯例）"""

    @classmethod
    def _models_dir(cls, project_id: str) -> str:
        return os.path.join(
            ProjectManager._get_project_dir(project_id), 'personal_models'
        )

    @classmethod
    def _versions_dir(cls, project_id: str) -> str:
        return os.path.join(cls._models_dir(project_id), 'versions')

    @classmethod
    def _current_path(cls, project_id: str) -> str:
        return os.path.join(cls._models_dir(project_id), 'personal_model.json')

    @classmethod
    def save(cls, project_id: str, model: Dict[str, Any]) -> None:
        """保存模型：写入当前版本并归档历史版本"""
        models_dir = cls._models_dir(project_id)
        versions_dir = cls._versions_dir(project_id)
        os.makedirs(versions_dir, exist_ok=True)

        version = int(model.get("model_version", 1))
        version_path = os.path.join(versions_dir, f"v{version}.json")
        with open(version_path, 'w', encoding='utf-8') as f:
            json.dump(model, f, ensure_ascii=False, indent=2)

        current_path = cls._current_path(project_id)
        with open(current_path, 'w', encoding='utf-8') as f:
            json.dump(model, f, ensure_ascii=False, indent=2)

        logger.info(
            f"保存个人模型: project={project_id}, version=v{version}"
        )

    @classmethod
    def get_current(cls, project_id: str) -> Optional[Dict[str, Any]]:
        """获取当前版本模型"""
        path = cls._current_path(project_id)
        if not os.path.exists(path):
            return None
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            logger.error(f"读取个人模型失败: {path}, {e}")
            return None

    @classmethod
    def get_version(cls, project_id: str, version: int) -> Optional[Dict[str, Any]]:
        """获取指定历史版本"""
        path = os.path.join(cls._versions_dir(project_id), f"v{version}.json")
        if not os.path.exists(path):
            return None
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            logger.error(f"读取个人模型版本失败: {path}, {e}")
            return None

    @classmethod
    def list_versions(cls, project_id: str) -> List[int]:
        """列出全部版本号（升序）"""
        versions_dir = cls._versions_dir(project_id)
        if not os.path.isdir(versions_dir):
            return []
        versions = []
        for filename in os.listdir(versions_dir):
            if filename.startswith('v') and filename.endswith('.json'):
                try:
                    versions.append(int(filename[1:-5]))
                except ValueError:
                    continue
        return sorted(versions)

    @classmethod
    def next_version(cls, project_id: str) -> int:
        """下一个版本号（无历史时为 1）"""
        versions = cls.list_versions(project_id)
        return (versions[-1] + 1) if versions else 1
