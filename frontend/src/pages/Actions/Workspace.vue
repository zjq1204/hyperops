<template>
  <AppLayout>
    <PageFrame
      :eyebrow="t('actions.workspace.eyebrow')"
      :title="t('actions.workspace.title')"
      :subtitle="t('actions.workspace.subtitle')"
    >
      <template #actions>
        <BaseButton variant="secondary" @click="refreshAll">{{
          t('actions.workspace.refresh')
        }}</BaseButton>
      </template>

      <section class="space-y-5">
        <section class="workspace-panel workspace-panel--padded">
          <div class="section-heading">
            <div>
              <h2 class="section-title">
                {{ t('actions.workspace.availableTitle') }}
              </h2>
              <p class="section-copy">
                {{ t('actions.workspace.availableHint') }}
              </p>
            </div>
          </div>

          <div
            v-if="loadingTemplates"
            class="py-12 text-center text-sm text-slate-500"
          >
            {{ t('actions.workspace.loading') }}
          </div>
          <div
            v-else-if="templates.length"
            class="workspace-list workspace-list--actions"
          >
            <div class="workspace-list__head workspace-list__head--actions">
              <span>{{ t('actions.workspace.table.template') }}</span>
              <span>{{ t('actions.workspace.table.config') }}</span>
              <span>{{ t('actions.workspace.table.actions') }}</span>
            </div>
            <article
              v-for="template in templates"
              :key="template.id"
              class="workspace-list-row workspace-list-row--actions"
            >
              <div class="workspace-list-row__main">
                <strong>{{ template.name }}</strong>
                <small>{{
                  template.description ||
                  t('actions.workspace.table.noDescription')
                }}</small>
              </div>

              <div class="workspace-list-row__meta">
                <span>{{
                  t('actions.workspace.templateMeta.steps', {
                    count: stepCount(template)
                  })
                }}</span>
                <span>{{
                  t('actions.workspace.templateMeta.parameters', {
                    count: parameterCount(template)
                  })
                }}</span>
              </div>

              <div class="workspace-list-row__actions">
                <BaseButton
                  variant="secondary"
                  size="sm"
                  @click="openPreviewModal(template)"
                  >{{ t('actions.workspace.table.preview') }}</BaseButton
                >
                <BaseButton size="sm" @click="openRunModal(template)">{{
                  t('actions.workspace.table.run')
                }}</BaseButton>
              </div>
            </article>
          </div>
          <EmptyState
            v-else
            :title="t('actions.workspace.empty.title')"
            :description="t('actions.workspace.empty.description')"
          />
        </section>
      </section>

      <BaseModal
        :show="showRunModal"
        size="lg"
        :title="
          selectedTemplate
            ? t('actions.workspace.runModal.titleWithTemplate', {
                name: selectedTemplate.name
              })
            : t('actions.workspace.runModal.titleFallback')
        "
        @close="closeRunModal"
      >
        <div v-if="selectedTemplate" class="space-y-6">
          <section
            class="rounded-lg border border-slate-200 bg-slate-50/80 p-4"
          >
            <h3 class="text-sm font-semibold text-slate-900">
              {{ t('actions.workspace.runModal.paramsTitle') }}
            </h3>
            <p class="mt-1 text-sm text-slate-500">
              {{ t('actions.workspace.runModal.paramsHint') }}
            </p>

            <div
              v-if="parameterFields.length"
              class="mt-4 grid gap-4 md:grid-cols-2"
            >
              <label
                v-for="field in parameterFields"
                :key="field.name"
                class="space-y-2"
              >
                <span class="admin-filter-label">
                  {{ field.label || field.name }}
                  <span v-if="field.required" class="text-rose-500">*</span>
                </span>
                <input
                  v-model="runParams[field.name]"
                  class="admin-filter-control"
                  :placeholder="field.default || field.name"
                />
              </label>
            </div>
            <p v-else class="mt-4 text-sm text-slate-500">
              {{ t('actions.workspace.runModal.noParams') }}
            </p>

            <label v-if="needsRuntimeProjects" class="mt-4 block space-y-2">
              <span class="admin-filter-label">{{
                t('actions.workspace.runModal.runtimeProjectsLabel')
              }}</span>
              <input
                v-model="runtimeProjectIdsText"
                class="admin-filter-control"
                :placeholder="
                  t('actions.workspace.runModal.runtimeProjectsPlaceholder')
                "
              />
            </label>
          </section>

          <section class="rounded-lg border border-slate-200 bg-white p-4">
            <h3 class="text-sm font-semibold text-slate-900">
              {{ t('actions.workspace.runModal.previewTitle') }}
            </h3>
            <ol class="mt-4 space-y-3">
              <li
                v-for="step in selectedTemplate.steps"
                :key="step.id"
                class="flex items-start gap-3 rounded-lg border border-slate-200 bg-slate-50/80 px-4 py-3"
              >
                <span
                  class="rounded-full bg-slate-900 px-2.5 py-1 text-xs font-semibold text-white"
                >
                  {{ step.order }}
                </span>
                <div class="min-w-0 flex-1">
                  <div class="font-semibold text-slate-900">
                    {{ step.name }}
                  </div>
                  <div class="mt-1 text-sm text-slate-500">
                    {{ actionTypeText(step.action_type) }} ·
                    {{
                      t(
                        step.failure_policy === 'continue'
                          ? 'actions.workspace.stepSummary.policyContinue'
                          : 'actions.workspace.stepSummary.policyStop'
                      )
                    }}
                  </div>
                </div>
              </li>
            </ol>
          </section>

          <div
            v-if="runError"
            class="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700"
          >
            {{ runError }}
          </div>
        </div>

        <template #footer>
          <div class="flex w-full justify-end gap-3">
            <BaseButton variant="secondary" @click="closeRunModal">{{
              t('actions.workspace.runModal.cancel')
            }}</BaseButton>
            <BaseButton :loading="startingRun" @click="startRun">{{
              t('actions.workspace.runModal.startRun')
            }}</BaseButton>
          </div>
        </template>
      </BaseModal>

      <BaseModal
        :show="showPreviewModal"
        size="lg"
        :title="
          previewTemplate
            ? t('actions.workspace.previewModal.titleWithTemplate', {
                name: previewTemplate.name
              })
            : t('actions.workspace.previewModal.titleFallback')
        "
        @close="closePreviewModal"
      >
        <div v-if="previewTemplate" class="action-workspace-preview">
          <section class="action-workspace-preview__summary">
            <div>
              <span>{{
                t('actions.workspace.previewModal.summarySteps')
              }}</span>
              <strong>{{ previewSteps.length }}</strong>
            </div>
            <div>
              <span>{{
                t('actions.workspace.previewModal.summaryParams')
              }}</span>
              <strong>{{ parameterCount(previewTemplate) }}</strong>
            </div>
          </section>

          <ol v-if="previewSteps.length" class="action-workspace-flow">
            <li
              v-for="step in previewSteps"
              :key="step.id || `${previewTemplate.id}-${step.order}`"
              class="action-workspace-flow__item"
            >
              <div class="action-workspace-flow__marker">
                {{ step.order }}
              </div>
              <div class="action-workspace-flow__content">
                <div class="action-workspace-flow__topline">
                  <strong>{{ step.name }}</strong>
                  <span>{{ actionTypeText(step.action_type) }}</span>
                </div>
                <p>{{ previewStepSummary(step) }}</p>
                <small>
                  {{
                    t(
                      step.failure_policy === 'continue'
                        ? 'actions.workspace.stepSummary.policyContinue'
                        : 'actions.workspace.stepSummary.policyStop'
                    )
                  }}
                </small>
              </div>
            </li>
          </ol>

          <EmptyState
            v-else
            :title="t('actions.workspace.previewModal.noStepsTitle')"
            :description="
              t('actions.workspace.previewModal.noStepsDescription')
            "
          />
        </div>

        <template #footer>
          <div class="flex w-full justify-end gap-3">
            <BaseButton variant="secondary" @click="closePreviewModal">{{
              t('actions.workspace.previewModal.close')
            }}</BaseButton>
            <BaseButton v-if="previewTemplate" @click="openRunFromPreview">{{
              t('actions.workspace.previewModal.run')
            }}</BaseButton>
          </div>
        </template>
      </BaseModal>
    </PageFrame>
  </AppLayout>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import AppLayout from '@/components/layout/AppLayout.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseModal from '@/components/ui/BaseModal.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import PageFrame from '@/components/ui/PageFrame.vue'
