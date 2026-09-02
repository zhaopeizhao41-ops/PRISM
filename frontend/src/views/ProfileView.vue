<template>
  <div class="profile-view">
    <!-- 顶部统一导航 -->
    <AppHeader :project-id="projectId" current-step="profile">
      <template #extra>
        <span v-if="model" class="nav-badge">v{{ model.model_version }}</span>
      </template>
    </AppHeader>

    <div class="main-content">
      <!-- 加载中 -->
      <div v-if="loading" class="state-box">
        <p>{{ t('profile.view.loading') }}</p>
      </div>

      <!-- 加载失败 -->
      <div v-else-if="!model" class="state-box error">
        <p>{{ loadError || t('profile.view.modelNotFound') }}</p>
        <button class="btn-mini" type="button" @click="router.push('/')">{{ t('profile.view.backHome') }}</button>
      </div>

      <template v-else>
        <!-- 卡片1：核心画像 -->
        <section class="profile-card core-card">
          <div class="card-label">{{ t('profile.view.coreTitle') }}</div>
          <p v-if="basicLine" class="core-line basic">{{ basicLine }}</p>
          <p v-if="traitLine" class="core-line trait">{{ traitLine }}</p>
          <p class="current-state">{{ model.current_state || t('common.noData') }}</p>
          <div v-if="sourceTags.length" class="source-tags">
            <span v-for="s in sourceTags" :key="s" class="source-tag">{{ s }}</span>
          </div>
        </section>

        <!-- 卡片2：目标与卡点 -->
        <section class="profile-card goals-card">
          <div class="card-label">{{ t('profile.view.goalsTitle') }}</div>
          <div v-if="!wants.length && !avoids.length" class="empty-goals">
            {{ t('common.noData') }}
          </div>
          <template v-else>
            <div v-if="wants.length" class="goal-group">
              <div class="goal-group-title want">{{ t('profile.view.want') }}</div>
              <p v-for="(a, i) in wants" :key="'w' + i" class="goal-item">✓ {{ a.content }}</p>
            </div>
            <div v-if="avoids.length" class="goal-group">
              <div class="goal-group-title avoid">{{ t('profile.view.avoid') }}</div>
              <p v-for="(a, i) in avoids" :key="'a' + i" class="goal-item">✕ {{ a.content }}</p>
            </div>
          </template>
        </section>

        <!-- 卡片3：折叠详情 -->
        <section class="profile-card details-card">
          <button class="details-toggle" type="button" @click="detailsOpen = !detailsOpen">
            <span class="card-label">{{ t('profile.view.detailsTitle') }}</span>
            <span class="toggle-arrow" :class="{ open: detailsOpen }">▾</span>
          </button>

          <div v-show="detailsOpen" class="details-body">
            <!-- 时间线 -->
            <div v-if="model.timeline?.length" class="detail-section">
              <div class="detail-title">{{ t('profile.view.timeline') }}</div>
              <div class="timeline">
                <div v-for="(item, i) in model.timeline" :key="i" class="timeline-item">
                  <span class="timeline-period">{{ item.period || '—' }}</span>
                  <span class="timeline-kind" :class="{ gap: item.kind === 'gap' }">{{ kindLabel(item.kind) }}</span>
                  <span class="timeline-summary">{{ item.summary }}</span>
                </div>
              </div>
            </div>

            <!-- 技能 -->
            <div v-if="model.skills?.length" class="detail-section">
              <div class="detail-title">{{ t('profile.view.skills') }}</div>
              <div class="chips">
                <span v-for="(s, i) in model.skills" :key="i" class="chip">
                  {{ s.name }}<template v-if="s.proficiency"> · {{ s.proficiency }}</template>
                </span>
              </div>
            </div>

            <!-- 关系人 -->
            <div v-if="model.relationships?.length" class="detail-section">
              <div class="detail-title">{{ t('profile.view.relations') }}</div>
              <div v-for="(r, i) in model.relationships" :key="i" class="relation-row">
                <span class="relation-person">{{ r.person }}</span>
                <span class="relation-meta">{{ r.relation }}<template v-if="r.closeness"> · {{ r.closeness }}</template></span>
                <span v-if="r.influence" class="relation-influence">{{ r.influence }}</span>
              </div>
            </div>

            <!-- 情绪模式 -->
            <div v-if="model.emotional_patterns?.length" class="detail-section">
              <div class="detail-title">{{ t('profile.view.emotional') }}</div>
              <div v-for="(e, i) in model.emotional_patterns" :key="i" class="pattern-row">
                <span class="pattern-trigger">{{ e.trigger || e.pattern_kind }}</span>
                <span v-if="e.evidence" class="pattern-evidence">{{ e.evidence }}</span>
              </div>
            </div>

            <!-- 表达基因 -->
            <div v-if="model.expression_dna?.length" class="detail-section">
              <div class="detail-title">{{ t('profile.view.expression') }}</div>
              <div v-for="(e, i) in model.expression_dna" :key="i" class="pattern-row">
                <span class="pattern-trigger">{{ e.feature }}<template v-if="e.scene"> · {{ e.scene }}</template></span>
                <span v-if="e.example" class="pattern-evidence">{{ e.example }}</span>
              </div>
            </div>

            <!-- 经历剧场 (Character-LLM 经历重构) -->
            <div v-if="model.episodic_anchors?.length" class="detail-section">
              <div class="detail-title">{{ t('profile.view.episodicAnchors') }}</div>
              <div class="episodic-list">
                <div v-for="(anchor, i) in model.episodic_anchors" :key="i" class="episodic-card">
                  <div class="episodic-header">
                    <span class="episodic-scene">{{ anchor.scene }}</span>
                    <span v-if="anchor.involved_persons?.length" class="episodic-persons">
                      {{ Array.isArray(anchor.involved_persons) ? anchor.involved_persons.join('、') : anchor.involved_persons }}
                    </span>
                  </div>
                  <div class="episodic-conflict"><strong>核心冲突：</strong>{{ anchor.core_conflict }}</div>
                  <div v-if="anchor.emotional_imprint" class="episodic-imprint"><strong>情绪印记：</strong>{{ anchor.emotional_imprint }}</div>
                  <div v-if="anchor.cognitive_anchor" class="episodic-cog"><strong>铸就信念：</strong>{{ anchor.cognitive_anchor }}</div>
                </div>
              </div>
            </div>

            <!-- 心理防御机制 (Character-LLM 敏感锚点) -->
            <div v-if="hasDefenseMechanisms" class="detail-section">
              <div class="detail-title">{{ t('profile.view.defenseMechanisms') }}</div>
              <div class="defense-grid">
                <div v-if="model.defense_mechanisms?.pride_anchors?.length" class="defense-block pride">
                  <div class="defense-type-title">▲ {{ t('profile.view.prideTitle') }}</div>
                  <div v-for="(p, i) in model.defense_mechanisms.pride_anchors" :key="'p'+i" class="defense-item">
                    <div class="defense-name">{{ p.anchor }}</div>
                    <div v-if="p.defense_behavior" class="defense-desc">应激反应：{{ p.defense_behavior }}</div>
                    <div v-if="p.evidence" class="defense-evidence">证据：{{ p.evidence }}</div>
                  </div>
                </div>
                <div v-if="model.defense_mechanisms?.trauma_triggers?.length" class="defense-block trauma">
                  <div class="defense-type-title">▼ {{ t('profile.view.traumaTitle') }}</div>
                  <div v-for="(t, i) in model.defense_mechanisms.trauma_triggers" :key="'t'+i" class="defense-item">
                    <div class="defense-name">{{ t.trigger }}</div>
                    <div v-if="t.response_pattern" class="defense-desc">应激模式：{{ t.response_pattern }}</div>
                    <div v-if="t.evidence" class="defense-evidence">证据：{{ t.evidence }}</div>
                  </div>
                </div>
              </div>
            </div>

            <!-- 决策模式 -->
            <div v-if="model.decision_patterns?.length" class="detail-section">
              <div class="detail-title">{{ t('profile.view.decisions') }}</div>
              <div v-for="(d, i) in model.decision_patterns" :key="i" class="pattern-row">
                <span class="pattern-trigger">{{ d.pattern }}<template v-if="d.style"> · {{ d.style }}</template></span>
                <span v-if="d.evidence" class="pattern-evidence">{{ d.evidence }}</span>
              </div>
            </div>

            <!-- 冲突 -->
            <div v-if="model.conflicts?.length" class="detail-section">
              <div class="detail-title">{{ t('profile.view.conflicts') }}</div>
              <div v-for="(c, i) in model.conflicts" :key="i" class="conflict-row">
                <span class="conflict-field">{{ c.field }}</span>
                <span class="conflict-views">{{ (c.views || []).join(' / ') }}</span>
              </div>
            </div>

            <!-- 资料缺口 -->
            <div v-if="model.open_questions?.length" class="detail-section">
              <div class="detail-title">{{ t('profile.view.openQuestions') }}</div>
              <ul class="question-list">
                <li v-for="(q, i) in model.open_questions" :key="i">{{ q }}</li>
              </ul>
            </div>

            <!-- 元信息 -->
            <div class="detail-section meta-section">
              <div class="detail-title">{{ t('profile.view.sourceCoverage') }}</div>
              <div class="coverage-bars">
                <div v-for="(v, k) in model.source_coverage" :key="k" class="coverage-row">
                  <span class="coverage-label">{{ matLabel(k) }}</span>
                  <div class="coverage-track">
                    <div class="coverage-fill" :style="{ width: Math.round(v * 100) + '%' }"></div>
                  </div>
                  <span class="coverage-value">{{ Math.round(v * 100) }}%</span>
                </div>
              </div>
              <p class="meta-line">
                {{ t('profile.view.version') }} v{{ model.model_version }} ·
                {{ model.entity_count }} {{ t('profile.view.entities') }} ·
                {{ formatDate(model.created_at) }}
              </p>
              <p class="disclaimer">{{ t('profile.view.disclaimer') }}</p>
            </div>
          </div>
        </section>

        <!-- 卡片4：关系人 Agent -->
        <section class="profile-card agents-card">
          <div class="card-label">{{ t('relationship.title') }}</div>

          <!-- 已生成的人格卡 -->
          <template v-if="agentCards.length">
            <div v-for="(card, i) in agentCards" :key="i" class="agent-card">
              <div class="agent-head">
                <span class="agent-name">{{ card.person_ref }}</span>
                <span class="agent-relation" :class="card.relation_kind">{{ relLabel(card.relation_kind) }}</span>
                <span v-if="card.thin" class="agent-thin" :title="t('relationship.thinNote')">
                  {{ t('relationship.thin') }}
                </span>
              </div>
              <p class="agent-persona">{{ card.persona }}</p>
              <div v-if="card.core_concern" class="agent-row">
                <span class="agent-field">{{ t('relationship.coreConcern') }}</span>
                <span>{{ card.core_concern }}</span>
              </div>
              <div v-if="card.communication_style" class="agent-row">
                <span class="agent-field">{{ t('relationship.commStyle') }}</span>
                <span>{{ card.communication_style }}</span>
              </div>
              <div v-if="triggerItems(card).length" class="agent-rows">
                <div v-for="(tr, j) in triggerItems(card)" :key="'t' + j" class="agent-row">
                  <span class="agent-field">{{ tr.label }}</span>
                  <span>{{ tr.value }}</span>
                </div>
              </div>
              <div v-if="conflictItems(card).length" class="agent-rows">
                <div v-for="(c, j) in conflictItems(card)" :key="'c' + j" class="agent-row">
                  <span class="agent-field">{{ c.label }}</span>
                  <span>{{ c.value }}</span>
                </div>
              </div>
              <div v-if="card.memory_signature?.length" class="agent-row">
                <span class="agent-field">{{ t('relationship.memory') }}</span>
                <span>{{ card.memory_signature.join('；') }}</span>
              </div>
              <p v-if="isBehaviorThin(card)" class="agent-unlock-hint">
                {{ t('relationship.unlockHint') }}
              </p>
              <div v-if="card.known_positions?.length" class="agent-positions">
                <div v-for="(p, j) in card.known_positions" :key="j" class="agent-position">
                  <span class="pos-topic">{{ p.topic }}</span>
                  <span class="pos-stance">{{ p.stance }}</span>
                </div>
              </div>
              <div v-if="card.defense_axis" class="agent-row">
                <span class="agent-field">防御底线与软肋</span>
                <span>骄傲底线：{{ card.defense_axis.pride_anchor }}<template v-if="card.defense_axis.vulnerability">；心虚软肋：{{ card.defense_axis.vulnerability }}</template></span>
              </div>
              <div v-if="card.episodic_memories?.length" class="agent-row">
                <span class="agent-field">交往经历片段</span>
                <span>{{ card.episodic_memories.map(m => `${m.scene}（${m.impact}）`).join('；') }}</span>
              </div>
              <div v-if="card.blind_spots?.length" class="agent-row">
                <span class="agent-field">{{ t('relationship.blindSpots') }}</span>
                <span>{{ card.blind_spots.join('；') }}</span>
              </div>

              <!-- 纠错回路：我的纠正 -->
              <div v-if="(corrections[card.person_ref] || []).length" class="correction-list">
                <div
                  v-for="(cr, j) in corrections[card.person_ref]"
                  :key="'cr' + j"
                  class="correction-item"
                >
                  <span class="correction-text">
                    {{ correctionText(cr) }}
                  </span>
                  <button
                    class="correction-del"
                    type="button"
                    :title="t('relationship.correction.delete')"
                    @click="removeCorrection(card.person_ref, j)"
                  >×</button>
                </div>
              </div>
              <div v-if="correctingRef === card.person_ref" class="correction-form">
                <input
                  v-model="correctionForm.scene"
                  class="correction-input"
                  :placeholder="t('relationship.correction.scenePh')"
                >
                <input
                  v-model="correctionForm.correct"
                  class="correction-input"
                  :placeholder="t('relationship.correction.correctPh')"
                  @keyup.enter="submitCorrection(card.person_ref)"
                >
                <div class="correction-actions">
                  <button class="correction-submit" type="button" :disabled="correctionBusy" @click="submitCorrection(card.person_ref)">
                    {{ correctionBusy ? t('common.loading') : t('relationship.correction.submit') }}
                  </button>
                  <button class="correction-cancel" type="button" @click="correctingRef = null">
                    {{ t('relationship.correction.cancel') }}
                  </button>
                </div>
              </div>
              <button
                v-else
                class="correction-toggle"
                type="button"
                @click="startCorrection(card.person_ref)"
              >
                ＋ {{ t('relationship.correction.add') }}
              </button>
            </div>
            <button class="agents-redo" type="button" :disabled="agentsBusy" @click="loadCandidates">
              ↻ {{ t('relationship.regenerate') }}
            </button>
          </template>

          <!-- 候选选择（尚未生成或重新生成） -->
          <template v-else-if="showCandidatePanel">
            <div v-if="candidatesLoading" class="agents-empty">{{ t('common.loading') }}</div>
            <template v-else-if="candidates.length">
              <p class="candidates-hint">{{ t('relationship.selectHint') }}</p>
              <label
                v-for="(c, i) in candidates"
                :key="i"
                class="candidate-row"
                :class="{ checked: selectedPersons.has(c.person_name) }"
              >
                <input
                  v-model="selectedSet"
                  :value="c.person_name"
                  type="checkbox"
                  class="candidate-check"
                >
                <span class="candidate-name">{{ c.person_name }}</span>
                <span class="candidate-relation">{{ relLabel(c.relation_kind) }}</span>
                <span class="candidate-facts">{{ t('relationship.factCount', { n: c.fact_count }) }}</span>
                <span v-if="c.influence" class="candidate-influence">{{ c.influence }}</span>
              </label>
              <button
                class="agents-generate-btn"
                type="button"
                :disabled="agentsBusy || !selectedSet.length"
                @click="generateAgents"
              >
                {{ agentsBusy ? genMessage || t('relationship.generating') : t('relationship.generateBtn') }}
              </button>
              <p v-if="agentsError" class="agents-error">{{ agentsError }}</p>
            </template>
            <div v-else class="agents-empty">{{ t('relationship.noCandidates') }}</div>
          </template>

          <!-- 入口按钮 -->
          <button v-else class="agents-entry-btn" type="button" @click="loadCandidates">
            {{ t('relationship.entryBtn') }} →
          </button>
        </section>

        <!-- 底部操作 -->
        <div class="action-bar">
          <button class="branches-btn" type="button" @click="router.push(`/branches/${projectId}`)">
            {{ t('branch.view.entry') }} →
          </button>
          <button class="regenerate-btn" type="button" @click="router.push(`/profile/create?project=${projectId}`)">
            {{ t('profile.view.regenerate') }}
          </button>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import AppHeader from '../components/AppHeader.vue'
