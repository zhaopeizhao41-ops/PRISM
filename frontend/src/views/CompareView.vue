<template>
  <div class="compare-view">
    <!-- 顶部统一导航 -->
    <AppHeader :project-id="projectId" current-step="compare" />

    <div class="main-content">
      <div v-if="loading" class="state-box">{{ t('common.loading') }}</div>

      <div v-else-if="!universes.length" class="state-box">
        <p>{{ t('compare.empty') }}</p>
        <button class="btn-mini" type="button" @click="router.push(`/branches/${projectId}`)">
          {{ t('compare.goEvolve') }} →
        </button>
      </div>

      <template v-else>
        <header class="page-header">
          <h1 class="page-title">⇄ {{ t('compare.title') }}</h1>
          <p class="page-meta">{{ t('compare.subtitle', { n: universes.length }) }}</p>
        </header>

        <!-- 宇宙列头 -->
        <div class="compare-scroll-wrapper">
          <div class="compare-grid" :style="{ gridTemplateColumns: `100px repeat(${universes.length}, minmax(260px, 1fr))` }">
            <div class="corner-cell"></div>
            <div v-for="u in universes" :key="u.session_id" class="universe-head">
            <span class="archetype-badge" :class="u.archetype">{{ archetypeLabel(u.archetype) }}</span>
            <p class="universe-positioning">{{ u.positioning }}</p>
            <span class="universe-meta">
              {{ u.stages_done }}/{{ u.stage_count }} ·
              <span :class="['st', u.status]">{{ statusLabel(u.status) }}</span>
            </span>
          </div>

          <!-- 核心收益与代价速览行 -->
          <div class="dim-cell highlight gain-label">{{ t('compare.coreGain') }}</div>
          <div
            v-for="u in universes"
            :key="'gain' + u.session_id"
            class="val-cell gain-cell"
            role="button"
            @click="router.push(`/evolution/${u.session_id}`)"
          >
            <span class="gain-badge">+ 收益</span>
            <span class="highlight-text">{{ extractGain(u) }}</span>
          </div>

          <div class="dim-cell highlight sacrifice-label">{{ t('compare.keySacrifice') }}</div>
          <div
            v-for="u in universes"
            :key="'sac' + u.session_id"
            class="val-cell sacrifice-cell"
            role="button"
            @click="router.push(`/evolution/${u.session_id}`)"
          >
            <span class="sac-badge">- 代价</span>
            <span class="highlight-text">{{ extractSacrifice(u) }}</span>
          </div>

          <!-- 4 维终态行 -->
          <template v-for="dim in dims" :key="dim.key">
            <div class="dim-cell" :class="dim.key">{{ t(`evolution.dim.${dim.key}`) }}</div>
            <div
              v-for="u in universes"
              :key="u.session_id + dim.key"
              class="val-cell"
              role="button"
              @click="router.push(`/evolution/${u.session_id}`)"
            >
              {{ u.final_world_state?.[dim.key] || '—' }}
            </div>
          </template>

          <!-- 叙事终局行 -->
          <div class="dim-cell narrative">{{ t('compare.endingRow') }}</div>
          <div
            v-for="u in universes"
            :key="'snap' + u.session_id"
            class="val-cell snapshot"
            role="button"
            tabindex="0"
            @click="router.push(`/evolution/${u.session_id}`)"
            @keydown.enter="router.push(`/evolution/${u.session_id}`)"
          >
            {{ u.final_snapshot || '—' }}
          </div>
        </div>
        </div>

        <!-- 偏离与分叉汇总 -->
        <section class="detail-section">
          <div class="section-title">{{ t('compare.divergenceTitle') }}</div>
          <div v-for="u in universes" :key="'d' + u.session_id" class="detail-row">
            <span class="archetype-badge small" :class="u.archetype">{{ archetypeLabel(u.archetype) }}</span>
            <div class="detail-body">
              <p v-for="(d, i) in u.divergences" :key="i" class="div-line">
                {{ t('evolution.view.stageNo', { n: d.stage }) }} ⤴ {{ d.note }}
              </p>
              <p v-for="(f, i) in u.resolved_forks" :key="'f' + i" class="fork-line">
                {{ f.question }} → <b>{{ f.choice }}</b>
              </p>
              <p v-if="!u.divergences.length && !u.resolved_forks.length" class="quiet">
                {{ t('compare.noDivergence') }}
              </p>
            </div>
          </div>
        </section>

        <!-- 收束区：多种可能的人生 -->
        <section class="closing-section">
          <h2 class="closing-title">{{ t('compare.closingTitle') }}</h2>
          <p class="closing-motto">{{ t('compare.closingMotto') }}</p>
          <p class="closing-text">{{ t('compare.closingText') }}</p>

          <!-- 接下来：进入圆桌辩论 -->
          <div class="compare-next-card">
            <div class="next-card-head">
              <span class="next-symbol">■</span>
              <span class="next-title">{{ t('compare.nextDebateTitle') }}</span>
            </div>
            <p class="next-card-desc">{{ t('compare.nextDebateDesc') }}</p>
            <div class="next-card-actions">
              <button class="next-btn primary" type="button" @click="router.push(`/roundtable/${projectId}`)">
                {{ t('compare.goRoundtableBtn') }} →
              </button>
              <button class="next-btn ghost" type="button" @click="router.push(`/branches/${projectId}`)">
                ← {{ t('compare.backBranches') }}
              </button>
            </div>
          </div>
        </section>
      </template>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import AppHeader from '../components/AppHeader.vue'
