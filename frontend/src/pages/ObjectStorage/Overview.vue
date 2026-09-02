<template>
  <AppLayout>
    <PageFrame
      class="object-storage-page"
      :eyebrow="t('objectStorage.overview.eyebrow')"
      :title="t('objectStorage.overview.title')"
      :subtitle="t('objectStorage.overview.subtitle')"
      variant="soft"
    >
      <template #actions>
        <BaseButton variant="secondary" :loading="loading" @click="loadData">
          {{ t('common.refresh') }}
        </BaseButton>
        <BaseButton v-if="!notConfigured" @click="goToBuckets">
          {{ t('objectStorage.actions.addBucket') }}
        </BaseButton>
      </template>

      <PageErrorState
        v-if="loadError && !notConfigured"
        :message="t('objectStorage.errors.loadOverview')"
        @retry="loadData"
      />
      <EmptyState
        v-else-if="notConfigured"
        :title="t('objectStorage.notConfigured')"
        :description="t('objectStorage.notConfiguredHint')"
      />

      <section
        v-if="!loadError && !notConfigured"
        class="grid gap-4 md:grid-cols-3"
      >
        <BaseCard shadow="none" class="border border-slate-200">
          <div class="flex items-start justify-between gap-4">
            <div>
              <p class="text-sm font-medium text-slate-500">
                {{ t('objectStorage.overview.bucketQuota') }}
              </p>
              <p
                class="mt-3 text-3xl font-semibold tabular-nums text-slate-950"
              >
                {{ loading ? '—' : overview.quota.used }}
                <span class="text-base font-medium text-slate-400"
                  >/ {{ loading ? '—' : overview.quota.limit }}</span
                >
              </p>
            </div>
            <span class="rounded-md bg-sky-50 p-2 text-sky-700">
              <svg
                class="h-5 w-5"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
                aria-hidden="true"
              >
                <path
                  d="M4 7.5C4 5.57 7.58 4 12 4s8 1.57 8 3.5S16.42 11 12 11 4 9.43 4 7.5Zm0 0V16.5C4 18.43 7.58 20 12 20s8-1.57 8-3.5v-9"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="2"
                />
              </svg>
            </span>
          </div>
          <p class="mt-3 text-xs leading-5 text-slate-500">
            {{ t('objectStorage.overview.quotaAvailable') }}
          </p>
        </BaseCard>

        <BaseCard shadow="none" class="border border-slate-200">
          <div class="flex items-start justify-between gap-4">
            <div>
              <p class="text-sm font-medium text-slate-500">
                {{ t('objectStorage.overview.identityStatus') }}
              </p>
              <div class="mt-3">
                <StatusBadge
                  v-if="overview.cloud_identity"
                  :status="identityStatus(overview.cloud_identity.state)"
                />
                <p v-else class="text-lg font-semibold text-slate-950">
                  {{ t('objectStorage.overview.notCreated') }}
                </p>
              </div>
            </div>
            <span class="rounded-md bg-slate-100 p-2 text-slate-600">
              <svg
                class="h-5 w-5"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
                aria-hidden="true"
              >
                <path
                  d="M12 3a4 4 0 1 1 0 8 4 4 0 0 1 0-8Zm-7 18a7 7 0 0 1 14 0"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="2"
                />
              </svg>
            </span>
          </div>
          <p class="mt-3 text-xs leading-5 text-slate-500">
            {{
              overview.cloud_identity?.ram_user_name ||
              t('objectStorage.overview.identityPending')
            }}
          </p>
        </BaseCard>

        <BaseCard shadow="none" class="border border-slate-200">
          <div class="flex items-start justify-between gap-4">
            <div>
              <p class="text-sm font-medium text-slate-500">
                {{ t('objectStorage.overview.keySummary') }}
              </p>
              <p
                class="mt-3 text-3xl font-semibold tabular-nums text-slate-950"
              >
                {{ overview.credentials.length }}
              </p>
            </div>
            <span class="rounded-md bg-emerald-50 p-2 text-emerald-700">
              <svg
                class="h-5 w-5"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
                aria-hidden="true"
              >
                <path
                  d="M15 7a4 4 0 1 1-7.87 1H3v4h3v3h3v-3h2.13A4 4 0 0 1 15 7Z"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="2"
                />
              </svg>
            </span>
          </div>
          <p class="mt-3 text-xs leading-5 text-slate-500">
            {{ latestCredentialText }}
          </p>
        </BaseCard>
      </section>

      <section
        v-if="!loadError && !notConfigured"
        class="mt-5 grid gap-5 xl:grid-cols-[minmax(0,1.4fr)_minmax(18rem,0.6fr)]"
      >
        <section class="workspace-panel workspace-panel--padded">
          <div class="section-heading">
            <div>
              <h2 class="section-title">
                {{ t('objectStorage.overview.myBuckets') }}
              </h2>
              <p class="section-copy">
                {{ t('objectStorage.overview.myBucketsHint') }}
              </p>
            </div>
            <router-link
              class="text-sm font-medium text-sky-700 hover:text-sky-900"
              :to="{ name: 'ObjectStorageBuckets' }"
            >
              {{ t('objectStorage.actions.viewAll') }}
            </router-link>
          </div>

          <div v-if="loading" class="py-10 text-center text-sm text-slate-500">
            {{ t('common.loading') }}
          </div>
          <div
            v-else-if="recentBuckets.length"
            class="divide-y divide-slate-100 border-y border-slate-200"
          >
            <article
              v-for="bucket in recentBuckets"
              :key="bucket.id"
              class="flex flex-col gap-3 py-4 sm:flex-row sm:items-center sm:justify-between"
            >
              <div class="min-w-0">
                <p class="break-all text-sm font-semibold text-slate-950">
                  {{ bucket.name }}
                </p>
                <p class="mt-1 text-xs text-slate-500">
                  {{ bucket.project }} ·
                  {{ environmentText(bucket.environment) }} ·
                  {{ bucket.region }}
                </p>
              </div>
              <StatusBadge :status="bucketStatus(bucket.state)" />
            </article>
          </div>
          <EmptyState
            v-else
            :title="t('objectStorage.overview.noBuckets')"
            :description="t('objectStorage.overview.noBucketsHint')"
          >
            <template #actions>
              <BaseButton size="sm" @click="goToBuckets">
                {{ t('objectStorage.actions.addFirstBucket') }}
              </BaseButton>
            </template>
          </EmptyState>
        </section>

        <section class="workspace-panel workspace-panel--padded">
          <div class="section-heading">
            <div>
              <h2 class="section-title">
                {{ t('objectStorage.overview.quickActions') }}
              </h2>
              <p class="section-copy">
                {{ t('objectStorage.overview.quickActionsHint') }}
              </p>
            </div>
          </div>
          <div class="divide-y divide-slate-100 border-y border-slate-200">
            <router-link
              v-for="action in quickActions"
              :key="action.name"
              :to="{ name: action.name }"
              class="flex min-h-14 items-center justify-between gap-4 py-3 text-sm font-medium text-slate-700 transition-colors hover:text-sky-700"
            >
              <span>{{ t(action.label) }}</span>
              <svg
                class="h-4 w-4 shrink-0"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
                aria-hidden="true"
              >
                <path
                  d="m9 5 7 7-7 7"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="2"
                />
              </svg>
            </router-link>
          </div>
        </section>
      </section>

      <section
        v-if="!loadError && !notConfigured"
        class="mt-5 workspace-panel workspace-panel--padded"
      >
        <div class="section-heading">
          <div>
            <h2 class="section-title">
              {{ t('objectStorage.overview.latestApplications') }}
            </h2>
            <p class="section-copy">
              {{ t('objectStorage.overview.latestApplicationsHint') }}
            </p>
          </div>
        </div>
        <div
          v-if="overview.applications.length"
          class="divide-y divide-slate-100 border-y border-slate-200"
        >
          <article
            v-for="application in overview.applications"
            :key="application.id"
            class="grid gap-3 py-4 sm:grid-cols-[minmax(0,1fr)_auto_auto] sm:items-center"
          >
            <div>
              <p class="text-sm font-semibold text-slate-950">
                {{ actionTypeText(application.action_type) }}
              </p>
              <p class="mt-1 text-xs text-slate-500">
                {{ formatDate(application.created_at) }}
              </p>
            </div>
            <StatusBadge :status="applicationStatus(application.status)" />
            <router-link
              :to="{ name: 'ObjectStorageApplications' }"
              class="text-sm font-medium text-sky-700 hover:text-sky-900"
            >
              {{ t('common.viewDetails') }}
            </router-link>
          </article>
        </div>
        <EmptyState
          v-else
          :title="t('objectStorage.applications.emptyTitle')"
          :description="t('objectStorage.applications.emptyHint')"
        />
      </section>
    </PageFrame>
  </AppLayout>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import objectStorageApi, {
  isObjectStorageNotConfigured
} from '@/api/objectStorage'
import AppLayout from '@/components/layout/AppLayout.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseCard from '@/components/ui/BaseCard.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import PageFrame from '@/components/ui/PageFrame.vue'
import PageErrorState from '@/components/ui/PageErrorState.vue'
import StatusBadge from '@/components/ui/StatusBadge.vue'
import { formatDateIsoLocale } from '@/utils/formatting'