import { getPersonalModel } from '../api/profile'
import {
  getRelationshipCandidates,
  generateRelationshipAgents,
  getRelationshipGenerateStatus,
  getRelationshipAgents,
  getRelationshipCorrections,
  addRelationshipCorrection,
  deleteRelationshipCorrection
} from '../api/relationship'

const props = defineProps({
  projectId: { type: String, required: true }
})

const router = useRouter()
const { t, te } = useI18n()

const loading = ref(true)
const loadError = ref('')
const model = ref(null)
const versions = ref([])
const detailsOpen = ref(false)

// ----- 关系人 Agent -----
const agentCards = ref([])
const showCandidatePanel = ref(false)
const candidatesLoading = ref(false)
const candidates = ref([])
const selectedSet = ref([])
const agentsBusy = ref(false)
const agentsError = ref('')
const genMessage = ref('')

const selectedPersons = computed(() => new Set(selectedSet.value))

const hasDefenseMechanisms = computed(() => {
  const d = model.value?.defense_mechanisms
  if (!d) return false
  return ((d.pride_anchors?.length || 0) > 0) || ((d.trauma_triggers?.length || 0) > 0)
})

function relLabel(kind) {
  const i18nKey = `relationship.relation.${kind}`
  return te(i18nKey) ? t(i18nKey) : (kind || '')
}

