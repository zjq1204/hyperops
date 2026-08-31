<template>
  <AppLayout>
    <PageFrame
      class="object-storage-page"
      :eyebrow="t('objectStorage.applications.eyebrow')"
      :title="t('objectStorage.applications.title')"
      :subtitle="t('objectStorage.applications.subtitle')"
    >
      <template #actions>
        <BaseButton
          variant="secondary"
          :loading="loading"
          @click="loadApplications"
        >
          {{ t('common.refresh') }}
        </BaseButton>
      </template>

      <ObjectStorageNav />

      <InlineAlert
        v-if="loadError"
        variant="error"
        :title="t('objectStorage.applications.loadErrorTitle')"
        :message="t('objectStorage.applications.loadErrorMessage')"
      />

      <section
        class="grid gap-5 xl:grid-cols-[minmax(0,1.4fr)_minmax(18rem,0.6fr)]"
      >
        <section class="workspace-panel workspace-panel--padded">
          <div class="section-heading">
            <div>
              <h2 class="section-title">
                {{ t('objectStorage.applications.historyTitle') }}
              </h2>
              <p class="section-copy">
                {{ t('objectStorage.applications.historyHint') }}
              </p>
            </div>
            <span class="text-sm font-medium text-slate-500">
              {{
                t('objectStorage.applications.count', {
                  count: applications.length
                })
              }}
            </span>
          </div>

          <div v-if="loading" class="py-12 text-center text-sm text-slate-500">
            {{ t('common.loading') }}
          </div>

          <div
            v-else-if="applications.length"
            class="divide-y divide-slate-100 border-y border-slate-200"
          >
            <article
              v-for="application in applications"
              :key="application.id"
              class="py-4"
            >
              <div
                class="grid gap-3 sm:grid-cols-[minmax(0,1fr)_auto_auto] sm:items-center"
              >
                <button
                  type="button"
                  class="min-w-0 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500"
                  :aria-expanded="expandedId === application.id"
                  @click="toggleDetail(application)"
                >
                  <span class="block text-sm font-semibold text-slate-950">
                    {{ actionTypeText(application.action_type) }}
                  </span>
                  <span class="mt-1 block text-xs text-slate-500">
                    {{ formatDate(application.created_at) }}
                  </span>
                </button>
                <StatusBadge :status="applicationStatus(application.status)" />
                <div class="flex items-center justify-end gap-2">
                  <BaseButton
                    v-if="isRetryable(application)"
                    size="sm"
                    variant="secondary"
                    :loading="retryingId === application.id"
                    @click="retryApplication(application)"
                  >
                    {{ t('objectStorage.applications.retryAction') }}
                  </BaseButton>
                  <BaseButton
                    size="sm"
                    variant="ghost"
                    @click="toggleDetail(application)"
                  >
                    {{
                      expandedId === application.id
                        ? t('common.close')
                        : t('common.viewDetails')
                    }}
                  </BaseButton>
                </div>
              </div>

              <p
                v-if="application.error_code"
                class="mt-3 text-sm text-rose-700"
              >
                {{
                  errorText(application.error_code, application.error_summary)
                }}
              </p>

              <section
                v-if="expandedId === application.id"
                class="mt-4 border-t border-slate-100 pt-4"
              >
                <div v-if="detailLoading" class="py-5 text-sm text-slate-500">
                  {{ t('common.loading') }}
                </div>
                <InlineAlert
                  v-else-if="detailError"
                  variant="error"
                  :title="t('objectStorage.applications.detailErrorTitle')"
                  :message="t('objectStorage.applications.detailErrorMessage')"
                />
                <template v-else-if="selectedDetail">
                  <dl class="grid gap-4 sm:grid-cols-3">
                    <div>
                      <dt class="text-xs font-medium text-slate-400">
                        {{ t('objectStorage.applications.currentStage') }}
                      </dt>
                      <dd class="mt-1 text-sm font-semibold text-slate-900">
                        {{ stageText(selectedDetail.current_stage) }}
                      </dd>
                    </div>
                    <div>
                      <dt class="text-xs font-medium text-slate-400">
                        {{ t('objectStorage.applications.attemptCount') }}
                      </dt>
                      <dd class="mt-1 text-sm font-semibold text-slate-900">
                        {{ selectedDetail.attempts?.length || 0 }}
                      </dd>
                    </div>
                    <div>
                      <dt class="text-xs font-medium text-slate-400">
                        {{ t('objectStorage.applications.updatedAt') }}
                      </dt>
                      <dd class="mt-1 text-sm font-semibold text-slate-900">
                        {{ formatDate(selectedDetail.updated_at) }}
                      </dd>
                    </div>
                  </dl>

                  <ol
                    v-if="selectedDetail.events?.length"
                    class="mt-4 divide-y divide-slate-100 border-y border-slate-200"
                  >
                    <li
                      v-for="event in selectedDetail.events"
                      :key="event.id"
                      class="grid gap-2 py-3 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center"
                    >
                      <div>
                        <p class="text-sm font-medium text-slate-900">
                          {{ stageText(event.stage) }}
                        </p>
                        <p
                          v-if="event.error_code"
                          class="mt-1 text-xs text-rose-700"
                        >
                          {{ errorText(event.error_code) }}
                        </p>
                      </div>
                      <span class="text-xs text-slate-500">{{
                        formatDate(event.created_at)
                      }}</span>
                    </li>
                  </ol>
                </template>
              </section>
            </article>
          </div>

          <EmptyState
            v-else
            :title="t('objectStorage.applications.emptyTitle')"
          />
        </section>

        <section class="workspace-panel workspace-panel--padded self-start">
          <div class="section-heading">
            <div>
              <h2 class="section-title">
                {{ t('objectStorage.applications.createTitle') }}
              </h2>
            </div>
          </div>
          <div class="divide-y divide-slate-200 border-y border-slate-200">
            <router-link
              :to="{ name: 'ObjectStorageBuckets' }"
              class="flex min-h-14 items-center justify-between gap-4 py-3 text-sm font-medium text-slate-700 hover:text-sky-700"
            >
              <span>{{ t('objectStorage.actions.addBucket') }}</span>
              <span aria-hidden="true">→</span>
            </router-link>
            <router-link
              :to="{ name: 'ObjectStorageCredentials' }"
              class="flex min-h-14 items-center justify-between gap-4 py-3 text-sm font-medium text-slate-700 hover:text-sky-700"
            >
              <span>{{ t('objectStorage.credentials.rotateAction') }}</span>
              <span aria-hidden="true">→</span>
            </router-link>
          </div>
        </section>
      </section>
    </PageFrame>
  </AppLayout>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import objectStorageApi from '@/api/objectStorage'
