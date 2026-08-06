<template>
  <AdminLayout>
    <PageFrame variant="soft">
      <template #hero>
        <div
          class="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between"
        >
          <div>
            <h1 class="page-title-soft">
              {{
                isNodesPage
                  ? t('adminPages.monitoring.probeNodesTitle')
                  : t('adminPages.monitoring.probeAccessTitle')
              }}
            </h1>
            <p class="mt-1 text-sm leading-6 text-slate-500">
              {{
                isNodesPage
                  ? t('adminPages.monitoring.probeNodesSubtitle')
                  : t('adminPages.monitoring.probeAccessSubtitle')
              }}
            </p>
          </div>
          <BaseButton
            v-if="isNodesPage"
            variant="primary"
            @click="openBlackboxInstall"
          >
            {{ t('adminPages.monitoring.deployProbeNode') }}
          </BaseButton>
        </div>
      </template>

      <ProbeManagementTabs />

      <AdminPageState :loading="loading" :error="error" :empty="false">
        <div class="grid gap-5">
          <section
            v-if="isNodesPage && probeNodeDiscoveries.length"
            class="overflow-hidden rounded-lg border border-sky-200 bg-white"
          >
            <header
              class="flex flex-col gap-2 border-b border-sky-100 bg-sky-50/70 px-4 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-5"
            >
              <div>
                <h2 class="text-sm font-semibold text-slate-900">
                  {{
                    t('adminPages.monitoring.discoveredProbeNodes', {
                      count: probeNodeDiscoveries.length
                    })
                  }}
                </h2>
                <p class="mt-1 text-xs leading-5 text-slate-600">
                  {{ t('adminPages.monitoring.discoveredProbeNodesHint') }}
                </p>
              </div>
              <span class="text-xs font-medium text-sky-700">
                {{ t('adminPages.monitoring.probeDiscoverySource') }}
              </span>
            </header>
            <div class="divide-y divide-slate-100">
              <article
                v-for="discovery in probeNodeDiscoveries"
                :key="discovery.endpoint"
                class="flex flex-col gap-4 px-4 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-5"
              >
                <div class="min-w-0">
                  <div class="flex flex-wrap items-center gap-x-3 gap-y-1">
                    <p
                      class="break-all font-mono text-sm font-semibold text-slate-900"
                    >
                      {{ discovery.endpoint }}
                    </p>
                    <span
                      class="inline-flex items-center gap-1.5 text-xs font-semibold"
                      :class="
                        discovery.health === 'up'
                          ? 'text-emerald-700'
                          : 'text-rose-700'
                      "
                    >
                      <span class="h-1.5 w-1.5 rounded-full bg-current" />
                      {{ discoveryHealthText(discovery.health) }}
                    </span>
                  </div>
                  <p class="mt-1 text-xs text-slate-500">
                    {{
                      discovery.last_scrape
                        ? t('adminPages.monitoring.lastDiscoveredAt', {
                            time: formatDate(discovery.last_scrape)
                          })
                        : t('adminPages.monitoring.discoveredByPrometheus')
                    }}
                  </p>
                </div>
                <BaseButton
                  variant="primary"
                  size="sm"
                  @click="openOnboardForm(discovery)"
                >
                  {{ t('adminPages.monitoring.onboardProbeNode') }}
                </BaseButton>
              </article>
            </div>
          </section>

          <section
            v-if="isNodesPage"
            class="overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm"
          >
            <header
              class="flex flex-col gap-3 border-b border-slate-200 px-4 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-5"
            >
              <div>
                <h2 class="text-base font-semibold text-slate-900">
                  {{ t('adminPages.monitoring.probeNodes') }}
                </h2>
                <p class="mt-1 text-xs leading-5 text-slate-500">
                  {{ t('adminPages.monitoring.probeNodesSectionHint') }}
                </p>
              </div>
              <BaseButton variant="outline" size="sm" @click="openNodeForm()">
                {{ t('adminPages.monitoring.addProbeNode') }}
              </BaseButton>
            </header>

            <AdminTable
              class="hidden rounded-none border-0 shadow-none md:block"
            >
              <thead>
                <tr>
                  <th class="admin-table-head">
                    {{ t('adminPages.monitoring.probeNode') }}
                  </th>
                  <th class="admin-table-head">
                    {{ t('adminPages.monitoring.address') }}
                  </th>
                  <th class="admin-table-head">
                    {{ t('adminPages.monitoring.probeNodeType') }}
                  </th>
                  <th class="admin-table-head">
                    {{ t('adminPages.monitoring.associatedHost') }}
                  </th>
                  <th class="admin-table-head">
                    {{ t('adminPages.monitoring.associatedTargets') }}
                  </th>
                  <th class="admin-table-head">
                    {{ t('adminPages.monitoring.serviceStatus') }}
                  </th>
                  <th class="admin-table-head">
                    {{ t('adminPages.monitoring.configStatus') }}
                  </th>
                  <th class="admin-table-head">{{ t('common.actions') }}</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="node in probeNodes"
                  :key="node.id"
                  class="admin-table-row"
                >
                  <td class="admin-table-cell font-semibold text-slate-900">
                    {{ node.name }}
                  </td>
                  <td class="admin-table-cell font-mono text-xs text-slate-600">
                    {{ node.blackbox_address }}
                  </td>
                  <td class="admin-table-cell text-slate-600">
                    {{ nodeTypeText(node) }}
                  </td>
                  <td class="admin-table-cell text-slate-600">
                    {{ associatedHostText(node) }}
                  </td>
                  <td class="admin-table-cell text-slate-600">
                    {{
                      t('adminPages.monitoring.probeNodeTargetCount', {
                        count: nodeTargetCount(node.id)
                      })
                    }}
                  </td>
                  <td class="admin-table-cell">
                    <span
                      class="inline-flex items-center gap-2 font-semibold"
                      :class="nodeRuntimeClass(node)"
                    >
                      <span class="h-1.5 w-1.5 rounded-full bg-current" />
                      {{ nodeRuntimeText(node) }}
                    </span>
                  </td>
                  <td class="admin-table-cell">
                    <span
                      class="inline-flex items-center gap-2 font-semibold"
                      :class="
                        node.enabled ? 'text-emerald-700' : 'text-slate-400'
                      "
                    >
                      <span class="h-1.5 w-1.5 rounded-full bg-current" />
                      {{
                        node.enabled
                          ? t('adminPages.monitoring.probeConfigEnabled')
                          : t('adminPages.monitoring.probeConfigDisabled')
                      }}
                    </span>
                  </td>
                  <td class="admin-table-cell">
                    <div class="flex flex-wrap gap-2">
                      <BaseButton
                        variant="outline"
                        size="sm"
                        @click="openNodeForm(node)"
                      >
                        {{ t('common.edit') }}
                      </BaseButton>
                      <BaseButton
                        variant="ghost"
                        size="sm"
                        @click="requestDeleteNode(node)"
                      >
                        {{ t('common.delete') }}
                      </BaseButton>
                    </div>
                  </td>
                </tr>
                <tr v-if="!probeNodes.length" class="admin-table-row">
                  <td class="admin-table-cell text-slate-400" colspan="8">
                    {{ t('adminPages.monitoring.noProbeNodes') }}
                  </td>
                </tr>
              </tbody>
            </AdminTable>

            <div class="divide-y divide-slate-100 md:hidden">
              <article
                v-for="node in probeNodes"
                :key="node.id"
                class="px-4 py-4"
              >
                <div class="flex items-start justify-between gap-3">
                  <div class="min-w-0">
                    <p class="font-semibold text-slate-900">{{ node.name }}</p>
                    <p class="mt-1 break-all font-mono text-xs text-slate-400">
                      {{ node.blackbox_address }}
                    </p>
                  </div>
                  <span
                    class="text-xs font-semibold"
                    :class="
                      node.enabled ? 'text-emerald-700' : 'text-slate-400'
                    "
                  >
                    {{
                      node.enabled
                        ? t('adminPages.monitoring.probeConfigEnabled')
                        : t('adminPages.monitoring.probeConfigDisabled')
                    }}
                  </span>
                </div>
                <p class="mt-3 text-sm text-slate-500">
                  {{ nodeTypeText(node) }} · {{ associatedHostText(node) }} ·
                  {{
                    t('adminPages.monitoring.probeNodeTargetCount', {
                      count: nodeTargetCount(node.id)
                    })
                  }}
                </p>
                <p
                  class="mt-2 text-sm font-semibold"
                  :class="nodeRuntimeClass(node)"
                >
                  {{ t('adminPages.monitoring.serviceStatus') }}：{{
                    nodeRuntimeText(node)
                  }}
                </p>
                <div class="mt-4 flex gap-2 border-t border-slate-100 pt-3">
                  <BaseButton
                    variant="outline"
                    size="sm"
                    @click="openNodeForm(node)"
                    >{{ t('common.edit') }}</BaseButton
                  >
                  <BaseButton
                    variant="ghost"
                    size="sm"
                    @click="requestDeleteNode(node)"
                    >{{ t('common.delete') }}</BaseButton
                  >
                </div>
              </article>
              <p
                v-if="!probeNodes.length"
                class="py-8 text-center text-sm text-slate-400"
              >
                {{ t('adminPages.monitoring.noProbeNodes') }}
              </p>
            </div>
          </section>

          <section
            v-else
            class="overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm"
          >
            <header class="border-b border-slate-200 px-4 py-4 sm:px-5">
              <h2 class="text-base font-semibold text-slate-900">
                {{ t('adminPages.monitoring.prometheusAccess') }}
              </h2>
              <p class="mt-1 text-xs leading-5 text-slate-500">
                {{ t('adminPages.monitoring.prometheusAccessHintShort') }}
              </p>
            </header>
            <div
              class="grid gap-5 px-4 py-5 sm:grid-cols-2 sm:px-5 lg:grid-cols-[1fr_1fr_auto] lg:items-center"
            >
              <div>
                <p class="text-xs font-medium text-slate-400">
                  {{ t('adminPages.monitoring.connectionStatus') }}
                </p>
                <p
                  class="mt-2 inline-flex items-center gap-2 font-semibold"
                  :class="
                    prometheusConnected ? 'text-emerald-700' : 'text-rose-700'
                  "
                >
                  <span class="h-1.5 w-1.5 rounded-full bg-current" />
                  {{
                    prometheusConnected
                      ? t('adminPages.monitoring.connected')
                      : t('adminPages.monitoring.notConnected')
                  }}
                </p>
              </div>
              <div>
                <p class="text-xs font-medium text-slate-400">
                  {{ t('adminPages.monitoring.accessCredential') }}
                </p>
                <p class="mt-2 font-semibold text-slate-800">
                  {{
                    httpSdConfig.token_configured
                      ? t('adminPages.monitoring.tokenConfigured')
                      : t('adminPages.monitoring.tokenNotConfigured')
                  }}
                </p>
              </div>
              <div
                class="flex flex-col gap-2 sm:col-span-2 sm:flex-row lg:col-span-1"
              >
                <BaseButton variant="outline" @click="showTokenModal = true">
                  {{ t('adminPages.monitoring.manageToken') }}
                </BaseButton>
                <BaseButton
                  variant="outline"
                  :disabled="!httpSdConfig.yaml"
                  @click="showYamlModal = true"
                >
                  {{ t('adminPages.monitoring.viewConfiguration') }}
                </BaseButton>
              </div>
            </div>
            <div
              v-if="probeDiscovery.legacy_http_sd?.detected"
              class="flex flex-col gap-3 border-t border-amber-200 bg-amber-50 px-4 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-5"
            >
              <div class="min-w-0">
                <p class="text-sm font-semibold text-amber-950">
                  {{ t('adminPages.monitoring.legacyHttpSdDetected') }}
                </p>
                <p class="mt-1 max-w-3xl text-xs leading-5 text-amber-900">
                  {{ t('adminPages.monitoring.legacyHttpSdHint') }}
                </p>
              </div>
              <BaseButton
                class="shrink-0"
                variant="outline"
                size="sm"
                @click="showYamlModal = true"
              >
                {{ t('adminPages.monitoring.viewMigrationConfig') }}
              </BaseButton>
            </div>
          </section>
        </div>
      </AdminPageState>
    </PageFrame>

    <BaseModal
      :show="showNodeForm"
      :title="
        nodeForm.id
          ? t('adminPages.monitoring.editProbeNode')
          : t('adminPages.monitoring.addProbeNode')
      "
      :close-on-backdrop="false"
      @close="closeNodeForm"
    >
      <form id="probe-node-form" class="grid gap-4" @submit.prevent="saveNode">
        <label class="admin-filter-field">
          <span class="admin-filter-label ml-0">{{
            t('adminPages.monitoring.probeNodeName')
          }}</span>
          <input
            v-model.trim="nodeForm.name"
            class="admin-filter-control"
            required
          />
        </label>
        <div class="grid gap-4 sm:grid-cols-[minmax(0,1fr)_8rem]">
          <label class="admin-filter-field">
            <span class="admin-filter-label ml-0">{{
              t('adminPages.monitoring.address')
            }}</span>
            <input
              v-model.trim="nodeForm.address"
              class="admin-filter-control"
              required
            />
          </label>
          <label class="admin-filter-field">
            <span class="admin-filter-label ml-0">{{
              t('adminPages.monitoring.blackboxPort')
            }}</span>
            <input
              v-model.trim="nodeForm.port"
              class="admin-filter-control"
              inputmode="numeric"
              required
            />
          </label>
        </div>
        <label class="admin-filter-field">
          <span class="admin-filter-label ml-0">{{
            t('adminPages.monitoring.associatedHost')
          }}</span>
          <select v-model="nodeForm.host" class="admin-filter-control">
            <option value="">
              {{ t('adminPages.monitoring.independentProbe') }}
            </option>
            <option v-for="host in hosts" :key="host.id" :value="host.id">
              {{ host.hostname }} · {{ host.address }}
            </option>
          </select>
          <span class="text-xs leading-5 text-slate-500">
            {{ t('adminPages.monitoring.probeHostAssociationHint') }}
          </span>
        </label>
        <label class="flex min-h-11 items-center gap-2 text-sm text-slate-700">
          <input
            v-model="nodeForm.enabled"
            type="checkbox"
            class="h-4 w-4 rounded border-slate-300 text-sky-600 focus:ring-sky-500"
          />
          {{ t('common.enabled') }}
        </label>
      </form>
      <template #footer>
        <div
          class="flex w-full flex-col-reverse gap-2 sm:flex-row sm:justify-end"
        >
          <BaseButton
            variant="outline"
            :disabled="savingNode"
            @click="closeNodeForm"
            >{{ t('common.cancel') }}</BaseButton
          >
          <BaseButton
            form="probe-node-form"
            type="submit"
            variant="primary"
            :loading="savingNode"
            >{{ t('common.save') }}</BaseButton
          >
        </div>
      </template>
    </BaseModal>

    <BaseModal
      :show="showOnboardModal"
      :title="t('adminPages.monitoring.onboardProbeNodeTitle')"
      :close-on-backdrop="false"
      @close="closeOnboardForm"
    >
      <form
        id="probe-node-onboard-form"
        class="grid gap-5"
        @submit.prevent="onboardDiscovery"
      >
        <div class="rounded-lg bg-slate-50 px-4 py-3">
          <p class="text-xs font-medium text-slate-500">
            {{ t('adminPages.monitoring.discoveredEndpoint') }}
          </p>
          <p
            class="mt-1 break-all font-mono text-sm font-semibold text-slate-900"
          >
            {{ selectedDiscovery?.endpoint || t('common.emptyValue') }}
          </p>
        </div>
        <label class="admin-filter-field">
          <span class="admin-filter-label ml-0">{{
            t('adminPages.monitoring.probeNodeName')
          }}</span>
          <input
            v-model.trim="onboardForm.name"
            class="admin-filter-control"
            required
          />
        </label>
        <label
          class="flex items-start gap-3 rounded-lg border border-slate-200 p-4"
        >
          <input
            v-model="onboardForm.bindUnassignedTargets"
            type="checkbox"
            class="mt-0.5 h-4 w-4 rounded border-slate-300 text-sky-600 focus:ring-sky-500"
          />
          <span>
            <span class="block text-sm font-semibold text-slate-800">
              {{
                t('adminPages.monitoring.bindUnassignedTargets', {
                  count: probeDiscovery.unbound_target_count || 0
                })
              }}
            </span>
            <span class="mt-1 block text-xs leading-5 text-slate-500">
              {{ t('adminPages.monitoring.bindUnassignedTargetsHint') }}
            </span>
          </span>
        </label>
      </form>
      <template #footer>
        <div
          class="flex w-full flex-col-reverse gap-2 sm:flex-row sm:justify-end"
        >
          <BaseButton
            variant="outline"
            :disabled="onboarding"
            @click="closeOnboardForm"
          >
            {{ t('common.cancel') }}
          </BaseButton>
          <BaseButton
            form="probe-node-onboard-form"
            type="submit"
            variant="primary"
            :loading="onboarding"
          >
            {{ t('adminPages.monitoring.confirmOnboard') }}
          </BaseButton>
        </div>
      </template>
    </BaseModal>

    <BaseModal
      :show="showBlackboxForm"
      :title="t('adminPages.monitoring.deployProbeNode')"
      size="lg"
      :close-on-backdrop="false"
      @close="closeBlackboxInstall"
    >
      <form
        id="blackbox-install-form"
        class="grid gap-4"
        @submit.prevent="runBlackboxInstall"
      >
        <label class="admin-filter-field">
          <span class="admin-filter-label ml-0">{{
            t('adminPages.monitoring.installTargetHost')
          }}</span>
          <select
            v-model="blackboxForm.hostId"
            class="admin-filter-control"
            required
          >
            <option value="" disabled>
              {{ t('adminPages.monitoring.selectInstallHost') }}
            </option>
            <option v-for="host in hosts" :key="host.id" :value="host.id">
              {{ host.hostname }} · {{ host.address }}
            </option>
          </select>
        </label>
        <div class="grid gap-4 sm:grid-cols-[minmax(0,1fr)_8rem]">
          <label class="admin-filter-field">
            <span class="admin-filter-label ml-0">{{
              t('adminPages.monitoring.probeNodeName')
            }}</span>
            <input
              v-model.trim="blackboxForm.probeName"
              class="admin-filter-control"
              required
            />
          </label>
          <label class="admin-filter-field">
            <span class="admin-filter-label ml-0">{{
              t('adminPages.monitoring.blackboxPort')
            }}</span>
            <input
              v-model.trim="blackboxForm.blackboxPort"
              class="admin-filter-control"
              inputmode="numeric"
              required
            />
          </label>
        </div>
        <label class="admin-filter-field">
          <span class="admin-filter-label ml-0">{{
            t('adminPages.monitoring.installDir')
          }}</span>
          <input
            v-model.trim="blackboxForm.installDir"
            class="admin-filter-control"
            required
          />
        </label>
        <label class="admin-filter-field">
          <span class="admin-filter-label ml-0">{{
            t('adminPages.monitoring.image')
          }}</span>
          <input
            v-model.trim="blackboxForm.image"
            class="admin-filter-control"
            required
          />
        </label>
        <pre
          v-if="blackboxPreviewText"
          class="max-h-72 overflow-auto whitespace-pre-wrap rounded-lg bg-slate-950 p-4 text-xs leading-6 text-slate-100"
          >{{ blackboxPreviewText }}</pre
        >
      </form>
      <template #footer>
        <div
          class="flex w-full flex-col-reverse gap-2 sm:flex-row sm:justify-end"
        >
          <BaseButton
            variant="outline"
            :disabled="runningBlackbox"
            @click="closeBlackboxInstall"
          >
            {{ t('common.cancel') }}
          </BaseButton>
          <BaseButton
            variant="outline"
            :loading="previewingBlackbox"
            :disabled="!blackboxForm.hostId"
            @click="previewBlackbox"
          >
            {{ t('adminPages.monitoring.previewInstall') }}
          </BaseButton>
          <BaseButton
            form="blackbox-install-form"
            type="submit"
            variant="primary"
            :loading="runningBlackbox"
            :disabled="!blackboxForm.hostId"
          >
            {{ t('adminPages.monitoring.startDeployment') }}
          </BaseButton>
        </div>
      </template>
    </BaseModal>

    <BaseModal
      :show="showTokenModal"
      :title="t('adminPages.monitoring.manageToken')"
      :close-on-backdrop="false"
      @close="closeTokenModal"
    >
      <dl class="grid grid-cols-[7rem_minmax(0,1fr)] gap-x-4 gap-y-3 text-sm">
        <dt class="text-slate-400">
          {{ t('adminPages.monitoring.configStatus') }}
        </dt>
        <dd class="font-semibold text-slate-800">
          {{
            httpSdConfig.token_configured
              ? t('adminPages.monitoring.tokenConfigured')
              : t('adminPages.monitoring.tokenNotConfigured')
          }}
        </dd>
        <dt class="text-slate-400">
          {{ t('adminPages.monitoring.tokenPreview') }}
        </dt>
        <dd class="break-all font-mono text-xs text-slate-700">
          {{ httpSdConfig.token_preview || t('common.emptyValue') }}
        </dd>
      </dl>
      <div
        v-if="generatedToken"
        class="mt-5 rounded-lg border border-amber-200 bg-amber-50 p-4"
      >
        <p class="text-sm font-semibold text-amber-900">
          {{ t('adminPages.monitoring.generatedToken') }}
        </p>
        <p class="mt-1 text-xs leading-5 text-amber-800">
          {{ t('adminPages.monitoring.generatedTokenHint') }}
        </p>
        <p
          class="mt-3 break-all rounded-md bg-white px-3 py-2 font-mono text-xs text-slate-800"
        >
          {{ generatedToken }}
        </p>
        <BaseButton
          class="mt-3"
          variant="outline"
          size="sm"
          @click="copyGeneratedToken"
        >
          {{ t('adminPages.monitoring.copyToken') }}
        </BaseButton>
      </div>
      <template #footer>
        <div
          class="flex w-full flex-col-reverse gap-2 sm:flex-row sm:justify-end"
        >
          <BaseButton variant="outline" @click="closeTokenModal">{{
            t('common.close')
          }}</BaseButton>
          <BaseButton
            variant="danger"
            :loading="rotatingToken"
            @click="requestRotateToken"
          >
            {{
              httpSdConfig.token_configured
                ? t('adminPages.monitoring.regenerateToken')
                : t('adminPages.monitoring.generateToken')
            }}
          </BaseButton>
        </div>
      </template>
    </BaseModal>

    <BaseModal
      :show="showYamlModal"
      :title="t('adminPages.monitoring.prometheusConfig')"
      size="lg"
      @close="showYamlModal = false"
    >
      <pre
        class="max-h-[30rem] overflow-auto whitespace-pre-wrap break-words rounded-lg bg-slate-950 p-4 text-xs leading-6 text-slate-100"
        >{{ httpSdConfig.yaml || t('common.emptyValue') }}</pre
      >
      <template #footer>
        <div
          class="flex w-full flex-col-reverse gap-2 sm:flex-row sm:justify-end"
        >
          <BaseButton variant="outline" @click="showYamlModal = false">{{
            t('common.close')
          }}</BaseButton>
          <BaseButton
            variant="primary"
            :disabled="!httpSdConfig.yaml"
            @click="copyPrometheusYaml"
          >
            {{ t('adminPages.monitoring.copyYaml') }}
          </BaseButton>
        </div>
      </template>
    </BaseModal>

    <ConfirmDialog
      :show="confirmDialog.show"
      :title="confirmDialog.title"
      :message="confirmDialog.message"
      :confirm-text="confirmDialog.confirmText"
      :variant="confirmDialog.variant"
      :loading="confirmDialog.loading"
      @close="closeConfirmDialog"
      @confirm="runConfirmedAction"
    />
  </AdminLayout>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import AdminLayout from '@/admin/layout/AdminLayout.vue'
