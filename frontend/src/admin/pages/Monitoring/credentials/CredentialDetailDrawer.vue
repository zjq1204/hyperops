<template>
  <Teleport to="body">
    <div v-if="show" class="fixed inset-0 z-[80]" @click.self="emit('close')">
      <div class="absolute inset-0 bg-slate-950/45" aria-hidden="true" />
      <aside class="glass-scrollbar absolute inset-y-0 right-0 flex w-full max-w-2xl flex-col overflow-y-auto bg-white shadow-2xl" role="dialog" aria-modal="true" :aria-label="t('monitoringCredentials.details')">
        <header class="sticky top-0 z-10 flex items-center justify-between gap-4 border-b border-slate-200 bg-white px-5 py-4 sm:px-6">
          <div class="min-w-0">
            <h2 class="truncate text-base font-semibold text-slate-950">{{ credential?.name || t('monitoringCredentials.details') }}</h2>
            <p v-if="credential" class="mt-1 truncate text-xs text-slate-500">{{ t(`monitoringCredentials.types.${credentialTypeKey(credential)}`) }}</p>
          </div>
          <button type="button" class="inline-flex h-9 w-9 flex-none items-center justify-center rounded-md text-slate-400 transition hover:bg-slate-100 hover:text-slate-700 focus:outline-none focus:ring-2 focus:ring-sky-500" :aria-label="t('common.close')" @click="emit('close')">
            <svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" /></svg>
          </button>
        </header>

        <div v-if="loading" class="flex flex-1 items-center justify-center p-8 text-sm text-slate-500">{{ t('common.loading') }}</div>
        <div v-else-if="error" class="p-6 text-sm text-rose-600" role="alert">{{ error }}</div>
        <div v-else-if="credential" class="grid flex-1 content-start gap-6 px-5 py-5 sm:px-6">
          <section class="border-b border-slate-200 pb-5">
            <dl class="grid grid-cols-2 gap-4 sm:grid-cols-4">
              <div><dt class="text-xs text-slate-500">{{ t('monitoringCredentials.type') }}</dt><dd class="mt-1 text-sm font-semibold text-slate-900">{{ t(`monitoringCredentials.types.${credentialTypeKey(credential)}`) }}</dd></div>
              <div><dt class="text-xs text-slate-500">{{ t('monitoringCredentials.activeVersion') }}</dt><dd class="mt-1 text-sm font-semibold text-slate-900">{{ activeVersionText }}</dd></div>
              <div><dt class="text-xs text-slate-500">{{ t('monitoringCredentials.lifecycle') }}</dt><dd class="mt-1 text-sm font-semibold text-slate-900">{{ lifecycleLabel(credential) }}</dd></div>
              <div><dt class="text-xs text-slate-500">{{ t('monitoringCredentials.validation') }}</dt><dd class="mt-1 text-sm font-semibold text-slate-900">{{ validationLabel(credential) }}</dd></div>
            </dl>
          </section>

          <section>
            <h3 class="text-sm font-semibold text-slate-900">{{ t('monitoringCredentials.associatedHosts') }}</h3>
            <div class="mt-3 divide-y divide-slate-100 border-y border-slate-200">
              <router-link v-for="host in associatedHosts" :key="host.id" :to="{ name: 'AdminMonitoringAssets', query: { host: host.id } }" class="flex items-center justify-between gap-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-sky-500">
                <span class="min-w-0"><span class="block truncate font-medium text-sky-700">{{ host.hostname || host.name }}</span><span class="block truncate text-xs text-slate-500">{{ host.address || t('common.emptyValue') }}</span></span>
                <span class="text-xs text-slate-500">{{ host.enabled === false ? t('common.disabled') : t('common.enabled') }}</span>
              </router-link>
              <p v-if="!associatedHosts.length" class="py-3 text-sm text-slate-500">{{ t('monitoringCredentials.noAssociatedHosts') }}</p>
            </div>
          </section>

          <section>
            <h3 class="text-sm font-semibold text-slate-900">{{ t('monitoringCredentials.latestValidations') }}</h3>
            <div class="mt-3 divide-y divide-slate-100 border-y border-slate-200">
              <div v-for="item in latestValidations" :key="item.id" class="grid grid-cols-[minmax(0,1fr)_auto] gap-3 py-3 text-sm">
                <span class="min-w-0"><span class="block truncate font-medium text-slate-800">{{ item.hostName || item.host_name || t('monitoringCredentials.hostFallback', { id: item.hostId || item.host_id }) }}</span><span class="block truncate text-xs text-slate-500">{{ item.errorCode || item.error_code || formatDate(item.checkedAt || item.checked_at) }}</span></span>
                <span class="font-semibold" :class="validationClass(item.status)">{{ statusText(item.status) }}</span>
              </div>
              <p v-if="!latestValidations.length" class="py-3 text-sm text-slate-500">{{ t('common.noData') }}</p>
            </div>
          </section>

          <section>
            <h3 class="text-sm font-semibold text-slate-900">{{ t('monitoringCredentials.versionHistory') }}</h3>
            <div class="mt-3 divide-y divide-slate-100 border-y border-slate-200">
              <div v-for="version in versionHistory" :key="version.id" class="grid grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-3 py-3 text-sm">
                <span class="flex items-center gap-2 font-semibold text-slate-900">v{{ version.version }}<span v-if="isActiveVersion(version)" class="rounded-md bg-emerald-50 px-1.5 py-0.5 text-[0.6875rem] font-semibold text-emerald-700">{{ t('monitoringCredentials.active') }}</span></span>
                <span class="min-w-0 truncate text-xs text-slate-500">{{ credentialTypeKey(credential) === 'private_key' ? credentialFingerprint(version) || credentialAlgorithmLabel(version) : t('monitoringCredentials.passwordManaged') }}</span>
                <span class="text-xs font-semibold" :class="validationClass(credentialValidationKey(version))">{{ validationLabel(version) }}</span>
              </div>
              <p v-if="!versionHistory.length" class="py-3 text-sm text-slate-500">{{ t('common.noData') }}</p>
            </div>
          </section>

          <section>
            <h3 class="text-sm font-semibold text-slate-900">{{ t('monitoringCredentials.auditHistory') }}</h3>
            <div class="mt-3 divide-y divide-slate-100 border-y border-slate-200">
              <div v-for="event in auditHistory" :key="event.id" class="grid grid-cols-[minmax(0,1fr)_auto] gap-3 py-3 text-sm"><span class="min-w-0"><span class="block truncate font-medium text-slate-800">{{ auditAction(event.action) }}</span><span class="block truncate text-xs text-slate-500">{{ auditActor(event) }}</span></span><time class="text-xs text-slate-500">{{ formatDate(event.createdAt || event.created_at) }}</time></div>
              <p v-if="!auditHistory.length" class="py-3 text-sm text-slate-500">{{ t('common.noData') }}</p>
            </div>
          </section>

          <section v-if="conflictHosts.length" class="border-t border-rose-200 pt-5">
            <h3 class="text-sm font-semibold text-rose-800">{{ t('monitoringCredentials.linkedHostConflict') }}</h3>
            <div class="mt-3 flex flex-wrap gap-2"><router-link v-for="host in conflictHosts" :key="host.id" :to="{ name: 'AdminMonitoringAssets', query: { host: host.id } }" class="rounded-md border border-rose-200 px-2.5 py-1.5 text-sm font-medium text-rose-700 focus:outline-none focus:ring-2 focus:ring-rose-500">{{ host.name || host.hostname }}</router-link></div>
          </section>
        </div>

        <footer v-if="credential" class="sticky bottom-0 flex flex-wrap justify-end gap-2 border-t border-slate-200 bg-slate-50 px-5 py-4 sm:px-6">
          <BaseButton v-if="canRotate" variant="outline" size="sm" @click="emit('rotate', credential)">{{ t('monitoringCredentials.rotate') }}</BaseButton>
          <BaseButton v-if="canArchiveCredential(credential, user)" variant="outline" size="sm" @click="emit('archive', credential)">{{ t('monitoringCredentials.archive') }}</BaseButton>
          <BaseButton v-if="showDeleteAction" variant="danger" size="sm" @click="emit('delete', credential)">{{ t('common.delete') }}</BaseButton>
        </footer>
      </aside>
    </div>
  </Teleport>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import BaseButton from '@/components/ui/BaseButton.vue'
