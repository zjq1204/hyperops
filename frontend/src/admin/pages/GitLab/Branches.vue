<template>
  <AdminLayout>
    <PageFrame
      variant="soft"
      :eyebrow="t('adminPages.gitlabBranches.eyebrow')"
      :title="t('adminPages.gitlabBranches.title')"
      :subtitle="t('adminPages.gitlabBranches.subtitle')"
    >
      <AdminScopeSection>
        <template #meta>
          <p class="admin-scope-kicker">
            {{ t('adminPages.gitlabBranches.scopeTitle') }}
          </p>
          <h2 class="admin-scope-heading">
            {{
              currentProject?.path ||
              t('adminPages.gitlabBranches.selectProject')
            }}
          </h2>
          <p class="admin-scope-copy">
            {{ t('adminPages.gitlabBranches.scopeHint') }}
          </p>
        </template>
        <template #actions>
          <BaseButton size="sm" @click="openBulkBranchModal">
            {{ t('adminPages.gitlabBranches.bulkOperate') }}
          </BaseButton>
        </template>
        <label class="admin-scope-card">
          <span class="admin-scope-card-label">{{
            t('adminPages.gitlabBranches.selectGroup')
          }}</span>
          <select
            v-model="selectedGroup"
            @change="handleGroupChange"
            class="admin-filter-control"
          >
            <option value="">
              {{ t('adminPages.gitlabBranches.allGroups') }}
            </option>
            <option v-for="group in groups" :key="group.id" :value="group.id">
              {{ group.name }}
            </option>
          </select>
        </label>
        <div class="admin-scope-card">
          <span class="admin-scope-card-label">{{
            t('adminPages.gitlabBranches.resourceLabels')
          }}</span>
          <div v-if="projectLabels.length" class="admin-tag-filter-list mt-3">
            <button
              v-for="label in projectLabels"
              :key="label.id"
              type="button"
              class="admin-tag-filter-chip"
              :class="{ 'is-active': selectedLabelIds.includes(label.id) }"
              @click="toggleLabelFilter(label.id)"
            >
              {{ label.name }}
            </button>
          </div>
          <p v-else class="admin-project-tag-empty">
            {{ t('adminPages.gitlabBranches.noResourceLabels') }}
          </p>
        </div>
        <label class="admin-scope-card">
          <span class="admin-scope-card-label">{{
            t('adminPages.gitlabBranches.selectProject')
          }}</span>
          <select
            v-model="branchProjectFilter"
            @change="handleProjectFilterChange"
            class="admin-filter-control"
          >
            <option value="">
              {{ t('adminPages.gitlabBranches.selectProject') }}
            </option>
            <option v-for="p in projects" :key="p.id" :value="p.id">
              {{ p.name }}
            </option>
          </select>
        </label>
        <div class="admin-scope-summary">
          <div class="admin-scope-stat">
            <span class="admin-scope-stat-label">{{
              t('adminPages.gitlabBranches.branchesTotal')
            }}</span>
            <strong class="admin-scope-stat-value">{{ totalCount }}</strong>
          </div>
          <div class="admin-scope-stat">
            <span class="admin-scope-stat-label">{{
              t('adminPages.gitlabBranches.protectedCount')
            }}</span>
            <strong class="admin-scope-stat-value">{{ protectedCount }}</strong>
          </div>
          <div class="admin-scope-stat">
            <span class="admin-scope-stat-label">{{
              t('adminPages.gitlabBranches.selectedCount')
            }}</span>
            <strong class="admin-scope-stat-value">{{
              selectedBranches.length
            }}</strong>
          </div>
        </div>
      </AdminScopeSection>

      <AdminTable v-if="branches.length">
        <thead>
          <tr>
            <th class="admin-table-head w-12">
              <input
                type="checkbox"
                v-model="selectAllBranches"
                @change="toggleSelectAllBranches"
                class="rounded"
              />
            </th>
            <th class="admin-table-head">
              {{ t('adminPages.gitlabBranches.branchName') }}
            </th>
            <th class="admin-table-head">{{ t('common.project') }}</th>
            <th class="admin-table-head">
              {{ t('adminPages.gitlabBranches.protected') }}
            </th>
            <th class="admin-table-head">
              {{ t('adminPages.gitlabBranches.lastCommit') }}
            </th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="branch in branches"
            :key="branch.id"
            class="admin-table-row"
          >
            <td class="admin-table-cell">
              <input
                type="checkbox"
                v-model="selectedBranches"
                :value="branch.id"
                class="rounded"
              />
            </td>
            <td class="admin-table-cell">
              <div class="branch-name-cell">
                <span>{{ branch.name }}</span>
              </div>
            </td>
            <td class="admin-table-cell font-mono text-sm text-slate-500">
              {{ branch.project_path }}
            </td>
            <td class="admin-table-cell">
              <span
                :class="
                  branch.protected
                    ? 'admin-status-badge admin-status-badge--success'
                    : 'admin-status-badge admin-status-badge--muted'
                "
                >{{ branch.protected ? t('common.yes') : t('common.no') }}</span
              >
            </td>
            <td class="admin-table-cell font-mono text-sm text-slate-500">
              {{ branch.last_commit_date || t('common.emptyValue') }}
            </td>
          </tr>
        </tbody>
      </AdminTable>
      <PaginationBar
        v-if="branches.length"
        variant="admin"
        :current-page="currentPage"
        :page-size="pageSize"
        :total-count="totalCount"
        @update:page-size="handlePageSizeChange"
        @prev="goPrevPage"
        @next="goNextPage"
      />

      <EmptyState
        v-else
        variant="admin"
        :title="t('adminPages.gitlabBranches.emptyTitle')"
        :description="t('adminPages.gitlabBranches.emptySubtitle')"
      />

      <!-- Bulk Branch Modal -->
      <BaseModal
        :show="showBulkBranchModal"
        size="wide"
        :title="t('adminPages.gitlabBranches.bulkOperateTitle')"
        @close="closeBulkBranchModal"
      >
        <div class="admin-bulk-dialog">
          <section class="admin-bulk-operations">
            <button
              v-for="operation in bulkOperations"
              :key="operation.value"
              type="button"
              :class="[
                'admin-bulk-operation',
                bulkBranchForm.operation === operation.value && 'is-active'
              ]"
              @click="bulkBranchForm.operation = operation.value"
            >
              {{ operation.label }}
            </button>
          </section>

          <section class="grid gap-3 md:grid-cols-3">
            <button
              type="button"
              :class="[
                'admin-scope-step-card',
                bulkBranchStep === 1 ? 'is-active' : ''
              ]"
              @click="bulkBranchStep = 1"
            >
              <span class="text-xs font-semibold uppercase tracking-[0.2em]">
                01
              </span>
              <p class="mt-2 text-sm font-semibold">
                {{ t('adminPages.gitlabBranches.stepScopeTitle') }}
              </p>
              <p class="mt-1 text-xs leading-5 opacity-80">
                {{ t('adminPages.gitlabBranches.stepScopeDesc') }}
              </p>
            </button>
            <button
              type="button"
              :disabled="!canGoToBulkProjectsStep"
              :class="[
                'admin-scope-step-card',
                bulkBranchStep === 2 ? 'is-active' : '',
                !canGoToBulkProjectsStep ? 'is-disabled' : ''
              ]"
              @click="goToBulkBranchProjectsStep"
            >
              <span class="text-xs font-semibold uppercase tracking-[0.2em]">
                02
              </span>
              <p class="mt-2 text-sm font-semibold">
                {{ t('adminPages.gitlabBranches.stepProjectsTitle') }}
              </p>
              <p class="mt-1 text-xs leading-5 opacity-80">
                {{ t('adminPages.gitlabBranches.stepProjectsDesc') }}
              </p>
            </button>
            <button
              type="button"
              :disabled="!canGoToBulkComposeStep"
              :class="[
                'admin-scope-step-card',
                bulkBranchStep === 3 ? 'is-active' : '',
                !canGoToBulkComposeStep ? 'is-disabled' : ''
              ]"
              @click="goToBulkBranchComposeStep"
            >
              <span class="text-xs font-semibold uppercase tracking-[0.2em]">
                03
              </span>
              <p class="mt-2 text-sm font-semibold">
                {{ t('adminPages.gitlabBranches.stepComposeTitle') }}
              </p>
              <p class="mt-1 text-xs leading-5 opacity-80">
                {{ t('adminPages.gitlabBranches.stepComposeDesc') }}
              </p>
            </button>
          </section>

          <section
            v-if="bulkBranchStep === 1"
            class="grid gap-5 lg:grid-cols-2"
          >
            <section class="admin-modal-card">
              <header class="admin-bulk-panel-head">
                <div>
                  <h3 class="admin-bulk-title">
                    {{ t('adminPages.gitlabBranches.targetGroups') }}
                  </h3>
                  <p class="admin-bulk-subtitle">
                    {{ t('adminPages.gitlabBranches.targetGroupsHint') }}
                  </p>
                </div>
                <span class="admin-bulk-count"
                  >{{ bulkBranchForm.group_ids.length }}/{{
                    groups.length
                  }}</span
                >
              </header>
              <div class="admin-bulk-choice-box admin-bulk-choice-box--groups">
                <label
                  v-for="group in groups"
                  :key="group.id"
                  :class="[
                    'admin-bulk-choice',
                    'admin-bulk-choice--group',
                    isBulkGroupSelected(group.id) && 'is-selected'
                  ]"
                >
                  <input
                    type="checkbox"
                    :checked="isBulkGroupSelected(group.id)"
                    @change="toggleBulkGroup(group.id)"
                  />
                  <div class="admin-bulk-choice-copy">
                    <span class="admin-bulk-choice-text">{{ group.name }}</span>
                    <span class="admin-bulk-choice-meta">{{
                      t('adminPages.gitlabBranches.groupProjectsPreview')
                    }}</span>
                  </div>
                </label>
              </div>
            </section>

            <section class="admin-modal-card">
              <header class="admin-bulk-panel-head">
                <div>
                  <h3 class="admin-bulk-title">
                    {{ t('adminPages.gitlabBranches.resourceLabels') }}
                  </h3>
                  <p class="admin-bulk-subtitle">
                    {{ t('adminPages.gitlabBranches.resourceLabelsHint') }}
                  </p>
                </div>
                <span class="admin-bulk-count"
                  >{{ bulkSelectedLabelIds.length }}/{{
                    projectLabels.length
                  }}</span
                >
              </header>
              <div v-if="projectLabels.length" class="admin-tag-filter-list">
                <button
                  v-for="label in projectLabels"
                  :key="label.id"
                  type="button"
                  class="admin-tag-filter-chip"
                  :class="{
                    'is-active': bulkSelectedLabelIds.includes(label.id)
                  }"
                  @click="toggleBulkLabelFilter(label.id)"
                >
                  {{ label.name }}
                </button>
              </div>
              <p v-else class="admin-project-tag-empty">
                {{ t('adminPages.gitlabBranches.noResourceLabels') }}
              </p>
            </section>
          </section>

          <section v-else-if="bulkBranchStep === 2" class="admin-modal-card">
            <header class="admin-bulk-panel-head">
              <div>
                <h3 class="admin-bulk-title">
                  {{ t('adminPages.gitlabBranches.targetProjects') }}
                </h3>
                <p class="admin-bulk-subtitle">
                  {{ t('adminPages.gitlabBranches.targetProjectsHint') }}
                </p>
              </div>
              <div class="admin-bulk-panel-actions">
                <span class="admin-bulk-count"
                  >{{ bulkBranchForm.project_ids.length }}/{{
                    bulkProjectOptions.length
                  }}</span
                >
                <button
                  type="button"
                  class="admin-bulk-inline-action"
                  :disabled="!bulkProjectOptions.length"
                  @click="selectAllBulkProjects"
                >
                  {{ t('adminPages.gitlabBranches.selectAllProjects') }}
                </button>
                <span class="admin-bulk-actions-divider">|</span>
                <button
                  type="button"
                  class="admin-bulk-inline-action"
                  :disabled="!bulkBranchForm.project_ids.length"
                  @click="clearBulkProjects"
                >
                  {{ t('adminPages.gitlabBranches.clearProjects') }}
                </button>
              </div>
            </header>
            <div
              v-if="bulkProjectOptions.length"
              class="admin-bulk-project-grid"
            >
              <label
                v-for="project in bulkProjectOptions"
                :key="project.id"
                :class="[
                  'admin-bulk-project-card',
                  selectedBulkProjectSet.has(project.id) && 'is-selected'
                ]"
              >
                <input
                  v-model="bulkBranchForm.project_ids"
                  type="checkbox"
                  :value="project.id"
                />
                <div class="admin-bulk-project-copy">
                  <strong>{{ project.name }}</strong>
                  <span>{{ project.path }}</span>
                </div>
              </label>
            </div>
            <p v-else class="admin-bulk-empty">
              {{
                bulkBranchForm.group_ids.length
                  ? t('adminPages.gitlabBranches.noMatchingProjects')
                  : t('adminPages.gitlabBranches.chooseGroupsFirst')
              }}
            </p>
          </section>

          <section v-else class="flex flex-col gap-5 xl:h-[26rem] xl:flex-row">
            <section
              class="admin-modal-card flex min-h-0 h-full flex-col overflow-hidden xl:w-[37%] xl:max-w-[25rem]"
            >
              <div
                class="admin-bulk-selected-shell admin-bulk-selected-shell--fill"
              >
                <div class="admin-bulk-selected-head">
                  <h3 class="admin-bulk-title">
                    {{
                      t('adminPages.gitlabBranches.selectedProjectsCount', {
                        count: selectedBulkProjects.length
                      })
                    }}
                  </h3>
                  <button
                    type="button"
                    class="admin-bulk-inline-action"
                    :disabled="!selectedBulkProjects.length"
                    @click="clearBulkProjects"
                  >
                    {{ t('adminPages.gitlabBranches.clearProjects') }}
                  </button>
                </div>
                <div
                  v-if="selectedBulkProjects.length"
                  class="admin-bulk-selected-grid admin-bulk-selected-grid--fill"
                >
                  <button
                    v-for="project in selectedBulkProjects"
                    :key="project.id"
                    type="button"
                    class="admin-bulk-selected-chip"
                    @click="removeBulkProject(project.id)"
                  >
                    <span>{{ project.path }}</span>
                    <span aria-hidden="true">×</span>
                  </button>
                </div>
                <p
                  v-else
                  class="admin-bulk-selected-empty admin-bulk-selected-empty--inline"
                >
                  {{
                    t('adminPages.gitlabBranches.selectedProjectsEmptyInline')
                  }}
                </p>
              </div>
            </section>

            <section
              class="admin-modal-card flex min-h-0 h-full min-w-0 flex-1 flex-col space-y-5"
            >
              <header
                class="flex flex-col gap-4 border-b border-slate-200 pb-4 lg:flex-row lg:items-start lg:justify-between"
              >
                <div class="space-y-1">
                  <h3 class="admin-bulk-title">
                    {{ t('adminPages.gitlabBranches.stepComposeTitle') }}
                  </h3>
                  <p class="text-sm text-slate-500">
                    {{ t('adminPages.gitlabBranches.stepComposeDesc') }}
                  </p>
                </div>
                <div class="admin-scope-preview-card">
                  {{
                    t('adminPages.gitlabBranches.bulkPreview', {
                      operation: bulkOperationLabel,
                      projects: bulkBranchForm.project_ids.length,
                      branches: parsedBulkBranchNames.length
                    })
                  }}
                </div>
              </header>

              <section
                class="grid gap-4"
                :class="
                  bulkBranchForm.operation === 'create'
                    ? 'lg:grid-cols-[220px_minmax(0,1fr)]'
                    : 'grid-cols-1'
                "
              >
                <div
                  v-if="bulkBranchForm.operation === 'create'"
                  class="space-y-2"
                >
                  <label class="admin-bulk-input-label">{{
                    t('adminPages.gitlabBranches.sourceRef')
                  }}</label>
                  <input
                    v-model="bulkBranchForm.ref"
                    type="text"
                    :placeholder="
                      t('adminPages.gitlabBranches.sourceRefPlaceholder')
                    "
                    class="admin-modal-control"
                  />
                  <p class="text-xs leading-5 text-slate-500">
                    {{ t('adminPages.gitlabBranches.sourceRefHint') }}
                  </p>
                </div>

                <div class="space-y-2">
                  <label class="admin-bulk-input-label">{{
                    branchNamesLabel
                  }}</label>
                  <textarea
                    v-model="bulkBranchForm.branch_names"
                    rows="8"
                    :placeholder="
                      t('adminPages.gitlabBranches.branchNamesPlaceholder')
                    "
                    class="admin-modal-control admin-bulk-textarea min-h-[220px] font-mono"
                  ></textarea>
                </div>
              </section>
            </section>
          </section>
        </div>
        <template #footer>
          <div class="flex w-full justify-end gap-3">
            <BaseButton variant="secondary" @click="closeBulkBranchModal">{{
              t('common.cancel')
            }}</BaseButton>
            <BaseButton
              v-if="bulkBranchStep > 1"
              variant="secondary"
              @click="goToPrevBulkBranchStep"
            >
              {{ t('common.previous') }}
            </BaseButton>
            <BaseButton
              v-if="bulkBranchStep < 3"
              :disabled="
                bulkBranchStep === 1
                  ? !canGoToBulkProjectsStep
                  : !canGoToBulkComposeStep
              "
              @click="goToNextBulkBranchStep"
            >
              {{ t('common.next') }}
            </BaseButton>
            <BaseButton v-else @click="submitBulkBranches">{{
              bulkSubmitLabel
            }}</BaseButton>
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

      <!-- Toast -->
      <div
        v-if="toast.show"
        :class="[
          'admin-toast',
          toast.type === 'success'
            ? 'admin-toast--success'
            : 'admin-toast--error'
        ]"
      >
        {{ toast.message }}
      </div>
    </PageFrame>
  </AdminLayout>
