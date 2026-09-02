import service from './index'

/**
 * 推演会话 API
 * 对应后端 /api/evolution/* 蓝图
 */

/**
 * 从分支创建推演会话（同步，1 次 LLM 调用）
 * @param {Object} data - { project_id, branch_index, stage_count?: 3-6 }
 */
export function createEvolutionSession(data) {
  return service({
    url: '/api/evolution/create',
    method: 'post',
    data
  })
}

/**
 * 获取会话详情（含全部 stage_history）
 */
export function getEvolutionSession(sessionId, projectId) {
  return service({
    url: `/api/evolution/${sessionId}`,
    method: 'get',
    params: projectId ? { project_id: projectId } : undefined
  })
}

/**
 * 推进下一阶段（同步，可携带注入事件）
 * 返回 { fork_required, fork?, session }
 */
export function advanceEvolution(sessionId, data = {}) {
  return service({
    url: `/api/evolution/${sessionId}/advance`,
    method: 'post',
    data
  })
}

/**
 * 裁决假设分叉
 * @param {Object} data - { fork_id, option_index, project_id? }
 */
export function resolveEvolutionFork(sessionId, data) {
  return service({
    url: `/api/evolution/${sessionId}/fork`,
    method: 'post',
    data
  })
}

/**
 * 预约注入事件（下一阶段生效）
 */
export function injectEvolutionEvent(sessionId, data) {
  return service({
    url: `/api/evolution/${sessionId}/event`,
    method: 'post',
    data
  })
}

/**
 * 终止会话
 */
export function abortEvolutionSession(sessionId) {
  return service({
    url: `/api/evolution/${sessionId}/abort`,
    method: 'post',
    data: {}
  })
}

/**
 * 项目的全部推演会话摘要
 */
export function listEvolutionSessions(projectId) {
  return service({
    url: `/api/evolution/list/${projectId}`,
    method: 'get'
  })
}

/**
 * 多宇宙对比（终态 world_state + 偏离 + 分叉汇总）
 */
export function compareEvolutionSessions(projectId) {
  return service({
    url: `/api/evolution/compare/${projectId}`,
    method: 'get'
  })
}
