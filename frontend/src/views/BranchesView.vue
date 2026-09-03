<template>
  <div class="branches-view">
    <!-- 顶部统一导航 -->
    <AppHeader :project-id="projectId" current-step="branches" />

    <div class="main-content">
      <!-- 加载/无分支态 -->
      <div v-if="loading" class="state-box">
        <p>{{ t('common.loading') }}</p>
      </div>

      <div v-else-if="!branchesData" class="state-box">
        <p>{{ loadError || t('branch.view.notGenerated') }}</p>
        <button class="generate-btn" type="button" @click="startGenerate">
          {{ t('branch.view.generateNow') }}
        </button>
      </div>

      <template v-else>
        <header class="page-header">
          <h1 class="page-title">{{ t('branch.view.title') }}</h1>
          <p class="page-meta">
            {{ t('branch.view.basedOn') }} v{{ branchesData.source_model_version }} ·
            {{ branchesData.branch_count }} {{ t('branch.view.branchesUnit') }}
          </p>
          <button class="regenerate-link" type="button" @click="startGenerate">
            ↻ {{ t('branch.view.regenerate') }}
          </button>
        </header>

        <!-- 生成中遮罩 -->
        <div v-if="generating" class="generating-bar">
          <div class="generating-progress">
            <div class="generating-fill" :style="{ width: genProgress + '%' }"></div>
          </div>
          <p class="generating-msg">{{ genMessage }}</p>
        </div>

        <!-- 分支选择 tab -->
        <div class="branch-tabs">
          <button
            v-for="(b, i) in branchesData.branches"
            :key="i"
            class="branch-tab"
            :class="{ active: activeIndex === i }"
            type="button"
            @click="activeIndex = i"
          >
            <span class="tab-archetype">{{ archetypeLabel(b.archetype) }}</span>
            <span class="tab-score">{{ b.fit_score }}</span>
          </button>
        </div>

        <!-- 当前分支 -->
        <div v-if="activeBranch" class="branch-detail">
          <!-- 定位条 -->
          <div class="positioning-row">
            <div class="positioning-main">
              <span class="archetype-badge" :class="activeBranch.archetype">{{ archetypeLabel(activeBranch.archetype) }}</span>
              <span class="positioning-text">{{ activeBranch.positioning }}</span>
            </div>
            <div class="positioning-actions">
              <div class="fit-box">
                <span class="fit-num">{{ activeBranch.fit_score }}</span>
                <span class="fit-label">{{ t('branch.view.fitScore') }}</span>
              </div>
            </div>
          </div>

          <!-- 叙事 -->
          <section class="branch-section">
            <div class="section-title">{{ t('branch.view.narrative') }} · {{ activeBranch.time_span }}</div>
            <p class="narrative-text">{{ activeBranch.narrative }}</p>
            <p class="rationale-text">{{ t('branch.view.whyThis') }}{{ activeBranch.rationale }}</p>
          </section>

          <!-- 时间线 -->
          <section v-if="activeBranch.timeline?.length" class="branch-section">
            <div class="section-title">{{ t('branch.view.timeline') }}</div>
            <div class="timeline">
              <div v-for="(node, i) in activeBranch.timeline" :key="i" class="timeline-node">
                <div class="node-period">{{ node.period }}</div>
                <div class="node-body">
                  <div class="node-event">{{ node.event }}</div>
                  <div class="node-change">{{ node.state_change }}</div>
                </div>
              </div>
            </div>
          </section>

          <!-- 双列：风险 & 里程碑 -->
          <div class="two-col">
            <section v-if="activeBranch.risks?.length" class="branch-section">
              <div class="section-title">{{ t('branch.view.risks') }}</div>
              <div v-for="(r, i) in activeBranch.risks" :key="i" class="risk-row">
                <div class="risk-top">
                  <span class="risk-likelihood" :class="r.likelihood">{{ likelihoodLabel(r.likelihood) }}</span>
                  <span class="risk-text">{{ r.risk }}</span>
                </div>
                <p class="risk-mitigation">→ {{ r.mitigation }}</p>
              </div>
            </section>

            <section v-if="activeBranch.milestones?.length" class="branch-section">
              <div class="section-title">{{ t('branch.view.milestones') }}</div>
              <div v-for="(m, i) in activeBranch.milestones" :key="i" class="milestone-row">
                <span class="milestone-kind" :class="m.milestone_kind">{{ kindLabel(m.milestone_kind) }}</span>
                <div class="milestone-body">
                  <div class="milestone-summary">{{ m.summary }}</div>
                  <div class="milestone-impact">{{ m.impact }}</div>
                </div>
              </div>
            </section>
          </div>

          <!-- 双列：能力缺口 & 关系影响 -->
          <div class="two-col">
            <section v-if="activeBranch.capability_gaps?.length" class="branch-section">
              <div class="section-title">{{ t('branch.view.gaps') }}</div>
              <ul class="gap-list">
                <li v-for="(g, i) in activeBranch.capability_gaps" :key="i">{{ g }}</li>
              </ul>
            </section>

            <section v-if="activeBranch.relationship_impacts?.length" class="branch-section">
              <div class="section-title">{{ t('branch.view.relImpacts') }}</div>
              <div v-for="(r, i) in activeBranch.relationship_impacts" :key="i" class="rel-row">
                <span class="rel-person">{{ r.person }}</span>
                <span class="rel-impact">{{ r.impact }}</span>
              </div>
            </section>
          </div>

          <!-- 关键假设 & 结局 -->
          <section class="branch-section assumption-section">
            <div class="section-title">{{ t('branch.view.keyAssumption') }}</div>
            <p class="assumption-text">{{ activeBranch.key_assumption }}</p>
            <div class="section-title ending-title">{{ t('branch.view.endingState') }}</div>
            <p class="ending-text">{{ activeBranch.ending_state }}</p>
            <p class="fit-rationale">{{ activeBranch.fit_rationale }}</p>
            <p class="disclaimer">{{ t('branch.view.disclaimer') }}</p>

            <!-- 深度推演入口 -->
            <button class="evolve-btn" type="button" :disabled="evolving" @click="startEvolution">
              {{ evolving ? t('evolution.view.creating') : t('evolution.view.entry') }} →
            </button>
          </section>
        </div>

        <!-- 已有推演会话（平行宇宙列表） -->
        <section v-if="sessions.length" class="branch-section">
          <div class="section-title universe-title-row">
            {{ t('evolution.view.myUniverses') }}
            <button class="roundtable-entry" type="button" @click="router.push(`/roundtable/${projectId}`)">
              {{ t('roundtable.view.entry') }}
            </button>
          </div>
          <div
            v-for="s in sessions"
            :key="s.session_id"
            class="session-row"
            role="button"
            @click="router.push(`/evolution/${s.session_id}`)"
          >
            <span class="archetype-badge" :class="s.source_branch_archetype">
              {{ archetypeLabel(s.source_branch_archetype) }}
            </span>
            <span class="session-positioning">{{ s.source_branch_positioning }}</span>
            <span class="session-progress">{{ s.stages_done }}/{{ s.stage_count }}</span>
            <span class="session-status" :class="s.status">{{ statusLabel(s.status) }}</span>
          </div>
        </section>
      </template>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import AppHeader from '../components/AppHeader.vue'
