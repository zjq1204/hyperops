<template>
  <AdminLayout>
    <PageFrame variant="soft" :title="t('adminPages.jenkinsEntries.title')">
      <template #actions>
        <BaseButton @click="showEntryModal = true">{{
          t('adminPages.jenkinsEntries.add')
        }}</BaseButton>
      </template>

      <AdminListSection>
        <AdminTable v-if="entries.length">
          <thead>
            <tr>
              <th class="admin-table-head">{{ t('common.name') }}</th>
              <th class="admin-table-head">
                Jenkins {{ t('adminNav.instances') }}
              </th>
              <th class="admin-table-head">
                {{ t('adminPages.jenkinsEntries.jobName') }}
              </th>
              <th class="admin-table-head">
                {{ t('adminPages.jenkinsEntries.paramCount') }}
              </th>
              <th class="admin-table-head">{{ t('common.status') }}</th>
              <th class="admin-table-head">{{ t('common.actions') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="entry in entries"
              :key="entry.id"
              class="admin-table-row"
            >
              <td class="admin-table-cell">
                <div class="font-semibold text-slate-900">{{ entry.name }}</div>
                <div
                  v-if="entry.description"
                  class="mt-1 text-xs text-slate-500"
                >
                  {{ entry.description }}
                </div>
              </td>
              <td class="admin-table-cell text-sm text-slate-500">
                {{ entry.instance_name }}
              </td>
              <td class="admin-table-cell font-mono text-sm text-slate-600">
                {{ entry.job_name }}
              </td>
              <td class="admin-table-cell text-sm text-slate-500">
                {{ Object.keys(entry.params_config || {}).length }}
              </td>
              <td class="admin-table-cell">
                <span
                  :class="
                    entry.is_active
                      ? 'admin-status-badge admin-status-badge--success'
                      : 'admin-status-badge admin-status-badge--muted'
                  "
                >
                  {{
                    entry.is_active ? t('common.enabled') : t('common.disabled')
                  }}
                </span>
              </td>
              <td class="admin-table-cell">
                <div class="admin-row-actions">
                  <button
                    @click="editEntry(entry)"
                    class="admin-row-action admin-row-action--primary"
                  >
                    {{ t('common.edit') }}
                  </button>
                  <button
                    @click="deleteEntry(entry)"
                    class="admin-row-action admin-row-action--danger"
                  >
                    {{ t('common.delete') }}
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </AdminTable>

        <EmptyState
          v-else
          variant="admin"
          :title="t('adminPages.jenkinsEntries.emptyTitle')"
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
                d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z"
              />
            </svg>
          </template>
          <template #actions>
            <BaseButton @click="showEntryModal = true">{{
              t('adminPages.jenkinsEntries.add')
            }}</BaseButton>
          </template>
        </EmptyState>
      </AdminListSection>

      <BaseModal
        :show="showEntryModal"
        :title="
          editingEntry
            ? t('adminPages.jenkinsEntries.editTitle')
            : t('adminPages.jenkinsEntries.createTitle')
        "
        @close="closeEntryModal"
      >
        <form @submit.prevent="saveEntry">
          <div class="admin-modal-stack">
            <div>
              <label class="admin-modal-field-label"
                >Jenkins {{ t('common.instance') }}</label
              >
              <select
                v-model="entryForm.instance"
                required
                class="admin-modal-control"
              >
                <option value="">
                  {{ t('adminPages.jenkinsEntries.selectInstance') }}
                </option>
                <option
                  v-for="inst in instances"
                  :key="inst.id"
                  :value="inst.id"
                >
                  {{ inst.name }}
                </option>
              </select>
            </div>
            <div>
              <label class="admin-modal-field-label">{{
                t('adminPages.jenkinsEntries.displayName')
              }}</label>
              <input
                v-model="entryForm.name"
                type="text"
                required
                class="admin-modal-control"
              />
            </div>
            <div>
              <div class="mb-2 flex items-center justify-between gap-3">
                <label class="admin-modal-field-label mb-0">{{
                  t('adminPages.jenkinsEntries.jobName')
                }}</label>
                <BaseButton
                  variant="ghost"
                  size="sm"
                  :disabled="!entryForm.instance"
                  @click="goToJobList"
                >
                  {{ t('adminPages.jenkinsEntries.pickFromJobs') }}
                </BaseButton>
              </div>
              <input
                v-model="entryForm.job_name"
                type="text"
                required
                class="admin-modal-control"
                :placeholder="t('adminPages.jenkinsEntries.jobNamePlaceholder')"
              />
            </div>
            <div>
              <label class="admin-modal-field-label">{{
                t('common.description')
              }}</label>
              <textarea
                v-model="entryForm.description"
                rows="2"
                class="admin-modal-control min-h-[5.5rem]"
              ></textarea>
            </div>
            <div class="admin-modal-card-muted space-y-3">
              <div class="flex items-center justify-between gap-3">
                <div>
                  <label class="block text-sm font-medium text-slate-700">{{
                    t('adminPages.jenkinsEntries.paramsConfig')
                  }}</label>
                </div>
                <div class="flex items-center gap-2">
                  <span
                    v-if="loadingDraftParams"
                    class="text-xs font-medium text-sky-600"
                  >
                    {{ t('adminPages.jenkinsEntries.loadingParams') }}
                  </span>
                  <BaseButton
                    v-if="entryForm.instance && entryForm.job_name"
                    variant="secondary"
                    size="sm"
                    :disabled="loadingDraftParams"
                    @click="refreshParamRows"
                  >
                    {{ t('adminPages.jenkinsEntries.refreshParams') }}
                  </BaseButton>
                  <BaseButton variant="outline" size="sm" @click="addParamRow">
                    {{ t('adminPages.jenkinsEntries.addParam') }}
                  </BaseButton>
                </div>
              </div>

              <div v-if="paramRows.length" class="space-y-3">
                <div
                  v-for="(row, index) in paramRows"
                  :key="row.key"
                  class="admin-modal-card"
                >
                  <div class="flex items-start justify-between gap-3">
                    <div class="min-w-0">
                      <div class="flex flex-wrap items-center gap-2">
                        <input
                          v-model="row.name"
                          type="text"
                          class="border-none bg-transparent p-0 text-base font-semibold text-slate-900 focus:outline-none focus:ring-0"
                          :placeholder="
                            t('adminPages.jenkinsEntries.paramNamePlaceholder')
                          "
                          :readonly="row.locked"
                        />
                        <span v-if="row.type" class="admin-modal-chip">
                          {{ getParamTypeLabel(row.type) }}
                        </span>
                      </div>
                      <p
                        v-if="row.description"
                        class="mt-2 text-xs leading-5 text-slate-500"
                      >
                        {{ row.description }}
                      </p>
                      <p
                        v-if="row.choices?.length"
                        class="mt-2 text-xs text-slate-500"
                      >
                        {{ t('adminPages.jenkinsEntries.paramChoices') }}:
                        {{ row.choices.join(' / ') }}
                      </p>
                      <p
                        v-if="row.value_source"
                        class="mt-2 text-xs font-medium"
                        :class="
                          row.value_source === 'latest_success_build'
                            ? 'text-emerald-600'
                            : 'text-slate-500'
                        "
                      >
                        {{ getValueSourceLabel(row.value_source) }}
                      </p>
                    </div>
                    <button
                      type="button"
                      class="rounded-lg border border-rose-200 px-3 py-1.5 text-xs font-semibold text-rose-600 transition hover:bg-rose-50"
                      @click="removeParamRow(index)"
                    >
                      {{ t('common.delete') }}
                    </button>
                  </div>

                  <div
                    class="mt-4 grid gap-3 md:grid-cols-[minmax(0,12rem)_minmax(0,1fr)]"
                  >
                    <div>
                      <label class="admin-modal-field-label--compact">
                        {{ t('adminPages.jenkinsEntries.paramMode') }}
                      </label>
                      <select v-model="row.mode" class="admin-modal-control">
                        <option value="editable">
                          {{ t('adminPages.jenkinsEntries.modeEditable') }}
                        </option>
                        <option value="readonly">
                          {{ t('adminPages.jenkinsEntries.modeReadonly') }}
                        </option>
                        <option value="hidden">
                          {{ t('adminPages.jenkinsEntries.modeHidden') }}
                        </option>
                      </select>
                    </div>
                    <div>
                      <label class="admin-modal-field-label--compact">
                        {{ t('adminPages.jenkinsEntries.paramDefaultValue') }}
                      </label>
                      <select
                        v-if="isExtendedChoiceParam(row) && row.choices?.length"
                        v-model="row.default_value"
                        multiple
                        class="admin-modal-control min-h-[7rem]"
                      >
                        <option
                          v-for="choice in row.choices"
                          :key="choice"
                          :value="choice"
                        >
                          {{ choice }}
                        </option>
                      </select>
                      <select
                        v-else-if="isChoiceParam(row) && row.choices?.length"
                        v-model="row.default_value"
                        class="admin-modal-control"
                      >
                        <option
                          v-for="choice in row.choices"
                          :key="choice"
                          :value="choice"
                        >
                          {{ choice }}
                        </option>
                      </select>
                      <label
                        v-else-if="isBooleanParam(row)"
                        class="admin-modal-toggle min-h-[2.75rem]"
                      >
                        <input v-model="row.default_value" type="checkbox" />
                        <span class="text-sm font-medium text-slate-700">
                          {{
                            row.default_value
                              ? t('adminPages.jenkinsEntries.booleanTrue')
                              : t('adminPages.jenkinsEntries.booleanFalse')
                          }}
                        </span>
                      </label>
                      <textarea
                        v-else-if="isTextParam(row)"
                        v-model="row.default_value"
                        rows="3"
                        class="admin-modal-control min-h-[5.5rem]"
                        :placeholder="
                          t('adminPages.jenkinsEntries.paramDefaultPlaceholder')
                        "
                      ></textarea>
                      <input
                        v-else
                        v-model="row.default_value"
                        :type="isPasswordParam(row) ? 'password' : 'text'"
                        class="admin-modal-control"
                        :placeholder="
                          t('adminPages.jenkinsEntries.paramDefaultPlaceholder')
                        "
                      />
                    </div>
                  </div>
                </div>
              </div>

              <div v-else class="admin-modal-card-dashed">
                <p class="text-sm font-medium text-slate-700">
                  {{ t('adminPages.jenkinsEntries.noParamsTitle') }}
                </p>
              </div>

              <details class="admin-modal-card-muted">
                <summary
                  class="cursor-pointer text-xs font-semibold uppercase tracking-[0.18em] text-slate-500"
                >
                  {{ t('adminPages.jenkinsEntries.rawJsonPreview') }}
                </summary>
                <textarea
                  :value="paramsConfigJson"
                  rows="6"
                  readonly
                  class="admin-modal-control mt-3 min-h-[10rem] font-mono text-sm text-slate-600"
                ></textarea>
              </details>
            </div>
            <label class="admin-modal-toggle">
              <input v-model="entryForm.is_active" type="checkbox" />
              <span class="text-sm font-medium text-slate-700">{{
                t('adminPages.jenkinsEntries.entryEnabled')
              }}</span>
            </label>
          </div>
        </form>
        <template #footer>
          <div class="flex w-full justify-end gap-3">
            <BaseButton variant="secondary" @click="closeEntryModal">{{
              t('common.cancel')
            }}</BaseButton>
            <BaseButton @click="saveEntry">{{ t('common.save') }}</BaseButton>
          </div>
        </template>
      </BaseModal>

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
    </PageFrame>
  </AdminLayout>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import AdminListSection from '@/admin/components/AdminListSection.vue'
import AdminTable from '@/admin/components/AdminTable.vue'
import AdminLayout from '@/admin/layout/AdminLayout.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseModal from '@/components/ui/BaseModal.vue'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import PageFrame from '@/components/ui/PageFrame.vue'
import { useConfirmDialog } from '@/composables/useConfirmDialog'
import { useToast } from '@/composables/useToast'
import jenkinsApi from '@/api/jenkins'
import {
  buildParamRowsFromConfig,
  buildParamRowsFromDefinitions,
  buildParamsConfigFromRows,
  createParamRow,
  getParamTypeLabelKey,
  isBooleanParam,
  isChoiceParam,
  isExtendedChoiceParam,
  isPasswordParam,
  isTextParam
} from '@/utils/jenkinsParams'

const { t } = useI18n()
const { showToast } = useToast()
const route = useRoute()
const router = useRouter()
const {
  confirmDialog,
  requestConfirm,
  closeConfirmDialog,
  runConfirmedAction
} = useConfirmDialog()

const instances = ref([])
const entries = ref([])
const showEntryModal = ref(false)
const editingEntry = ref(null)
const routeDraftHandled = ref(false)

const entryForm = ref({
  instance: '',
  name: '',
  job_name: '',
  description: '',
  params_config: {},
  is_active: true
})

const paramsConfigJson = ref('{}')
const paramRows = ref([])

const loadingDraftParams = ref(false)
function getParamTypeLabel(type = '') {
  return t(`adminPages.jenkinsEntries.${getParamTypeLabelKey(type)}`)
}

function syncParamsConfigJsonFromRows() {
  const config = buildParamsConfigFromRows(paramRows.value)
  entryForm.value.params_config = config
  paramsConfigJson.value = JSON.stringify(config, null, 2)
}

function getValueSourceLabel(source) {
  if (source === 'latest_success_build') {
    return t('adminPages.jenkinsEntries.valueSource.latestSuccessBuild')
  }
  if (source === 'job_default') {
    return t('adminPages.jenkinsEntries.valueSource.jobDefault')
  }
  if (source === 'empty') {
    return t('adminPages.jenkinsEntries.valueSource.empty')
  }
  return ''
}

async function loadInstances() {
  try {
    instances.value = await jenkinsApi.listInstances()
  } catch (e) {
    showToast(
      t('adminPages.jenkinsEntries.toast.loadInstancesFailed', {
        message: e.message
      }),
      'error'
    )
  }
}

async function loadEntries() {
  try {
    entries.value = await jenkinsApi.listEntries()
  } catch (e) {
    showToast(
      t('adminPages.jenkinsEntries.toast.loadEntriesFailed', {
        message: e.message
      }),
      'error'
    )
  }
}

function editEntry(entry) {
  editingEntry.value = entry
  entryForm.value = {
    instance: entry.instance,
    name: entry.name,
    job_name: entry.job_name,
    description: entry.description,
    params_config: entry.params_config || {},
    is_active: entry.is_active
  }
  paramRows.value = buildParamRowsFromConfig(entry.params_config || {})
  syncParamsConfigJsonFromRows()
  showEntryModal.value = true
}

function closeEntryModal() {
  showEntryModal.value = false
  editingEntry.value = null
  entryForm.value = {
    instance: '',
    name: '',
    job_name: '',
    description: '',
    params_config: {},
    is_active: true
  }
  paramRows.value = []
  paramsConfigJson.value = '{}'
}

function goToJobList() {
  if (!entryForm.value.instance) {
    showToast(t('adminPages.jenkinsEntries.toast.selectInstanceFirst'), 'error')
    return
  }

  router.push({
    path: '/management/jenkins/jobs',
    query: {
      instance: String(entryForm.value.instance)
    }
  })
}

async function hydrateDraftParams(instanceId, jobName) {
  if (!instanceId || !jobName) return

  loadingDraftParams.value = true
  try {
    const data = await jenkinsApi.fetchParams(instanceId, jobName)
    const existingConfig = entryForm.value.params_config || {}
    paramRows.value = buildParamRowsFromDefinitions(
      data.params || [],
      existingConfig
    )
    syncParamsConfigJsonFromRows()
    const config = entryForm.value.params_config || {}
    if (!Object.keys(config).length) {
      showToast(t('adminPages.jenkinsEntries.toast.noParamsFound'), 'error')
    }
  } catch (e) {
    entryForm.value.params_config = {}
    paramRows.value = []
    paramsConfigJson.value = '{}'
    showToast(
      t('adminPages.jenkinsEntries.toast.loadParamsFailed', {
        message: e.message
      }),
      'error'
    )
  } finally {
    loadingDraftParams.value = false
  }
}

async function refreshParamRows() {
  if (!entryForm.value.instance || !entryForm.value.job_name) return
  await hydrateDraftParams(
    String(entryForm.value.instance),
    String(entryForm.value.job_name)
  )
}

async function applyJobDraftFromRoute() {
  if (routeDraftHandled.value) return

  const instanceId = route.query.instance
  const jobName = route.query.job_name
  if (!instanceId || !jobName) return

  const jobLabel = route.query.job_label
  editingEntry.value = null
  entryForm.value = {
    instance: String(instanceId),
    name:
      entryForm.value.name ||
      String(jobLabel || jobName)
        .split('/')
        .pop(),
    job_name: String(jobName),
    description: '',
    params_config: {},
    is_active: true
  }
  paramsConfigJson.value = '{}'
  paramRows.value = []
  showEntryModal.value = true
  await hydrateDraftParams(String(instanceId), String(jobName))
  routeDraftHandled.value = true

  router.replace({
    path: route.path,
    query: {}
  })
}

async function saveEntry() {
  entryForm.value.params_config = buildParamsConfigFromRows(paramRows.value)
  paramsConfigJson.value = JSON.stringify(
    entryForm.value.params_config || {},
    null,
    2
  )

  try {
    if (editingEntry.value) {
      await jenkinsApi.updateEntry(editingEntry.value.id, entryForm.value)
      showToast(t('adminPages.jenkinsEntries.toast.updated'))
    } else {
      await jenkinsApi.createEntry(entryForm.value)
      showToast(t('adminPages.jenkinsEntries.toast.created'))
    }
    closeEntryModal()
    loadEntries()
  } catch (e) {
    showToast(
      t('adminPages.jenkinsEntries.toast.saveFailed', { message: e.message }),
      'error'
    )
  }
}

async function deleteEntry(entry) {
  requestConfirm({
    title: t('common.delete'),
    message: t('adminPages.jenkinsEntries.deleteConfirm', { name: entry.name }),
    confirmText: t('common.delete'),
    onConfirm: async () => {
      try {
        await jenkinsApi.deleteEntry(entry.id)
        showToast(t('adminPages.jenkinsEntries.toast.deleteSucceeded'))
        loadEntries()
      } catch (e) {
        showToast(
          t('adminPages.jenkinsEntries.toast.deleteFailed', {
            message: e.message
          }),
          'error'
        )
      }
    }
  })
}

function addParamRow() {
  paramRows.value.push(createParamRow())
  syncParamsConfigJsonFromRows()
}

function removeParamRow(index) {
  paramRows.value.splice(index, 1)
  syncParamsConfigJsonFromRows()
}

onMounted(() => {
  loadInstances()
    .then(() => loadEntries())
    .then(() => {
      applyJobDraftFromRoute()
    })
})

watch(
  paramRows,
  () => {
    syncParamsConfigJsonFromRows()
  },
  { deep: true }
)
</script>
