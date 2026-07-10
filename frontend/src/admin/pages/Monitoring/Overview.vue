<template>
  <AdminLayout>
    <PageFrame
      variant="soft"
      :title="t('adminPages.monitoring.overviewTitle')"
    >
      <AdminListSection>
        <template #toolbarEnd>
          <BaseButton variant="primary" size="sm" :loading="syncing" @click="syncRealState">
            {{ t('adminPages.monitoring.syncRealState') }}
          </BaseButton>
          <BaseButton variant="outline" size="sm" :loading="loading" @click="load">
            {{ t('common.refresh') }}
          </BaseButton>
        </template>

        <AdminPageState :loading="loading" :error="error" :empty="false">
          <section class="grid gap-4">
            <section class="grid gap-4 xl:grid-cols-3">
              <article class="admin-workbench-panel p-5">
                <div class="flex items-start justify-between gap-3">
                  <div>
                    <p class="text-sm font-semibold text-slate-900">
                      {{ t('adminPages.monitoring.hyperopsConfigState') }}
                    </p>
                  </div>
                </div>
                <div class="mt-5 grid grid-cols-2 gap-3">
                  <div v-for="item in hyperOpsStats" :key="item.label" class="rounded-lg bg-slate-50 px-3 py-3">
                    <p class="text-xs font-medium text-slate-500">{{ item.label }}</p>
                    <p class="mt-1 text-2xl font-semibold text-slate-950">{{ item.value }}</p>
                  </div>
                </div>
              </article>

              <article class="admin-workbench-panel p-5">
                <div class="flex items-start justify-between gap-3">
                  <div>
                    <p class="text-sm font-semibold text-slate-900">
                      {{ t('adminPages.monitoring.n9eRealityState') }}
                    </p>
                  </div>
                  <span :class="connectionPillClass(Boolean(n9eSummary.connected))">
                    {{ n9eSummary.connected ? t('adminPages.monitoring.connected') : t('adminPages.monitoring.notConnected') }}
                  </span>
                </div>
                <div class="mt-5 grid grid-cols-2 gap-3">
                  <div v-for="item in n9eStats" :key="item.label" class="rounded-lg bg-slate-50 px-3 py-3">
                    <p class="text-xs font-medium text-slate-500">{{ item.label }}</p>
                    <p class="mt-1 text-xl font-semibold text-slate-950">{{ item.value }}</p>
                  </div>
                </div>
                <p v-if="n9eSummary.error" class="mt-4 text-xs leading-5 text-rose-600">
                  {{ n9eSummary.error }}
                </p>
                <p class="mt-4 break-all text-xs text-slate-500">
                  {{ t('adminPages.monitoring.n9eUrl') }}:
                  <span class="font-medium text-slate-700">{{ n9eSummary.n9e_url || config.n9e_url || t('adminPages.monitoring.notConfigured') }}</span>
                </p>
                <p class="mt-2 text-xs text-slate-500">
                  {{ t('adminPages.monitoring.lastSyncedAt') }}:
                  <span class="font-medium text-slate-700">{{ n9eSummary.synced_at || t('common.emptyValue') }}</span>
                </p>
              </article>

              <article class="admin-workbench-panel p-5">
                <div class="flex items-start justify-between gap-3">
                  <div>
                    <p class="text-sm font-semibold text-slate-900">
                      {{ t('adminPages.monitoring.prometheusRealityState') }}
                    </p>
                  </div>
                  <span :class="connectionPillClass(Boolean(prometheusSummary.connected))">
                    {{ prometheusSummary.connected ? t('adminPages.monitoring.connected') : t('adminPages.monitoring.notConnected') }}
                  </span>
                </div>
                <div class="mt-5 grid grid-cols-3 gap-3">
                  <div v-for="item in prometheusStats" :key="item.label" class="rounded-lg bg-slate-50 px-3 py-3">
                    <p class="text-xs font-medium text-slate-500">{{ item.label }}</p>
                    <p class="mt-1 text-2xl font-semibold text-slate-950">{{ item.value }}</p>
                  </div>
                </div>
                <p v-if="prometheusSummary.error" class="mt-4 text-xs leading-5 text-rose-600">
                  {{ prometheusSummary.error }}
                </p>
                <p class="mt-4 break-all text-xs text-slate-500">
                  {{ t('adminPages.monitoring.prometheusUrl') }}:
                  <span class="font-medium text-slate-700">{{ prometheusSummary.prometheus_url || config.prometheus_url || t('adminPages.monitoring.notConfigured') }}</span>
                </p>
                <p class="mt-2 text-xs text-slate-500">
                  {{ t('adminPages.monitoring.lastSyncedAt') }}:
                  <span class="font-medium text-slate-700">{{ prometheusSummary.synced_at || t('common.emptyValue') }}</span>
                </p>
              </article>
            </section>

            <section class="admin-workbench-panel p-5">
              <div class="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p class="text-sm font-semibold text-slate-900">
                    {{ t('adminPages.monitoring.governanceFindingsTitle') }}
                  </p>
                </div>
                <router-link class="btn btn-outline btn-sm" to="/management/monitoring/probes">
                  {{ t('adminPages.monitoring.fixProbeTargets') }}
                </router-link>
              </div>
              <div class="mt-4 grid gap-3 sm:grid-cols-3">
                <div v-for="item in governanceFindingStats" :key="item.label" class="rounded-lg bg-slate-50 px-3 py-3">
                  <p class="text-xs font-medium text-slate-500">{{ item.label }}</p>
                  <p class="mt-1 text-2xl font-semibold text-slate-950">{{ item.value }}</p>
                </div>
              </div>
              <div class="mt-4 grid gap-2">
                <p v-if="!governanceFindings.length" class="text-xs text-slate-400">
                  {{ t('adminPages.monitoring.noRiskItems') }}
                </p>
                <article
                  v-for="item in governanceFindings"
                  :key="item.id"
                  class="flex flex-wrap items-center justify-between gap-3 rounded-lg bg-slate-50 px-4 py-3"
                >
                  <div class="min-w-0">
                    <p class="truncate text-sm font-semibold text-slate-900">{{ item.title }}</p>
                    <p class="mt-1 truncate text-xs text-slate-500">
                      {{ findingCategoryLabel(item.category) }} / {{ item.subject_key }}
                    </p>
                  </div>
                  <div class="flex items-center gap-2">
                    <span
                      class="inline-flex rounded-full border px-2.5 py-1 text-xs font-semibold"
                      :class="findingSeverityClass(item.severity)"
                    >
                      {{ findingSeverityLabel(item.severity) }}
                    </span>
                    <router-link class="btn btn-outline btn-sm" :to="findingTargetRoute(item)">
                      {{ t('common.view') }}
                    </router-link>
                  </div>
                </article>
              </div>
            </section>

            <section class="grid gap-4">
              <div class="admin-workbench-panel p-5">
                <div class="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <p class="text-sm font-semibold text-slate-900">
                      {{ t('adminPages.monitoring.quickActionsTitle') }}
                    </p>
                  </div>
                  <span class="text-xs font-medium text-slate-500">
                    {{ syncStatusText }}
                  </span>
                </div>
                <div class="mt-4 grid gap-3 md:grid-cols-3">
                  <div
                    v-for="item in pendingItems"
                    :key="item.title"
                    class="flex items-center justify-between gap-3 rounded-lg bg-slate-50 px-4 py-3"
                  >
                    <p class="text-sm font-semibold text-slate-900">{{ item.title }}</p>
                    <router-link class="btn btn-outline btn-sm" :to="item.to">
                      {{ item.action }}
                    </router-link>
                  </div>
                </div>
              </div>
            </section>
          </section>
        </AdminPageState>
      </AdminListSection>
    </PageFrame>
  </AdminLayout>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import AdminLayout from '@/admin/layout/AdminLayout.vue'
