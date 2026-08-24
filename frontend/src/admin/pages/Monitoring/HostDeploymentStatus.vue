<template>
  <AdminLayout>
    <section class="page-shell deployment-status-page">
      <button type="button" class="deployment-back" @click="goBack">
        <span aria-hidden="true">←</span>
        {{ t('adminPages.monitoring.backToDeployment') }}
      </button>

      <AdminPageState
        :loading="loading"
        :error="error"
        :empty="!host"
        :empty-title="t('adminPages.monitoring.noDeploymentHistory')"
      >
        <template v-if="host">
          <header class="deployment-heading">
            <h1 class="deployment-title">
              {{
                t('adminPages.monitoring.hostDeploymentTitle', {
                  host: host.hostname
                })
              }}
            </h1>
            <p class="deployment-subtitle">
              <span>{{ host.address }}</span>
              <span aria-hidden="true">/</span>
              <span>{{ t('adminPages.monitoring.hosts') }}</span>
              <span aria-hidden="true">/</span>
              <span>{{
                t(
                  'adminPages.monitoring.installedComponentSummary',
                  componentStats
                )
              }}</span>
            </p>
          </header>

          <section class="deployment-workspace">
            <nav
              class="deployment-tabs"
              :aria-label="
                t('adminPages.monitoring.hostDeploymentTitle', {
                  host: host.hostname
                })
              "
            >
              <button
                v-for="tab in workspaceTabs"
                :key="tab.key"
                type="button"
                :class="{ active: activeTab === tab.key }"
                @click="setTab(tab.key)"
              >
                {{ tab.label }}
              </button>
            </nav>

            <section v-if="activeTab === 'current'" class="component-overview">
              <div class="component-overview-heading">
                <div>
                  <h2>{{ t('adminPages.monitoring.installedComponents') }}</h2>
                  <p>
                    {{
                      t(
                        'adminPages.monitoring.installedComponentSummary',
                        componentStats
                      )
                    }}
                  </p>
                </div>
                <span
                  class="host-enabled-state"
                  :class="
                    hostRecord?.enabled === false ? 'is-disabled' : 'is-enabled'
                  "
                >
                  {{
                    hostRecord?.enabled === false
                      ? t('common.disabled')
                      : t('common.enabled')
                  }}
                </span>
              </div>

              <div class="component-list-heading" aria-hidden="true">
                <span>{{ t('adminPages.monitoring.component') }}</span>
                <span>{{ t('adminPages.monitoring.installationState') }}</span>
                <span>{{ t('adminPages.monitoring.runtimeState') }}</span>
                <span>{{
                  t('adminPages.monitoring.enabledCapabilities')
                }}</span>
                <span>{{ t('adminPages.monitoring.installLocation') }}</span>
                <span></span>
              </div>

              <article
                v-for="row in componentRows"
                :key="row.component"
                class="component-row"
              >
                <div class="component-identity">
                  <span class="component-mark" :class="`is-${row.component}`">
                    {{ row.component === 'blackbox' ? 'B' : 'C' }}
                  </span>
                  <div class="min-w-0">
                    <h3>{{ componentLabel(row.component) }}</h3>
                    <p>{{ row.runtimeEndpoint || t('common.emptyValue') }}</p>
                  </div>
                </div>

                <div class="component-state-cell">
                  <span class="component-field-label">
                    {{ t('adminPages.monitoring.installationState') }}
                  </span>
                  <span
                    class="component-state-badge"
                    :class="`is-${row.status}`"
                  >
                    {{ installationLabel(row) }}
                  </span>
                </div>

                <div class="component-state-cell">
                  <span class="component-field-label">
                    {{ t('adminPages.monitoring.runtimeState') }}
                  </span>
                  <span
                    class="runtime-state"
                    :class="`is-${row.runtimeStatus}`"
                  >
                    <span aria-hidden="true"></span>
                    {{ runtimeLabel(row.runtimeStatus) }}
                  </span>
                </div>

                <div class="component-capabilities">
                  <span class="component-field-label">
                    {{ t('adminPages.monitoring.enabledCapabilities') }}
                  </span>
                  <div class="capability-list">
                    <span
                      v-for="capability in row.capabilities"
                      :key="capability"
                    >
                      {{ capability }}
                    </span>
                  </div>
                </div>

                <dl class="component-location">
                  <div>
                    <dt>{{ t('adminPages.monitoring.installLocation') }}</dt>
                    <dd>{{ row.installDir || t('common.emptyValue') }}</dd>
                  </div>
                  <div>
                    <dt>{{ t('adminPages.monitoring.latestExecution') }}</dt>
                    <dd>{{ formatDateTime(row.latest?.created_at) }}</dd>
                  </div>
                </dl>

                <div class="component-actions">
                  <BaseButton
                    v-if="row.component === 'categraf'"
                    variant="outline"
                    size="sm"
                    @click="openCapabilityAdjustment"
                  >
                    {{ t('adminPages.monitoring.adjustCapabilities') }}
                  </BaseButton>
                  <BaseButton
                    v-if="row.latest"
                    variant="outline"
                    size="sm"
                    @click="openComponentDetails(row)"
                  >
                    {{ t('adminPages.monitoring.viewDetails') }}
                  </BaseButton>
                  <RouterLink
                    v-if="row.failed && row.sshFailure"
                    class="deployment-text-action"
                    to="/management/monitoring/credentials"
                  >
                    {{ t('adminPages.monitoring.openCredential') }}
                  </RouterLink>
                  <button
                    v-if="row.failed && row.sshFailure"
                    type="button"
                    class="deployment-text-action"
                    :disabled="testingConnection"
                    @click="testConnection"
                  >
                    {{
                      testingConnection
                        ? t('common.loading')
                        : t('adminPages.monitoring.verifyConnection')
                    }}
                  </button>
                  <BaseButton
                    v-if="row.failed || row.updateFailed"
                    size="sm"
                    :loading="retryingComponent === row.component"
                    @click="retryComponent(row)"
                  >
                    {{ t('adminPages.monitoring.retryDeployment') }}
                  </BaseButton>
                </div>

                <p
                  v-if="row.failed || row.updateFailed"
                  class="component-error"
                  :class="{ 'is-warning': row.updateFailed }"
                >
                  {{
                    row.updateFailed
                      ? t('adminPages.monitoring.capabilityUpdateFailedActive')
                      : jobFailureSummary(row.latest || row.job)
                  }}
                </p>
              </article>

              <p
                v-if="connectionMessage"
                class="connection-result"
                :class="
                  connectionStatus === 'success' ? 'is-success' : 'is-error'
                "
              >
                {{ connectionMessage }}
              </p>
            </section>

            <section
              v-else-if="activeTab === 'history'"
              class="deployment-history-panel"
            >
              <div class="deployment-history-heading">
                <p>{{ t('adminPages.monitoring.allExecutionRecords') }}</p>
                <div class="deployment-history-filters">
                  <select
                    v-model="historyComponentFilter"
                    class="admin-filter-control min-w-36"
                    :aria-label="t('adminPages.monitoring.taskType')"
                  >
                    <option value="">
                      {{ t('adminPages.monitoring.allTaskTypes') }}
                    </option>
                    <option
                      v-for="component in componentOptions"
                      :key="component"
                      :value="component"
                    >
                      {{ taskTypeLabel(component) }}
                    </option>
                  </select>
                  <select
                    v-model="historyStatusFilter"
                    class="admin-filter-control min-w-32"
                    :aria-label="t('common.status')"
                  >
                    <option value="">
                      {{ t('adminPages.monitoring.allStatuses') }}
                    </option>
                    <option value="queued">
                      {{ t('adminPages.monitoring.statusQueued') }}
                    </option>
                    <option value="running">
                      {{ t('adminPages.monitoring.statusRunning') }}
                    </option>
                    <option value="success">{{ t('common.success') }}</option>
                    <option value="failed">
                      {{ t('adminPages.monitoring.statusFailed') }}
                    </option>
                  </select>
                </div>
              </div>

              <div
                v-if="filteredHistory.length"
                class="hidden overflow-x-auto md:block"
              >
                <table class="deployment-history-table">
                  <thead>
                    <tr>
                      <th>{{ t('adminPages.monitoring.taskType') }}</th>
                      <th>{{ t('common.status') }}</th>
                      <th>{{ t('adminPages.monitoring.startedAt') }}</th>
                      <th>{{ t('adminPages.monitoring.duration') }}</th>
                      <th class="text-right">{{ t('common.actions') }}</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr
                      v-for="attempt in filteredHistory"
                      :key="attempt.job_id"
                    >
                      <td class="font-semibold text-slate-900">
                        {{ taskTypeLabel(attempt.component) }}
                      </td>
                      <td>
                        <span
                          class="deployment-table-status"
                          :class="`is-${normalizeStatus(attempt.host_status)}`"
                        >
                          {{ statusLabel(attempt.host_status) }}
                        </span>
                      </td>
                      <td>{{ formatDateTime(attempt.created_at) }}</td>
                      <td>{{ formatDuration(attempt.duration_seconds) }}</td>
                      <td class="text-right">
                        <button
                          type="button"
                          class="deployment-log-link"
                          @click="selectAttempt(attempt)"
                        >
                          {{ t('adminPages.monitoring.viewDetails') }}
                        </button>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>

              <div
                v-if="filteredHistory.length"
                class="divide-y divide-slate-200 md:hidden"
              >
                <article
                  v-for="attempt in filteredHistory"
                  :key="attempt.job_id"
                  class="history-mobile-row"
                >
                  <div class="flex items-center justify-between gap-3">
                    <span class="font-semibold text-slate-900">
                      {{ taskTypeLabel(attempt.component) }}
                    </span>
                    <span
                      class="deployment-table-status"
                      :class="`is-${normalizeStatus(attempt.host_status)}`"
                    >
                      {{ statusLabel(attempt.host_status) }}
                    </span>
                  </div>
                  <p>
                    {{ formatDateTime(attempt.created_at) }} ·
                    {{ formatDuration(attempt.duration_seconds) }}
                  </p>
                  <button
                    type="button"
                    class="deployment-log-link"
                    @click="selectAttempt(attempt)"
                  >
                    {{ t('adminPages.monitoring.viewDetails') }}
                  </button>
                </article>
              </div>

              <div v-else class="deployment-empty">
                {{ t('adminPages.monitoring.noDeploymentHistory') }}
              </div>
            </section>

            <section v-else class="execution-detail-panel">
              <div class="execution-detail-toolbar">
                <button
                  type="button"
                  class="execution-back"
                  @click="setTab('history')"
                >
                  <span aria-hidden="true">←</span>
                  {{ t('adminPages.monitoring.returnToExecutionHistory') }}
                </button>
                <select
                  v-if="allHistory.length"
                  :value="selectedAttempt?.job_id"
                  class="deployment-attempt-select"
                  :aria-label="t('adminPages.monitoring.selectAttempt')"
                  @change="selectAttemptById($event.target.value)"
                >
                  <option
                    v-for="attempt in allHistory"
                    :key="attempt.job_id"
                    :value="attempt.job_id"
                  >
                    {{ formatExecutionOption(attempt) }}
                  </option>
                </select>
              </div>

              <div v-if="jobLoading" class="deployment-empty">
                {{ t('common.loading') }}
              </div>
              <template v-else-if="selectedJob && selectedAttempt">
                <header class="execution-detail-heading">
                  <div>
                    <h2>{{ taskTypeLabel(selectedAttempt.component) }}</h2>
                    <p>{{ formatDateTime(selectedAttempt.created_at) }}</p>
                  </div>
                  <span
                    class="deployment-table-status"
                    :class="`is-${detailStatus}`"
                  >
                    {{ statusLabel(detailStatus) }}
                  </span>
                </header>

                <dl class="execution-summary">
                  <div>
                    <dt>{{ t('common.status') }}</dt>
                    <dd>{{ statusLabel(detailStatus) }}</dd>
                  </div>
                  <div>
                    <dt>{{ t('adminPages.monitoring.startedAt') }}</dt>
                    <dd>
                      {{
                        formatDateTime(
                          selectedJob.started_at || selectedJob.created_at
                        )
                      }}
                    </dd>
                  </div>
                  <div>
                    <dt>{{ t('adminPages.monitoring.duration') }}</dt>
                    <dd>{{ formatDuration(selectedJob.duration_seconds) }}</dd>
                  </div>
                </dl>

                <section class="execution-capability-summary">
                  <div class="execution-capability-heading">
                    <h2>
                      {{ t('adminPages.monitoring.deploymentCapabilities') }}
                    </h2>
                    <BaseButton
                      v-if="selectedAttempt.component === 'categraf'"
                      variant="outline"
                      size="sm"
                      @click="openCapabilityAdjustment"
                    >
                      {{ t('adminPages.monitoring.adjustCapabilities') }}
                    </BaseButton>
                  </div>
                  <div class="capability-list">
                    <span
                      v-for="capability in selectedJobCapabilities"
                      :key="capability"
                    >
                      {{ capability }}
                    </span>
                  </div>
                </section>

                <section class="execution-process">
                  <h2>{{ t('adminPages.monitoring.executionProgress') }}</h2>
                  <ol
                    class="execution-progress"
                    :aria-label="t('adminPages.monitoring.executionProgress')"
                  >
                    <li
                      v-for="(stage, index) in progressStages"
                      :key="stage.key"
                      :class="progressStepState(index)"
                    >
                      <span class="execution-progress-dot">
                        {{ progressStepMarker(index) }}
                      </span>
                      <span>{{ stage.label }}</span>
                    </li>
                  </ol>
                </section>

                <section
                  v-if="detailFailed"
                  class="execution-failure-diagnosis"
                >
                  <h2>{{ t('adminPages.monitoring.failureDiagnosis') }}</h2>
                  <p>{{ jobFailureSummary(selectedJob) }}</p>
                </section>

                <section class="execution-log-section">
                  <div class="deployment-log-heading">
                    <div>
                      <h2>
                        {{ t('adminPages.monitoring.fullAnsibleOutput') }}
                      </h2>
                      <p>
                        {{ taskTypeLabel(selectedAttempt.component) }} ·
                        {{ formatDateTime(selectedAttempt.created_at) }}
                      </p>
                    </div>
                    <BaseButton
                      variant="outline"
                      size="sm"
                      :disabled="!selectedJob.logs?.length"
                      @click="copyLogs"
                    >
                      {{ t('adminPages.monitoring.copyLogs') }}
                    </BaseButton>
                  </div>
                  <pre class="deployment-log-block">{{
                    (selectedJob.logs || []).join('\n') ||
                    t('common.emptyValue')
                  }}</pre>
                </section>
              </template>
              <div v-else class="deployment-empty">
                {{ t('adminPages.monitoring.noDeploymentHistory') }}
              </div>
            </section>
          </section>
        </template>
      </AdminPageState>
    </section>
  </AdminLayout>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import AdminLayout from '@/admin/layout/AdminLayout.vue'
