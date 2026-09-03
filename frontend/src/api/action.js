import service from './index'

/**
 * 现实行动实验 API。
 * 复盘只记录现实结果和用户明确的画像更新授权，不自动改写画像。
 */
export function listActionExperiments(projectId) {
  return service({
    url: `/api/action/experiments/${projectId}`,
    method: 'get'
  })
}

export function createActionExperiment(data) {
  return service({
    url: '/api/action/experiments',
    method: 'post',
    data
  })
}

export function updateActionExperiment(experimentId, data) {
  return service({
    url: `/api/action/experiments/${experimentId}`,
    method: 'patch',
    data
  })
}

export function saveActionRetrospective(experimentId, data) {
  return service({
    url: `/api/action/experiments/${experimentId}/retrospective`,
    method: 'post',
    data
  })
}

export function deleteActionExperiment(experimentId, projectId) {
  return service({
    url: `/api/action/experiments/${experimentId}`,
    method: 'delete',
    data: { project_id: projectId }
  })
}
