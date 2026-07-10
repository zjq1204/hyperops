<template>
  <AdminLayout>
    <PageFrame
      variant="soft"
      :title="t('adminPages.monitoring.probesTitle')"
    >
      <AdminListSection>
        <template #filterFields>
          <label class="admin-filter-field">
            <span class="admin-filter-label">{{ t('adminPages.monitoring.probeType') }}</span>
            <select v-model="filters.type" class="admin-filter-control" @change="load">
              <option value="">{{ t('common.all') }}</option>
              <option value="http">HTTP</option>
              <option value="tcp">TCP</option>
              <option value="icmp">ICMP</option>
            </select>
          </label>
        </template>
        <template #filterActions>
          <BaseButton variant="outline" size="sm" :loading="loading" @click="load">
            {{ t('common.refresh') }}
          </BaseButton>
          <BaseButton variant="outline" size="sm" :loading="loadingHttpSdConfig" @click="openPrometheusConfig">
            {{ t('adminPages.monitoring.prometheusConfig') }}
          </BaseButton>
          <BaseButton variant="primary" size="sm" @click="openCreateForm">
            {{ t('common.add') }}
          </BaseButton>
        </template>

        <AdminPageState :loading="loading" :error="error" :empty="false">
          <section class="grid gap-4">
            <div class="flex flex-wrap gap-2">
              <button
                v-for="tab in tabs"
                :key="tab.key"
                type="button"
                class="rounded-lg border px-3 py-2 text-sm font-semibold transition"
                :class="activeTab === tab.key ? 'border-slate-900 bg-slate-900 text-white' : 'border-slate-200 bg-white text-slate-600 hover:border-slate-300 hover:text-slate-900'"
                @click="switchTab(tab.key)"
              >
                {{ tab.label }}
              </button>
            </div>

            <section v-if="activeTab === 'targets'" class="rounded-xl border border-slate-200 bg-white px-4 py-3 shadow-sm">
              <div class="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
                <div class="min-w-0">
                  <div class="flex flex-wrap items-center gap-2">
                    <h2 class="text-sm font-semibold text-slate-900">
                      {{ t('adminPages.monitoring.prometheusRealityState') }}
                    </h2>
                    <span :class="prometheusConnected ? 'border-emerald-200 bg-emerald-50 text-emerald-700' : 'border-slate-200 bg-slate-50 text-slate-500'" class="inline-flex rounded-full border px-2.5 py-1 text-xs font-semibold">
                      {{ prometheusConnected ? t('adminPages.monitoring.connected') : t('adminPages.monitoring.notConnected') }}
                    </span>
                  </div>
                  <p v-if="prometheusSummary.error" class="mt-1 text-xs leading-5 text-rose-600">
                    {{ prometheusSummary.error }}
                  </p>
                </div>
                <div class="grid grid-cols-3 gap-2 text-right">
                  <div v-for="item in prometheusStats" :key="item.label" class="rounded-lg bg-slate-50 px-3 py-2">
                    <p class="text-[11px] font-medium text-slate-500">{{ item.label }}</p>
                    <p class="mt-1 text-lg font-semibold text-slate-900">{{ item.value }}</p>
                  </div>
                </div>
              </div>
            </section>

            <section
              v-if="activeTab === 'targets' && probeFindings.length"
              class="rounded-xl border border-amber-200 bg-amber-50/60 px-4 py-3"
            >
              <div class="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                <div class="min-w-0">
                  <h2 class="text-sm font-semibold text-amber-900">
                    {{ t('adminPages.monitoring.governanceFindingsTitle') }}
                  </h2>
                </div>
                <div class="flex flex-wrap gap-2">
                  <span
                    v-for="finding in probeFindings"
                    :key="finding.id"
                    class="inline-flex items-center gap-2 rounded-full border border-amber-200 bg-white px-3 py-1.5 text-xs font-semibold text-amber-800"
                  >
                    <span class="max-w-[18rem] truncate">{{ finding.title }}</span>
                    <BaseButton
                      v-if="finding.recommended_action === 'create_probe_target'"
                      variant="primary"
                      size="sm"
                      :loading="resolvingFindingId === finding.id"
                      @click="resolveProbeFinding(finding)"
                    >
                      {{ t('adminPages.monitoring.createProbeTarget') }}
                    </BaseButton>
                    <BaseButton
                      variant="ghost"
                      size="sm"
                      :loading="resolvingFindingId === finding.id"
                      @click="ignoreProbeFinding(finding)"
                    >
                      {{ t('adminPages.monitoring.ignoreFinding') }}
                    </BaseButton>
                  </span>
                </div>
              </div>
            </section>

            <AdminTable v-if="activeTab === 'targets'">
              <thead>
                <tr>
                  <th class="admin-table-head">{{ t('adminPages.monitoring.probeType') }}</th>
                  <th class="admin-table-head">{{ t('adminPages.monitoring.target') }}</th>
                  <th class="admin-table-head">{{ t('adminPages.monitoring.probeNode') }}</th>
                  <th class="admin-table-head">{{ t('adminPages.monitoring.labels') }}</th>
                  <th class="admin-table-head">{{ t('adminPages.monitoring.configStatus') }}</th>
                  <th class="admin-table-head">{{ t('adminPages.monitoring.prometheusStatus') }}</th>
                  <th class="admin-table-head">{{ t('common.actions') }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-if="!targets.length" class="admin-table-row">
                  <td class="admin-table-cell text-slate-400" colspan="7">
                    {{ t('common.noData') }}
                  </td>
                </tr>
                <tr v-for="target in targets" :key="target.id" class="admin-table-row">
                  <td class="admin-table-cell font-semibold uppercase text-slate-900">
                    {{ target.type }}
                  </td>
                  <td class="admin-table-cell break-all text-slate-700">{{ target.target }}</td>
                  <td class="admin-table-cell">
                    <div class="grid gap-1">
                      <span class="font-semibold text-slate-800">
                        {{ target.probe_node_name || t('adminPages.monitoring.probeNodeNotSelected') }}
                      </span>
                      <span v-if="target.blackbox_address" class="font-mono text-xs text-slate-500">
                        {{ target.blackbox_address }}
                      </span>
                    </div>
                  </td>
                  <td class="admin-table-cell text-slate-500">
                    <div class="flex max-w-md flex-wrap gap-1.5">
                      <span
                        v-for="item in labelPairs(target.labels)"
                        :key="item"
                        class="rounded-full border border-slate-200 bg-slate-50 px-2 py-1 text-xs font-medium text-slate-600"
                      >
                        {{ item }}
                      </span>
                      <span v-if="!labelPairs(target.labels).length" class="text-slate-400">
                        {{ t('common.emptyValue') }}
                      </span>
                    </div>
                  </td>
                  <td class="admin-table-cell">
                    <span
                      class="inline-flex rounded-full border px-2.5 py-1 text-xs font-semibold"
                      :class="target.enabled ? 'border-emerald-200 bg-emerald-50 text-emerald-700' : 'border-slate-200 bg-slate-50 text-slate-500'"
                    >
                      {{ target.enabled ? t('adminPages.monitoring.configActive') : t('adminPages.monitoring.configDisabled') }}
                    </span>
                  </td>
                  <td class="admin-table-cell">
                    <div class="grid gap-1.5">
                      <span
                        v-for="finding in targetFindings(target)"
                        :key="finding.id"
                        class="inline-flex w-fit rounded-full border border-amber-200 bg-amber-50 px-2.5 py-1 text-xs font-semibold text-amber-700"
                      >
                        {{ finding.title }}
                      </span>
                      <span
                        class="inline-flex w-fit rounded-full border px-2.5 py-1 text-xs font-semibold"
                        :class="prometheusStatusClass(prometheusStatusFor(target).status)"
                      >
                        {{ prometheusStatusText(prometheusStatusFor(target).status) }}
                      </span>
                      <span
                        v-if="prometheusStatusFor(target).last_error"
                        class="max-w-xs break-words text-xs text-rose-600"
                      >
                        {{ prometheusStatusFor(target).last_error }}
                      </span>
                    </div>
                  </td>
                  <td class="admin-table-cell">
                    <div class="admin-row-actions">
                      <BaseButton variant="outline" size="sm" @click="editTarget(target)">
                        {{ t('common.edit') }}
                      </BaseButton>
                      <BaseButton variant="ghost" size="sm" @click="removeTarget(target)">
                        {{ t('common.delete') }}
                      </BaseButton>
                    </div>
                  </td>
                </tr>
              </tbody>
            </AdminTable>

            <section v-if="activeTab === 'nodes'" class="grid gap-4">
              <div class="flex flex-col gap-3 rounded-xl border border-slate-200 bg-white px-4 py-3 shadow-sm lg:flex-row lg:items-center lg:justify-between">
                <div>
                  <h2 class="text-sm font-semibold text-slate-900">
                    {{ t('adminPages.monitoring.probeNodes') }}
                  </h2>
                  <p class="mt-1 text-xs text-slate-500">
                    {{ t('adminPages.monitoring.probeNodesHint') }}
                  </p>
                </div>
                <BaseButton variant="primary" size="sm" @click="openNodeForm">
                  {{ t('adminPages.monitoring.addProbeNode') }}
                </BaseButton>
              </div>
              <AdminTable>
                <thead>
                  <tr>
                    <th class="admin-table-head">{{ t('adminPages.monitoring.probeNode') }}</th>
                    <th class="admin-table-head">{{ t('adminPages.monitoring.address') }}</th>
                    <th class="admin-table-head">{{ t('adminPages.monitoring.source') }}</th>
                    <th class="admin-table-head">{{ t('adminPages.monitoring.configStatus') }}</th>
                    <th class="admin-table-head">{{ t('common.actions') }}</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-if="!probeNodes.length" class="admin-table-row">
                    <td class="admin-table-cell text-slate-400" colspan="5">
                      {{ t('adminPages.monitoring.noProbeNodes') }}
                    </td>
                  </tr>
                  <tr v-for="node in probeNodes" :key="node.id" class="admin-table-row">
                    <td class="admin-table-cell font-semibold text-slate-900">{{ node.name }}</td>
                    <td class="admin-table-cell font-mono text-xs text-slate-700">{{ node.blackbox_address }}</td>
                    <td class="admin-table-cell text-slate-600">{{ probeNodeSourceText(node.source) }}</td>
                    <td class="admin-table-cell">
                      <span
                        class="inline-flex rounded-full border px-2.5 py-1 text-xs font-semibold"
                        :class="node.enabled ? 'border-emerald-200 bg-emerald-50 text-emerald-700' : 'border-slate-200 bg-slate-50 text-slate-500'"
                      >
                        {{ node.enabled ? t('adminPages.monitoring.configActive') : t('adminPages.monitoring.configDisabled') }}
                      </span>
                    </td>
                    <td class="admin-table-cell">
                      <div class="admin-row-actions">
                        <BaseButton variant="outline" size="sm" @click="editNode(node)">
                          {{ t('common.edit') }}
                        </BaseButton>
                        <BaseButton variant="ghost" size="sm" @click="removeNode(node)">
                          {{ t('common.delete') }}
                        </BaseButton>
                      </div>
                    </td>
                  </tr>
                </tbody>
              </AdminTable>
            </section>

            <section v-if="activeTab === 'prometheus'" class="grid gap-4">
              <div class="rounded-xl border border-slate-200 bg-white px-4 py-4 shadow-sm">
                <div class="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                  <div>
                    <h2 class="text-sm font-semibold text-slate-900">
                      {{ t('adminPages.monitoring.prometheusConfig') }}
                    </h2>
                    <p class="mt-1 text-xs text-slate-500">
                      {{ t('adminPages.monitoring.prometheusOneTimeConfigHint') }}
                    </p>
                  </div>
                  <div class="flex flex-wrap gap-2">
                    <BaseButton variant="outline" size="sm" :loading="generatingHttpSdToken" @click="generateHttpSdToken">
                      {{ httpSdConfig.token_configured ? t('adminPages.monitoring.regenerateToken') : t('adminPages.monitoring.generateToken') }}
                    </BaseButton>
                    <BaseButton variant="primary" size="sm" :disabled="!httpSdConfig.yaml" @click="copyPrometheusYaml">
                      {{ prometheusYamlCopied ? t('adminPages.monitoring.yamlCopied') : t('adminPages.monitoring.copyYaml') }}
                    </BaseButton>
                  </div>
                </div>
                <pre class="mt-4 max-h-[32rem] overflow-auto whitespace-pre-wrap break-words rounded-xl bg-slate-950 p-4 text-xs leading-6 text-slate-100">{{ httpSdConfig.yaml || t('common.emptyValue') }}</pre>
              </div>
            </section>

          </section>
        </AdminPageState>
      </AdminListSection>
    </PageFrame>

    <BaseModal
      :show="showForm"
      :title="form.id ? t('adminPages.monitoring.editProbe') : t('adminPages.monitoring.addProbe')"
      size="md"
      @close="closeForm"
    >
      <form class="grid gap-4" @submit.prevent="saveTarget">
        <label class="admin-filter-field">
          <span class="admin-filter-label">{{ t('adminPages.monitoring.probeType') }}</span>
          <select v-model="form.type" class="admin-filter-control">
            <option value="http">HTTP</option>
            <option value="tcp">TCP</option>
            <option value="icmp">ICMP</option>
          </select>
        </label>
        <label class="admin-filter-field">
          <span class="admin-filter-label">{{ t('adminPages.monitoring.target') }}</span>
          <input v-model="form.target" class="admin-filter-control" />
        </label>
        <label class="admin-filter-field">
          <span class="admin-filter-label">{{ t('adminPages.monitoring.probeNode') }}</span>
          <select v-model="form.probeNode" class="admin-filter-control">
            <option value="">{{ t('adminPages.monitoring.probeNodeRequired') }}</option>
            <option v-for="node in enabledProbeNodes" :key="node.id" :value="String(node.id)">
              {{ node.name }} · {{ node.blackbox_address }}
            </option>
          </select>
        </label>
        <label class="flex items-center gap-2 text-sm text-slate-700">
          <input v-model="form.enabled" type="checkbox" />
          {{ t('common.enabled') }}
        </label>
        <details class="rounded-lg border border-slate-200/70 bg-slate-50/60 p-4">
          <summary class="cursor-pointer text-sm font-semibold text-slate-800">
            {{ t('adminPages.monitoring.advancedLabels') }}
          </summary>
          <div class="mt-4 grid gap-3 sm:grid-cols-2">
            <label class="admin-filter-field">
              <span class="admin-filter-label">{{ t('adminPages.monitoring.region') }}</span>
              <input v-model="form.region" class="admin-filter-control" />
            </label>
            <label class="admin-filter-field">
              <span class="admin-filter-label">{{ t('adminPages.monitoring.env') }}</span>
              <input v-model="form.env" class="admin-filter-control" />
            </label>
            <label class="admin-filter-field">
              <span class="admin-filter-label">{{ t('adminPages.monitoring.team') }}</span>
              <input v-model="form.team" class="admin-filter-control" />
            </label>
            <label class="admin-filter-field">
              <span class="admin-filter-label">{{ t('adminPages.monitoring.service') }}</span>
              <input v-model="form.service" class="admin-filter-control" />
            </label>
            <label class="admin-filter-field">
              <span class="admin-filter-label">{{ t('adminPages.monitoring.probeScope') }}</span>
              <input v-model="form.probeScope" class="admin-filter-control" />
            </label>
            <label class="admin-filter-field">
              <span class="admin-filter-label">{{ t('adminPages.monitoring.critical') }}</span>
              <select v-model="form.critical" class="admin-filter-control">
                <option value="false">false</option>
                <option value="true">true</option>
              </select>
            </label>
          </div>
        </details>
        <div class="flex justify-end gap-2 pt-2">
          <BaseButton variant="outline" type="button" @click="closeForm">
            {{ t('common.cancel') }}
          </BaseButton>
          <BaseButton variant="primary" type="submit" :loading="saving">
            {{ form.id ? t('common.save') : t('common.add') }}
          </BaseButton>
        </div>
      </form>
    </BaseModal>

    <BaseModal
      :show="showNodeForm"
      :title="nodeForm.id ? t('adminPages.monitoring.editProbeNode') : t('adminPages.monitoring.addProbeNode')"
      size="md"
      @close="closeNodeForm"
    >
      <form class="grid gap-4" @submit.prevent="saveNode">
        <label class="admin-filter-field">
          <span class="admin-filter-label">{{ t('adminPages.monitoring.probeNodeName') }}</span>
          <input v-model.trim="nodeForm.name" class="admin-filter-control" placeholder="blackbox-beijing" />
        </label>
        <div class="grid gap-4 md:grid-cols-[minmax(0,1fr)_8rem]">
          <label class="admin-filter-field">
            <span class="admin-filter-label">{{ t('adminPages.monitoring.address') }}</span>
            <input v-model.trim="nodeForm.address" class="admin-filter-control" placeholder="192.168.7.159" />
          </label>
          <label class="admin-filter-field">
            <span class="admin-filter-label">{{ t('adminPages.monitoring.blackboxPort') }}</span>
            <input v-model.trim="nodeForm.port" class="admin-filter-control" placeholder="9115" />
          </label>
        </div>
        <label class="flex items-center gap-2 text-sm text-slate-700">
          <input v-model="nodeForm.enabled" type="checkbox" />
          {{ t('common.enabled') }}
        </label>
        <div class="flex justify-end gap-2 pt-2">
          <BaseButton variant="outline" type="button" @click="closeNodeForm">
            {{ t('common.cancel') }}
          </BaseButton>
          <BaseButton variant="primary" type="submit" :loading="savingNode">
            {{ nodeForm.id ? t('common.save') : t('common.add') }}
          </BaseButton>
        </div>
      </form>
    </BaseModal>

    <BaseModal
      :show="showPrometheusConfig"
      :title="t('adminPages.monitoring.prometheusConfig')"
      size="xl"
      @close="closePrometheusConfig"
    >
      <section class="grid gap-4">
        <div
          v-if="httpSdError"
          class="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm font-semibold text-rose-700"
        >
          {{ httpSdError }}
        </div>

        <div class="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3">
          <div class="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <div class="min-w-0">
              <div class="flex flex-wrap items-center gap-2">
                <p class="text-sm font-semibold text-slate-900">
                  {{ t('adminPages.monitoring.prometheusHttpSdTitle') }}
                </p>
                <span
                  class="inline-flex rounded-full border px-2.5 py-1 text-xs font-semibold"
                  :class="httpSdConfig.token_configured ? 'border-emerald-200 bg-emerald-50 text-emerald-700' : 'border-amber-200 bg-amber-50 text-amber-700'"
                >
                  {{ httpSdConfig.token_configured ? t('adminPages.monitoring.tokenConfigured') : t('adminPages.monitoring.tokenNotConfigured') }}
                </span>
              </div>
              <p class="mt-2 text-xs leading-5 text-slate-500">
                {{ t('adminPages.monitoring.prometheusHttpSdHint') }}
              </p>
            </div>
            <div class="flex flex-wrap gap-2">
              <BaseButton
                variant="outline"
                size="sm"
                :loading="generatingHttpSdToken"
                @click="generateHttpSdToken"
              >
                {{ httpSdConfig.token_configured ? t('adminPages.monitoring.regenerateToken') : t('adminPages.monitoring.generateToken') }}
              </BaseButton>
              <BaseButton
                variant="primary"
                size="sm"
                :disabled="!httpSdConfig.yaml"
                @click="copyPrometheusYaml"
              >
                {{ prometheusYamlCopied ? t('adminPages.monitoring.yamlCopied') : t('adminPages.monitoring.copyYaml') }}
              </BaseButton>
            </div>
          </div>

          <div class="mt-4 grid gap-3 md:grid-cols-3">
            <div class="rounded-lg bg-white px-3 py-3">
              <p class="text-[11px] font-medium text-slate-500">
                {{ t('adminPages.monitoring.tokenSource') }}
              </p>
              <p class="mt-1 text-sm font-semibold text-slate-800">
                {{ tokenSourceText(httpSdConfig.token_source) }}
              </p>
            </div>
            <div class="rounded-lg bg-white px-3 py-3">
              <p class="text-[11px] font-medium text-slate-500">
                {{ t('adminPages.monitoring.tokenPreview') }}
              </p>
              <p class="mt-1 font-mono text-sm font-semibold text-slate-800">
                {{ httpSdConfig.token_preview || t('common.emptyValue') }}
              </p>
            </div>
            <div class="rounded-lg bg-white px-3 py-3">
              <p class="text-[11px] font-medium text-slate-500">
                {{ t('adminPages.monitoring.tokenFilePath') }}
              </p>
              <p class="mt-1 break-all font-mono text-sm font-semibold text-slate-800">
                {{ httpSdConfig.token_file_path || '/etc/prometheus/hyperops-http-sd.token' }}
              </p>
            </div>
          </div>
        </div>

        <div
          v-if="generatedHttpSdToken"
          class="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3"
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
                {{ generatedHttpSdToken }}
              </p>
            </div>
            <BaseButton variant="outline" size="sm" @click="copyGeneratedHttpSdToken">
              {{ httpSdTokenCopied ? t('adminPages.monitoring.tokenCopied') : t('adminPages.monitoring.copyToken') }}
            </BaseButton>
          </div>
        </div>

        <div class="rounded-xl border border-slate-200 bg-white">
          <div class="flex items-center justify-between gap-3 border-b border-slate-100 px-4 py-3">
            <p class="text-sm font-semibold text-slate-900">
              {{ t('adminPages.monitoring.prometheusYaml') }}
            </p>
            <BaseButton
              variant="outline"
              size="sm"
              :disabled="!httpSdConfig.yaml"
              @click="copyPrometheusYaml"
            >
              {{ prometheusYamlCopied ? t('adminPages.monitoring.yamlCopied') : t('adminPages.monitoring.copyYaml') }}
            </BaseButton>
          </div>
          <pre class="max-h-[28rem] overflow-auto whitespace-pre-wrap break-words bg-slate-950 p-4 text-xs leading-6 text-slate-100">{{ httpSdConfig.yaml || t('common.emptyValue') }}</pre>
        </div>
      </section>
    </BaseModal>
  </AdminLayout>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import AdminLayout from '@/admin/layout/AdminLayout.vue'
import AdminListSection from '@/admin/components/AdminListSection.vue'
import AdminPageState from '@/admin/components/AdminPageState.vue'
import AdminTable from '@/admin/components/AdminTable.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseModal from '@/components/ui/BaseModal.vue'
import PageFrame from '@/components/ui/PageFrame.vue'
import { monitoringStackApi } from '@/admin/api/monitoringStack'

const { t } = useI18n()
const loading = ref(false)
const saving = ref(false)
const savingNode = ref(false)
const error = ref('')
const targets = ref([])
const probeNodes = ref([])
const prometheusSummary = ref({})
const probeFindings = ref([])
const resolvingFindingId = ref(null)
const showForm = ref(false)
const showNodeForm = ref(false)
const showPrometheusConfig = ref(false)
const loadingHttpSdConfig = ref(false)
const generatingHttpSdToken = ref(false)
const httpSdConfig = ref({})
const httpSdError = ref('')
const prometheusYamlCopied = ref(false)
const generatedHttpSdToken = ref('')
const httpSdTokenCopied = ref(false)
const filters = reactive({ type: '' })
const form = reactive(defaultForm())
const nodeForm = reactive(defaultNodeForm())

const activeTab = ref('targets')
const tabs = computed(() => [
  { key: 'targets', label: t('adminPages.monitoring.probeTargets') },
  { key: 'nodes', label: t('adminPages.monitoring.probeNodes') },
  { key: 'prometheus', label: t('adminPages.monitoring.prometheusAccess') }
])

const prometheusConnected = computed(() => Boolean(prometheusSummary.value?.connected))
const enabledProbeNodes = computed(() => probeNodes.value.filter((node) => node.enabled))
const prometheusStats = computed(() => [
  {
    label: t('adminPages.monitoring.activeTargets'),
    value: prometheusSummary.value?.active_targets ?? 0
  },
  {
    label: t('adminPages.monitoring.downTargets'),
    value: prometheusSummary.value?.down_targets ?? 0
  },
  {
    label: t('adminPages.monitoring.blackboxTargets'),
    value: prometheusSummary.value?.blackbox_targets ?? 0
  }
])

function defaultForm() {
  return {
    id: '',
    type: 'http',
    target: '',
    probeNode: '',
    enabled: true,
    region: 'center',
    env: 'prod',
    team: 'ops',
    service: 'website',
    probeScope: 'public',
    critical: 'false'
  }
}

function defaultNodeForm() {
  return {
    id: '',
    name: '',
    address: '',
    port: '9115',
    enabled: true
  }
}

function normalizeList(data) {
  return data?.results || data || []
}

function labelPairs(labels) {
  return Object.entries(labels || {})
    .map(([key, value]) => `${key}=${value}`)
}

function prometheusStatusFor(target) {
  if (!prometheusConnected.value) {
    return {
      status: 'unknown',
      last_error: prometheusSummary.value?.error || t('adminPages.monitoring.prometheusNotConnectedHint')
    }
  }
  const key = `${target.type}:${target.target}`
  const matched = prometheusSummary.value?.probe_statuses?.[key]
  if (!matched) {
    return {
      status: 'unknown',
      last_error: t('adminPages.monitoring.prometheusUnknownHint')
    }
  }
  return {
    status: matched.health === 'up' ? 'up' : 'down',
    last_error: matched.last_error || ''
  }
}

function targetFindings(target) {
  const key = `${target.type}:${target.target}`
  return probeFindings.value.filter((finding) => finding.subject_key === key)
}

function prometheusStatusText(status) {
  if (status === 'up') return t('adminPages.monitoring.statusUp')
  if (status === 'down') return t('adminPages.monitoring.statusDown')
  return t('adminPages.monitoring.statusUnknown')
}

function prometheusStatusClass(status) {
  if (status === 'up') return 'border-emerald-200 bg-emerald-50 text-emerald-700'
  if (status === 'down') return 'border-rose-200 bg-rose-50 text-rose-700'
  return 'border-slate-200 bg-slate-50 text-slate-500'
}

function probeNodeSourceText(source) {
  if (source === 'install') return t('adminPages.monitoring.probeNodeSourceInstall')
  return t('adminPages.monitoring.probeNodeSourceManual')
}

function switchTab(tab) {
  activeTab.value = tab
  if (tab === 'prometheus') loadHttpSdConfig()
}

function tokenSourceText(source) {
  if (source === 'database') return t('adminPages.monitoring.tokenSourceDatabase')
  if (source === 'env') return t('adminPages.monitoring.tokenSourceEnv')
  return t('common.emptyValue')
}

function resetForm() {
  Object.assign(form, defaultForm())
}

function resetNodeForm() {
  Object.assign(nodeForm, defaultNodeForm())
}

function openCreateForm() {
  resetForm()
  if (enabledProbeNodes.value.length === 1) {
    form.probeNode = String(enabledProbeNodes.value[0].id)
  }
  showForm.value = true
}

function closeForm() {
  resetForm()
  showForm.value = false
}

function openNodeForm() {
  resetNodeForm()
  showNodeForm.value = true
}

function closeNodeForm() {
  resetNodeForm()
  showNodeForm.value = false
}

function closePrometheusConfig() {
  showPrometheusConfig.value = false
  httpSdError.value = ''
  prometheusYamlCopied.value = false
  httpSdTokenCopied.value = false
}

function editTarget(target) {
  const labels = target.labels || {}
  Object.assign(form, {
    id: target.id,
    type: target.type || 'http',
    target: target.target || '',
    probeNode: target.probe_node ? String(target.probe_node) : '',
    enabled: Boolean(target.enabled),
    region: labels.region || 'center',
    env: labels.env || 'prod',
    team: labels.team || 'ops',
    service: labels.service || 'website',
    probeScope: labels.probe_scope || 'public',
    critical: labels.critical || 'false'
  })
  showForm.value = true
}

function buildPayload() {
  return {
    type: form.type,
    target: form.target,
    probe_node: form.probeNode || null,
    enabled: form.enabled,
    labels: {
      region: form.region,
      env: form.env,
      team: form.team,
      service: form.service,
      probe_scope: form.probeScope,
      critical: form.critical
    }
  }
}

function editNode(node) {
  Object.assign(nodeForm, {
    id: node.id,
    name: node.name || '',
    address: node.address || '',
    port: node.port || '9115',
    enabled: Boolean(node.enabled)
  })
  showNodeForm.value = true
}

function buildNodePayload() {
  return {
    name: nodeForm.name,
    address: nodeForm.address,
    port: nodeForm.port || '9115',
    enabled: nodeForm.enabled,
    source: 'manual',
    labels: {}
  }
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const [targetData, nodeData, prometheusData, findingData] = await Promise.all([
      monitoringStackApi.getProbeTargets(filters.type ? { type: filters.type } : {}),
      monitoringStackApi.getProbeNodes(),
      monitoringStackApi.getPrometheusTargetsSummary(),
      monitoringStackApi.getGovernanceFindings({ status: 'open', subject_type: 'probe' })
    ])
    targets.value = normalizeList(targetData)
    probeNodes.value = normalizeList(nodeData)
    prometheusSummary.value = prometheusData || {}
    probeFindings.value = normalizeList(findingData)
  } catch (err) {
    error.value = err?.response?.data?.detail || err.message
  } finally {
    loading.value = false
  }
}

