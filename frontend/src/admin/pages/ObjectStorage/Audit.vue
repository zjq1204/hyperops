<template>
  <AdminLayout>
    <PageFrame variant="soft" :title="t('adminPages.objectStorage.audit')">
      <AdminListSection>
        <template #toolbarStart>
          <select
            v-model="tenantId"
            class="admin-filter-control min-w-52"
            @change="loadEvents"
          >
            <option value="">
              {{ t('adminPages.objectStorage.selectTenant') }}
            </option>
            <option
              v-for="tenant in tenants"
              :key="tenant.id"
              :value="String(tenant.id)"
            >
              {{ tenant.name }}
            </option>
          </select>
          <input
            v-model.trim="filters.action"
            class="admin-filter-control min-w-48"
            :placeholder="t('adminPages.objectStorage.auditAction')"
            @keyup.enter="loadEvents"
          />
          <select
            v-model="filters.result"
            class="admin-filter-control min-w-36"
            @change="loadEvents"
          >
            <option value="">
              {{ t('adminPages.objectStorage.allResults') }}
            </option>
            <option value="accepted">{{ resultLabel('accepted') }}</option>
            <option value="succeeded">{{ resultLabel('succeeded') }}</option>
            <option value="failed">{{ resultLabel('failed') }}</option>
            <option value="cancelled">{{ resultLabel('cancelled') }}</option>
          </select>
        </template>
        <template #toolbarEnd
          ><span class="admin-summary-pill">{{
            t('adminPages.objectStorage.lastThirtyDays')
          }}</span
          ><BaseButton
            variant="outline"
            size="sm"
            :loading="loading"
            @click="loadEvents"
            >{{ t('common.refresh') }}</BaseButton
          ></template
        >

        <InlineAlert
          class="mb-4"
          variant="info"
          :message="t('adminPages.objectStorage.auditSanitizedHint')"
        />
        <AdminPageState
          :loading="loading"
          :error="error"
          :empty="!events.length"
          :empty-title="t('adminPages.objectStorage.noAuditEvents')"
        >
          <AdminTable>
            <thead>
              <tr>
                <th class="admin-table-head">
                  {{ t('adminPages.objectStorage.createdAt') }}
                </th>
                <th class="admin-table-head">
                  {{ t('adminPages.objectStorage.auditAction') }}
                </th>
                <th class="admin-table-head">
                  {{ t('adminPages.objectStorage.actor') }}
                </th>
                <th class="admin-table-head">
                  {{ t('adminPages.objectStorage.target') }}
                </th>
                <th class="admin-table-head">
                  {{ t('adminPages.objectStorage.result') }}
                </th>
                <th class="admin-table-head">
                  {{ t('adminPages.objectStorage.reason') }}
                </th>
                <th class="admin-table-head">
                  {{ t('adminPages.objectStorage.requestReference') }}
                </th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="event in events"
                :key="event.id"
                class="admin-table-row"
              >
                <td class="admin-table-cell whitespace-nowrap">
                  {{ formatDate(event.created_at) }}
                </td>
                <td class="admin-table-cell">
                  <p class="font-medium text-slate-900">
                    {{ actionLabel(event.action) }}
                  </p>
                  <p class="mt-1 text-xs text-slate-500">
                    {{
                      event.application_id
                        ? t('adminPages.objectStorage.taskReference', {
                            id: event.application_id
                          })
                        : t('common.emptyValue')
                    }}
                  </p>
                </td>
                <td class="admin-table-cell">
                  {{
                    event.actor_id
                      ? t('adminPages.objectStorage.userReference', {
                          id: event.actor_id
                        })
                      : t('adminPages.objectStorage.systemActor')
                  }}
                </td>
                <td class="admin-table-cell">
                  <p>{{ event.target_type || t('common.emptyValue') }}</p>
                  <p class="mt-1 text-xs text-slate-500">
                    {{ event.target_id || t('common.emptyValue') }}
                  </p>
                </td>
                <td class="admin-table-cell">
                  <span :class="resultClass(event.result)">{{
                    resultLabel(event.result)
                  }}</span>
                </td>
                <td
                  class="admin-table-cell max-w-64 whitespace-normal text-slate-600"
                >
                  {{ event.reason || t('common.emptyValue') }}
                </td>
                <td
                  class="admin-table-cell max-w-52 truncate font-mono text-xs text-slate-500"
                  :title="event.request_id"
                >
                  {{ event.request_id || t('common.emptyValue') }}
                </td>
              </tr>
            </tbody>
          </AdminTable>
        </AdminPageState>
      </AdminListSection>
    </PageFrame>
  </AdminLayout>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import AdminLayout from '@/admin/layout/AdminLayout.vue'
import AdminListSection from '@/admin/components/AdminListSection.vue'
import AdminPageState from '@/admin/components/AdminPageState.vue'
import AdminTable from '@/admin/components/AdminTable.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import InlineAlert from '@/components/ui/InlineAlert.vue'
import PageFrame from '@/components/ui/PageFrame.vue'
import { extractErrorMessage } from '@/utils/api'
import objectStorageAdminApi from '@/admin/api/objectStorage'

const { t, locale } = useI18n()
const tenants = ref([])
const tenantId = ref('')
const events = ref([])
const loading = ref(true)
const error = ref('')
const filters = reactive({ action: '', result: '' })
const formatDate = (value) =>
  value
    ? new Intl.DateTimeFormat(locale.value, {
        dateStyle: 'medium',
        timeStyle: 'short'
      }).format(new Date(value))
    : t('common.emptyValue')
const resultLabel = (value) =>
  t(
    `adminPages.objectStorage.results.${value || 'unknown'}`,
    value || t('common.emptyValue')
  )
const actionLabel = (value) =>
  t(
    `adminPages.objectStorage.auditActions.${String(value || '').replaceAll('.', '_')}`,
    value || t('common.emptyValue')
  )
const resultClass = (value) => [
  'admin-status-badge',
  ['succeeded', 'accepted'].includes(value)
    ? 'admin-status-badge--success'
    : value === 'failed'
      ? 'admin-status-badge--danger'
      : 'admin-status-badge--muted'
]
async function load() {
  loading.value = true
  error.value = ''
  try {
    tenants.value = await objectStorageAdminApi.listTenants()
    tenantId.value = String(tenants.value[0]?.id || '')
    await loadEvents()
  } catch (err) {
    error.value = extractErrorMessage(
      err,
      t('adminPages.objectStorage.loadFailed')
    )
  } finally {
    loading.value = false
  }
}
async function loadEvents() {
  if (!tenantId.value) return
  loading.value = true
  error.value = ''
  try {
    events.value = await objectStorageAdminApi.listAuditEvents({
      tenant_id: tenantId.value,
      action: filters.action || undefined,
      result: filters.result || undefined
    })
  } catch (err) {
    error.value = extractErrorMessage(
      err,
      t('adminPages.objectStorage.loadFailed')
    )
  } finally {
    loading.value = false
  }
}
onMounted(load)
</script>
