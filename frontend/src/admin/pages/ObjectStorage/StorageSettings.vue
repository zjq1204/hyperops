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
          <BaseButton v-if="!pools.length" size="sm" @click="startSetup">
            {{ t('adminPages.objectStorage.addConfiguration') }}
          </BaseButton>
        </template>

        <AdminPageState :loading="loading" :error="loadError">
          <section v-if="!pools.length" class="admin-workbench-panel overflow-hidden p-0">
            <EmptyState
              variant="admin"
              :title="t('adminPages.objectStorage.initialTitle')"
              :description="t('adminPages.objectStorage.initialHint')"
            >
              <template #actions>
                <BaseButton @click="startSetup">
                  {{ t('adminPages.objectStorage.addConfiguration') }}
                </BaseButton>
              </template>
            </EmptyState>
          </section>

          <section v-else class="admin-workbench-panel overflow-hidden p-0">
            <div class="border-b border-slate-200/80 px-5 py-5 sm:px-6">
              <div class="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <div class="flex flex-wrap items-center gap-3">
                    <h2 class="text-lg font-semibold text-slate-950">
                      {{ isConfigured ? t('adminPages.objectStorage.configuredTitle') : t('adminPages.objectStorage.incompleteTitle') }}
                    </h2>
                    <StatusBadge :status="isConfigured ? 'success' : 'pending'" />
                  </div>
                  <p class="mt-1 text-sm leading-6 text-slate-500">
                    {{ isConfigured ? t('adminPages.objectStorage.configuredHint') : t('adminPages.objectStorage.incompleteHint') }}
                  </p>
                </div>
                <BaseButton @click="startSetup">
                  {{ isConfigured ? t('adminPages.objectStorage.editConfiguration') : t('adminPages.objectStorage.continueConfiguration') }}
                </BaseButton>
              </div>
            </div>

            <dl class="grid gap-x-8 gap-y-5 px-5 py-5 sm:grid-cols-2 sm:px-6 lg:grid-cols-3">
              <div>
                <dt class="text-xs font-medium text-slate-500">{{ t('adminPages.objectStorage.provider') }}</dt>
                <dd class="mt-1 text-sm font-semibold text-slate-900">{{ t('adminPages.objectStorage.providerName') }}</dd>
              </div>
              <div>
                <dt class="text-xs font-medium text-slate-500">{{ t('adminPages.objectStorage.enabledPool') }}</dt>
                <dd class="mt-1 break-all text-sm font-semibold text-slate-900">
                  {{ displayPool?.cloud_account_id }} · {{ displayPool?.region }}
                </dd>
              </div>
              <div>
                <dt class="text-xs font-medium text-slate-500">{{ t('adminPages.objectStorage.connectionState') }}</dt>
                <dd class="mt-1 text-sm font-semibold" :class="connectionReady ? 'text-emerald-700' : 'text-amber-700'">
                  {{ connectionReady ? t('adminPages.objectStorage.validated') : t('adminPages.objectStorage.validationRequired') }}
                </dd>
              </div>
              <div>
                <dt class="text-xs font-medium text-slate-500">{{ t('adminPages.objectStorage.namingTemplate') }}</dt>
                <dd class="mt-1 break-all font-mono text-sm font-semibold text-slate-900">{{ form.naming_template }}</dd>
              </div>
              <div>
                <dt class="text-xs font-medium text-slate-500">{{ t('adminPages.objectStorage.bucketQuota') }}</dt>
                <dd class="mt-1 text-sm font-semibold text-slate-900">{{ form.default_bucket_quota }} {{ t('adminPages.objectStorage.bucketUnit') }}</dd>
              </div>
              <div>
                <dt class="text-xs font-medium text-slate-500">{{ t('adminPages.objectStorage.defaultSection') }}</dt>
                <dd class="mt-1 text-sm font-semibold text-slate-900">{{ form.default_storage_class }} · {{ form.default_encryption }}</dd>
              </div>
            </dl>

            <div class="flex flex-wrap items-center justify-between gap-3 border-t border-slate-200/80 bg-slate-50/55 px-5 py-4 sm:px-6">
              <p class="text-sm text-slate-500">
                {{ displayPool?.last_validated_at ? t('adminPages.objectStorage.validatedAt', { date: formatDate(displayPool.last_validated_at) }) : t('adminPages.objectStorage.notValidated') }}
              </p>
              <span class="text-sm font-medium" :class="servicePaused ? 'text-amber-700' : 'text-emerald-700'">
                {{ servicePaused ? t('adminPages.objectStorage.servicePaused') : t('adminPages.objectStorage.serviceRunning') }}
              </span>
            </div>
          </section>
        </AdminPageState>
      </AdminListSection>
    </PageFrame>

    <BaseModal
      :show="setupOpen"
      :title="isConfigured ? t('adminPages.objectStorage.editConfiguration') : t('adminPages.objectStorage.addConfiguration')"
      size="wide"
      :close-on-backdrop="false"
      @close="closeSetup"
    >
      <div class="-mx-5 -mt-5 sm:-mx-6">
        <p class="border-b border-slate-200/80 px-5 py-3 text-sm leading-6 text-slate-500 sm:px-6">
          {{ t('adminPages.objectStorage.wizardHint') }}
        </p>
      </div>

      <InlineAlert v-if="wizardError" class="mt-5" variant="error" :message="wizardError" />

      <div class="min-h-[22rem] py-5">
        <section v-if="activeStep === 0" class="admin-settings-group">
          <div class="section-intro">
            <h2 class="admin-settings-title mb-0">{{ t('adminPages.objectStorage.connectionSection') }}</h2>
            <p class="mt-1 max-w-3xl text-sm leading-6 text-slate-500">{{ t('adminPages.objectStorage.connectionHint') }}</p>
          </div>

          <div v-if="selectedPool" class="mt-5 border-y border-slate-200/70 py-4">
            <div class="grid gap-3 sm:grid-cols-[minmax(0,1fr)_auto_auto] sm:items-center">
              <div>
                <p class="font-medium text-slate-900">{{ selectedPool.cloud_account_id }} · {{ selectedPool.region }}</p>
                <p class="mt-1 text-xs text-slate-500">{{ t('adminPages.objectStorage.keyEnding', { value: selectedPool.access_key_last_four }) }}</p>
              </div>
              <StatusBadge :status="poolBadge(selectedPool)" />
              <div class="flex flex-wrap gap-2">
                <BaseButton size="sm" variant="outline" :loading="validatingPool === selectedPool.id" @click="validatePool(selectedPool)">
                  {{ t('adminPages.objectStorage.validate') }}
                </BaseButton>
                <BaseButton size="sm" variant="ghost" @click="connectionEditorOpen = !connectionEditorOpen">
                  {{ t('adminPages.objectStorage.updateConnection') }}
                </BaseButton>
              </div>
            </div>
          </div>

          <div v-if="!selectedPool || connectionEditorOpen" class="mt-5 grid gap-4 sm:grid-cols-2">
            <label class="admin-form-field">
              <span class="admin-form-label">{{ t('adminPages.objectStorage.provider') }}</span>
              <input class="admin-filter-control" :value="t('adminPages.objectStorage.providerName')" readonly />
            </label>
            <label class="admin-form-field">
              <span class="admin-form-label">{{ t('adminPages.objectStorage.accountId') }}</span>
              <input v-model.trim="poolForm.cloud_account_id" class="admin-filter-control" />
            </label>
            <label class="admin-form-field">
              <span class="admin-form-label">{{ t('adminPages.objectStorage.region') }}</span>
              <input v-model.trim="poolForm.region" class="admin-filter-control" />
            </label>
            <label class="admin-form-field">
              <span class="admin-form-label">{{ t('adminPages.objectStorage.managementAccessKey') }}</span>
              <input v-model="poolForm.management_access_key" class="admin-filter-control font-mono" autocomplete="off" />
            </label>
            <label class="admin-form-field sm:col-span-2">
              <span class="admin-form-label">{{ t('adminPages.objectStorage.managementSecretKey') }}</span>
              <input v-model="poolForm.management_secret_key" class="admin-filter-control font-mono" type="password" autocomplete="new-password" />
              <span v-if="selectedPool" class="admin-form-help">{{ t('adminPages.objectStorage.secretUpdateHint') }}</span>
            </label>
            <div class="flex justify-end sm:col-span-2">
              <BaseButton type="button" :loading="poolSaving" @click="saveAndValidateConnection">
                {{ t('adminPages.objectStorage.saveAndValidate') }}
              </BaseButton>
            </div>
          </div>
        </section>

        <section v-else-if="activeStep === 1" class="admin-settings-group">
          <h2 class="admin-settings-title">{{ t('adminPages.objectStorage.policySection') }}</h2>
          <div class="admin-settings-row">
            <div class="admin-settings-row-main"><label for="storage-naming-template" class="admin-settings-row-title">{{ t('adminPages.objectStorage.namingTemplate') }}</label><p class="admin-settings-row-copy">{{ t('adminPages.objectStorage.namingTemplateHint') }}</p></div>
            <div class="admin-settings-row-control"><input id="storage-naming-template" v-model.trim="form.naming_template" class="admin-modal-control font-mono" /></div>
          </div>
          <div class="admin-settings-row">
            <div class="admin-settings-row-main"><label for="storage-bucket-quota" class="admin-settings-row-title">{{ t('adminPages.objectStorage.bucketQuota') }}</label><p class="admin-settings-row-copy">{{ t('adminPages.objectStorage.bucketQuotaHint') }}</p></div>
            <div class="admin-settings-row-control"><input id="storage-bucket-quota" v-model.number="form.default_bucket_quota" class="admin-modal-control w-28" type="number" min="1" max="100" /><span class="admin-settings-unit">{{ t('adminPages.objectStorage.bucketUnit') }}</span></div>
          </div>
          <div class="admin-settings-row">
            <div class="admin-settings-row-main"><label for="storage-delivery-lifetime" class="admin-settings-row-title">{{ t('adminPages.objectStorage.deliveryLifetime') }}</label><p class="admin-settings-row-copy">{{ t('adminPages.objectStorage.deliveryLifetimeHint') }}</p></div>
            <div class="admin-settings-row-control"><input id="storage-delivery-lifetime" v-model.number="deliveryLifetimeMinutes" class="admin-modal-control w-28" type="number" min="10" max="10080" /><span class="admin-settings-unit">{{ t('adminPages.objectStorage.minuteUnit') }}</span></div>
          </div>
          <div class="admin-settings-row">
            <div class="admin-settings-row-main"><label for="storage-audit-retention" class="admin-settings-row-title">{{ t('adminPages.objectStorage.auditRetention') }}</label><p class="admin-settings-row-copy">{{ t('adminPages.objectStorage.auditRetentionSettingHint') }}</p></div>
            <div class="admin-settings-row-control"><input id="storage-audit-retention" v-model.number="form.audit_retention_days" class="admin-modal-control w-28" type="number" min="1" max="3650" /><span class="admin-settings-unit">{{ t('adminPages.objectStorage.dayUnit') }}</span></div>
          </div>
        </section>

        <section v-else class="admin-settings-group">
          <h2 class="admin-settings-title">{{ t('adminPages.objectStorage.defaultSection') }}</h2>
          <div class="admin-settings-row">
            <div class="admin-settings-row-main"><label for="storage-class" class="admin-settings-row-title">{{ t('adminPages.objectStorage.storageClass') }}</label><p class="admin-settings-row-copy">{{ t('adminPages.objectStorage.storageClassHint') }}</p></div>
            <div class="admin-settings-row-control"><select id="storage-class" v-model="form.default_storage_class" class="admin-modal-control"><option v-for="option in storageClasses" :key="option" :value="option">{{ option }}</option></select></div>
          </div>
          <div class="admin-settings-row">
            <div class="admin-settings-row-main"><h3 class="admin-settings-row-title">{{ t('adminPages.objectStorage.encryption') }}</h3><p class="admin-settings-row-copy">{{ t('adminPages.objectStorage.encryptionHint') }}</p></div>
            <div class="admin-settings-row-control"><span class="text-sm font-semibold text-slate-900">{{ form.default_encryption }}</span></div>
          </div>
          <div class="admin-settings-row">
            <div class="admin-settings-row-main"><h3 class="admin-settings-row-title">{{ t('adminPages.objectStorage.versioning') }}</h3><p class="admin-settings-row-copy">{{ t('adminPages.objectStorage.versioningHint') }}</p></div>
            <div class="admin-settings-row-control"><label class="inline-flex min-h-11 cursor-pointer items-center gap-3"><input v-model="form.default_versioning" type="checkbox" class="admin-modal-checkbox" /><span class="text-sm font-medium text-slate-700">{{ form.default_versioning ? t('common.enabled') : t('common.disabled') }}</span></label></div>
          </div>
          <p class="border-t border-slate-200/70 pt-4 text-sm leading-6 text-slate-500">{{ t('adminPages.objectStorage.privateAclHint') }}</p>

          <div class="mt-6">
            <h3 class="text-sm font-semibold text-slate-900">{{ t('adminPages.objectStorage.operationSection') }}</h3>
            <div v-for="item in operationControls" :key="item.key" class="admin-settings-row">
              <div class="admin-settings-row-main"><h4 class="admin-settings-row-title">{{ t(item.label) }}</h4><p class="admin-settings-row-copy">{{ t(item.hint) }}</p></div>
              <div class="admin-settings-row-control"><label class="inline-flex min-h-11 cursor-pointer items-center gap-3"><input v-model="form[item.key]" type="checkbox" class="admin-modal-checkbox" /><span class="text-sm font-medium" :class="form[item.key] ? 'text-amber-700' : 'text-slate-700'">{{ form[item.key] ? t('adminPages.objectStorage.paused') : t('adminPages.objectStorage.running') }}</span></label></div>
            </div>
          </div>

          <InlineAlert
            v-if="!feishuReady"
            class="mt-6"
            variant="warning"
            :message="t('adminPages.objectStorage.dependenciesRequired')"
          >
            <template #actions>
              <RouterLink
                class="text-sm font-semibold text-sky-700 hover:text-sky-900"
                to="/management/authentication/feishu"
              >
                {{ t('adminPages.objectStorage.configureAuthentication') }}
              </RouterLink>
            </template>
          </InlineAlert>
        </section>
      </div>

      <template #footer>
        <div class="flex w-full flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <span class="text-sm text-slate-500">{{ t('adminPages.objectStorage.stepProgress', { current: activeStep + 1, total: totalSteps }) }}</span>
          <div class="flex items-center justify-end gap-2">
            <BaseButton v-if="activeStep > 0" type="button" variant="outline" @click="activeStep -= 1">{{ t('adminPages.objectStorage.previousStep') }}</BaseButton>
            <BaseButton v-if="activeStep < totalSteps - 1" type="button" :disabled="activeStep === 0 && !connectionReady" @click="goNext">{{ t('adminPages.objectStorage.nextStep') }}</BaseButton>
            <BaseButton v-else type="button" :loading="saving" :disabled="!canEnable" @click="saveAndFinish">{{ isConfigured ? t('adminPages.objectStorage.saveAndFinish') : t('adminPages.objectStorage.createAndEnable') }}</BaseButton>
          </div>
        </div>
      </template>
    </BaseModal>
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
import { extractErrorMessage } from '@/utils/api'
import { formatDateIsoLocale } from '@/utils/formatting'
import { useToast } from '@/composables/useToast'
import objectStorageAdminApi from '@/admin/api/objectStorage'

