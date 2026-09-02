import service from './index'

/**
 * 关系人 Agent API
 * 对应后端 /api/relationship/* 蓝图
 */

/**
 * 识别候选关系人（无 LLM 调用）
 * 返回 { candidates: [{ person_name, relation_kind, fact_count, facts, thin, ... }] }
 */
export function getRelationshipCandidates(projectId) {
  return service({
    url: `/api/relationship/candidates/${projectId}`,
    method: 'get'
  })
}

/**
 * 为勾选的关系人生成人格卡（异步任务）
 * @param {Object} data - { project_id, person_refs: ['母亲', ...] }
 */
export function generateRelationshipAgents(data) {
  return service({
    url: '/api/relationship/generate',
    method: 'post',
    data
  })
}

/**
 * 查询人格卡生成任务状态
 */
export function getRelationshipGenerateStatus(taskId) {
  return service({
    url: `/api/relationship/generate/status/${taskId}`,
    method: 'get'
  })
}

/**
 * 获取当前人格卡集合
 */
export function getRelationshipAgents(projectId) {
  return service({
    url: `/api/relationship/${projectId}`,
    method: 'get'
  })
}

/**
 * 获取全部纠错记录
 * 返回 { corrections: { person_ref: [{ scene, wrong, correct, created_at }] } }
 */
export function getRelationshipCorrections(projectId) {
  return service({
    url: `/api/relationship/corrections/${projectId}`,
    method: 'get'
  })
}

/**
 * 追加一条纠错记录
 * @param {string} projectId
 * @param {Object} data - { person_ref, scene, wrong, correct }
 */
export function addRelationshipCorrection(projectId, data) {
  return service({
    url: '/api/relationship/corrections',
    method: 'post',
    data: { ...data, project_id: projectId }
  })
}

/**
 * 删除一条纠错记录（按 person_ref + 下标）
 */
export function deleteRelationshipCorrection(projectId, personRef, index) {
  return service({
    url: '/api/relationship/corrections',
    method: 'delete',
    data: { project_id: projectId, person_ref: personRef, index }
  })
}
