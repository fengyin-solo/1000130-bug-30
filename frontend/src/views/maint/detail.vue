<template>
  <section class="page detail-page" data-module="maint">
    <header class="page-head">
      <div>
        <h2>维保工单详情</h2>
        <p class="page-desc">查看并补充故障现象、紧急程度、期望完成时间等信息，按状态执行受理、派工与关闭。</p>
      </div>
      <div class="page-actions">
        <RouterLink class="btn" to="/maint">返回列表</RouterLink>
      </div>
    </header>

    <div v-if="notFound" class="empty-state card">未找到该维保工单，可能已归档。</div>

    <template v-else-if="entry">
      <div class="card">
        <div class="detail-summary">
          <span class="field-label">工单编号</span>
          <strong>{{ entry['工单编号'] }}</strong>
          <span class="status-tag" :class="statusClass(entry.status)">{{ entry.status }}</span>
        </div>

        <form class="detail-form" @submit.prevent="saveFields">
          <label class="form-item">
            <span>关联设备</span>
            <input v-model="form['关联设备']" type="text" :disabled="readonly" />
          </label>
          <label class="form-item">
            <span>报修人</span>
            <input v-model="form['报修人']" type="text" :disabled="readonly" />
          </label>
          <label class="form-item">
            <span>受理班组</span>
            <select v-model="form['受理班组']" :disabled="readonly || entry.status !== '待受理'">
              <option value="" disabled>请选择受理班组</option>
              <option v-for="team in teams" :key="team" :value="team">{{ team }}</option>
            </select>
            <small v-if="entry.status !== '待受理'" class="form-hint">受理后班组归属固定，派工不再改动</small>
          </label>
          <label class="form-item">
            <span>紧急程度</span>
            <select v-model="form['紧急程度']" :disabled="readonly">
              <option value="" disabled>请选择紧急程度</option>
              <option v-for="level in urgencyLevels" :key="level" :value="level">{{ level }}</option>
            </select>
          </label>
          <label class="form-item">
            <span>期望完成时间</span>
            <input v-model="form['期望完成时间']" type="date" :disabled="readonly" />
          </label>
          <label class="form-item form-item-wide">
            <span>故障现象</span>
            <textarea v-model="form['故障现象']" rows="3" :disabled="readonly"></textarea>
          </label>

          <div class="form-foot">
            <button class="btn primary" type="submit" :disabled="readonly || saving">
              {{ saving ? '保存中…' : '保存字段' }}
            </button>
            <span v-if="readonly" class="form-hint">工单已关闭，字段不可修改</span>
          </div>
        </form>
      </div>

      <div class="card action-card">
        <h3>状态流转</h3>
        <div class="action-row">
          <button
            v-for="action in actions"
            :key="action.name"
            class="btn"
            :class="action.primary ? 'primary' : ''"
            type="button"
            :disabled="!action.enabled || busy"
            :title="action.enabled ? action.name : action.hint"
            @click="runAction(action.name)"
          >
            {{ action.name }}
          </button>
        </div>
        <ol class="status-flow">
          <li v-for="step in statuses" :key="step" :class="{ active: entry.status === step, done: isDone(step) }">
            {{ step }}
          </li>
        </ol>
      </div>
    </template>

    <footer class="page-foot">
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
      <span v-else-if="successMessage" class="success-text">{{ successMessage }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'

import { request } from '@/api/client'

type Entry = Record<string, string | number | boolean | null>

const route = useRoute()
const ENDPOINT = '/api/maint'
const entryId = String(route.params.id)

const editableFields = ['关联设备', '故障现象', '紧急程度', '报修人', '受理班组', '期望完成时间']
const urgencyLevels = ['低', '中', '高', '紧急']
const teams = ['制冷一班', '制冷二班', '电气一班', '电气二班', '机修班']
const statuses = ['待受理', '处理中', '待验收', '已关闭']
const ACTION_FROM: Record<string, string[]> = {
  '受理工单': ['待受理'],
  '派工处理': ['处理中'],
  '关闭工单': ['处理中', '待验收'],
}

const entry = ref<Entry | null>(null)
const notFound = ref(false)
const busy = ref(false)
const saving = ref(false)
const errorMessage = ref('')
const successMessage = ref('')
const form = reactive<Record<string, string>>(
  Object.fromEntries(editableFields.map((field) => [field, ''])),
)

const readonly = computed(() => String(entry.value?.status) === '已关闭')

const actions = computed(() =>
  (['受理工单', '派工处理', '关闭工单'] as const).map((name) => {
    const enabled = ACTION_FROM[name].includes(String(entry.value?.status))
    let hint = ''
    if (!enabled) {
      hint = readonly.value ? '工单已关闭，不能重复操作' : `当前为「${entry.value?.status}」状态，不能执行${name}`
    }
    return { name, enabled, hint, primary: name === '关闭工单' }
  }),
)

function statusClass(status: unknown): string {
  return {
    '待受理': 'status-pending',
    '处理中': 'status-doing',
    '待验收': 'status-checking',
    '已关闭': 'status-closed',
  }[String(status)] ?? ''
}

function isDone(step: string): boolean {
  return statuses.indexOf(String(entry.value?.status)) > statuses.indexOf(step)
}

function fillForm(data: Entry) {
  for (const field of editableFields) {
    form[field] = data[field] == null ? '' : String(data[field])
  }
}

async function loadEntry() {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${entryId}`)
    if (response.status === 404) {
      notFound.value = true
      return
    }
    if (!response.ok) {
      throw new Error('维保工单详情读取失败')
    }
    const data: Entry = await response.json()
    entry.value = data
    notFound.value = false
    fillForm(data)
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '维保工单详情读取失败'
  }
}

// 保存字段时只提交有值的字段；受理班组在非受理状态由后端保护，保持原有归属
function collectFields(): Record<string, string> {
  const values: Record<string, string> = {}
  for (const field of editableFields) {
    const value = form[field].trim()
    if (value) {
      values[field] = value
    }
  }
  return values
}

async function saveFields() {
  errorMessage.value = ''
  successMessage.value = ''
  saving.value = true
  try {
    const response = await request(`${ENDPOINT}/${entryId}`, {
      method: 'PATCH',
      body: JSON.stringify({ values: collectFields() }),
    })
    const payload = await response.json().catch(() => null) as { ok?: boolean; message?: string; entry?: Entry } | null
    if (!response.ok || !payload?.ok || !payload.entry) {
      throw new Error(payload?.message || '字段保存失败')
    }
    entry.value = payload.entry
    fillForm(payload.entry)
    successMessage.value = '字段已保存'
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '字段保存失败'
  } finally {
    saving.value = false
  }
}

async function runAction(actionName: string) {
  errorMessage.value = ''
  successMessage.value = ''
  busy.value = true
  try {
    // 动作同时带上当前表单字段一起回写，派工时后端会保留受理班组
    const response = await request(`${ENDPOINT}/${entryId}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values: { action: actionName, ...collectFields() } }),
    })
    const payload = await response.json().catch(() => null) as { ok?: boolean; message?: string; entry?: Entry } | null
    if (!response.ok || !payload?.ok || !payload.entry) {
      throw new Error(payload?.message || '维保工单动作未生效')
    }
    entry.value = payload.entry
    fillForm(payload.entry)
    successMessage.value = payload.message || '操作成功'
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '维保工单操作失败'
  } finally {
    busy.value = false
  }
}