const { t, locale } = useI18n()
const { showSuccess } = useToast()
const loading = ref(true)
const saving = ref(false)
const poolSaving = ref(false)
const validatingPool = ref(null)
const loadError = ref('')
const wizardError = ref('')
const settings = ref(null)
const feishu = ref(null)
const pools = ref([])
const selectedPoolId = ref(null)
const setupOpen = ref(false)
const connectionEditorOpen = ref(false)
const activeStep = ref(0)
const totalSteps = 3
const storageClasses = ['Standard', 'IA', 'Archive', 'ColdArchive', 'DeepColdArchive']
const form = reactive({ naming_template: '', default_bucket_quota: 5, delivery_lifetime_seconds: 86400, audit_retention_days: 30, default_storage_class: 'Standard', default_encryption: 'AES256', default_versioning: false, default_lifecycle: {}, pause_new_applications: true, pause_key_operations: true, default_bucket_acl: 'private' })
const poolForm = reactive({ cloud_account_id: '', region: '', management_access_key: '', management_secret_key: '' })
const operationControls = [
  { key: 'pause_new_applications', label: 'adminPages.objectStorage.pauseApplications', hint: 'adminPages.objectStorage.pauseApplicationsHint' },
  { key: 'pause_key_operations', label: 'adminPages.objectStorage.pauseKeys', hint: 'adminPages.objectStorage.pauseKeysHint' }
]
const enabledPool = computed(() => pools.value.find((pool) => pool.enabled && pool.validation_status === 'valid'))
const selectedPool = computed(() => pools.value.find((pool) => pool.id === selectedPoolId.value) || enabledPool.value || pools.value.find((pool) => pool.validation_status === 'valid') || pools.value[0] || null)
const displayPool = computed(() => enabledPool.value || selectedPool.value)
const connectionReady = computed(() => selectedPool.value?.validation_status === 'valid')
const feishuReady = computed(() => feishu.value?.validation_status === 'valid')
const isConfigured = computed(() => Boolean(enabledPool.value && feishu.value?.enabled && feishuReady.value))
const canEnable = computed(() => connectionReady.value && feishuReady.value)
const servicePaused = computed(() => form.pause_new_applications || form.pause_key_operations)
const deliveryLifetimeMinutes = computed({ get: () => form.delivery_lifetime_seconds / 60, set: (value) => { form.delivery_lifetime_seconds = Number(value) * 60 } })
const formatDate = (value) => formatDateIsoLocale(value, locale.value)
const poolBadge = (pool) => pool?.validation_status === 'valid' ? 'success' : pool?.validation_status === 'invalid' ? 'failed' : 'pending'

