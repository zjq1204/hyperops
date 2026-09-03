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
          <form class="admin-workbench-panel overflow-hidden p-0" @submit.prevent="saveSettings">
            <div class="border-b border-slate-200/80 px-5 py-4 sm:px-6">
              <h2 class="text-base font-semibold text-slate-950">
                {{ t('adminPages.objectStorage.setupTitle') }}
              </h2>
              <p class="mt-1 max-w-3xl text-sm leading-6 text-slate-500">
                {{ t('adminPages.objectStorage.setupHint') }}
              </p>
            </div>

            <nav :aria-label="t('adminPages.objectStorage.setupTitle')" class="border-b border-slate-200/80 bg-slate-50/55">
              <ol class="grid grid-cols-2 lg:grid-cols-4">
                <li v-for="(step, index) in steps" :key="step.key" class="border-slate-200/80 [&:nth-child(even)]:border-l [&:nth-child(n+3)]:border-t lg:border-l lg:border-t-0 lg:first:border-l-0">
                  <button
                    type="button"
                    class="flex min-h-20 w-full items-center gap-3 px-4 py-3 text-left transition-colors duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-sky-500 sm:px-5"
                    :class="activeStep === index ? 'bg-white' : 'hover:bg-white/70'"
                    :aria-current="activeStep === index ? 'step' : undefined"
                    @click="activeStep = index"
                  >
                    <span
                      class="flex h-7 w-7 shrink-0 items-center justify-center rounded-full border text-xs font-semibold"
                      :class="activeStep === index ? 'border-sky-600 bg-sky-600 text-white' : index < activeStep ? 'border-sky-200 bg-sky-50 text-sky-700' : 'border-slate-300 bg-white text-slate-500'"
                    >
                      {{ index + 1 }}
                    </span>
                    <span class="min-w-0">
                      <span class="block text-sm font-semibold" :class="activeStep === index ? 'text-slate-950' : 'text-slate-700'">
                        {{ t(step.label) }}
                      </span>
                      <span class="mt-0.5 hidden text-xs leading-5 text-slate-500 sm:block">
                        {{ t(step.hint) }}
                      </span>
                    </span>
                  </button>
                </li>
              </ol>
            </nav>

            <div class="min-h-[26rem] px-5 py-5 sm:px-6 sm:py-6">
              <section v-if="activeStep === 0" class="admin-settings-group">
                <div class="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <h2 class="admin-settings-title mb-0">{{ t('adminPages.objectStorage.connectionSection') }}</h2>
                    <p class="mt-1 max-w-3xl text-sm leading-6 text-slate-500">{{ t('adminPages.objectStorage.connectionHint') }}</p>
                  </div>
                  <BaseButton size="sm" variant="outline" @click="showPoolForm = !showPoolForm">
                    {{ showPoolForm ? t('common.cancel') : t('adminPages.objectStorage.addPool') }}
                  </BaseButton>
                </div>

                <div class="admin-settings-row mt-5">
                  <div class="admin-settings-row-main">
                    <h3 class="admin-settings-row-title">{{ t('adminPages.objectStorage.provider') }}</h3>
                    <p class="admin-settings-row-copy">{{ t('adminPages.objectStorage.providerHint') }}</p>
                  </div>
                  <div class="admin-settings-row-control">
                    <span class="text-sm font-medium text-slate-900">{{ t('adminPages.objectStorage.providerName') }}</span>
                  </div>
                </div>

                <div v-if="showPoolForm" class="grid gap-4 border-y border-slate-200/70 bg-slate-50/60 py-5 sm:grid-cols-2">
                  <label class="admin-form-field"><span class="admin-form-label">{{ t('adminPages.objectStorage.accountId') }}</span><input v-model.trim="poolForm.cloud_account_id" class="admin-filter-control" /></label>
                  <label class="admin-form-field"><span class="admin-form-label">{{ t('adminPages.objectStorage.region') }}</span><input v-model.trim="poolForm.region" class="admin-filter-control" /></label>
                  <label class="admin-form-field"><span class="admin-form-label">{{ t('adminPages.objectStorage.managementAccessKey') }}</span><input v-model="poolForm.management_access_key" class="admin-filter-control font-mono" autocomplete="off" /></label>
                  <label class="admin-form-field"><span class="admin-form-label">{{ t('adminPages.objectStorage.managementSecretKey') }}</span><input v-model="poolForm.management_secret_key" class="admin-filter-control font-mono" type="password" autocomplete="new-password" /></label>
                  <div class="flex items-center justify-end gap-2 sm:col-span-2">
                    <BaseButton type="button" variant="outline" @click="showPoolForm = false">{{ t('common.cancel') }}</BaseButton>
                    <BaseButton type="button" :loading="poolSaving" @click="createPool">{{ t('adminPages.objectStorage.savePool') }}</BaseButton>
                  </div>
                </div>

                <div v-if="pools.length" class="mt-1 divide-y divide-slate-200 border-y border-slate-200/70">
                  <div v-for="pool in pools" :key="pool.id" class="grid gap-3 py-4 sm:grid-cols-[minmax(0,1fr)_minmax(9rem,0.5fr)_auto] sm:items-center">
                    <div>
                      <p class="font-medium text-slate-900">{{ pool.cloud_account_id }}</p>
                      <p class="mt-1 text-xs text-slate-500">{{ pool.region }} · {{ t('adminPages.objectStorage.keyEnding', { value: pool.access_key_last_four }) }}</p>
                    </div>
                    <StatusBadge :status="statusBadge(pool.validation_status, pool.enabled)" />
                    <BaseButton size="sm" variant="outline" :loading="validatingPool === pool.id" @click="validatePool(pool)">{{ t('adminPages.objectStorage.validate') }}</BaseButton>
                  </div>
                </div>
                <EmptyState v-else variant="admin" :title="t('adminPages.objectStorage.noPool')" :description="t('adminPages.objectStorage.noPoolHint')" />
              </section>

              <section v-else-if="activeStep === 1" class="admin-settings-group">
                <h2 class="admin-settings-title">{{ t('adminPages.objectStorage.policySection') }}</h2>
                <div class="admin-settings-row">
                  <div class="admin-settings-row-main"><label for="object-storage-naming-template" class="admin-settings-row-title">{{ t('adminPages.objectStorage.namingTemplate') }}</label><p class="admin-settings-row-copy">{{ t('adminPages.objectStorage.namingTemplateHint') }}</p></div>
                  <div class="admin-settings-row-control"><input id="object-storage-naming-template" v-model.trim="form.naming_template" class="admin-modal-control font-mono" /></div>
                </div>
                <div class="admin-settings-row">
                  <div class="admin-settings-row-main"><label for="object-storage-bucket-quota" class="admin-settings-row-title">{{ t('adminPages.objectStorage.bucketQuota') }}</label><p class="admin-settings-row-copy">{{ t('adminPages.objectStorage.bucketQuotaHint') }}</p></div>
                  <div class="admin-settings-row-control"><input id="object-storage-bucket-quota" v-model.number="form.default_bucket_quota" class="admin-modal-control w-28" type="number" min="1" max="100" /><span class="admin-settings-unit">{{ t('adminPages.objectStorage.bucketUnit') }}</span></div>
                </div>
                <div class="admin-settings-row">
                  <div class="admin-settings-row-main"><label for="object-storage-delivery-lifetime" class="admin-settings-row-title">{{ t('adminPages.objectStorage.deliveryLifetime') }}</label><p class="admin-settings-row-copy">{{ t('adminPages.objectStorage.deliveryLifetimeHint') }}</p></div>
                  <div class="admin-settings-row-control"><input id="object-storage-delivery-lifetime" v-model.number="deliveryLifetimeMinutes" class="admin-modal-control w-28" type="number" min="10" max="10080" /><span class="admin-settings-unit">{{ t('adminPages.objectStorage.minuteUnit') }}</span></div>
                </div>
                <div class="admin-settings-row">
                  <div class="admin-settings-row-main"><label for="object-storage-audit-retention" class="admin-settings-row-title">{{ t('adminPages.objectStorage.auditRetention') }}</label><p class="admin-settings-row-copy">{{ t('adminPages.objectStorage.auditRetentionSettingHint') }}</p></div>
                  <div class="admin-settings-row-control"><input id="object-storage-audit-retention" v-model.number="form.audit_retention_days" class="admin-modal-control w-28" type="number" min="1" max="3650" /><span class="admin-settings-unit">{{ t('adminPages.objectStorage.dayUnit') }}</span></div>
                </div>
              </section>

              <section v-else-if="activeStep === 2" class="admin-settings-group">
                <h2 class="admin-settings-title">{{ t('adminPages.objectStorage.defaultSection') }}</h2>
                <div class="admin-settings-row">
                  <div class="admin-settings-row-main"><label for="object-storage-storage-class" class="admin-settings-row-title">{{ t('adminPages.objectStorage.storageClass') }}</label><p class="admin-settings-row-copy">{{ t('adminPages.objectStorage.storageClassHint') }}</p></div>
                  <div class="admin-settings-row-control"><select id="object-storage-storage-class" v-model="form.default_storage_class" class="admin-modal-control"><option v-for="option in storageClasses" :key="option" :value="option">{{ option }}</option></select></div>
                </div>
                <div class="admin-settings-row">
                  <div class="admin-settings-row-main"><h3 class="admin-settings-row-title">{{ t('adminPages.objectStorage.encryption') }}</h3><p class="admin-settings-row-copy">{{ t('adminPages.objectStorage.encryptionHint') }}</p></div>
                  <div class="admin-settings-row-control"><span class="text-sm font-medium text-slate-900">{{ form.default_encryption }}</span></div>
                </div>
                <div class="admin-settings-row">
                  <div class="admin-settings-row-main"><h3 class="admin-settings-row-title">{{ t('adminPages.objectStorage.versioning') }}</h3><p class="admin-settings-row-copy">{{ t('adminPages.objectStorage.versioningHint') }}</p></div>
                  <div class="admin-settings-row-control"><label class="inline-flex min-h-11 cursor-pointer items-center gap-3"><input v-model="form.default_versioning" type="checkbox" class="admin-modal-checkbox" /><span class="text-sm font-medium text-slate-700">{{ form.default_versioning ? t('common.enabled') : t('common.disabled') }}</span></label></div>
                </div>
                <div class="admin-settings-row">
                  <div class="admin-settings-row-main"><h3 class="admin-settings-row-title">{{ t('adminPages.objectStorage.lifecycle') }}</h3><p class="admin-settings-row-copy">{{ t('adminPages.objectStorage.lifecycleHint') }}</p></div>
                  <div class="admin-settings-row-control"><span class="text-sm font-medium text-slate-700">{{ hasLifecycle ? t('adminPages.objectStorage.configured') : t('adminPages.objectStorage.notConfiguredShort') }}</span></div>
                </div>
                <p class="border-t border-slate-200/70 pt-4 text-sm leading-6 text-slate-500">{{ t('adminPages.objectStorage.privateAclHint') }}</p>
              </section>

              <section v-else class="admin-settings-group">
                <h2 class="admin-settings-title">{{ t('adminPages.objectStorage.operationSection') }}</h2>
                <div v-for="item in operationControls" :key="item.key" class="admin-settings-row">
                  <div class="admin-settings-row-main"><h3 class="admin-settings-row-title">{{ t(item.label) }}</h3><p class="admin-settings-row-copy">{{ t(item.hint) }}</p></div>
                  <div class="admin-settings-row-control"><label class="inline-flex min-h-11 cursor-pointer items-center gap-3"><input v-model="form[item.key]" type="checkbox" class="admin-modal-checkbox" /><span class="text-sm font-medium" :class="form[item.key] ? 'text-amber-700' : 'text-slate-700'">{{ form[item.key] ? t('adminPages.objectStorage.paused') : t('adminPages.objectStorage.running') }}</span></label></div>
                </div>
                <p class="border-t border-slate-200/70 pt-4 text-sm leading-6 text-slate-500">{{ t('adminPages.objectStorage.operationHint') }}</p>
              </section>
            </div>

            <div class="flex flex-col gap-3 border-t border-slate-200/80 bg-slate-50/60 px-5 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-6">
              <p class="text-sm text-slate-500">{{ t('adminPages.objectStorage.stepProgress', { current: activeStep + 1, total: steps.length }) }}</p>
              <div class="flex items-center justify-end gap-2">
                <BaseButton v-if="activeStep > 0" type="button" variant="outline" @click="activeStep -= 1">{{ t('adminPages.objectStorage.previousStep') }}</BaseButton>
                <BaseButton v-if="activeStep < steps.length - 1" type="button" @click="goNext">{{ t('adminPages.objectStorage.nextStep') }}</BaseButton>
                <BaseButton v-else type="submit" :loading="saving">{{ t('common.save') }}</BaseButton>
              </div>
            </div>
          </form>
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
const activeStep = ref(0)
const steps = [
  { key: 'connection', label: 'adminPages.objectStorage.connectionSection', hint: 'adminPages.objectStorage.stepConnectionHint' },
  { key: 'rules', label: 'adminPages.objectStorage.policySection', hint: 'adminPages.objectStorage.stepPolicyHint' },
  { key: 'defaults', label: 'adminPages.objectStorage.defaultSection', hint: 'adminPages.objectStorage.stepDefaultsHint' },
  { key: 'controls', label: 'adminPages.objectStorage.operationSection', hint: 'adminPages.objectStorage.stepControlsHint' }
]
const storageClasses = ['Standard', 'IA', 'Archive', 'ColdArchive', 'DeepColdArchive']
const form = reactive({
  naming_template: '',
  default_bucket_quota: 5,
  delivery_lifetime_seconds: 86400,
  audit_retention_days: 30,
  default_storage_class: 'Standard',
  default_encryption: 'AES256',
  default_versioning: false,
  default_lifecycle: {},
  pause_new_applications: false,
  pause_key_operations: false,
  default_bucket_acl: 'private'
})
const poolForm = reactive({ cloud_account_id: '', region: '', management_access_key: '', management_secret_key: '' })
const operationControls = [
  { key: 'pause_new_applications', label: 'adminPages.objectStorage.pauseApplications', hint: 'adminPages.objectStorage.pauseApplicationsHint' },
  { key: 'pause_key_operations', label: 'adminPages.objectStorage.pauseKeys', hint: 'adminPages.objectStorage.pauseKeysHint' }
]
const deliveryLifetimeMinutes = computed({
  get: () => form.delivery_lifetime_seconds / 60,
  set: (value) => { form.delivery_lifetime_seconds = Number(value) * 60 }
})
const hasLifecycle = computed(() => Array.isArray(form.default_lifecycle) ? form.default_lifecycle.length > 0 : Object.keys(form.default_lifecycle || {}).length > 0)
const statusBadge = (status, enabled) => enabled ? 'success' : status === 'invalid' ? 'failed' : 'pending'

