<template>
  <AppLayout>
    <PageFrame
      :eyebrow="t('jenkinsWorkspace.eyebrow')"
      :title="t('jenkinsWorkspace.title')"
      :subtitle="t('jenkinsWorkspace.subtitle')"
    >
      <section class="workspace-inline-summary">
        <div class="workspace-inline-stat">
          <span>{{ t('jenkinsWorkspace.availableEntries') }}</span>
          <strong>{{ entries.length }}</strong>
          <small>{{ t('jenkinsWorkspace.availableEntriesHint') }}</small>
        </div>
        <div class="workspace-inline-stat">
          <span>{{ t('jenkinsWorkspace.searchStatus') }}</span>
          <strong>{{ searchQuery ? t('jenkinsWorkspace.searching') : t('common.all') }}</strong>
          <small>{{ searchQuery || t('jenkinsWorkspace.searchHint') }}</small>
        </div>
        <div class="workspace-inline-stat">
          <span>{{ t('jenkinsWorkspace.interactionMode') }}</span>
          <strong>Manual</strong>
          <small>{{ t('jenkinsWorkspace.interactionModeHint') }}</small>
        </div>
      </section>

      <section class="workspace-panel workspace-panel--padded">
        <div class="section-heading">
          <div>
            <h2 class="section-title">{{ t('jenkinsWorkspace.catalogTitle') }}</h2>
            <p class="section-copy">{{ t('jenkinsWorkspace.catalogSubtitle') }}</p>
          </div>
        </div>
        <div class="relative">
          <svg class="pointer-events-none absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          <input
            v-model="searchQuery"
            type="text"
            :placeholder="t('jenkinsWorkspace.searchPlaceholder')"
            class="input pl-12"
          />
        </div>
      </section>

      <section v-if="filteredEntries.length > 0" class="space-y-3">
        <article
          v-for="entry in filteredEntries"
          :key="entry.id"
          class="workspace-entry-row workspace-entry-row--card"
        >
          <div class="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
            <div class="min-w-0 flex-1">
              <div class="flex flex-wrap items-center gap-3">
                <span class="workspace-chip workspace-chip--sky">
                  {{ entry.instance_name }}
                </span>
                <span class="workspace-chip">
                  {{ t('jenkinsWorkspace.jobName') }}
                </span>
                <span class="font-mono text-sm text-slate-500">
                  {{ entry.job_name }}
                </span>
              </div>

              <div class="mt-4 flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between lg:gap-6">
                <div class="min-w-0 flex-1">
                  <h3 class="text-xl font-semibold text-slate-900">
                    {{ entry.name }}
                  </h3>
                  <p class="mt-2 max-w-3xl text-sm leading-6 text-slate-500">
                    {{ entry.description || t('jenkinsWorkspace.emptyDescription') }}
                  </p>
                </div>

                <div class="workspace-meta-box lg:min-w-[18rem]">
                  <div class="flex items-center justify-between gap-3">
                    <p class="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">
                      {{ t('jenkinsWorkspace.notificationSectionTag') }}
                    </p>
                    <span
                      :class="entryNotificationEnabled(entry.id) ? 'status-pill-success' : 'status-pill-neutral'"
                    >
                      {{
                        entryNotificationEnabled(entry.id)
                          ? t('jenkinsWorkspace.notificationEnabled')
                          : t('jenkinsWorkspace.notificationDisabled')
                      }}
                    </span>
                  </div>
                  <p class="mt-2 text-sm leading-6 text-slate-500">
                    {{ notificationSummaryForEntry(entry.id) }}
                  </p>
                </div>
              </div>
            </div>

            <div class="flex shrink-0 flex-col gap-2 sm:flex-row xl:self-end">
              <BaseButton
                variant="outline"
                size="sm"
                @click="openNotificationModal(entry)"
              >
                {{ t('jenkinsWorkspace.notificationConfigure') }}
              </BaseButton>
              <BaseButton size="sm" @click="openTriggerModal(entry)">
                {{ t('jenkinsWorkspace.buildSettingsAction') }}
              </BaseButton>
            </div>
          </div>
        </article>
      </section>

      <EmptyState
        v-else
        :title="t('jenkinsWorkspace.emptyTitle')"
        :description="t('jenkinsWorkspace.emptySubtitle')"
      >
        <template #icon>
          <svg class="h-8 w-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z" />
          </svg>
        </template>
      </EmptyState>

      <BaseModal :show="showTriggerModal" :title="selectedEntry ? t('jenkinsWorkspace.triggerTitle', { name: selectedEntry.name }) : t('jenkinsWorkspace.triggerBuild')" @close="closeTriggerModal">
        <div v-if="loadingParams" class="py-10">
          <BaseLoading full-page size="lg" variant="primary" :text="t('jenkinsWorkspace.loadingParams')" />
        </div>

        <form v-else class="space-y-5" @submit.prevent="triggerBuild">
          <div
            v-for="param in params"
            :key="param.name"
            class="rounded-lg border border-slate-200/80 bg-slate-50/80 p-4"
          >
            <label class="block text-sm font-semibold text-slate-800">
              {{ param.name }}
            </label>
            <p v-if="param.description" class="mt-1 text-xs leading-5 text-slate-500">
              {{ param.description }}
            </p>

            <input
              v-if="param.type === 'StringParameterDefinition' || param.type === 'TextParameterDefinition'"
              v-model="formParams[param.name]"
              :type="param.name.toLowerCase().includes('password') ? 'password' : 'text'"
              :placeholder="param.default_value || ''"
              :readonly="param.mode === 'readonly'"
              :class="['input mt-3', param.mode === 'readonly' ? 'bg-slate-100/90' : '']"
            />

            <div v-else-if="param.type === 'BooleanParameterDefinition'" class="mt-3 flex items-center">
              <input
                :id="'param-' + param.name"
                v-model="formParams[param.name]"
                type="checkbox"
                class="mr-3"
              />
              <label :for="'param-' + param.name" class="text-sm text-slate-600">
                {{ param.default_value ? t('jenkinsWorkspace.defaultOn') : t('jenkinsWorkspace.defaultOff') }}
              </label>
            </div>

            <select
              v-else-if="param.type === 'ChoiceParameterDefinition'"
              v-model="formParams[param.name]"
              class="input mt-3"
            >
              <option v-for="choice in param.choices" :key="choice" :value="choice">
                {{ choice }}
              </option>
            </select>

            <input
              v-else-if="param.name.toLowerCase().includes('password') || param.type === 'PasswordParameterDefinition'"
              v-model="formParams[param.name]"
              type="password"
              :placeholder="param.default_value || ''"
              :readonly="param.mode === 'readonly'"
              :class="['input mt-3', param.mode === 'readonly' ? 'bg-slate-100/90' : '']"
            />

            <input
              v-else
              v-model="formParams[param.name]"
              type="text"
              :placeholder="param.default_value || ''"
              :readonly="param.mode === 'readonly'"
              :class="['input mt-3', param.mode === 'readonly' ? 'bg-slate-100/90' : '']"
            />

            <p v-if="param.mode === 'readonly'" class="mt-2 text-xs font-medium text-sky-700">
              {{ t('jenkinsWorkspace.presetField') }}
            </p>
          </div>
        </form>

        <template #footer>
          <div class="flex w-full flex-col gap-3 sm:flex-row sm:justify-end">
            <BaseButton variant="secondary" @click="closeTriggerModal">{{ t('common.cancel') }}</BaseButton>
            <BaseButton :loading="triggering" @click="triggerBuild">
              {{ triggering ? t('jenkinsWorkspace.triggering') : t('jenkinsWorkspace.triggerBuild') }}
            </BaseButton>
          </div>
        </template>
      </BaseModal>

      <BaseModal
        :show="showNotificationModal"
        :title="
          selectedNotificationEntry
            ? t('jenkinsWorkspace.notificationSettingsTitle', {
                name: selectedNotificationEntry.name
              })
            : t('jenkinsWorkspace.notificationSettingsFallbackTitle')
        "
        @close="closeNotificationModal"
      >
        <div v-if="selectedNotificationEntry" class="space-y-5">
          <section class="rounded-lg border border-slate-200/80 bg-white/95 px-4 py-4 sm:px-5">
            <div class="flex flex-wrap items-start justify-between gap-3">
              <div class="min-w-0">
                <div class="flex flex-wrap items-center gap-2">
                  <span class="inline-flex rounded-full bg-slate-100 px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">
                    {{ t('jenkinsWorkspace.notificationSectionTag') }}
                  </span>
                  <span :class="notificationEnabled ? 'status-pill-success' : 'status-pill-neutral'">
                    {{
                      notificationEnabled
                        ? t('jenkinsWorkspace.notificationEnabled')
                        : t('jenkinsWorkspace.notificationDisabled')
                    }}
                  </span>
                </div>
                <h3 class="mt-3 text-base font-semibold text-slate-900">
                  {{ t('jenkinsWorkspace.notificationPanelTitle') }}
                </h3>
                <p class="mt-1 text-sm leading-6 text-slate-500">
                  {{ notificationSummary }}
                </p>
              </div>
              <button
                type="button"
                class="text-sm font-semibold text-slate-500 transition hover:text-slate-700"
                @click="resetNotificationChannels"
              >
                {{ t('jenkinsWorkspace.notificationReset') }}
              </button>
            </div>

            <div class="mt-4 grid gap-3 md:grid-cols-2">
              <label
                v-for="targetGroup in notificationTargetGroups"
                :key="targetGroup.key"
                :class="[
                  'flex cursor-pointer items-start gap-3 rounded-lg border px-4 py-3 transition-all duration-150',
                  !hasNotificationTargets(targetGroup.key)
                    ? 'cursor-not-allowed opacity-70'
                    : '',
                  notificationChannels[targetGroup.key]
                    ? 'border-sky-200 bg-white shadow-sm'
                    : 'border-slate-200/80 bg-white/70 hover:border-slate-300 hover:bg-white'
                ]"
              >
                <input
                  v-model="notificationChannels[targetGroup.key]"
                  type="checkbox"
                  class="mt-1"
                  :disabled="!hasNotificationTargets(targetGroup.key)"
                />
                <div class="min-w-0 flex-1">
                  <div class="flex flex-wrap items-center gap-2">
                    <p class="text-sm font-semibold text-slate-800">
                      {{ targetGroup.label }}
                    </p>
                    <span class="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-semibold text-slate-500">
                      {{ notificationTargets[targetGroup.key].length }}
                    </span>
                  </div>

                  <div
                    v-if="notificationTargets[targetGroup.key].length"
                    class="mt-3 flex flex-wrap gap-2"
                  >
                    <span
                      v-for="target in notificationTargets[targetGroup.key]"
                      :key="`${targetGroup.key}-${target}`"
                      class="inline-flex max-w-full items-center rounded-full bg-slate-100 px-2.5 py-1 text-xs text-slate-600"
                    >
                      <span class="truncate">
                        {{ formatNotificationTarget(targetGroup.key, target) }}
                      </span>
                    </span>
                  </div>

                  <p v-else class="mt-3 text-xs text-slate-400">
                    {{ t('jenkinsWorkspace.notificationNoTargets') }}
                  </p>
                </div>
              </label>
            </div>

            <p class="mt-4 text-xs leading-5 text-slate-400">
              {{ t('jenkinsWorkspace.notificationTargetsHint') }}
            </p>
          </section>
        </div>

        <template #footer>
          <div class="flex w-full flex-col gap-3 sm:flex-row sm:justify-end">
            <BaseButton variant="secondary" @click="closeNotificationModal">
              {{ t('common.cancel') }}
            </BaseButton>
            <BaseButton :loading="notificationSaving" @click="saveNotificationPreferencesForSelectedEntry">
              {{ t('common.save') }}
            </BaseButton>
          </div>
        </template>
      </BaseModal>

      <BaseModal :show="showResultModal" :title="t('jenkinsWorkspace.buildTriggered')" @close="closeResultModal">
        <div class="space-y-4">
	          <div class="rounded-lg border border-slate-200/80 bg-slate-50/80 p-4">
	            <p class="metric-label">{{ t('jenkinsWorkspace.buildNumber') }}</p>
	            <p class="mt-2 text-2xl font-semibold text-slate-900">
	              {{ triggerResult.build_number ? `#${triggerResult.build_number}` : t('jenkinsWorkspace.queuedBuild') }}
	            </p>
	          </div>
          <div class="rounded-lg border border-slate-200/80 bg-slate-50/80 p-4">
            <p class="metric-label">{{ t('jenkinsWorkspace.resultStatus') }}</p>
            <span :class="resultStatusClass(triggerResult.status)" class="mt-3 inline-flex">
              {{ statusLabel(triggerResult.status || 'pending') }}
            </span>
          </div>
          <div v-if="hasBuildProgress(triggerResult)" class="rounded-lg border border-slate-200/80 bg-slate-50/80 p-4">
            <div class="flex items-center justify-between gap-3">
              <p class="metric-label">{{ t('jenkinsWorkspace.progress') }}</p>
              <span class="text-sm font-semibold text-slate-800">
                {{ progressLabel(triggerResult) }}
              </span>
            </div>
            <div class="mt-3 h-2 overflow-hidden rounded-full bg-slate-100">
              <div
                class="h-full rounded-full bg-sky-500 transition-all"
                :style="{ width: `${progressPercent(triggerResult)}%` }"
              />
            </div>
            <div class="mt-3 flex flex-wrap items-center justify-between gap-2 text-sm">
              <span class="font-medium text-slate-700">{{ progressStage(triggerResult) }}</span>
              <span v-if="progressSummary(triggerResult)" class="text-xs text-slate-400">
                {{ progressSummary(triggerResult) }}
              </span>
            </div>
          </div>
          <div class="rounded-lg border border-slate-200/80 bg-slate-50/80 p-4">
            <p class="metric-label">{{ t('jenkinsWorkspace.notificationSectionTitle') }}</p>
            <p class="mt-2 text-lg font-semibold text-slate-900">
              {{ resultNotificationSummary }}
            </p>
            <p class="mt-2 text-sm leading-6 text-slate-500">
              {{ t('jenkinsWorkspace.notificationResultHint') }}
            </p>
          </div>
        </div>
        <template #footer>
          <div class="flex w-full flex-col gap-3 sm:flex-row sm:justify-end">
            <BaseButton variant="secondary" :loading="manualRefreshing" @click="refreshStatus({ source: 'manual' })">
              {{ manualRefreshing ? t('jenkinsWorkspace.refreshing') : t('jenkinsWorkspace.refreshStatus') }}
            </BaseButton>
            <BaseButton @click="closeResultModal">{{ t('common.close') }}</BaseButton>
          </div>
        </template>
      </BaseModal>

      <div
        v-if="toast.show"
        :class="[
          'fixed bottom-5 right-5 z-[60] rounded-lg px-4 py-3 text-sm font-medium text-white shadow-[0_14px_34px_rgba(15,23,42,0.18)]',
          toast.type === 'success' ? 'bg-emerald-600' : 'bg-rose-600'
        ]"
      >
        {{ toast.message }}
      </div>
    </PageFrame>
  </AppLayout>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import AppLayout from '@/components/layout/AppLayout.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseLoading from '@/components/ui/BaseLoading.vue'