import actionsApi from '@/api/actions'
import { useToast } from '@/composables/useToast'

const router = useRouter()
const { t } = useI18n()
const { showToast } = useToast()
const templates = ref([])
const loadingTemplates = ref(false)
const showRunModal = ref(false)
const showPreviewModal = ref(false)
const selectedTemplate = ref(null)
const previewTemplate = ref(null)
const runParams = ref({})
const runtimeProjectIdsText = ref('')
const runError = ref('')
const startingRun = ref(false)
const parameterFields = computed(() => {
  const schema = selectedTemplate.value?.parameter_schema
  return Array.isArray(schema) ? schema.filter((item) => item?.name) : []
})

const needsRuntimeProjects = computed(() =>
  (selectedTemplate.value?.steps || []).some(
    (step) =>
      [
        'gitlab_branch_create',
        'gitlab_branch_operation',
        'gitlab_tag_operation',
        'gitlab_webhook_operation'
      ].includes(step.action_type) &&
      step.config?.allow_runtime_project_selection
  )
)

const previewSteps = computed(() =>
  sortedSteps(previewTemplate.value?.steps || [])
)

async function loadTemplates() {
  loadingTemplates.value = true
  try {
    templates.value = await actionsApi.listWorkspaceTemplates()
  } catch (error) {
    showToast(
      t('actions.workspace.runModal.toast.loadFailed', {
        message: error.message || ''
      }),
      'error'
    )
  } finally {
    loadingTemplates.value = false
  }
}