import AdminPageState from '@/admin/components/AdminPageState.vue'
import AdminTable from '@/admin/components/AdminTable.vue'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseModal from '@/components/ui/BaseModal.vue'
import PageFrame from '@/components/ui/PageFrame.vue'
import ProbeManagementTabs from '@/admin/pages/Monitoring/probes/ProbeManagementTabs.vue'
import { monitoringStackApi } from '@/admin/api/monitoringStack'
import { useConfirmDialog } from '@/composables/useConfirmDialog'
import { useToast } from '@/composables/useToast'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const { showSuccess, showError } = useToast()
const {
  confirmDialog,
  requestConfirm,
  closeConfirmDialog,
  runConfirmedAction
} = useConfirmDialog()

const loading = ref(false)
const savingNode = ref(false)
const onboarding = ref(false)
const rotatingToken = ref(false)
const error = ref('')
const probeNodes = ref([])
const targets = ref([])
const hosts = ref([])
const prometheusSummary = ref({})
const probeDiscovery = ref({})
const httpSdConfig = ref({})
const showNodeForm = ref(false)
const showOnboardModal = ref(false)
const showTokenModal = ref(false)
const showYamlModal = ref(false)
const showBlackboxForm = ref(false)
const generatedToken = ref('')
const selectedDiscovery = ref(null)
const nodeForm = reactive(defaultNodeForm())
const onboardForm = reactive({ name: '', bindUnassignedTargets: true })
const previewingBlackbox = ref(false)
const runningBlackbox = ref(false)
const blackboxPreviewText = ref('')
const installerConfig = ref({})
const blackboxForm = reactive(defaultBlackboxForm())
const isNodesPage = computed(() => route.path.endsWith('/nodes'))

