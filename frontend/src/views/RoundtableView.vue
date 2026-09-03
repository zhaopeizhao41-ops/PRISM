<template>
  <div class="roundtable-view">
    <!-- 顶部统一导航 -->
    <AppHeader :project-id="projectId" current-step="roundtable" />

    <div class="main-content">
      <!-- 加载态 -->
      <div v-if="loading" class="state-box"><p>{{ t('common.loading') }}</p></div>

      <template v-else>
        <!-- 阶段一：开桌设置 -->
        <template v-if="phase === 'setup'">
          <header class="page-header">
            <h1 class="page-title">{{ t('roundtable.view.title') }}</h1>
            <p class="page-sub">{{ t('roundtable.view.subtitle') }}</p>
          </header>

          <!-- 历史圆桌 -->
          <section v-if="dialogs.length" class="history-box">
            <div class="box-title">{{ t('roundtable.view.history') }}</div>
            <div
              v-for="d in dialogs"
              :key="d.dialog_id"
              class="history-row"
              role="button"
              @click="openDialog(d.dialog_id)"
            >
              <span class="history-topic">{{ d.topic }}</span>
              <div class="history-right">
                <span class="history-meta">{{ d.participant_count }} {{ t('roundtable.view.people') }} · {{ d.speech_count }} {{ t('roundtable.view.speeches') }}</span>
                <button
                  class="history-del-btn"
                  type="button"
                  :title="t('common.delete')"
                  @click.stop="promptDeleteDialog(d)"
                >
                  ✕
                </button>
              </div>
            </div>
          </section>

          <!-- 删除确认弹窗 -->
          <div v-if="deleteDialogTarget" class="modal-backdrop" @click="cancelDeleteDialog">
            <div class="modal-dialog" @click.stop>
              <div class="modal-title">
                <span class="status-dot alert">■</span> {{ t('common.delete') }}: {{ deleteDialogTarget.topic }}
              </div>
              <p class="modal-desc">{{ t('common.deleteConfirm') }}</p>
              <div class="modal-actions">
                <button class="modal-btn cancel" type="button" :disabled="deleteDialogBusy" @click="cancelDeleteDialog">
                  {{ t('common.cancel') }}
                </button>
                <button class="modal-btn delete" type="button" :disabled="deleteDialogBusy" @click="doDeleteDialog">
                  {{ deleteDialogBusy ? t('common.loading') : t('common.confirm') }}
                </button>
              </div>
            </div>
          </div>

          <!-- 议题 -->
          <section class="setup-box">
            <div class="box-title">{{ t('roundtable.view.topic') }}</div>
            <textarea
              v-model="topic"
              class="topic-input"
              rows="3"
              :placeholder="t('roundtable.view.topicPlaceholder')"
            ></textarea>

            <!-- 宇宙参与者 -->
            <div class="box-title">{{ t('roundtable.view.universes') }}</div>
            <div v-if="!universes.length" class="empty-hint">{{ t('roundtable.view.noUniverses') }}</div>
            <label
              v-for="(u, i) in universes"
              :key="u.session_id"
              class="participant-row"
              :class="{ checked: chosenSessions.includes(u.session_id) }"
            >
              <input v-model="chosenSessions" :value="u.session_id" type="checkbox" class="p-check">
              <span class="archetype-badge" :class="u.archetype">{{ archetypeLabel(u.archetype) }}</span>
              <span class="p-label">{{ t('roundtable.view.universeMe') }}</span>
              <span class="p-depth">{{ u.stages_done }}/{{ u.stage_count }}</span>
              <span class="p-positioning">{{ u.positioning }}</span>
              <span v-if="i === 0" class="p-first">{{ t('roundtable.view.speaksFirst') }}</span>
            </label>

            <!-- 关系人参与者 -->
            <template v-if="related.length">
              <div class="box-title">{{ t('roundtable.view.relatedAgents') }}</div>
              <label
                v-for="r in related"
                :key="r.person_ref"
                class="participant-row"
                :class="{ checked: chosenPersons.includes(r.person_ref) }"
              >
                <input v-model="chosenPersons" :value="r.person_ref" type="checkbox" class="p-check">
                <span class="p-label related-name">{{ r.person_ref }}</span>
                <span class="p-relation">{{ relLabel(r.relation_kind) }}</span>
                <span v-if="r.thin" class="p-thin">{{ t('relationship.thin') }}</span>
                <span class="p-positioning">{{ r.persona }}</span>
              </label>
            </template>

            <!-- 辩论深度与轮次选择 -->
            <div class="box-title">{{ t('roundtable.view.roundsTitle') }}</div>
            <div class="rounds-selector-grid">
              <button
                v-for="rOption in [1, 2, 3, 4]"
                :key="rOption"
                type="button"
                class="round-option-btn"
                :class="{ active: selectedRounds === rOption }"
                @click="selectedRounds = rOption"
              >
                <div class="round-btn-head">
                  <span class="round-radio-box" :class="{ checked: selectedRounds === rOption }"></span>
                  <span class="round-num-label">{{ rOption }} {{ t('roundtable.view.roundUnit') }}</span>
                  <span v-if="rOption === 2" class="round-rec-badge">推荐</span>
                </div>
                <div class="round-desc-text">{{ t(`roundtable.view.roundDesc.${rOption}`) }}</div>
              </button>
            </div>

            <button
              class="open-btn"
              type="button"
              :disabled="opening || !topic.trim() || (!chosenSessions.length && !chosenPersons.length)"
              @click="open"
            >
              {{ opening ? t('roundtable.view.opening') : t('roundtable.view.openBtn') }}
            </button>
            <p v-if="setupError" class="error-text">{{ setupError }}</p>
          </section>
        </template>

        <!-- 阶段二：圆桌进行中 / 已结束 -->
        <template v-else>
          <header class="page-header">
            <h1 class="page-title">
              {{ dialogRunning ? t('roundtable.view.inProgress') : t('roundtable.view.finished') }}
            </h1>
            <p class="roundtopic">「{{ dialog.topic }}」</p>
          </header>

          <!-- 发言区 -->
          <div class="speech-list">
            <template v-for="(s, i) in dialog.transcript" :key="i">
              <!-- 轮次分割线 (Round Divider) -->
              <div
                v-if="dialog.total_rounds > 1 && (i === 0 || s.round !== dialog.transcript[i - 1]?.round)"
                class="round-divider-block"
              >
                <div class="round-divider-line"></div>
                <div class="round-divider-pill">
                  <span class="round-pill-badge">第 {{ s.round || 1 }} 轮</span>
                  <span class="round-pill-title">{{ roundStageTitle(s.round || 1, dialog.total_rounds) }}</span>
                </div>
                <div class="round-divider-line"></div>
              </div>

              <div
                class="speech-bubble"
                :class="{
                  related: s.speaker_type === 'related',
                  userInterject: s.speaker_type === 'user_interjection',
                  replyInterject: s.is_interjection_reply
                }"
              >
                <div class="speech-head">
                  <span class="speaker-name">
                    <template v-if="s.speaker_type === 'user_interjection'">
                      [ 用户现场质询 ➔ {{ s.target_name || '席位' }} ]
                    </template>
                    <template v-else>
                      {{ s.speaker }}
                    </template>
                  </span>
                  <span v-if="s.round && dialog.total_rounds > 1" class="speaker-round-badge">R{{ s.round }}</span>
                  <span v-if="s.speaker_type === 'related'" class="speaker-type">{{ t('roundtable.view.relatedTag') }}</span>
                  <span v-else-if="s.speaker_type === 'user_interjection'" class="speaker-type user-tag">现场质询</span>
                  <span v-else-if="s.is_interjection_reply" class="speaker-type reply-tag">现场回应</span>
                  <span v-if="s.anti_drift" class="speech-fidelity-badge">
                    {{ t('roundtable.view.antiDriftFidelity') }}: {{ s.anti_drift.fidelity_score }}%
                  </span>
                </div>
              <p class="speech-content">{{ s.content }}</p>

              <!-- Letta 核心工作记忆块 (Core Working Memory) 与自编辑日志 -->
              <div v-if="s.core_memory" class="core-memory-wrapper">
                <button
                  type="button"
                  class="core-memory-toggle"
                  :class="{ active: openMemoryIndex === i }"
                  @click="toggleCoreMemory(i)"
                >
                  <span class="memory-toggle-icon">■</span>
                  <span>{{ t('roundtable.view.coreMemory') }}</span>
                  <span v-if="s.core_memory_edits?.length" class="memory-edit-count">
                    {{ t('roundtable.view.memoryEdits') }}: {{ s.core_memory_edits.length }}
                  </span>
                </button>

                <div v-if="openMemoryIndex === i" class="core-memory-drawer">
                  <!-- 自编辑日志 -->
                  <div v-if="s.core_memory_edits?.length" class="memory-edits-list">
                    <div v-for="(edit, eIdx) in s.core_memory_edits" :key="eIdx" class="memory-edit-pill">
                      <span class="edit-action-badge" :class="edit.action">{{ t(`roundtable.view.editAction.${edit.action}`) || edit.action }}</span>
                      <span class="edit-block-badge">[{{ edit.block.toUpperCase() }}]</span>
                      <span class="edit-content-text">{{ edit.content }}</span>
                    </div>
                  </div>

                  <!-- 3 大核心记忆块 -->
                  <div class="core-blocks-grid">
                    <div class="core-block persona">
                      <div class="block-label">{{ t('roundtable.view.blockPersona') }}</div>
                      <div class="block-body">{{ s.core_memory.persona }}</div>
                    </div>
                    <div class="core-block human">
                      <div class="block-label">{{ t('roundtable.view.blockHuman') }}</div>
                      <div class="block-body">{{ s.core_memory.human }}</div>
                    </div>
                    <div class="core-block situation">
                      <div class="block-label">{{ t('roundtable.view.blockSituation') }}</div>
                      <div class="block-body">{{ s.core_memory.situation }}</div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </template>

            <!-- 进行中指示 -->
            <div v-if="dialog.status === 'running'" class="running-hint">
              <span class="pulse"></span>
              {{ dialog.transcript.length >= ((dialog.participants?.length || 0) * (dialog.total_rounds || 1))
                 ? t('roundtable.view.moderating') : t('roundtable.view.waitingSpeech') }}
            </div>
            <div v-else-if="dialog.status === 'failed'" class="error-text">
              {{ t('roundtable.view.failed') }}{{ dialog.error }}
            </div>
          </div>

          <!-- 现场追问与质询面板 -->
          <section v-if="dialog.status === 'completed'" class="interjection-panel">
            <div class="interjection-head">
              <span class="interjection-title">■ 现场追问 / 临时质询</span>
              <span class="interjection-hint">向在场任一宇宙自我或关系人发起质询，对方将基于性格与经历当场回应</span>
            </div>
            <div class="interjection-form">
              <div class="target-picker">
                <span class="target-label">质询席位：</span>
                <select v-model="selectedInterjectTarget" class="target-select">
                  <option v-for="p in interjectTargets" :key="p.ref" :value="p.ref">
                    {{ p.label }}
                  </option>
                </select>
              </div>
              <div class="interjection-input-group">
                <textarea
                  v-model="interjectQuestion"
                  class="interjection-input"
                  :placeholder="t('roundtable.view.interjectPlaceholder')"
                  rows="2"
                  :disabled="interjecting"
                ></textarea>
                <button
                  class="interject-btn"
                  type="button"
                  :disabled="interjecting || !interjectQuestion.trim()"
                  @click="submitInterjection"
                >
                  {{ interjecting ? t('roundtable.view.interjecting') : t('roundtable.view.interjectBtn') }}
                </button>
              </div>
              <p v-if="interjectError" class="error-text">{{ interjectError }}</p>
            </div>
          </section>

          <!-- 主持人报告 -->
          <section v-if="moderation && dialog.status === 'completed'" class="moderation-box">
            <div class="mod-title">{{ t('roundtable.view.moderation') }}</div>
            <p v-if="moderation.summary" class="mod-summary">{{ moderation.summary }}</p>

            <!-- 跨宇宙认知收敛与宿命量化透视 (Quantitative Epistemic Consensus) -->
            <div v-if="moderation.epistemic_consensus" class="epistemic-dashboard">
              <div class="epistemic-head">
                <span class="epistemic-badge">■ 量化认知收敛</span>
                <span class="epistemic-title">{{ t('roundtable.view.epistemicConsensusTitle') }}</span>
              </div>

              <!-- 3 大量化指标仪表板 -->
              <div class="epistemic-gauges">
                <div class="gauge-card">
                  <div class="gauge-header">
                    <span class="gauge-label">{{ t('roundtable.view.convergenceIndex') }}</span>
                    <span class="gauge-value">{{ moderation.epistemic_consensus.convergence_index || 0 }}%</span>
                  </div>
                  <div class="gauge-bar-track">
                    <div class="gauge-bar-fill convergence" :style="{ width: `${moderation.epistemic_consensus.convergence_index || 0}%` }"></div>
                  </div>
                </div>

                <div class="gauge-card">
                  <div class="gauge-header">
                    <span class="gauge-label">{{ t('roundtable.view.inevitabilityScore') }}</span>
                    <span class="gauge-value">{{ moderation.epistemic_consensus.inevitability_score || 0 }}%</span>
                  </div>
                  <div class="gauge-bar-track">
                    <div class="gauge-bar-fill inevitability" :style="{ width: `${moderation.epistemic_consensus.inevitability_score || 0}%` }"></div>
                  </div>
                </div>

                <div class="gauge-card">
                  <div class="gauge-header">
                    <span class="gauge-label">{{ t('roundtable.view.leverageRatio') }}</span>
                    <span class="gauge-value">{{ moderation.epistemic_consensus.leverage_ratio || 0 }}%</span>
                  </div>
                  <div class="gauge-bar-track">
                    <div class="gauge-bar-fill leverage" :style="{ width: `${moderation.epistemic_consensus.leverage_ratio || 0}%` }"></div>
                  </div>
                </div>
              </div>

              <!-- 宿命必然性约束与高杠杆支点 -->
              <div class="epistemic-details-grid">
                <div v-if="moderation.epistemic_consensus.inevitable_constraints?.length" class="epistemic-col">
                  <div class="epistemic-col-title">▲ {{ t('roundtable.view.inevitableConstraints') }}</div>
                  <div v-for="(item, idx) in moderation.epistemic_consensus.inevitable_constraints" :key="idx" class="epistemic-item-card constraint">
                    <div class="item-main-text">{{ item.constraint }}</div>
                    <div class="item-sub-row" v-if="item.why">
                      <span class="item-sub-label">{{ t('roundtable.view.constraintWhy') }}</span>
                      <span class="item-sub-val">{{ item.why }}</span>
                    </div>
                    <div class="item-sub-row" v-if="item.impact">
                      <span class="item-sub-label">{{ t('roundtable.view.constraintImpact') }}</span>
                      <span class="item-sub-val">{{ item.impact }}</span>
                    </div>
                  </div>
                </div>

                <div v-if="moderation.epistemic_consensus.high_leverage_variables?.length" class="epistemic-col">
                  <div class="epistemic-col-title">◆ {{ t('roundtable.view.highLeverageVariables') }}</div>
                  <div v-for="(item, idx) in moderation.epistemic_consensus.high_leverage_variables" :key="idx" class="epistemic-item-card leverage">
                    <div class="item-main-text">{{ item.variable }}</div>
                    <div class="item-sub-row" v-if="item.mechanism">
                      <span class="item-sub-label">{{ t('roundtable.view.constraintWhy') }}</span>
                      <span class="item-sub-val">{{ item.mechanism }}</span>
                    </div>
                    <div class="item-sub-row" v-if="item.optimal_timing">
                      <span class="item-sub-label">{{ t('roundtable.view.optimalTiming') }}</span>
                      <span class="item-sub-val highlight">{{ item.optimal_timing }}</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <!-- 证据审计 -->
            <div v-if="moderation.audit?.length" class="mod-section">
              <div class="mod-section-title">{{ t('roundtable.view.audit') }}</div>
              <div v-for="(a, i) in moderation.audit" :key="i" class="audit-row">
                <span class="verdict-badge" :class="a.verdict">{{ verdictLabel(a.verdict) }}</span>
                <span class="audit-speaker">{{ a.speaker }}：</span>
                <span class="audit-claim">“{{ a.claim }}”</span>
                <span class="audit-note" v-if="a.note">— {{ a.note }}</span>
              </div>
            </div>

            <!-- 收敛点 -->
            <div v-if="moderation.convergences?.length" class="mod-section">
              <div class="mod-section-title">{{ t('roundtable.view.convergences') }}</div>
              <div v-for="(c, i) in moderation.convergences" :key="i" class="conv-card">
                <div class="conv-head">
                  <span class="conv-badge" :class="c.type">{{ c.type === 'hard' ? t('roundtable.view.hardConv') : t('roundtable.view.softConv') }}</span>
                  <span class="conv-conf">{{ c.confidence }}</span>
                </div>
                <div class="conv-point">{{ c.point }}</div>
                <div class="conv-support">{{ c.supporting?.join(' · ') }}</div>
                <div v-if="c.soft_note" class="conv-note">{{ c.soft_note }}</div>
              </div>
            </div>

            <!-- 分岔点 -->
            <div v-if="moderation.divergences?.length" class="mod-section">
              <div class="mod-section-title">{{ t('roundtable.view.divergences') }}</div>
              <div v-for="(d, i) in moderation.divergences" :key="i" class="div-card">
                <div class="div-head">
                  <span class="div-badge" :class="d.root_cause">{{ rootCauseLabel(d.root_cause) }}</span>
                  <span class="div-topic">{{ d.topic }}</span>
                </div>
                <div class="div-positions">
                  <div v-for="(p, j) in d.positions" :key="j" class="div-position">
                    <span class="div-universe">{{ p.universe }}</span>
                    <span class="div-claim">{{ p.claim }}</span>
                  </div>
                </div>
                <p v-if="d.root_note" class="div-note">{{ d.root_note }}</p>
                <div v-if="d.decision_variable" class="div-variable">
                  {{ t('roundtable.view.decisionVariable') }}：<b>{{ d.decision_variable }}</b>
                </div>
              </div>
            </div>

            <!-- reframe -->
            <div v-if="moderation.reframe" class="mod-section">
              <div class="mod-section-title">{{ t('roundtable.view.reframe') }}</div>
              <p class="reframe-text">{{ moderation.reframe }}</p>
            </div>

            <!-- open questions -->
            <div v-if="moderation.open_questions?.length" class="mod-section">
              <div class="mod-section-title">{{ t('roundtable.view.openQuestions') }}</div>
              <ul class="oq-list">
                <li v-for="(q, i) in moderation.open_questions" :key="i">{{ q }}</li>
              </ul>
            </div>
          </section>

          <!-- 底部操作与闭环 -->
          <div class="bottom-bar">
            <button
              v-if="moderation && dialog.status === 'completed'"
              class="ghost-btn"
              type="button"
              @click="exportDecisionMemo"
            >
              ⤓ {{ t('roundtable.view.exportMemo') }}
            </button>
            <button
              v-if="moderation && dialog.status === 'completed'"
              class="ghost-btn"
              type="button"
              @click="exportReport"
            >
              ⤓ {{ t('roundtable.view.exportReport') }}
            </button>
            <button class="ghost-btn" type="button" @click="phase = 'setup'">{{ t('roundtable.view.newRound') }}</button>
            <button class="ghost-btn primary" type="button" @click="router.push(`/workbench/${projectId}`)">
              ▤ {{ t('workbench.navLink') }} →
            </button>
          </div>
        </template>
      </template>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import AppHeader from '../components/AppHeader.vue'
