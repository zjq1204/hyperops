<template>
  <AdminLayout>
    <PageFrame
      variant="soft"
      :title="t('adminPages.authentication.feishuConfigTitle')"
      :subtitle="t('adminPages.authentication.feishuConfigSubtitle')"
    >
      <template #actions>
        <RouterLink
          class="text-sm font-medium text-sky-700 hover:text-sky-900"
          to="/management/authentication"
        >
          {{ t('adminPages.authentication.backToSources') }}
        </RouterLink>
      </template>

      <AdminListSection>
        <AdminPageState
          :loading="loading"
          :error="error"
          :empty="false"
          :empty-title="t('adminPages.authentication.emptyTitle')"
          :empty-description="t('adminPages.authentication.emptyDescription')"
        >
          <form
            v-if="true"
            class="admin-workbench-panel p-5"
            @submit.prevent="saveFeishu"
          >
            <div
              class="mb-6 flex flex-wrap items-start justify-between gap-4 border-b border-slate-200 pb-5"
            >
              <div>
                <p class="text-xs font-semibold text-sky-700">
                  {{ t('adminPages.authentication.platformSource') }}
                </p>
                <h2 class="mt-1 text-base font-semibold text-slate-950">
                  {{ t('adminPages.authentication.feishuTitle') }}
                </h2>
                <p class="mt-1 max-w-2xl text-sm leading-6 text-slate-500">
                  {{ t('adminPages.authentication.feishuHint') }}
                </p>
              </div>
              <StatusBadge
                :status="validationBadge(feishu?.validation_status)"
              />
            </div>

            <div class="grid gap-5 sm:grid-cols-2">
              <div class="space-y-1.5">
                <label
                  for="feishu-app-id"
                  class="block text-sm font-medium text-slate-800"
                >
                  {{ t('adminPages.objectStorage.appId') }}
                </label>
                <input
                  id="feishu-app-id"
                  v-model.trim="form.app_id"
                  class="admin-filter-control block w-full rounded-md"
                  autocomplete="off"
                  required
                />
              </div>
              <div class="space-y-1.5">
                <label
                  for="feishu-app-secret"
                  class="block text-sm font-medium text-slate-800"
                >
                  {{ t('adminPages.objectStorage.appSecret') }}
                </label>
                <input
                  id="feishu-app-secret"
                  v-model="form.app_secret"
                  class="admin-filter-control block w-full rounded-md"
                  type="password"
                  autocomplete="new-password"
                  :required="!feishu?.id"
                  :placeholder="t('adminPages.objectStorage.writeOnly')"
                />
                <p class="text-xs leading-5 text-slate-500">
                  {{ t('adminPages.objectStorage.secretNeverReturned') }}
                </p>
              </div>
              <div class="space-y-1.5 sm:col-span-2">
                <label
                  for="feishu-callback"
                  class="block text-sm font-medium text-slate-800"
                >
                  {{ t('adminPages.objectStorage.callbackUrl') }}
                </label>
                <input
                  id="feishu-callback"
                  v-model.trim="form.oauth_callback_url"
                  class="admin-filter-control block w-full rounded-md"
                  type="url"
                  required
                />
              </div>
            </div>

            <section class="mt-7 border-t border-slate-200 pt-6">
              <div class="mb-4">
                <h3 class="text-sm font-semibold text-slate-950">
                  {{ t('adminPages.authentication.accessGroupTitle') }}
                </h3>
                <p class="mt-1 text-xs leading-5 text-slate-500">
                  {{ t('adminPages.authentication.accessGroupHint') }}
                </p>
              </div>
              <div class="max-w-xl space-y-1.5">
                <label
                  for="feishu-access-group"
                  class="block text-sm font-medium text-slate-800"
                >
                  {{ t('adminPages.authentication.accessGroup') }}
                </label>
                <select
                  id="feishu-access-group"
                  v-model="form.access_group"
                  class="admin-filter-control block w-full rounded-md"
                  required
                >
                  <option value="">
                    {{ t('adminPages.authentication.selectAccessGroup') }}
                  </option>
                  <option
                    v-for="group in groups"
                    :key="group.id"
                    :value="String(group.id)"
                  >
                    {{ group.name }}
                  </option>
                </select>
                <p class="text-xs leading-5 text-slate-500">
                  {{ t('adminPages.authentication.accessGroupRoleHint') }}
                  <RouterLink
                    class="ml-1 font-medium text-sky-700 hover:text-sky-900"
                    to="/management/groups"
                  >
                    {{ t('adminPages.authentication.manageGroups') }}
                  </RouterLink>
                </p>
              </div>
            </section>

            <div
              class="mt-6 flex flex-wrap items-center gap-2 border-t border-slate-200 pt-4"
            >
              <BaseButton variant="secondary" type="submit" :loading="saving">
                {{ feishuActionLabel }}
              </BaseButton>
              <BaseButton
                variant="outline"
                type="button"
                :loading="validating"
                :disabled="!feishu?.id"
                @click="validateFeishu"
              >
                {{ t('adminPages.authentication.validate') }}
              </BaseButton>
              <span
                v-if="feishu?.last_validated_at"
                class="text-xs text-slate-500"
              >
                {{
                  t('adminPages.objectStorage.validatedAt', {
                    date: formatDate(feishu.last_validated_at)
                  })
                }}
              </span>
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
import PageFrame from '@/components/ui/PageFrame.vue'
import StatusBadge from '@/components/ui/StatusBadge.vue'
import { useToast } from '@/composables/useToast'
import { formatDateIsoLocale } from '@/utils/formatting'
import objectStorageAdminApi from '@/admin/api/objectStorage'

