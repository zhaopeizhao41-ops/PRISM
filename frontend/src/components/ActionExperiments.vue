<template>
  <section id="action-experiments" class="action-section" aria-labelledby="action-title">
    <header class="action-header">
      <div>
        <div class="action-kicker">{{ t('workbench.actions.kicker') }}</div>
        <h2 id="action-title">{{ t('workbench.actions.title') }}</h2>
        <p>{{ t('workbench.actions.subtitle') }}</p>
      </div>
      <span v-if="experiments.length" class="action-count">
        {{ t('workbench.actions.count', { n: experiments.length }) }}
      </span>
    </header>

    <div class="action-layout">
      <form class="action-form" @submit.prevent="submitExperiment">
        <div class="form-title">{{ t('workbench.actions.newTitle') }}</div>
        <label>
          <span>{{ t('workbench.actions.titleLabel') }}</span>
          <input v-model.trim="form.title" type="text" maxlength="120" required :placeholder="t('workbench.actions.titlePlaceholder')">
        </label>

        <div class="form-row">
          <label>
            <span>{{ t('workbench.actions.horizonLabel') }}</span>
            <select v-model.number="form.horizon_days">
              <option v-for="days in horizons" :key="days" :value="days">
                {{ t('workbench.actions.horizon', { n: days }) }}
              </option>
            </select>
          </label>
          <label>
            <span>{{ t('workbench.actions.reviewLabel') }}</span>
            <input v-model="form.review_date" type="date" required>
          </label>
        </div>

        <label>
          <span>{{ t('workbench.actions.goalLabel') }}</span>
          <textarea v-model.trim="form.goal" rows="2" maxlength="600" required :placeholder="t('workbench.actions.goalPlaceholder')"></textarea>
        </label>
        <label>
          <span>{{ t('workbench.actions.minimumLabel') }}</span>
          <textarea v-model.trim="form.minimum_action" rows="2" maxlength="600" required :placeholder="t('workbench.actions.minimumPlaceholder')"></textarea>
        </label>
        <label>
          <span>{{ t('workbench.actions.metricLabel') }}</span>
          <textarea v-model.trim="form.success_metric" rows="2" maxlength="400" required :placeholder="t('workbench.actions.metricPlaceholder')"></textarea>
        </label>

        <div class="form-row">
          <label>
            <span>{{ t('workbench.actions.stopLabel') }}</span>
            <input v-model.trim="form.stop_condition" type="text" maxlength="400">
          </label>
          <label>
            <span>{{ t('workbench.actions.costLabel') }}</span>
            <input v-model.trim="form.expected_cost" type="text" maxlength="400">
          </label>
        </div>

        <label>
          <span>{{ t('workbench.actions.sourceLabel') }}</span>
          <select v-model="form.source_session_id">
            <option value="">{{ t('workbench.actions.sourceNone') }}</option>
            <option v-for="session in sessions" :key="session.session_id" :value="session.session_id">
              {{ sessionLabel(session) }}
            </option>
          </select>
        </label>

        <p v-if="error" class="action-error" role="alert">{{ error }}</p>
        <button class="action-submit" type="submit" :disabled="saving">
          {{ saving ? t('workbench.actions.saving') : t('workbench.actions.create') }}
        </button>
      </form>

      <div class="action-list">
        <div v-if="loading" class="action-empty">{{ t('workbench.actions.loading') }}</div>
        <div v-else-if="!experiments.length" class="action-empty">
          <strong>{{ t('workbench.actions.emptyTitle') }}</strong>
          <span>{{ t('workbench.actions.emptyDescription') }}</span>
        </div>

        <article v-for="experiment in experiments" :key="experiment.experiment_id" class="action-item">
          <div class="action-item-head">
            <div>
              <h3>{{ experiment.title }}</h3>
              <div class="action-meta">
                <span>{{ t('workbench.actions.horizon', { n: experiment.horizon_days }) }}</span>
                <span>{{ t('workbench.actions.reviewOn', { date: experiment.review_date }) }}</span>
              </div>
            </div>
            <span class="action-status" :class="`status-${experiment.status}`">
              {{ statusLabel(experiment.status) }}
            </span>
          </div>

          <dl class="action-fields">
            <div><dt>{{ t('workbench.actions.goalLabel') }}</dt><dd>{{ experiment.goal }}</dd></div>
            <div><dt>{{ t('workbench.actions.minimumLabel') }}</dt><dd>{{ experiment.minimum_action }}</dd></div>
            <div><dt>{{ t('workbench.actions.metricLabel') }}</dt><dd>{{ experiment.success_metric }}</dd></div>
            <div v-if="experiment.stop_condition"><dt>{{ t('workbench.actions.stopLabel') }}</dt><dd>{{ experiment.stop_condition }}</dd></div>
            <div v-if="experiment.expected_cost"><dt>{{ t('workbench.actions.costLabel') }}</dt><dd>{{ experiment.expected_cost }}</dd></div>
          </dl>

          <div v-if="experiment.source_summary" class="action-source">
            <span>{{ t('workbench.actions.sourceSummary') }}</span>{{ experiment.source_summary }}
          </div>

          <div class="action-controls">
            <button v-if="experiment.status === 'planned'" type="button" @click="changeStatus(experiment, 'in_progress')">
              {{ t('workbench.actions.start') }}
            </button>
            <button v-if="experiment.status === 'in_progress'" type="button" @click="changeStatus(experiment, 'paused')">
              {{ t('workbench.actions.pause') }}
            </button>
            <button v-if="['in_progress', 'paused'].includes(experiment.status)" type="button" @click="changeStatus(experiment, 'completed')">
              {{ t('workbench.actions.complete') }}
            </button>
            <button v-if="['planned', 'in_progress', 'paused'].includes(experiment.status)" type="button" class="muted" @click="changeStatus(experiment, 'cancelled')">
              {{ t('workbench.actions.cancel') }}
            </button>
            <button v-if="experiment.status !== 'cancelled'" type="button" class="muted" @click="openRetrospective(experiment)">
              {{ experiment.retrospective ? t('workbench.actions.editRetrospective') : t('workbench.actions.retrospective') }}
            </button>
            <button type="button" class="danger" @click="removeExperiment(experiment)">
              {{ t('workbench.actions.delete') }}
            </button>
          </div>

          <div v-if="retrospectiveId === experiment.experiment_id" class="retrospective-panel">
            <div class="form-title">{{ t('workbench.actions.retroTitle') }}</div>
            <div class="form-row">
              <label>
                <span>{{ t('workbench.actions.outcomeLabel') }}</span>
                <select v-model="retroForm.outcome">
                  <option v-for="outcome in outcomes" :key="outcome" :value="outcome">{{ outcomeLabel(outcome) }}</option>
                </select>
              </label>
              <label>
                <span>{{ t('workbench.actions.varianceLabel') }}</span>
                <select v-model="retroForm.variance_type">
                  <option v-for="variance in varianceTypes" :key="variance" :value="variance">{{ varianceLabel(variance) }}</option>
                </select>
              </label>
            </div>
            <label>
              <span>{{ t('workbench.actions.observedLabel') }}</span>
              <textarea v-model.trim="retroForm.observed_result" rows="3" maxlength="1200" required :placeholder="t('workbench.actions.observedPlaceholder')"></textarea>
            </label>
            <label>
              <span>{{ t('workbench.actions.notesLabel') }}</span>
              <textarea v-model.trim="retroForm.notes" rows="2" maxlength="1200"></textarea>
            </label>
            <label class="consent-check">
              <input v-model="retroForm.model_update_consent" type="checkbox">
              <span>{{ t('workbench.actions.consentLabel') }}</span>
            </label>
            <p class="consent-note">{{ t('workbench.actions.consentNote') }}</p>
            <p v-if="retroError" class="action-error" role="alert">{{ retroError }}</p>
            <div class="retro-actions">
              <button type="button" class="action-submit" :disabled="retroSaving" @click="submitRetrospective(experiment)">
                {{ retroSaving ? t('workbench.actions.saving') : t('workbench.actions.saveRetro') }}
              </button>
              <button type="button" class="muted-btn" @click="retrospectiveId = ''">{{ t('common.cancel') }}</button>
            </div>
          </div>
        </article>
      </div>
    </div>
  </section>
