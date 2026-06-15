<template>
  <AppLayout>
    <PageFrame
      eyebrow="动作编排"
      title="执行记录"
      subtitle="查看动作编排的执行状态、步骤结果和人工确认处理。"
    >
      <template #actions>
        <BaseButton variant="secondary" @click="goToWorkspace">返回工作台</BaseButton>
        <BaseButton variant="secondary" :loading="loadingRuns" @click="loadRuns">刷新</BaseButton>
      </template>

      <section class="surface-panel-strong p-6">
        <div class="section-heading">
          <div>
            <h2 class="section-title">全部记录</h2>
            <p class="section-copy">按最近发起时间排序，点击记录可查看每一步明细。</p>
          </div>
        </div>

        <div v-if="loadingRuns" class="py-12 text-center text-sm text-slate-500">
          正在加载执行记录...
        </div>

        <div v-else-if="runs.length" class="action-runs-list">
          <div class="action-runs-list__head">
            <span>模板</span>
            <span>状态</span>
            <span>当前步骤</span>
            <span>发起时间</span>
            <span>操作</span>
          </div>

          <button
            v-for="run in runs"
            :key="run.id"
            type="button"
            class="action-run-row"
            @click="openRunDetail(run)"
          >
            <span class="action-run-row__main">
              <strong>{{ run.template_name }}</strong>
              <small>#{{ run.id }} · {{ run.triggered_by_name || '-' }}</small>
            </span>
            <span>
              <span :class="runStatusClass(run.status)">
                {{ runStatusText(run.status) }}
              </span>
            </span>
            <span class="action-run-row__muted">
              {{ run.current_step_name || '-' }}
            </span>
            <span class="action-run-row__muted">
              {{ formatDate(run.created_at) }}
            </span>
            <span class="action-run-row__actions">
              查看详情
            </span>
          </button>
        </div>

        <EmptyState
          v-else
          title="暂无执行记录"
          description="从动作编排工作台执行模板后，这里会展示运行状态。"
        />
      </section>

      <BaseModal
        :show="showDetailModal"
        size="xl"
        :title="selectedRun ? `执行记录 #${selectedRun.id}` : '执行详情'"
        @close="closeDetailModal"
      >
        <div v-if="selectedRun" class="space-y-5">
          <section class="rounded-2xl border border-slate-200 bg-slate-50 p-4">
            <div class="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h3 class="text-base font-semibold text-slate-900">
                  {{ selectedRun.template_name }}
                </h3>
                <p class="mt-1 text-sm text-slate-500">
                  发起人：{{ selectedRun.triggered_by_name || '-' }} ·
                  {{ formatDate(selectedRun.created_at) }}
                </p>
              </div>
              <span :class="runStatusClass(selectedRun.status)">
                {{ runStatusText(selectedRun.status) }}
              </span>
            </div>
            <div v-if="selectedRun.error_message" class="mt-3 text-sm text-rose-600">
              {{ selectedRun.error_message }}
            </div>
          </section>

          <section class="space-y-3">
            <article
              v-for="stepRun in selectedRun.step_runs"
              :key="stepRun.id"
              class="rounded-2xl border border-slate-200 bg-white p-4"
            >
              <div class="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <div class="text-sm font-semibold text-slate-900">
                    {{ stepRun.step_order }}. {{ stepRun.step_name }}
                  </div>
                  <div class="mt-1 text-xs text-slate-500">
                    {{ actionTypeText(stepRun.action_type) }}
                    <span v-if="stepRun.jenkins_record_id">
                      · Jenkins 记录 #{{ stepRun.jenkins_record_id }}
                    </span>
                  </div>
                </div>
                <span :class="stepStatusClass(stepRun.status)">
                  {{ stepStatusText(stepRun.status) }}
                </span>
              </div>
              <pre
                v-if="Object.keys(stepRun.output || {}).length"
                class="mt-3 max-h-40 overflow-auto rounded-xl bg-slate-950 p-3 text-xs text-slate-100"
              >{{ JSON.stringify(stepRun.output, null, 2) }}</pre>
              <div v-if="stepRun.error_message" class="mt-3 text-sm text-rose-600">
                {{ stepRun.error_message }}
              </div>
            </article>
          </section>

          <section
            v-if="selectedRun.status === 'waiting_approval'"
            class="rounded-2xl border border-amber-200 bg-amber-50 p-4"
          >
            <h3 class="text-sm font-semibold text-amber-900">等待人工确认</h3>
            <textarea
              v-model="approvalComment"
              rows="2"
              class="mt-3 w-full rounded-xl border border-amber-200 bg-white px-4 py-3 text-sm outline-none focus:border-amber-400"
              placeholder="可选：填写确认说明"
            ></textarea>
            <div class="mt-3 flex justify-end gap-3">
              <BaseButton
                variant="danger"
                size="sm"
                :loading="approvalLoading === 'reject'"
                @click="rejectRun"
              >
                驳回
              </BaseButton>
              <BaseButton
                size="sm"
                :loading="approvalLoading === 'approve'"
                @click="approveRun"
              >
                确认继续
              </BaseButton>
            </div>
          </section>
        </div>

        <template #footer>
          <div class="flex w-full justify-end gap-3">
            <BaseButton variant="secondary" @click="refreshSelectedRun">
              刷新详情
            </BaseButton>
            <BaseButton @click="closeDetailModal">关闭</BaseButton>
          </div>
        </template>
      </BaseModal>

      <div
        v-if="toast.show"
        :class="[
          'fixed bottom-5 right-5 z-[90] rounded-2xl px-4 py-3 text-sm font-medium text-white shadow-2xl',
          toast.type === 'success' ? 'bg-emerald-600' : 'bg-rose-600'
        ]"
      >
        {{ toast.message }}
      </div>
    </PageFrame>
  </AppLayout>
