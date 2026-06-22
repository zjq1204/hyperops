<template>
  <AdminLayout>
    <PageFrame
      variant="soft"
      :title="t('notificationManagement.stats.title')"
      :subtitle="t('notificationManagement.stats.subtitle')"
    >
      <AdminListSection>
        <template #filters>
          <div class="admin-filter-grid">
            <div class="admin-filter-field">
              <label class="admin-filter-label">
                {{ t('notificationManagement.stats.userScope') }}
              </label>
              <select
                v-model="userScope"
                class="admin-filter-control min-w-[140px]"
                @change="fetchStats"
              >
                <option value="">
                  {{ t('notificationManagement.stats.allUsers') }}
                </option>
                <option
                  v-for="u in userOptions"
                  :key="u.user_id"
                  :value="String(u.user_id)"
                >
                  {{ u.display }}
                </option>
              </select>
            </div>
            <div class="admin-filter-field">
              <label class="admin-filter-label">
                {{ t('notificationManagement.stats.granularity') }}
              </label>
              <div class="admin-segmented-control">
                <button
                  v-for="opt in granularityOptions"
                  :key="opt.value"
                  type="button"
                  :class="[
                    'admin-segmented-option',
                    granularity === opt.value ? 'is-active' : ''
                  ]"
                  @click="selectGranularity(opt.value)"
                >
                  {{ opt.label }}
                </button>
              </div>
            </div>
            <div class="admin-filter-field">
              <label class="admin-filter-label">
                {{
                  granularity === 'day'
                    ? t('notificationManagement.stats.selectDay')
                    : granularity === 'month'
                      ? t('notificationManagement.stats.selectYearMonth')
                      : t('notificationManagement.stats.selectYear')
                }}
              </label>
              <div v-if="granularity === 'day'" class="flex items-center gap-2">
                <input
                  v-model="selectedDay"
                  type="date"
                  class="admin-filter-control w-40"
                  @change="onDayChange"
                />
              </div>
              <div
                v-else-if="granularity === 'month'"
                class="flex items-center gap-2"
              >
                <select
                  v-model="selectedYear"
                  class="admin-filter-control w-24"
                  @change="onMonthYearChange"
                >
                  <option v-for="y in yearOptions" :key="y" :value="y">
                    {{ y }}
                  </option>
                </select>
                <select
                  v-model="selectedMonth"
                  class="admin-filter-control w-28"
                  @change="onMonthYearChange"
                >
                  <option v-for="m in 12" :key="m" :value="m">
                    {{ String(m).padStart(2, '0') }}
                  </option>
                </select>
              </div>
              <div v-else class="flex items-center gap-2">
                <select
                  v-model="selectedYear"
                  class="admin-filter-control w-24"
                  @change="onYearChange"
                >
                  <option v-for="y in yearOptions" :key="y" :value="y">
                    {{ y }}
                  </option>
                </select>
              </div>
            </div>
          </div>
          <div class="admin-toolbar-end">
            <BaseButton
              variant="outline"
              size="sm"
              class="flex items-center gap-2"
              @click="fetchStats"
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
              {{ t('notificationManagement.stats.refreshData') }}
            </BaseButton>
          </div>
        </template>

        <div class="w-full">
          <BaseLoading v-if="loading && !statsData" />

          <EmptyState
            v-if="!loading && !statsData"
            variant="admin"
            :title="t('notificationManagement.stats.noData')"
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
                  d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"
                />
              </svg>
            </template>
          </EmptyState>

          <template v-else-if="statsData">
            <section class="admin-summary-grid mb-6">
              <MetricTile
                :label="t('notificationManagement.stats.total')"
                :value="formatNum(statsData.summary?.total)"
                :hint="t('notificationManagement.stats.totalDesc')"
              />
              <MetricTile
                :label="t('notificationManagement.stats.success')"
                :value="formatNum(statsData.summary?.total_sent)"
                :hint="successMetricHint"
              />
              <MetricTile
                :label="t('notificationManagement.stats.failure')"
                :value="formatNum(statsData.summary?.total_failed)"
                :hint="failureMetricHint"
              />
            </section>

            <div class="admin-chart-panel admin-chart-panel--tall mb-6">
              <h3 class="admin-chart-title">
                {{ t('notificationManagement.stats.seriesTitle') }}
              </h3>
              <p class="admin-chart-copy">
                {{ t('notificationManagement.stats.seriesSubtitle') }}
              </p>
              <div class="admin-chart-body">
                <div
                  v-if="seriesChartData && seriesChartData.labels.length > 0"
                  class="admin-chart-canvas admin-chart-canvas--tall"
                >
                  <Line :data="seriesChartData" :options="seriesChartOptions" />
                </div>
                <div v-else class="admin-chart-empty admin-chart-canvas--tall">
                  {{ t('notificationManagement.stats.noData') }}
                </div>
              </div>
            </div>

            <div
              class="grid grid-cols-1 xl:grid-cols-2 gap-6 mb-6 items-stretch"
            >
              <div class="admin-chart-panel">
                <h3 class="admin-chart-title">
                  {{ t('notificationManagement.stats.channelTitle') }}
                </h3>
                <p class="admin-chart-copy">
                  {{ t('notificationManagement.stats.channelSubtitle') }}
                </p>
                <div class="flex-1 min-h-0 overflow-y-auto space-y-5 pr-1">
                  <div
                    v-for="(row, idx) in channelBarData"
                    :key="row.provider_type"
                    class="space-y-1.5"
                  >
                    <div class="flex items-center justify-between gap-3">
                      <span
                        class="shrink-0 text-sm font-medium text-slate-700"
                        >{{ row.label }}</span
                      >
                      <span class="flex items-center gap-2 shrink-0">
                        <span class="text-xs font-medium text-slate-500"
                          >{{ row.percent }}%</span
                        >
                        <span class="text-xs font-medium text-slate-900">{{
                          formatNum(row.count)
                        }}</span>
                      </span>
                    </div>
                    <div class="admin-progress-track">
                      <div
                        :style="{
                          width: row.percent + '%',
                          backgroundColor: row.color
                        }"
                        class="h-full rounded-full transition-all"
                      />
                    </div>
                  </div>
                </div>
                <BaseButton
                  variant="outline"
                  size="sm"
                  class="flex-shrink-0 w-full mt-4 flex items-center justify-center py-2.5"
                  @click="goToRecords"
                >
                  {{ t('notificationManagement.stats.viewReport') }}
                </BaseButton>
              </div>
              <div class="admin-chart-panel">
                <h3 class="admin-chart-title mb-3">
                  {{ t('notificationManagement.stats.bySource') }}
                </h3>
                <div
                  v-if="sourcePieData?.datasets?.[0]?.data?.some((v) => v > 0)"
                  class="admin-chart-canvas"
                >
                  <Doughnut :data="sourcePieData" :options="sourcePieOptions" />
                </div>
                <div v-else class="admin-chart-empty">
                  {{ t('notificationManagement.stats.noData') }}
                </div>
              </div>
            </div>
          </template>
        </div>
      </AdminListSection>
    </PageFrame>
  </AdminLayout>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { Line, Doughnut } from 'vue-chartjs'
