<template>
  <AdminLayout>
    <PageFrame variant="soft" :title="t('adminPages.monitoring.blackboxInstancesTitle')">
      <AdminListSection>
        <template #filterFields>
          <label class="admin-filter-field">
            <span class="admin-filter-label">{{ t('adminPages.monitoring.installStatus') }}</span>
            <select v-model="filters.installStatus" class="admin-filter-control">
              <option value="all">{{ t('common.all') }}</option>
              <option value="success">{{ t('adminPages.monitoring.statusSuccess') }}</option>
              <option value="failed">{{ t('adminPages.monitoring.statusFailed') }}</option>
              <option value="installing">{{ t('adminPages.monitoring.statusInstalling') }}</option>
              <option value="unknown">{{ t('adminPages.monitoring.statusUnknown') }}</option>
            </select>
          </label>
          <label class="admin-filter-field">
            <span class="admin-filter-label">{{ t('adminPages.monitoring.prometheusStatus') }}</span>
            <select v-model="filters.prometheusStatus" class="admin-filter-control">
              <option value="all">{{ t('common.all') }}</option>
              <option value="up">{{ t('adminPages.monitoring.statusUp') }}</option>
              <option value="down">{{ t('adminPages.monitoring.statusDown') }}</option>
              <option value="not_discovered">{{ t('adminPages.monitoring.prometheusNotDiscovered') }}</option>
            </select>
          </label>
        </template>
        <template #toolbarEnd>
          <BaseButton variant="outline" size="sm" :loading="syncing" @click="syncAndLoad">
            {{ t('adminPages.monitoring.syncRealState') }}
          </BaseButton>
          <BaseButton variant="outline" size="sm" :loading="loading" @click="load">
            {{ t('common.refresh') }}
          </BaseButton>
        </template>

        <AdminPageState :loading="loading" :error="error" :empty="false">
          <section class="grid gap-4">
            <section class="grid gap-3 md:grid-cols-4">
              <div v-for="item in summaryCards" :key="item.label" class="admin-workbench-panel px-4 py-3">
                <p class="text-xs font-medium text-slate-500">{{ item.label }}</p>
                <p class="mt-1 text-2xl font-semibold text-slate-950">{{ item.value }}</p>
              </div>
            </section>

            <AdminTable>
              <thead>
                <tr>
                  <th class="admin-table-head">{{ t('adminPages.monitoring.blackboxInstance') }}</th>
                  <th class="admin-table-head">{{ t('adminPages.monitoring.address') }}</th>
                  <th class="admin-table-head">{{ t('adminPages.monitoring.installStatus') }}</th>
                  <th class="admin-table-head">{{ t('adminPages.monitoring.prometheusStatus') }}</th>
                  <th class="admin-table-head">{{ t('adminPages.monitoring.relatedProbeTargets') }}</th>
                  <th class="admin-table-head">{{ t('common.actions') }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-if="!filteredInstances.length" class="admin-table-row">
                  <td class="admin-table-cell text-slate-400" colspan="6">
                    {{ t('common.noData') }}
                  </td>
                </tr>
                <tr v-for="item in filteredInstances" :key="item.host_id" class="admin-table-row align-top">
                  <td class="admin-table-cell">
                    <p class="font-semibold text-slate-900">{{ item.probe_name || item.hostname }}</p>
                    <p class="mt-1 text-xs text-slate-500">{{ item.hostname }}</p>
                  </td>
                  <td class="admin-table-cell text-slate-600">
                    <p>{{ item.address }}:{{ item.port }}</p>
                    <p class="mt-1 break-all text-xs text-slate-400">{{ item.install_dir || t('common.emptyValue') }}</p>
                  </td>
                  <td class="admin-table-cell">
                    <span class="inline-flex rounded-full border px-2.5 py-1 text-xs font-semibold" :class="installStatusClass(item.install_status)">
                      {{ installStatusText(item.install_status) }}
                    </span>
                    <p v-if="item.last_error" class="mt-2 max-w-xs break-words text-xs text-rose-600">
                      {{ item.last_error }}
                    </p>
                  </td>
                  <td class="admin-table-cell">
                    <span class="inline-flex rounded-full border px-2.5 py-1 text-xs font-semibold" :class="prometheusStatusClass(item.prometheus_status)">
                      {{ prometheusStatusText(item.prometheus_status) }}
                    </span>
                  </td>
                  <td class="admin-table-cell text-slate-600">
                    <p class="font-semibold text-slate-900">{{ item.probe_target_count }}</p>
                    <div v-if="item.probe_targets?.length" class="mt-2 grid gap-1">
                      <span
                        v-for="target in item.probe_targets.slice(0, 3)"
                        :key="`${target.type}:${target.target}`"
                        class="max-w-xs truncate text-xs text-slate-500"
                      >
                        {{ target.type || '-' }} / {{ target.target }}
                      </span>
                    </div>
                  </td>
                  <td class="admin-table-cell">
                    <div class="admin-row-actions">
                      <router-link class="btn btn-outline btn-sm" to="/management/monitoring/assets">
                        {{ item.install_status === 'success' ? t('adminPages.monitoring.openAssets') : t('adminPages.monitoring.installBlackbox') }}
                      </router-link>
                      <router-link class="btn btn-ghost btn-sm" to="/management/monitoring/probes">
                        {{ t('adminPages.monitoring.openProbes') }}
                      </router-link>
                    </div>
                  </td>
                </tr>
              </tbody>
            </AdminTable>
          </section>
        </AdminPageState>
      </AdminListSection>
    </PageFrame>
  </AdminLayout>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import AdminLayout from '@/admin/layout/AdminLayout.vue'
import AdminListSection from '@/admin/components/AdminListSection.vue'
import AdminPageState from '@/admin/components/AdminPageState.vue'
import AdminTable from '@/admin/components/AdminTable.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import PageFrame from '@/components/ui/PageFrame.vue'
import { monitoringStackApi } from '@/admin/api/monitoringStack'

const { t } = useI18n()
const loading = ref(false)
const syncing = ref(false)
const error = ref('')
const instances = ref([])
const summary = ref({})
const filters = reactive({
  installStatus: 'all',
  prometheusStatus: 'all'
})

const filteredInstances = computed(() =>
  instances.value.filter((item) => {
    const installMatched = filters.installStatus === 'all' || item.install_status === filters.installStatus
    const prometheusMatched = filters.prometheusStatus === 'all' || item.prometheus_status === filters.prometheusStatus
    return installMatched && prometheusMatched
  })
)

const summaryCards = computed(() => [
  {
    label: t('adminPages.monitoring.blackboxInstanceCount'),
    value: summary.value.total || 0
  },
  {
    label: t('adminPages.monitoring.installedInstances'),
    value: summary.value.installed || 0
  },
  {
    label: t('adminPages.monitoring.abnormalInstances'),
    value: summary.value.abnormal || 0
  },
  {
    label: t('adminPages.monitoring.prometheusDiscoveredInstances'),
    value: summary.value.prometheus_discovered || 0
  }
])

function installStatusText(status) {
  const value = String(status || 'unknown').toLowerCase()
  if (value === 'success') return t('adminPages.monitoring.statusSuccess')
  if (value === 'failed') return t('adminPages.monitoring.statusFailed')
  if (value === 'installing') return t('adminPages.monitoring.statusInstalling')
  return t('adminPages.monitoring.statusUnknown')
}

function installStatusClass(status) {
  const value = String(status || 'unknown').toLowerCase()
  if (value === 'success') return 'border-emerald-200 bg-emerald-50 text-emerald-700'
  if (value === 'failed') return 'border-rose-200 bg-rose-50 text-rose-700'
  if (value === 'installing') return 'border-sky-200 bg-sky-50 text-sky-700'
  return 'border-slate-200 bg-slate-50 text-slate-500'
}

function prometheusStatusText(status) {
  const value = String(status || 'not_discovered').toLowerCase()
  if (value === 'up') return t('adminPages.monitoring.statusUp')
  if (value === 'down') return t('adminPages.monitoring.statusDown')
  return t('adminPages.monitoring.prometheusNotDiscovered')
}

function prometheusStatusClass(status) {
  const value = String(status || 'not_discovered').toLowerCase()
  if (value === 'up') return 'border-emerald-200 bg-emerald-50 text-emerald-700'
  if (value === 'down') return 'border-rose-200 bg-rose-50 text-rose-700'
  return 'border-slate-200 bg-slate-50 text-slate-500'
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const data = await monitoringStackApi.getBlackboxInstances()
    summary.value = data.summary || {}
    instances.value = data.results || []
  } catch (err) {
    error.value = err?.response?.data?.detail || err.message
  } finally {
    loading.value = false
  }
}

async function syncAndLoad() {
  syncing.value = true
  error.value = ''
  try {
    await monitoringStackApi.syncGovernance('all')
    await load()
  } catch (err) {
    error.value = err?.response?.data?.detail || err.message
  } finally {
    syncing.value = false
  }
}

onMounted(load)
</script>
