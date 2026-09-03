<template>
  <div class="profile-create">
    <!-- 顶部导航 -->
    <nav class="navbar">
      <div class="nav-brand" @click="router.push('/')">
        <img src="../assets/logo/logo_mark.png" alt="PRISM logo" class="brand-logo" />
        <span class="brand-word">PRISM</span>
      </div>
      <div class="nav-links">
        <LanguageSwitcher />
        <span class="nav-mode-tag">{{ appendMode ? t('profile.create.appendMode') : t('profile.create.navBadge') }}</span>
        <button class="nav-back-btn" type="button" @click="router.push('/')">
          ← {{ t('profile.create.back') }}
        </button>
      </div>
    </nav>

    <!-- 编辑态：表单 + 自由资料 -->
    <div v-if="phase === 'editing'" class="main-content">
      <header class="page-header">
        <div class="page-header-row">
          <h1 class="page-title">{{ t('profile.create.title') }}</h1>
          <div v-if="draftRestored" class="draft-badge">
            <span class="draft-dot">■</span>
            <span>{{ t('profile.create.draftRestored') }}</span>
            <button class="draft-clear-btn" type="button" @click="clearDraft">
              {{ t('profile.create.clearDraft') }}
            </button>
          </div>
        </div>
        <p class="page-desc">{{ t('profile.create.subtitle') }}</p>
      </header>

      <!-- A. 基本盘 -->
      <section class="form-card">
        <div class="card-header">
          <span class="card-num">01</span>
          <span class="card-title">{{ t('profile.create.secBasic') }}</span>
          <span class="card-hint">{{ t('profile.create.allOptional') }}</span>
        </div>
        <div class="field-grid">
          <div class="field">
            <label>{{ t('profile.create.fNickname') }}</label>
            <input v-model="form.nickname" type="text" :placeholder="t('profile.create.phNickname')" />
          </div>
          <div class="field">
            <label>{{ t('profile.create.fAge') }}</label>
            <select v-model="form.age_range">
              <option value="">{{ t('profile.create.unfilled') }}</option>
              <option v-for="o in ageOptions" :key="o" :value="o">{{ optLabel(o) }}</option>
            </select>
          </div>
          <div class="field">
            <label>{{ t('profile.create.fGender') }}</label>
            <select v-model="form.gender">
              <option value="">{{ t('profile.create.unfilled') }}</option>
              <option v-for="o in genderOptions" :key="o" :value="o">{{ optLabel(o) }}</option>
            </select>
          </div>
          <div class="field">
            <label>{{ t('profile.create.fLocation') }}</label>
            <input v-model="form.location" type="text" :placeholder="t('profile.create.phLocation')" />
          </div>
          <div class="field">
            <label>{{ t('profile.create.fIndustry') }}</label>
            <input v-model="form.industry" type="text" :placeholder="t('profile.create.phIndustry')" />
          </div>
          <div class="field">
            <label>{{ t('profile.create.fStatus') }}</label>
            <select v-model="form.current_status">
              <option value="">{{ t('profile.create.unfilled') }}</option>
              <option v-for="o in statusOptions" :key="o" :value="o">{{ optLabel(o) }}</option>
            </select>
          </div>
          <div class="field">
            <label>{{ t('profile.create.fEdu') }}</label>
            <select v-model="form.education_level">
              <option value="">{{ t('profile.create.unfilled') }}</option>
              <option v-for="o in eduOptions" :key="o" :value="o">{{ optLabel(o) }}</option>
            </select>
          </div>
          <div class="field">
            <label>{{ t('profile.create.fFinance') }}</label>
            <select v-model="form.financial_state">
              <option value="">{{ t('profile.create.unfilled') }}</option>
              <option v-for="o in financeOptions" :key="o" :value="o">{{ optLabel(o) }}</option>
            </select>
          </div>
        </div>
      </section>

      <!-- B. 性格与认知 -->
      <section class="form-card">
        <div class="card-header">
          <span class="card-num">02</span>
          <span class="card-title">{{ t('profile.create.secPersonality') }}</span>
        </div>
        <div class="field-grid">
          <div class="field">
            <label>{{ t('profile.create.fMbti') }}</label>
            <select v-model="form.mbti">
              <option value="">{{ t('profile.create.unfilled') }}</option>
              <option v-for="m in mbtiOptions" :key="m" :value="m === '不确定' ? '' : m">{{ m }}</option>
            </select>
          </div>
        </div>
        <div class="field">
          <label>{{ t('profile.create.fBig5') }}</label>
          <label class="checkbox-row">
            <input v-model="big5Enabled" type="checkbox" />
            <span>{{ t('profile.create.big5Toggle') }}</span>
          </label>
          <div v-if="big5Enabled" class="big5-sliders">
            <div v-for="d in big5Dims" :key="d.key" class="slider-row">
              <span class="slider-label">{{ t(`profile.create.big5_${d.key}`) }}</span>
              <input v-model.number="form.big5[d.key]" type="range" min="1" max="7" />
              <span class="slider-value">{{ form.big5[d.key] }}</span>
            </div>
          </div>
        </div>
        <div class="field">
          <label>{{ t('profile.create.fTags') }}</label>
          <div class="tag-cloud">
            <button
              v-for="tag in presetTags"
              :key="tag"
              class="tag-chip"
              :class="{ active: form.self_tags.includes(tag) }"
              type="button"
              @click="toggleTag(tag)"
            >
              {{ optLabel(tag) }}
            </button>
          </div>
          <div class="tag-input-row">
            <input
              v-model="customTagInput"
              type="text"
              :placeholder="t('profile.create.phCustomTag')"
              @keyup.enter="addCustomTag"
            />
            <button class="btn-mini" type="button" @click="addCustomTag">{{ t('profile.create.add') }}</button>
          </div>
          <div v-if="customTags.length" class="tag-cloud">
            <button
              v-for="tag in customTags"
              :key="tag"
              class="tag-chip active"
              type="button"
              @click="removeCustomTag(tag)"
            >
              {{ tag }} ×
            </button>
          </div>
        </div>
      </section>

      <!-- C. 能力与资源 -->
      <section class="form-card">
        <div class="card-header">
          <span class="card-num">03</span>
          <span class="card-title">{{ t('profile.create.secSkills') }}</span>
        </div>
        <div class="dynamic-rows">
          <div v-for="(skill, i) in form.skills" :key="i" class="dynamic-row">
            <input v-model="skill.name" type="text" :placeholder="t('profile.create.phSkillName')" class="grow" />
            <select v-model="skill.proficiency">
              <option value="">{{ t('profile.create.proficiency') }}</option>
              <option v-for="n in 5" :key="n" :value="String(n)">{{ n }}/5</option>
            </select>
            <select v-model="skill.domain">
              <option v-for="d in skillDomains" :key="d" :value="d">{{ optLabel(d) }}</option>
            </select>
            <button class="btn-mini danger" type="button" @click="form.skills.splice(i, 1)">×</button>
          </div>
        </div>
        <button class="btn-mini" type="button" @click="form.skills.push({ name: '', proficiency: '', domain: '专业' })">
          + {{ t('profile.create.addSkill') }}
        </button>
      </section>

      <!-- D. 人际与支持 -->
      <section class="form-card">
        <div class="card-header">
          <span class="card-num">04</span>
          <span class="card-title">{{ t('profile.create.secRelations') }}</span>
        </div>
        <div class="field-grid">
          <div class="field">
            <label>{{ t('profile.create.fFamily') }}</label>
            <select v-model="form.family_status">
              <option value="">{{ t('profile.create.unfilled') }}</option>
              <option v-for="o in familyOptions" :key="o" :value="o">{{ optLabel(o) }}</option>
            </select>
          </div>
          <div class="field">
            <label>{{ t('profile.create.fSupport') }}</label>
            <select v-model="form.social_support">
              <option value="">{{ t('profile.create.unfilled') }}</option>
              <option v-for="n in 5" :key="n" :value="String(n)">{{ n }}/5</option>
            </select>
          </div>
        </div>
        <div class="field">
          <label>{{ t('profile.create.fKeyPersons') }}</label>
          <div class="dynamic-rows">
            <div v-for="(rel, i) in form.important_relations" :key="i" class="dynamic-row">
              <input v-model="rel.person" type="text" :placeholder="t('profile.create.phPersonName')" />
              <select v-model="rel.relation">
                <option v-for="k in relationKinds" :key="k" :value="k">{{ optLabel(k) }}</option>
              </select>
              <select v-model="rel.closeness">
                <option value="">{{ t('profile.create.closeness') }}</option>
                <option v-for="n in 5" :key="n" :value="String(n)">{{ n }}/5</option>
              </select>
              <input v-model="rel.influence" type="text" :placeholder="t('profile.create.phInfluence')" class="grow" />
              <button class="btn-mini danger" type="button" @click="form.important_relations.splice(i, 1)">×</button>
            </div>
          </div>
          <button class="btn-mini" type="button" @click="form.important_relations.push({ person: '', relation: '家人', closeness: '', influence: '' })">
            + {{ t('profile.create.addRelation') }}
          </button>
        </div>
      </section>

      <!-- E. 目标与困扰 -->
      <section class="form-card">
        <div class="card-header">
          <span class="card-num">05</span>
          <span class="card-title">{{ t('profile.create.secGoals') }}</span>
        </div>
        <div class="field">
          <label>{{ t('profile.create.fGoal') }}</label>
          <textarea v-model="form.goal_short_term" rows="2" :placeholder="t('profile.create.phGoal')"></textarea>
        </div>
        <div class="field">
          <label>{{ t('profile.create.fBlocker') }}</label>
          <textarea v-model="form.current_blocker" rows="2" :placeholder="t('profile.create.phBlocker')"></textarea>
        </div>
        <div class="field">
          <label>{{ t('profile.create.fAvoid') }}</label>
          <textarea v-model="form.want_to_avoid" rows="2" :placeholder="t('profile.create.phAvoid')"></textarea>
        </div>
      </section>

      <!-- 自由资料区 -->
      <section class="form-card">
        <div class="card-header">
          <span class="card-num">06</span>
          <span class="card-title">{{ t('profile.create.secMaterials') }}</span>
          <span class="card-hint">{{ t('profile.create.materialsHint') }}</span>
        </div>
        <div class="materials-controls">
          <div class="field inline">
            <label>{{ t('profile.create.fMaterialMode') }}</label>
            <select v-model="materialMode">
              <option value="personal">{{ t('profile.create.personalMode') }}</option>
              <option value="fictional">{{ t('profile.create.fictionalMode') }}</option>
            </select>
          </div>
          <div class="field inline">
            <label>{{ t('profile.create.fMaterialType') }}</label>
            <select v-model="materialType">
              <option v-for="m in materialTypes" :key="m.value" :value="m.value">{{ t(`profile.mat.${m.value}`) }}</option>
            </select>
          </div>
          <div class="field inline">
            <label>{{ t('profile.create.fTimeRange') }}</label>
            <input v-model="timeRange" type="text" :placeholder="t('profile.create.phTimeRange')" />
          </div>
        </div>
        <div class="field">
          <div class="textarea-header">
            <label>{{ t('profile.create.phPaste') }}</label>
            <span v-if="pastedText.length" class="char-count">
              {{ t('profile.create.charCount', { n: pastedText.length.toLocaleString() }) }}
            </span>
          </div>
          <textarea v-model="pastedText" rows="5" :placeholder="t('profile.create.phPaste')"></textarea>
        </div>
        <div
          class="upload-zone"
          :class="{ 'drag-over': isDragOver }"
          @dragover.prevent="isDragOver = true"
          @dragleave.prevent="isDragOver = false"
          @drop.prevent="handleDrop"
          @click="triggerFileInput"
        >
          <input
            ref="fileInput"
            type="file"
            multiple
            accept=".pdf,.docx,.doc,.xlsx,.xls,.csv,.pptx,.txt,.md,.markdown,.html,.htm,.json,.log,.rtf,.png,.jpg,.jpeg,.webp"
            style="display: none"
            @change="handleFileSelect"
          />
          <div class="upload-icon-symbol">▲</div>
          <p class="upload-main">{{ t('profile.create.uploadMain') }}</p>
          <p class="upload-sub">{{ t('profile.create.uploadSub') }}</p>
          <div class="format-badges">
            <span class="fmt-pill">{{ t('profile.create.fmtWord') }}</span>
            <span class="fmt-pill">{{ t('profile.create.fmtPdf') }}</span>
            <span class="fmt-pill">{{ t('profile.create.fmtExcel') }}</span>
            <span class="fmt-pill">{{ t('profile.create.fmtPpt') }}</span>
            <span class="fmt-pill">{{ t('profile.create.fmtImage') }}</span>
            <span class="fmt-pill">{{ t('profile.create.fmtText') }}</span>
          </div>
        </div>
        <div v-if="selectedFiles.length" class="file-list">
          <div v-for="(f, i) in selectedFiles" :key="i" class="file-item">
            <span class="file-badge" :class="getFileBadgeClass(f.name)">{{ getFileBadge(f.name) }}</span>
            <span class="file-name">{{ f.name }}</span>
            <span class="file-size">{{ (f.size / 1024).toFixed(1) }} KB</span>
            <button class="btn-mini danger" type="button" @click="selectedFiles.splice(i, 1)">×</button>
          </div>
        </div>
        <!-- 已提交资料清单（补充模式） -->
        <div v-if="existingMaterials.length" class="existing-materials">
          <div class="existing-header">{{ t('profile.create.existingMaterials') }} ({{ existingMaterials.length }})</div>
          <div v-for="(m, i) in existingMaterials" :key="i" class="file-item">
            <span class="mat-type">{{ t(`profile.mat.${m.material_type}`, m.material_type) }}</span>
            <span class="file-size">{{ m.char_count }} {{ t('profile.create.charsUnit') }}</span>
          </div>
        </div>
      </section>

      <!-- 提交栏 -->
      <div class="submit-bar">
        <p v-if="!canSubmit" class="submit-warn">{{ t('profile.create.emptyWarn') }}</p>
        <button class="submit-btn" :disabled="!canSubmit" @click="handleGenerate">
          {{ appendMode ? t('profile.create.regenerate') : t('profile.create.submit') }}
        </button>
      </div>
    </div>

    <!-- 进度态 -->
    <div v-else class="main-content progress-content">
      <div class="progress-card">
        <div class="progress-steps">
          <div
            v-for="(s, i) in progressSteps"
            :key="s.key"
            class="progress-step"
            :class="{ active: s.key === phase, done: stepDone(i) }"
          >
            <span class="step-marker">{{ stepDone(i) ? '✓' : i + 1 }}</span>
            <span class="step-name">{{ s.label }}</span>
          </div>
        </div>
        <div class="progress-bar-track">
          <div class="progress-bar-fill" :style="{ width: progress + '%' }"></div>
        </div>
        <p class="progress-message">{{ phaseMessage || t('common.loading') }}</p>

        <div v-if="phase === 'error'" class="error-box">
          <p class="error-title">{{ t('common.failed') }}</p>
          <pre class="error-detail">{{ errorMessage }}</pre>
          <button class="btn-mini" type="button" @click="backToEditing">{{ t('common.back') }}</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import LanguageSwitcher from '../components/LanguageSwitcher.vue'
