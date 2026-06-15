<template>
  <AdminLayout>
    <PageFrame
      variant="soft"
      :eyebrow="t('adminPages.gitlabProjects.eyebrow')"
      :title="t('adminPages.gitlabProjects.title')"
      :subtitle="t('adminPages.gitlabProjects.subtitle')"
    >
      <template #actions>
        <BaseButton variant="secondary" @click="openLabelLibraryModal">
          {{ t('adminPages.gitlabProjects.manageLabels') }}
        </BaseButton>
        <BaseButton
          v-if="canBulkAssignToCurrentLabel"
          variant="secondary"
          @click="openBulkAssignModal"
        >
          {{ t('adminPages.gitlabProjects.bulkAssignAction') }}
        </BaseButton>
        <BaseButton
          variant="secondary"
          :disabled="totalCount === 0"
          @click="openBulkCollectModal"
        >
          {{ t('adminPages.gitlabProjects.bulkCollectAction') }}
        </BaseButton>
      </template>

      <AdminListSection>
        <template #filters>
          <div class="admin-filter-grid">
            <div class="admin-filter-field">
              <label class="admin-filter-label">
                {{ t('adminPages.gitlabProjects.groupFilterTitle') }}
              </label>
              <select
                v-model="selectedGroup"
                class="admin-filter-control min-w-[22rem] max-w-xl"
                @change="handleGroupChange"
              >
                <option value="">
                  {{ t('adminPages.gitlabProjects.allGroups') }}
                </option>
                <option
                  v-for="group in groups"
                  :key="group.id"
                  :value="group.id"
                >
                  {{ group.name }}
                </option>
              </select>
            </div>
            <div class="admin-filter-field lg:col-span-2">
              <label class="admin-filter-label">
                {{ t('adminPages.gitlabProjects.resourceLabels') }}
              </label>
              <div
                v-if="projectLabels.length"
                class="admin-tag-filter-list mt-3"
              >
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
                {{ t('adminPages.gitlabProjects.noResourceLabels') }}
              </p>
            </div>
          </div>
          <div class="admin-toolbar-end">
            <span class="admin-summary-pill">
              {{
                t('adminPages.gitlabProjects.summaryCount', {
                  count: totalCount
                })
              }}
            </span>
          </div>
        </template>

        <AdminTable v-if="projects.length">
          <thead>
            <tr>
              <th class="admin-table-head">{{ t('common.name') }}</th>
              <th class="admin-table-head">{{ t('common.path') }}</th>
              <th class="admin-table-head">
                {{ t('adminPages.gitlabProjects.defaultBranch') }}
              </th>
              <th class="admin-table-head">
                {{ t('adminPages.gitlabProjects.resourceLabels') }}
              </th>
              <th class="admin-table-head">
                {{ t('adminPages.gitlabProjects.collectedAt') }}
              </th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="project in projects"
              :key="project.id"
              class="admin-table-row"
            >
              <td class="admin-table-cell">
                <div class="font-semibold text-slate-900">
                  {{ project.name }}
                </div>
              </td>
              <td class="admin-table-cell font-mono text-sm text-slate-500">
                {{ project.path }}
              </td>
              <td class="admin-table-cell font-mono text-sm text-slate-600">
                {{ project.default_branch }}
              </td>
              <td class="admin-table-cell">
                <div
                  v-if="project.labels?.length"
                  class="admin-project-tag-list"
                >
                  <span
                    v-for="label in project.labels"
                    :key="label.id"
                    class="admin-project-tag-chip"
                  >
                    {{ label.name }}
                  </span>
                </div>
                <span v-else class="admin-project-tag-empty">
                  {{ t('adminPages.gitlabProjects.noLabels') }}
                </span>
              </td>
              <td class="admin-table-cell text-sm text-slate-500">
                {{ project.collected_at || '-' }}
              </td>
            </tr>
          </tbody>
        </AdminTable>
        <PaginationBar
          v-if="projects.length"
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
          :title="t('adminPages.gitlabProjects.emptyTitle')"
          :description="t('adminPages.gitlabProjects.emptySubtitle')"
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
                d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z"
              />
            </svg>
          </template>
        </EmptyState>
      </AdminListSection>

      <BaseModal
        :show="showLabelLibraryModal"
        :title="t('adminPages.gitlabProjects.labelLibraryTitle')"
        @close="closeLabelLibraryModal"
      >
        <div class="admin-modal-stack">
          <section class="admin-modal-card">
            <label class="admin-bulk-input-label">
              {{ t('adminPages.gitlabProjects.labelName') }}
            </label>
            <div class="flex gap-3">
              <input
                v-model="labelDraft.name"
                type="text"
                class="input flex-1"
                :placeholder="
                  t('adminPages.gitlabProjects.labelNamePlaceholder')
                "
              />
              <BaseButton @click="saveProjectLabel">
                {{
                  editingLabel
                    ? t('common.save')
                    : t('adminPages.gitlabProjects.createLabel')
                }}
              </BaseButton>
            </div>
            <p class="admin-bulk-input-hint">
              {{ t('adminPages.gitlabProjects.labelLibraryHint') }}
            </p>
          </section>

          <section class="admin-modal-card">
            <div class="section-heading settings-section-heading-compact">
              <div>
                <h3 class="section-title">
                  {{ t('adminPages.gitlabProjects.labelLibraryListTitle') }}
                </h3>
                <p class="section-copy">
                  {{ t('adminPages.gitlabProjects.labelLibraryListHint') }}
                </p>
              </div>
            </div>

            <div v-if="projectLabels.length" class="space-y-3">
              <div
                v-for="label in projectLabels"
                :key="label.id"
                class="admin-label-library-item"
              >
                <div class="min-w-0">
                  <div class="admin-project-tag-list">
                    <span class="admin-project-tag-chip">{{ label.name }}</span>
                  </div>
                  <p class="mt-2 text-xs text-slate-500">
                    {{
                      t('adminPages.gitlabProjects.labelUsageCount', {
                        count: label.project_count
                      })
                    }}
                  </p>
                </div>
                <div class="flex flex-wrap gap-3 text-sm font-semibold">
                  <button
                    class="text-sky-700 hover:text-sky-900"
                    @click="startEditProjectLabel(label)"
                  >
                    {{ t('common.edit') }}
                  </button>
                  <button
                    class="text-rose-700 hover:text-rose-900"
                    @click="deleteProjectLabel(label)"
                  >
                    {{ t('common.delete') }}
                  </button>
                </div>
              </div>
            </div>
            <p v-else class="admin-project-tag-empty">
              {{ t('adminPages.gitlabProjects.noLabelLibraryData') }}
            </p>
          </section>
        </div>
        <template #footer>
          <div class="flex w-full justify-end gap-3">
            <BaseButton variant="secondary" @click="closeLabelLibraryModal">{{
              t('common.close')
            }}</BaseButton>
          </div>
        </template>
      </BaseModal>

      <BaseModal
        :show="showProjectLabelsModal"
        :title="
          t('adminPages.gitlabProjects.editProjectLabelsTitle', {
            name: editingProject?.name || ''
          })
        "
        @close="closeProjectLabelsModal"
      >
        <div class="admin-modal-stack">
          <section class="admin-modal-card">
            <p class="admin-bulk-input-hint">
              {{ t('adminPages.gitlabProjects.projectLabelBindingHint') }}
            </p>
            <div v-if="projectLabels.length" class="admin-tag-filter-list mt-4">
              <label
                v-for="label in projectLabels"
                :key="label.id"
                class="admin-tag-filter-chip"
                :class="{
                  'is-active': selectedProjectLabelIds.includes(label.id)
                }"
              >
                <input
                  v-model="selectedProjectLabelIds"
                  type="checkbox"
                  :value="label.id"
                  class="sr-only"
                />
                <span>{{ label.name }}</span>
              </label>
            </div>
            <p v-else class="admin-project-tag-empty">
              {{ t('adminPages.gitlabProjects.noLabelLibraryData') }}
            </p>
          </section>
        </div>
        <template #footer>
          <div class="flex w-full justify-end gap-3">
            <BaseButton variant="secondary" @click="closeProjectLabelsModal">{{
              t('common.cancel')
            }}</BaseButton>
            <BaseButton @click="saveProjectLabels">{{
              t('common.save')
            }}</BaseButton>
          </div>
        </template>
      </BaseModal>

      <BaseModal
        :show="showBulkAssignModal"
        :title="
          t('adminPages.gitlabProjects.bulkAssignTitle', {
            name: selectedBulkLabel?.name || ''
          })
        "
        @close="closeBulkAssignModal"
      >
        <div class="admin-modal-stack">
          <section class="admin-modal-card">
            <div class="admin-bulk-summary-metrics">
              <div class="admin-bulk-summary-metric">
                <span>{{
                  t('adminPages.gitlabProjects.bulkAssignTargetLabel')
                }}</span>
                <strong>{{ selectedBulkLabel?.name || '—' }}</strong>
              </div>
              <div class="admin-bulk-summary-metric">
                <span>{{
                  t('adminPages.gitlabProjects.bulkAssignScope')
                }}</span>
                <strong>{{ bulkAssignScopeLabel }}</strong>
              </div>
              <div class="admin-bulk-summary-metric">
                <span>{{
                  t('adminPages.gitlabProjects.bulkAssignAlreadyTagged')
                }}</span>
                <strong>{{ bulkAlreadyTaggedCount }}</strong>
              </div>
            </div>
            <p class="admin-bulk-input-hint">
              {{ t('adminPages.gitlabProjects.bulkAssignHint') }}
            </p>
          </section>

          <section class="admin-modal-card">
            <div
              class="flex flex-col gap-3 md:flex-row md:items-center md:justify-between"
            >
              <div class="min-w-0 flex-1">
                <label class="admin-bulk-input-label">
                  {{ t('adminPages.gitlabProjects.bulkAssignAvailableTitle') }}
                </label>
                <p class="admin-bulk-input-hint">
                  {{ t('adminPages.gitlabProjects.bulkAssignAvailableHint') }}
                </p>
              </div>
              <div class="flex shrink-0 items-center gap-3">
                <span class="admin-bulk-count">
                  {{ bulkSelectedProjectIds.length }}/{{
                    filteredBulkAssignableProjects.length
                  }}
                </span>
                <button
                  type="button"
                  class="admin-bulk-inline-action"
                  :disabled="!filteredBulkAssignableProjects.length"
                  @click="selectAllBulkAssignableProjects"
                >
                  {{ t('adminPages.gitlabProjects.bulkAssignSelectAll') }}
                </button>
                <span class="admin-bulk-actions-divider">|</span>
                <button
                  type="button"
                  class="admin-bulk-inline-action"
                  :disabled="!bulkSelectedProjectIds.length"
                  @click="clearBulkAssignSelection"
                >
                  {{ t('adminPages.gitlabProjects.bulkAssignClear') }}
                </button>
              </div>
            </div>

            <input
              v-model="bulkAssignSearch"
              type="text"
              class="input mt-4"
              :placeholder="
                t('adminPages.gitlabProjects.bulkAssignSearchPlaceholder')
              "
            />

            <div
              v-if="!bulkAssignLoading && filteredBulkAssignableProjects.length"
              class="admin-bulk-project-grid mt-4"
            >
              <label
                v-for="project in filteredBulkAssignableProjects"
                :key="project.id"
                :class="[
                  'admin-bulk-project-card',
                  selectedBulkProjectSet.has(project.id) && 'is-selected'
                ]"
              >
                <input
                  v-model="bulkSelectedProjectIds"
                  type="checkbox"
                  :value="project.id"
                />
                <div class="admin-bulk-project-copy">
                  <strong>{{ project.name }}</strong>
                  <span>{{ project.path }}</span>
                </div>
              </label>
            </div>
            <p v-else-if="bulkAssignLoading" class="admin-bulk-empty mt-4">
              {{ t('common.loading') }}
            </p>
            <p v-else class="admin-bulk-empty mt-4">
              {{ t('adminPages.gitlabProjects.bulkAssignEmpty') }}
            </p>
          </section>
        </div>
        <template #footer>
          <div class="flex w-full justify-end gap-3">
            <BaseButton variant="secondary" @click="closeBulkAssignModal">{{
              t('common.cancel')
            }}</BaseButton>
            <BaseButton
              :loading="bulkAssignSaving"
              :disabled="!bulkSelectedProjectIds.length"
              @click="saveBulkAssign"
            >
              {{ t('adminPages.gitlabProjects.bulkAssignConfirm') }}
            </BaseButton>
          </div>
        </template>
      </BaseModal>

      <BaseModal
        :show="showBulkCollectModal"
        :title="t('adminPages.gitlabProjects.bulkCollectTitle')"
        @close="closeBulkCollectModal"
      >
        <div class="admin-modal-stack">
          <section class="admin-modal-card">
            <div class="admin-bulk-summary-metrics">
              <div class="admin-bulk-summary-metric">
                <span>{{
                  t('adminPages.gitlabProjects.bulkCollectScope')
                }}</span>
                <strong>{{ bulkCollectScopeLabel }}</strong>
              </div>
              <div class="admin-bulk-summary-metric">
                <span>{{
                  t('adminPages.gitlabProjects.bulkCollectSelected')
                }}</span>
                <strong>{{ bulkCollectSelectedProjectIds.length }}</strong>
              </div>
            </div>
            <p class="admin-bulk-input-hint">
              {{ t('adminPages.gitlabProjects.bulkCollectHint') }}
            </p>
          </section>

          <section class="admin-modal-card">
            <div
              class="flex flex-col gap-3 md:flex-row md:items-center md:justify-between"
            >
              <div class="min-w-0 flex-1">
                <label class="admin-bulk-input-label">
                  {{ t('adminPages.gitlabProjects.bulkCollectAvailableTitle') }}
                </label>
                <p class="admin-bulk-input-hint">
                  {{ t('adminPages.gitlabProjects.bulkCollectAvailableHint') }}
                </p>
              </div>
              <div class="flex shrink-0 items-center gap-3">
                <span class="admin-bulk-count">
                  {{ bulkCollectSelectedProjectIds.length }}/{{
                    filteredBulkCollectProjects.length
                  }}
                </span>
                <button
                  type="button"
                  class="admin-bulk-inline-action"
                  :disabled="!filteredBulkCollectProjects.length"
                  @click="selectAllBulkCollectProjects"
                >
                  {{ t('adminPages.gitlabProjects.bulkAssignSelectAll') }}
                </button>
                <span class="admin-bulk-actions-divider">|</span>
                <button
                  type="button"
                  class="admin-bulk-inline-action"
                  :disabled="!bulkCollectSelectedProjectIds.length"
                  @click="clearBulkCollectSelection"
                >
                  {{ t('adminPages.gitlabProjects.bulkAssignClear') }}
                </button>
              </div>
            </div>

            <input
              v-model="bulkCollectSearch"
              type="text"
              class="input mt-4"
              :placeholder="
                t('adminPages.gitlabProjects.bulkAssignSearchPlaceholder')
              "
            />

            <div
              v-if="!bulkCollectLoading && filteredBulkCollectProjects.length"
              class="admin-bulk-project-grid mt-4"
            >
              <label
                v-for="project in filteredBulkCollectProjects"
                :key="project.id"
                :class="[
                  'admin-bulk-project-card',
                  selectedBulkCollectProjectSet.has(project.id) && 'is-selected'
                ]"
              >
                <input
                  v-model="bulkCollectSelectedProjectIds"
                  type="checkbox"
                  :value="project.id"
                />
                <div class="admin-bulk-project-copy">
                  <strong>{{ project.name }}</strong>
                  <span>{{ project.path }}</span>
                </div>
              </label>
            </div>
            <p v-else-if="bulkCollectLoading" class="admin-bulk-empty mt-4">
              {{ t('common.loading') }}
            </p>
            <p v-else class="admin-bulk-empty mt-4">
              {{ t('adminPages.gitlabProjects.bulkCollectEmpty') }}
            </p>
          </section>
        </div>
        <template #footer>
          <div class="flex w-full justify-end gap-3">
            <BaseButton variant="secondary" @click="closeBulkCollectModal">{{
              t('common.cancel')
            }}</BaseButton>
            <BaseButton
              :loading="bulkCollectSaving"
              :disabled="!bulkCollectSelectedProjectIds.length"
              @click="saveBulkCollect"
            >
              {{ t('adminPages.gitlabProjects.bulkCollectConfirm') }}
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

      <!-- Toast -->
      <div
        v-if="toast.show"
        :class="[
          'fixed bottom-4 right-4 px-4 py-2 rounded-md text-white',
          toast.type === 'success' ? 'bg-green-600' : 'bg-red-600'
        ]"
      >
        {{ toast.message }}
      </div>
    </PageFrame>
  </AdminLayout>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import AdminListSection from '@/admin/components/AdminListSection.vue'
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
const selectedGroup = ref('')
const selectedLabelIds = ref([])
const currentPage = ref(1)
const pageSize = ref(20)
const totalCount = ref(0)
const projectLabels = ref([])
const toast = ref({ show: false, message: '', type: 'success' })
const showLabelLibraryModal = ref(false)
const showProjectLabelsModal = ref(false)
const showBulkAssignModal = ref(false)
const showBulkCollectModal = ref(false)
const bulkAssignLoading = ref(false)
const bulkAssignSaving = ref(false)
const bulkCollectLoading = ref(false)
const bulkCollectSaving = ref(false)
const editingProject = ref(null)
const editingLabel = ref(null)
const selectedProjectLabelIds = ref([])
const bulkScopeProjects = ref([])
const bulkSelectedProjectIds = ref([])
const bulkAssignSearch = ref('')
const bulkCollectProjects = ref([])
const bulkCollectSelectedProjectIds = ref([])
const bulkCollectSearch = ref('')
const labelDraft = ref({ name: '' })

