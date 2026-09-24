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
      <label class="filter-item">
        <span>工单状态</span>
        <select v-model="filters.status">
          <option value="">全部状态</option>
          <option v-for="status in statuses" :key="status" :value="status">{{ status }}</option>
        </select>
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
          <td v-for="column in columns" :key="column">
            <RouterLink v-if="column === '工单编号'" class="link" :to="`/maint/${row.id}`">
              {{ row[column] ?? '—' }}
            </RouterLink>
            <template v-else>{{ row[column] ?? '—' }}</template>
          </td>
          <td>
            <span class="status-tag" :class="statusClass(row.status)">{{ row.status ?? '—' }}</span>
          </td>
          <td class="row-actions">
            <button
              v-for="action in actions"
              :key="action"
              class="link"
              type="button"
              :disabled="!canRun(action, row)"
              :title="canRun(action, row) ? action : actionHint(action, row)"
              @click="runAction(action, row)"
            >
              {{ action }}
            </button>
            <RouterLink class="link" :to="`/maint/${row.id}`">详情</RouterLink>
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
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, string | number | null>

const ENDPOINT = '/api/maint'
const columns = ["工单编号", "关联设备", "故障现象", "紧急程度", "报修人", "受理班组", "期望完成时间"]
const actions = ["受理工单", "派工处理", "关闭工单"]
const statuses = ["待受理", "处理中", "待验收", "已关闭"]
// 与后端状态机保持一致：只在工单当前状态允许时给出可点击入口
const ACTION_FROM: Record<string, string[]> = {
  '受理工单': ['待受理'],
  '派工处理': ['处理中'],
  '关闭工单': ['处理中', '待验收'],
}
const stats = [{"label": "待受理工单", "value": 0}, {"label": "超时工单", "value": 0}, {"label": "平均处理时长", "value": 0}]

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const filters = ref<Record<string, string>>({})
const filterFields = columns.slice(0, 3)

function canRun(action: string, row: Row): boolean {
  return ACTION_FROM[action].includes(String(row.status))
}

function actionHint(action: string, row: Row): string {
  if (String(row.status) === '已关闭') {
    return '工单已关闭，不能重复操作'
  }
  return `当前为「${row.status}」状态，不能执行${action}`
}

function statusClass(status: unknown): string {
  return {
    '待受理': 'status-pending',
    '处理中': 'status-doing',
    '待验收': 'status-checking',
    '已关闭': 'status-closed',
  }[String(status)] ?? ''
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

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  if (!canRun(action, row)) {
    errorMessage.value = actionHint(action, row)
    return
  }
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values: { action } }),
    })
    const payload = await response.json().catch(() => null) as { ok?: boolean; message?: string } | null
    if (!response.ok || !payload?.ok) {
      throw new Error(payload?.message || '维保工单动作未生效，请稍后重试')
    }
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '维保工单操作失败'
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
.page-actions {
  display: flex;
  gap: 8px;
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
.row-actions .link:disabled {
  color: #98a2b3;
  cursor: not-allowed;
}
</style>
