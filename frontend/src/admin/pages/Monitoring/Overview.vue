<template>
  <AdminLayout>
    <PageFrame
      variant="soft"
      :title="t('adminPages.monitoring.overviewTitle')"
      :subtitle="t('adminPages.monitoring.overviewSubtitle')"
    >
      <AdminListSection>
        <template #toolbarEnd>
          <BaseButton
            variant="primary"
            size="sm"
            :loading="syncing"
            @click="syncRealState"
          >
            {{ t('adminPages.monitoring.syncRealState') }}
          </BaseButton>
          <BaseButton
            variant="outline"
            size="sm"
            :loading="loading"
            @click="load"
          >
            {{ t('common.refresh') }}
          </BaseButton>
        </template>

        <AdminPageState :loading="loading" :error="error" :empty="false">
          <section class="monitoring-overview">
            <section
              class="monitoring-status-list"
              :aria-label="t('adminPages.monitoring.connectionStatus')"
            >
              <div class="monitoring-status-row">
                <div class="monitoring-status-main">
                  <h2>{{ t('adminPages.monitoring.hyperopsConfigState') }}</h2>
                  <span
                    class="monitoring-status-pill monitoring-status-pill--configured"
                  >
                    {{ t('adminPages.monitoring.connected') }}
                  </span>
                </div>
                <div class="monitoring-status-metrics">
                  <span v-for="item in hyperOpsStats" :key="item.label">
                    <small>{{ item.label }}</small>
                    <strong>{{ item.value }}</strong>
                  </span>
                </div>
              </div>

              <div class="monitoring-status-row">
                <div class="monitoring-status-main">
                  <h2>{{ t('adminPages.monitoring.n9eRealityState') }}</h2>
                  <span
                    class="monitoring-status-pill"
                    :class="connectionPillClass(Boolean(n9eSummary.connected))"
                    role="status"
                  >
                    {{
                      n9eSummary.connected
                        ? t('adminPages.monitoring.connected')
                        : t('adminPages.monitoring.notConnected')
                    }}
                  </span>
                </div>
                <div class="monitoring-status-metrics">
                  <span v-for="item in n9eStats" :key="item.label">
                    <small>{{ item.label }}</small>
                    <strong>{{ item.value }}</strong>
                  </span>
                </div>
                <p v-if="n9eSummary.error" class="monitoring-status-error">
                  {{ n9eSummary.error }}
                </p>
              </div>

              <div class="monitoring-status-row">
                <div class="monitoring-status-main">
                  <h2>
                    {{ t('adminPages.monitoring.prometheusRealityState') }}
                  </h2>
                  <span
                    class="monitoring-status-pill"
                    :class="
                      connectionPillClass(Boolean(prometheusSummary.connected))
                    "
                    role="status"
                  >
                    {{
                      prometheusSummary.connected
                        ? t('adminPages.monitoring.connected')
                        : t('adminPages.monitoring.notConnected')
                    }}
                  </span>
                </div>
                <div class="monitoring-status-metrics">
                  <span v-for="item in prometheusStats" :key="item.label">
                    <small>{{ item.label }}</small>
                    <strong>{{ item.value }}</strong>
                  </span>
                </div>
                <p
                  v-if="prometheusSummary.error"
                  class="monitoring-status-error"
                >
                  {{ prometheusSummary.error }}
                </p>
              </div>
            </section>

            <section class="monitoring-main-grid">
              <section
                class="monitoring-findings"
                :aria-labelledby="'monitoring-findings-title'"
              >
                <div class="monitoring-section-heading">
                  <div>
                    <h2 id="monitoring-findings-title">
                      {{ t('adminPages.monitoring.governanceFindingsTitle') }}
                    </h2>
                    <p>
                      {{ t('adminPages.monitoring.openFindings') }}
                      {{ governanceFindingCounts.open || 0 }} ·
                      {{ t('adminPages.monitoring.criticalFindings') }}
                      {{ governanceFindingCounts.critical || 0 }} ·
                      {{ t('adminPages.monitoring.warningFindings') }}
                      {{ governanceFindingCounts.warning || 0 }}
                    </p>
                  </div>
                  <router-link
                    class="btn btn-outline btn-sm"
                    to="/management/monitoring/probes"
                  >
                    {{ t('adminPages.monitoring.fixProbeTargets') }}
                  </router-link>
                </div>
                <p
                  v-if="!governanceFindings.length"
                  class="monitoring-empty-line"
                >
                  {{ t('adminPages.monitoring.noRiskItems') }}
                </p>
                <article
                  v-for="item in governanceFindings"
                  :key="item.id"
                  class="monitoring-finding-row"
                >
                  <div class="min-w-0">
                    <p class="monitoring-finding-title">
                      {{ findingTitle(item) }}
                    </p>
                    <p class="monitoring-finding-meta">
                      {{ findingCategoryLabel(item.category) }} /
                      {{ findingSubjectLabel(item) }}
                    </p>
                  </div>
                  <div class="monitoring-finding-actions">
                    <span
                      class="monitoring-finding-severity"
                      :class="findingSeverityClass(item.severity)"
                    >
                      {{ findingSeverityLabel(item.severity) }}
                    </span>
                    <router-link
                      class="monitoring-view-link"
                      :to="findingTargetRoute(item)"
                    >
                      {{ t('common.view') }}
                    </router-link>
                  </div>
                </article>
              </section>

              <aside
                class="monitoring-quick-actions"
                :aria-labelledby="'monitoring-actions-title'"
              >
                <div class="monitoring-section-heading">
                  <div>
                    <h2 id="monitoring-actions-title">
                      {{ t('adminPages.monitoring.quickActionsTitle') }}
                    </h2>
                    <p>{{ syncStatusText }}</p>
                  </div>
                </div>
                <router-link
                  v-for="item in pendingItems"
                  :key="item.title"
                  class="monitoring-action-row"
                  :to="item.to"
                >
                  <span>{{ item.title }}</span>
                  <small
                    >{{ item.action }} <span aria-hidden="true">→</span></small
                  >
                </router-link>
              </aside>
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
  return (
    n9eSummary.value?.[`${field}_unavailable_reason`] ||
    t('adminPages.monitoring.n9eVersionNotExposed')
  )
}

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
    label: t('adminPages.monitoring.deploymentHistory'),
    value: jobs.value.length
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

