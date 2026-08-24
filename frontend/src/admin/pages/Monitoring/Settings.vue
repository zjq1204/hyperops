<template>
  <AdminLayout>
    <PageFrame variant="soft" :title="t('adminPages.monitoring.settingsTitle')">
      <AdminPageState :loading="loading" :error="error" :empty="false">
        <section class="max-w-4xl overflow-hidden rounded-lg border border-slate-200/80 bg-white">
          <article
            v-for="integration in integrationRows"
            :key="integration.key"
            class="grid min-h-[5.5rem] items-center gap-3 border-b border-slate-200/80 px-5 py-4 last:border-b-0 sm:grid-cols-[9rem_minmax(0,1fr)_auto] sm:gap-5 sm:px-6"
          >
            <div class="flex items-center justify-between gap-3 sm:block">
              <h2 class="text-sm font-semibold text-slate-950">
                {{ integration.name }}
              </h2>
              <span class="inline-flex items-center gap-2 text-xs font-medium text-slate-500 sm:mt-2">
                <span class="h-1.5 w-1.5 rounded-full" :class="integration.configured ? 'bg-sky-500' : 'bg-slate-300'" aria-hidden="true"></span>
                {{ integration.configured ? t('adminPages.monitoring.connectionSet') : t('adminPages.monitoring.connectionNotSet') }}
              </span>
            </div>
            <p class="min-w-0 truncate text-sm text-slate-600" :class="integration.url ? 'font-mono' : 'text-slate-400'" :title="integration.url || ''">
              {{ integration.url || t('common.emptyValue') }}
            </p>
            <BaseButton variant="outline" size="sm" class="justify-self-start sm:justify-self-end" @click="startEdit(integration.key)">
              {{ t('common.edit') }}
            </BaseButton>
          </article>
        </section>
      </AdminPageState>
    </PageFrame>

    <Teleport to="body">
      <Transition
        enter-active-class="transition duration-200 ease-out"
        enter-from-class="opacity-0"
        enter-to-class="opacity-100"
        leave-active-class="transition duration-150 ease-in"
        leave-from-class="opacity-100"
        leave-to-class="opacity-0"
      >
        <div v-if="editingKey" class="fixed inset-0 z-[80]" @click.self="requestCloseEditor">
          <div class="absolute inset-0 bg-slate-950/45" aria-hidden="true"></div>
          <aside class="absolute inset-y-0 right-0 flex w-full max-w-xl flex-col bg-white shadow-2xl" role="dialog" aria-modal="true" :aria-label="t('adminPages.monitoring.editIntegration', { name: activeIntegration.name })">
            <header class="flex shrink-0 items-center justify-between gap-4 border-b border-slate-200 bg-white px-5 py-4 sm:px-6">
              <div class="min-w-0">
                <h2 class="truncate text-base font-semibold text-slate-950">
                  {{ t('adminPages.monitoring.editIntegration', { name: activeIntegration.name }) }}
                </h2>
                <p class="mt-1 truncate text-xs text-slate-500">
                  {{ activeIntegration.url || t('adminPages.monitoring.connectionNotSet') }}
                </p>
              </div>
              <button type="button" class="flex h-11 w-11 shrink-0 items-center justify-center rounded-md text-slate-400 transition hover:bg-slate-100 hover:text-slate-700 focus:outline-none focus:ring-2 focus:ring-sky-500" :aria-label="t('common.close')" @click="requestCloseEditor">
                <svg class="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
                  <path d="M6 6l12 12M18 6 6 18" />
                </svg>
              </button>
            </header>

            <form class="flex min-h-0 flex-1 flex-col" @submit.prevent="saveIntegration">
              <div class="glass-scrollbar flex-1 overflow-y-auto px-5 py-6 sm:px-6">
                <div v-if="editingKey === 'n9e'" class="grid gap-5">
                  <label class="admin-filter-field">
                    <span class="admin-filter-label">{{ t('adminPages.monitoring.n9eUrl') }}</span>
                    <input ref="activeUrlInput" v-model.trim="draft.n9eUrl" class="admin-filter-control" :class="fieldError ? 'border-rose-400 focus:border-rose-500 focus:ring-rose-100' : ''" placeholder="http://monitor-n9e:17000" autocomplete="url" :aria-invalid="Boolean(fieldError)" aria-describedby="active-url-error" @blur="validateUrl('n9eUrl')" />
                    <span v-if="fieldError" id="active-url-error" class="text-xs font-medium text-rose-600" role="alert">{{ fieldError }}</span>
                  </label>
                  <label class="admin-filter-field">
                    <span class="admin-filter-label">{{ t('adminPages.monitoring.user') }}</span>
                    <input v-model.trim="draft.n9eUsername" class="admin-filter-control" placeholder="root" autocomplete="username" />
                  </label>
                  <label class="admin-filter-field">
                    <span class="admin-filter-label">
                      {{ t('adminPages.monitoring.n9ePassword') }}
                      <span v-if="hasPassword" class="ml-1 text-xs font-normal text-slate-500">{{ t('adminPages.monitoring.passwordConfigured') }}</span>
                    </span>
                    <span class="relative block w-full">
                      <input v-model="draft.n9ePassword" :type="showPassword ? 'text' : 'password'" class="admin-filter-control w-full pr-12" :placeholder="hasPassword ? t('adminPages.monitoring.passwordKeepHint') : ''" autocomplete="new-password" />
                      <button type="button" class="absolute inset-y-0 right-0 flex w-11 items-center justify-center rounded-r-lg text-slate-500 transition-colors hover:bg-slate-50 hover:text-slate-800 focus:outline-none focus:ring-2 focus:ring-inset focus:ring-sky-500" :aria-label="showPassword ? t('common.hidePassword') : t('common.showPassword')" @click="showPassword = !showPassword">
                        <svg v-if="showPassword" class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><path d="m3 3 18 18M10.6 10.6a2 2 0 0 0 2.8 2.8M9.9 4.2A10.7 10.7 0 0 1 12 4c5 0 8.5 4 9 6-.2.8-.9 2-2 3.2M6.6 6.6C4.6 8 3.4 9.8 3 11c.5 2 4 6 9 6 1.2 0 2.3-.2 3.3-.7" /></svg>
                        <svg v-else class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><path d="M3 12c.5-2 4-6 9-6s8.5 4 9 6c-.5 2-4 6-9 6s-8.5-4-9-6Z" /><circle cx="12" cy="12" r="2.5" /></svg>
                      </button>
                    </span>
                  </label>
                </div>

                <label v-else class="admin-filter-field">
                  <span class="admin-filter-label">{{ editingKey === 'prometheus' ? t('adminPages.monitoring.prometheusUrl') : t('adminPages.monitoring.grafanaUrl') }}</span>
                  <input ref="activeUrlInput" v-model.trim="draft.url" class="admin-filter-control" :class="fieldError ? 'border-rose-400 focus:border-rose-500 focus:ring-rose-100' : ''" :placeholder="activeIntegration.placeholder" autocomplete="url" :aria-invalid="Boolean(fieldError)" aria-describedby="active-url-error" @blur="validateUrl('url')" />
                  <span v-if="fieldError" id="active-url-error" class="text-xs font-medium text-rose-600" role="alert">{{ fieldError }}</span>
                </label>
              </div>

              <footer class="sticky bottom-0 flex shrink-0 flex-col-reverse gap-2 border-t border-slate-200 bg-slate-50 px-5 py-4 sm:flex-row sm:justify-end sm:px-6">
                <BaseButton variant="outline" :disabled="saving" @click="requestCloseEditor">{{ t('common.cancel') }}</BaseButton>
                <BaseButton type="submit" variant="primary" :loading="saving" :disabled="!activeIsDirty || hasActiveError">{{ t('common.save') }}</BaseButton>
              </footer>
            </form>
          </aside>
        </div>
      </Transition>
    </Teleport>

    <div v-if="saveMessage" aria-live="polite" class="fixed bottom-5 right-5 z-[70] rounded-lg border border-emerald-200 bg-white px-4 py-3 text-sm font-semibold text-emerald-700 shadow-lg">
      {{ saveMessage }}
    </div>

    <ConfirmDialog :show="confirmDialog.show" :title="confirmDialog.title" :message="confirmDialog.message" :confirm-text="confirmDialog.confirmText" :variant="confirmDialog.variant" :loading="confirmDialog.loading" @close="closeConfirmDialog" @confirm="runConfirmedAction" />
  </AdminLayout>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import AdminLayout from '@/admin/layout/AdminLayout.vue'