const selectedBulkLabel = computed(() => {
  if (selectedLabelIds.value.length !== 1) return null
  return (
    projectLabels.value.find(
      (label) => label.id === Number(selectedLabelIds.value[0])
    ) || null
  )
})

const canBulkAssignToCurrentLabel = computed(
  () => selectedLabelIds.value.length === 1 && Boolean(selectedBulkLabel.value)
)

const bulkAssignScopeLabel = computed(() => {
  if (!selectedGroup.value) {
    return t('adminPages.gitlabProjects.allGroups')
  }

  const matchedGroup = groups.value.find(
    (group) => String(group.id) === String(selectedGroup.value)
  )
  return matchedGroup?.name || t('adminPages.gitlabProjects.allGroups')
})

const selectedLabelNames = computed(() =>
  selectedLabelIds.value
    .map((labelId) =>
      projectLabels.value.find((label) => label.id === Number(labelId))
    )
    .filter(Boolean)
    .map((label) => label.name)
)

const bulkCollectScopeLabel = computed(() => {
  const scopeParts = [bulkAssignScopeLabel.value]
  if (selectedLabelNames.value.length) {
    scopeParts.push(selectedLabelNames.value.join(' / '))
  }
  return scopeParts.join(' · ')
})

const bulkAlreadyTaggedCount = computed(() => {
  const targetLabelId = selectedBulkLabel.value?.id
  if (!targetLabelId) return 0

  return bulkScopeProjects.value.filter((project) =>
    (project.labels || []).some((label) => label.id === targetLabelId)
  ).length
})