import AdminPageState from '@/admin/components/AdminPageState.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import { monitoringStackApi } from '@/admin/api/monitoringStack'
import { normalizeHostSummaries } from '@/admin/utils/monitoringJobHistory'
import { useToast } from '@/composables/useToast'
import { getApiErrorMessage } from '@/utils/apiError'

const { t, locale } = useI18n()
const route = useRoute()
const router = useRouter()
const { showSuccess, showError } = useToast()

const componentOptions = ['categraf', 'blackbox']
const loading = ref(false)
const error = ref('')
const hostSummaries = ref([])
const hostRecords = ref([])
const componentJobs = ref({})
const selectedJob = ref(null)
const jobLoading = ref(false)
const retryingComponent = ref('')
const testingConnection = ref(false)
const connectionStatus = ref('')
const connectionMessage = ref('')
const historyComponentFilter = ref('')
const historyStatusFilter = ref('')
let pollTimer = null
let jobRequestToken = 0

const hostId = computed(() => Number(route.params.hostId))
const host = computed(
  () =>
    hostSummaries.value.find((item) => Number(item.host_id) === hostId.value) ||
    null
)
const hostRecord = computed(
  () =>
    hostRecords.value.find((item) => Number(item.id) === hostId.value) || null
)
const activeTab = computed(() =>
  ['current', 'history', 'detail'].includes(String(route.query.tab))
    ? String(route.query.tab)
    : 'current'
)
const allHistory = computed(() =>
  componentOptions
    .flatMap((component) => host.value?.components?.[component]?.history || [])
    .sort(
      (left, right) => new Date(right.created_at) - new Date(left.created_at)
    )
)
const requestedJobId = computed(() => {
  const value = Number(route.query.job)
  return Number.isInteger(value) && value > 0 ? value : null
})
const selectedAttempt = computed(
  () =>
    allHistory.value.find(
      (attempt) => Number(attempt.job_id) === Number(requestedJobId.value)
    ) ||
    allHistory.value[0] ||
    null
)
const filteredHistory = computed(() => {
  return allHistory.value.filter((attempt) => {
    const matchesComponent =
      !historyComponentFilter.value ||
      attempt.component === historyComponentFilter.value
    const matchesStatus =
      !historyStatusFilter.value ||
      normalizeStatus(attempt.host_status) === historyStatusFilter.value
    return matchesComponent && matchesStatus
  })
})
const componentStatusMap = computed(() =>
  Object.fromEntries(
    (hostRecord.value?.component_statuses || []).map((item) => [
      item.component,
      item
    ])
  )
)
const componentRows = computed(() =>
  componentOptions.map((component) => {
    const latest = host.value?.components?.[component]?.latest || null
    const runtime = componentStatusMap.value[component] || null
    const job = componentJobs.value[component] || null
    const status = normalizeStatus(runtime?.status || latest?.host_status)
    const latestStatus = normalizeStatus(latest?.host_status)
    const runtimeStatus = normalizeRuntimeStatus(runtime?.runtime_status)
    const updateFailed = Boolean(
      runtime?.active_job_id &&
      latestStatus === 'failed' &&
      Number(latest?.job_id) !== Number(runtime.active_job_id)
    )
    return {
      component,
      latest,
      runtime,
      job,
      status,
      runtimeStatus,
      updateFailed,
      failed: status === 'failed',
      sshFailure: jobFailureReason(latest || job).startsWith('ssh_'),
      installDir: runtime?.install_dir || job?.install_dir || '',
      runtimeEndpoint: runtime?.runtime_endpoint || '',
      capabilities: componentCapabilities(component, job)
    }
  })
)
const componentStats = computed(() => ({
  installed: componentRows.value.filter((row) => row.status === 'success')
    .length,
  total: componentRows.value.length,
  online: componentRows.value.filter((row) => row.runtimeStatus === 'online')
    .length
}))
const detailStatus = computed(() =>
  normalizeStatus(
    selectedAttempt.value?.host_status || selectedJob.value?.status
  )
)
const detailFailed = computed(() => detailStatus.value === 'failed')
const selectedJobCapabilities = computed(() => {
  if (!selectedAttempt.value?.component) return []
  return componentCapabilities(
    selectedAttempt.value.component,
    selectedJob.value
  )
})
const progressStages = computed(() => [
  { key: 'queued', label: t('adminPages.monitoring.progressQueued') },
  { key: 'preparing', label: t('adminPages.monitoring.progressPreparing') },
  { key: 'connecting', label: t('adminPages.monitoring.progressConnecting') },
  { key: 'installing', label: t('adminPages.monitoring.progressInstalling') },
  { key: 'verifying', label: t('adminPages.monitoring.progressVerifying') },
  { key: 'completed', label: t('adminPages.monitoring.progressCompleted') }
])
const currentProgressStep = computed(() => {
  if (detailStatus.value === 'success') return progressStages.value.length
  if (
    detailFailed.value &&
    jobFailureReason(selectedJob.value).startsWith('ssh_')
  )
    return 3
  const current = Number(selectedJob.value?.progress?.current || 0)
  if (current)
    return Math.min(progressStages.value.length, Math.max(1, current))
  return detailFailed.value ? 4 : 1
})