import { compareEvolutionSessions } from '../api/evolution'

const props = defineProps({
  projectId: { type: String, required: true }
})

const router = useRouter()
const { t, te } = useI18n()

const loading = ref(true)
const universes = ref([])

const dims = [
  { key: 'career' }, { key: 'family' },
  { key: 'resources' }, { key: 'psyche' },
]

function archetypeLabel(key) {
  const i18nKey = `branch.archetype.${key}`
  return te(i18nKey) ? t(i18nKey) : (key || '')
}

function statusLabel(key) {
  const i18nKey = `evolution.status.${key}`
  return te(i18nKey) ? t(i18nKey) : (key || '')
}

function extractGain(u) {
  const ws = u.final_world_state || {}
  const gains = []
  if (ws.resources && /增加|增长|提升|多出|缓冲|4|5|清零|还清|二两/.test(ws.resources)) {
    gains.push(ws.resources.split(/[，。；]/)[0])
  }
  if (ws.career && /扩展|增多|口碑|固定客户|稳定|建立|摆摊|代写/.test(ws.career)) {
    gains.push(ws.career.split(/[，。；]/)[0])
  }
  if (ws.psyche && /减轻|好转|积极|踏实|实在感|适应/.test(ws.psyche)) {
    gains.push(ws.psyche.split(/[，。；]/)[0])
  }
  if (gains.length) return gains.slice(0, 2).join('；')
  return u.positioning ? u.positioning.split(/[，。；]/)[0] : '—'
}

function extractSacrifice(u) {
  const ws = u.final_world_state || {}
  const sacrifices = []
  if (ws.resources && /债务|借款|高筑|手头空空|手头拮据|消耗/.test(ws.resources)) {
    sacrifices.push(ws.resources.split(/[，。；]/)[0])
  }
  if (ws.psyche && /内耗|加剧|压力增大|羞耻|崩溃|焦虑|自嘲|落魄/.test(ws.psyche)) {
    sacrifices.push(ws.psyche.split(/[，。；]/)[0])
  }
  if (ws.career && /受限|缓慢|停了|无法|辞退|打折|粗活|地位未/.test(ws.career)) {
    sacrifices.push(ws.career.split(/[，。；]/)[0])
  }
  if (ws.family && /恶化|疏远|嘲笑|冲突|追债|断绝/.test(ws.family)) {
    sacrifices.push(ws.family.split(/[，。；]/)[0])
  }
  if (sacrifices.length) return sacrifices.slice(0, 2).join('；')
  return '维持现状与机会成本'
}

