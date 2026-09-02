<template>
  <AdminLayout>
    <PageFrame variant="soft" :title="t('adminPages.objectStorage.accessKeysTitle')" :subtitle="t('adminPages.objectStorage.accessKeysSubtitle')">
      <AdminListSection>
        <template #toolbarStart><input v-model.trim="query" class="admin-filter-control min-w-56" :placeholder="t('adminPages.objectStorage.searchAccessKeys')" /><select v-model="stateFilter" class="admin-filter-control min-w-40"><option value="">{{ t('adminPages.objectStorage.allStatuses') }}</option><option v-for="state in states" :key="state" :value="state">{{ stateLabel(state) }}</option></select></template>
        <template #toolbarEnd><span class="admin-summary-pill">{{ t('adminPages.objectStorage.count', { count: filteredKeys.length }) }}</span><BaseButton variant="outline" size="sm" :loading="loading" @click="load">{{ t('common.refresh') }}</BaseButton></template>
        <AdminPageState :loading="loading" :error="error" :empty="!filteredKeys.length" :empty-title="t('adminPages.objectStorage.noAccessKeys')">
          <div class="admin-workbench-panel overflow-hidden"><div class="overflow-x-auto"><table class="admin-table"><thead><tr><th class="admin-table-head">{{ t('adminPages.objectStorage.accessKey') }}</th><th class="admin-table-head">{{ t('adminPages.objectStorage.owner') }}</th><th class="admin-table-head">{{ t('common.status') }}</th><th class="admin-table-head">{{ t('adminPages.objectStorage.lastSynced') }}</th><th class="admin-table-head text-right">{{ t('common.actions') }}</th></tr></thead><tbody><tr v-for="key in filteredKeys" :key="key.id" class="admin-table-row"><td class="admin-table-cell"><p class="font-mono text-sm font-semibold text-slate-900">···· {{ key.last_four }}</p><p class="mt-1 font-mono text-xs text-slate-500">{{ key.fingerprint?.slice(0, 16) }}…</p></td><td class="admin-table-cell"><p class="text-slate-800">{{ key.username || `#${key.user_id}` }}</p><p class="mt-1 text-xs text-slate-500">{{ t('adminPages.objectStorage.identityReference', { id: key.cloud_identity_id }) }}</p></td><td class="admin-table-cell"><StatusBadge :status="statusBadge(key.local_state)" /></td><td class="admin-table-cell text-sm text-slate-600">{{ formatDate(key.last_synced_at) }}</td><td class="admin-table-cell text-right"><div class="flex flex-wrap justify-end gap-2"><BaseButton size="sm" variant="ghost" @click="openReveal(key)">{{ t('adminPages.objectStorage.reveal') }}</BaseButton><BaseButton v-if="key.local_state === 'active'" size="sm" variant="outline" :loading="acting === key.id" @click="disable(key)">{{ t('adminPages.objectStorage.disable') }}</BaseButton><BaseButton v-else-if="key.local_state === 'disabled'" size="sm" variant="outline" :loading="acting === key.id" @click="enable(key)">{{ t('adminPages.objectStorage.enable') }}</BaseButton><BaseButton v-if="!['retired', 'retiring'].includes(key.local_state)" size="sm" variant="ghost" :loading="acting === key.id" @click="revoke(key)">{{ t('adminPages.objectStorage.revoke') }}</BaseButton></div></td></tr></tbody></table></div></div>
        </AdminPageState>
      </AdminListSection>
    </PageFrame>
    <BaseModal :show="Boolean(revealKey)" :title="t('adminPages.objectStorage.revealTitle')" size="sm" @close="closeReveal"><form v-if="!revealResult" class="space-y-4" @submit.prevent="reveal"><p class="text-sm leading-6 text-slate-600">{{ t('adminPages.objectStorage.revealWarning') }}</p><label class="admin-form-field"><span class="admin-form-label">{{ t('adminPages.objectStorage.reason') }}</span><textarea v-model.trim="reason" class="admin-filter-control min-h-24" required /></label><div class="flex justify-end gap-2"><BaseButton variant="outline" @click="closeReveal">{{ t('common.cancel') }}</BaseButton><BaseButton type="submit" :loading="revealing">{{ t('adminPages.objectStorage.reveal') }}</BaseButton></div></form><div v-else class="space-y-4"><InlineAlert variant="warning" :message="t('adminPages.objectStorage.revealOnce')" /><label class="admin-form-field"><span class="admin-form-label">{{ t('adminPages.objectStorage.accessKey') }}</span><input :value="revealResult.access_key_id" class="admin-filter-control font-mono" readonly /></label><label class="admin-form-field"><span class="admin-form-label">{{ t('adminPages.objectStorage.secretKey') }}</span><input :value="revealResult.secret_access_key" class="admin-filter-control font-mono" readonly /></label><div class="flex justify-end"><BaseButton variant="outline" @click="closeReveal">{{ t('common.close') }}</BaseButton></div></div></BaseModal>
  </AdminLayout>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import AdminLayout from '@/admin/layout/AdminLayout.vue'