onMounted(loadEntry)
</script>

<style scoped>
.card {
  background: #fff;
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 12px;
}
.detail-summary {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 14px;
}
.status-tag {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 12px;
  border: 1px solid var(--border);
}
.status-pending { color: #b54708; background: #fffaeb; border-color: #fedf89; }
.status-doing { color: #175cd3; background: #eff8ff; border-color: #b2ddff; }
.status-checking { color: #b93816; background: #fff4ed; border-color: #f9dbaf; }
.status-closed { color: #475467; background: #f2f4f7; border-color: #d0d5dd; }
.detail-form {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px 16px;
}
.form-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 13px;
}
.form-item span {
  color: var(--muted);
  font-size: 12px;
}
.form-item input,
.form-item select,
.form-item textarea {
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 6px 8px;
  font: inherit;
}
.form-item-wide {
  grid-column: 1 / -1;
}
.form-item input:disabled,
.form-item select:disabled,
.form-item textarea:disabled {
  background: #f9fafb;
  color: #667085;
}
.form-hint {
  color: var(--muted);
  font-size: 12px;
}
.form-foot {
  grid-column: 1 / -1;
  display: flex;
  align-items: center;
  gap: 10px;
}
.action-card h3 {
  margin: 0 0 10px;
  font-size: 14px;
}
.action-row {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}
.btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}
.status-flow {
  display: flex;
  gap: 8px;
  list-style: none;
  margin: 0;
  padding: 0;
}
.status-flow li {
  flex: 1;
  text-align: center;
  font-size: 12px;
  color: var(--muted);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 6px 0;
}
.status-flow li.done {
  color: #175cd3;
  border-color: #b2ddff;
  background: #eff8ff;
}
.status-flow li.active {
  color: #fff;
  border-color: var(--brand);
  background: var(--brand);
}
.success-text {
  color: #027a48;
}
</style>