</template>

<script setup>
import { onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  createActionExperiment,
  deleteActionExperiment,
  listActionExperiments,
  saveActionRetrospective,
  updateActionExperiment,
} from '../api/action'

const props = defineProps({
  projectId: { type: String, required: true },
  sessions: { type: Array, default: () => [] },
})

const emit = defineEmits(['count-change'])

const { t } = useI18n()
const horizons = [7, 30, 90]
const outcomes = ['not_started', 'met', 'partial', 'missed']
const varianceTypes = ['not_assessed', 'model_error', 'missing_data', 'external_change', 'execution_deviation']
const experiments = ref([])
const loading = ref(false)
const saving = ref(false)
const error = ref('')
const retrospectiveId = ref('')
const retroSaving = ref(false)
const retroError = ref('')

function dateAfter(days) {
  const target = new Date()
  target.setDate(target.getDate() + days)
  return target.toISOString().slice(0, 10)
}

function emptyForm() {
  return {
    title: '',
    horizon_days: 30,
    goal: '',
    minimum_action: '',
    success_metric: '',
    stop_condition: '',
    expected_cost: '',
    review_date: dateAfter(30),
    source_session_id: '',
  }
}

const form = ref(emptyForm())
const retroForm = ref({
  outcome: 'partial',
  variance_type: 'not_assessed',
  observed_result: '',
  notes: '',
  model_update_consent: false,
})

