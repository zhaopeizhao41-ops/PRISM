import service from './index'

/**
 * 个人画像层 API
 * 对应后端 /api/profile/* 蓝图（docs/PERSONAL_PROFILE_DESIGN.md 第六节）
 */

/**
 * 创建个人画像项目
 * @param {Object} data - { name?: string }
 * @returns {Promise} { project_id }
 */
export function createProfileProject(data) {
  return service({
    url: '/api/profile/create',
    method: 'post',
    data
  })
}

/**
 * 提交量化基础信息表单
 * @param {Object} data - { project_id, form }
 * @returns {Promise} { material_id, received_fields, normalized_text_preview }
 */
export function submitStructuredInput(data) {
  return service({
    url: '/api/profile/structured-input',
    method: 'post',
    data
  })
}

/**
 * 提交自由资料（粘贴文本 / 上传文件）
 * @param {FormData} formData - project_id, text?, material_type, time_range?, files?
 * @returns {Promise} { materials, total_text_length, material_count }
 */
export function submitMaterials(formData) {
  return service({
    url: '/api/profile/materials',
    method: 'post',
    data: formData,
    headers: {
      'Content-Type': 'multipart/form-data'
    }
  })
}

/**
 * 列出项目全部资料条目
 * @param {String} projectId
 */
export function listMaterials(projectId) {
  return service({
    url: `/api/profile/materials/${projectId}`,
    method: 'get'
  })
}

/**
 * 触发个人图谱构建
 * @param {Object} data - { project_id, force? }
 * @returns {Promise} { task_id, reused? }
 */
export function buildProfileGraph(data) {
  return service({
    url: '/api/profile/build',
    method: 'post',
    data
  })
}

/**
 * 查询建图任务状态
 * @param {String} taskId
 */
export function getBuildStatus(taskId) {
  return service({
    url: `/api/profile/build/status/${taskId}`,
    method: 'get'
  })
}

/**
 * 触发画像三阶段合成
 * @param {Object} data - { project_id }
 * @returns {Promise} { task_id }
 */
export function generatePersonalModel(data) {
  return service({
    url: '/api/profile/model/generate',
    method: 'post',
    data
  })
}

/**
 * 查询画像合成任务状态（progress_detail.stage: snapshot|narrative|synthesize）
 * @param {String} taskId
 */
export function getGenerateStatus(taskId) {
  return service({
    url: `/api/profile/model/generate/status/${taskId}`,
    method: 'get'
  })
}

/**
 * 获取个人模型
 * @param {String} projectId
 * @returns {Promise} { model, versions }
 */
export function getPersonalModel(projectId) {
  return service({
    url: `/api/profile/model/${projectId}`,
    method: 'get'
  })
}

/**
 * 创建或复用本地脱敏演示项目，不调用 LLM 或 Zep Cloud。
 */
export function createDemoProject() {
  return service({
    url: '/api/profile/demo',
    method: 'post'
  })
}

/**
 * 获取项目的决策上下文（问题、时间范围和不可妥协条件）。
 */
export function getDecisionContext(projectId) {
  return service({
    url: `/api/profile/decision-context/${projectId}`,
    method: 'get'
  })
}

/**
 * 更新项目的决策上下文。
 */
export function updateDecisionContext(projectId, data) {
  return service({
    url: `/api/profile/decision-context/${projectId}`,
    method: 'patch',
    data
  })
}

export function comparePersonalModelVersions(projectId, fromVersion, toVersion) {
  return service({
    url: `/api/profile/model/compare/${projectId}`,
    method: 'get',
    params: { from: fromVersion, to: toVersion }
  })
}

export function getLiteraryAnalysis(projectId) {
  return service({
    url: `/api/profile/literary-analysis/${projectId}`,
    method: 'get'
  })
}

/**
 * 画像项目列表（首页）
 * @returns {Promise} [{ project_id, name, created_at, model_version, branch_count, ... }]
 */
export function getProfileProjects() {
  return service({
    url: '/api/profile/projects',
    method: 'get'
  })
}

/**
 * 删除项目
 * @param {string} projectId
 * @returns {Promise}
 */
export function deleteProject(projectId) {
  return service({
    url: `/api/profile/project/${projectId}`,
    method: 'delete'
  })
}

/**
 * 导出项目快照。浏览器下载由页面使用返回的 blob 完成。
 * @param {string} projectId
 * @param {boolean} includeRaw - 是否明确包含原始资料正文与引用
 */
export function exportProject(projectId, includeRaw = false) {
  return service({
    url: `/api/profile/export/${projectId}`,
    method: 'get',
    params: { include_raw: includeRaw ? 'true' : 'false' },
    responseType: 'blob'
  })
}

export function getProjectPrivacy(projectId) {
  return service({
    url: `/api/profile/privacy/${projectId}`,
    method: 'get'
  })
}

export function updateProjectPrivacy(projectId, data) {
  return service({
    url: `/api/profile/privacy/${projectId}`,
    method: 'patch',
    data
  })
}
