<template>
  <div class="evolution-view">
    <!-- 顶部统一导航 -->
    <AppHeader
      :project-id="session?.project_id || ''"
      current-step="evolution"
      :session-id="sessionId"
    >
      <template #extra>
        <button v-if="session?.status === 'active'" class="abort-btn" type="button" @click="abortSession">
          {{ t('evolution.view.abort') }}
        </button>
      </template>
    </AppHeader>

    <div class="main-content">
      <!-- 加载/异常态 -->
      <div v-if="loading" class="state-box">
        <p>{{ t('common.loading') }}</p>
      </div>

      <div v-else-if="!session" class="state-box error">
        <p>{{ loadError || t('evolution.view.notFound') }}</p>
      </div>

      <template v-else>
        <!-- 平行宇宙多分支切换栏 -->
        <div v-if="universeTabs.length > 1" class="universe-switch-bar">
          <div class="universe-tabs">
            <button
              v-for="u in universeTabs"
              :key="u.id"
              class="universe-tab"
              :class="{
                active: u.isSession && u.sessionId === sessionId,
                pending: !u.isSession,
                [u.archetype]: true
              }"
              type="button"
              @click="handleTabClick(u)"
            >
              <span class="tab-archetype-tag" :class="u.archetype">
                {{ archetypeLabel(u.archetype) }}
              </span>
              <span class="tab-pos">{{ u.positioning }}</span>
              <span v-if="u.isSession" class="tab-stat">
                {{ u.stagesDone }}/{{ u.stageCount }}
                <span v-if="u.status === 'completed'" class="tab-done">✓</span>
              </span>
              <span v-else class="tab-stat pending-tag">
                + 待推演
              </span>
            </button>
          </div>
          <button
            class="more-branches-btn"
            type="button"
            @click="router.push(`/branches/${session.project_id}`)"
          >
            + {{ t('workbench.stepBranches') }}
          </button>
        </div>

        <!-- 头部 -->
        <header class="page-header">
          <h1 class="page-title">
            <span class="archetype-badge" :class="session.source_branch_archetype">
              {{ archetypeLabel(session.source_branch_archetype) }}
            </span>
            {{ t('evolution.view.title') }}
          </h1>
          <p class="page-meta">
            {{ session.source_branch_positioning }} ·
            {{ t('evolution.view.basedOn') }} v{{ session.source_model_version }} ·
            {{ t('evolution.view.stageProgress', { done: stagesDone, total: stageTotal }) }}
            <span v-if="session.status === 'completed'" class="status-badge done">{{ t('evolution.view.completed') }}</span>
            <span v-else-if="session.status === 'aborted'" class="status-badge aborted">{{ t('evolution.view.aborted') }}</span>
          </p>
        </header>

        <!-- 宇宙终局总结（完成态出口） -->
        <div v-if="session.status === 'completed'" class="ending-panel">
          <div class="ending-title">✦ {{ t('evolution.view.endingTitle') }}</div>
          <p v-if="finalStage" class="ending-snapshot">{{ finalStage.state_snapshot }}</p>
          <div v-if="finalStage?.world_state" class="world-grid ending-world">
            <div v-for="dim in dims" :key="dim.key" class="world-cell">
              <div class="world-dim">{{ t(`evolution.dim.${dim.key}`) }}</div>
              <div class="world-val">{{ finalStage.world_state[dim.key] || '—' }}</div>
            </div>
          </div>
          <div class="ending-actions">
            <button class="ending-btn primary" type="button" @click="router.push(`/roundtable/${session.project_id}`)">
              {{ t('evolution.view.goRoundtable') }}
            </button>
            <button class="ending-btn" type="button" @click="router.push(`/compare/${session.project_id}`)">
              ⇄ {{ t('evolution.view.goCompare') }}
            </button>
          </div>
        </div>

        <!-- 阶段轴 -->
        <div class="stage-axis">
          <div
            v-for="(stage, i) in session.stage_plan"
            :key="i"
            class="stage-dot"
            :class="{ done: i < stagesDone, current: i === stagesDone }"
          >
            <div class="dot"></div>
            <div class="stage-label">{{ stage.stage_label }}</div>
          </div>
        </div>

        <!-- 分叉挡板 -->
        <div v-if="activeFork" class="fork-panel" :class="{ 'is-emergency': activeFork.is_emergency }">
          <div class="fork-title" :class="{ 'is-emergency': activeFork.is_emergency }">
            <span v-if="activeFork.is_emergency" class="emergency-tag">■ 真实感硬性断路器拦截 · 0 TOKEN</span>
            <span v-else>{{ t('evolution.view.forkTitle') }}</span>
          </div>
          <p class="fork-question">{{ activeFork.question }}</p>
          <div class="fork-options">
            <button
              v-for="(opt, i) in activeFork.options"
              :key="i"
              class="fork-option"
              :class="{ 'is-emergency': activeFork.is_emergency }"
              type="button"
              :disabled="advancing"
              @click="chooseFork(i)"
            >
              <span class="option-label">{{ opt.label }}</span>
              <span class="option-condition">{{ opt.condition }}</span>
            </button>
          </div>
        </div>

        <!-- 阶段历史（倒序展示，最新在上） -->
        <div class="stage-list">
          <section
            v-for="entry in [...session.stage_history].reverse()"
            :key="entry.stage_index"
            class="stage-card"
          >
            <div class="stage-card-head">
              <span class="stage-no">{{ t('evolution.view.stageNo', { n: entry.stage_index }) }}</span>
              <span class="stage-card-label">{{ entry.stage_label }}</span>
              <span v-if="entry.divergence_note" class="divergence-badge"
                    :title="entry.divergence_note">⤴ {{ t('evolution.view.diverged') }}</span>
            </div>

            <!-- 4 维世界状态 -->
            <div class="world-grid">
              <div v-for="dim in dims" :key="dim.key" class="world-cell">
                <div class="world-dim">
                  <span>{{ t(`evolution.dim.${dim.key}`) }}</span>
                  <span
                    v-if="getStageDelta(entry, dim.key)"
                    class="delta-tag"
                    :class="getStageDelta(entry, dim.key).trend"
                  >
                    {{ getStageDelta(entry, dim.key).label }}
                  </span>
                </div>
                <div class="world-val">{{ entry.world_state?.[dim.key] || '—' }}</div>
              </div>
            </div>

            <!-- 叙事 -->
            <p class="stage-snapshot">{{ entry.state_snapshot }}</p>

            <!-- 发生的事件 -->
            <div v-if="entry.occurred_events?.length" class="occurred-events">
              <div class="events-title">{{ t('evolution.view.events') }}</div>
              <ul>
                <li v-for="(e, i) in entry.occurred_events" :key="i">{{ e }}</li>
              </ul>
            </div>

            <!-- 心智反思与认知转变 -->
            <div v-if="entry.reflections?.length" class="reflections-block">
              <div class="reflections-title">■ {{ t('evolution.view.reflections') }}</div>
              <div class="reflection-list">
                <div v-for="(r, idx) in entry.reflections" :key="idx" class="reflection-card">
                  <div class="reflection-meta">
                    <span class="reflection-badge" :class="r.type">
                      {{ t(`evolution.view.reflectionType.${r.type}`) || '认知转变' }}
                    </span>
                  </div>
                  <p class="reflection-insight">“{{ r.insight }}”</p>
                  <div v-if="r.grounded_events?.length" class="reflection-grounded">
                    <span class="grounded-label">{{ t('evolution.view.reflectionsGrounded') }}</span>
                    <span class="grounded-text">{{ r.grounded_events.join('；') }}</span>
                  </div>
                </div>
              </div>
            </div>

            <!-- 关系人主动博弈与施压 (Stakeholder Agency) -->
            <div v-if="entry.stakeholder_moves?.length" class="stakeholders-block">
              <div class="stakeholders-title">▲ {{ t('evolution.view.stakeholderMoves') }}</div>
              <div class="stakeholder-list">
                <div v-for="(m, idx) in entry.stakeholder_moves" :key="idx" class="stakeholder-move-card">
                  <div class="stakeholder-move-head">
                    <span class="stakeholder-name">{{ m.person }}</span>
                    <span v-if="m.role" class="stakeholder-role">{{ m.role }}</span>
                    <span class="stakeholder-stance-badge" :class="m.stance">
                      {{ t(`evolution.view.stakeholderStance.${m.stance}`) || m.stance }}
                    </span>
                  </div>
                  <div class="stakeholder-detail-row" v-if="m.motive">
                    <span class="detail-label">{{ t('evolution.view.stakeholderMotive') }}</span>
                    <span class="detail-val">{{ m.motive }}</span>
                  </div>
                  <div class="stakeholder-detail-row" v-if="m.action">
                    <span class="detail-label">{{ t('evolution.view.stakeholderAction') }}</span>
                    <span class="detail-val">{{ m.action }}</span>
                  </div>
                  <div class="stakeholder-demand-row" v-if="m.demand">
                    <span class="demand-label">{{ t('evolution.view.stakeholderDemand') }}</span>
                    <span class="demand-val">“{{ m.demand }}”</span>
                  </div>
                </div>
              </div>
            </div>

            <!-- 原子记忆变更流 (Mem0 架构) -->
            <div v-if="entry.memory_mutations?.length" class="mutations-block">
              <div class="mutations-title">
                <span>◆ {{ t('evolution.view.memoryMutations') }}</span>
                <span v-if="entry.active_memories_count" class="active-count-tag">
                  {{ t('evolution.view.activeMemories') }}: {{ entry.active_memories_count }}
                </span>
              </div>
              <div class="mutation-list">
                <div v-for="(mut, idx) in entry.memory_mutations" :key="idx" class="mutation-card" :class="mut.action.toLowerCase()">
                  <div class="mutation-header">
                    <span class="action-tag" :class="mut.action.toLowerCase()">
                      {{ t(`evolution.view.memoryAction.${mut.action}`) || mut.action }}
                    </span>
                    <span class="category-tag">{{ t(`evolution.view.memoryCategory.${mut.category}`) || mut.category }}</span>
                    <span v-if="mut.subject" class="subject-tag">{{ mut.subject }}</span>
                  </div>
                  <div class="mutation-fact">
                    <span v-if="mut.previous_fact" class="prev-fact">{{ t('evolution.view.memoryPrevious') }}{{ mut.previous_fact }} → </span>
                    <span class="current-fact">{{ mut.fact }}</span>
                  </div>
                  <div v-if="mut.reason" class="mutation-reason">
                    <span class="reason-label">{{ t('evolution.view.memoryReason') }}</span>
                    <span class="reason-val">{{ mut.reason }}</span>
                  </div>
                </div>
              </div>
            </div>

            <!-- 人格防漂移保真度审计 (Anti-Drift Guard) -->
            <div v-if="entry.anti_drift" class="anti-drift-block">
              <div class="anti-drift-head">
                <div class="anti-drift-title">
                  <span class="drift-bullet">■</span>
                  <span>{{ t('evolution.view.antiDriftTitle') }}</span>
                </div>
                <div class="anti-drift-badge" :class="entry.anti_drift.drift_status">
                  <span class="drift-score">{{ entry.anti_drift.fidelity_score }}%</span>
                  <span class="drift-status-label">{{ t(`evolution.view.driftStatus.${entry.anti_drift.drift_status}`) }}</span>
                </div>
              </div>
              <p class="anti-drift-diagnostics">{{ entry.anti_drift.diagnostics }}</p>
              <div v-if="entry.anti_drift.anchor_citations?.length" class="anti-drift-anchors">
                <span v-for="(anc, aIdx) in entry.anti_drift.anchor_citations" :key="aIdx" class="anchor-tag">
                  {{ anc }}
                </span>
              </div>
            </div>

            <!-- 偏离说明 -->
            <p v-if="entry.divergence_note" class="divergence-note">
              {{ t('evolution.view.divergenceNote') }}{{ entry.divergence_note }}
            </p>
          </section>
        </div>

        <!-- 推进控制 -->
        <div v-if="session.status === 'active'" class="advance-bar-wrapper">
          <div v-if="activeFork" class="fork-pending-banner">
            <span class="banner-symbol">■</span>
            <span>{{ t('evolution.view.forkPendingHint') }}</span>
          </div>
          <div class="advance-bar">
            <input
              v-model="eventInput"
              class="event-input"
              type="text"
              :placeholder="activeFork ? t('evolution.view.forkPendingHint') : t('evolution.view.eventPlaceholder')"
              :disabled="advancing || !!activeFork"
              @keyup.enter="advance('')"
            >
            <button class="advance-btn" type="button" :disabled="advancing || !!activeFork" @click="advance()">
              {{ advancing ? t('evolution.view.advancing') : (activeFork ? t('evolution.view.forkPendingHint') : t('evolution.view.advance')) }} →
            </button>
          </div>
        </div>
        <p v-if="advanceError" class="advance-error">{{ advanceError }}</p>

        <!-- 已裁决分叉记录 -->
        <div v-if="resolvedForks.length" class="resolved-forks">
          <div class="events-title">{{ t('evolution.view.resolvedForks') }}</div>
          <div v-for="f in resolvedForks" :key="f.fork_id" class="resolved-fork-row">
            <span class="fork-q">{{ f.question }}</span>
            <span class="fork-choice">→ {{ f.resolved?.label }}</span>
          </div>
        </div>

        <!-- 下一步行动引导卡片（终局承接） -->
        <section v-if="session.status === 'completed' || session.status === 'aborted'" class="next-action-card">
          <div class="next-card-head">
            <span class="next-symbol">■</span>
            <span class="next-title">{{ t('evolution.view.nextActionTitle') }}</span>
          </div>
          <p class="next-card-desc">{{ t('evolution.view.nextActionDesc') }}</p>
          <div class="next-card-actions">
            <button class="next-btn primary" type="button" @click="router.push(`/compare/${session.project_id}`)">
              ⇄ {{ t('evolution.view.goCompare') }} →
            </button>
            <button class="next-btn" type="button" @click="router.push(`/roundtable/${session.project_id}`)">
              {{ t('evolution.view.goRoundtable') }} →
            </button>
            <button class="next-btn ghost" type="button" @click="router.push(`/branches/${session.project_id}`)">
              ← {{ t('evolution.view.exploreOtherBranches') }}
            </button>
          </div>
        </section>
      </template>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import AppHeader from '../components/AppHeader.vue'
