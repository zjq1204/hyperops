<template>
  <AdminLayout>
    <PageFrame
      variant="soft"
      :title="t('notificationManagement.records.title')"
      :subtitle="t('notificationManagement.records.subtitle')"
    >
      <AdminListSection>
        <template #filters>
          <div class="admin-filter-grid">
            <input
              v-model="filters.source_app"
              type="text"
              :placeholder="t('notificationManagement.records.sourceApp')"
              class="admin-filter-control w-40"
              @input="onFiltersChanged"
            />
            <input
              v-model="filters.source_type"
              type="text"
              :placeholder="t('notificationManagement.records.sourceType')"
              class="admin-filter-control w-40"
              @input="onFiltersChanged"
            />
            <select
              v-model="filters.status"
              class="admin-filter-control w-36"
              @change="onFiltersChanged"
            >
              <option value="">
                {{ t('notificationManagement.records.statusAll') }}
              </option>
              <option value="success">
                {{ t('notificationManagement.records.statusSuccess') }}
              </option>
              <option value="failed">
                {{ t('notificationManagement.records.statusFailed') }}
              </option>
              <option value="merged">
                {{ t('notificationManagement.records.statusMerged') }}
              </option>
              <option value="silenced">
                {{ t('notificationManagement.records.statusSilenced') }}
              </option>
              <option value="pending">
                {{ t('notificationManagement.records.statusPending') }}
              </option>
            </select>
            <input
              v-model="filters.start_date"
              type="date"
              :max="filters.end_date || undefined"
              class="admin-filter-control"
              @change="onFiltersChanged"
            />
            <span class="text-slate-400">-</span>
            <input
              v-model="filters.end_date"
              type="date"
              :min="filters.start_date || undefined"
              class="admin-filter-control"
              @change="onFiltersChanged"
            />
          </div>
          <div class="admin-toolbar-end">
            <BaseButton
              variant="outline"
              size="sm"
              :loading="loading"
              :title="t('common.refresh')"
              class="flex items-center gap-1"
              @click="fetchRecords"
            >
              <svg
                v-if="!loading"
                class="w-4 h-4"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="2"
                  d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
                />
              </svg>
              <span class="sr-only">{{ t('common.refresh') }}</span>
            </BaseButton>
            <BaseButton
              variant="outline"
              size="sm"
              class="flex items-center gap-1"
              @click="resetFilters"
            >
              <svg
                class="w-4 h-4"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="2"
                  d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
                />
              </svg>
              {{ t('notificationManagement.records.resetFilters') }}
            </BaseButton>
          </div>
        </template>

        <section class="space-y-6">
          <BaseLoading v-if="loading && records.length === 0" />

          <EmptyState
            v-else-if="!loading && records.length === 0"
            variant="admin"
            :title="t('notificationManagement.records.noRecords')"
          >
            <template #icon>
              <svg
                class="h-8 w-8"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="2"
                  d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                />
              </svg>
            </template>
          </EmptyState>

          <template v-else>
            <AdminTable>
              <thead>
                <tr>
                  <th class="admin-table-head">
                    {{ t('notificationManagement.records.sourceApp') }}
                  </th>
                  <th class="admin-table-head">
                    {{ t('notificationManagement.records.sourceType') }}
                  </th>
                  <th class="admin-table-head">
                    {{ t('notificationManagement.records.sourceId') }}
                  </th>
                  <th class="admin-table-head">
                    {{ t('notificationManagement.records.provider') }}
                  </th>
                  <th class="admin-table-head">
                    {{ t('notificationManagement.records.status') }}
                  </th>
                  <th class="admin-table-head">
                    {{ t('notificationManagement.records.createdAt') }}
                  </th>
                  <th class="admin-table-head">
                    {{ t('notificationManagement.records.sentAt') }}
                  </th>
                  <th class="admin-table-head">
                    {{ t('notificationManagement.records.user') }}
                  </th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="r in records"
                  :key="r.uuid"
                  class="admin-table-row cursor-pointer"
                  @click="openDetail(r.uuid)"
                >
                  <td class="admin-table-cell whitespace-nowrap text-slate-900">
                    {{ r.source_app || t('common.emptyValue') }}
                  </td>
                  <td class="admin-table-cell whitespace-nowrap text-slate-600">
                    {{ r.source_type || t('common.emptyValue') }}
                  </td>
                  <td
                    class="admin-table-cell whitespace-nowrap font-mono text-slate-600"
                  >
                    {{ r.source_id || t('common.emptyValue') }}
                  </td>
                  <td class="admin-table-cell whitespace-nowrap text-slate-600">
                    {{
                      r.provider_display_name ||
                      r.provider_type ||
                      t('common.emptyValue')
                    }}
                  </td>
                  <td class="admin-table-cell whitespace-nowrap">
                    <span :class="statusClass(r.status)">{{
                      r.status || t('common.emptyValue')
                    }}</span>
                  </td>
                  <td class="admin-table-cell whitespace-nowrap text-slate-600">
                    {{ formatDate(r.created_at) }}
                  </td>
                  <td class="admin-table-cell whitespace-nowrap text-slate-600">
                    {{ formatDate(r.sent_at) }}
                  </td>
                  <td class="admin-table-cell whitespace-nowrap text-slate-600">
                    {{ r.user_display ?? r.user_id ?? '-' }}
                  </td>
                </tr>
              </tbody>
            </AdminTable>

            <div v-if="total > pageSize" class="admin-pagination">
              <p class="text-sm text-slate-600">
                {{
                  t('common.pagination.showing', {
                    from: (page - 1) * pageSize + 1,
                    to: Math.min(page * pageSize, total),
                    total
                  })
                }}
              </p>
              <div class="flex items-center gap-2">
                <select
                  v-model.number="pageSize"
                  class="admin-filter-control w-20 py-1.5"
                  @change="handlePageSizeChange"
                >
                  <option :value="10">10</option>
                  <option :value="20">20</option>
                  <option :value="50">50</option>
                  <option :value="100">100</option>
                </select>
                <span class="text-sm text-slate-500">{{
                  t('notificationManagement.records.pageSize')
                }}</span>
                <BaseButton
                  variant="outline"
                  size="sm"
                  :disabled="page <= 1"
                  :title="t('common.pagination.previous')"
                  class="flex items-center gap-1"
                  @click="goPrevPage"
                >
                  <svg
                    class="w-4 h-4"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      stroke-linecap="round"
                      stroke-linejoin="round"
                      stroke-width="2"
                      d="M15 19l-7-7 7-7"
                    />
                  </svg>
                  <span class="sr-only">{{
                    t('common.pagination.previous')
                  }}</span>
                </BaseButton>
                <BaseButton
                  variant="outline"
                  size="sm"
                  :disabled="page >= totalPages"
                  :title="t('common.pagination.next')"
                  class="flex items-center gap-1"
                  @click="goNextPage"
                >
                  <svg
                    class="w-4 h-4"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      stroke-linecap="round"
                      stroke-linejoin="round"
                      stroke-width="2"
                      d="M9 5l7 7-7 7"
                    />
                  </svg>
                  <span class="sr-only">{{ t('common.pagination.next') }}</span>
                </BaseButton>
              </div>
            </div>
          </template>
        </section>

        <!-- Record detail right panel -->
        <Transition
          enter-active-class="transition-opacity duration-200"
          enter-from-class="opacity-0"
          enter-to-class="opacity-100"
          leave-active-class="transition-opacity duration-150"
          leave-from-class="opacity-100"
          leave-to-class="opacity-0"
        >
          <div
            v-if="detailVisible"
            class="admin-drawer-overlay"
            aria-hidden="true"
            @click="closeDetail"
          />
        </Transition>
        <Transition
          enter-active-class="transition-transform duration-300 ease-out"
          enter-from-class="translate-x-full"
          enter-to-class="translate-x-0"
          leave-active-class="transition-transform duration-250 ease-in"
          leave-from-class="translate-x-0"
          leave-to-class="translate-x-full"
        >
          <div
            v-if="detailVisible"
            class="admin-drawer"
            role="dialog"
            aria-modal="true"
            :aria-label="t('notificationManagement.records.detailTitle')"
          >
            <div class="admin-drawer-header">
              <h2 class="admin-drawer-title">
                {{ t('notificationManagement.records.detailTitle') }}
              </h2>
              <button
                type="button"
                class="admin-drawer-close"
                :aria-label="t('common.close')"
                @click="closeDetail"
              >
                <svg
                  class="w-5 h-5"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    stroke-width="2"
                    d="M6 18L18 6M6 6l12 12"
                  />
                </svg>
              </button>
            </div>
            <div class="admin-drawer-body">
              <BaseLoading v-if="detailLoading" />
              <template v-else-if="detailRecord">
                <div class="admin-drawer-section">
                  <h3 class="admin-drawer-section-title">
                    {{ t('notificationManagement.records.basicInfo') }}
                  </h3>
                  <dl class="grid grid-cols-1 gap-4">
                    <div>
                      <dt class="admin-drawer-field-label">
                        {{ t('notificationManagement.records.sourceApp') }}
                      </dt>
                      <dd class="admin-drawer-field-value">
                        {{ detailRecord.source_app || t('common.emptyValue') }}
                      </dd>
                    </div>
                    <div>
                      <dt class="admin-drawer-field-label">
                        {{ t('notificationManagement.records.sourceType') }}
                      </dt>
                      <dd class="admin-drawer-field-value">
                        {{
                          detailRecord.source_type || t('common.emptyValue')
                        }}
                      </dd>
                    </div>
                    <div>
                      <dt class="admin-drawer-field-label">
                        {{ t('notificationManagement.records.provider') }}
                      </dt>
                      <dd class="admin-drawer-field-value">
                        {{
                          detailRecord.provider_display_name ||
                          detailRecord.provider_type ||
                          t('common.emptyValue')
                        }}
                      </dd>
                    </div>
                    <div>
                      <dt class="admin-drawer-field-label">
                        {{ t('notificationManagement.records.status') }}
                      </dt>
                      <dd>
                        <span
                          :class="statusClass(detailRecord.status)"
                          class="text-sm font-medium"
                          >{{
                            detailRecord.status || t('common.emptyValue')
                          }}</span
                        >
                      </dd>
                    </div>
                    <div>
                      <dt class="admin-drawer-field-label">
                        {{ t('notificationManagement.records.user') }}
                      </dt>
                      <dd class="admin-drawer-field-value">
                        {{
                          detailRecord.user_display ??
                          detailRecord.user_id ??
                          '-'
                        }}
                      </dd>
                    </div>
                    <div>
                      <dt class="admin-drawer-field-label">
                        {{ t('notificationManagement.records.createdAt') }}
                      </dt>
                      <dd class="admin-drawer-field-value">
                        {{ formatDate(detailRecord.created_at) }}
                      </dd>
                    </div>
                    <div>
                      <dt class="admin-drawer-field-label">
                        {{ t('notificationManagement.records.sentAt') }}
                      </dt>
                      <dd class="admin-drawer-field-value">
                        {{ formatDate(detailRecord.sent_at) }}
                      </dd>
                    </div>
                  </dl>
                </div>
                <div
                  v-if="detailRecord.error_message"
                  class="admin-drawer-section"
                >
                  <h3 class="admin-drawer-section-title">
                    {{ t('notificationManagement.records.errorMessage') }}
                  </h3>
                  <div
                    class="admin-modal-code-panel admin-modal-code-panel--error"
                  >
                    <pre class="admin-modal-code admin-modal-code--error">{{
                      detailRecord.error_message
                    }}</pre>
                  </div>
                </div>
                <div
                  v-if="
                    detailRecord.payload &&
                    Object.keys(detailRecord.payload).length
                  "
                  class="admin-drawer-section"
                >
                  <h3 class="admin-drawer-section-title">
                    {{ t('notificationManagement.records.payload') }}
                  </h3>
                  <div class="admin-modal-code-panel">
                    <pre class="admin-modal-code">{{
                      JSON.stringify(detailRecord.payload, null, 2)
                    }}</pre>
                  </div>
                </div>
                <div
                  v-if="detailRecord.response != null"
                  class="admin-drawer-section"
                >
                  <h3 class="admin-drawer-section-title">
                    {{ t('notificationManagement.records.response') }}
                  </h3>
                  <div class="admin-modal-code-panel">
                    <pre class="admin-modal-code">{{
                      typeof detailRecord.response === 'object'
                        ? JSON.stringify(detailRecord.response, null, 2)
                        : detailRecord.response
                    }}</pre>
                  </div>
                </div>
              </template>
              <p v-else class="text-sm text-slate-500">
                {{ t('notificationManagement.records.detailNotFound') }}
              </p>
            </div>
          </div>
        </Transition>
      </AdminListSection>
    </PageFrame>
  </AdminLayout>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { format } from 'date-fns'
