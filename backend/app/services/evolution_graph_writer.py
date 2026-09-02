"""
推演图谱写入服务
把每个推演阶段的产出（事件、状态迁移）写入**独立的推演图谱**，
让图谱成为随推演实时"生长"的可观测视图。

为什么是独立图谱（而非写入主图谱）：
主图谱是"这个人真实传记"的唯一事实来源，画像蒸馏与关系人人格卡都从它读取。
若平行宇宙的推演事件写进主图谱，Zep 抽取的实体/事实会与真实传记混叠
（例如某宇宙里"作家回了信"会污染真实人生里"作家从未回信"的节点），
进而污染人格卡与圆桌证据。因此推演写入 project.evolution_graph_id 指向的
独立图谱，与主图谱物理隔离。

写入通道与 zep_graph_memory_updater 相同：client.graph.add(text)。
失败只记日志，绝不阻断推演主流程。
"""

import threading
import uuid
from typing import Any, Dict, List, Optional

from ..models.project import Project, ProjectManager
from ..utils.logger import get_logger
from ..utils.zep import get_zep_client

logger = get_logger('prism.evolution.graph_writer')

# world_state 维度的中文标签（写入文本用，帮助 Zep 抽取语义）
_DIM_LABELS = {
    "career": "事业",
    "family": "家庭",
    "resources": "资源",
    "psyche": "心理",
}

# 首次写入的懒创建锁（按项目；多个宇宙并行 advance 时避免重复建图）
_creation_locks: Dict[str, threading.Lock] = {}
_creation_locks_guard = threading.Lock()


def _creation_lock(project_id: str) -> threading.Lock:
    with _creation_locks_guard:
        return _creation_locks.setdefault(project_id, threading.Lock())


def _get_or_create_evolution_graph(project: Project) -> Optional[str]:
    """返回项目的推演图谱 ID；不存在时创建并持久化到项目。"""
    existing = getattr(project, "evolution_graph_id", None)
    if existing:
        return existing

    with _creation_lock(project.project_id):
        # 双重检查：等锁期间可能已被并发创建
        existing = getattr(project, "evolution_graph_id", None)
        if existing:
            return existing

        graph_id = f"prismevo_{uuid.uuid4().hex[:16]}"
        client = get_zep_client()
        client.graph.create(
            graph_id=graph_id,
            name=f"{project.name} 推演宇宙",
        )
        project.evolution_graph_id = graph_id
        ProjectManager.save_project(project)
        logger.info(f"已创建推演独立图谱: project={project.project_id} graph={graph_id}")
        return graph_id


def _build_stage_text(session: Dict[str, Any], entry: Dict[str, Any]) -> str:
    """把一个推演阶段转成 Zep 可抽取实体/关系的自然语言文本"""
    archetype = session.get("source_branch_archetype", "")
    positioning = session.get("source_branch_positioning", "")

    lines = [
        f"[平行宇宙推演 分支方向: {archetype}]",
        f"[分支定位: {positioning}]",
        f"[推演会话: {session.get('session_id', '')}]",
        f"[阶段 {entry.get('stage_index')}: {entry.get('stage_label', '')}]",
        "",
        "本阶段发生了以下事件（虚构推演，非真实人生）：",
    ]
    events: List[str] = entry.get("occurred_events") or []
    if events:
        lines.extend(f"- {e}" for e in events)
    else:
        lines.append("- （无明确事件）")

    snapshot = entry.get("state_snapshot", "")
    if snapshot:
        lines.extend(["", f"阶段结束时的状态：{snapshot}"])

    world_state: Dict[str, str] = entry.get("world_state") or {}
    state_parts = [
        f"{_DIM_LABELS.get(dim, dim)}: {val}"
        for dim, val in world_state.items()
        if val
    ]
    if state_parts:
        lines.extend(["", "世界状态：" + "；".join(state_parts)])

    divergence = entry.get("divergence_note")
    if divergence:
        lines.extend(["", f"与原定轨迹的偏离：{divergence}"])

    return "\n".join(lines)


def write_stage_to_graph(
    project: Project,
    session: Dict[str, Any],
    entry: Dict[str, Any],
) -> Optional[str]:
    """
    把一个已完成的推演阶段写入该项目的推演独立图谱（懒创建）。

    Returns:
        成功时返回 episode uuid；失败时返回 None（不抛异常）。
    """
    try:
        graph_id = _get_or_create_evolution_graph(project)
    except Exception as error:
        logger.warning(f"推演图谱创建失败（不影响推演）: {error}")
        return None

    text = _build_stage_text(session, entry)
    try:
        client = get_zep_client()
        episode = client.graph.add(
            graph_id=graph_id,
            type="text",
            data=text,
            source_description="PRISM parallel universe evolution",
            metadata={
                "source": "prism_evolution",
                "session_id": session.get("session_id", ""),
                "archetype": session.get("source_branch_archetype", ""),
                "stage_index": entry.get("stage_index", 0),
                "stage_label": entry.get("stage_label", ""),
            },
        )
        logger.info(
            f"推演阶段已写入独立图谱: session={session.get('session_id')} "
            f"stage={entry.get('stage_index')} graph={graph_id}"
        )
        return getattr(episode, "uuid", None)
    except Exception as error:
        logger.warning(f"推演图谱写入失败（不影响推演）: {error}")
        return None


def delete_evolution_graph(project: Project) -> None:
    """
    删除项目的推演独立图谱并清除引用（项目删除/重置/重建时调用，
    防止 Zep Cloud 遗留孤儿图谱）。失败只记日志。
    """
    graph_id = getattr(project, "evolution_graph_id", None)
    if not graph_id:
        return
    try:
        client = get_zep_client()
        client.graph.delete(graph_id=graph_id)
        logger.info(f"推演独立图谱已删除: {graph_id}")
    except Exception as error:
        logger.warning(f"推演图谱删除失败（继续清除引用）: {error}")
    finally:
        project.evolution_graph_id = None