import {
  getEvolutionSession,
  advanceEvolution,
  resolveEvolutionFork,
  abortEvolutionSession,
  listEvolutionSessions
} from '../api/evolution'
import { getBranches } from '../api/branch'

const props = defineProps({
  sessionId: { type: String, required: true }
})

const router = useRouter()
const { t, te } = useI18n()

const loading = ref(true)
const loadError = ref('')
const session = ref(null)
const projectSessions = ref([])
const projectBranches = ref([])
const advancing = ref(false)
const advanceError = ref('')
const eventInput = ref('')
const forkGate = ref(null) // advance 返回的待裁决分叉

const dims = [
  { key: 'career' }, { key: 'family' },
  { key: 'resources' }, { key: 'psyche' },
]

const stageTotal = computed(() => session.value?.stage_plan?.length || 0)
const stagesDone = computed(() => session.value?.stage_history?.length || 0)

const universeTabs = computed(() => {
  const tabs = []
  
  // 1. 已开启的推演会话
  for (const s of projectSessions.value) {
    tabs.push({
      id: s.session_id,
      sessionId: s.session_id,
      archetype: s.source_branch_archetype,
      positioning: s.source_branch_positioning,
      stagesDone: s.stages_done,
      stageCount: s.stage_count,
      status: s.status,
      isSession: true
    })
  }

  // 2. 尚未开启推演的分支
  for (const [idx, b] of projectBranches.value.entries()) {
    const hasSession = projectSessions.value.some(s => s.source_branch_archetype === b.archetype)
    if (!hasSession) {
      tabs.push({
        id: 'branch_' + (b.branch_id || idx),
        branchIndex: idx,
        archetype: b.archetype,
        positioning: b.positioning,
        stagesDone: 0,
        stageCount: 0,
        status: 'pending',
        isSession: false
      })
    }
  }
  return tabs
})