import BaseModal from '@/components/ui/BaseModal.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import PageFrame from '@/components/ui/PageFrame.vue'
import jenkinsApi from '@/api/jenkins'
import { useUserStore } from '@/store/user'

const { t } = useI18n()
const userStore = useUserStore()

const entries = ref([])
const searchQuery = ref('')
const showTriggerModal = ref(false)
const showResultModal = ref(false)
const showNotificationModal = ref(false)
const selectedEntry = ref(null)
const selectedNotificationEntry = ref(null)
const params = ref([])
const formParams = ref({})
const notificationPreferences = ref([])
const notificationChannels = ref(createEmptyNotificationChannels())
const loadingParams = ref(false)
const triggering = ref(false)
const notificationSaving = ref(false)
const manualRefreshing = ref(false)
const triggerResult = ref({})
const statusRefreshInFlight = ref(false)

const AUTO_REFRESH_INTERVAL_MS = 10000
const AUTO_REFRESH_MAX_ERRORS = 3
let autoRefreshTimer = null
let autoRefreshFailureCount = 0

const toast = ref({ show: false, message: '', type: 'success' })

const filteredEntries = computed(() => {
  if (!searchQuery.value) return entries.value
  const query = searchQuery.value.toLowerCase()
  return entries.value.filter((e) =>
    e.name.toLowerCase().includes(query) ||
    e.description?.toLowerCase().includes(query) ||
    e.job_name.toLowerCase().includes(query)
  )
})

