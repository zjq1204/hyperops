<template>
  <AdminLayout>
    <PageFrame
      variant="soft"
      :eyebrow="t('adminPages.jenkinsInstances.eyebrow')"
      :title="t('adminPages.jenkinsInstances.title')"
      :subtitle="t('adminPages.jenkinsInstances.subtitle')"
    >
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

        <section v-if="loading" class="admin-card">
          <div class="admin-card-body px-6 py-16">
            <div class="flex justify-center">
              <div
                class="h-12 w-12 animate-spin rounded-full border-4 border-slate-200 border-t-sky-500"
              ></div>
            </div>
          </div>
        </section>

        <section
          v-else-if="filteredInstances.length"
          class="grid gap-5 xl:grid-cols-2"
        >
          <article
            v-for="instance in filteredInstances"
            :key="instance.id"
            class="admin-card admin-card-body transition-transform duration-200 hover:-translate-y-0.5"
          >
            <div class="flex items-start justify-between gap-4">
              <div class="flex items-center gap-4">
                <div
                  :class="[
                    'flex h-12 w-12 items-center justify-center rounded-[1.1rem] shadow-sm',
                    instance.is_active
                      ? 'bg-emerald-100 text-emerald-600'
                      : 'bg-slate-100 text-slate-400'
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
                      d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z"
                    />
                  </svg>
                </div>
                <div>
                  <h3 class="text-lg font-semibold text-slate-900">
                    {{ instance.name }}
                  </h3>
                  <p class="mt-1 text-sm text-slate-500">
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

            <div
              class="mt-5 rounded-lg border border-slate-200 bg-slate-50 px-4 py-3"
            >
              <div
                class="flex flex-col gap-4 md:flex-row md:items-end md:justify-between"
              >
                <div class="min-w-0 flex-1">
                  <div
                    class="text-[11px] font-semibold uppercase tracking-[0.24em] text-slate-400"
                  >
                    Endpoint
                  </div>
                  <div class="mt-2 break-all font-mono text-sm text-slate-600">
                    {{ instance.url }}
                  </div>
                </div>

                <div class="admin-jenkins-instance-cache-card">
                  <div class="admin-jenkins-instance-cache-card-top">
                    <span class="admin-jenkins-instance-cache-card-label">{{
                      t('adminPages.jenkinsInstances.cacheBadge')
                    }}</span>
                    <span class="admin-jenkins-instance-cache-card-value">{{
                      t('adminPages.jenkinsInstances.cacheDaysValue', {
                        days: instance.job_catalog_cache_ttl_days || 1
                      })
                    }}</span>
                  </div>
                  <div class="admin-jenkins-instance-cache-card-time">
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

            <div class="admin-jenkins-instance-actions">
              <button
                type="button"
                class="admin-jenkins-instance-action admin-jenkins-instance-action-primary"
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
                class="admin-jenkins-instance-action admin-jenkins-instance-action-secondary"
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
                class="admin-jenkins-instance-action admin-jenkins-instance-action-danger"
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
          :description="t('adminPages.jenkinsInstances.emptySubtitle')"
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
            <div>
              <label class="mb-2 block text-sm font-medium text-slate-700">
                {{ t('adminPages.jenkinsInstances.nameLabel') }}
                <span class="text-rose-500">*</span>
              </label>
              <input
                v-model="instanceForm.name"
                type="text"
                required
                :placeholder="t('adminPages.jenkinsInstances.namePlaceholder')"
                class="input"
              />
            </div>

            <div>
              <label class="mb-2 block text-sm font-medium text-slate-700">
                Jenkins URL
                <span class="text-rose-500">*</span>
              </label>
              <input
                v-model="instanceForm.url"
                type="url"
                required
                placeholder="https://jenkins.example.com"
                class="input"
              />
            </div>

            <div>
              <label class="mb-2 block text-sm font-medium text-slate-700">
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
                class="input"
              />
            </div>

            <div>
              <label class="mb-2 block text-sm font-medium text-slate-700">
                {{ t('adminPages.jenkinsInstances.cacheTtlDaysLabel') }}
                <span class="text-rose-500">*</span>
              </label>
              <input
                v-model.number="instanceForm.job_catalog_cache_ttl_days"
                type="number"
                min="1"
                step="1"
                required
                class="input"
              />
              <p class="mt-2 text-xs text-slate-500">
                {{ t('adminPages.jenkinsInstances.cacheTtlDaysHint') }}
              </p>
            </div>

            <div>
              <label class="mb-2 block text-sm font-medium text-slate-700">
                API Token
                <span class="text-rose-500">*</span>
              </label>
              <input
                v-model="instanceForm.token"
                type="password"
                :required="!editingInstance"
                placeholder="Jenkins API Token"
                class="input"
              />
              <p class="mt-2 text-xs text-slate-500">
                {{ t('adminPages.jenkinsInstances.tokenHint') }}
              </p>
            </div>

            <label class="admin-jenkins-instance-switch-row">
              <div>
                <p class="text-sm font-medium text-slate-700">
                  {{ t('adminPages.jenkinsInstances.activeLabel') }}
                </p>
                <p class="mt-1 text-xs text-slate-500">
                  {{
                    instanceForm.is_active
                      ? t('adminPages.jenkinsInstances.activeStateEnabled')
                      : t('adminPages.jenkinsInstances.activeStateDisabled')
                  }}
                </p>
              </div>

              <span class="admin-jenkins-instance-switch">
                <input
                  id="instance_active"
                  v-model="instanceForm.is_active"
                  type="checkbox"
                  class="sr-only peer"
                />
                <span class="admin-jenkins-instance-switch-track"></span>
                <span class="admin-jenkins-instance-switch-thumb"></span>
              </span>
            </label>

            <div class="admin-modal-card-muted">
              <div class="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p class="admin-modal-section-title">
                    {{ t('adminPages.jenkinsInstances.testConnection') }}
                  </p>
                  <p class="admin-modal-section-copy">
                    {{ t('adminPages.jenkinsInstances.connectionHint') }}
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

      <div
        v-if="toast.show"
        :class="[
          'fixed bottom-4 right-4 rounded-md px-4 py-2 text-white',
          toast.type === 'success' ? 'bg-green-600' : 'bg-red-600'
        ]"
      >
        {{ toast.message }}
      </div>
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
import PageFrame from '@/components/ui/PageFrame.vue'
import { useConfirmDialog } from '@/composables/useConfirmDialog'
import jenkinsApi from '@/api/jenkins'

