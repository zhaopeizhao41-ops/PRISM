<template>
  <div class="workbench-view">
    <!-- 顶部统一导航 -->
    <AppHeader :project-id="projectId" :current-step="viewMode" />

    <div class="main-content">
      <!-- ============ 工作台模式 ============ -->
      <template v-if="viewMode === 'workbench'">
        <header class="page-header">
          <div class="header-left">
            <h1 class="page-title">▤ {{ t('workbench.title') }}</h1>
            <p class="page-meta">{{ t('workbench.subtitle') }}</p>
          </div>
        </header>

        <section v-if="!loading && nextAction" class="next-action-panel" :class="`tone-${nextAction.tone}`">
          <div class="next-action-mark" aria-hidden="true">→</div>
          <div class="next-action-copy">
            <div class="next-action-label">{{ t('workbench.nextAction.label') }}</div>
            <h2>{{ nextAction.title }}</h2>
            <p>{{ nextAction.description }}</p>
          </div>
          <button class="link-btn primary next-action-btn" type="button" @click="goToNextAction">
            {{ nextAction.cta }} →
          </button>
        </section>

        <div v-if="loading" class="state-box">{{ t('common.loading') }}</div>

        <template v-else>
          <!-- 步骤 1：画像 -->
          <section class="step-section" :class="{ 'is-open': expandedStep === 1 }">
            <div class="step-head" @click="toggleStep(1)">
              <span class="step-num">01</span>
              <span class="step-title">{{ t('workbench.stepProfile') }}</span>
              <span v-if="model" class="step-badge done">✓ v{{ model.model_version }}</span>
              <span v-else class="step-badge pending">{{ t('workbench.stepPending') }}</span>
              <span class="step-chevron" :class="{ open: expandedStep === 1 }">▾</span>
            </div>
            <div v-if="expandedStep === 1 && model" class="step-body profile-line">
              <p class="basic-line">{{ basicLine }}</p>
              <p class="current-line">{{ model.current_state }}</p>
              <div v-if="wants.length || avoids.length" class="goal-rows">
                <div v-if="wants.length" class="goal-row">
                  <span class="goal-tag want">{{ t('profile.view.want') }}</span>
                  <span v-for="(w, i) in wants" :key="'w' + i" class="goal-chip want">✓ {{ w.content }}</span>
                </div>
                <div v-if="avoids.length" class="goal-row">
                  <span class="goal-tag avoid">{{ t('profile.view.avoid') }}</span>
                  <span v-for="(a, i) in avoids" :key="'a' + i" class="goal-chip avoid">✕ {{ a.content }}</span>
                </div>
              </div>
              <div class="step-body-action">
                <button class="link-btn" type="button" @click="router.push(`/profile/${projectId}`)">
                  {{ t('workbench.viewProfile') }} →
                </button>
              </div>
            </div>
          </section>

          <div class="step-flow"></div>

          <!-- 步骤 2：分支 -->
          <section class="step-section" :class="{ 'is-open': expandedStep === 2 }">
            <div class="step-head" @click="toggleStep(2)">
              <span class="step-num">02</span>
              <span class="step-title">{{ t('workbench.stepBranches') }}</span>
              <span v-if="branchCount" class="step-badge done">{{ t('workbench.branchCount', { n: branchCount }) }}</span>
              <span v-else class="step-badge pending">{{ t('workbench.stepPending') }}</span>
              <span class="step-chevron" :class="{ open: expandedStep === 2 }">▾</span>
            </div>
            <div v-if="expandedStep === 2" class="step-body">
              <template v-if="branches.length">
                <div
                  v-for="b in branches"
                  :key="b.branch_id"
                  class="branch-row"
                  role="button"
                  @click="router.push(`/branches/${projectId}`)"
                >
                  <span class="archetype-badge" :class="b.archetype">{{ archetypeLabel(b.archetype) }}</span>
                  <span class="branch-positioning">{{ b.positioning }}</span>
                  <span class="branch-fit">{{ b.fit_score }}</span>
                </div>
                <div class="step-body-action">
                  <button class="link-btn" type="button" @click="router.push(`/branches/${projectId}`)">
                    {{ t('workbench.manageBranches') }} →
                  </button>
                </div>
              </template>
              <button v-else class="link-btn primary" type="button" @click="router.push(`/branches/${projectId}`)">
                {{ t('workbench.manageBranches') }} →
              </button>
            </div>
          </section>

          <div class="step-flow"></div>

          <!-- 步骤 3：宇宙推演（核心工作区） -->
          <section class="step-section" :class="{ 'is-open': expandedStep === 3 }">
            <div class="step-head" @click="toggleStep(3)">
              <span class="step-num">03</span>
              <span class="step-title">{{ t('workbench.stepEvolution') }}</span>
              <span v-if="sessions.length" class="step-badge done">{{ t('workbench.universeCount', { n: sessions.length }) }}</span>
              <span v-else class="step-badge pending">{{ t('workbench.noUniverses') }}</span>
              <span class="step-chevron" :class="{ open: expandedStep === 3 }">▾</span>
            </div>

            <template v-if="expandedStep === 3">
            <div v-if="!sessions.length" class="step-body">
              <button class="link-btn primary" type="button" @click="router.push(`/branches/${projectId}`)">
                {{ t('workbench.goEvolve') }} →
              </button>
            </div>

            <div v-else class="universe-list">
              <div v-for="s in sessions" :key="s.session_id" class="universe-card" :class="{ active: activeSessionId === s.session_id }">
                <div class="uni-head" @click="selectSession(s)">
                  <span class="archetype-badge" :class="s.source_branch_archetype">
                    {{ archetypeLabel(s.source_branch_archetype) }}
                  </span>
                  <span class="uni-positioning">{{ s.source_branch_positioning }}</span>
                  <span class="uni-progress">{{ s.stages_done }}/{{ s.stage_count }}</span>
                  <span class="uni-status" :class="s.status">{{ statusLabel(s.status) }}</span>
                </div>

                <!-- 展开的操作区 -->
                <div v-if="activeSessionId === s.session_id" class="uni-body">
                  <!-- 进度轴 -->
                  <div v-if="activeSession" class="stage-track">
                    <span
                      v-for="i in activeSession.stage_count"
                      :key="i"
                      class="stage-dot"
                      :class="{ done: i <= activeSession.stages_done }"
                    >{{ i }}</span>
                  </div>

                  <!-- Realism 真实性摘要条 -->
                  <div v-if="lastStageRealism" class="realism-strip">
                    <!-- 上排：健康条 + 压力条 + 财务胶囊 -->
                    <div class="realism-row top">
                      <!-- 健康 -->
                      <div class="meter-block">
                        <div class="meter-label">
                          <span class="lbl-name">{{ t('workbench.realism.health') }}</span>
                          <span class="lbl-val">{{ healthText }}</span>
                        </div>
                        <div class="meter-track">
                          <div
                            class="meter-fill health"
                            :style="{ width: healthPct + '%' }"
                          ></div>
                        </div>
                      </div>
                      <!-- 压力 -->
                      <div class="meter-block">
                        <div class="meter-label">
                          <span class="lbl-name">{{ t('workbench.realism.stress') }}</span>
                          <span class="lbl-val">{{ stressText }}</span>
                        </div>
                        <div class="meter-track">
                          <div
                            class="meter-fill stress"
                            :style="{ width: stressPct + '%' }"
                          ></div>
                        </div>
                      </div>
                      <!-- 财务胶囊 -->
                      <div class="finance-pills">
                        <span
                          class="pill cash"
                          :class="{ warn: cashMonths <= 1 }"
                        >
                          {{ t('workbench.realism.cashMonths', { n: cashMonths }) }}
                        </span>
                        <span
                          v-if="debtMonths > 0"
                          class="pill debt"
                        >
                          {{ t('workbench.realism.debtMonths', { n: debtMonths }) }}
                        </span>
                        <span class="pill stability">
                          {{ t('workbench.realism.incomeStability', { n: incomeStability }) }}
                        </span>
                      </div>
                    </div>

                    <!-- 中排：关系张力 chips -->
                    <div v-if="relationships.length" class="realism-row mid">
                      <span class="chip-label">{{ t('workbench.realism.tensionLabel') }}</span>
                      <div class="tension-chips">
                        <span
                          v-for="(r, idx) in relationships"
                          :key="idx"
                          class="tension-chip"
                          :class="tensionClass(r.tension)"
                          :title="r.last_event || ''"
                        >
                          {{ r.name }} · {{ r.tension }}
                        </span>
                      </div>
                    </div>

                    <!-- 下排：意外事件彩条 or 因果警告 -->
                    <div
                      v-if="lifeEvent || causalWarnings"
                      class="realism-row bottom"
                    >
                      <div
                        v-if="lifeEvent"
                        class="life-event"
                        :class="lifeEvent.kind"
                      >
                        <span class="le-tag">
                          {{ lifeEvent.kind === 'good'
                            ? t('workbench.realism.goodLuck')
                            : t('workbench.realism.badLuck') }}
                        </span>
                        <span class="le-template">{{ lifeEvent.template }}</span>
                      </div>
                      <div
                        v-if="causalWarnings"
                        class="causal-warn"
                        :title="causalWarningsText"
                      >
                        <span class="cw-tag">!</span>
                        {{ t('workbench.realism.causalWarn', { n: causalWarningsCount }) }}
                      </div>
                    </div>
                  </div>

                  <!-- 最近阶段摘要 -->
                  <div v-if="lastStage" class="last-stage">
                    <div class="world-grid">
                      <div v-for="dim in dims" :key="dim.key" class="world-cell">
                        <div class="world-dim">{{ t(`evolution.dim.${dim.key}`) }}</div>
                        <div class="world-val">{{ lastStage.world_state?.[dim.key] || '—' }}</div>
                      </div>
                    </div>
                    <p class="snapshot">{{ lastStage.state_snapshot }}</p>
                  </div>

                  <!-- 分叉裁决 -->
                  <div v-if="activeFork" class="fork-panel">
                    <div class="fork-tag">{{ t('workbench.forkTag') }}</div>
                    <div class="fork-q">{{ activeFork.question }}</div>
                    <div class="fork-options">
                      <button
                        v-for="(opt, i) in activeFork.options"
                        :key="i"
                        class="fork-opt"
                        type="button"
                        :disabled="advancing"
                        @click="chooseFork(i)"
                      >
                        <b>{{ opt.label }}</b>
                        <span class="opt-cond">{{ opt.condition }}</span>
                      </button>
                    </div>
                  </div>

                  <!-- 注入事件 + 推进 -->
                  <div v-else class="advance-row">
                    <input
                      v-model="eventInput"
                      class="event-input"
                      :placeholder="t('workbench.eventPlaceholder')"
                      :disabled="advancing || activeSession?.status !== 'active'"
                    />
                    <button
                      class="advance-btn"
                      type="button"
                      :disabled="advancing || activeSession?.status !== 'active'"
                      @click="advance"
                    >
                      {{ advancing ? t('workbench.advancing') : `▶ ${t('workbench.advance')}` }}
                    </button>
                  </div>

                  <p v-if="advanceError" class="error-line">{{ advanceError }}</p>

                  <div class="uni-links">
                    <button class="mini-link" type="button" @click="router.push(`/evolution/${s.session_id}`)">
                      {{ t('workbench.openDetail') }} →
                    </button>
                  </div>
                </div>
              </div>

              <!-- 跨维对比引导入口 -->
              <div v-if="sessions.length >= 2" class="step-body-action">
                <button class="link-btn" type="button" @click="router.push(`/compare/${projectId}`)">
                  ⇄ {{ t('workbench.compare') }} →
                </button>
              </div>
            </div>
            </template>
          </section>

          <div class="step-flow"></div>

          <!-- 步骤 4：圆桌 -->
          <section class="step-section" :class="{ 'is-open': expandedStep === 4 }">
            <div class="step-head" @click="toggleStep(4)">
              <span class="step-num">04</span>
              <span class="step-title">{{ t('workbench.stepRoundtable') }}</span>
              <span v-if="roundtableCount" class="step-badge done">{{ t('workbench.roundtableCount', { n: roundtableCount }) }}</span>
              <span v-else class="step-badge pending">{{ t('workbench.stepPending') }}</span>
              <span class="step-chevron" :class="{ open: expandedStep === 4 }">▾</span>
            </div>
            <div v-if="expandedStep === 4" class="step-body">
              <template v-if="roundtables.length">
                <div
                  v-for="d in roundtables"
                  :key="d.dialog_id"
                  class="rt-row"
                  role="button"
                  @click="router.push(`/roundtable/${projectId}?dialog=${d.dialog_id}`)"
                >
                  <span class="rt-topic">{{ d.topic }}</span>
                  <span class="rt-meta">{{ d.participant_count }} {{ t('roundtable.view.people') }} · {{ d.speech_count }} {{ t('roundtable.view.speeches') }}</span>
                </div>
              </template>
              <button class="link-btn primary" type="button" @click="router.push(`/roundtable/${projectId}`)">
                {{ t('workbench.startRoundtable') }} →
              </button>
            </div>
          </section>
        </template>
      </template>

      <!-- ============ 图谱模式 ============ -->
      <template v-else>
        <!-- 图谱：无轮询，仅在推演等数据变化后刷新（GraphPanel 自带刷新按钮） -->
        <div class="graph-shell">
          <div v-if="!graphLoaded && graphLoading" class="graph-state">{{ t('common.loading') }}</div>
          <div v-else-if="graphError" class="graph-state error">{{ graphError }}</div>
          <div v-else-if="!graphId" class="graph-state">{{ t('profile.view.noGraph') }}</div>
          <div v-else-if="!graphData" class="graph-state">{{ t('graphView.emptyGraph') }}</div>
          <GraphPanel
            v-else
            :key="refreshKey"
            :graphData="graphData"
            :loading="graphLoading"
            :currentPhase="4"
          />
        </div>
      </template>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import AppHeader from '../components/AppHeader.vue'