const workspaceTabs = computed(() => [
  { key: 'current', label: t('adminPages.monitoring.currentStatusTab') },
  { key: 'history', label: t('adminPages.monitoring.executionHistoryTab') },
  { key: 'detail', label: t('adminPages.monitoring.executionDetailTab') }
])

function normalizeList(data) {
  return Array.isArray(data) ? data : data?.results || []
}

function normalizeStatus(status) {
  const value = String(status || '').toLowerCase()
  if (['succeeded', 'completed', 'done', 'installed'].includes(value))
    return 'success'
  if (['error', 'timeout'].includes(value)) return 'failed'
  return value || 'empty'
}

function normalizeRuntimeStatus(status) {
  const value = String(status || '').toLowerCase()
  if (['online', 'healthy', 'up', 'running'].includes(value)) return 'online'
  if (['offline', 'down', 'failed', 'error'].includes(value)) return 'offline'
  return 'unknown'
}

function statusLabel(status) {
  const labels = {
    queued: t('adminPages.monitoring.statusQueued'),
    running: t('adminPages.monitoring.statusRunning'),
    success: t('common.success'),
    failed: t('adminPages.monitoring.statusFailed')
  }
  return labels[normalizeStatus(status)] || t('common.emptyValue')
}

function installationLabel(row) {
  if (row.status === 'success') return t('adminPages.monitoring.installed')
  if (row.status === 'failed') return t('adminPages.monitoring.statusFailed')
  if (row.status === 'queued') return t('adminPages.monitoring.statusQueued')
  if (row.status === 'running') return t('adminPages.monitoring.statusRunning')
  return t('adminPages.monitoring.notInstalled')
}