import { useDebounceFn } from '@vueuse/core'
import { useToast } from '@/composables/useToast'
import { extractErrorMessage } from '@/utils/api'
import { notificationsAdminApi } from '@/admin/api'
import AdminListSection from '@/admin/components/AdminListSection.vue'
import AdminTable from '@/admin/components/AdminTable.vue'
import AdminLayout from '@/admin/layout/AdminLayout.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseLoading from '@/components/ui/BaseLoading.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import PageFrame from '@/components/ui/PageFrame.vue'

const { t } = useI18n()
const { showError } = useToast()

const loading = ref(false)
const records = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const detailVisible = ref(false)
const detailLoading = ref(false)
const detailRecord = ref(null)
const selectedRecordUuid = ref(null)

function getDefaultDetailDateRange() {
  const now = new Date()
  const endStr = format(now, 'yyyy-MM-dd')
  const start = new Date(now)
  start.setDate(start.getDate() - 3)
  return { start_date: format(start, 'yyyy-MM-dd'), end_date: endStr }
}

const defaultDateRange = getDefaultDetailDateRange()
const filters = ref({
  source_app: '',
  source_type: '',
  status: '',
  start_date: defaultDateRange.start_date,
  end_date: defaultDateRange.end_date
})

const totalPages = computed(() =>
  total.value > 0 ? Math.ceil(total.value / pageSize.value) : 1
)

