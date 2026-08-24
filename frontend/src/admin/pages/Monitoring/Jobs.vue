<template>
  <AdminLayout>
    <PageFrame variant="soft" :title="t('adminPages.monitoring.jobsTitle')">
      <nav
        class="mb-4 flex gap-1 border-b border-slate-200"
        :aria-label="t('adminPages.monitoring.jobsTitle')"
      >
        <button
          v-for="tab in deploymentTabs"
          :key="tab.key"
          type="button"
          class="relative min-h-11 px-4 text-sm font-semibold transition-colors"
          :class="
            activeView === tab.key
              ? 'text-slate-950'
              : 'text-slate-500 hover:text-slate-800'
          "
          @click="selectView(tab.key)"
        >
          {{ tab.label }}
          <span
            v-if="activeView === tab.key"
            class="absolute inset-x-2 -bottom-px h-0.5 rounded-full bg-slate-900"
          ></span>
        </button>
      </nav>

      <DeploymentResources v-if="activeView === 'resources'" />

      <AdminListSection v-else>
        <template #toolbarStart>
          <div class="flex flex-wrap gap-2">
            <input
              v-model.trim="hostSearch"
              class="admin-filter-control min-w-52"
              :placeholder="t('adminPages.monitoring.jobHostSearch')"
            />
            <select
              v-model="componentFilter"
              class="admin-filter-control min-w-36"
            >
              <option value="">
                {{ t('adminPages.monitoring.allComponents') }}
              </option>
              <option value="categraf">Categraf</option>
              <option value="blackbox">blackbox</option>
            </select>
            <select
              v-model="statusFilter"
              class="admin-filter-control min-w-32"
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
              <option value="success">
                {{ t('adminPages.monitoring.statusSuccess') }}
              </option>
              <option value="failed">
                {{ t('adminPages.monitoring.statusFailed') }}
              </option>
            </select>
          </div>
        </template>
        <template #toolbarEnd>
          <div class="flex items-center gap-3">
            <span class="text-xs text-slate-500">
              {{
                t('adminPages.monitoring.hostSummaryCount', {
                  count: filteredHosts.length
                })
              }}
            </span>
            <BaseButton
              variant="outline"
              size="sm"
              :loading="loading"
              @click="load"
            >
              {{ t('common.refresh') }}
            </BaseButton>
          </div>
        </template>

        <AdminPageState
          :loading="loading"
          :error="error"
          :empty="!filteredHosts.length"
        >
          <div class="hidden xl:block">
            <AdminTable>
              <thead>
                <tr>
                  <th class="admin-table-head">
                    {{ t('adminPages.monitoring.hostname') }}
                  </th>
                  <th class="admin-table-head">Categraf</th>
                  <th class="admin-table-head">blackbox</th>
                  <th class="admin-table-head text-right">
                    {{ t('common.actions') }}
                  </th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="host in filteredHosts"
                  :key="host.host_id"
                  class="admin-table-row align-middle"
                >
                  <td class="admin-table-cell">
                    <p class="font-semibold text-slate-900">
                      {{ host.hostname }}
                    </p>
                    <p class="mt-1 text-xs text-slate-500">
                      {{ host.address }}
                    </p>
                  </td>
                  <td class="admin-table-cell">
                    <ComponentState :summary="host.components?.categraf" />
                  </td>
                  <td class="admin-table-cell">
                    <ComponentState :summary="host.components?.blackbox" />
                  </td>
                  <td class="admin-table-cell text-right">
                    <BaseButton
                      variant="outline"
                      size="sm"
                      @click="openHostStatus(host)"
                    >
                      {{ t('adminPages.monitoring.viewDeploymentStatus') }}
                    </BaseButton>
                  </td>
                </tr>
              </tbody>
            </AdminTable>
          </div>

          <div class="divide-y divide-slate-200 xl:hidden">
            <article
              v-for="host in filteredHosts"
              :key="host.host_id"
              class="py-4 first:pt-0 last:pb-0"
            >
              <div class="flex items-start justify-between gap-4">
                <div class="min-w-0">
                  <p class="truncate text-sm font-semibold text-slate-900">
                    {{ host.hostname }}
                  </p>
                  <p class="mt-1 truncate text-xs text-slate-500">
                    {{ host.address }}
                  </p>
                </div>
                <BaseButton
                  variant="outline"
                  size="sm"
                  @click="openHostStatus(host)"
                >
                  {{ t('adminPages.monitoring.viewDeploymentStatus') }}
                </BaseButton>
              </div>
              <div class="mt-4 grid grid-cols-2 gap-x-5 gap-y-3">
                <div>
                  <p class="mb-1.5 text-xs font-medium text-slate-500">
                    Categraf
                  </p>
                  <ComponentState :summary="host.components?.categraf" />
                </div>
                <div>
                  <p class="mb-1.5 text-xs font-medium text-slate-500">
                    blackbox
                  </p>
                  <ComponentState :summary="host.components?.blackbox" />
                </div>
              </div>
            </article>
          </div>
        </AdminPageState>
      </AdminListSection>
    </PageFrame>

    <BaseModal
      :show="Boolean(selectedJob)"
      :title="
        selectedJob
          ? `${t('adminPages.monitoring.taskReference', { id: selectedJob.id })} · ${componentLabel(selectedJob.component)}`
          : ''
      "
      size="xl"
      @close="closeJob"
    >
      <div v-if="selectedJob" class="grid gap-5">
        <div class="grid gap-3 sm:grid-cols-4">
          <InfoCell
            :label="t('common.status')"
            :value="statusLabel(selectedJob.status)"
          />
          <InfoCell
            :label="t('adminPages.monitoring.hostResult')"
            :value="`${selectedJob.success_hosts || 0} / ${selectedJob.total_hosts || 0}`"
          />
          <InfoCell
            :label="t('adminPages.monitoring.duration')"
            :value="formatDuration(selectedJob.duration_seconds)"
          />
          <InfoCell
            :label="t('adminPages.monitoring.returnCode')"
            :value="selectedJob.returncode ?? t('common.emptyValue')"
          />
        </div>

        <section
          v-if="selectedJob.progress"
          class="border-y border-slate-200 py-4"
        >
          <div class="flex flex-wrap items-center justify-between gap-2">
            <div class="min-w-0">
              <p class="text-sm font-semibold text-slate-900">
                {{ progressStageLabel(selectedJob.progress.stage) }}
              </p>
              <p
                v-if="selectedJob.progress.current_host"
                class="mt-1 truncate text-xs text-slate-500"
              >
                {{ t('adminPages.monitoring.progressCurrentHost') }}：{{
                  selectedJob.progress.current_host
                }}
              </p>
            </div>
            <span class="text-sm font-semibold tabular-nums text-slate-700"
              >{{ selectedJob.progress.percent || 0 }}%</span
            >
          </div>
          <div class="mt-4 overflow-x-auto pb-1">
            <ol
              class="grid grid-cols-3 gap-y-5 sm:min-w-[38rem] sm:grid-cols-6 sm:gap-y-0"
            >
              <li
                v-for="(stage, index) in progressStages"
                :key="stage.key"
                class="relative text-center"
              >
                <span
                  v-if="index < progressStages.length - 1"
                  class="absolute left-[calc(50%+0.875rem)] right-[calc(-50%+0.875rem)] top-3 h-px"
                  :class="[
                    progressStepComplete(index + 1)
                      ? 'bg-blue-500'
                      : 'bg-slate-200',
                    index === 2 ? 'hidden sm:block' : ''
                  ]"
                ></span>
                <span
                  class="relative mx-auto flex h-6 w-6 items-center justify-center rounded-full border text-[0.6875rem] font-semibold"
                  :class="progressStepClass(index)"
                  >{{ index + 1 }}</span
                >
                <span
                  class="mt-2 block whitespace-nowrap text-xs font-medium"
                  :class="progressStepTextClass(index)"
                >
                  {{ stage.label }}
                </span>
              </li>
            </ol>
          </div>
        </section>

        <div class="flex flex-wrap gap-2 border-b border-slate-200">
          <button
            v-for="tab in detailTabs"
            :key="tab.key"
            class="border-b-2 px-3 py-2 text-sm font-semibold transition"
            :class="
              detailTab === tab.key
                ? 'border-slate-900 text-slate-950'
                : 'border-transparent text-slate-500 hover:text-slate-800'
            "
            @click="detailTab = tab.key"
          >
            {{ tab.label }}
          </button>
        </div>

        <section v-if="detailTab === 'result'" class="grid gap-3">
          <div
            v-if="selectedJob.status === 'failed'"
            class="rounded-lg bg-rose-50 px-4 py-3 text-sm font-medium text-rose-800"
          >
            {{ jobFailureSummary(selectedJob) }}
          </div>
          <pre class="admin-code-block">{{
            prettyJson(selectedJob.results || [])
          }}</pre>
        </section>
        <section
          v-else-if="detailTab === 'ansible'"
          class="grid gap-4 lg:grid-cols-2"
        >
          <div>
            <p class="mb-2 text-sm font-semibold">
              {{ t('adminPages.monitoring.inventory') }}
            </p>
            <pre class="admin-code-block">{{
              selectedJob.inventory || t('common.emptyValue')
            }}</pre>
          </div>
          <div>
            <p class="mb-2 text-sm font-semibold">
              {{ t('adminPages.monitoring.vars') }}
            </p>
            <pre class="admin-code-block">{{
              prettyJson(selectedJob.vars || {})
            }}</pre>
          </div>
        </section>
        <section v-else-if="detailTab === 'command'" class="grid gap-3">
          <div class="flex justify-end">
            <BaseButton
              variant="outline"
              size="sm"
              :disabled="!selectedJob.manual_command"
              @click="copyManualCommand"
              >{{
                copied
                  ? t('adminPages.monitoring.commandCopied')
                  : t('adminPages.monitoring.copyCommand')
              }}</BaseButton
            >
          </div>
          <pre class="admin-code-block">{{
            selectedJob.manual_command || t('common.emptyValue')
          }}</pre>
        </section>
        <section v-else>
          <pre ref="logBlock" class="admin-code-block">{{
            (selectedJob.logs || []).join('\n') || t('common.emptyValue')
          }}</pre>
        </section>

        <div class="flex justify-end gap-2">
          <BaseButton variant="outline" @click="closeJob">
            {{ t('common.close') }}
          </BaseButton>
        </div>
      </div>
    </BaseModal>
  </AdminLayout>
