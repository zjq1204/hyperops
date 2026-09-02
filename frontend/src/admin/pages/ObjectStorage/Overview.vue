<template>
  <AdminLayout>
    <PageFrame variant="soft" :title="t('adminPages.objectStorage.title')" :subtitle="t('adminPages.objectStorage.overviewSubtitle')">
      <AdminListSection>
        <template #toolbarEnd><BaseButton variant="outline" size="sm" :loading="loading" @click="load">{{ t('common.refresh') }}</BaseButton></template>
        <AdminPageState :loading="loading" :error="error">
          <InlineAlert v-if="settings?.pause_new_applications" class="mb-5" variant="warning" :message="t('adminPages.objectStorage.applicationsPaused')" />
          <section class="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <article v-for="stat in stats" :key="stat.key" class="admin-workbench-panel p-5"><p class="text-xs font-semibold text-slate-500">{{ t(stat.label) }}</p><p class="mt-3 text-3xl font-semibold tabular-nums text-slate-950">{{ stat.value }}</p><p class="mt-1 text-xs text-slate-500">{{ t(stat.hint) }}</p></article>
          </section>
          <section class="mt-5 grid gap-5 lg:grid-cols-[minmax(0,1.2fr)_minmax(18rem,0.8fr)]">
            <article class="admin-workbench-panel overflow-hidden"><div class="border-b border-slate-200 px-5 py-4"><h2 class="text-sm font-semibold text-slate-950">{{ t('adminPages.objectStorage.platformState') }}</h2><p class="mt-1 text-xs leading-5 text-slate-500">{{ t('adminPages.objectStorage.platformStateHint') }}</p></div><dl class="grid gap-4 p-5 sm:grid-cols-2"><InfoCell :label="t('adminPages.objectStorage.enabledPool')" :value="enabledPool ? `${enabledPool.cloud_account_id} · ${enabledPool.region}` : t('adminPages.objectStorage.noPool')" /><InfoCell :label="t('adminPages.objectStorage.namingTemplate')" :value="settings?.naming_template" /><InfoCell :label="t('adminPages.objectStorage.bucketQuota')" :value="settings?.default_bucket_quota" /><InfoCell :label="t('adminPages.objectStorage.auditRetention')" :value="`${settings?.audit_retention_days || '-'} days`" /></dl></article>
            <article class="admin-workbench-panel overflow-hidden"><div class="border-b border-slate-200 px-5 py-4"><h2 class="text-sm font-semibold text-slate-950">{{ t('adminPages.objectStorage.quickLinksTitle') }}</h2></div><div class="divide-y divide-slate-200"><router-link v-for="link in links" :key="link.to" :to="link.to" class="flex min-h-12 items-center justify-between px-5 text-sm font-medium text-slate-700 hover:text-sky-700">{{ t(link.label) }}<span aria-hidden="true">→</span></router-link></div></article>
          </section>
        </AdminPageState>
      </AdminListSection>
    </PageFrame>
  </AdminLayout>
</template>

<script setup>
import { computed, defineComponent, h, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import AdminLayout from '@/admin/layout/AdminLayout.vue'
import AdminListSection from '@/admin/components/AdminListSection.vue'
import AdminPageState from '@/admin/components/AdminPageState.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import InlineAlert from '@/components/ui/InlineAlert.vue'
import PageFrame from '@/components/ui/PageFrame.vue'
import { extractErrorMessage } from '@/utils/api'
import objectStorageAdminApi from '@/admin/api/objectStorage'

const { t } = useI18n(); const settings = ref(null); const pools = ref([]); const buckets = ref([]); const keys = ref([]); const applications = ref([]); const loading = ref(true); const error = ref('')
const enabledPool = computed(() => pools.value.find((pool) => pool.enabled))
const stats = computed(() => [
  { key: 'buckets', value: buckets.value.length, label: 'adminPages.objectStorage.bucketCount', hint: 'adminPages.objectStorage.bucketCountHint' },
  { key: 'keys', value: keys.value.length, label: 'adminPages.objectStorage.keyCount', hint: 'adminPages.objectStorage.keyCountHint' },
  { key: 'applications', value: applications.value.filter((item) => ['pending', 'running', 'manual_required'].includes(item.status)).length, label: 'adminPages.objectStorage.pendingCount', hint: 'adminPages.objectStorage.pendingCountHint' },
  { key: 'pools', value: pools.value.filter((pool) => pool.enabled).length, label: 'adminPages.objectStorage.poolCount', hint: 'adminPages.objectStorage.poolCountHint' }
])
const links = [{ to: '/management/object-storage/settings', label: 'adminPages.objectStorage.settingsTitle' }, { to: '/management/object-storage/buckets', label: 'adminPages.objectStorage.bucketsTitle' }, { to: '/management/object-storage/access-keys', label: 'adminPages.objectStorage.accessKeysTitle' }, { to: '/management/object-storage/applications', label: 'adminPages.objectStorage.applicationsTitle' }]
const InfoCell = defineComponent({ props: { label: String, value: [String, Number] }, setup: (props) => () => h('div', [h('dt', { class: 'text-xs font-medium text-slate-500' }, props.label), h('dd', { class: 'mt-1 break-all text-sm font-medium text-slate-900' }, props.value || '-')]) })
async function load() { loading.value = true; error.value = ''; try { [settings.value, pools.value, buckets.value, keys.value, applications.value] = await Promise.all([objectStorageAdminApi.getSettings(), objectStorageAdminApi.listResourcePools(), objectStorageAdminApi.listBuckets(), objectStorageAdminApi.listAccessKeys(), objectStorageAdminApi.listApplications()]) } catch (err) { error.value = extractErrorMessage(err, t('adminPages.objectStorage.loadFailed')) } finally { loading.value = false } }
onMounted(load)
</script>