// 情感触发器 / 冲突模式：过滤空值子字段后转为展示行
function triggerItems(card) {
  const tr = card.emotional_triggers || {}
  return [
    { key: 'opens_up_when', value: tr.opens_up_when },
    { key: 'withdraws_when', value: tr.withdraws_when },
    { key: 'defensive_when', value: tr.defensive_when },
    { key: 'shows_care_when', value: tr.shows_care_when },
  ].filter(item => item.value)
    .map(item => ({ label: t(`relationship.trigger.${item.key}`), value: item.value }))
}

function conflictItems(card) {
  const c = card.conflict_pattern || {}
  return [
    { key: 'style', value: c.style },
    { key: 'silence', value: c.silence },
    { key: 'repair', value: c.repair },
    { key: 'apology_accepted', value: c.apology_accepted },
  ].filter(item => item.value)
    .map(item => ({ label: t(`relationship.conflict.${item.key}`), value: item.value }))
}

// 行为四件套（触发器/冲突模式/共同记忆）是否全部缺失 → 显示补充材料提示
function isBehaviorThin(card) {
  return !triggerItems(card).length
    && !conflictItems(card).length
    && !(card.memory_signature || []).length
}

async function loadExistingCards() {
  try {
    const res = await getRelationshipAgents(props.projectId)
    agentCards.value = res.data?.cards || []
  } catch {
    agentCards.value = []
  }
  loadCorrections()
}

