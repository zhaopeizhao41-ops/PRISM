<template>
  <div class="life-home">
    <!-- 顶部导航栏 -->
    <nav class="navbar">
      <div class="nav-brand" @click="router.push('/')">
        <img src="../assets/logo/logo_v3.png" alt="PRISM logo" class="brand-logo" />
      </div>
      <div class="nav-links">
        <LanguageSwitcher />
        <button class="create-btn" type="button" @click="router.push('/profile/create')">
          + {{ t('lifeHome.create') }}
        </button>
      </div>
    </nav>

    <div class="main-content">
      <!-- Hero -->
      <section class="hero">
        <div class="hero-left">
          <span class="orange-tag">{{ t('lifeHome.tagline') }}</span>
          <h1 class="main-title">
            {{ t('lifeHome.heroTitle1') }}<br>
            <span class="gradient-text">{{ t('lifeHome.heroTitle2') }}</span>
          </h1>
          <p class="hero-desc">{{ t('lifeHome.heroDesc') }}</p>
          <p class="hero-slogan">{{ t('lifeHome.heroSlogan') }}</p>
          <button v-if="!projects.length" class="hero-cta" type="button" @click="router.push('/profile/create')">
            {{ t('lifeHome.cta') }} →
          </button>
        </div>
        <div class="hero-right">
          <img src="../assets/logo/parallel_prism_v3.png" alt="Prism refracting into parallel lives" class="hero-logo" />
        </div>
      </section>

      <!-- 项目列表 -->
      <section class="projects-section">
        <div class="section-header">
          <span class="status-dot">■</span> {{ t('lifeHome.myProjects') }}
        </div>

        <div v-if="loading" class="empty-state">{{ t('common.loading') }}</div>

        <div v-else-if="!projects.length" class="empty-state">
          <p>{{ t('lifeHome.emptyHint') }}</p>
          <button class="hero-cta" type="button" @click="router.push('/profile/create')">
            {{ t('lifeHome.cta') }} →
          </button>
        </div>

        <div v-else class="projects-grid">
          <div
            v-for="p in projects"
            :key="p.project_id"
            class="project-card"
            role="button"
            tabindex="0"
            @click="handleCardClick(p)"
            @keydown.enter="handleCardClick(p)"
          >
            <div class="card-head">
              <span class="project-name">{{ p.name }}</span>
              <div class="card-head-right">
                <span class="project-date">{{ formatDate(p.created_at) }}</span>
                <button
                  class="project-del-btn"
                  type="button"
                  :title="t('common.delete')"
                  @click.stop="promptDelete(p)"
                >
                  ✕
                </button>
              </div>
            </div>
            <div class="card-badges">
              <span v-if="p.model_version" class="badge model">v{{ p.model_version }}</span>
              <span v-else class="badge pending">{{ t('lifeHome.noModel') }}</span>
              <span v-if="p.resume_session_id" class="badge active-session">
                ● {{ t('lifeHome.resume') }} {{ p.resume_stage }}/{{ p.resume_total }}
              </span>
              <span v-if="p.branch_count" class="badge">{{ t('lifeHome.branches', { n: p.branch_count }) }}</span>
              <span v-if="p.universe_count" class="badge">{{ t('lifeHome.universes', { n: p.universe_count }) }}</span>
              <span v-if="p.relationship_count" class="badge">{{ t('lifeHome.related', { n: p.relationship_count }) }}</span>
              <span v-if="p.roundtable_count" class="badge">{{ t('lifeHome.roundtables', { n: p.roundtable_count }) }}</span>
            </div>
            <div class="card-arrow">→</div>
          </div>
        </div>

        <!-- 删除确认弹窗 -->
        <div v-if="deleteTarget" class="modal-backdrop" @click="cancelDelete">
          <div class="modal-dialog" @click.stop>
            <div class="modal-title">
              <span class="status-dot alert">■</span> {{ t('common.delete') }}: {{ deleteTarget.name }}
            </div>
            <p class="modal-desc">{{ t('common.deleteConfirm') }}</p>
            <div class="modal-actions">
              <button class="modal-btn cancel" type="button" :disabled="deleteBusy" @click="cancelDelete">
                {{ t('common.cancel') }}
              </button>
              <button class="modal-btn delete" type="button" :disabled="deleteBusy" @click="doDelete">
                {{ deleteBusy ? t('common.loading') : t('common.confirm') }}
              </button>
            </div>
          </div>
        </div>
      </section>

      <!-- 流程说明 -->
      <section class="flow-section">
        <div class="section-header">
          <span class="diamond-icon">◇</span> {{ t('lifeHome.howItWorks') }}
        </div>
        <div class="flow-grid">
          <div class="flow-step">
            <span class="step-num">01</span>
            <div class="step-title">{{ t('lifeHome.step1') }}</div>
            <div class="step-desc">{{ t('lifeHome.step1Desc') }}</div>
          </div>
          <div class="flow-step">
            <span class="step-num">02</span>
            <div class="step-title">{{ t('lifeHome.step2') }}</div>
            <div class="step-desc">{{ t('lifeHome.step2Desc') }}</div>
          </div>
          <div class="flow-step">
            <span class="step-num">03</span>
            <div class="step-title">{{ t('lifeHome.step3') }}</div>
            <div class="step-desc">{{ t('lifeHome.step3Desc') }}</div>
          </div>
          <div class="flow-step">
            <span class="step-num">04</span>
            <div class="step-title">{{ t('lifeHome.step4') }}</div>
            <div class="step-desc">{{ t('lifeHome.step4Desc') }}</div>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import LanguageSwitcher from '../components/LanguageSwitcher.vue'
