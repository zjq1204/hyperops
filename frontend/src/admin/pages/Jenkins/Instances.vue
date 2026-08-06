<template>
  <AdminLayout>
    <PageFrame variant="soft" :title="t('adminPages.jenkinsInstances.title')">
      <template #actions>
        <BaseButton @click="openCreateModal">{{
          t('adminPages.jenkinsInstances.add')
        }}</BaseButton>
      </template>

      <AdminListSection>
        <template #filterFields>
          <div class="admin-filter-field min-w-[16rem]">
            <label class="admin-filter-label">
              {{ t('adminPages.jenkinsInstances.searchPlaceholder') }}
            </label>
            <div class="relative">
              <svg
                class="pointer-events-none absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2 text-slate-400"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="2"
                  d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
                />
              </svg>
              <input
                v-model="searchQuery"
                type="text"
                :placeholder="
                  t('adminPages.jenkinsInstances.searchPlaceholder')
                "
                class="admin-filter-control pl-12"
              />
            </div>
          </div>
        </template>

        <section v-if="loading" class="admin-workbench-panel">
          <div class="flex min-h-[12rem] items-center justify-center">
            <div
              class="h-10 w-10 animate-spin rounded-full border-4 border-slate-200 border-t-sky-500"
            ></div>
          </div>
        </section>

        <section v-else-if="pageError" class="admin-workbench-panel">
          <PageErrorState
            :message="pageError.message"
            :request-id="pageError.requestId"
            :retryable="pageError.retryable"
            @retry="loadInstances"
          />
        </section>

        <section
          v-else-if="filteredInstances.length"
          class="admin-instance-grid"
        >
          <article
            v-for="instance in filteredInstances"
            :key="instance.id"
            class="admin-instance-card"
          >
            <div class="admin-instance-card-head">
              <div class="admin-instance-identity">
                <div
                  :class="[
                    'admin-instance-icon',
                    instance.is_active
                      ? 'admin-instance-icon--active'
                      : 'admin-instance-icon--inactive'
                  ]"
                >
                  <svg
                    class="h-6 w-6"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      stroke-linecap="round"
                      stroke-linejoin="round"
                      stroke-width="2"
                      d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"
                    />
                  </svg>
                </div>
                <div class="min-w-0">
                  <h3 class="admin-instance-title">
                    {{ instance.name }}
                  </h3>
                  <p class="admin-instance-subtitle">
                    {{ instance.username }}
                  </p>
                </div>
              </div>
              <span
                :class="
                  instance.is_active
                    ? 'admin-status-badge admin-status-badge--success'
                    : 'admin-status-badge admin-status-badge--muted'
                "
              >
                {{
                  instance.is_active
                    ? t('common.enabled')
                    : t('common.disabled')
                }}
              </span>
            </div>

            <div class="admin-instance-detail-card">
              <div
                class="flex flex-col gap-4 md:flex-row md:items-end md:justify-between"
              >
                <div class="min-w-0 flex-1">
                  <div class="admin-instance-detail-label">
                    {{ t('adminPages.jenkinsInstances.endpointLabel') }}
                  </div>
                  <div class="admin-instance-detail-value">
                    {{ instance.url }}
                  </div>
                </div>

                <div class="admin-instance-cache-card">
                  <div class="admin-instance-cache-card-top">
                    <span class="admin-instance-cache-card-label">{{
                      t('adminPages.jenkinsInstances.cacheBadge')
                    }}</span>
                    <span class="admin-instance-cache-card-value">{{
                      t('adminPages.jenkinsInstances.cacheDaysValue', {
                        days: instance.job_catalog_cache_ttl_days || 1
                      })
                    }}</span>
                  </div>
                  <div class="admin-instance-cache-card-time">
                    <span>{{
                      t('adminPages.jenkinsInstances.cacheLastFetched')
                    }}</span>
                    <time
                      v-if="instance.job_catalog_cache_fetched_at"
                      :datetime="instance.job_catalog_cache_fetched_at"
                    >
                      {{
                        formatCacheFetchedAt(
                          instance.job_catalog_cache_fetched_at
                        )
                      }}
                    </time>
                    <strong v-else>{{
                      t('adminPages.jenkinsInstances.cacheNeverFetched')
                    }}</strong>
                  </div>
                </div>
              </div>
            </div>

            <InlineAlert
              v-if="instanceErrors[instance.id]"
              :variant="
                instanceErrors[instance.id].warning ? 'warning' : 'error'
              "
              :title="t('adminPages.jenkinsInstances.refreshErrorTitle')"
              :message="instanceErrors[instance.id].message"
              :request-id="instanceErrors[instance.id].requestId"
            >
              <template #actions>
                <button type="button" @click="editInstance(instance)">
                  {{ t('adminPages.jenkinsInstances.edit') }}
                </button>
                <button type="button" @click="refreshJobCache(instance)">
                  {{ t('common.tryAgain') }}
                </button>
              </template>
            </InlineAlert>

            <div class="admin-instance-actions">
              <button
                type="button"
                class="admin-instance-action admin-instance-action-primary"
                :disabled="refreshingInstanceId === instance.id"
                @click="refreshJobCache(instance)"
              >
                <svg
                  v-if="refreshingInstanceId === instance.id"
                  class="h-4 w-4 animate-spin"
                  viewBox="0 0 24 24"
                  fill="none"
                >
                  <circle
                    cx="12"
                    cy="12"
                    r="9"
                    stroke="currentColor"
                    stroke-width="3"
                    class="opacity-25"
                  />
                  <path
                    d="M21 12a9 9 0 0 0-9-9"
                    stroke="currentColor"
                    stroke-width="3"
                    stroke-linecap="round"
                  />
                </svg>
                <svg
                  v-else
                  class="h-4 w-4"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                >
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    stroke-width="1.9"
                    d="M4 4v6h6M20 20v-6h-6"
                  />
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    stroke-width="1.9"
                    d="M20 9a8 8 0 0 0-13.66-3.66L4 10M4 15a8 8 0 0 0 13.66 3.66L20 14"
                  />
                </svg>
                <span>{{ t('adminPages.jenkinsInstances.refreshJobs') }}</span>
              </button>

              <button
                type="button"
                class="admin-instance-action admin-instance-action-secondary"
                @click="editInstance(instance)"
              >
                <svg
                  class="h-4 w-4"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                >
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    stroke-width="1.9"
                    d="M4 20h4l10-10a2.121 2.121 0 0 0-4-4L4 16v4z"
                  />
                </svg>
                <span>{{ t('adminPages.jenkinsInstances.edit') }}</span>
              </button>

              <button
                type="button"
                class="admin-instance-action admin-instance-action-danger"
                @click="deleteInstance(instance)"
              >
                <svg
                  class="h-4 w-4"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                >
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    stroke-width="1.9"
                    d="M6 7h12M9 7V5h6v2m-7 4v6m4-6v6m4-6v6M8 7l1 12h6l1-12"
                  />
                </svg>
                <span>{{ t('common.delete') }}</span>
              </button>
            </div>
          </article>
        </section>

        <EmptyState
          v-else
          variant="admin"
          :title="t('adminPages.jenkinsInstances.emptyTitle')"
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
            <BaseButton @click="openCreateModal">{{
              t('adminPages.jenkinsInstances.add')
            }}</BaseButton>
          </template>
        </EmptyState>
      </AdminListSection>

      <BaseModal
        :show="showInstanceModal"
        :title="
          editingInstance
            ? t('adminPages.jenkinsInstances.editTitle')
            : t('adminPages.jenkinsInstances.createTitle')
        "
        @close="closeInstanceModal"
      >
        <form @submit.prevent="saveInstance">
          <div class="admin-modal-stack">
            <InlineAlert
              v-if="modalError"
              :title="t('common.error')"
              :message="modalError.message"
              :request-id="modalError.requestId"
            />

            <div>
              <label class="admin-modal-field-label">
                {{ t('adminPages.jenkinsInstances.nameLabel') }}
                <span class="text-rose-500">*</span>
              </label>
              <input
                v-model="instanceForm.name"
                type="text"
                required
                :placeholder="t('adminPages.jenkinsInstances.namePlaceholder')"
                class="admin-modal-control"
              />
            </div>

            <div>
              <label class="admin-modal-field-label">
                {{ t('adminPages.jenkinsInstances.urlLabel') }}
                <span class="text-rose-500">*</span>
              </label>
              <input
                v-model="instanceForm.url"
                type="url"
                required
                :placeholder="t('adminPages.jenkinsInstances.urlPlaceholder')"
                class="admin-modal-control"
              />
            </div>

            <div>
              <label class="admin-modal-field-label">
                {{ t('adminPages.jenkinsInstances.usernameLabel') }}
                <span class="text-rose-500">*</span>
              </label>
              <input
                v-model="instanceForm.username"
                type="text"
                required
                :placeholder="
                  t('adminPages.jenkinsInstances.usernamePlaceholder')
                "
                class="admin-modal-control"
              />
            </div>

            <div>
              <label class="admin-modal-field-label">
                {{ t('adminPages.jenkinsInstances.cacheTtlDaysLabel') }}
                <span class="text-rose-500">*</span>
              </label>
              <input
                v-model.number="instanceForm.job_catalog_cache_ttl_days"
                type="number"
                min="1"
                step="1"
                required
                class="admin-modal-control"
              />
            </div>

            <div>
              <label class="admin-modal-field-label">
                {{ t('adminPages.jenkinsInstances.tokenLabel') }}
                <span class="text-rose-500">*</span>
              </label>
              <input
                v-model="instanceForm.token"
                type="password"
                :required="!editingInstance"
                :placeholder="t('adminPages.jenkinsInstances.tokenPlaceholder')"
                class="admin-modal-control"
              />
            </div>

            <label class="admin-modal-toggle">
              <input
                id="instance_active"
                v-model="instanceForm.is_active"
                type="checkbox"
                class="admin-modal-checkbox"
              />
              <div>
                <p class="text-sm font-medium text-slate-700">
                  {{ t('adminPages.jenkinsInstances.activeLabel') }}
                </p>
              </div>
            </label>

            <div class="admin-modal-card-muted">
              <div class="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p class="admin-modal-section-title">
                    {{ t('adminPages.jenkinsInstances.testConnection') }}
                  </p>
                </div>
                <BaseButton
                  variant="secondary"
                  :loading="testingDraftConnection"
                  :disabled="testingDraftConnection || !canTestDraftConnection"
                  @click="validateDraftConnection"
                >
                  {{ t('adminPages.jenkinsInstances.testConnection') }}
                </BaseButton>
              </div>

              <p
                v-if="draftConnectionMessage"
                :class="[
                  'mt-3 text-sm',
                  draftConnectionVerified
                    ? 'text-emerald-600'
                    : 'text-slate-500'
                ]"
              >
                {{ draftConnectionMessage }}
              </p>
            </div>
          </div>
        </form>
        <template #footer>
          <div class="flex w-full justify-end gap-3">
            <BaseButton variant="secondary" @click="closeInstanceModal">{{
              t('common.cancel')
            }}</BaseButton>
            <BaseButton
              :disabled="!draftConnectionVerified"
              @click="saveInstance"
            >
              {{
                editingInstance
                  ? t('common.save')
                  : t('adminPages.jenkinsInstances.add')
              }}
            </BaseButton>
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
import { ref, computed, onMounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import AdminListSection from '@/admin/components/AdminListSection.vue'
import AdminLayout from '@/admin/layout/AdminLayout.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseModal from '@/components/ui/BaseModal.vue'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import InlineAlert from '@/components/ui/InlineAlert.vue'
import PageFrame from '@/components/ui/PageFrame.vue'
import PageErrorState from '@/components/ui/PageErrorState.vue'
import { useConfirmDialog } from '@/composables/useConfirmDialog'
import { useToast } from '@/composables/useToast'
import jenkinsApi from '@/api/jenkins'
import { normalizeApiError } from '@/utils/apiError'

const { t, locale } = useI18n()
const {
  confirmDialog,
  requestConfirm,
  closeConfirmDialog,
  runConfirmedAction
} = useConfirmDialog()
const { showSuccess, showError } = useToast()

const instances = ref([])
const showInstanceModal = ref(false)
const editingInstance = ref(null)
const loading = ref(false)
const searchQuery = ref('')
const refreshingInstanceId = ref(null)
const testingDraftConnection = ref(false)
const draftConnectionVerified = ref(false)
const draftConnectionMessage = ref('')
const lastVerifiedSignature = ref('')
const pageError = ref(null)
const modalError = ref(null)
const instanceErrors = ref({})

const instanceForm = ref({
  name: '',
  url: '',
  username: '',
  token: '',
  job_catalog_cache_ttl_days: 1,
  is_active: true
})

const canTestDraftConnection = computed(() => {
  if (!instanceForm.value.url || !instanceForm.value.username) return false
  if (editingInstance.value) return true
  return Boolean(instanceForm.value.token)
})

const filteredInstances = computed(() => {
  if (!searchQuery.value) return instances.value
  const query = searchQuery.value.toLowerCase()
  return instances.value.filter(
    (inst) =>
      inst.name.toLowerCase().includes(query) ||
      inst.url.toLowerCase().includes(query)
  )
})

function formatCacheFetchedAt(dateStr) {
  if (!dateStr) return t('adminPages.jenkinsInstances.cacheNeverFetched')
  const date = new Date(dateStr)
  if (Number.isNaN(date.getTime())) return dateStr
  return date.toLocaleString(locale.value || 'zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

async function loadInstances() {
  loading.value = true
  pageError.value = null
  try {
    instances.value = await jenkinsApi.listInstances()
  } catch (e) {
    pageError.value = normalizeApiError(e, {
      fallbackMessage: t('adminPages.jenkinsInstances.toast.loadFailed', {
        message: ''
      })
    })
  } finally {
    loading.value = false
  }
}

function editInstance(instance) {
  editingInstance.value = instance
  instanceForm.value = { ...instance, token: '' }
  draftConnectionVerified.value = false
  draftConnectionMessage.value = ''
  lastVerifiedSignature.value = ''
  modalError.value = null
  showInstanceModal.value = true
}

function openCreateModal() {
  editingInstance.value = null
  instanceForm.value = {
    name: '',
    url: '',
    username: '',
    token: '',
    job_catalog_cache_ttl_days: 1,
    is_active: true
  }
  draftConnectionVerified.value = false
  draftConnectionMessage.value = ''
  lastVerifiedSignature.value = ''
  modalError.value = null
  showInstanceModal.value = true
}

function closeInstanceModal() {
  showInstanceModal.value = false
  editingInstance.value = null
  instanceForm.value = {
    name: '',
    url: '',
    username: '',
    token: '',
    job_catalog_cache_ttl_days: 1,
    is_active: true
  }
  draftConnectionVerified.value = false
  draftConnectionMessage.value = ''
  lastVerifiedSignature.value = ''
  modalError.value = null
}

async function saveInstance() {
  if (!draftConnectionVerified.value) {
    modalError.value = normalizeApiError(
      new Error(t('adminPages.jenkinsInstances.toast.testBeforeSave')),
      { retryable: false }
    )
    return
  }

  modalError.value = null
  try {
    if (editingInstance.value) {
      await jenkinsApi.updateInstance(
        editingInstance.value.id,
        instanceForm.value
      )
      showSuccess(t('adminPages.jenkinsInstances.toast.updated'))
    } else {
      await jenkinsApi.createInstance(instanceForm.value)
      showSuccess(t('adminPages.jenkinsInstances.toast.created'))
    }
    closeInstanceModal()
    loadInstances()
  } catch (e) {
    modalError.value = normalizeApiError(e, {
      fallbackMessage: t('adminPages.jenkinsInstances.toast.saveFailed', {
        message: ''
      })
    })
  }
}

function getDraftSignature() {
  return JSON.stringify({
    instanceId: editingInstance.value?.id || null,
    url: instanceForm.value.url,
    username: instanceForm.value.username,
    token: instanceForm.value.token
  })
}

async function validateDraftConnection() {
  if (!canTestDraftConnection.value) {
    modalError.value = normalizeApiError(
      new Error(t('adminPages.jenkinsInstances.toast.fillConnectionFields')),
      { retryable: false }
    )
    return
  }

  testingDraftConnection.value = true
  modalError.value = null
  try {
    await jenkinsApi.validateConnection({
      url: instanceForm.value.url,
      username: instanceForm.value.username,
      token: instanceForm.value.token,
      instance_id: editingInstance.value?.id
    })
    draftConnectionVerified.value = true
    lastVerifiedSignature.value = getDraftSignature()
    draftConnectionMessage.value = t(
      'adminPages.jenkinsInstances.connectionVerified'
    )
    showSuccess(t('adminPages.jenkinsInstances.toast.testSucceeded'))
  } catch (e) {
    draftConnectionVerified.value = false
    lastVerifiedSignature.value = ''
    draftConnectionMessage.value = t(
      'adminPages.jenkinsInstances.connectionFailed'
    )
    modalError.value = normalizeApiError(e, {
      fallbackMessage: t('adminPages.jenkinsInstances.toast.testFailed', {
        message: ''
      })
    })
  } finally {
    testingDraftConnection.value = false
  }
}

async function refreshJobCache(instance) {
  refreshingInstanceId.value = instance.id
  const nextErrors = { ...instanceErrors.value }
  delete nextErrors[instance.id]
  instanceErrors.value = nextErrors
  try {
    const data = await jenkinsApi.listJobs(instance.id, { forceRefresh: true })
    const count = Array.isArray(data.jobs) ? data.jobs.length : 0
    instance.job_catalog_cache_fetched_at =
      data.fetched_at || instance.job_catalog_cache_fetched_at || null
    if (data.warning) {
      instanceErrors.value = {
        ...instanceErrors.value,
        [instance.id]: {
          message: data.warning,
          requestId: data.request_id || '',
          code: data.warning_code || 'JENKINS_REQUEST_FAILED',
          retryable: true,
          warning: true
        }
      }
      return
    }
    showSuccess(
      t('adminPages.jenkinsInstances.toast.refreshJobsSucceeded', {
        name: instance.name,
        count
      })
    )
  } catch (e) {
    instanceErrors.value = {
      ...instanceErrors.value,
      [instance.id]: normalizeApiError(e, {
        fallbackMessage: t(
          'adminPages.jenkinsInstances.toast.refreshJobsFailed',
          { name: instance.name, message: '' }
        )
      })
    }
  } finally {
    refreshingInstanceId.value = null
  }
}

async function deleteInstance(instance) {
  requestConfirm({
    title: t('common.delete'),
    message: t('adminPages.jenkinsInstances.deleteConfirm', {
      name: instance.name
    }),
    confirmText: t('common.delete'),
    onConfirm: async () => {
      try {
        await jenkinsApi.deleteInstance(instance.id)
        showSuccess(t('adminPages.jenkinsInstances.toast.deleteSucceeded'))
        loadInstances()
      } catch (e) {
        showError(e, 6000, {
          fallbackMessage: t('adminPages.jenkinsInstances.toast.deleteFailed', {
            message: ''
          })
        })
      }
    }
  })
}

onMounted(() => {
  loadInstances()
})

watch(
  instanceForm,
  () => {
    const currentSignature = getDraftSignature()
    if (currentSignature !== lastVerifiedSignature.value) {
      draftConnectionVerified.value = false
      modalError.value = null
      draftConnectionMessage.value =
        currentSignature ===
        JSON.stringify({
          instanceId: editingInstance.value?.id || null,
          url: '',
          username: '',
          token: ''
        })
          ? ''
          : t('adminPages.jenkinsInstances.connectionPending')
    }
  },
  { deep: true }
)
</script>
