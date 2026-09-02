<template>
  <nav class="workflow-stepper">
    <div class="stepper-track">
      <template v-for="(step, i) in steps" :key="step.key">
        <span v-if="i > 0" class="step-divider">/</span>
        <button
          class="step-item"
          :class="{ active: currentStep === step.key }"
          type="button"
          @click="navigate(step)"
        >
          <span class="step-label">{{ t('stepper.' + step.key) }}</span>
        </button>
      </template>
    </div>

    <div class="stepper-actions">
      <button
        class="action-pill"
        :class="{ active: currentStep === 'workbench' }"
        type="button"
        @click="router.push('/workbench/' + projectId)"
      >
        ▤ {{ t('stepper.workbench') }}
      </button>
      <button
        class="action-pill"
        :class="{ active: currentStep === 'graph' }"
        type="button"
        @click="router.push('/graph/' + projectId)"
      >
        ◈ {{ t('stepper.graph') }}
      </button>
    </div>
  </nav>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { listEvolutionSessions } from '../api/evolution'

const props = defineProps({
  projectId: { type: String, required: true },
  currentStep: { type: String, default: '' },
  activeSessionId: { type: String, default: '' }
})

const router = useRouter()
const { t } = useI18n()
const resolvedSessionId = ref(props.activeSessionId || '')

async function fetchLatestSession() {
  if (resolvedSessionId.value || !props.projectId) return resolvedSessionId.value
  try {
    const res = await listEvolutionSessions(props.projectId)
    const list = Array.isArray(res?.data) ? res.data : (res?.sessions || [])
    if (list.length > 0) {
      // 优先选择 active 会话，其次选择最新会话
      const active = list.find(s => s.status === 'active')
      resolvedSessionId.value = active ? active.session_id : list[0].session_id
      return resolvedSessionId.value
    }
  } catch {
    // ignore
  }
  return ''
}

onMounted(() => {
  fetchLatestSession()
})

const steps = computed(() => [
  { key: 'profile', path: '/profile/' + props.projectId },
  { key: 'branches', path: '/branches/' + props.projectId },
  {
    key: 'evolution',
    path: resolvedSessionId.value ? '/evolution/' + resolvedSessionId.value : '/branches/' + props.projectId
  },
  { key: 'compare', path: '/compare/' + props.projectId },
  { key: 'roundtable', path: '/roundtable/' + props.projectId }
])

async function navigate(step) {
  if (props.currentStep === step.key) return
  if (step.key === 'evolution') {
    const sessId = resolvedSessionId.value || await fetchLatestSession()
    if (sessId) {
      router.push('/evolution/' + sessId)
      return
    }
    router.push('/branches/' + props.projectId)
    return
  }
  router.push(step.path)
}
</script>

<style scoped>
.workflow-stepper {
  display: flex;
  align-items: center;
  gap: 12px;
}

.stepper-track {
  display: flex;
  align-items: center;
  gap: 4px;
  background: var(--c-bg-subtle, #f5f3ee);
  padding: 3px 8px;
  border: 1px solid var(--c-line-soft);
  border-radius: var(--r-sm);
}

.step-divider {
  color: var(--c-line-strong);
  font-size: 11px;
  user-select: none;
  opacity: 0.5;
}

.step-item {
  background: transparent;
  border: none;
  padding: 3px 8px;
  font-family: inherit;
  font-size: 12px;
  font-weight: 500;
  color: var(--c-ink-3);
  cursor: pointer;
  border-radius: var(--r-sm);
  transition: all var(--dur-fast);
  white-space: nowrap;
}

.step-item:hover {
  color: var(--c-ink);
  background: var(--c-paper);
  box-shadow: 1px 1px 0 var(--c-ink);
  transform: translate(-0.5px, -0.5px);
}

.step-item.active {
  color: var(--c-paper);
  font-weight: 700;
  background: var(--c-ink);
  box-shadow: 1px 1px 0 var(--c-ink);
  transform: translate(0, 0);
}

.stepper-actions {
  display: flex;
  align-items: center;
  gap: 6px;
}

.action-pill {
  background: var(--c-bg-softer);
  border: 1px solid var(--c-line-strong);
  color: var(--c-ink-3);
  padding: 3px 10px;
  font-family: inherit;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  border-radius: var(--r-sm);
  transition: all var(--dur-fast);
  white-space: nowrap;
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.action-pill:hover {
  border-color: var(--c-ink);
  color: var(--c-ink);
  background: var(--c-paper);
  box-shadow: 2px 2px 0 var(--c-ink);
  transform: translate(-1px, -1px);
}

.action-pill.active {
  background: var(--c-ink);
  color: var(--c-paper);
  border-color: var(--c-ink);
  font-weight: 700;
  box-shadow: 2px 2px 0 var(--c-ink);
}

@media (max-width: 860px) {
  .workflow-stepper {
    display: none;
  }
}
</style>