</template>

<script setup>
import {
  computed,
  defineComponent,
  h,
  nextTick,
  onBeforeUnmount,
  onMounted,
  ref,
  watch
} from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import AdminLayout from '@/admin/layout/AdminLayout.vue'
import AdminListSection from '@/admin/components/AdminListSection.vue'
import AdminPageState from '@/admin/components/AdminPageState.vue'
import AdminTable from '@/admin/components/AdminTable.vue'
import DeploymentResources from '@/admin/pages/Monitoring/Installers.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseModal from '@/components/ui/BaseModal.vue'
import PageFrame from '@/components/ui/PageFrame.vue'
import { monitoringStackApi } from '@/admin/api/monitoringStack'
import {
  keepLogPinnedAfterRender,
  normalizeHostSummaries
} from '@/admin/utils/monitoringJobHistory'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const loading = ref(false)
const error = ref('')
const hostSummaries = ref([])
const selectedJob = ref(null)
const detailTab = ref('result')
const hostSearch = ref('')
const componentFilter = ref('')
const statusFilter = ref('')
const copied = ref(false)
const logBlock = ref(null)
const pollingJob = ref(false)
let pollTimer = null

const activeView = computed(() =>
  route.query.view === 'resources' ? 'resources' : 'tasks'
)
const deploymentTabs = computed(() => [
  { key: 'tasks', label: t('adminPages.monitoring.deploymentTasksTab') },
  {
    key: 'resources',
    label: t('adminPages.monitoring.deploymentResourcesTab')
  }
])

