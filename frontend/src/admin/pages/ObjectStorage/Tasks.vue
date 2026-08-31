<template>
  <AdminLayout>
    <PageFrame variant="soft" :title="t('adminPages.objectStorage.tasks')">
      <AdminListSection>
        <template #toolbarStart>
          <select
            v-model="tenantId"
            class="admin-filter-control min-w-52"
            @change="loadTasks"
          >
            <option value="">
              {{ t('adminPages.objectStorage.selectTenant') }}
            </option>
            <option
              v-for="tenant in tenants"
              :key="tenant.id"
              :value="String(tenant.id)"
            >
              {{ tenant.name }}
            </option>
          </select>
          <select v-model="statusFilter" class="admin-filter-control min-w-40">
            <option value="">
              {{ t('adminPages.objectStorage.allStatuses') }}
            </option>
            <option v-for="status in statuses" :key="status" :value="status">
              {{ statusLabel(status) }}
            </option>
          </select>
          <select v-model="actionFilter" class="admin-filter-control min-w-48">
            <option value="">
              {{ t('adminPages.objectStorage.allTaskTypes') }}
            </option>
            <option v-for="action in actions" :key="action" :value="action">
              {{ actionLabel(action) }}
            </option>
          </select>
        </template>
        <template #toolbarEnd
          ><span class="admin-summary-pill">{{
            t('adminPages.objectStorage.taskCount', {
              count: filteredTasks.length
            })
          }}</span
          ><BaseButton
            variant="outline"
            size="sm"
            :loading="loading"
            @click="loadTasks"
            >{{ t('common.refresh') }}</BaseButton
          ></template
        >

        <InlineAlert
          v-if="error"
          class="mb-4"
          variant="error"
          :message="error"
        />
        <AdminPageState
          :loading="loading"
          :error="''"
          :empty="!filteredTasks.length"
          :empty-title="t('adminPages.objectStorage.noTasks')"
        >
          <section class="admin-workbench-panel overflow-hidden">
            <div class="divide-y divide-slate-200">
              <article
                v-for="task in filteredTasks"
                :key="task.id"
                :class="
                  task.status === 'manual_required'
                    ? 'border-l-4 border-l-rose-500'
                    : ''
                "
              >
                <button
                  type="button"
                  class="grid w-full gap-3 px-5 py-4 text-left hover:bg-slate-50 lg:grid-cols-[minmax(0,1.2fr)_minmax(8rem,0.5fr)_minmax(10rem,0.6fr)_auto] lg:items-center"
                  :aria-expanded="expandedId === task.id"
                  @click="toggleDetail(task)"
                >
                  <div class="min-w-0">
                    <p class="font-semibold text-slate-950">
                      {{ actionLabel(task.action_type) }}
                    </p>
                    <p class="mt-1 text-xs text-slate-500">
                      {{
                        t('adminPages.objectStorage.taskReference', {
                          id: task.id
                        })
                      }}
                      ·
                      {{
                        t('adminPages.objectStorage.memberReference', {
                          id: task.applicant_id
                        })
                      }}
                    </p>
                  </div>
                  <div>
                    <p class="text-xs text-slate-500">
                      {{ t('adminPages.objectStorage.currentStage') }}
                    </p>
                    <p class="mt-1 text-sm font-medium text-slate-800">
                      {{ stageLabel(task.current_stage) }}
                    </p>
                  </div>
                  <div>
                    <p class="text-xs text-slate-500">
                      {{ t('adminPages.objectStorage.createdAt') }}
                    </p>
                    <p class="mt-1 text-sm text-slate-700">
                      {{ formatDate(task.created_at) }}
                    </p>
                  </div>
                  <div
                    class="flex items-center justify-between gap-3 lg:justify-end"
                  >
                    <StatusBadge :status="statusBadge(task.status)" /><span
                      class="text-slate-400"
                      aria-hidden="true"
                      >{{ expandedId === task.id ? '⌃' : '⌄' }}</span
                    >
                  </div>
                </button>

                <div
                  v-if="expandedId === task.id"
                  class="border-t border-slate-200 bg-slate-50/60 px-5 py-5"
                >
                  <div v-if="detailLoading" class="text-sm text-slate-500">
                    {{ t('common.loading') }}
                  </div>
                  <div v-else-if="detail" class="grid gap-5">
                    <InlineAlert
                      v-if="detail.error_code"
                      variant="warning"
                      :title="detail.error_code"
                      :message="
                        detail.error_summary ||
                        t('adminPages.objectStorage.manualReviewHint')
                      "
                    />
                    <dl class="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                      <InfoCell
                        :label="t('adminPages.objectStorage.taskType')"
                        :value="actionLabel(detail.action_type)"
                      /><InfoCell
                        :label="t('common.status')"
                        :value="statusLabel(detail.status)"
                      /><InfoCell
                        :label="t('adminPages.objectStorage.startedAt')"
                        :value="formatDate(detail.started_at)"
                      /><InfoCell
                        :label="t('adminPages.objectStorage.finishedAt')"
                        :value="formatDate(detail.finished_at)"
                      />
                    </dl>
                    <section>
                      <h3
                        class="text-xs font-semibold uppercase tracking-wide text-slate-500"
                      >
                        {{ t('adminPages.objectStorage.executionProcess') }}
                      </h3>
                      <ol class="mt-3 grid gap-2">
                        <li
                          v-for="event in detail.events || []"
                          :key="event.id"
                          class="grid gap-2 border-l-2 border-slate-300 bg-white px-4 py-3 sm:grid-cols-[minmax(8rem,0.35fr)_minmax(8rem,0.35fr)_minmax(0,1fr)_auto]"
                        >
                          <span class="text-sm font-medium text-slate-900">{{
                            stageLabel(event.stage)
                          }}</span
                          ><span class="text-sm text-slate-600">{{
                            resultLabel(event.result)
                          }}</span
                          ><span class="text-xs text-rose-700">{{
                            event.error_code || t('common.emptyValue')
                          }}</span
                          ><time class="text-xs text-slate-500">{{
                            formatDate(event.created_at)
                          }}</time>
                        </li>
                      </ol>
                      <p
                        v-if="!detail.events?.length"
                        class="mt-3 text-sm text-slate-500"
                      >
                        {{ t('adminPages.objectStorage.noExecutionEvents') }}
                      </p>
                    </section>
                    <div
                      v-if="
                        ['manual_required', 'failed'].includes(detail.status)
                      "
                      class="flex flex-wrap justify-end gap-2 border-t border-slate-200 pt-4"
                    >
                      <BaseButton
                        variant="outline"
                        :loading="acting === 'resolve'"
                        @click="resolveTask(detail)"
                        >{{
                          t('adminPages.objectStorage.markResolved')
                        }}</BaseButton
                      ><BaseButton
                        :loading="acting === 'retry'"
                        @click="retryTask(detail)"
                        >{{
                          t('adminPages.objectStorage.retryTask')
                        }}</BaseButton
                      >
                    </div>
                  </div>
                </div>
              </article>
            </div>
          </section>
        </AdminPageState>
      </AdminListSection>
    </PageFrame>
  </AdminLayout>
