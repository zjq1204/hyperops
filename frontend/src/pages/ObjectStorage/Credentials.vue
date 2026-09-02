<template>
  <AppLayout>
    <PageFrame
      class="object-storage-page"
      :eyebrow="t('objectStorage.credentials.eyebrow')"
      :title="t('objectStorage.credentials.title')"
      :subtitle="t('objectStorage.credentials.subtitle')"
    >
      <template #actions>
        <BaseButton
          variant="secondary"
          :loading="loading"
          @click="loadSafeData"
        >
          {{ t('common.refresh') }}
        </BaseButton>
      </template>

      <section
        class="grid gap-5 lg:grid-cols-[minmax(0,1.15fr)_minmax(20rem,0.85fr)]"
      >
        <div class="space-y-5">
          <section class="workspace-panel workspace-panel--padded">
            <div class="section-heading">
              <div>
                <h2 class="section-title">
                  {{ t('objectStorage.credentials.summaryTitle') }}
                </h2>
                <p class="section-copy">
                  {{ t('objectStorage.credentials.summaryHint') }}
                </p>
              </div>
            </div>

            <PageErrorState
              v-if="overviewLoadError && !overviewNotConfigured"
              :message="t('objectStorage.errors.loadCredentials')"
              @retry="loadOverviewData"
            />
            <EmptyState
              v-else-if="overviewNotConfigured"
              :title="t('objectStorage.notConfigured')"
              :description="t('objectStorage.notConfiguredHint')"
            />
            <div
              v-else-if="overviewLoading"
              class="py-10 text-center text-sm text-slate-500"
            >
              {{ t('common.loading') }}
            </div>
            <template v-else>
              <div
                v-if="credentials.length"
                class="divide-y divide-slate-100 border-y border-slate-200"
              >
                <article
                  v-for="credential in credentials"
                  :key="credential.id"
                  class="flex flex-col gap-3 py-4 sm:flex-row sm:items-center sm:justify-between"
                >
                  <div>
                    <p class="font-mono text-sm font-semibold text-slate-950">
                      {{
                        t('objectStorage.credentials.endingIn', {
                          lastFour: credential.last_four
                        })
                      }}
                    </p>
                    <p class="mt-1 text-xs text-slate-500">
                      {{
                        t('objectStorage.credentials.createdAt', {
                          date: formatDate(credential.created_at)
                        })
                      }}
                    </p>
                  </div>
                  <StatusBadge :status="credentialStatus(credential)" />
                </article>
              </div>
              <EmptyState
                v-else
                :title="t('objectStorage.credentials.emptyTitle')"
                :description="t('objectStorage.credentials.emptyHint')"
              />

              <dl
                class="mt-5 grid gap-4 border-y border-slate-200 py-4 sm:grid-cols-2"
              >
                <div>
                  <dt class="text-xs font-medium text-slate-400">
                    {{ t('objectStorage.credentials.scopeLabel') }}
                  </dt>
                  <dd class="mt-1 text-sm font-semibold text-slate-900">
                    {{
                      t('objectStorage.credentials.scopeValue', {
                        count: buckets.length
                      })
                    }}
                  </dd>
                </div>
                <div>
                  <dt class="text-xs font-medium text-slate-400">
                    {{ t('objectStorage.credentials.secretPolicyLabel') }}
                  </dt>
                  <dd class="mt-1 text-sm font-semibold text-slate-900">
                    {{ t('objectStorage.credentials.secretPolicyValue') }}
                  </dd>
                </div>
              </dl>
            </template>
          </section>

          <section class="workspace-panel workspace-panel--padded">
            <div class="section-heading">
              <div>
                <h2 class="section-title">
                  {{ t('objectStorage.credentials.deliveryTitle') }}
                </h2>
                <p class="section-copy">
                  {{ t('objectStorage.credentials.deliveryHint') }}
                </p>
              </div>
            </div>

            <template v-if="!secretMaterial">
              <PageErrorState
                v-if="applicationsLoadError && !applicationsNotConfigured"
                :message="t('objectStorage.errors.loadCredentials')"
                @retry="loadApplicationsData"
              />
              <EmptyState
                v-else-if="applicationsNotConfigured"
                :title="t('objectStorage.notConfigured')"
                :description="t('objectStorage.notConfiguredHint')"
              />
              <div
                v-else-if="applicationsLoading"
                class="mt-5 py-10 text-center text-sm text-slate-500"
              >
                {{ t('common.loading') }}
              </div>
              <form
                v-else
                class="mt-5 grid gap-4"
                @submit.prevent="retrieveCredentials"
              >
                <label class="max-w-md space-y-2">
                  <span class="admin-filter-label">{{
                    t('objectStorage.credentials.applicationIdLabel')
                  }}</span>
                  <select
                    v-model="deliveryApplicationId"
                    class="admin-filter-control"
                    required
                  >
                    <option value="" disabled>
                      {{
                        t('objectStorage.credentials.applicationIdPlaceholder')
                      }}
                    </option>
                    <option
                      v-for="application in deliveryApplications"
                      :key="application.id"
                      :value="String(application.id)"
                    >
                      {{
                        t('objectStorage.credentials.deliveryOption', {
                          id: application.id,
                          date: formatDate(application.created_at)
                        })
                      }}
                    </option>
                  </select>
                </label>
                <p class="text-xs leading-5 text-slate-500">
                  {{ t('objectStorage.credentials.applicationIdHelp') }}
                </p>
                <div>
                  <BaseButton
                    type="submit"
                    :loading="delivering"
                    :disabled="!deliveryApplicationId"
                  >
                    {{ t('objectStorage.credentials.retrieveAction') }}
                  </BaseButton>
                </div>
              </form>
            </template>

            <section
              v-else
              class="mt-5 border-l-2 border-amber-400 bg-amber-50/70 p-4"
              aria-live="polite"
            >
              <div
                class="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between"
              >
                <div>
                  <h3 class="text-sm font-semibold text-amber-950">
                    {{ t('objectStorage.credentials.oneTimeTitle') }}
                  </h3>
                  <p class="mt-1 text-sm leading-6 text-amber-900/80">
                    {{ t('objectStorage.credentials.oneTimeWarning') }}
                  </p>
                </div>
                <BaseButton
                  size="sm"
                  variant="ghost"
                  @click="clearSecretMaterial"
                >
                  {{ t('objectStorage.credentials.clearAction') }}
                </BaseButton>
              </div>

              <div class="mt-4 grid gap-4">
                <label class="space-y-2">
                  <span class="admin-filter-label">{{
                    t('objectStorage.credentials.accessKeyId')
                  }}</span>
                  <div class="flex flex-col gap-2 sm:flex-row">
                    <input
                      :value="secretMaterial.access_key_id"
                      class="admin-filter-control min-w-0 flex-1 font-mono"
                      readonly
                      autocomplete="off"
                    />
                    <BaseButton
                      size="sm"
                      variant="secondary"
                      @click="copySecret(secretMaterial.access_key_id)"
                    >
                      {{ t('common.copy') }}
                    </BaseButton>
                  </div>
                </label>
                <label class="space-y-2">
                  <span class="admin-filter-label">{{
                    t('objectStorage.credentials.secretAccessKey')
                  }}</span>
                  <div class="flex flex-col gap-2 sm:flex-row">
                    <input
                      :value="secretMaterial.secret_access_key"
                      class="admin-filter-control min-w-0 flex-1 font-mono"
                      :type="showSecretMaterial ? 'text' : 'password'"
                      readonly
                      autocomplete="off"
                    />
                    <BaseButton
                      size="sm"
                      variant="secondary"
                      :aria-pressed="showSecretMaterial"
                      @click="showSecretMaterial = !showSecretMaterial"
                    >
                      {{
                        showSecretMaterial
                          ? t('objectStorage.credentials.hideSecret')
                          : t('objectStorage.credentials.showSecret')
                      }}
                    </BaseButton>
                    <BaseButton
                      size="sm"
                      variant="secondary"
                      @click="copySecret(secretMaterial.secret_access_key)"
                    >
                      {{ t('common.copy') }}
                    </BaseButton>
                  </div>
                </label>
              </div>
            </section>
          </section>
        </div>

        <section class="workspace-panel workspace-panel--padded self-start">
          <div class="section-heading">
            <div>
              <h2 class="section-title">
                {{ t('objectStorage.credentials.rotationTitle') }}
              </h2>
              <p class="section-copy">
                {{ t('objectStorage.credentials.rotationHint') }}
              </p>
            </div>
          </div>

          <PageErrorState
            v-if="rotationLoadError && !rotationNotConfigured"
            :message="t('objectStorage.errors.loadCredentials')"
            @retry="loadRotationData"
          />
          <EmptyState
            v-else-if="rotationNotConfigured"
            :title="t('objectStorage.notConfigured')"
            :description="t('objectStorage.notConfiguredHint')"
          />
          <div
            v-else-if="rotationLoading"
            class="py-10 text-center text-sm text-slate-500"
          >
            {{ t('common.loading') }}
          </div>
          <template v-else>
            <div
              v-if="rotationPreview?.candidate"
              class="border-y border-slate-200 py-4"
            >
              <p class="text-xs font-medium uppercase text-slate-400">
                {{ t('objectStorage.credentials.rotationCandidate') }}
              </p>
              <div class="mt-3 flex items-center justify-between gap-4">
                <div>
                  <p class="font-mono text-sm font-semibold text-slate-950">
                    {{
                      t('objectStorage.credentials.endingIn', {
                        lastFour: rotationPreview.candidate.last_four
                      })
                    }}
                  </p>
                  <p class="mt-1 text-xs text-slate-500">
                    {{
                      t('objectStorage.credentials.createdAt', {
                        date: formatDate(rotationPreview.candidate.created_at)
                      })
                    }}
                  </p>
                </div>
                <StatusBadge
                  :status="credentialStatus(rotationPreview.candidate)"
                />
              </div>
              <p class="mt-3 text-xs leading-5 text-slate-500">
                {{ t('objectStorage.credentials.rotationCandidateHelp') }}
              </p>
            </div>

            <p
              v-else
              class="border-y border-slate-200 py-4 text-sm leading-6 text-slate-600"
            >
              {{ t('objectStorage.credentials.noRotationCandidate') }}
            </p>

            <label
              class="mt-4 flex cursor-pointer items-start gap-3 text-sm text-slate-700"
            >
              <input
                v-model="rotationConfirmed"
                type="checkbox"
                class="mt-1 h-4 w-4 rounded border-slate-300 text-sky-600 focus:ring-sky-500"
              />
              <span>{{ t('objectStorage.credentials.rotationConfirm') }}</span>
            </label>

            <div class="mt-5">
              <BaseButton
                variant="danger"
                :loading="rotating"
                :disabled="!rotationConfirmed"
                @click="rotateCredentials"
              >
                {{ t('objectStorage.credentials.rotateAction') }}
              </BaseButton>
            </div>

            <InlineAlert
              v-if="rotationApplication"
              class="mt-5"
              variant="info"
              :title="t('objectStorage.applications.submittedTitle')"
              :message="
                t('objectStorage.applications.submittedMessage', {
                  id: rotationApplication.id
                })
              "
            />
          </template>
        </section>
      </section>
    </PageFrame>
  </AppLayout>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import objectStorageApi, {
  isObjectStorageNotConfigured
} from '@/api/objectStorage'
import AppLayout from '@/components/layout/AppLayout.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import InlineAlert from '@/components/ui/InlineAlert.vue'
import PageFrame from '@/components/ui/PageFrame.vue'
import PageErrorState from '@/components/ui/PageErrorState.vue'
import StatusBadge from '@/components/ui/StatusBadge.vue'
import { useToast } from '@/composables/useToast'
import { formatDateIsoLocale } from '@/utils/formatting'

