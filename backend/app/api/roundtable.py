"""
圆桌 API
/api/roundtable/participants/<project_id>  GET   可参与者（宇宙 + 关系人）
/api/roundtable/open                       POST  召开圆桌（异步，发言逐条落盘）
/api/roundtable/<dialog_id>                GET   圆桌记录（transcript 渐增）
/api/roundtable/list/<project_id>          GET   历史圆桌摘要
"""

import threading
import traceback
import uuid

from flask import jsonify, request

from . import roundtable_bp
from ..utils.locale import t, get_locale, set_locale
from ..models.task import TaskManager, TaskStatus
from ..models.personal_model import PersonalModelStore
from ..models.relationship_agent import RelationshipAgentStore
from ..models.roundtable import RoundtableStore
from ..models.project import ProjectManager
from ..services.roundtable_engine import RoundtableEngine, MAX_PARTICIPANTS
from ..utils.logger import get_logger

logger = get_logger('prism.api.roundtable')


def _get_profile_project(project_id: str):
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


def _load_dialog(dialog_id: str):
    """定位圆桌记录（可带 project_id 加速，否则扫描）"""
    data = request.get_json(silent=True) or request.args
    project_id = data.get('project_id')
    if project_id:
        dialog = RoundtableStore.get(project_id, dialog_id)
        if dialog:
            return dialog, None
        return None, (jsonify({
            "success": False, "error": f"圆桌记录不存在: {dialog_id}"
        }), 404)

    import os
    projects_root = ProjectManager.PROJECTS_DIR
    if os.path.isdir(projects_root):
        for dirname in os.listdir(projects_root):
            dialog = RoundtableStore.get(dirname, dialog_id)
            if dialog:
                return dialog, None
    return None, (jsonify({
        "success": False, "error": f"圆桌记录不存在: {dialog_id}"
    }), 404)


@roundtable_bp.route('/participants/<project_id>', methods=['GET'])
def list_participants(project_id: str):
    """可参与者列表（无 LLM 调用）"""
    project, error = _get_profile_project(project_id)
    if error:
        return error

    engine = RoundtableEngine()
    return jsonify({"success": True, "data": {
        "project_id": project_id,
        **engine.list_participants(project_id),
    }})