const prometheusConnected = computed(() =>
  Boolean(prometheusSummary.value?.connected)
)
const probeNodeDiscoveries = computed(() =>
  Array.isArray(probeDiscovery.value?.discoveries)
    ? probeDiscovery.value.discoveries
    : []
)
const managedNodeStates = computed(() => {
  const states = Array.isArray(probeDiscovery.value?.managed_nodes)
    ? probeDiscovery.value.managed_nodes
    : []
  return new Map(states.map((item) => [String(item.node_id), item]))
})

function normalizeList(data) {
  return data?.results || data || []
}

function defaultNodeForm() {
  return {
    id: '',
    name: '',
    address: '',
    port: '9115',
    host: '',
    source: 'manual',
    enabled: true
  }
}

function defaultBlackboxForm() {
  return {
    hostId: '',
    probeName: 'blackbox-center',
    blackboxPort: '9115',
    installDir: '/opt/blackbox-exporter',
    image: 'prom/blackbox-exporter:latest'
  }
}

function nodeTargetCount(nodeId) {
  return targets.value.filter(
    (target) => String(target.probe_node || '') === String(nodeId)
  ).length
}

function nodeTypeText(node) {
  return node.host
    ? t('adminPages.monitoring.hostProbe')
    : t('adminPages.monitoring.independentProbe')
}

