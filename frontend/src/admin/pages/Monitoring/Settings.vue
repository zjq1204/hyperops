<template>
  <AdminLayout>
    <PageFrame
      variant="soft"
      :title="t('adminPages.monitoring.settingsTitle')"
    >
      <AdminListSection>
        <template #toolbarEnd>
          <BaseButton variant="outline" size="sm" :loading="loading" @click="load">
            {{ t('common.refresh') }}
          </BaseButton>
          <BaseButton variant="primary" size="sm" :loading="saving" @click="saveConfig">
            {{ t('common.save') }}
          </BaseButton>
        </template>

        <AdminPageState :loading="loading" :error="error" :empty="false">
          <section class="grid gap-4">
            <div
              v-if="saveMessage"
              class="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm font-semibold text-emerald-800"
            >
              {{ saveMessage }}
            </div>

            <section class="grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(0,0.9fr)]">
              <article class="admin-workbench-panel p-5">
                <div class="flex items-start justify-between gap-3">
                  <div>
                    <p class="text-sm font-semibold text-slate-900">
                      {{ t('adminPages.monitoring.externalIntegrations') }}
                    </p>
                  </div>
                  <span :class="connectionPillClass(Boolean(form.n9eUrl || form.prometheusUrl || form.grafanaUrl))">
                    {{ t('adminPages.monitoring.configState') }}
                  </span>
                </div>
                <div class="mt-5 grid gap-4 md:grid-cols-2">
                  <label class="admin-filter-field md:col-span-2">
                    <span class="admin-filter-label">{{ t('adminPages.monitoring.n9eUrl') }}</span>
                    <input v-model.trim="form.n9eUrl" class="admin-filter-control" placeholder="http://monitor-n9e:17000" />
                  </label>
                  <label class="admin-filter-field">
                    <span class="admin-filter-label">{{ t('adminPages.monitoring.user') }}</span>
                    <input v-model.trim="form.n9eUsername" class="admin-filter-control" placeholder="root" />
                  </label>
                  <label class="admin-filter-field">
                    <span class="admin-filter-label">
                      {{ t('adminPages.monitoring.n9ePassword') }}
                      <span v-if="hasPassword" class="ml-2 text-xs font-normal text-emerald-600">
                        {{ t('adminPages.monitoring.passwordConfigured') }}
                      </span>
                    </span>
                    <input
                      v-model="form.n9ePassword"
                      type="password"
                      class="admin-filter-control"
                      :placeholder="hasPassword ? t('adminPages.monitoring.passwordKeepHint') : ''"
                    />
                  </label>
                  <label class="admin-filter-field md:col-span-2">
                    <span class="admin-filter-label">{{ t('adminPages.monitoring.prometheusUrl') }}</span>
                    <input v-model.trim="form.prometheusUrl" class="admin-filter-control" placeholder="http://monitor-prometheus:9090" />
                  </label>
                  <label class="admin-filter-field md:col-span-2">
                    <span class="admin-filter-label">{{ t('adminPages.monitoring.grafanaUrl') }}</span>
                    <input v-model.trim="form.grafanaUrl" class="admin-filter-control" placeholder="http://monitor-grafana:3000" />
                  </label>
                </div>
              </article>

              <article class="admin-workbench-panel p-5">
                <div>
                  <p class="text-sm font-semibold text-slate-900">
                    {{ t('adminPages.monitoring.installerDefaults') }}
                  </p>
                </div>
                <div class="mt-5 grid gap-4">
                  <label class="admin-filter-field">
                    <span class="admin-filter-label">{{ t('adminPages.monitoring.baseUrl') }}</span>
                    <input v-model.trim="form.installerBaseUrl" class="admin-filter-control" />
                  </label>
                  <label class="admin-filter-field">
                    <span class="admin-filter-label">{{ t('adminPages.monitoring.installDir') }}</span>
                    <input v-model.trim="form.categrafInstallDir" class="admin-filter-control" />
                  </label>
                  <label class="admin-filter-field">
                    <span class="admin-filter-label">{{ t('adminPages.monitoring.blackboxInstallDir') }}</span>
                    <input v-model.trim="form.blackboxInstallDir" class="admin-filter-control" />
                  </label>
                  <div class="grid gap-4 md:grid-cols-[8rem_minmax(0,1fr)]">
                    <label class="admin-filter-field">
                      <span class="admin-filter-label">{{ t('adminPages.monitoring.blackboxPort') }}</span>
                      <input v-model.trim="form.blackboxPort" class="admin-filter-control" />
                    </label>
                    <label class="admin-filter-field">
                      <span class="admin-filter-label">{{ t('adminPages.monitoring.blackboxImage') }}</span>
                      <input v-model.trim="form.blackboxImage" class="admin-filter-control" />
                    </label>
                  </div>
                  <div class="flex justify-between gap-3 pt-1">
                    <router-link class="btn btn-outline btn-sm" to="/management/monitoring/installers">
                      {{ t('adminPages.monitoring.advancedInstallerPage') }}
                    </router-link>
                  </div>
                </div>
              </article>
            </section>

            <article class="admin-workbench-panel p-5">
              <div class="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                <div class="min-w-0">
                  <div class="flex flex-wrap items-center gap-2">
                    <p class="text-sm font-semibold text-slate-900">
                      {{ t('adminPages.monitoring.prometheusHttpSdTitle') }}
                    </p>
                    <span :class="connectionPillClass(Boolean(httpSd.token_configured))">
                      {{ httpSd.token_configured ? t('adminPages.monitoring.tokenConfigured') : t('adminPages.monitoring.tokenNotConfigured') }}
                    </span>
                  </div>
                  <p class="mt-2 max-w-3xl text-xs leading-5 text-slate-500">
                    {{ t('adminPages.monitoring.prometheusHttpSdHint') }}
                  </p>
                </div>
                <div class="flex flex-wrap gap-2">
                  <BaseButton variant="outline" size="sm" :loading="rotatingToken" @click="rotateHttpSdToken">
                    {{ httpSd.token_configured ? t('adminPages.monitoring.regenerateToken') : t('adminPages.monitoring.generateToken') }}
                  </BaseButton>
                  <router-link class="btn btn-outline btn-sm" to="/management/monitoring/probes">
                    {{ t('adminPages.monitoring.viewPrometheusConfig') }}
                  </router-link>
                </div>
              </div>

              <div class="mt-4 grid gap-3 md:grid-cols-3">
                <div class="rounded-lg bg-slate-50 px-3 py-3">
                  <p class="text-[11px] font-medium text-slate-500">
                    {{ t('adminPages.monitoring.tokenSource') }}
                  </p>
                  <p class="mt-1 text-sm font-semibold text-slate-800">
                    {{ tokenSourceText(httpSd.token_source) }}
                  </p>
                </div>
                <div class="rounded-lg bg-slate-50 px-3 py-3">
                  <p class="text-[11px] font-medium text-slate-500">
                    {{ t('adminPages.monitoring.tokenPreview') }}
                  </p>
                  <p class="mt-1 font-mono text-sm font-semibold text-slate-800">
                    {{ httpSd.token_preview || t('common.emptyValue') }}
                  </p>
                </div>
                <div class="rounded-lg bg-slate-50 px-3 py-3">
                  <p class="text-[11px] font-medium text-slate-500">
                    {{ t('adminPages.monitoring.tokenFilePath') }}
                  </p>
                  <p class="mt-1 break-all font-mono text-sm font-semibold text-slate-800">
                    {{ httpSd.token_file_path || '/etc/prometheus/hyperops-http-sd.token' }}
                  </p>
                </div>
              </div>

              <div
                v-if="generatedToken"
                class="mt-4 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3"
              >
                <div class="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                  <div class="min-w-0">
                    <p class="text-sm font-semibold text-amber-900">
                      {{ t('adminPages.monitoring.generatedToken') }}
                    </p>
                    <p class="mt-1 text-xs leading-5 text-amber-800">
                      {{ t('adminPages.monitoring.generatedTokenHint') }}
                    </p>
                    <p class="mt-2 break-all rounded-lg bg-white px-3 py-2 font-mono text-xs text-slate-900">
                      {{ generatedToken }}
                    </p>
                  </div>
                  <BaseButton variant="outline" size="sm" @click="copyGeneratedToken">
                    {{ tokenCopied ? t('adminPages.monitoring.tokenCopied') : t('adminPages.monitoring.copyToken') }}
                  </BaseButton>
                </div>
              </div>
            </article>

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
import PageFrame from '@/components/ui/PageFrame.vue'
import { monitoringStackApi } from '@/admin/api/monitoringStack'