const filteredBulkAssignableProjects = computed(() => {
  const targetLabelId = selectedBulkLabel.value?.id
  if (!targetLabelId) return []

  const query = bulkAssignSearch.value.trim().toLowerCase()

  return bulkScopeProjects.value.filter((project) => {
    const alreadyTagged = (project.labels || []).some(
      (label) => label.id === targetLabelId
    )
    if (alreadyTagged) return false

    if (!query) return true
    return (
      project.name.toLowerCase().includes(query) ||
      project.path.toLowerCase().includes(query)
    )
  })
})

const selectedBulkProjectSet = computed(
  () => new Set(bulkSelectedProjectIds.value)
)

const filteredBulkCollectProjects = computed(() => {
  const query = bulkCollectSearch.value.trim().toLowerCase()
  if (!query) return bulkCollectProjects.value

  return bulkCollectProjects.value.filter((project) => {
    return (
      project.name.toLowerCase().includes(query) ||
      project.path.toLowerCase().includes(query)
    )
  })
})

const selectedBulkCollectProjectSet = computed(
  () => new Set(bulkCollectSelectedProjectIds.value)
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
      t('adminPages.gitlabProjects.toast.loadLabelsFailed', {
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
      page: currentPage.value,
      page_size: pageSize.value,
      label_ids: selectedLabelIds.value.join(',')
    })
    projects.value = Array.isArray(data) ? data : (data?.results ?? [])
    totalCount.value = Array.isArray(data)
      ? data.length
      : Number(data?.count ?? projects.value.length)
  } catch (e) {
    projects.value = []
    totalCount.value = 0
    showToast(
      t('adminPages.gitlabProjects.toast.loadFailed', { message: e.message }),
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
      t('adminPages.gitlabProjects.toast.loadGroupsFailed', {
        message: e.message
      }),
      'error'
    )
  }
}

