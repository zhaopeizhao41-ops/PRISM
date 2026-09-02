<template>
  <header class="app-header">
    <!-- 左侧：固定宽度品牌区 -->
    <div class="brand-zone" @click="goHome">
      <img src="../assets/logo/logo_mark.png" alt="PRISM" class="brand-logo" />
      <span class="brand-word">PRISM</span>
    </div>

    <!-- 中间：严格绝对居中的工作流导航 -->
    <div class="stepper-zone">
      <WorkflowStepper
        v-if="projectId"
        :project-id="projectId"
        :current-step="currentStep"
        :active-session-id="sessionId"
      />
    </div>

    <!-- 右侧：固定宽度工具区 -->
    <div class="actions-zone">
      <LanguageSwitcher />
      <slot name="extra"></slot>
    </div>
  </header>
</template>

<script setup>
import { computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import LanguageSwitcher from './LanguageSwitcher.vue'
import WorkflowStepper from './WorkflowStepper.vue'

const props = defineProps({
  projectId: { type: String, default: '' },
  currentStep: { type: String, default: '' },
  sessionId: { type: String, default: '' }
})

const router = useRouter()
const route = useRoute()

function goHome() {
  router.push('/')
}
</script>

<style scoped>
.app-header {
  height: 56px;
  display: grid;
  grid-template-columns: 200px 1fr 200px;
  align-items: center;
  padding: 0 32px;
  position: sticky;
  top: 0;
  background: var(--c-paper);
  border-bottom: 1px solid var(--c-line);
  z-index: 100;
  box-sizing: border-box;
}

.brand-zone {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  user-select: none;
  justify-self: start;
}

.brand-logo {
  height: 24px;
  width: auto;
  display: block;
}

.brand-word {
  font-family: 'Space Grotesk', 'Inter', sans-serif;
  font-weight: 700;
  font-size: 16px;
  letter-spacing: 3px;
  color: var(--c-ink);
}

.stepper-zone {
  display: flex;
  justify-content: center;
  align-items: center;
  width: 100%;
}

.actions-zone {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 12px;
  justify-self: end;
}

@media (max-width: 900px) {
  .app-header {
    grid-template-columns: 140px 1fr auto;
    padding: 0 16px;
  }
}
</style>