import GraphPanel from '../components/GraphPanel.vue'
import { getProject, getGraphData } from '../api/graph'
import { getPersonalModel, getProfileProjects } from '../api/profile'
import { getBranches } from '../api/branch'
import { listRoundtables } from '../api/roundtable'
import {
  listEvolutionSessions,
  getEvolutionSession,
  advanceEvolution,
  resolveEvolutionFork,
} from '../api/evolution'

const props = defineProps({
  projectId: { type: String, required: true }
})

const router = useRouter()
const route = useRoute()
const { t, te } = useI18n()

// ---------- 模式切换 ----------
const viewMode = ref(route.query.view === 'graph' ? 'graph' : 'workbench')

function switchMode(mode) {
  viewMode.value = mode
  router.replace({ query: mode === 'graph' ? { view: 'graph' } : {} })
}

// ---------- 工作台数据 ----------
const loading = ref(true)
const model = ref(null)
const branchCount = ref(0)
const roundtableCount = ref(0)
const branches = ref([])
const roundtables = ref([])
const sessions = ref([])
const activeSessionId = ref('')
const activeSession = ref(null)

const advanceError = ref('')
const advancing = ref(false)
const eventInput = ref('')
const forkGate = ref(null)

// 步骤展开/折叠：默认全部折叠
const expandedStep = ref(0)

