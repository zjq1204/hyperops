<template>
  <AdminListSection>
    <template #toolbarStart>
          <span class="admin-summary-pill">
            {{ t('adminPages.monitoring.assetTotal', { count: assetRows.length }) }}
          </span>
          <span class="admin-summary-pill admin-summary-pill--success">
            {{ t('adminPages.monitoring.assetReadyCount', { count: readyCount }) }}
          </span>
          <span v-if="missingCount" class="admin-summary-pill admin-summary-pill--danger">
            {{ t('adminPages.monitoring.assetMissingCount', { count: missingCount }) }}
          </span>
    </template>
    <template #toolbarEnd>
          <BaseButton variant="outline" size="sm" :loading="loading" @click="load">
            {{ t('common.refresh') }}
          </BaseButton>
          <BaseButton variant="primary" size="sm" :loading="building" @click="buildAssets">
            {{ t('adminPages.monitoring.rebuildAssets') }}
          </BaseButton>
    </template>

    <AdminPageState :loading="loading" :error="error" :empty="false">
          <section class="admin-workbench-panel overflow-hidden p-0">
            <header class="flex flex-col gap-3 border-b border-slate-200/70 px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
              <div class="min-w-0">
                <h2 class="text-base font-semibold text-slate-900">
                  {{ t('adminPages.monitoring.installerFiles') }}
                </h2>
                <p v-if="assets.installer_dir" class="mt-1 truncate font-mono text-xs text-slate-500" :title="assets.installer_dir">
                  {{ assets.installer_dir }}
                </p>
              </div>
              <span :class="resourceStateClass">
                {{ resourceStateText }}
              </span>
            </header>

            <AdminTable>
              <thead>
                <tr>
                  <th class="admin-table-head">{{ t('common.name') }}</th>
                  <th class="admin-table-head hidden sm:table-cell">{{ t('common.status') }}</th>
                  <th class="admin-table-head hidden sm:table-cell">{{ t('adminPages.monitoring.size') }}</th>
                  <th class="admin-table-head hidden text-right sm:table-cell">{{ t('common.actions') }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="asset in assetRows" :key="asset.name" class="admin-table-row">
                  <td class="admin-table-cell">
                    <div class="flex min-w-0 items-start gap-3 sm:items-center">
                      <span class="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-slate-100 text-slate-500" aria-hidden="true">
                        <svg viewBox="0 0 24 24" class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="1.8">
                          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z" />
                          <path d="M14 2v6h6M8 13h8M8 17h6" />
                        </svg>
                      </span>
                      <div class="min-w-0 flex-1">
                        <span class="block truncate font-medium text-slate-900" :title="asset.name">
                          {{ asset.name }}
                        </span>
                        <div class="mt-1.5 flex items-center gap-3 text-xs sm:hidden">
                          <span :class="asset.exists ? 'text-emerald-700' : 'text-rose-700'">
                            {{ asset.exists ? t('adminPages.monitoring.assetReady') : t('adminPages.monitoring.assetMissing') }}
                          </span>
                          <span class="tabular-nums text-slate-500">{{ formatFileSize(asset.size) }}</span>
                          <a
                            v-if="asset.exists"
                            class="font-semibold text-blue-700"
                            :href="`/api/v1/monitoring/installer/${asset.name}`"
                            target="_blank"
                            rel="noopener"
                          >
                            {{ t('adminPages.monitoring.download') }}
                          </a>
                        </div>
                      </div>
                    </div>
                  </td>
                  <td class="admin-table-cell hidden sm:table-cell">
                    <span :class="asset.exists ? 'admin-status-pill admin-status-pill--success' : 'admin-status-pill admin-status-pill--danger'">
                      {{ asset.exists ? t('adminPages.monitoring.assetReady') : t('adminPages.monitoring.assetMissing') }}
                    </span>
                  </td>
                  <td class="admin-table-cell hidden tabular-nums text-slate-600 sm:table-cell" :title="String(asset.size || 0)">
                    {{ formatFileSize(asset.size) }}
                  </td>
                  <td class="admin-table-cell hidden text-right sm:table-cell">
                    <a
                      v-if="asset.exists"
                      class="inline-flex min-h-9 items-center rounded-md px-3 text-sm font-semibold text-blue-700 hover:bg-blue-50 hover:text-blue-900"
                      :href="`/api/v1/monitoring/installer/${asset.name}`"
                      target="_blank"
                      rel="noopener"
                    >
                      {{ t('adminPages.monitoring.download') }}
                    </a>
                    <span v-else class="text-sm text-slate-400">{{ t('common.emptyValue') }}</span>
                  </td>
                </tr>
              </tbody>
            </AdminTable>
          </section>
    </AdminPageState>
  </AdminListSection>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import AdminListSection from '@/admin/components/AdminListSection.vue'
import AdminPageState from '@/admin/components/AdminPageState.vue'
import AdminTable from '@/admin/components/AdminTable.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import { monitoringStackApi } from '@/admin/api/monitoringStack'

const { t } = useI18n()
const loading = ref(false)
const building = ref(false)
const error = ref('')
const assets = ref({})

const assetRows = computed(() =>
  Object.values(assets.value?.assets || {}).sort((a, b) =>
    a.name.localeCompare(b.name)
  )
)
const readyCount = computed(
  () => assetRows.value.filter((asset) => asset.exists).length
)
const missingCount = computed(() => assetRows.value.length - readyCount.value)
const resourceStateText = computed(() =>
  missingCount.value
    ? t('adminPages.monitoring.assetSetIncomplete')
    : t('adminPages.monitoring.assetSetReady')
)
const resourceStateClass = computed(() => [
  'inline-flex shrink-0 self-start rounded-full border px-2.5 py-1 text-xs font-semibold sm:self-auto',
  missingCount.value
    ? 'border-rose-200 bg-rose-50 text-rose-700'
    : 'border-emerald-200 bg-emerald-50 text-emerald-700'
])

function formatFileSize(value) {
  const bytes = Number(value) || 0
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    assets.value = (await monitoringStackApi.getInstallerAssets()) || {}
  } catch (err) {
    error.value = err?.response?.data?.detail || err.message
  } finally {
    loading.value = false
  }
}

async function buildAssets() {
  building.value = true
  error.value = ''
  try {
    assets.value = (await monitoringStackApi.buildInstallerAssets()) || {}
  } catch (err) {
    error.value = err?.response?.data?.detail || err.message
  } finally {
    building.value = false
  }
}

onMounted(load)
</script>