import { getBranches, generateBranches, getBranchGenerateStatus } from '../api/branch'
import { createEvolutionSession, listEvolutionSessions } from '../api/evolution'

const props = defineProps({
  projectId: { type: String, required: true }
})

const router = useRouter()
const { t, te } = useI18n()

const loading = ref(true)
const loadError = ref('')
const branchesData = ref(null)
const activeIndex = ref(0)
const generating = ref(false)
const genProgress = ref(0)
const genMessage = ref('')
const evolving = ref(false)
const sessions = ref([])
let generationToken = 0

function statusLabel(key) {
  const i18nKey = `evolution.status.${key}`
  return te(i18nKey) ? t(i18nKey) : (key || '')
}

async function loadSessions() {
  try {
    const res = await listEvolutionSessions(props.projectId)
    sessions.value = res.data || []
  } catch {
    sessions.value = []
  }
}

async function startEvolution() {
  if (evolving.value || activeIndex.value == null) return
  evolving.value = true
  try {
    const res = await createEvolutionSession({
      project_id: props.projectId,
      branch_index: activeIndex.value
    })
    router.push(`/evolution/${res.data.session_id}`)
  } catch (e) {
    loadError.value = e?.message || String(e)
  } finally {
    evolving.value = false
  }
}

const activeBranch = computed(() => branchesData.value?.branches?.[activeIndex.value])

function archetypeLabel(key) {
  const i18nKey = `branch.archetype.${key}`
  return te(i18nKey) ? t(i18nKey) : (key || '')
}

function likelihoodLabel(key) {
  const i18nKey = `branch.likelihood.${key}`
  return te(i18nKey) ? t(i18nKey) : (key || '')
}

