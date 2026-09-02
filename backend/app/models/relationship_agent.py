"""
关系人 Agent 人格卡存储
存储于项目目录：uploads/projects/{project_id}/relationship_agents/
- relationship_agents.json   当前人格卡集合
- history/                   历史批次归档（按时间戳命名）
"""

import json
import os
from datetime import datetime
from typing import Any, Dict, Optional

from ..models.project import ProjectManager
from ..utils.logger import get_logger

logger = get_logger('prism.relationship.store')


class RelationshipAgentStore:
    """关系人人格卡文件式存储（沿用 BranchStore 惯例）"""

    @classmethod
    def _agents_dir(cls, project_id: str) -> str:
        return os.path.join(
            ProjectManager._get_project_dir(project_id), 'relationship_agents'
        )

    @classmethod
    def _current_path(cls, project_id: str) -> str:
        return os.path.join(cls._agents_dir(project_id), 'relationship_agents.json')

    @classmethod
    def save(cls, project_id: str, data: Dict[str, Any]) -> None:
        """保存当前人格卡集合，并把上一批归档到 history/"""
        agents_dir = cls._agents_dir(project_id)
        history_dir = os.path.join(agents_dir, 'history')
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
            f"保存人格卡集合: project={project_id}, cards={len(payload.get('cards') or [])}"
        )

    @classmethod
    def get_current(cls, project_id: str) -> Optional[Dict[str, Any]]:
        path = cls._current_path(project_id)
        if not os.path.exists(path):
            return None
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            logger.error(f"读取人格卡失败: {path}, {e}")
            return None

    # ------------------------------------------------------------------
    # Correction 纠错回路：用户对人格卡的现场纠正，独立于人格卡版本存在
    # ------------------------------------------------------------------

    @classmethod
    def _corrections_path(cls, project_id: str) -> str:
        return os.path.join(cls._agents_dir(project_id), 'corrections.json')

    @classmethod
    def get_corrections(cls, project_id: str) -> Dict[str, list]:
        """读取全部纠错记录：{ person_ref: [ {scene, wrong, correct, created_at} ] }"""
        path = cls._corrections_path(project_id)
        if not os.path.exists(path):
            return {}
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except (OSError, json.JSONDecodeError) as e:
            logger.error(f"读取纠错记录失败: {path}, {e}")
            return {}

    @classmethod
    def add_correction(cls, project_id: str, person_ref: str,
                       scene: str, wrong: str, correct: str) -> Dict[str, Any]:
        """追加一条纠错（Distilly correction 结构：scene/wrong/correct）"""
        if not person_ref or not correct:
            raise ValueError("person_ref 与 correct 不能为空")

        corrections = cls.get_corrections(project_id)
        records = corrections.setdefault(person_ref, [])
        records.append({
            "scene": scene or "",
            "wrong": wrong or "",
            "correct": correct,
            "created_at": datetime.now().isoformat(),
        })

        # 维护规则（化用 Distilly）：每人上限 50 条，超出合并最旧两条语义相近记录
        if len(records) > 50:
            records = records[-50:]

        corrections[person_ref] = records
        cls._write_corrections(project_id, corrections)
        logger.info(f"追加纠错: project={project_id}, person={person_ref}, total={len(records)}")
        return corrections[person_ref][-1]

    @classmethod
    def delete_correction(cls, project_id: str, person_ref: str, index: int) -> None:
        """删除指定纠错记录（按列表下标）"""
        corrections = cls.get_corrections(project_id)
        records = corrections.get(person_ref) or []
        if index < 0 or index >= len(records):
            raise IndexError(f"纠错记录不存在: person={person_ref}, index={index}")
        records.pop(index)
        if records:
            corrections[person_ref] = records
        else:
            corrections.pop(person_ref, None)
        cls._write_corrections(project_id, corrections)
        logger.info(f"删除纠错: project={project_id}, person={person_ref}, index={index}")

    @classmethod
    def _write_corrections(cls, project_id: str, corrections: Dict[str, list]) -> None:
        agents_dir = cls._agents_dir(project_id)
        os.makedirs(agents_dir, exist_ok=True)
        with open(cls._corrections_path(project_id), 'w', encoding='utf-8') as f:
            json.dump(corrections, f, ensure_ascii=False, indent=2)
