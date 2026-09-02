"""
人生分支 API
/api/branch/generate         POST   触发分支生成（异步）
/api/branch/generate/status   GET    查询生成任务状态
/api/branch/<project_id>      GET    获取最新分支批次
"""

import threading
import traceback

from flask import jsonify, request

from . import branch_bp
from ..utils.locale import t, get_locale, set_locale
from ..models.task import TaskManager, TaskStatus
from ..models.personal_model import PersonalModelStore
from ..models.branch import BranchStore
from ..models.project import ProjectManager
from ..services.branch_generator import BranchGenerator
from ..utils.logger import get_logger

logger = get_logger('prism.api.branch')


def _get_profile_project(project_id: str):
    """校验项目存在且为画像类型（与 profile.py 惯例一致）"""
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


# 阶段 → 进度区间
_STAGE_PROGRESS = {
    "directions": 15, "expand": 40, "finalize": 95,
}


@branch_bp.route('/generate', methods=['POST'])
def generate_branches():
    """
    触发人生分支生成（异步任务）

    请求（JSON）：{ "project_id": "proj_xxx", "branch_count": 3~5（缺省 5） }
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

    branch_count = data.get('branch_count', 5)
    try:
        branch_count = max(3, min(5, int(branch_count)))
    except (TypeError, ValueError):
        branch_count = 5

    task_manager = TaskManager()
    task_id = task_manager.create_task(f"人生分支生成: {project.name}")
    logger.info(f"启动分支生成: project={project_id}, task={task_id}, count={branch_count}")

    current_locale = get_locale()

    def generate_task():
        set_locale(current_locale)
        gen_logger = get_logger('prism.branch.generate')
        try:
            task_manager.update_task(
                task_id,
                status=TaskStatus.PROCESSING,
                message="分支生成任务启动",
                progress=5,
            )

            def progress_callback(stage, message):
                task_manager.update_task(
                    task_id,
                    message=message,
                    progress=_STAGE_PROGRESS.get(stage, 50),
                    progress_detail={"stage": stage},
                )

            generator = BranchGenerator()
            result = generator.generate(
                personal_model=model,
                branch_count=branch_count,
                progress_callback=progress_callback,
            )
            result["project_id"] = project_id
            BranchStore.save(project_id, result)

            task_manager.update_task(
                task_id,
                status=TaskStatus.COMPLETED,
                message="人生分支生成完成",
                progress=100,
                progress_detail={"stage": "done"},
                result={
                    "project_id": project_id,
                    "branch_count": result["branch_count"],
                    "source_model_version": result["source_model_version"],
                },
            )
            gen_logger.info(
                f"[{task_id}] 分支生成完成: {result['branch_count']} 个分支"
            )

        except Exception as e:
            gen_logger.error(f"[{task_id}] 分支生成失败: {e}")
            gen_logger.debug(traceback.format_exc())
            task_manager.update_task(
                task_id,
                status=TaskStatus.FAILED,
                message=f"分支生成失败: {e}",
                error=traceback.format_exc(),
            )

    threading.Thread(target=generate_task, daemon=True).start()

    return jsonify({
        "success": True,
        "data": {
            "project_id": project_id,
            "task_id": task_id,
            "branch_count": branch_count,
            "message": "分支生成任务已启动",
        }
    })


@branch_bp.route('/generate/status/<task_id>', methods=['GET'])
def get_generate_status(task_id: str):
    """查询分支生成任务状态（含当前阶段 stage: directions|expand|finalize）"""
    task = TaskManager().get_task(task_id)
    if not task:
        return jsonify({
            "success": False,
            "error": t('api.taskNotFound', id=task_id)
        }), 404
    return jsonify({"success": True, "data": task.to_dict()})


@branch_bp.route('/<project_id>', methods=['GET'])
def get_branches(project_id: str):
    """获取最新分支批次"""
    project, error = _get_profile_project(project_id)
    if error:
        return error

    data = BranchStore.get_current(project_id)
    if not data:
        return jsonify({
            "success": False,
            "error": "分支尚未生成，请先调用 /api/branch/generate"
        }), 404

    return jsonify({"success": True, "data": data})