const { t, locale } = useI18n()
const router = useRouter()
const overview = reactive({
  quota: { used: 0, limit: 0 },
  cloud_identity: null,
  buckets: [],
  credentials: [],
  applications: []
})
const loading = ref(false)
const loadError = ref(false)
const notConfigured = ref(false)

const buckets = computed(() => overview.buckets)
const recentBuckets = computed(() => buckets.value.slice(0, 3))
const latestCredentialText = computed(() => {
  const credential = overview.credentials[0]
  return credential
    ? t('objectStorage.credentials.endingIn', {
        lastFour: credential.last_four
      })
    : t('objectStorage.overview.noCredentials')
})
const quickActions = [
  {
    name: 'ObjectStorageBuckets',
    label: 'objectStorage.actions.manageBuckets'
  },
  {
    name: 'ObjectStorageCredentials',
    label: 'objectStorage.actions.manageCredentials'
  },
  {
    name: 'ObjectStorageApplications',
    label: 'objectStorage.actions.viewApplications'
  }
]

function bucketStatus(state) {
  if (state === 'active') return 'enabled'
  if (state === 'failed') return 'failed'
  if (state === 'released') return 'disabled'
  return 'processing'
}

function identityStatus(state) {
  if (state === 'active') return 'enabled'
  if (state === 'error') return 'failed'
  if (state === 'suspended') return 'disabled'
  return 'processing'
}

