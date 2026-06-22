<template>
  <AdminLayout>
    <PageFrame
      variant="soft"
      :title="t('management.roleManagement')"
      :subtitle="t('management.rolesSubtitle')"
    >
      <AdminListSection>
        <template #toolbarStart>
          <span class="admin-summary-pill">{{
            t('management.totalRoles', { count: totalCount })
          }}</span>
        </template>
        <template #toolbarEnd>
          <BaseButton
            variant="outline"
            size="sm"
            :loading="loading"
            @click="fetchRoles"
          >
            {{ t('common.refresh') }}
          </BaseButton>
          <BaseButton variant="primary" size="sm" @click="openCreateModal">
            {{ t('management.createRole') }}
          </BaseButton>
        </template>

        <AdminPageState
          :loading="loading && !roles.length"
          :error="error"
          :empty="!loading && !error && !roles.length"
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
                <th class="admin-table-head">{{ t('common.id') }}</th>
                <th class="admin-table-head">
                  {{ t('management.roleName') }}
                </th>
                <th class="admin-table-head">
                  {{ t('management.visibleFeatures') }}
                </th>
                <th class="admin-table-head">
                  {{ t('management.defaultPlatform') }}
                </th>
                <th class="admin-table-head">
                  {{ t('management.groupUserCount') }}
                </th>
                <th class="admin-table-head">
                  {{ t('management.groupCount') }}
                </th>
                <th class="admin-table-head">
                  {{ t('management.isActive') }}
                </th>
                <th class="admin-table-head">{{ t('common.actions') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="role in roles" :key="role.id" class="admin-table-row">
                <td class="admin-table-cell text-slate-900">{{ role.id }}</td>
                <td class="admin-table-cell font-medium text-slate-900">
                  {{ role.name }}
                </td>
                <td class="admin-table-cell text-slate-500">
                  {{ formatFeatures(role.visible_features) }}
                </td>
                <td class="admin-table-cell text-slate-500">
                  {{ formatPlatform(role.preferred_platform) }}
                </td>
                <td class="admin-table-cell text-slate-500">
                  {{ role.user_count ?? 0 }}
                </td>
                <td class="admin-table-cell text-slate-500">
                  {{ role.group_count ?? 0 }}
                </td>
                <td class="admin-table-cell">
                  <span
                    :class="
                      role.is_active
                        ? 'admin-status-badge admin-status-badge--success'
                        : 'admin-status-badge admin-status-badge--muted'
                    "
                  >
                    {{ role.is_active ? t('common.yes') : t('common.no') }}
                  </span>
                </td>
                <td class="admin-table-cell">
                  <BaseButton
                    variant="outline"
                    size="sm"
                    @click="openEditModal(role)"
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
        <form @submit.prevent="submitRole" class="admin-modal-stack">
          <p v-if="submitError" class="text-sm text-red-600">
            {{ submitError }}
          </p>
          <div>
            <label class="admin-modal-field-label">{{
              t('management.roleName')
            }}</label>
            <input
              v-model="form.name"
              type="text"
              class="admin-modal-control"
            />
          </div>
          <div>
            <label class="admin-modal-field-label">{{
              t('management.visibleFeatures')
            }}</label>
            <div class="space-y-3">
              <section
                v-for="group in permissionGroups"
                :key="group.key"
                class="admin-modal-card-muted"
              >
                <label class="flex cursor-pointer items-center gap-3">
                  <input
                    type="checkbox"
                    class="admin-modal-checkbox"
                    :checked="isGroupChecked(group)"
                    :indeterminate.prop="isGroupIndeterminate(group)"
                    @change="toggleGroup(group, $event.target.checked)"
                  />
                  <span class="text-sm font-semibold text-slate-900">
                    {{ group.label }}
                  </span>
                  <span class="ml-auto text-xs text-slate-500">
                    {{ selectedFeatureCount(group) }}/{{
                      group.children.length
                    }}
                  </span>
                </label>
                <div class="mt-3 grid gap-2 sm:grid-cols-2">
                  <label
                    v-for="feature in group.children"
                    :key="feature.key"
                    class="admin-permission-option"
                  >
                    <input
                      type="checkbox"
                      class="admin-modal-checkbox mt-0.5"
                      :checked="isFeatureSelected(feature.key)"
                      @change="
                        toggleFeature(feature.key, $event.target.checked)
                      "
                    />
                    <span class="min-w-0">
                      <span class="block text-sm font-medium text-slate-800">
                        {{ feature.label }}
                      </span>
                    </span>
                  </label>
                </div>
              </section>
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
              <option value="">{{ t('management.noDefaultPlatform') }}</option>
              <option
                v-for="platform in selectedPlatformOptions"
                :key="platform.key"
                :value="platform.key"
              >
                {{ platform.label }}
              </option>
            </select>
          </div>
          <div class="admin-modal-inline-toggle">
            <input
              v-model="form.is_active"
              type="checkbox"
              id="role-is-active"
              class="admin-modal-checkbox"
            />
            <label
              for="role-is-active"
              class="cursor-pointer text-sm font-medium text-slate-700"
            >
              {{ t('management.isActive') }}
            </label>
          </div>
        </form>
        <template #footer>
          <div class="flex flex-row-reverse gap-2">
            <BaseButton
              variant="primary"
              :loading="submitLoading"
              @click="submitRole"
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
import { computed, onMounted, ref, watch } from 'vue'
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
import {
  FEATURE_DEFINITIONS,
  PLATFORM_DEFINITIONS
} from '@/utils/platformAccess'

const { t } = useI18n()

const roles = ref([])
const featureOptions = ref([])
const apiPlatformOptions = ref([])
const loading = ref(false)
const error = ref(null)
const currentPage = ref(1)
const pageSize = ref(20)
const totalCount = ref(0)

const showModal = ref(false)
const mode = ref('create')
const editingRoleId = ref(null)
const submitLoading = ref(false)
const submitError = ref(null)
const form = ref({
  name: '',
  visible_features: [],
  preferred_platform: '',
  is_active: true
})

const totalPages = computed(() =>
  totalCount.value > 0 ? Math.ceil(totalCount.value / pageSize.value) : 1
)

const modalTitle = computed(() =>
  mode.value === 'create'
    ? t('management.createRole')
    : t('management.editRole')
)

const localFeatureOptions = computed(() =>
  FEATURE_DEFINITIONS.map((item) => ({
    key: item.key,
    label: item.label,
    platform: item.platform,
    parent_key: item.parentKey,
    default_path: item.defaultPath
  }))
)

const localPlatformOptions = computed(() =>
  PLATFORM_DEFINITIONS.map((item) => ({
    key: item.key,
    label: t(item.labelKey),
    default_path: item.defaultPath
  }))
)

const normalizedFeatureOptions = computed(() =>
  (featureOptions.value.length
    ? featureOptions.value
    : localFeatureOptions.value
  ).map((item) => ({
    key: item.key,
    label: item.label || item.key,
    platform: item.platform || item.parent_key || '',
    parent_key: item.parent_key || item.platform || '',
    default_path: item.default_path || item.defaultPath || ''
  }))
)

const platformOptions = computed(() =>
  (apiPlatformOptions.value.length
    ? apiPlatformOptions.value
    : localPlatformOptions.value
  ).map((item) => ({
    key: item.key,
    label: item.label || item.key,
    default_path: item.default_path || item.defaultPath || ''
  }))
)

const permissionGroups = computed(() =>
  platformOptions.value
    .map((platform) => ({
      ...platform,
      children: normalizedFeatureOptions.value.filter(
        (feature) => feature.platform === platform.key
      )
    }))
    .filter((group) => group.children.length)
)

const selectedPlatformOptions = computed(() =>
  permissionGroups.value
    .filter((group) =>
      group.children.some((feature) =>
        form.value.visible_features.includes(feature.key)
      )
    )
    .map((group) => ({
      key: group.key,
      label: group.label
    }))
)

const selectedFeatureSet = computed(
  () => new Set(form.value.visible_features || [])
)

watch(
  () => form.value.visible_features,
  () => {
    const selectedPlatformKeys = new Set(
      selectedPlatformOptions.value.map((item) => item.key)
    )
    if (!selectedPlatformKeys.has(form.value.preferred_platform)) {
      form.value.preferred_platform = ''
    }
  }
)

function isFeatureSelected(featureKey) {
  return selectedFeatureSet.value.has(featureKey)
}

function selectedFeatureCount(group) {
  return group.children.filter((feature) => isFeatureSelected(feature.key))
    .length
}

function isGroupChecked(group) {
  return (
    group.children.length > 0 &&
    selectedFeatureCount(group) === group.children.length
  )
}

function isGroupIndeterminate(group) {
  const count = selectedFeatureCount(group)
  return count > 0 && count < group.children.length
}

function setVisibleFeatures(values) {
  const orderedKeys = normalizedFeatureOptions.value.map((item) => item.key)
  const selected = new Set(values)
  form.value.visible_features = orderedKeys.filter((key) => selected.has(key))
}

function toggleFeature(featureKey, checked) {
  const selected = new Set(form.value.visible_features || [])
  if (checked) {
    selected.add(featureKey)
  } else {
    selected.delete(featureKey)
  }
  setVisibleFeatures([...selected])
}

function toggleGroup(group, checked) {
  const selected = new Set(form.value.visible_features || [])
  group.children.forEach((feature) => {
    if (checked) {
      selected.add(feature.key)
    } else {
      selected.delete(feature.key)
    }
  })
  setVisibleFeatures([...selected])
}

function formatFeatures(items) {
  if (!Array.isArray(items) || !items.length) return t('common.emptyValue')
  const selected = new Set(items)
  return (
    permissionGroups.value
      .map((group) => {
        const labels = group.children
          .filter((feature) => selected.has(feature.key))
          .map((feature) => feature.label)
        if (!labels.length) return ''
        return `${group.label}: ${labels.join(t('common.listSeparator'))}`
      })
      .filter(Boolean)
      .join(t('common.groupSeparator')) || t('common.emptyValue')
  )
}

function normalizeSelectedFeatures(items) {
  if (!Array.isArray(items)) return []
  const featureKeySet = new Set(
    normalizedFeatureOptions.value.map((item) => item.key)
  )
  return normalizedFeatureOptions.value
    .map((item) => item.key)
    .filter((key) => items.includes(key) && featureKeySet.has(key))
}

function syncOptionsFromPayload(data) {
  if (Array.isArray(data?.feature_options)) {
    featureOptions.value = data.feature_options
  }
  if (Array.isArray(data?.platform_options)) {
    apiPlatformOptions.value = data.platform_options
  }
}

function syncRolesFromPayload(data) {
  const nextRoles = Array.isArray(data) ? data : (data?.results ?? [])
  roles.value = nextRoles.map((role) => ({
    ...role,
    visible_features: normalizeSelectedFeatures(role.visible_features)
  }))
  totalCount.value = Array.isArray(data)
    ? data.length
    : Number(data?.count ?? roles.value.length)
}

function formatPlatform(value) {
  const match = platformOptions.value.find((item) => item.key === value)
  return match?.label || t('common.emptyValue')
}

function closeModal() {
  showModal.value = false
  editingRoleId.value = null
  submitError.value = null
  submitLoading.value = false
  form.value = {
    name: '',
    visible_features: [],
    preferred_platform: '',
    is_active: true
  }
}

function openCreateModal() {
  mode.value = 'create'
  closeModal()
  mode.value = 'create'
  showModal.value = true
}

function openEditModal(role) {
  mode.value = 'edit'
  editingRoleId.value = role.id
  form.value = {
    name: role.name || '',
    visible_features: normalizeSelectedFeatures(role.visible_features),
    preferred_platform: role.preferred_platform || '',
    is_active: role.is_active !== false
  }
  showModal.value = true
}

async function submitRole() {
  submitError.value = null
  const name = (form.value.name || '').trim()
  if (!name) {
    submitError.value = t('management.roleNameRequired')
    return
  }

  submitLoading.value = true
  try {
    const payload = {
      name,
      visible_features: Array.isArray(form.value.visible_features)
        ? form.value.visible_features
        : [],
      preferred_platform: form.value.preferred_platform || '',
      is_active: !!form.value.is_active
    }
    if (mode.value === 'create') {
      await managementApi.createRole(payload)
    } else {
      await managementApi.updateRole(editingRoleId.value, payload)
    }
    closeModal()
    await fetchRoles()
  } catch (e) {
    if (e?.response?.data?.code === 'name_taken') {
      submitError.value = t('management.roleNameTaken')
    } else {
      submitError.value =
        e?.response?.data?.detail || e?.message || t('common.error')
    }
  } finally {
    submitLoading.value = false
  }
}

async function fetchRoles() {
  loading.value = true
  error.value = null
  try {
    const data = await managementApi.getRoles({
      page: currentPage.value,
      page_size: pageSize.value
    })
    syncOptionsFromPayload(data)
    syncRolesFromPayload(data)
  } catch (e) {
    roles.value = []
    totalCount.value = 0
    error.value = e?.response?.data?.detail || e?.message || t('common.error')
  } finally {
    loading.value = false
  }
}

function handlePageSizeChange(size) {
  pageSize.value = size
  currentPage.value = 1
  fetchRoles()
}

function goPrevPage() {
  if (currentPage.value <= 1) return
  currentPage.value -= 1
  fetchRoles()
}

function goNextPage() {
  if (currentPage.value >= totalPages.value) return
  currentPage.value += 1
  fetchRoles()
}

onMounted(() => {
  fetchRoles()
})
</script>
