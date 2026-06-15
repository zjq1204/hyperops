<template>
  <AdminLayout>
    <PageFrame
      variant="soft"
      :eyebrow="t('adminPages.gitlabGroups.eyebrow')"
      :title="t('adminPages.gitlabGroups.title')"
      :subtitle="t('adminPages.gitlabGroups.subtitle')"
    >
      <AdminListSection>
        <template #filters>
          <div class="admin-filter-grid">
            <div class="admin-filter-field">
              <label class="admin-filter-label">
                {{ t('adminPages.gitlabGroups.selectInstance') }}
              </label>
              <select
                v-model="selectedInstance"
                @change="handleInstanceChange"
                class="admin-filter-control min-w-[18rem] max-w-sm"
              >
                <option value="">
                  {{ t('adminPages.gitlabGroups.selectInstance') }}
                </option>
                <option
                  v-for="inst in instances"
                  :key="inst.id"
                  :value="inst.id"
                >
                  {{ inst.name }}
                </option>
              </select>
            </div>
          </div>
          <div class="admin-toolbar-end">
            <BaseButton
              @click="showGroupModal = true"
              :disabled="!selectedInstance"
            >
              {{ t('adminPages.gitlabGroups.addFromGitLab') }}
            </BaseButton>
            <BaseButton
              variant="secondary"
              @click="collectAllProjects"
              :disabled="!selectedInstance || groups.length === 0"
            >
              {{ t('adminPages.gitlabGroups.collectAllProjects') }}
            </BaseButton>
          </div>
        </template>

        <AdminTable v-if="groups.length">
          <thead>
            <tr>
              <th class="admin-table-head">{{ t('common.name') }}</th>
              <th class="admin-table-head">{{ t('common.path') }}</th>
              <th class="admin-table-head">
                {{ t('adminPages.gitlabGroups.collectedAt') }}
              </th>
              <th class="admin-table-head">{{ t('common.actions') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="group in groups" :key="group.id" class="admin-table-row">
              <td class="admin-table-cell">
                <div class="font-semibold text-slate-900">{{ group.name }}</div>
              </td>
              <td class="admin-table-cell font-mono text-sm text-slate-500">
                {{ group.path }}
              </td>
              <td class="admin-table-cell text-sm text-slate-500">
                {{ group.collected_at || '-' }}
              </td>
              <td class="admin-table-cell">
                <div class="flex gap-3 text-sm font-semibold">
                  <button
                    @click="collectProjects(group)"
                    class="text-violet-700 hover:text-violet-900"
                  >
                    {{ t('adminPages.gitlabGroups.collectProjects') }}
                  </button>
                  <button
                    @click="deleteGroup(group)"
                    class="text-rose-700 hover:text-rose-900"
                  >
                    {{ t('common.delete') }}
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </AdminTable>
        <PaginationBar
          v-if="groups.length"
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
          :title="t('adminPages.gitlabGroups.emptyTitle')"
          :description="t('adminPages.gitlabGroups.emptySubtitle')"
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
                d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z"
              />
            </svg>
          </template>
        </EmptyState>
      </AdminListSection>

      <BaseModal
        :show="showGroupModal"
        :title="t('adminPages.gitlabGroups.addTitle')"
        @close="showGroupModal = false"
      >
        <div class="admin-modal-stack">
          <label class="mb-2 block text-sm font-medium text-slate-700">{{
            t('adminPages.gitlabGroups.chooseGroup')
          }}</label>
          <select v-model="selectedGitLabGroup" class="input">
            <option value="">
              {{
                gitLabGroups.length
                  ? t('adminPages.gitlabGroups.chooseGroup')
                  : t('adminPages.gitlabGroups.loadingOption')
              }}
            </option>
            <option
              v-for="group in gitLabGroups"
              :key="group.id"
              :value="group.id"
            >
              {{ group.name }} ({{ group.path }})
            </option>
          </select>
        </div>
        <template #footer>
          <div class="flex w-full justify-end gap-3">
            <BaseButton variant="secondary" @click="showGroupModal = false">{{
              t('common.cancel')
            }}</BaseButton>
            <BaseButton @click="addGroup" :disabled="!selectedGitLabGroup">{{
              t('common.add')
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
import { ref, onMounted, watch } from 'vue'
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
const groups = ref([])
const selectedInstance = ref('')
const showGroupModal = ref(false)
const selectedGitLabGroup = ref('')
const gitLabGroups = ref([])
const currentPage = ref(1)
const pageSize = ref(20)
const totalCount = ref(0)

const toast = ref({ show: false, message: '', type: 'success' })

function showToast(message, type = 'success') {
  toast.value = { show: true, message, type }
  setTimeout(() => {
    toast.value.show = false
  }, 3000)
}

async function loadInstances() {
  try {
    instances.value = await gitlabApi.listInstances()
  } catch (e) {
    showToast(
      t('adminPages.gitlabGroups.toast.loadInstancesFailed', {
        message: e.message
      }),
      'error'
    )
  }
}

async function loadGroups() {
  if (!selectedInstance.value) {
    groups.value = []
    totalCount.value = 0
    return
  }
  try {
    const data = await gitlabApi.listGroupsPage({
      instance: selectedInstance.value,
      page: currentPage.value,
      page_size: pageSize.value
    })
    groups.value = Array.isArray(data) ? data : (data?.results ?? [])
    totalCount.value = Array.isArray(data)
      ? data.length
      : Number(data?.count ?? groups.value.length)
  } catch (e) {
    groups.value = []
    totalCount.value = 0
    showToast(
      t('adminPages.gitlabGroups.toast.loadGroupsFailed', {
        message: e.message
      }),
      'error'
    )
  }
}

function handleInstanceChange() {
  currentPage.value = 1
  loadGroups()
}

function handlePageSizeChange(size) {
  pageSize.value = size
  currentPage.value = 1
  loadGroups()
}

function goPrevPage() {
  if (currentPage.value <= 1) return
  currentPage.value -= 1
  loadGroups()
}

function goNextPage() {
  if (currentPage.value * pageSize.value >= totalCount.value) return
  currentPage.value += 1
  loadGroups()
}

async function loadGitLabGroups() {
  if (!selectedInstance.value) return
  try {
    selectedGitLabGroup.value = ''
    gitLabGroups.value = []
    gitLabGroups.value = await gitlabApi.listGroupsFromGitLab(
      selectedInstance.value
    )
  } catch (e) {
    showToast(
      t('adminPages.gitlabGroups.toast.loadGitLabGroupsFailed', {
        message: e.message
      }),
      'error'
    )
  }
}

async function addGroup() {
  if (!selectedGitLabGroup.value) return
  const group = gitLabGroups.value.find(
    (g) => g.id === parseInt(selectedGitLabGroup.value)
  )
  if (!group) return
  try {
    await gitlabApi.createGroup({
      instance: parseInt(selectedInstance.value),
      gitlab_id: group.id,
      name: group.name,
      path: group.path,
      description: group.description
    })
    showToast(t('adminPages.gitlabGroups.toast.addSucceeded'))
    showGroupModal.value = false
    loadGroups()
  } catch (e) {
    showToast(
      t('adminPages.gitlabGroups.toast.addFailed', { message: e.message }),
      'error'
    )
  }
}

async function collectProjects(group) {
  try {
    const result = await gitlabApi.collectProjects(group.id)
    showToast(result.message)
    loadGroups()
  } catch (e) {
    showToast(
      t('adminPages.gitlabGroups.toast.collectFailed', { message: e.message }),
      'error'
    )
  }
}

async function collectAllProjects() {
  for (const group of groups.value) {
    try {
      await gitlabApi.collectProjects(group.id)
    } catch (e) {
      showToast(
        t('adminPages.gitlabGroups.toast.collectGroupFailed', {
          name: group.name,
          message: e.message
        }),
        'error'
      )
    }
  }
  showToast(t('adminPages.gitlabGroups.toast.collectCompleted'))
  loadGroups()
}

async function deleteGroup(group) {
  requestConfirm({
    title: t('common.delete'),
    message: t('adminPages.gitlabGroups.deleteConfirm', { name: group.name }),
    confirmText: t('common.delete'),
    onConfirm: async () => {
      try {
        await gitlabApi.deleteGroup(group.id)
        showToast(t('adminPages.gitlabGroups.toast.deleteSucceeded'))
        loadGroups()
      } catch (e) {
        showToast(
          t('adminPages.gitlabGroups.toast.deleteFailed', {
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

watch(showGroupModal, async (val) => {
  if (val && selectedInstance.value) {
    await loadGitLabGroups()
  }
})

watch(selectedInstance, () => {
  selectedGitLabGroup.value = ''
  gitLabGroups.value = []
})
</script>