const { t, locale } = useI18n()
const { showSuccess, showError } = useToast()
const buckets = ref([])
const credentials = ref([])
const applications = ref([])
const rotationPreview = ref(null)
const overviewLoading = ref(false)
const applicationsLoading = ref(false)
const rotationLoading = ref(false)
const overviewLoadError = ref(false)
const applicationsLoadError = ref(false)
const rotationLoadError = ref(false)
const overviewNotConfigured = ref(false)
const applicationsNotConfigured = ref(false)
const rotationNotConfigured = ref(false)
const deliveryApplicationId = ref('')
const delivering = ref(false)
const secretMaterial = ref(null)
const showSecretMaterial = ref(false)
const rotationConfirmed = ref(false)
const rotating = ref(false)
const rotationApplication = ref(null)
const loading = computed(
  () =>
    overviewLoading.value || applicationsLoading.value || rotationLoading.value
)
const deliveryApplications = computed(() =>
  applications.value.filter(
    (application) => application.status === 'delivery_ready'
  )
)

function formatDate(value) {
  return formatDateIsoLocale(value, locale.value)
}

function credentialStatus(credential) {
  if (credential.local_state === 'error') return 'failed'
  if (
    credential.local_state === 'retired' ||
    credential.cloud_state === 'deleted'
  )
    return 'disabled'
  if (
    credential.local_state === 'active' &&
    credential.cloud_state === 'active'
  )
    return 'enabled'
  return 'processing'
}