function runtimeLabel(status) {
  const labels = {
    online: t('adminPages.monitoring.runtimeOnline'),
    offline: t('adminPages.monitoring.runtimeAbnormal'),
    unknown: t('adminPages.monitoring.runtimeUnknown')
  }
  return labels[status] || labels.unknown
}

function componentLabel(component) {
  return component === 'blackbox' ? 'blackbox' : 'Categraf'
}

function taskTypeLabel(component) {
  return t('adminPages.monitoring.installTaskType', {
    component: componentLabel(component)
  })
}

function componentCapabilities(component, job) {
  if (component === 'categraf') {
    const profileLabels = {
      'linux-basic': t('adminPages.monitoring.profileLinuxBasic'),
      'docker-host': t('adminPages.monitoring.profileDockerHost')
    }
    const profiles = (job?.profiles || []).map(
      (profile) => profileLabels[profile] || profile
    )
    return profiles.length
      ? profiles
      : [t('adminPages.monitoring.defaultCollectionProfile')]
  }

  const capabilities = []
  if ((hostRecord.value?.roles || []).includes('probe_node')) {
    capabilities.push(t('adminPages.monitoring.probeNodeCapability'))
  }
  if (job?.probe_name) {
    capabilities.push(
      t('adminPages.monitoring.probeNameCapability', { name: job.probe_name })
    )
  }
  if (job?.blackbox_port) {
    capabilities.push(
      t('adminPages.monitoring.portCapability', { port: job.blackbox_port })
    )
  }
  return capabilities.length
    ? capabilities
    : [t('adminPages.monitoring.defaultProbeProfile')]
}

function formatDuration(value) {
  if (value === null || value === undefined) return t('common.emptyValue')
  return value < 60 ? `${value}s` : `${Math.floor(value / 60)}m ${value % 60}s`
}

function formatDateTime(value) {
  return value
    ? new Intl.DateTimeFormat(locale.value, {
        dateStyle: 'short',
        timeStyle: 'short'
      }).format(new Date(value))
    : t('common.emptyValue')
}

function formatExecutionOption(attempt) {
  return `${taskTypeLabel(attempt.component)} · ${statusLabel(attempt.host_status)} · ${formatDateTime(attempt.created_at)}`
}

