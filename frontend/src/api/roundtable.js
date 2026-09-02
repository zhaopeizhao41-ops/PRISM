import service from './index'

/**
 * 平行宇宙圆桌 API
 * 对应后端 /api/roundtable/* 蓝图
 */

/**
 * 可参与者列表（宇宙 + 关系人）
 */
export function getRoundtableParticipants(projectId) {
  return service({
    url: `/api/roundtable/participants/${projectId}`,
    method: 'get'
  })
}

/**
 * 召开圆桌（异步任务，发言逐条落盘）
 * @param {Object} data - { project_id, topic, session_ids?, person_refs? }
 */
export function openRoundtable(data) {
  return service({
    url: '/api/roundtable/open',
    method: 'post',
    data
  })
}

/**
 * 圆桌记录（transcript 渐增，供轮询）
 */
export function getRoundtableDialog(dialogId, projectId) {
  return service({
    url: `/api/roundtable/${dialogId}`,
    method: 'get',
    params: projectId ? { project_id: projectId } : undefined
  })
}

/**
 * 历史圆桌摘要
 */
export function listRoundtables(projectId) {
  return service({
    url: `/api/roundtable/list/${projectId}`,
    method: 'get'
  })
}

/**
 * 删除单场圆桌记录
 */
export function deleteRoundtable(dialogId, projectId) {
  return service({
    url: `/api/roundtable/${dialogId}`,
    method: 'delete',
    params: projectId ? { project_id: projectId } : undefined
  })
}

/**
 * 现场向指定席位追问/质询
 * @param {string} dialogId
 * @param {Object} data - { speaker_ref, question, project_id? }
 */
export function interjectRoundtableSpeech(dialogId, data) {
  return service({
    url: `/api/roundtable/${dialogId}/interject`,
    method: 'post',
    data
  })
}