const { t } = useI18n()
const loading = ref(false)
const saving = ref(false)
const rotatingToken = ref(false)
const error = ref('')
const saveMessage = ref('')
const config = ref({})
const generatedToken = ref('')
const tokenCopied = ref(false)
const form = reactive({
  n9eUrl: '',
  n9eUsername: '',
  n9ePassword: '',
  prometheusUrl: '',
  grafanaUrl: '',
  installerBaseUrl: '',
  categrafInstallDir: '',
  blackboxInstallDir: '',
  blackboxPort: '',
  blackboxImage: ''
})

const hasPassword = computed(() => Boolean(config.value?.n9e?.has_password))
const httpSd = computed(() => config.value?.http_sd || {})

function connectionPillClass(connected) {
  return [
    'inline-flex rounded-full border px-2.5 py-1 text-xs font-semibold',
    connected
      ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
      : 'border-slate-200 bg-slate-50 text-slate-500'
  ].join(' ')
}

function fillForm(data) {
  const nextInstaller = data?.installer || {}
  form.n9eUrl = data?.n9e_url || nextInstaller?.n9e_url || ''
  form.n9eUsername = data?.n9e?.username || ''
  form.n9ePassword = ''
  form.prometheusUrl = data?.prometheus_url || ''
  form.grafanaUrl = data?.grafana_url || ''
  form.installerBaseUrl = nextInstaller?.base_url || ''
  form.categrafInstallDir = nextInstaller?.install_dir || ''
  form.blackboxInstallDir = nextInstaller?.blackbox_dir || ''
  form.blackboxPort = nextInstaller?.blackbox_port || ''
  form.blackboxImage = nextInstaller?.blackbox_image || ''
}