// 当前挡路的分叉：advance 返回的 fork_gate 优先，其次检查未决且已到时机的分叉
const activeFork = computed(() => {
  if (forkGate.value) return forkGate.value
  const nextStage = stagesDone.value + 1
  return (session.value?.pending_forks || []).find(
    f => f.at_stage === nextStage && !f.resolved
  ) || null
})

const resolvedForks = computed(() =>
  (session.value?.pending_forks || []).filter(f => f.resolved)
)

const finalStage = computed(() => {
  const history = session.value?.stage_history || []
  return history.length ? history[history.length - 1] : null
})

function archetypeLabel(key) {
  const i18nKey = `branch.archetype.${key}`
  return te(i18nKey) ? t(i18nKey) : (key || '')
}

function getStageDelta(entry, dimKey) {
  if (!session.value?.stage_history || entry.stage_index <= 1) return null
  const prev = session.value.stage_history.find(s => s.stage_index === entry.stage_index - 1)
  if (!prev?.world_state) return null

  const currentVal = String(entry.world_state?.[dimKey] || '')
  const prevVal = String(prev.world_state?.[dimKey] || '')
  if (!currentVal || !prevVal || currentVal === prevVal) return null

  // 1. 资源/财务变动模式
  if (dimKey === 'resources') {
    if (/增加|增长|提升|多出|缓冲.*(?:多|增|4|5|6)|归零|清零|还清/.test(currentVal) && !/借款|高筑|欠账/.test(currentVal)) {
      return { trend: 'improved', label: '+ 缓冲增强' }
    }
    if (/债务|借款|高筑|借了|手头空空|手头拮据|月数当量-/.test(currentVal)) {
      return { trend: 'depleted', label: '- 债务承压' }
    }
  }

  // 2. 心理变动模式
  if (dimKey === 'psyche') {
    if (/减轻|好转|积极|踏实|实在感|适应/.test(currentVal)) {
      return { trend: 'improved', label: '+ 心态转好' }
    }
    if (/内耗|加剧|压力增大|羞耻|崩溃|焦虑|内疚/.test(currentVal)) {
      return { trend: 'depleted', label: '- 心理承压' }
    }
  }

  // 3. 事业变动模式
  if (dimKey === 'career') {
    if (/扩展|增多|口碑|固定客户|稳定|晋升|单子/.test(currentVal) && !/停|受限/.test(currentVal)) {
      return { trend: 'improved', label: '+ 业务拓展' }
    }
    if (/受限|缓慢|停了|无法|辞退|打折/.test(currentVal)) {
      return { trend: 'depleted', label: '- 发展受限' }
    }
  }

  // 4. 关系变动模式
  if (dimKey === 'family') {
    if (/改善|缓和|支持|接济|认可/.test(currentVal)) {
      return { trend: 'improved', label: '+ 关系缓和' }
    }
    if (/恶化|疏远|嘲笑|冲突|追债|断绝/.test(currentVal)) {
      return { trend: 'depleted', label: '- 关系紧张' }
    }
  }

  return { trend: 'shifted', label: '• 状态演进' }
}

