<template>
  <AdminLayout>
    <PageFrame
      variant="soft"
      :title="t('adminPages.objectStorage.resourcesTitle')"
      :subtitle="t('adminPages.objectStorage.resourcesSubtitle')"
    >
      <AdminListSection>
        <template #toolbar>
          <div class="flex w-full flex-wrap items-center justify-between gap-3">
            <select
              v-model="tenantId"
              class="admin-filter-control min-w-[14rem] sm:max-w-xs"
            >
              <option value="">
                {{ t('adminPages.objectStorage.selectTenant') }}
              </option>
              <option
                v-for="tenant in tenants"
                :key="tenant.id"
                :value="String(tenant.id)"
              >
                {{ tenant.name }}
              </option>
            </select>
            <BaseButton
              variant="outline"
              size="sm"
              :loading="loading"
              @click="load"
              >{{ t('common.refresh') }}</BaseButton
            >
          </div>
        </template>
        <AdminPageState :loading="loading" :error="error" :empty="!tenantId">
          <section
            v-if="tenantId"
            class="admin-workbench-panel overflow-hidden"
          >
            <div class="flex overflow-x-auto border-b border-slate-200 px-5">
              <button
                v-for="tab in tabs"
                :key="tab.key"
                type="button"
                class="min-h-12 shrink-0 border-b-2 px-4 text-sm font-medium"
                :class="
                  activeTab === tab.key
                    ? 'border-sky-600 text-sky-700'
                    : 'border-transparent text-slate-500 hover:text-slate-900'
                "
                @click="activeTab = tab.key"
              >
                {{ t(tab.label) }}
                <span class="ml-1 text-xs text-slate-400">{{
                  rows[tab.key].length
                }}</span>
              </button>
            </div>
            <div class="p-5">
              <div v-if="activeTab === 'buckets'" class="overflow-x-auto">
                <table class="admin-table">
                  <thead>
                    <tr>
                      <th class="admin-table-head">
                        {{ t('adminPages.objectStorage.bucket') }}
                      </th>
                      <th class="admin-table-head">
                        {{ t('adminPages.objectStorage.owner') }}
                      </th>
                      <th class="admin-table-head">
                        {{ t('adminPages.objectStorage.environment') }}
                      </th>
                      <th class="admin-table-head">{{ t('common.status') }}</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr
                      v-for="row in rows.buckets"
                      :key="row.id"
                      class="admin-table-row"
                    >
                      <td class="admin-table-cell">
                        <p class="font-semibold text-slate-900">
                          {{ row.name }}
                        </p>
                        <p class="mt-1 text-xs text-slate-500">
                          {{ row.region }} · {{ row.project }}
                        </p>
                      </td>
                      <td class="admin-table-cell">
                        {{ ownerName(row.owner_id) }}
                      </td>
                      <td class="admin-table-cell">{{ row.environment }}</td>
                      <td class="admin-table-cell">
                        <StatusBadge :status="statusBadge(row.state)" />
                      </td>
                    </tr>
                  </tbody>
                </table>
                <EmptyState
                  v-if="!rows.buckets.length"
                  variant="admin"
                  :title="t('adminPages.objectStorage.noRows')"
                />
              </div>
              <div v-else-if="activeTab === 'keys'" class="overflow-x-auto">
                <table class="admin-table">
                  <thead>
                    <tr>
                      <th class="admin-table-head">
                        {{ t('adminPages.objectStorage.credential') }}
                      </th>
                      <th class="admin-table-head">
                        {{ t('adminPages.objectStorage.cloudIdentity') }}
                      </th>
                      <th class="admin-table-head">{{ t('common.status') }}</th>
                      <th class="admin-table-head text-right">
                        {{ t('common.actions') }}
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr
                      v-for="row in rows.keys"
                      :key="row.id"
                      class="admin-table-row"
                    >
                      <td class="admin-table-cell font-mono">
                        ···· {{ row.last_four }}
                        <p class="mt-1 text-xs font-sans text-slate-500">
                          {{ row.fingerprint }}
                        </p>
                      </td>
                      <td class="admin-table-cell">
                        {{ identityName(row.cloud_identity_id) }}
                      </td>
                      <td class="admin-table-cell">
                        <StatusBadge :status="statusBadge(row.local_state)" />
                      </td>
                      <td class="admin-table-cell text-right">
                        <BaseButton
                          size="sm"
                          variant="outline"
                          @click="openReveal(row)"
                          >{{
                            t('adminPages.objectStorage.reveal')
                          }}</BaseButton
                        >
                      </td>
                    </tr>
                  </tbody>
                </table>
                <EmptyState
                  v-if="!rows.keys.length"
                  variant="admin"
                  :title="t('adminPages.objectStorage.noRows')"
                />
              </div>
              <div
                v-else-if="activeTab === 'identities'"
                class="overflow-x-auto"
              >
                <table class="admin-table">
                  <thead>
                    <tr>
                      <th class="admin-table-head">
                        {{ t('adminPages.objectStorage.cloudIdentity') }}
                      </th>
                      <th class="admin-table-head">
                        {{ t('adminPages.objectStorage.owner') }}
                      </th>
                      <th class="admin-table-head">{{ commonStatus }}</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr
                      v-for="row in rows.identities"
                      :key="row.id"
                      class="admin-table-row"
                    >
                      <td class="admin-table-cell">
                        <p class="font-semibold text-slate-900">
                          {{ row.ram_user_name }}
                        </p>
                        <p class="mt-1 text-xs text-slate-500">
                          {{ row.ram_user_id || t('common.emptyValue') }}
                        </p>
                      </td>
                      <td class="admin-table-cell">
                        {{ ownerName(row.membership_id) }}
                      </td>
                      <td class="admin-table-cell">
                        <StatusBadge :status="statusBadge(row.state)" />
                      </td>
                    </tr>
                  </tbody>
                </table>
                <EmptyState
                  v-if="!rows.identities.length"
                  variant="admin"
                  :title="t('adminPages.objectStorage.noRows')"
                />
              </div>
            </div>
          </section>
        </AdminPageState>
      </AdminListSection>
    </PageFrame>
    <BaseModal
      :show="Boolean(revealKey)"
      :title="t('adminPages.objectStorage.revealTitle')"
      size="sm"
      @close="closeReveal"
      ><div v-if="revealResult" class="space-y-4">
        <InlineAlert
          variant="warning"
          :title="t('adminPages.objectStorage.revealSuccess')"
          :message="t('adminPages.objectStorage.revealWarning')"
        /><label class="admin-form-field"
          ><span class="admin-form-label">{{
            t('adminPages.objectStorage.revealAccessKey')
          }}</span
          ><input
            :value="revealResult.access_key_id"
            class="admin-filter-control font-mono"
            readonly /></label
        ><label class="admin-form-field"
          ><span class="admin-form-label">{{
            t('adminPages.objectStorage.revealSecretKey')
          }}</span
          ><input
            :value="revealResult.secret_access_key"
            class="admin-filter-control font-mono"
            readonly
        /></label>
        <div class="flex justify-end">
          <BaseButton variant="outline" @click="closeReveal">{{
            t('common.close')
          }}</BaseButton>
        </div>
      </div>
      <form v-else class="space-y-4" @submit.prevent="reveal">
        <p class="text-sm text-slate-600">
          {{ t('adminPages.objectStorage.revealWarning') }}
        </p>
        <label class="admin-form-field"
          ><span class="admin-form-label">{{
            t('adminPages.objectStorage.reason')
          }}</span
          ><textarea
            v-model.trim="revealReason"
            class="admin-filter-control min-h-24"
            required
          />
        </label>
        <div class="flex justify-end gap-2">
          <BaseButton variant="outline" @click="closeReveal">{{
            t('common.cancel')
          }}</BaseButton
          ><BaseButton variant="danger" type="submit" :loading="revealing">{{
            t('adminPages.objectStorage.reveal')
          }}</BaseButton>
        </div>
      </form></BaseModal
    >
  </AdminLayout>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import AdminLayout from '@/admin/layout/AdminLayout.vue'