function progressStepState(index) {
  const step = index + 1
  if (detailFailed.value && step === currentProgressStep.value)
    return 'is-failed'
  if (
    step < currentProgressStep.value ||
    (!detailFailed.value && step === currentProgressStep.value)
  )
    return 'is-complete'
  return 'is-pending'
}

function progressStepMarker(index) {
  const step = index + 1
  if (
    step < currentProgressStep.value ||
    (!detailFailed.value && step === currentProgressStep.value)
  )
    return '✓'
  return step
}

function jobFailureReason(job) {
  const reason = String(
    job?.reason_code || job?.progress?.reason_code || ''
  ).toLowerCase()
  if (reason && reason !== 'failed') return reason
  const output = [job?.last_error, ...(job?.logs || [])]
    .join('\n')
    .toLowerCase()
  if (
    output.includes('error in libcrypto') ||
    output.includes('invalid format')
  )
    return 'ssh_key_invalid'
  if (
    output.includes('permission denied') ||
    output.includes('authentication failed')
  )
    return 'ssh_auth_failed'
  if (output.includes("connection plugin 'paramiko' was not found"))
    return 'ssh_runtime_unavailable'
  if (output.includes('unreachable!')) return 'ssh_unreachable'
  return reason || 'ansible_failed'
}

function jobFailureSummary(job) {
  const labels = {
    ssh_key_invalid: 'jobFailureSshKeyInvalid',
    ssh_auth_failed: 'jobFailureSshAuthFailed',
    ssh_unreachable: 'jobFailureSshUnreachable',
    ssh_runtime_unavailable: 'jobFailureSshRuntimeUnavailable',
    timeout: 'jobFailureTimeout',
    no_hosts: 'jobFailureNoHosts',
    ansible_missing: 'jobFailureAnsibleMissing',
    dispatch_failed: 'jobFailureDispatchFailed',
    worker_failed: 'jobFailureWorkerFailed',
    ansible_failed: 'jobFailureAnsibleFailed'
  }
  return t(
    `adminPages.monitoring.${labels[jobFailureReason(job)] || labels.ansible_failed}`
  )
}

function queryWith(updates) {
  return Object.fromEntries(
    Object.entries({ ...route.query, ...updates }).filter(
      ([, value]) => value !== undefined && value !== null && value !== ''
    )
  )
}

function goBack() {
  router.push({ name: 'AdminMonitoringJobs' })
}

function openCapabilityAdjustment() {
  const currentJob = componentJobs.value.categraf
  const currentProfiles = currentJob?.profiles || []
  router.push({
    path: '/management/monitoring/assets',
    query: {
      adjust: 'categraf',
      host: String(hostId.value),
      baseJob: currentJob?.id ? String(currentJob.id) : undefined,
      profiles: (currentProfiles.length
        ? currentProfiles
        : ['linux-basic']
      ).join(',')
    }
  })
}

function setTab(tab) {
  if (tab === 'detail') {
    const attempt = selectedAttempt.value || allHistory.value[0]
    router.replace({
      query: queryWith({
        tab,
        component: attempt?.component,
        job: attempt?.job_id
      })
    })
    return
  }
  router.replace({
    query: queryWith({ tab, component: undefined, job: undefined })
  })
}

function selectAttempt(attempt) {
  router.replace({
    query: queryWith({
      tab: 'detail',
      component: attempt.component,
      job: attempt.job_id
    })
  })
}

function selectAttemptById(jobId) {
  const attempt = allHistory.value.find(
    (item) => Number(item.job_id) === Number(jobId)
  )
  if (attempt) selectAttempt(attempt)
}

function openComponentDetails(row) {
  if (row.latest) selectAttempt(row.latest)
}

async function loadComponentJobs() {
  const entries = await Promise.all(
    componentOptions.map(async (component) => {
      const runtime = componentStatusMap.value[component]
      const latest = host.value?.components?.[component]?.latest
      const jobId = runtime?.active_job_id || latest?.job_id
      if (!jobId) return [component, null]
      return [component, await monitoringStackApi.getJob(jobId)]
    })
  )
  componentJobs.value = Object.fromEntries(entries)
}

async function loadPage() {
  loading.value = true
  error.value = ''
  try {
    const [summaryData, hostData] = await Promise.all([
      monitoringStackApi.getJobHostSummaries(),
      monitoringStackApi.getHosts()
    ])
    hostSummaries.value = normalizeHostSummaries(summaryData)
    hostRecords.value = normalizeList(hostData)
    if (!host.value) return
    await loadComponentJobs()
    if (activeTab.value === 'detail') {
      await loadSelectedJob()
    } else if (route.query.component || route.query.job) {
      await router.replace({
        query: queryWith({ component: undefined, job: undefined })
      })
    }
  } catch (err) {
    error.value = getApiErrorMessage(err, err?.message || t('common.error'))
  } finally {
    loading.value = false
  }
}

async function loadSelectedJob() {
  const jobId = selectedAttempt.value?.job_id
  clearPolling()
  if (!jobId) {
    selectedJob.value = null
    return
  }
  const token = ++jobRequestToken
  jobLoading.value = true
  try {
    const cached = Object.values(componentJobs.value).find(
      (job) => Number(job?.id) === Number(jobId)
    )
    const data = cached || (await monitoringStackApi.getJob(jobId))
    if (token !== jobRequestToken) return
    selectedJob.value = data
    startPolling()
  } catch (err) {
    if (token === jobRequestToken) showError(err)
  } finally {
    if (token === jobRequestToken) jobLoading.value = false
  }
}

function clearPolling() {
  if (pollTimer) window.clearInterval(pollTimer)
  pollTimer = null
}

function startPolling() {
  clearPolling()
  if (
    !['queued', 'running'].includes(normalizeStatus(selectedJob.value?.status))
  )
    return
  pollTimer = window.setInterval(async () => {
    if (!selectedJob.value?.id || jobLoading.value) return
    await loadSelectedJob()
    if (
      !['queued', 'running'].includes(
        normalizeStatus(selectedJob.value?.status)
      )
    ) {
      clearPolling()
      await refreshData()
    }
  }, 1000)
}

async function refreshData() {
  hostSummaries.value = normalizeHostSummaries(
    await monitoringStackApi.getJobHostSummaries()
  )
  await loadComponentJobs()
}

