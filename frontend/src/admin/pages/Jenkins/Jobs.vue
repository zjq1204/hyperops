<template>
  <AdminLayout>
    <PageFrame
      variant="soft"
      :eyebrow="t('adminPages.jenkinsJobs.eyebrow')"
      :title="t('adminPages.jenkinsJobs.title')"
      :subtitle="t('adminPages.jenkinsJobs.subtitle')"
    >
      <section class="metrics-strip metrics-strip--four">
        <MetricTile
          :label="t('adminPages.jenkinsJobs.totalJobs')"
          :value="allJobsFlat.length"
          :hint="t('adminPages.jenkinsJobs.totalJobsHint')"
        />
        <MetricTile
          :label="t('adminPages.jenkinsJobs.folderCount')"
          :value="folderCount"
          :hint="t('adminPages.jenkinsJobs.folderCountHint')"
        />
        <MetricTile
          :label="t('adminPages.jenkinsJobs.filteredJobs')"
          :value="filteredJobs.length"
          :hint="t('adminPages.jenkinsJobs.filteredJobsHint')"
        />
        <MetricTile
          :label="t('adminPages.jenkinsJobs.selectedJob')"
          :value="selectedJob ? '1' : '0'"
          :hint="t('adminPages.jenkinsJobs.selectedJobHint')"
        />
      </section>

      <section class="admin-filter-panel">
        <div class="admin-filter-grid xl:grid-cols-none">
          <div class="admin-filter-field">
            <label class="admin-filter-label">
              {{ t('adminPages.jenkinsJobs.selectInstance') }}
            </label>
            <select
              v-model="selectedInstanceId"
              class="admin-filter-control min-w-[18rem]"
            >
              <option value="">
                {{ t('adminPages.jenkinsJobs.selectInstancePlaceholder') }}
              </option>
              <option
                v-for="inst in instances"
                :key="inst.id"
                :value="String(inst.id)"
              >
                {{ inst.name }}
              </option>
            </select>
          </div>

          <div class="admin-filter-field flex-1">
            <label class="admin-filter-label">
              {{ t('adminPages.jenkinsJobs.search') }}
            </label>
            <div class="relative">
              <svg
                class="pointer-events-none absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2 text-slate-400"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="2"
                  d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
                />
              </svg>
              <input
                v-model="searchQuery"
                type="text"
                :placeholder="t('adminPages.jenkinsJobs.searchPlaceholder')"
                class="admin-filter-control w-full pl-12"
              />
            </div>
          </div>

          <div class="admin-filter-field">
            <label class="admin-filter-label">
              {{ t('adminPages.jenkinsJobs.displayMode') }}
            </label>
            <button
              type="button"
              class="admin-filter-control inline-flex w-full items-center justify-center gap-2 px-4 font-semibold transition-colors duration-200"
              :class="
                showEnabledOnly
                  ? 'border-emerald-200 bg-emerald-50 text-emerald-700 shadow-[0_8px_20px_rgba(16,185,129,0.12)] hover:border-emerald-300 hover:bg-emerald-100'
                  : 'text-slate-600 hover:border-slate-300 hover:bg-slate-50'
              "
              @click="showEnabledOnly = !showEnabledOnly"
            >
              <span
                class="h-2.5 w-2.5 rounded-full"
                :class="showEnabledOnly ? 'bg-emerald-500' : 'bg-slate-300'"
              ></span>
              {{
                showEnabledOnly
                  ? t('adminPages.jenkinsJobs.showingEnabledOnly')
                  : t('adminPages.jenkinsJobs.showingAllJobs')
              }}
            </button>
          </div>
        </div>

        <div
          v-if="jobSourceLabel || lastFetchedLabel"
          class="mt-2 flex flex-wrap items-center gap-3 text-xs text-slate-500"
        >
          <span
            v-if="jobSourceLabel"
            class="admin-status-badge admin-status-badge--muted"
            >{{ jobSourceLabel }}</span
          >
          <span v-if="lastFetchedLabel">{{ lastFetchedLabel }}</span>
        </div>
      </section>

      <section
        v-if="loadingJobs"
        class="rounded-[1.75rem] border border-white/75 bg-white/78 px-6 py-16 shadow-[0_20px_50px_rgba(15,23,42,0.08)]"
      >
        <div class="flex justify-center">
          <div
            class="h-12 w-12 animate-spin rounded-full border-4 border-slate-200 border-t-sky-500"
          ></div>
        </div>
      </section>

      <EmptyState
        v-else-if="!instances.length"
        variant="admin"
        :title="t('adminPages.jenkinsJobs.emptyNoInstanceTitle')"
        :description="t('adminPages.jenkinsJobs.emptyNoInstanceSubtitle')"
      >
        <template #actions>
          <BaseButton @click="goToInstances">{{
            t('adminPages.jenkinsJobs.goToInstances')
          }}</BaseButton>
        </template>
      </EmptyState>

      <EmptyState
        v-else-if="!selectedInstanceId"
        variant="admin"
        :title="t('adminPages.jenkinsJobs.emptySelectTitle')"
        :description="t('adminPages.jenkinsJobs.emptySelectSubtitle')"
      >
        <template #actions>
          <BaseButton @click="selectDefaultInstance">{{
            t('adminPages.jenkinsJobs.selectDefaultInstance')
          }}</BaseButton>
        </template>
      </EmptyState>

      <EmptyState
        v-else-if="!filteredJobs.length"
        variant="admin"
        :title="
          showEnabledOnly
            ? t('adminPages.jenkinsJobs.emptyEnabledTitle')
            : t('adminPages.jenkinsJobs.emptyTitle')
        "
        :description="
          showEnabledOnly
            ? t('adminPages.jenkinsJobs.emptyEnabledSubtitle')
            : t('adminPages.jenkinsJobs.emptySubtitle')
        "
      >
        <template #actions>
          <BaseButton variant="secondary" @click="goToInstances">{{
            t('adminPages.jenkinsJobs.goToInstances')
          }}</BaseButton>
          <BaseButton
            v-if="showEnabledOnly"
            variant="outline"
            @click="showEnabledOnly = false"
          >
            {{ t('adminPages.jenkinsJobs.showAllJobs') }}
          </BaseButton>
        </template>
      </EmptyState>

      <section
        v-else
        class="grid gap-5 xl:grid-cols-[minmax(0,1.45fr)_minmax(24rem,0.95fr)]"
      >
        <article
          class="rounded-[1.9rem] border border-white/75 bg-white/82 shadow-[0_24px_70px_rgba(15,23,42,0.1)] backdrop-blur"
        >
          <div
            class="flex items-center justify-between gap-4 border-b border-slate-200/70 px-5 py-4"
          >
            <div>
              <p class="text-sm font-semibold text-slate-900">
                {{
                  selectedInstance?.name ||
                  t('adminPages.jenkinsJobs.jobListTitle')
                }}
              </p>
              <p class="mt-1 text-xs text-slate-500">
                {{ t('adminPages.jenkinsJobs.jobListSubtitle') }}
              </p>
            </div>
            <span class="admin-status-badge admin-status-badge--muted"
              >{{ filteredJobs.length }} / {{ allJobsFlat.length }}</span
            >
          </div>

          <div class="max-h-[44rem] overflow-y-auto p-3">
            <button
              v-for="job in filteredJobs"
              :key="job.full_name"
              type="button"
              class="group mb-2 flex w-full items-stretch rounded-[1.35rem] border px-4 py-4 text-left transition-all duration-200"
              :class="
                selectedJob?.full_name === job.full_name
                  ? 'border-sky-300 bg-sky-50/80 shadow-[0_16px_30px_rgba(56,189,248,0.12)]'
                  : job.enabled === false
                    ? 'border-slate-200/70 bg-slate-50/80 opacity-80 hover:border-slate-300 hover:bg-slate-100/80'
                    : 'border-slate-200/80 bg-white/85 hover:border-sky-200 hover:bg-white'
              "
              @click="selectJob(job)"
            >
              <div
                class="flex w-full min-w-0 items-start gap-4"
                :style="{ paddingLeft: `${job.depth * 1.1}rem` }"
              >
                <div
                  class="flex h-11 w-11 flex-shrink-0 items-center justify-center rounded-[0.95rem] border shadow-sm"
                  :class="
                    job.has_children
                      ? 'border-sky-200 bg-sky-50 text-sky-700'
                      : 'border-slate-200 bg-slate-50 text-slate-600'
                  "
                >
                  <svg
                    v-if="job.has_children"
                    class="h-5 w-5"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      stroke-linecap="round"
                      stroke-linejoin="round"
                      stroke-width="1.9"
                      d="M3 7h6l2 2h10v8a2 2 0 01-2 2H3V7z"
                    />
                  </svg>
                  <svg
                    v-else
                    class="h-5 w-5"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      stroke-linecap="round"
                      stroke-linejoin="round"
                      stroke-width="1.9"
                      d="M4 7h16M4 12h16M4 17h10"
                    />
                  </svg>
                </div>

                <div class="min-w-0 flex-1">
                  <div class="flex flex-wrap items-center gap-2">
                    <h3 class="truncate text-lg font-semibold text-slate-900">
                      {{ job.display_name }}
                    </h3>
                    <span
                      class="rounded-full px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.2em]"
                      :class="
                        job.has_children
                          ? 'bg-sky-100 text-sky-700'
                          : 'bg-slate-100 text-slate-500'
                      "
                    >
                      {{ job.type }}
                    </span>
                    <span
                      v-if="
                        !job.has_children &&
                        job.enabled !== null &&
                        job.enabled !== undefined
                      "
                      class="rounded-full px-2.5 py-1 text-[11px] font-semibold tracking-[0.08em]"
                      :class="
                        job.enabled
                          ? 'bg-emerald-100 text-emerald-700'
                          : 'bg-amber-100 text-amber-700'
                      "
                    >
                      {{
                        job.enabled
                          ? t('adminPages.jenkinsJobs.enabled')
                          : t('adminPages.jenkinsJobs.disabled')
                      }}
                    </span>
                  </div>
                  <p class="mt-1 truncate font-mono text-xs text-slate-500">
                    {{ job.full_name }}
                  </p>
                  <p class="mt-2 truncate text-xs text-slate-500">
                    {{ job.url }}
                  </p>
                  <div class="mt-3 flex flex-wrap gap-2">
                    <span
                      v-if="job.has_children"
                      class="admin-status-badge admin-status-badge--success"
                      >{{ t('adminPages.jenkinsJobs.hasChildren') }}</span
                    >
                  </div>
                </div>
              </div>
            </button>
          </div>
        </article>

        <aside
          class="rounded-[1.9rem] border border-white/75 bg-white/86 p-5 shadow-[0_24px_70px_rgba(15,23,42,0.1)] backdrop-blur"
        >
          <template v-if="selectedJob">
            <div class="flex items-start justify-between gap-4">
              <div class="min-w-0">
                <p
                  class="text-xs font-semibold uppercase tracking-[0.24em] text-sky-600"
                >
                  {{
                    selectedJob.has_children
                      ? t('adminPages.jenkinsJobs.folder')
                      : t('adminPages.jenkinsJobs.job')
                  }}
                </p>
                <h2 class="mt-2 truncate text-2xl font-semibold text-slate-900">
                  {{ selectedJob.display_name }}
                </h2>
                <p class="mt-2 break-all font-mono text-sm text-slate-500">
                  {{ selectedJob.full_name }}
                </p>
              </div>
              <div class="flex flex-wrap justify-end gap-2">
                <span class="admin-status-badge admin-status-badge--success">{{
                  selectedJob.type
                }}</span>
                <span
                  v-if="
                    !selectedJob.has_children &&
                    selectedJob.enabled !== null &&
                    selectedJob.enabled !== undefined
                  "
                  class="rounded-full px-3 py-1 text-xs font-semibold tracking-[0.08em]"
                  :class="
                    selectedJob.enabled
                      ? 'bg-emerald-100 text-emerald-700'
                      : 'bg-amber-100 text-amber-700'
                  "
                >
                  {{
                    selectedJob.enabled
                      ? t('adminPages.jenkinsJobs.enabled')
                      : t('adminPages.jenkinsJobs.disabled')
                  }}
                </span>
              </div>
            </div>

            <div class="mt-6 grid gap-3 sm:grid-cols-2">
              <div
                class="rounded-[1.2rem] border border-slate-200/80 bg-slate-50/75 px-4 py-3"
              >
                <p
                  class="text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-400"
                >
                  {{ t('adminPages.jenkinsJobs.detailPath') }}
                </p>
                <p class="mt-2 break-all font-mono text-sm text-slate-700">
                  {{ selectedJob.full_name }}
                </p>
              </div>
              <div
                class="rounded-[1.2rem] border border-slate-200/80 bg-slate-50/75 px-4 py-3"
              >
                <p
                  class="text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-400"
                >
                  {{ t('adminPages.jenkinsJobs.detailType') }}
                </p>
                <p class="mt-2 text-sm font-medium text-slate-700">
                  {{ selectedJob.type }}
                </p>
              </div>
              <div
                class="rounded-[1.2rem] border border-slate-200/80 bg-slate-50/75 px-4 py-3"
              >
                <p
                  class="text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-400"
                >
                  {{ t('adminPages.jenkinsJobs.detailUrl') }}
                </p>
                <a
                  :href="selectedJob.url"
                  target="_blank"
                  rel="noreferrer"
                  class="mt-2 block break-all text-sm font-medium text-sky-700 hover:text-sky-900"
                >
                  {{ selectedJob.url }}
                </a>
              </div>
              <div
                class="rounded-[1.2rem] border border-slate-200/80 bg-slate-50/75 px-4 py-3"
              >
                <p
                  class="text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-400"
                >
                  {{ t('adminPages.jenkinsJobs.detailChildren') }}
                </p>
                <p class="mt-2 text-sm font-medium text-slate-700">
                  {{
                    selectedJob.has_children
                      ? t('adminPages.jenkinsJobs.hasChildren')
                      : t('adminPages.jenkinsJobs.noChildren')
                  }}
                </p>
              </div>
              <div
                v-if="
                  !selectedJob.has_children &&
                  selectedJob.enabled !== null &&
                  selectedJob.enabled !== undefined
                "
                class="rounded-[1.2rem] border border-slate-200/80 bg-slate-50/75 px-4 py-3"
              >
                <p
                  class="text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-400"
                >
                  {{ t('adminPages.jenkinsJobs.detailStatus') }}
                </p>
                <p
                  class="mt-2 text-sm font-medium"
                  :class="
                    selectedJob.enabled ? 'text-emerald-700' : 'text-amber-700'
                  "
                >
                  {{
                    selectedJob.enabled
                      ? t('adminPages.jenkinsJobs.enabled')
                      : t('adminPages.jenkinsJobs.disabled')
                  }}
                </p>
              </div>
              <div
                v-if="!selectedJob.has_children && selectedJob.color"
                class="rounded-[1.2rem] border border-slate-200/80 bg-slate-50/75 px-4 py-3"
              >
                <p
                  class="text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-400"
                >
                  {{ t('adminPages.jenkinsJobs.detailColor') }}
                </p>
                <p class="mt-2 font-mono text-sm text-slate-700">
                  {{ selectedJob.color }}
                </p>
              </div>
            </div>

            <div class="mt-6 flex flex-wrap gap-3">
              <BaseButton @click="useForEntry(selectedJob)">{{
                t('adminPages.jenkinsJobs.useForEntry')
              }}</BaseButton>
              <BaseButton
                variant="secondary"
                @click="copyJobPath(selectedJob.full_name)"
              >
                {{ t('adminPages.jenkinsJobs.copyPath') }}
              </BaseButton>
              <BaseButton
                variant="outline"
                @click="openInJenkins(selectedJob.url)"
              >
                {{ t('adminPages.jenkinsJobs.openInJenkins') }}
              </BaseButton>
            </div>

            <div
              class="mt-6 rounded-[1.35rem] border border-slate-200/80 bg-gradient-to-br from-sky-50/90 via-white to-indigo-50/80 px-4 py-4"
            >
              <p
                class="text-xs font-semibold uppercase tracking-[0.22em] text-slate-400"
              >
                {{ t('adminPages.jenkinsJobs.detailNoteTitle') }}
              </p>
              <p class="mt-2 text-sm leading-6 text-slate-600">
                {{ t('adminPages.jenkinsJobs.detailNote') }}
              </p>
            </div>
          </template>

          <EmptyState
            v-else
            :title="t('adminPages.jenkinsJobs.emptyDetailTitle')"
            :description="t('adminPages.jenkinsJobs.emptyDetailSubtitle')"
          >
            <template #icon>
              <svg
                class="h-8 w-8"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="2"
                  d="M4 7h6l2 2h8a2 2 0 012 2v6a2 2 0 01-2 2H4V7z"
                />
              </svg>
            </template>
          </EmptyState>
        </aside>
      </section>

      <div
        v-if="toast.show"
        :class="[
          'fixed bottom-4 right-4 rounded-md px-4 py-2 text-white shadow-lg',
          toast.type === 'success' ? 'bg-green-600' : 'bg-red-600'
        ]"
      >
        {{ toast.message }}
      </div>
    </PageFrame>
  </AdminLayout>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import AdminLayout from '@/admin/layout/AdminLayout.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import MetricTile from '@/components/ui/MetricTile.vue'