import { formatDate } from '@/utils/formatting'
import {
  canArchiveCredential,
  collectionFromPayload,
  credentialActiveVersionNumber,
  credentialAlgorithmLabel,
  credentialFingerprint,
  credentialHostCount,
  credentialLifecycleKey,
  credentialTypeKey,
  credentialValidationKey,
  hasCredentialPermission,
  readField
} from './credentialState'

const props = defineProps({ show: { type: Boolean, default: false }, credential: { type: Object, default: null }, loading: { type: Boolean, default: false }, error: { type: String, default: '' }, user: { type: Object, default: null }, conflictHosts: { type: Array, default: () => [] } })
const emit = defineEmits(['close', 'rotate', 'archive', 'delete'])
const { t } = useI18n()
const associatedHosts = computed(() => collectionFromPayload(readField(props.credential, 'associatedHosts', 'associated_hosts', readField(props.credential, 'hosts', 'hosts', []))))
const latestValidations = computed(() => {
  const latestByHost = new Map()
  collectionFromPayload(
    readField(props.credential, 'latestValidations', 'validations', [])
  ).forEach((item) => {
    const key = String(item.hostId ?? item.host_id ?? `candidate-${item.id}`)
    const current = latestByHost.get(key)
    const checkedAt = new Date(item.checkedAt || item.checked_at || 0).getTime()
    const currentCheckedAt = new Date(
      current?.checkedAt || current?.checked_at || 0
    ).getTime()
    if (!current || checkedAt >= currentCheckedAt) latestByHost.set(key, item)
  })
  return [...latestByHost.values()]
})
const versionHistory = computed(() => collectionFromPayload(readField(props.credential, 'versionHistory', 'versions', [])))
const auditHistory = computed(() => collectionFromPayload(readField(props.credential, 'auditHistory', 'audit_history', readField(props.credential, 'audit', 'audit', readField(props.credential, 'auditEvents', 'audit_events', [])))))
const activeVersionText = computed(() => credentialActiveVersionNumber(props.credential) ? `v${credentialActiveVersionNumber(props.credential)}` : t('common.emptyValue'))
const canRotate = computed(() => hasCredentialPermission(props.user, 'manage') && credentialLifecycleKey(props.credential) !== 'archived')
const showDeleteAction = computed(
  () =>
    hasCredentialPermission(props.user, 'delete') &&
    (credentialLifecycleKey(props.credential) === 'archived' ||
      credentialHostCount(props.credential) > 0)
)

