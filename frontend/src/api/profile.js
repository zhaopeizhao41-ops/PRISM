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
