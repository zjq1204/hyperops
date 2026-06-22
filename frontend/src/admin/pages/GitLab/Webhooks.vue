<template>
  <AdminLayout>
    <PageFrame
      variant="soft"
      :eyebrow="t('adminPages.gitlabWebhooks.eyebrow')"
      :title="t('adminPages.gitlabWebhooks.title')"
      :subtitle="t('adminPages.gitlabWebhooks.subtitle')"
    >
      <AdminScopeSection>
        <template #meta>
          <p class="admin-scope-kicker">
            {{ t('adminPages.gitlabWebhooks.scopeTitle') }}
          </p>
          <h2 class="admin-scope-heading">
            {{
              currentProject?.path ||
              t('adminPages.gitlabWebhooks.selectProject')
            }}
          </h2>
          <p class="admin-scope-copy">
            {{ t('adminPages.gitlabWebhooks.scopeHint') }}
          </p>
        </template>
        <template #actions>
          <BaseButton size="sm" @click="openBulkWebhookModal">
            {{ t('adminPages.gitlabWebhooks.bulkOperate') }}
          </BaseButton>
        </template>
        <label class="admin-scope-card">
          <span class="admin-scope-card-label">{{
            t('adminPages.gitlabWebhooks.selectGroup')
          }}</span>
          <select
            v-model="selectedGroup"
            @change="handleGroupChange"
            class="admin-filter-control"
          >
            <option value="">
              {{ t('adminPages.gitlabWebhooks.allGroups') }}
            </option>
            <option v-for="group in groups" :key="group.id" :value="group.id">
              {{ group.name }}
            </option>
          </select>
        </label>
        <div class="admin-scope-card">
          <span class="admin-scope-card-label">{{
            t('adminPages.gitlabWebhooks.resourceLabels')
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
            {{ t('adminPages.gitlabWebhooks.noResourceLabels') }}
          </p>
        </div>
        <label class="admin-scope-card">
          <span class="admin-scope-card-label">{{
            t('adminPages.gitlabWebhooks.selectProject')
          }}</span>
          <select
            v-model="webhookProjectFilter"
            @change="handleProjectFilterChange"
            class="admin-filter-control"
          >
            <option value="">
              {{ t('adminPages.gitlabWebhooks.selectProject') }}
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
              t('adminPages.gitlabWebhooks.webhooksTotal')
            }}</span>
            <strong class="admin-scope-stat-value">{{ totalCount }}</strong>
          </div>
          <div class="admin-scope-stat">
            <span class="admin-scope-stat-label">{{
              t('adminPages.gitlabWebhooks.pushEnabledCount')
            }}</span>
            <strong class="admin-scope-stat-value">{{
              pushEnabledCount
            }}</strong>
          </div>
          <div class="admin-scope-stat">
            <span class="admin-scope-stat-label">{{
              t('adminPages.gitlabWebhooks.selectedCount')
            }}</span>
            <strong class="admin-scope-stat-value">{{
              selectedWebhooks.length
            }}</strong>
          </div>
        </div>
      </AdminScopeSection>

      <AdminTable v-if="webhooks.length">
        <thead>
          <tr>
            <th class="admin-table-head w-12">
              <input
                type="checkbox"
                v-model="selectAllWebhooks"
                @change="toggleSelectAllWebhooks"
                class="rounded"
              />
            </th>
            <th class="admin-table-head">{{ t('common.url') }}</th>
            <th class="admin-table-head">{{ t('common.project') }}</th>
            <th class="admin-table-head">
              {{ t('adminPages.gitlabWebhooks.pushColumn') }}
            </th>
            <th class="admin-table-head">
              {{ t('adminPages.gitlabWebhooks.tagColumn') }}
            </th>
            <th class="admin-table-head">
              {{ t('adminPages.gitlabWebhooks.mr') }}
            </th>
            <th class="admin-table-head">{{ t('common.actions') }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="hook in webhooks" :key="hook.id" class="admin-table-row">
            <td class="admin-table-cell">
              <input
                type="checkbox"
                v-model="selectedWebhooks"
                :value="hook.id"
                class="rounded"
              />
            </td>
            <td
              class="admin-table-cell max-w-xs truncate text-sm text-slate-500"
            >
              {{ hook.url }}
            </td>
            <td class="admin-table-cell text-sm text-slate-500">
              {{ hook.project_path }}
            </td>
            <td class="admin-table-cell">
              {{ hook.push_events ? '✓' : t('common.emptyValue') }}
            </td>
            <td class="admin-table-cell">
              {{ hook.tag_push_events ? '✓' : t('common.emptyValue') }}
            </td>
            <td class="admin-table-cell">
              {{ hook.merge_requests_events ? '✓' : t('common.emptyValue') }}
            </td>
            <td class="admin-table-cell">
              <div class="admin-row-actions">
                <button
                  @click="editWebhook(hook)"
                  class="admin-row-action admin-row-action--primary"
                >
                  {{ t('common.edit') }}
                </button>
                <button
                  @click="deleteWebhook(hook)"
                  class="admin-row-action admin-row-action--danger"
                >
                  {{ t('common.delete') }}
                </button>
              </div>
            </td>
          </tr>
        </tbody>
      </AdminTable>
      <PaginationBar
        v-if="webhooks.length"
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
        :title="t('adminPages.gitlabWebhooks.emptyTitle')"
        :description="t('adminPages.gitlabWebhooks.emptySubtitle')"
      />

      <BaseModal
        :show="showBulkWebhookModal"
        size="wide"
        :title="t('adminPages.gitlabWebhooks.bulkOperateTitle')"
        @close="closeBulkWebhookModal"
      >
        <div class="admin-bulk-dialog">
          <section class="admin-bulk-operations">
            <button
              v-for="operation in bulkWebhookOperations"
              :key="operation.value"
              type="button"
              :class="[
                'admin-bulk-operation',
                bulkWebhookOperation === operation.value && 'is-active'
              ]"
              @click="bulkWebhookOperation = operation.value"
            >
              {{ operation.label }}
            </button>
          </section>

          <section v-if="bulkWebhookOperation === 'create'" class="space-y-5">
            <section class="grid gap-3 md:grid-cols-3">
              <button
                type="button"
                :class="[
                  'admin-scope-step-card',
                  bulkWebhookStep === 1 ? 'is-active' : ''
                ]"
                @click="bulkWebhookStep = 1"
              >
                <span class="text-xs font-semibold uppercase tracking-[0.2em]">
                  01
                </span>
                <p class="mt-2 text-sm font-semibold">
                  {{ t('adminPages.gitlabWebhooks.stepScopeTitle') }}
                </p>
                <p class="mt-1 text-xs leading-5 opacity-80">
                  {{ t('adminPages.gitlabWebhooks.stepScopeDesc') }}
                </p>
              </button>
              <button
                type="button"
                :disabled="!canGoToBulkWebhookProjectsStep"
                :class="[
                  'admin-scope-step-card',
                  bulkWebhookStep === 2 ? 'is-active' : '',
                  !canGoToBulkWebhookProjectsStep ? 'is-disabled' : ''
                ]"
                @click="goToBulkWebhookProjectsStep"
              >
                <span class="text-xs font-semibold uppercase tracking-[0.2em]">
                  02
                </span>
                <p class="mt-2 text-sm font-semibold">
                  {{ t('adminPages.gitlabWebhooks.stepProjectsTitle') }}
                </p>
                <p class="mt-1 text-xs leading-5 opacity-80">
                  {{ t('adminPages.gitlabWebhooks.stepProjectsDesc') }}
                </p>
              </button>
              <button
                type="button"
                :disabled="!canGoToBulkWebhookComposeStep"
                :class="[
                  'admin-scope-step-card',
                  bulkWebhookStep === 3 ? 'is-active' : '',
                  !canGoToBulkWebhookComposeStep ? 'is-disabled' : ''
                ]"
                @click="goToBulkWebhookComposeStep"
              >
                <span class="text-xs font-semibold uppercase tracking-[0.2em]">
                  03
                </span>
                <p class="mt-2 text-sm font-semibold">
                  {{ t('adminPages.gitlabWebhooks.stepComposeTitle') }}
                </p>
                <p class="mt-1 text-xs leading-5 opacity-80">
                  {{ t('adminPages.gitlabWebhooks.stepComposeDesc') }}
                </p>
              </button>
            </section>

            <section
              v-if="bulkWebhookStep === 1"
              class="grid gap-5 lg:grid-cols-2"
            >
              <section class="admin-modal-card">
                <header class="admin-bulk-panel-head">
                  <div>
                    <h3 class="admin-bulk-title">
                      {{ t('adminPages.gitlabWebhooks.targetGroups') }}
                    </h3>
                    <p class="admin-bulk-subtitle">
                      {{ t('adminPages.gitlabWebhooks.targetGroupsHint') }}
                    </p>
                  </div>
                  <span class="admin-bulk-count"
                    >{{ bulkWebhookForm.group_ids.length }}/{{
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
                        t('adminPages.gitlabWebhooks.groupProjectsPreview')
                      }}</span>
                    </div>
                  </label>
                </div>
              </section>

              <section class="admin-modal-card">
                <header class="admin-bulk-panel-head">
                  <div>
                    <h3 class="admin-bulk-title">
                      {{ t('adminPages.gitlabWebhooks.resourceLabels') }}
                    </h3>
                    <p class="admin-bulk-subtitle">
                      {{ t('adminPages.gitlabWebhooks.resourceLabelsHint') }}
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
                  {{ t('adminPages.gitlabWebhooks.noResourceLabels') }}
                </p>
              </section>
            </section>

            <section v-else-if="bulkWebhookStep === 2" class="admin-modal-card">
              <header class="admin-bulk-panel-head">
                <div>
                  <h3 class="admin-bulk-title">
                    {{ t('adminPages.gitlabWebhooks.targetProjects') }}
                  </h3>
                  <p class="admin-bulk-subtitle">
                    {{ t('adminPages.gitlabWebhooks.targetProjectsHint') }}
                  </p>
                </div>
                <div class="admin-bulk-panel-actions">
                  <span class="admin-bulk-count"
                    >{{ bulkWebhookForm.project_ids.length }}/{{
                      bulkProjectOptions.length
                    }}</span
                  >
                  <button
                    type="button"
                    class="admin-bulk-inline-action"
                    :disabled="!bulkProjectOptions.length"
                    @click="selectAllBulkProjects"
                  >
                    {{ t('adminPages.gitlabWebhooks.selectAllProjects') }}
                  </button>
                  <span class="admin-bulk-actions-divider">|</span>
                  <button
                    type="button"
                    class="admin-bulk-inline-action"
                    :disabled="!bulkWebhookForm.project_ids.length"
                    @click="clearBulkProjects"
                  >
                    {{ t('adminPages.gitlabWebhooks.clearProjects') }}
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
                    v-model="bulkWebhookForm.project_ids"
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
                  bulkWebhookForm.group_ids.length
                    ? t('adminPages.gitlabWebhooks.noMatchingProjects')
                    : t('adminPages.gitlabWebhooks.chooseGroupsFirst')
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
                        t('adminPages.gitlabWebhooks.selectedProjectsCount', {
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
                      {{ t('adminPages.gitlabWebhooks.clearProjects') }}
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
                      t('adminPages.gitlabWebhooks.selectedProjectsEmptyInline')
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
                      {{ t('adminPages.gitlabWebhooks.stepComposeTitle') }}
                    </h3>
                    <p class="text-sm text-slate-500">
                      {{ t('adminPages.gitlabWebhooks.stepComposeDesc') }}
                    </p>
                  </div>
                  <div class="admin-scope-preview-card">
                    {{
                      t('adminPages.gitlabWebhooks.bulkPreview', {
                        projects: bulkWebhookForm.project_ids.length
                      })
                    }}
                  </div>
                </header>

                <section class="space-y-4">
                  <div class="space-y-2">
                    <label class="admin-bulk-input-label">{{
                      t('common.url')
                    }}</label>
                    <input
                      v-model="bulkWebhookForm.url"
                      type="url"
                      class="admin-modal-control"
                    />
                  </div>
                  <div class="admin-bulk-event-grid">
                    <label class="admin-bulk-event-card">
                      <input
                        v-model="bulkWebhookForm.push_events"
                        type="checkbox"
                      />
                      <span>{{
                        t('adminPages.gitlabWebhooks.pushEvents')
                      }}</span>
                    </label>
                    <label class="admin-bulk-event-card">
                      <input
                        v-model="bulkWebhookForm.tag_push_events"
                        type="checkbox"
                      />
                      <span>{{
                        t('adminPages.gitlabWebhooks.tagPushEvents')
                      }}</span>
                    </label>
                    <label class="admin-bulk-event-card">
                      <input
                        v-model="bulkWebhookForm.merge_requests_events"
                        type="checkbox"
                      />
                      <span>{{
                        t('adminPages.gitlabWebhooks.mergeRequestEvents')
                      }}</span>
                    </label>
                    <label class="admin-bulk-event-card">
                      <input
                        v-model="bulkWebhookForm.enable_ssl_verification"
                        type="checkbox"
                      />
                      <span>{{
                        t('adminPages.gitlabWebhooks.sslVerification')
                      }}</span>
                    </label>
                  </div>
                </section>
              </section>
            </section>
          </section>

          <section v-else class="admin-bulk-grid">
            <section class="admin-bulk-panel admin-bulk-summary-panel">
              <header
                class="admin-bulk-panel-head admin-bulk-panel-head--compact"
              >
                <h3 class="admin-bulk-title">
                  {{ t('adminPages.gitlabWebhooks.summaryTitle') }}
                </h3>
              </header>
              <div class="admin-bulk-summary-metrics">
                <div class="admin-bulk-summary-metric">
                  <span>{{
                    t('adminPages.gitlabWebhooks.selectedCount')
                  }}</span>
                  <strong>{{ selectedWebhooks.length }}</strong>
                </div>
                <div class="admin-bulk-summary-metric">
                  <span>{{
                    t('adminPages.gitlabWebhooks.selectProject')
                  }}</span>
                  <strong>{{
                    currentProject?.name || t('common.emptyValue')
                  }}</strong>
                </div>
              </div>
              <div class="admin-bulk-note">
                <p>{{ t('adminPages.gitlabWebhooks.deleteSelectionHint') }}</p>
              </div>
            </section>

            <section class="admin-bulk-panel admin-bulk-compose-panel">
              <div class="admin-bulk-selected-shell">
                <div class="admin-bulk-selected-head">
                  <h3 class="admin-bulk-title">
                    {{
                      t('adminPages.gitlabWebhooks.selectedDeleteCount', {
                        count: selectedBulkWebhooks.length
                      })
                    }}
                  </h3>
                </div>
                <div
                  v-if="selectedBulkWebhooks.length"
                  class="admin-bulk-selected-grid"
                >
                  <div
                    v-for="hook in selectedBulkWebhooks"
                    :key="hook.id"
                    class="admin-bulk-selected-chip"
                  >
                    <span>{{ hook.url }}</span>
                  </div>
                </div>
                <p
                  v-else
                  class="admin-bulk-selected-empty admin-bulk-selected-empty--inline"
                >
                  {{ t('adminPages.gitlabWebhooks.selectedDeleteEmpty') }}
                </p>
              </div>
            </section>
          </section>
        </div>
        <template #footer>
          <div class="flex w-full justify-end gap-3">
            <BaseButton variant="secondary" @click="closeBulkWebhookModal">{{
              t('common.cancel')
            }}</BaseButton>
            <BaseButton
              v-if="bulkWebhookOperation === 'create' && bulkWebhookStep > 1"
              variant="secondary"
              @click="goToPrevBulkWebhookStep"
            >
              {{ t('common.previous') }}
            </BaseButton>
            <BaseButton
              v-if="bulkWebhookOperation === 'create' && bulkWebhookStep < 3"
              :disabled="
                bulkWebhookStep === 1
                  ? !canGoToBulkWebhookProjectsStep
                  : !canGoToBulkWebhookComposeStep
              "
              @click="goToNextBulkWebhookStep"
            >
              {{ t('common.next') }}
            </BaseButton>
            <BaseButton v-else @click="submitBulkWebhooks">{{
              bulkWebhookSubmitLabel
            }}</BaseButton>
          </div>
        </template>
      </BaseModal>

      <BaseModal
        :show="showWebhookModal"
        :title="
          editingWebhook
            ? t('adminPages.gitlabWebhooks.editTitle')
            : t('adminPages.gitlabWebhooks.createTitle')
        "
        @close="closeWebhookModal"
      >
        <div class="admin-modal-stack">
          <div>
            <label class="admin-modal-field-label">{{
              t('common.project')
            }}</label>
            <select
              v-model="webhookForm.project"
              required
              class="admin-modal-control"
            >
              <option value="">
                {{ t('adminPages.gitlabWebhooks.selectProject') }}
              </option>
              <option
                v-for="project in projects"
                :key="project.id"
                :value="project.id"
              >
                {{ project.path }}
              </option>
            </select>
          </div>
          <div>
            <label class="admin-modal-field-label">{{ t('common.url') }}</label>
            <input
              v-model="webhookForm.url"
              type="url"
              required
              class="admin-modal-control"
            />
          </div>
          <div class="admin-modal-card-muted space-y-2">
            <label class="flex items-center">
              <input
                v-model="webhookForm.push_events"
                type="checkbox"
                class="mr-2"
              />
              <span class="text-sm">{{
                t('adminPages.gitlabWebhooks.pushEvents')
              }}</span>
            </label>
            <label class="flex items-center">
              <input
                v-model="webhookForm.tag_push_events"
                type="checkbox"
                class="mr-2"
              />
              <span class="text-sm">{{
                t('adminPages.gitlabWebhooks.tagPushEvents')
              }}</span>
            </label>
            <label class="flex items-center">
              <input
                v-model="webhookForm.merge_requests_events"
                type="checkbox"
                class="mr-2"
              />
              <span class="text-sm">{{
                t('adminPages.gitlabWebhooks.mergeRequestEvents')
              }}</span>
            </label>
            <label class="flex items-center">
              <input
                v-model="webhookForm.enable_ssl_verification"
                type="checkbox"
                class="mr-2"
              />
              <span class="text-sm">{{
                t('adminPages.gitlabWebhooks.sslVerification')
              }}</span>
            </label>
          </div>
        </div>
        <template #footer>
          <div class="flex w-full justify-end gap-3">
            <BaseButton variant="secondary" @click="closeWebhookModal">{{
              t('common.cancel')
            }}</BaseButton>
            <BaseButton @click="saveWebhook">{{ t('common.save') }}</BaseButton>
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
const webhooks = ref([])
const selectedWebhooks = ref([])
const selectAllWebhooks = ref(false)
const selectedGroup = ref('')
const webhookProjectFilter = ref('')
const selectedLabelIds = ref([])
const projectLabels = ref([])
const showWebhookModal = ref(false)
const showBulkWebhookModal = ref(false)
const editingWebhook = ref(null)
const bulkWebhookOperation = ref('create')
const bulkWebhookStep = ref(1)
const bulkProjectOptions = ref([])
const bulkSelectedLabelIds = ref([])
const currentPage = ref(1)
const pageSize = ref(20)
const totalCount = ref(0)

const webhookForm = ref({
  project: '',
  url: '',
  push_events: true,
  tag_push_events: false,
  merge_requests_events: false,
  enable_ssl_verification: true
})

const bulkWebhookForm = ref({
  group_ids: [],
  project_ids: [],
  url: '',
  push_events: true,
  tag_push_events: false,
  merge_requests_events: false,
  enable_ssl_verification: true
})

const toast = ref({ show: false, message: '', type: 'success' })

const currentProject = computed(() =>
  projects.value.find(
    (project) => String(project.id) === String(webhookProjectFilter.value)
  )
)

const selectedWebhookSet = computed(() => new Set(selectedWebhooks.value))

const selectedBulkWebhooks = computed(() =>
  webhooks.value.filter((hook) => selectedWebhookSet.value.has(hook.id))
)

const bulkWebhookOperations = computed(() => [
  { value: 'create', label: t('adminPages.gitlabWebhooks.operationCreate') },
  { value: 'delete', label: t('adminPages.gitlabWebhooks.operationDelete') }
])

const bulkWebhookSubmitLabel = computed(() =>
  bulkWebhookOperation.value === 'delete'
    ? t('adminPages.gitlabWebhooks.executeDelete')
    : t('adminPages.gitlabWebhooks.executeCreate')
)

const pushEnabledCount = computed(
  () => webhooks.value.filter((hook) => hook.push_events).length
)

const selectedBulkProjectSet = computed(
  () => new Set(bulkWebhookForm.value.project_ids)
)

const selectedBulkProjects = computed(() =>
  bulkProjectOptions.value.filter((project) =>
    selectedBulkProjectSet.value.has(project.id)
  )
)

const canGoToBulkWebhookProjectsStep = computed(
  () => bulkWebhookForm.value.group_ids.length > 0
)

const canGoToBulkWebhookComposeStep = computed(
  () => bulkWebhookForm.value.project_ids.length > 0
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
      t('adminPages.gitlabWebhooks.toast.loadLabelsFailed', {
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
      t('adminPages.gitlabWebhooks.toast.loadGroupsFailed', {
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
        (project) => String(project.id) === String(webhookProjectFilter.value)
      )
    ) {
      webhookProjectFilter.value = projects.value.length
        ? String(projects.value[0].id)
        : ''
    }
  } catch (e) {
    projects.value = []
    webhookProjectFilter.value = ''
    showToast(
      t('adminPages.gitlabWebhooks.toast.loadProjectsFailed', {
        message: e.message
      }),
      'error'
    )
  }
}

async function loadWebhooks() {
  if (!webhookProjectFilter.value) {
    webhooks.value = []
    totalCount.value = 0
    selectedWebhooks.value = []
    selectAllWebhooks.value = false
    return
  }
  try {
    const data = await gitlabApi.listWebhooksPage({
      page: currentPage.value,
      page_size: pageSize.value,
      project_id: webhookProjectFilter.value
    })
    webhooks.value = Array.isArray(data) ? data : (data?.results ?? [])
    totalCount.value = Array.isArray(data)
      ? data.length
      : Number(data?.count ?? webhooks.value.length)
    selectedWebhooks.value = []
    selectAllWebhooks.value = false
  } catch (e) {
    webhooks.value = []
    totalCount.value = 0
    showToast(
      t('adminPages.gitlabWebhooks.toast.loadHooksFailed', {
        message: e.message
      }),
      'error'
    )
  }
}

function handlePageSizeChange(size) {
  pageSize.value = size
  currentPage.value = 1
  loadWebhooks()
}

function goPrevPage() {
  if (currentPage.value <= 1) return
  currentPage.value -= 1
  loadWebhooks()
}

function goNextPage() {
  if (currentPage.value * pageSize.value >= totalCount.value) return
  currentPage.value += 1
  loadWebhooks()
}

async function handleGroupChange() {
  currentPage.value = 1
  webhookProjectFilter.value = ''
  webhooks.value = []
  totalCount.value = 0
  await loadProjects()
  await loadWebhooks()
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
  webhookProjectFilter.value = ''
  await loadProjects()
  await loadWebhooks()
}

function handleProjectFilterChange() {
  currentPage.value = 1
  loadWebhooks()
}

function toggleSelectAllWebhooks() {
  if (selectAllWebhooks.value) {
    selectedWebhooks.value = webhooks.value.map((hook) => hook.id)
  } else {
    selectedWebhooks.value = []
  }
}

function openBulkWebhookModal() {
  bulkWebhookOperation.value = 'create'
  bulkWebhookStep.value = 1
  bulkSelectedLabelIds.value = [...selectedLabelIds.value]
  bulkWebhookForm.value = {
    group_ids: selectedGroup.value ? [Number(selectedGroup.value)] : [],
    project_ids: webhookProjectFilter.value
      ? [Number(webhookProjectFilter.value)]
      : [],
    url: '',
    push_events: true,
    tag_push_events: false,
    merge_requests_events: false,
    enable_ssl_verification: true
  }
  bulkProjectOptions.value = [...projects.value]
  showBulkWebhookModal.value = true
}

function closeBulkWebhookModal() {
  showBulkWebhookModal.value = false
  bulkWebhookStep.value = 1
  bulkSelectedLabelIds.value = []
}

function goToBulkWebhookProjectsStep() {
  if (!canGoToBulkWebhookProjectsStep.value) return
  bulkWebhookStep.value = 2
}

function goToBulkWebhookComposeStep() {
  if (!canGoToBulkWebhookComposeStep.value) return
  bulkWebhookStep.value = 3
}

function goToPrevBulkWebhookStep() {
  bulkWebhookStep.value = Math.max(1, bulkWebhookStep.value - 1)
}

function goToNextBulkWebhookStep() {
  if (bulkWebhookStep.value === 1) {
    goToBulkWebhookProjectsStep()
    return
  }
  if (bulkWebhookStep.value === 2) {
    goToBulkWebhookComposeStep()
  }
}

function isBulkGroupSelected(groupId) {
  return bulkWebhookForm.value.group_ids.includes(Number(groupId))
}

async function toggleBulkGroup(groupId) {
  const normalizedGroupId = Number(groupId)
  const selected = bulkWebhookForm.value.group_ids
  if (selected.includes(normalizedGroupId)) {
    bulkWebhookForm.value.group_ids = selected.filter(
      (id) => id !== normalizedGroupId
    )
  } else {
    bulkWebhookForm.value.group_ids = [...selected, normalizedGroupId]
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
  bulkWebhookForm.value.project_ids = bulkProjectOptions.value.map(
    (project) => project.id
  )
}

function clearBulkProjects() {
  bulkWebhookForm.value.project_ids = []
}

function removeBulkProject(projectId) {
  bulkWebhookForm.value.project_ids = bulkWebhookForm.value.project_ids.filter(
    (id) => id !== projectId
  )
}

async function loadBulkProjectOptions() {
  const groupIds = bulkWebhookForm.value.group_ids
  if (!groupIds.length) {
    bulkProjectOptions.value = []
    bulkWebhookForm.value.project_ids = []
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
    bulkWebhookForm.value.project_ids =
      bulkWebhookForm.value.project_ids.filter((projectId) =>
        seen.has(projectId)
      )
  } catch (e) {
    bulkProjectOptions.value = []
    bulkWebhookForm.value.project_ids = []
    showToast(
      t('adminPages.gitlabWebhooks.toast.loadProjectsFailed', {
        message: e.message
      }),
      'error'
    )
  }
}

function editWebhook(hook) {
  editingWebhook.value = hook
  webhookForm.value = {
    project: hook.project,
    url: hook.url,
    push_events: hook.push_events,
    tag_push_events: hook.tag_push_events,
    merge_requests_events: hook.merge_requests_events,
    enable_ssl_verification: hook.enable_ssl_verification
  }
  showWebhookModal.value = true
}

function closeWebhookModal() {
  showWebhookModal.value = false
  editingWebhook.value = null
  webhookForm.value = {
    project: '',
    url: '',
    push_events: true,
    tag_push_events: false,
    merge_requests_events: false,
    enable_ssl_verification: true
  }
}

async function saveWebhook() {
  try {
    if (editingWebhook.value) {
      await gitlabApi.updateWebhook(editingWebhook.value.id, webhookForm.value)
      showToast(t('adminPages.gitlabWebhooks.toast.updated'))
    } else {
      await gitlabApi.createWebhook(webhookForm.value)
      showToast(t('adminPages.gitlabWebhooks.toast.created'))
    }
    closeWebhookModal()
    loadWebhooks()
  } catch (e) {
    showToast(
      t('adminPages.gitlabWebhooks.toast.saveFailed', { message: e.message }),
      'error'
    )
  }
}

async function submitBulkWebhooks() {
  if (bulkWebhookOperation.value === 'delete') {
    await bulkDeleteWebhooks()
    return
  }
  if (!bulkWebhookForm.value.project_ids.length) {
    showToast(t('adminPages.gitlabWebhooks.selectProjectError'), 'error')
    return
  }
  if (!bulkWebhookForm.value.url) {
    showToast(t('adminPages.gitlabWebhooks.inputUrlError'), 'error')
    return
  }

  const payload = {
    url: bulkWebhookForm.value.url,
    push_events: bulkWebhookForm.value.push_events,
    tag_push_events: bulkWebhookForm.value.tag_push_events,
    merge_requests_events: bulkWebhookForm.value.merge_requests_events,
    enable_ssl_verification: bulkWebhookForm.value.enable_ssl_verification
  }

  const results = await Promise.allSettled(
    bulkWebhookForm.value.project_ids.map((projectId) =>
      gitlabApi.createWebhook({
        project: projectId,
        ...payload
      })
    )
  )

  const created = results.filter(
    (result) => result.status === 'fulfilled'
  ).length
  const failed = results.length - created
  if (failed) {
    showToast(
      t('adminPages.gitlabWebhooks.toast.bulkCreateResult', {
        created,
        failed
      }),
      failed === results.length ? 'error' : 'success'
    )
  } else {
    showToast(
      t('adminPages.gitlabWebhooks.toast.bulkCreateResult', { created, failed })
    )
  }
  closeBulkWebhookModal()
  loadWebhooks()
}

async function deleteWebhook(hook) {
  requestConfirm({
    title: t('common.delete'),
    message: t('adminPages.gitlabWebhooks.deleteConfirm', { url: hook.url }),
    confirmText: t('common.delete'),
    onConfirm: async () => {
      try {
        await gitlabApi.deleteWebhook(hook.id)
        showToast(t('adminPages.gitlabWebhooks.toast.deleteSucceeded'))
        loadWebhooks()
      } catch (e) {
        showToast(
          t('adminPages.gitlabWebhooks.toast.deleteFailed', {
            message: e.message
          }),
          'error'
        )
      }
    }
  })
}

async function bulkDeleteWebhooks() {
  if (!selectedWebhooks.value.length) {
    showToast(t('adminPages.gitlabWebhooks.selectDeleteError'), 'error')
    return
  }

  requestConfirm({
    title: t('common.delete'),
    message: t('adminPages.gitlabWebhooks.bulkDeleteConfirm', {
      count: selectedWebhooks.value.length
    }),
    confirmText: t('common.delete'),
    onConfirm: async () => {
      const results = await Promise.allSettled(
        selectedWebhooks.value.map((id) => gitlabApi.deleteWebhook(id))
      )
      const deleted = results.filter(
        (result) => result.status === 'fulfilled'
      ).length
      const failed = results.length - deleted
      showToast(
        t('adminPages.gitlabWebhooks.toast.bulkDeleteResult', {
          deleted,
          failed
        }),
        failed === results.length ? 'error' : 'success'
      )
      closeBulkWebhookModal()
      selectedWebhooks.value = []
      loadWebhooks()
    }
  })
}

onMounted(async () => {
  await loadProjectLabels()
  await loadGroups()
  await loadProjects()
  await loadWebhooks()
})
</script>