const notificationTargetGroups = computed(() => [
  {
    key: 'email',
    label: t('jenkinsWorkspace.notificationEmailLabel')
  },
  {
    key: 'webhook',
    label: t('jenkinsWorkspace.notificationWebhookLabel')
  }
])

const notificationSourceTargets = computed(() => {
  const profileSettings =
    userStore.userInfo?.profile?.jenkins_notification_settings || {}
  const groups = userStore.userInfo?.groups || []

  return {
    personalEmails: dedupeTargets([
      userStore.userInfo?.email || '',
      ...(profileSettings.notification_emails || [])
    ]),
    personalWebhooks: dedupeTargets(
      profileSettings.notification_webhooks || []
    ),
    groupEmails: dedupeTargets(
      groups.flatMap(
        (group) =>
          group?.jenkins_notification_settings?.notification_emails || []
      )
    ),
    groupWebhooks: dedupeTargets(
      groups.flatMap(
        (group) =>
          group?.jenkins_notification_settings?.notification_webhooks || []
      )
    )
  }
})

const notificationTargets = computed(() => ({
  email: dedupeTargets([
    ...notificationSourceTargets.value.personalEmails,
    ...notificationSourceTargets.value.groupEmails
  ]),
  webhook: dedupeTargets([
    ...notificationSourceTargets.value.personalWebhooks,
    ...notificationSourceTargets.value.groupWebhooks
  ])
}))

