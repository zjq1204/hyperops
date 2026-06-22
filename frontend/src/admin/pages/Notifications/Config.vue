<template>
  <AdminLayout>
    <PageFrame
      variant="soft"
      :title="t('notificationManagement.settings.title')"
      :subtitle="t('notificationManagement.settings.subtitle')"
    >
      <section class="admin-workbench-panel">
        <BaseLoading v-if="loading" />
        <div v-else class="admin-settings-group">
          <h2 class="admin-settings-title">
            {{ t('notificationManagement.settings.scheduleSection') }}
          </h2>

          <section class="admin-settings-row">
            <div class="admin-settings-row-main">
              <h3 class="admin-settings-row-title">
                {{ t('notificationManagement.settings.retentionTitle') }}
              </h3>
              <p class="admin-settings-row-copy">
                {{ t('notificationManagement.settings.retentionDesc') }}
              </p>
            </div>
            <div class="admin-settings-row-control">
              <input
                v-model.number="form.retention_days"
                type="number"
                min="1"
                max="3650"
                :placeholder="
                  t('notificationManagement.settings.retentionDaysPlaceholder')
                "
                class="admin-modal-control w-24"
              />
              <span class="admin-settings-unit">
                {{ t('notificationManagement.settings.daysUnit') }}
              </span>
            </div>
          </section>

          <section class="admin-settings-row">
            <div class="admin-settings-row-main">
              <h3 class="admin-settings-row-title">
                {{ t('notificationManagement.settings.cleanupTitle') }}
              </h3>
              <p class="admin-settings-row-copy">
                {{ t('notificationManagement.settings.cleanupDesc') }}
              </p>
            </div>
            <div class="admin-settings-row-control">
              <label class="admin-modal-toggle">
                <input
                  v-model="form.cleanup_enabled"
                  type="checkbox"
                  class="admin-modal-checkbox"
                />
                <span class="text-sm font-medium text-slate-700">
                  {{
                    form.cleanup_enabled
                      ? t('common.enabled')
                      : t('common.disabled')
                  }}
                </span>
              </label>
            </div>
          </section>

          <section class="admin-settings-row">
            <div class="admin-settings-row-main">
              <label class="admin-settings-row-title">
                {{ t('notificationManagement.settings.cleanupCrontab') }}
              </label>
              <p class="admin-settings-row-copy">
                {{ t('notificationManagement.settings.crontabHelp') }}
              </p>
            </div>
            <div class="admin-settings-row-control">
              <input
                v-model="form.cleanup_crontab"
                type="text"
                :placeholder="
                  t('notificationManagement.settings.cleanupCrontabPlaceholder')
                "
                :disabled="!form.cleanup_enabled"
                class="admin-modal-control font-mono"
              />
            </div>
          </section>

          <div class="admin-settings-actions">
            <BaseButton
              variant="secondary"
              size="sm"
              :disabled="saving"
              @click="resetForm"
            >
              {{ t('notificationManagement.settings.reset') }}
            </BaseButton>
            <BaseButton
              variant="primary"
              size="sm"
              :loading="saving"
              @click="saveConfig"
            >
              {{ t('notificationManagement.settings.saveChanges') }}
            </BaseButton>
          </div>
          <p
            v-if="saveError"
            class="admin-settings-feedback admin-settings-feedback--error"
          >
            {{ saveError }}
          </p>
          <p
            v-if="saveSuccess"
            class="admin-settings-feedback admin-settings-feedback--success"
          >
            {{ t('notificationManagement.settings.saveSuccess') }}
          </p>
        </div>
      </section>
    </PageFrame>
  </AdminLayout>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useToast } from '@/composables/useToast'
import { notificationsAdminApi } from '@/admin/api'
import AdminLayout from '@/admin/layout/AdminLayout.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseLoading from '@/components/ui/BaseLoading.vue'
import PageFrame from '@/components/ui/PageFrame.vue'

const { t } = useI18n()
const { showSuccess, showError } = useToast()
const loading = ref(false)
const saving = ref(false)
const saveError = ref('')
const saveSuccess = ref(false)

const form = reactive({
  retention_days: 180,
  cleanup_enabled: true,
  cleanup_crontab: '0 2 * * *'
})

const initialValues = reactive({
  retention_days: 180,
  cleanup_enabled: true,
  cleanup_crontab: '0 2 * * *'
})

function resetForm() {
  form.retention_days = initialValues.retention_days
  form.cleanup_enabled = initialValues.cleanup_enabled
  form.cleanup_crontab = initialValues.cleanup_crontab
  saveError.value = ''
  saveSuccess.value = false
}

function assignFromValue(raw) {
  if (!raw || typeof raw !== 'object') return
  const rd = raw.retention_days
  form.retention_days = typeof rd === 'number' && rd > 0 ? rd : 180
  form.cleanup_enabled = raw.cleanup_enabled !== false
  form.cleanup_crontab =
    typeof raw.cleanup_crontab === 'string' && raw.cleanup_crontab.trim()
      ? raw.cleanup_crontab.trim()
      : '0 2 * * *'
  initialValues.retention_days = form.retention_days
  initialValues.cleanup_enabled = form.cleanup_enabled
  initialValues.cleanup_crontab = form.cleanup_crontab
}

async function load() {
  loading.value = true
  saveError.value = ''
  saveSuccess.value = false
  try {
    const data = await notificationsAdminApi.getGlobalConfig()
    const raw = data?.value
    assignFromValue(raw)
  } catch {
    assignFromValue(null)
  } finally {
    loading.value = false
  }
}

async function saveConfig() {
  saveError.value = ''
  saveSuccess.value = false
  const value = {
    retention_days: Math.max(
      1,
      Math.min(3650, Number(form.retention_days) || 180)
    ),
    cleanup_enabled: !!form.cleanup_enabled,
    cleanup_crontab: (form.cleanup_crontab || '').trim() || '0 2 * * *'
  }
  saving.value = true
  try {
    await notificationsAdminApi.putGlobalConfig(value)
    initialValues.retention_days = value.retention_days
    initialValues.cleanup_enabled = value.cleanup_enabled
    initialValues.cleanup_crontab = value.cleanup_crontab
    saveSuccess.value = true
    showSuccess(t('notificationManagement.settings.saveSuccess'))
    setTimeout(() => {
      saveSuccess.value = false
    }, 3000)
  } catch (e) {
    const detail = e?.response?.data?.data?.detail ?? e?.response?.data?.detail
    saveError.value =
      detail || e?.message || t('notificationManagement.settings.saveFailed')
    showError(saveError.value)
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  load()
})
</script>
