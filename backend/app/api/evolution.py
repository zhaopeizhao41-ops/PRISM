"""
推演会话 API（同步单阶段设计：create/advance 各 1 次 LLM 调用，秒级返回）
/api/evolution/create              POST   从分支创建推演会话
/api/evolution/<session_id>        GET    获取会话（含全部 stage_history）
/api/evolution/<session_id>/advance POST   推进下一阶段（可携带 injected_event）
/api/evolution/<session_id>/fork    POST   裁决假设分叉
/api/evolution/<session_id>/event   POST   预约注入事件（下一阶段生效）
/api/evolution/<session_id>/abort   POST   终止会话
/api/evolution/list/<project_id>    GET    项目的全部会话摘要
"""

import traceback

from flask import jsonify, request

from . import evolution_bp
from ..utils.locale import t
from ..models.evolution import EvolutionStore
from ..models.personal_model import PersonalModelStore
from ..models.branch import BranchStore
from ..models.project import ProjectManager
from ..services.evolution_engine import EvolutionEngine
from ..utils.logger import get_logger

logger = get_logger('prism.api.evolution')


def _get_profile_project(project_id: str):
    """校验项目存在且为画像类型（与 branch.py 惯例一致）"""
    project = ProjectManager.get_project(project_id)
    if not project:
        return None, (jsonify({
            "success": False,
            "error": t('api.projectNotFound', id=project_id)
        }), 404)
    if getattr(project, 'project_type', None) != 'personal_profile':
        return None, (jsonify({
            "success": False,
            "error": "项目类型不是个人画像（personal_profile）"
        }), 400)
    return project, None


def _load_session(session_id: str):
    """按 session_id 定位会话（会话内含 project_id，无需路径参数）"""
    # session_id 全局唯一（uuid 后缀），但存储按项目分目录——先从请求体取 project_id，
    # 没有则扫描各画像项目目录
    data = request.get_json(silent=True) or {}
    project_id = data.get('project_id')
    if project_id:
        session = EvolutionStore.get(project_id, session_id)
        if session:
            return session, None
        return None, (jsonify({
            "success": False, "error": f"推演会话不存在: {session_id}"
        }), 404)

    # 扫描方案：遍历项目目录下的 evolutions/
    import os
    from ..models.project import ProjectManager as PM
    projects_root = PM.PROJECTS_DIR
    if os.path.isdir(projects_root):
        for dirname in os.listdir(projects_root):
            session = EvolutionStore.get(dirname, session_id)
            if session:
                return session, None
    return None, (jsonify({
        "success": False, "error": f"推演会话不存在: {session_id}"
    }), 404)


@evolution_bp.route('/create', methods=['POST'])
def create_session():
    """
    从某分支创建推演会话（同步，1 次 LLM 调用）

    请求（JSON）：{ "project_id": "proj_xxx", "branch_index": 0, "stage_count": 4 }
    """
    data = request.get_json(silent=True) or {}
    project_id = data.get('project_id')
    if not project_id:
        return jsonify({"success": False, "error": "project_id is required"}), 400

    project, error = _get_profile_project(project_id)
    if error:
        return error

    model = PersonalModelStore.get_current(project_id)
    if not model:
        return jsonify({
            "success": False,
            "error": "个人模型尚未生成，请先调用 /api/profile/model/generate"
        }), 400

    branches_data = BranchStore.get_current(project_id)
    if not branches_data:
        return jsonify({
            "success": False,
            "error": "分支尚未生成，请先调用 /api/branch/generate"
        }), 400

    branches = branches_data.get("branches") or []
    try:
        branch_index = int(data.get('branch_index', 0))
    except (TypeError, ValueError):
        branch_index = 0
    if not (0 <= branch_index < len(branches)):
        return jsonify({
            "success": False,
            "error": f"branch_index 无效（共 {len(branches)} 个分支）"
        }), 400

    try:
        stage_count = max(3, min(6, int(data.get('stage_count', 4))))
    except (TypeError, ValueError):
        stage_count = 4

    # 关系人卡片：作为 realism 账本的关系张力初始化来源
    try:
        from ..models.relationship_agent import RelationshipAgentStore
        rels_data = RelationshipAgentStore.get_current(project_id) or {}
        relationship_cards_raw = rels_data.get("cards") or []
        if isinstance(relationship_cards_raw, list):
            relationship_cards = [c for c in relationship_cards_raw if isinstance(c, dict)]
        else:
            relationship_cards = []
    except Exception:
        relationship_cards = []

    try:
        engine = EvolutionEngine()
        session = engine.create_session(
            project_id=project_id,
            branch=branches[branch_index],
            personal_model=model,
            stage_count=stage_count,
            relationship_cards=relationship_cards,
        )
        engine.prepare_initial_state(session, model)
        EvolutionStore.save(session)
    except Exception as e:
        logger.error(f"创建推演会话失败: {e}")
        logger.debug(traceback.format_exc())
        return jsonify({"success": False, "error": str(e)}), 500

    return jsonify({"success": True, "data": session})


@evolution_bp.route('/<session_id>', methods=['GET'])
def get_session(session_id: str):
    """获取会话详情（query: ?project_id= 可选，加速定位）"""
    project_id = request.args.get('project_id')
    if project_id:
        session = EvolutionStore.get(project_id, session_id)
    else:
        session, error = _load_session(session_id)
        if error:
            return error
    if not session:
        return jsonify({"success": False, "error": f"推演会话不存在: {session_id}"}), 404
    return jsonify({"success": True, "data": session})


