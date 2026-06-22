<template>
  <AdminLayout>
    <PageFrame
      variant="soft"
      :eyebrow="t('adminPages.gitlabTags.eyebrow')"
      :title="t('adminPages.gitlabTags.title')"
      :subtitle="t('adminPages.gitlabTags.subtitle')"
    >
      <AdminScopeSection>
        <template #meta>
          <p class="admin-scope-kicker">
            {{ t('adminPages.gitlabTags.scopeTitle') }}
          </p>
          <h2 class="admin-scope-heading">
            {{
              currentProject?.path || t('adminPages.gitlabTags.selectProject')
            }}
          </h2>
          <p class="admin-scope-copy">
            {{ t('adminPages.gitlabTags.scopeHint') }}
          </p>
        </template>
        <template #actions>
          <BaseButton size="sm" @click="openBulkTagModal">
            {{ t('adminPages.gitlabTags.bulkOperate') }}
          </BaseButton>
        </template>
        <label class="admin-scope-card">
          <span class="admin-scope-card-label">{{
            t('adminPages.gitlabTags.selectGroup')
          }}</span>
          <select
            v-model="selectedGroup"
            @change="handleGroupChange"
            class="admin-filter-control"
          >
            <option value="">
              {{ t('adminPages.gitlabTags.allGroups') }}
            </option>
            <option v-for="group in groups" :key="group.id" :value="group.id">
              {{ group.name }}
            </option>
          </select>
        </label>
        <div class="admin-scope-card">
          <span class="admin-scope-card-label">{{
            t('adminPages.gitlabTags.resourceLabels')
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
            {{ t('adminPages.gitlabTags.noResourceLabels') }}
          </p>
        </div>
        <label class="admin-scope-card">
          <span class="admin-scope-card-label">{{
            t('adminPages.gitlabTags.selectProject')
          }}</span>
          <select
            v-model="tagProjectFilter"
            @change="handleProjectFilterChange"
            class="admin-filter-control"
          >
            <option value="">
              {{ t('adminPages.gitlabTags.selectProject') }}
            </option>
            <option
              v-for="project in projects"
              :key="project.id"
              :value="project.id"
            >
              {{ project.name }}
            </option>
          </select>
        </label>
        <div class="admin-scope-summary">
          <div class="admin-scope-stat">
            <span class="admin-scope-stat-label">{{
              t('adminPages.gitlabTags.tagsTotal')
            }}</span>
            <strong class="admin-scope-stat-value">{{ totalCount }}</strong>
          </div>
          <div class="admin-scope-stat">
            <span class="admin-scope-stat-label">{{
              t('adminPages.gitlabTags.visibleCount')
            }}</span>
            <strong class="admin-scope-stat-value">{{ tags.length }}</strong>
          </div>
          <div class="admin-scope-stat">
            <span class="admin-scope-stat-label">{{
              t('adminPages.gitlabTags.selectedCount')
            }}</span>
            <strong class="admin-scope-stat-value">{{
              selectedTags.length
            }}</strong>
          </div>
        </div>
      </AdminScopeSection>

      <AdminTable v-if="tags.length">
        <thead>
          <tr>
            <th class="admin-table-head w-12">
              <input
                type="checkbox"
                v-model="selectAllTags"
                @change="toggleSelectAllTags"
                class="rounded"
              />
            </th>
            <th class="admin-table-head">
              {{ t('adminPages.gitlabTags.tagName') }}
            </th>
            <th class="admin-table-head">{{ t('common.project') }}</th>
            <th class="admin-table-head">
              {{ t('adminPages.gitlabTags.commitSha') }}
            </th>
            <th class="admin-table-head">
              {{ t('adminPages.gitlabTags.releaseDate') }}
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="tag in tags" :key="tag.id" class="admin-table-row">
            <td class="admin-table-cell">
              <input
                type="checkbox"
                v-model="selectedTags"
                :value="tag.id"
                class="rounded"
              />
            </td>
            <td class="admin-table-cell">
              <div class="branch-name-cell">
                <span>{{ tag.name }}</span>
              </div>
            </td>
            <td class="admin-table-cell font-mono text-sm text-slate-500">
              {{ tag.project_path }}
            </td>
            <td class="admin-table-cell font-mono text-sm text-slate-600">
              {{ tag.commit_sha?.substring(0, 8) || t('common.emptyValue') }}
            </td>
            <td class="admin-table-cell text-sm text-slate-500">
              {{ tag.released_at || t('common.emptyValue') }}
            </td>
          </tr>
        </tbody>
      </AdminTable>
      <PaginationBar
        v-if="tags.length"
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
        :title="t('adminPages.gitlabTags.emptyTitle')"
        :description="t('adminPages.gitlabTags.emptySubtitle')"
      />

      <BaseModal
        :show="showBulkTagModal"
        size="wide"
        :title="t('adminPages.gitlabTags.bulkOperateTitle')"
        @close="closeBulkTagModal"
      >
        <div class="admin-bulk-dialog">
          <section class="admin-bulk-operations">
            <button
              v-for="operation in bulkTagOperations"
              :key="operation.value"
              type="button"
              :class="[
                'admin-bulk-operation',
                bulkTagOperation === operation.value && 'is-active'
              ]"
              @click="bulkTagOperation = operation.value"
            >
              {{ operation.label }}
            </button>
          </section>

          <template v-if="bulkTagOperation === 'create'">
            <section class="grid gap-3 md:grid-cols-3">
              <button
                type="button"
                :class="[
                  'admin-scope-step-card',
                  bulkTagStep === 1 ? 'is-active' : ''
                ]"
                @click="bulkTagStep = 1"
              >
                <span class="text-xs font-semibold uppercase tracking-[0.2em]">
                  01
                </span>
                <p class="mt-2 text-sm font-semibold">
                  {{ t('adminPages.gitlabTags.stepScopeTitle') }}
                </p>
                <p class="mt-1 text-xs leading-5 opacity-80">
                  {{ t('adminPages.gitlabTags.stepScopeDesc') }}
                </p>
              </button>
              <button
                type="button"
                :disabled="!canGoToBulkProjectsStep"
                :class="[
                  'admin-scope-step-card',
                  bulkTagStep === 2 ? 'is-active' : '',
                  !canGoToBulkProjectsStep ? 'is-disabled' : ''
                ]"
                @click="goToBulkProjectsStep"
              >
                <span class="text-xs font-semibold uppercase tracking-[0.2em]">
                  02
                </span>
                <p class="mt-2 text-sm font-semibold">
                  {{ t('adminPages.gitlabTags.stepProjectsTitle') }}
                </p>
                <p class="mt-1 text-xs leading-5 opacity-80">
                  {{ t('adminPages.gitlabTags.stepProjectsDesc') }}
                </p>
              </button>
              <button
                type="button"
                :disabled="!canGoToBulkComposeStep"
                :class="[
                  'admin-scope-step-card',
                  bulkTagStep === 3 ? 'is-active' : '',
                  !canGoToBulkComposeStep ? 'is-disabled' : ''
                ]"
                @click="goToBulkComposeStep"
              >
                <span class="text-xs font-semibold uppercase tracking-[0.2em]">
                  03
                </span>
                <p class="mt-2 text-sm font-semibold">
                  {{ t('adminPages.gitlabTags.stepComposeTitle') }}
                </p>
                <p class="mt-1 text-xs leading-5 opacity-80">
                  {{ t('adminPages.gitlabTags.stepComposeDesc') }}
                </p>
              </button>
            </section>

            <section v-if="bulkTagStep === 1" class="grid gap-5 lg:grid-cols-2">
              <section class="admin-modal-card">
                <header class="admin-bulk-panel-head">
                  <div>
                    <h3 class="admin-bulk-title">
                      {{ t('adminPages.gitlabTags.targetGroups') }}
                    </h3>
                    <p class="admin-bulk-subtitle">
                      {{ t('adminPages.gitlabTags.targetGroupsHint') }}
                    </p>
                  </div>
                  <span class="admin-bulk-count"
                    >{{ bulkTagForm.group_ids.length }}/{{
                      groups.length
                    }}</span
                  >
                </header>
                <div
                  class="admin-bulk-choice-box admin-bulk-choice-box--groups"
                >
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
                      <span class="admin-bulk-choice-text">{{
                        group.name
                      }}</span>
                      <span class="admin-bulk-choice-meta">{{
                        t('adminPages.gitlabTags.groupProjectsPreview')
                      }}</span>
                    </div>
                  </label>
                </div>
              </section>

              <section class="admin-modal-card">
                <header class="admin-bulk-panel-head">
                  <div>
                    <h3 class="admin-bulk-title">
                      {{ t('adminPages.gitlabTags.resourceLabels') }}
                    </h3>
                    <p class="admin-bulk-subtitle">
                      {{ t('adminPages.gitlabTags.resourceLabelsHint') }}
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
                  {{ t('adminPages.gitlabTags.noResourceLabels') }}
                </p>
              </section>
            </section>

            <section v-else-if="bulkTagStep === 2" class="admin-modal-card">
              <header class="admin-bulk-panel-head">
                <div>
                  <h3 class="admin-bulk-title">
                    {{ t('adminPages.gitlabTags.targetProjects') }}
                  </h3>
                  <p class="admin-bulk-subtitle">
                    {{ t('adminPages.gitlabTags.targetProjectsHint') }}
                  </p>
                </div>
                <div class="admin-bulk-panel-actions">
                  <span class="admin-bulk-count"
                    >{{ bulkTagForm.project_ids.length }}/{{
                      bulkProjectOptions.length
                    }}</span
                  >
                  <button
                    type="button"
                    class="admin-bulk-inline-action"
                    :disabled="!bulkProjectOptions.length"
                    @click="selectAllBulkProjects"
                  >
                    {{ t('adminPages.gitlabTags.selectAllProjects') }}
                  </button>
                  <span class="admin-bulk-actions-divider">|</span>
                  <button
                    type="button"
                    class="admin-bulk-inline-action"
                    :disabled="!bulkTagForm.project_ids.length"
                    @click="clearBulkProjects"
                  >
                    {{ t('adminPages.gitlabTags.clearProjects') }}
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
                    v-model="bulkTagForm.project_ids"
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
                  bulkTagForm.group_ids.length
                    ? t('adminPages.gitlabTags.noMatchingProjects')
                    : t('adminPages.gitlabTags.chooseGroupsFirst')
                }}
              </p>
            </section>

            <section
              v-else
              class="flex flex-col gap-5 xl:h-[26rem] xl:flex-row"
            >
              <section
                class="admin-modal-card flex min-h-0 h-full flex-col overflow-hidden xl:w-[37%] xl:max-w-[25rem]"
              >
                <div
                  class="admin-bulk-selected-shell admin-bulk-selected-shell--fill"
                >
                  <div class="admin-bulk-selected-head">
                    <h3 class="admin-bulk-title">
                      {{
                        t('adminPages.gitlabTags.selectedProjectsCount', {
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
                      {{ t('adminPages.gitlabTags.clearProjects') }}
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
                    {{ t('adminPages.gitlabTags.selectedProjectsEmptyInline') }}
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
                      {{ t('adminPages.gitlabTags.stepComposeTitle') }}
                    </h3>
                    <p class="text-sm text-slate-500">
                      {{ t('adminPages.gitlabTags.stepComposeDesc') }}
                    </p>
                  </div>
                  <div class="admin-scope-preview-card">
                    {{
                      t('adminPages.gitlabTags.bulkPreview', {
                        projects: bulkTagForm.project_ids.length,
                        tags: parsedBulkTagNames.length
                      })
                    }}
                  </div>
                </header>

                <section class="grid gap-4 lg:grid-cols-[260px_minmax(0,1fr)]">
                  <div class="space-y-4">
                    <div class="space-y-2">
                      <label class="admin-bulk-input-label">{{
                        t('adminPages.gitlabTags.sourceRef')
                      }}</label>
                      <input
                        v-model="bulkTagForm.ref"
                        type="text"
                        :placeholder="
                          t('adminPages.gitlabTags.sourceRefPlaceholder')
                        "
                        class="admin-modal-control"
                      />
                      <p class="text-xs leading-5 text-slate-500">
                        {{ t('adminPages.gitlabTags.sourceRefHint') }}
                      </p>
                    </div>

                    <div class="space-y-2">
                      <label class="admin-bulk-input-label">{{
                        t('adminPages.gitlabTags.tagMessage')
                      }}</label>
                      <textarea
                        v-model="bulkTagForm.message"
                        rows="6"
                        :placeholder="
                          t('adminPages.gitlabTags.tagMessagePlaceholder')
                        "
                        class="admin-modal-control admin-bulk-textarea min-h-[132px]"
                      ></textarea>
                      <p class="text-xs leading-5 text-slate-500">
                        {{ t('adminPages.gitlabTags.tagMessageHint') }}
                      </p>
                    </div>
                  </div>

                  <div class="space-y-2">
                    <label class="admin-bulk-input-label">{{
                      t('adminPages.gitlabTags.newTagNames')
                    }}</label>
                    <textarea
                      v-model="bulkTagForm.tag_names"
                      rows="8"
                      :placeholder="
                        t('adminPages.gitlabTags.tagNamesPlaceholder')
                      "
                      class="admin-modal-control admin-bulk-textarea min-h-[220px] font-mono"
                    ></textarea>
                  </div>
                </section>
              </section>
            </section>
          </template>

          <section v-else class="admin-bulk-grid">
            <section class="admin-bulk-panel admin-bulk-summary-panel">
              <header
                class="admin-bulk-panel-head admin-bulk-panel-head--compact"
              >
                <h3 class="admin-bulk-title">
                  {{ t('adminPages.gitlabTags.summaryTitle') }}
                </h3>
              </header>
              <div class="admin-bulk-note">
                <p>{{ t('adminPages.gitlabTags.deleteSelectionHint') }}</p>
              </div>
            </section>

            <section class="admin-bulk-panel admin-bulk-compose-panel">
              <div class="admin-bulk-selected-shell">
                <div class="admin-bulk-selected-head">
                  <h3 class="admin-bulk-title">
                    {{
                      t('adminPages.gitlabTags.selectedDeleteCount', {
                        count: selectedBulkTags.length
                      })
                    }}
                  </h3>
                </div>
                <div
                  v-if="selectedBulkTags.length"
                  class="admin-bulk-selected-grid"
                >
                  <div
                    v-for="tag in selectedBulkTags"
                    :key="tag.id"
                    class="admin-bulk-selected-chip"
                  >
                    <span>{{ tag.name }}</span>
                  </div>
                </div>
                <p
                  v-else
                  class="admin-bulk-selected-empty admin-bulk-selected-empty--inline"
                >
                  {{ t('adminPages.gitlabTags.selectedDeleteEmpty') }}
                </p>
              </div>
            </section>
          </section>
        </div>
        <template #footer>
          <div class="flex w-full justify-end gap-3">
            <BaseButton variant="secondary" @click="closeBulkTagModal">{{
              t('common.cancel')
            }}</BaseButton>
            <BaseButton
              v-if="bulkTagOperation === 'create' && bulkTagStep > 1"
              variant="secondary"
              @click="goToPrevBulkStep"
            >
              {{ t('common.previous') }}
            </BaseButton>
            <BaseButton
              v-if="bulkTagOperation === 'create' && bulkTagStep < 3"
              :disabled="
                bulkTagStep === 1
                  ? !canGoToBulkProjectsStep
                  : !canGoToBulkComposeStep
              "
              @click="goToNextBulkStep"
            >
              {{ t('common.next') }}
            </BaseButton>
            <BaseButton v-else @click="submitBulkTags">{{
              bulkTagSubmitLabel
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
import { computed, onMounted, ref } from 'vue'
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
const tags = ref([])
const selectedTags = ref([])
const selectAllTags = ref(false)
const selectedGroup = ref('')
const tagProjectFilter = ref('')
const selectedLabelIds = ref([])
const projectLabels = ref([])
const showBulkTagModal = ref(false)
const bulkTagOperation = ref('create')
const bulkProjectOptions = ref([])
const bulkSelectedLabelIds = ref([])
const bulkTagStep = ref(1)
const bulkTagForm = ref({
  group_ids: [],
  project_ids: [],
  ref: 'main',
  tag_names: '',
  message: ''
})
const currentPage = ref(1)
const pageSize = ref(20)
const totalCount = ref(0)

const toast = ref({ show: false, message: '', type: 'success' })

const currentProject = computed(() =>
  projects.value.find(
    (project) => String(project.id) === String(tagProjectFilter.value)
  )
)

const parsedBulkTagNames = computed(() =>
  bulkTagForm.value.tag_names
    .split('\n')
    .map((name) => name.trim())
    .filter(Boolean)
)

const selectedBulkProjectSet = computed(
  () => new Set(bulkTagForm.value.project_ids)
)

const selectedBulkProjects = computed(() =>
  bulkProjectOptions.value.filter((project) =>
    selectedBulkProjectSet.value.has(project.id)
  )
)

const canGoToBulkProjectsStep = computed(
  () => bulkTagForm.value.group_ids.length > 0
)

const canGoToBulkComposeStep = computed(
  () => bulkTagForm.value.project_ids.length > 0
)

const selectedTagSet = computed(() => new Set(selectedTags.value))

const selectedBulkTags = computed(() =>
  tags.value.filter((tag) => selectedTagSet.value.has(tag.id))
)

const bulkTagOperations = computed(() => [
  { value: 'create', label: t('adminPages.gitlabTags.operationCreate') },
  { value: 'delete', label: t('adminPages.gitlabTags.operationDelete') }
])

const bulkTagSubmitLabel = computed(() =>
  bulkTagOperation.value === 'delete'
    ? t('adminPages.gitlabTags.executeDelete')
    : t('adminPages.gitlabTags.create')
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
      t('adminPages.gitlabTags.toast.loadLabelsFailed', {
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
      t('adminPages.gitlabTags.toast.loadGroupsFailed', { message: e.message }),
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
        (project) => String(project.id) === String(tagProjectFilter.value)
      )
    ) {
      tagProjectFilter.value = projects.value.length
        ? String(projects.value[0].id)
        : ''
    }
  } catch (e) {
    projects.value = []
    tagProjectFilter.value = ''
    showToast(
      t('adminPages.gitlabTags.toast.loadProjectsFailed', {
        message: e.message
      }),
      'error'
    )
  }
}

async function loadTags() {
  if (!tagProjectFilter.value) {
    tags.value = []
    totalCount.value = 0
    selectedTags.value = []
    selectAllTags.value = false
    return
  }
  try {
    const data = await gitlabApi.listTagsPage({
      page: currentPage.value,
      page_size: pageSize.value,
      project_id: tagProjectFilter.value
    })
    tags.value = Array.isArray(data) ? data : (data?.results ?? [])
    totalCount.value = Array.isArray(data)
      ? data.length
      : Number(data?.count ?? tags.value.length)
    selectedTags.value = []
    selectAllTags.value = false
  } catch (e) {
    tags.value = []
    totalCount.value = 0
    showToast(
      t('adminPages.gitlabTags.toast.loadTagsFailed', { message: e.message }),
      'error'
    )
  }
}

function handlePageSizeChange(size) {
  pageSize.value = size
  currentPage.value = 1
  loadTags()
}

function goPrevPage() {
  if (currentPage.value <= 1) return
  currentPage.value -= 1
  loadTags()
}

function goNextPage() {
  if (currentPage.value * pageSize.value >= totalCount.value) return
  currentPage.value += 1
  loadTags()
}

async function handleGroupChange() {
  currentPage.value = 1
  tagProjectFilter.value = ''
  tags.value = []
  totalCount.value = 0
  await loadProjects()
  await loadTags()
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
  tagProjectFilter.value = ''
  await loadProjects()
  await loadTags()
}

function handleProjectFilterChange() {
  currentPage.value = 1
  loadTags()
}

function toggleSelectAllTags() {
  if (selectAllTags.value) {
    selectedTags.value = tags.value.map((tag) => tag.id)
  } else {
    selectedTags.value = []
  }
}

function openBulkTagModal() {
  bulkTagOperation.value = 'create'
  bulkTagStep.value = 1
  bulkSelectedLabelIds.value = [...selectedLabelIds.value]
  bulkTagForm.value = {
    group_ids: selectedGroup.value ? [Number(selectedGroup.value)] : [],
    project_ids: tagProjectFilter.value ? [Number(tagProjectFilter.value)] : [],
    ref: 'main',
    tag_names: '',
    message: ''
  }
  bulkProjectOptions.value = [...projects.value]
  showBulkTagModal.value = true
}

function closeBulkTagModal() {
  showBulkTagModal.value = false
  bulkSelectedLabelIds.value = []
  bulkTagStep.value = 1
}

function goToBulkProjectsStep() {
  if (!canGoToBulkProjectsStep.value) return
  bulkTagStep.value = 2
}

function goToBulkComposeStep() {
  if (!canGoToBulkComposeStep.value) return
  bulkTagStep.value = 3
}

function goToPrevBulkStep() {
  bulkTagStep.value = Math.max(1, bulkTagStep.value - 1)
}

function goToNextBulkStep() {
  if (bulkTagStep.value === 1) {
    goToBulkProjectsStep()
    return
  }
  if (bulkTagStep.value === 2) {
    goToBulkComposeStep()
  }
}

function isBulkGroupSelected(groupId) {
  return bulkTagForm.value.group_ids.includes(Number(groupId))
}

async function toggleBulkGroup(groupId) {
  const normalizedGroupId = Number(groupId)
  const selected = bulkTagForm.value.group_ids
  if (selected.includes(normalizedGroupId)) {
    bulkTagForm.value.group_ids = selected.filter(
      (id) => id !== normalizedGroupId
    )
  } else {
    bulkTagForm.value.group_ids = [...selected, normalizedGroupId]
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
  bulkTagForm.value.project_ids = bulkProjectOptions.value.map(
    (project) => project.id
  )
}

function clearBulkProjects() {
  bulkTagForm.value.project_ids = []
}

function removeBulkProject(projectId) {
  bulkTagForm.value.project_ids = bulkTagForm.value.project_ids.filter(
    (id) => id !== projectId
  )
}

async function loadBulkProjectOptions() {
  const groupIds = bulkTagForm.value.group_ids
  if (!groupIds.length) {
    bulkProjectOptions.value = []
    bulkTagForm.value.project_ids = []
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
    bulkTagForm.value.project_ids = bulkTagForm.value.project_ids.filter(
      (projectId) => seen.has(projectId)
    )
  } catch (e) {
    bulkProjectOptions.value = []
    bulkTagForm.value.project_ids = []
    showToast(
      t('adminPages.gitlabTags.toast.loadProjectsFailed', {
        message: e.message
      }),
      'error'
    )
  }
}

async function submitBulkTags() {
  if (bulkTagOperation.value === 'delete') {
    await bulkDeleteTags()
    return
  }
  if (!bulkTagForm.value.project_ids.length) {
    showToast(t('adminPages.gitlabTags.selectProjectError'), 'error')
    return
  }
  const names = parsedBulkTagNames.value
  if (!names.length) {
    showToast(t('adminPages.gitlabTags.inputTagNamesError'), 'error')
    return
  }

  try {
    const result = await gitlabApi.bulkCreateTags({
      project_ids: bulkTagForm.value.project_ids,
      ref: bulkTagForm.value.ref,
      tag_names: names,
      message: bulkTagForm.value.message
    })

    showToast(
      t('adminPages.gitlabTags.toast.createResult', {
        created: result.success_count ?? result.created?.length ?? 0,
        failed: result.error_count ?? result.errors?.length ?? 0
      })
    )
    closeBulkTagModal()
    loadTags()
  } catch (e) {
    showToast(
      t('adminPages.gitlabTags.toast.createFailed', { message: e.message }),
      'error'
    )
  }
}

async function executeBulkDeleteTags() {
  try {
    const result = await gitlabApi.bulkDeleteTags(selectedTags.value)
    showToast(
      t('adminPages.gitlabTags.toast.deleteResult', {
        deleted: result.deleted.length,
        failed: result.errors.length
      })
    )
    closeBulkTagModal()
    selectedTags.value = []
    loadTags()
  } catch (e) {
    showToast(
      t('adminPages.gitlabTags.toast.deleteFailed', { message: e.message }),
      'error'
    )
  }
}

async function bulkDeleteTags() {
  if (!selectedTags.value.length) {
    showToast(t('adminPages.gitlabTags.selectDeleteError'), 'error')
    return
  }

  requestConfirm({
    title: t('common.delete'),
    message: `${t('adminPages.gitlabTags.deleteConfirm', {
      count: selectedTags.value.length
    })} ${t('adminPages.gitlabTags.deleteConfirmSecond')}`,
    confirmText: t('common.delete'),
    onConfirm: executeBulkDeleteTags
  })
}

onMounted(async () => {
  await loadProjectLabels()
  await loadGroups()
  await loadProjects()
  await loadTags()
})
</script>