import {
  getRoundtableParticipants,
  openRoundtable,
  getRoundtableDialog,
  listRoundtables,
  deleteRoundtable,
  interjectRoundtableSpeech
} from '../api/roundtable'

const props = defineProps({
  projectId: { type: String, required: true }
})

const router = useRouter()
const route = useRoute()
const { t, te } = useI18n()

const loading = ref(true)
const phase = ref('setup') // setup | dialog
const topic = ref('')
const universes = ref([])
const related = ref([])
const chosenSessions = ref([])
const chosenPersons = ref([])
const selectedRounds = ref(2)
const opening = ref(false)
const setupError = ref('')
const dialogs = ref([])
const dialog = ref(null)
const dialogRunning = computed(() => dialog.value?.status === 'running')
const deleteDialogTarget = ref(null)
const deleteDialogBusy = ref(false)

const selectedInterjectTarget = ref('')
const interjectQuestion = ref('')
const interjecting = ref(false)
const interjectError = ref('')

const interjectTargets = computed(() => {
  const list = []
  for (const p of (dialog.value?.participants || [])) {
    list.push({
      ref: p.session_id || p.person_ref || p.speaker || p.label,
      label: p.label || p.person_ref || p.speaker
    })
  }
  return list
})

async function submitInterjection() {
  if (interjecting.value || !interjectQuestion.value.trim() || !dialog.value?.dialog_id) return
  interjecting.value = true
  interjectError.value = ''
  try {
    const targetRef = selectedInterjectTarget.value || interjectTargets.value[0]?.ref
    const res = await interjectRoundtableSpeech(dialog.value.dialog_id, {
      project_id: props.projectId,
      speaker_ref: targetRef,
      question: interjectQuestion.value.trim()
    })
    if (res.data?.dialog) {
      dialog.value = res.data.dialog
    }
    interjectQuestion.value = ''
  } catch (err) {
    interjectError.value = err?.message || String(err)
  } finally {
    interjecting.value = false
  }
}

