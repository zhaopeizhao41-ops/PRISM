"""
圆桌记录存储
存储于项目目录：uploads/projects/{project_id}/roundtables/
- {dialog_id}.json   每场圆桌一个文件（transcript 逐条追加 + moderation）
对话不回写宇宙状态（因果隔离，用户已确认）。
"""

import json
import os
import uuid
from typing import Any, Dict, List, Optional

from ..models.project import ProjectManager
from ..utils.logger import get_logger

logger = get_logger('prism.roundtable.store')


class RoundtableStore:
    """圆桌记录文件式存储"""

    @classmethod
    def _dir(cls, project_id: str) -> str:
        return os.path.join(
            ProjectManager._get_project_dir(project_id), 'roundtables'
        )

    @classmethod
    def _path(cls, project_id: str, dialog_id: str) -> str:
        return os.path.join(cls._dir(project_id), f"{dialog_id}.json")

    @classmethod
    def save(cls, dialog: Dict[str, Any]) -> None:
        """保存（剥离 _card 等运行时字段）"""
        project_id = dialog["project_id"]
        os.makedirs(cls._dir(project_id), exist_ok=True)
        payload = {
            k: v for k, v in dialog.items() if not k.startswith("_")
        }
        clean_participants = []
        for p in payload.get("participants") or []:
            clean_participants.append({
                k: v for k, v in p.items() if not k.startswith("_")
            })
        payload["participants"] = clean_participants
        with open(cls._path(project_id, dialog["dialog_id"]), 'w', encoding='utf-8') as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

    @classmethod
    def get(cls, project_id: str, dialog_id: str) -> Optional[Dict[str, Any]]:
        path = cls._path(project_id, dialog_id)
        if not os.path.exists(path):
            return None
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            logger.error(f"读取圆桌记录失败: {path}, {e}")
            return None

    @classmethod
    def list_dialogs(cls, project_id: str) -> List[Dict[str, Any]]:
        """项目全部圆桌摘要（按时间倒序）"""
        dialogs_dir = cls._dir(project_id)
        if not os.path.isdir(dialogs_dir):
            return []
        dialogs = []
        for filename in os.listdir(dialogs_dir):
            if not (filename.startswith('rt_') and filename.endswith('.json')):
                continue
            try:
                with open(os.path.join(dialogs_dir, filename), 'r', encoding='utf-8') as f:
                    d = json.load(f)
                dialogs.append({
                    "dialog_id": d.get("dialog_id"),
                    "topic": d.get("topic"),
                    "status": d.get("status"),
                    "participant_count": len(d.get("participants") or []),
                    "speech_count": len(d.get("transcript") or []),
                    "has_moderation": bool(d.get("moderation")),
                    "created_at": d.get("created_at"),
                })
            except (OSError, json.JSONDecodeError) as e:
                logger.warning(f"跳过损坏的圆桌文件: {filename}, {e}")
        dialogs.sort(key=lambda d: d.get("created_at") or "", reverse=True)
        return dialogs

    @classmethod
    def delete(cls, project_id: str, dialog_id: str) -> bool:
        """删除单场圆桌记录"""
        path = cls._path(project_id, dialog_id)
        if os.path.exists(path):
            try:
                os.remove(path)
                return True
            except OSError as e:
                logger.error(f"删除圆桌记录失败: {path}, {e}")
                return False
        return False