import AdminListSection from '@/admin/components/AdminListSection.vue'
import AdminPageState from '@/admin/components/AdminPageState.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseModal from '@/components/ui/BaseModal.vue'
import InlineAlert from '@/components/ui/InlineAlert.vue'
import PageFrame from '@/components/ui/PageFrame.vue'
import StatusBadge from '@/components/ui/StatusBadge.vue'
import { extractErrorMessage } from '@/utils/api'
import objectStorageAdminApi from '@/admin/api/objectStorage'

const { t, locale } = useI18n(); const keys = ref([]); const loading = ref(true); const error = ref(''); const query = ref(''); const stateFilter = ref(''); const acting = ref(null); const revealKey = ref(null); const revealResult = ref(null); const reason = ref(''); const revealing = ref(false)
const states = ['issuing', 'delivery_ready', 'active', 'disabled', 'retiring', 'retired', 'error']
const filteredKeys = computed(() => keys.value.filter((key) => (!stateFilter.value || key.local_state === stateFilter.value) && (!query.value || [key.username, key.last_four, key.fingerprint].some((value) => String(value || '').toLowerCase().includes(query.value.toLowerCase())))))
const stateLabel = (state) => t(`adminPages.objectStorage.keyStates.${state}`, state)
const statusBadge = (state) => ['active', 'delivery_ready'].includes(state) ? 'success' : ['error', 'retiring'].includes(state) ? 'failed' : ['disabled', 'retired'].includes(state) ? 'disabled' : 'pending'
const formatDate = (value) => value ? new Intl.DateTimeFormat(locale.value, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value)) : t('common.emptyValue')
async function load() { loading.value = true; error.value = ''; try { keys.value = await objectStorageAdminApi.listAccessKeys() } catch (err) { error.value = extractErrorMessage(err, t('adminPages.objectStorage.loadFailed')) } finally { loading.value = false } }
async function mutate(key, method, confirmKey) { if (!window.confirm(t(confirmKey))) return; const value = window.prompt(t('adminPages.objectStorage.reasonPrompt')); if (!value?.trim()) return; acting.value = key.id; try { await method(key.id, { reason: value.trim() }); await load() } catch (err) { error.value = extractErrorMessage(err, t('adminPages.objectStorage.actionFailed')) } finally { acting.value = null } }
const disable = (key) => mutate(key, objectStorageAdminApi.disableAccessKey, 'adminPages.objectStorage.disableConfirm')
const enable = (key) => mutate(key, objectStorageAdminApi.enableAccessKey, 'adminPages.objectStorage.enableConfirm')
const revoke = (key) => mutate(key, objectStorageAdminApi.revokeAccessKey, 'adminPages.objectStorage.revokeConfirm')
function openReveal(key) { revealKey.value = key; revealResult.value = null; reason.value = '' }
function closeReveal() { revealKey.value = null; revealResult.value = null; reason.value = '' }
async function reveal() { revealing.value = true; try { revealResult.value = await objectStorageAdminApi.revealAccessKey(revealKey.value.id, reason.value.trim()) } catch (err) { error.value = extractErrorMessage(err, t('adminPages.objectStorage.actionFailed')); closeReveal() } finally { revealing.value = false } }
onMounted(load)
</script>