function formatDate(val) {
  if (!val) return '-'
  try {
    return format(new Date(val), 'yyyy-MM-dd HH:mm')
  } catch {
    return String(val)
  }
}

function statusClass(status) {
  const s = (status || '').toLowerCase()
  const base = 'admin-status-badge'
  if (s === 'success') return `${base} admin-status-badge--success`
  if (s === 'failed') return `${base} admin-status-badge--danger`
  if (s === 'pending') return `${base} admin-status-badge--info`
  if (s === 'merged' || s === 'silenced')
    return `${base} admin-status-badge--muted`
  return `${base} admin-status-badge--muted`
}

function onFiltersChanged() {
  page.value = 1
  debouncedFetch()
}

const debouncedFetch = useDebounceFn(() => {
  fetchRecords()
}, 300)

function resetFilters() {
  const range = getDefaultDetailDateRange()
  filters.value = {
    source_app: '',
    source_type: '',
    status: '',
    start_date: range.start_date,
    end_date: range.end_date
  }
  page.value = 1
  fetchRecords()
}

function openDetail(uuid) {
  selectedRecordUuid.value = uuid
  detailVisible.value = true
  detailRecord.value = null
}

function closeDetail() {
  detailVisible.value = false
  selectedRecordUuid.value = null
  detailRecord.value = null
}