async function retryComponent(row) {
  if (!row.latest?.job_id || (!row.failed && !row.updateFailed)) return
  retryingComponent.value = row.component
  try {
    const job = await monitoringStackApi.retryJob(row.latest.job_id, {
      host_id: hostId.value
    })
    componentJobs.value = { ...componentJobs.value, [row.component]: job }
    selectedJob.value = job
    await refreshData()
    showSuccess(t('adminPages.monitoring.jobDispatched', { id: job.id }))
    startPolling()
  } catch (err) {
    showError(err)
  } finally {
    retryingComponent.value = ''
  }
}

async function testConnection() {
  if (!host.value) return
  testingConnection.value = true
  connectionStatus.value = ''
  connectionMessage.value = ''
  try {
    const record = hostRecord.value || {}
    const result = await monitoringStackApi.testHostConnection({
      host_id: hostId.value,
      address: record.address || host.value.address,
      ssh_user: record.ssh_user || 'root',
      ssh_port: record.ssh_port || 22,
      ssh_auth_type: record.ssh_auth_type || 'private_key'
    })
    connectionStatus.value = 'success'
    connectionMessage.value = t(
      'adminPages.monitoring.sshConnectionSuccessDetail',
      {
        latency: result?.latency_ms || 0
      }
    )
    showSuccess(connectionMessage.value)
  } catch (err) {
    connectionStatus.value = 'error'
    connectionMessage.value = getApiErrorMessage(
      err,
      t('adminPages.monitoring.sshConnectionFailedDetail')
    )
    showError(err)
  } finally {
    testingConnection.value = false
  }
}

async function copyLogs() {
  const content = (selectedJob.value?.logs || []).join('\n')
  if (!content) return
  const copied = await copyText(content)
  copied
    ? showSuccess(t('adminPages.monitoring.logsCopied'))
    : showError(t('adminPages.monitoring.copyFailed'))
}

async function copyText(content) {
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(content)
      return true
    }
  } catch (_error) {
    // Continue with the fallback for non-secure internal origins.
  }

  const textarea = document.createElement('textarea')
  textarea.value = content
  textarea.setAttribute('readonly', '')
  textarea.style.position = 'fixed'
  textarea.style.left = '-9999px'
  document.body.appendChild(textarea)
  textarea.focus()
  textarea.select()
  let copied = false
  try {
    copied = document.execCommand('copy')
  } finally {
    textarea.remove()
  }
  return copied
}

watch(
  () => [activeTab.value, selectedAttempt.value?.job_id],
  async ([tab, jobId], [oldTab, oldJobId]) => {
    if (loading.value || tab !== 'detail') return
    if (tab !== oldTab || jobId !== oldJobId) await loadSelectedJob()
  }
)

onMounted(loadPage)
onBeforeUnmount(clearPolling)
</script>

<style scoped>
.deployment-status-page {
  padding-bottom: 2.5rem;
}

.deployment-back {
  display: inline-flex;
  min-height: 2.25rem;
  align-items: center;
  gap: 0.45rem;
  border: 0;
  background: transparent;
  padding: 0;
  color: #64748b;
  font-size: 0.8125rem;
  font-weight: 650;
}

.deployment-back:hover {
  color: #0f172a;
}

.deployment-heading {
  padding: 0.9rem 0 1.25rem;
}

.deployment-title {
  margin: 0;
  color: #0f172a;
  font-size: 1.5rem;
  font-weight: 750;
  line-height: 1.3;
}

.deployment-subtitle {
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem;
  margin: 0.4rem 0 0;
  color: #64748b;
  font-size: 0.8125rem;
}

.deployment-workspace {
  overflow: hidden;
  border: 1px solid #dbe3ec;
  border-radius: 0.5rem;
  background: #fff;
  box-shadow: 0 5px 14px rgb(15 23 42 / 8%);
}

.deployment-tabs {
  display: flex;
  min-height: 3rem;
  align-items: flex-end;
  gap: 0.25rem;
  overflow-x: auto;
  border-bottom: 1px solid #dbe3ec;
  padding: 0 1.125rem;
}

.deployment-tabs button {
  position: relative;
  min-height: 3rem;
  flex: none;
  border: 0;
  background: transparent;
  padding: 0 0.875rem;
  color: #64748b;
  font-size: 0.8125rem;
  font-weight: 700;
}

.deployment-tabs button.active {
  color: #0f172a;
}

.deployment-tabs button.active::after {
  position: absolute;
  right: 0.625rem;
  bottom: -1px;
  left: 0.625rem;
  height: 2px;
  background: #223248;
  content: '';
}

.component-overview {
  min-width: 0;
}

.component-overview-heading {
  display: flex;
  min-height: 4.5rem;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.875rem 1.25rem;
}

.component-overview-heading h2,
.deployment-log-heading h2 {
  margin: 0;
  color: #0f172a;
  font-size: 0.875rem;
  font-weight: 750;
}

.component-overview-heading p,
.deployment-log-heading p,
.deployment-history-heading p {
  margin: 0.3rem 0 0;
  color: #64748b;
  font-size: 0.75rem;
}

.host-enabled-state,
.component-state-badge,
.deployment-table-status {
  display: inline-flex;
  min-height: 1.5rem;
  align-items: center;
  border-radius: 999px;
  padding: 0 0.55rem;
  font-size: 0.6875rem;
  font-weight: 750;
  white-space: nowrap;
}

.host-enabled-state.is-enabled,
.component-state-badge.is-success,
.deployment-table-status.is-success {
  background: #ecfdf5;
  color: #047857;
}

.host-enabled-state.is-disabled,
.component-state-badge.is-empty {
  background: #f1f5f9;
  color: #64748b;
}

.component-state-badge.is-failed,
.deployment-table-status.is-failed {
  background: #fff1f2;
  color: #be123c;
}

.component-state-badge.is-running,
.component-state-badge.is-queued,
.deployment-table-status.is-running,
.deployment-table-status.is-queued {
  background: #eff6ff;
  color: #1d4ed8;
}