function handleGroupChange() {
  currentPage.value = 1
  loadProjects()
}

function toggleLabelFilter(labelId) {
  const normalizedId = Number(labelId)
  if (selectedLabelIds.value.includes(normalizedId)) {
    selectedLabelIds.value = selectedLabelIds.value.filter(
      (id) => id !== normalizedId
    )
  } else {
    selectedLabelIds.value = [...selectedLabelIds.value, normalizedId]
  }
  currentPage.value = 1
  loadProjects()
}

function handlePageSizeChange(size) {
  pageSize.value = size
  currentPage.value = 1
  loadProjects()
}

function goPrevPage() {
  if (currentPage.value <= 1) return
  currentPage.value -= 1
  loadProjects()
}

function goNextPage() {
  if (currentPage.value * pageSize.value >= totalCount.value) return
  currentPage.value += 1
  loadProjects()
}

async function deleteProject(project) {
  requestConfirm({
    title: t('common.delete'),
    message: t('adminPages.gitlabProjects.deleteConfirm', {
      name: project.name
    }),
    confirmText: t('common.delete'),
    onConfirm: async () => {
      try {
        await gitlabApi.deleteProject(project.id)
        showToast(t('adminPages.gitlabProjects.toast.deleteSucceeded'))
        loadProjects()
      } catch (e) {
        showToast(
          t('adminPages.gitlabProjects.toast.deleteFailed', {
            message: e.message
          }),
          'error'
        )
      }
    }
  })
}