import {
  Chart as ChartJS,
  ArcElement,
  CategoryScale,
  Filler,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend
} from 'chart.js'
import { notificationsAdminApi } from '@/admin/api'
import AdminListSection from '@/admin/components/AdminListSection.vue'
import AdminLayout from '@/admin/layout/AdminLayout.vue'
import BaseLoading from '@/components/ui/BaseLoading.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import MetricTile from '@/components/ui/MetricTile.vue'
import PageFrame from '@/components/ui/PageFrame.vue'

ChartJS.register(
  ArcElement,
  CategoryScale,
  Filler,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend
)

const { t } = useI18n()
const router = useRouter()

function formatNum(value) {
  if (value == null || value === '') return '0'
  const n = Number(value)
  return Number.isFinite(n) ? n.toLocaleString() : '0'
}

const statsData = ref(null)
const loading = ref(false)
const granularity = ref('day')
const userScope = ref('')
const userOptions = ref([])
const startDate = ref('')
const endDate = ref('')

const selectedDay = ref('')
const selectedYear = ref(new Date().getFullYear())
const selectedMonth = ref(new Date().getMonth() + 1)

const currentYear = new Date().getFullYear()
const yearOptions = computed(() => {
  const arr = []
  for (let y = currentYear; y >= currentYear - 10; y--) arr.push(y)
  return arr
})

const granularityOptions = computed(() => [
  { value: 'day', label: t('notificationManagement.stats.granularityDay') },
  { value: 'month', label: t('notificationManagement.stats.granularityMonth') },
  { value: 'year', label: t('notificationManagement.stats.granularityYear') }
])

const bySource = computed(() => {
  const list = statsData.value?.by_source
  return Array.isArray(list) ? list : []
})