// ----- 纠错回路 -----
const corrections = ref({})
const correctingRef = ref(null)
const correctionForm = ref({ scene: '', correct: '' })
const correctionBusy = ref(false)

async function loadCorrections() {
  try {
    const res = await getRelationshipCorrections(props.projectId)
    corrections.value = res.data?.corrections || {}
  } catch {
    corrections.value = {}
  }
}

function correctionText(cr) {
  const scene = cr.scene ? `（${cr.scene}）` : ''
  return `${t('relationship.correction.tag')}${scene}${cr.correct}`
}

function startCorrection(personRef) {
  correctingRef.value = personRef
  correctionForm.value = { scene: '', correct: '' }
}

async function submitCorrection(personRef) {
  if (!correctionForm.value.correct.trim() || correctionBusy.value) return
  correctionBusy.value = true
  try {
    await addRelationshipCorrection(props.projectId, {
      person_ref: personRef,
      scene: correctionForm.value.scene.trim(),
      wrong: '',
      correct: correctionForm.value.correct.trim(),
    })
    correctingRef.value = null
    await loadCorrections()
  } catch (e) {
    agentsError.value = e?.message || String(e)
  } finally {
    correctionBusy.value = false
  }
}

async function removeCorrection(personRef, index) {
  try {
    await deleteRelationshipCorrection(props.projectId, personRef, index)
    await loadCorrections()
  } catch (e) {
    agentsError.value = e?.message || String(e)
  }
}

