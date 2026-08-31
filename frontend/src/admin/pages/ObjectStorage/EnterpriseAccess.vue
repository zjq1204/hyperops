<template>
  <AdminLayout>
    <PageFrame
      variant="soft"
      :title="t('adminPages.objectStorage.enterpriseAccessTitle')"
      :subtitle="t('adminPages.objectStorage.enterpriseAccessSubtitle')"
    >
      <AdminListSection>
        <template #toolbar>
          <div class="flex w-full flex-wrap items-center justify-between gap-3">
            <label class="min-w-[14rem] flex-1 sm:max-w-sm">
              <span class="sr-only">{{
                t('adminPages.objectStorage.selectTenant')
              }}</span>
              <select v-model="tenantId" class="admin-filter-control">
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
            </label>
            <div class="flex items-center gap-2">
              <BaseButton
                variant="outline"
                size="sm"
                :loading="loading"
                @click="load"
                >{{ t('common.refresh') }}</BaseButton
              >
              <BaseButton
                size="sm"
                :loading="saving"
                :disabled="!selectedTenant"
                @click="saveTenant"
                >{{ t('common.save') }}</BaseButton
              >
            </div>
          </div>
        </template>

        <AdminPageState
          :loading="loading"
          :error="error"
          :empty="!selectedTenant"
        >
          <section v-if="selectedTenant" class="grid gap-5 xl:grid-cols-2">
            <article class="admin-workbench-panel p-5">
              <div class="mb-5 border-b border-slate-200 pb-4">
                <h2 class="text-sm font-semibold text-slate-950">
                  {{ t('adminPages.objectStorage.enterprisePolicy') }}
                </h2>
                <p class="mt-1 text-xs text-slate-500">
                  {{ t('adminPages.objectStorage.enterprisePolicyHint') }}
                </p>
              </div>
              <div class="grid gap-4">
                <label class="admin-form-field"
                  ><span class="admin-form-label">{{
                    t('adminPages.objectStorage.tenantName')
                  }}</span
                  ><input
                    v-model="tenantForm.name"
                    class="admin-filter-control"
                    required
                /></label>
                <label class="admin-form-field"
                  ><span class="admin-form-label">{{
                    t('adminPages.objectStorage.namingTemplate')
                  }}</span
                  ><input
                    v-model="tenantForm.bucket_naming_template"
                    class="admin-filter-control font-mono"
                    required
                  /><small class="admin-form-hint">{{
                    t('adminPages.objectStorage.namingTemplateHint')
                  }}</small></label
                >
                <div class="grid gap-4 sm:grid-cols-2">
                  <label class="admin-form-field"
                    ><span class="admin-form-label">{{
                      t('adminPages.objectStorage.bucketQuota')
                    }}</span
                    ><input
                      v-model.number="tenantForm.default_bucket_quota"
                      class="admin-filter-control"
                      type="number"
                      min="1"
                  /></label>
                  <label class="admin-form-field"
                    ><span class="admin-form-label">{{
                      t('adminPages.objectStorage.deliveryLifetime')
                    }}</span
                    ><select
                      v-model.number="tenantForm.delivery_lifetime_seconds"
                      class="admin-filter-control"
                    >
                      <option :value="3600">
                        {{ t('adminPages.objectStorage.hours', { count: 1 }) }}
                      </option>
                      <option :value="86400">
                        {{ t('adminPages.objectStorage.days', { count: 1 }) }}
                      </option>
                      <option :value="604800">
                        {{ t('adminPages.objectStorage.days', { count: 7 }) }}
                      </option>
                    </select></label
                  >
                </div>
                <label class="flex items-center gap-3 text-sm text-slate-700"
                  ><input v-model="tenantForm.enabled" type="checkbox" />{{
                    t('adminPages.objectStorage.enableEmployeeAccess')
                  }}</label
                >
              </div>
            </article>

            <article class="admin-workbench-panel p-5">
              <div
                class="mb-5 flex items-start justify-between gap-3 border-b border-slate-200 pb-4"
              >
                <div>
                  <h2 class="text-sm font-semibold text-slate-950">
                    {{ t('adminPages.objectStorage.feishuTitle') }}
                  </h2>
                  <p class="mt-1 text-xs text-slate-500">
                    {{ t('adminPages.objectStorage.feishuHint') }}
                  </p>
                </div>
                <StatusBadge
                  :status="validationBadge(feishu?.validation_status)"
                />
              </div>
              <div class="grid gap-4">
                <label class="admin-form-field"
                  ><span class="admin-form-label">{{
                    t('adminPages.objectStorage.appId')
                  }}</span
                  ><input
                    v-model="feishuForm.app_id"
                    class="admin-filter-control"
                    autocomplete="off"
                /></label>
                <label class="admin-form-field"
                  ><span class="admin-form-label">{{
                    t('adminPages.objectStorage.appSecret')
                  }}</span
                  ><input
                    v-model="feishuForm.app_secret"
                    class="admin-filter-control"
                    type="password"
                    autocomplete="new-password"
                    :placeholder="t('adminPages.objectStorage.writeOnly')"
                  /><small class="admin-form-hint">{{
                    t('adminPages.objectStorage.secretNeverReturned')
                  }}</small></label
                >
                <label class="admin-form-field"
                  ><span class="admin-form-label">{{
                    t('adminPages.objectStorage.callbackUrl')
                  }}</span
                  ><input
                    v-model="feishuForm.oauth_callback_url"
                    class="admin-filter-control"
                    type="url"
                /></label>
                <div
                  class="flex flex-wrap items-center gap-2 border-t border-slate-200 pt-4"
                >
                  <BaseButton
                    size="sm"
                    variant="secondary"
                    :loading="savingFeishu"
                    @click="saveFeishu"
                    >{{ t('adminPages.objectStorage.saveFeishu') }}</BaseButton
                  ><BaseButton
                    size="sm"
                    variant="outline"
                    :loading="validatingFeishu"
                    :disabled="!feishu?.id"
                    @click="validateFeishu"
                    >{{ t('adminPages.objectStorage.validate') }}</BaseButton
                  ><span
                    v-if="feishu?.last_validated_at"
                    class="text-xs text-slate-500"
                    >{{
                      t('adminPages.objectStorage.validatedAt', {
                        date: formatDate(feishu.last_validated_at)
                      })
                    }}</span
                  >
                </div>
              </div>
            </article>

            <article class="admin-workbench-panel p-5 xl:col-span-2">
              <div
                class="mb-5 flex flex-wrap items-start justify-between gap-3 border-b border-slate-200 pb-4"
              >
                <div>
                  <h2 class="text-sm font-semibold text-slate-950">
                    {{ t('adminPages.objectStorage.aliyunTitle') }}
                  </h2>
                  <p class="mt-1 text-xs text-slate-500">
                    {{ t('adminPages.objectStorage.aliyunHint') }}
                  </p>
                </div>
                <StatusBadge
                  :status="validationBadge(pool?.validation_status)"
                />
              </div>
              <div class="grid gap-4 md:grid-cols-3">
                <label class="admin-form-field"
                  ><span class="admin-form-label">{{
                    t('adminPages.objectStorage.cloudAccount')
                  }}</span
                  ><input
                    v-model="poolForm.cloud_account_id"
                    class="admin-filter-control"
                /></label>
                <label class="admin-form-field"
                  ><span class="admin-form-label">{{
                    t('adminPages.objectStorage.region')
                  }}</span
                  ><input
                    v-model="poolForm.region"
                    class="admin-filter-control"
                /></label>
                <label class="admin-form-field"
                  ><span class="admin-form-label">{{
                    t('adminPages.objectStorage.managementAccessKey')
                  }}</span
                  ><input
                    v-model="poolForm.management_access_key"
                    class="admin-filter-control"
                    autocomplete="off"
                /></label>
                <label class="admin-form-field"
                  ><span class="admin-form-label">{{
                    t('adminPages.objectStorage.managementSecretKey')
                  }}</span
                  ><input
                    v-model="poolForm.management_secret_key"
                    class="admin-filter-control"
                    type="password"
                    autocomplete="new-password"
                    :placeholder="t('adminPages.objectStorage.writeOnly')"
                /></label>
              </div>
              <div
                class="mt-4 flex flex-wrap items-center gap-2 border-t border-slate-200 pt-4"
              >
                <BaseButton
                  size="sm"
                  variant="secondary"
                  :loading="savingPool"
                  @click="savePool"
                  >{{ t('adminPages.objectStorage.savePool') }}</BaseButton
                ><BaseButton
                  size="sm"
                  variant="outline"
                  :loading="validatingPool"
                  :disabled="!pool?.id"
                  @click="validatePool"
                  >{{ t('adminPages.objectStorage.validate') }}</BaseButton
                ><span
                  v-if="pool?.access_key_last_four"
                  class="text-xs text-slate-500"
                  >{{
                    t('adminPages.objectStorage.keyFingerprint', {
                      fingerprint: pool.credential_fingerprint,
                      lastFour: pool.access_key_last_four
                    })
                  }}</span
                >
              </div>
            </article>
          </section>
        </AdminPageState>
      </AdminListSection>
    </PageFrame>
  </AdminLayout>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
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
const route = useRoute()
const router = useRouter()
const tenants = ref([])
const tenantId = ref('')
const feishu = ref(null)
const pool = ref(null)
const loading = ref(false)
const saving = ref(false)
const savingFeishu = ref(false)
const savingPool = ref(false)
const validatingFeishu = ref(false)
const validatingPool = ref(false)
const error = ref('')
const tenantForm = reactive({
  name: '',
  bucket_naming_template: '',
  default_bucket_quota: 5,
  delivery_lifetime_seconds: 86400,
  enabled: true
})
const feishuForm = reactive({
  app_id: '',
  app_secret: '',
  oauth_callback_url: ''
})
const poolForm = reactive({
  cloud_account_id: '',
  region: '',
  management_access_key: '',
  management_secret_key: ''
})
const selectedTenant = computed(() =>
  tenants.value.find((item) => String(item.id) === String(tenantId.value))
)
const formatDate = (value) => formatDateIsoLocale(value, locale.value)
const validationBadge = (value) =>
  value === 'valid' ? 'success' : value === 'invalid' ? 'failed' : 'pending'