const successRatePct = computed(() => {
  const s = statsData.value?.summary
  if (!s || !s.total) return null
  const rate = (Number(s.total_sent) / Number(s.total)) * 100
  return rate.toFixed(1)
})

const failedRatePct = computed(() => {
  const s = statsData.value?.summary
  if (!s || !s.total) return null
  const rate = (Number(s.total_failed) / Number(s.total)) * 100
  return rate.toFixed(1)
})

const successMetricHint = computed(() =>
  successRatePct.value !== null
    ? `${t('notificationManagement.stats.sentDesc')}${t('common.metaSeparator')}${successRatePct.value}% ${t('notificationManagement.stats.successRate')}`
    : t('notificationManagement.stats.sentDesc')
)

const failureMetricHint = computed(() =>
  failedRatePct.value !== null
    ? `${t('notificationManagement.stats.failedDesc')}${t('common.metaSeparator')}${failedRatePct.value}% ${t('notificationManagement.stats.failureRate')}`
    : t('notificationManagement.stats.failedDesc')
)

const seriesItems = computed(() => {
  const list = statsData.value?.series
  return Array.isArray(list) ? list : []
})

const hasSuccessFailedSeries = computed(() => {
  const first = seriesItems.value[0]
  return first && 'success' in first && 'failed' in first
})

const seriesChartData = computed(() => {
  const list = seriesItems.value
  if (list.length === 0) return null
  if (hasSuccessFailedSeries.value) {
    return {
      labels: list.map((r) => r.bucket || t('common.emptyValue')),
      datasets: [
        {
          label: t('notificationManagement.stats.totalSent'),
          data: list.map((r) => r.success ?? 0),
          borderColor: 'rgb(34, 197, 94)',
          backgroundColor: 'rgba(34, 197, 94, 0.1)',
          tension: 0.3,
          fill: true
        },
        {
          label: t('notificationManagement.stats.totalFailed'),
          data: list.map((r) => r.failed ?? 0),
          borderColor: 'rgb(239, 68, 68)',
          backgroundColor: 'rgba(239, 68, 68, 0.1)',
          tension: 0.3,
          fill: true
        }
      ]
    }
  }
  return {
    labels: list.map((r) => r.bucket || t('common.emptyValue')),
    datasets: [
      {
        label: t('notificationManagement.stats.count'),
        data: list.map((r) => r.count ?? 0),
        borderColor: 'rgb(99, 102, 241)',
        backgroundColor: 'rgba(99, 102, 241, 0.1)',
        tension: 0.3,
        fill: true
      }
    ]
  }
})

const seriesChartOptions = computed(() => ({
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: {
      position: 'top',
      align: 'end',
      labels: { usePointStyle: true, padding: 12 }
    },
    tooltip: {
      mode: 'index',
      intersect: false
    }
  },
  scales: {
    x: {
      grid: { display: false },
      ticks: {
        maxTicksLimit: 12,
        maxRotation: 45,
        minRotation: 0,
        font: { size: 11 }
      }
    },
    y: {
      beginAtZero: true,
      grid: { color: 'rgba(0,0,0,0.06)' },
      ticks: { precision: 0 }
    }
  }
}))

const totalForChannel = computed(() => {
  const list = statsData.value?.by_provider
  if (!Array.isArray(list)) return 0
  return list.reduce((sum, r) => sum + Number(r.count || 0), 0)
})

const CHANNEL_COLORS = ['#3b82f6', '#22c55e', '#eab308', '#a855f7']

const ALL_CHANNELS = [
  {
    provider_type: 'feishu',
    labelKey: 'notificationManagement.channels.providerFeishu'
  },
  {
    provider_type: 'wecom',
    labelKey: 'notificationManagement.channels.providerWecom'
  },
  {
    provider_type: 'wechat',
    labelKey: 'notificationManagement.channels.providerWechat'
  },
  {
    provider_type: 'email',
    labelKey: 'notificationManagement.channels.typeEmail'
  }
]

const channelBarData = computed(() => {
  const list = statsData.value?.by_provider
  const byType = Array.isArray(list)
    ? Object.fromEntries(
        list.map((r) => [
          r.provider_type,
          {
            count: Number(r.count ?? 0),
            label: r.provider_display_name || r.provider_type
          }
        ])
      )
    : {}
  const total = totalForChannel.value || 1
  return ALL_CHANNELS.map((ch, i) => {
    const data = byType[ch.provider_type]
    const count = data ? data.count : 0
    const label = ch.labelKey ? t(ch.labelKey) : data?.label || ch.provider_type
    return {
      provider_type: ch.provider_type,
      label,
      count,
      percent: total > 0 ? Math.round((count / total) * 100) : 0,
      color: CHANNEL_COLORS[i % CHANNEL_COLORS.length]
    }
  })
})