function clearSecretMaterial() {
  secretMaterial.value = null
  showSecretMaterial.value = false
}

async function copySecret(value) {
  try {
    await navigator.clipboard.writeText(value)
    showSuccess(t('common.copied'))
  } catch {
    showError(t('objectStorage.errors.copySecret'))
  }
}

async function loadOverviewData() {
  overviewLoading.value = true
  overviewLoadError.value = false
  overviewNotConfigured.value = false
  try {
    const overview = await objectStorageApi.getOverview()
    buckets.value = Array.isArray(overview?.buckets) ? overview.buckets : []
    credentials.value = Array.isArray(overview?.credentials)
      ? overview.credentials
      : []
    return true
  } catch (error) {
    buckets.value = []
    credentials.value = []
    overviewLoadError.value = true
    overviewNotConfigured.value = isObjectStorageNotConfigured(error)
    return false
  } finally {
    overviewLoading.value = false
  }
}

async function loadApplicationsData() {
  applicationsLoading.value = true
  applicationsLoadError.value = false
  applicationsNotConfigured.value = false
  try {
    const applicationRows = await objectStorageApi.listApplications()
    applications.value = Array.isArray(applicationRows) ? applicationRows : []
    if (!deliveryApplicationId.value && deliveryApplications.value.length) {
      deliveryApplicationId.value = String(deliveryApplications.value[0].id)
    }
    return true
  } catch (error) {
    applications.value = []
    deliveryApplicationId.value = ''
    applicationsLoadError.value = true
    applicationsNotConfigured.value = isObjectStorageNotConfigured(error)
    return false
  } finally {
    applicationsLoading.value = false
  }
}