function promptDeleteDialog(d) {
  deleteDialogTarget.value = d
}

function cancelDeleteDialog() {
  deleteDialogTarget.value = null
}

async function doDeleteDialog() {
  if (!deleteDialogTarget.value || deleteDialogBusy.value) return
  deleteDialogBusy.value = true
  try {
    await deleteRoundtable(deleteDialogTarget.value.dialog_id, props.projectId)
    dialogs.value = dialogs.value.filter(d => d.dialog_id !== deleteDialogTarget.value.dialog_id)
    deleteDialogTarget.value = null
  } catch (err) {
    console.error('Delete roundtable failed', err)
  } finally {
    deleteDialogBusy.value = false
  }
}
let pollTimer = null
let pollToken = 0
let pollStartedAt = 0
let pollAttempts = 0

const openMemoryIndex = ref(null)
function toggleCoreMemory(i) {
  openMemoryIndex.value = openMemoryIndex.value === i ? null : i
}

const moderation = computed(() => dialog.value?.moderation || null)

function archetypeLabel(key) {
  const i18nKey = `branch.archetype.${key}`
  return te(i18nKey) ? t(i18nKey) : (key || '')
}

function relLabel(kind) {
  const i18nKey = `relationship.relation.${kind}`
  return te(i18nKey) ? t(i18nKey) : (kind || '')
}

