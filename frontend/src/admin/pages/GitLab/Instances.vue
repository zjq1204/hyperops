<template>
  <AdminLayout>
    <PageFrame
      variant="soft"
      :eyebrow="t('adminPages.gitlabInstances.eyebrow')"
      :title="t('adminPages.gitlabInstances.title')"
      :subtitle="t('adminPages.gitlabInstances.subtitle')"
    >
      <template #actions>
        <BaseButton @click="openCreateInstanceModal">{{
          t('adminPages.gitlabInstances.add')
        }}</BaseButton>
      </template>

      <AdminListSection>
        <section v-if="instances.length" class="admin-instance-grid">
          <article
            v-for="inst in instances"
            :key="inst.id"
            class="admin-instance-card"
          >
            <div class="admin-instance-card-head">
              <div class="admin-instance-identity">
                <div
                  :class="[
                    'admin-instance-icon',
                    inst.is_active
                      ? 'admin-instance-icon--gitlab-active'
                      : 'admin-instance-icon--inactive'
                  ]"
                >
                  <svg
                    class="h-6 w-6"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      stroke-linecap="round"
                      stroke-linejoin="round"
                      stroke-width="2"
                      d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4"
                    />
                  </svg>
                </div>
                <div class="min-w-0">
                  <h3 class="admin-instance-title">
                    {{ inst.name }}
                  </h3>
                </div>
              </div>
              <span
                :class="
                  inst.is_active
                    ? 'admin-status-badge admin-status-badge--success'
                    : 'admin-status-badge admin-status-badge--muted'
                "
              >
                {{
                  inst.is_active ? t('common.enabled') : t('common.disabled')
                }}
              </span>
            </div>

            <div class="admin-instance-detail-card">
              <div class="admin-instance-detail-label">
                {{ t('common.url') }}
              </div>
              <div class="admin-instance-detail-value">
                {{ inst.url }}
              </div>
            </div>

            <div class="admin-instance-actions">
              <button
                type="button"
                class="admin-instance-action admin-instance-action-primary"
                @click="testGitLabConnection(inst)"
              >
                <svg
                  class="h-4 w-4"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                >
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    stroke-width="1.9"
                    d="M5 13l4 4L19 7"
                  />
                </svg>
                <span>{{ t('adminPages.gitlabInstances.test') }}</span>
              </button>
              <button
                type="button"
                class="admin-instance-action admin-instance-action-secondary"
                @click="editInstance(inst)"
              >
                <svg
                  class="h-4 w-4"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                >
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    stroke-width="1.9"
                    d="M4 20h4l10-10a2.121 2.121 0 0 0-4-4L4 16v4z"
                  />
                </svg>
                <span>{{ t('common.edit') }}</span>
              </button>
              <button
                type="button"
                class="admin-instance-action admin-instance-action-danger"
                @click="deleteInstance(inst)"
              >
                <svg
                  class="h-4 w-4"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                >
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    stroke-width="1.9"
                    d="M6 7h12M10 7V5a1 1 0 011-1h2a1 1 0 011 1v2M9 10v7M15 10v7M8 7l1 13h6l1-13"
                  />
                </svg>
                <span>{{ t('common.delete') }}</span>
              </button>
            </div>
          </article>
        </section>
        <PaginationBar
          v-if="instances.length"
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
          :title="t('adminPages.gitlabInstances.emptyTitle')"
          :description="t('adminPages.gitlabInstances.emptySubtitle')"
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
                d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4"
              />
            </svg>
          </template>
          <template #actions>
            <BaseButton @click="openCreateInstanceModal">{{
              t('adminPages.gitlabInstances.add')
            }}</BaseButton>
          </template>
        </EmptyState>
      </AdminListSection>

      <BaseModal
        :show="showInstanceModal"
        :title="
          editingInstance
            ? t('adminPages.gitlabInstances.editTitle')
            : t('adminPages.gitlabInstances.createTitle')
        "
        @close="closeInstanceModal"
      >
        <form @submit.prevent="saveInstance">
          <div class="admin-modal-stack">
            <div>
              <label class="admin-modal-field-label">{{
                t('common.name')
              }}</label>
              <input
                v-model="instanceForm.name"
                type="text"
                required
                class="admin-modal-control"
              />
            </div>
            <div>
              <label class="admin-modal-field-label">{{
                t('common.url')
              }}</label>
              <input
                v-model="instanceForm.url"
                type="url"
                required
                :placeholder="t('adminPages.gitlabInstances.urlPlaceholder')"
                class="admin-modal-control"
              />
            </div>
            <div>
              <label class="admin-modal-field-label">{{
                t('adminPages.gitlabInstances.tokenLabel')
              }}</label>
              <input
                v-model="instanceForm.private_token"
                type="password"
                :required="!editingInstance"
                class="admin-modal-control"
              />
              <p v-if="editingInstance" class="admin-modal-help">
                {{ t('adminPages.gitlabInstances.tokenEditHint') }}
              </p>
            </div>
            <label class="admin-modal-toggle">
              <input
                v-model="instanceForm.is_active"
                type="checkbox"
                class="admin-modal-checkbox"
              />
              <span class="text-sm font-medium text-slate-700">
                {{ t('adminPages.gitlabInstances.activeLabel') }}
              </span>
            </label>
          </div>
        </form>
        <template #footer>
          <div class="flex w-full justify-end gap-3">
            <BaseButton variant="secondary" @click="closeInstanceModal">{{
              t('common.cancel')
            }}</BaseButton>
            <BaseButton @click="saveInstance">{{
              t('common.save')
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
    </PageFrame>
  </AdminLayout>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import AdminListSection from '@/admin/components/AdminListSection.vue'
import AdminLayout from '@/admin/layout/AdminLayout.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseModal from '@/components/ui/BaseModal.vue'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import PageFrame from '@/components/ui/PageFrame.vue'
import PaginationBar from '@/components/ui/PaginationBar.vue'
import { useConfirmDialog } from '@/composables/useConfirmDialog'
import { useToast } from '@/composables/useToast'
import gitlabApi from '@/api/gitlab'

const { t } = useI18n()
const { showToast } = useToast()
const {
  confirmDialog,
  requestConfirm,
  closeConfirmDialog,
  runConfirmedAction
} = useConfirmDialog()

const instances = ref([])
const showInstanceModal = ref(false)
const editingInstance = ref(null)
const currentPage = ref(1)
const pageSize = ref(20)
const totalCount = ref(0)

const instanceForm = ref({
  name: '',
  url: '',
  private_token: '',
  is_active: true
})

async function loadInstances() {
  try {
    const data = await gitlabApi.listInstancesPage({
      page: currentPage.value,
      page_size: pageSize.value
    })
    instances.value = Array.isArray(data) ? data : (data?.results ?? [])
    totalCount.value = Array.isArray(data)
      ? data.length
      : Number(data?.count ?? instances.value.length)
  } catch (e) {
    instances.value = []
    totalCount.value = 0
    showToast(
      t('adminPages.gitlabInstances.toast.loadFailed', { message: e.message }),
      'error'
    )
  }
}

function handlePageSizeChange(size) {
  pageSize.value = size
  currentPage.value = 1
  loadInstances()
}

function goPrevPage() {
  if (currentPage.value <= 1) return
  currentPage.value -= 1
  loadInstances()
}

function goNextPage() {
  if (currentPage.value * pageSize.value >= totalCount.value) return
  currentPage.value += 1
  loadInstances()
}

async function testGitLabConnection(inst) {
  try {
    await gitlabApi.testConnection(inst.id)
    showToast(t('adminPages.gitlabInstances.toast.testSucceeded'))
  } catch (e) {
    showToast(
      t('adminPages.gitlabInstances.toast.testFailed', { message: e.message }),
      'error'
    )
  }
}

function resetInstanceForm() {
  instanceForm.value = {
    name: '',
    url: '',
    private_token: '',
    is_active: true
  }
}

function openCreateInstanceModal() {
  editingInstance.value = null
  resetInstanceForm()
  showInstanceModal.value = true
}

function editInstance(inst) {
  editingInstance.value = inst
  instanceForm.value = {
    name: inst.name,
    url: inst.url,
    private_token: '',
    is_active: inst.is_active
  }
  showInstanceModal.value = true
}

function closeInstanceModal() {
  showInstanceModal.value = false
  editingInstance.value = null
  resetInstanceForm()
}

async function saveInstance() {
  try {
    const payload = {
      name: instanceForm.value.name,
      url: instanceForm.value.url,
      is_active: instanceForm.value.is_active
    }
    if (instanceForm.value.private_token) {
      payload.private_token = instanceForm.value.private_token
    }

    if (editingInstance.value) {
      await gitlabApi.updateInstance(editingInstance.value.id, payload)
      showToast(t('adminPages.gitlabInstances.toast.updated'))
    } else {
      await gitlabApi.createInstance({
        ...payload,
        private_token: instanceForm.value.private_token
      })
      showToast(t('adminPages.gitlabInstances.toast.created'))
    }
    closeInstanceModal()
    loadInstances()
  } catch (e) {
    showToast(
      t('adminPages.gitlabInstances.toast.saveFailed', { message: e.message }),
      'error'
    )
  }
}

async function deleteInstance(inst) {
  requestConfirm({
    title: t('common.delete'),
    message: t('adminPages.gitlabInstances.deleteConfirm', {
      name: inst.name
    }),
    confirmText: t('common.delete'),
    onConfirm: async () => {
      try {
        await gitlabApi.deleteInstance(inst.id)
        showToast(t('adminPages.gitlabInstances.toast.deleteSucceeded'))
        loadInstances()
      } catch (e) {
        showToast(
          t('adminPages.gitlabInstances.toast.deleteFailed', {
            message: e.message
          }),
          'error'
        )
      }
    }
  })
}

onMounted(() => {
  loadInstances()
})
</script>
