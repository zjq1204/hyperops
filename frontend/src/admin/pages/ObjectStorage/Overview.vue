<template>
  <AdminLayout>
    <PageFrame variant="soft" :title="t('adminPages.objectStorage.title')" :subtitle="t('adminPages.objectStorage.overviewSubtitle')">
      <AdminListSection>
        <template #toolbarEnd><BaseButton variant="outline" size="sm" :loading="loading" @click="load">{{ t('common.refresh') }}</BaseButton></template>
        <AdminPageState :loading="loading" :error="error">
          <section class="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <article v-for="stat in stats" :key="stat.key" class="admin-workbench-panel p-5"><p class="text-xs font-semibold text-slate-500">{{ t(stat.label) }}</p><p class="mt-3 text-3xl font-semibold tabular-nums text-slate-950">{{ stat.value }}</p></article>
          </section>
          <section class="mt-5 grid gap-5 lg:grid-cols-[minmax(0,1.2fr)_minmax(18rem,0.8fr)]">
            <article class="admin-workbench-panel overflow-hidden">
              <div class="border-b border-slate-200 px-5 py-4">
                <h2 class="text-sm font-semibold text-slate-950">{{ t('adminPages.objectStorage.platformState') }}</h2>
              </div>
              <dl class="divide-y divide-slate-200">
                <div
                  v-for="detail in platformDetails"
                  :key="detail.key"
                  class="grid gap-1 px-5 py-3.5 sm:grid-cols-[9rem_minmax(0,1fr)] sm:items-start sm:gap-5"
                >
                  <dt class="text-sm text-slate-500">{{ t(detail.label) }}</dt>
                  <dd
                    class="min-w-0 text-sm font-medium text-slate-900"
                    :class="detail.mono ? 'break-all font-mono' : 'break-words'"
                  >
                    {{ detail.value ?? '-' }}
                  </dd>
                </div>
              </dl>
            </article>
            <article class="admin-workbench-panel overflow-hidden"><div class="border-b border-slate-200 px-5 py-4"><h2 class="text-sm font-semibold text-slate-950">{{ t('adminPages.objectStorage.quickLinksTitle') }}</h2></div><div class="divide-y divide-slate-200"><router-link v-for="link in links" :key="link.to" :to="link.to" class="flex min-h-12 items-center justify-between px-5 text-sm font-medium text-slate-700 hover:text-sky-700">{{ t(link.label) }}<span aria-hidden="true">→</span></router-link></div></article>
          </section>
        </AdminPageState>
      </AdminListSection>
    </PageFrame>
  </AdminLayout>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import AdminLayout from '@/admin/layout/AdminLayout.vue'
import AdminListSection from '@/admin/components/AdminListSection.vue'
import AdminPageState from '@/admin/components/AdminPageState.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import PageFrame from '@/components/ui/PageFrame.vue'
import { extractErrorMessage } from '@/utils/api'
import objectStorageAdminApi from '@/admin/api/objectStorage'

const { t } = useI18n(); const settings = ref(null); const pools = ref([]); const buckets = ref([]); const keys = ref([]); const applications = ref([]); const loading = ref(true); const error = ref('')
const enabledPool = computed(() => pools.value.find((pool) => pool.enabled))
const stats = computed(() => [
  { key: 'buckets', value: buckets.value.length, label: 'adminPages.objectStorage.bucketCount' },
  { key: 'keys', value: keys.value.length, label: 'adminPages.objectStorage.keyCount' },
  { key: 'applications', value: applications.value.filter((item) => ['pending', 'running', 'manual_required'].includes(item.status)).length, label: 'adminPages.objectStorage.pendingCount' },
  { key: 'pools', value: pools.value.filter((pool) => pool.enabled).length, label: 'adminPages.objectStorage.poolCount' }
])
const platformDetails = computed(() => [
  { key: 'pool', label: 'adminPages.objectStorage.enabledPool', value: enabledPool.value ? `${enabledPool.value.cloud_account_id} · ${enabledPool.value.region}` : t('adminPages.objectStorage.noPool') },
  { key: 'template', label: 'adminPages.objectStorage.namingTemplate', value: settings.value?.naming_template, mono: true },
  { key: 'quota', label: 'adminPages.objectStorage.bucketQuota', value: settings.value?.default_bucket_quota },
  { key: 'retention', label: 'adminPages.objectStorage.auditRetention', value: t('adminPages.objectStorage.days', { count: settings.value?.audit_retention_days || 0 }) }
])
const links = [{ to: '/management/object-storage/settings', label: 'adminPages.objectStorage.settingsTitle' }, { to: '/management/object-storage/buckets', label: 'adminPages.objectStorage.bucketsTitle' }, { to: '/management/object-storage/access-keys', label: 'adminPages.objectStorage.accessKeysTitle' }, { to: '/management/object-storage/applications', label: 'adminPages.objectStorage.applicationsTitle' }]
async function load() { loading.value = true; error.value = ''; try { [settings.value, pools.value, buckets.value, keys.value, applications.value] = await Promise.all([objectStorageAdminApi.getSettings(), objectStorageAdminApi.listResourcePools(), objectStorageAdminApi.listBuckets(), objectStorageAdminApi.listAccessKeys(), objectStorageAdminApi.listApplications()]) } catch (err) { error.value = extractErrorMessage(err, t('adminPages.objectStorage.loadFailed')) } finally { loading.value = false } }
onMounted(load)
</script>