async function resolveProbeFinding(finding) {
  resolvingFindingId.value = finding.id
  try {
    await monitoringStackApi.resolveGovernanceFinding(finding.id, {
      action: finding.recommended_action
    })
    await load()
  } finally {
    resolvingFindingId.value = null
  }
}

async function ignoreProbeFinding(finding) {
  resolvingFindingId.value = finding.id
  try {
    await monitoringStackApi.resolveGovernanceFinding(finding.id, {
      action: 'ignore'
    })
    await load()
  } finally {
    resolvingFindingId.value = null
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

async function loadHttpSdConfig() {
  loadingHttpSdConfig.value = true
  httpSdError.value = ''
  try {
    httpSdConfig.value = await monitoringStackApi.getPrometheusHttpSdConfig()
  } catch (err) {
    httpSdError.value = err?.response?.data?.detail || err.message
  } finally {
    loadingHttpSdConfig.value = false
  }
}

async function openPrometheusConfig() {
  activeTab.value = 'prometheus'
  generatedHttpSdToken.value = ''
  await loadHttpSdConfig()
}

async function generateHttpSdToken() {
  generatingHttpSdToken.value = true
  httpSdError.value = ''
  try {
    const data = await monitoringStackApi.rotatePrometheusHttpSdToken()
    generatedHttpSdToken.value = data?.token || ''
    httpSdTokenCopied.value = false
    await loadHttpSdConfig()
  } catch (err) {
    httpSdError.value = err?.response?.data?.detail || err.message
  } finally {
    generatingHttpSdToken.value = false
  }
}

async function copyPrometheusYaml() {
  const copied = await copyText(httpSdConfig.value?.yaml || '')
  if (!copied) return
  prometheusYamlCopied.value = true
  window.setTimeout(() => {
    prometheusYamlCopied.value = false
  }, 1600)
}

async function copyGeneratedHttpSdToken() {
  const copied = await copyText(generatedHttpSdToken.value)
  if (!copied) return
  httpSdTokenCopied.value = true
  window.setTimeout(() => {
    httpSdTokenCopied.value = false
  }, 1600)
}

async function saveTarget() {
  if (!form.probeNode) {
    error.value = t('adminPages.monitoring.probeNodeRequired')
    return
  }
  saving.value = true
  error.value = ''
  try {
    if (form.id) await monitoringStackApi.updateProbeTarget(form.id, buildPayload())
    else await monitoringStackApi.createProbeTarget(buildPayload())
    closeForm()
    await load()
  } finally {
    saving.value = false
  }
}

async function saveNode() {
  savingNode.value = true
  error.value = ''
  try {
    if (nodeForm.id) await monitoringStackApi.updateProbeNode(nodeForm.id, buildNodePayload())
    else await monitoringStackApi.createProbeNode(buildNodePayload())
    closeNodeForm()
    await load()
  } catch (err) {
    error.value = err?.response?.data?.detail || err.message
  } finally {
    savingNode.value = false
  }
}

async function removeNode(node) {
  await monitoringStackApi.deleteProbeNode(node.id)
  if (nodeForm.id === node.id) closeNodeForm()
  await load()
}

async function removeTarget(target) {
  await monitoringStackApi.deleteProbeTarget(target.id)
  if (form.id === target.id) closeForm()
  await load()
}

onMounted(load)
</script>
