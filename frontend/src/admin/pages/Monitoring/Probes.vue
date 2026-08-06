<template>
  <AdminLayout>
    <PageFrame variant="soft">
      <template #hero>
        <div
          class="flex flex-col gap-4 md:flex-row md:items-start md:justify-between"
        >
          <div>
            <h1 class="page-title-soft">
              {{ t('adminPages.monitoring.probesTitle') }}
            </h1>
            <p class="mt-1 text-sm leading-6 text-slate-500">
              {{ t('adminPages.monitoring.probesSubtitle') }}
            </p>
          </div>
          <div class="flex flex-col-reverse gap-2 sm:flex-row">
            <BaseButton variant="primary" @click="openCreateForm">
              {{ t('adminPages.monitoring.addProbe') }}
            </BaseButton>
          </div>
        </div>
      </template>

      <ProbeManagementTabs />

      <AdminListSection>
        <template #filterFields>
          <label
            class="probe-filter-field admin-filter-field min-w-[15rem] flex-1"
          >
            <span class="admin-filter-label">{{ t('common.search') }}</span>
            <input
              v-model="filters.search"
              class="admin-filter-control"
              :placeholder="t('adminPages.monitoring.searchProbeTargets')"
            />
          </label>
          <label class="probe-filter-field admin-filter-field min-w-[9rem]">
            <span class="admin-filter-label">{{
              t('adminPages.monitoring.probeType')
            }}</span>
            <select v-model="filters.type" class="admin-filter-control">
              <option value="">
                {{ t('adminPages.monitoring.allProbeTypes') }}
              </option>
              <option value="http">HTTP</option>
              <option value="tcp">TCP</option>
              <option value="icmp">ICMP</option>
            </select>
          </label>
          <label class="probe-filter-field admin-filter-field min-w-[9rem]">
            <span class="admin-filter-label">{{
              t('adminPages.monitoring.configStatus')
            }}</span>
            <select v-model="filters.config" class="admin-filter-control">
              <option value="">
                {{ t('adminPages.monitoring.allConfigStatuses') }}
              </option>
              <option value="enabled">
                {{ t('adminPages.monitoring.probeConfigEnabled') }}
              </option>
              <option value="disabled">
                {{ t('adminPages.monitoring.probeConfigDisabled') }}
              </option>
            </select>
          </label>
          <label class="probe-filter-field admin-filter-field min-w-[10rem]">
            <span class="admin-filter-label">{{
              t('adminPages.monitoring.effectStatus')
            }}</span>
            <select v-model="filters.effect" class="admin-filter-control">
              <option value="">
                {{ t('adminPages.monitoring.allEffectStatuses') }}
              </option>
              <option value="effective">
                {{ t('adminPages.monitoring.effectEffective') }}
              </option>
              <option value="pending">
                {{ t('adminPages.monitoring.effectPending') }}
              </option>
              <option value="abnormal">
                {{ t('adminPages.monitoring.effectAbnormal') }}
              </option>
              <option value="incomplete">
                {{ t('adminPages.monitoring.effectIncomplete') }}
              </option>
              <option value="unknown">
                {{ t('adminPages.monitoring.effectUnknown') }}
              </option>
            </select>
          </label>
        </template>
        <template #filterActions>
          <BaseButton
            variant="outline"
            size="sm"
            :loading="loading"
            @click="load"
          >
            {{ t('common.refresh') }}
          </BaseButton>
        </template>

        <div
          v-if="prometheusSummary.error && targets.length"
          class="flex flex-col gap-3 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 sm:flex-row sm:items-center sm:justify-between"
        >
          <p class="text-sm leading-6 text-amber-900">
            {{ t('adminPages.monitoring.effectUnknownHint') }}：{{
              prometheusSummary.error
            }}
          </p>
          <div class="flex flex-wrap gap-2">
            <BaseButton variant="outline" size="sm" @click="load">
              {{ t('adminPages.monitoring.retryLoad') }}
            </BaseButton>
            <BaseButton variant="outline" size="sm" @click="openSettings">
              {{ t('adminPages.monitoring.basicConfiguration') }}
            </BaseButton>
          </div>
        </div>

        <AdminPageState :loading="loading" :error="error" :empty="false">
          <div v-if="!targets.length" class="admin-empty-state">
            <h2 class="text-base font-semibold text-slate-900">
              {{ t('adminPages.monitoring.noProbeTargets') }}
            </h2>
            <p class="mt-2 max-w-md text-sm leading-6 text-slate-500">
              {{ t('adminPages.monitoring.noProbeTargetsHint') }}
            </p>
            <BaseButton class="mt-4" variant="primary" @click="openCreateForm">
              {{ t('adminPages.monitoring.addProbe') }}
            </BaseButton>
          </div>

          <template v-else>
            <AdminTable class="hidden md:block">
              <thead>
                <tr>
                  <th class="admin-table-head w-[28%]">
                    {{ t('adminPages.monitoring.target') }}
                  </th>
                  <th class="admin-table-head w-[8%]">
                    {{ t('adminPages.monitoring.probeType') }}
                  </th>
                  <th class="admin-table-head w-[18%]">
                    {{ t('adminPages.monitoring.probeNode') }}
                  </th>
                  <th class="admin-table-head w-[16%]">
                    {{ t('adminPages.monitoring.labels') }}
                  </th>
                  <th class="admin-table-head w-[12%]">
                    {{ t('adminPages.monitoring.configStatus') }}
                  </th>
                  <th class="admin-table-head w-[14%]">
                    {{ t('adminPages.monitoring.effectStatus') }}
                  </th>
                  <th class="admin-table-head w-[4%]">
                    <span class="sr-only">{{ t('common.actions') }}</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="row in filteredRows"
                  :key="row.target.id"
                  class="admin-table-row cursor-pointer"
                  @click="openDetails(row)"
                >
                  <td class="admin-table-cell">
                    <p class="break-all font-semibold text-slate-900">
                      {{ row.target.target }}
                    </p>
                    <p
                      v-if="row.target.labels?.service"
                      class="mt-1 text-xs text-slate-400"
                    >
                      {{ row.target.labels.service }}
                    </p>
                  </td>
                  <td
                    class="admin-table-cell text-xs font-semibold uppercase text-slate-600"
                  >
                    {{ row.target.type }}
                  </td>
                  <td class="admin-table-cell">
                    <p
                      class="font-semibold"
                      :class="
                        row.target.probe_node_name
                          ? 'text-slate-700'
                          : 'text-rose-600'
                      "
                    >
                      {{
                        row.target.probe_node_name ||
                        t('adminPages.monitoring.probeNodeNotSelected')
                      }}
                    </p>
                    <p
                      v-if="row.target.blackbox_address"
                      class="mt-1 break-all font-mono text-[11px] text-slate-400"
                    >
                      {{ row.target.blackbox_address }}
                    </p>
                  </td>
                  <td class="admin-table-cell">
                    <div class="flex flex-wrap gap-1.5">
                      <span
                        v-for="[key, value] in visibleLabels(row.target)"
                        :key="key"
                        class="rounded-md border border-slate-200 bg-slate-50 px-2 py-1 text-[11px] font-medium text-slate-600"
                      >
                        {{ value }}
                      </span>
                      <span
                        v-if="hiddenLabelCount(row.target)"
                        class="rounded-md border border-slate-200 bg-slate-50 px-2 py-1 text-[11px] font-medium text-slate-500"
                      >
                        +{{ hiddenLabelCount(row.target) }}
                      </span>
                      <span
                        v-if="!probeLabelPairs(row.target.labels).length"
                        class="text-slate-400"
                      >
                        {{ t('common.emptyValue') }}
                      </span>
                    </div>
                  </td>
                  <td class="admin-table-cell">
                    <span
                      class="inline-flex items-center gap-2 font-semibold"
                      :class="
                        row.target.enabled
                          ? 'text-emerald-700'
                          : 'text-slate-400'
                      "
                    >
                      <span class="h-1.5 w-1.5 rounded-full bg-current" />
                      {{
                        row.target.enabled
                          ? t('adminPages.monitoring.probeConfigEnabled')
                          : t('adminPages.monitoring.probeConfigDisabled')
                      }}
                    </span>
                  </td>
                  <td class="admin-table-cell">
                    <template v-if="row.effect.key !== 'disabled'">
                      <span
                        class="inline-flex items-center gap-2 font-semibold"
                        :class="effectClass(row.effect.key)"
                      >
                        <span class="h-1.5 w-1.5 rounded-full bg-current" />
                        {{ effectText(row.effect.key) }}
                      </span>
                      <p
                        class="mt-1 max-w-[14rem] break-words text-xs leading-5 text-slate-400"
                      >
                        {{ row.effect.error || effectHint(row.effect.key) }}
                      </p>
                    </template>
                    <span v-else class="text-slate-300">—</span>
                  </td>
                  <td class="admin-table-cell" @click.stop>
                    <details class="relative">
                      <summary
                        class="flex h-9 w-9 cursor-pointer list-none items-center justify-center rounded-md text-xl leading-none text-slate-500 transition hover:bg-slate-100 hover:text-slate-900"
                        :title="t('adminPages.monitoring.moreActions')"
                      >
                        <span aria-hidden="true">⋮</span>
                        <span class="sr-only">{{
                          t('adminPages.monitoring.moreActions')
                        }}</span>
                      </summary>
                      <div
                        class="absolute right-0 z-20 mt-1 grid min-w-32 gap-1 rounded-lg border border-slate-200 bg-white p-1.5 shadow-xl"
                      >
                        <button
                          class="min-h-9 rounded-md px-3 text-left text-sm text-slate-600 hover:bg-slate-50 hover:text-slate-900"
                          @click="editTarget(row.target)"
                        >
                          {{ t('common.edit') }}
                        </button>
                        <button
                          class="min-h-9 rounded-md px-3 text-left text-sm text-slate-600 hover:bg-slate-50 hover:text-slate-900"
                          @click="toggleTarget(row.target)"
                        >
                          {{
                            row.target.enabled
                              ? t('adminPages.monitoring.disableTarget')
                              : t('adminPages.monitoring.enableTarget')
                          }}
                        </button>
                        <button
                          class="min-h-9 rounded-md px-3 text-left text-sm text-rose-600 hover:bg-rose-50"
                          @click="requestDelete(row.target)"
                        >
                          {{ t('common.delete') }}
                        </button>
                      </div>
                    </details>
                  </td>
                </tr>
                <tr v-if="!filteredRows.length" class="admin-table-row">
                  <td
                    class="admin-table-cell text-center text-slate-400"
                    colspan="7"
                  >
                    {{ t('common.noData') }}
                  </td>
                </tr>
              </tbody>
            </AdminTable>

            <div class="grid gap-3 md:hidden">
              <article
                v-for="row in filteredRows"
                :key="row.target.id"
                class="rounded-lg border border-slate-200 bg-white p-4 shadow-sm"
                @click="openDetails(row)"
              >
                <div class="flex items-start justify-between gap-3">
                  <div class="min-w-0">
                    <p class="break-all font-semibold text-slate-900">
                      {{ row.target.target }}
                    </p>
                    <p class="mt-1 text-xs text-slate-400">
                      {{ row.target.type.toUpperCase() }} ·
                      {{
                        row.target.probe_node_name ||
                        t('adminPages.monitoring.probeNodeNotSelected')
                      }}
                    </p>
                  </div>
                  <span
                    v-if="row.effect.key !== 'disabled'"
                    class="inline-flex flex-shrink-0 items-center gap-1.5 text-xs font-semibold"
                    :class="effectClass(row.effect.key)"
                  >
                    <span class="h-1.5 w-1.5 rounded-full bg-current" />
                    {{ effectText(row.effect.key) }}
                  </span>
                </div>
                <dl
                  class="mt-4 grid grid-cols-[5rem_1fr] gap-2 border-t border-slate-100 pt-4 text-sm"
                >
                  <dt class="text-slate-400">
                    {{ t('adminPages.monitoring.configStatus') }}
                  </dt>
                  <dd class="text-slate-700">
                    {{
                      row.target.enabled
                        ? t('adminPages.monitoring.probeConfigEnabled')
                        : t('adminPages.monitoring.probeConfigDisabled')
                    }}
                  </dd>
                  <dt class="text-slate-400">
                    {{ t('adminPages.monitoring.labels') }}
                  </dt>
                  <dd class="text-slate-700">
                    {{
                      visibleLabels(row.target)
                        .map(([, value]) => value)
                        .join(t('common.metaSeparator')) ||
                      t('common.emptyValue')
                    }}
                  </dd>
                </dl>
              </article>
              <p
                v-if="!filteredRows.length"
                class="rounded-lg border border-slate-200 bg-white px-4 py-10 text-center text-sm text-slate-400"
              >
                {{ t('common.noData') }}
              </p>
            </div>

            <p class="text-sm text-slate-400">
              {{
                t('adminPages.monitoring.probeTargetCount', {
                  count: filteredRows.length
                })
              }}
            </p>
          </template>
        </AdminPageState>
      </AdminListSection>
    </PageFrame>

    <ProbeTargetForm
      :show="showForm"
      :target="editingTarget"
      :nodes="probeNodes"
      :saving="saving"
      @close="closeForm"
      @submit="saveTarget"
      @open-settings="openSettings"
    />

    <ProbeTargetDrawer
      :show="showDetails"
      :target="selectedRow?.target"
      :effect-state="selectedRow?.effect"
      @close="showDetails = false"
      @edit="editTarget"
      @toggle-enabled="toggleTarget"
    />

    <ConfirmDialog
      :show="confirmDialog.show"
      :title="confirmDialog.title"
      :message="confirmDialog.message"
      :confirm-text="confirmDialog.confirmText"
      :variant="confirmDialog.variant"
      :loading="confirmDialog.loading"
      @close="closeConfirmDialog"
      @confirm="runConfirmedAction"
    />
  </AdminLayout>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import AdminLayout from '@/admin/layout/AdminLayout.vue'