</template>

<script setup>
import { onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppLayout from '@/components/layout/AppLayout.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseModal from '@/components/ui/BaseModal.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import PageFrame from '@/components/ui/PageFrame.vue'
import actionsApi from '@/api/actions'

const route = useRoute()
const router = useRouter()
const runs = ref([])
const loadingRuns = ref(false)
const showDetailModal = ref(false)
const selectedRun = ref(null)
const approvalComment = ref('')
const approvalLoading = ref('')
const toast = ref({ show: false, message: '', type: 'success' })

function showToast(message, type = 'success') {
  toast.value = { show: true, message, type }
  setTimeout(() => {
    toast.value.show = false
  }, 2600)
}

function normalizeList(payload) {
  if (Array.isArray(payload)) return payload
  if (payload?.results) return payload.results
  return []
}

async function loadRuns() {
  loadingRuns.value = true
  try {
    runs.value = normalizeList(await actionsApi.listRuns())
  } catch (error) {
    showToast(error.message || '加载执行记录失败', 'error')
  } finally {
    loadingRuns.value = false
  }
}

function goToWorkspace() {
  router.push('/actions/workspace')
}

async function openRunDetail(run) {
  try {
    selectedRun.value = await actionsApi.getRun(run.id)
    approvalComment.value = ''
    showDetailModal.value = true
  } catch (error) {
    showToast(error.message || '加载执行详情失败', 'error')
  }
}

function closeDetailModal() {
  showDetailModal.value = false
  if (route.query.run) {
    router.replace({ path: '/actions/runs' })
  }
}

async function refreshSelectedRun() {
  if (!selectedRun.value) return
  selectedRun.value = await actionsApi.getRun(selectedRun.value.id)
  await loadRuns()
}

async function approveRun() {
  if (!selectedRun.value) return
  approvalLoading.value = 'approve'
  try {
    selectedRun.value = await actionsApi.approveRun(
      selectedRun.value.id,
      approvalComment.value
    )
    showToast('已确认继续执行')
    await loadRuns()
  } catch (error) {
    showToast(error.message || '确认失败', 'error')
  } finally {
    approvalLoading.value = ''
  }
}

async function rejectRun() {
  if (!selectedRun.value) return
  approvalLoading.value = 'reject'
  try {
    selectedRun.value = await actionsApi.rejectRun(
      selectedRun.value.id,
      approvalComment.value
    )
    showToast('已驳回执行')
    await loadRuns()
  } catch (error) {
    showToast(error.message || '驳回失败', 'error')
  } finally {
    approvalLoading.value = ''
  }
}

async function openRunFromQuery() {
  const runId = Number(route.query.run)
  if (!Number.isFinite(runId)) return
  await openRunDetail({ id: runId })
}

function actionTypeText(type) {
  const map = {
    jenkins_trigger: '触发 Jenkins',
    gitlab_branch_create: '新增 GitLab 分支',
    gitlab_branch_operation: 'GitLab 分支操作',
    gitlab_tag_operation: 'GitLab 标签操作',
    gitlab_webhook_operation: 'GitLab Webhook 操作',
    manual_approval: '人工确认'
  }
  return map[type] || type
}

function runStatusText(status) {
  const map = {
    queued: '排队中',
    running: '执行中',
    waiting_approval: '待确认',
    success: '成功',
    failed: '失败',
    rejected: '已驳回'
  }
  return map[status] || status
}

function runStatusClass(status) {
  if (status === 'success') return 'status-pill-success'
  if (status === 'failed' || status === 'rejected') return 'status-pill-danger'
  if (status === 'waiting_approval') return 'status-pill-warning'
  return 'status-pill-neutral'
}

function stepStatusText(status) {
  const map = {
    pending: '等待中',
    running: '执行中',
    waiting_approval: '待确认',
    success: '成功',
    failed: '失败',
    skipped: '已跳过',
    rejected: '已驳回'
  }
  return map[status] || status
}

function stepStatusClass(status) {
  if (status === 'success') return 'status-pill-success'
  if (status === 'failed' || status === 'rejected') return 'status-pill-danger'
  if (status === 'running' || status === 'waiting_approval') {
    return 'status-pill-warning'
  }
  return 'status-pill-neutral'
}

function formatDate(value) {
  if (!value) return '-'
  return new Date(value).toLocaleString()
}

watch(
  () => route.query.run,
  () => {
    openRunFromQuery()
  }
)

onMounted(async () => {
  await loadRuns()
  await openRunFromQuery()
})
</script>

<style scoped>
.action-runs-list {
  margin-top: 1rem;
  overflow: hidden;
  border: 1px solid #e2e8f0;
  border-radius: 1.25rem;
  background: #fff;
}

.action-runs-list__head,
.action-run-row {
  display: grid;
  grid-template-columns: minmax(16rem, 1fr) minmax(7rem, auto) minmax(10rem, 0.8fr) minmax(12rem, auto) auto;
  align-items: center;
  gap: 1rem;
}

.action-runs-list__head {
  padding: 0.85rem 1rem;
  border-bottom: 1px solid #e2e8f0;
  background: #f8fafc;
  color: #64748b;
  font-size: 0.72rem;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.action-run-row {
  width: 100%;
  padding: 1rem;
  text-align: left;
  transition: background 0.18s ease, box-shadow 0.18s ease;
}

.action-run-row + .action-run-row {
  border-top: 1px solid #eef2f7;
}

.action-run-row:hover {
  background: #fbfdff;
  box-shadow: inset 3px 0 0 #0f766e;
}

.action-run-row__main {
  min-width: 0;
}

.action-run-row__main strong,
.action-run-row__main small {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.action-run-row__main strong {
  color: #0f172a;
  font-size: 0.95rem;
  font-weight: 800;
}

.action-run-row__main small,
.action-run-row__muted {
  color: #64748b;
  font-size: 0.82rem;
}

.action-run-row__main small {
  margin-top: 0.3rem;
}

.action-run-row__actions {
  justify-self: end;
  color: #0f766e;
  font-size: 0.82rem;
  font-weight: 800;
}

@media (max-width: 900px) {
  .action-runs-list__head {
    display: none;
  }

  .action-runs-list {
    border: 0;
    border-radius: 0;
    background: transparent;
  }

  .action-run-row {
    grid-template-columns: 1fr;
    border: 1px solid #e2e8f0;
    border-radius: 1.1rem;
    background: #fff;
  }

  .action-run-row + .action-run-row {
    margin-top: 0.75rem;
    border-top: 1px solid #e2e8f0;
  }

  .action-run-row__actions {
    justify-self: start;
  }
}
</style>