function toggleStep(id) {
  expandedStep.value = expandedStep.value === id ? 0 : id
}

// 步骤完成状态
const stepStates = computed(() => ({
  1: model.value ? 'done' : 'pending',
  2: branchCount.value > 0 ? 'done' : 'pending',
  3: sessions.value.length > 0
    ? (sessions.value.some(s => s.status === 'active' && s.stages_done < s.stage_count) ? 'active' : 'done')
    : 'pending',
  4: roundtableCount.value > 0 ? 'done' : 'pending',
}))

const dims = [
  { key: 'career' }, { key: 'family' },
  { key: 'resources' }, { key: 'psyche' },
]

// 推演中的宇宙数（图谱 tab 橙点提示用）
const evolvingCount = computed(() =>
  sessions.value.filter(s => s.status === 'active' && s.stages_done < s.stage_count).length
)

// 根据项目实际进度给出唯一的下一步，避免用户在流程页之间来回寻找入口。
const nextAction = computed(() => {
  if (!model.value) {
    return {
      tone: 'start',
      title: t('workbench.nextAction.profileTitle'),
      description: t('workbench.nextAction.profileDescription'),
      cta: t('workbench.nextAction.profileCta'),
      path: `/profile/create?project=${encodeURIComponent(props.projectId)}`,
    }
  }

  const active = sessions.value.find(s =>
    s.status === 'active' && Number(s.stages_done || 0) < Number(s.stage_count || 0)
  )
  if (active) {
    return {
      tone: 'continue',
      title: t('workbench.nextAction.evolutionTitle'),
      description: t('workbench.nextAction.evolutionDescription'),
      cta: t('workbench.nextAction.evolutionCta'),
      path: `/evolution/${active.session_id}`,
    }
  }

  if (!branches.value.length) {
    return {
      tone: 'start',
      title: t('workbench.nextAction.branchesTitle'),
      description: t('workbench.nextAction.branchesDescription'),
      cta: t('workbench.nextAction.branchesCta'),
      path: `/branches/${props.projectId}`,
    }
  }

  if (!sessions.value.length) {
    return {
      tone: 'continue',
      title: t('workbench.nextAction.evolutionStartTitle'),
      description: t('workbench.nextAction.evolutionStartDescription'),
      cta: t('workbench.nextAction.evolutionStartCta'),
      path: `/branches/${props.projectId}`,
    }
  }

  if (sessions.value.length >= 2 && !roundtableCount.value) {
    return {
      tone: 'compare',
      title: t('workbench.nextAction.compareTitle'),
      description: t('workbench.nextAction.compareDescription'),
      cta: t('workbench.nextAction.compareCta'),
      path: `/compare/${props.projectId}`,
    }
  }

  return {
    tone: 'review',
    title: t('workbench.nextAction.roundtableTitle'),
    description: t('workbench.nextAction.roundtableDescription'),
    cta: t('workbench.nextAction.roundtableCta'),
    path: `/roundtable/${props.projectId}`,
  }
})

