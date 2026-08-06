<template>
  <AdminLayout>
    <PageFrame
      variant="soft"
      :eyebrow="t('adminPages.gitlabOperationRecords.eyebrow')"
      :title="t('adminPages.gitlabOperationRecords.title')"
      :subtitle="t('adminPages.gitlabOperationRecords.subtitle')"
    >
      <AdminListSection>
        <template #filters>
          <div class="admin-filter-grid">
            <div class="admin-filter-field">
              <label class="admin-filter-label">
                {{ t('adminPages.gitlabOperationRecords.action') }}
              </label>
              <select
                v-model="filters.action"
                class="admin-filter-control min-w-[14rem]"
                @change="handleFilterChange"
              >
                <option value="">
                  {{ t('adminPages.gitlabOperationRecords.actionAll') }}
                </option>
                <option
                  v-for="option in actionOptions"
                  :key="option.value"
                  :value="option.value"
                >
                  {{ option.label }}
                </option>
              </select>
            </div>
            <div class="admin-filter-field">
              <label class="admin-filter-label">
                {{ t('adminPages.gitlabOperationRecords.result') }}
              </label>
              <select
                v-model="filters.status"
                class="admin-filter-control min-w-[12rem]"
                @change="handleFilterChange"
              >
                <option value="">
                  {{ t('adminPages.gitlabOperationRecords.statusAll') }}
                </option>
                <option value="success">
                  {{ t('adminPages.gitlabOperationRecords.success') }}
                </option>
                <option value="partial_success">
                  {{ t('adminPages.gitlabOperationRecords.partialSuccess') }}
                </option>
                <option value="failed">
                  {{ t('adminPages.gitlabOperationRecords.failed') }}
                </option>
              </select>
            </div>
          </div>
          <div class="admin-toolbar-end">
            <span class="admin-summary-pill">
              {{
                t('adminPages.gitlabOperationRecords.summaryCount', {
                  count: totalCount
                })
              }}
            </span>
            <BaseButton
              variant="secondary"
              :loading="loading"
              @click="loadRecords"
            >
              {{ t('common.refresh') }}
            </BaseButton>
          </div>
        </template>

        <AdminTable v-if="records.length">
          <thead>
            <tr>
              <th class="admin-table-head">
                {{ t('adminPages.gitlabOperationRecords.action') }}
              </th>
              <th class="admin-table-head">
                {{ t('adminPages.gitlabOperationRecords.result') }}
              </th>
              <th class="admin-table-head">
                {{ t('adminPages.gitlabOperationRecords.target') }}
              </th>
              <th class="admin-table-head">
                {{ t('adminPages.gitlabOperationRecords.actor') }}
              </th>
              <th class="admin-table-head">
                {{ t('adminPages.gitlabOperationRecords.time') }}
              </th>
              <th class="admin-table-head">
                {{ t('common.actions') }}
              </th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="record in records"
              :key="record.id"
              class="admin-table-row"
            >
              <td class="admin-table-cell">
                <div class="font-semibold text-slate-900">
                  {{ record.action_label || record.action }}
                </div>
                <div class="mt-1 font-mono text-xs text-slate-400">
                  {{ record.action || t('common.emptyValue') }}
                </div>
              </td>
              <td class="admin-table-cell">
                <span
                  class="admin-status-badge"
                  :class="statusClass(record.status)"
                >
                  {{ statusLabel(record.status) }}
                </span>
                <div class="mt-2 flex flex-wrap gap-2 text-xs text-slate-500">
                  <span>
                    {{
                      t('adminPages.gitlabOperationRecords.successCount', {
                        count: record.success_count || 0
                      })
                    }}
                  </span>
                  <span>
                    {{
                      t('adminPages.gitlabOperationRecords.failedCount', {
                        count: record.failed_count || 0
                      })
                    }}
                  </span>
                </div>
              </td>
              <td class="admin-table-cell">
                <div class="max-w-md text-sm font-medium text-slate-800">
                  {{ targetTitle(record) }}
                </div>
                <div class="mt-2 flex max-w-lg flex-wrap gap-2">
                  <span
                    v-if="record.instance_name"
                    class="admin-operation-chip"
                  >
                    {{ record.instance_name }}
                  </span>
                  <span
                    v-if="record.project_path"
                    class="admin-operation-chip admin-operation-chip--mono"
                  >
                    {{ record.project_path }}
                  </span>
                </div>
              </td>
              <td class="admin-table-cell text-sm text-slate-600">
                {{ record.actor_name || t('common.emptyValue') }}
              </td>
              <td class="admin-table-cell text-sm text-slate-500">
                <div>
                  {{ formatDateTime(record.finished_at || record.started_at) }}
                </div>
                <div
                  v-if="record.finished_at && record.started_at"
                  class="mt-1 text-xs text-slate-400"
                >
                  {{ t('adminPages.gitlabOperationRecords.startedAt') }}:
                  {{ formatDateTime(record.started_at) }}
                </div>
              </td>
              <td class="admin-table-cell">
                <BaseButton
                  variant="secondary"
                  size="sm"
                  @click="openDetail(record)"
                >
                  {{ t('adminPages.gitlabOperationRecords.detail') }}
                </BaseButton>
              </td>
            </tr>
          </tbody>
        </AdminTable>

        <PaginationBar
          v-if="records.length"
          variant="admin"
          :current-page="currentPage"
          :page-size="pageSize"
          :total-count="totalCount"
          @update:page-size="handlePageSizeChange"
          @prev="goPrevPage"
          @next="goNextPage"
        />

        <EmptyState
          v-if="!loading && !records.length"
          variant="admin"
          :title="t('adminPages.gitlabOperationRecords.emptyTitle')"
          :description="t('adminPages.gitlabOperationRecords.emptySubtitle')"
        />
      </AdminListSection>

      <BaseModal
        :show="Boolean(selectedRecord)"
        size="xl"
        :title="t('adminPages.gitlabOperationRecords.detail')"
        @close="selectedRecord = null"
      >
        <div v-if="selectedRecord" class="space-y-5">
          <section class="grid gap-3 md:grid-cols-3">
            <div class="admin-modal-card-muted">
              <p
                class="text-xs font-semibold uppercase tracking-wide text-slate-400"
              >
                {{ t('adminPages.gitlabOperationRecords.action') }}
              </p>
              <p class="mt-2 font-semibold text-slate-900">
                {{ selectedRecord.action_label || selectedRecord.action }}
              </p>
            </div>
            <div class="admin-modal-card-muted">
              <p
                class="text-xs font-semibold uppercase tracking-wide text-slate-400"
              >
                {{ t('adminPages.gitlabOperationRecords.result') }}
              </p>
              <p class="mt-2 font-semibold text-slate-900">
                {{ statusLabel(selectedRecord.status) }}
              </p>
            </div>
            <div class="admin-modal-card-muted">
              <p
                class="text-xs font-semibold uppercase tracking-wide text-slate-400"
              >
                {{ t('adminPages.gitlabOperationRecords.actor') }}
              </p>
              <p class="mt-2 font-semibold text-slate-900">
                {{ selectedRecord.actor_name || t('common.emptyValue') }}
              </p>
            </div>
            <div class="admin-modal-card-muted">
              <p
                class="text-xs font-semibold uppercase tracking-wide text-slate-400"
              >
                {{ t('adminPages.gitlabOperationRecords.target') }}
              </p>
              <p class="mt-2 font-semibold text-slate-900">
                {{ targetTitle(selectedRecord) }}
              </p>
            </div>
          </section>

          <section class="grid gap-4 lg:grid-cols-2">
            <article class="admin-modal-card">
              <h3 class="admin-bulk-title">
                {{ t('adminPages.gitlabOperationRecords.requestData') }}
              </h3>
              <p class="admin-operation-summary-copy">
                {{ t('adminPages.gitlabOperationRecords.requestSummary') }}
              </p>
              <dl class="admin-operation-summary-list">
                <template
                  v-for="item in summarizePayload(selectedRecord.request_data)"
                  :key="`request-${item.label}`"
                >
                  <dt>{{ item.label }}</dt>
                  <dd>{{ item.value }}</dd>
                </template>
              </dl>
              <details class="admin-operation-json-details">
                <summary>
                  {{ t('adminPages.gitlabOperationRecords.viewRawJson') }}
                </summary>
                <pre class="admin-operation-json">{{
                  prettyJson(selectedRecord.request_data)
                }}</pre>
              </details>
            </article>
            <article class="admin-modal-card">
              <h3 class="admin-bulk-title">
                {{ t('adminPages.gitlabOperationRecords.resultData') }}
              </h3>
              <p class="admin-operation-summary-copy">
                {{ t('adminPages.gitlabOperationRecords.resultSummary') }}
              </p>
              <dl class="admin-operation-summary-list">
                <template
                  v-for="item in summarizePayload(selectedRecord.result_data)"
                  :key="`result-${item.label}`"
                >
                  <dt>{{ item.label }}</dt>
                  <dd>{{ item.value }}</dd>
                </template>
              </dl>
              <details class="admin-operation-json-details">
                <summary>
                  {{ t('adminPages.gitlabOperationRecords.viewRawJson') }}
                </summary>
                <pre class="admin-operation-json">{{
                  prettyJson(selectedRecord.result_data)
                }}</pre>
              </details>
            </article>
          </section>
        </div>
        <template #footer>
          <div class="flex w-full justify-end">
            <BaseButton variant="secondary" @click="selectedRecord = null">
              {{ t('common.cancel') }}
            </BaseButton>
          </div>
        </template>
      </BaseModal>
    </PageFrame>
  </AdminLayout>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import AdminListSection from '@/admin/components/AdminListSection.vue'
