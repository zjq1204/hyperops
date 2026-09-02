<template>
  <AdminLayout>
    <PageFrame variant="soft" :title="t('adminPages.objectStorage.applicationsTitle')" :subtitle="t('adminPages.objectStorage.applicationsSubtitle')">
      <AdminListSection>
        <template #toolbarStart><select v-model="statusFilter" class="admin-filter-control min-w-44"><option value="">{{ t('adminPages.objectStorage.allStatuses') }}</option><option v-for="status in statuses" :key="status" :value="status">{{ statusLabel(status) }}</option></select></template>
        <template #toolbarEnd><span class="admin-summary-pill">{{ t('adminPages.objectStorage.count', { count: filteredApplications.length }) }}</span><BaseButton variant="outline" size="sm" :loading="loading" @click="load">{{ t('common.refresh') }}</BaseButton></template>
        <AdminPageState :loading="loading" :error="error" :empty="!filteredApplications.length" :empty-title="t('adminPages.objectStorage.noApplications')">
          <div class="admin-workbench-panel overflow-hidden divide-y divide-slate-200">
            <article v-for="application in filteredApplications" :key="application.id">
              <button type="button" class="grid w-full gap-3 px-5 py-4 text-left hover:bg-slate-50 lg:grid-cols-[minmax(0,1fr)_minmax(13rem,0.7fr)_auto] lg:items-center" :aria-expanded="expanded === application.id" @click="toggle(application)">
                <div><p class="font-medium text-slate-900">{{ t('adminPages.objectStorage.applicationNumber', { id: application.id }) }}</p><p class="mt-1 text-xs text-slate-500">{{ application.username || `#${application.applicant_id}` }} · {{ formatDate(application.created_at) }}</p></div>
                <div class="text-sm text-slate-600">{{ t('adminPages.objectStorage.applicationCounts', application.counts || {}) }}</div>
                <div class="flex items-center justify-end gap-3"><StatusBadge :status="statusBadge(application.status)" /><span aria-hidden="true" class="text-slate-400">{{ expanded === application.id ? '⌃' : '⌄' }}</span></div>
              </button>
              <div v-if="expanded === application.id" class="border-t border-slate-200 bg-slate-50/60 px-5 py-5"><div v-if="detailLoading" class="text-sm text-slate-500">{{ t('common.loading') }}</div><template v-else-if="detail"><div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-4"><InfoCell :label="t('common.status')" :value="statusLabel(detail.status)" /><InfoCell :label="t('adminPages.objectStorage.currentStage')" :value="detail.current_stage || t('common.emptyValue')" /><InfoCell :label="t('adminPages.objectStorage.startedAt')" :value="formatDate(detail.started_at)" /><InfoCell :label="t('adminPages.objectStorage.finishedAt')" :value="formatDate(detail.finished_at)" /></div><div class="mt-5 divide-y divide-slate-200 border-y border-slate-200"><div v-for="item in detail.items || []" :key="item.id" class="py-4"><div class="flex flex-wrap items-start justify-between gap-3"><div><p class="font-medium text-slate-900">{{ item.business_name }}</p><p class="mt-1 break-all font-mono text-xs text-slate-500">{{ item.rendered_bucket_name || t('common.emptyValue') }}</p></div><StatusBadge :status="statusBadge(item.status)" /></div><p v-if="item.error_code" class="mt-2 text-xs text-rose-700">{{ item.error_code }}</p></div></div><div v-if="['failed', 'manual_required'].includes(detail.status)" class="mt-4 flex justify-end"><BaseButton :loading="acting" @click="retry(detail)">{{ t('adminPages.objectStorage.retryApplication') }}</BaseButton></div></template></div>
            </article>
          </div>
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
import PageFrame from '@/components/ui/PageFrame.vue'
import StatusBadge from '@/components/ui/StatusBadge.vue'
import { extractErrorMessage } from '@/utils/api'
import objectStorageAdminApi from '@/admin/api/objectStorage'

const { t, locale } = useI18n(); const applications = ref([]); const loading = ref(true); const error = ref(''); const statusFilter = ref(''); const expanded = ref(null); const detail = ref(null); const detailLoading = ref(false); const acting = ref(false)
const statuses = ['pending', 'running', 'succeeded', 'partially_succeeded', 'failed', 'cancelled', 'manual_required']
const filteredApplications = computed(() => applications.value.filter((item) => !statusFilter.value || item.status === statusFilter.value))
const statusLabel = (value) => t(`adminPages.objectStorage.applicationStates.${value}`, value)
const statusBadge = (value) => ['succeeded'].includes(value) ? 'success' : ['failed', 'manual_required'].includes(value) ? 'failed' : ['running'].includes(value) ? 'processing' : ['cancelled'].includes(value) ? 'disabled' : 'pending'
const formatDate = (value) => value ? new Intl.DateTimeFormat(locale.value, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value)) : t('common.emptyValue')
const InfoCell = defineComponent({ props: { label: String, value: [String, Number] }, setup: (props) => () => h('div', [h('dt', { class: 'text-xs font-medium text-slate-500' }, props.label), h('dd', { class: 'mt-1 text-sm text-slate-800' }, props.value || t('common.emptyValue'))]) })
async function load() { loading.value = true; error.value = ''; try { applications.value = await objectStorageAdminApi.listApplications() } catch (err) { error.value = extractErrorMessage(err, t('adminPages.objectStorage.loadFailed')) } finally { loading.value = false } }
async function toggle(application) { if (expanded.value === application.id) { expanded.value = null; detail.value = null; return }; expanded.value = application.id; detailLoading.value = true; try { detail.value = await objectStorageAdminApi.getApplication(application.id) } catch (err) { error.value = extractErrorMessage(err, t('adminPages.objectStorage.loadFailed')) } finally { detailLoading.value = false } }
async function retry(application) { if (!window.confirm(t('adminPages.objectStorage.retryConfirm'))) return; const reason = window.prompt(t('adminPages.objectStorage.reasonPrompt')); if (!reason?.trim()) return; acting.value = true; try { await objectStorageAdminApi.retryApplication(application.id, reason.trim()); await load(); await toggle(application) } catch (err) { error.value = extractErrorMessage(err, t('adminPages.objectStorage.actionFailed')) } finally { acting.value = false } }
onMounted(load)
</script>