async function openBulkCollectModal() {
  bulkCollectLoading.value = true
  bulkCollectSelectedProjectIds.value = []
  bulkCollectSearch.value = ''
  showBulkCollectModal.value = true

  try {
    const data = await gitlabApi.listProjectsPage({
      group: selectedGroup.value,
      label_ids: selectedLabelIds.value.join(','),
      page_size: 10000
    })
    bulkCollectProjects.value = normalizeCollection(data)
  } catch (e) {
    bulkCollectProjects.value = []
    showToast(
      t('adminPages.gitlabProjects.toast.loadBulkCollectProjectsFailed', {
        message: e.message
      }),
      'error'
    )
  } finally {
    bulkCollectLoading.value = false
  }
}

function closeBulkCollectModal() {
  showBulkCollectModal.value = false
  bulkCollectLoading.value = false
  bulkCollectSaving.value = false
  bulkCollectProjects.value = []
  bulkCollectSelectedProjectIds.value = []
  bulkCollectSearch.value = ''
}

function selectAllBulkCollectProjects() {
  bulkCollectSelectedProjectIds.value = filteredBulkCollectProjects.value.map(
    (project) => project.id
  )
}

function clearBulkCollectSelection() {
  bulkCollectSelectedProjectIds.value = []
}

async function saveBulkCollect() {
  if (!bulkCollectSelectedProjectIds.value.length) return

  bulkCollectSaving.value = true
  try {
    const result = await gitlabApi.bulkCollectProjects({
      project_ids: bulkCollectSelectedProjectIds.value
    })
    showToast(
      t('adminPages.gitlabProjects.toast.bulkCollectCompleted', {
        success: result.success_count ?? 0,
        failed: result.failed_count ?? 0
      })
    )
    await loadProjects()
    closeBulkCollectModal()
  } catch (e) {
    showToast(
      t('adminPages.gitlabProjects.toast.bulkCollectFailed', {
        message: e.message
      }),
      'error'
    )
  } finally {
    bulkCollectSaving.value = false
  }
}

