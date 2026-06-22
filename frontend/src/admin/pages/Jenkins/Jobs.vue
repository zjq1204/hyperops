<template>
  <AdminLayout>
    <PageFrame
      variant="soft"
      :eyebrow="t('adminPages.jenkinsJobs.eyebrow')"
      :title="t('adminPages.jenkinsJobs.title')"
      :subtitle="t('adminPages.jenkinsJobs.subtitle')"
    >
      <section class="admin-job-filter admin-job-filter--toolbar">
        <div class="admin-job-filter__topbar">
          <div class="admin-job-filter__primary">
            <div
              class="admin-job-filter__field admin-job-filter__field--instance"
            >
              <span class="admin-job-filter__field-label">
                {{ t('adminPages.jenkinsJobs.selectInstance') }}
              </span>
              <div class="admin-filter-control-shell">
                <svg
                  class="admin-filter-control-icon"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    stroke-width="2"
                    d="M5 12h14M5 6h14M5 18h7"
                  />
                </svg>
                <select
                  v-model="selectedInstanceId"
                  class="admin-filter-control admin-filter-control--with-icon"
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
            </div>

            <div
              class="admin-job-filter__field admin-job-filter__field--search"
            >
              <span class="admin-job-filter__field-label">
                {{ t('adminPages.jenkinsJobs.search') }}
              </span>
              <div class="admin-filter-control-shell">
                <svg
                  class="admin-filter-control-icon"
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
                  class="admin-filter-control admin-filter-control--with-icon"
                />
              </div>
            </div>

            <div class="admin-job-filter__mode" role="group">
              <span class="admin-job-filter__field-label">
                {{ t('adminPages.jenkinsJobs.displayMode') }}
              </span>
              <div class="admin-job-filter__mode-control">
                <button
                  type="button"
                  class="admin-job-filter__mode-option"
                  :class="{ 'is-active': showEnabledOnly }"
                  @click="showEnabledOnly = true"
                >
                  {{ t('adminPages.jenkinsJobs.showingEnabledOnly') }}
                </button>
                <button
                  type="button"
                  class="admin-job-filter__mode-option"
                  :class="{ 'is-active': !showEnabledOnly }"
                  @click="showEnabledOnly = false"
                >
                  {{ t('adminPages.jenkinsJobs.showingAllJobs') }}
                </button>
              </div>
            </div>
          </div>
        </div>

        <div class="admin-job-filter__labelbar">
          <div class="admin-job-filter__label-head">
            <span class="admin-job-filter__field-label">
              {{ t('adminPages.jenkinsJobs.filterByLabel') }}
            </span>
            <button
              type="button"
              class="admin-filter-manage-link"
              @click="openLabelLibraryModal"
            >
              <svg
                class="h-3.5 w-3.5"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="2"
                  d="M7 7h.01M7 3h5a1.99 1.99 0 011.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A2 2 0 013 12V7a4 4 0 014-4z"
                />
              </svg>
              {{ t('adminPages.jenkinsJobs.manageLabels') }}
            </button>
            <button
              v-if="resourceLabels.length"
              type="button"
              class="admin-bulk-label-start"
              @click="startBulkAddMode"
            >
              <svg
                class="h-3.5 w-3.5"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="2"
                  d="M12 5v14m7-7H5"
                />
              </svg>
              {{ t('adminPages.jenkinsJobs.bulkAddCurrentLabel') }}
            </button>
          </div>
          <div v-if="resourceLabels.length" class="admin-tag-filter-list">
            <button
              v-for="label in resourceLabels"
              :key="label.id"
              type="button"
              class="admin-tag-filter-chip"
              :class="{
                'is-active': selectedLabelIds.includes(label.id)
              }"
              @click="toggleLabelFilter(label.id)"
            >
              <span class="admin-tag-filter-chip__check">
                <svg
                  v-if="selectedLabelIds.includes(label.id)"
                  class="h-3 w-3"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    stroke-width="3"
                    d="M5 13l4 4L19 7"
                  />
                </svg>
              </span>
              {{ label.name }}
            </button>
          </div>
          <button
            v-else
            type="button"
            class="admin-labels-empty-inline"
            @click="openLabelLibraryModal"
          >
            {{ t('adminPages.jenkinsJobs.noResourceLabels') }}
          </button>
        </div>
      </section>
      <section v-if="loadingJobs" class="admin-job-loading-panel">
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

      <section v-else class="admin-job-workbench-grid">
        <article class="admin-job-workbench-panel">
          <div class="admin-job-panel-head">
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

          <div v-if="bulkAddMode" class="admin-job-bulk-bar">
            <label class="admin-job-bulk-target">
              <span>{{
                t('adminPages.jenkinsJobs.bulkTargetLabelPlain')
              }}</span>
              <select v-model="bulkTargetLabelId">
                <option
                  v-for="label in resourceLabels"
                  :key="label.id"
                  :value="label.id"
                >
                  {{ label.name }}
                </option>
              </select>
            </label>
            <label class="admin-job-bulk-select-all">
              <input
                type="checkbox"
                :checked="allFilteredBulkJobsSelected"
                @change="toggleSelectAllFilteredJobs"
              />
              <span>{{ t('adminPages.jenkinsJobs.bulkSelectVisible') }}</span>
            </label>
            <div class="admin-job-bulk-summary">
              <strong>
                {{
                  t('adminPages.jenkinsJobs.bulkSelectedCount', {
                    count: bulkSelectedJobNames.length
                  })
                }}
              </strong>
              <span>
                {{
                  t('adminPages.jenkinsJobs.bulkTargetLabel', {
                    name: selectedBulkTargetLabel?.name || ''
                  })
                }}
              </span>
              <span>
                {{
                  t('adminPages.jenkinsJobs.bulkSelectableCount', {
                    count: bulkSelectableFilteredJobs.length
                  })
                }}
              </span>
            </div>
            <div class="admin-job-bulk-actions">
              <BaseButton
                size="sm"
                :loading="bulkApplying"
                :disabled="!bulkSelectedJobNames.length || bulkApplying"
                @click="applyBulkAddLabel"
              >
                {{ t('adminPages.jenkinsJobs.bulkApply') }}
              </BaseButton>
              <BaseButton
                size="sm"
                variant="outline"
                :disabled="bulkApplying"
                @click="cancelBulkAddMode"
              >
                {{ t('common.cancel') }}
              </BaseButton>
            </div>
          </div>

          <div class="admin-job-list-scroll">
            <button
              v-for="job in filteredJobs"
              :key="job.full_name"
              type="button"
              class="admin-job-list-item"
              :class="
                isBulkJobSelected(job)
                  ? 'admin-job-list-item--bulk-selected'
                  : selectedJob?.full_name === job.full_name
                    ? 'admin-job-list-item--selected'
                    : job.enabled === false
                      ? 'admin-job-list-item--disabled'
                      : 'admin-job-list-item--default'
              "
              @click="selectJob(job)"
            >
              <div
                class="flex w-full min-w-0 items-start gap-4"
                :style="{ paddingLeft: `${job.depth * 1.1}rem` }"
              >
                <label
                  v-if="bulkAddMode && !job.has_children"
                  class="admin-job-bulk-checkbox"
                  :class="{ 'is-disabled': isBulkJobAlreadyTagged(job) }"
                  @click.stop
                >
                  <input
                    type="checkbox"
                    :checked="isBulkJobSelected(job)"
                    :disabled="isBulkJobAlreadyTagged(job)"
                    @change="toggleBulkJobSelection(job)"
                  />
                </label>
                <div
                  class="admin-job-type-icon"
                  :class="
                    job.has_children
                      ? 'admin-job-type-icon--folder'
                      : 'admin-job-type-icon--job'
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
                    <button
                      v-if="!job.has_children"
                      type="button"
                      class="admin-job-quick-icon"
                      :title="t('adminPages.jenkinsJobs.editLabel')"
                      :aria-label="t('adminPages.jenkinsJobs.editLabel')"
                      @click.stop="openEditJobLabelsModal(job)"
                    >
                      <svg
                        class="h-3.5 w-3.5"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path
                          stroke-linecap="round"
                          stroke-linejoin="round"
                          stroke-width="2"
                          d="M7 7h.01M3 11l8.586-8.586a2 2 0 012.828 0L20 8l-9 9H3v-6z"
                        />
                      </svg>
                    </button>
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
                  <div
                    v-if="job.labels?.length"
                    class="admin-project-tag-list mt-2"
                  >
                    <span
                      v-for="label in job.labels"
                      :key="label.id"
                      class="admin-project-tag-chip"
                    >
                      {{ label.name }}
                    </span>
                  </div>
                  <p
                    v-else-if="!job.has_children"
                    class="admin-project-tag-empty mt-2"
                  >
                    {{ t('adminPages.jenkinsJobs.jobLabelsEmpty') }}
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
          class="admin-job-workbench-panel admin-job-workbench-panel--detail"
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

            <div class="admin-job-detail-grid">
              <div class="admin-job-detail-card">
                <p class="admin-job-detail-label">
                  {{ t('adminPages.jenkinsJobs.detailPath') }}
                </p>
                <p class="mt-2 break-all font-mono text-sm text-slate-700">
                  {{ selectedJob.full_name }}
                </p>
              </div>
              <div class="admin-job-detail-card">
                <p class="admin-job-detail-label">
                  {{ t('adminPages.jenkinsJobs.detailType') }}
                </p>
                <p class="mt-2 text-sm font-medium text-slate-700">
                  {{ selectedJob.type }}
                </p>
              </div>
              <div class="admin-job-detail-card">
                <p class="admin-job-detail-label">
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
              <div class="admin-job-detail-card">
                <p class="admin-job-detail-label">
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
                class="admin-job-detail-card"
              >
                <p class="admin-job-detail-label">
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
                class="admin-job-detail-card"
              >
                <p class="admin-job-detail-label">
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

            <div class="admin-job-detail-note">
              <p class="admin-job-detail-label">
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
          'admin-toast',
          toast.type === 'success'
            ? 'admin-toast--success'
            : 'admin-toast--error'
        ]"
      >
        {{ toast.message }}
      </div>
    </PageFrame>

    <BaseModal
      :show="showLabelLibraryModal"
      :title="t('adminPages.jenkinsJobs.labelLibraryTitle')"
      size="md"
      @close="closeLabelLibraryModal"
    >
      <div class="admin-modal-stack">
        <section class="admin-modal-card">
          <label class="admin-modal-field-label">
            {{ t('adminPages.jenkinsJobs.labelName') }}
          </label>
          <div class="admin-modal-inline-field">
            <input
              v-model="labelDraft.name"
              type="text"
              class="admin-modal-control"
              :placeholder="t('adminPages.jenkinsJobs.labelNamePlaceholder')"
            />
            <BaseButton @click="saveResourceLabel">
              {{
                editingLabel
                  ? t('adminPages.jenkinsJobs.editLabel')
                  : t('adminPages.jenkinsJobs.createLabel')
              }}
            </BaseButton>
          </div>
          <p class="admin-bulk-input-hint">
            {{ t('adminPages.jenkinsJobs.labelLibraryHint') }}
          </p>
        </section>

        <section class="admin-modal-card">
          <div class="section-heading settings-section-heading-compact">
            <div>
              <h3 class="section-title">
                {{ t('adminPages.jenkinsJobs.labelLibraryListTitle') }}
              </h3>
              <p class="section-copy">
                {{ t('adminPages.jenkinsJobs.labelLibraryListHint') }}
              </p>
            </div>
          </div>
          <div v-if="resourceLabels.length" class="space-y-3">
            <div
              v-for="label in resourceLabels"
              :key="label.id"
              class="admin-label-library-item"
            >
              <div class="min-w-0">
                <div class="admin-project-tag-list">
                  <span class="admin-project-tag-chip">{{ label.name }}</span>
                </div>
                <p class="mt-2 text-xs text-slate-500">
                  {{
                    t('adminPages.jenkinsJobs.labelUsageCount', {
                      count: label.job_count ?? 0
                    })
                  }}
                </p>
              </div>
              <div class="admin-row-actions">
                <button
                  class="admin-row-action admin-row-action--primary"
                  @click="startEditLabel(label)"
                >
                  {{ t('common.edit') }}
                </button>
                <button
                  class="admin-row-action admin-row-action--danger"
                  @click="deleteResourceLabel(label)"
                >
                  {{ t('common.delete') }}
                </button>
              </div>
            </div>
          </div>
          <p v-else class="admin-project-tag-empty">
            {{ t('adminPages.jenkinsJobs.noLabelLibraryData') }}
          </p>
        </section>
      </div>
    </BaseModal>

    <BaseModal
      :show="showEditJobLabelsModal"
      :title="t('adminPages.jenkinsJobs.editJobLabelsTitle')"
      size="sm"
      @close="closeEditJobLabelsModal"
    >
      <div class="admin-modal-stack">
        <p v-if="jobLabelsTarget" class="text-sm text-slate-600">
          <span class="font-mono">{{ jobLabelsTarget.full_name }}</span>
        </p>
        <p class="admin-bulk-input-hint">
          {{ t('adminPages.jenkinsJobs.editJobLabelsHint') }}
        </p>
        <div v-if="resourceLabels.length" class="admin-tag-filter-list">
          <button
            v-for="label in resourceLabels"
            :key="label.id"
            type="button"
            class="admin-tag-filter-chip"
            :class="{
              'is-active': jobLabelsDraft.includes(label.id)
            }"
            @click="toggleJobLabelDraft(label.id)"
          >
            {{ label.name }}
          </button>
        </div>
        <p v-else class="admin-project-tag-empty">
          {{ t('adminPages.jenkinsJobs.noResourceLabels') }}
        </p>
      </div>
      <template #footer>
        <div class="flex flex-wrap justify-end gap-3">
          <BaseButton variant="outline" @click="closeEditJobLabelsModal">
            {{ t('common.cancel') }}
          </BaseButton>
          <BaseButton @click="saveJobLabels">
            {{ t('common.save') }}
          </BaseButton>
        </div>
      </template>
    </BaseModal>
  </AdminLayout>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import AdminLayout from '@/admin/layout/AdminLayout.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseModal from '@/components/ui/BaseModal.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
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
const showEnabledOnly = ref(true)
const resourceLabels = ref([])
const selectedLabelIds = ref([])
const showLabelLibraryModal = ref(false)
const labelDraft = ref({ name: '' })
const editingLabel = ref(null)
const showEditJobLabelsModal = ref(false)
const jobLabelsTarget = ref(null)
const jobLabelsDraft = ref([])
const bulkAddMode = ref(false)
const bulkTargetLabelId = ref(null)
const bulkSelectedJobNames = ref([])
const bulkApplying = ref(false)

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