.component-list-heading,
.component-row {
  display: grid;
  grid-template-columns:
    minmax(9.5rem, 0.8fr) minmax(5.5rem, 0.45fr) minmax(5.5rem, 0.45fr)
    minmax(12rem, 1fr) minmax(12rem, 0.85fr) minmax(7.5rem, auto);
  align-items: center;
  column-gap: 1rem;
}

.component-list-heading {
  min-height: 2.5rem;
  border-top: 1px solid #dbe3ec;
  background: #f8fafc;
  padding: 0 1.25rem;
  color: #64748b;
  font-size: 0.6875rem;
  font-weight: 700;
}

.component-row {
  position: relative;
  min-height: 7.25rem;
  border-top: 1px solid #dbe3ec;
  padding: 1rem 1.25rem;
}

.component-identity {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 0.75rem;
}

.component-mark {
  display: grid;
  width: 2rem;
  height: 2rem;
  flex: none;
  place-items: center;
  border-radius: 0.4375rem;
  background: #eff6ff;
  color: #1d4ed8;
  font-size: 0.75rem;
  font-weight: 800;
}

.component-mark.is-blackbox {
  background: #f1f5f9;
  color: #334155;
}

.component-identity h3 {
  margin: 0;
  color: #0f172a;
  font-size: 0.875rem;
  font-weight: 750;
}

.component-identity p {
  margin: 0.25rem 0 0;
  overflow: hidden;
  color: #64748b;
  font-size: 0.6875rem;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.component-field-label {
  display: none;
  color: #64748b;
  font-size: 0.6875rem;
  font-weight: 650;
}

.runtime-state {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  color: #64748b;
  font-size: 0.75rem;
  font-weight: 700;
}

.runtime-state > span {
  width: 0.45rem;
  height: 0.45rem;
  border-radius: 50%;
  background: #94a3b8;
}

.runtime-state.is-online {
  color: #047857;
}

.runtime-state.is-online > span {
  background: #10b981;
}

.runtime-state.is-offline {
  color: #be123c;
}

.runtime-state.is-offline > span {
  background: #e11d48;
}

.capability-list {
  display: flex;
  flex-wrap: wrap;
  gap: 0.375rem;
}

.capability-list span {
  display: inline-flex;
  min-height: 1.625rem;
  align-items: center;
  border-radius: 0.375rem;
  background: #f1f5f9;
  padding: 0 0.5rem;
  color: #334155;
  font-size: 0.6875rem;
  font-weight: 650;
}

.component-location {
  display: grid;
  gap: 0.45rem;
  margin: 0;
}

.component-location div {
  display: grid;
  grid-template-columns: 4rem minmax(0, 1fr);
  gap: 0.5rem;
  font-size: 0.6875rem;
}

.component-location dt {
  color: #64748b;
}

.component-location dd {
  min-width: 0;
  margin: 0;
  overflow: hidden;
  color: #334155;
  font-weight: 650;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.component-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 0.45rem;
}

.deployment-text-action,
.deployment-log-link {
  border: 0;
  background: transparent;
  color: #2563eb;
  font-size: 0.75rem;
  font-weight: 700;
}

.deployment-text-action:disabled {
  cursor: not-allowed;
  color: #94a3b8;
}

.component-error {
  grid-column: 1 / -1;
  margin: 0.75rem 0 0;
  border-top: 1px solid #fecdd3;
  padding-top: 0.75rem;
  color: #be123c;
  font-size: 0.75rem;
}

.component-error.is-warning {
  border-color: #fde68a;
  color: #92400e;
}

.connection-result {
  margin: 0;
  border-top: 1px solid #dbe3ec;
  padding: 0.75rem 1.25rem;
  font-size: 0.75rem;
  font-weight: 650;
}

.connection-result.is-success {
  color: #047857;
}

.connection-result.is-error {
  color: #be123c;
}

.deployment-history-heading,
.deployment-log-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  border-bottom: 1px solid #dbe3ec;
  padding: 0.9375rem 1.25rem;
}

.deployment-history-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.8125rem;
}

.deployment-history-table th {
  height: 2.5rem;
  background: #f8fafc;
  padding: 0 1rem;
  color: #64748b;
  font-size: 0.6875rem;
  font-weight: 700;
  text-align: left;
  white-space: nowrap;
}

.deployment-history-table td {
  height: 3.125rem;
  border-top: 1px solid #dbe3ec;
  padding: 0 1rem;
  color: #334155;
  white-space: nowrap;
}

.execution-detail-panel {
  min-width: 0;
  padding-bottom: 1.25rem;
}

.execution-detail-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  border-bottom: 1px solid #dbe3ec;
  padding: 0.75rem 1.25rem;
}

.execution-back {
  display: inline-flex;
  min-height: 2.125rem;
  align-items: center;
  gap: 0.4rem;
  border: 0;
  background: transparent;
  padding: 0;
  color: #475569;
  font-size: 0.75rem;
  font-weight: 700;
}

.execution-back:hover {
  color: #0f172a;
}

.execution-detail-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 1.125rem 1.25rem 0.875rem;
}

.execution-detail-heading h2,
.execution-process h2,
.execution-capability-summary h2,
.execution-failure-diagnosis h2 {
  margin: 0;
  color: #0f172a;
  font-size: 0.875rem;
  font-weight: 750;
}

.execution-detail-heading p {
  margin: 0.3rem 0 0;
  color: #64748b;
  font-size: 0.75rem;
}

.execution-summary {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  margin: 0 1.25rem;
  border-top: 1px solid #dbe3ec;
  border-bottom: 1px solid #dbe3ec;
}

.execution-summary > div {
  min-width: 0;
  padding: 0.875rem 1rem;
  border-right: 1px solid #dbe3ec;
}

.execution-summary > div:first-child {
  padding-left: 0;
}

.execution-summary > div:last-child {
  border-right: 0;
}

.execution-summary dt {
  color: #64748b;
  font-size: 0.6875rem;
}

.execution-summary dd {
  margin: 0.35rem 0 0;
  color: #0f172a;
  font-size: 0.8125rem;
  font-weight: 700;
}