import AdminListSection from '@/admin/components/AdminListSection.vue'
import AdminPageState from '@/admin/components/AdminPageState.vue'
import AdminTable from '@/admin/components/AdminTable.vue'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import PageFrame from '@/components/ui/PageFrame.vue'
import ProbeManagementTabs from '@/admin/pages/Monitoring/probes/ProbeManagementTabs.vue'
import { monitoringStackApi } from '@/admin/api/monitoringStack'
import { useConfirmDialog } from '@/composables/useConfirmDialog'
import { useToast } from '@/composables/useToast'
import ProbeTargetDrawer from './probes/ProbeTargetDrawer.vue'
import ProbeTargetForm from './probes/ProbeTargetForm.vue'
import {
  matchesProbeFilters,
  probeLabelPairs,
  targetEffectState
} from './probes/targetState'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const { showSuccess, showError } = useToast()
const {
  confirmDialog,
  requestConfirm,
  closeConfirmDialog,
  runConfirmedAction
} = useConfirmDialog()

const loading = ref(false)
const saving = ref(false)
const error = ref('')
const targets = ref([])
const probeNodes = ref([])
const prometheusSummary = ref({ connected: false, probe_statuses: {} })
const showForm = ref(false)
const showDetails = ref(false)
const editingTarget = ref(null)
const selectedRow = ref(null)
const filters = reactive({
  search: String(route.query.search || ''),
  type: String(route.query.type || ''),
  config: String(route.query.config || ''),
  effect: String(route.query.effect || '')
})