function associatedHostText(node) {
  if (!node.host) return t('adminPages.monitoring.probeHostUnassociated')
  const host = hosts.value.find((item) => String(item.id) === String(node.host))
  return host ? `${host.hostname} · ${host.address}` : `#${node.host}`
}

function nodeRuntimeState(node) {
  if (!node.enabled) return 'disabled'
  return managedNodeStates.value.get(String(node.id))?.health || 'unknown'
}

function nodeRuntimeText(node) {
  const keys = {
    up: 'probeServiceOnline',
    down: 'probeServiceAbnormal',
    disabled: 'componentNotEnabled',
    unknown: 'probeServiceUnknown'
  }
  return t(
    `adminPages.monitoring.${keys[nodeRuntimeState(node)] || keys.unknown}`
  )
}

function nodeRuntimeClass(node) {
  const state = nodeRuntimeState(node)
  if (state === 'up') return 'text-emerald-700'
  if (state === 'down') return 'text-rose-700'
  return 'text-slate-400'
}

function discoveryHealthText(health) {
  return health === 'up'
    ? t('adminPages.monitoring.discoveryOnline')
    : t('adminPages.monitoring.discoveryAbnormal')
}

function formatDate(value) {
  if (!value) return t('common.emptyValue')
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return value
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: 'short',
    timeStyle: 'short'
  }).format(parsed)
}

