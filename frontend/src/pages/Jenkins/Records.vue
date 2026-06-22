<template>
  <AppLayout>
    <PageFrame
      :eyebrow="t('jenkinsRecords.eyebrow')"
      :title="t('jenkinsRecords.title')"
      :subtitle="t('jenkinsRecords.subtitle')"
    >
      <section class="workspace-panel workspace-panel--padded">
        <div class="section-heading">
          <div>
            <h2 class="section-title">{{ t('jenkinsRecords.filtersTitle') }}</h2>
            <p class="section-copy">{{ t('jenkinsRecords.filtersSubtitle') }}</p>
          </div>
        </div>
        <div class="grid gap-4 lg:grid-cols-[1fr_1fr_auto]">
          <select v-model="filterEntry" @change="loadRecords" class="input">
            <option value="">{{ t('jenkinsRecords.allEntries') }}</option>
            <option v-for="entry in entries" :key="entry.id" :value="entry.id">
              {{ entry.name }}
            </option>
          </select>
          <select v-model="filterStatus" @change="loadRecords" class="input">
            <option value="">{{ t('jenkinsRecords.allStatuses') }}</option>
            <option value="pending">{{ t('jenkinsRecords.status.pending') }}</option>
            <option value="running">{{ t('jenkinsRecords.status.running') }}</option>
            <option value="success">{{ t('jenkinsRecords.status.success') }}</option>
            <option value="failure">{{ t('jenkinsRecords.status.failure') }}</option>
            <option value="aborted">{{ t('jenkinsRecords.status.aborted') }}</option>
          </select>
          <BaseButton variant="secondary" @click="clearFilters">{{ t('jenkinsRecords.clearFilters') }}</BaseButton>
        </div>
      </section>

      <section v-if="records.length" class="workspace-table-shell">
        <div class="overflow-x-auto">
          <table class="workspace-table">
            <thead>
              <tr>
                <th>{{ t('jenkinsRecords.entry') }}</th>
                <th>{{ t('jenkinsRecords.buildNumber') }}</th>
                <th>{{ t('jenkinsRecords.statusLabel') }}</th>
                <th>{{ t('jenkinsRecords.progress') }}</th>
                <th>{{ t('jenkinsRecords.notificationSummary.columnHeader') }}</th>
                <th>{{ t('jenkinsRecords.triggeredBy') }}</th>
                <th>{{ t('jenkinsRecords.triggeredAt') }}</th>
                <th>{{ t('jenkinsRecords.duration') }}</th>
                <th>{{ t('jenkinsRecords.finishedAt') }}</th>
                <th>{{ t('common.actions') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="record in records" :key="record.id">
                <td>
                  <div class="font-semibold text-slate-900">{{ record.entry_name }}</div>
                </td>
                <td>
                  <span class="rounded-full bg-slate-100 px-3 py-1 font-mono text-xs text-slate-700">
                    {{ record.build_number ? `#${record.build_number}` : t('jenkinsRecords.queuedBuild') }}
                  </span>
                </td>
                <td>
                  <span :class="statusClass(record.status)">
                    {{ statusText(record.status) }}
                  </span>
                </td>
                <td>
                  <div v-if="hasBuildProgress(record)" class="min-w-[10rem]">
                    <div class="flex items-center justify-between gap-3">
                      <span class="text-xs font-semibold text-slate-800">
                        {{ progressLabel(record) }}
                      </span>
                      <span class="max-w-[9rem] truncate text-xs text-slate-500">
                        {{ progressStage(record) }}
                      </span>
                    </div>
                    <div class="mt-2 h-2 overflow-hidden rounded-full bg-slate-100">
                      <div
                        class="h-full rounded-full bg-sky-500 transition-all"
                        :style="{ width: `${progressPercent(record)}%` }"
                      />
                    </div>
                    <p v-if="progressSummary(record)" class="mt-1 text-[11px] text-slate-400">
                      {{ progressSummary(record) }}
                    </p>
                  </div>
                  <span v-else class="text-sm text-slate-400">-</span>
                </td>
                <td>
                  <div class="max-w-[18rem]">
                    <div class="font-medium text-slate-800">
                      {{ record.notification_result?.summary || t('jenkinsRecords.notificationSummary.pendingFallback') }}
                    </div>
                    <div class="mt-1 text-xs text-slate-500">
                      {{ t('jenkinsRecords.notificationSummary.channelSummary', { emailCount: record.notification_result?.emails?.length || 0, webhookCount: record.notification_result?.webhooks?.length || 0 }) }}
                    </div>
                  </div>
                </td>
                <td>{{ record.username || '-' }}</td>
                <td class="text-slate-500">{{ formatDate(record.triggered_at) }}</td>
                <td class="text-slate-500">{{ formatDuration(record) }}</td>
                <td class="text-slate-500">{{ formatDate(record.finished_at) || '-' }}</td>
                <td>
                  <div class="flex flex-wrap gap-3">
                    <button
                      v-if="canRefreshRecord(record)"
                      type="button"
                      class="text-sm font-semibold text-sky-700 transition hover:text-sky-900 disabled:opacity-50"
                      :disabled="refreshing === record.id"
                      @click="refreshStatus(record)"
                    >
                      {{ refreshing === record.id ? t('jenkinsRecords.refreshing') : t('jenkinsRecords.refresh') }}
                    </button>
                    <button
                      v-if="record.artifacts && record.artifacts.length > 0"
                      type="button"
                      class="text-sm font-semibold text-violet-700 transition hover:text-violet-900"
                      @click="showArtifacts(record)"
                    >
                      {{ t('jenkinsRecords.artifactCount', { count: record.artifacts.length }) }}
                    </button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <EmptyState
        v-else
        :title="t('jenkinsRecords.emptyTitle')"
        :description="t('jenkinsRecords.emptySubtitle')"
      >
        <template #icon>
          <svg class="h-8 w-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
        </template>
      </EmptyState>

      <div v-if="totalPages > 1" class="surface-panel-strong flex items-center justify-between px-5 py-4">
        <BaseButton
          variant="secondary"
          :disabled="currentPage === 1"
          @click="goToPage(currentPage - 1)"
        >
          {{ t('jenkinsRecords.previousPage') }}
        </BaseButton>
        <span class="text-sm font-medium text-slate-500">{{ t('jenkinsRecords.pageIndicator', { current: currentPage, total: totalPages }) }}</span>
        <BaseButton
          variant="secondary"
          :disabled="currentPage === totalPages"
          @click="goToPage(currentPage + 1)"
        >
          {{ t('jenkinsRecords.nextPage') }}
        </BaseButton>
      </div>

      <BaseModal :show="showArtifactsModal" :title="t('jenkinsRecords.artifactsTitle')" @close="showArtifactsModal = false">
        <div class="space-y-3">
          <div
            v-for="artifact in selectedRecord?.artifacts"
            :key="artifact.path"
            class="rounded-lg border border-slate-200/80 bg-slate-50/80 p-4"
          >
            <div class="font-semibold text-slate-900">{{ artifact.name }}</div>
            <div class="mt-1 break-words font-mono text-xs text-slate-500">{{ artifact.path }}</div>
          </div>
        </div>
        <template #footer>
          <div class="flex w-full justify-end">
            <BaseButton @click="showArtifactsModal = false">{{ t('common.close') }}</BaseButton>
          </div>
        </template>
      </BaseModal>

      <div
        v-if="toast.show"
        :class="[
          'fixed bottom-5 right-5 z-[60] rounded-lg px-4 py-3 text-sm font-medium text-white shadow-[0_14px_34px_rgba(15,23,42,0.18)]',
          toast.type === 'success' ? 'bg-emerald-600' : 'bg-rose-600'
        ]"
      >
        {{ toast.message }}
      </div>
    </PageFrame>
  </AppLayout>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { useI18n } from 'vue-i18n'
import AppLayout from '@/components/layout/AppLayout.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseModal from '@/components/ui/BaseModal.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import PageFrame from '@/components/ui/PageFrame.vue'
import jenkinsApi from '@/api/jenkins'

const { t, locale } = useI18n()

const records = ref([])
const entries = ref([])
const filterEntry = ref('')
const filterStatus = ref('')
const currentPage = ref(1)
const totalPages = ref(1)
const pageSize = 20
const refreshing = ref(null)
const showArtifactsModal = ref(false)
const selectedRecord = ref(null)
const nowMs = ref(Date.now())
const recordsRefreshInFlight = ref(false)
let durationTicker = null
let autoRefreshTicker = null
const activeRefreshIds = new Set()

const AUTO_REFRESH_INTERVAL_MS = 10000

const toast = ref({ show: false, message: '', type: 'success' })

function showToast(message, type = 'success') {
  toast.value = { show: true, message, type }
  setTimeout(() => {
    toast.value.show = false
  }, 3000)
}

function statusClass(status) {
  const classes = {
    pending: 'status-pill-warning',
    running: 'status-pill-warning',
    success: 'status-pill-success',
    failure: 'status-pill-danger',
    aborted: 'status-pill-neutral'
  }
  return classes[status] || 'status-pill-neutral'
}

function statusText(status) {
  const texts = {
    pending: t('jenkinsRecords.status.pending'),
    running: t('jenkinsRecords.status.running'),
    success: t('jenkinsRecords.status.success'),
    failure: t('jenkinsRecords.status.failure'),
    aborted: t('jenkinsRecords.status.aborted')
  }
  return texts[status] || status
}

function canRefreshRecord(record) {
  return Boolean(record.build_number || record.queue_url)
}

function progressPercent(record) {
  const value = Number(record?.progress_percent ?? 0)
  if (Number.isNaN(value)) return 0
  return Math.max(0, Math.min(value, 100))
}

function hasBuildProgress(record) {
  if (!record) return false
  if (record.pipeline_supported) return true
  return record.progress_percent != null && isActiveBuildStatus(record.status)
}

function progressLabel(record) {
  if (record?.status === 'running' && record?.pipeline_supported) {
    return t('jenkinsRecords.estimatedProgress', {
      percent: progressPercent(record)
    })
  }
  return `${progressPercent(record)}%`
}

function progressStage(record) {
  if (record?.current_stage) return record.current_stage
  if (record?.status === 'pending') return t('jenkinsRecords.queuedBuild')
  return statusText(record?.status)
}

function progressSummary(record) {
  if (['success', 'failure', 'aborted'].includes(record?.status)) {
    return record.status === 'success'
      ? t('jenkinsRecords.pipelineCompleted')
      : t('jenkinsRecords.pipelineFinished')
  }
  const summary = record?.stage_summary
  if (!summary || !summary.total) return ''
  return t('jenkinsRecords.stageSummary', {
    completed: summary.completed || 0,
    total: summary.total
  })
}

function isActiveBuildStatus(status) {
  return status === 'pending' || status === 'running'
}

function hasRefreshTarget(record) {
  return Boolean(record.build_number || record.queue_url)
}

function formatDate(dateStr) {
  if (!dateStr) return null
  const date = new Date(dateStr)
  return date.toLocaleString(locale.value || 'en', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  })
}