import {
  createProfileProject,
  submitStructuredInput,
  submitMaterials,
  listMaterials,
  buildProfileGraph,
  getBuildStatus,
  generatePersonalModel,
  getGenerateStatus
} from '../api/profile'

const router = useRouter()
const route = useRoute()
const { t, te } = useI18n()

// ============== 常量 ==============

const DRAFT_STORAGE_KEY = 'prism_profile_draft_v1'

const ageOptions = ['18-24', '25-30', '31-35', '36-45', '46-55', '56+', '不便透露']
const genderOptions = ['女', '男', '其他', '不便透露']
const statusOptions = ['在职稳定', '在职迷茫', '求学', '求职', 'Gap', '创业', '自由职业']
const eduOptions = ['高中及以下', '大专', '本科', '硕士', '博士', '在读']
const financeOptions = ['宽裕', '稳定有结余', '紧平衡', '压力大有负债', '不便透露']
const mbtiOptions = [
  'INTJ', 'INTP', 'ENTJ', 'ENTP', 'INFJ', 'INFP', 'ENFJ', 'ENFP',
  'ISTJ', 'ISTP', 'ESTJ', 'ESTP', 'ISFJ', 'ISFP', 'ESFJ', 'ESFP', '不确定'
]
const familyOptions = ['单身', '恋爱中', '已婚', '已婚有孩', '其他']
const relationKinds = ['家人', '朋友', '同事', '导师', '其他']
const skillDomains = ['专业', '软技能', '爱好']
const presetTags = [
  '执行力强', '容易内耗', '社恐但线上活跃', '完美主义', '冒险偏好', '求稳',
  '乐观', '谨慎', '三分钟热度', '深度思考', '感性', '理性'
]
const materialTypes = [
  { value: 'diary' }, { value: 'reflection' }, { value: 'resume' },
  { value: 'preference' }, { value: 'chat_log' }, { value: 'literary' }, { value: 'other' }
]
const big5Dims = [
  { key: 'openness' }, { key: 'conscientiousness' }, { key: 'extraversion' },
  { key: 'agreeableness' }, { key: 'neuroticism' }
]