function configPayload() {
  return {
    n9e_url: form.n9eUrl,
    n9e_username: form.n9eUsername,
    n9e_password: form.n9ePassword,
    prometheus_url: form.prometheusUrl,
    grafana_url: form.grafanaUrl,
    installer_base_url: form.installerBaseUrl,
    categraf_install_dir: form.categrafInstallDir,
    blackbox_install_dir: form.blackboxInstallDir,
    blackbox_port: form.blackboxPort,
    blackbox_image: form.blackboxImage
  }
}

function tokenSourceText(source) {
  if (source === 'database') return t('adminPages.monitoring.tokenSourceDatabase')
  if (source === 'env') return t('adminPages.monitoring.tokenSourceEnv')
  return t('common.emptyValue')
}

async function load() {
  loading.value = true
  error.value = ''
  saveMessage.value = ''
  try {
    const configData = await monitoringStackApi.getConfig()
    config.value = configData || {}
    generatedToken.value = ''
    tokenCopied.value = false
    fillForm(config.value)
  } catch (err) {
    error.value = err?.response?.data?.detail || err.message
  } finally {
    loading.value = false
  }
}

async function copyText(text) {
  if (!text) return false
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text)
      return true
    }
  } catch (_err) {
    // Continue to textarea fallback for non-secure origins.
  }
  const textarea = document.createElement('textarea')
  textarea.value = text
  textarea.setAttribute('readonly', '')
  textarea.style.position = 'fixed'
  textarea.style.left = '-9999px'
  document.body.appendChild(textarea)
  textarea.select()
  const copied = document.execCommand('copy')
  document.body.removeChild(textarea)
  return copied
}

async function rotateHttpSdToken() {
  rotatingToken.value = true
  error.value = ''
  saveMessage.value = ''
  try {
    const data = await monitoringStackApi.rotatePrometheusHttpSdToken()
    generatedToken.value = data?.token || ''
    tokenCopied.value = false
    config.value = {
      ...(config.value || {}),
      http_sd: data?.http_sd || {}
    }
    saveMessage.value = t('adminPages.monitoring.tokenGenerated')
  } catch (err) {
    error.value = err?.response?.data?.detail || err.message
  } finally {
    rotatingToken.value = false
  }
}

async function copyGeneratedToken() {
  const copied = await copyText(generatedToken.value)
  if (!copied) return
  tokenCopied.value = true
  window.setTimeout(() => {
    tokenCopied.value = false
  }, 1600)
}

async function saveConfig() {
  saving.value = true
  error.value = ''
  saveMessage.value = ''
  try {
    config.value = await monitoringStackApi.updateConfig(configPayload())
    fillForm(config.value)
    saveMessage.value = t('adminPages.monitoring.configSaved')
  } catch (err) {
    error.value = err?.response?.data?.detail || err.message
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>
