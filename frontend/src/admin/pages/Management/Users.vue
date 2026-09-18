<template>
  <AdminLayout>
    <PageFrame
      variant="soft"
      :title="t('management.userManagement')"
      :subtitle="t('management.usersSubtitle')"
    >
      <AdminListSection>
        <template #toolbar>
          <div class="user-list-toolbar">
            <div class="user-list-toolbar-main">
              <span class="user-list-count">
                {{ t('management.totalUsers', { count: totalCount }) }}
              </span>
              <label class="user-list-search">
                <span class="sr-only">{{ t('management.searchUsers') }}</span>
                <svg
                  aria-hidden="true"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    stroke-width="1.8"
                    d="m21 21-4.35-4.35m2.35-5.65a8 8 0 1 1-16 0 8 8 0 0 1 16 0Z"
                  />
                </svg>
                <input
                  v-model="searchQuery"
                  type="search"
                  :placeholder="t('management.userSearchPlaceholder')"
                />
              </label>
            </div>
            <div class="user-list-toolbar-actions">
              <BaseButton
                variant="outline"
                size="sm"
                :loading="loading"
                @click="fetchUsers"
              >
                {{ t('common.refresh') }}
              </BaseButton>
              <BaseButton variant="primary" size="sm" @click="openCreateModal">
                {{ t('management.createUser') }}
              </BaseButton>
            </div>
          </div>
        </template>

        <AdminPageState
          :loading="loading && !users.length"
          :error="error"
          :empty="!loading && !error && !users.length"
          :empty-title="
            searchQuery.trim()
              ? t('management.userSearchEmptyTitle')
              : t('common.noData')
          "
          :empty-description="
            searchQuery.trim() ? t('management.userSearchEmptyDescription') : ''
          "
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
          <template v-if="searchQuery.trim()" #emptyActions>
            <BaseButton variant="outline" size="sm" @click="clearUserSearch">
              {{ t('management.clearUserSearch') }}
            </BaseButton>
          </template>

          <AdminTable class="user-list-table">
            <thead>
              <tr>
                <th class="admin-table-head">
                  {{ t('management.userIdentity') }}
                </th>
                <th class="admin-table-head">
                  {{ t('management.authSource') }}
                </th>
                <th class="admin-table-head">
                  {{ t('management.accessOverview') }}
                </th>
                <th class="admin-table-head">
                  {{ t('management.defaultPlatform') }}
                </th>
                <th class="admin-table-head">{{ t('management.status') }}</th>
                <th class="admin-table-head">{{ t('common.actions') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="user in users" :key="user.id" class="admin-table-row">
                <td class="admin-table-cell user-list-identity">
                  <div class="user-list-identity-main">
                    <span class="user-list-avatar" aria-hidden="true">
                      {{
                        (user.display_name || user.username || '?')
                          .charAt(0)
                          .toUpperCase()
                      }}
                    </span>
                    <div class="min-w-0">
                      <div class="user-list-name">{{ user.username }}</div>
                      <div class="user-list-secondary">
                        {{
                          user.display_name ||
                          user.email ||
                          t('common.emptyValue')
                        }}
                      </div>
                    </div>
                  </div>
                </td>
                <td class="admin-table-cell user-list-auth">
                  <span :class="authSourceBadgeClass(user.auth_source)">
                    {{ formatAuthSource(user.auth_source) }}
                  </span>
                </td>
                <td class="admin-table-cell user-list-access">
                  <div class="user-access-summary">
                    {{
                      t('management.accessSummary', {
                        groups: user.groups?.length || 0,
                        roles: (user.effective_roles || user.roles)?.length || 0
                      })
                    }}
                  </div>
                  <div class="user-access-detail">
                    {{ joinNames(user.effective_roles || user.roles) }}
                  </div>
                </td>
                <td class="admin-table-cell user-list-platform">
                  {{
                    formatPlatform(
                      user.preferred_platform ||
                        user.access_profile?.preferred_platform
                    )
                  }}
                </td>
                <td class="admin-table-cell user-list-status">
                  <div class="user-list-status-items">
                    <span
                      :class="
                        user.is_active !== false
                          ? 'admin-status-badge admin-status-badge--success'
                          : 'admin-status-badge admin-status-badge--muted'
                      "
                    >
                      {{
                        user.is_active !== false
                          ? t('management.isActive')
                          : t('management.inactive')
                      }}
                    </span>
                    <span
                      v-if="user.is_staff"
                      class="admin-status-badge admin-status-badge--info"
                    >
                      {{ t('management.adminUser') }}
                    </span>
                  </div>
                </td>
                <td class="admin-table-cell">
                  <button
                    type="button"
                    class="user-list-edit"
                    @click="openEditModal(user)"
                  >
                    {{ t('common.edit') }}
                  </button>
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
        <form @submit.prevent="submitUser" class="admin-modal-stack">
          <p v-if="submitError" class="text-sm text-red-600">
            {{ submitError }}
          </p>
          <div>
            <label class="admin-modal-field-label">{{
              t('dashboard.username')
            }}</label>
            <input
              v-model="form.username"
              type="text"
              class="admin-modal-control"
            />
          </div>
          <div>
            <label class="admin-modal-field-label">{{
              t('dashboard.email')
            }}</label>
            <input
              v-model="form.email"
              type="email"
              class="admin-modal-control"
            />
          </div>
          <div v-if="mode === 'create'">
            <label class="admin-modal-field-label">{{
              t('password.reset.newPassword')
            }}</label>
            <input
              v-model="form.password"
              type="password"
              class="admin-modal-control"
            />
          </div>
          <div>
            <label class="admin-modal-field-label">{{
              t('management.selectGroups')
            }}</label>
            <div class="admin-modal-checklist max-h-32">
              <label
                v-for="group in groupOptions"
                :key="group.id"
                class="admin-modal-checkitem"
              >
                <input
                  v-model="form.group_ids"
                  type="checkbox"
                  :value="group.id"
                  class="admin-modal-checkbox"
                />
                <span class="text-sm text-slate-700">{{ group.name }}</span>
              </label>
            </div>
          </div>
          <div>
            <label class="admin-modal-field-label">{{
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
                <span class="text-sm text-slate-700">{{ role.name }}</span>
              </label>
            </div>
          </div>
          <div>
            <label class="admin-modal-field-label">{{
              t('management.defaultPlatform')
            }}</label>
            <select
              v-model="form.preferred_platform"
              class="admin-modal-control"
            >
              <option value="">
                {{ t('management.followRolePreference') }}
              </option>
              <option
                v-for="platform in platformOptions"
                :key="platform.key"
                :value="platform.key"
              >
                {{ platform.label }}
              </option>
            </select>
          </div>
          <div class="grid gap-4 md:grid-cols-2">
            <div class="admin-modal-inline-toggle">
              <input
                v-model="form.is_staff"
                type="checkbox"
                id="user-is-staff"
                class="admin-modal-checkbox"
              />
              <label
                for="user-is-staff"
                class="cursor-pointer text-sm font-medium text-slate-700"
              >
                {{ t('dashboard.isStaff') }}
              </label>
            </div>
            <div class="admin-modal-inline-toggle">
              <input
                v-model="form.is_active"
                type="checkbox"
                id="user-is-active"
                class="admin-modal-checkbox"
              />
              <label
                for="user-is-active"
                class="cursor-pointer text-sm font-medium text-slate-700"
              >
                {{ t('management.isActive') }}
              </label>
            </div>
          </div>
        </form>
        <template #footer>
          <div class="flex flex-row-reverse gap-2">
            <BaseButton
              variant="primary"
              :loading="submitLoading"
              @click="submitUser"
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
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import AdminListSection from '@/admin/components/AdminListSection.vue'
import AdminPageState from '@/admin/components/AdminPageState.vue'
import AdminLayout from '@/admin/layout/AdminLayout.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseModal from '@/components/ui/BaseModal.vue'
import AdminTable from '@/admin/components/AdminTable.vue'
import PageFrame from '@/components/ui/PageFrame.vue'
import PaginationBar from '@/components/ui/PaginationBar.vue'
import { managementApi } from '@/admin/api/management'
import { PLATFORM_DEFINITIONS } from '@/utils/platformAccess'

const { t } = useI18n()

const users = ref([])
const loading = ref(false)
const error = ref(null)
const currentPage = ref(1)
const pageSize = ref(20)
const totalCount = ref(0)
const searchQuery = ref('')

const showModal = ref(false)
const mode = ref('create')
const editingUserId = ref(null)
const submitLoading = ref(false)
const submitError = ref(null)

const groupOptions = ref([])
const roleOptions = ref([])
let searchTimer = null
let userRequestId = 0

const createEmptyForm = () => ({
  username: '',
  email: '',
  password: '',
  is_staff: false,
  is_active: true,
  group_ids: [],
  role_ids: [],
  preferred_platform: ''
})

const form = ref(createEmptyForm())

const totalPages = computed(() =>
  totalCount.value > 0 ? Math.ceil(totalCount.value / pageSize.value) : 1
)

const modalTitle = computed(() =>
  mode.value === 'create'
    ? t('management.createUser')
    : t('management.editUser')
)

const platformOptions = computed(() =>
  PLATFORM_DEFINITIONS.map((item) => ({
    key: item.key,
    label: t(item.labelKey)
  }))
)

function joinNames(items) {
  return Array.isArray(items) && items.length
    ? items.map((item) => item.name).join(', ')
    : t('common.emptyValue')
}

function formatPlatform(value) {
  const match = platformOptions.value.find((item) => item.key === value)
  return match?.label || t('common.emptyValue')
}

function formatAuthSource(value) {
  if (value === 'ldap') return t('management.authSourceLdap')
  if (value === 'oauth') return t('management.authSourceOauth')
  return t('management.authSourceLocal')
}

function authSourceBadgeClass(value) {
  if (value === 'ldap') {
    return 'admin-status-badge admin-status-badge--info'
  }
  if (value === 'oauth') {
    return 'admin-status-badge admin-status-badge--success'
  }
  return 'admin-status-badge admin-status-badge--muted'
}

function closeModal() {
  showModal.value = false
  submitError.value = null
  submitLoading.value = false
  editingUserId.value = null
  form.value = createEmptyForm()
}

function openCreateModal() {
  mode.value = 'create'
  form.value = createEmptyForm()
  showModal.value = true
}

function openEditModal(user) {
  mode.value = 'edit'
  editingUserId.value = user.id
  form.value = {
    username: user.username || '',
    email: user.email || '',
    password: '',
    is_staff: !!user.is_staff,
    is_active: user.is_active !== false,
    group_ids: Array.isArray(user.groups)
      ? user.groups.map((item) => item.id)
      : [],
    role_ids: Array.isArray(user.roles)
      ? user.roles.map((item) => item.id)
      : [],
    preferred_platform: user.preferred_platform || ''
  }
  showModal.value = true
}

async function loadOptions() {
  try {
    const [groupsData, rolesData] = await Promise.all([
      managementApi.getGroups({ page: 1, page_size: 1000 }),
      managementApi.getRoles({ page: 1, page_size: 1000 })
    ])
    groupOptions.value = Array.isArray(groupsData)
      ? groupsData
      : (groupsData?.results ?? [])
    roleOptions.value = Array.isArray(rolesData)
      ? rolesData
      : (rolesData?.results ?? [])
  } catch {
    groupOptions.value = []
  }
}

async function submitUser() {
  submitError.value = null
  const payload = {
    username: (form.value.username || '').trim(),
    email: (form.value.email || '').trim(),
    is_staff: !!form.value.is_staff,
    is_active: !!form.value.is_active,
    group_ids: Array.isArray(form.value.group_ids) ? form.value.group_ids : [],
    role_ids: Array.isArray(form.value.role_ids) ? form.value.role_ids : [],
    preferred_platform: form.value.preferred_platform || ''
  }

  if (!payload.username) {
    submitError.value = t('management.usernameRequired')
    return
  }

  if (mode.value === 'create') {
    payload.password = (form.value.password || '').trim()
    if (!payload.password) {
      submitError.value = t('management.passwordRequired')
      return
    }
  }

  submitLoading.value = true
  try {
    if (mode.value === 'create') {
      await managementApi.createUser(payload)
    } else {
      await managementApi.updateUser(editingUserId.value, payload)
    }
    closeModal()
    await fetchUsers()
  } catch (e) {
    const detail = e?.response?.data?.detail
    if (e?.response?.data?.code === 'username_taken') {
      submitError.value = t('management.usernameTaken')
    } else if (e?.response?.data?.code === 'email_taken') {
      submitError.value = t('management.emailTaken')
    } else {
      submitError.value =
        typeof detail === 'string' ? detail : t('common.error')
    }
  } finally {
    submitLoading.value = false
  }
}

async function fetchUsers() {
  const requestId = ++userRequestId
  loading.value = true
  error.value = null
  try {
    const data = await managementApi.getUsers({
      page: currentPage.value,
      page_size: pageSize.value,
      search: searchQuery.value.trim() || undefined
    })
    if (requestId !== userRequestId) return
    users.value = Array.isArray(data) ? data : (data?.results ?? [])
    totalCount.value = Array.isArray(data)
      ? data.length
      : Number(data?.count ?? users.value.length)
  } catch (e) {
    if (requestId !== userRequestId) return
    users.value = []
    totalCount.value = 0
    error.value = e?.response?.data?.detail || e?.message || t('common.error')
  } finally {
    if (requestId === userRequestId) loading.value = false
  }
}

function clearUserSearch() {
  searchQuery.value = ''
}

function handlePageSizeChange(size) {
  pageSize.value = size
  currentPage.value = 1
  fetchUsers()
}

function goPrevPage() {
  if (currentPage.value <= 1) return
  currentPage.value -= 1
  fetchUsers()
}

function goNextPage() {
  if (currentPage.value >= totalPages.value) return
  currentPage.value += 1
  fetchUsers()
}

watch(searchQuery, () => {
  if (searchTimer) window.clearTimeout(searchTimer)
  searchTimer = window.setTimeout(() => {
    currentPage.value = 1
    fetchUsers()
  }, 250)
})

onBeforeUnmount(() => {
  if (searchTimer) window.clearTimeout(searchTimer)
})

onMounted(async () => {
  await Promise.all([fetchUsers(), loadOptions()])
})
</script>