const selectedNotificationCount = computed(
  () => Object.values(notificationChannels.value).filter(Boolean).length
)

const notificationEnabled = computed(() => selectedNotificationCount.value > 0)

const notificationSummary = computed(() =>
  formatNotificationSummary(notificationChannels.value)
)

const resultNotificationSummary = computed(() =>
  formatNotificationSummary(
    triggerResult.value.notification_channels || notificationChannels.value
  )
)

function createEmptyNotificationChannels() {
  return {
    email: false,
    webhook: false
  }
}

function hasNotificationTargets(channelKey) {
  return (notificationTargets.value[channelKey] || []).length > 0
}

function normalizeNotificationChannels(channels = {}) {
  if ('email' in channels || 'webhook' in channels) {
    return {
      email: Boolean(channels.email),
      webhook: Boolean(channels.webhook)
    }
  }

  return {
    email: Boolean(channels.personal_email || channels.group_email),
    webhook: Boolean(channels.personal_webhook || channels.group_webhook)
  }
}

function sanitizeNotificationChannels(channels = {}) {
  const normalized = normalizeNotificationChannels(channels)

  return {
    email: normalized.email && hasNotificationTargets('email'),
    webhook: normalized.webhook && hasNotificationTargets('webhook')
  }
}

function dedupeTargets(values = []) {
  return [
    ...new Set(
      values.map((value) => String(value || '').trim()).filter(Boolean)
    )
  ]
}