function kindLabel(key) {
  const i18nKey = `branch.kind.${key}`
  return te(i18nKey) ? t(i18nKey) : (key || '')
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms))
}

async function startGenerate() {
  const token = ++generationToken
  generating.value = true
  genProgress.value = 5
  genMessage.value = t('branch.view.genStarting')
  try {
    const res = await generateBranches({ project_id: props.projectId })
    const deadline = Date.now() + 15 * 60 * 1000
    let failures = 0
    while (Date.now() < deadline) {
      await sleep(3000)
      if (token !== generationToken) return
      try {
        const statusRes = await getBranchGenerateStatus(res.data.task_id)
        failures = 0
        const task = statusRes.data
        genProgress.value = task.progress || 0
        genMessage.value = task.message || ''
        if (task.status === 'completed') break
        if (['failed', 'cancelled', 'stale'].includes(task.status)) {
          throw new Error(task.message || task.error || 'task failed')
        }
      } catch (error) {
        failures += 1
        if (failures >= 5) throw error
        await sleep(Math.min(30000, 1000 * 2 ** failures))
      }
    }
    if (Date.now() >= deadline) throw new Error('任务超过最大等待时间，请刷新查看状态')
    if (token !== generationToken) return
    const dataRes = await getBranches(props.projectId)
    branchesData.value = dataRes.data
    activeIndex.value = 0
  } catch (e) {
    loadError.value = e?.message || String(e)
    genMessage.value = loadError.value
  } finally {
    if (token === generationToken) generating.value = false
  }
}

onMounted(async () => {
  try {
    const res = await getBranches(props.projectId)
    branchesData.value = res.data
  } catch (e) {
    // 404 = 尚未生成，页面会显示生成按钮
    loadError.value = ''
  } finally {
    await loadSessions()
    loading.value = false
  }
})

onUnmounted(() => {
  generationToken += 1
})
</script>