// 中文枚举值 → 本地化标签（zh 直接显示原值，en 走 profile.optMap 翻译）
function optLabel(value) {
  const key = `profile.optMap.${value}`
  return te(key) ? t(key) : value
}

// ============== 状态 ==============

const appendMode = computed(() => !!route.query.project)
const projectId = ref('')
const phase = ref('editing') // editing | submitting | building | synthesizing | error
const progress = ref(0)
const phaseMessage = ref('')
const errorMessage = ref('')
const draftRestored = ref(false)

const big5Enabled = ref(false)
const customTagInput = ref('')
const customTags = ref([])
const pastedText = ref('')
const materialType = ref('diary')
const materialMode = ref('personal')
const timeRange = ref('')
const selectedFiles = ref([])
const isDragOver = ref(false)
const fileInput = ref(null)
const existingMaterials = ref([])

const form = reactive({
  nickname: '',
  age_range: '',
  gender: '',
  location: '',
  industry: '',
  current_status: '',
  education_level: '',
  financial_state: '',
  mbti: '',
  self_tags: [],
  big5: { openness: 4, conscientiousness: 4, extraversion: 4, agreeableness: 4, neuroticism: 4 },
  skills: [{ name: '', proficiency: '', domain: '专业' }],
  family_status: '',
  social_support: '',
  important_relations: [{ person: '', relation: '家人', closeness: '', influence: '' }],
  goal_short_term: '',
  current_blocker: '',
  want_to_avoid: ''
})

