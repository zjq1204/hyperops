<template>
  <AdminLayout>
    <PageFrame
      variant="soft"
      :title="t('adminPages.objectStorage.settingsTitle')"
      :subtitle="t('adminPages.objectStorage.settingsSubtitle')"
    >
      <AdminListSection>
        <template #toolbarEnd>
          <BaseButton variant="outline" size="sm" :loading="loading" @click="load">
            {{ t('common.refresh') }}
          </BaseButton>
        </template>

        <AdminPageState :loading="loading" :error="loadError">
          <form class="space-y-5" @submit.prevent="saveSettings">
            <section class="admin-workbench-panel overflow-hidden">
              <div class="border-b border-slate-200 px-5 py-4">
                <h2 class="text-sm font-semibold text-slate-950">
                  {{ t('adminPages.objectStorage.connectionSection') }}
                </h2>
                <p class="mt-1 text-xs leading-5 text-slate-500">
                  {{ t('adminPages.objectStorage.connectionHint') }}
                </p>
              </div>
              <div class="grid gap-5 p-5 sm:grid-cols-2">
                <label class="admin-form-field">
                  <span class="admin-form-label">{{ t('adminPages.objectStorage.provider') }}</span>
                  <input class="admin-filter-control" :value="t('adminPages.objectStorage.providerName')" readonly />
                </label>
                <label class="admin-form-field">
                  <span class="admin-form-label">{{ t('adminPages.objectStorage.enabledPool') }}</span>
                  <div class="admin-filter-control flex items-center" aria-live="polite">
                    {{ currentPool ? `${currentPool.cloud_account_id} · ${currentPool.region}` : t('adminPages.objectStorage.noPool') }}
                  </div>
                </label>
              </div>
            </section>

            <section class="admin-workbench-panel overflow-hidden">
              <div class="border-b border-slate-200 px-5 py-4">
                <h2 class="text-sm font-semibold text-slate-950">
                  {{ t('adminPages.objectStorage.policySection') }}
                </h2>
                <p class="mt-1 text-xs leading-5 text-slate-500">
                  {{ t('adminPages.objectStorage.policyHint') }}
                </p>
              </div>
              <div class="grid gap-5 p-5 sm:grid-cols-2">
                <label class="admin-form-field sm:col-span-2">
                  <span class="admin-form-label">{{ t('adminPages.objectStorage.namingTemplate') }}</span>
                  <input v-model.trim="form.naming_template" class="admin-filter-control font-mono" required />
                  <span class="admin-form-help">{{ t('adminPages.objectStorage.namingTemplateHint') }}</span>
                </label>
                <label class="admin-form-field">
                  <span class="admin-form-label">{{ t('adminPages.objectStorage.bucketQuota') }}</span>
                  <input v-model.number="form.default_bucket_quota" class="admin-filter-control" type="number" min="1" max="100" required />
                </label>
                <label class="admin-form-field">
                  <span class="admin-form-label">{{ t('adminPages.objectStorage.deliveryLifetime') }}</span>
                  <input v-model.number="form.delivery_lifetime_seconds" class="admin-filter-control" type="number" min="300" required />
                </label>
                <label class="admin-form-field">
                  <span class="admin-form-label">{{ t('adminPages.objectStorage.auditRetention') }}</span>
                  <input v-model.number="form.audit_retention_days" class="admin-filter-control" type="number" min="1" required />
                </label>
              </div>
            </section>

            <section class="admin-workbench-panel overflow-hidden">
              <div class="border-b border-slate-200 px-5 py-4">
                <h2 class="text-sm font-semibold text-slate-950">
                  {{ t('adminPages.objectStorage.defaultSection') }}
                </h2>
              </div>
              <div class="grid gap-4 p-5 sm:grid-cols-2 lg:grid-cols-4">
                <label v-for="item in defaults" :key="item.key" class="flex items-start gap-3 text-sm text-slate-700">
                  <input v-model="form[item.key]" type="checkbox" class="mt-0.5" :disabled="item.disabled" />
                  <span>{{ t(item.label) }}</span>
                </label>
                <p class="sm:col-span-2 lg:col-span-4 text-xs text-slate-500">
                  {{ t('adminPages.objectStorage.privateAclHint') }}
                </p>
              </div>
            </section>

            <section class="admin-workbench-panel overflow-hidden">
              <div class="flex flex-wrap items-start justify-between gap-3 border-b border-slate-200 px-5 py-4">
                <div>
                  <h2 class="text-sm font-semibold text-slate-950">{{ t('adminPages.objectStorage.operationSection') }}</h2>
                  <p class="mt-1 text-xs leading-5 text-slate-500">{{ t('adminPages.objectStorage.operationHint') }}</p>
                </div>
                <StatusBadge :status="settings?.pause_new_applications ? 'disabled' : 'success'" />
              </div>
              <div class="grid gap-4 p-5 sm:grid-cols-2">
                <label class="flex items-start gap-3 text-sm text-slate-700">
                  <input v-model="form.pause_new_applications" type="checkbox" class="mt-0.5" />
                  <span>{{ t('adminPages.objectStorage.pauseApplications') }}</span>
                </label>
                <label class="flex items-start gap-3 text-sm text-slate-700">
                  <input v-model="form.pause_key_operations" type="checkbox" class="mt-0.5" />
                  <span>{{ t('adminPages.objectStorage.pauseKeys') }}</span>
                </label>
              </div>
            </section>

            <div class="flex justify-end border-t border-slate-200 pt-4">
              <BaseButton type="submit" :loading="saving">{{ t('common.save') }}</BaseButton>
            </div>
          </form>

          <section class="mt-6 admin-workbench-panel overflow-hidden">
            <div class="flex flex-wrap items-start justify-between gap-3 border-b border-slate-200 px-5 py-4">
              <div>
                <h2 class="text-sm font-semibold text-slate-950">{{ t('adminPages.objectStorage.poolsTitle') }}</h2>
                <p class="mt-1 text-xs leading-5 text-slate-500">{{ t('adminPages.objectStorage.poolsHint') }}</p>
              </div>
              <BaseButton size="sm" variant="outline" @click="showPoolForm = !showPoolForm">
                {{ showPoolForm ? t('common.cancel') : t('adminPages.objectStorage.addPool') }}
              </BaseButton>
            </div>
            <div v-if="showPoolForm" class="grid gap-4 border-b border-slate-200 bg-slate-50/60 p-5 sm:grid-cols-2">
              <label class="admin-form-field"><span class="admin-form-label">{{ t('adminPages.objectStorage.accountId') }}</span><input v-model.trim="poolForm.cloud_account_id" class="admin-filter-control" required /></label>
              <label class="admin-form-field"><span class="admin-form-label">{{ t('adminPages.objectStorage.region') }}</span><input v-model.trim="poolForm.region" class="admin-filter-control" required /></label>
              <label class="admin-form-field"><span class="admin-form-label">{{ t('adminPages.objectStorage.managementAccessKey') }}</span><input v-model="poolForm.management_access_key" class="admin-filter-control font-mono" autocomplete="off" required /></label>
              <label class="admin-form-field"><span class="admin-form-label">{{ t('adminPages.objectStorage.managementSecretKey') }}</span><input v-model="poolForm.management_secret_key" class="admin-filter-control font-mono" type="password" autocomplete="new-password" required /></label>
              <div class="flex items-center justify-end gap-2 sm:col-span-2"><BaseButton type="button" variant="outline" @click="showPoolForm = false">{{ t('common.cancel') }}</BaseButton><BaseButton type="button" :loading="poolSaving" @click="createPool">{{ t('adminPages.objectStorage.savePool') }}</BaseButton></div>
            </div>
            <div v-if="pools.length" class="divide-y divide-slate-200">
              <div v-for="pool in pools" :key="pool.id" class="grid gap-3 px-5 py-4 sm:grid-cols-[minmax(0,1fr)_minmax(10rem,0.7fr)_auto] sm:items-center">
                <div><p class="font-medium text-slate-900">{{ pool.cloud_account_id }}</p><p class="mt-1 text-xs text-slate-500">{{ pool.provider }} · {{ pool.region }} · {{ t('adminPages.objectStorage.keyEnding', { value: pool.access_key_last_four }) }}</p></div>
                <StatusBadge :status="statusBadge(pool.validation_status, pool.enabled)" />
                <BaseButton size="sm" variant="outline" :loading="validatingPool === pool.id" @click="validatePool(pool)">{{ t('adminPages.objectStorage.validate') }}</BaseButton>
              </div>
            </div>
            <EmptyState v-else variant="admin" :title="t('adminPages.objectStorage.noPool')" :description="t('adminPages.objectStorage.noPoolHint')" />
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
import BaseButton from '@/components/ui/BaseButton.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import PageFrame from '@/components/ui/PageFrame.vue'
import StatusBadge from '@/components/ui/StatusBadge.vue'
import { extractErrorMessage } from '@/utils/api'
import { useToast } from '@/composables/useToast'
import objectStorageAdminApi from '@/admin/api/objectStorage'

