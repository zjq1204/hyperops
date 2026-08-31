<template>
  <AdminLayout>
    <PageFrame variant="soft" :title="pageTitle">
      <template #actions>
        <BaseButton variant="secondary" @click="goBack">
          {{ t('adminPages.jenkinsEntries.backToEntries') }}
        </BaseButton>
        <BaseButton :loading="saving" @click="saveEntry">
          {{ t('common.save') }}
        </BaseButton>
      </template>

      <div v-if="loadingPage" class="py-16 text-center text-sm text-slate-500">
        {{ t('common.loading') }}
      </div>

      <form
        v-else
        ref="formRef"
        class="border-y border-slate-200 bg-white"
        @submit.prevent="saveEntry"
      >
        <section class="px-5 py-6 sm:px-6">
          <div class="mb-5">
            <h2 class="text-base font-semibold text-slate-900">
              {{ t('adminPages.jenkinsEntries.basicInfoTitle') }}
            </h2>
            <p class="mt-1 text-sm text-slate-500">
              {{ t('adminPages.jenkinsEntries.editorSubtitle') }}
            </p>
          </div>

          <div class="grid gap-5 lg:grid-cols-2">
            <label class="block">
              <span class="admin-modal-field-label">
                Jenkins {{ t('common.instance') }}
              </span>
              <select
                v-model="entryForm.instance"
                required
                class="admin-modal-control"
              >
                <option value="">
                  {{ t('adminPages.jenkinsEntries.selectInstance') }}
                </option>
                <option
                  v-for="instance in instances"
                  :key="instance.id"
                  :value="String(instance.id)"
                >
                  {{ instance.name }}
                </option>
              </select>
            </label>

            <label class="block">
              <span class="admin-modal-field-label">
                {{ t('adminPages.jenkinsEntries.displayName') }}
              </span>
              <input
                v-model="entryForm.name"
                type="text"
                required
                class="admin-modal-control"
              />
            </label>

            <div class="lg:col-span-2">
              <div class="mb-1 flex items-center justify-between gap-3">
                <label
                  for="jenkins-entry-job"
                  class="text-sm font-medium text-slate-700"
                >
                  {{ t('adminPages.jenkinsEntries.jobName') }}
                </label>
                <button
                  type="button"
                  class="text-sm font-medium text-sky-700 hover:text-sky-900 disabled:cursor-not-allowed disabled:opacity-40"
                  :disabled="!entryForm.instance"
                  @click="goToJobList"
                >
                  {{ t('adminPages.jenkinsEntries.pickFromJobs') }}
                </button>
              </div>
              <input
                id="jenkins-entry-job"
                v-model="entryForm.job_name"
                type="text"
                required
                class="admin-modal-control"
                :placeholder="t('adminPages.jenkinsEntries.jobNamePlaceholder')"
              />
            </div>

            <label class="block lg:col-span-2">
              <span class="admin-modal-field-label">
                {{ t('common.description') }}
              </span>
              <textarea
                v-model="entryForm.description"
                rows="2"
                class="admin-modal-control"
                :placeholder="
                  t('adminPages.jenkinsEntries.descriptionPlaceholder')
                "
              ></textarea>
            </label>
          </div>
        </section>

        <section class="px-5 pb-6 sm:px-6">
          <JenkinsParameterTable
            v-model:rows="paramRows"
            :loading="loadingParams"
            :can-refresh="Boolean(entryForm.instance && entryForm.job_name)"
            @refresh="refreshParamRows"
          />
        </section>

        <details class="border-t border-slate-200 px-5 py-5 sm:px-6">
          <summary
            class="flex min-h-11 cursor-pointer list-none items-center justify-between gap-4"
          >
            <span>
              <span class="block text-sm font-semibold text-slate-900">
                {{ t('adminPages.jenkinsEntries.advancedOptions') }}
              </span>
              <span class="mt-1 block text-xs text-slate-500">
                {{ t('adminPages.jenkinsEntries.advancedOptionsHint') }}
              </span>
            </span>
            <svg
              class="h-4 w-4 shrink-0 text-slate-400"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
              aria-hidden="true"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="1.8"
                d="m6 9 6 6 6-6"
              />
            </svg>
          </summary>
          <div
            class="mt-4 grid gap-5 border-t border-slate-200 pt-5 lg:grid-cols-2"
          >
            <label class="admin-modal-toggle self-start">
              <input v-model="entryForm.is_active" type="checkbox" />
              <span class="text-sm font-medium text-slate-700">
                {{ t('adminPages.jenkinsEntries.entryEnabled') }}
              </span>
            </label>
            <div>
              <label class="admin-modal-field-label">
                {{ t('adminPages.jenkinsEntries.rawJsonPreview') }}
              </label>
              <textarea
                :value="paramsConfigJson"
                rows="8"
                readonly
                class="admin-modal-control min-h-[12rem] font-mono text-xs text-slate-600"
              ></textarea>
            </div>
          </div>
        </details>

        <div
          class="flex justify-end gap-3 border-t border-slate-200 bg-white px-5 py-4 sm:px-6"
        >
          <BaseButton variant="secondary" @click="goBack">
            {{ t('common.cancel') }}
          </BaseButton>
          <BaseButton type="submit" :loading="saving">
            {{ t('common.save') }}
          </BaseButton>
        </div>
      </form>
    </PageFrame>
  </AdminLayout>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import AdminLayout from '@/admin/layout/AdminLayout.vue'