import AdminListSection from '@/admin/components/AdminListSection.vue'
import AdminPageState from '@/admin/components/AdminPageState.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import PageFrame from '@/components/ui/PageFrame.vue'
import { monitoringStackApi } from '@/admin/api/monitoringStack'

const { t } = useI18n()
const loading = ref(false)
const syncing = ref(false)
const error = ref('')
const loadedAt = ref('')
const lastSyncRun = ref(null)
const config = ref({})
const hosts = ref([])
const probes = ref([])
const profiles = ref([])
const rules = ref([])
const jobs = ref([])
const prometheusSummary = ref({})
const n9eSummary = ref({})
const governanceOverview = ref({})

function normalizeList(data) {
  return data?.results || data || []
}

function countEnabled(items) {
  return items.filter((item) => item.enabled !== false).length
}

function n9eMetric(value) {
  return value === null || value === undefined ? '-' : value
}

function n9eUnavailableReason(field) {
  return n9eSummary.value?.[`${field}_unavailable_reason`] || t('adminPages.monitoring.n9eVersionNotExposed')
}

const failedJobs = computed(() =>
  jobs.value.filter((job) => ['failed', 'error', 'timeout'].includes(String(job.status || '').toLowerCase()))
)

const hyperOpsStats = computed(() => [
  {
    label: t('adminPages.monitoring.sshHostCount'),
    value: hosts.value.length
  },
  {
    label: t('adminPages.monitoring.enabledProbeCount'),
    value: countEnabled(probes.value)
  },
  {
    label: t('adminPages.monitoring.ruleTemplateCount'),
    value: rules.value.length
  },
  {
    label: t('adminPages.monitoring.failedJobCount'),
    value: failedJobs.value.length
  }
])