</template>

<script setup>
import { computed, defineComponent, h, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import AdminLayout from '@/admin/layout/AdminLayout.vue'
import AdminListSection from '@/admin/components/AdminListSection.vue'
import AdminPageState from '@/admin/components/AdminPageState.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import InlineAlert from '@/components/ui/InlineAlert.vue'
import PageFrame from '@/components/ui/PageFrame.vue'
import StatusBadge from '@/components/ui/StatusBadge.vue'
import { extractErrorMessage } from '@/utils/api'
import objectStorageAdminApi from '@/admin/api/objectStorage'

const { t, locale } = useI18n()
const tenants = ref([])
const tenantId = ref('')
const tasks = ref([])
const loading = ref(true)
const error = ref('')
const statusFilter = ref('')
const actionFilter = ref('')
const expandedId = ref(null)
const detail = ref(null)
const detailLoading = ref(false)
const acting = ref('')
const statuses = [
  'manual_required',
  'failed',
  'pending',
  'running',
  'delivery_ready',
  'succeeded',
  'cancelled'
]
const actions = [
  'first_bucket_and_credential',
  'add_bucket',
  'rotate_credential',
  'release_bucket',
  'suspend_membership',
  'reactivate_membership'
]
const priority = {
  manual_required: 0,
  failed: 1,
  running: 2,
  pending: 3,
  delivery_ready: 4,
  succeeded: 5,
  cancelled: 6
}
const filteredTasks = computed(() =>
  tasks.value
    .filter(
      (item) =>
        (!statusFilter.value || item.status === statusFilter.value) &&
        (!actionFilter.value || item.action_type === actionFilter.value)
    )
    .sort(
      (a, b) =>
        (priority[a.status] ?? 9) - (priority[b.status] ?? 9) ||
        new Date(b.created_at) - new Date(a.created_at)
    )
)
const statusLabel = (value) =>
  t(
    `adminPages.objectStorage.statuses.${value}`,
    value || t('common.emptyValue')
  )
const actionLabel = (value) =>
  t(
    `adminPages.objectStorage.actions.${value}`,
    value || t('common.emptyValue')
  )
const stageLabel = (value) =>
  t(
    `adminPages.objectStorage.stages.${value || 'pending'}`,
    value || t('adminPages.objectStorage.notStarted')
  )
const resultLabel = (value) =>
  t(
    `adminPages.objectStorage.results.${value || 'unknown'}`,
    value || t('common.emptyValue')
  )
const statusBadge = (value) =>
  ({
    manual_required: 'failed',
    failed: 'failed',
    pending: 'pending',
    running: 'processing',
    delivery_ready: 'success',
    succeeded: 'success',
    cancelled: 'disabled'
  })[value] || 'unknown'
const formatDate = (value) =>
  value
    ? new Intl.DateTimeFormat(locale.value, {
        dateStyle: 'medium',
        timeStyle: 'short'
      }).format(new Date(value))
    : t('common.emptyValue')
const InfoCell = defineComponent({
  props: { label: String, value: [String, Number] },
  setup(props) {
    return () =>
      h('div', [
        h('dt', { class: 'text-xs font-medium text-slate-500' }, props.label),
        h(
          'dd',
          { class: 'mt-1 text-sm font-semibold text-slate-900' },
          props.value
        )
      ])
  }
})

async function load() {
  loading.value = true
  error.value = ''
  try {
    tenants.value = await objectStorageAdminApi.listTenants()
    tenantId.value = String(tenants.value[0]?.id || '')
    await loadTasks()
  } catch (err) {
    error.value = extractErrorMessage(
      err,
      t('adminPages.objectStorage.loadFailed')
    )
  } finally {
    loading.value = false
  }
}
async function loadTasks() {
  if (!tenantId.value) return
  loading.value = true
  try {
    tasks.value = await objectStorageAdminApi.listApplications(tenantId.value)
    if (expandedId.value) await loadDetail(expandedId.value)
  } catch (err) {
    error.value = extractErrorMessage(
      err,
      t('adminPages.objectStorage.loadFailed')
    )
  } finally {
    loading.value = false
  }
}
async function loadDetail(id) {
  detailLoading.value = true
  try {
    detail.value = await objectStorageAdminApi.getApplication(id)
  } catch (err) {
    error.value = extractErrorMessage(
      err,
      t('adminPages.objectStorage.loadFailed')
    )
  } finally {
    detailLoading.value = false
  }
}
async function toggleDetail(task) {
  if (expandedId.value === task.id) {
    expandedId.value = null
    detail.value = null
    return
  }
  expandedId.value = task.id
  await loadDetail(task.id)
}
async function act(kind, task) {
  const reason = window.prompt(t('adminPages.objectStorage.reasonPrompt'))
  if (!reason?.trim()) return
  acting.value = kind
  try {
    if (kind === 'retry')
      await objectStorageAdminApi.retryApplication(task.id, reason.trim())
    else await objectStorageAdminApi.resolveApplication(task.id, reason.trim())
    await loadTasks()
  } catch (err) {
    error.value = extractErrorMessage(
      err,
      t('adminPages.objectStorage.actionFailed')
    )
  } finally {
    acting.value = ''
  }
}
const retryTask = (task) => act('retry', task)
const resolveTask = (task) => act('resolve', task)
onMounted(load)
</script>