onMounted(async () => {
  try {
    const res = await compareEvolutionSessions(props.projectId)
    universes.value = res.data || []
  } catch {
    universes.value = []
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.compare-view {
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
  max-width: 1100px;
  margin: 0 auto;
  padding: 32px 24px 96px;
}

.state-box {
  text-align: center;
  padding: 80px 0;
  color: var(--c-ink-3);
}

.btn-mini {
  margin-top: 12px;
  border: 1px solid var(--c-ink);
  background: var(--c-paper);
  padding: 8px 20px;
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
  font-family: inherit;
  border-radius: var(--r-sm);
}

.btn-mini:hover {
  box-shadow: var(--shadow-pop-sm);
}

.page-header {
  margin-bottom: 24px;
}

.page-title {
  font-size: 24px;
  font-weight: 700;
}

.page-meta {
  margin-top: 8px;
  color: var(--c-ink-4);
  font-size: 13px;
}

/* 对比网格容器 */
.compare-scroll-wrapper {
  width: 100%;
  overflow-x: auto;
  margin-bottom: 32px;
  border-radius: var(--r-md);
}

.compare-grid {
  display: grid;
  gap: 1px;
  background: var(--c-line);
  border: 1px solid var(--c-line);
  border-radius: var(--r-md);
  overflow: hidden;
  min-width: 100%;
}

.compare-grid > div {
  background: var(--c-paper);
  padding: 12px 16px;
  font-size: 13px;
  line-height: 1.7;
}

.corner-cell {
  background: var(--c-bg-softer);
}

.universe-head {
  display: flex;
  flex-direction: column;
  gap: 6px;
  align-items: flex-start;
}

.universe-positioning {
  font-size: 13px;
  font-weight: 600;
  line-height: 1.5;
}

.universe-meta {
  font-size: 11px;
  color: var(--c-ink-4);
}

.universe-meta .st.completed { color: var(--a-balanced); }
.universe-meta .st.active { color: var(--c-brand); }
.universe-meta .st.aborted { color: var(--c-ink-4); }

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

.archetype-badge.small {
  font-size: 10px;
  padding: 2px 8px;
  white-space: nowrap;
}

.dim-cell {
  font-size: 12px;
  font-weight: 700;
  background: var(--c-bg-softer);
  display: flex;
  align-items: center;
  border-left: 3px solid var(--c-ink-4);
}

.dim-cell.career { border-left-color: var(--a-aggressive); }
.dim-cell.family { border-left-color: var(--a-balanced); }
.dim-cell.resources { border-left-color: var(--a-detour); }
.dim-cell.psyche { border-left-color: var(--a-exit); }
.dim-cell.narrative { border-left-color: var(--c-ink); }
.dim-cell.gain-label {
  border-left-color: #059669;
  color: #059669;
  background: #F0FDF4;
}
.dim-cell.sacrifice-label {
  border-left-color: #DC2626;
  color: #DC2626;
  background: #FEF2F2;
}

.val-cell {
  cursor: pointer;
  transition: background 0.12s;
  color: var(--c-ink-2);
}

.val-cell:hover {
  background: var(--c-brand-tint);
}

.val-cell.gain-cell {
  background: #FAFCF8;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.val-cell.gain-cell:hover {
  background: #ECFDF5;
}

.val-cell.sacrifice-cell {
  background: #FCF9F9;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.val-cell.sacrifice-cell:hover {
  background: #FEF2F2;
}

.gain-badge {
  font-size: 10px;
  font-weight: 700;
  color: #059669;
  width: fit-content;
  padding: 1px 6px;
  background: #DCFCE7;
  border-radius: var(--r-sm);
  border: 1px solid #86EFAC;
}

.sac-badge {
  font-size: 10px;
  font-weight: 700;
  color: #DC2626;
  width: fit-content;
  padding: 1px 6px;
  background: #FEE2E2;
  border-radius: var(--r-sm);
  border: 1px solid #FCA5A5;
}

.highlight-text {
  font-size: 13px;
  font-weight: 600;
  color: var(--c-ink);
  line-height: 1.45;
}

.val-cell.snapshot {
  color: var(--c-ink-3);
  font-size: 12px;
}

/* 偏离汇总 */
.detail-section {
  border-top: 2px solid var(--c-ink);
  padding-top: 16px;
}

.section-title {
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 1px;
  margin-bottom: 14px;
}

.closing-section {
  margin-top: 36px;
  border-top: 2px solid var(--c-ink);
  padding-top: 28px;
  text-align: center;
}

.closing-title {
  font-family: 'Space Grotesk', 'Inter', sans-serif;
  font-size: 24px;
  font-weight: 800;
  letter-spacing: 4px;
  color: var(--c-ink);
}

.closing-motto {
  margin-top: 10px;
  font-size: 14px;
  font-weight: 600;
  letter-spacing: 1px;
  color: var(--c-brand);
}

.closing-text {
  margin: 22px auto 0;
  max-width: 640px;
  font-size: 13.5px;
  line-height: 2.1;
  color: var(--c-ink-2);
  white-space: pre-line;
  text-align: left;
  background: var(--c-bg-softer, #FAF9F6);
  border: 1px dashed var(--c-line-strong);
  border-radius: var(--r-sm);
  padding: 20px 24px;
}

.compare-next-card {
  margin-top: 36px;
  padding: 24px;
  background: var(--c-paper);
  border: 2px solid var(--c-ink);
  border-radius: var(--r-md);
  box-shadow: var(--shadow-pop);
  text-align: left;
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
  font-size: 15px;
  font-weight: 700;
  color: var(--c-ink);
}

.next-card-desc {
  font-size: 13px;
  color: var(--c-ink-3);
  line-height: 1.6;
  margin-bottom: 18px;
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
  padding: 10px 22px;
  border-radius: var(--r-sm);
  cursor: pointer;
  border: 1px solid var(--c-ink);
  background: var(--c-paper);
  color: var(--c-ink);
  transition: all 0.15s;
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

.detail-row {
  display: flex;
  gap: 12px;
  padding: 10px 0;
  border-bottom: 1px dashed var(--c-line-soft);
  align-items: flex-start;
}

.detail-body {
  flex: 1;
  font-size: 13px;
  line-height: 1.8;
}

.div-line { color: var(--a-detour); }
.fork-line { color: var(--c-ink-3); }
.fork-line b { color: var(--a-detour); }
.quiet { color: var(--c-ink-5); }

@media (max-width: 860px) {
  .compare-grid {
    display: block;
  }
  .compare-grid > div {
    border-bottom: 1px solid var(--c-line-soft);
  }
  .next-card-actions {
    flex-direction: column;
  }
}
</style>