function openOnboardForm(discovery) {
  selectedDiscovery.value = discovery
  const safeAddress = String(discovery.address || 'probe')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '')
  onboardForm.name = safeAddress.startsWith('blackbox-')
    ? safeAddress
    : `blackbox-${safeAddress || 'probe'}`
  onboardForm.bindUnassignedTargets = true
  showOnboardModal.value = true
}

function closeOnboardForm() {
  if (onboarding.value) return
  showOnboardModal.value = false
  selectedDiscovery.value = null
  onboardForm.name = ''
  onboardForm.bindUnassignedTargets = true
}

function openNodeForm(node = null) {
  Object.assign(nodeForm, defaultNodeForm(), {
    id: node?.id || '',
    name: node?.name || '',
    address: node?.address || '',
    port: node?.port || '9115',
    host: node?.host || '',
    source: node?.source || 'manual',
    enabled: node ? Boolean(node.enabled) : true
  })
  showNodeForm.value = true
}

function closeNodeForm() {
  showNodeForm.value = false
  Object.assign(nodeForm, defaultNodeForm())
}

function closeTokenModal() {
  showTokenModal.value = false
  generatedToken.value = ''
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    if (isNodesPage.value) {
      const [nodeData, targetData, hostData, discoveryData, configData] =
        await Promise.all([
          monitoringStackApi.getProbeNodes(),
          monitoringStackApi.getProbeTargets(),
          monitoringStackApi.getHosts(),
          monitoringStackApi.getProbeNodeDiscoveries(),
          monitoringStackApi.getConfig()
        ])
      probeNodes.value = normalizeList(nodeData)
      targets.value = normalizeList(targetData)
      hosts.value = normalizeList(hostData)
      probeDiscovery.value = discoveryData || {}
      installerConfig.value = configData || {}
    } else {
      const [prometheusData, httpSdData, discoveryData] = await Promise.all([
        monitoringStackApi.getPrometheusTargetsSummary(),
        monitoringStackApi.getPrometheusHttpSdConfig(),
        monitoringStackApi.getProbeNodeDiscoveries()
      ])
      prometheusSummary.value = prometheusData || {}
      httpSdConfig.value = httpSdData || {}
      probeDiscovery.value = discoveryData || {}
    }
  } catch (err) {
    error.value = err?.response?.data?.detail || err.message
  } finally {
    loading.value = false
  }
}