@evolution_bp.route('/<session_id>/advance', methods=['POST'])
def advance_session(session_id: str):
    """
    推进下一阶段（同步，1 次 LLM 调用）

    请求（JSON）：{ "project_id": "proj_xxx"（可选）, "injected_event": "决定要二胎"（可选） }
    返回 fork_required=true 时前端应先引导用户裁决分叉
    """
    session, error = _load_session(session_id)
    if error:
        return error

    data = request.get_json(silent=True) or {}
    injected_event = (data.get('injected_event') or '').strip() or None

    try:
        engine = EvolutionEngine()
        result = engine.advance(session, injected_event=injected_event)
        EvolutionStore.save(result["session"])
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    except Exception as e:
        logger.error(f"推进会话失败: {session_id}, {e}")
        logger.debug(traceback.format_exc())
        return jsonify({"success": False, "error": str(e)}), 500

    # 推演增量写入独立图谱（可观测；失败不阻断推演；与主图谱物理隔离防污染）
    graph_episode_uuid = None
    if not result["fork_required"] and result["session"]["stage_history"]:
        try:
            project, _ = _get_profile_project(result["session"]["project_id"])
            if project:
                from ..services.evolution_graph_writer import write_stage_to_graph
                graph_episode_uuid = write_stage_to_graph(
                    project, result["session"], result["session"]["stage_history"][-1],
                )
        except Exception as e:
            logger.warning(f"推演图谱写入调度失败（不影响推演）: {e}")

    return jsonify({"success": True, "data": {
        "fork_required": result["fork_required"],
        "fork": result.get("fork"),
        "session": result["session"],
        "graph_episode_uuid": graph_episode_uuid,
    }})


@evolution_bp.route('/<session_id>/fork', methods=['POST'])
def resolve_fork(session_id: str):
    """裁决假设分叉（无 LLM 调用）。请求：{ "fork_id": "fork_1", "option_index": 0 }"""
    session, error = _load_session(session_id)
    if error:
        return error

    data = request.get_json(silent=True) or {}
    fork_id = data.get('fork_id')
    try:
        option_index = int(data.get('option_index'))
    except (TypeError, ValueError):
        return jsonify({"success": False, "error": "option_index is required"}), 400

    try:
        engine = EvolutionEngine()
        session = engine.resolve_fork(session, fork_id, option_index)
        EvolutionStore.save(session)
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    except Exception as e:
        logger.error(f"裁决分叉失败: {session_id}, {e}")
        logger.debug(traceback.format_exc())
        return jsonify({"success": False, "error": str(e)}), 500

    return jsonify({"success": True, "data": session})


@evolution_bp.route('/<session_id>/event', methods=['POST'])
def inject_event(session_id: str):
    """预约注入事件（下一阶段生效）。请求：{ "event": "..." }"""
    session, error = _load_session(session_id)
    if error:
        return error

    data = request.get_json(silent=True) or {}
    event = (data.get('event') or '').strip()
    if not event:
        return jsonify({"success": False, "error": "event is required"}), 400

    next_stage = len(session.get("stage_history") or []) + 1
    session.setdefault("user_events", []).append({
        "at_stage": next_stage,
        "event": event,
        "injected": True,
    })
    EvolutionStore.save(session)
    return jsonify({"success": True, "data": session})


@evolution_bp.route('/<session_id>/abort', methods=['POST'])
def abort_session(session_id: str):
    """终止会话"""
    session, error = _load_session(session_id)
    if error:
        return error

    session["status"] = "aborted"
    EvolutionStore.save(session)
    return jsonify({"success": True, "data": session})


@evolution_bp.route('/list/<project_id>', methods=['GET'])
def list_sessions(project_id: str):
    """项目的全部推演会话摘要（按创建时间倒序）"""
    project, error = _get_profile_project(project_id)
    if error:
        return error
    return jsonify({"success": True, "data": EvolutionStore.list_sessions(project_id)})


@evolution_bp.route('/compare/<project_id>', methods=['GET'])
def compare_sessions(project_id: str):
    """
    多宇宙对比（无 LLM 调用，纯数据聚合）
    每个有进展的宇宙：终态 4 维 world_state + 偏离记录 + 已裁决分叉
    """
    project, error = _get_profile_project(project_id)
    if error:
        return error

    universes = []
    for s in EvolutionStore.list_sessions(project_id):
        if s["stages_done"] < 1:
            continue
        session = EvolutionStore.get(project_id, s["session_id"]) or {}
        history = session.get("stage_history") or []
        final = history[-1] if history else {}
        divergences = [
            {"stage": e.get("stage_index"), "note": e.get("divergence_note")}
            for e in history if e.get("divergence_note")
        ]
        forks = [
            {"question": f.get("question"), "choice": (f.get("resolved") or {}).get("label")}
            for f in session.get("pending_forks") or [] if f.get("resolved")
        ]
        universes.append({
            "session_id": s["session_id"],
            "archetype": s["source_branch_archetype"],
            "positioning": s["source_branch_positioning"],
            "status": s["status"],
            "stages_done": s["stages_done"],
            "stage_count": s["stage_count"],
            "final_world_state": final.get("world_state") or {},
            "final_snapshot": final.get("state_snapshot") or "",
            "divergences": divergences,
            "resolved_forks": forks,
        })
    return jsonify({"success": True, "data": universes})