function goToNextAction() {
  if (nextAction.value?.path) router.push(nextAction.value.path)
}

const basicLine = computed(() => {
  const m = model.value
  if (!m) return ''
  const b = m.basic_info || {}
  return [b.age_range, b.location, b.industry, b.current_status]
    .filter(Boolean)
    .join(' · ')
})

// 画像目标与回避（步骤 01 展开体用）
const wants = computed(() =>
  (model.value?.aspirations || []).filter(a => a.polarity === 'want')
)
const avoids = computed(() =>
  (model.value?.aspirations || []).filter(a => a.polarity === 'want_to_avoid')
)

const lastStage = computed(() => {
  const h = activeSession.value?.stage_history || []
  return h.length ? h[h.length - 1] : null
})

// ---- Realism 摘要层：从最新 stage.realism 读数 ----
const lastStageRealism = computed(() => lastStage.value?.realism || null)

const healthPct = computed(() => {
  const v = Number(lastStageRealism.value?.health_score ?? 0)
  return Math.max(0, Math.min(100, v))
})
const healthText = computed(() => {
  const v = Math.round(healthPct.value)
  if (v >= 80) return `${v} · ${t('workbench.realism.healthGreat')}`
  if (v >= 60) return `${v} · ${t('workbench.realism.healthGood')}`
  if (v >= 30) return `${v} · ${t('workbench.realism.healthWeak')}`
  return `${v} · ${t('workbench.realism.healthBad')}`
})

const stressPct = computed(() => {
  const v = Number(lastStageRealism.value?.stress_carryover ?? 0)
  return Math.max(0, Math.min(100, v))
})
const stressText = computed(() => {
  const v = Math.round(stressPct.value)
  if (v <= 20) return `${v} · ${t('workbench.realism.stressLow')}`
  if (v <= 50) return `${v} · ${t('workbench.realism.stressMid')}`
  if (v <= 75) return `${v} · ${t('workbench.realism.stressHigh')}`
  return `${v} · ${t('workbench.realism.stressMax')}`
})

const cashMonths = computed(() =>
  Math.max(0, Math.round(Number(lastStageRealism.value?.finance?.cash_months ?? 0)))
)
const debtMonths = computed(() =>
  Math.max(0, Math.round(Number(lastStageRealism.value?.finance?.debt_months ?? 0)))
)
const incomeStability = computed(() =>
  Math.max(1, Math.min(5, Math.round(Number(lastStageRealism.value?.finance?.income_stability ?? 3))))
)

const relationships = computed(() => {
  const rels = lastStageRealism.value?.relationships || []
  return Array.isArray(rels) ? rels : []
})
function tensionClass(t) {
  const v = Number(t ?? 50)
  if (v >= 60) return 'tense'
  if (v <= 30) return 'calm'
  return 'mid'
}

const lifeEvent = computed(() => lastStageRealism.value?.life_event || null)

const causalWarnings = computed(() => {
  const v = lastStageRealism.value?.causal_violations_remaining
  return Array.isArray(v) && v.length ? v : null
})
const causalWarningsCount = computed(() => (causalWarnings.value || []).length)
const causalWarningsText = computed(() => (causalWarnings.value || []).join(' | '))

const activeFork = computed(() => {
  if (forkGate.value) return forkGate.value
  const s = activeSession.value
  if (!s) return null
  const next = (s.stage_history?.length || 0) + 1
  return (s.pending_forks || []).find(
    f => f.at_stage === next && !f.resolved
  ) || null
})

function archetypeLabel(key) {
  const i18nKey = `branch.archetype.${key}`
  return te(i18nKey) ? t(i18nKey) : (key || '')
}

function statusLabel(key) {
  const i18nKey = `evolution.status.${key}`
  return te(i18nKey) ? t(i18nKey) : (key || '')
}