.execution-capability-summary {
  padding: 1rem 1.25rem 0;
}

.execution-capability-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
}

.execution-capability-summary .capability-list {
  margin-top: 0.625rem;
}

.execution-process {
  padding: 1.125rem 1.25rem 1.375rem;
}

.execution-progress {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  margin: 1.25rem 0 0;
  padding: 0;
  list-style: none;
}

.execution-progress li {
  position: relative;
  color: #64748b;
  font-size: 0.6875rem;
  text-align: center;
  white-space: nowrap;
}

.execution-progress li::before {
  position: absolute;
  top: 0.6875rem;
  right: 50%;
  left: -50%;
  height: 2px;
  background: #cbd5e1;
  content: '';
}

.execution-progress li:first-child::before {
  display: none;
}

.execution-progress-dot {
  position: relative;
  z-index: 1;
  display: grid;
  width: 1.5rem;
  height: 1.5rem;
  margin: 0 auto 0.5rem;
  place-items: center;
  border: 2px solid #cbd5e1;
  border-radius: 50%;
  background: #fff;
  color: #64748b;
  font-size: 0.625rem;
  font-weight: 750;
}

.execution-progress li.is-complete::before,
.execution-progress li.is-failed::before {
  background: #2563eb;
}

.execution-progress li.is-complete .execution-progress-dot {
  border-color: #2563eb;
  background: #2563eb;
  color: #fff;
}

.execution-progress li.is-failed {
  color: #be123c;
  font-weight: 700;
}

.execution-progress li.is-failed .execution-progress-dot {
  border-color: #be123c;
  background: #be123c;
  color: #fff;
}

.execution-failure-diagnosis {
  margin: 0 1.25rem 1.25rem;
  border: 1px solid #fecdd3;
  border-radius: 0.4375rem;
  background: #fff1f2;
  padding: 0.875rem 1rem;
}

.execution-failure-diagnosis h2,
.execution-failure-diagnosis p {
  color: #9f1239;
}

.execution-failure-diagnosis p {
  margin: 0.35rem 0 0;
  font-size: 0.8125rem;
  line-height: 1.55;
}

.execution-log-section {
  border-top: 1px solid #dbe3ec;
}

.deployment-attempt-select {
  min-height: 2.125rem;
  max-width: 24rem;
  border: 1px solid #dbe3ec;
  border-radius: 0.375rem;
  background: #fff;
  padding: 0 0.625rem;
  color: #334155;
  font-size: 0.75rem;
  font-weight: 650;
}

.deployment-log-block {
  min-height: 24rem;
  max-height: 46rem;
  margin: 0 1.25rem;
  overflow: auto;
  border-radius: 0.4375rem;
  background: #020617;
  padding: 1rem;
  color: #e2e8f0;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 0.75rem;
  line-height: 1.55;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.deployment-empty {
  min-height: 13rem;
  display: grid;
  place-items: center;
  color: #64748b;
  font-size: 0.8125rem;
}

.history-mobile-row {
  position: relative;
  padding: 1rem;
}

.history-mobile-row p {
  margin: 0.5rem 0 0.75rem;
  color: #64748b;
  font-size: 0.75rem;
}

.deployment-history-filters {
  display: flex;
  align-items: center;
  gap: 0.625rem;
  flex-wrap: wrap;
}

@media (max-width: 1120px) {
  .component-list-heading {
    display: none;
  }

  .component-row {
    grid-template-columns: minmax(10rem, 0.8fr) repeat(2, minmax(7rem, 0.45fr));
    row-gap: 1rem;
  }

  .component-capabilities,
  .component-location {
    grid-column: span 2;
  }

  .component-actions {
    align-self: end;
  }

  .component-field-label {
    display: block;
    margin-bottom: 0.35rem;
  }
}

@media (max-width: 720px) {
  .deployment-status-page {
    padding-right: 0;
    padding-left: 0;
  }

  .deployment-back,
  .deployment-heading {
    margin-right: 1rem;
    margin-left: 1rem;
  }

  .deployment-title {
    font-size: 1.25rem;
  }

  .deployment-workspace {
    margin: 0 1rem;
  }

  .deployment-tabs {
    padding: 0 0.25rem;
  }

  .deployment-tabs button {
    flex: 1;
    padding: 0 0.5rem;
  }

  .component-overview-heading,
  .deployment-history-heading,
  .deployment-log-heading,
  .execution-detail-toolbar {
    align-items: stretch;
    flex-direction: column;
  }

  .component-row {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    padding: 1rem;
  }

  .component-identity,
  .component-capabilities,
  .component-location,
  .component-actions,
  .component-error {
    grid-column: 1 / -1;
  }

  .component-actions {
    justify-content: flex-start;
  }

  .component-actions :deep(.btn) {
    flex: 1;
  }

  .component-location div {
    grid-template-columns: 4.75rem minmax(0, 1fr);
  }

  .deployment-attempt-select {
    width: 100%;
    max-width: none;
  }

  .deployment-history-filters,
  .deployment-history-filters select {
    width: 100%;
  }

  .deployment-log-block {
    min-height: 20rem;
    margin: 0 1rem;
  }

  .execution-summary {
    grid-template-columns: 1fr;
    margin: 0 1rem;
  }

  .execution-summary > div,
  .execution-summary > div:first-child {
    border-right: 0;
    border-bottom: 1px solid #dbe3ec;
    padding: 0.75rem 0;
  }

  .execution-summary > div:last-child {
    border-bottom: 0;
  }

  .execution-process {
    padding-right: 1rem;
    padding-left: 1rem;
  }

  .execution-progress {
    grid-template-columns: 1fr;
    gap: 0.75rem;
    margin-top: 1rem;
  }

  .execution-progress li {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    text-align: left;
  }

  .execution-progress li::before {
    top: -0.75rem;
    right: auto;
    left: 0.6875rem;
    width: 2px;
    height: 0.75rem;
  }

  .execution-progress-dot {
    flex: 0 0 auto;
    margin: 0;
  }

  .execution-failure-diagnosis {
    margin-right: 1rem;
    margin-left: 1rem;
  }
}
</style>
