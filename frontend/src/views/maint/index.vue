<template>
  <section class="page" data-module="maint">
    <header class="page-head">
      <div>
        <h2>维保工单管理</h2>
        <p class="page-desc">维护维保工单，围绕工单编号、关联设备、故障现象、紧急程度做登记、筛选与状态流转。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记维保工单</button>
        <button class="btn" type="button" @click="exportRows">导出维保工单清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="reload">
      <label v-for="field in filterFields" :key="field" class="filter-item">
        <span>{{ field }}</span>
        <input v-model="filters[field]" :placeholder="`按${field}检索`" />
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>工单状态</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td v-for="column in columns" :key="column">{{ row[column] ?? '—' }}</td>
          <td>{{ row.status ?? '—' }}</td>
          <td class="row-actions">
            <button class="link" type="button" @click="openDetail(row)">查看详情</button>
            <button
              v-for="action in allowedActions(row.status)"
              :key="action"
              class="link"
              type="button"
              @click="openDetail(row, action)"
            >
              {{ action }}
            </button>
            <span v-if="!allowedActions(row.status).length" class="muted-text">—</span>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 2" class="empty-state">暂无维保工单数据，可先登记维保工单</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条维保工单记录</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>

    <div v-if="detailVisible" class="modal-mask" @click.self="closeDetail">
      <div class="modal-panel">
        <div class="modal-head">
          <h3>维保工单详情{{ pendingAction ? `·${pendingAction}` : '' }}</h3>
          <button class="link" type="button" @click="closeDetail">关闭</button>
        </div>
        <div v-if="detailLoading" class="modal-body muted-text">工单明细加载中…</div>
        <form v-else class="modal-body" @submit.prevent="handleSubmit">
          <label class="form-item">
            <span>工单编号</span>
            <input v-model="detailForm['工单编号']" disabled />
          </label>
          <label class="form-item">
            <span>关联设备</span>
            <input v-model="detailForm['关联设备']" disabled />
          </label>
          <label class="form-item form-item-wide">
            <span>故障现象</span>
            <input v-model="detailForm['故障现象']" disabled />
          </label>
          <label class="form-item">
            <span>紧急程度</span>
            <select v-model="detailForm['紧急程度']">
              <option value="" disabled>请选择紧急程度</option>
              <option v-for="level in urgencyOptions" :key="level" :value="level">{{ level }}</option>
            </select>
          </label>
          <label class="form-item">
            <span>报修人</span>
            <input v-model="detailForm['报修人']" placeholder="请输入报修人" />
          </label>
          <label class="form-item">
            <span>受理班组</span>
            <input v-model="detailForm['受理班组']" placeholder="请输入受理班组" />
          </label>
          <label class="form-item">
            <span>期望完成时间</span>
            <input v-model="detailForm['期望完成时间']" type="date" />
          </label>
          <div class="form-item form-item-wide form-readonly">
            <span>工单状态</span>
            <strong>{{ detailForm.status }}</strong>
          </div>
          <p v-if="detailError" class="error-text">{{ detailError }}</p>
          <div class="modal-foot">
            <button class="btn ghost" type="button" @click="closeDetail">取消</button>
            <button
              v-for="action in detailActions"
              :key="action"
              class="btn primary"
              type="button"
              :disabled="detailSubmitting"
              @click="submitAction(action)"
            >
              {{ action }}
            </button>
            <span v-if="!detailActions.length" class="muted-text">该工单已无可执行动作</span>
          </div>
        </form>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, string | number | boolean | null>

interface ActionResponse {
  ok: boolean
  message: string
  entry?: Row | null
}

const ENDPOINT = '/api/maint'
const columns = ["工单编号", "关联设备", "故障现象", "紧急程度", "报修人", "受理班组", "期望完成时间"]
// 各状态下允许的动作：受理后才能派工，派工后进入待验收才能关闭，已关闭不再出现任何动作。
const STATUS_ACTIONS: Record<string, string[]> = {
  "待受理": ["受理工单"],
  "处理中": ["派工处理"],
  "待验收": ["关闭工单"],
  "已关闭": [],
}
const urgencyLevels = ["一般", "紧急", "特急"]
const stats = [{"label": "待受理工单", "value": 0}, {"label": "超时工单", "value": 0}, {"label": "平均处理时长", "value": 0}]

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const filters = ref<Record<string, string>>({})
const filterFields = columns.slice(0, 3)

const detailVisible = ref(false)
const detailLoading = ref(false)
const detailSubmitting = ref(false)
const detailError = ref('')
const detailForm = ref<Row>({})
const pendingAction = ref('')