async function loadCandidates() {
  showCandidatePanel.value = true
  candidatesLoading.value = true
  agentsError.value = ''
  try {
    const res = await getRelationshipCandidates(props.projectId)
    candidates.value = res.data?.candidates || []
    selectedSet.value = []
  } catch (e) {
    agentsError.value = e?.message || String(e)
    candidates.value = []
  } finally {
    candidatesLoading.value = false
  }
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms))
}

async function generateAgents() {
  if (agentsBusy.value || !selectedSet.value.length) return
  agentsBusy.value = true
  agentsError.value = ''
  genMessage.value = t('relationship.generating')
  try {
    const res = await generateRelationshipAgents({
      project_id: props.projectId,
      person_refs: selectedSet.value
    })
    for (;;) {
      await sleep(3000)
      const statusRes = await getRelationshipGenerateStatus(res.data.task_id)
      const task = statusRes.data
      genMessage.value = task.message || ''
      if (task.status === 'completed') break
      if (task.status === 'failed') {
        throw new Error(task.message || task.error || 'task failed')
      }
    }
    await loadExistingCards()
    showCandidatePanel.value = false
  } catch (e) {
    agentsError.value = e?.message || String(e)
  } finally {
    agentsBusy.value = false
  }
}

const basicLine = computed(() => {
  if (!model.value) return ''
  const b = model.value.basic_info || {}
  return [b.age_range, b.location, b.industry, b.current_status]
    .filter(Boolean)
    .join(' · ')
})

const traitLine = computed(() => {
  if (!model.value) return ''
  const p = model.value.personality || {}
  const parts = []
  if (p.mbti?.value) parts.push(p.mbti.value)
  const traits = [...(p.self_view || []), ...(p.observed || [])]
    .map(x => x.trait)
    .filter(Boolean)
    .slice(0, 4)
  parts.push(...traits)
  return parts.join(' · ')
})

const wants = computed(() =>
  (model.value?.aspirations || []).filter(a => a.polarity === 'want')
)
const avoids = computed(() =>
  (model.value?.aspirations || []).filter(a => a.polarity === 'want_to_avoid')
)

const sourceTags = computed(() => {
  const coverage = model.value?.source_coverage || {}
  return Object.keys(coverage).map(k => `${matLabel(k)} ${Math.round(coverage[k] * 100)}%`)
})

function kindLabel(kind) {
  const key = `profile.view.kind_${kind}`
  return te(key) ? t(key) : (kind || '—')
}

function matLabel(key) {
  const i18nKey = `profile.mat.${key}`
  return te(i18nKey) ? t(i18nKey) : key
}

function formatDate(iso) {
  if (!iso) return ''
  try {
    return new Date(iso).toLocaleString()
  } catch {
    return iso
  }
}