const progressSteps = computed(() => [
  { key: 'submitting', label: t('profile.create.stepSubmit') },
  { key: 'building', label: t('profile.create.stepBuild') },
  { key: 'synthesizing', label: t('profile.create.stepSynthesize') }
])

function stepDone(index) {
  const order = ['submitting', 'building', 'synthesizing']
  const current = order.indexOf(phase.value)
  if (phase.value === 'error') return false
  return current > index
}

// ============== 表单辅助 ==============

function buildFormPayload() {
  const payload = {}
  const strFields = [
    'nickname', 'age_range', 'gender', 'location', 'industry', 'current_status',
    'education_level', 'financial_state', 'mbti', 'family_status',
    'goal_short_term', 'current_blocker', 'want_to_avoid'
  ]
  for (const key of strFields) {
    if (form[key] && String(form[key]).trim()) payload[key] = String(form[key]).trim()
  }
  if (form.self_tags.length) payload.self_tags = [...form.self_tags]
  if (big5Enabled.value) payload.big5 = { ...form.big5 }
  const skills = form.skills
    .filter(s => s.name && s.name.trim())
    .map(s => ({ name: s.name.trim(), proficiency: s.proficiency || '', domain: s.domain || '专业' }))
  if (skills.length) payload.skills = skills
  const relations = form.important_relations
    .filter(r => r.person && r.person.trim())
    .map(r => ({
      person: r.person.trim(),
      relation: r.relation || '其他',
      closeness: r.closeness || '',
      influence: (r.influence || '').trim()
    }))
  if (relations.length) payload.important_relations = relations
  if (form.social_support) payload.social_support = form.social_support
  return payload
}

const hasFormInput = computed(() => Object.keys(buildFormPayload()).length > 0)
const hasMaterialInput = computed(() => !!(pastedText.value.trim() || selectedFiles.value.length))
const canSubmit = computed(() => hasFormInput.value || hasMaterialInput.value)

function toggleTag(tag) {
  const idx = form.self_tags.indexOf(tag)
  if (idx >= 0) form.self_tags.splice(idx, 1)
  else form.self_tags.push(tag)
}

function addCustomTag() {
  const tag = customTagInput.value.trim()
  if (!tag) return
  if (!form.self_tags.includes(tag) && !presetTags.includes(tag)) customTags.value.push(tag)
  if (!form.self_tags.includes(tag)) form.self_tags.push(tag)
  customTagInput.value = ''
}

function removeCustomTag(tag) {
  customTags.value = customTags.value.filter(x => x !== tag)
  const idx = form.self_tags.indexOf(tag)
  if (idx >= 0) form.self_tags.splice(idx, 1)
}