import AdminTable from '@/admin/components/AdminTable.vue'
import AdminLayout from '@/admin/layout/AdminLayout.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseModal from '@/components/ui/BaseModal.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import PageFrame from '@/components/ui/PageFrame.vue'
import PaginationBar from '@/components/ui/PaginationBar.vue'
import gitlabApi from '@/api/gitlab'
import { useToast } from '@/composables/useToast'

const { t } = useI18n()
const { showToast } = useToast()

const loading = ref(false)
const records = ref([])
const totalCount = ref(0)
const currentPage = ref(1)
const pageSize = ref(20)
const selectedRecord = ref(null)
const filters = ref({
  action: '',
  status: ''
})
const actionOptions = computed(() => [
  {
    value: 'collect_projects',
    label: t('adminPages.gitlabOperationRecords.actions.collectProjects')
  },
  {
    value: 'collect_resources',
    label: t('adminPages.gitlabOperationRecords.actions.collectResources')
  },
  {
    value: 'branch_create',
    label: t('adminPages.gitlabOperationRecords.actions.branchCreate')
  },
  {
    value: 'branch_delete',
    label: t('adminPages.gitlabOperationRecords.actions.branchDelete')
  },
  {
    value: 'branch_protect',
    label: t('adminPages.gitlabOperationRecords.actions.branchProtect')
  },
  {
    value: 'branch_unprotect',
    label: t('adminPages.gitlabOperationRecords.actions.branchUnprotect')
  },
  {
    value: 'tag_create',
    label: t('adminPages.gitlabOperationRecords.actions.tagCreate')
  },
  {
    value: 'tag_delete',
    label: t('adminPages.gitlabOperationRecords.actions.tagDelete')
  },
  {
    value: 'webhook_create',
    label: t('adminPages.gitlabOperationRecords.actions.webhookCreate')
  },
  {
    value: 'webhook_update',
    label: t('adminPages.gitlabOperationRecords.actions.webhookUpdate')
  },
  {
    value: 'webhook_delete',
    label: t('adminPages.gitlabOperationRecords.actions.webhookDelete')
  }
])