function verdictLabel(v) {
  const i18nKey = `roundtable.verdict.${v}`
  return te(i18nKey) ? t(i18nKey) : (v || '')
}

function roundStageTitle(roundNum, totalRounds) {
  const key = `roundtable.view.roundStageTitle.${roundNum}`
  if (te(key)) return t(key)
  return t('roundtable.view.roundStageTitle.4')
}

function rootCauseLabel(c) {
  const i18nKey = `roundtable.rootCause.${c}`
  return te(i18nKey) ? t(i18nKey) : (c || '')
}

// 主持人报告导出为《一页纸人生决策备忘录》
function exportDecisionMemo() {
  const d = dialog.value
  if (!d) return
  const m = d.moderation || {}

  const lines = []
  lines.push(`# ${t('roundtable.view.exportMemoTitle')}`)
  lines.push('')
  lines.push(`> **核心议题**：${d.topic || ''}`)
  lines.push(`> **记录时间**：${new Date(d.created_at || Date.now()).toLocaleDateString()}`)
  lines.push('')
  lines.push('---')
  lines.push('')

  if (m.summary) {
    lines.push('## 一、 决策总评与局势定性')
    lines.push('')
    lines.push(m.summary)
    lines.push('')
  }

  if (m.reframe) {
    lines.push('## 二、 核心决策变量与议题重构')
    lines.push('')
    lines.push(m.reframe)
    lines.push('')
  }

  if (m.convergences?.length) {
    lines.push('## 三、 跨宇宙独立印证规律（收敛点）')
    lines.push('')
    for (const c of m.convergences) {
      const typeLabel = c.type === 'hard' ? '硬收敛（客观必然）' : '软收敛（同源起点）'
      lines.push(`- **[${typeLabel}]** ${c.point}`)
      if (c.supporting?.length) lines.push(`  - 印证席位: ${c.supporting.join('、')}`)
    }
    lines.push('')
  }

  if (m.divergences?.length) {
    lines.push('## 四、 平行宇宙真实分岔与不可逆代价')
    lines.push('')
    for (const dv of m.divergences) {
      lines.push(`### [${rootCauseLabel(dv.root_cause)}] ${dv.topic}`)
      for (const p of dv.positions || []) {
        lines.push(`- **${p.universe}**：${p.claim}`)
      }
      if (dv.decision_variable) {
        lines.push(`- **核心可控变量**：\`${dv.decision_variable}\``)
      }
      lines.push('')
    }
  }

  if (m.open_questions?.length) {
    lines.push('## 五、 下一步必须验证的开放问题')
    lines.push('')
    for (const q of m.open_questions) {
      lines.push(`- [ ] ${q}`)
    }
    lines.push('')
  }

  lines.push('---')
  lines.push('*由 PRISM (Personal Reality Simulation Engine) 交叉验证生成*')

  const blob = new Blob([lines.join('\n')], { type: 'text/markdown;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `PRISM-Decision-Memo-${(d.topic || '').slice(0, 20).replace(/[\\/:*?"<>|\s]/g, '_')}.md`
  a.click()
  URL.revokeObjectURL(url)
}

// 主持人报告导出为 Markdown 文件
function exportReport() {
  const d = dialog.value
  if (!d || !moderation.value) return
  const m = moderation.value
  const lines = []

  lines.push(`# ${t('roundtable.view.exportTitle')}`)
  lines.push('')
  lines.push(`> ${t('roundtable.view.topic')}: ${d.topic}`)
  lines.push(`> ${t('roundtable.view.participants')}: ${(d.participants || []).map(p => p.label || p.speaker).join('、')}`)
  lines.push(`> ${d.created_at || ''}`)
  lines.push('')

  if (m.summary) {
    lines.push(`## ${t('roundtable.view.moderation')}`)
    lines.push('')
    lines.push(m.summary)
    lines.push('')
  }

  if (m.audit?.length) {
    lines.push(`## ${t('roundtable.view.audit')}`)
    lines.push('')
    for (const a of m.audit) {
      lines.push(`- **${verdictLabel(a.verdict)}** ${a.speaker}: “${a.claim}”${a.note ? ` — ${a.note}` : ''}`)
    }
    lines.push('')
  }

  if (m.convergences?.length) {
    lines.push(`## ${t('roundtable.view.convergences')}`)
    lines.push('')
    for (const c of m.convergences) {
      lines.push(`- [${c.type}] ${c.point}（${c.confidence}）`)
      if (c.supporting?.length) lines.push(`  - ${t('roundtable.view.supporting')}: ${c.supporting.join('、')}`)
      if (c.soft_note) lines.push(`  - ${c.soft_note}`)
    }
    lines.push('')
  }

  if (m.divergences?.length) {
    lines.push(`## ${t('roundtable.view.divergences')}`)
    lines.push('')
    for (const dv of m.divergences) {
      lines.push(`### [${rootCauseLabel(dv.root_cause)}] ${dv.topic}`)
      for (const p of dv.positions || []) {
        lines.push(`- ${p.universe}: ${p.claim}`)
      }
      if (dv.root_note) lines.push(`> ${dv.root_note}`)
      if (dv.decision_variable) {
        lines.push(`**${t('roundtable.view.decisionVariable')}**: ${dv.decision_variable}`)
      }
      lines.push('')
    }
  }

  if (m.reframe) {
    lines.push(`## ${t('roundtable.view.reframe')}`)
    lines.push('')
    lines.push(m.reframe)
    lines.push('')
  }

  if (m.open_questions?.length) {
    lines.push(`## ${t('roundtable.view.openQuestions')}`)
    lines.push('')
    for (const q of m.open_questions) lines.push(`- ${q}`)
    lines.push('')
  }

  if (d.transcript?.length) {
    lines.push('---')
    lines.push('')
    lines.push(`## ${t('roundtable.view.transcript')}`)
    lines.push('')
    for (const s of d.transcript) {
      lines.push(`**${s.speaker}**: ${s.content}`)
      lines.push('')
    }
  }

  const blob = new Blob([lines.join('\n')], { type: 'text/markdown;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `PRISM-roundtable-${(d.topic || '').slice(0, 20).replace(/[\\/:*?"<>|\s]/g, '_')}.md`
  a.click()
  URL.revokeObjectURL(url)
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms))
}

function stopPolling() {
  pollToken += 1
  if (pollTimer) {
    clearTimeout(pollTimer)
    pollTimer = null
  }
}

async function pollDialog() {
  const token = pollToken
  if (Date.now() - pollStartedAt > 10 * 60 * 1000) {
    setupError.value = '圆桌任务超过最大等待时间，请刷新查看状态'
    return
  }
  try {
    const res = await getRoundtableDialog(dialog.value.dialog_id, props.projectId)
    if (token !== pollToken) return
    dialog.value = res.data
    if (res.data.status === 'running') {
      pollAttempts = 0
      pollTimer = setTimeout(pollDialog, 3000)
    }
  } catch (err) {
    pollAttempts += 1
    if (pollAttempts <= 5) {
      pollTimer = setTimeout(pollDialog, Math.min(30000, 2000 * 2 ** pollAttempts))
    } else {
      setupError.value = err?.message || '圆桌状态读取失败，请稍后重试'
    }
  }
}

async function openDialog(dialogId) {
  stopPolling()
  const res = await getRoundtableDialog(dialogId, props.projectId)
  dialog.value = res.data
  phase.value = 'dialog' // 数据就绪后再切换，避免空帧渲染
  if (res.data.status === 'running') {
    pollStartedAt = Date.now()
    pollAttempts = 0
    pollTimer = setTimeout(pollDialog, 3000)
  }
}

async function open() {
  if (opening.value) return
  opening.value = true
  setupError.value = ''
  try {
    const res = await openRoundtable({
      project_id: props.projectId,
      topic: topic.value.trim(),
      total_rounds: selectedRounds.value,
      session_ids: chosenSessions.value,
      person_refs: chosenPersons.value
    })
    await openDialog(res.data.dialog_id)
    topic.value = ''
  } catch (e) {
    setupError.value = e?.message || String(e)
  } finally {
    opening.value = false
  }
}

onMounted(async () => {
  try {
    const [pRes, dRes] = await Promise.all([
      getRoundtableParticipants(props.projectId),
      listRoundtables(props.projectId)
    ])
    universes.value = pRes.data?.universes || []
    related.value = pRes.data?.related || []
    chosenSessions.value = universes.value.map(u => u.session_id)
    chosenPersons.value = related.value.map(r => r.person_ref)
    dialogs.value = dRes.data || []
  } catch (e) {
    setupError.value = e?.message || String(e)
  } finally {
    loading.value = false
  }
  // 深链接：?dialog=rt_xxx 直接打开历史圆桌
  const deepLink = route.query.dialog
  if (deepLink) {
    try {
      await openDialog(String(deepLink))
    } catch {
      /* 记录不存在则停留在开桌页 */
    }
  }
})

onBeforeUnmount(stopPolling)
</script>

<style scoped>
.roundtable-view {
  min-height: 100vh;
  background: var(--c-paper);
}

.navbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 32px;
  border-bottom: 1px solid var(--c-line);
  position: sticky;
  top: 0;
  background: var(--c-paper);
  z-index: 10;
}

.nav-brand {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
}

.nav-brand .brand-logo {
  height: 26px;
  width: auto;
}

.nav-brand .brand-word {
  font-family: 'Space Grotesk', 'Inter', sans-serif;
  font-weight: 700;
  font-size: 17px;
  letter-spacing: 3px;
}

.nav-links {
  display: flex;
  align-items: center;
  gap: 16px;
}

.graph-link {
  border: 1px solid var(--c-line-strong);
  background: var(--c-paper);
  padding: 6px 14px;
  font-size: 13px;
  cursor: pointer;
  font-family: inherit;
  border-radius: var(--r-sm);
  color: var(--c-ink-2);
}

.graph-link:hover {
  border-color: var(--c-brand);
  color: var(--c-brand);
}

.back-btn {
  border: 1px solid var(--c-line-strong);
  background: var(--c-paper);
  padding: 6px 14px;
  font-size: 13px;
  cursor: pointer;
  font-family: inherit;
  border-radius: var(--r-sm);
  color: var(--c-ink-2);
}

.back-btn:hover {
  border-color: var(--c-ink);
}

.main-content {
  max-width: 860px;
  margin: 0 auto;
  padding: 32px 24px 96px;
}

.state-box {
  text-align: center;
  padding: 80px 0;
  color: var(--c-ink-3);
}

.page-header {
  margin-bottom: 24px;
}

.page-title {
  font-size: 24px;
  font-weight: 700;
}

.page-sub {
  margin-top: 8px;
  color: var(--c-ink-4);
  font-size: 14px;
  line-height: 1.6;
}

.roundtopic {
  margin-top: 10px;
  font-size: 16px;
  color: var(--c-ink-2);
  font-weight: 600;
}

.box-title {
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 1px;
  color: var(--c-brand);
  margin: 22px 0 10px;
}

/* 历史圆桌 */
.history-box {
  margin-bottom: 8px;
}

.history-row {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 16px;
  padding: 10px 12px;
  border: 1px solid var(--c-line-soft);
  border-radius: var(--r-sm);
  margin-bottom: 6px;
  cursor: pointer;
  transition: border-color 0.15s;
}

.history-row:hover {
  border-color: var(--c-ink-4);
}

.history-topic {
  font-size: 14px;
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
}

.history-right {
  display: flex;
  align-items: center;
  gap: 10px;
}

.history-meta {
  font-size: 12px;
  color: var(--c-ink-4);
  white-space: nowrap;
}

.history-del-btn {
  opacity: 0;
  pointer-events: none;
  background: transparent;
  border: 1px solid transparent;
  color: var(--c-ink-4);
  font-size: 11px;
  cursor: pointer;
  padding: 2px 6px;
  border-radius: var(--r-sm);
  transition: all 0.15s;
}

.history-row:hover .history-del-btn {
  opacity: 1;
  pointer-events: auto;
  color: var(--c-ink-3);
}

.history-del-btn:hover {
  background: var(--c-bg-soft);
  color: var(--a-aggressive);
  border-color: var(--c-line);
}

/* 设置区 */
.setup-box {
  margin-top: 8px;
}

.topic-input {
  width: 100%;
  box-sizing: border-box;
  border: 1px solid var(--c-line-strong);
  padding: 12px 16px;
  font-size: 15px;
  font-family: inherit;
  border-radius: var(--r-sm);
  outline: none;
  resize: vertical;
  line-height: 1.6;
}

.topic-input:focus {
  border-color: var(--c-brand);
}

.empty-hint {
  font-size: 13px;
  color: var(--c-ink-4);
  padding: 12px 0;
}

.participant-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 14px;
  border: 1px solid var(--c-line-strong);
  border-radius: var(--r-sm);
  margin-bottom: 8px;
  cursor: pointer;
  font-size: 14px;
  background: var(--c-paper);
  transition: all var(--dur-fast);
}