const { t } = useI18n()
const { showSuccess, showError } = useToast()
const loading = ref(true)
const saving = ref(false)
const poolSaving = ref(false)
const validatingPool = ref(null)
const loadError = ref('')
const settings = ref(null)
const pools = ref([])
const showPoolForm = ref(false)
const form = reactive({
  naming_template: '', default_bucket_quota: 5, delivery_lifetime_seconds: 86400,
  audit_retention_days: 30, default_storage_class: 'standard', default_encryption: true,
  default_versioning: false, default_lifecycle: false, pause_new_applications: false,
  pause_key_operations: false, default_bucket_acl: 'private'
})
const poolForm = reactive({ cloud_account_id: '', region: '', management_access_key: '', management_secret_key: '' })
const defaults = [
  { key: 'default_encryption', label: 'adminPages.objectStorage.encryption', disabled: false },
  { key: 'default_versioning', label: 'adminPages.objectStorage.versioning', disabled: false },
  { key: 'default_lifecycle', label: 'adminPages.objectStorage.lifecycle', disabled: false }
]
const currentPool = computed(() => pools.value.find((pool) => pool.enabled))
const statusBadge = (status, enabled) => enabled ? 'success' : status === 'invalid' ? 'failed' : 'pending'

function copySettings(data) {
  Object.keys(form).forEach((key) => { if (data[key] !== undefined) form[key] = data[key] })
}
async function load() {
  loading.value = true; loadError.value = ''
  try {
    const [data, poolData] = await Promise.all([objectStorageAdminApi.getSettings(), objectStorageAdminApi.listResourcePools()])
    settings.value = data; pools.value = poolData; copySettings(data)
  } catch (error) { loadError.value = extractErrorMessage(error, t('adminPages.objectStorage.loadFailed')) } finally { loading.value = false }
}
async function saveSettings() {
  saving.value = true
  try {
    settings.value = await objectStorageAdminApi.updateSettings({ ...form })
    showSuccess(t('adminPages.objectStorage.saved'))
  } catch (error) { showError(extractErrorMessage(error, t('adminPages.objectStorage.saveFailed'))) } finally { saving.value = false }
}
async function createPool() {
  poolSaving.value = true
  try { await objectStorageAdminApi.createResourcePool({ ...poolForm }); showSuccess(t('adminPages.objectStorage.poolCreated')); Object.assign(poolForm, { cloud_account_id: '', region: '', management_access_key: '', management_secret_key: '' }); showPoolForm.value = false; await load() }
  catch (error) { showError(extractErrorMessage(error, t('adminPages.objectStorage.saveFailed'))) } finally { poolSaving.value = false }
}
async function validatePool(pool) {
  validatingPool.value = pool.id
  try { await objectStorageAdminApi.validateResourcePool(pool.id); showSuccess(t('adminPages.objectStorage.validationStarted')); await load() }
  catch (error) { showError(extractErrorMessage(error, t('adminPages.objectStorage.validationFailed'))) } finally { validatingPool.value = null }
}
onMounted(load)
</script>