function getFileBadge(filename) {
  const ext = (filename.split('.').pop() || '').toLowerCase()
  if (['docx', 'doc'].includes(ext)) return 'DOCX'
  if (ext === 'pdf') return 'PDF'
  if (['xlsx', 'xls', 'csv'].includes(ext)) return 'XLS'
  if (ext === 'pptx') return 'PPT'
  if (['png', 'jpg', 'jpeg', 'webp'].includes(ext)) return 'IMG'
  if (['html', 'htm'].includes(ext)) return 'HTML'
  if (ext === 'json') return 'JSON'
  if (['md', 'markdown'].includes(ext)) return 'MD'
  return 'TXT'
}

function getFileBadgeClass(filename) {
  const ext = (filename.split('.').pop() || '').toLowerCase()
  if (['docx', 'doc'].includes(ext)) return 'badge-word'
  if (ext === 'pdf') return 'badge-pdf'
  if (['xlsx', 'xls', 'csv'].includes(ext)) return 'badge-excel'
  if (ext === 'pptx') return 'badge-ppt'
  if (['png', 'jpg', 'jpeg', 'webp'].includes(ext)) return 'badge-img'
  return 'badge-text'
}

function triggerFileInput() {
  fileInput.value?.click()
}

function handleFileSelect(e) {
  for (const f of e.target.files) selectedFiles.value.push(f)
  e.target.value = ''
}

function handleDrop(e) {
  isDragOver.value = false
  const allowedExts = [
    'pdf', 'docx', 'doc', 'xlsx', 'xls', 'csv', 'pptx',
    'txt', 'md', 'markdown', 'html', 'htm', 'json', 'log', 'rtf',
    'png', 'jpg', 'jpeg', 'webp'
  ]
  for (const f of e.dataTransfer.files) {
    const ext = (f.name.split('.').pop() || '').toLowerCase()
    if (allowedExts.includes(ext)) {
      selectedFiles.value.push(f)
    }
  }
}

// ============== 草稿管理 ==============

let draftTimer = null
function saveDraft() {
  if (appendMode.value || phase.value !== 'editing') return
  clearTimeout(draftTimer)
  draftTimer = setTimeout(() => {
    try {
      const data = {
        form: JSON.parse(JSON.stringify(form)),
        pastedText: pastedText.value,
        materialType: materialType.value,
        materialMode: materialMode.value,
        timeRange: timeRange.value,
        customTags: [...customTags.value],
        big5Enabled: big5Enabled.value,
        savedAt: Date.now()
      }
      localStorage.setItem(DRAFT_STORAGE_KEY, JSON.stringify(data))
    } catch {
      /* ignore quota errors */
    }
  }, 400)
}

function loadDraft() {
  if (appendMode.value) return
  try {
    const raw = localStorage.getItem(DRAFT_STORAGE_KEY)
    if (!raw) return
    const data = JSON.parse(raw)
    let hasContent = false
    if (data.form) {
      Object.assign(form, data.form)
      for (const [k, v] of Object.entries(data.form)) {
        if (k === 'big5' || k === 'skills' || k === 'important_relations') continue
        if (Array.isArray(v) && v.length) hasContent = true
        else if (typeof v === 'string' && v.trim()) hasContent = true
      }
    }
    if (data.pastedText && data.pastedText.trim()) {
      pastedText.value = data.pastedText
      hasContent = true
    }
    if (data.materialType) materialType.value = data.materialType
    if (data.materialMode) materialMode.value = data.materialMode
    if (data.timeRange) timeRange.value = data.timeRange
    if (data.customTags?.length) {
      customTags.value = data.customTags
      hasContent = true
    }
    if (data.big5Enabled !== undefined) big5Enabled.value = data.big5Enabled
    if (hasContent) {
      draftRestored.value = true
    }
  } catch {
    /* ignore parse errors */
  }
}

function clearDraft() {
  localStorage.removeItem(DRAFT_STORAGE_KEY)
  resetForm()
  draftRestored.value = false
}

function resetForm() {
  form.nickname = ''
  form.age_range = ''
  form.gender = ''
  form.location = ''
  form.industry = ''
  form.current_status = ''
  form.education_level = ''
  form.financial_state = ''
  form.mbti = ''
  form.self_tags = []
  form.big5 = { openness: 4, conscientiousness: 4, extraversion: 4, agreeableness: 4, neuroticism: 4 }
  form.skills = [{ name: '', proficiency: '', domain: '专业' }]
  form.family_status = ''
  form.social_support = ''
  form.important_relations = [{ person: '', relation: '家人', closeness: '', influence: '' }]
  form.goal_short_term = ''
  form.current_blocker = ''
  form.want_to_avoid = ''
  pastedText.value = ''
  customTags.value = []
  big5Enabled.value = false
}

watch(
  [() => form, pastedText, materialType, materialMode, timeRange, customTags, big5Enabled],
  () => {
    saveDraft()
  },
  { deep: true }
)

watch(materialMode, value => {
  if (value === 'fictional') materialType.value = 'literary'
  else if (materialType.value === 'literary') materialType.value = 'diary'
})

// ============== 提交流程 ==============

function isDuplicateError(e) {
  return /重复|duplicate/i.test(e?.message || '')
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms))
}