const visibleJobs = computed(() => {
  const labelSet = new Set(selectedLabelIds.value)
  let jobs = allJobsFlat.value

  if (labelSet.size) {
    jobs = jobs.filter(
      (job) =>
        !job.has_children &&
        Array.isArray(job.labels) &&
        job.labels.some((label) => labelSet.has(label.id))
    )
  }

  if (!showEnabledOnly.value) return jobs

  return jobs.filter((job) => {
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

const selectedBulkTargetLabel = computed(() => {
  return (
    resourceLabels.value.find(
      (label) => label.id === bulkTargetLabelId.value
    ) || null
  )
})

const bulkSelectableFilteredJobs = computed(() =>
  filteredJobs.value.filter((job) => {
    if (job.has_children) return false
    if (!bulkTargetLabelId.value) return true
    return !(job.labels || []).some(
      (label) => label.id === bulkTargetLabelId.value
    )
  })
)

const allFilteredBulkJobsSelected = computed(() => {
  const selectableNames = bulkSelectableFilteredJobs.value.map(
    (job) => job.full_name
  )
  if (!selectableNames.length) return false
  return selectableNames.every((fullName) =>
    bulkSelectedJobNames.value.includes(fullName)
  )
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
    return
  }

  loadingJobs.value = true
  try {
    const data = await jenkinsApi.listJobs(selectedInstanceId.value, options)
    jobsTree.value = data.jobs || []
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

function updateJobLabelsInTree(fullNames, labels) {
  const targetNames = new Set(fullNames)
  const walk = (nodes) => {
    for (const node of nodes || []) {
      if (targetNames.has(node.full_name)) {
        node.labels = labels
      }
      if (node.children?.length) {
        walk(node.children)
      }
    }
  }
  walk(jobsTree.value)
}

function startBulkAddMode() {
  if (!resourceLabels.value.length) {
    showToast(t('adminPages.jenkinsJobs.toast.selectOneLabelForBulk'), 'error')
    return
  }
  bulkTargetLabelId.value =
    selectedLabelIds.value.length === 1
      ? selectedLabelIds.value[0]
      : resourceLabels.value[0]?.id || null
  bulkSelectedJobNames.value = []
  bulkAddMode.value = true
  removeBulkTargetFromFilters()
}

function cancelBulkAddMode() {
  bulkAddMode.value = false
  bulkTargetLabelId.value = null
  bulkSelectedJobNames.value = []
  bulkApplying.value = false
}

function isBulkJobSelected(job) {
  return bulkSelectedJobNames.value.includes(job.full_name)
}

function isBulkJobAlreadyTagged(job) {
  if (!bulkTargetLabelId.value) return false
  return (job.labels || []).some(
    (label) => label.id === bulkTargetLabelId.value
  )
}

function toggleBulkJobSelection(job) {
  if (job.has_children) return
  if (isBulkJobAlreadyTagged(job)) return
  if (bulkSelectedJobNames.value.includes(job.full_name)) {
    bulkSelectedJobNames.value = bulkSelectedJobNames.value.filter(
      (fullName) => fullName !== job.full_name
    )
    return
  }
  bulkSelectedJobNames.value = [...bulkSelectedJobNames.value, job.full_name]
}

function toggleSelectAllFilteredJobs() {
  const selectableNames = bulkSelectableFilteredJobs.value.map(
    (job) => job.full_name
  )
  if (allFilteredBulkJobsSelected.value) {
    const visibleSet = new Set(selectableNames)
    bulkSelectedJobNames.value = bulkSelectedJobNames.value.filter(
      (fullName) => !visibleSet.has(fullName)
    )
    return
  }
  bulkSelectedJobNames.value = Array.from(
    new Set([...bulkSelectedJobNames.value, ...selectableNames])
  )
}

function pruneBulkSelectedJobs() {
  const selectableNames = new Set(
    bulkSelectableFilteredJobs.value.map((job) => job.full_name)
  )
  bulkSelectedJobNames.value = bulkSelectedJobNames.value.filter((fullName) =>
    selectableNames.has(fullName)
  )
}

function removeBulkTargetFromFilters() {
  if (!bulkTargetLabelId.value) return
  selectedLabelIds.value = selectedLabelIds.value.filter(
    (labelId) => labelId !== bulkTargetLabelId.value
  )
}

async function applyBulkAddLabel() {
  if (!selectedInstanceId.value || !bulkTargetLabelId.value) return
  if (!bulkSelectedJobNames.value.length) {
    showToast(t('adminPages.jenkinsJobs.toast.selectJobsForBulk'), 'error')
    return
  }

  const targetLabel = resourceLabels.value.find(
    (label) => label.id === bulkTargetLabelId.value
  )
  if (!targetLabel) {
    showToast(t('adminPages.jenkinsJobs.toast.selectOneLabelForBulk'), 'error')
    return
  }

  bulkApplying.value = true
  try {
    await jenkinsApi.bulkAddJobLabel(
      selectedInstanceId.value,
      bulkTargetLabelId.value,
      bulkSelectedJobNames.value
    )
    const selectedNames = [...bulkSelectedJobNames.value]
    const updatedLabelSets = new Map()
    for (const job of allJobsFlat.value) {
      if (!selectedNames.includes(job.full_name)) continue
      const labels = Array.isArray(job.labels) ? [...job.labels] : []
      if (!labels.some((label) => label.id === targetLabel.id)) {
        labels.push(targetLabel)
      }
      updatedLabelSets.set(job.full_name, labels)
    }
    for (const [fullName, labels] of updatedLabelSets.entries()) {
      updateJobLabelsInTree([fullName], labels)
    }
    showToast(
      t('adminPages.jenkinsJobs.toast.bulkLabelsUpdated', {
        count: selectedNames.length,
        name: targetLabel.name
      })
    )
    await loadResourceLabels()
    cancelBulkAddMode()
  } catch (e) {
    showToast(
      t('adminPages.jenkinsJobs.toast.bulkLabelsUpdateFailed', {
        message: e.message
      }),
      'error'
    )
  } finally {
    bulkApplying.value = false
  }
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

watch(
  [filteredJobs, bulkTargetLabelId],
  () => {
    if (bulkAddMode.value) {
      removeBulkTargetFromFilters()
      pruneBulkSelectedJobs()
    }
  },
  { flush: 'post' }
)

function toggleLabelFilter(labelId) {
  if (selectedLabelIds.value.includes(labelId)) {
    selectedLabelIds.value = selectedLabelIds.value.filter(
      (id) => id !== labelId
    )
  } else {
    selectedLabelIds.value = [...selectedLabelIds.value, labelId]
  }
  if (bulkAddMode.value) {
    removeBulkTargetFromFilters()
  }
}

async function loadResourceLabels() {
  try {
    resourceLabels.value = await jenkinsApi.listResourceLabels()
  } catch (e) {
    resourceLabels.value = []
    showToast(
      t('adminPages.jenkinsJobs.toast.loadLabelsFailed', {
        message: e.message
      }),
      'error'
    )
  }
}

function openLabelLibraryModal() {
  editingLabel.value = null
  labelDraft.value = { name: '' }
  showLabelLibraryModal.value = true
}

function closeLabelLibraryModal() {
  showLabelLibraryModal.value = false
  editingLabel.value = null
  labelDraft.value = { name: '' }
}

function startEditLabel(label) {
  editingLabel.value = label
  labelDraft.value = { name: label.name }
}

async function saveResourceLabel() {
  const name = labelDraft.value.name.trim()
  if (!name) {
    showToast(t('adminPages.jenkinsJobs.toast.inputLabelNameError'), 'error')
    return
  }
  try {
    if (editingLabel.value) {
      await jenkinsApi.updateResourceLabel(editingLabel.value.id, { name })
      showToast(t('adminPages.jenkinsJobs.toast.labelUpdated'))
    } else {
      await jenkinsApi.createResourceLabel({ name })
      showToast(t('adminPages.jenkinsJobs.toast.labelCreated'))
    }
    await loadResourceLabels()
    editingLabel.value = null
    labelDraft.value = { name: '' }
  } catch (e) {
    showToast(
      t('adminPages.jenkinsJobs.toast.saveLabelFailed', { message: e.message }),
      'error'
    )
  }
}

async function deleteResourceLabel(label) {
  if (
    !window.confirm(
      t('adminPages.jenkinsJobs.toast.deleteLabelConfirm', { name: label.name })
    )
  ) {
    return
  }
  try {
    await jenkinsApi.deleteResourceLabel(label.id)
    selectedLabelIds.value = selectedLabelIds.value.filter(
      (id) => id !== label.id
    )
    showToast(t('adminPages.jenkinsJobs.toast.labelDeleted'))
    await loadResourceLabels()
  } catch (e) {
    showToast(
      t('adminPages.jenkinsJobs.toast.saveLabelFailed', { message: e.message }),
      'error'
    )
  }
}

function openEditJobLabelsModal(job) {
  jobLabelsTarget.value = job
  jobLabelsDraft.value = (job.labels || []).map((label) => label.id)
  showEditJobLabelsModal.value = true
}

function closeEditJobLabelsModal() {
  showEditJobLabelsModal.value = false
  jobLabelsTarget.value = null
  jobLabelsDraft.value = []
}

function toggleJobLabelDraft(labelId) {
  if (jobLabelsDraft.value.includes(labelId)) {
    jobLabelsDraft.value = jobLabelsDraft.value.filter((id) => id !== labelId)
  } else {
    jobLabelsDraft.value = [...jobLabelsDraft.value, labelId]
  }
}

async function saveJobLabels() {
  if (!jobLabelsTarget.value || !selectedInstanceId.value) return
  try {
    await jenkinsApi.assignJobLabels(
      selectedInstanceId.value,
      jobLabelsTarget.value.full_name,
      jobLabelsDraft.value
    )
    const labels = resourceLabels.value.filter((label) =>
      jobLabelsDraft.value.includes(label.id)
    )
    updateJobLabelsInTree([jobLabelsTarget.value.full_name], labels)
    showToast(t('adminPages.jenkinsJobs.toast.labelsUpdated'))
    closeEditJobLabelsModal()
  } catch (e) {
    showToast(
      t('adminPages.jenkinsJobs.toast.labelsUpdateFailed', {
        message: e.message
      }),
      'error'
    )
  }
}

onMounted(async () => {
  await loadInstances()
  await loadResourceLabels()
})
</script>