import AdminPageState from '@/admin/components/AdminPageState.vue'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import PageFrame from '@/components/ui/PageFrame.vue'
import { monitoringStackApi } from '@/admin/api/monitoringStack'
import { useConfirmDialog } from '@/composables/useConfirmDialog'

const { t } = useI18n()
const { confirmDialog, requestConfirm, closeConfirmDialog, runConfirmedAction } = useConfirmDialog()
const loading = ref(false)
const saving = ref(false)
const error = ref('')
const config = ref({})
const editingKey = ref('')
const initialDraft = ref('')
const fieldError = ref('')
const saveMessage = ref('')
const showPassword = ref(false)
const activeUrlInput = ref(null)
const draft = reactive({ n9eUrl: '', n9eUsername: '', n9ePassword: '', url: '' })

const hasPassword = computed(() => Boolean(config.value?.n9e?.has_password))
const integrationRows = computed(() => [
  { key: 'n9e', name: 'n9e', url: config.value?.n9e_url || '', configured: Boolean(config.value?.n9e_url) },
  { key: 'prometheus', name: 'Prometheus', url: config.value?.prometheus_url || '', placeholder: 'http://monitor-prometheus:9090', configured: Boolean(config.value?.prometheus_url) },
  { key: 'grafana', name: 'Grafana', url: config.value?.grafana_url || '', placeholder: 'http://monitor-grafana:3000', configured: Boolean(config.value?.grafana_url) }
])
const activeIntegration = computed(() => integrationRows.value.find((item) => item.key === editingKey.value) || {})
const draftSnapshot = computed(() => JSON.stringify(activePayload()))
const activeIsDirty = computed(() => Boolean(editingKey.value) && draftSnapshot.value !== initialDraft.value)
const hasActiveError = computed(() => Boolean(fieldError.value))