const componentOptions = ['categraf', 'blackbox']
const statusClasses = {
  success: 'bg-emerald-50 text-emerald-700',
  failed: 'bg-rose-50 text-rose-700',
  running: 'bg-sky-50 text-sky-700',
  queued: 'bg-sky-50 text-sky-700'
}

const StatusBadge = defineComponent({
  props: { status: { type: String, default: '' } },
  setup(props) {
    return () =>
      h(
        'span',
        {
          class: [
            'inline-flex rounded-full px-2 py-1 text-xs font-semibold',
            statusClasses[normalizeStatus(props.status)] ||
              'bg-slate-100 text-slate-600'
          ]
        },
        statusLabel(props.status)
      )
  }
})

const ComponentState = defineComponent({
  props: { summary: { type: Object, default: null } },
  setup(props) {
    return () => {
      const latest = props.summary?.latest
      if (!latest)
        return h(
          'span',
          { class: 'text-xs text-slate-400' },
          t('adminPages.monitoring.notInstalled')
        )
      return h(StatusBadge, { status: latest.host_status })
    }
  }
})

const InfoCell = defineComponent({
  props: { label: String, value: [String, Number] },
  setup(props) {
    return () =>
      h('div', { class: 'rounded-lg bg-slate-50 px-3 py-3' }, [
        h('p', { class: 'text-xs font-medium text-slate-500' }, props.label),
        h(
          'p',
          { class: 'mt-1 text-sm font-semibold text-slate-900' },
          props.value
        )
      ])
  }
})