async function onboardDiscovery() {
  if (!selectedDiscovery.value) return
  onboarding.value = true
  try {
    const data = await monitoringStackApi.onboardProbeNode({
      address: selectedDiscovery.value.address,
      port: selectedDiscovery.value.port || '9115',
      name: onboardForm.name,
      bind_unassigned_targets: onboardForm.bindUnassignedTargets
    })
    const boundCount = data?.bound_target_count || 0
    showOnboardModal.value = false
    selectedDiscovery.value = null
    onboardForm.name = ''
    onboardForm.bindUnassignedTargets = true
    showSuccess(
      boundCount
        ? t('adminPages.monitoring.probeNodeOnboardedWithTargets', {
            count: boundCount
          })
        : t('adminPages.monitoring.probeNodeOnboarded')
    )
    await load()
  } catch (err) {
    showError(err?.response?.data?.detail || err.message)
  } finally {
    onboarding.value = false
  }
}

async function saveNode() {
  savingNode.value = true
  try {
    const payload = {
      name: nodeForm.name,
      address: nodeForm.address,
      port: nodeForm.port || '9115',
      enabled: nodeForm.enabled,
      source: nodeForm.source,
      host: nodeForm.host || null,
      labels: {}
    }
    if (nodeForm.id)
      await monitoringStackApi.updateProbeNode(nodeForm.id, payload)
    else await monitoringStackApi.createProbeNode(payload)
    closeNodeForm()
    showSuccess(t('adminPages.monitoring.nodeSaved'))
    await load()
  } catch (err) {
    showError(err?.response?.data?.detail || err.message)
  } finally {
    savingNode.value = false
  }
}