function normalizeCollection(data) {
  return Array.isArray(data) ? data : (data?.results ?? [])
}

async function loadRecords() {
  loading.value = true
  try {
    const data = await gitlabApi.listOperationRecords({
      page: currentPage.value,
      page_size: pageSize.value,
      action: filters.value.action,
      status: filters.value.status
    })
    records.value = normalizeCollection(data)
    totalCount.value = Array.isArray(data)
      ? data.length
      : Number(data?.count ?? records.value.length)
  } catch (e) {
    records.value = []
    totalCount.value = 0
    showToast(
      t('adminPages.gitlabOperationRecords.toast.loadFailed', {
        message: e.message
      }),
      'error'
    )
  } finally {
    loading.value = false
  }
}

function handleFilterChange() {
  currentPage.value = 1
  loadRecords()
}

function handlePageSizeChange(size) {
  pageSize.value = size
  currentPage.value = 1
  loadRecords()
}

function goPrevPage() {
  if (currentPage.value <= 1) return
  currentPage.value -= 1
  loadRecords()
}

function goNextPage() {
  if (currentPage.value * pageSize.value >= totalCount.value) return
  currentPage.value += 1
  loadRecords()
}

function openDetail(record) {
  selectedRecord.value = record
}

function statusLabel(status) {
  if (status === 'success')
    return t('adminPages.gitlabOperationRecords.success')
  if (status === 'partial_success') {
    return t('adminPages.gitlabOperationRecords.partialSuccess')
  }
  if (status === 'failed') return t('adminPages.gitlabOperationRecords.failed')
  return t('adminPages.gitlabOperationRecords.unknown')
}