function activePayload() {
  if (editingKey.value === 'n9e') return { n9e_url: draft.n9eUrl, n9e_username: draft.n9eUsername, n9e_password: draft.n9ePassword }
  if (editingKey.value === 'prometheus') return { prometheus_url: draft.url }
  if (editingKey.value === 'grafana') return { grafana_url: draft.url }
  return {}
}

async function startEdit(key) {
  editingKey.value = key
  fieldError.value = ''
  showPassword.value = false
  if (key === 'n9e') {
    Object.assign(draft, { n9eUrl: config.value?.n9e_url || '', n9eUsername: config.value?.n9e?.username || '', n9ePassword: '', url: '' })
  } else {
    Object.assign(draft, { n9eUrl: '', n9eUsername: '', n9ePassword: '', url: key === 'prometheus' ? config.value?.prometheus_url || '' : config.value?.grafana_url || '' })
  }
  initialDraft.value = draftSnapshot.value
  await nextTick()
  const input = Array.isArray(activeUrlInput.value) ? activeUrlInput.value[0] : activeUrlInput.value
  input?.focus?.()
}

function cancelEdit() {
  editingKey.value = ''
  fieldError.value = ''
  showPassword.value = false
}

function requestCloseEditor() {
  if (!activeIsDirty.value) {
    cancelEdit()
    return
  }
  requestConfirm({
    title: t('adminPages.monitoring.discardIntegrationTitle'),
    message: t('adminPages.monitoring.unsavedIntegrationChanges'),
    confirmText: t('adminPages.monitoring.discardChanges'),
    variant: 'warning',
    onConfirm: cancelEdit
  })
}

function validateUrl(field) {
  const value = String(draft[field] || '').trim()
  if (!value) { fieldError.value = ''; return true }
  try {
    const parsed = new URL(value)
    if (!['http:', 'https:'].includes(parsed.protocol)) throw new Error('protocol')
    fieldError.value = ''
    return true
  } catch {
    fieldError.value = t('adminPages.monitoring.invalidHttpUrl')
    return false
  }
}

async function load() {
  loading.value = true
  error.value = ''
  try { config.value = (await monitoringStackApi.getConfig()) || {} }
  catch (err) { error.value = err?.response?.data?.detail || err.message }
  finally { loading.value = false }
}

async function saveIntegration() {
  const urlField = editingKey.value === 'n9e' ? 'n9eUrl' : 'url'
  if (!validateUrl(urlField) || !activeIsDirty.value || saving.value) return
  saving.value = true
  error.value = ''
  try {
    const name = activeIntegration.value.name
    config.value = await monitoringStackApi.updateConfig(activePayload())
    cancelEdit()
    saveMessage.value = t('adminPages.monitoring.integrationSaved', { name })
    window.setTimeout(() => { saveMessage.value = '' }, 3000)
  } catch (err) { error.value = err?.response?.data?.detail || err.message }
  finally { saving.value = false }
}

function handleKeydown(event) {
  if (event.key === 'Escape' && editingKey.value && !confirmDialog.show) requestCloseEditor()
}

watch(editingKey, (value) => { document.body.style.overflow = value ? 'hidden' : '' })
onMounted(() => { load(); document.addEventListener('keydown', handleKeydown) })
onBeforeUnmount(() => { document.body.style.overflow = ''; document.removeEventListener('keydown', handleKeydown) })
</script>
