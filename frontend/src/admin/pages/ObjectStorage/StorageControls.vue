<template>
  <AdminLayout>
    <PageFrame
      variant="soft"
      :title="t('adminPages.objectStorage.controlsTitle')"
      :subtitle="t('adminPages.objectStorage.controlsSubtitle')"
    >
      <AdminListSection>
        <template #toolbarEnd>
          <BaseButton variant="outline" size="sm" :loading="loading" @click="load">{{ t('common.refresh') }}</BaseButton>
        </template>
        <AdminPageState :loading="loading" :error="loadError">
          <form class="admin-workbench-panel overflow-hidden p-0" @submit.prevent="save">
            <div class="border-b border-slate-200/80 px-5 py-4 sm:px-6">
              <h2 class="text-base font-semibold text-slate-950">{{ t('adminPages.objectStorage.operationSection') }}</h2>
              <p class="mt-1 max-w-3xl text-sm leading-6 text-slate-500">{{ t('adminPages.objectStorage.operationPageHint') }}</p>
            </div>
            <div class="px-5 py-5 sm:px-6">
              <div class="admin-settings-group">
                <h2 class="admin-settings-title">{{ t('adminPages.objectStorage.serviceAvailability') }}</h2>
                <div v-for="item in controls" :key="item.key" class="admin-settings-row">
                  <div class="admin-settings-row-main">
                    <h3 class="admin-settings-row-title">{{ t(item.label) }}</h3>
                    <p class="admin-settings-row-copy">{{ t(item.hint) }}</p>
                  </div>
                  <div class="admin-settings-row-control">
                    <label class="inline-flex min-h-11 cursor-pointer items-center gap-3">
                      <input v-model="form[item.key]" type="checkbox" class="admin-modal-checkbox" />
                      <span class="text-sm font-medium" :class="form[item.key] ? 'text-amber-700' : 'text-slate-700'">{{ form[item.key] ? t('adminPages.objectStorage.paused') : t('adminPages.objectStorage.running') }}</span>
                    </label>
                  </div>
                </div>
              </div>
            </div>
            <div class="flex items-center justify-between gap-4 border-t border-slate-200/80 bg-slate-50/60 px-5 py-4 sm:px-6">
              <p class="text-sm text-slate-500">{{ t('adminPages.objectStorage.operationHint') }}</p>
              <BaseButton type="submit" :loading="saving">{{ t('common.save') }}</BaseButton>
            </div>
          </form>
        </AdminPageState>
      </AdminListSection>
    </PageFrame>
  </AdminLayout>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
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
const form = reactive({ pause_new_applications: false, pause_key_operations: false })
const controls = [
  { key: 'pause_new_applications', label: 'adminPages.objectStorage.pauseApplications', hint: 'adminPages.objectStorage.pauseApplicationsHint' },
  { key: 'pause_key_operations', label: 'adminPages.objectStorage.pauseKeys', hint: 'adminPages.objectStorage.pauseKeysHint' }
]
function copySettings(data) { controls.forEach(({ key }) => { if (data[key] !== undefined) form[key] = Boolean(data[key]) }) }
async function load() {
  loading.value = true
  loadError.value = ''
  try { copySettings(await objectStorageAdminApi.getSettings()) }
  catch (error) { loadError.value = extractErrorMessage(error, t('adminPages.objectStorage.loadFailed')) }
  finally { loading.value = false }
}
async function save() {
  saving.value = true
  try { await objectStorageAdminApi.updateSettings({ ...form }); showSuccess(t('adminPages.objectStorage.saved')) }
  catch (error) { showError(extractErrorMessage(error, t('adminPages.objectStorage.saveFailed'))) }
  finally { saving.value = false }
}
onMounted(load)
</script>
