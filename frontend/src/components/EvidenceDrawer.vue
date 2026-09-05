<template>
  <Teleport to="body">
    <div
      v-if="open"
      class="evidence-backdrop"
      role="presentation"
      @click.self="close"
    >
      <aside
        ref="drawer"
        class="evidence-drawer"
        role="dialog"
        aria-modal="true"
        :aria-labelledby="titleId"
      >
        <header class="evidence-header">
          <div>
            <div class="evidence-kicker">{{ t('evidence.kicker') }}</div>
            <h2 :id="titleId" class="evidence-title">{{ title }}</h2>
          </div>
          <button
            ref="closeButton"
            class="evidence-close"
            type="button"
            :aria-label="t('evidence.close')"
            @click="close"
          >
            ×
          </button>
        </header>

        <div class="evidence-body">
          <div class="evidence-summary" :class="{ warning: warnings.length }">
            <span class="evidence-summary-mark" aria-hidden="true">{{ warnings.length ? '!' : '✓' }}</span>
            <span>{{ summaryText }}</span>
          </div>

          <div v-if="loading" class="evidence-state">{{ t('evidence.loading') }}</div>
          <div v-else-if="!items.length" class="evidence-state">
            <strong>{{ t('evidence.noVerifiedTitle') }}</strong>
            <span>{{ t('evidence.noVerifiedDescription') }}</span>
          </div>

          <div v-else class="evidence-list">
            <article v-for="item in items" :key="item.id" class="evidence-item" :class="{ unverified: !item.verified }">
              <div class="evidence-item-head">
                <span class="evidence-source">{{ sourceLabel(item.source) }}</span>
                <span class="evidence-field">{{ item.label }}</span>
                <span class="evidence-traceability" :class="{ unverified: !item.verified }">
                  {{ item.verified ? t('evidence.verified') : t('evidence.unverified') }}
                </span>
              </div>
              <p v-if="item.claim" class="evidence-claim">{{ item.claim }}</p>

              <p v-if="!item.verified" class="evidence-inference-note">
                {{ t('evidence.inferenceDescription') }}
              </p>

              <div v-for="(evidenceRef, index) in item.refs" :key="`${item.id}-${index}`" class="evidence-reference">
                <div class="evidence-reference-meta">
                  <span>{{ materialLabel(evidenceRef) }}</span>
                  <span v-if="evidenceRef.chunk_id">{{ evidenceRef.chunk_id }}</span>
                </div>
                <blockquote v-if="referenceText(evidenceRef)" class="evidence-quote">
                  <template v-for="(segment, segmentIndex) in referenceSegments(evidenceRef)" :key="segmentIndex">
                    <mark v-if="segment.highlight">{{ segment.text }}</mark>
                    <template v-else>{{ segment.text }}</template>
                  </template>
                </blockquote>
                <p v-else class="evidence-missing">{{ t('evidence.referenceUnavailable') }}</p>
              </div>
            </article>
          </div>

          <div v-if="warnings.length" class="evidence-warning">
            <div class="evidence-warning-title">{{ t('evidence.warningTitle') }}</div>
            <div class="evidence-warning-copy">
              {{ t('evidence.warningDescription', { n: warnings.length }) }}
            </div>
          </div>
        </div>
      </aside>
    </div>
  </Teleport>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

const props = defineProps({
  open: { type: Boolean, default: false },
  title: { type: String, default: '' },
  items: { type: Array, default: () => [] },
  materials: { type: Array, default: () => [] },
  warnings: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
})

const emit = defineEmits(['close'])
const { t } = useI18n()
const drawer = ref(null)
const closeButton = ref(null)
const titleId = `evidence-title-${Math.random().toString(36).slice(2)}`

const verifiedCount = computed(() => props.items.reduce((count, item) => count + (item.refs?.length || 0), 0))
const unverifiedCount = computed(() => props.items.filter(item => !item.verified).length)
const summaryText = computed(() => props.warnings.length
  ? t('evidence.summaryWithWarnings', {
    verified: verifiedCount.value,
    unverified: unverifiedCount.value,
    warnings: props.warnings.length,
  })
  : t('evidence.summary', { verified: verifiedCount.value, unverified: unverifiedCount.value }))

function close() {
  emit('close')
}

function onKeydown(event) {
  if (event.key === 'Escape') close()
}

function sourceLabel(source) {
  if (!source || source === 'inference') return t('evidence.inference')
  const key = `profile.mat.${source}`
  return t(key) === key ? source : t(key)
}

function materialFor(evidenceRef) {
  return props.materials.find(material => material?.material_id === evidenceRef?.material_id)
}

function materialLabel(evidenceRef) {
  const material = materialFor(evidenceRef)
  if (material?.filename) return material.filename
  if (material?.material_type) return sourceLabel(material.material_type)
  return evidenceRef?.material_id || t('evidence.unknownSource')
}

function chunkFor(evidenceRef) {
  const material = materialFor(evidenceRef)
  return material?.chunks?.find(chunk => chunk?.chunk_id === evidenceRef?.chunk_id)
}

function referenceText(evidenceRef) {
  return String(chunkFor(evidenceRef)?.text || '')
}