function openBlackboxInstall() {
  const installer = installerConfig.value?.installer || {}
  Object.assign(blackboxForm, defaultBlackboxForm(), {
    installDir: installer.blackbox_dir || '/opt/blackbox-exporter',
    image: installer.blackbox_image || 'prom/blackbox-exporter:latest',
    blackboxPort: installer.blackbox_port || '9115',
    probeName: installer.options?.probe_names?.[0] || 'blackbox-center'
  })
  blackboxPreviewText.value = ''
  showBlackboxForm.value = true
}

function closeBlackboxInstall() {
  showBlackboxForm.value = false
  blackboxPreviewText.value = ''
  Object.assign(blackboxForm, defaultBlackboxForm())
}

function blackboxJobPayload() {
  const installer = installerConfig.value?.installer || {}
  const base = installer.base_url || window.location.origin
  const baseUrl = base.endsWith('/api/v1/monitoring/installer')
    ? base
    : `${base.replace(/\/+$/, '')}/api/v1/monitoring/installer`
  return {
    component: 'blackbox',
    host_ids: [blackboxForm.hostId],
    profiles: [],
    base_url: baseUrl,
    n9e_url: '',
    install_dir: blackboxForm.installDir,
    image: blackboxForm.image,
    probe_name: blackboxForm.probeName,
    blackbox_port: blackboxForm.blackboxPort
  }
}