function getEntryNotificationPreference(entryId) {
  return notificationPreferences.value.find((item) => item.entry_id === entryId)
}

function getNotificationChannelsForEntry(entryId) {
  return sanitizeNotificationChannels(
    getEntryNotificationPreference(entryId)?.notification_channels
  )
}

function formatNotificationTarget(channelKey, target) {
  if (!target) return ''
  if (channelKey !== 'webhook') {
    return target
  }

  try {
    const url = new URL(target)
    const path = url.pathname === '/' ? '' : url.pathname
    return `${url.host}${path}`
  } catch {
    return target
  }
}

function formatNotificationSummary(channels) {
  const activeLabels = notificationTargetGroups.value
    .filter((channel) => channels?.[channel.key])
    .map((channel) => channel.label)

  if (activeLabels.length === 0) {
    return t('jenkinsWorkspace.notificationSummaryDisabled')
  }

  return t('jenkinsWorkspace.notificationSummaryEnabled', {
    channels: activeLabels.join(' / ')
  })
}

function resetNotificationChannels() {
  notificationChannels.value = createEmptyNotificationChannels()
}

function notificationSummaryForEntry(entryId) {
  return formatNotificationSummary(getNotificationChannelsForEntry(entryId))
}

function entryNotificationEnabled(entryId) {
  return Object.values(getNotificationChannelsForEntry(entryId)).some(Boolean)
}