function referenceSegments(evidenceRef) {
  const text = referenceText(evidenceRef)
  if (!text) return []
  const span = evidenceRef?.span || {}
  const start = Number.isInteger(span.start) ? Math.max(0, Math.min(text.length, span.start)) : -1
  const end = Number.isInteger(span.end) ? Math.max(start, Math.min(text.length, span.end)) : -1
  if (start < 0 || end <= start) return [{ text, highlight: false }]
  return [
    { text: text.slice(0, start), highlight: false },
    { text: text.slice(start, end), highlight: true },
    { text: text.slice(end), highlight: false },
  ].filter(segment => segment.text)
}

watch(() => props.open, async (open) => {
  if (open) {
    document.addEventListener('keydown', onKeydown)
    await nextTick()
    closeButton.value?.focus()
  } else {
    document.removeEventListener('keydown', onKeydown)
  }
})

onBeforeUnmount(() => document.removeEventListener('keydown', onKeydown))
</script>

<style scoped>
.evidence-backdrop {
  position: fixed;
  inset: 0;
  z-index: 300;
  display: flex;
  justify-content: flex-end;
  background: rgba(0, 0, 0, 0.28);
}

.evidence-drawer {
  display: flex;
  flex-direction: column;
  width: min(560px, 100vw);
  height: 100%;
  background: var(--c-paper);
  border-left: 1px solid var(--c-ink);
  box-shadow: -6px 0 0 rgba(0, 0, 0, 0.08);
}

.evidence-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  padding: 22px 24px 18px;
  border-bottom: 1px solid var(--c-line);
}

.evidence-kicker {
  margin-bottom: 6px;
  color: var(--c-brand);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 1px;
  text-transform: uppercase;
}

.evidence-title {
  max-width: 430px;
  font-size: 18px;
  line-height: 1.35;
}

.evidence-close {
  width: 32px;
  height: 32px;
  flex: 0 0 32px;
  border: 1px solid var(--c-line-strong);
  background: var(--c-paper);
  color: var(--c-ink);
  font-size: 22px;
  line-height: 1;
  cursor: pointer;
}

.evidence-close:hover {
  border-color: var(--c-brand);
  color: var(--c-brand);
}

.evidence-body {
  flex: 1;
  overflow-y: auto;
  padding: 18px 24px 36px;
}

.evidence-summary {
  display: flex;
  align-items: flex-start;
  gap: 9px;
  margin-bottom: 18px;
  padding: 10px 12px;
  border-left: 3px solid var(--c-ink);
  background: var(--c-bg-softer);
  color: var(--c-ink-3);
  font-size: 12px;
  line-height: 1.55;
}

.evidence-summary.warning {
  border-left-color: var(--c-brand);
  background: var(--c-brand-tint);
}

.evidence-summary-mark {
  flex: 0 0 auto;
  color: var(--c-brand);
  font-weight: 700;
}

.evidence-state {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 48px 8px;
  color: var(--c-ink-3);
  font-size: 13px;
  line-height: 1.6;
  text-align: center;
}

.evidence-state strong {
  color: var(--c-ink-2);
}

.evidence-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.evidence-item {
  padding-bottom: 16px;
  border-bottom: 1px solid var(--c-line-soft);
}

.evidence-item:last-child {
  border-bottom: none;
}

.evidence-item.unverified {
  border-left: 3px solid var(--c-brand);
  padding-left: 12px;
}

.evidence-item-head,
.evidence-reference-meta {
  display: flex;
  align-items: baseline;
  gap: 8px;
  flex-wrap: wrap;
}

.evidence-source {
  color: var(--c-brand);
  font-size: 11px;
  font-weight: 700;
}

.evidence-field {
  color: var(--c-ink-4);
  font-size: 11px;
}

.evidence-traceability {
  margin-left: auto;
  color: var(--a-conservative);
  font-size: 10px;
  font-weight: 700;
}

.evidence-traceability.unverified {
  color: var(--c-brand);
}

.evidence-claim {
  margin: 7px 0 10px;
  color: var(--c-ink-2);
  font-size: 14px;
  line-height: 1.6;
}

.evidence-inference-note {
  margin: 6px 0 0;
  color: var(--c-brand);
  font-size: 11px;
  line-height: 1.5;
}

.evidence-reference {
  margin-top: 10px;
  padding: 10px 12px;
  background: var(--c-bg-softer);
  border: 1px solid var(--c-line-soft);
}

.evidence-reference-meta {
  justify-content: space-between;
  color: var(--c-ink-4);
  font-size: 10px;
}

.evidence-quote {
  margin: 8px 0 0;
  color: var(--c-ink-3);
  font-size: 12px;
  line-height: 1.75;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.evidence-quote mark {
  padding: 1px 2px;
  background: #ffe2d7;
  color: var(--c-ink);
}

.evidence-missing {
  margin-top: 7px;
  color: var(--c-brand);
  font-size: 12px;
}

.evidence-warning {
  margin-top: 16px;
  padding: 12px;
  border: 1px solid var(--c-brand-line);
  background: var(--c-brand-tint);
  color: var(--c-ink-3);
  font-size: 12px;
  line-height: 1.55;
}

.evidence-warning-title {
  margin-bottom: 4px;
  color: var(--c-brand);
  font-weight: 700;
}

@media (max-width: 640px) {
  .evidence-header,
  .evidence-body {
    padding-left: 16px;
    padding-right: 16px;
  }
}
</style>
