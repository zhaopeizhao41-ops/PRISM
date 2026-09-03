import service from './index'

/**
 * 生成本体（上传文档和模拟需求）
 * @param {Object} data - 包含files, simulation_requirement, project_name等
 * @returns {Promise}
 */
export function generateOntology(formData) {
  return service({
    url: '/api/graph/ontology/generate',
    method: 'post',
    data: formData,
    headers: {
      'Content-Type': 'multipart/form-data'
    }
  })
}

/**
 * 构建图谱
 * @param {Object} data - 包含project_id, graph_name等
 * @returns {Promise}
 */
export function buildGraph(data) {
  return service({
    url: '/api/graph/build',
    method: 'post',
    data
  })
}

/**
 * 查询任务状态
 * @param {String} taskId - 任务ID
 * @returns {Promise}
 */
export function getTaskStatus(taskId) {
  return service({
    url: `/api/graph/task/${taskId}`,
    method: 'get'
  })
}

/**
 * 获取项目的长任务状态（工作台任务中心使用）
 * @param {String} projectId
 */
export function listProjectTasks(projectId) {
  return service({
    url: '/api/graph/tasks',
    method: 'get',
    params: { project_id: projectId }
  })
}

/**
 * 取消项目任务
 * @param {String} taskId
 */
export function cancelTask(taskId) {
  return service({
    url: `/api/graph/task/${taskId}/cancel`,
    method: 'post'
  })
}

/**
 * 获取图谱数据
 * @param {String} graphId - 图谱ID
 * @returns {Promise}
 */
export function getGraphData(graphId) {
  return service({
    url: `/api/graph/data/${graphId}`,
    method: 'get'
  })
}

/**
 * 获取项目信息
 * @param {String} projectId - 项目ID
 * @returns {Promise}
 */
export function getProject(projectId) {
  return service({
    url: `/api/graph/project/${projectId}`,
    method: 'get'
  })
}
