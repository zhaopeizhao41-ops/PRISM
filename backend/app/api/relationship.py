"""
关系人 Agent API
/api/relationship/candidates/<project_id>    GET    识别候选关系人（无 LLM）
/api/relationship/generate                   POST   为勾选的关系人生成人格卡（异步）
/api/relationship/generate/status/<task_id>  GET    查询生成任务状态
/api/relationship/<project_id>               GET    获取当前人格卡集合
/api/relationship/corrections/<project_id>   GET    获取全部纠错记录
/api/relationship/corrections                POST   追加一条纠错记录
/api/relationship/corrections                DELETE 删除一条纠错记录
"""

import threading
import traceback

from flask import jsonify, request

from . import relationship_bp
from ..utils.locale import t, get_locale, set_locale
from ..models.task import TaskManager, TaskStatus
from ..models.personal_model import PersonalModelStore
from ..models.relationship_agent import RelationshipAgentStore
from ..models.project import ProjectManager
from ..services.relationship_agent_generator import RelationshipAgentGenerator
from ..utils.logger import get_logger

logger = get_logger('prism.api.relationship')


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


def _load_graph_and_model(project_id: str):
    """加载图谱与个人模型（候选识别与生成都需要）"""
    project = ProjectManager.get_project(project_id)
    if not project or not project.graph_id:
        return None, (jsonify({
            "success": False,
            "error": "项目图谱尚未构建"
        }), 400)
    model = PersonalModelStore.get_current(project_id)
    if not model:
        return None, (jsonify({
            "success": False,
            "error": "个人模型尚未生成，请先调用 /api/profile/model/generate"
        }), 400)
    return (project, model), None


@relationship_bp.route('/candidates/<project_id>', methods=['GET'])
def list_candidates(project_id: str):
    """识别可生成 Agent 的关系人候选（无 LLM 调用）"""
    project, error = _get_profile_project(project_id)
    if error:
        return error

    loaded, error = _load_graph_and_model(project_id)
    if error:
        return error
    project, model = loaded

    try:
        generator = RelationshipAgentGenerator()
        candidates = generator.list_candidates(project.graph_id, model)
    except Exception as e:
        logger.error(f"关系人候选识别失败: {project_id}, {e}")
        logger.debug(traceback.format_exc())
        return jsonify({"success": False, "error": str(e)}), 500

    return jsonify({"success": True, "data": {
        "project_id": project_id,
        "candidates": candidates,
    }})


@relationship_bp.route('/generate', methods=['POST'])
def generate_cards():
    """
    为勾选的关系人生成人格卡（异步任务，每位 1 次 LLM 调用）

    请求（JSON）：{ "project_id": "proj_xxx", "person_refs": ["母亲", "挚友"] }
    """
    data = request.get_json(silent=True) or {}
    project_id = data.get('project_id')
    person_refs = data.get('person_refs')
    if person_refs is None:
        person_refs = []
    if not project_id:
        return jsonify({"success": False, "error": "project_id is required"}), 400
    if not person_refs or not isinstance(person_refs, list):
        return jsonify({"success": False, "error": "person_refs 不能为空"}), 400
    person_refs = list(dict.fromkeys(str(p).strip() for p in person_refs if str(p).strip()))
    if not person_refs or len(person_refs) > 8:
        return jsonify({"success": False, "error": "person_refs 数量必须为 1-8"}), 400
    allow_mediated = bool(data.get("allow_mediated", False))

    project, error = _get_profile_project(project_id)
    if error:
        return error

    loaded, error = _load_graph_and_model(project_id)
    if error:
        return error
    _, model = loaded

    task_manager = TaskManager()
    task_id = task_manager.create_task(
        f"关系人 Agent 生成: {project.name}",
        metadata={"project_id": project_id, "kind": "relationship_generation"},
    )
    logger.info(
        f"启动人格卡生成: project={project_id}, task={task_id}, persons={person_refs}"
    )

    current_locale = get_locale()

    def generate_task():
        set_locale(current_locale)
        gen_logger = get_logger('prism.relationship.generate')
        try:
            if task_manager.is_cancelled(task_id):
                return
            task_manager.update_task(
                task_id,
                status=TaskStatus.PROCESSING,
                message="人格卡生成任务启动",
                progress=10,
            )

            def progress_callback(stage, message, done, total):
                if task_manager.is_cancelled(task_id):
                    raise RuntimeError("任务已取消")
                task_manager.update_task(
                    task_id,
                    message=message,
                    progress=min(90, 10 + int(80 * done / total)) if total else 50,
                )

            generator = RelationshipAgentGenerator()
            cards = generator.generate_cards(
                graph_id=project.graph_id,
                personal_model=model,
                selected_names=person_refs,
                progress_callback=progress_callback,
                allow_mediated=allow_mediated,
            )
            if task_manager.is_cancelled(task_id):
                return

            payload = {
                "cards": cards,
                "card_count": len(cards),
                "source_model_version": model.get("model_version"),
                "project_id": project_id,
            }
            RelationshipAgentStore.save(project_id, payload)

            task_manager.update_task(
                task_id,
                status=TaskStatus.COMPLETED,
                message="关系人 Agent 生成完成",
                progress=100,
                result={
                    "project_id": project_id,
                    "card_count": len(cards),
                },
            )
            gen_logger.info(f"[{task_id}] 人格卡生成完成: {len(cards)} 张")

        except Exception as e:
            gen_logger.error(f"[{task_id}] 人格卡生成失败: {e}")
            gen_logger.debug(traceback.format_exc())
            task_manager.update_task(
                task_id,
                status=TaskStatus.FAILED,
                message=f"人格卡生成失败: {e}",
                error=traceback.format_exc(),
            )

    threading.Thread(target=generate_task, daemon=True).start()

    return jsonify({
        "success": True,
        "data": {
            "project_id": project_id,
            "task_id": task_id,
            "person_count": len(person_refs),
            "message": "人格卡生成任务已启动",
        }
    })


