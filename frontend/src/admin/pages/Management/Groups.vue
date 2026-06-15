<template>
  <AdminLayout>
    <PageFrame
      variant="soft"
      :title="t('management.groupManagement')"
      :subtitle="t('management.groupsSubtitle')"
    >
      <AdminListSection>
        <template #toolbarStart>
          <span class="admin-summary-pill">{{
            t('management.totalGroups', { count: totalCount })
          }}</span>
        </template>
        <template #toolbarEnd>
          <BaseButton
            variant="outline"
            size="sm"
            :loading="loading"
            @click="fetchGroups"
          >
            {{ t('common.refresh') }}
          </BaseButton>
          <BaseButton variant="primary" size="sm" @click="openCreateModal">
            {{ t('management.createGroup') }}
          </BaseButton>
        </template>

        <AdminPageState
          :loading="loading && !groups.length"
          :error="error"
          :empty="!loading && !error && !groups.length"
          :empty-title="t('common.noData')"
        >
          <template #emptyIcon>
            <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="1.8"
                d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z"
              />
            </svg>
          </template>

          <AdminTable>
            <thead>
              <tr>
                <th class="admin-table-head">ID</th>
                <th class="admin-table-head">
                  {{ t('management.groupName') }}
                </th>
                <th class="admin-table-head">
                  {{ t('management.groupUserCount') }}
                </th>
                <th class="admin-table-head">{{ t('management.roles') }}</th>
                <th class="admin-table-head">Jenkins 通知</th>
                <th class="admin-table-head">
                  {{ t('management.permissionCount') }}
                </th>
                <th class="admin-table-head">{{ t('common.actions') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="group in groups"
                :key="group.id"
                class="admin-table-row"
              >
                <td class="admin-table-cell text-gray-900">{{ group.id }}</td>
                <td class="admin-table-cell font-medium text-gray-900">
                  {{ group.name }}
                </td>
                <td class="admin-table-cell text-gray-500">
                  {{ group.user_count ?? 0 }}
                </td>
                <td class="admin-table-cell text-gray-500">
                  {{ joinNames(group.roles) }}
                </td>
                <td class="admin-table-cell text-gray-500">
                  <div class="space-y-1">
                    <div>{{ countNotifications(group).emails }} 邮箱</div>
                    <div>{{ countNotifications(group).webhooks }} Webhook</div>
                  </div>
                </td>
                <td class="admin-table-cell text-gray-500">
                  {{ group.permission_count ?? 0 }}
                </td>
                <td class="admin-table-cell">
                  <BaseButton
                    variant="outline"
                    size="sm"
                    @click="openEditModal(group)"
                  >
                    {{ t('common.edit') }}
                  </BaseButton>
                </td>
              </tr>
            </tbody>
          </AdminTable>

          <PaginationBar
            v-if="!loading"
            variant="admin"
            :current-page="currentPage"
            :page-size="pageSize"
            :total-count="totalCount"
            @update:page-size="handlePageSizeChange"
            @prev="goPrevPage"
            @next="goNextPage"
          />
        </AdminPageState>
      </AdminListSection>

      <BaseModal :show="showModal" :title="modalTitle" @close="closeModal">
        <form @submit.prevent="submitGroup" class="admin-modal-stack">
          <p v-if="submitError" class="text-sm text-red-600">
            {{ submitError }}
          </p>
          <div>
            <label class="mb-1 block text-sm font-medium text-gray-700">{{
              t('management.groupName')
            }}</label>
            <input v-model="form.name" type="text" class="input" />
          </div>
          <div>
            <label class="mb-1 block text-sm font-medium text-gray-700">{{
              t('management.selectRoles')
            }}</label>
            <div class="admin-modal-checklist">
              <label
                v-for="role in roleOptions"
                :key="role.id"
                class="admin-modal-checkitem"
              >
                <input
                  v-model="form.role_ids"
                  type="checkbox"
                  :value="role.id"
                  class="admin-modal-checkbox"
                />
                <span class="text-sm text-gray-700">{{ role.name }}</span>
              </label>
            </div>
          </div>
          <div>
            <label class="mb-1 block text-sm font-medium text-gray-700">
              Jenkins 通知邮箱
            </label>
            <textarea
              v-model="form.notification_emails_text"
              rows="4"
              class="input min-h-[7rem]"
              placeholder="每行一个邮箱地址"
            ></textarea>
          </div>
          <div>
            <label class="mb-1 block text-sm font-medium text-gray-700">
              Jenkins Webhook
            </label>
            <textarea
              v-model="form.notification_webhooks_text"
              rows="4"
              class="input min-h-[7rem]"
              placeholder="每行一个 Webhook URL"
            ></textarea>
          </div>
        </form>
        <template #footer>
          <div class="flex flex-row-reverse gap-2">
            <BaseButton
              variant="primary"
              :loading="submitLoading"
              @click="submitGroup"
            >
              {{ t('common.confirm') }}
            </BaseButton>
            <BaseButton variant="secondary" @click="closeModal">
              {{ t('common.cancel') }}
            </BaseButton>
          </div>
        </template>
      </BaseModal>
    </PageFrame>
  </AdminLayout>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import AdminListSection from '@/admin/components/AdminListSection.vue'
import AdminPageState from '@/admin/components/AdminPageState.vue'
import AdminTable from '@/admin/components/AdminTable.vue'
import AdminLayout from '@/admin/layout/AdminLayout.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseModal from '@/components/ui/BaseModal.vue'
import PageFrame from '@/components/ui/PageFrame.vue'
import PaginationBar from '@/components/ui/PaginationBar.vue'
import { managementApi } from '@/admin/api/management'

const { t } = useI18n()

const groups = ref([])
const loading = ref(false)
const error = ref(null)
const currentPage = ref(1)
const pageSize = ref(20)
const totalCount = ref(0)

const roleOptions = ref([])

const showModal = ref(false)
const mode = ref('create')
const editingGroupId = ref(null)
const submitLoading = ref(false)
const submitError = ref(null)
const form = ref({
  name: '',
  role_ids: [],
  notification_emails_text: '',
  notification_webhooks_text: ''
})

const totalPages = computed(() =>
  totalCount.value > 0 ? Math.ceil(totalCount.value / pageSize.value) : 1
)

const modalTitle = computed(() =>
  mode.value === 'create'
    ? t('management.createGroup')
    : t('management.editGroup')
)

function joinNames(items) {
  return Array.isArray(items) && items.length
    ? items.map((item) => item.name).join(', ')
    : '—'
}

function countNotifications(group) {
  return {
    emails:
      group?.jenkins_notification_settings?.notification_emails?.length || 0,
    webhooks:
      group?.jenkins_notification_settings?.notification_webhooks?.length || 0
  }
}

function closeModal() {
  showModal.value = false
  editingGroupId.value = null
  submitError.value = null
  submitLoading.value = false
  form.value = {
    name: '',
    role_ids: [],
    notification_emails_text: '',
    notification_webhooks_text: ''
  }
}

function openCreateModal() {
  mode.value = 'create'
  form.value = {
    name: '',
    role_ids: [],
    notification_emails_text: '',
    notification_webhooks_text: ''
  }
  showModal.value = true
}

function openEditModal(group) {
  mode.value = 'edit'
  editingGroupId.value = group.id
  form.value = {
    name: group.name || '',
    role_ids: Array.isArray(group.roles)
      ? group.roles.map((item) => item.id)
      : [],
    notification_emails_text: (
      group.jenkins_notification_settings?.notification_emails || []
    ).join('\n'),
    notification_webhooks_text: (
      group.jenkins_notification_settings?.notification_webhooks || []
    ).join('\n')
  }
  showModal.value = true
}

async function loadRoleOptions() {
  try {
    const data = await managementApi.getRoles({ page: 1, page_size: 1000 })
    roleOptions.value = Array.isArray(data) ? data : (data?.results ?? [])
  } catch {
    roleOptions.value = []
  }
}

async function submitGroup() {
  submitError.value = null
  const name = (form.value.name || '').trim()
  if (!name) {
    submitError.value = t('management.groupNameRequired')
    return
  }

  submitLoading.value = true
  try {
    const payload = {
      name,
      role_ids: Array.isArray(form.value.role_ids) ? form.value.role_ids : [],
      jenkins_notification_settings: {
        notification_emails: form.value.notification_emails_text
          .split('\n')
          .map((item) => item.trim())
          .filter(Boolean),
        notification_webhooks: form.value.notification_webhooks_text
          .split('\n')
          .map((item) => item.trim())
          .filter(Boolean)
      }
    }
    if (mode.value === 'create') {
      await managementApi.createGroup(payload)
    } else {
      await managementApi.updateGroup(editingGroupId.value, payload)
    }
    closeModal()
    await fetchGroups()
  } catch (e) {
    if (e?.response?.data?.code === 'name_taken') {
      submitError.value = t('management.groupNameTaken')
    } else {
      submitError.value =
        e?.response?.data?.detail || e?.message || t('common.error')
    }
  } finally {
    submitLoading.value = false
  }
}

async function fetchGroups() {
  loading.value = true
  error.value = null
  try {
    const data = await managementApi.getGroups({
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
    error.value = e?.response?.data?.detail || e?.message || t('common.error')
  } finally {
    loading.value = false
  }
}

function handlePageSizeChange(size) {
  pageSize.value = size
  currentPage.value = 1
  fetchGroups()
}

function goPrevPage() {
  if (currentPage.value <= 1) return
  currentPage.value -= 1
  fetchGroups()
}

function goNextPage() {
  if (currentPage.value >= totalPages.value) return
  currentPage.value += 1
  fetchGroups()
}

onMounted(async () => {
  await Promise.all([fetchGroups(), loadRoleOptions()])
})
</script>