async function pollTask(taskId, statusFn) {
  const deadline = Date.now() + 15 * 60 * 1000
  let failures = 0
  while (Date.now() < deadline) {
    await sleep(3000)
    try {
      const res = await statusFn(taskId)
      failures = 0
      const task = res.data
      progress.value = task.progress || 0
      phaseMessage.value = task.message || ''
      if (task.status === 'completed') return
      if (task.status === 'failed' || task.status === 'cancelled' || task.status === 'stale') {
        throw new Error(task.message || task.error || 'task failed')
      }
    } catch (error) {
      failures += 1
      if (failures >= 5) throw error
      await sleep(Math.min(30000, 1000 * 2 ** failures))
    }
  }
  throw new Error('任务超过最大等待时间，请稍后从项目页恢复')
}

async function handleGenerate() {
  if (!canSubmit.value) return
  errorMessage.value = ''
  try {
    localStorage.removeItem(DRAFT_STORAGE_KEY)
    // 1. 确保项目存在
    if (!projectId.value) {
      phase.value = 'submitting'
      phaseMessage.value = t('profile.create.phCreating')
      const res = await createProfileProject({ name: form.nickname || 'Personal Profile' })
      projectId.value = res.data.project_id
    }

    // 2. 提交量化表单
    if (hasFormInput.value) {
      phaseMessage.value = t('profile.create.phForm')
      try {
        await submitStructuredInput({ project_id: projectId.value, form: buildFormPayload() })
      } catch (e) {
        if (!isDuplicateError(e)) throw e
      }
    }

    // 3. 提交自由资料
    if (hasMaterialInput.value) {
      phaseMessage.value = t('profile.create.phMaterials')
      const fd = new FormData()
      fd.append('project_id', projectId.value)
      fd.append('material_type', materialType.value)
      fd.append('material_mode', materialMode.value)
      if (timeRange.value.trim()) fd.append('time_range', timeRange.value.trim())
      if (pastedText.value.trim()) fd.append('text', pastedText.value.trim())
      for (const f of selectedFiles.value) fd.append('files', f)
      try {
        await submitMaterials(fd)
      } catch (e) {
        if (!isDuplicateError(e)) throw e
      }
    }

    // 4. 构建图谱（补充模式强制重建）
    phase.value = 'building'
    progress.value = 0
    phaseMessage.value = t('profile.create.phBuilding')
    const buildRes = await buildProfileGraph({
      project_id: projectId.value,
      force: appendMode.value
    })
    if (!buildRes.data.reused) {
      await pollTask(buildRes.data.task_id, getBuildStatus)
    }

    // 5. 合成画像
    phase.value = 'synthesizing'
    progress.value = 0
    phaseMessage.value = t('profile.create.phSynthesizing')
    const analysisScope = materialMode.value === 'fictional' && !hasFormInput.value ? 'literary' : 'personal'
    const genRes = await generatePersonalModel({ project_id: projectId.value, scope: analysisScope })
    await pollTask(genRes.data.task_id, getGenerateStatus)

    // 6. 跳转画像页
    router.push(analysisScope === 'literary'
      ? `/profile/${projectId.value}?scope=literary`
      : `/profile/${projectId.value}`)
  } catch (e) {
    phase.value = 'error'
    errorMessage.value = e?.message || String(e)
  }
}

function backToEditing() {
  phase.value = 'editing'
  progress.value = 0
  phaseMessage.value = ''
}

// ============== 初始化 ==============

onMounted(async () => {
  if (route.query.project) {
    projectId.value = String(route.query.project)
    try {
      const res = await listMaterials(projectId.value)
      existingMaterials.value = res.data.materials || []
    } catch (e) {
      console.error('Failed to load materials:', e)
    }
  } else {
    loadDraft()
  }
})
</script>

<style scoped>
.profile-create {
  min-height: 100vh;
  background: var(--c-paper);
}

.navbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 32px;
  border-bottom: 1px solid var(--border, var(--c-line));
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
  gap: 14px;
}

.nav-mode-tag {
  font-size: 12px;
  font-weight: 600;
  padding: 4px 10px;
  background: var(--c-bg-subtle, #f0ede6);
  color: var(--c-ink-2);
  border: 1px solid var(--c-line-soft);
  border-radius: var(--r-sm);
}

.nav-back-btn {
  background: transparent;
  border: 1px solid var(--c-line-strong);
  color: var(--c-ink-2);
  padding: 6px 14px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  border-radius: var(--r-sm);
  transition: all 0.15s;
  font-family: inherit;
}

.nav-back-btn:hover {
  border-color: var(--c-ink);
  color: var(--c-ink);
}

.main-content {
  max-width: 860px;
  margin: 0 auto;
  padding: 32px 24px 96px;
}

.page-header {
  margin-bottom: 28px;
}

.page-header-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}

.page-title {
  font-size: 26px;
  font-weight: 700;
}

.draft-badge {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  background: var(--c-brand-tint, #fff8f5);
  border: 1px solid var(--c-brand);
  padding: 4px 10px;
  border-radius: var(--r-sm);
  color: var(--c-ink);
}

.draft-dot {
  color: var(--c-brand);
  font-size: 10px;
}

.draft-clear-btn {
  background: transparent;
  border: none;
  color: var(--c-ink-4);
  font-size: 12px;
  text-decoration: underline;
  cursor: pointer;
  padding: 0 2px;
  font-family: inherit;
}

.draft-clear-btn:hover {
  color: var(--a-aggressive);
}

.page-desc {
  margin-top: 8px;
  color: var(--c-ink-3);
  font-size: 14px;
  line-height: 1.6;
}

/* 表单卡片 */
.form-card {
  border: 1px solid var(--c-line);
  border-radius: var(--r-md);
  padding: 20px 24px;
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 18px;
}

.card-num {
  font-size: 12px;
  color: var(--c-brand);
  font-weight: 700;
}

.card-title {
  font-size: 15px;
  font-weight: 700;
}

.card-hint {
  font-size: 12px;
  color: var(--c-ink-4);
  margin-left: auto;
}

.field-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px 20px;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 12px;
}