async function loadSiblingSessions() {
  if (!session.value?.project_id) return
  try {
    const [sessRes, branchRes] = await Promise.allSettled([
      listEvolutionSessions(session.value.project_id),
      getBranches(session.value.project_id)
    ])
    if (sessRes.status === 'fulfilled') {
      projectSessions.value = Array.isArray(sessRes.value?.data) ? sessRes.value.data : (sessRes.value?.sessions || [])
    }
    if (branchRes.status === 'fulfilled') {
      projectBranches.value = Array.isArray(branchRes.value?.data?.branches) ? branchRes.value.data.branches : (branchRes.value?.branches || [])
    }
  } catch {
    // ignore
  }
}

async function handleTabClick(tab) {
  if (tab.isSession) {
    if (tab.sessionId !== props.sessionId) {
      router.push(`/evolution/${tab.sessionId}`)
    }
  } else {
    router.push(`/branches/${session.value.project_id}`)
  }
}

async function load() {
  loading.value = true
  loadError.value = ''
  try {
    const rawId = props.sessionId
    if (!rawId) {
      loadError.value = t('evolution.view.notFound')
      return
    }

    // 若传入的是 projectId (以 proj_ 开头)，自动重定向到该项目最近推进的会话
    if (rawId.startsWith('proj_')) {
      const listRes = await listEvolutionSessions(rawId)
      const sessions = Array.isArray(listRes?.data) ? listRes.data : (listRes?.sessions || [])
      if (sessions.length > 0) {
        const latest = sessions[0]
        router.replace(`/evolution/${latest.session_id}`)
        return
      } else {
        // 尚未开始推演，自动引导至分支规划页
        router.replace(`/branches/${rawId}`)
        return
      }
    }

    const res = await getEvolutionSession(rawId)
    session.value = res.data
    await loadSiblingSessions()
  } catch (e) {
    loadError.value = e?.message || String(e)
  } finally {
    loading.value = false
  }
}

watch(() => props.sessionId, () => {
  load()
})

async function advance() {
  if (advancing.value) return
  advancing.value = true
  advanceError.value = ''
  try {
    const res = await advanceEvolution(props.sessionId, {
      injected_event: eventInput.value.trim() || undefined
    })
    session.value = res.data.session
    forkGate.value = res.data.fork_required ? res.data.fork : null
    eventInput.value = ''
  } catch (e) {
    advanceError.value = e?.message || String(e)
  } finally {
    advancing.value = false
  }
}

async function chooseFork(optionIndex) {
  if (!activeFork.value) return
  advancing.value = true
  advanceError.value = ''
  try {
    const res = await resolveEvolutionFork(props.sessionId, {
      fork_id: activeFork.value.fork_id,
      option_index: optionIndex
    })
    session.value = res.data
    forkGate.value = null
  } catch (e) {
    advanceError.value = e?.message || String(e)
  } finally {
    advancing.value = false
  }
}

async function abortSession() {
  try {
    await abortEvolutionSession(props.sessionId)
    await load()
  } catch (e) {
    advanceError.value = e?.message || String(e)
  }
}

onMounted(load)
</script>

<style scoped>
.evolution-view {
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

.back-branches {
  border: 1px solid var(--c-line-strong);
  background: var(--c-paper);
  padding: 6px 14px;
  font-size: 13px;
  cursor: pointer;
  font-family: inherit;
  border-radius: var(--r-sm);
  color: var(--c-ink-2);
}

.back-branches:hover {
  border-color: var(--c-ink);
}

.abort-btn {
  border: 1px solid var(--c-brand);
  background: var(--c-paper);
  color: var(--c-brand);
  padding: 6px 14px;
  font-size: 13px;
  cursor: pointer;
  font-family: inherit;
  border-radius: var(--r-sm);
}

.abort-btn:hover {
  background: var(--c-brand-soft);
}

.main-content {
  max-width: 860px;
  margin: 0 auto;
  padding: 32px 24px 96px;
}

/* 平行宇宙多分支切换栏 */
.universe-switch-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 24px;
  padding-bottom: 16px;
  border-bottom: 1px dashed var(--c-line-strong);
}