import AdminListSection from '@/admin/components/AdminListSection.vue'
import AdminPageState from '@/admin/components/AdminPageState.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseModal from '@/components/ui/BaseModal.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import InlineAlert from '@/components/ui/InlineAlert.vue'
import PageFrame from '@/components/ui/PageFrame.vue'
import StatusBadge from '@/components/ui/StatusBadge.vue'
import objectStorageAdminApi from '@/admin/api/objectStorage'
import { useToast } from '@/composables/useToast'

const { t } = useI18n()
const { showSuccess, showError } = useToast()
const tenants = ref([])
const tenantId = ref('')
const loading = ref(false)
const error = ref('')
const activeTab = ref('buckets')
const revealKey = ref(null)
const revealReason = ref('')
const revealResult = ref(null)
const revealing = ref(false)
const rows = reactive({ members: [], identities: [], buckets: [], keys: [] })
const tabs = [
  { key: 'buckets', label: 'adminPages.objectStorage.bucketsTab' },
  { key: 'identities', label: 'adminPages.objectStorage.identitiesTab' },
  { key: 'keys', label: 'adminPages.objectStorage.credentialsTab' }
]
const commonStatus = computed(() => t('common.status'))
const ownerName = (id) =>
  rows.members.find((row) => row.id === id)?.display_name ||
  t('common.emptyValue')
const identityName = (id) =>
  rows.identities.find((row) => row.id === id)?.ram_user_name ||
  t('common.emptyValue')
const statusBadge = (value) =>
  ({
    active: 'enabled',
    succeeded: 'success',
    delivery_ready: 'success',
    failed: 'failed',
    suspended: 'disabled',
    deleted: 'disabled',
    retired: 'disabled'
  })[value] || 'processing'
async function load() {
  loading.value = true
  error.value = ''
  try {
    if (!tenants.value.length)
      tenants.value = await objectStorageAdminApi.listTenants()
    tenantId.value ||= String(tenants.value[0]?.id || '')
    if (!tenantId.value) return
    const [members, identities, buckets, keys] = await Promise.all([
      objectStorageAdminApi.listMembers(tenantId.value),
      objectStorageAdminApi.listCloudIdentities(tenantId.value),
      objectStorageAdminApi.listBuckets(tenantId.value),
      objectStorageAdminApi.listAccessKeys(tenantId.value)
    ])
    Object.assign(rows, { members, identities, buckets, keys })
  } catch (err) {
    error.value = err?.message || t('adminPages.objectStorage.loadFailed')
  } finally {
    loading.value = false
  }
}
function openReveal(row) {
  revealKey.value = row
  revealResult.value = null
  revealReason.value = ''
}
function closeReveal() {
  revealKey.value = null
  revealResult.value = null
  revealReason.value = ''
}
async function reveal() {
  if (!revealKey.value || !revealReason.value) return
  revealing.value = true
  try {
    revealResult.value = await objectStorageAdminApi.revealAccessKey(
      revealKey.value.id,
      revealReason.value
    )
    showSuccess(t('adminPages.objectStorage.revealSuccess'))
  } catch {
    showError(t('adminPages.objectStorage.revealFailed'))
  } finally {
    revealing.value = false
  }
}
onMounted(load)
</script>