const { t, locale } = useI18n()
const { showSuccess, showError } = useToast()
const feishu = ref(null)
const loading = ref(false)
const saving = ref(false)
const validating = ref(false)
const groups = ref([])
const error = ref('')
const form = reactive({
  app_id: '',
  app_secret: '',
  oauth_callback_url: '',
  access_group: ''
})
const feishuActionLabel = computed(() => {
  if (!feishu.value?.id) return t('adminPages.authentication.startSetup')
  if (feishu.value.validation_status === 'invalid') {
    return t('adminPages.authentication.fixConfiguration')
  }
  if (feishu.value.validation_status === 'valid') {
    return t('adminPages.authentication.manageConfiguration')
  }
  return t('adminPages.authentication.continueSetup')
})
const validationBadge = (value) =>
  value === 'valid' ? 'success' : value === 'invalid' ? 'failed' : 'pending'
const formatDate = (value) => formatDateIsoLocale(value, locale.value)

async function load() {
  loading.value = true
  error.value = ''
  try {
    const [config, groupList] = await Promise.all([
      objectStorageAdminApi.getFeishu(),
      objectStorageAdminApi.listAccessGroups()
    ])
    feishu.value = config
    groups.value = groupList
    if (config) {
      Object.assign(form, {
        app_id: config.app_id || '',
        oauth_callback_url: config.oauth_callback_url || '',
        access_group: config.access_group ? String(config.access_group) : ''
      })
    }
  } catch (requestError) {
    error.value =
      requestError?.response?.data?.detail ||
      requestError?.message ||
      t('adminPages.authentication.loadFailed')
  } finally {
    loading.value = false
  }
}

async function saveFeishu() {
  saving.value = true
  try {
    const body = { ...form }
    if (!body.app_secret) delete body.app_secret
    feishu.value = await objectStorageAdminApi.saveFeishu(body)
    form.app_secret = ''
    showSuccess(t('adminPages.authentication.saved'))
  } catch {
    showError(t('adminPages.authentication.saveFailed'))
  } finally {
    saving.value = false
  }
}

async function validateFeishu() {
  validating.value = true
  try {
    feishu.value = {
      ...feishu.value,
      ...(await objectStorageAdminApi.validateFeishu())
    }
    showSuccess(t('adminPages.authentication.validated'))
  } catch {
    showError(t('adminPages.authentication.validationFailed'))
  } finally {
    validating.value = false
  }
}

onMounted(load)
</script>