@roundtable_bp.route('/open', methods=['POST'])
def open_roundtable():
    """
    召开圆桌（异步任务）：发言逐条落盘，前端轮询 GET /<dialog_id> 渐进显示。

    请求（JSON）：
    {
      "project_id": "proj_xxx",
      "topic": "我该不该明年竞聘时押注量化体系？",
      "session_ids": ["evo_xxx", ...],     // 可选，默认全部可用宇宙
      "person_refs": ["母亲", ...]          // 可选，默认全部关系人
    }
    """
    data = request.get_json(silent=True) or {}
    project_id = data.get('project_id')
    topic = (data.get('topic') or '').strip()
    if not project_id:
        return jsonify({"success": False, "error": "project_id is required"}), 400
    if not topic:
        return jsonify({"success": False, "error": "topic is required（圆桌议题）"}), 400

    project, error = _get_profile_project(project_id)
    if error:
        return error

    model = PersonalModelStore.get_current(project_id)
    if not model:
        return jsonify({
            "success": False,
            "error": "个人模型尚未生成"
        }), 400

    engine = RoundtableEngine()
    available = engine.list_participants(project_id)

    chosen_sessions = data.get('session_ids') or [u["session_id"] for u in available["universes"]]
    chosen_persons = data.get('person_refs')
    if chosen_persons is None:
        chosen_persons = [r["person_ref"] for r in available["related"]]

    universe_map = {u["session_id"]: u for u in available["universes"]}
    participants = []
    for sid in chosen_sessions:
        u = universe_map.get(sid)
        if not u:
            return jsonify({"success": False, "error": f"宇宙不可用或无推演深度: {sid}"}), 400
        participants.append({
            "type": "universe", "session_id": sid, "label": u["label"],
        })
    # 宇宙已按浅→深排序（list_participants 保证）

    cards_data = RelationshipAgentStore.get_current(project_id)
    cards_map = {
        c.get("person_ref"): c for c in ((cards_data.get("cards") if cards_data else []) or [])
    }
    related_selected = []
    for ref in chosen_persons:
        card = cards_map.get(ref)
        if not card:
            return jsonify({"success": False, "error": f"关系人无人格卡: {ref}"}), 400
        related_selected.append({
            "type": "related", "person_ref": ref, "label": ref,
            "_card": card,  # 运行时注入，落盘时剥离
        })

    if not participants and not related_selected:
        return jsonify({
            "success": False,
            "error": "没有可参与的宇宙（需至少一个宇宙推演≥1阶段）或关系人"
        }), 400
    if len(participants) + len(related_selected) > MAX_PARTICIPANTS:
        return jsonify({
            "success": False,
            "error": f"圆桌人数上限 {MAX_PARTICIPANTS}"
        }), 400

    total_rounds = data.get('total_rounds', 2)
    try:
        total_rounds = max(1, min(5, int(total_rounds)))
    except (ValueError, TypeError):
        total_rounds = 2

    import time as _time
    dialog = {
        "dialog_id": f"rt_{uuid.uuid4().hex[:12]}",
        "project_id": project_id,
        "topic": topic,
        "total_rounds": total_rounds,
        "current_round": 1,
        "status": "running",
        "participants": participants + related_selected,
        "transcript": [],
        "moderation": None,
        "created_at": _time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    RoundtableStore.save(dialog)

    task_manager = TaskManager()
    task_id = task_manager.create_task(f"圆桌: {topic[:30]}")
    logger.info(
        f"召开圆桌: project={project_id}, dialog={dialog['dialog_id']}, "
        f"universes={len(participants)}, related={len(related_selected)}, total_rounds={total_rounds}"
    )

    current_locale = get_locale()

    def run_task():
        set_locale(current_locale)
        rt_logger = get_logger('prism.roundtable.run')
        try:
            task_manager.update_task(
                task_id, status=TaskStatus.PROCESSING,
                message="圆桌发言进行中", progress=10,
            )

            def progress_callback(stage, speech):
                if stage == "speech" and speech:
                    RoundtableStore.save(dialog)
                    done = len(dialog.get("transcript") or [])
                    num_p = len(dialog.get("participants") or [])
                    total_speeches = num_p * total_rounds
                    curr_r = speech.get("round", 1)
                    task_manager.update_task(
                        task_id,
                        message=f"[第{curr_r}/{total_rounds}轮] {speech['speaker']} 已发言（{done}/{total_speeches}）",
                        progress=min(90, 10 + int(80 * done / max(1, total_speeches + 1))),
                    )
                elif stage == "moderate":
                    RoundtableStore.save(dialog)
                    task_manager.update_task(
                        task_id, message="主持人正在跨轮交叉审计…", progress=92,
                    )

            engine = RoundtableEngine()
            engine.run_roundtable(dialog, model, progress_callback=progress_callback)

            dialog["status"] = "completed"
            RoundtableStore.save(dialog)
            task_manager.update_task(
                task_id, status=TaskStatus.COMPLETED,
                message="圆桌结束", progress=100,
                result={"dialog_id": dialog["dialog_id"]},
            )
        except Exception as e:
            rt_logger.error(f"[{task_id}] 圆桌失败: {e}")
            rt_logger.debug(traceback.format_exc())
            dialog["status"] = "failed"
            dialog["error"] = str(e)
            RoundtableStore.save(dialog)
            task_manager.update_task(
                task_id, status=TaskStatus.FAILED,
                message=f"圆桌失败: {e}", error=traceback.format_exc(),
            )

    threading.Thread(target=run_task, daemon=True).start()

    return jsonify({"success": True, "data": {
        "dialog_id": dialog["dialog_id"],
        "task_id": task_id,
        "project_id": project_id,
        "participant_count": len(participants) + len(related_selected),
    }})


@roundtable_bp.route('/<dialog_id>', methods=['GET'])
def get_dialog(dialog_id: str):
    """圆桌记录（transcript 渐增，供前端轮询）"""
    project_id = request.args.get('project_id')
    if project_id:
        dialog = RoundtableStore.get(project_id, dialog_id)
    else:
        dialog, error = _load_dialog(dialog_id)
        if error:
            return error
    if not dialog:
        return jsonify({"success": False, "error": f"圆桌记录不存在: {dialog_id}"}), 404
    return jsonify({"success": True, "data": dialog})


@roundtable_bp.route('/list/<project_id>', methods=['GET'])
def list_dialogs(project_id: str):
    """历史圆桌摘要"""
    project, error = _get_profile_project(project_id)
    if error:
        return error
    return jsonify({"success": True, "data": RoundtableStore.list_dialogs(project_id)})


@roundtable_bp.route('/<dialog_id>/interject', methods=['POST'])
def interject_speech(dialog_id: str):
    """
    用户对圆桌指定席位现场追问 / 质询
    请求体：{ "speaker_ref": str, "question": str, "project_id": str }
    """
    data = request.get_json(silent=True) or {}
    project_id = data.get('project_id')
    speaker_ref = data.get('speaker_ref')
    question = (data.get('question') or '').strip()

    if not speaker_ref or not question:
        return jsonify({"success": False, "error": "speaker_ref and question are required"}), 400

    if project_id:
        dialog = RoundtableStore.get(project_id, dialog_id)
    else:
        dialog, error = _load_dialog(dialog_id)
        if error:
            return error
    if not dialog:
        return jsonify({"success": False, "error": f"圆桌记录不存在: {dialog_id}"}), 404

    project_id = dialog["project_id"]
    model_data = PersonalModelStore.get_current(project_id)
    personal_model = model_data.get("model", {}) if model_data else {}

    engine = RoundtableEngine()
    try:
        reply = engine.interject(dialog, speaker_ref, question, personal_model)
        return jsonify({"success": True, "data": {
            "reply": reply,
            "dialog": dialog
        }})
    except Exception as e:
        logger.error(f"Interjection error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@roundtable_bp.route('/<dialog_id>', methods=['DELETE'])
def delete_dialog(dialog_id: str):
    """删除圆桌记录"""
    project_id = request.args.get('project_id')
    if not project_id:
        projects_root = ProjectManager.PROJECTS_DIR
        if os.path.isdir(projects_root):
            for dirname in os.listdir(projects_root):
                if os.path.exists(os.path.join(projects_root, dirname, 'roundtables', f"{dialog_id}.json")):
                    project_id = dirname
                    break
    if not project_id:
        return jsonify({"success": False, "error": "project_id not found"}), 404
    success = RoundtableStore.delete(project_id, dialog_id)
    if not success:
        return jsonify({"success": False, "error": f"Failed to delete roundtable {dialog_id}"}), 400
    return jsonify({"success": True, "data": {"deleted": dialog_id}})