import PageFrame from '@/components/ui/PageFrame.vue'
import jenkinsApi from '@/api/jenkins'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()

const instances = ref([])
const selectedInstanceId = ref('')
const jobsTree = ref([])
const searchQuery = ref('')
const loadingInstances = ref(false)
const loadingJobs = ref(false)
const selectedJobFullName = ref('')
const toast = ref({ show: false, message: '', type: 'success' })
const jobsFetchedAt = ref('')
const jobsCached = ref(false)
const jobsStale = ref(false)
const showEnabledOnly = ref(true)

const selectedInstance = computed(
  () =>
    instances.value.find(
      (item) => String(item.id) === selectedInstanceId.value
    ) || null
)

function showToast(message, type = 'success') {
  toast.value = { show: true, message, type }
  setTimeout(() => {
    toast.value.show = false
  }, 3000)
}

function flattenJobs(nodes, depth = 0, acc = []) {
  for (const node of nodes || []) {
    acc.push({ ...node, depth })
    if (node.children?.length) {
      flattenJobs(node.children, depth + 1, acc)
    }
  }
  return acc
}

const allJobsFlat = computed(() => flattenJobs(jobsTree.value))

const folderCount = computed(
  () => allJobsFlat.value.filter((job) => job.has_children).length
)

const visibleJobs = computed(() => {
  if (!showEnabledOnly.value) return allJobsFlat.value

  return allJobsFlat.value.filter((job) => {
    if (job.has_children) return false
    if (job.enabled === null || job.enabled === undefined) return true
    return job.enabled === true
  })
})