function resetLabelDraft() {
  editingLabel.value = null
  labelDraft.value = { name: '' }
}

async function openLabelLibraryModal() {
  await loadProjectLabels()
  resetLabelDraft()
  showLabelLibraryModal.value = true
}

function closeLabelLibraryModal() {
  showLabelLibraryModal.value = false
  resetLabelDraft()
}

function startEditProjectLabel(label) {
  editingLabel.value = label
  labelDraft.value = { name: label.name }
}

async function saveProjectLabel() {
  const name = labelDraft.value.name.trim()
  if (!name) {
    showToast(t('adminPages.gitlabProjects.toast.inputLabelNameError'), 'error')
    return
  }

  try {
    if (editingLabel.value) {
      await gitlabApi.updateProjectLabel(editingLabel.value.id, { name })
      showToast(t('adminPages.gitlabProjects.toast.labelUpdated'))
    } else {
      await gitlabApi.createProjectLabel({ name })
      showToast(t('adminPages.gitlabProjects.toast.labelCreated'))
    }
    await loadProjectLabels()
    await loadProjects()
    resetLabelDraft()
  } catch (e) {
    showToast(
      t('adminPages.gitlabProjects.toast.saveLabelFailed', {
        message: e.message
      }),
      'error'
    )
  }
}

async function deleteProjectLabel(label) {
  requestConfirm({
    title: t('common.delete'),
    message: t('adminPages.gitlabProjects.deleteLabelConfirm', {
      name: label.name
    }),
    confirmText: t('common.delete'),
    onConfirm: async () => {
      try {
        await gitlabApi.deleteProjectLabel(label.id)
        if (selectedLabelIds.value.includes(label.id)) {
          selectedLabelIds.value = selectedLabelIds.value.filter(
            (id) => id !== label.id
          )
        }
        showToast(t('adminPages.gitlabProjects.toast.labelDeleted'))
        await loadProjectLabels()
        await loadProjects()
        if (editingProject.value) {
          selectedProjectLabelIds.value = selectedProjectLabelIds.value.filter(
            (id) => id !== label.id
          )
        }
      } catch (e) {
        showToast(
          t('adminPages.gitlabProjects.toast.deleteLabelFailed', {
            message: e.message
          }),
          'error'
        )
      }
    }
  })
}