.field.inline {
  margin-bottom: 0;
}

.field label {
  font-size: 12px;
  color: var(--c-ink-3);
  font-weight: 600;
}

.field input[type='text'],
.field select,
.field textarea {
  border: 1px solid var(--c-line-strong);
  padding: 8px 10px;
  font-size: 14px;
  font-family: inherit;
  border-radius: var(--r-sm);
  background: var(--c-bg-softer);
  outline: none;
  transition: border-color 0.15s;
}

.field input:focus,
.field select:focus,
.field textarea:focus {
  border-color: var(--c-brand);
  background: var(--c-paper);
}

.field textarea {
  resize: vertical;
  line-height: 1.6;
}

.checkbox-row {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: var(--c-ink-3);
  cursor: pointer;
}

/* 大五滑块 */
.big5-sliders {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 14px 16px;
  background: var(--c-bg-softer, #FAF9F6);
  border: 1px dashed var(--c-line-strong);
  border-radius: var(--r-sm);
  margin-top: 8px;
}

.slider-row {
  display: flex;
  align-items: center;
  gap: 14px;
}

.slider-label {
  width: 190px;
  min-width: 190px;
  flex-shrink: 0;
  font-size: 13px;
  font-weight: 600;
  color: var(--c-ink);
  white-space: nowrap;
}

.slider-row input[type='range'] {
  flex: 1;
  accent-color: var(--c-brand);
  cursor: pointer;
}

.slider-value {
  width: 24px;
  min-width: 24px;
  text-align: right;
  font-size: 14px;
  font-weight: 700;
  font-family: var(--font-mono, monospace);
  color: var(--c-brand);
}

/* 标签 */
.tag-cloud {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 10px;
}

.tag-chip {
  border: 1px solid var(--c-line-strong);
  background: var(--c-bg-softer);
  padding: 5px 12px;
  font-size: 13px;
  border-radius: var(--r-lg);
  cursor: pointer;
  font-family: inherit;
  transition: all 0.15s;
}

.tag-chip:hover {
  border-color: var(--c-brand);
}

.tag-chip.active {
  background: var(--c-ink);
  color: var(--c-paper);
  border-color: var(--c-ink);
}

.tag-input-row {
  display: flex;
  gap: 8px;
}

.tag-input-row input {
  flex: 1;
  border: 1px solid var(--c-line-strong);
  padding: 7px 10px;
  font-size: 13px;
  font-family: inherit;
  border-radius: var(--r-sm);
  outline: none;
}

.tag-input-row input:focus {
  border-color: var(--c-brand);
}

/* 动态行 */
.dynamic-rows {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-bottom: 10px;
}

.dynamic-row {
  display: flex;
  gap: 8px;
  align-items: center;
}

.dynamic-row input[type='text'],
.dynamic-row select {
  border: 1px solid var(--c-line-strong);
  padding: 7px 10px;
  font-size: 13px;
  font-family: inherit;
  border-radius: var(--r-sm);
  background: var(--c-bg-softer);
  outline: none;
}

.dynamic-row .grow {
  flex: 1;
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
  border-color: var(--c-ink);
  transform: translate(0, 0);
  box-shadow: none;
}

.btn-mini.danger {
  border-color: var(--c-line-strong);
  color: var(--c-ink-4);
  padding: 6px 10px;
}

.btn-mini.danger:hover {
  border-color: var(--a-aggressive);
  color: var(--a-aggressive);
  background: #ffebee;
  box-shadow: 2px 2px 0 var(--a-aggressive);
  transform: translate(-1px, -1px);
}

/* 自由资料 */
.materials-controls {
  display: flex;
  gap: 20px;
  margin-bottom: 12px;
}

.materials-controls .field {
  flex: 1;
}

.upload-zone {
  border: 1px dashed var(--c-line-strong);
  border-radius: var(--r-md);
  padding: 24px 20px;
  text-align: center;
  cursor: pointer;
  transition: all 0.15s ease;
  background: var(--c-bg-softer, #FAF9F6);
  margin-bottom: 12px;
}

.upload-zone:hover,
.upload-zone.drag-over {
  border-color: var(--c-brand);
  background: #FFFDF9;
  box-shadow: var(--shadow-pop-sm);
}

.upload-icon-symbol {
  font-size: 16px;
  color: var(--c-brand);
  margin-bottom: 6px;
}

.upload-main {
  font-size: 14px;
  font-weight: 700;
  color: var(--c-ink);
}

.upload-sub {
  font-size: 12px;
  color: var(--c-ink-4);
  margin-top: 4px;
}

.format-badges {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  justify-content: center;
  margin-top: 14px;
}

.fmt-pill {
  font-size: 11px;
  font-family: var(--font-mono, monospace);
  padding: 3px 8px;
  border-radius: var(--r-sm);
  border: 1px solid var(--c-line-strong);
  background: var(--c-paper);
  color: var(--c-ink-2);
  letter-spacing: 0.3px;
}

.file-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-top: 8px;
}

.file-item {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 13px;
  padding: 8px 12px;
  border: 1px solid var(--c-line-strong);
  border-radius: var(--r-sm);
  background: var(--c-paper);
}

.file-badge {
  font-size: 10px;
  font-family: var(--font-mono, monospace);
  font-weight: 700;
  padding: 2px 6px;
  border-radius: var(--r-sm);
  border: 1px solid var(--c-ink);
  background: var(--c-paper);
  letter-spacing: 0.5px;
}

.file-badge.badge-word {
  background: #EBF3FF;
  color: #1A56DB;
  border-color: #1A56DB;
}

.file-badge.badge-pdf {
  background: #FDF2F2;
  color: #E02424;
  border-color: #E02424;
}

.file-badge.badge-excel {
  background: #EDFDF5;
  color: #057A55;
  border-color: #057A55;
}

.file-badge.badge-ppt {
  background: #FFF8F1;
  color: #D03801;
  border-color: #D03801;
}

.file-badge.badge-img {
  background: #F6F5FF;
  color: #6C2BD9;
  border-color: #6C2BD9;
}

.file-badge.badge-text {
  background: var(--c-bg-softer);
  color: var(--c-ink-2);
  border-color: var(--c-line-strong);
}

.file-name {
  flex: 1;
}

.file-size {
  color: var(--c-ink-4);
  font-size: 12px;
}

.mat-type {
  font-weight: 600;
}

.existing-materials {
  margin-top: 16px;
  padding-top: 14px;
  border-top: 1px dashed var(--c-line-soft);
}

.existing-header {
  font-size: 12px;
  color: var(--c-ink-4);
  margin-bottom: 8px;
  font-weight: 600;
}

.textarea-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}

