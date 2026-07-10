<template>
  <AdminLayout>
    <PageFrame
      variant="soft"
      :title="t('adminPages.monitoring.installersTitle')"
    >
      <AdminListSection>
        <template #toolbarStart>
          <span v-if="installerVersion" class="admin-summary-pill">{{ installerVersion }}</span>
        </template>
        <template #toolbarEnd>
          <BaseButton variant="outline" size="sm" :loading="loading" @click="load">
            {{ t('common.refresh') }}
          </BaseButton>
          <BaseButton variant="primary" size="sm" :loading="building" @click="buildAssets">
            {{ t('adminPages.monitoring.rebuildAssets') }}
          </BaseButton>
        </template>

        <AdminPageState :loading="loading" :error="error" :empty="false">
          <section class="grid gap-4 xl:grid-cols-[minmax(0,0.85fr)_minmax(28rem,1fr)]">
            <form class="admin-workbench-panel grid gap-5 p-5">
              <div class="grid gap-4 md:grid-cols-2">
                <label class="admin-filter-field">
                  <span class="admin-filter-label">{{ t('adminPages.monitoring.component') }}</span>
                  <select v-model="form.component" class="admin-filter-control">
                    <option value="categraf">Categraf</option>
                    <option value="blackbox">blackbox-exporter</option>
                  </select>
                </label>

                <label v-if="isCategraf" class="admin-filter-field">
                  <span class="admin-filter-label">{{ t('adminPages.monitoring.clientType') }}</span>
                  <select v-model="form.clientType" class="admin-filter-control">
                    <option value="docker">Docker</option>
                    <option value="linux">Linux</option>
                  </select>
                </label>

                <label class="admin-filter-field md:col-span-2">
                  <span class="admin-filter-label">{{ t('adminPages.monitoring.baseUrl') }}</span>
                  <input v-model="form.baseUrl" class="admin-filter-control" />
                </label>

                <label v-if="isCategraf" class="admin-filter-field">
                  <span class="admin-filter-label">{{ t('adminPages.monitoring.n9eUrl') }}</span>
                  <input v-model="form.n9eUrl" class="admin-filter-control" />
                </label>

                <label class="admin-filter-field">
                  <span class="admin-filter-label">{{ t('adminPages.monitoring.installDir') }}</span>
                  <input v-model="form.installDir" class="admin-filter-control" />
                </label>

                <label class="admin-filter-field">
                  <span class="admin-filter-label">{{ t('adminPages.monitoring.region') }}</span>
                  <select v-model="form.region" class="admin-filter-control">
                    <option v-for="item in installerOptions.regions" :key="item" :value="item">
                      {{ item }}
                    </option>
                  </select>
                </label>

                <label v-if="isCategraf" class="admin-filter-field">
                  <span class="admin-filter-label">{{ t('adminPages.monitoring.service') }}</span>
                  <select v-model="form.service" class="admin-filter-control">
                    <option v-for="item in installerOptions.services" :key="item" :value="item">
                      {{ item }}
                    </option>
                  </select>
                </label>

                <label v-if="!isCategraf" class="admin-filter-field">
                  <span class="admin-filter-label">{{ t('adminPages.monitoring.probeName') }}</span>
                  <select v-model="form.probeName" class="admin-filter-control">
                    <option v-for="item in installerOptions.probe_names" :key="item" :value="item">
                      {{ item }}
                    </option>
                  </select>
                </label>

                <label v-if="!isCategraf" class="admin-filter-field">
                  <span class="admin-filter-label">{{ t('adminPages.monitoring.blackboxPort') }}</span>
                  <input v-model="form.blackboxPort" class="admin-filter-control" />
                </label>
              </div>

              <details class="rounded-lg border border-slate-200/70 bg-slate-50/60 p-4">
                <summary class="cursor-pointer text-sm font-semibold text-slate-800">
                  {{ t('adminPages.monitoring.advancedOptions') }}
                </summary>

                <div class="mt-4 grid gap-4 md:grid-cols-2">
                  <label v-if="isCategraf" class="admin-filter-field">
                    <span class="admin-filter-label">{{ t('adminPages.monitoring.env') }}</span>
                    <select v-model="form.env" class="admin-filter-control">
                      <option v-for="item in installerOptions.envs" :key="item" :value="item">
                        {{ item }}
                      </option>
                    </select>
                  </label>

                  <label v-if="isCategraf" class="admin-filter-field">
                    <span class="admin-filter-label">{{ t('adminPages.monitoring.team') }}</span>
                    <select v-model="form.team" class="admin-filter-control">
                      <option v-for="item in installerOptions.teams" :key="item" :value="item">
                        {{ item }}
                      </option>
                    </select>
                  </label>

                  <label v-if="isCategraf" class="admin-filter-field">
                    <span class="admin-filter-label">{{ t('adminPages.monitoring.role') }}</span>
                    <select v-model="form.role" class="admin-filter-control">
                      <option v-for="item in installerOptions.roles" :key="item" :value="item">
                        {{ item }}
                      </option>
                    </select>
                  </label>

                  <label v-if="isCategraf" class="admin-filter-field">
                    <span class="admin-filter-label">{{ t('adminPages.monitoring.hostname') }}</span>
                    <input v-model="form.hostname" class="admin-filter-control" />
                  </label>

                  <label class="admin-filter-field md:col-span-2">
                    <span class="admin-filter-label">{{ t('adminPages.monitoring.image') }}</span>
                    <input v-model="form.image" class="admin-filter-control" />
                  </label>
                </div>

                <div v-if="isCategraf" class="mt-4 grid gap-4">
                  <div>
                    <p class="admin-filter-label mb-2">Profile</p>
                    <div class="flex flex-wrap gap-2">
                      <label
                        v-for="profile in commandProfiles"
                        :key="profile.id"
                        class="inline-flex cursor-pointer items-center gap-2 rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-600"
                      >
                        <input
                          v-model="form.profiles"
                          class="mr-2"
                          type="checkbox"
                          :value="profile.id"
                        />
                        {{ profile.id }}
                      </label>
                    </div>
                  </div>

                  <div class="grid gap-4 md:grid-cols-2">
                    <input v-model="form.mysqlAddress" class="admin-filter-control" placeholder="MySQL/RDS address" />
                    <input v-model="form.mysqlUser" class="admin-filter-control" placeholder="MySQL user" />
                    <input v-model="form.mysqlPassword" type="password" class="admin-filter-control" placeholder="MySQL password" />
                    <input v-model="form.mysqlParameters" class="admin-filter-control" placeholder="MySQL parameters" />
                    <input v-model="form.redisAddress" class="admin-filter-control" placeholder="Redis address" />
                    <input v-model="form.redisUsername" class="admin-filter-control" placeholder="Redis user" />
                    <input v-model="form.redisPassword" type="password" class="admin-filter-control" placeholder="Redis password" />
                    <input v-model="form.nginxStatusUrl" class="admin-filter-control" placeholder="Nginx status URL" />
                  </div>
                </div>
              </details>
            </form>

            <div class="admin-workbench-panel overflow-hidden">
              <div class="flex items-center justify-between gap-3 border-b border-slate-200/70 px-5 py-4">
                <div>
                  <p class="text-sm font-semibold text-slate-900">
                    {{ t('adminPages.monitoring.generatedCommand') }}
                  </p>
                </div>
                <BaseButton variant="outline" size="sm" @click="copyCommand">
                  {{ t('adminPages.monitoring.copyCommand') }}
                </BaseButton>
              </div>
              <pre class="max-h-[34rem] overflow-auto whitespace-pre-wrap break-words bg-slate-950 p-5 text-xs leading-6 text-slate-100">{{ installCommand }}</pre>
            </div>
          </section>

          <details class="admin-workbench-panel mt-4">
            <summary class="cursor-pointer text-sm font-semibold text-slate-800">
              {{ t('adminPages.monitoring.installerFiles') }}
            </summary>
            <div class="mt-4">
              <AdminTable>
                <thead>
                  <tr>
                    <th class="admin-table-head">{{ t('common.name') }}</th>
                    <th class="admin-table-head">{{ t('common.status') }}</th>
                    <th class="admin-table-head">{{ t('adminPages.monitoring.size') }}</th>
                    <th class="admin-table-head">{{ t('common.actions') }}</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="asset in assetRows" :key="asset.name" class="admin-table-row">
                    <td class="admin-table-cell font-medium text-slate-900">{{ asset.name }}</td>
                    <td class="admin-table-cell">
                      {{ asset.exists ? t('adminPages.monitoring.assetReady') : t('adminPages.monitoring.assetMissing') }}
                    </td>
                    <td class="admin-table-cell text-slate-500">{{ asset.size || 0 }}</td>
                    <td class="admin-table-cell">
                      <a
                        v-if="asset.exists"
                        class="text-sm font-semibold text-emerald-700 hover:text-emerald-900"
                        :href="`/api/v1/monitoring/installer/${asset.name}`"
                        target="_blank"
                      >
                        {{ t('adminPages.monitoring.download') }}
                      </a>
                      <span v-else class="text-sm text-slate-400">{{ t('common.emptyValue') }}</span>
                    </td>
                  </tr>
                </tbody>
              </AdminTable>
            </div>
          </details>
        </AdminPageState>
      </AdminListSection>
    </PageFrame>
  </AdminLayout>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import AdminLayout from '@/admin/layout/AdminLayout.vue'
