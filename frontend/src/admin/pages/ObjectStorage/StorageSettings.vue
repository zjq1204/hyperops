<template>
  <AdminLayout>
    <PageFrame
      variant="soft"
      :title="t('adminPages.objectStorage.connectionTitle')"
      :subtitle="t('adminPages.objectStorage.connectionSubtitle')"
    >
      <AdminListSection>
        <template #toolbarEnd>
          <BaseButton variant="outline" size="sm" :loading="loading" @click="load">
            {{ t('common.refresh') }}
          </BaseButton>
        </template>

        <AdminPageState :loading="loading" :error="loadError">
          <section class="admin-workbench-panel overflow-hidden p-0">
            <div class="border-b border-slate-200/80 px-5 py-4 sm:px-6">
              <div class="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <h2 class="text-base font-semibold text-slate-950">
                    {{ t('adminPages.objectStorage.connectionSection') }}
                  </h2>
                  <p class="mt-1 max-w-3xl text-sm leading-6 text-slate-500">
                    {{ t('adminPages.objectStorage.connectionPageHint') }}
                  </p>
                </div>
                <StatusBadge :status="currentPool ? statusBadge(currentPool.validation_status, currentPool.enabled) : 'pending'" />
              </div>
            </div>

            <div class="px-5 py-5 sm:px-6">
              <div class="admin-settings-group">
                <h2 class="admin-settings-title">
                  {{ t('adminPages.objectStorage.provider') }}
                </h2>
                <div class="admin-settings-row">
                  <div class="admin-settings-row-main">
                    <h3 class="admin-settings-row-title">
                      {{ t('adminPages.objectStorage.provider') }}
                    </h3>
                    <p class="admin-settings-row-copy">
                      {{ t('adminPages.objectStorage.providerHint') }}
                    </p>
                  </div>
                  <div class="admin-settings-row-control">
                    <span class="text-sm font-medium text-slate-900">
                      {{ t('adminPages.objectStorage.providerName') }}
                    </span>
                  </div>
                </div>
              </div>

              <div class="admin-settings-group mt-8 border-t border-slate-200/70 pt-5">
                <div class="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <h2 class="admin-settings-title mb-0">
                      {{ t('adminPages.objectStorage.poolsTitle') }}
                    </h2>
                    <p class="mt-1 max-w-3xl text-sm leading-6 text-slate-500">
                      {{ t('adminPages.objectStorage.poolsHint') }}
                    </p>
                  </div>
                  <BaseButton size="sm" variant="outline" @click="showPoolForm = !showPoolForm">
                    {{ showPoolForm ? t('common.cancel') : t('adminPages.objectStorage.addPool') }}
                  </BaseButton>
                </div>

                <div v-if="showPoolForm" class="mt-5 grid gap-4 border-y border-slate-200/70 bg-slate-50/60 py-5 sm:grid-cols-2">
                  <label class="admin-form-field">
                    <span class="admin-form-label">{{ t('adminPages.objectStorage.accountId') }}</span>
                    <input v-model.trim="poolForm.cloud_account_id" class="admin-filter-control" required />
                  </label>
                  <label class="admin-form-field">
                    <span class="admin-form-label">{{ t('adminPages.objectStorage.region') }}</span>
                    <input v-model.trim="poolForm.region" class="admin-filter-control" required />
                  </label>
                  <label class="admin-form-field">
                    <span class="admin-form-label">{{ t('adminPages.objectStorage.managementAccessKey') }}</span>
                    <input v-model="poolForm.management_access_key" class="admin-filter-control font-mono" autocomplete="off" required />
                  </label>
                  <label class="admin-form-field">
                    <span class="admin-form-label">{{ t('adminPages.objectStorage.managementSecretKey') }}</span>
                    <input v-model="poolForm.management_secret_key" class="admin-filter-control font-mono" type="password" autocomplete="new-password" required />
                  </label>
                  <div class="flex items-center justify-end gap-2 sm:col-span-2">
                    <BaseButton type="button" variant="outline" @click="showPoolForm = false">
                      {{ t('common.cancel') }}
                    </BaseButton>
                    <BaseButton type="button" :loading="poolSaving" @click="createPool">
                      {{ t('adminPages.objectStorage.savePool') }}
                    </BaseButton>
                  </div>
                </div>

                <div v-if="pools.length" class="mt-5 divide-y divide-slate-200 border-y border-slate-200/70">
                  <div v-for="pool in pools" :key="pool.id" class="grid gap-3 py-4 sm:grid-cols-[minmax(0,1fr)_minmax(10rem,0.7fr)_auto] sm:items-center">
                    <div>
                      <p class="font-medium text-slate-900">{{ pool.cloud_account_id }}</p>
                      <p class="mt-1 text-xs text-slate-500">
                        {{ t('adminPages.objectStorage.providerName') }} · {{ pool.region }} · {{ t('adminPages.objectStorage.keyEnding', { value: pool.access_key_last_four }) }}
                      </p>
                    </div>
                    <StatusBadge :status="statusBadge(pool.validation_status, pool.enabled)" />
                    <BaseButton size="sm" variant="outline" :loading="validatingPool === pool.id" @click="validatePool(pool)">
                      {{ t('adminPages.objectStorage.validate') }}
                    </BaseButton>
                  </div>
                </div>
                <EmptyState v-else variant="admin" :title="t('adminPages.objectStorage.noPool')" :description="t('adminPages.objectStorage.noPoolHint')" />
              </div>
            </div>
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
const poolSaving = ref(false)
const validatingPool = ref(null)
const loadError = ref('')
const pools = ref([])
const showPoolForm = ref(false)
const poolForm = reactive({ cloud_account_id: '', region: '', management_access_key: '', management_secret_key: '' })
const currentPool = computed(() => pools.value.find((pool) => pool.enabled))
const statusBadge = (status, enabled) => enabled ? 'success' : status === 'invalid' ? 'failed' : 'pending'

async function load() {
  loading.value = true
  loadError.value = ''
  try {
    pools.value = await objectStorageAdminApi.listResourcePools()
  } catch (error) {
    loadError.value = extractErrorMessage(error, t('adminPages.objectStorage.loadFailed'))
  } finally {
    loading.value = false
  }
}

async function createPool() {
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