async function loadWorkbench() {
  loading.value = true
  try {
    const [modelRes, sessionRes, projectsRes, branchRes, rtRes] = await Promise.all([
      getPersonalModel(props.projectId).catch(() => ({ data: null })),
      listEvolutionSessions(props.projectId).catch(() => ({ data: [] })),
      getProfileProjects().catch(() => ({ data: [] })),
      getBranches(props.projectId).catch(() => ({ data: {} })),
      listRoundtables(props.projectId).catch(() => ({ data: [] })),
    ])
    model.value = modelRes.data?.model || modelRes.data || null
    sessions.value = sessionRes.data || []
    branches.value = branchRes.data?.branches || []
    roundtables.value = rtRes.data || []
    const proj = (projectsRes.data || []).find(p => p.project_id === props.projectId)
    roundtableCount.value = roundtables.value.length || proj?.roundtable_count || 0
    // 智能默认展开最高进展步骤
    if (sessions.value.length) {
      expandedStep.value = 3
    } else if (branches.value.length) {
      expandedStep.value = 2
    } else if (model.value) {
      expandedStep.value = 1
    }
    // 默认选中最近活跃会话
    const preferred = sessions.value.find(s => s.status === 'active') || sessions.value[0]
    if (preferred) await selectSession(preferred)
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

async function selectSession(s) {
  if (activeSessionId.value === s.session_id) {
    activeSessionId.value = ''
    activeSession.value = null
    return
  }
  activeSessionId.value = s.session_id
  forkGate.value = null
  advanceError.value = ''
  try {
    const res = await getEvolutionSession(s.session_id)
    activeSession.value = res.data
  } catch (e) {
    advanceError.value = e?.message || String(e)
  }
}

async function advance() {
  if (advancing.value || !activeSessionId.value) return
  advancing.value = true
  advanceError.value = ''
  try {
    const res = await advanceEvolution(activeSessionId.value, {
      injected_event: eventInput.value.trim() || undefined
    })
    activeSession.value = res.data.session
    forkGate.value = res.data.fork_required ? res.data.fork : null
    eventInput.value = ''
    // 同步列表进度
    const item = sessions.value.find(s => s.session_id === activeSessionId.value)
    if (item) {
      item.stages_done = activeSession.value.stage_history?.length || item.stages_done
      item.status = activeSession.value.status
    }
  } catch (e) {
    advanceError.value = e?.message || String(e)
  } finally {
    advancing.value = false
  }
}

async function chooseFork(optionIndex) {
  if (!activeFork.value || !activeSessionId.value) return
  advancing.value = true
  advanceError.value = ''
  try {
    const res = await resolveEvolutionFork(activeSessionId.value, {
      fork_id: activeFork.value.fork_id,
      option_index: optionIndex
    })
    activeSession.value = res.data
    forkGate.value = null
    markGraphStale()  // 分叉裁决影响后续写入，标记待刷新
  } catch (e) {
    advanceError.value = e?.message || String(e)
  } finally {
    advancing.value = false
  }
}

// ---------- 图谱模式数据 ----------
const graphLoaded = ref(false)
const graphLoading = ref(false)
const graphError = ref('')
const graphId = ref('')
const graphData = ref(null)
const refreshKey = ref(0)

// 推演等数据变化后置位，切到图谱 tab 时刷新
const graphStale = ref(false)

function markGraphStale() {
  if (viewMode.value === 'graph') {
    loadGraph()
  } else {
    graphStale.value = true
  }
}

async function loadGraph(manual = false) {
  graphLoading.value = true
  graphError.value = ''
  try {
    if (!graphId.value) {
      const proj = await getProject(props.projectId)
      graphId.value = proj.data?.graph_id || ''
    }
    if (!graphId.value) {
      graphData.value = null
      return
    }
    const res = await getGraphData(graphId.value)
    graphData.value = res.data || null
    refreshKey.value++
  } catch (e) {
    if (manual) graphError.value = e?.message || String(e)
  } finally {
    graphLoading.value = false
    graphLoaded.value = true
  }
}

watch(viewMode, (mode) => {
  if (mode === 'graph' && (graphStale.value || !graphLoaded.value)) {
    graphStale.value = false
    loadGraph()
  }
})

watch(() => route.query.view, (val) => {
  const targetMode = val === 'graph' ? 'graph' : 'workbench'
  if (viewMode.value !== targetMode) {
    viewMode.value = targetMode
  }
})

onMounted(async () => {
  await loadWorkbench()
  if (viewMode.value === 'graph') {
    loadGraph()
  }
})
</script>

<style scoped>
.workbench-view {
  min-height: 100vh;
  background: var(--c-paper);
}

.navbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 32px;
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

/* 模式切换器 */
.view-switcher {
  display: flex;
  border: 1px solid var(--c-ink);
  border-radius: var(--r-sm);
  overflow: hidden;
}

.switch-btn {
  border: none;
  background: var(--c-paper);
  color: var(--c-ink-2);
  padding: 8px 20px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  font-family: inherit;
  transition: all var(--dur-fast);
  position: relative;
}

.switch-btn + .switch-btn {
  border-left: 1px solid var(--c-ink);
}

.switch-btn.active {
  background: var(--c-ink);
  color: var(--c-paper);
}

.switch-dot {
  position: absolute;
  top: 6px;
  right: 8px;
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--c-brand);
  animation: pulse 1.4s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.4; transform: scale(0.75); }
}

.nav-links {
  display: flex;
  align-items: center;
  gap: 16px;
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
  max-width: 1000px;
  margin: 0 auto;
  padding: 28px 24px 80px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  gap: 16px;
  flex-wrap: wrap;
  margin-bottom: 24px;
}