.universe-tabs {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  flex: 1;
}

.universe-tab {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 6px 14px;
  background: var(--c-bg-softer);
  border: 1px solid var(--c-line-strong);
  border-radius: var(--r-sm);
  font-family: inherit;
  font-size: 13px;
  color: var(--c-ink-2);
  cursor: pointer;
  transition: all 0.15s;
  user-select: none;
}

.universe-tab:hover {
  border-color: var(--c-ink);
  background: var(--c-paper);
}

.universe-tab.active {
  background: var(--c-paper);
  border: 2px solid var(--c-ink);
  box-shadow: var(--shadow-pop-sm);
  font-weight: 700;
  color: var(--c-ink);
  padding: 5px 13px;
}

.tab-archetype-tag {
  font-size: 11px;
  font-weight: 700;
  padding: 1px 6px;
  border-radius: var(--r-sm);
  background: var(--c-bg-soft);
}

.tab-archetype-tag.aggressive { background: #ffebee; color: var(--a-aggressive); }
.tab-archetype-tag.conservative { background: #e8f4fd; color: var(--a-conservative); }
.tab-archetype-tag.balanced { background: #e8f8f0; color: var(--a-balanced); }
.tab-archetype-tag.detour { background: #fef7e6; color: var(--a-detour); }
.tab-archetype-tag.exit { background: #f3eafd; color: var(--a-exit); }

.tab-pos {
  max-width: 140px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 12px;
  color: var(--c-ink-3);
}

.universe-tab.active .tab-pos {
  color: var(--c-ink);
}

.tab-stat {
  font-size: 11px;
  color: var(--c-ink-4);
  display: inline-flex;
  align-items: center;
  gap: 3px;
}

.universe-tab.pending {
  border-style: dashed;
  opacity: 0.85;
}

.universe-tab.pending:hover {
  opacity: 1;
  border-color: var(--c-brand);
}

.pending-tag {
  color: var(--c-brand);
  font-weight: 600;
}

.tab-done {
  color: var(--c-brand);
  font-weight: 700;
}

.more-branches-btn {
  background: transparent;
  border: 1px dashed var(--c-line-strong);
  color: var(--c-ink-3);
  font-size: 12px;
  font-family: inherit;
  padding: 6px 12px;
  border-radius: var(--r-sm);
  cursor: pointer;
  white-space: nowrap;
  transition: all 0.15s;
}

.more-branches-btn:hover {
  border-color: var(--c-brand);
  color: var(--c-brand);
  background: var(--c-brand-soft);
}

.state-box {
  text-align: center;
  padding: 80px 0;
  color: var(--c-ink-3);
}

.state-box.error p {
  color: var(--c-brand);
}

/* 头部 */
.page-header {
  margin-bottom: 24px;
}

.page-title {
  font-size: 24px;
  font-weight: 700;
  display: flex;
  align-items: center;
  gap: 12px;
}

.archetype-badge {
  font-size: 12px;
  font-weight: 700;
  padding: 5px 12px;
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

.page-meta {
  margin-top: 8px;
  color: var(--c-ink-4);
  font-size: 13px;
}

.status-badge {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: var(--r-sm);
  margin-left: 8px;
  color: var(--c-paper);
}

.status-badge.done { background: var(--a-balanced); }
.status-badge.aborted { background: var(--c-ink-4); }

/* 宇宙终局总结 */
.ending-panel {
  border: 2px solid var(--c-ink);
  border-radius: var(--r-md);
  padding: 22px 26px;
  margin-bottom: 28px;
  background: var(--c-paper);
  box-shadow: var(--shadow-pop);
}

.ending-title {
  font-size: 15px;
  font-weight: 700;
  margin-bottom: 12px;
}

.ending-snapshot {
  font-size: 14px;
  line-height: 1.9;
  color: var(--c-ink-2);
  margin-bottom: 14px;
}

.ending-world {
  margin-bottom: 18px;
}

.ending-actions {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.ending-btn {
  border: 1px solid var(--c-ink);
  background: var(--c-paper);
  color: var(--c-ink);
  padding: 10px 22px;
  font-size: 14px;
  font-weight: 700;
  cursor: pointer;
  border-radius: var(--r-sm);
  font-family: inherit;
  transition: all 0.15s;
}

.ending-btn.primary {
  background: var(--c-brand);
  border-color: var(--c-brand);
  color: var(--c-paper);
}

.ending-btn:hover {
  box-shadow: var(--shadow-pop-sm);
  transform: translate(-1px, -1px);
}

/* 阶段轴 */
.stage-axis {
  display: flex;
  justify-content: space-between;
  margin-bottom: 28px;
  position: relative;
}

.stage-axis::before {
  content: '';
  position: absolute;
  top: 6px;
  left: 12px;
  right: 12px;
  height: 1px;
  background: var(--c-line-strong);
}

.stage-dot {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  position: relative;
  z-index: 1;
  flex: 1;
}

.stage-dot .dot {
  width: 13px;
  height: 13px;
  border-radius: 50%;
  background: var(--c-paper);
  border: 2px solid var(--c-line-strong);
}

.stage-dot.done .dot {
  background: var(--c-brand);
  border-color: var(--c-brand);
}

.stage-dot.current .dot {
  border-color: var(--c-brand);
  box-shadow: 0 0 0 3px var(--c-brand-line);
}

.stage-label {
  font-size: 12px;
  color: var(--c-ink-3);
  text-align: center;
}

.stage-dot.done .stage-label {
  color: var(--c-ink-2);
  font-weight: 600;
}

.stage-dot.current .stage-label {
  color: var(--c-brand);
  font-weight: 700;
}

/* 分叉挡板 */
.fork-panel {
  border: 2px solid var(--a-detour);
  background: #FFFCF2;
  border-radius: var(--r-md);
  padding: 20px 24px;
  margin-bottom: 24px;
}

.fork-title {
  font-size: 13px;
  font-weight: 700;
  color: var(--a-detour);
  margin-bottom: 10px;
}

.fork-question {
  font-size: 16px;
  font-weight: 700;
  margin-bottom: 16px;
  line-height: 1.6;
}

.fork-options {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.fork-option {
  border: 1px solid #E5D9A8;
  background: var(--c-paper);
  padding: 14px 16px;
  cursor: pointer;
  font-family: inherit;
  border-radius: var(--r-sm);
  text-align: left;
  display: flex;
  flex-direction: column;
  gap: 6px;
  transition: all var(--dur-fast);
}

.fork-option:hover:not(:disabled) {
  border-color: var(--c-ink);
  box-shadow: var(--shadow-pop-sm);
  transform: translate(-1px, -1px);
}

.fork-option:active:not(:disabled) {
  background: var(--c-bg-soft);
  transform: translate(1px, 1px);
  box-shadow: 1px 1px 0 var(--c-ink);
}

.fork-option:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.option-label {
  font-size: 14px;
  font-weight: 700;
}

.option-condition {
  font-size: 12px;
  color: var(--c-ink-3);
  line-height: 1.5;
}

/* 真实感硬性断路器拦截样式 */
.fork-panel.is-emergency {
  border: 2px solid #DC2626;
  background: #FFFBFB;
  box-shadow: 4px 4px 0 #DC2626;
}

.fork-title.is-emergency {
  color: #DC2626;
}

.emergency-tag {
  display: inline-block;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.5px;
  background: #FEF2F2;
  color: #DC2626;
  border: 1px solid #FECACA;
  padding: 2px 8px;
  border-radius: var(--r-sm);
}

.fork-option.is-emergency {
  border-color: #FECACA;
  background: #FFFFFF;
}

.fork-option.is-emergency:hover:not(:disabled) {
  border-color: #DC2626;
  box-shadow: 3px 3px 0 #DC2626;
}

/* 阶段卡片 */
.stage-list {
  display: flex;
  flex-direction: column;
  gap: 20px;
  margin-bottom: 28px;
}

.stage-card {
  border: 1px solid var(--c-line);
  border-radius: var(--r-md);
  padding: 20px 24px;
}

.stage-card-head {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}

.stage-no {
  font-size: 11px;
  font-weight: 700;
  color: var(--c-paper);
  background: var(--c-ink);
  padding: 3px 9px;
  border-radius: var(--r-sm);
}

.stage-card-label {
  font-size: 15px;
  font-weight: 700;
}

.divergence-badge {
  font-size: 11px;
  color: var(--a-detour);
  border: 1px solid #E5D9A8;
  padding: 2px 8px;
  border-radius: var(--r-lg);
}

/* 4 维世界状态 */
.world-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  margin-bottom: 16px;
}

.world-cell {
  background: var(--c-bg-softer);
  border-left: 3px solid var(--c-ink-4);
  padding: 10px 14px;
}

.world-cell:nth-child(1) { border-left-color: var(--a-aggressive); }
.world-cell:nth-child(2) { border-left-color: var(--a-balanced); }
.world-cell:nth-child(3) { border-left-color: var(--a-detour); }
.world-cell:nth-child(4) { border-left-color: var(--a-exit); }

.world-dim {
  font-size: 11px;
  font-weight: 700;
  color: var(--c-ink-4);
  margin-bottom: 6px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.delta-tag {
  font-size: 10px;
  font-weight: 700;
  padding: 1px 6px;
  border-radius: var(--r-sm);
  letter-spacing: 0.2px;
  border: 1px solid currentColor;
  line-height: 1.3;
}

.delta-tag.improved {
  color: #059669;
  background: #ECFDF5;
  border-color: #A7F3D0;
}

.delta-tag.depleted {
  color: #DC2626;
  background: #FEF2F2;
  border-color: #FECACA;
}

.delta-tag.shifted {
  color: var(--c-ink-3);
  background: var(--c-bg-soft);
  border-color: var(--c-line-soft);
}

.world-val {
  font-size: 13px;
  line-height: 1.5;
  color: var(--c-ink-2);
}

.stage-narrative {
  font-size: 14px;
  line-height: 1.8;
  color: var(--c-ink-2);
}

.stage-snapshot {
  margin-top: 12px;
  font-size: 12px;
  color: var(--c-ink-4);
  border-top: 1px dashed var(--c-line-soft);
  padding-top: 8px;
}

/* 事件 */
.events-title {
  font-size: 12px;
  font-weight: 700;
  color: var(--c-brand);
  letter-spacing: 1px;
  margin-bottom: 8px;
}

.occurred-events ul {
  padding-left: 18px;
  font-size: 13px;
  color: var(--c-ink-3);
  line-height: 1.8;
}

/* 心智反思与认知转变 (Stanford Generative Agents Reflection) */
.reflections-block {
  margin-top: 14px;
  padding: 12px 14px;
  background: var(--c-bg-subtle, #FAF9F6);
  border: 1px solid var(--c-line-soft);
  border-left: 3px solid var(--c-brand);
  border-radius: var(--r-sm);
}

.reflections-title {
  font-size: 11px;
  font-weight: 700;
  color: var(--c-brand);
  letter-spacing: 1px;
  margin-bottom: 8px;
}

.reflection-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.reflection-card {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.reflection-meta {
  display: flex;
  align-items: center;
  gap: 6px;
}

.reflection-badge {
  font-size: 10px;
  font-weight: 700;
  padding: 1px 6px;
  border-radius: var(--r-sm);
  border: 1px solid currentColor;
  letter-spacing: 0.5px;
  line-height: 1.4;
}

.reflection-badge.self_paradox {
  color: #B45309;
  background: #FFFBEB;
  border-color: #FDE68A;
}

.reflection-badge.relation_insight {
  color: #0369A1;
  background: #F0F9FF;
  border-color: #BAE6FD;
}

.reflection-badge.price_consensus {
  color: #4338CA;
  background: #EEF2FF;
  border-color: #C7D2FE;
}

.reflection-insight {
  font-size: 13px;
  font-weight: 600;
  color: var(--c-ink-1);
  line-height: 1.6;
  font-style: normal;
  margin: 0;
}

.reflection-grounded {
  font-size: 11px;
  color: var(--c-ink-4);
  line-height: 1.4;
  margin-top: 2px;
}

.grounded-label {
  font-weight: 700;
}

/* 关系人主动博弈与施压 (AgentVerse Stakeholder Agency) */
.stakeholders-block {
  margin-top: 14px;
  padding: 12px 14px;
  background: var(--c-bg-subtle, #FAF9F6);
  border: 1px solid var(--c-line-soft);
  border-left: 3px solid #D97706;
  border-radius: var(--r-sm);
}

.stakeholders-title {
  font-size: 11px;
  font-weight: 700;
  color: #B45309;
  letter-spacing: 1px;
  margin-bottom: 8px;
}

.stakeholder-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.stakeholder-move-card {
  padding: 10px 12px;
  background: var(--c-paper, #FFFFFF);
  border: 1px solid var(--c-line-soft);
  border-radius: var(--r-sm);
}

.stakeholder-move-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.stakeholder-name {
  font-size: 13px;
  font-weight: 700;
  color: var(--c-ink-1);
}

.stakeholder-role {
  font-size: 11px;
  color: var(--c-ink-4);
}

.stakeholder-stance-badge {
  font-size: 10px;
  font-weight: 700;
  padding: 1px 6px;
  border-radius: var(--r-sm);
  border: 1px solid currentColor;
  line-height: 1.4;
}

.stakeholder-stance-badge.confrontational {
  color: #DC2626;
  background: #FEF2F2;
  border-color: #FECACA;
}

.stakeholder-stance-badge.transactional {
  color: #B45309;
  background: #FFFBEB;
  border-color: #FDE68A;
}

.stakeholder-stance-badge.supportive {
  color: #0369A1;
  background: #F0F9FF;
  border-color: #BAE6FD;
}

.stakeholder-detail-row {
  font-size: 12px;
  color: var(--c-ink-3);
  line-height: 1.5;
  margin-top: 2px;
}

.detail-label {
  font-weight: 700;
  color: var(--c-ink-2);
}

.stakeholder-demand-row {
  margin-top: 6px;
  padding-top: 6px;
  border-top: 1px dashed var(--c-line-soft);
  font-size: 12px;
  color: var(--c-ink-1);
  font-weight: 600;
}

.demand-label {
  font-weight: 700;
  color: #DC2626;
}

.divergence-note {
  font-size: 12px;
  color: var(--a-detour);
  border-top: 1px dashed var(--c-line-soft);
  padding-top: 10px;
  margin-top: 4px;
}

/* 推演控制栏 */
.advance-bar {
  display: flex;
  gap: 12px;
  margin-bottom: 20px;
}

.event-input {
  flex: 1;
  border: 1px solid var(--c-line-strong);
  padding: 10px 16px;
  font-size: 13px;
  font-family: inherit;
  border-radius: var(--r-sm);
  outline: none;
}

.event-input:focus {
  border-color: var(--c-brand);
}

.advance-btn {
  background: var(--c-brand);
  color: var(--c-paper);
  border: 1px solid var(--c-brand);
  padding: 11px 28px;
  font-size: 14px;
  font-weight: 700;
  cursor: pointer;
  border-radius: var(--r-sm);
  font-family: inherit;
  white-space: nowrap;
  transition: all var(--dur-fast);
}

.advance-btn:hover:not(:disabled) {
  background: var(--c-brand-deep);
  border-color: var(--c-brand-deep);
  box-shadow: var(--shadow-pop-sm);
  transform: translate(-1px, -1px);
}

.advance-btn:active:not(:disabled) {
  transform: translate(1px, 1px);
  box-shadow: 1px 1px 0 var(--c-ink);
}

.advance-btn:disabled {
  background: var(--c-bg-soft);
  border-color: var(--c-line);
  color: var(--c-ink-5);
  cursor: not-allowed;
  transform: none;
  box-shadow: none;
}

.advance-error {
  color: var(--c-brand);
  font-size: 13px;
  margin-top: 8px;
}

/* 已裁决分叉 */
.resolved-forks {
  border: 1px solid var(--c-line-soft);
  border-radius: var(--r-md);
  padding: 16px 20px;
  margin-top: 20px;
}

.resolved-fork-row {
  display: flex;
  gap: 10px;
  padding: 6px 0;
  font-size: 13px;
  align-items: baseline;
}

.fork-q {
  color: var(--c-ink-3);
}

.fork-choice {
  font-weight: 700;
  color: var(--a-detour);
}

/* 下一步行动引导卡片 */
.next-action-card {
  margin-top: 32px;
  padding: 24px;
  background: var(--c-bg-subtle, #fbf9f5);
  border: 2px solid var(--c-ink);
  border-radius: var(--r-md);
  box-shadow: var(--shadow-pop);
}

.next-card-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.next-symbol {
  color: var(--c-brand);
  font-size: 11px;
}

.next-title {
  font-size: 16px;
  font-weight: 700;
  color: var(--c-ink);
  letter-spacing: 0.5px;
}

.next-card-desc {
  font-size: 13px;
  color: var(--c-ink-3);
  line-height: 1.6;
  margin-bottom: 20px;
}

.next-card-actions {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.next-btn {
  font-family: inherit;
  font-size: 13px;
  font-weight: 700;
  padding: 10px 20px;
  border-radius: var(--r-sm);
  cursor: pointer;
  border: 1px solid var(--c-line-strong);
  background: var(--c-paper);
  color: var(--c-ink-2);
  transition: all var(--dur-fast);
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.next-btn:hover {
  box-shadow: var(--shadow-pop-sm);
  transform: translate(-1px, -1px);
}

.next-btn.primary {
  background: var(--c-brand);
  color: var(--c-paper);
  border-color: var(--c-brand);
}

.next-btn.primary:hover {
  background: var(--c-brand-deep);
  border-color: var(--c-brand-deep);
}

.next-btn.ghost {
  background: transparent;
  border-color: var(--c-line-strong);
  color: var(--c-ink-3);
}

.next-btn.ghost:hover {
  border-color: var(--c-ink);
  color: var(--c-ink);
}

@media (max-width: 640px) {
  .world-grid {
    grid-template-columns: 1fr;
  }
  .fork-options {
    grid-template-columns: 1fr;
  }
  .advance-bar {
    flex-direction: column;
  }
  .next-card-actions {
    flex-direction: column;
  }
}



/* 原子记忆状态变更流 (Mem0 架构) */
.mutations-block {
  margin-top: 14px;
  padding: 12px 14px;
  background: var(--c-bg-subtle, #FAF9F6);
  border: 1px solid var(--c-line-soft);
  border-left: 3px solid #059669;
  border-radius: var(--r-sm);
}

.mutations-title {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 11px;
  font-weight: 700;
  color: #047857;
  letter-spacing: 1px;
  margin-bottom: 8px;
}

.active-count-tag {
  font-size: 10px;
  font-weight: 600;
  color: var(--c-ink-4);
  background: var(--c-paper, #FFFFFF);
  border: 1px solid var(--c-line-soft);
  padding: 1px 6px;
  border-radius: var(--r-sm);
}

.mutation-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.mutation-card {
  padding: 10px 12px;
  background: var(--c-paper, #FFFFFF);
  border: 1px solid var(--c-line-soft);
  border-radius: var(--r-sm);
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.mutation-header {
  display: flex;
  align-items: center;
  gap: 6px;
}

.action-tag {
  font-size: 10px;
  font-weight: 700;
  padding: 1px 6px;
  border-radius: var(--r-sm);
  border: 1px solid currentColor;
  line-height: 1.4;
}

.action-tag.add {
  color: #059669;
  background: #ECFDF5;
  border-color: #A7F3D0;
}

.action-tag.update {
  color: #D97706;
  background: #FFFBEB;
  border-color: #FDE68A;
}

.action-tag.delete {
  color: #DC2626;
  background: #FEF2F2;
  border-color: #FECACA;
}

.action-tag.noop {
  color: #6B7280;
  background: #F3F4F6;
  border-color: #E5E7EB;
}

.category-tag {
  font-size: 10px;
  color: var(--c-ink-4);
  background: var(--c-bg-soft);
  border: 1px solid var(--c-line-soft);
  padding: 1px 5px;
  border-radius: var(--r-sm);
}

.subject-tag {
  font-size: 11px;
  font-weight: 600;
  color: var(--c-ink-2);
}

.mutation-fact {
  font-size: 12px;
  line-height: 1.5;
  color: var(--c-ink-1);
}

.prev-fact {
  color: var(--c-ink-4);
  text-decoration: line-through;
  margin-right: 4px;
}

.current-fact {
  font-weight: 600;
}

.mutation-reason {
  font-size: 11px;
  color: var(--c-ink-4);
  line-height: 1.4;
}

.reason-label {
  font-weight: 600;
}


/* 人格防漂移保真度审计 (Anti-Drift Guard) */
.anti-drift-block {
  margin-top: 14px;
  background: var(--c-bg-subtle, #FAF9F6);
  border: 1px solid var(--c-line-soft);
  border-left: 3px solid #4F46E5;
  border-radius: var(--r-sm);
  padding: 10px 14px;
}

.anti-drift-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6px;
}

.anti-drift-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  font-weight: 700;
  color: var(--c-ink-2);
  letter-spacing: 0.5px;
}

.drift-bullet {
  color: #4F46E5;
  font-size: 9px;
}

.anti-drift-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 2px 8px;
  border-radius: var(--r-sm);
  font-size: 11px;
  font-weight: 700;
  border: 1px solid currentColor;
}

.anti-drift-badge.stable {
  color: #059669;
  background: #ECFDF5;
  border-color: #A7F3D0;
}

.anti-drift-badge.minor_divergence {
  color: #D97706;
  background: #FFFBEB;
  border-color: #FDE68A;
}

.anti-drift-badge.drift_warning {
  color: #DC2626;
  background: #FEF2F2;
  border-color: #FECACA;
}

.drift-score {
  font-family: var(--font-mono, monospace);
  font-size: 12px;
}

.drift-status-label {
  font-size: 10px;
}

.anti-drift-diagnostics {
  font-size: 12px;
  color: var(--c-ink-2);
  line-height: 1.5;
  margin: 0 0 6px 0;
}

.anti-drift-anchors {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.anchor-tag {
  font-size: 10px;
  font-weight: 600;
  color: var(--c-ink-3);
  background: var(--c-paper, #FFFFFF);
  border: 1px solid var(--c-line-soft);
  padding: 1px 6px;
  border-radius: var(--r-sm);
}

</style>