import AdminListSection from '@/admin/components/AdminListSection.vue'
import AdminPageState from '@/admin/components/AdminPageState.vue'
import AdminTable from '@/admin/components/AdminTable.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import PageFrame from '@/components/ui/PageFrame.vue'
import { monitoringStackApi } from '@/admin/api/monitoringStack'

const { t } = useI18n()
const loading = ref(false)
const building = ref(false)
const error = ref('')
const config = ref({})
const assets = ref({})
const profiles = ref([])
const form = reactive({
  component: 'categraf',
  clientType: 'docker',
  baseUrl: '',
  n9eUrl: '',
  installDir: '/opt/categraf',
  region: 'beijing-idc',
  env: 'prod',
  team: 'ops',
  service: 'infra',
  role: 'docker-host',
  hostname: '',
  probeName: 'blackbox-beijing-idc',
  blackboxPort: '9115',
  image: 'flashcatcloud/categraf:latest',
  profiles: ['linux-basic', 'docker-host'],
  mysqlAddress: '',
  mysqlUser: '',
  mysqlPassword: '',
  mysqlParameters: 'tls=false',
  redisAddress: '',
  redisUsername: '',
  redisPassword: '',
  nginxStatusUrl: ''
})

const isCategraf = computed(() => form.component === 'categraf')
const installerVersion = computed(() => config.value?.installer_version || '')
const installerOptions = computed(() => {
  const options = config.value?.installer?.options || {}
  return {
    regions: options.regions || ['center'],
    envs: options.envs || ['prod'],
    teams: options.teams || ['ops'],
    services: options.services || ['infra'],
    roles: options.roles || ['docker-host', 'linux-host'],
    probe_names: options.probe_names || ['blackbox-center']
  }
})
const commandProfiles = computed(() =>
  profiles.value.filter((item) =>
    ['linux-basic', 'docker-host', 'mysql-rds', 'redis', 'nginx'].includes(item.id)
  )
)
const assetRows = computed(() =>
  Object.values(assets.value?.assets || {}).sort((a, b) => a.name.localeCompare(b.name))
)
const installerBaseUrl = computed(() => {
  const baseUrl = (form.baseUrl || window.location.origin).replace(/\/+$/, '')
  if (baseUrl.endsWith('/api/v1/monitoring/installer')) return baseUrl
  return `${baseUrl}/api/v1/monitoring/installer`
})
function shellQuote(value) {
  const raw = String(value ?? '')
  if (!raw) return "''"
  if (/^[A-Za-z0-9_./:@%+=,-]+$/.test(raw)) return raw
  return `'${raw.replace(/'/g, `'\"'\"'`)}'`
}

