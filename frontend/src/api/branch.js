import service from './index'

/**
 * 人生分支 API
 * 对应后端 /api/branch/* 蓝图
 */

/**
 * 触发分支生成（异步）
 * @param {Object} data - { project_id, branch_count?: 3-5 }
 */
export function generateBranches(data) {
  return service({
    url: '/api/branch/generate',
    method: 'post',
    data
  })
}

/**
 * 查询生成任务状态（progress_detail.stage: directions|expand|finalize）
 */
export function getBranchGenerateStatus(taskId) {
  return service({
    url: `/api/branch/generate/status/${taskId}`,
    method: 'get'
  })
}

/**
 * 获取最新分支批次
 * @returns {Promise} { branches, branch_count, source_model_version, created_at }
 */
export function getBranches(projectId) {
  return service({
    url: `/api/branch/${projectId}`,
    method: 'get'
  })
}