const rows = computed(() =>
  targets.value.map((target) => ({
    target,
    effect: targetEffectState(target, probeNodes.value, prometheusSummary.value)
  }))
)
const filteredRows = computed(() =>
  rows.value.filter((row) =>
    matchesProbeFilters(row.target, row.effect, filters)
  )
)

const effectTextKeys = {
  incomplete: 'effectIncomplete',
  unknown: 'effectUnknown',
  pending: 'effectPending',
  effective: 'effectEffective',
  abnormal: 'effectAbnormal'
}
const effectHintKeys = {
  incomplete: 'effectIncompleteHint',
  unknown: 'effectUnknownHint',
  pending: 'effectPendingHint',
  effective: 'effectEffectiveHint',
  abnormal: 'effectAbnormalHint'
}
const effectClasses = {
  incomplete: 'text-blue-700',
  unknown: 'text-slate-500',
  pending: 'text-amber-700',
  effective: 'text-emerald-700',
  abnormal: 'text-rose-700'
}

function normalizeList(data) {
  return data?.results || data || []
}

function effectText(key) {
  return t(`adminPages.monitoring.${effectTextKeys[key] || 'effectUnknown'}`)
}

function effectHint(key) {
  return t(
    `adminPages.monitoring.${effectHintKeys[key] || 'effectUnknownHint'}`
  )
}