function pushArg(args, option, value) {
  const text = String(value || '').trim()
  if (text) args.push(option, text)
}

const installCommand = computed(() => {
  const baseUrl = installerBaseUrl.value
  if (!isCategraf.value) {
    const args = [
      '--base-url',
      baseUrl,
      '--region',
      form.region,
      '--name',
      form.probeName,
      '--port',
      form.blackboxPort || '9115',
      '--dir',
      form.installDir || '/opt/blackbox-exporter',
      '--image',
      form.image || 'prom/blackbox-exporter:latest'
    ]
    return [
      `curl -fsSL ${shellQuote(`${baseUrl}/install-blackbox.sh`)} | sudo bash -s -- ${args.map(shellQuote).join(' ')}`,
      '',
      `# Prometheus scrape: http://<blackbox-host>:${form.blackboxPort || '9115'}/probe`
    ].join('\n')
  }

  const selectedProfiles = form.profiles.filter(
    (profile) => form.clientType === 'docker' || profile !== 'docker-host'
  )
  const args = [
    '--base-url',
    baseUrl,
    '--n9e',
    (form.n9eUrl || 'http://localhost:17000').replace(/\/+$/, ''),
    '--region',
    form.region,
    '--env',
    form.env || 'prod',
    '--team',
    form.team || 'ops',
    '--service',
    form.service || 'infra',
    '--role',
    form.role || (form.clientType === 'docker' ? 'docker-host' : 'linux-host'),
    '--dir',
    form.installDir || '/opt/categraf',
    '--image',
    form.image || 'flashcatcloud/categraf:latest'
  ]
  pushArg(args, '--hostname', form.hostname)
  if (form.clientType === 'linux') args.push('--no-docker')
  selectedProfiles.forEach((profile) => args.push('--profile', profile))
  pushArg(args, '--mysql-address', form.mysqlAddress)
  pushArg(args, '--mysql-user', form.mysqlUser)
  pushArg(args, '--mysql-password', form.mysqlPassword)
  pushArg(args, '--mysql-parameters', form.mysqlParameters)
  pushArg(args, '--redis-address', form.redisAddress)
  pushArg(args, '--redis-username', form.redisUsername)
  pushArg(args, '--redis-password', form.redisPassword)
  pushArg(args, '--nginx-status-url', form.nginxStatusUrl)
  return `curl -fsSL ${shellQuote(`${baseUrl}/install.sh`)} | sudo bash -s -- ${args.map(shellQuote).join(' ')}`
})