.char-count {
  font-size: 12px;
  color: var(--c-brand);
  font-weight: 600;
  font-family: var(--font-mono, monospace);
}

/* 提交栏（粘性吸底） */
.submit-bar {
  position: sticky;
  bottom: 0;
  background: var(--c-paper);
  border-top: 1px solid var(--c-line);
  padding: 16px 24px;
  margin-top: 36px;
  margin-left: -24px;
  margin-right: -24px;
  margin-bottom: -96px;
  display: flex;
  flex-direction: row;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  box-shadow: 0 -4px 16px rgba(0, 0, 0, 0.04);
  z-index: 9;
}

.submit-warn {
  font-size: 13px;
  color: var(--c-ink-4);
  margin: 0;
}

.submit-btn {
  background: var(--c-brand);
  color: var(--c-paper);
  border: 1px solid var(--c-brand);
  padding: 12px 36px;
  font-size: 15px;
  font-weight: 700;
  cursor: pointer;
  border-radius: var(--r-sm);
  font-family: inherit;
  transition: all var(--dur-fast);
  white-space: nowrap;
}

.submit-btn:hover:not(:disabled) {
  background: var(--c-brand-deep);
  border-color: var(--c-brand-deep);
  box-shadow: var(--shadow-pop-sm);
  transform: translate(-1px, -1px);
}

.submit-btn:active:not(:disabled) {
  transform: translate(1px, 1px);
  box-shadow: 1px 1px 0 var(--c-ink);
}

.submit-btn:disabled {
  background: var(--c-bg-soft);
  border-color: var(--c-line);
  color: var(--c-ink-5);
  cursor: not-allowed;
  transform: none;
  box-shadow: none;
}

/* 进度态 */
.progress-content {
  display: flex;
  justify-content: center;
  padding-top: 80px;
}

.progress-card {
  width: 100%;
  max-width: 560px;
  border: 1px solid var(--c-line);
  border-radius: var(--r-md);
  padding: 32px;
}

.progress-steps {
  display: flex;
  justify-content: space-between;
  margin-bottom: 28px;
}

.progress-step {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  flex: 1;
}

.step-marker {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  border: 1px solid var(--c-ink-5);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  color: var(--c-ink-4);
}

.progress-step.active .step-marker {
  border-color: var(--c-brand);
  color: var(--c-brand);
  font-weight: 700;
}

.progress-step.done .step-marker {
  background: var(--c-ink);
  border-color: var(--c-ink);
  color: var(--c-paper);
}

.step-name {
  font-size: 12px;
  color: var(--c-ink-4);
}

.progress-step.active .step-name {
  color: var(--c-ink);
  font-weight: 600;
}

.progress-bar-track {
  height: 4px;
  background: #F0F0F0;
  border-radius: var(--r-sm);
  overflow: hidden;
}

.progress-bar-fill {
  height: 100%;
  background: var(--c-brand);
  transition: width 0.6s ease;
}

.progress-message {
  margin-top: 18px;
  text-align: center;
  font-size: 14px;
  color: var(--c-ink-3);
  min-height: 20px;
}

.error-box {
  margin-top: 20px;
  border: 1px solid #FFD5CC;
  background: #FFF8F6;
  border-radius: var(--r-md);
  padding: 16px;
}

.error-title {
  color: var(--c-brand);
  font-weight: 700;
  font-size: 14px;
  margin-bottom: 8px;
}

.error-detail {
  font-size: 12px;
  color: var(--c-ink-3);
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 160px;
  overflow-y: auto;
  margin-bottom: 12px;
  font-family: inherit;
}

@media (max-width: 640px) {
  .field-grid,
  .materials-controls {
    grid-template-columns: 1fr;
    flex-direction: column;
  }
}
</style>