function applicationStatus(status) {
  if (status === 'succeeded' || status === 'delivery_ready') return 'success'
  if (status === 'failed' || status === 'manual_required') return 'failed'
  if (status === 'cancelled') return 'disabled'
  if (status === 'pending') return 'pending'
  return 'processing'
}

function actionTypeText(actionType) {
  return t(`objectStorage.applicationTypes.${actionType}`, actionType)
}

function formatDate(value) {
  return formatDateIsoLocale(value, locale.value)
}

function environmentText(environment) {
  return t(`objectStorage.environments.${environment}`, environment)
}

function goToBuckets() {
  router.push({ name: 'ObjectStorageBuckets' })
}

async function loadData() {
  loading.value = true
  loadError.value = false
  notConfigured.value = false
  try {
    const payload = await objectStorageApi.getOverview()
    Object.assign(overview, {
      quota: payload?.quota || { used: 0, limit: 0 },
      cloud_identity: payload?.cloud_identity || null,
      buckets: Array.isArray(payload?.buckets) ? payload.buckets : [],
      credentials: Array.isArray(payload?.credentials)
        ? payload.credentials
        : [],
      applications: Array.isArray(payload?.applications)
        ? payload.applications
        : []
    })
  } catch (error) {
    loadError.value = true
    notConfigured.value = isObjectStorageNotConfigured(error)
    Object.assign(overview, {
      quota: { used: 0, limit: 0 },
      cloud_identity: null,
      buckets: [],
      credentials: [],
      applications: []
    })
  } finally {
    loading.value = false
  }
}

onMounted(loadData)
</script>
