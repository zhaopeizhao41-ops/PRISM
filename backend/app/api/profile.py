"""
个人画像层API路由
资料输入（结构化表单 + 自由资料）→ 固定个人本体 → Zep 个人图谱。

P1 范围：创建项目、接收资料、触发建图、查询任务状态。
P2 将增加 /model/generate（画像合成）。

设计文档见 docs/PERSONAL_PROFILE_DESIGN.md 第六节 API 契约。
"""

import os
import json
import threading
import traceback

from flask import request, jsonify

from . import profile_bp
from ..config import Config
from ..services.graph_builder import GraphBuilderService
from ..services.text_processor import TextProcessor
from ..services.person_ontology import get_person_ontology
from ..services.profile_materials import (
    MATERIAL_CONFIDENCE,
    VALID_MATERIAL_TYPES,
    VALID_MATERIAL_MODES,
    MATERIAL_TYPE_ALIASES,
    structured_form_to_text,
    free_material_to_text,
    merge_materials,
    material_fingerprint,
    build_evidence_index,
    count_filled_fields,
    canonicalize_goals,
)
from ..utils.file_parser import FileParser
from ..utils.logger import get_logger
from ..utils.locale import t, get_locale, set_locale
from ..models.task import TaskManager, TaskStatus
from ..models.project import ProjectManager, ProjectStatus
from ..models.personal_model import PersonalModelStore
from ..services.profile_synthesizer import ProfileSynthesizer

logger = get_logger('prism.profile')

# 资料清单锁：同一项目的资料追加/建图串行化
_material_locks: dict[str, threading.Lock] = {}
_material_locks_guard = threading.Lock()


def _material_lock(project_id: str) -> threading.Lock:
    with _material_locks_guard:
        return _material_locks.setdefault(project_id, threading.Lock())


def _get_profile_project(project_id: str):
    """获取项目并校验其为画像项目"""
    project = ProjectManager.get_project(project_id)
    if not project:
        return None, (jsonify({
            "success": False,
            "error": t('api.projectNotFound', id=project_id)
        }), 404)
    if getattr(project, "project_type", None) != "personal_profile":
        return None, (jsonify({
            "success": False,
            "error": f"Project {project_id} is not a personal profile project"
        }), 400)
    return project, None


def _get_manifest_path(project_id: str) -> str:
    return os.path.join(
        ProjectManager._get_project_dir(project_id), 'materials_manifest.json'
    )


def _load_manifest(project_id: str) -> list:
    path = _get_manifest_path(project_id)
    if not os.path.exists(path):
        return []
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            entries = data.get("materials", []) if isinstance(data, dict) else data
            migrated = []
            for item in entries if isinstance(entries, list) else []:
                if not isinstance(item, dict):
                    continue
                was_legacy = "material_mode" not in item or item.get("schema_version", 1) < 2
                item.setdefault("material_mode", "personal")
                if item.get("material_type") in MATERIAL_TYPE_ALIASES:
                    item["material_type"] = MATERIAL_TYPE_ALIASES[item["material_type"]]
                item.setdefault("schema_version", 2)
                if was_legacy or item.get("legacy"):
                    item["legacy"] = True
                migrated.append(item)
            return migrated
    except (OSError, json.JSONDecodeError):
        return []