function effectClass(key) {
  return effectClasses[key] || effectClasses.unknown
}

function visibleLabels(target) {
  return probeLabelPairs(target.labels).slice(0, 2)
}

function hiddenLabelCount(target) {
  return Math.max(probeLabelPairs(target.labels).length - 2, 0)
}

function openCreateForm() {
  editingTarget.value = null
  showForm.value = true
}

function editTarget(target) {
  showDetails.value = false
  editingTarget.value = target
  showForm.value = true
}

function closeForm() {
  showForm.value = false
  editingTarget.value = null
}

function openDetails(row) {
  selectedRow.value = row
  showDetails.value = true
}

function openSettings() {
  closeForm()
  router.push('/management/monitoring/probes/settings')
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const [targetResult, nodeResult, prometheusResult] =
      await Promise.allSettled([
        monitoringStackApi.getProbeTargets(),
        monitoringStackApi.getProbeNodes(),
        monitoringStackApi.getPrometheusTargetsSummary()
      ])
    if (targetResult.status === 'rejected') throw targetResult.reason
    if (nodeResult.status === 'rejected') throw nodeResult.reason
    targets.value = normalizeList(targetResult.value)
    probeNodes.value = normalizeList(nodeResult.value)
    if (prometheusResult.status === 'fulfilled') {
      prometheusSummary.value = prometheusResult.value || { connected: false }
    } else {
      prometheusSummary.value = {
        connected: false,
        probe_statuses: {},
        error:
          prometheusResult.reason?.response?.data?.detail ||
          prometheusResult.reason?.message
      }
    }
  } catch (err) {
    error.value = err?.response?.data?.detail || err.message
  } finally {
    loading.value = false
  }
}