function statusClass(status) {
  if (status === 'success') return 'admin-status-badge--success'
  if (status === 'partial_success') return 'admin-status-badge--info'
  if (status === 'failed') return 'admin-status-badge--danger'
  return 'admin-status-badge--muted'
}

function targetTitle(record) {
  return (
    record.target_summary ||
    record.project_path ||
    record.instance_name ||
    t('common.emptyValue')
  )
}

function formatDateTime(value) {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat(undefined, {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  }).format(date)
}

function normalizePayload(value) {
  if (!value) return {}
  if (typeof value === 'string') {
    try {
      return JSON.parse(value)
    } catch {
      return { value }
    }
  }
  return value
}

function formatSummaryValue(value) {
  if (Array.isArray(value)) {
    if (!value.length) return t('adminPages.gitlabOperationRecords.emptyValue')
    const preview = value.slice(0, 3).map((item) => {
      if (item && typeof item === 'object') {
        return (
          item.name ||
          item.path ||
          item.full_path ||
          item.id ||
          JSON.stringify(item)
        )
      }
      return String(item)
    })
    const suffix =
      value.length > preview.length
        ? t('adminPages.gitlabOperationRecords.moreItems', {
            count: value.length - preview.length
          })
        : ''
    return [preview.join(', '), suffix].filter(Boolean).join(' ')
  }
  if (value && typeof value === 'object') {
    const keys = Object.keys(value)
    if (!keys.length) return t('adminPages.gitlabOperationRecords.emptyValue')
    return t('adminPages.gitlabOperationRecords.objectSummary', {
      count: keys.length
    })
  }
  if (value === null || value === undefined || value === '') {
    return t('adminPages.gitlabOperationRecords.emptyValue')
  }
  return String(value)
}

function summarizePayload(value) {
  const payload = normalizePayload(value)
  if (!payload || typeof payload !== 'object' || Array.isArray(payload)) {
    return [
      {
        label: t('adminPages.gitlabOperationRecords.value'),
        value: formatSummaryValue(payload)
      }
    ]
  }

  const entries = Object.entries(payload).filter(([, entryValue]) => {
    return entryValue !== null && entryValue !== undefined && entryValue !== ''
  })

  if (!entries.length) {
    return [
      {
        label: t('adminPages.gitlabOperationRecords.noData'),
        value: t('adminPages.gitlabOperationRecords.emptyValue')
      }
    ]
  }

  return entries.slice(0, 6).map(([key, entryValue]) => ({
    label: key.replace(/_/g, ' '),
    value: formatSummaryValue(entryValue)
  }))
}

function prettyJson(value) {
  return JSON.stringify(normalizePayload(value), null, 2)
}

onMounted(loadRecords)
</script>

<style scoped>
.admin-operation-json {
  margin-top: 0.75rem;
  max-height: 20rem;
  overflow: auto;
  border-radius: 1rem;
  border: 1px solid rgba(148, 163, 184, 0.26);
  background: #0f172a;
  padding: 1rem;
  color: #dbeafe;
  font-size: 0.78rem;
  line-height: 1.6;
}

.admin-operation-chip {
  display: inline-flex;
  max-width: 18rem;
  align-items: center;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  border-radius: 999px;
  border: 1px solid rgba(203, 213, 225, 0.86);
  background: rgba(248, 250, 252, 0.92);
  padding: 0.25rem 0.6rem;
  font-size: 0.72rem;
  font-weight: 600;
  color: rgb(71 85 105);
}

.admin-operation-chip--mono {
  font-family:
    ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono',
    'Courier New', monospace;
}

.admin-operation-summary-copy {
  margin-top: 0.5rem;
  font-size: 0.82rem;
  line-height: 1.5;
  color: rgb(100 116 139);
}

.admin-operation-summary-list {
  margin-top: 0.85rem;
  display: grid;
  gap: 0.5rem;
}

.admin-operation-summary-list div,
.admin-operation-summary-list dt,
.admin-operation-summary-list dd {
  min-width: 0;
}

.admin-operation-summary-list dt {
  color: rgb(100 116 139);
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.admin-operation-summary-list dd {
  margin: 0.15rem 0 0;
  overflow-wrap: anywhere;
  border-radius: 0.75rem;
  background: rgb(248 250 252);
  padding: 0.55rem 0.7rem;
  color: rgb(15 23 42);
  font-size: 0.85rem;
  line-height: 1.5;
}

.admin-operation-json-details {
  margin-top: 1rem;
}

.admin-operation-json-details summary {
  cursor: pointer;
  color: rgb(37 99 235);
  font-size: 0.82rem;
  font-weight: 700;
}
</style>