function handlePageSizeChange() {
  page.value = 1
  fetchRecords()
}

function goPrevPage() {
  if (page.value <= 1) return
  page.value -= 1
  fetchRecords()
}

function goNextPage() {
  if (page.value >= totalPages.value) return
  page.value += 1
  fetchRecords()
}

async function fetchDetail() {
  if (!selectedRecordUuid.value) return
  detailLoading.value = true
  detailRecord.value = null
  try {
    const data = await notificationsAdminApi.getRecord(selectedRecordUuid.value)
    detailRecord.value = data
  } catch {
    detailRecord.value = null
  } finally {
    detailLoading.value = false
  }
}

async function fetchRecords() {
  loading.value = true
  try {
    const params = { page: page.value, page_size: pageSize.value }
    if (filters.value.source_app) params.source_app = filters.value.source_app
    if (filters.value.source_type)
      params.source_type = filters.value.source_type
    if (filters.value.status) params.status = filters.value.status
    if (filters.value.start_date) params.start_date = filters.value.start_date
    if (filters.value.end_date) params.end_date = filters.value.end_date
    const data = await notificationsAdminApi.getRecords(params)
    records.value = data?.results ?? []
    total.value = data?.total ?? 0
  } catch (e) {
    showError(extractErrorMessage(e, t('common.error')))
    records.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchRecords()
})

watch(detailVisible, (visible) => {
  if (visible && selectedRecordUuid.value) {
    fetchDetail()
  }
})
</script>