function copySettings(data) { Object.keys(form).forEach((key) => { if (data[key] !== undefined) form[key] = data[key] }) }
function copyPool(pool) {
  Object.assign(poolForm, { cloud_account_id: pool?.cloud_account_id || '', region: pool?.region || '', management_access_key: '', management_secret_key: '' })
}
function startSetup() {
  activeStep.value = 0
  wizardError.value = ''
  connectionEditorOpen.value = !selectedPool.value
  copyPool(selectedPool.value)
  if (!isConfigured.value) {
    form.pause_new_applications = false
    form.pause_key_operations = false
  }
  setupOpen.value = true
}
function closeSetup() {
  setupOpen.value = false
  wizardError.value = ''
  connectionEditorOpen.value = false
  if (settings.value) copySettings(settings.value)
}
function validatePolicy() {
  return Boolean(form.naming_template.trim()) && Number.isInteger(form.default_bucket_quota) && form.default_bucket_quota >= 1 && form.default_bucket_quota <= 100 && Number.isInteger(form.delivery_lifetime_seconds) && form.delivery_lifetime_seconds >= 600 && form.delivery_lifetime_seconds <= 604800 && Number.isInteger(form.audit_retention_days) && form.audit_retention_days >= 1 && form.audit_retention_days <= 3650
}
function goNext() {
  wizardError.value = ''
  if (activeStep.value === 0 && !connectionReady.value) { wizardError.value = t('adminPages.objectStorage.connectionRequired'); return }
  if (activeStep.value === 1 && !validatePolicy()) { wizardError.value = t('adminPages.objectStorage.policyValidationFailed'); return }
  activeStep.value += 1
}
async function load() {
  loading.value = true
  loadError.value = ''
  try {
    const [data, poolData, feishuData] = await Promise.all([objectStorageAdminApi.getSettings(), objectStorageAdminApi.listResourcePools(), objectStorageAdminApi.getFeishu()])
    settings.value = data
    pools.value = poolData
    feishu.value = feishuData
    copySettings(data)
    if (!selectedPoolId.value && poolData.length) selectedPoolId.value = (poolData.find((pool) => pool.enabled) || poolData[0]).id
  } catch (error) {
    loadError.value = extractErrorMessage(error, t('adminPages.objectStorage.loadFailed'))
  } finally {
    loading.value = false
  }
}
async function refreshSetupData() {
  const [poolData, feishuData] = await Promise.all([objectStorageAdminApi.listResourcePools(), objectStorageAdminApi.getFeishu()])
  pools.value = poolData
  feishu.value = feishuData
}
async function saveAndValidateConnection() {
  wizardError.value = ''
  const updating = Boolean(selectedPool.value)
  const credentialsProvided = poolForm.management_access_key && poolForm.management_secret_key
  if (!poolForm.cloud_account_id || !poolForm.region || (!updating && !credentialsProvided) || Boolean(poolForm.management_access_key) !== Boolean(poolForm.management_secret_key)) {
    wizardError.value = t('adminPages.objectStorage.poolValidationFailed')
    return
  }
  poolSaving.value = true
  try {
    const body = { ...poolForm }
    if (!credentialsProvided) { delete body.management_access_key; delete body.management_secret_key }
    const pool = updating ? await objectStorageAdminApi.updateResourcePool(selectedPool.value.id, body) : await objectStorageAdminApi.createResourcePool(body)
    selectedPoolId.value = pool.id
    await objectStorageAdminApi.validateResourcePool(pool.id)
    await refreshSetupData()
    connectionEditorOpen.value = false
    copyPool(selectedPool.value)
    showSuccess(t('adminPages.objectStorage.connectionValidated'))
  } catch (error) {
    wizardError.value = extractErrorMessage(error, t('adminPages.objectStorage.validationFailed'))
  } finally {
    poolSaving.value = false
  }
}
async function validatePool(pool) {
  validatingPool.value = pool.id
  wizardError.value = ''
  try {
    await objectStorageAdminApi.validateResourcePool(pool.id)
    selectedPoolId.value = pool.id
    await refreshSetupData()
    showSuccess(t('adminPages.objectStorage.connectionValidated'))
  } catch (error) {
    wizardError.value = extractErrorMessage(error, t('adminPages.objectStorage.validationFailed'))
  } finally {
    validatingPool.value = null
  }
}
async function saveAndFinish() {
  wizardError.value = ''
  if (!canEnable.value) { wizardError.value = t('adminPages.objectStorage.dependenciesRequired'); return }
  if (!validatePolicy()) { activeStep.value = 1; wizardError.value = t('adminPages.objectStorage.policyValidationFailed'); return }
  saving.value = true
  try {
    settings.value = await objectStorageAdminApi.updateSettings({ ...form })
    await objectStorageAdminApi.enablePlatform(selectedPool.value.id)
    await load()
    setupOpen.value = false
    showSuccess(t('adminPages.objectStorage.configurationEnabled'))
  } catch (error) {
    wizardError.value = extractErrorMessage(error, t('adminPages.objectStorage.enableFailed'))
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>