function refreshAll() {
  loadTemplates()
}

function sortedSteps(steps) {
  return [...(steps || [])].sort(
    (a, b) => (Number(a.order) || 0) - (Number(b.order) || 0)
  )
}

function stepCount(template) {
  return template?.steps?.length || 0
}

function parameterCount(template) {
  const schema = template?.parameter_schema
  return Array.isArray(schema) ? schema.filter((item) => item?.name).length : 0
}

function openPreviewModal(template) {
  previewTemplate.value = template
  showPreviewModal.value = true
}

function closePreviewModal() {
  showPreviewModal.value = false
}

function openRunFromPreview() {
  if (!previewTemplate.value) return
  const template = previewTemplate.value
  closePreviewModal()
  openRunModal(template)
}

function openRunModal(template) {
  selectedTemplate.value = template
  runParams.value = {}
  parameterFields.value.forEach((field) => {
    runParams.value[field.name] = field.default || ''
  })
  runtimeProjectIdsText.value = ''
  runError.value = ''
  showRunModal.value = true
}

function closeRunModal() {
  showRunModal.value = false
}

function parseRuntimeProjectIds() {
  return runtimeProjectIdsText.value
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean)
    .map((item) => Number(item))
    .filter((item) => Number.isFinite(item))
}

async function startRun() {
  if (!selectedTemplate.value) return
  runError.value = ''
  for (const field of parameterFields.value) {
    if (field.required && !String(runParams.value[field.name] || '').trim()) {
      runError.value = t('actions.workspace.runModal.errorParamRequired', {
        field: field.label || field.name
      })
      return
    }
  }

  const inputParams = { ...runParams.value }
  if (needsRuntimeProjects.value) {
    inputParams.project_ids = parseRuntimeProjectIds()
  }

  startingRun.value = true
  try {
    const run = await actionsApi.startRun({
      template: selectedTemplate.value.id,
      input_params: inputParams
    })
    closeRunModal()
    showToast(t('actions.workspace.runModal.toast.started'))
    router.push({ path: '/actions/runs', query: { run: run.id } })
  } catch (error) {
    runError.value =
      error.message || t('actions.workspace.runModal.toast.startFailed')
  } finally {
    startingRun.value = false
  }
}

function actionTypeText(type) {
  const map = {
    jenkins_trigger: t('actions.runs.actionTypes.jenkins_trigger'),
    gitlab_branch_create: t('actions.runs.actionTypes.gitlab_branch_create'),
    gitlab_branch_operation: t(
      'actions.runs.actionTypes.gitlab_branch_operation'
    ),
    gitlab_tag_operation: t('actions.runs.actionTypes.gitlab_tag_operation'),
    gitlab_webhook_operation: t(
      'actions.runs.actionTypes.gitlab_webhook_operation'
    ),
    manual_approval: t('actions.runs.actionTypes.manual_approval'),
    conditional_branch: t('actions.runs.actionTypes.conditional_branch')
  }
  return map[type] || type
}

function gitlabOperationText(step) {
  const operation = step.config?.operation || 'create'
  if (step.action_type === 'gitlab_branch_operation') {
    return (
      {
        create: t('actions.workspace.operations.create'),
        protect: t('actions.workspace.operations.protect'),
        unprotect: t('actions.workspace.operations.unprotect')
      }[operation] || operation
    )
  }
  if (step.action_type === 'gitlab_tag_operation')
    return t('actions.workspace.operations.tagCreate')
  if (step.action_type === 'gitlab_webhook_operation')
    return t('actions.workspace.operations.webhookCreate')
  return operation
}