async function saveTarget({ id, payload }) {
  saving.value = true
  try {
    if (id) await monitoringStackApi.updateProbeTarget(id, payload)
    else await monitoringStackApi.createProbeTarget(payload)
    closeForm()
    showSuccess(t('adminPages.monitoring.targetSavedPending'))
    await load()
  } catch (err) {
    showError(err?.response?.data?.detail || err.message)
  } finally {
    saving.value = false
  }
}

async function toggleTarget(target) {
  try {
    await monitoringStackApi.updateProbeTarget(target.id, {
      enabled: !target.enabled
    })
    showDetails.value = false
    showSuccess(
      target.enabled
        ? t('adminPages.monitoring.targetDisabled')
        : t('adminPages.monitoring.targetEnabled')
    )
    await load()
  } catch (err) {
    showError(err?.response?.data?.detail || err.message)
  }
}

function requestDelete(target) {
  requestConfirm({
    title: t('adminPages.monitoring.deleteTargetTitle'),
    message: t('adminPages.monitoring.deleteTargetMessage', {
      target: target.target
    }),
    confirmText: t('common.delete'),
    variant: 'danger',
    onConfirm: async () => {
      await monitoringStackApi.deleteProbeTarget(target.id)
      showDetails.value = false
      showSuccess(t('adminPages.monitoring.targetDeleted'))
      await load()
    }
  })
}

watch(
  filters,
  (value) => {
    const query = Object.fromEntries(
      Object.entries(value).filter(([, item]) => String(item || '').trim())
    )
    router.replace({ query })
  },
  { deep: true }
)

onMounted(load)
</script>

<style scoped>
@media (max-width: 639px) {
  .probe-filter-field,
  .probe-filter-field :deep(.admin-filter-control),
  :deep(.admin-filter-grid),
  :deep(.admin-toolbar-end),
  :deep(.admin-toolbar-end .btn) {
    width: 100%;
    min-width: 0;
  }
}
</style>