async function previewBlackbox() {
  previewingBlackbox.value = true
  try {
    const data = await monitoringStackApi.previewAnsible(blackboxJobPayload())
    blackboxPreviewText.value = [
      '# inventory',
      data.inventory,
      '# vars',
      JSON.stringify(data.vars, null, 2)
    ].join('\n')
  } catch (err) {
    showError(err?.response?.data?.detail || err.message)
  } finally {
    previewingBlackbox.value = false
  }
}

async function runBlackboxInstall() {
  runningBlackbox.value = true
  try {
    const job = await monitoringStackApi.createJob(blackboxJobPayload())
    closeBlackboxInstall()
    showSuccess(
      t('adminPages.monitoring.jobDispatched', { id: job.id }),
      8000,
      {
        title: t('adminPages.monitoring.jobDispatchedTitle'),
        action: {
          label: t('adminPages.monitoring.viewTaskDetails'),
          onClick: () =>
            router.push({
              path: '/management/monitoring/jobs',
              query: { job: String(job.id) }
            })
        }
      }
    )
    await load()
  } catch (err) {
    showError(err?.response?.data?.detail || err.message)
  } finally {
    runningBlackbox.value = false
  }
}

function requestDeleteNode(node) {
  const count = nodeTargetCount(node.id)
  requestConfirm({
    title: t('adminPages.monitoring.deleteNodeTitle'),
    message: count
      ? t('adminPages.monitoring.deleteUsedNodeMessage', {
          name: node.name,
          count
        })
      : t('adminPages.monitoring.deleteNodeMessage', { name: node.name }),
    confirmText: t('common.delete'),
    variant: 'danger',
    onConfirm: async () => {
      await monitoringStackApi.deleteProbeNode(node.id)
      showSuccess(t('adminPages.monitoring.nodeDeleted'))
      await load()
    }
  })
}

function requestRotateToken() {
  requestConfirm({
    title: t('adminPages.monitoring.rotateTokenTitle'),
    message: t('adminPages.monitoring.rotateTokenWarning'),
    confirmText: t('adminPages.monitoring.confirmRotateToken'),
    variant: 'danger',
    onConfirm: rotateToken
  })
}

async function rotateToken() {
  rotatingToken.value = true
  try {
    const data = await monitoringStackApi.rotatePrometheusHttpSdToken()
    generatedToken.value = data?.token || ''
    httpSdConfig.value = await monitoringStackApi.getPrometheusHttpSdConfig()
    showSuccess(t('adminPages.monitoring.tokenRotated'))
  } catch (err) {
    showError(err?.response?.data?.detail || err.message)
  } finally {
    rotatingToken.value = false
  }
}

async function copyText(text) {
  if (!text) return false
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text)
      return true
    }
  } catch (_error) {
    // Continue with the fallback for non-secure origins.
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

async function copyGeneratedToken() {
  const copied = await copyText(generatedToken.value)
  copied
    ? showSuccess(t('adminPages.monitoring.tokenCopied'))
    : showError(t('adminPages.monitoring.copyFailed'))
}

async function copyPrometheusYaml() {
  const copied = await copyText(httpSdConfig.value?.yaml || '')
  copied
    ? showSuccess(t('adminPages.monitoring.yamlCopied'))
    : showError(t('adminPages.monitoring.copyFailed'))
}

onMounted(load)
watch(() => route.path, load)
</script>