const detailTabs = computed(() => [
  { key: 'result', label: t('adminPages.monitoring.executionResult') },
  { key: 'ansible', label: t('adminPages.monitoring.ansiblePreview') },
  { key: 'command', label: t('adminPages.monitoring.manualCommandPreview') },
  { key: 'logs', label: t('adminPages.monitoring.logs') }
])

const progressStages = computed(() => [
  { key: 'queued', label: t('adminPages.monitoring.progressQueued') },
  { key: 'preparing', label: t('adminPages.monitoring.progressPreparing') },
  { key: 'connecting', label: t('adminPages.monitoring.progressConnecting') },
  { key: 'installing', label: t('adminPages.monitoring.progressInstalling') },
  { key: 'verifying', label: t('adminPages.monitoring.progressVerifying') },
  {
    key: selectedJob.value?.status === 'failed' ? 'failed' : 'completed',
    label:
      selectedJob.value?.status === 'failed'
        ? t('adminPages.monitoring.progressFailed')
        : t('adminPages.monitoring.progressCompleted')
  }
])

const filteredHosts = computed(() =>
  hostSummaries.value.filter((host) => {
    const query = hostSearch.value.toLowerCase()
    if (
      query &&
      !`${host.hostname} ${host.address}`.toLowerCase().includes(query)
    )
      return false
    const summaries = componentFilter.value
      ? [host.components?.[componentFilter.value]]
      : componentOptions.map((key) => host.components?.[key])
    if (componentFilter.value && !summaries[0]?.latest) return false
    if (
      statusFilter.value &&
      !summaries.some(
        (summary) =>
          normalizeStatus(summary?.latest?.host_status) === statusFilter.value
      )
    )
      return false
    return true
  })
)

function selectView(view) {
  const query = { ...route.query }
  delete query.job
  router.replace({
    query: {
      ...query,
      view: view === 'resources' ? 'resources' : undefined
    }
  })
}