.participant-row:hover {
  border-color: var(--c-ink);
  box-shadow: 2px 2px 0 var(--c-ink);
  transform: translate(-1px, -1px);
}

.participant-row.checked {
  border: 2px solid var(--c-brand);
  background: var(--c-brand-soft);
  box-shadow: 2px 2px 0 var(--c-brand);
  padding: 9px 13px;
}

.p-check {
  accent-color: var(--c-brand);
}

.archetype-badge {
  font-size: 11px;
  font-weight: 700;
  padding: 2px 9px;
  border-radius: var(--r-sm);
  color: var(--c-paper);
  background: var(--c-ink-2);
  white-space: nowrap;
}

.archetype-badge.aggressive { background: var(--a-aggressive); }
.archetype-badge.conservative { background: var(--a-conservative); }
.archetype-badge.balanced { background: var(--a-balanced); }
.archetype-badge.detour { background: var(--a-detour); }
.archetype-badge.exit { background: var(--a-exit); }

.p-label {
  font-weight: 700;
  white-space: nowrap;
}

.related-name {
  font-size: 15px;
}

.p-relation {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: var(--r-sm);
  background: #F0F0F0;
  color: var(--c-ink-3);
  white-space: nowrap;
}

.p-depth {
  font-size: 12px;
  font-weight: 700;
  color: var(--c-ink-3);
  white-space: nowrap;
}

