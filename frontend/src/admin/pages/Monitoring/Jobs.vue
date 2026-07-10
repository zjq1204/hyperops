<template>
  <AdminLayout>
    <PageFrame
      variant="soft"
      :title="t('adminPages.monitoring.jobsTitle')"
    >
      <AdminListSection>
        <template #toolbarStart>
          <div class="flex flex-wrap gap-2">
            <select v-model="componentFilter" class="admin-filter-control min-w-40">
              <option value="">{{ t('adminPages.monitoring.allComponents') }}</option>
              <option value="categraf">{{ t('adminPages.monitoring.componentCategraf') }}</option>
              <option value="blackbox">{{ t('adminPages.monitoring.componentBlackbox') }}</option>
            </select>
            <select v-model="statusFilter" class="admin-filter-control min-w-36">
              <option value="">{{ t('adminPages.monitoring.allStatuses') }}</option>
              <option value="queued">{{ t('adminPages.monitoring.statusQueued') }}</option>
              <option value="running">{{ t('adminPages.monitoring.statusRunning') }}</option>
              <option value="success">{{ t('adminPages.monitoring.statusSuccess') }}</option>
              <option value="failed">{{ t('adminPages.monitoring.statusFailed') }}</option>
            </select>
          </div>
        </template>
        <template #toolbarEnd>
          <BaseButton variant="outline" size="sm" :loading="loading" @click="load">
            {{ t('common.refresh') }}
          </BaseButton>
        </template>
        <AdminPageState :loading="loading" :error="error" :empty="!filteredJobs.length">
          <section class="grid gap-4">
            <AdminTable>
              <thead>
                <tr>
                  <th class="admin-table-head">{{ t('common.id') }}</th>
                  <th class="admin-table-head">{{ t('adminPages.monitoring.component') }}</th>
                  <th class="admin-table-head">{{ t('common.status') }}</th>
                  <th class="admin-table-head">{{ t('adminPages.monitoring.hostResult') }}</th>
                  <th class="admin-table-head">{{ t('adminPages.monitoring.duration') }}</th>
                  <th class="admin-table-head">{{ t('adminPages.monitoring.lastError') }}</th>
                  <th class="admin-table-head">{{ t('common.actions') }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="job in filteredJobs" :key="job.id" class="admin-table-row align-top">
                  <td class="admin-table-cell text-slate-900">
                    <div class="font-semibold">#{{ job.id }}</div>
                    <div v-if="job.retry_of" class="mt-1 text-xs text-slate-400">
                      {{ t('adminPages.monitoring.retryOf') }} #{{ job.retry_of }}
                    </div>
                  </td>
                  <td class="admin-table-cell text-slate-600">
                    {{ componentLabel(job.component) }}
                  </td>
                  <td class="admin-table-cell">
                    <span
                      class="inline-flex rounded-full border px-2.5 py-1 text-xs font-semibold"
                      :class="statusClass(job.status)"
                    >
                      {{ statusLabel(job.status) }}
                    </span>
                  </td>
                  <td class="admin-table-cell text-slate-600">
                    <div class="font-semibold text-slate-800">
                      {{ job.success_hosts || 0 }} / {{ job.total_hosts || 0 }}
                    </div>
                    <div v-if="job.failed_hosts" class="mt-1 text-xs text-rose-600">
                      {{ t('adminPages.monitoring.failedHostCount', { count: job.failed_hosts }) }}
                    </div>
                  </td>
                  <td class="admin-table-cell text-slate-500">
                    {{ formatDuration(job.duration_seconds) }}
                  </td>
                  <td class="admin-table-cell text-slate-500">
                    <p class="max-w-xs truncate">
                      {{ job.last_error || t('common.emptyValue') }}
                    </p>
                    <p
                      v-for="finding in jobFindingsFor(job)"
                      :key="finding.id"
                      class="mt-1 max-w-xs truncate text-xs font-semibold text-amber-700"
                    >
                      {{ finding.title }}
                    </p>
                  </td>
                  <td class="admin-table-cell">
                    <div class="admin-row-actions">
                      <BaseButton variant="outline" size="sm" @click="openJob(job)">
                        {{ t('adminPages.monitoring.viewDetails') }}
                      </BaseButton>
                      <BaseButton
                        v-if="retryFindingFor(job)"
                        variant="primary"
                        size="sm"
                        :loading="resolvingFindingId === retryFindingFor(job).id"
                        @click="retryFinding(retryFindingFor(job))"
                      >
                        {{ t('adminPages.monitoring.retryFailedHosts') }}
                      </BaseButton>
                      <BaseButton v-else-if="canRetry(job)" variant="outline" size="sm" @click="retry(job)">
                        {{ t('adminPages.monitoring.retryFailedHosts') }}
                      </BaseButton>
                    </div>
                  </td>
                </tr>
              </tbody>
            </AdminTable>
          </section>
        </AdminPageState>
      </AdminListSection>
    </PageFrame>

    <BaseModal
      :show="Boolean(selectedJob)"
      :title="selectedJob ? `#${selectedJob.id} ${componentLabel(selectedJob.component)}` : t('adminPages.monitoring.viewDetails')"
      size="xl"
      @close="selectedJob = null"
    >
      <div v-if="selectedJob" class="grid gap-5">
        <div class="grid gap-3 sm:grid-cols-4">
          <div class="rounded-lg bg-slate-50 px-3 py-3">
            <p class="text-xs font-medium text-slate-500">{{ t('common.status') }}</p>
            <p class="mt-1 text-sm font-semibold text-slate-900">{{ statusLabel(selectedJob.status) }}</p>
          </div>
          <div class="rounded-lg bg-slate-50 px-3 py-3">
            <p class="text-xs font-medium text-slate-500">{{ t('adminPages.monitoring.hostResult') }}</p>
            <p class="mt-1 text-sm font-semibold text-slate-900">
              {{ selectedJob.success_hosts || 0 }} / {{ selectedJob.total_hosts || 0 }}
            </p>
          </div>
          <div class="rounded-lg bg-slate-50 px-3 py-3">
            <p class="text-xs font-medium text-slate-500">{{ t('adminPages.monitoring.duration') }}</p>
            <p class="mt-1 text-sm font-semibold text-slate-900">
              {{ formatDuration(selectedJob.duration_seconds) }}
            </p>
          </div>
          <div class="rounded-lg bg-slate-50 px-3 py-3">
            <p class="text-xs font-medium text-slate-500">{{ t('adminPages.monitoring.returnCode') }}</p>
            <p class="mt-1 text-sm font-semibold text-slate-900">
              {{ selectedJob.returncode ?? t('common.emptyValue') }}
            </p>
          </div>
        </div>

        <div class="flex flex-wrap gap-2 border-b border-slate-200">
          <button
            v-for="tab in detailTabs"
            :key="tab.key"
            class="border-b-2 px-3 py-2 text-sm font-semibold transition"
            :class="detailTab === tab.key ? 'border-slate-900 text-slate-950' : 'border-transparent text-slate-500 hover:text-slate-800'"
            @click="detailTab = tab.key"
          >
            {{ tab.label }}
          </button>
        </div>

        <section v-if="detailTab === 'result'" class="grid gap-3">
          <div v-if="selectedJob.failed_hostnames?.length" class="rounded-lg border border-rose-100 bg-rose-50 p-4">
            <p class="text-sm font-semibold text-rose-900">{{ t('adminPages.monitoring.failedHosts') }}</p>
            <div class="mt-3 flex flex-wrap gap-2">
              <span
                v-for="host in selectedJob.failed_hostnames"
                :key="host"
                class="rounded-full bg-white px-3 py-1 text-xs font-semibold text-rose-700"
              >
                {{ host }}
              </span>
            </div>
          </div>
          <pre class="admin-code-block">{{ prettyJson(selectedJob.results || []) }}</pre>
        </section>

        <section v-else-if="detailTab === 'ansible'" class="grid gap-4 lg:grid-cols-2">
          <div>
            <p class="mb-2 text-sm font-semibold text-slate-900">{{ t('adminPages.monitoring.inventory') }}</p>
            <pre class="admin-code-block">{{ selectedJob.inventory || t('common.emptyValue') }}</pre>
          </div>
          <div>
            <p class="mb-2 text-sm font-semibold text-slate-900">{{ t('adminPages.monitoring.vars') }}</p>
            <pre class="admin-code-block">{{ prettyJson(selectedJob.vars || {}) }}</pre>
          </div>
        </section>

        <section v-else-if="detailTab === 'command'" class="grid gap-3">
          <div class="flex justify-end">
            <BaseButton variant="outline" size="sm" :disabled="!selectedJob.manual_command" @click="copyManualCommand">
              {{ copied ? t('adminPages.monitoring.commandCopied') : t('adminPages.monitoring.copyCommand') }}
            </BaseButton>
          </div>
          <pre class="admin-code-block">{{ selectedJob.manual_command || t('common.emptyValue') }}</pre>
        </section>

        <section v-else class="grid gap-3">
          <pre class="admin-code-block">{{ (selectedJob.logs || []).join('\n') || t('common.emptyValue') }}</pre>
        </section>

        <div class="flex justify-end gap-2">
          <BaseButton variant="outline" @click="selectedJob = null">
            {{ t('common.close') }}
          </BaseButton>
          <BaseButton
            v-if="retryFindingFor(selectedJob)"
            variant="primary"
            :loading="resolvingFindingId === retryFindingFor(selectedJob).id"
            @click="retryFinding(retryFindingFor(selectedJob))"
          >
            {{ t('adminPages.monitoring.retryFailedHosts') }}
          </BaseButton>
          <BaseButton v-else-if="canRetry(selectedJob)" variant="primary" @click="retry(selectedJob)">
            {{ t('adminPages.monitoring.retryFailedHosts') }}
          </BaseButton>
        </div>
      </div>
    </BaseModal>
  </AdminLayout>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import AdminLayout from '@/admin/layout/AdminLayout.vue'
import AdminListSection from '@/admin/components/AdminListSection.vue'
import AdminPageState from '@/admin/components/AdminPageState.vue'
import AdminTable from '@/admin/components/AdminTable.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseModal from '@/components/ui/BaseModal.vue'
import PageFrame from '@/components/ui/PageFrame.vue'
import { monitoringStackApi } from '@/admin/api/monitoringStack'

const { t } = useI18n()
const loading = ref(false)
const error = ref('')
const jobs = ref([])
const jobFindings = ref([])
const selectedJob = ref(null)
const detailTab = ref('result')
const componentFilter = ref('')
const statusFilter = ref('')
const copied = ref(false)
const resolvingFindingId = ref(null)

const detailTabs = computed(() => [
  { key: 'result', label: t('adminPages.monitoring.executionResult') },
  { key: 'ansible', label: t('adminPages.monitoring.ansiblePreview') },
  { key: 'command', label: t('adminPages.monitoring.manualCommandPreview') },
  { key: 'logs', label: t('adminPages.monitoring.logs') }
])

const filteredJobs = computed(() => jobs.value.filter((job) => {
  const componentMatched = !componentFilter.value || job.component === componentFilter.value
  const statusMatched = !statusFilter.value || job.status === statusFilter.value
  return componentMatched && statusMatched
}))

function normalizeList(data) {
  return data?.results || data || []
}

function canRetry(job) {
  return String(job?.status || '').toLowerCase() === 'failed' && Number(job?.failed_hosts || 0) > 0
}

function jobFindingsFor(job) {
  if (!job) return []
  return jobFindings.value.filter((finding) => String(finding.subject_key) === String(job.id))
}

function retryFindingFor(job) {
  return jobFindingsFor(job).find((finding) => finding.recommended_action === 'retry_job')
}

function componentLabel(component) {
  return component === 'blackbox'
    ? t('adminPages.monitoring.componentBlackbox')
    : t('adminPages.monitoring.componentCategraf')
}

function statusLabel(status) {
  const labels = {
    queued: t('adminPages.monitoring.statusQueued'),
    running: t('adminPages.monitoring.statusRunning'),
    pending: t('adminPages.monitoring.statusPending'),
    success: t('common.success'),
    failed: t('common.failed'),
    error: t('adminPages.monitoring.statusError'),
    timeout: t('adminPages.monitoring.statusTimeout')
  }
  return labels[String(status || '').toLowerCase()] || status || t('common.emptyValue')
}

function statusClass(status) {
  const value = String(status || '').toLowerCase()
  if (['success', 'succeeded', 'completed', 'done'].includes(value)) {
    return 'border-emerald-200 bg-emerald-50 text-emerald-700'
  }
  if (['failed', 'error', 'timeout'].includes(value)) {
    return 'border-rose-200 bg-rose-50 text-rose-700'
  }
  if (['running', 'pending', 'queued'].includes(value)) {
    return 'border-sky-200 bg-sky-50 text-sky-700'
  }
  return 'border-slate-200 bg-slate-50 text-slate-600'
}

function formatDuration(value) {
  if (value === null || value === undefined) return t('common.emptyValue')
  if (value < 60) return `${value}s`
  const minutes = Math.floor(value / 60)
  const seconds = value % 60
  return `${minutes}m ${seconds}s`
}

function prettyJson(value) {
  return JSON.stringify(value, null, 2)
}

function openJob(job) {
  selectedJob.value = job
  detailTab.value = 'result'
  copied.value = false
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    await monitoringStackApi.getGovernanceOverview()
    const [data, findingData] = await Promise.all([
      monitoringStackApi.getJobs(),
      monitoringStackApi.getGovernanceFindings({ status: 'open', subject_type: 'job' })
    ])
    jobs.value = normalizeList(data)
    jobFindings.value = normalizeList(findingData)
    if (selectedJob.value) {
      selectedJob.value = jobs.value.find((job) => job.id === selectedJob.value.id) || selectedJob.value
    }
  } catch (err) {
    error.value = err?.response?.data?.detail || err.message
  } finally {
    loading.value = false
  }
}

async function retryFinding(finding) {
  resolvingFindingId.value = finding.id
  try {
    const data = await monitoringStackApi.resolveGovernanceFinding(finding.id, {
      action: 'retry_job'
    })
    const retryJobId = data?.details?.resolution?.job_id
    await load()
    if (retryJobId) {
      selectedJob.value = jobs.value.find((job) => job.id === retryJobId) || selectedJob.value
      detailTab.value = 'result'
    }
  } finally {
    resolvingFindingId.value = null
  }
}

async function retry(job) {
  const data = await monitoringStackApi.retryJob(job.id)
  selectedJob.value = data
  detailTab.value = 'result'
  await load()
}

async function copyManualCommand() {
  if (!selectedJob.value?.manual_command) return
  await navigator.clipboard.writeText(selectedJob.value.manual_command)
  copied.value = true
  window.setTimeout(() => {
    copied.value = false
  }, 1600)
}

onMounted(load)
</script>

<style scoped>
.admin-code-block {
  max-height: 24rem;
  overflow: auto;
  white-space: pre-wrap;
  border-radius: 0.5rem;
  background: #020617;
  padding: 1rem;
  font-size: 0.75rem;
  line-height: 1.5rem;
  color: #f8fafc;
}
</style>