async function openProjectLabelsModal(project) {
  editingProject.value = project
  selectedProjectLabelIds.value = (project.labels || []).map(
    (label) => label.id
  )
  await loadProjectLabels()
  showProjectLabelsModal.value = true
}

function closeProjectLabelsModal() {
  showProjectLabelsModal.value = false
  editingProject.value = null
  selectedProjectLabelIds.value = []
}

async function openBulkAssignModal() {
  if (!selectedBulkLabel.value) return

  bulkAssignLoading.value = true
  bulkSelectedProjectIds.value = []
  bulkAssignSearch.value = ''
  showBulkAssignModal.value = true

  try {
    const data = await gitlabApi.listProjectsPage({
      group: selectedGroup.value,
      page_size: 10000
    })
    bulkScopeProjects.value = normalizeCollection(data)
  } catch (e) {
    bulkScopeProjects.value = []
    showToast(
      t('adminPages.gitlabProjects.toast.loadBulkProjectsFailed', {
        message: e.message
      }),
      'error'
    )
  } finally {
    bulkAssignLoading.value = false
  }
}

function closeBulkAssignModal() {
  showBulkAssignModal.value = false
  bulkAssignLoading.value = false
  bulkAssignSaving.value = false
  bulkScopeProjects.value = []
  bulkSelectedProjectIds.value = []
  bulkAssignSearch.value = ''
}

function selectAllBulkAssignableProjects() {
  bulkSelectedProjectIds.value = filteredBulkAssignableProjects.value.map(
    (project) => project.id
  )
}

function clearBulkAssignSelection() {
  bulkSelectedProjectIds.value = []
}

async function saveProjectLabels() {
  if (!editingProject.value) return
  try {
    await gitlabApi.updateProject(editingProject.value.id, {
      label_ids: selectedProjectLabelIds.value
    })
    showToast(t('adminPages.gitlabProjects.toast.projectLabelsUpdated'))
    await loadProjects()
    closeProjectLabelsModal()
  } catch (e) {
    showToast(
      t('adminPages.gitlabProjects.toast.saveProjectLabelsFailed', {
        message: e.message
      }),
      'error'
    )
  }
}

async function saveBulkAssign() {
  if (!selectedBulkLabel.value || !bulkSelectedProjectIds.value.length) return

  bulkAssignSaving.value = true
  try {
    const targetLabelId = selectedBulkLabel.value.id
    const selectedProjects = bulkScopeProjects.value.filter((project) =>
      bulkSelectedProjectIds.value.includes(project.id)
    )

    await Promise.all(
      selectedProjects.map((project) => {
        const existingLabelIds = (project.labels || []).map((label) => label.id)
        return gitlabApi.updateProject(project.id, {
          label_ids: [...new Set([...existingLabelIds, targetLabelId])]
        })
      })
    )

    showToast(
      t('adminPages.gitlabProjects.toast.bulkAssignSucceeded', {
        count: selectedProjects.length,
        name: selectedBulkLabel.value.name
      })
    )
    await Promise.all([loadProjects(), loadProjectLabels()])
    closeBulkAssignModal()
  } catch (e) {
    showToast(
      t('adminPages.gitlabProjects.toast.bulkAssignFailed', {
        message: e.message
      }),
      'error'
    )
  } finally {
    bulkAssignSaving.value = false
  }
}

onMounted(async () => {
  await Promise.all([loadProjectLabels(), loadGroups()])
  await loadProjects()
})
</script>