.p-thin {
  font-size: 11px;
  color: var(--a-detour);
  border: 1px solid #E5D9A8;
  padding: 1px 8px;
  border-radius: var(--r-lg);
  white-space: nowrap;
}

.p-positioning {
  flex: 1;
  font-size: 12px;
  color: var(--c-ink-4);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.p-first {
  font-size: 11px;
  color: var(--a-detour);
  white-space: nowrap;
}

.open-btn {
  width: 100%;
  margin-top: 14px;
  background: var(--c-brand);
  color: var(--c-paper);
  border: 1px solid var(--c-brand);
  padding: 13px 24px;
  font-size: 15px;
  font-weight: 700;
  cursor: pointer;
  border-radius: var(--r-sm);
  font-family: inherit;
}

.open-btn:hover:not(:disabled) {
  background: var(--c-brand-deep);
}

.open-btn:disabled {
  background: var(--c-ink-5);
  cursor: not-allowed;
}

.error-text {
  color: var(--c-brand);
  font-size: 13px;
  margin-top: 10px;
}

/* 发言区 */
.speech-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
  margin-bottom: 24px;
}

.speech-bubble {
  border: 1px solid var(--c-line);
  border-radius: var(--r-md);
  padding: 16px 20px;
  background: var(--c-paper);
}

.speech-bubble.related {
  background: #FAF9F6;
  border-color: #E8E2D5;
}

.speech-bubble.userInterject {
  background: #FFFDF5;
  border: 1.5px solid var(--c-ink);
  box-shadow: 2px 2px 0 var(--c-ink);
}

.speech-bubble.replyInterject {
  background: #F8FAFC;
  border: 1.5px solid #0284C7;
  border-left-width: 4px;
}

.speech-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.speaker-name {
  font-size: 14px;
  font-weight: 700;
}

.speaker-type {
  font-size: 11px;
  color: #8B7355;
  border: 1px solid #E8E2D5;
  padding: 1px 8px;
  border-radius: var(--r-lg);
}

.speaker-type.user-tag {
  color: var(--c-paper);
  background: var(--c-ink);
  border-color: var(--c-ink);
  font-weight: 700;
}

.speaker-type.reply-tag {
  color: #0284C7;
  background: #E0F2FE;
  border-color: #BAE6FD;
  font-weight: 700;
}

.speech-fidelity-badge {
  font-size: 10px;
  font-weight: 700;
  color: #4F46E5;
  background: #EEF2FF;
  border: 1px solid #C7D2FE;
  padding: 1px 7px;
  border-radius: var(--r-sm);
  font-family: var(--font-mono, monospace);
}

/* 现场追问面板 */
.interjection-panel {
  border: 2px solid var(--c-ink);
  background: var(--c-bg-softer);
  padding: 18px 20px;
  border-radius: var(--r-md);
  margin-bottom: 28px;
  box-shadow: var(--shadow-pop-sm);
}

.interjection-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 14px;
  flex-wrap: wrap;
  gap: 8px;
}

.interjection-title {
  font-size: 14px;
  font-weight: 700;
  color: var(--c-ink);
  letter-spacing: 0.5px;
}

.interjection-hint {
  font-size: 12px;
  color: var(--c-ink-4);
}

.interjection-form {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.target-picker {
  display: flex;
  align-items: center;
  gap: 10px;
}

.target-label {
  font-size: 13px;
  font-weight: 700;
  color: var(--c-ink-2);
}

.target-select {
  border: 1px solid var(--c-line-strong);
  background: var(--c-paper);
  padding: 6px 12px;
  font-size: 13px;
  font-family: inherit;
  font-weight: 600;
  border-radius: var(--r-sm);
  outline: none;
  cursor: pointer;
}

.target-select:focus {
  border-color: var(--c-ink);
}

.interjection-input-group {
  display: flex;
  gap: 12px;
  align-items: stretch;
}

.interjection-input {
  flex: 1;
  border: 1px solid var(--c-line-strong);
  background: var(--c-paper);
  padding: 10px 14px;
  font-size: 14px;
  font-family: inherit;
  border-radius: var(--r-sm);
  outline: none;
  resize: vertical;
  line-height: 1.5;
}

.interjection-input:focus {
  border-color: var(--c-ink);
}

.interject-btn {
  background: var(--c-ink);
  color: var(--c-paper);
  border: 1px solid var(--c-ink);
  padding: 0 20px;
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
  border-radius: var(--r-sm);
  font-family: inherit;
  white-space: nowrap;
  transition: all var(--dur-fast);
}

.interject-btn:hover:not(:disabled) {
  background: var(--c-brand);
  border-color: var(--c-brand);
  box-shadow: 2px 2px 0 var(--c-ink);
  transform: translate(-1px, -1px);
}

.interject-btn:disabled {
  background: var(--c-ink-5);
  border-color: var(--c-ink-5);
  cursor: not-allowed;
}

.speech-content {
  font-size: 14px;
  line-height: 1.9;
  color: var(--c-ink-2);
}

.running-hint {
  display: flex;
  align-items: center;
  gap: 10px;
  color: var(--c-ink-4);
  font-size: 13px;
  padding: 12px 0;
}

.pulse {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--c-brand);
  animation: pulse 1.2s infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.2; }
}

/* 主持人报告 */
.moderation-box {
  border: 2px solid var(--c-ink);
  border-radius: var(--r-md);
  padding: 24px 28px;
}

.mod-title {
  font-size: 17px;
  font-weight: 700;
  margin-bottom: 10px;
}

.mod-summary {
  font-size: 14px;
  color: var(--c-ink-3);
  padding-bottom: 14px;
  border-bottom: 1px solid var(--c-line-soft);
  line-height: 1.7;
}

/* 跨宇宙认知收敛与宿命量化仪表板 */
.epistemic-dashboard {
  margin-top: 18px;
  margin-bottom: 20px;
  padding: 16px 18px;
  background: var(--c-bg-softer, #F7F5F0);
  border: 1.5px solid var(--c-ink);
  border-radius: var(--r-sm);
  box-shadow: 2px 2px 0 var(--c-ink);
}

.epistemic-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 14px;
}