function hydrate() {
  if (!selectedTenant.value) return
  Object.assign(tenantForm, selectedTenant.value)
}
async function loadTenantData() {
  if (!tenantId.value) return
  feishu.value = null
  pool.value = null
  try {
    feishu.value = await objectStorageAdminApi.getFeishu(tenantId.value)
  } catch {
    feishu.value = null
  }
  const pools = await objectStorageAdminApi.listResourcePools(tenantId.value)
  pool.value = pools[0] || null
  hydrate()
  if (feishu.value)
    Object.assign(feishuForm, {
      app_id: feishu.value.app_id || '',
      app_secret: '',
      oauth_callback_url: feishu.value.oauth_callback_url || ''
    })
  if (pool.value)
    Object.assign(poolForm, {
      cloud_account_id: pool.value.cloud_account_id || '',
      region: pool.value.region || '',
      management_access_key: '',
      management_secret_key: ''
    })
}
async function load() {
  loading.value = true
  error.value = ''
  try {
    tenants.value = await objectStorageAdminApi.listTenants()
    const requested = route.query.tenant
    tenantId.value = String(requested || tenants.value[0]?.id || '')
    await loadTenantData()
  } catch (err) {
    error.value = err?.message || t('adminPages.objectStorage.loadFailed')
  } finally {
    loading.value = false
  }
}
async function saveTenant() {
  saving.value = true
  try {
    await objectStorageAdminApi.updateTenant(tenantId.value, tenantForm)
    showSuccess(t('adminPages.objectStorage.saved'))
    await load()
  } catch {
    showError(t('adminPages.objectStorage.saveFailed'))
  } finally {
    saving.value = false
  }
}
async function saveFeishu() {
  savingFeishu.value = true
  try {
    const body = { ...feishuForm }
    if (!body.app_secret) delete body.app_secret
    feishu.value = await objectStorageAdminApi.saveFeishu(tenantId.value, body)
    feishuForm.app_secret = ''
    showSuccess(t('adminPages.objectStorage.saved'))
  } catch {
    showError(t('adminPages.objectStorage.saveFailed'))
  } finally {
    savingFeishu.value = false
  }
}
async function validateFeishu() {
  validatingFeishu.value = true
  try {
    feishu.value = {
      ...feishu.value,
      ...(await objectStorageAdminApi.validateFeishu(tenantId.value))
    }
    showSuccess(t('adminPages.objectStorage.validated'))
  } catch {
    showError(t('adminPages.objectStorage.validationFailed'))
  } finally {
    validatingFeishu.value = false
  }
}
async function savePool() {
  savingPool.value = true
  try {
    const body = { ...poolForm }
    if (!body.management_access_key) delete body.management_access_key
    if (!body.management_secret_key) delete body.management_secret_key
    pool.value = pool.value?.id
      ? await objectStorageAdminApi.updateResourcePool(pool.value.id, body)
      : await objectStorageAdminApi.createResourcePool(tenantId.value, body)
    poolForm.management_access_key = ''
    poolForm.management_secret_key = ''
    showSuccess(t('adminPages.objectStorage.saved'))
  } catch {
    showError(t('adminPages.objectStorage.saveFailed'))
  } finally {
    savingPool.value = false
  }
}
async function validatePool() {
  validatingPool.value = true
  try {
    pool.value = {
      ...pool.value,
      ...(await objectStorageAdminApi.validateResourcePool(pool.value.id))
    }
    showSuccess(t('adminPages.objectStorage.validated'))
  } catch {
    showError(t('adminPages.objectStorage.validationFailed'))
  } finally {
    validatingPool.value = false
  }
}
watch(tenantId, async (value) => {
  if (value) {
    await router.replace({ query: { tenant: value } })
    await loadTenantData()
  }
})
onMounted(load)
</script>