const prometheusStats = computed(() => [
  {
    label: t('adminPages.monitoring.activeTargets'),
    value: prometheusSummary.value?.active_targets ?? 0
  },
  {
    label: t('adminPages.monitoring.downTargets'),
    value: prometheusSummary.value?.down_targets ?? 0
  },
  {
    label: t('adminPages.monitoring.blackboxTargets'),
    value: prometheusSummary.value?.blackbox_targets ?? 0
  }
])

const governanceFindings = computed(() => governanceOverview.value?.top_findings || [])
const governanceFindingCounts = computed(() => governanceOverview.value?.finding_counts || {})
const governanceFindingStats = computed(() => [
  {
    label: t('adminPages.monitoring.openFindings'),
    value: governanceFindingCounts.value.open || 0
  },
  {
    label: t('adminPages.monitoring.criticalFindings'),
    value: governanceFindingCounts.value.critical || 0
  },
  {
    label: t('adminPages.monitoring.warningFindings'),
    value: governanceFindingCounts.value.warning || 0
  }
])

const n9eStats = computed(() => [
  {
    label: t('adminPages.monitoring.businessGroups'),
    value: n9eMetric(n9eSummary.value?.business_groups)
  },
  {
    label: t('adminPages.monitoring.prometheusDatasources'),
    value: n9eMetric(n9eSummary.value?.prometheus_datasources)
  },
  {
    label: t('adminPages.monitoring.n9eRules'),
    value: n9eSummary.value?.rules_available
      ? n9eMetric(n9eSummary.value?.rules)
      : n9eUnavailableReason('rules')
  },
  {
    label: t('adminPages.monitoring.n9eHosts'),
    value: n9eSummary.value?.hosts_available
      ? n9eMetric(n9eSummary.value?.hosts)
      : n9eUnavailableReason('hosts')
  }
])

const pendingItems = computed(() => [
  {
    title: t('adminPages.monitoring.pendingIntegrations'),
    action: t('adminPages.monitoring.openSettings'),
    to: '/management/monitoring/settings'
  },
  {
    title: t('adminPages.monitoring.pendingInstallStatus'),
    action: t('adminPages.monitoring.openAssets'),
    to: '/management/monitoring/assets'
  },
  {
    title: t('adminPages.monitoring.pendingFailedJobs', { count: failedJobs.value.length }),
    action: t('adminPages.monitoring.openJobs'),
    to: '/management/monitoring/jobs'
  }
])