</template>

<script setup>
import { computed, ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import AdminScopeSection from '@/admin/components/AdminScopeSection.vue'
import AdminTable from '@/admin/components/AdminTable.vue'
import AdminLayout from '@/admin/layout/AdminLayout.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseModal from '@/components/ui/BaseModal.vue'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import PageFrame from '@/components/ui/PageFrame.vue'
import PaginationBar from '@/components/ui/PaginationBar.vue'
import { useConfirmDialog } from '@/composables/useConfirmDialog'
import gitlabApi from '@/api/gitlab'

const { t } = useI18n()
const {
  confirmDialog,
  requestConfirm,
  closeConfirmDialog,
  runConfirmedAction
} = useConfirmDialog()

const groups = ref([])
const projects = ref([])
const branches = ref([])
const selectedBranches = ref([])
const selectAllBranches = ref(false)
const selectedGroup = ref('')
const branchProjectFilter = ref('')
const selectedLabelIds = ref([])
const projectLabels = ref([])
const showBulkBranchModal = ref(false)
const bulkProjectOptions = ref([])
const bulkSelectedLabelIds = ref([])
const bulkBranchStep = ref(1)
const bulkBranchForm = ref({
  operation: 'create',
  group_ids: [],
  project_ids: [],
  ref: 'main',
  branch_names: ''
})
const currentPage = ref(1)
const pageSize = ref(20)
const totalCount = ref(0)

const toast = ref({ show: false, message: '', type: 'success' })

const currentProject = computed(() =>
  projects.value.find(
    (project) => String(project.id) === String(branchProjectFilter.value)
  )
)

const protectedCount = computed(
  () => branches.value.filter((branch) => branch.protected).length
)

const parsedBulkBranchNames = computed(() =>
  bulkBranchForm.value.branch_names
    .split('\n')
    .map((name) => name.trim())
    .filter(Boolean)
)

const canGoToBulkProjectsStep = computed(
  () => bulkBranchForm.value.group_ids.length > 0
)

const canGoToBulkComposeStep = computed(
  () => bulkBranchForm.value.project_ids.length > 0
)

const bulkOperations = computed(() => [
  { value: 'create', label: t('adminPages.gitlabBranches.operationCreate') },
  { value: 'delete', label: t('adminPages.gitlabBranches.operationDelete') },
  { value: 'protect', label: t('adminPages.gitlabBranches.operationProtect') },
  {
    value: 'unprotect',
    label: t('adminPages.gitlabBranches.operationUnprotect')
  }
])

const bulkOperationLabel = computed(
  () =>
    bulkOperations.value.find(
      (operation) => operation.value === bulkBranchForm.value.operation
    )?.label || ''
)

const branchNamesLabel = computed(() =>
  bulkBranchForm.value.operation === 'create'
    ? t('adminPages.gitlabBranches.newBranchNames')
    : t('adminPages.gitlabBranches.targetBranchNames')
)

const bulkSubmitLabel = computed(() => {
  const labels = {
    create: t('adminPages.gitlabBranches.executeCreate'),
    delete: t('adminPages.gitlabBranches.executeDelete'),
    protect: t('adminPages.gitlabBranches.executeProtect'),
    unprotect: t('adminPages.gitlabBranches.executeUnprotect')
  }
  return (
    labels[bulkBranchForm.value.operation] ||
    t('adminPages.gitlabBranches.execute')
  )
})

const selectedBulkProjectSet = computed(
  () => new Set(bulkBranchForm.value.project_ids)
)

const selectedBulkProjects = computed(() =>
  bulkProjectOptions.value.filter((project) =>
    selectedBulkProjectSet.value.has(project.id)
  )
)

function showToast(message, type = 'success') {
  toast.value = { show: true, message, type }
  setTimeout(() => {
    toast.value.show = false
  }, 3000)
}

function normalizeCollection(data) {
  return Array.isArray(data) ? data : (data?.results ?? [])
}

async function loadProjectLabels() {
  try {
    const data = await gitlabApi.listProjectLabels({ page_size: 1000 })
    projectLabels.value = normalizeCollection(data)
  } catch (e) {
    projectLabels.value = []
    showToast(
      t('adminPages.gitlabBranches.toast.loadLabelsFailed', {
        message: e.message
      }),
      'error'
    )
  }
}

async function loadGroups() {
  try {
    groups.value = await gitlabApi.listGroups()
  } catch (e) {
    groups.value = []
    selectedGroup.value = ''
    showToast(
      t('adminPages.gitlabBranches.toast.loadGroupsFailed', {
        message: e.message
      }),
      'error'
    )
  }
}

async function loadProjects() {
  try {
    const data = await gitlabApi.listProjectsPage({
      group: selectedGroup.value,
      page: 1,
      page_size: 10000,
      label_ids: selectedLabelIds.value.join(',')
    })
    projects.value = Array.isArray(data) ? data : (data?.results ?? [])
    if (
      !projects.value.some(
        (project) => String(project.id) === String(branchProjectFilter.value)
      )
    ) {
      branchProjectFilter.value = projects.value.length
        ? String(projects.value[0].id)
        : ''
    }
  } catch (e) {
    projects.value = []
    branchProjectFilter.value = ''
    showToast(
      t('adminPages.gitlabBranches.toast.loadProjectsFailed', {
        message: e.message
      }),
      'error'
    )
  }
}

async function loadBranches() {
  if (!branchProjectFilter.value) {
    branches.value = []
    totalCount.value = 0
    selectedBranches.value = []
    selectAllBranches.value = false
    return
  }
  try {
    const params = {
      page: currentPage.value,
      page_size: pageSize.value,
      project_id: branchProjectFilter.value
    }
    const data = await gitlabApi.listBranchesPage(params)
    branches.value = Array.isArray(data) ? data : (data?.results ?? [])
    totalCount.value = Array.isArray(data)
      ? data.length
      : Number(data?.count ?? branches.value.length)
    selectedBranches.value = []
    selectAllBranches.value = false
  } catch (e) {
    branches.value = []
    totalCount.value = 0
    showToast(
      t('adminPages.gitlabBranches.toast.loadBranchesFailed', {
        message: e.message
      }),
      'error'
    )
  }
}

async function handleGroupChange() {
  currentPage.value = 1
  branchProjectFilter.value = ''
  branches.value = []
  totalCount.value = 0
  await loadProjects()
  await loadBranches()
}

async function toggleLabelFilter(labelId) {
  const normalizedId = Number(labelId)
  if (selectedLabelIds.value.includes(normalizedId)) {
    selectedLabelIds.value = selectedLabelIds.value.filter(
      (id) => id !== normalizedId
    )
  } else {
    selectedLabelIds.value = [...selectedLabelIds.value, normalizedId]
  }
  currentPage.value = 1
  branchProjectFilter.value = ''
  await loadProjects()
  await loadBranches()
}

function handleProjectFilterChange() {
  currentPage.value = 1
  loadBranches()
}

function handlePageSizeChange(size) {
  pageSize.value = size
  currentPage.value = 1
  loadBranches()
}

function goPrevPage() {
  if (currentPage.value <= 1) return
  currentPage.value -= 1
  loadBranches()
}

function goNextPage() {
  if (currentPage.value * pageSize.value >= totalCount.value) return
  currentPage.value += 1
  loadBranches()
}

function toggleSelectAllBranches() {
  if (selectAllBranches.value) {
    selectedBranches.value = branches.value.map((b) => b.id)
  } else {
    selectedBranches.value = []
  }
}

function openBulkBranchModal() {
  bulkBranchStep.value = 1
  bulkSelectedLabelIds.value = [...selectedLabelIds.value]
  bulkBranchForm.value = {
    operation: 'create',
    group_ids: selectedGroup.value ? [Number(selectedGroup.value)] : [],
    project_ids: branchProjectFilter.value
      ? [Number(branchProjectFilter.value)]
      : [],
    ref: 'main',
    branch_names: ''
  }
  bulkProjectOptions.value = [...projects.value]
  showBulkBranchModal.value = true
}

function closeBulkBranchModal() {
  showBulkBranchModal.value = false
  bulkBranchStep.value = 1
  bulkSelectedLabelIds.value = []
}

function goToBulkBranchProjectsStep() {
  if (!canGoToBulkProjectsStep.value) return
  bulkBranchStep.value = 2
}

function goToBulkBranchComposeStep() {
  if (!canGoToBulkComposeStep.value) return
  bulkBranchStep.value = 3
}

function goToPrevBulkBranchStep() {
  bulkBranchStep.value = Math.max(1, bulkBranchStep.value - 1)
}

function goToNextBulkBranchStep() {
  if (bulkBranchStep.value === 1) {
    goToBulkBranchProjectsStep()
    return
  }
  if (bulkBranchStep.value === 2) {
    goToBulkBranchComposeStep()
  }
}

function isBulkGroupSelected(groupId) {
  return bulkBranchForm.value.group_ids.includes(Number(groupId))
}

async function toggleBulkGroup(groupId) {
  const normalizedGroupId = Number(groupId)
  const selected = bulkBranchForm.value.group_ids
  if (selected.includes(normalizedGroupId)) {
    bulkBranchForm.value.group_ids = selected.filter(
      (id) => id !== normalizedGroupId
    )
  } else {
    bulkBranchForm.value.group_ids = [...selected, normalizedGroupId]
  }
  await loadBulkProjectOptions()
}

async function toggleBulkLabelFilter(labelId) {
  const normalizedId = Number(labelId)
  if (bulkSelectedLabelIds.value.includes(normalizedId)) {
    bulkSelectedLabelIds.value = bulkSelectedLabelIds.value.filter(
      (id) => id !== normalizedId
    )
  } else {
    bulkSelectedLabelIds.value = [...bulkSelectedLabelIds.value, normalizedId]
  }
  await loadBulkProjectOptions()
}

function selectAllBulkProjects() {
  bulkBranchForm.value.project_ids = bulkProjectOptions.value.map(
    (project) => project.id
  )
}

function clearBulkProjects() {
  bulkBranchForm.value.project_ids = []
}

function removeBulkProject(projectId) {
  bulkBranchForm.value.project_ids = bulkBranchForm.value.project_ids.filter(
    (id) => id !== projectId
  )
}

async function loadBulkProjectOptions() {
  const groupIds = bulkBranchForm.value.group_ids
  if (!groupIds.length) {
    bulkProjectOptions.value = []
    bulkBranchForm.value.project_ids = []
    return
  }

  try {
    const projectPages = await Promise.all(
      groupIds.map((groupId) =>
        gitlabApi.listProjectsPage({
          group: groupId,
          page: 1,
          page_size: 10000,
          label_ids: bulkSelectedLabelIds.value.join(',')
        })
      )
    )
    const mergedProjects = []
    const seen = new Set()
    projectPages
      .flatMap((data) => (Array.isArray(data) ? data : (data?.results ?? [])))
      .forEach((project) => {
        if (!seen.has(project.id)) {
          seen.add(project.id)
          mergedProjects.push(project)
        }
      })
    bulkProjectOptions.value = mergedProjects
    bulkBranchForm.value.project_ids = bulkBranchForm.value.project_ids.filter(
      (projectId) => seen.has(projectId)
    )
  } catch (e) {
    bulkProjectOptions.value = []
    bulkBranchForm.value.project_ids = []
    showToast(
      t('adminPages.gitlabBranches.toast.loadProjectsFailed', {
        message: e.message
      }),
      'error'
    )
  }
}

async function executeBulkBranches(names) {
  try {
    const result = await gitlabApi.bulkApplyBranches({
      operation: bulkBranchForm.value.operation,
      project_ids: bulkBranchForm.value.project_ids,
      ref: bulkBranchForm.value.ref,
      branch_names: names
    })
    showToast(
      t('adminPages.gitlabBranches.toast.bulkApplyResult', {
        succeeded: result.success_count,
        failed: result.error_count
      })
    )
    showBulkBranchModal.value = false
    loadBranches()
  } catch (e) {
    showToast(
      t('adminPages.gitlabBranches.toast.bulkApplyFailed', {
        message: e.message
      }),
      'error'
    )
  }
}

async function submitBulkBranches() {
  if (!bulkBranchForm.value.project_ids.length) {
    showToast(t('adminPages.gitlabBranches.selectProjectError'), 'error')
    return
  }
  const names = parsedBulkBranchNames.value
  if (names.length === 0) {
    showToast(t('adminPages.gitlabBranches.inputBranchNamesError'), 'error')
    return
  }

  if (bulkBranchForm.value.operation === 'delete') {
    requestConfirm({
      title: t('common.delete'),
      message: t('adminPages.gitlabBranches.deleteByNameConfirm', {
        projects: bulkBranchForm.value.project_ids.length,
        branches: names.length
      }),
      confirmText: t('common.delete'),
      onConfirm: () => executeBulkBranches(names)
    })
    return
  }

  await executeBulkBranches(names)
}

onMounted(async () => {
  await loadProjectLabels()
  await loadGroups()
  await loadProjects()
  await loadBranches()
})
</script>