.epistemic-badge {
  font-size: 11px;
  font-weight: 700;
  color: var(--c-brand);
  background: #FFF3EB;
  border: 1px solid var(--c-brand);
  padding: 2px 6px;
  border-radius: var(--r-sm);
}

.epistemic-title {
  font-size: 14px;
  font-weight: 700;
  color: var(--c-ink);
}

.epistemic-gauges {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 14px;
  margin-bottom: 16px;
}

.gauge-card {
  background: var(--c-paper, #FFFFFF);
  border: 1px solid var(--c-line-strong);
  padding: 10px 12px;
  border-radius: var(--r-sm);
}

.gauge-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.gauge-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--c-ink-3);
}

.gauge-value {
  font-size: 14px;
  font-weight: 800;
  font-family: var(--font-mono, monospace);
  color: var(--c-ink-1);
}

.gauge-bar-track {
  width: 100%;
  height: 6px;
  background: var(--c-line-soft, #E5E5E5);
  border-radius: 3px;
  overflow: hidden;
}

.gauge-bar-fill {
  height: 100%;
  border-radius: 3px;
  transition: width 0.4s ease-out;
}

.gauge-bar-fill.convergence {
  background: var(--c-brand, #E05D44);
}

.gauge-bar-fill.inevitability {
  background: #B45309;
}

.gauge-bar-fill.leverage {
  background: #0284C7;
}

.epistemic-details-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.epistemic-col-title {
  font-size: 12px;
  font-weight: 700;
  color: var(--c-ink-2);
  margin-bottom: 8px;
  letter-spacing: 0.5px;
}

.epistemic-item-card {
  background: var(--c-paper, #FFFFFF);
  border: 1px solid var(--c-line-soft);
  padding: 10px 12px;
  border-radius: var(--r-sm);
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-bottom: 8px;
}

.epistemic-item-card.constraint {
  border-left: 3px solid #B45309;
}

.epistemic-item-card.leverage {
  border-left: 3px solid #0284C7;
}

.item-main-text {
  font-size: 13px;
  font-weight: 700;
  color: var(--c-ink-1);
  line-height: 1.5;
}

.item-sub-row {
  font-size: 11px;
  color: var(--c-ink-3);
  line-height: 1.4;
}

.item-sub-label {
  font-weight: 700;
  color: var(--c-ink-4);
}

.item-sub-val.highlight {
  color: #0284C7;
  font-weight: 700;
}

.mod-section {
  margin-top: 20px;
}

.mod-section-title {
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 1px;
  color: var(--c-brand);
  margin-bottom: 10px;
}

/* 审计 */
.audit-row {
  display: flex;
  align-items: baseline;
  gap: 8px;
  flex-wrap: wrap;
  padding: 7px 0;
  border-bottom: 1px dashed var(--c-bg-soft);
  font-size: 13px;
  line-height: 1.6;
}

.verdict-badge {
  font-size: 11px;
  font-weight: 700;
  padding: 1px 8px;
  border-radius: var(--r-sm);
  color: var(--c-paper);
  white-space: nowrap;
}

.verdict-badge.grounded { background: var(--a-balanced); }
.verdict-badge.unsupported { background: var(--c-ink-4); }
.verdict-badge.contradicted { background: var(--a-aggressive); }
.verdict-badge.documented_vs_claimed { background: var(--a-detour); }

.audit-speaker {
  font-weight: 700;
}

.audit-claim {
  color: var(--c-ink-2);
}

.audit-note {
  color: var(--c-ink-4);
}

/* 收敛 */
.conv-card {
  border: 1px solid var(--c-line);
  border-radius: var(--r-sm);
  padding: 12px 16px;
  margin-bottom: 8px;
}

.conv-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.conv-badge {
  font-size: 11px;
  font-weight: 700;
  padding: 1px 8px;
  border-radius: var(--r-sm);
  color: var(--c-paper);
}

.conv-badge.hard { background: var(--a-balanced); }
.conv-badge.soft { background: var(--c-ink-4); }

.conv-conf {
  font-size: 11px;
  color: var(--c-ink-4);
  text-transform: uppercase;
}

.conv-point {
  font-size: 14px;
  font-weight: 600;
  line-height: 1.6;
}

.conv-support {
  font-size: 12px;
  color: var(--c-ink-3);
  margin-top: 4px;
}

.conv-note {
  font-size: 12px;
  color: var(--a-detour);
  margin-top: 4px;
}

/* 分岔 */
.div-card {
  border: 1px solid var(--c-line);
  border-radius: var(--r-sm);
  padding: 12px 16px;
  margin-bottom: 8px;
}

.div-head {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
  flex-wrap: wrap;
}

.div-badge {
  font-size: 11px;
  font-weight: 700;
  padding: 1px 8px;
  border-radius: var(--r-sm);
  color: var(--c-paper);
  white-space: nowrap;
}

.div-badge.choice { background: var(--a-aggressive); }
.div-badge.environment { background: var(--a-conservative); }
.div-badge.depth { background: var(--a-exit); }

.div-topic {
  font-size: 14px;
  font-weight: 600;
}

.div-positions {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.div-position {
  display: flex;
  gap: 10px;
  font-size: 13px;
  line-height: 1.6;
}

.div-universe {
  font-weight: 700;
  white-space: nowrap;
  min-width: 90px;
}

.div-claim {
  color: var(--c-ink-2);
}

.div-note {
  font-size: 12px;
  color: var(--c-ink-3);
  margin-top: 8px;
}

.div-variable {
  margin-top: 10px;
  font-size: 13px;
  background: var(--c-brand-soft);
  border-left: 3px solid var(--c-brand);
  padding: 8px 12px;
  line-height: 1.6;
}

/* reframe / oq */
.reframe-text {
  font-size: 14px;
  line-height: 1.8;
  background: var(--c-bg-softer);
  padding: 14px 18px;
  border-left: 3px solid var(--c-ink);
}

.oq-list {
  padding-left: 18px;
  font-size: 13px;
  color: var(--c-ink-3);
  line-height: 1.9;
}

/* 底部 */
.bottom-bar {
  margin-top: 24px;
  display: flex;
  gap: 12px;
}

.ghost-btn {
  border: 1px solid var(--c-line-strong);
  background: var(--c-paper);
  padding: 8px 18px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  font-family: inherit;
  border-radius: var(--r-sm);
  color: var(--c-ink-2);
  transition: all var(--dur-fast);
}

.ghost-btn:hover {
  border-color: var(--c-ink);
  color: var(--c-ink);
  box-shadow: var(--shadow-pop-sm);
  transform: translate(-1px, -1px);
}

.ghost-btn:active {
  transform: translate(1px, 1px);
  box-shadow: 1px 1px 0 var(--c-ink);
}

.ghost-btn.primary {
  background: var(--c-brand);
  color: var(--c-paper);
  border-color: var(--c-brand);
  font-weight: 700;
}

.ghost-btn.primary:hover {
  background: var(--c-brand-deep);
  border-color: var(--c-brand-deep);
  color: var(--c-paper);
  box-shadow: var(--shadow-pop-sm);
  transform: translate(-1px, -1px);
}

.ghost-btn.primary:active {
  transform: translate(1px, 1px);
  box-shadow: 1px 1px 0 var(--c-ink);
}

/* 确认弹窗 */
.modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
  padding: 20px;
}

.modal-dialog {
  background: var(--c-paper);
  border: 2px solid var(--c-ink);
  border-radius: var(--r-md);
  box-shadow: var(--shadow-pop);
  max-width: 440px;
  width: 100%;
  padding: 24px;
}

.modal-title {
  font-size: 15px;
  font-weight: 700;
  margin-bottom: 12px;
  display: flex;
  align-items: center;
}

.status-dot.alert {
  color: var(--a-aggressive);
}

.modal-desc {
  font-size: 13px;
  color: var(--c-ink-3);
  line-height: 1.7;
  margin-bottom: 20px;
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

.modal-btn {
  font-family: inherit;
  font-size: 13px;
  font-weight: 700;
  padding: 8px 18px;
  border-radius: var(--r-sm);
  cursor: pointer;
  border: 1px solid var(--c-ink);
  transition: all 0.15s;
}

.modal-btn.cancel {
  background: var(--c-paper);
  color: var(--c-ink-2);
  border-color: var(--c-line-strong);
}

.modal-btn.cancel:hover {
  border-color: var(--c-ink);
  color: var(--c-ink);
}

.modal-btn.delete {
  background: var(--a-aggressive);
  color: var(--c-paper);
  border-color: var(--a-aggressive);
}

.modal-btn.delete:hover:not(:disabled) {
  background: #c93b40;
  box-shadow: var(--shadow-pop-sm);
  transform: translate(-1px, -1px);
}

.modal-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* Letta 核心工作记忆块样式 (Neo-Brutalist) */
.core-memory-wrapper {
  margin-top: 10px;
  border-top: 1px dashed var(--c-line-soft);
  padding-top: 8px;
}

.core-memory-toggle {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: var(--c-bg-subtle, #FAF9F6);
  border: 1px solid var(--c-line-soft);
  padding: 3px 8px;
  font-size: 11px;
  font-weight: 700;
  color: var(--c-ink-3);
  border-radius: var(--r-sm);
  cursor: pointer;
  transition: all var(--dur-fast);
}

.core-memory-toggle:hover {
  border-color: var(--c-ink);
  color: var(--c-ink-1);
}

.core-memory-toggle.active {
  background: var(--c-ink);
  color: var(--c-paper);
  border-color: var(--c-ink);
}

.memory-toggle-icon {
  font-size: 8px;
}

.memory-edit-count {
  font-size: 10px;
  background: #FEF3C7;
  color: #92400E;
  border: 1px solid #FDE68A;
  padding: 0 4px;
  border-radius: 2px;
}

.core-memory-toggle.active .memory-edit-count {
  background: #F59E0B;
  color: #1F2937;
  border-color: #F59E0B;
}

.core-memory-drawer {
  margin-top: 8px;
  padding: 10px 12px;
  background: var(--c-paper, #FFFFFF);
  border: 1px solid var(--c-line-soft);
  border-radius: var(--r-sm);
  box-shadow: var(--shadow-pop-sm);
}

.memory-edits-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 8px;
  padding-bottom: 8px;
  border-bottom: 1px dashed var(--c-line-soft);
}

.memory-edit-pill {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  background: #FFFBEB;
  border: 1px solid #FDE68A;
  padding: 2px 6px;
  border-radius: var(--r-sm);
}

.edit-action-badge {
  font-size: 9px;
  font-weight: 700;
  color: #B45309;
}

.edit-block-badge {
  font-size: 9px;
  font-weight: 700;
  color: #6B7280;
}

.edit-content-text {
  font-weight: 600;
  color: var(--c-ink-1);
}

.core-blocks-grid {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 8px;
}

.core-block {
  padding: 8px 10px;
  background: var(--c-bg-subtle, #FAF9F6);
  border: 1px solid var(--c-line-soft);
  border-radius: var(--r-sm);
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.core-block.persona {
  border-left: 3px solid #6366F1;
}

.core-block.human {
  border-left: 3px solid #0EA5E9;
}

.core-block.situation {
  border-left: 3px solid #10B981;
}

.block-label {
  font-size: 10px;
  font-weight: 700;
  color: var(--c-ink-3);
  letter-spacing: 0.5px;
}

.block-body {
  font-size: 11px;
  color: var(--c-ink-2);
  line-height: 1.5;
}

@media (max-width: 768px) {
  .core-blocks-grid {
    grid-template-columns: 1fr;
  }
}


/* 辩论轮次选择器 (Rounds Selector) */
.rounds-selector-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 10px;
  margin-bottom: 20px;
}

@media (max-width: 768px) {
  .rounds-selector-grid {
    grid-template-columns: 1fr;
  }
}

.round-option-btn {
  text-align: left;
  background: var(--c-paper, #FFFFFF);
  border: 1px solid var(--c-line-strong);
  border-radius: var(--r-sm);
  padding: 12px 14px;
  cursor: pointer;
  transition: all var(--t-fast);
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.round-option-btn:hover {
  border-color: var(--c-ink);
  background: #FAF9F6;
}

.round-option-btn.active {
  border: 2px solid var(--c-ink);
  background: #FAF9F6;
  box-shadow: 2px 2px 0 var(--c-ink);
}

.round-btn-head {
  display: flex;
  align-items: center;
  gap: 8px;
}

.round-radio-box {
  width: 12px;
  height: 12px;
  border: 1.5px solid var(--c-ink);
  border-radius: 2px;
  display: inline-block;
  background: var(--c-paper, #FFFFFF);
}

.round-radio-box.checked {
  background: var(--c-ink);
  box-shadow: inset 0 0 0 2px var(--c-paper, #FFFFFF);
}

.round-num-label {
  font-size: 13px;
  font-weight: 700;
  color: var(--c-ink);
}

.round-rec-badge {
  font-size: 10px;
  font-weight: 700;
  color: #B45309;
  background: #FEF3C7;
  border: 1px solid #FDE68A;
  padding: 1px 6px;
  border-radius: var(--r-sm);
}

.round-desc-text {
  font-size: 11px;
  color: var(--c-ink-3);
  line-height: 1.4;
  padding-left: 20px;
}

/* 轮次分割指示带 (Round Divider) */
.round-divider-block {
  display: flex;
  align-items: center;
  gap: 14px;
  margin: 20px 0 12px 0;
}

.round-divider-line {
  flex: 1;
  height: 1px;
  background: var(--c-line-strong);
}

.round-divider-pill {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  background: #F3F0E6;
  border: 1.5px solid var(--c-ink);
  padding: 4px 14px;
  border-radius: var(--r-sm);
  box-shadow: 2px 2px 0 var(--c-ink);
}

.round-pill-badge {
  font-size: 11px;
  font-weight: 800;
  color: var(--c-paper);
  background: var(--c-ink);
  padding: 1px 7px;
  border-radius: 2px;
  font-family: var(--font-mono, monospace);
  letter-spacing: 0.5px;
}

.round-pill-title {
  font-size: 12px;
  font-weight: 700;
  color: var(--c-ink);
}

.speaker-round-badge {
  font-size: 10px;
  font-weight: 800;
  color: #0369A1;
  background: #E0F2FE;
  border: 1px solid #BAE6FD;
  padding: 1px 6px;
  border-radius: 2px;
  font-family: var(--font-mono, monospace);
}

</style>