function showToast(message, type = 'success') {
  toast.value = { show: true, message, type }
  setTimeout(() => {
    toast.value.show = false
  }, 3000)
}

function resultStatusClass(status) {
  if (status === 'success') return 'status-pill-success'
  if (status === 'failure') return 'status-pill-danger'
  if (status === 'running' || status === 'pending') return 'status-pill-warning'
  return 'status-pill-neutral'
}

function statusLabel(status) {
  return t(`jenkinsWorkspace.status.${status}`, status)
}

function progressPercent(record) {
  const value = Number(record?.progress_percent ?? 0)
  if (Number.isNaN(value)) return 0
  return Math.max(0, Math.min(value, 100))
}

function hasBuildProgress(record) {
  if (!record) return false
  if (record.pipeline_supported) return true
  return record.progress_percent != null && isActiveBuildStatus(record.status)
}

function progressLabel(record) {
  if (record?.status === 'running' && record?.pipeline_supported) {
    return t('jenkinsWorkspace.estimatedProgress', {
      percent: progressPercent(record)
    })
  }
  return `${progressPercent(record)}%`
}

function progressStage(record) {
  if (record?.current_stage) return record.current_stage
  if (record?.status === 'pending') return t('jenkinsWorkspace.queuedBuild')
  return statusLabel(record?.status)
}

function progressSummary(record) {
  if (['success', 'failure', 'aborted'].includes(record?.status)) {
    return record.status === 'success'
      ? t('jenkinsWorkspace.pipelineCompleted')
      : t('jenkinsWorkspace.pipelineFinished')
  }
  const summary = record?.stage_summary
  if (!summary || !summary.total) return ''
  return t('jenkinsWorkspace.stageSummary', {
    completed: summary.completed || 0,
    total: summary.total
  })
}

function isActiveBuildStatus(status) {
  return status === 'pending' || status === 'running'
}

function hasRefreshTarget(record) {
  return Boolean(record?.build_number || record?.queue_url)
}

function stopAutoRefresh() {
  if (autoRefreshTimer) {
    window.clearInterval(autoRefreshTimer)
    autoRefreshTimer = null
  }
}

function syncAutoRefresh() {
  if (
    !showResultModal.value ||
    document.visibilityState === 'hidden' ||
    !triggerResult.value.record_id ||
    !hasRefreshTarget(triggerResult.value) ||
    !isActiveBuildStatus(triggerResult.value.status || 'pending')
  ) {
    stopAutoRefresh()
    return
  }

  if (autoRefreshTimer) return
  autoRefreshTimer = window.setInterval(() => {
    void refreshStatus({ source: 'auto', silent: true })
  }, AUTO_REFRESH_INTERVAL_MS)
}

