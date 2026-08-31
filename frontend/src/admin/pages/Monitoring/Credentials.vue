<template>
  <AdminLayout>
    <PageFrame variant="soft" :title="t('monitoringCredentials.title')">
      <AdminListSection>
        <template #toolbar>
          <div class="flex w-full flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div class="flex min-w-0 flex-1 flex-col gap-2 sm:flex-row">
              <label class="min-w-0 flex-1 sm:max-w-xs">
                <span class="sr-only">{{ t('monitoringCredentials.search') }}</span>
                <input v-model.trim="filters.query" class="admin-filter-control w-full" :placeholder="t('monitoringCredentials.searchPlaceholder')" />
              </label>
              <label class="sm:w-40">
                <span class="sr-only">{{ t('monitoringCredentials.type') }}</span>
                <select v-model="filters.type" class="admin-filter-control w-full">
                  <option value="">{{ t('common.all') }}</option>
                  <option value="private_key">{{ t('monitoringCredentials.types.private_key') }}</option>
                  <option value="password">{{ t('monitoringCredentials.types.password') }}</option>
                </select>
              </label>
              <label class="sm:w-40">
                <span class="sr-only">{{ t('monitoringCredentials.lifecycle') }}</span>
                <select v-model="filters.status" class="admin-filter-control w-full">
                  <option value="">{{ t('common.all') }}</option>
                  <option value="active">{{ t('monitoringCredentials.lifecycleStates.active') }}</option>
                  <option value="archived">{{ t('monitoringCredentials.lifecycleStates.archived') }}</option>
                  <option value="needs_reupload">{{ t('monitoringCredentials.lifecycleStates.needs_reupload') }}</option>
                </select>
              </label>
            </div>
            <div class="flex items-center justify-end gap-2">
              <BaseButton variant="outline" size="sm" :loading="loading" @click="loadCredentials">
                {{ t('common.refresh') }}
              </BaseButton>
              <BaseButton v-if="canManage" variant="primary" size="sm" @click="openCreate">{{ t('monitoringCredentials.addCredential') }}</BaseButton>
            </div>
          </div>
        </template>

        <AdminPageState :loading="loading && !credentials.length" :error="credentials.length ? '' : error" :empty="!loading && !error && !filteredCredentials.length" :empty-title="t('monitoringCredentials.empty')">
          <div v-if="error && credentials.length" class="mb-3 flex items-center justify-between gap-3 border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800" role="alert"><span>{{ error }}</span><BaseButton variant="ghost" size="sm" @click="loadCredentials">{{ t('monitoringCredentials.retry') }}</BaseButton></div>

          <div class="hidden overflow-x-auto md:block">
            <table class="min-w-full table-fixed text-left text-sm">
              <thead class="border-y border-slate-200 bg-slate-50 text-xs font-semibold text-slate-500">
                <tr>
                  <th class="w-2/5 px-4 py-3">{{ t('common.name') }}</th>
                  <th class="w-24 px-4 py-3">{{ t('monitoringCredentials.activeVersion') }}</th>
                  <th class="w-28 px-4 py-3">{{ t('monitoringCredentials.lifecycle') }}</th>
                  <th class="w-28 px-4 py-3">{{ t('monitoringCredentials.hostUsage') }}</th>
                  <th class="w-40 px-4 py-3">{{ t('monitoringCredentials.updatedTime') }}</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-slate-100">
                <tr v-for="item in filteredCredentials" :key="item.id" tabindex="0" class="cursor-pointer hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-inset focus:ring-sky-500" @click="openDetail(item)" @keydown.enter.prevent="openDetail(item)" @keydown.space.prevent="openDetail(item)">
                  <td class="truncate px-4 py-3.5 font-semibold text-slate-900">{{ item.name }}</td>
                  <td class="px-4 py-3.5 text-slate-600">{{ versionText(item) }}</td>
                  <td class="px-4 py-3.5"><span :class="badgeClass(credentialLifecycleKey(item))">{{ lifecycleLabel(item) }}</span></td>
                  <td class="px-4 py-3.5 text-slate-600">{{ credentialHostCount(item) }}</td>
                  <td class="px-4 py-3.5 text-xs text-slate-500">{{ formatDate(credentialUpdatedAt(item)) }}</td>
                </tr>
              </tbody>
            </table>
          </div>

          <div data-testid="credential-mobile-list" class="divide-y divide-slate-200 border-y border-slate-200 md:hidden">
            <button v-for="item in filteredCredentials" :key="item.id" type="button" class="block w-full px-1 py-4 text-left focus:outline-none focus:ring-2 focus:ring-inset focus:ring-sky-500" @click="openDetail(item)">
              <span class="flex items-start justify-between gap-3"><span class="min-w-0 flex-1 truncate text-sm font-semibold text-slate-900">{{ item.name }}</span><span :class="badgeClass(credentialLifecycleKey(item))">{{ lifecycleLabel(item) }}</span></span>
              <span class="mt-2 grid grid-cols-2 gap-x-4 gap-y-1 text-xs text-slate-500"><span>{{ versionText(item) }}</span><span class="text-right">{{ t('monitoringCredentials.hostUsageCount', { count: credentialHostCount(item) }) }}</span><span class="col-span-2">{{ formatDate(credentialUpdatedAt(item)) }}</span></span>
            </button>
          </div>
        </AdminPageState>
      </AdminListSection>
    </PageFrame>

    <CredentialUploadModal :show="uploadOpen" :mode="uploadMode" :credential="selectedCredential" :hosts="hosts" @close="uploadOpen = false" @completed="handleUploadCompleted" />
    <CredentialDetailDrawer :show="drawerOpen" :credential="selectedCredential" :loading="detailLoading" :error="detailError" :user="currentUser" :conflict-hosts="conflictHosts" @close="closeDetail" @rotate="openRotate" @archive="archiveCredential" @delete="deleteCredential" />
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
import { computed, onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import AdminListSection from '@/admin/components/AdminListSection.vue'
import AdminPageState from '@/admin/components/AdminPageState.vue'
import AdminLayout from '@/admin/layout/AdminLayout.vue'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import PageFrame from '@/components/ui/PageFrame.vue'
import { monitoringStackApi } from '@/admin/api/monitoringStack'
import { useConfirmDialog } from '@/composables/useConfirmDialog'
import { useUserStore } from '@/store/user'
import { formatDate as formatDateValue } from '@/utils/formatting'
import CredentialDetailDrawer from './credentials/CredentialDetailDrawer.vue'
import CredentialUploadModal from './credentials/CredentialUploadModal.vue'
import {
  collectionFromPayload,
  credentialActiveVersionNumber,
  credentialHostCount,
  credentialLifecycleKey,
  credentialTypeKey,
  credentialUpdatedAt,
  hasCredentialPermission
} from './credentials/credentialState'

const { t } = useI18n()
const userStore = useUserStore()
const {
  confirmDialog,
  requestConfirm,
  closeConfirmDialog,
  runConfirmedAction
} = useConfirmDialog()
const currentUser = computed(() => userStore.userInfo || userStore.user)
const credentials = ref([])
const hosts = ref([])
const loading = ref(false)
const error = ref('')
const filters = reactive({ query: '', type: '', status: '' })
const drawerOpen = ref(false)
const detailLoading = ref(false)
const detailError = ref('')
const selectedCredential = ref(null)
const conflictHosts = ref([])
const uploadOpen = ref(false)
const uploadMode = ref('create')
const canManage = computed(() => hasCredentialPermission(currentUser.value, 'manage'))
const filteredCredentials = computed(() => {
  const query = filters.query.toLocaleLowerCase()
  return credentials.value.filter((item) => {
    const haystack = `${item.name || ''}`.toLocaleLowerCase()
    return (!query || haystack.includes(query)) && (!filters.type || credentialTypeKey(item) === filters.type) && (!filters.status || credentialLifecycleKey(item) === filters.status)
  })
})

function formatDate(value) { return value ? formatDateValue(value) : t('common.emptyValue') }
function versionText(item) { const value = credentialActiveVersionNumber(item); return value ? `v${value}` : t('common.emptyValue') }
function lifecycleLabel(item) { return t(`monitoringCredentials.lifecycleStates.${credentialLifecycleKey(item)}`) }
function badgeClass(status) { const tones = { active: 'bg-emerald-50 text-emerald-700', valid: 'bg-emerald-50 text-emerald-700', archived: 'bg-slate-100 text-slate-600', invalid: 'bg-rose-50 text-rose-700', unavailable: 'bg-rose-50 text-rose-700', needs_reupload: 'bg-amber-50 text-amber-700', unverified: 'bg-amber-50 text-amber-700', draft: 'bg-sky-50 text-sky-700' }; return `inline-flex rounded-md px-2 py-1 text-xs font-semibold ${tones[status] || 'bg-slate-100 text-slate-600'}` }

async function loadCredentials() {
  loading.value = true; error.value = ''
  try { credentials.value = collectionFromPayload(await monitoringStackApi.getCredentials()) }
  catch (loadError) { error.value = loadError?.response?.data?.detail || loadError?.message || t('monitoringCredentials.loadFailed') }
  finally { loading.value = false }
}
async function loadHosts() { try { hosts.value = collectionFromPayload(await monitoringStackApi.getHosts()) } catch { hosts.value = [] } }
async function openDetail(item) {
  selectedCredential.value = item; drawerOpen.value = true; detailLoading.value = true; detailError.value = ''; conflictHosts.value = []
  try { selectedCredential.value = await monitoringStackApi.getCredential(item.id) }
  catch (detailLoadError) { detailError.value = detailLoadError?.response?.data?.detail || detailLoadError?.message || t('monitoringCredentials.loadDetailFailed') }
  finally { detailLoading.value = false }
}
function closeDetail() { drawerOpen.value = false; detailError.value = ''; conflictHosts.value = [] }
function openCreate() { selectedCredential.value = null; uploadMode.value = 'create'; uploadOpen.value = true }
function openRotate(item) { selectedCredential.value = item; uploadMode.value = 'rotate'; uploadOpen.value = true }
async function handleUploadCompleted(id) { uploadOpen.value = false; await loadCredentials(); if (id) { const item = credentials.value.find((entry) => String(entry.id) === String(id)); if (item) await openDetail(item) } }
function archiveCredential(item) {
  requestConfirm({
    title: t('monitoringCredentials.archiveConfirmTitle'),
    message: t('monitoringCredentials.archiveConfirmMessage', {
      name: item.name
    }),
    confirmText: t('monitoringCredentials.archive'),
    variant: 'warning',
    onConfirm: async () => {
      try {
        await monitoringStackApi.archiveCredential(item.id)
        closeDetail()
        await loadCredentials()
      } catch (actionError) {
        handleConflict(actionError)
      }
    }
  })
}
function deleteCredential(item) {
  requestConfirm({
    title: t('monitoringCredentials.deleteConfirmTitle'),
    message: t('monitoringCredentials.deleteConfirmMessage', {
      name: item.name
    }),
    confirmText: t('common.delete'),
    variant: 'danger',
    onConfirm: async () => {
      try {
        await monitoringStackApi.deleteCredential(item.id)
        closeDetail()
        await loadCredentials()
      } catch (actionError) {
        handleConflict(actionError)
      }
    }
  })
}
function handleConflict(actionError) { const payload = actionError?.response?.data || {}; if (actionError?.response?.status === 409) { conflictHosts.value = payload.hosts || payload.linked_hosts || []; return } detailError.value = payload.detail || actionError?.message || t('monitoringCredentials.actionFailed') }

onMounted(() => { loadCredentials(); loadHosts() })
</script>