function normalizeStatus(status) {
  const value = String(status || '').toLowerCase()
  if (['succeeded', 'completed', 'done'].includes(value)) return 'success'
  if (['error', 'timeout'].includes(value)) return 'failed'
  return value
}
function statusLabel(status) {
  return (
    {
      queued: t('adminPages.monitoring.statusQueued'),
      running: t('adminPages.monitoring.statusRunning'),
      success: t('common.success'),
      failed: t('adminPages.monitoring.statusFailed')
    }[normalizeStatus(status)] || t('common.emptyValue')
  )
}
function componentLabel(component) {
  return component === 'blackbox' ? 'blackbox' : 'Categraf'
}
function latestExecution(host) {
  return (
    componentOptions
      .map((key) => host.components?.[key]?.latest)
      .filter(Boolean)
      .sort((a, b) => new Date(b.created_at) - new Date(a.created_at))[0] ||
    null
  )
}
function jobFailureReason(job) {
  const reason = String(
    job?.reason_code || job?.progress?.reason_code || ''
  ).toLowerCase()
  if (reason && reason !== 'failed') return reason
  const output = String(job?.last_error || '').toLowerCase()
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
  if (normalizeStatus(job?.host_status || job?.status) !== 'failed')
    return t('common.emptyValue')
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
function formatDuration(value) {
  if (value === null || value === undefined) return t('common.emptyValue')
  return value < 60 ? `${value}s` : `${Math.floor(value / 60)}m ${value % 60}s`
}
function prettyJson(value) {
  return JSON.stringify(value, null, 2)
}

function openHostStatus(host) {
  const newest = latestExecution(host)
  router.push({
    name: 'AdminMonitoringHostDeploymentStatus',
    params: { hostId: host.host_id },
    query: { component: newest?.component || 'categraf' }
  })
}
function closeJob() {
  selectedJob.value = null
  clearPolling()
  if (route.query.job) {
    const query = { ...route.query }
    delete query.job
    router.replace({ query })
  }
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    hostSummaries.value = normalizeHostSummaries(
      await monitoringStackApi.getJobHostSummaries()
    )
  } catch (err) {
    error.value = err?.response?.data?.detail || err.message
  } finally {
    loading.value = false
  }
}

function isActiveJob(job) {
  return ['queued', 'running'].includes(normalizeStatus(job?.status))
}
function clearPolling() {
  if (pollTimer) window.clearInterval(pollTimer)
  pollTimer = null
  pollingJob.value = false
}
function startPolling() {
  clearPolling()
  if (!isActiveJob(selectedJob.value)) return
  pollTimer = window.setInterval(async () => {
    if (pollingJob.value || !selectedJob.value?.id) return
    pollingJob.value = true
    try {
      selectedJob.value = await monitoringStackApi.getJob(selectedJob.value.id)
      if (!isActiveJob(selectedJob.value)) {
        clearPolling()
        await load()
      }
    } finally {
      pollingJob.value = false
    }
  }, 1000)
}
async function openLinkedJob() {
  const jobId = Number(route.query.job)
  if (!Number.isInteger(jobId) || jobId <= 0) return
  selectedJob.value = await monitoringStackApi.getJob(jobId)
}
async function copyManualCommand() {
  if (!selectedJob.value?.manual_command) return
  await navigator.clipboard.writeText(selectedJob.value.manual_command)
  copied.value = true
  window.setTimeout(() => {
    copied.value = false
  }, 1600)
}
function progressStageLabel(stage) {
  return (
    progressStages.value.find((item) => item.key === stage)?.label ||
    statusLabel(selectedJob.value?.status)
  )
}
function progressCurrentStep() {
  return Number(selectedJob.value?.progress?.current || 1)
}
function progressStepComplete(step) {
  return step < progressCurrentStep()
}
function progressStepClass(index) {
  const step = index + 1
  const current = progressCurrentStep()
  if (step < current) return 'border-blue-600 bg-blue-600 text-white'
  if (step === current && selectedJob.value?.status === 'failed')
    return 'border-rose-600 bg-rose-600 text-white'
  if (step === current)
    return 'border-blue-600 bg-white text-blue-700 ring-4 ring-blue-50'
  return 'border-slate-300 bg-white text-slate-400'
}
function progressStepTextClass(index) {
  const step = index + 1
  const current = progressCurrentStep()
  if (step === current && selectedJob.value?.status === 'failed')
    return 'text-rose-700'
  return step <= current ? 'text-slate-800' : 'text-slate-400'
}

watch(() => [selectedJob.value?.id, selectedJob.value?.status], startPolling)
watch(
  () => route.query.job,
  async (jobId, oldId) => {
    if (jobId && jobId !== oldId) await openLinkedJob()
  }
)
watch(
  () => selectedJob.value?.logs?.length,
  async () => {
    if (detailTab.value !== 'logs' || !logBlock.value) return
    await keepLogPinnedAfterRender({
      element: logBlock.value,
      getCurrentElement: () => logBlock.value,
      nextRender: nextTick
    })
  },
  { flush: 'pre' }
)

onMounted(async () => {
  await load()
  await openLinkedJob()
})
onBeforeUnmount(clearPolling)
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