function closeResultModal() {
  showResultModal.value = false
  stopAutoRefresh()
}

function applyRecordStatus(record, { notifyTerminal = true } = {}) {
  triggerResult.value.status = record.status
  triggerResult.value.build_number = record.build_number
  triggerResult.value.queue_url = record.queue_url
  triggerResult.value.progress_percent = record.progress_percent
  triggerResult.value.current_stage = record.current_stage
  triggerResult.value.stage_summary = record.stage_summary
  triggerResult.value.pipeline_supported = record.pipeline_supported

  if (record.status === 'success') {
    if (notifyTerminal) {
      showToast(t('jenkinsWorkspace.toast.buildSuccess'))
    }
    stopAutoRefresh()
  } else if (record.status === 'failure') {
    if (notifyTerminal) {
      showToast(t('jenkinsWorkspace.toast.buildFailure'), 'error')
    }
    stopAutoRefresh()
  } else if (record.status === 'aborted') {
    if (notifyTerminal) {
      showToast(t('jenkinsWorkspace.toast.buildAborted'), 'error')
    }
    stopAutoRefresh()
  } else {
    syncAutoRefresh()
  }
}

async function loadEntries() {
  try {
    entries.value = await jenkinsApi.getUserEntries()
  } catch (e) {
    showToast(t('jenkinsWorkspace.toast.loadEntriesFailed', { message: e.message }), 'error')
  }
}

async function loadNotificationPreferences() {
  try {
    notificationPreferences.value =
      await jenkinsApi.getUserNotificationPreferences()
  } catch (e) {
    showToast(
      t('jenkinsWorkspace.toast.loadNotificationPreferencesFailed', {
        message: e.message
      }),
      'error'
    )
  }
}

async function openTriggerModal(entry) {
  selectedEntry.value = entry
  showTriggerModal.value = true
  loadingParams.value = true

  try {
    const data = await jenkinsApi.getEntryParams(entry.id)
    params.value = data.params || []

    formParams.value = {}
    for (const p of params.value) {
      formParams.value[p.name] = p.default_value || ''
    }
  } catch (e) {
    showToast(t('jenkinsWorkspace.toast.loadParamsFailed', { message: e.message }), 'error')
  } finally {
    loadingParams.value = false
  }
}

function closeTriggerModal() {
  showTriggerModal.value = false
  selectedEntry.value = null
  params.value = []
  formParams.value = {}
}

function openNotificationModal(entry) {
  if (!entry) return
  selectedNotificationEntry.value = entry
  notificationChannels.value = createEmptyNotificationChannels()
  notificationChannels.value = getNotificationChannelsForEntry(entry.id)
  showNotificationModal.value = true
}

function closeNotificationModal() {
  showNotificationModal.value = false
  selectedNotificationEntry.value = null
  notificationChannels.value = createEmptyNotificationChannels()
}

async function persistNotificationPreferences(entry, channels) {
  if (!entry) return

  const currentPreferences = notificationPreferences.value.length
    ? notificationPreferences.value.map((item) => ({
        ...item,
        notification_channels: normalizeNotificationChannels(
          item.notification_channels
        )
      }))
    : await jenkinsApi.getUserNotificationPreferences()

  const nextChannels = normalizeNotificationChannels(channels)
  const mappedChannels = {
    personal_email:
      nextChannels.email &&
      notificationSourceTargets.value.personalEmails.length > 0,
    group_email:
      nextChannels.email &&
      notificationSourceTargets.value.groupEmails.length > 0,
    personal_webhook:
      nextChannels.webhook &&
      notificationSourceTargets.value.personalWebhooks.length > 0,
    group_webhook:
      nextChannels.webhook &&
      notificationSourceTargets.value.groupWebhooks.length > 0
  }
  const existingIndex = currentPreferences.findIndex(
    (item) => item.entry_id === entry.id
  )

  if (existingIndex >= 0) {
    currentPreferences[existingIndex] = {
      ...currentPreferences[existingIndex],
      notification_channels: mappedChannels
    }
  } else {
    currentPreferences.push({
      entry_id: entry.id,
      entry_name: entry.name,
      instance_name: entry.instance_name,
      job_name: entry.job_name,
      description: entry.description,
      notification_channels: mappedChannels
    })
  }

  notificationPreferences.value =
    await jenkinsApi.saveUserNotificationPreferences(currentPreferences)
}