<style scoped>
.branches-view {
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

.back-profile {
  border: 1px solid var(--c-line-strong);
  background: var(--c-paper);
  padding: 6px 14px;
  font-size: 13px;
  cursor: pointer;
  font-family: inherit;
  border-radius: var(--r-sm);
  color: var(--c-ink-2);
}

.back-profile:hover {
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
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
}

.page-header {
  margin-bottom: 24px;
}

.page-title {
  font-size: 24px;
  font-weight: 700;
}

.page-meta {
  margin-top: 6px;
  color: var(--c-ink-4);
  font-size: 13px;
}

.regenerate-link {
  margin-top: 10px;
  border: none;
  background: none;
  color: var(--c-brand);
  font-size: 13px;
  cursor: pointer;
  font-family: inherit;
  padding: 0;
}

.regenerate-link:hover {
  text-decoration: underline;
}

/* 生成进度 */
.generating-bar {
  border: 1px solid var(--c-brand-line);
  background: var(--c-brand-tint);
  border-radius: var(--r-md);
  padding: 16px 20px;
  margin-bottom: 24px;
}

.generating-progress {
  height: 4px;
  background: var(--c-brand-line);
  border-radius: var(--r-sm);
  overflow: hidden;
}

.generating-fill {
  height: 100%;
  background: var(--c-brand);
  transition: width 0.6s ease;
}

.generating-msg {
  margin-top: 10px;
  font-size: 13px;
  color: var(--c-ink-3);
}

/* 分支 tab */
.branch-tabs {
  display: flex;
  gap: 8px;
  margin-bottom: 20px;
  overflow-x: auto;
  padding-bottom: 4px;
}

.branch-tab {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 3px;
  border: 1px solid var(--c-line-strong);
  background: var(--c-bg-softer);
  padding: 10px 16px;
  cursor: pointer;
  font-family: inherit;
  border-radius: var(--r-sm);
  min-width: 96px;
  transition: all var(--dur-fast);
}

.branch-tab:hover {
  background: var(--c-paper);
  border-color: var(--c-ink);
  box-shadow: 2px 2px 0 var(--c-ink);
  transform: translate(-1px, -1px);
}

.branch-tab.active {
  border-color: var(--c-ink);
  background: var(--c-ink);
  box-shadow: var(--shadow-pop-sm);
  transform: translate(0, 0);
}

.branch-tab.active .tab-archetype,
.branch-tab.active .tab-score {
  color: var(--c-paper);
}

.tab-archetype {
  font-size: 13px;
  font-weight: 700;
  color: var(--c-ink-2);
}

.tab-score {
  font-size: 11px;
  color: var(--c-brand);
}

.branch-tab.active .tab-score {
  color: var(--c-brand-light);
}

/* 分支详情 */
.branch-detail {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.positioning-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  border: 1px solid var(--c-line);
  border-radius: var(--r-md);
  padding: 18px 22px;
}

.positioning-main {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.archetype-badge {
  font-size: 11px;
  font-weight: 700;
  padding: 4px 10px;
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

.positioning-text {
  font-size: 15px;
  font-weight: 600;
  line-height: 1.6;
}

.positioning-actions {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-shrink: 0;
}

.evolve-btn-top {
  background: var(--c-brand);
  color: var(--c-paper);
  border: none;
  padding: 10px 18px;
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
  border-radius: var(--r-sm);
  font-family: inherit;
  white-space: nowrap;
  transition: all 0.15s;
}

.evolve-btn-top:hover:not(:disabled) {
  background: var(--c-brand-deep);
  box-shadow: var(--shadow-pop-sm);
  transform: translate(-1px, -1px);
}

.evolve-btn-top:disabled {
  background: var(--c-ink-5);
  cursor: not-allowed;
}

.fit-box {
  display: flex;
  flex-direction: column;
  align-items: center;
  border-left: 1px solid var(--c-line-soft);
  padding-left: 16px;
  min-width: 60px;
}

.fit-num {
  font-size: 28px;
  font-weight: 700;
  color: var(--c-brand);
}

.fit-label {
  font-size: 11px;
  color: var(--c-ink-4);
}

/* 区块 */
.branch-section {
  border: 1px solid var(--c-line);
  border-radius: var(--r-md);
  padding: 20px 24px;
}

.section-title {
  font-size: 12px;
  font-weight: 700;
  color: var(--c-brand);
  letter-spacing: 1px;
  text-transform: uppercase;
  margin-bottom: 14px;
}

.narrative-text {
  font-size: 14px;
  line-height: 1.9;
  color: var(--c-ink-2);
}

.rationale-text {
  margin-top: 12px;
  font-size: 12px;
  color: var(--c-ink-4);
  border-top: 1px dashed var(--c-line-soft);
  padding-top: 10px;
}

/* 时间线 */
.timeline {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.timeline-node {
  display: flex;
  gap: 16px;
  position: relative;
  padding-bottom: 18px;
}

.timeline-node:not(:last-child)::before {
  content: '';
  position: absolute;
  left: 5px;
  top: 16px;
  bottom: 0;
  width: 1px;
  background: var(--c-line-strong);
}

.timeline-node::before {
  content: '';
  position: absolute;
  left: 2px;
  top: 7px;
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--c-brand);
}

.node-period {
  min-width: 96px;
  font-size: 13px;
  font-weight: 700;
  color: var(--c-ink-2);
  padding-top: 2px;
}

.node-body {
  padding-left: 12px;
}

.node-event {
  font-size: 14px;
  line-height: 1.6;
  color: var(--c-ink-2);
}

.node-change {
  margin-top: 4px;
  font-size: 12px;
  color: var(--c-ink-4);
  line-height: 1.5;
}

/* 双列 */
.two-col {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
}

/* 风险 */
.risk-row {
  padding: 10px 0;
  border-bottom: 1px solid var(--c-bg-soft);
}

.risk-row:last-child {
  border-bottom: none;
}

.risk-top {
  display: flex;
  gap: 8px;
  align-items: baseline;
}

.risk-likelihood {
  font-size: 10px;
  font-weight: 700;
  padding: 2px 7px;
  border-radius: var(--r-sm);
  white-space: nowrap;
  color: var(--c-paper);
}

.risk-likelihood.high { background: var(--a-aggressive); }
.risk-likelihood.medium { background: var(--a-detour); }
.risk-likelihood.low { background: var(--c-ink-3); }

.risk-text {
  font-size: 13px;
  font-weight: 600;
  line-height: 1.5;
}

.risk-mitigation {
  margin-top: 4px;
  font-size: 12px;
  color: var(--c-ink-3);
  line-height: 1.5;
  padding-left: 2px;
}

/* 里程碑 */
.milestone-row {
  display: flex;
  gap: 10px;
  padding: 10px 0;
  border-bottom: 1px solid var(--c-bg-soft);
  align-items: flex-start;
}

.milestone-row:last-child {
  border-bottom: none;
}

.milestone-kind {
  font-size: 10px;
  font-weight: 700;
  padding: 2px 7px;
  border-radius: var(--r-sm);
  white-space: nowrap;
  margin-top: 2px;
  color: var(--c-paper);
}

.milestone-kind.turning_point { background: var(--c-ink-2); }
.milestone-kind.achievement { background: var(--a-balanced); }
.milestone-kind.setback { background: var(--a-aggressive); }

.milestone-summary {
  font-size: 13px;
  font-weight: 600;
  line-height: 1.5;
}

.milestone-impact {
  margin-top: 3px;
  font-size: 12px;
  color: var(--c-ink-4);
  line-height: 1.5;
}

/* 能力缺口 & 关系 */
.gap-list {
  padding-left: 18px;
  font-size: 13px;
  color: var(--c-ink-2);
  line-height: 1.8;
}

.rel-row {
  display: flex;
  flex-direction: column;
  gap: 3px;
  padding: 8px 0;
  border-bottom: 1px solid var(--c-bg-soft);
}

.rel-row:last-child {
  border-bottom: none;
}

.rel-person {
  font-size: 13px;
  font-weight: 700;
}

.rel-impact {
  font-size: 12px;
  color: var(--c-ink-3);
  line-height: 1.5;
}

/* 假设与结局 */
.assumption-text {
  font-size: 14px;
  font-weight: 600;
  line-height: 1.7;
  color: var(--c-ink-2);
  background: var(--c-bg-softer);
  border-left: 3px solid var(--a-detour);
  padding: 12px 16px;
}

.ending-title {
  margin-top: 18px;
}

.ending-text {
  font-size: 14px;
  line-height: 1.8;
  color: var(--c-ink-2);
}

.fit-rationale {
  margin-top: 14px;
  font-size: 12px;
  color: var(--c-ink-4);
  border-top: 1px dashed var(--c-line-soft);
  padding-top: 10px;
}

.disclaimer {
  margin-top: 10px;
  font-size: 11px;
  color: var(--c-ink-5);
}

/* 深度推演入口 */
.evolve-btn {
  margin-top: 18px;
  width: 100%;
  background: var(--c-brand);
  color: var(--c-paper);
  border: 1px solid var(--c-brand);
  padding: 13px 24px;
  font-size: 14px;
  font-weight: 700;
  cursor: pointer;
  border-radius: var(--r-sm);
  font-family: inherit;
  transition: all var(--dur-fast);
}

.evolve-btn:hover:not(:disabled) {
  background: var(--c-brand-deep);
  border-color: var(--c-brand-deep);
  box-shadow: var(--shadow-pop-sm);
  transform: translate(-1px, -1px);
}

.evolve-btn:active:not(:disabled) {
  transform: translate(1px, 1px);
  box-shadow: 1px 1px 0 var(--c-ink);
}

.evolve-btn:disabled {
  border-color: var(--c-ink-5);
  color: var(--c-ink-5);
  cursor: not-allowed;
}

/* 推演会话列表 */
.session-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 8px;
  border-bottom: 1px solid var(--c-bg-soft);
  cursor: pointer;
  transition: background 0.15s;
}

.universe-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.roundtable-entry {
  border: 2px solid var(--c-brand);
  background: var(--c-paper);
  color: var(--c-brand);
  font-size: 13px;
  font-weight: 700;
  padding: 6px 16px;
  border-radius: var(--r-sm);
  cursor: pointer;
  font-family: inherit;
  transition: all 0.15s;
}

.roundtable-entry:hover {
  background: var(--c-brand);
  color: var(--c-paper);
}

.session-row:last-child {
  border-bottom: none;
}

.session-row:hover {
  background: var(--c-bg-softer);
}

.session-positioning {
  flex: 1;
  font-size: 13px;
  color: var(--c-ink-2);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.session-progress {
  font-size: 12px;
  font-weight: 700;
  color: var(--c-ink-3);
}

.session-status {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: var(--r-sm);
  color: var(--c-paper);
  background: var(--c-ink-4);
  white-space: nowrap;
}

.session-status.active { background: var(--c-brand); }
.session-status.completed { background: var(--a-balanced); }
.session-status.aborted { background: var(--c-ink-4); }

.generate-btn {
  background: var(--c-brand);
  color: var(--c-paper);
  border: none;
  padding: 12px 32px;
  font-size: 14px;
  font-weight: 700;
  cursor: pointer;
  border-radius: var(--r-sm);
  font-family: inherit;
}

.generate-btn:hover {
  background: var(--c-brand-deep);
}

@media (max-width: 720px) {
  .two-col {
    grid-template-columns: 1fr;
  }
  .positioning-row {
    flex-direction: column;
  }
  .fit-box {
    border-left: none;
    padding-left: 0;
    flex-direction: row;
    gap: 8px;
    align-items: baseline;
  }
}
</style>