const syncStatusText = computed(() => {
  if (lastSyncRun.value?.finished_at) {
    return `${t('adminPages.monitoring.lastSyncedAt')}: ${lastSyncRun.value.finished_at}`
  }
  return `${t('adminPages.monitoring.lastLoadedAt')}: ${loadedAt.value || t('common.emptyValue')}`
})

function connectionPillClass(connected) {
  return [
    'inline-flex rounded-full border px-2.5 py-1 text-xs font-semibold',
    connected
      ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
      : 'border-slate-200 bg-slate-50 text-slate-500'
  ].join(' ')
}

function findingSeverityLabel(severity) {
  const labels = {
    critical: t('adminPages.monitoring.severityCritical'),
    warning: t('adminPages.monitoring.severityWarning'),
    info: t('adminPages.monitoring.severityInfo')
  }
  return labels[severity] || severity || t('common.emptyValue')
}

function findingSeverityClass(severity) {
  if (severity === 'critical') return 'border-rose-200 bg-rose-50 text-rose-700'
  if (severity === 'warning') return 'border-amber-200 bg-amber-50 text-amber-700'
  return 'border-slate-200 bg-white text-slate-600'
}

function findingCategoryLabel(category) {
  const labels = {
    host_not_in_n9e: t('adminPages.monitoring.categoryHostNotInN9e'),
    host_not_scraped_by_prometheus: t('adminPages.monitoring.categoryHostNotScrapedByPrometheus'),
    categraf_not_installed: t('adminPages.monitoring.categoryCategrafNotInstalled'),
    blackbox_not_installed: t('adminPages.monitoring.categoryBlackboxNotInstalled'),
    probe_configured_not_discovered: t('adminPages.monitoring.configuredNotDiscovered'),
    probe_discovered_not_configured: t('adminPages.monitoring.discoveredNotConfigured'),
    probe_abnormal: t('adminPages.monitoring.abnormalProbeTargets')
  }
  return labels[category] || category || t('common.emptyValue')
}

function findingTargetRoute(item) {
  if (item.subject_type === 'host') return '/management/monitoring/assets'
  if (item.subject_type === 'rule') return '/management/monitoring/rules'
  return '/management/monitoring/probes'
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const [
      configData,
      hostData,
      probeData,
      profileData,
      ruleData,
      jobData,
      prometheusData,
      n9eData,
      governanceData
    ] = await Promise.all([
      monitoringStackApi.getConfig(),
      monitoringStackApi.getHosts(),
      monitoringStackApi.getProbeTargets(),
      monitoringStackApi.getProfiles(),
      monitoringStackApi.getRules(),
      monitoringStackApi.getJobs(),
      monitoringStackApi.getPrometheusTargetsSummary(),
      monitoringStackApi.getN9eSummary(),
      monitoringStackApi.getGovernanceOverview()
    ])
    config.value = configData || {}
    hosts.value = normalizeList(hostData)
    probes.value = normalizeList(probeData)
    profiles.value = normalizeList(profileData)
    rules.value = normalizeList(ruleData)
    jobs.value = normalizeList(jobData)
    prometheusSummary.value = prometheusData || {}
    n9eSummary.value = n9eData || {}
    governanceOverview.value = governanceData || {}
    loadedAt.value = new Date().toLocaleString()
  } catch (err) {
    error.value = err?.response?.data?.detail || err.message
  } finally {
    loading.value = false
  }
}

async function syncRealState() {
  syncing.value = true
  error.value = ''
  try {
    lastSyncRun.value = await monitoringStackApi.syncGovernance('all')
    await load()
  } catch (err) {
    error.value = err?.response?.data?.detail || err.message
  } finally {
    syncing.value = false
  }
}

onMounted(load)
</script>