const { t, locale } = useI18n()
const {
  confirmDialog,
  requestConfirm,
  closeConfirmDialog,
  runConfirmedAction
} = useConfirmDialog()

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

const instanceForm = ref({
  name: '',
  url: '',
  username: '',
  token: '',
  job_catalog_cache_ttl_days: 1,
  is_active: true
})

const toast = ref({ show: false, message: '', type: 'success' })

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

function showToast(message, type = 'success') {
  toast.value = { show: true, message, type }
  setTimeout(() => {
    toast.value.show = false
  }, 3000)
}

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
  try {
    instances.value = await jenkinsApi.listInstances()
  } catch (e) {
    showToast(
      t('adminPages.jenkinsInstances.toast.loadFailed', { message: e.message }),
      'error'
    )
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
}

async function saveInstance() {
  if (!draftConnectionVerified.value) {
    showToast(t('adminPages.jenkinsInstances.toast.testBeforeSave'), 'error')
    return
  }

  try {
    if (editingInstance.value) {
      await jenkinsApi.updateInstance(
        editingInstance.value.id,
        instanceForm.value
      )
      showToast(t('adminPages.jenkinsInstances.toast.updated'))
    } else {
      await jenkinsApi.createInstance(instanceForm.value)
      showToast(t('adminPages.jenkinsInstances.toast.created'))
    }
    closeInstanceModal()
    loadInstances()
  } catch (e) {
    showToast(
      t('adminPages.jenkinsInstances.toast.saveFailed', { message: e.message }),
      'error'
    )
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
    showToast(
      t('adminPages.jenkinsInstances.toast.fillConnectionFields'),
      'error'
    )
    return
  }

  testingDraftConnection.value = true
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
    showToast(t('adminPages.jenkinsInstances.toast.testSucceeded'))
  } catch (e) {
    draftConnectionVerified.value = false
    lastVerifiedSignature.value = ''
    draftConnectionMessage.value = t(
      'adminPages.jenkinsInstances.connectionFailed'
    )
    showToast(
      t('adminPages.jenkinsInstances.toast.testFailed', { message: e.message }),
      'error'
    )
  } finally {
    testingDraftConnection.value = false
  }
}

async function refreshJobCache(instance) {
  refreshingInstanceId.value = instance.id
  try {
    const data = await jenkinsApi.listJobs(instance.id, { forceRefresh: true })
    const count = Array.isArray(data.jobs) ? data.jobs.length : 0
    instance.job_catalog_cache_fetched_at =
      data.fetched_at || instance.job_catalog_cache_fetched_at || null
    if (data.warning) {
      showToast(data.warning, 'error')
      return
    }
    showToast(
      t('adminPages.jenkinsInstances.toast.refreshJobsSucceeded', {
        name: instance.name,
        count
      })
    )
  } catch (e) {
    showToast(
      t('adminPages.jenkinsInstances.toast.refreshJobsFailed', {
        name: instance.name,
        message: e.message
      }),
      'error'
    )
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
        showToast(t('adminPages.jenkinsInstances.toast.deleteSucceeded'))
        loadInstances()
      } catch (e) {
        showToast(
          t('adminPages.jenkinsInstances.toast.deleteFailed', {
            message: e.message
          }),
          'error'
        )
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
