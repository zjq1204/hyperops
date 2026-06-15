<template>
  <AdminLayout>
    <PageFrame
      variant="soft"
      :eyebrow="t('adminPages.gitlabInstances.eyebrow')"
      :title="t('adminPages.gitlabInstances.title')"
      :subtitle="t('adminPages.gitlabInstances.subtitle')"
    >
      <template #actions>
        <BaseButton @click="showInstanceModal = true">{{
          t('adminPages.gitlabInstances.add')
        }}</BaseButton>
      </template>

      <AdminListSection>
        <AdminTable v-if="instances.length">
          <thead>
            <tr>
              <th class="admin-table-head">{{ t('common.name') }}</th>
              <th class="admin-table-head">{{ t('common.url') }}</th>
              <th class="admin-table-head">{{ t('common.status') }}</th>
              <th class="admin-table-head">{{ t('common.actions') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="inst in instances"
              :key="inst.id"
              class="admin-table-row"
            >
              <td class="admin-table-cell">
                <div class="font-semibold text-slate-900">{{ inst.name }}</div>
              </td>
              <td class="admin-table-cell text-sm text-slate-500">
                {{ inst.url }}
              </td>
              <td class="admin-table-cell">
                <span
                  :class="
                    inst.is_active
                      ? 'admin-status-badge admin-status-badge--success'
                      : 'admin-status-badge admin-status-badge--muted'
                  "
                  >{{
                    inst.is_active ? t('common.enabled') : t('common.disabled')
                  }}</span
                >
              </td>
              <td class="admin-table-cell">
                <div class="flex gap-3">
                  <button
                    @click="testGitLabConnection(inst)"
                    class="text-sm font-semibold text-sky-700 hover:text-sky-900"
                  >
                    {{ t('adminPages.gitlabInstances.test') }}
                  </button>
                  <button
                    @click="deleteInstance(inst)"
                    class="text-sm font-semibold text-rose-700 hover:text-rose-900"
                  >
                    {{ t('common.delete') }}
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </AdminTable>
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
            <BaseButton @click="showInstanceModal = true">{{
              t('adminPages.gitlabInstances.add')
            }}</BaseButton>
          </template>
        </EmptyState>
      </AdminListSection>

      <BaseModal
        :show="showInstanceModal"
        :title="t('adminPages.gitlabInstances.createTitle')"
        @close="showInstanceModal = false"
      >
        <form @submit.prevent="saveInstance">
          <div class="admin-modal-stack">
            <div>
              <label class="mb-2 block text-sm font-medium text-slate-700">{{
                t('common.name')
              }}</label>
              <input
                v-model="instanceForm.name"
                type="text"
                required
                class="input"
              />
            </div>
            <div>
              <label class="mb-2 block text-sm font-medium text-slate-700">{{
                t('common.url')
              }}</label>
              <input
                v-model="instanceForm.url"
                type="url"
                required
                placeholder="https://gitlab.example.com"
                class="input"
              />
            </div>
            <div>
              <label class="mb-2 block text-sm font-medium text-slate-700">{{
                t('adminPages.gitlabInstances.tokenLabel')
              }}</label>
              <input
                v-model="instanceForm.private_token"
                type="password"
                required
                class="input"
              />
            </div>
          </div>
        </form>
        <template #footer>
          <div class="flex w-full justify-end gap-3">
            <BaseButton
              variant="secondary"
              @click="showInstanceModal = false"
              >{{ t('common.cancel') }}</BaseButton
            >
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
import { ref, onMounted } from 'vue'
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

const instances = ref([])
const showInstanceModal = ref(false)
const currentPage = ref(1)
const pageSize = ref(20)
const totalCount = ref(0)

const instanceForm = ref({
  name: '',
  url: '',
  private_token: '',
  is_active: true
})

const toast = ref({ show: false, message: '', type: 'success' })

function showToast(message, type = 'success') {
  toast.value = { show: true, message, type }
  setTimeout(() => {
    toast.value.show = false
  }, 3000)
}

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

async function saveInstance() {
  try {
    await gitlabApi.createInstance(instanceForm.value)
    showToast(t('adminPages.gitlabInstances.toast.created'))
    showInstanceModal.value = false
    instanceForm.value = {
      name: '',
      url: '',
      private_token: '',
      is_active: true
    }
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