.page-title {
  font-size: 22px;
  font-weight: 700;
}

.page-meta {
  margin-top: 6px;
  color: var(--c-ink-4);
  font-size: 13px;
}

.next-action-panel {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: 16px;
  margin: 0 0 22px;
  padding: 16px 18px;
  border: 1px solid var(--c-ink);
  border-left: 6px solid var(--c-brand);
  background: var(--c-bg-softer);
  box-shadow: var(--shadow-pop-sm);
}

.next-action-panel.tone-compare {
  border-left-color: var(--a-balanced);
}

.next-action-panel.tone-review {
  border-left-color: var(--c-ink-3);
}

.next-action-mark {
  display: grid;
  place-items: center;
  width: 38px;
  height: 38px;
  border: 1px solid currentColor;
  color: var(--c-brand);
  font-size: 22px;
  font-weight: 700;
}

.next-action-copy {
  min-width: 0;
}

.next-action-label {
  color: var(--c-brand);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 1.5px;
  text-transform: uppercase;
}

.next-action-copy h2 {
  margin: 3px 0 4px;
  font-size: 17px;
  line-height: 1.3;
}

.next-action-copy p {
  margin: 0;
  color: var(--c-ink-3);
  font-size: 12px;
  line-height: 1.55;
}

.next-action-btn {
  white-space: nowrap;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.link-btn {
  border: 1px solid var(--c-line-strong);
  background: var(--c-paper);
  padding: 7px 16px;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  font-family: inherit;
  border-radius: var(--r-sm);
  color: var(--c-ink-2);
  transition: all var(--dur-fast);
}

.link-btn:hover:not(:disabled) {
  border-color: var(--c-ink);
  box-shadow: var(--shadow-pop-sm);
  transform: translate(-1px, -1px);
}

.link-btn.primary {
  background: var(--c-brand);
  border-color: var(--c-brand);
  color: var(--c-paper);
}

.state-box {
  text-align: center;
  padding: 60px 0;
  color: var(--c-ink-4);
}

/* 步骤区：4 步统一边框，展开的步骤获得强调 */
.step-section {
  border: 1px solid var(--c-line-strong);
  border-radius: var(--r-md);
  padding: 16px 20px;
  margin-bottom: 14px;
  transition: border-color var(--dur-fast), box-shadow var(--dur-fast);
}

.step-section.is-open {
  border: 2px solid var(--c-ink);
  box-shadow: var(--shadow-pop);
  padding: 15px 19px; /* 补偿 2px 边框多占的 1px，避免内容跳动 */
}

/* hover 与主页画像项目卡一致：墨线 + 硬阴影 */
.step-section:not(.is-open):hover {
  border-color: var(--c-ink);
  box-shadow: var(--shadow-pop);
}

.step-head {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  cursor: pointer;
  user-select: none;
}

.step-body-action {
  margin-top: 14px;
  padding-top: 12px;
  border-top: 1px dashed var(--c-line-soft);
  display: flex;
  justify-content: flex-end;
}

/* 流程连接箭头 */
.step-flow {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 24px;
  position: relative;
}

.step-flow::before {
  content: '';
  width: 1px;
  height: 100%;
  background: var(--c-line-strong);
}

.step-flow::after {
  content: '▼';
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  font-size: 9px;
  color: var(--c-ink-5);
  background: var(--c-paper);
  padding: 0 6px;
}

/* 展开折叠箭头 */
.step-chevron {
  margin-left: auto;
  font-size: 12px;
  color: var(--c-ink-4);
  transition: transform var(--dur-fast);
  transform: rotate(-90deg);
  flex-shrink: 0;
}

.step-chevron.open {
  transform: rotate(0deg);
}

.step-link {
  border: none;
  background: none;
  color: var(--c-brand);
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
  font-family: inherit;
  padding: 4px 0;
  white-space: nowrap;
}

.step-link:hover {
  text-decoration: underline;
}

.step-num {
  font-family: 'Space Grotesk', 'Inter', sans-serif;
  font-size: 18px;
  font-weight: 700;
  color: var(--c-brand);
}

.step-title {
  font-size: 14px;
  font-weight: 700;
}

/* 统一步骤状态徽标 */
.step-badge {
  font-size: 11px;
  padding: 2px 9px;
  border-radius: var(--r-sm);
  border: 1px solid var(--c-line);
  white-space: nowrap;
}

.step-badge.done {
  color: var(--a-balanced);
  border-color: var(--a-balanced);
}

.step-badge.active {
  color: var(--c-brand);
  border-color: var(--c-brand);
}

.step-badge.pending {
  color: var(--c-ink-4);
  border-color: var(--c-line);
}

/* 步骤 01 展开体：目标/回避 chips */
.goal-rows {
  margin-top: 10px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.goal-row {
  display: flex;
  align-items: baseline;
  gap: 8px;
  flex-wrap: wrap;
}

.goal-tag {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 1px;
  white-space: nowrap;
  flex-shrink: 0;
}

.goal-tag.want { color: var(--a-balanced); }
.goal-tag.avoid { color: var(--a-aggressive); }

.goal-chip {
  font-size: 12px;
  color: var(--c-ink-2);
  border: 1px solid var(--c-line-strong);
  border-radius: var(--r-sm);
  padding: 2px 9px;
  background: var(--c-paper);
}

.goal-chip.want { border-color: var(--a-balanced); }
.goal-chip.avoid { border-color: var(--a-aggressive); }

/* 步骤 02 展开体：分支行 */
.branch-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 10px;
  border: 1px solid var(--c-line-soft);
  border-radius: var(--r-sm);
  margin-bottom: 6px;
  cursor: pointer;
  transition: border-color var(--dur-fast);
}

.branch-row:hover {
  border-color: var(--c-ink);
}

.branch-positioning {
  flex: 1;
  font-size: 13px;
  color: var(--c-ink-2);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.branch-fit {
  font-size: 12px;
  font-weight: 700;
  color: var(--c-brand);
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}

/* 步骤 04 展开体：圆桌历史行 */
.rt-row {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 16px;
  padding: 8px 10px;
  border: 1px solid var(--c-line-soft);
  border-radius: var(--r-sm);
  margin-bottom: 6px;
  cursor: pointer;
  transition: border-color var(--dur-fast);
}

.rt-row:hover {
  border-color: var(--c-ink);
}

.rt-topic {
  font-size: 13px;
  font-weight: 600;
  color: var(--c-ink-2);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.rt-meta {
  font-size: 11px;
  color: var(--c-ink-4);
  white-space: nowrap;
}

.step-body {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px dashed var(--c-line-soft);
}

.profile-line .basic-line {
  font-size: 13px;
  font-weight: 600;
}

.profile-line .current-line {
  margin-top: 6px;
  font-size: 13px;
  color: var(--c-ink-3);
  line-height: 1.7;
}

/* 宇宙列表 */
.universe-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-top: 14px;
}

.universe-card {
  border: 1px solid var(--c-line);
  border-radius: var(--r-md);
  overflow: hidden;
}

.universe-card.active {
  border-color: var(--c-ink);
}

.uni-head {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  cursor: pointer;
  flex-wrap: wrap;
}

.uni-head:hover {
  background: var(--c-brand-tint);
}

.uni-positioning {
  flex: 1;
  font-size: 13px;
  font-weight: 600;
  min-width: 200px;
}

.uni-progress {
  font-size: 12px;
  color: var(--c-ink-4);
  font-variant-numeric: tabular-nums;
}

.uni-status {
  font-size: 11px;
  font-weight: 700;
}

.uni-status.completed { color: var(--a-balanced); }
.uni-status.active { color: var(--c-brand); }
.uni-status.aborted { color: var(--c-ink-4); }

.archetype-badge {
  font-size: 11px;
  font-weight: 700;
  padding: 3px 10px;
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

.uni-body {
  padding: 14px 16px;
  border-top: 1px dashed var(--c-line-soft);
}

.stage-track {
  display: flex;
  gap: 8px;
  margin-bottom: 14px;
}

.stage-dot {
  width: 26px;
  height: 26px;
  border: 1px solid var(--c-line-strong);
  border-radius: var(--r-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  color: var(--c-ink-4);
}

.stage-dot.done {
  background: var(--c-ink);
  border-color: var(--c-ink);
  color: var(--c-paper);
}

/* ============ Realism strip 真实性摘要 ============ */
.realism-strip {
  border: 1px solid var(--c-line-strong);
  border-radius: var(--r-sm);
  padding: 12px 14px;
  margin-bottom: 14px;
  background: var(--c-bg-soft);
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.realism-row {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.realism-row.top {
  gap: 16px;
}

/* meter 条：健康 / 压力 */
.meter-block {
  flex: 1 1 200px;
  min-width: 180px;
}

.meter-label {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 5px;
}

.lbl-name {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.5px;
  color: var(--c-ink-3);
}

.lbl-val {
  font-size: 11px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
  color: var(--c-ink-2);
}

.meter-track {
  height: 8px;
  background: var(--c-line-soft);
  border: 1px solid var(--c-line-strong);
  border-radius: var(--r-sm);
  overflow: hidden;
}

.meter-fill {
  height: 100%;
  transition: width 0.4s ease-out;
}

.meter-fill.health {
  background: var(--a-balanced);
}

.meter-fill.stress {
  background: var(--c-brand);
}

/* 财务胶囊 */
.finance-pills {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
}

.pill {
  display: inline-flex;
  align-items: center;
  font-size: 11px;
  font-weight: 700;
  padding: 4px 10px;
  border-radius: var(--r-sm);
  border: 1px solid var(--c-line-strong);
  background: var(--c-paper);
}

.pill.cash {
  color: var(--a-balanced);
  border-color: var(--a-balanced);
}

.pill.cash.warn {
  color: var(--c-brand);
  border-color: var(--c-brand);
  background: var(--c-brand-soft);
}

.pill.debt {
  color: var(--a-aggressive);
  border-color: var(--a-aggressive);
  background: #fff1f0;
}

.pill.stability {
  color: var(--c-ink-2);
  background: #eef1f4;
}

/* 关系张力 chips */
.chip-label {
  font-size: 11px;
  font-weight: 700;
  color: var(--c-ink-3);
  letter-spacing: 0.5px;
  white-space: nowrap;
}

.tension-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.tension-chip {
  font-size: 11px;
  font-weight: 600;
  padding: 3px 9px;
  border-radius: var(--r-sm);
  border: 1px solid var(--c-line-strong);
  background: var(--c-paper);
  cursor: default;
}

.tension-chip.calm {
  color: var(--a-balanced);
  border-color: var(--a-balanced);
}

.tension-chip.mid {
  color: var(--c-ink-2);
  border-color: var(--c-ink-3);
}

.tension-chip.tense {
  color: var(--a-aggressive);
  border-color: var(--a-aggressive);
  background: #fff1f0;
}

/* 意外事件 & 因果警告 */
.realism-row.bottom {
  gap: 8px;
}

.life-event {
  flex: 1 1 300px;
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 8px 12px;
  border-radius: var(--r-sm);
  border: 1px solid var(--c-ink);
  box-shadow: var(--shadow-pop-sm);
}

.life-event.good {
  background: #e8f7ec;
  border-color: var(--a-balanced);
}

.life-event.bad {
  background: #fff1f0;
  border-color: var(--a-aggressive);
}

.le-tag {
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 1px;
  padding: 2px 7px;
  border-radius: var(--r-sm);
  white-space: nowrap;
  flex-shrink: 0;
}

.life-event.good .le-tag {
  background: var(--a-balanced);
  color: var(--c-paper);
}

.life-event.bad .le-tag {
  background: var(--a-aggressive);
  color: var(--c-paper);
}

.le-template {
  font-size: 12px;
  line-height: 1.6;
  color: var(--c-ink-2);
}

.causal-warn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  font-weight: 700;
  color: #8a6900;
  padding: 5px 11px;
  border-radius: var(--r-sm);
  background: #fff8e1;
  border: 1px solid #e6c200;
  cursor: help;
}

.cw-tag {
  width: 16px;
  height: 16px;
  line-height: 14px;
  text-align: center;
  border-radius: 50%;
  background: #e6c200;
  color: var(--c-paper);
  font-weight: 900;
  font-size: 11px;
}

.last-stage .world-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 1px;
  background: var(--c-line);
  border: 1px solid var(--c-line);
  border-radius: var(--r-sm);
  overflow: hidden;
  margin-bottom: 10px;
}

.world-cell {
  background: var(--c-paper);
  padding: 8px 10px;
}

.world-dim {
  font-size: 10px;
  color: var(--c-ink-4);
  margin-bottom: 4px;
}

.world-val {
  font-size: 12px;
  line-height: 1.5;
}

.snapshot {
  font-size: 13px;
  color: var(--c-ink-3);
  line-height: 1.8;
}

/* 分叉裁决 */
.fork-panel {
  border: 1px solid var(--c-brand-line);
  background: var(--c-brand-soft);
  border-radius: var(--r-md);
  padding: 14px 16px;
  margin-top: 12px;
}

.fork-tag {
  display: inline-block;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 1px;
  color: var(--c-brand);
  border: 1px solid var(--c-brand-line);
  padding: 2px 8px;
  border-radius: var(--r-sm);
  margin-bottom: 10px;
}

.fork-q {
  font-size: 14px;
  font-weight: 700;
  margin-bottom: 12px;
  line-height: 1.6;
}

.fork-options {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}

.fork-opt {
  border: 1px solid var(--c-line-strong);
  background: var(--c-paper);
  border-radius: var(--r-sm);
  padding: 10px 14px;
  cursor: pointer;
  font-family: inherit;
  text-align: left;
  transition: all var(--dur-fast);
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.fork-opt b {
  font-size: 13px;
  color: var(--c-brand);
}

.opt-cond {
  font-size: 12px;
  color: var(--c-ink-3);
  line-height: 1.6;
}

.fork-opt:hover:not(:disabled) {
  border-color: var(--c-brand);
  box-shadow: var(--shadow-pop-sm);
  transform: translate(-1px, -1px);
}

.fork-opt:disabled {
  opacity: 0.5;
  cursor: wait;
}

/* 推进行 */
.advance-row {
  display: flex;
  gap: 10px;
  margin-top: 12px;
  flex-wrap: wrap;
}

.event-input {
  flex: 1;
  min-width: 220px;
  border: 1px solid var(--c-line-strong);
  border-radius: var(--r-sm);
  padding: 9px 12px;
  font-size: 13px;
  font-family: inherit;
  outline: none;
}

.event-input:focus {
  border-color: var(--c-brand);
}

.advance-btn {
  background: var(--c-brand);
  color: var(--c-paper);
  border: 1px solid var(--c-brand);
  border-radius: var(--r-sm);
  padding: 9px 22px;
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
  font-family: inherit;
  transition: all var(--dur-fast);
}

.advance-btn:hover:not(:disabled) {
  box-shadow: var(--shadow-pop-sm);
  transform: translate(-1px, -1px);
}

.advance-btn:disabled {
  opacity: 0.5;
  cursor: wait;
}

.error-line {
  margin-top: 10px;
  font-size: 12px;
  color: var(--a-aggressive);
}

.uni-links {
  margin-top: 12px;
  display: flex;
  gap: 12px;
}

.mini-link {
  border: none;
  background: none;
  color: var(--c-brand);
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  font-family: inherit;
  padding: 0;
}

.mini-link:hover {
  text-decoration: underline;
}

/* 图谱模式 */
.graph-shell {
  height: calc(100vh - 150px);
  min-height: 480px;
  border: 1px solid var(--c-line);
  border-radius: var(--r-md);
  overflow: hidden;
  position: relative;
}

.graph-state {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: var(--c-ink-4);
  font-size: 14px;
}

.graph-state.error {
  color: var(--c-brand);
}

@media (max-width: 860px) {
  .navbar {
    flex-wrap: wrap;
    gap: 10px;
    padding: 12px 16px;
  }
  .next-action-panel {
    grid-template-columns: auto minmax(0, 1fr);
    align-items: start;
  }
  .next-action-btn {
    grid-column: 2;
    justify-self: start;
  }
  /* 极窄时换行，switcher 内容宽度不再全宽拉伸（避免与语言下拉重叠） */
  .fork-options {
    grid-template-columns: 1fr;
  }
  .last-stage .world-grid {
    grid-template-columns: 1fr 1fr;
  }
}
</style>