function parseTimeMs(value) {
  if (!value) return null
  const time = new Date(value).getTime()
  return Number.isNaN(time) ? null : time
}

function formatDurationValue(durationMs) {
  const safeMs = Math.max(durationMs || 0, 1000)
  const totalSeconds = Math.floor(safeMs / 1000)
  const days = Math.floor(totalSeconds / 86400)
  const hours = Math.floor((totalSeconds % 86400) / 3600)
  const minutes = Math.floor((totalSeconds % 3600) / 60)
  const seconds = totalSeconds % 60

  if (days > 0) {
    return hours > 0
      ? `${days}${t('jenkinsRecords.durationDays')}${hours}${t('jenkinsRecords.durationHours')}`
      : `${days}${t('jenkinsRecords.durationDays')}`
  }
  if (hours > 0) {
    return `${hours}${t('jenkinsRecords.durationHours')}${String(minutes).padStart(2, '0')}${t('jenkinsRecords.durationMinutes')}`
  }
  if (minutes > 0) {
    return `${minutes}${t('jenkinsRecords.durationMinutes')}${seconds}${t('jenkinsRecords.durationSeconds')}`
  }
  return `${Math.max(seconds, 1)}${t('jenkinsRecords.durationSeconds')}`
}

function formatDuration(record) {
  const startedAtMs = parseTimeMs(record.triggered_at)
  if (!startedAtMs) return '-'

  const endedAtMs = ['success', 'failure', 'aborted'].includes(record.status)
    ? parseTimeMs(record.finished_at)
    : nowMs.value

  if (!endedAtMs || endedAtMs < startedAtMs) return '-'
  return formatDurationValue(endedAtMs - startedAtMs)
}