const filteredJobs = computed(() => {
  const query = searchQuery.value.trim().toLowerCase()
  if (!query) return visibleJobs.value
  return visibleJobs.value.filter((job) => {
    return [job.display_name, job.full_name, job.url, job.type]
      .filter(Boolean)
      .some((value) => String(value).toLowerCase().includes(query))
  })
})

const selectedJob = computed(() => {
  return (
    filteredJobs.value.find(
      (job) => job.full_name === selectedJobFullName.value
    ) ||
    filteredJobs.value[0] ||
    null
  )
})

const jobSourceLabel = computed(() => {
  if (!selectedInstanceId.value || !jobsFetchedAt.value) return ''
  if (jobsStale.value) return t('adminPages.jenkinsJobs.status.staleCache')
  return jobsCached.value
    ? t('adminPages.jenkinsJobs.status.cached')
    : t('adminPages.jenkinsJobs.status.live')
})

const lastFetchedLabel = computed(() => {
  if (!jobsFetchedAt.value) return ''
  const formatted = new Date(jobsFetchedAt.value)
  if (Number.isNaN(formatted.getTime())) return ''
  return t('adminPages.jenkinsJobs.status.fetchedAt', {
    time: formatted.toLocaleString()
  })
})

async function loadInstances() {
  loadingInstances.value = true
  try {
    instances.value = await jenkinsApi.listInstances()
    const routeInstanceId = route.query.instance
      ? String(route.query.instance)
      : ''
    if (
      routeInstanceId &&
      instances.value.some((item) => String(item.id) === routeInstanceId)
    ) {
      selectedInstanceId.value = routeInstanceId
      return
    }

    if (!selectedInstanceId.value && instances.value.length) {
      const activeInstance =
        instances.value.find((item) => item.is_active) || instances.value[0]
      selectedInstanceId.value = String(activeInstance.id)
    }
  } catch (e) {
    showToast(
      t('adminPages.jenkinsJobs.toast.loadInstancesFailed', {
        message: e.message
      }),
      'error'
    )
  } finally {
    loadingInstances.value = false
  }
}