def _save_manifest(project_id: str, manifest: list) -> None:
    path = _get_manifest_path(project_id)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump({"schema_version": 2, "materials": manifest}, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _literary_analysis_path(project_id: str) -> str:
    return os.path.join(ProjectManager._get_project_dir(project_id), 'literary_analysis.json')


def _save_literary_analysis(project_id: str, model: dict) -> None:
    path = _literary_analysis_path(project_id)
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(model, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _append_manifest_entry(project_id: str, entry: dict) -> bool:
    """追加资料条目；指纹重复时返回 False"""
    with _material_lock(project_id):
        manifest = _load_manifest(project_id)
        if any(item.get("fingerprint") == entry["fingerprint"] for item in manifest):
            return False
        manifest.append(entry)
        _save_manifest(project_id, manifest)
        return True


def _chunk_provenance(chunks: list[str], entries: list[dict]) -> list[dict]:
    """Attach stable local material/chunk identities to each Zep episode."""
    material_ids = [m.get("material_id") for m in entries if m.get("material_id")]
    indexed = [
        (m.get("material_id"), c.get("chunk_id"), str(c.get("text") or ""))
        for m in entries for c in (m.get("chunks") or [])
    ]
    result = []
    for chunk in chunks:
        text = str(chunk or "")
        matches = []
        for material_id, chunk_id, evidence_text in indexed:
            left = " ".join(text.split())
            right = " ".join(evidence_text.split())
            if (len(left) >= 40 and left[:40] in right) or (len(right) >= 40 and right[:40] in left):
                matches.append(chunk_id)
        result.append({
            "source_material_ids": material_ids,
            "evidence_chunk_ids": matches[:8],
        })
    return result


# ============== 项目管理 ==============

@profile_bp.route('/create', methods=['POST'])
def create_profile_project():
    """
    创建个人画像项目

    请求（JSON，均可选）：
        { "name": "我的画像" }

    返回：{ "success": true, "data": { "project_id": "proj_xxx" } }
    """
    data = request.get_json(silent=True) or {}
    name = (data.get('name') or 'Personal Profile').strip() or 'Personal Profile'

    project = ProjectManager.create_project(name=name)
    project.project_type = "personal_profile"
    # 画像项目直接注入固定本体，状态推进到"本体已生成"，跳过 LLM 本体生成
    ontology = get_person_ontology()
    project.ontology = {
        "entity_types": ontology["entity_types"],
        "edge_types": ontology["edge_types"],
    }
    project.analysis_summary = ontology["analysis_summary"]
    project.status = ProjectStatus.ONTOLOGY_GENERATED
    ProjectManager.save_project(project)

    logger.info(f"创建个人画像项目: {project.project_id}")
    return jsonify({
        "success": True,
        "data": {"project_id": project.project_id}
    })


# ============== 资料接入 ==============

@profile_bp.route('/structured-input', methods=['POST'])
def submit_structured_input():
    """
    提交量化基础信息表单

    请求（JSON）：设计文档 2.1 节表单结构，全部字段可选。
    幂等：重复提交相同表单会因指纹去重被拒绝。

    返回：{ received_fields, normalized_text_preview }
    """
    data = request.get_json(silent=True) or {}
    project_id = data.get('project_id')
    if not project_id:
        return jsonify({"success": False, "error": "project_id is required"}), 400

    project, error = _get_profile_project(project_id)
    if error:
        return error

    form = data.get('form')
    if not isinstance(form, dict) or not form:
        return jsonify({"success": False, "error": "form (object) is required"}), 400

    text = structured_form_to_text(form)
    if not text:
        return jsonify({"success": False, "error": "表单所有字段均为空"}), 400

    fingerprint = material_fingerprint(text)
    entry = {
        "material_id": f"mat_{fingerprint}",
        "material_type": "structured_form",
        "material_mode": "personal",
        "schema_version": 2,
        "fingerprint": fingerprint,
        "char_count": len(text),
        "preview": text[:200],
        "normalized_text": text,
        "chunks": build_evidence_index(f"mat_{fingerprint}", text),
        "goals": canonicalize_goals(form),
    }
    if not _append_manifest_entry(project_id, entry):
        return jsonify({
            "success": False,
            "error": "该表单内容已提交过（内容指纹重复）"
        }), 409

    # 追加到项目提取文本（与建图管线衔接）
    existing = ProjectManager.get_extracted_text(project_id) or ""
    merged = merge_materials([existing, text]) if existing else text
    ProjectManager.save_extracted_text(project_id, merged)

    return jsonify({
        "success": True,
        "data": {
            "material_id": entry["material_id"],
            "received_fields": count_filled_fields(form),
            "normalized_text_preview": text,
        }
    })


@profile_bp.route('/materials', methods=['POST'])
def submit_material():
    """
    提交自由资料：粘贴文本 或 上传文件（二选一或同时）

    请求（multipart/form-data）：
        project_id: 必填
        text: 粘贴的文本（可选）
        material_type: 日记/感想随笔/简历/书单影单/聊天记录/其他 → 枚举键
        time_range: 可选，如 "2024全年"
        files: 上传文件（pdf/md/txt，可多个），文件资料统一按 material_type 归类

    返回：{ materials: [{material_id, source, chunks_preview}] }
    """
    project_id = request.form.get('project_id')
    if not project_id:
        return jsonify({"success": False, "error": "project_id is required"}), 400

    project, error = _get_profile_project(project_id)
    if error:
        return error

    material_type = request.form.get('material_type', 'other')
    material_type = MATERIAL_TYPE_ALIASES.get(material_type, material_type)
    if material_type not in VALID_MATERIAL_TYPES:
        return jsonify({
            "success": False,
            "error": f"material_type must be one of: {sorted(VALID_MATERIAL_TYPES)}"
        }), 400
    material_mode = request.form.get('material_mode', 'personal').strip().lower()
    if material_mode not in VALID_MATERIAL_MODES:
        return jsonify({
            "success": False,
            "error": f"material_mode must be one of: {sorted(VALID_MATERIAL_MODES)}"
        }), 400
    if material_mode == "fictional" and material_type not in {"literary", "other"}:
        return jsonify({
            "success": False,
            "error": "fictional material_mode requires material_type=literary or other"
        }), 400
    time_range = request.form.get('time_range', '').strip() or None

    blocks = []          # 文本块列表
    results = []         # 响应明细

    # 1) 粘贴文本
    pasted = request.form.get('text', '').strip()
    if pasted:
        block = free_material_to_text(pasted, material_type, time_range, material_mode)
        blocks.append(block)
        results.append({
            "material_id": f"mat_{material_fingerprint(block)}",
            "source": "pasted_text",
            "char_count": len(pasted),
        })

    # 2) 上传文件
    for file in request.files.getlist('files'):
        if not file or not file.filename:
            continue
        ext = os.path.splitext(file.filename)[1].lower().lstrip('.')
        if ext not in Config.ALLOWED_EXTENSIONS:
            results.append({
                "source": "file",
                "filename": file.filename,
                "error": f"unsupported extension: .{ext}"
            })
            continue
        file_info = ProjectManager.save_file_to_project(
            project_id, file, file.filename
        )
        project.files.append({
            "filename": file_info["original_filename"],
            "size": file_info["size"],
        })
        raw_text = FileParser.extract_text(file_info["path"])
        raw_text = TextProcessor.preprocess_text(raw_text)
        block = free_material_to_text(raw_text, material_type, time_range, material_mode)
        blocks.append(block)
        results.append({
            "material_id": f"mat_{material_fingerprint(block)}",
            "source": "file",
            "filename": file_info["original_filename"],
            "char_count": len(raw_text),
        })

    if not blocks:
        return jsonify({
            "success": False,
            "error": "未提供有效资料（text 或 files 至少一项）"
        }), 400

    # 3) 追加资料清单（指纹去重）
    added = []
    for block, result in zip(blocks, results):
        if "error" in result:
            continue
        fingerprint = material_fingerprint(block)
        entry = {
            "material_id": result["material_id"],
            "material_type": material_type,
            "material_mode": material_mode,
            "schema_version": 2,
            "fingerprint": fingerprint,
            "char_count": result["char_count"],
            "preview": block[:200],
            "normalized_text": block,
            "chunks": build_evidence_index(result["material_id"], block),
        }
        if _append_manifest_entry(project_id, entry):
            added.append(block)
        else:
            result["duplicate"] = True

    if not added:
        ProjectManager.save_project(project)
        return jsonify({
            "success": False,
            "error": "所有资料均与已提交内容重复",
            "data": {"materials": results},
        }), 409

    # 4) 合并进项目提取文本
    existing = ProjectManager.get_extracted_text(project_id) or ""
    merged = merge_materials([existing] + added) if existing else merge_materials(added)
    ProjectManager.save_extracted_text(project_id, merged)
    project.total_text_length = len(merged)
    ProjectManager.save_project(project)

    return jsonify({
        "success": True,
        "data": {
            "materials": results,
            "total_text_length": len(merged),
            "material_count": len(_load_manifest(project_id)),
        }
    })


@profile_bp.route('/materials/<project_id>', methods=['GET'])
def list_materials(project_id: str):
    """列出项目当前的全部资料条目"""
    project, error = _get_profile_project(project_id)
    if error:
        return error
    manifest = _load_manifest(project_id)
    return jsonify({
        "success": True,
        "data": {
            "materials": manifest,
            "total_text_length": project.total_text_length,
        }
    })


# ============== 建图 ==============

@profile_bp.route('/build', methods=['POST'])
def build_profile_graph():
    """
    触发个人图谱构建（复用 GraphBuilderService，固定本体已在创建时注入）

    请求（JSON）：{ "project_id": "proj_xxx" }
    返回：{ task_id }，用 GET /api/profile/build/status/<task_id> 轮询
    """
    data = request.get_json(silent=True) or {}
    project_id = data.get('project_id')
    if not project_id:
        return jsonify({"success": False, "error": "project_id is required"}), 400

    project, error = _get_profile_project(project_id)
    if error:
        return error

    if project.status == ProjectStatus.GRAPH_BUILDING:
        task = TaskManager().get_task(project.graph_build_task_id) if project.graph_build_task_id else None
        if task and task.status in {TaskStatus.PENDING, TaskStatus.PROCESSING}:
            return jsonify({
                "success": True,
                "data": {
                    "project_id": project_id,
                    "task_id": project.graph_build_task_id,
                    "graph_id": project.graph_id,
                    "literary_graph_id": project.literary_graph_id,
                    "reused": True,
                    "message": "图谱构建进行中",
                }
            })

    force = bool(data.get('force', False))
    if project.status == ProjectStatus.GRAPH_COMPLETED and not force:
        return jsonify({
            "success": True,
            "data": {
                "project_id": project_id,
                "task_id": project.graph_build_task_id,
                "graph_id": project.graph_id,
                "literary_graph_id": project.literary_graph_id,
                "reused": True,
                "message": "图谱已构建完成",
            }
        })

    if project.status == ProjectStatus.FAILED or force:
        # 失败重试 / 强制重建：删除云端旧图后回到本体就绪状态
        if project.graph_id:
            try:
                GraphBuilderService(api_key=Config.ZEP_API_KEY).delete_graph(project.graph_id)
            except Exception:
                logger.exception(f"删除旧图谱失败: {project.graph_id}")
        if project.literary_graph_id:
            try:
                GraphBuilderService(api_key=Config.ZEP_API_KEY).delete_graph(project.literary_graph_id)
            except Exception:
                logger.exception(f"删除旧文学图谱失败: {project.literary_graph_id}")
        from ..services.evolution_graph_writer import delete_evolution_graph
        try:
            delete_evolution_graph(project)
        except Exception:
            logger.exception("删除推演图谱失败")
        project.graph_id = None
        project.literary_graph_id = None
        project.graph_build_task_id = None
        project.zep_batch_id = None
        project.zep_batch_operation_id = None
        project.error = None
        project.status = ProjectStatus.ONTOLOGY_GENERATED
        ProjectManager.save_project(project)

    manifest = _load_manifest(project_id)
    personal_entries = [m for m in manifest if m.get("material_mode", "personal") != "fictional"]
    literary_entries = [m for m in manifest if m.get("material_mode") == "fictional"]
    text = merge_materials([m.get("normalized_text", "") for m in personal_entries if m.get("normalized_text")])
    literary_text = merge_materials([m.get("normalized_text", "") for m in literary_entries if m.get("normalized_text")])
    if not text and not literary_text:
        text = ProjectManager.get_extracted_text(project_id)
    if not personal_entries and not literary_entries:
        return jsonify({"success": False, "error": "项目尚无资料，请先提交资料"}), 400
    if not personal_entries and not literary_text and not text:
        return jsonify({
            "success": False,
            "error": "项目仅包含文学/虚构资料，无法构建个人图谱；请先添加 personal 材料",
            "profile_scope": "fictional_only",
        }), 409
    if not text and not literary_text:
        return jsonify({"success": False, "error": "项目尚无资料，请先提交资料"}), 400

    if not Config.ZEP_API_KEY:
        return jsonify({"success": False, "error": t('api.zepApiKeyMissing')}), 500

    ontology = project.ontology
    if not ontology:
        return jsonify({"success": False, "error": t('api.ontologyNotFound')}), 400

    chunk_size = data.get('chunk_size', Config.DEFAULT_CHUNK_SIZE)
    chunk_overlap = data.get('chunk_overlap', Config.DEFAULT_CHUNK_OVERLAP)

    task_manager = TaskManager()
    task_id = task_manager.create_task(f"个人图谱构建: {project.name}")
    project.status = ProjectStatus.GRAPH_BUILDING
    project.graph_build_task_id = task_id
    ProjectManager.save_project(project)
    logger.info(f"启动个人图谱构建: project={project_id}, task={task_id}")

    current_locale = get_locale()

    def build_task():
        set_locale(current_locale)
        build_logger = get_logger('prism.profile.build')
        try:
            if task_manager.is_cancelled(task_id):
                return
            task_manager.update_task(
                task_id,
                status=TaskStatus.PROCESSING,
                message="初始化图谱服务",
                progress=5,
            )
            builder = GraphBuilderService(api_key=Config.ZEP_API_KEY)

            scopes = []
            if text:
                scopes.append(("personal", text, "graph_id", 10, 50))
            if literary_text:
                scopes.append(("literary", literary_text, "literary_graph_id", 52, 88))

            graph_ids = {}
            total_chunks = 0
            for scope_name, scope_text, graph_attr, start_progress, end_progress in scopes:
                if task_manager.is_cancelled(task_id):
                    return
                chunks = TextProcessor.split_text(scope_text, chunk_size=chunk_size, overlap=chunk_overlap)
                scope_entries = literary_entries if scope_name == "literary" else personal_entries
                chunk_metadata = _chunk_provenance(chunks, scope_entries)
                builder.validate_batch_chunks(chunks, batch_size=350)
                total_chunks += len(chunks)
                task_manager.update_task(task_id, message=f"创建 {scope_name} Zep 图谱", progress=start_progress)

                def remember_graph(graph_id, attr=graph_attr):
                    setattr(project, attr, graph_id)
                    ProjectManager.save_project(project)

                graph_id = builder.create_graph(name=f"{project.name} {scope_name} Graph", graph_id_callback=remember_graph)
                graph_ids[scope_name] = graph_id
                task_manager.update_task(task_id, message=f"设置{scope_name}本体", progress=start_progress + 5)
                builder.set_ontology(graph_id, ontology)

                def add_progress_callback(msg, progress_ratio, base=start_progress, end=end_progress):
                    task_manager.update_task(
                        task_id, message=msg,
                        progress=min(end - 12, base + 8 + int(progress_ratio * max(1, end - base - 20))),
                    )

                def remember_batch(batch_id, operation_id):
                    project.zep_batch_id = batch_id
                    project.zep_batch_operation_id = operation_id
                    ProjectManager.save_project(project)

                task_manager.update_task(task_id, message=f"分块写入{scope_name}资料（{len(chunks)} 块）", progress=start_progress + 8)
                submission = builder.add_text_batches(
                    graph_id, chunks, batch_size=350,
                    progress_callback=add_progress_callback,
                    batch_created_callback=remember_batch,
                    scope=scope_name,
                    chunk_metadata=chunk_metadata,
                )

                def wait_progress_callback(msg, progress_ratio, base=start_progress, end=end_progress):
                    task_manager.update_task(
                        task_id, message=msg,
                        progress=min(end - 2, base + 20 + int(progress_ratio * max(1, end - base - 25))),
                    )

                task_manager.update_task(task_id, message=f"等待 {scope_name} Zep 处理完成", progress=end_progress - 10)
                builder._wait_for_batch(submission, wait_progress_callback)

            task_manager.update_task(task_id, message="获取图谱数据", progress=95)
            if task_manager.is_cancelled(task_id):
                return
            primary_graph = graph_ids.get("personal") or graph_ids.get("literary")
            graph_data = builder.get_graph_data(primary_graph)

            project.status = ProjectStatus.GRAPH_COMPLETED
            project.error = None
            ProjectManager.save_project(project)
            task_manager.update_task(
                task_id,
                status=TaskStatus.COMPLETED,
                message="个人图谱构建完成",
                progress=100,
                result={
                    "project_id": project_id,
                    "graph_id": graph_ids.get("personal"),
                    "literary_graph_id": graph_ids.get("literary"),
                    "node_count": graph_data.get("node_count", 0),
                    "edge_count": graph_data.get("edge_count", 0),
                    "chunk_count": total_chunks,
                },
            )
            build_logger.info(
                f"[{task_id}] 个人图谱构建完成: 节点={graph_data.get('node_count')}, "
                f"边={graph_data.get('edge_count')}"
            )

        except Exception as e:
            if task_manager.is_cancelled(task_id):
                return
            build_logger.error(f"[{task_id}] 个人图谱构建失败: {e}")
            build_logger.debug(traceback.format_exc())
            project.status = ProjectStatus.FAILED
            project.error = str(e)
            ProjectManager.save_project(project)
            task_manager.update_task(
                task_id,
                status=TaskStatus.FAILED,
                message=f"构建失败: {e}",
                error=traceback.format_exc(),
            )

    threading.Thread(target=build_task, daemon=True).start()

    return jsonify({
        "success": True,
        "data": {
            "project_id": project_id,
            "task_id": task_id,
            "message": "个人图谱构建任务已启动",
        }
    })


@profile_bp.route('/build/status/<task_id>', methods=['GET'])
def get_build_status(task_id: str):
    """查询建图任务状态（复用 TaskManager，格式与 /api/graph/task 一致）"""
    task = TaskManager().get_task(task_id)
    if not task:
        return jsonify({
            "success": False,
            "error": t('api.taskNotFound', id=task_id)
        }), 404
    return jsonify({"success": True, "data": task.to_dict()})


# ============== 画像合成 ==============

# 阶段 → 进度区间
_STAGE_PROGRESS = {"prepare": 10, "snapshot": 35, "narrative": 65, "synthesize": 85, "finalize": 95}


@profile_bp.route('/model/generate', methods=['POST'])
def generate_personal_model():
    """
    触发画像三阶段合成（异步任务）

    请求（JSON）：{ "project_id": "proj_xxx" }
    返回：{ task_id }，用 GET /api/profile/model/generate/status/<task_id> 轮询
    """
    data = request.get_json(silent=True) or {}
    project_id = data.get('project_id')
    if not project_id:
        return jsonify({"success": False, "error": "project_id is required"}), 400

    project, error = _get_profile_project(project_id)
    if error:
        return error

    scope = str(data.get('scope') or 'personal').lower()
    if scope not in {'personal', 'literary'}:
        return jsonify({"success": False, "error": "scope must be personal or literary"}), 400
    selected_graph = project.graph_id if scope == 'personal' else project.literary_graph_id
    if not selected_graph:
        return jsonify({
            "success": False,
            "error": "对应 scope 图谱尚未构建，请先调用 /api/profile/build"
        }), 400

    task_manager = TaskManager()
    task_id = task_manager.create_task(f"{'文学分析' if scope == 'literary' else '画像合成'}: {project.name}")
    logger.info(f"启动画像合成: project={project_id}, task={task_id}")

    graph_id = selected_graph
    manifest = [m for m in _load_manifest(project_id) if (m.get("material_mode", "personal") == "fictional") == (scope == 'literary')]
    next_version = 1 if scope == 'literary' else PersonalModelStore.next_version(project_id)
    current_locale = get_locale()

    def generate_task():
        set_locale(current_locale)
        gen_logger = get_logger('prism.profile.generate')
        try:
            if task_manager.is_cancelled(task_id):
                return
            task_manager.update_task(
                task_id,
                status=TaskStatus.PROCESSING,
                message="画像合成任务启动",
                progress=5,
            )

            def progress_callback(stage, message):
                task_manager.update_task(
                    task_id,
                    message=message,
                    progress=_STAGE_PROGRESS.get(stage, 50),
                    progress_detail={"stage": stage},
                )

            synthesizer = ProfileSynthesizer()
            model = synthesizer.synthesize(
                graph_id=graph_id,
                manifest=manifest,
                project_id=project_id,
                previous_version=next_version - 1,
                progress_callback=progress_callback,
                raw_text=merge_materials([
                    m.get("normalized_text", "") for m in manifest
                    if m.get("material_mode", "personal") == ("fictional" if scope == "literary" else "personal") and m.get("normalized_text")
                ]),
                goals=[goal for m in manifest for goal in (m.get("goals") or [])],
            )
            if task_manager.is_cancelled(task_id):
                return
            model["analysis_scope"] = scope
            if scope == 'literary':
                _save_literary_analysis(project_id, model)
            else:
                PersonalModelStore.save(project_id, model)

            task_manager.update_task(
                task_id,
                status=TaskStatus.COMPLETED,
                message="文学分析完成" if scope == 'literary' else "个人模型合成完成",
                progress=100,
                progress_detail={"stage": "done"},
                result={
                    "project_id": project_id,
                    "model_version": model["model_version"],
                    "analysis_scope": scope,
                    "content_hash": model["content_hash"],
                    "entity_count": model["entity_count"],
                },
            )
            gen_logger.info(
                f"[{task_id}] 画像合成完成: v{model['model_version']}, "
                f"entities={model['entity_count']}"
            )

        except Exception as e:
            if task_manager.is_cancelled(task_id):
                return
            gen_logger.error(f"[{task_id}] 画像合成失败: {e}")
            gen_logger.debug(traceback.format_exc())
            task_manager.update_task(
                task_id,
                status=TaskStatus.FAILED,
                message=f"画像合成失败: {e}",
                error=traceback.format_exc(),
            )

    threading.Thread(target=generate_task, daemon=True).start()

    return jsonify({
        "success": True,
        "data": {
            "project_id": project_id,
            "task_id": task_id,
            "message": "画像合成任务已启动",
        }
    })


@profile_bp.route('/model/generate/status/<task_id>', methods=['GET'])
def get_generate_status(task_id: str):
    """查询画像合成任务状态（含当前阶段 stage）"""
    task = TaskManager().get_task(task_id)
    if not task:
        return jsonify({
            "success": False,
            "error": t('api.taskNotFound', id=task_id)
        }), 404
    return jsonify({"success": True, "data": task.to_dict()})


@profile_bp.route('/literary-analysis/<project_id>', methods=['GET'])
def get_literary_analysis(project_id: str):
    project, error = _get_profile_project(project_id)
    if error:
        return error
    path = _literary_analysis_path(project_id)
    if not os.path.exists(path):
        return jsonify({"success": False, "error": "文学分析尚未生成，请调用 /api/profile/model/generate 并传 scope=literary"}), 404
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return jsonify({"success": True, "data": json.load(f)})
    except (OSError, json.JSONDecodeError):
        return jsonify({"success": False, "error": "文学分析文件损坏"}), 500


@profile_bp.route('/model/<project_id>', methods=['GET'])
def get_personal_model(project_id: str):
    """
    获取个人模型

    查询参数：version（可选，缺省返回当前版本）
    返回：完整 personal_model JSON；附 versions 列表
    """
    project, error = _get_profile_project(project_id)
    if error:
        return error

    version_param = request.args.get('version', type=int)
    if version_param:
        model = PersonalModelStore.get_version(project_id, version_param)
    else:
        model = PersonalModelStore.get_current(project_id)

    if not model:
        return jsonify({
            "success": False,
            "error": "个人模型尚未生成，请先调用 /api/profile/model/generate"
        }), 404

    return jsonify({
        "success": True,
        "data": {
            "model": model,
            "versions": PersonalModelStore.list_versions(project_id),
        }
    })


@profile_bp.route('/projects', methods=['GET'])
def list_profile_projects():
    """
    画像项目列表（首页用）
    每项含进度徽标数据：模型版本 / 分支数 / 推演宇宙数 / 圆桌数 / 关系人数
    """
    from ..models.branch import BranchStore
    from ..models.evolution import EvolutionStore
    from ..models.roundtable import RoundtableStore
    from ..models.relationship_agent import RelationshipAgentStore

    projects = [
        p for p in ProjectManager.list_projects(limit=None)
        if getattr(p, 'project_type', None) == 'personal_profile'
    ]
    result = []
    for p in projects:
        model = PersonalModelStore.get_current(p.project_id)
        branches_data = BranchStore.get_current(p.project_id)
        sessions = EvolutionStore.list_sessions(p.project_id)
        dialogs = RoundtableStore.list_dialogs(p.project_id)
        cards_data = RelationshipAgentStore.get_current(p.project_id)
        # 最近可续推的会话：优先 active，其次最近有进展的
        active = next(
            (s for s in sessions if s.get("status") == "active" and s.get("stages_done", 0) >= 1),
            None,
        )
        resume_session = active or next(
            (s for s in sessions if s.get("stages_done", 0) >= 1), None,
        )
        result.append({
            "project_id": p.project_id,
            "name": p.name,
            "status": p.status,
            "created_at": p.created_at,
            "model_version": (model or {}).get("model_version"),
            "branch_count": len((branches_data or {}).get("branches") or []),
            "universe_count": len([s for s in sessions if s["stages_done"] >= 1]),
            "roundtable_count": len(dialogs),
            "relationship_count": len((cards_data or {}).get("cards") or []),
            "resume_session_id": (resume_session or {}).get("session_id"),
            "resume_stage": (resume_session or {}).get("stages_done"),
            "resume_total": (resume_session or {}).get("stage_count"),
        })
    return jsonify({"success": True, "data": result})


@profile_bp.route('/project/<project_id>', methods=['DELETE'])
@profile_bp.route('/<project_id>', methods=['DELETE'])
def delete_profile_project(project_id: str):
    """删除画像项目及关联数据"""
    from .graph import _project_build_lock, _delete_project_impl
    with _project_build_lock(project_id):
        return _delete_project_impl(project_id)