async function loadRotationData() {
  rotationLoading.value = true
  rotationLoadError.value = false
  rotationNotConfigured.value = false
  try {
    rotationPreview.value = await objectStorageApi.getRotationPreview()
    return true
  } catch (error) {
    rotationPreview.value = null
    rotationLoadError.value = true
    rotationNotConfigured.value = isObjectStorageNotConfigured(error)
    return false
  } finally {
    rotationLoading.value = false
  }
}

async function loadSafeData() {
  const results = await Promise.allSettled([
    loadOverviewData(),
    loadApplicationsData(),
    loadRotationData()
  ])
  const loadStates = [
    [results[0], overviewNotConfigured.value],
    [results[1], applicationsNotConfigured.value],
    [results[2], rotationNotConfigured.value]
  ]
  if (
    loadStates.some(
      ([result, isNotConfigured]) =>
        result.status === 'rejected' ||
        (result.value === false && !isNotConfigured)
    )
  ) {
    showError(t('objectStorage.errors.loadCredentials'))
  }
}

async function retrieveCredentials() {
  delivering.value = true
  const applicationId = deliveryApplicationId.value
  clearSecretMaterial()
  try {
    const delivery =
      await objectStorageApi.getApplicationDeliveryToken(applicationId)
    const token = delivery?.token
    if (!token) throw new Error('DELIVERY_TOKEN_UNAVAILABLE')
    secretMaterial.value = await objectStorageApi.deliverCredentials(token)
    showSecretMaterial.value = false
    applications.value = applications.value.filter(
      (application) => String(application.id) !== String(applicationId)
    )
    deliveryApplicationId.value = ''
    showSuccess(t('objectStorage.credentials.retrieveSuccess'))
  } catch {
    showError(t('objectStorage.errors.retrieveCredentials'))
  } finally {
    delivering.value = false
  }
}

async function rotateCredentials() {
  if (!rotationConfirmed.value) return
  rotating.value = true
  try {
    rotationApplication.value = await objectStorageApi.rotateCredentials({
      candidate_access_key_id: rotationPreview.value?.candidate?.id,
      confirmed: true
    })
    rotationConfirmed.value = false
    showSuccess(t('objectStorage.credentials.rotationSubmitted'))
  } catch {
    showError(t('objectStorage.errors.rotateCredentials'))
  } finally {
    rotating.value = false
  }
}

onMounted(loadSafeData)
onBeforeUnmount(() => {
  clearSecretMaterial()
  deliveryApplicationId.value = ''
})
</script>
