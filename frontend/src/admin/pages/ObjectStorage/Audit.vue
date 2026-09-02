<template>
  <AdminLayout>
    <PageFrame variant="soft" :title="t('adminPages.objectStorage.auditTitle')" :subtitle="t('adminPages.objectStorage.auditSubtitle')">
      <AdminListSection>
        <template #toolbarStart><input v-model.trim="action" class="admin-filter-control min-w-56" :placeholder="t('adminPages.objectStorage.auditAction')" @keyup.enter="load" /><select v-model="result" class="admin-filter-control min-w-40"><option value="">{{ t('adminPages.objectStorage.allResults') }}</option><option v-for="item in results" :key="item" :value="item">{{ resultLabel(item) }}</option></select></template>
        <template #toolbarEnd><span class="admin-summary-pill">{{ t('adminPages.objectStorage.count', { count: events.length }) }}</span><BaseButton variant="outline" size="sm" :loading="loading" @click="load">{{ t('common.refresh') }}</BaseButton></template>
        <AdminPageState :loading="loading" :error="error" :empty="!events.length" :empty-title="t('adminPages.objectStorage.noAuditEvents')">
          <div class="admin-workbench-panel overflow-hidden"><div class="overflow-x-auto"><table class="admin-table"><thead><tr><th class="admin-table-head">{{ t('adminPages.objectStorage.createdAt') }}</th><th class="admin-table-head">{{ t('adminPages.objectStorage.auditAction') }}</th><th class="admin-table-head">{{ t('adminPages.objectStorage.actor') }}</th><th class="admin-table-head">{{ t('adminPages.objectStorage.target') }}</th><th class="admin-table-head">{{ t('adminPages.objectStorage.result') }}</th><th class="admin-table-head">{{ t('adminPages.objectStorage.reason') }}</th></tr></thead><tbody><tr v-for="event in events" :key="event.id" class="admin-table-row"><td class="admin-table-cell whitespace-nowrap text-sm">{{ formatDate(event.created_at) }}</td><td class="admin-table-cell"><p class="font-medium text-slate-900">{{ actionLabel(event.action) }}</p><p class="mt-1 font-mono text-xs text-slate-500">{{ event.request_id }}</p></td><td class="admin-table-cell">{{ event.actor_name_snapshot || t('adminPages.objectStorage.systemActor') }}</td><td class="admin-table-cell"><p>{{ event.target_type }}</p><p class="mt-1 text-xs text-slate-500">#{{ event.target_id }}</p></td><td class="admin-table-cell"><StatusBadge :status="resultStatus(event.result)" /></td><td class="admin-table-cell max-w-72 whitespace-normal text-sm text-slate-600">{{ event.reason || t('common.emptyValue') }}</td></tr></tbody></table></div></div>
        </AdminPageState>
      </AdminListSection>
    </PageFrame>
  </AdminLayout>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import AdminLayout from '@/admin/layout/AdminLayout.vue'
import AdminListSection from '@/admin/components/AdminListSection.vue'
import AdminPageState from '@/admin/components/AdminPageState.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import PageFrame from '@/components/ui/PageFrame.vue'
import StatusBadge from '@/components/ui/StatusBadge.vue'
import { extractErrorMessage } from '@/utils/api'
import objectStorageAdminApi from '@/admin/api/objectStorage'

const { t, locale } = useI18n(); const events = ref([]); const loading = ref(true); const error = ref(''); const action = ref(''); const result = ref(''); const results = ['accepted', 'succeeded', 'failed', 'cancelled']
const formatDate = (value) => value ? new Intl.DateTimeFormat(locale.value, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value)) : t('common.emptyValue')
const resultLabel = (value) => t(`adminPages.objectStorage.results.${value}`, value)
const actionLabel = (value) => t(`adminPages.objectStorage.auditActions.${String(value || '').replaceAll('.', '_')}`, value || t('common.emptyValue'))
const resultStatus = (value) => ['accepted', 'succeeded'].includes(value) ? 'success' : value === 'failed' ? 'failed' : 'pending'
async function load() { loading.value = true; error.value = ''; try { events.value = await objectStorageAdminApi.listAuditEvents({ action: action.value || undefined, result: result.value || undefined }) } catch (err) { error.value = extractErrorMessage(err, t('adminPages.objectStorage.loadFailed')) } finally { loading.value = false } }
onMounted(load)
</script>