async function saveNotificationPreferencesForSelectedEntry() {
  if (!selectedNotificationEntry.value) return

  notificationSaving.value = true
  try {
    await persistNotificationPreferences(
      selectedNotificationEntry.value,
      notificationChannels.value
    )
    showToast(t('jenkinsWorkspace.toast.notificationSaved'))
    closeNotificationModal()
  } catch (e) {
    showToast(
      t('jenkinsWorkspace.toast.notificationSaveFailed', {
        message: e.message
      }),
      'error'
    )
  } finally {
    notificationSaving.value = false
  }
}

async function triggerBuild() {
  triggering.value = true
  try {
    const result = await jenkinsApi.triggerBuild(
      selectedEntry.value.id,
      formParams.value
    )
    triggerResult.value = {
      ...result,
      notification_channels: normalizeNotificationChannels(
        selectedEntry.value
          ? getNotificationChannelsForEntry(selectedEntry.value.id)
          : createEmptyNotificationChannels()
      )
    }
    showTriggerModal.value = false
    showResultModal.value = true
    autoRefreshFailureCount = 0
    showToast(t('jenkinsWorkspace.toast.triggerQueued'))
    syncAutoRefresh()
  } catch (e) {
    showToast(t('jenkinsWorkspace.toast.triggerFailed', { message: e.message }), 'error')
  } finally {
    triggering.value = false
  }
}

async function refreshStatus({ source = 'manual', silent = false } = {}) {
  if (!triggerResult.value.record_id) return
  if (!hasRefreshTarget(triggerResult.value)) {
    if (source === 'manual' && !silent) {
      showToast(t('jenkinsWorkspace.toast.refreshUnavailable'), 'error')
    }
    stopAutoRefresh()
    return
  }
  if (statusRefreshInFlight.value) return

  statusRefreshInFlight.value = true
  if (source === 'manual') {
    manualRefreshing.value = true
  }

  try {
    const record = await jenkinsApi.refreshStatus(triggerResult.value.record_id)
    autoRefreshFailureCount = 0
    applyRecordStatus(record, { notifyTerminal: true })
  } catch (e) {
    if (source === 'manual' && !silent) {
      showToast(t('jenkinsWorkspace.toast.refreshFailed', { message: e.message }), 'error')
    } else {
      autoRefreshFailureCount += 1
      if (autoRefreshFailureCount >= AUTO_REFRESH_MAX_ERRORS) {
        stopAutoRefresh()
        showToast(t('jenkinsWorkspace.toast.autoRefreshStopped', { message: e.message }), 'error')
      }
    }
  } finally {
    statusRefreshInFlight.value = false
    if (source === 'manual') {
      manualRefreshing.value = false
    }
  }
}

function handleVisibilityChange() {
  if (document.visibilityState === 'hidden') {
    stopAutoRefresh()
    return
  }
  syncAutoRefresh()
}

onMounted(() => {
  loadEntries()
  loadNotificationPreferences()
  document.addEventListener('visibilitychange', handleVisibilityChange)
})

onBeforeUnmount(() => {
  stopAutoRefresh()
  document.removeEventListener('visibilitychange', handleVisibilityChange)
})

watch(
  () => showResultModal.value,
  () => {
    if (!showResultModal.value) {
      stopAutoRefresh()
      return
    }
    syncAutoRefresh()
  }
)

watch(
  () => triggerResult.value.status,
  () => {
    syncAutoRefresh()
  }
)
</script>
