<template>
  <AdminLayout>
    <PageFrame variant="soft" :title="t('adminPages.objectStorage.bucketsTitle')" :subtitle="t('adminPages.objectStorage.bucketsSubtitle')">
      <AdminListSection>
        <template #toolbarStart>
          <input v-model.trim="query" class="admin-filter-control min-w-56" :placeholder="t('adminPages.objectStorage.searchBuckets')" />
          <select v-model="stateFilter" class="admin-filter-control min-w-40">
            <option value="">{{ t('adminPages.objectStorage.allStatuses') }}</option>
            <option v-for="state in states" :key="state" :value="state">{{ stateLabel(state) }}</option>
          </select>
        </template>
        <template #toolbarEnd>
          <span class="admin-summary-pill">{{ t('adminPages.objectStorage.count', { count: filteredBuckets.length }) }}</span>
          <BaseButton variant="outline" size="sm" :loading="loading" @click="load">{{ t('common.refresh') }}</BaseButton>
        </template>
        <AdminPageState :loading="loading" :error="error" :empty="!filteredBuckets.length" :empty-title="t('adminPages.objectStorage.noBuckets')">
          <div class="admin-workbench-panel overflow-hidden">
            <div class="overflow-x-auto">
              <table class="admin-table">
                <thead><tr><th class="admin-table-head">{{ t('adminPages.objectStorage.bucket') }}</th><th class="admin-table-head">{{ t('adminPages.objectStorage.owner') }}</th><th class="admin-table-head">{{ t('adminPages.objectStorage.region') }}</th><th class="admin-table-head">{{ t('common.status') }}</th><th class="admin-table-head text-right">{{ t('common.actions') }}</th></tr></thead>
                <tbody>
                  <template v-for="bucket in filteredBuckets" :key="bucket.id">
                    <tr class="admin-table-row">
                      <td class="admin-table-cell"><button type="button" class="text-left font-semibold text-sky-700 hover:text-sky-900" @click="toggle(bucket)">{{ bucket.name }}</button><p class="mt-1 text-xs text-slate-500">{{ bucket.project || t('common.emptyValue') }} · {{ bucket.environment }}</p></td>
                      <td class="admin-table-cell"><p class="text-slate-800">{{ bucket.username || `#${bucket.owner_id}` }}</p><p class="mt-1 text-xs text-slate-500">{{ bucket.business_name }}</p></td>
                      <td class="admin-table-cell">{{ bucket.region }}</td>
                      <td class="admin-table-cell"><StatusBadge :status="bucketStatus(bucket.state)" /></td>
                      <td class="admin-table-cell text-right"><div class="flex flex-wrap justify-end gap-2"><BaseButton v-if="canRelease(bucket)" size="sm" variant="outline" :loading="acting === bucket.id" @click="release(bucket)">{{ t('adminPages.objectStorage.release') }}</BaseButton><BaseButton v-if="canRecover(bucket)" size="sm" variant="outline" :loading="acting === bucket.id" @click="recover(bucket)">{{ t('adminPages.objectStorage.recover') }}</BaseButton><BaseButton size="sm" variant="ghost" @click="toggle(bucket)">{{ expanded === bucket.id ? t('common.close') : t('adminPages.objectStorage.viewDetails') }}</BaseButton></div></td>
                    </tr>
                    <tr v-if="expanded === bucket.id" class="bg-slate-50/70"><td colspan="5" class="px-5 py-4"><div v-if="detailLoading" class="text-sm text-slate-500">{{ t('common.loading') }}</div><dl v-else-if="detail" class="grid gap-4 sm:grid-cols-2 lg:grid-cols-4"><InfoCell :label="t('adminPages.objectStorage.purpose')" :value="detail.purpose" /><InfoCell :label="t('adminPages.objectStorage.configState')" :value="detail.config_state" /><InfoCell :label="t('adminPages.objectStorage.createdAt')" :value="formatDate(detail.created_at)" /><InfoCell :label="t('adminPages.objectStorage.lastSynced')" :value="formatDate(detail.last_synced_at)" /><div class="sm:col-span-2 lg:col-span-4"><dt class="text-xs font-medium text-slate-500">{{ t('adminPages.objectStorage.desiredConfig') }}</dt><dd class="mt-1 break-all font-mono text-xs text-slate-700">{{ JSON.stringify(detail.desired_config_snapshot || {}) }}</dd></div></dl></td></tr>
                  </template>
                </tbody>
              </table>
            </div>
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

const { t, locale } = useI18n()
const buckets = ref([]); const loading = ref(true); const error = ref(''); const query = ref(''); const stateFilter = ref(''); const expanded = ref(null); const detail = ref(null); const detailLoading = ref(false); const acting = ref(null)
const states = ['requested', 'creating', 'active', 'releasing', 'pending_deletion', 'deletion_blocked', 'released', 'failed', 'cancelled']
const filteredBuckets = computed(() => buckets.value.filter((bucket) => (!stateFilter.value || bucket.state === stateFilter.value) && (!query.value || [bucket.name, bucket.username, bucket.business_name, bucket.project].some((value) => String(value || '').toLowerCase().includes(query.value.toLowerCase())))))
const stateLabel = (state) => t(`adminPages.objectStorage.states.${state}`, state)
const bucketStatus = (state) => ['active'].includes(state) ? 'success' : ['failed', 'deletion_blocked'].includes(state) ? 'failed' : ['creating', 'releasing', 'pending_deletion'].includes(state) ? 'processing' : 'pending'
const formatDate = (value) => value ? new Intl.DateTimeFormat(locale.value, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value)) : t('common.emptyValue')
const canRelease = (bucket) => ['active', 'failed'].includes(bucket.state)
const canRecover = (bucket) => ['released', 'deletion_blocked', 'cancelled'].includes(bucket.state)
const InfoCell = defineComponent({ props: { label: String, value: [String, Number] }, setup: (props) => () => h('div', [h('dt', { class: 'text-xs font-medium text-slate-500' }, props.label), h('dd', { class: 'mt-1 text-sm text-slate-800' }, props.value || t('common.emptyValue'))]) })
async function load() { loading.value = true; error.value = ''; try { buckets.value = await objectStorageAdminApi.listBuckets() } catch (err) { error.value = extractErrorMessage(err, t('adminPages.objectStorage.loadFailed')) } finally { loading.value = false } }
async function toggle(bucket) { if (expanded.value === bucket.id) { expanded.value = null; detail.value = null; return }; expanded.value = bucket.id; detailLoading.value = true; try { detail.value = await objectStorageAdminApi.getBucket(bucket.id) } catch (err) { error.value = extractErrorMessage(err, t('adminPages.objectStorage.loadFailed')) } finally { detailLoading.value = false } }
async function runAction(bucket, method, confirmation) { if (!window.confirm(confirmation)) return; const reason = window.prompt(t('adminPages.objectStorage.reasonPrompt')); if (!reason?.trim()) return; acting.value = bucket.id; try { await method(bucket.id, { reason: reason.trim(), bucket_name: bucket.name, confirmed: true }); await load() } catch (err) { error.value = extractErrorMessage(err, t('adminPages.objectStorage.actionFailed')) } finally { acting.value = null } }
const release = (bucket) => runAction(bucket, objectStorageAdminApi.releaseBucket, t('adminPages.objectStorage.releaseConfirm', { name: bucket.name }))
const recover = (bucket) => runAction(bucket, objectStorageAdminApi.recoverBucket, t('adminPages.objectStorage.recoverConfirm', { name: bucket.name }))
onMounted(load)
</script>