function normalizeList(data) {
  return data?.results || data || []
}

function applyConfig(configData) {
  const installer = configData?.installer || {}
  const options = installer.options || {}
  form.baseUrl = installer.base_url || window.location.origin
  form.n9eUrl = installer.n9e_url || configData?.n9e_url || ''
  form.region = options.regions?.[0] || 'center'
  form.env = options.envs?.includes('prod') ? 'prod' : options.envs?.[0] || 'prod'
  form.team = options.teams?.includes('ops') ? 'ops' : options.teams?.[0] || 'ops'
  form.service = options.services?.includes('infra') ? 'infra' : options.services?.[0] || 'infra'
  form.role = options.roles?.includes('docker-host') ? 'docker-host' : options.roles?.[0] || 'docker-host'
  form.probeName = options.probe_names?.[0] || 'blackbox-center'
  form.blackboxPort = installer.blackbox_port || '9115'
}

function applyComponentDefaults() {
  const installer = config.value?.installer || {}
  if (isCategraf.value) {
    form.installDir = installer.install_dir || '/opt/categraf'
    form.image = 'flashcatcloud/categraf:latest'
    if (form.clientType === 'docker' && form.role === 'linux-host') form.role = 'docker-host'
  } else {
    form.installDir = installer.blackbox_dir || '/opt/blackbox-exporter'
    form.image = installer.blackbox_image || 'prom/blackbox-exporter:latest'
    form.blackboxPort = installer.blackbox_port || '9115'
  }
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const [configData, assetsData, profileData] = await Promise.all([
      monitoringStackApi.getConfig(),
      monitoringStackApi.getInstallerAssets(),
      monitoringStackApi.getProfiles()
    ])
    config.value = configData
    assets.value = assetsData
    profiles.value = normalizeList(profileData)
    applyConfig(configData)
    applyComponentDefaults()
  } catch (err) {
    error.value = err?.response?.data?.detail || err.message
  } finally {
    loading.value = false
  }
}

async function buildAssets() {
  building.value = true
  try {
    assets.value = await monitoringStackApi.buildInstallerAssets()
  } finally {
    building.value = false
  }
}

async function copyCommand() {
  await navigator.clipboard?.writeText(installCommand.value)
}

watch(
  () => form.component,
  () => applyComponentDefaults()
)
watch(
  () => form.clientType,
  (value) => {
    if (value === 'linux' && form.role === 'docker-host') form.role = 'linux-host'
    if (value === 'docker' && form.role === 'linux-host') form.role = 'docker-host'
  }
)

onMounted(load)
</script>