// 详情页底部动作同样按当前状态收敛：已关闭工单不再冒出任何动作按钮。
const detailActions = computed(() => allowedActions(detailForm.value.status))

// 已有的紧急程度若是历史值（不在标准选项里），也要原样保留在下拉中，
// 避免打开详情时紧急程度显示成空/默认值。
const urgencyOptions = computed(() => {
  const current = String(detailForm.value['紧急程度'] ?? '').trim()
  return current && !urgencyLevels.includes(current) ? [current, ...urgencyLevels] : urgencyLevels
})

function allowedActions(status: unknown): string[] {
  return STATUS_ACTIONS[String(status)] ?? []
}

function handleSubmit() {
  void submitAction()
}

function resetFilters() {
  filters.value = {}
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function openCreate() {
  errorMessage.value = '维保工单登记入口尚未接入审批流'
}

async function openDetail(row: Row, action = '') {
  pendingAction.value = action
  detailVisible.value = true
  detailLoading.value = true
  detailError.value = ''
  detailForm.value = {}
  try {
    const response = await request(`${ENDPOINT}/${row.id}`)
    if (!response.ok) {
      throw new Error(`维保工单详情读取失败（${response.status}）`)
    }
    // 详情页必须用后端返回的最新数据回填，避免紧急程度落回默认值、期望完成时间丢失。
    detailForm.value = await response.json()
  } catch (error) {
    detailError.value = error instanceof Error ? error.message : '维保工单详情读取失败'
  } finally {
    detailLoading.value = false
  }
}

function closeDetail() {
  if (detailSubmitting.value) {
    return
  }
  detailVisible.value = false
  pendingAction.value = ''
  detailError.value = ''
}

async function submitAction(action?: string) {
  const chosen = action ?? pendingAction.value
  if (!chosen) {
    detailError.value = '请先选择要执行的动作'
    return
  }
  detailSubmitting.value = true
  detailError.value = ''
  const body: Row = { action: chosen }
  for (const field of ["紧急程度", "报修人", "受理班组", "期望完成时间"]) {
    const value = detailForm.value[field]
    if (value !== null && value !== undefined && String(value).trim() !== '') {
      body[field] = value
    }
  }
  try {
    const response = await request(`${ENDPOINT}/${detailForm.value.id}/actions`, {
      method: 'POST',
      body: JSON.stringify(body),
    })
    const payload = await response.json().catch(() => null) as ActionResponse | null
    if (!response.ok || !payload?.ok) {
      throw new Error(payload?.message || '维保工单动作未生效，请稍后重试')
    }
    if (payload.entry) {
      // 用后端回写后的工单刷新详情，保证再次进入时字段与列表、详情一致。
      detailForm.value = payload.entry
    }
    pendingAction.value = ''
    await reload()
    if (String(detailForm.value.status) === "已关闭") {
      detailVisible.value = false
    }
  } catch (error) {
    detailError.value = error instanceof Error ? error.message : '维保工单操作失败'
  } finally {
    detailSubmitting.value = false
  }
}

async function reload() {
  errorMessage.value = ''
  const query = new URLSearchParams(filters.value as Record<string, string>).toString()
  try {
    const response = await request(`${ENDPOINT}?${query}`)
    if (!response.ok) {
      throw new Error('维保工单列表读取失败')
    }
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '维保工单列表读取失败'
  }
}

onMounted(reload)
</script>

<style scoped>
.muted-text {
  color: var(--muted);
  font-size: 12px;
}

.modal-mask {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 20;
}

.modal-panel {
  width: 640px;
  max-width: calc(100vw - 32px);
  max-height: calc(100vh - 64px);
  overflow: auto;
  background: #fff;
  border-radius: 10px;
  box-shadow: 0 12px 32px rgba(15, 23, 42, 0.2);
}

.modal-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 18px;
  border-bottom: 1px solid var(--border);
}

.modal-head h3 {
  margin: 0;
  font-size: 15px;
}

.modal-body {
  display: flex;
  flex-wrap: wrap;
  gap: 12px 16px;
  padding: 16px 18px;
}

.form-item {
  flex: 1 1 calc(50% - 16px);
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 12px;
  color: var(--muted);
}

.form-item-wide {
  flex-basis: 100%;
}

.form-item input,
.form-item select {
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 6px 8px;
  font-size: 13px;
  color: #1f2937;
}

.form-item input:disabled {
  background: #f1f5f9;
}

.form-readonly {
  flex-direction: row;
  align-items: center;
  gap: 8px;
}

.modal-foot {
  flex-basis: 100%;
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: 8px;
  margin-top: 4px;
}
</style>