function applyRecordUpdate(updatedRecord) {
  const index = records.value.findIndex((record) => record.id === updatedRecord.id)
  if (index === -1) return
  records.value[index] = {
    ...records.value[index],
    ...updatedRecord,
  }
}

function stopRecordsAutoRefresh() {
  if (autoRefreshTicker) {
    window.clearInterval(autoRefreshTicker)
    autoRefreshTicker = null
  }
}

function getAutoRefreshCandidates() {
  return records.value.filter((record) => isActiveBuildStatus(record.status) && hasRefreshTarget(record))
}

function syncRecordsAutoRefresh() {
  const hasActiveRecords = getAutoRefreshCandidates().length > 0
  if (document.visibilityState === 'hidden' || !hasActiveRecords) {
    stopRecordsAutoRefresh()
    return
  }

  if (autoRefreshTicker) return
  autoRefreshTicker = window.setInterval(() => {
    void refreshActiveRecords()
  }, AUTO_REFRESH_INTERVAL_MS)
}

async function loadRecords() {
  try {
    const params = {
      page: currentPage.value,
      page_size: pageSize
    }
    if (filterEntry.value) params.entry_id = filterEntry.value
    if (filterStatus.value) params.status = filterStatus.value
    const data = await jenkinsApi.listRecords(params)
    records.value = data.results || data
    totalPages.value = data.total_pages || 1
    syncRecordsAutoRefresh()
  } catch (e) {
    showToast(t('jenkinsRecords.toast.loadRecordsFailed', { message: e.message }), 'error')
  }
}