import AppLayout from '@/components/layout/AppLayout.vue'
import ObjectStorageNav from '@/components/layout/ObjectStorageNav.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import InlineAlert from '@/components/ui/InlineAlert.vue'
import PageFrame from '@/components/ui/PageFrame.vue'
import StatusBadge from '@/components/ui/StatusBadge.vue'
import { useToast } from '@/composables/useToast'
import { formatDateIsoLocale } from '@/utils/formatting'

const { t, locale } = useI18n()
const { showSuccess, showError } = useToast()
const applications = ref([])
const loading = ref(false)
const loadError = ref(false)
const expandedId = ref(null)
const selectedDetail = ref(null)
const detailLoading = ref(false)
const detailError = ref(false)
const retryingId = ref(null)

function formatDate(value) {
  return formatDateIsoLocale(value, locale.value)
}

function actionTypeText(actionType) {
  return t(`objectStorage.applicationTypes.${actionType}`, actionType)
}

function stageText(stage) {
  if (!stage) return t('objectStorage.applications.notStarted')
  return t(`objectStorage.applicationStages.${stage}`, stage)
}

function errorText(code, fallback = '') {
  return t(`objectStorage.errorCodes.${code}`, fallback || code)
}

function applicationStatus(status) {
  if (status === 'succeeded' || status === 'delivery_ready') return 'success'
  if (status === 'failed' || status === 'manual_required') return 'failed'
  if (status === 'cancelled') return 'disabled'
  if (status === 'pending') return 'pending'
  return 'processing'
}

function isRetryable(application) {
  return ['failed', 'manual_required'].includes(application.status)
}

async function loadApplications() {
  loading.value = true
  loadError.value = false
  try {
    applications.value = await objectStorageApi.listApplications()
  } catch {
    applications.value = []
    loadError.value = true
  } finally {
    loading.value = false
  }
}

async function toggleDetail(application) {
  if (expandedId.value === application.id) {
    expandedId.value = null
    selectedDetail.value = null
    return
  }
  expandedId.value = application.id
  selectedDetail.value = null
  detailError.value = false
  detailLoading.value = true
  try {
    selectedDetail.value = await objectStorageApi.getApplicationDetail(
      application.id
    )
  } catch {
    detailError.value = true
  } finally {
    detailLoading.value = false
  }
}

async function retryApplication(application) {
  retryingId.value = application.id
  try {
    await objectStorageApi.retryApplication(application.id)
    showSuccess(t('objectStorage.applications.retrySubmitted'))
    await loadApplications()
  } catch {
    showError(t('objectStorage.applications.retryError'))
  } finally {
    retryingId.value = null
  }
}

onMounted(loadApplications)
</script>