async function loadJobs(options = {}) {
  if (!selectedInstanceId.value) {
    jobsTree.value = []
    selectedJobFullName.value = ''
    jobsFetchedAt.value = ''
    jobsCached.value = false
    jobsStale.value = false
    return
  }

  loadingJobs.value = true
  try {
    const data = await jenkinsApi.listJobs(selectedInstanceId.value, options)
    jobsTree.value = data.jobs || []
    jobsFetchedAt.value = data.fetched_at || ''
    jobsCached.value = Boolean(data.cached)
    jobsStale.value = Boolean(data.stale)
    const flatJobs = flattenJobs(jobsTree.value)
    const firstEnabledJob = flatJobs.find(
      (job) => !job.has_children && job.enabled === true
    )
    const firstJob =
      firstEnabledJob ||
      flatJobs.find((job) => !job.has_children) ||
      flatJobs[0]
    if (
      !selectedJobFullName.value ||
      !flatJobs.some((job) => job.full_name === selectedJobFullName.value)
    ) {
      selectedJobFullName.value = firstJob?.full_name || ''
    }
    if (data.warning) {
      showToast(data.warning, 'error')
    }
  } catch (e) {
    jobsTree.value = []
    selectedJobFullName.value = ''
    jobsFetchedAt.value = ''
    jobsCached.value = false
    jobsStale.value = false
    showToast(
      t('adminPages.jenkinsJobs.toast.loadJobsFailed', { message: e.message }),
      'error'
    )
  } finally {
    loadingJobs.value = false
  }
}

