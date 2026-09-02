<template>
  <router-view v-slot="{ Component, route }">
    <transition name="page-fade" mode="out-in">
      <component :is="Component" :key="route.name === 'Workbench' ? 'workbench-' + route.params.projectId : (route.params.projectId || route.params.sessionId || route.path)" />
    </transition>
  </router-view>
</template>

<script setup>
// 使用 Vue Router 来管理页面
</script>

<style>
/* 页面平滑过渡 */
.page-fade-enter-active,
.page-fade-leave-active {
  transition: opacity 0.1s ease;
}

.page-fade-enter-from,
.page-fade-leave-to {
  opacity: 0;
}
/* ===== PRISM 设计 tokens =====
   体系：新粗野主义 + 仪器感
   白底纸面 / 墨黑描边 / 品牌橙锐利点缀 / 硬偏移阴影 */
:root {
  /* 品牌色 */
  --c-brand: #FF4500;
  --c-brand-deep: #E03D00;
  --c-brand-light: #FF7A50;
  --c-brand-soft: #FFF3EE;   /* 橙底浅背景 */
  --c-brand-line: #FFE0D4;   /* 橙浅描边 */
  --c-brand-tint: #FFF8F4;   /* 橙极浅底（hover） */

  /* 墨阶 */
  --c-ink: #000000;
  --c-ink-2: #333333;
  --c-ink-3: #666666;
  --c-ink-4: #999999;
  --c-ink-5: #CCCCCC;

  /* 线与底 */
  --c-line: #E5E5E5;
  --c-line-soft: #EEEEEE;
  --c-line-strong: #DDDDDD;
  --c-bg-soft: #F5F5F5;
  --c-bg-softer: #FAFAFA;
  --c-paper: #ffffff;

  /* archetype 徽章（与主色同明度的高饱和组） */
  --a-aggressive: #E5484D;
  --a-conservative: #3E7CB1;
  --a-balanced: #2F9E77;
  --a-detour: #D97706;
  --a-exit: #7C5CBF;

  /* 圆角分级：锐利 */
  --r-sm: 2px;   /* 小控件：按钮/徽章 */
  --r-md: 4px;   /* 卡片/输入框 */
  --r-lg: 10px;  /* 头像/圆形元素 */

  /* 硬偏移阴影 */
  --shadow-pop: 4px 4px 0 var(--c-ink);
  --shadow-pop-sm: 3px 3px 0 var(--c-ink);
  --shadow-pop-lg: 8px 8px 0 rgba(0, 0, 0, 0.15);

  /* 动效 */
  --ease-pop: cubic-bezier(0.2, 0.7, 0.3, 1.2);
  --dur-fast: 0.15s;
  --dur-rise: 0.5s;
}

/* 全局样式重置 */
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

#app {
  font-family: 'JetBrains Mono', 'Space Grotesk', 'Noto Sans SC', monospace;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  color: var(--c-ink);
  background-color: var(--c-paper);
}

/* 键盘可访问性：统一品牌橙焦点环 */
:focus-visible {
  outline: 2px solid var(--c-brand);
  outline-offset: 2px;
}

/* 尊重系统减少动效设置 */
@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
}

/* 滚动条样式 */
::-webkit-scrollbar {
  width: 8px;
  height: 8px;
}

::-webkit-scrollbar-track {
  background: var(--c-bg-soft);
}

::-webkit-scrollbar-thumb {
  background: var(--c-ink);
}

::-webkit-scrollbar-thumb:hover {
  background: var(--c-ink-2);
}

/* 全局按钮与交互控件统一规范体系 */
button {
  font-family: inherit;
  cursor: pointer;
}

/* 1. 主要操作按钮 (Primary / Brand) */
.btn-primary,
button.primary,
.primary-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  background: var(--c-brand);
  border: 1px solid var(--c-brand);
  color: var(--c-paper);
  padding: 8px 18px;
  font-size: 13px;
  font-weight: 700;
  font-family: inherit;
  border-radius: var(--r-sm);
  cursor: pointer;
  transition: all var(--dur-fast);
  user-select: none;
}

.btn-primary:hover:not(:disabled),
button.primary:hover:not(:disabled),
.primary-btn:hover:not(:disabled) {
  background: var(--c-brand-deep);
  border-color: var(--c-brand-deep);
  box-shadow: var(--shadow-pop-sm);
  transform: translate(-1px, -1px);
}

.btn-primary:active:not(:disabled),
button.primary:active:not(:disabled),
.primary-btn:active:not(:disabled) {
  transform: translate(1px, 1px);
  box-shadow: 1px 1px 0 var(--c-ink);
}

.btn-primary:disabled,
button.primary:disabled,
.primary-btn:disabled {
  background: var(--c-bg-soft);
  border-color: var(--c-line);
  color: var(--c-ink-5);
  cursor: not-allowed;
  transform: none;
  box-shadow: none;
}

/* 2. 次要 / 描边按钮 (Secondary / Outline / Link) */
.btn-secondary,
.btn-outline,
.link-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  background: var(--c-paper);
  border: 1px solid var(--c-line-strong);
  color: var(--c-ink-2);
  padding: 7px 16px;
  font-size: 12px;
  font-weight: 600;
  font-family: inherit;
  border-radius: var(--r-sm);
  cursor: pointer;
  transition: all var(--dur-fast);
  user-select: none;
}

.btn-secondary:hover:not(:disabled),
.btn-outline:hover:not(:disabled),
.link-btn:hover:not(:disabled) {
  border-color: var(--c-ink);
  color: var(--c-ink);
  box-shadow: var(--shadow-pop-sm);
  transform: translate(-1px, -1px);
}

.btn-secondary:active:not(:disabled),
.btn-outline:active:not(:disabled),
.link-btn:active:not(:disabled) {
  background: var(--c-ink);
  color: var(--c-paper);
  border-color: var(--c-ink);
  transform: translate(0, 0);
  box-shadow: none;
}

/* 3. 标签式选项卡与分段切换器 (Tabs / Switchers) */
.tab-item,
.switch-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: var(--c-bg-softer);
  border: 1px solid var(--c-line-strong);
  color: var(--c-ink-3);
  padding: 6px 14px;
  font-size: 13px;
  font-weight: 600;
  font-family: inherit;
  border-radius: var(--r-sm);
  cursor: pointer;
  transition: all var(--dur-fast);
  user-select: none;
}

.tab-item:hover,
.switch-item:hover {
  background: var(--c-paper);
  border-color: var(--c-ink);
  color: var(--c-ink);
  box-shadow: 2px 2px 0 var(--c-ink);
  transform: translate(-1px, -1px);
}

.tab-item.active,
.switch-item.active {
  background: var(--c-ink);
  border-color: var(--c-ink);
  color: var(--c-paper);
  font-weight: 700;
  box-shadow: var(--shadow-pop-sm);
  transform: translate(0, 0);
}
</style>