import JenkinsParameterTable from '@/admin/pages/Jenkins/components/JenkinsParameterTable.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import PageFrame from '@/components/ui/PageFrame.vue'
import { useToast } from '@/composables/useToast'
import jenkinsApi from '@/api/jenkins'
import {
  buildParamRowsFromConfig,
  buildParamRowsFromDefinitions,
  buildParamsConfigFromRows
} from '@/utils/jenkinsParams'

const { t } = useI18n()
const { showToast } = useToast()
const route = useRoute()
const router = useRouter()

const formRef = ref(null)
const instances = ref([])
const paramRows = ref([])
const loadingPage = ref(true)
const loadingParams = ref(false)
const saving = ref(false)

const entryForm = ref({
  instance: '',
  name: '',
  job_name: '',
  description: '',
  params_config: {},
  is_active: true
})

const editingId = computed(() => route.params.id || '')
const pageTitle = computed(() =>
  editingId.value
    ? t('adminPages.jenkinsEntries.editPageTitle')
    : t('adminPages.jenkinsEntries.createPageTitle')
)

const paramsConfigJson = computed(() =>
  JSON.stringify(buildParamsConfigFromRows(paramRows.value), null, 2)
)

async function loadInstances() {
  instances.value = await jenkinsApi.listInstances()
}

async function loadEntry() {
  const entries = await jenkinsApi.listEntries()
  const entry = entries.find(
    (item) => String(item.id) === String(editingId.value)
  )
  if (!entry) {
    showToast(t('adminPages.jenkinsEntries.toast.entryNotFound'), 'error')
    goBack()
    return
  }
  entryForm.value = {
    instance: String(entry.instance),
    name: entry.name,
    job_name: entry.job_name,
    description: entry.description || '',
    params_config: entry.params_config || {},
    is_active: entry.is_active
  }
  paramRows.value = buildParamRowsFromConfig(entry.params_config || {})
}

async function applyCreateDraft() {
  const instanceId = route.query.instance
  const jobName = route.query.job_name
  if (!instanceId || !jobName) return
  entryForm.value.instance = String(instanceId)
  entryForm.value.job_name = String(jobName)
  entryForm.value.name = String(route.query.job_label || jobName)
    .split('/')
    .pop()
  await refreshParamRows()
}

async function refreshParamRows() {
  if (!entryForm.value.instance || !entryForm.value.job_name) return
  loadingParams.value = true
  try {
    const data = await jenkinsApi.fetchParams(
      String(entryForm.value.instance),
      String(entryForm.value.job_name)
    )
    paramRows.value = buildParamRowsFromDefinitions(
      data.params || [],
      buildParamsConfigFromRows(paramRows.value)
    )
    if (!paramRows.value.length) {
      showToast(t('adminPages.jenkinsEntries.toast.noParamsFound'), 'error')
    }
  } catch (error) {
    showToast(
      t('adminPages.jenkinsEntries.toast.loadParamsFailed', {
        message: error.message
      }),
      'error'
    )
  } finally {
    loadingParams.value = false
  }
}

async function saveEntry() {
  if (!formRef.value?.reportValidity()) return
  saving.value = true
  const payload = {
    ...entryForm.value,
    params_config: buildParamsConfigFromRows(paramRows.value)
  }
  try {
    if (editingId.value) {
      await jenkinsApi.updateEntry(editingId.value, payload)
      showToast(t('adminPages.jenkinsEntries.toast.updated'))
    } else {
      await jenkinsApi.createEntry(payload)
      showToast(t('adminPages.jenkinsEntries.toast.created'))
    }
    goBack()
  } catch (error) {
    showToast(
      t('adminPages.jenkinsEntries.toast.saveFailed', {
        message: error.message
      }),
      'error'
    )
  } finally {
    saving.value = false
  }
}

function goToJobList() {
  router.push({
    path: '/management/jenkins/jobs',
    query: { instance: entryForm.value.instance }
  })
}

function goBack() {
  router.push('/management/jenkins/entries')
}

onMounted(async () => {
  try {
    await loadInstances()
    if (editingId.value) await loadEntry()
    else await applyCreateDraft()
  } catch (error) {
    showToast(
      t('adminPages.jenkinsEntries.toast.loadEditorFailed', {
        message: error.message
      }),
      'error'
    )
  } finally {
    loadingPage.value = false
  }
})

watch(
  paramRows,
  () => {
    entryForm.value.params_config = buildParamsConfigFromRows(paramRows.value)
  },
  { deep: true }
)
</script>