function sessionLabel(session) {
  return `${session.source_branch_archetype || ''} · ${session.stages_done || 0}/${session.stage_count || 0}`
}

function statusLabel(status) {
  return t(`workbench.actions.status.${status}`)
}

function outcomeLabel(outcome) {
  return t(`workbench.actions.outcome.${outcome}`)
}

function varianceLabel(variance) {
  return t(`workbench.actions.variance.${variance}`)
}

async function loadExperiments() {
  loading.value = true
  error.value = ''
  try {
    const response = await listActionExperiments(props.projectId)
    experiments.value = response.data || []
    emit('count-change', experiments.value.length)
  } catch (cause) {
    error.value = cause?.message || String(cause)
  } finally {
    loading.value = false
  }
}

async function submitExperiment() {
  if (saving.value) return
  saving.value = true
  error.value = ''
  try {
    const response = await createActionExperiment({
      project_id: props.projectId,
      ...form.value,
      source_session_id: form.value.source_session_id || undefined,
    })
    experiments.value = [response.data, ...experiments.value]
    emit('count-change', experiments.value.length)
    form.value = emptyForm()
  } catch (cause) {
    error.value = cause?.message || String(cause)
  } finally {
    saving.value = false
  }
}

async function changeStatus(experiment, status) {
  try {
    const response = await updateActionExperiment(experiment.experiment_id, {
      project_id: props.projectId,
      status,
    })
    Object.assign(experiment, response.data)
  } catch (cause) {
    error.value = cause?.message || String(cause)
  }
}

function openRetrospective(experiment) {
  retrospectiveId.value = experiment.experiment_id
  retroError.value = ''
  retroForm.value = {
    outcome: experiment.retrospective?.outcome || 'partial',
    variance_type: experiment.retrospective?.variance_type || 'not_assessed',
    observed_result: experiment.retrospective?.observed_result || '',
    notes: experiment.retrospective?.notes || '',
    model_update_consent: Boolean(experiment.retrospective?.model_update_consent),
  }
}

async function submitRetrospective(experiment) {
  if (retroSaving.value) return
  retroSaving.value = true
  retroError.value = ''
  try {
    const response = await saveActionRetrospective(experiment.experiment_id, {
      project_id: props.projectId,
      ...retroForm.value,
    })
    Object.assign(experiment, response.data)
    retrospectiveId.value = ''
  } catch (cause) {
    retroError.value = cause?.message || String(cause)
  } finally {
    retroSaving.value = false
  }
}

async function removeExperiment(experiment) {
  if (!window.confirm(t('workbench.actions.deleteConfirm'))) return
  try {
    await deleteActionExperiment(experiment.experiment_id, props.projectId)
    experiments.value = experiments.value.filter(item => item.experiment_id !== experiment.experiment_id)
    emit('count-change', experiments.value.length)
    if (retrospectiveId.value === experiment.experiment_id) retrospectiveId.value = ''
  } catch (cause) {
    error.value = cause?.message || String(cause)
  }
}

watch(() => props.projectId, loadExperiments)
onMounted(loadExperiments)
</script>

<style scoped>
.action-section {
  margin-top: 32px;
  border-top: 2px solid var(--c-ink);
  padding-top: 22px;
}

.action-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 18px;
  margin-bottom: 18px;
}

.action-kicker {
  color: var(--c-brand);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 1.4px;
  text-transform: uppercase;
}

.action-header h2 {
  margin-top: 4px;
  font-size: 20px;
}

.action-header p {
  margin-top: 6px;
  color: var(--c-ink-3);
  font-size: 12px;
  line-height: 1.55;
}

.action-count {
  flex: 0 0 auto;
  color: var(--c-ink-3);
  font-size: 12px;
}

.action-layout {
  display: grid;
  grid-template-columns: minmax(260px, 0.85fr) minmax(0, 1.4fr);
  gap: 18px;
  align-items: start;
}

.action-form,
.action-item {
  border: 1px solid var(--c-line-strong);
  background: var(--c-paper);
}

.action-form {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 16px;
}

.form-title {
  color: var(--c-ink-2);
  font-size: 13px;
  font-weight: 700;
}

.action-form label,
.retrospective-panel label {
  display: flex;
  flex-direction: column;
  gap: 5px;
  min-width: 0;
}

.action-form label > span,
.retrospective-panel label > span {
  color: var(--c-ink-3);
  font-size: 11px;
  font-weight: 600;
}