import { getProfileProjects, deleteProject } from '../api/profile'

const router = useRouter()
const { t } = useI18n()

const loading = ref(true)
const projects = ref([])
const deleteTarget = ref(null)
const deleteBusy = ref(false)

function formatDate(iso) {
  if (!iso) return ''
  return iso.replace('T', ' ').slice(0, 10)
}

function handleCardClick(p) {
  if (!p.model_version) {
    router.push(`/profile/create?project=${p.project_id}`)
  } else {
    router.push(`/profile/${p.project_id}`)
  }
}

function promptDelete(p) {
  deleteTarget.value = p
}

function cancelDelete() {
  deleteTarget.value = null
}

async function doDelete() {
  if (!deleteTarget.value || deleteBusy.value) return
  deleteBusy.value = true
  try {
    await deleteProject(deleteTarget.value.project_id)
    projects.value = projects.value.filter(p => p.project_id !== deleteTarget.value.project_id)
    deleteTarget.value = null
  } catch (err) {
    console.error('Delete failed', err)
  } finally {
    deleteBusy.value = false
  }
}

onMounted(async () => {
  try {
    const res = await getProfileProjects()
    projects.value = res.data || []
  } catch {
    projects.value = []
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.life-home {
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

.brand-logo {
  height: 38px;
  width: auto;
}

.brand-word {
  font-family: 'Space Grotesk', 'Inter', sans-serif;
  font-weight: 700;
  font-size: 19px;
  letter-spacing: 4px;
}

.nav-links {
  display: flex;
  align-items: center;
  gap: 16px;
}

.create-btn {
  background: var(--c-brand);
  color: var(--c-paper);
  border: none;
  padding: 8px 18px;
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
  border-radius: var(--r-sm);
  font-family: inherit;
}

.create-btn:hover {
  background: var(--c-brand-deep);
}

.main-content {
  max-width: 1060px;
  margin: 0 auto;
  padding: 48px 24px 96px;
}

/* Hero */
.hero {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 40px;
  margin-bottom: 56px;
}

.orange-tag {
  display: inline-block;
  background: var(--c-brand);
  color: var(--c-paper);
  font-size: 12px;
  font-weight: 700;
  padding: 4px 12px;
  border-radius: var(--r-sm);
  margin-bottom: 18px;
  letter-spacing: 1px;
}

.main-title {
  font-size: 44px;
  font-weight: 700;
  line-height: 1.25;
}

.accent-text {
  color: var(--c-brand);
}

/* hero 入场：staggered rise */
@keyframes rise-in {
  from { opacity: 0; transform: translateY(16px); }
  to { opacity: 1; transform: translateY(0); }
}

.hero-left > * {
  animation: rise-in var(--dur-rise) var(--ease-pop) both;
}

.hero-left > :nth-child(1) { animation-delay: 0.04s; }
.hero-left > :nth-child(2) { animation-delay: 0.12s; }
.hero-left > :nth-child(3) { animation-delay: 0.20s; }
.hero-left > :nth-child(4) { animation-delay: 0.28s; }
.hero-left > :nth-child(5) { animation-delay: 0.36s; }

.hero-logo {
  max-width: 380px;
  width: 100%;
  height: auto;
  animation: rise-in 0.7s var(--ease-pop) 0.15s both;
}

.hero-desc {
  margin-top: 18px;
  font-size: 15px;
  color: var(--c-ink-3);
  line-height: 1.8;
  max-width: 520px;
}

.hero-slogan {
  margin-top: 14px;
  font-family: 'Space Grotesk', 'Inter', sans-serif;
  font-size: 13px;
  letter-spacing: 1px;
  color: var(--c-brand);
  font-weight: 600;
}

.hero-cta {
  margin-top: 26px;
  background: var(--c-ink);
  color: var(--c-paper);
  border: none;
  padding: 13px 32px;
  font-size: 15px;
  font-weight: 700;
  cursor: pointer;
  border-radius: var(--r-sm);
  font-family: inherit;
}

.hero-cta:hover {
  background: var(--c-ink-2);
}

/* 区块头 */
.section-header {
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 2px;
  margin-bottom: 20px;
}

.status-dot {
  color: var(--c-brand);
  margin-right: 6px;
}

.diamond-icon {
  color: var(--c-brand);
  margin-right: 6px;
}

/* 项目列表 */
.projects-section {
  margin-bottom: 56px;
}

.projects-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 16px;
}

.project-card {
  position: relative;
  border: 1px solid var(--c-line);
  border-radius: var(--r-md);
  padding: 20px 22px;
  cursor: pointer;
  transition: all 0.15s;
}

.project-card:hover {
  border-color: var(--c-ink);
  box-shadow: var(--shadow-pop);
}

.card-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.project-name {
  font-size: 16px;
  font-weight: 700;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
}

.card-head-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.project-date {
  font-size: 12px;
  color: var(--c-ink-4);
  white-space: nowrap;
}

.project-del-btn {
  opacity: 0;
  pointer-events: none;
  background: transparent;
  border: 1px solid transparent;
  color: var(--c-ink-4);
  font-size: 11px;
  cursor: pointer;
  padding: 2px 6px;
  border-radius: var(--r-sm);
  transition: all 0.15s;
}

.project-card:hover .project-del-btn {
  opacity: 1;
  pointer-events: auto;
  color: var(--c-ink-3);
}

.project-del-btn:hover {
  background: var(--c-bg-soft);
  color: var(--a-aggressive);
  border-color: var(--c-line);
}

.card-badges {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.badge {
  font-size: 11px;
  padding: 2px 9px;
  border-radius: var(--r-sm);
  background: var(--c-bg-soft);
  color: var(--c-ink-3);
  white-space: nowrap;
}

.badge.model {
  background: var(--c-ink);
  color: var(--c-paper);
  font-weight: 700;
}

.badge.pending {
  background: var(--c-brand-soft);
  color: var(--c-brand);
}

.badge.active-session {
  background: var(--c-brand-soft);
  color: var(--c-brand);
  border: 1px solid var(--c-brand-line);
  font-weight: 600;
}

.card-arrow {
  position: absolute;
  right: 18px;
  bottom: 14px;
  color: var(--c-ink-5);
  font-size: 16px;
  transition: all 0.15s;
}

.project-card:hover .card-arrow {
  color: var(--c-brand);
  transform: translateX(2px);
}

.empty-state {
  border: 1px dashed var(--c-line-strong);
  border-radius: var(--r-md);
  padding: 48px 24px;
  text-align: center;
  color: var(--c-ink-4);
  font-size: 14px;
}

/* 流程说明 */
.flow-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}

.flow-step {
  border-top: 2px solid var(--c-ink);
  padding-top: 14px;
}

.step-num {
  font-size: 22px;
  font-weight: 700;
  color: var(--c-brand);
}

.step-title {
  font-size: 15px;
  font-weight: 700;
  margin: 8px 0 6px;
}

.step-desc {
  font-size: 12px;
  color: var(--c-ink-4);
  line-height: 1.7;
}

@media (max-width: 860px) {
  .hero {
    flex-direction: column;
    align-items: flex-start;
  }
  .flow-grid {
    grid-template-columns: repeat(2, 1fr);
  }
  .main-title {
    font-size: 32px;
  }
}

/* 确认弹窗 */
.modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
  padding: 20px;
}

.modal-dialog {
  background: var(--c-paper);
  border: 2px solid var(--c-ink);
  border-radius: var(--r-md);
  box-shadow: var(--shadow-pop);
  max-width: 440px;
  width: 100%;
  padding: 24px;
}

.modal-title {
  font-size: 15px;
  font-weight: 700;
  margin-bottom: 12px;
  display: flex;
  align-items: center;
}

.status-dot.alert {
  color: var(--a-aggressive);
}

.modal-desc {
  font-size: 13px;
  color: var(--c-ink-3);
  line-height: 1.7;
  margin-bottom: 20px;
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

.modal-btn {
  font-family: inherit;
  font-size: 13px;
  font-weight: 700;
  padding: 8px 18px;
  border-radius: var(--r-sm);
  cursor: pointer;
  border: 1px solid var(--c-ink);
  transition: all 0.15s;
}

.modal-btn.cancel {
  background: var(--c-paper);
  color: var(--c-ink-2);
  border-color: var(--c-line-strong);
}

.modal-btn.cancel:hover {
  border-color: var(--c-ink);
  color: var(--c-ink);
}

.modal-btn.delete {
  background: var(--a-aggressive);
  color: var(--c-paper);
  border-color: var(--a-aggressive);
}

.modal-btn.delete:hover:not(:disabled) {
  background: #c93b40;
  box-shadow: var(--shadow-pop-sm);
  transform: translate(-1px, -1px);
}

.modal-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