const governanceFindings = computed(
  () => governanceOverview.value?.top_findings || []
)
const governanceFindingCounts = computed(
  () => governanceOverview.value?.finding_counts || {}
)

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
    title: t('adminPages.monitoring.deploymentHistory'),
    action: t('adminPages.monitoring.viewDeploymentHistory'),
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
  return connected
    ? 'monitoring-status-pill--connected'
    : 'monitoring-status-pill--unavailable'
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
  if (severity === 'critical') return 'monitoring-finding-severity--critical'
  if (severity === 'warning') return 'monitoring-finding-severity--warning'
  return 'monitoring-finding-severity--info'
}

function findingCategoryLabel(category) {
  const labels = {
    host_not_in_n9e: t('adminPages.monitoring.categoryHostNotInN9e'),
    host_not_scraped_by_prometheus: t(
      'adminPages.monitoring.categoryHostNotScrapedByPrometheus'
    ),
    categraf_not_installed: t(
      'adminPages.monitoring.categoryCategrafNotInstalled'
    ),
    blackbox_not_installed: t(
      'adminPages.monitoring.categoryBlackboxNotInstalled'
    ),
    install_job_failed: t('adminPages.monitoring.categoryInstallJobFailed'),
    probe_configured_not_discovered: t(
      'adminPages.monitoring.configuredNotDiscovered'
    ),
    probe_discovered_not_configured: t(
      'adminPages.monitoring.discoveredNotConfigured'
    ),
    probe_abnormal: t('adminPages.monitoring.abnormalProbeTargets')
  }
  return labels[category] || category || t('common.emptyValue')
}

function findingTitle(item) {
  if (item.category !== 'install_job_failed') return item.title
  return t('adminPages.monitoring.deploymentFailedFinding', {
    host: item.details?.hostname || t('common.emptyValue'),
    component: item.details?.component === 'blackbox' ? 'blackbox' : 'Categraf'
  })
}

function findingSubjectLabel(item) {
  if (item.category === 'install_job_failed') {
    return item.details?.job_id
      ? `#${item.details.job_id}`
      : t('common.emptyValue')
  }
  return item.subject_key
}

function findingTargetRoute(item) {
  if (item.subject_type === 'job') {
    return {
      path: '/management/monitoring/jobs',
      query: { job: item.details?.job_id }
    }
  }
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