function previewStepSummary(step) {
  const config = step.config || {}
  if (step.action_type === 'conditional_branch') {
    const cases = (config.branches || [])
      .map((branch) =>
        t('actions.workspace.stepSummary.branchCase', {
          condition: branchConditionText(branch),
          steps: branchNestedStepNames(branch)
        })
      )
      .join(' / ')
    return t('actions.workspace.stepSummary.conditionalBranch', {
      count: (config.branches || []).length,
      cases: cases || t('actions.workspace.stepSummary.branchDefaultSkip')
    })
  }
  if (step.action_type === 'jenkins_trigger') {
    return config.wait_for_completion
      ? t('actions.workspace.stepSummary.jenkinsWait')
      : t('actions.workspace.stepSummary.jenkinsNoWait')
  }
  if (step.action_type === 'gitlab_branch_create') {
    const branch =
      config.branch_name || t('actions.workspace.stepSummary.branchMissing')
    const ref = config.ref || t('actions.workspace.stepSummary.refDefault')
    return t('actions.workspace.stepSummary.branch', { branch, ref })
  }
  if (step.action_type === 'gitlab_branch_operation') {
    const branch =
      config.branch_name || t('actions.workspace.stepSummary.branchMissing')
    const isCreate = (config.operation || 'create') === 'create'
    const refPart = isCreate
      ? t('actions.workspace.stepSummary.branch', {
          branch: '',
          ref: config.ref || t('actions.workspace.stepSummary.refDefault')
        })
      : ''
    return t('actions.workspace.stepSummary.branchOperation', {
      operation: gitlabOperationText(step),
      branch,
      ref: refPart
    })
  }
  if (step.action_type === 'gitlab_tag_operation') {
    return t('actions.workspace.stepSummary.tagCreate', {
      tag: config.tag_name || t('actions.workspace.stepSummary.tagMissing'),
      ref: config.ref || t('actions.workspace.stepSummary.refDefault')
    })
  }
  if (step.action_type === 'gitlab_webhook_operation') {
    return t('actions.workspace.stepSummary.webhookCreate', {
      url: config.url || t('actions.workspace.stepSummary.urlMissing')
    })
  }
  if (step.action_type === 'manual_approval') {
    const userCount = (config.approver_user_ids || []).length
    const groupCount = (config.approver_group_ids || []).length
    return t('actions.workspace.stepSummary.approverSummary', {
      userCount,
      groupCount
    })
  }
  return t('actions.workspace.stepSummary.unknown')
}

function branchConditionText(branch) {
  const condition = branch?.condition || {}
  if (!condition.param)
    return t('actions.workspace.stepSummary.conditionMissing')
  if (condition.operator === 'is_empty') return `${condition.param} is empty`
  if (condition.operator === 'is_not_empty')
    return `${condition.param} is not empty`
  const operatorText =
    {
      equals: '=',
      not_equals: '!=',
      contains: 'contains'
    }[condition.operator || 'equals'] || condition.operator
  return `${condition.param} ${operatorText} ${condition.value || ''}`
}

function branchNestedStepNames(branch) {
  const names = (branch?.steps || [])
    .map(
      (nestedStep) => nestedStep.name || actionTypeText(nestedStep.action_type)
    )
    .filter(Boolean)
  return names.length
    ? names.join(', ')
    : t('actions.workspace.stepSummary.unknown')
}

onMounted(() => {
  loadTemplates()
})
</script>

<style scoped>
.action-workspace-preview {
  display: grid;
  gap: 1rem;
}

.action-workspace-preview__summary {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.75rem;
}

.action-workspace-preview__summary div {
  border: 1px solid rgba(226, 232, 240, 0.86);
  border-radius: 0.75rem;
  background: rgba(248, 250, 252, 0.8);
  padding: 1rem;
}

.action-workspace-preview__summary span {
  display: block;
  color: #64748b;
  font-size: 0.75rem;
  font-weight: 700;
}

.action-workspace-preview__summary strong {
  display: block;
  margin-top: 0.35rem;
  color: #0f172a;
  font-size: 1.35rem;
  font-weight: 700;
}

.action-workspace-flow {
  display: grid;
  gap: 0.75rem;
  margin: 0;
  padding: 0;
  list-style: none;
}

.action-workspace-flow__item {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 0.85rem;
  align-items: stretch;
}

.action-workspace-flow__marker {
  display: grid;
  width: 2.25rem;
  min-height: 2.25rem;
  place-items: center;
  border-radius: 0.75rem;
  background: #334155;
  color: #fff;
  font-size: 0.78rem;
  font-weight: 700;
}

.action-workspace-flow__content {
  border: 1px solid rgba(226, 232, 240, 0.86);
  border-radius: 0.75rem;
  background: #fff;
  padding: 0.9rem 1rem;
}

.action-workspace-flow__topline {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
}

.action-workspace-flow__topline strong {
  color: #0f172a;
  font-size: 0.92rem;
}

.action-workspace-flow__topline span {
  border-radius: 999px;
  background: #f1f5f9;
  padding: 0.25rem 0.6rem;
  color: #475569;
  font-size: 0.72rem;
  font-weight: 700;
}

.action-workspace-flow__content p {
  margin-top: 0.5rem;
  color: #475569;
  font-size: 0.84rem;
}

.action-workspace-flow__content small {
  display: block;
  margin-top: 0.45rem;
  color: #94a3b8;
  font-size: 0.75rem;
}
</style>