.action-form input,
.action-form textarea,
.action-form select,
.retrospective-panel input,
.retrospective-panel textarea,
.retrospective-panel select {
  width: 100%;
  border: 1px solid var(--c-line-strong);
  border-radius: var(--r-sm);
  background: var(--c-paper);
  color: var(--c-ink);
  padding: 8px 9px;
  font: inherit;
  font-size: 12px;
}

.action-form textarea,
.retrospective-panel textarea {
  resize: vertical;
  line-height: 1.5;
}

.action-form input:focus,
.action-form textarea:focus,
.action-form select:focus,
.retrospective-panel input:focus,
.retrospective-panel textarea:focus,
.retrospective-panel select:focus {
  outline: 2px solid var(--c-brand-line);
  outline-offset: 1px;
}

.form-row {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.action-submit {
  align-self: flex-start;
  border: 1px solid var(--c-brand);
  background: var(--c-brand);
  color: var(--c-paper);
  padding: 8px 14px;
  border-radius: var(--r-sm);
  font: inherit;
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
}

.action-submit:disabled {
  cursor: wait;
  opacity: 0.55;
}

.action-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.action-empty {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 30px 18px;
  border: 1px dashed var(--c-line-strong);
  color: var(--c-ink-4);
  font-size: 12px;
  line-height: 1.55;
  text-align: center;
}

.action-empty strong {
  color: var(--c-ink-2);
}

.action-item {
  padding: 16px;
}

.action-item-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
}

.action-item h3 {
  font-size: 15px;
  line-height: 1.35;
}

.action-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 5px;
  color: var(--c-ink-4);
  font-size: 11px;
}

.action-status {
  flex: 0 0 auto;
  padding: 3px 7px;
  border: 1px solid var(--c-line-strong);
  color: var(--c-ink-3);
  font-size: 10px;
  font-weight: 700;
}

.action-status.status-in_progress { color: var(--c-brand); border-color: var(--c-brand-line); }
.action-status.status-completed { color: var(--a-balanced); border-color: var(--a-balanced); }
.action-status.status-cancelled { color: var(--c-ink-4); }

.action-fields {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px 14px;
  margin: 15px 0 0;
}

.action-fields > div {
  min-width: 0;
}

.action-fields dt {
  color: var(--c-ink-4);
  font-size: 10px;
  font-weight: 700;
}

.action-fields dd {
  margin-top: 3px;
  color: var(--c-ink-2);
  font-size: 12px;
  line-height: 1.55;
  overflow-wrap: anywhere;
}

.action-source {
  margin-top: 12px;
  padding: 8px 10px;
  border-left: 3px solid var(--c-line-strong);
  background: var(--c-bg-softer);
  color: var(--c-ink-3);
  font-size: 11px;
  line-height: 1.55;
}

.action-source span {
  margin-right: 5px;
  color: var(--c-ink-4);
  font-weight: 700;
}

.action-controls,
.retro-actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 14px;
  padding-top: 12px;
  border-top: 1px dashed var(--c-line-soft);
}

.action-controls button,
.muted-btn {
  border: 1px solid var(--c-line-strong);
  background: var(--c-paper);
  color: var(--c-ink-2);
  padding: 5px 9px;
  border-radius: var(--r-sm);
  font: inherit;
  font-size: 11px;
  cursor: pointer;
}

.action-controls button:hover,
.muted-btn:hover {
  border-color: var(--c-brand);
  color: var(--c-brand);
}

.action-controls .muted,
.muted-btn {
  color: var(--c-ink-4);
}

.action-controls .danger {
  margin-left: auto;
  color: var(--a-aggressive);
}

.retrospective-panel {
  margin-top: 14px;
  padding: 14px;
  border-left: 3px solid var(--c-brand);
  background: var(--c-bg-softer);
}

.retrospective-panel .form-title {
  margin-bottom: 12px;
}

.retrospective-panel > label,
.retrospective-panel > .form-row {
  margin-top: 11px;
}

.consent-check {
  flex-direction: row !important;
  align-items: flex-start;
  gap: 8px !important;
}

.consent-check input {
  width: auto;
  margin-top: 2px;
}

.consent-note {
  margin-top: 8px;
  color: var(--c-ink-4);
  font-size: 10px;
  line-height: 1.5;
}

.action-error {
  color: var(--a-aggressive);
  font-size: 11px;
  line-height: 1.45;
}

@media (max-width: 820px) {
  .action-layout {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 540px) {
  .action-header,
  .action-item-head {
    flex-direction: column;
  }

  .form-row,
  .action-fields {
    grid-template-columns: 1fr;
  }

  .action-controls .danger {
    margin-left: 0;
  }
}
</style>
