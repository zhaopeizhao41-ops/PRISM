<template>
  <div class="language-switcher" ref="switcherRef">
    <button class="switcher-trigger" @click="toggleDropdown">
      {{ currentLabel }}
      <span class="caret">{{ open ? '▲' : '▼' }}</span>
    </button>
    <ul v-if="open" class="switcher-dropdown">
      <li
        v-for="loc in availableLocales"
        :key="loc.key"
        class="switcher-option"
        :class="{ active: loc.key === locale }"
        @click="switchLocale(loc.key)"
      >
        {{ loc.label }}
      </li>
    </ul>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { availableLocales } from '@/i18n/index.js'

const { locale } = useI18n()
const open = ref(false)
const switcherRef = ref(null)

const currentLabel = computed(() => {
  const found = availableLocales.find(l => l.key === locale.value)
  return found ? found.label : locale.value
})

const toggleDropdown = () => {
  open.value = !open.value
}

const switchLocale = (key) => {
  locale.value = key
  localStorage.setItem('locale', key)
  document.documentElement.lang = key
  open.value = false
}

const onClickOutside = (e) => {
  if (switcherRef.value && !switcherRef.value.contains(e.target)) {
    open.value = false
  }
}

onMounted(() => {
  document.addEventListener('click', onClickOutside)
  document.documentElement.lang = locale.value
})

onUnmounted(() => {
  document.removeEventListener('click', onClickOutside)
})
</script>

<style scoped>
.language-switcher {
  position: relative;
  display: inline-block;
  font-family: inherit;
}

.switcher-trigger {
  background: var(--c-paper);
  color: var(--c-ink-2);
  border: 1px solid var(--c-line-strong);
  padding: 4px 12px;
  font-family: inherit;
  font-size: 12px;
  font-weight: 600;
  border-radius: var(--r-sm);
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 6px;
  transition: all var(--dur-fast);
}

.switcher-trigger:hover {
  border-color: var(--c-ink);
  color: var(--c-ink);
  box-shadow: 2px 2px 0 var(--c-ink);
  transform: translate(-1px, -1px);
}

.caret {
  font-size: 8px;
  color: var(--c-ink-4);
}

.switcher-dropdown {
  position: absolute;
  top: 100%;
  right: 0;
  margin-top: 6px;
  background: var(--c-paper);
  border: 1px solid var(--c-ink);
  list-style: none;
  padding: 4px 0;
  min-width: 100%;
  z-index: 1000;
  border-radius: var(--r-sm);
  box-shadow: var(--shadow-pop-sm);
}

.switcher-option {
  padding: 6px 14px;
  font-size: 12px;
  color: var(--c-ink-2);
  cursor: pointer;
  white-space: nowrap;
  transition: background 0.15s;
}

.switcher-option:hover {
  background: var(--c-bg-soft);
  color: var(--c-ink);
}

.switcher-option.active {
  color: var(--c-brand);
  font-weight: 700;
}
</style>