function selectJob(job) {
  selectedJobFullName.value = job.full_name
}

function useForEntry(job) {
  if (!selectedInstanceId.value) return
  router.push({
    path: '/management/jenkins/entries',
    query: {
      instance: selectedInstanceId.value,
      job_name: job.full_name,
      job_label: job.display_name
    }
  })
}

function goToInstances() {
  router.push('/management/jenkins/instances')
}

function selectDefaultInstance() {
  if (instances.value.length) {
    const activeInstance =
      instances.value.find((item) => item.is_active) || instances.value[0]
    selectedInstanceId.value = String(activeInstance.id)
  }
}

async function copyJobPath(path) {
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(path)
      showToast(t('adminPages.jenkinsJobs.toast.copySucceeded'))
    } else {
      throw new Error('Clipboard API not available')
    }
  } catch (e) {
    showToast(
      t('adminPages.jenkinsJobs.toast.copyFailed', { message: e.message }),
      'error'
    )
  }
}

function openInJenkins(url) {
  window.open(url, '_blank', 'noopener,noreferrer')
}

watch(
  selectedInstanceId,
  () => {
    if (selectedInstanceId.value) {
      selectedJobFullName.value = ''
      loadJobs()
    }
  },
  { flush: 'post' }
)

watch(
  jobsTree,
  () => {
    if (!selectedJobFullName.value && selectedJob.value) {
      selectedJobFullName.value = selectedJob.value.full_name
    }
  },
  { deep: true }
)

watch(
  [filteredJobs, showEnabledOnly],
  () => {
    if (!filteredJobs.value.length) {
      selectedJobFullName.value = ''
      return
    }
    if (
      !filteredJobs.value.some(
        (job) => job.full_name === selectedJobFullName.value
      )
    ) {
      selectedJobFullName.value = filteredJobs.value[0].full_name
    }
  },
  { flush: 'post' }
)

onMounted(async () => {
  await loadInstances()
})
</script>