@relationship_bp.route('/generate/status/<task_id>', methods=['GET'])
def get_generate_status(task_id: str):
    """查询人格卡生成任务状态"""
    task = TaskManager().get_task(task_id)
    if not task:
        return jsonify({
            "success": False,
            "error": t('api.taskNotFound', id=task_id)
        }), 404
    return jsonify({"success": True, "data": task.to_dict()})


@relationship_bp.route('/<project_id>', methods=['GET'])
def get_cards(project_id: str):
    """获取当前人格卡集合"""
    project, error = _get_profile_project(project_id)
    if error:
        return error

    data = RelationshipAgentStore.get_current(project_id)
    if not data:
        return jsonify({
            "success": False,
            "error": "人格卡尚未生成，请先调用 /api/relationship/generate"
        }), 404

    return jsonify({"success": True, "data": data})


@relationship_bp.route('/corrections/<project_id>', methods=['GET'])
def get_corrections(project_id: str):
    """获取全部纠错记录"""
    project, error = _get_profile_project(project_id)
    if error:
        return error

    return jsonify({"success": True, "data": {
        "project_id": project_id,
        "corrections": RelationshipAgentStore.get_corrections(project_id),
    }})


@relationship_bp.route('/corrections', methods=['POST'])
def add_correction():
    """
    追加一条纠错记录

    请求（JSON）：{
        "project_id": "proj_xxx",
        "person_ref": "母亲",
        "scene": "被问起婚事时",
        "wrong": "笑着岔开话题",
        "correct": "她会直接沉默，然后去厨房"
    }
    """
    data = request.get_json(silent=True) or {}
    project_id = data.get('project_id')
    person_ref = data.get('person_ref')
    if not project_id or not person_ref:
        return jsonify({
            "success": False,
            "error": "project_id 与 person_ref 不能为空"
        }), 400

    project, error = _get_profile_project(project_id)
    if error:
        return error

    try:
        record = RelationshipAgentStore.add_correction(
            project_id,
            person_ref=person_ref,
            scene=data.get('scene', ''),
            wrong=data.get('wrong', ''),
            correct=data.get('correct', ''),
        )
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    except Exception as e:
        logger.error(f"追加纠错失败: {project_id}, {e}")
        return jsonify({"success": False, "error": str(e)}), 500

    return jsonify({"success": True, "data": {
        "project_id": project_id,
        "person_ref": person_ref,
        "record": record,
    }})


@relationship_bp.route('/corrections', methods=['DELETE'])
def delete_correction():
    """删除一条纠错记录（按 person_ref + 下标）"""
    data = request.get_json(silent=True) or {}
    project_id = data.get('project_id')
    person_ref = data.get('person_ref')
    index = data.get('index')
    if not project_id or not person_ref or index is None:
        return jsonify({
            "success": False,
            "error": "project_id、person_ref、index 不能为空"
        }), 400

    project, error = _get_profile_project(project_id)
    if error:
        return error

    try:
        RelationshipAgentStore.delete_correction(project_id, person_ref, int(index))
    except (ValueError, IndexError) as e:
        return jsonify({"success": False, "error": str(e)}), 404
    except Exception as e:
        logger.error(f"删除纠错失败: {project_id}, {e}")
        return jsonify({"success": False, "error": str(e)}), 500

    return jsonify({"success": True, "data": {"project_id": project_id}})