async function loadEntries() {
  try {
    entries.value = await jenkinsApi.getUserEntries()
  } catch (e) {
    showToast(t('jenkinsRecords.toast.loadEntriesFailed', { message: e.message }), 'error')
  }
}

async function refreshStatus(record, { silent = false, manual = true } = {}) {
  if (!hasRefreshTarget(record)) {
    if (manual && !silent) {
      showToast(t('jenkinsRecords.toast.refreshUnavailable'), 'error')
    }
    return
  }

  if (activeRefreshIds.has(record.id)) return

  activeRefreshIds.add(record.id)
  if (manual) {
    refreshing.value = record.id
  }

  try {
    const updatedRecord = await jenkinsApi.refreshStatus(record.id)
    applyRecordUpdate(updatedRecord)
    syncRecordsAutoRefresh()
    if (manual && !silent) {
      showToast(t('jenkinsRecords.statusRefreshed'))
    }
  } catch (e) {
    if (manual && !silent) {
      showToast(t('jenkinsRecords.toast.refreshFailed', { message: e.message }), 'error')
    } else {
      console.warn(`Auto refresh failed for record ${record.id}:`, e)
    }
  } finally {
    activeRefreshIds.delete(record.id)
    if (manual) {
      refreshing.value = null
    }
  }
}

async function refreshActiveRecords() {
  if (recordsRefreshInFlight.value) return

  const candidates = getAutoRefreshCandidates().filter((record) => !activeRefreshIds.has(record.id))
  if (!candidates.length) {
    stopRecordsAutoRefresh()
    return
  }

  recordsRefreshInFlight.value = true
  try {
    await Promise.allSettled(
      candidates.map((record) => refreshStatus(record, { silent: true, manual: false }))
    )
  } finally {
    recordsRefreshInFlight.value = false
    syncRecordsAutoRefresh()
  }
}

function showArtifacts(record) {
  selectedRecord.value = record
  showArtifactsModal.value = true
}

function clearFilters() {
  filterEntry.value = ''
  filterStatus.value = ''
  currentPage.value = 1
  loadRecords()
}

function goToPage(page) {
  if (page < 1 || page > totalPages.value) return
  currentPage.value = page
  loadRecords()
}

function handleVisibilityChange() {
  if (document.visibilityState === 'hidden') {
    stopRecordsAutoRefresh()
    return
  }
  syncRecordsAutoRefresh()
}

onMounted(() => {
  loadRecords()
  loadEntries()
  durationTicker = window.setInterval(() => {
    nowMs.value = Date.now()
  }, 1000)
  document.addEventListener('visibilitychange', handleVisibilityChange)
})

onBeforeUnmount(() => {
  if (durationTicker) {
    window.clearInterval(durationTicker)
    durationTicker = null
  }
  stopRecordsAutoRefresh()
  document.removeEventListener('visibilitychange', handleVisibilityChange)
})
</script>