onMounted(async () => {
  try {
    const res = await getPersonalModel(props.projectId)
    model.value = res.data.model
    versions.value = res.data.versions || []
    await loadExistingCards()
  } catch (e) {
    loadError.value = e?.message || String(e)
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.profile-view {
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
  gap: 10px;
  cursor: pointer;
}

.nav-brand .brand-logo {
  height: 28px;
  width: auto;
}

.nav-brand .brand-word {
  font-family: 'Space Grotesk', 'Inter', sans-serif;
  font-weight: 700;
  font-size: 18px;
  letter-spacing: 4px;
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

.nav-badge {
  font-size: 12px;
  padding: 4px 10px;
  background: var(--c-ink);
  color: var(--c-paper);
  border-radius: var(--r-sm);
  font-weight: 700;
}

.main-content {
  max-width: 720px;
  margin: 0 auto;
  padding: 40px 24px 96px;
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

.state-box.error p {
  color: var(--c-brand);
}

/* 画像卡片 */
.profile-card {
  border: 1px solid var(--c-line);
  border-radius: var(--r-md);
  padding: 24px 28px;
  margin-bottom: 20px;
}

.card-label {
  font-size: 12px;
  color: var(--c-brand);
  font-weight: 700;
  letter-spacing: 1px;
  text-transform: uppercase;
  margin-bottom: 14px;
}

/* 核心画像 */
.core-line {
  font-size: 16px;
  font-weight: 600;
  margin-bottom: 8px;
}

.core-line.basic {
  font-size: 20px;
}

.current-state {
  margin-top: 16px;
  padding: 14px 16px;
  background: var(--c-bg-softer);
  border-left: 3px solid var(--c-brand);
  font-size: 14px;
  line-height: 1.8;
  color: var(--c-ink-2);
}

.source-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 14px;
}

.source-tag {
  font-size: 11px;
  color: var(--c-ink-4);
  border: 1px solid var(--c-line-soft);
  padding: 3px 8px;
  border-radius: var(--r-lg);
}

/* 目标与卡点 */
.empty-goals {
  color: var(--c-ink-4);
  font-size: 14px;
}

.goal-group {
  margin-bottom: 14px;
}

.goal-group:last-child {
  margin-bottom: 0;
}

.goal-group-title {
  font-size: 12px;
  font-weight: 700;
  margin-bottom: 8px;
  letter-spacing: 1px;
}

.goal-group-title.want {
  color: var(--c-ink);
}

.goal-group-title.avoid {
  color: var(--c-brand);
}

.goal-item {
  font-size: 15px;
  line-height: 1.8;
}

/* 折叠详情 */
.details-toggle {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  background: none;
  border: none;
  cursor: pointer;
  font-family: inherit;
  padding: 0;
}

.details-toggle .card-label {
  margin-bottom: 0;
}

.toggle-arrow {
  color: var(--c-ink-4);
  transition: transform 0.2s;
  font-size: 14px;
}

.toggle-arrow.open {
  transform: rotate(180deg);
}

.details-body {
  margin-top: 20px;
  border-top: 1px dashed var(--c-line-soft);
  padding-top: 20px;
}

.detail-section {
  margin-bottom: 22px;
}

.detail-section:last-child {
  margin-bottom: 0;
}

.detail-title {
  font-size: 13px;
  font-weight: 700;
  color: var(--c-ink-3);
  margin-bottom: 10px;
}

/* 时间线 */
.timeline {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.timeline-item {
  display: flex;
  gap: 12px;
  align-items: baseline;
  font-size: 14px;
}

.timeline-period {
  min-width: 100px;
  font-weight: 600;
  color: var(--c-ink-2);
}

.timeline-kind {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: var(--r-lg);
  background: #F0F0F0;
  color: var(--c-ink-3);
  white-space: nowrap;
}

.timeline-kind.gap {
  background: var(--c-brand-soft);
  color: var(--c-brand);
}

.timeline-summary {
  color: var(--c-ink-3);
  line-height: 1.6;
}

/* 技能 chips */
.chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.chip {
  font-size: 13px;
  border: 1px solid var(--c-line-strong);
  padding: 5px 12px;
  border-radius: var(--r-lg);
  color: var(--c-ink-2);
}

/* 关系人 */
.relation-row {
  display: flex;
  gap: 12px;
  align-items: baseline;
  font-size: 14px;
  padding: 6px 0;
  border-bottom: 1px solid var(--c-bg-soft);
}

.relation-row:last-child {
  border-bottom: none;
}

.relation-person {
  font-weight: 600;
  min-width: 60px;
}

.relation-meta {
  color: var(--c-ink-4);
  font-size: 12px;
  white-space: nowrap;
}

.relation-influence {
  color: var(--c-ink-3);
  line-height: 1.5;
}

/* 情绪模式 */
.pattern-row {
  font-size: 14px;
  padding: 6px 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.pattern-trigger {
  font-weight: 600;
}

.pattern-evidence {
  color: var(--c-ink-4);
  font-size: 13px;
}

/* 冲突 */
.conflict-row {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 8px 12px;
  border: 1px solid #FFF0EA;
  background: #FFFAF8;
  border-radius: var(--r-sm);
  margin-bottom: 8px;
}

.conflict-field {
  font-size: 12px;
  font-weight: 700;
  color: var(--c-brand);
}

.conflict-views {
  font-size: 13px;
  color: var(--c-ink-3);
}

/* 资料缺口 */
.question-list {
  padding-left: 18px;
  font-size: 14px;
  color: var(--c-ink-3);
  line-height: 1.8;
}

/* 元信息 */
.coverage-bars {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 14px;
}

.coverage-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.coverage-label {
  width: 110px;
  font-size: 12px;
  color: var(--c-ink-3);
}

.coverage-track {
  flex: 1;
  height: 6px;
  background: #F0F0F0;
  border-radius: var(--r-sm);
  overflow: hidden;
}

.coverage-fill {
  height: 100%;
  background: var(--c-ink);
}

.coverage-value {
  width: 36px;
  font-size: 12px;
  color: var(--c-ink-4);
  text-align: right;
}

.meta-line {
  font-size: 12px;
  color: var(--c-ink-4);
  margin-top: 10px;
}

.disclaimer {
  font-size: 11px;
  color: var(--c-ink-5);
  margin-top: 8px;
}

/* 关系人 Agent */
.agents-card {
  /* 继承 profile-card 基础样式 */
}

.agent-card {
  border: 1px solid var(--c-line-soft);
  border-radius: var(--r-md);
  padding: 18px 20px;
  margin-bottom: 14px;
}

/* ----- 纠错回路 ----- */
.correction-list {
  margin-top: 10px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.correction-item {
  display: flex;
  align-items: baseline;
  gap: 8px;
  font-size: 12.5px;
  color: var(--c-ink-soft);
}

.correction-text::before {
  content: "✎ ";
  color: var(--c-brand);
}

.correction-del {
  border: none;
  background: none;
  color: var(--c-ink-faint);
  cursor: pointer;
  font-size: 14px;
  padding: 0 2px;
  line-height: 1;
}

.correction-del:hover {
  color: var(--c-danger, #c0392b);
}

.correction-form {
  margin-top: 10px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.correction-input {
  width: 100%;
  border: 1px solid var(--c-line-soft);
  border-radius: var(--r-sm);
  padding: 7px 10px;
  font-size: 12.5px;
  font-family: inherit;
  background: var(--c-bg, transparent);
  color: inherit;
  box-sizing: border-box;
}

.correction-input:focus {
  outline: none;
  border-color: var(--c-brand);
}

.correction-actions {
  display: flex;
  gap: 10px;
}

.correction-submit {
  border: none;
  background: var(--c-brand);
  color: #fff;
  border-radius: var(--r-sm);
  padding: 6px 14px;
  font-size: 12.5px;
  cursor: pointer;
  font-family: inherit;
}

.correction-submit:disabled {
  opacity: 0.6;
  cursor: default;
}

.correction-cancel {
  border: none;
  background: none;
  color: var(--c-ink-faint);
  padding: 6px 4px;
  font-size: 12.5px;
  cursor: pointer;
  font-family: inherit;
}

.correction-toggle {
  margin-top: 10px;
  border: none;
  background: none;
  color: var(--c-brand);
  font-size: 12.5px;
  cursor: pointer;
  font-family: inherit;
  padding: 2px 0;
}

.correction-toggle:hover {
  text-decoration: underline;
}

.agent-head {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
  flex-wrap: wrap;
}

.agent-name {
  font-size: 16px;
  font-weight: 700;
}

.agent-relation {
  font-size: 11px;
  padding: 2px 9px;
  border-radius: var(--r-sm);
  color: var(--c-paper);
  background: var(--a-conservative);
  white-space: nowrap;
}

.agent-relation.family { background: var(--a-aggressive); }
.agent-relation.friend { background: var(--a-balanced); }
.agent-relation.colleague { background: #2C3E50; }

.agent-thin {
  font-size: 11px;
  color: var(--a-detour);
  border: 1px solid #E5D9A8;
  padding: 1px 8px;
  border-radius: var(--r-lg);
}

.agent-unlock-hint {
  font-size: 12px;
  line-height: 1.6;
  color: var(--c-ink-3, #9A8F7A);
  border-left: 2px solid #E5D9A8;
  padding: 2px 0 2px 10px;
  margin: 8px 0 2px;
}

.agent-persona {
  font-size: 14px;
  line-height: 1.7;
  color: var(--c-ink-2);
  margin-bottom: 10px;
}

.agent-row {
  display: flex;
  gap: 10px;
  font-size: 13px;
  padding: 6px 0;
  border-top: 1px dashed var(--c-bg-soft);
  line-height: 1.6;
}

.agent-field {
  min-width: 72px;
  font-weight: 700;
  color: var(--c-ink-4);
  white-space: nowrap;
}

.agent-positions {
  border-top: 1px dashed var(--c-bg-soft);
  padding-top: 8px;
}

.agent-position {
  display: flex;
  gap: 10px;
  font-size: 13px;
  padding: 4px 0;
}

.pos-topic {
  font-weight: 600;
  min-width: 72px;
}

.pos-stance {
  color: var(--c-ink-3);
}

.agents-redo {
  border: none;
  background: none;
  color: var(--c-brand);
  font-size: 13px;
  cursor: pointer;
  font-family: inherit;
  padding: 4px 0;
}

.agents-redo:hover {
  text-decoration: underline;
}

.agents-entry-btn {
  width: 100%;
  background: var(--c-paper);
  color: var(--c-ink);
  border: 1px solid var(--c-ink);
  padding: 10px 24px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  border-radius: var(--r-sm);
  font-family: inherit;
  transition: all 0.15s;
}

.agents-entry-btn:hover {
  background: var(--c-ink);
  color: var(--c-paper);
}

.candidates-hint {
  font-size: 13px;
  color: var(--c-ink-3);
  margin-bottom: 12px;
  line-height: 1.6;
}

.candidate-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  border: 1px solid var(--c-line-soft);
  border-radius: var(--r-sm);
  margin-bottom: 8px;
  cursor: pointer;
  font-size: 14px;
  transition: all 0.15s;
}

.candidate-row:hover {
  border-color: var(--c-ink-4);
}

.candidate-row.checked {
  border-color: var(--c-brand);
  background: var(--c-brand-tint);
}

.candidate-check {
  accent-color: var(--c-brand);
}

.candidate-name {
  font-weight: 700;
  min-width: 60px;
}

.candidate-relation {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: var(--r-sm);
  background: #F0F0F0;
  color: var(--c-ink-3);
  white-space: nowrap;
}

.candidate-facts {
  font-size: 12px;
  color: var(--c-ink-4);
  white-space: nowrap;
}

.candidate-influence {
  flex: 1;
  font-size: 12px;
  color: var(--c-ink-3);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.agents-generate-btn {
  width: 100%;
  background: var(--c-brand);
  color: var(--c-paper);
  border: 1px solid var(--c-brand);
  padding: 11px 24px;
  font-size: 14px;
  font-weight: 700;
  cursor: pointer;
  border-radius: var(--r-sm);
  font-family: inherit;
  margin-top: 6px;
  transition: all var(--dur-fast);
}

.agents-generate-btn:hover:not(:disabled) {
  background: var(--c-brand-deep);
  border-color: var(--c-brand-deep);
  box-shadow: var(--shadow-pop-sm);
  transform: translate(-1px, -1px);
}

.agents-generate-btn:active:not(:disabled) {
  transform: translate(1px, 1px);
  box-shadow: 1px 1px 0 var(--c-ink);
}

.agents-generate-btn:disabled {
  background: var(--c-bg-soft);
  border-color: var(--c-line);
  color: var(--c-ink-5);
  cursor: not-allowed;
  transform: none;
  box-shadow: none;
}

.agents-error {
  color: var(--c-brand);
  font-size: 13px;
  margin-top: 10px;
}

.agents-empty {
  color: var(--c-ink-4);
  font-size: 14px;
  padding: 16px 0;
  text-align: center;
}

/* 底部操作 */
.action-bar {
  display: flex;
  justify-content: center;
  gap: 14px;
  position: sticky;
  bottom: 0;
  background: var(--c-paper);
  padding: 16px 24px;
  border-top: 1px solid var(--c-line-strong);
  margin-top: 36px;
  z-index: 20;
}

.branches-btn {
  background: var(--c-brand);
  color: var(--c-paper);
  border: 1px solid var(--c-brand);
  padding: 11px 32px;
  font-size: 14px;
  font-weight: 700;
  cursor: pointer;
  border-radius: var(--r-sm);
  font-family: inherit;
  transition: all var(--dur-fast);
}

.branches-btn:hover {
  background: var(--c-brand-deep);
  border-color: var(--c-brand-deep);
  box-shadow: var(--shadow-pop-sm);
  transform: translate(-1px, -1px);
}

.branches-btn:active {
  transform: translate(1px, 1px);
  box-shadow: 1px 1px 0 var(--c-ink);
}

.regenerate-btn {
  background: var(--c-paper);
  color: var(--c-ink-2);
  border: 1px solid var(--c-line-strong);
  padding: 11px 32px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  border-radius: var(--r-sm);
  font-family: inherit;
  transition: all var(--dur-fast);
}

.regenerate-btn:hover {
  border-color: var(--c-ink);
  color: var(--c-ink);
  box-shadow: var(--shadow-pop-sm);
  transform: translate(-1px, -1px);
}

.regenerate-btn:active {
  background: var(--c-ink);
  color: var(--c-paper);
  border-color: var(--c-ink);
  transform: translate(0, 0);
  box-shadow: none;
}

.btn-mini {
  border: 1px solid var(--c-line-strong);
  background: var(--c-paper);
  color: var(--c-ink-2);
  padding: 6px 14px;
  font-size: 13px;
  cursor: pointer;
  font-family: inherit;
  border-radius: var(--r-sm);
  transition: all var(--dur-fast);
}

.btn-mini:hover {
  border-color: var(--c-ink);
  color: var(--c-ink);
  box-shadow: var(--shadow-pop-sm);
  transform: translate(-1px, -1px);
}

.btn-mini:active {
  background: var(--c-ink);
  color: var(--c-paper);
}

@media (max-width: 640px) {
  .timeline-item {
    flex-direction: column;
    gap: 4px;
  }
}

/* Character-LLM 经历剧场与心理防御样式 */
.episodic-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-top: 8px;
}
.episodic-card {
  border: 1px solid var(--border, #000);
  background: var(--bg-card, #f8f6f0);
  padding: 12px 14px;
  font-size: 13px;
  line-height: 1.6;
  box-shadow: 2px 2px 0 var(--border, #000);
}
.episodic-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
  padding-bottom: 4px;
  border-bottom: 1px dashed var(--border, #ccc);
}
.episodic-scene {
  font-weight: 700;
  color: var(--text-main, #111);
}
.episodic-persons {
  font-size: 12px;
  background: var(--bg-muted, #eee);
  padding: 1px 6px;
  border: 1px solid var(--border, #999);
}
.episodic-conflict, .episodic-imprint, .episodic-cog {
  margin-top: 4px;
  color: var(--text-muted, #333);
}

.defense-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 12px;
  margin-top: 8px;
}
.defense-block {
  border: 1px solid var(--border, #000);
  padding: 12px;
  box-shadow: 2px 2px 0 var(--border, #000);
}
.defense-block.pride {
  background: rgba(43, 90, 138, 0.04);
  border-left: 4px solid #2b5a8a;
}
.defense-block.trauma {
  background: rgba(184, 51, 42, 0.04);
  border-left: 4px solid #b8332a;
}
.defense-type-title {
  font-weight: 700;
  font-size: 13px;
  margin-bottom: 8px;
  color: var(--text-main, #000);
}
.defense-item {
  margin-bottom: 8px;
  padding-bottom: 6px;
  border-bottom: 1px dotted var(--border, #ddd);
}
.defense-item:last-child {
  margin-bottom: 0;
  padding-bottom: 0;
  border-bottom: none;
}
.defense-name {
  font-weight: 600;
  font-size: 13px;
  color: var(--text-main, #111);
}
.defense-desc {
  font-size: 12px;
  color: var(--text-muted, #444);
  margin-top: 2px;
}
.defense-evidence {
  font-size: 11px;
  color: #777;
  margin-top: 2px;
}
</style>