function copySettings(data) {
  Object.keys(form).forEach((key) => { if (data[key] !== undefined) form[key] = data[key] })
}
function validatePolicy() {
  if (!form.naming_template.trim()) return false
  if (!Number.isInteger(form.default_bucket_quota) || form.default_bucket_quota < 1 || form.default_bucket_quota > 100) return false
  if (!Number.isInteger(form.delivery_lifetime_seconds) || form.delivery_lifetime_seconds < 600 || form.delivery_lifetime_seconds > 604800) return false
  return Number.isInteger(form.audit_retention_days) && form.audit_retention_days >= 1 && form.audit_retention_days <= 3650
}
function goNext() {
  if (activeStep.value === 1 && !validatePolicy()) {
    showError(t('adminPages.objectStorage.policyValidationFailed'))
    return
  }
  activeStep.value += 1
}
async function load() {
  loading.value = true
  loadError.value = ''
  try {
    const [data, poolData] = await Promise.all([objectStorageAdminApi.getSettings(), objectStorageAdminApi.listResourcePools()])
    settings.value = data
    pools.value = poolData
    copySettings(data)
  } catch (error) {
    loadError.value = extractErrorMessage(error, t('adminPages.objectStorage.loadFailed'))
  } finally {
    loading.value = false
  }
}
async function saveSettings() {
  if (!validatePolicy()) {
    activeStep.value = 1
    showError(t('adminPages.objectStorage.policyValidationFailed'))
    return
  }
  saving.value = true
  try {
    settings.value = await objectStorageAdminApi.updateSettings({ ...form })
    showSuccess(t('adminPages.objectStorage.saved'))
  } catch (error) {
    showError(extractErrorMessage(error, t('adminPages.objectStorage.saveFailed')))
  } finally {
    saving.value = false
  }
}
async function createPool() {
  if (!poolForm.cloud_account_id || !poolForm.region || !poolForm.management_access_key || !poolForm.management_secret_key) {
    showError(t('adminPages.objectStorage.poolValidationFailed'))
    return
  }
  poolSaving.value = true
  try {
    await objectStorageAdminApi.createResourcePool({ ...poolForm })
    showSuccess(t('adminPages.objectStorage.poolCreated'))
    Object.assign(poolForm, { cloud_account_id: '', region: '', management_access_key: '', management_secret_key: '' })
    showPoolForm.value = false
    await load()
  } catch (error) {
    showError(extractErrorMessage(error, t('adminPages.objectStorage.saveFailed')))
  } finally {
    poolSaving.value = false
  }
}
async function validatePool(pool) {
  validatingPool.value = pool.id
  try {
    await objectStorageAdminApi.validateResourcePool(pool.id)
    showSuccess(t('adminPages.objectStorage.validationStarted'))
    await load()
  } catch (error) {
    showError(extractErrorMessage(error, t('adminPages.objectStorage.validationFailed')))
  } finally {
    validatingPool.value = null
  }
}

onMounted(load)
</script>