const SOURCE_PIE_COLORS = [
  '#3b82f6',
  '#22c55e',
  '#eab308',
  '#a855f7',
  '#ec4899',
  '#06b6d4',
  '#f97316',
  '#84cc16',
  '#6366f1',
  '#14b8a6'
]

const sourcePieData = computed(() => {
  const list = bySource.value
  if (!list.length) return null
  return {
    labels: list.map((r) => {
      const app = r.source_app || t('common.emptyValue')
      const type = r.source_type || t('common.emptyValue')
      return `${app} / ${type}`
    }),
    datasets: [
      {
        data: list.map((r) => Number(r.count ?? 0)),
        backgroundColor: list.map(
          (_, i) => SOURCE_PIE_COLORS[i % SOURCE_PIE_COLORS.length]
        ),
        borderWidth: 1,
        borderColor: '#fff'
      }
    ]
  }
})

const sourcePieOptions = computed(() => ({
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: {
      position: 'right',
      labels: { usePointStyle: true, padding: 10, font: { size: 11 } }
    },
    tooltip: {
      callbacks: {
        label: (ctx) => {
          const total = ctx.dataset.data.reduce((a, b) => a + b, 0)
          const pct = total > 0 ? ((ctx.raw / total) * 100).toFixed(1) : 0
          return `${ctx.label}: ${ctx.raw} (${pct}%)`
        }
      }
    }
  }
}))

function formatDate(date) {
  const y = date.getFullYear()
  const m = String(date.getMonth() + 1).padStart(2, '0')
  const d = String(date.getDate()).padStart(2, '0')
  return `${y}-${m}-${d}`
}

async function fetchUserOptions() {
  try {
    const list = await notificationsAdminApi.getUsers()
    userOptions.value = Array.isArray(list)
      ? list.map((u) => ({
          user_id: u.user_id ?? u.id,
          display: (
            u.display ??
            u.username ??
            (u.user_id != null
              ? `#${u.user_id}`
              : u.id != null
                ? `#${u.id}`
                : '')
          ).toString()
        }))
      : []
  } catch {
    userOptions.value = []
  }
}

function setDefaultDates() {
  const now = new Date()
  const todayStr = formatDate(now)
  const g = granularity.value
  if (g === 'day') {
    selectedDay.value = todayStr
    startDate.value = todayStr
    endDate.value = todayStr
  } else if (g === 'month') {
    selectedYear.value = now.getFullYear()
    selectedMonth.value = now.getMonth() + 1
    startDate.value = `${selectedYear.value}-${String(selectedMonth.value).padStart(2, '0')}-01`
    const last = new Date(selectedYear.value, selectedMonth.value, 0)
    endDate.value = formatDate(last)
  } else {
    selectedYear.value = now.getFullYear()
    startDate.value = `${selectedYear.value}-01-01`
    endDate.value = `${selectedYear.value}-12-31`
  }
}

function onDayChange() {
  if (!selectedDay.value) return
  startDate.value = selectedDay.value
  endDate.value = selectedDay.value
  fetchStats()
}

function onMonthYearChange() {
  const y = selectedYear.value
  const m = selectedMonth.value
  if (!y || !m) return
  startDate.value = `${y}-${String(m).padStart(2, '0')}-01`
  const last = new Date(y, m, 0)
  endDate.value = formatDate(last)
  fetchStats()
}

function onYearChange() {
  const y = selectedYear.value
  if (!y) return
  startDate.value = `${y}-01-01`
  endDate.value = `${y}-12-31`
  fetchStats()
}

function selectGranularity(g) {
  granularity.value = g
  setDefaultDates()
  fetchStats()
}

async function fetchStats() {
  if (!startDate.value || !endDate.value) {
    setDefaultDates()
  }
  loading.value = true
  try {
    const params = { granularity: granularity.value }
    if (startDate.value) params.start_date = startDate.value
    if (endDate.value) params.end_date = endDate.value
    if (userScope.value) params.user_id = userScope.value
    const data = await notificationsAdminApi.getStats(params)
    statsData.value = data ?? null
  } catch {
    statsData.value = null
  } finally {
    loading.value = false
  }
}

function goToRecords() {
  router.push({ name: 'AdminNotificationsRecords' })
}

onMounted(() => {
  fetchUserOptions()
  setDefaultDates()
  fetchStats()
})
</script>