function lifecycleLabel(item) { return t(`monitoringCredentials.lifecycleStates.${credentialLifecycleKey(item)}`) }
function validationLabel(item) { return t(`monitoringCredentials.validationStates.${credentialValidationKey(item)}`) }
function statusText(status) { return t(`monitoringCredentials.validationStates.${status || 'unverified'}`) }
function auditAction(action) { return t(`monitoringCredentials.auditActions.${action || 'unknown'}`) }
function auditActor(event) {
  const actor = event.actorName || event.actor_name
  const actorId = event.actorId ?? event.actor_id
  return actor || (actorId ? `#${actorId}` : t('common.emptyValue'))
}
function isActiveVersion(version) {
  const active = readField(props.credential, 'activeVersion', 'active_version')
  const activeId = active && typeof active === 'object' ? active.id : active
  return String(activeId || '') === String(version.id || '')
}
function validationClass(status) { return ['passed', 'success', 'valid'].includes(status) ? 'text-emerald-700' : ['failed', 'invalid'].includes(status) ? 'text-rose-700' : 'text-slate-600' }
function handleEscape(event) { if (event.key === 'Escape' && props.show) emit('close') }
watch(() => props.show, (show) => { document.body.style.overflow = show ? 'hidden' : '' })
onMounted(() => document.addEventListener('keydown', handleEscape))
onBeforeUnmount(() => { document.body.style.overflow = ''; document.removeEventListener('keydown', handleEscape) })
</script>
