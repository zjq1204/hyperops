<template>
  <AdminLayout>
    <PageFrame
      variant="soft"
      :title="t('adminPages.objectStorage.policyTitle')"
      :subtitle="t('adminPages.objectStorage.policySubtitle')"
    >
      <AdminListSection>
        <template #toolbarEnd>
          <BaseButton variant="outline" size="sm" :loading="loading" @click="load">
            {{ t('common.refresh') }}
          </BaseButton>
        </template>
        <AdminPageState :loading="loading" :error="loadError">
          <form class="admin-workbench-panel overflow-hidden p-0" @submit.prevent="save">
            <div class="border-b border-slate-200/80 px-5 py-4 sm:px-6">
              <h2 class="text-base font-semibold text-slate-950">{{ t('adminPages.objectStorage.policySection') }}</h2>
              <p class="mt-1 max-w-3xl text-sm leading-6 text-slate-500">{{ t('adminPages.objectStorage.policyPageHint') }}</p>
            </div>
            <div class="px-5 py-5 sm:px-6">
              <div class="admin-settings-group">
                <h2 class="admin-settings-title">{{ t('adminPages.objectStorage.applicationRules') }}</h2>
                <div class="admin-settings-row">
                  <div class="admin-settings-row-main">
                    <label for="object-storage-naming-template" class="admin-settings-row-title">{{ t('adminPages.objectStorage.namingTemplate') }}</label>
                    <p class="admin-settings-row-copy">{{ t('adminPages.objectStorage.namingTemplateHint') }}</p>
                  </div>
                  <div class="admin-settings-row-control"><input id="object-storage-naming-template" v-model.trim="form.naming_template" class="admin-modal-control font-mono" required /></div>
                </div>
                <div class="admin-settings-row">
                  <div class="admin-settings-row-main">
                    <label for="object-storage-bucket-quota" class="admin-settings-row-title">{{ t('adminPages.objectStorage.bucketQuota') }}</label>
                    <p class="admin-settings-row-copy">{{ t('adminPages.objectStorage.bucketQuotaHint') }}</p>
                  </div>
                  <div class="admin-settings-row-control"><input id="object-storage-bucket-quota" v-model.number="form.default_bucket_quota" class="admin-modal-control w-28" type="number" min="1" max="100" required /><span class="admin-settings-unit">{{ t('adminPages.objectStorage.bucketUnit') }}</span></div>
                </div>
                <div class="admin-settings-row">
                  <div class="admin-settings-row-main">
                    <label for="object-storage-delivery-lifetime" class="admin-settings-row-title">{{ t('adminPages.objectStorage.deliveryLifetime') }}</label>
                    <p class="admin-settings-row-copy">{{ t('adminPages.objectStorage.deliveryLifetimeHint') }}</p>
                  </div>
                  <div class="admin-settings-row-control"><input id="object-storage-delivery-lifetime" v-model.number="deliveryLifetimeMinutes" class="admin-modal-control w-28" type="number" min="10" max="10080" required /><span class="admin-settings-unit">{{ t('adminPages.objectStorage.minuteUnit') }}</span></div>
                </div>
                <div class="admin-settings-row">
                  <div class="admin-settings-row-main">
                    <label for="object-storage-audit-retention" class="admin-settings-row-title">{{ t('adminPages.objectStorage.auditRetention') }}</label>
                    <p class="admin-settings-row-copy">{{ t('adminPages.objectStorage.auditRetentionSettingHint') }}</p>
                  </div>
                  <div class="admin-settings-row-control"><input id="object-storage-audit-retention" v-model.number="form.audit_retention_days" class="admin-modal-control w-28" type="number" min="1" max="3650" required /><span class="admin-settings-unit">{{ t('adminPages.objectStorage.dayUnit') }}</span></div>
                </div>
              </div>

              <div class="admin-settings-group mt-8 border-t border-slate-200/70 pt-5">
                <h2 class="admin-settings-title">{{ t('adminPages.objectStorage.defaultSection') }}</h2>
                <div v-for="item in defaults" :key="item.key" class="admin-settings-row">
                  <div class="admin-settings-row-main">
                    <h3 class="admin-settings-row-title">{{ t(item.label) }}</h3>
                    <p class="admin-settings-row-copy">{{ t(item.hint) }}</p>
                  </div>
                  <div class="admin-settings-row-control">
                    <label class="inline-flex min-h-11 cursor-pointer items-center gap-3">
                      <input v-model="form[item.key]" type="checkbox" class="admin-modal-checkbox" :disabled="item.disabled" />
                      <span class="text-sm font-medium text-slate-700">{{ form[item.key] ? t('common.enabled') : t('common.disabled') }}</span>
                    </label>
                  </div>
                </div>
                <p class="border-t border-slate-200/70 pt-4 text-sm leading-6 text-slate-500">{{ t('adminPages.objectStorage.privateAclHint') }}</p>
              </div>
            </div>
            <div class="flex items-center justify-end border-t border-slate-200/80 bg-slate-50/60 px-5 py-4 sm:px-6"><BaseButton type="submit" :loading="saving">{{ t('common.save') }}</BaseButton></div>
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
import PageFrame from '@/components/ui/PageFrame.vue'
import { extractErrorMessage } from '@/utils/api'
import { useToast } from '@/composables/useToast'
import objectStorageAdminApi from '@/admin/api/objectStorage'

const { t } = useI18n()
const { showSuccess, showError } = useToast()
const loading = ref(true)
const saving = ref(false)
const loadError = ref('')
const settings = ref(null)
const form = reactive({ naming_template: '', default_bucket_quota: 5, delivery_lifetime_seconds: 86400, audit_retention_days: 30, default_encryption: false, default_versioning: false, default_lifecycle: false, default_bucket_acl: 'private' })
const defaults = [
  { key: 'default_encryption', label: 'adminPages.objectStorage.encryption', hint: 'adminPages.objectStorage.encryptionHint', disabled: false },
  { key: 'default_versioning', label: 'adminPages.objectStorage.versioning', hint: 'adminPages.objectStorage.versioningHint', disabled: false },
  { key: 'default_lifecycle', label: 'adminPages.objectStorage.lifecycle', hint: 'adminPages.objectStorage.lifecycleHint', disabled: false }
]
const deliveryLifetimeMinutes = computed({
  get: () => form.delivery_lifetime_seconds / 60,
  set: (value) => { form.delivery_lifetime_seconds = Number(value) * 60 }
})

function copySettings(data) {
  Object.keys(form).forEach((key) => { if (data[key] !== undefined) form[key] = data[key] })
  form.default_encryption = Boolean(data.default_encryption)
  form.default_lifecycle = Boolean(data.default_lifecycle)
}
async function load() {
  loading.value = true
  loadError.value = ''
  try { settings.value = await objectStorageAdminApi.getSettings(); copySettings(settings.value) }
  catch (error) { loadError.value = extractErrorMessage(error, t('adminPages.objectStorage.loadFailed')) }
  finally { loading.value = false }
}
async function save() {
  saving.value = true
  try {
    settings.value = await objectStorageAdminApi.updateSettings({ ...form, default_encryption: form.default_encryption ? 'AES256' : '', default_lifecycle: form.default_lifecycle ? {} : {} })
    showSuccess(t('adminPages.objectStorage.saved'))
  } catch (error) { showError(extractErrorMessage(error, t('adminPages.objectStorage.saveFailed'))) }
  finally { saving.value = false }
}
onMounted(load)
</script>
