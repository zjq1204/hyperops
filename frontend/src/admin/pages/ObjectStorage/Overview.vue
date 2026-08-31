<template>
  <AdminLayout>
    <PageFrame
      variant="soft"
      :title="t('adminPages.objectStorage.title')"
      :subtitle="t('adminPages.objectStorage.overviewSubtitle')"
    >
      <AdminListSection>
        <template #toolbarStart>
          <span class="admin-summary-pill">
            {{
              t('adminPages.objectStorage.tenantCount', {
                count: tenants.length
              })
            }}
          </span>
        </template>
        <template #toolbarEnd>
          <BaseButton
            variant="outline"
            size="sm"
            :loading="loading"
            @click="load"
          >
            {{ t('common.refresh') }}
          </BaseButton>
          <router-link
            class="btn btn-primary btn-sm"
            to="/management/object-storage/enterprise-access"
          >
            {{ t('adminPages.objectStorage.configureAccess') }}
          </router-link>
        </template>

        <AdminPageState
          :loading="loading"
          :error="error"
          :empty="!tenants.length"
        >
          <section class="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <article
              v-for="stat in stats"
              :key="stat.key"
              class="admin-workbench-panel p-5"
            >
              <p
                class="text-xs font-semibold uppercase tracking-wide text-slate-500"
              >
                {{ t(stat.label) }}
              </p>
              <p
                class="mt-3 text-3xl font-semibold tabular-nums text-slate-950"
              >
                {{ stat.value }}
              </p>
              <p class="mt-1 text-xs text-slate-500">{{ t(stat.hint) }}</p>
            </article>
          </section>

          <section
            class="mt-5 grid gap-5 xl:grid-cols-[minmax(0,1.3fr)_minmax(18rem,0.7fr)]"
          >
            <article class="admin-workbench-panel overflow-hidden">
              <div
                class="flex items-start justify-between gap-4 border-b border-slate-200 px-5 py-4"
              >
                <div>
                  <h2 class="text-sm font-semibold text-slate-950">
                    {{ t('adminPages.objectStorage.pendingTitle') }}
                  </h2>
                  <p class="mt-1 text-xs leading-5 text-slate-500">
                    {{ t('adminPages.objectStorage.pendingHint') }}
                  </p>
                </div>
                <router-link
                  class="text-sm font-semibold text-sky-700 hover:text-sky-900"
                  to="/management/object-storage/tasks"
                >
                  {{ t('adminPages.objectStorage.viewTasks') }}
                </router-link>
              </div>
              <div
                v-if="attentionApplications.length"
                class="divide-y divide-slate-200"
              >
                <article
                  v-for="application in attentionApplications"
                  :key="application.id"
                  class="flex flex-col gap-3 px-5 py-4 sm:flex-row sm:items-center sm:justify-between"
                >
                  <div class="min-w-0">
                    <p class="font-medium text-slate-900">
                      {{ actionLabel(application.action_type) }}
                    </p>
                    <p class="mt-1 text-xs text-slate-500">
                      {{ tenantName(application.tenant_id) }} ·
                      {{ formatDate(application.created_at) }}
                    </p>
                    <p
                      v-if="application.error_summary"
                      class="mt-2 text-xs leading-5 text-rose-700"
                    >
                      {{ application.error_summary }}
                    </p>
                  </div>
                  <StatusBadge :status="statusBadge(application.status)" />
                </article>
              </div>
              <EmptyState
                v-else
                variant="admin"
                :title="t('adminPages.objectStorage.noPending')"
              />
            </article>

            <article class="admin-workbench-panel p-5">
              <h2 class="text-sm font-semibold text-slate-950">
                {{ t('adminPages.objectStorage.quickLinksTitle') }}
              </h2>
              <div
                class="mt-4 divide-y divide-slate-200 border-y border-slate-200"
              >
                <router-link
                  v-for="link in quickLinks"
                  :key="link.to"
                  :to="link.to"
                  class="flex min-h-12 items-center justify-between gap-3 text-sm font-medium text-slate-700 hover:text-sky-700"
                >
                  {{ t(link.label) }}
                  <span aria-hidden="true" class="text-slate-400">→</span>
                </router-link>
              </div>
            </article>
          </section>

          <section class="mt-5 admin-workbench-panel overflow-hidden">
            <div class="border-b border-slate-200 px-5 py-4">
              <h2 class="text-sm font-semibold text-slate-950">
                {{ t('adminPages.objectStorage.tenantsTitle') }}
              </h2>
              <p class="mt-1 text-xs leading-5 text-slate-500">
                {{ t('adminPages.objectStorage.tenantsHint') }}
              </p>
            </div>
            <AdminTable>
              <thead>
                <tr>
                  <th class="admin-table-head">
                    {{ t('adminPages.objectStorage.tenant') }}
                  </th>
                  <th class="admin-table-head">
                    {{ t('adminPages.objectStorage.bucketQuota') }}
                  </th>
                  <th class="admin-table-head">
                    {{ t('adminPages.objectStorage.deliveryLifetime') }}
                  </th>
                  <th class="admin-table-head">{{ t('common.status') }}</th>
                  <th class="admin-table-head text-right">
                    {{ t('common.actions') }}
                  </th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="tenant in tenants"
                  :key="tenant.id"
                  class="admin-table-row"
                >
                  <td class="admin-table-cell">
                    <p class="font-semibold text-slate-900">
                      {{ tenant.name }}
                    </p>
                    <p class="mt-1 text-xs text-slate-500">{{ tenant.code }}</p>
                  </td>
                  <td class="admin-table-cell tabular-nums text-slate-700">
                    {{ tenant.default_bucket_quota }}
                  </td>
                  <td class="admin-table-cell text-slate-700">
                    {{ formatLifetime(tenant.delivery_lifetime_seconds) }}
                  </td>
                  <td class="admin-table-cell">
                    <StatusBadge
                      :status="tenant.enabled ? 'enabled' : 'disabled'"
                    />
                  </td>
                  <td class="admin-table-cell text-right">
                    <router-link
                      class="text-sm font-semibold text-sky-700 hover:text-sky-900"
                      :to="{
                        path: '/management/object-storage/enterprise-access',
                        query: { tenant: tenant.id }
                      }"
                      >{{ t('common.manage') }}</router-link
                    >
                  </td>
                </tr>
              </tbody>
            </AdminTable>
          </section>
        </AdminPageState>
      </AdminListSection>
    </PageFrame>
  </AdminLayout>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import AdminLayout from '@/admin/layout/AdminLayout.vue'
import AdminListSection from '@/admin/components/AdminListSection.vue'
import AdminPageState from '@/admin/components/AdminPageState.vue'
import AdminTable from '@/admin/components/AdminTable.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import PageFrame from '@/components/ui/PageFrame.vue'
import StatusBadge from '@/components/ui/StatusBadge.vue'
import { extractErrorMessage } from '@/utils/api'
import objectStorageAdminApi from '@/admin/api/objectStorage'

const { t, locale } = useI18n()
const loading = ref(true)
const error = ref('')
const tenants = ref([])
const applications = ref([])
const resources = ref({ members: [], identities: [], buckets: [], keys: [] })

const quickLinks = [
  {
    to: '/management/object-storage/enterprise-access',
    label: 'adminPages.objectStorage.enterpriseAccess'
  },
  {
    to: '/management/object-storage/resources',
    label: 'adminPages.objectStorage.resources'
  },
  {
    to: '/management/object-storage/tasks',
    label: 'adminPages.objectStorage.tasks'
  },
  {
    to: '/management/object-storage/audit',
    label: 'adminPages.objectStorage.audit'
  }
]

const attentionApplications = computed(() =>
  applications.value
    .filter((item) =>
      ['manual_required', 'failed', 'pending', 'running'].includes(item.status)
    )
    .sort(
      (a, b) =>
        Number(b.status === 'manual_required') -
          Number(a.status === 'manual_required') ||
        new Date(b.created_at) - new Date(a.created_at)
    )
    .slice(0, 6)
)

const stats = computed(() => [
  {
    key: 'tenants',
    label: 'adminPages.objectStorage.statTenants',
    hint: 'adminPages.objectStorage.statTenantsHint',
    value: tenants.value.length
  },
  {
    key: 'members',
    label: 'adminPages.objectStorage.statMembers',
    hint: 'adminPages.objectStorage.statMembersHint',
    value: resources.value.members.length
  },
  {
    key: 'buckets',
    label: 'adminPages.objectStorage.statBuckets',
    hint: 'adminPages.objectStorage.statBucketsHint',
    value: resources.value.buckets.length
  },
  {
    key: 'attention',
    label: 'adminPages.objectStorage.statAttention',
    hint: 'adminPages.objectStorage.statAttentionHint',
    value: applications.value.filter((item) =>
      ['manual_required', 'failed'].includes(item.status)
    ).length
  }
])

const tenantName = (id) =>
  tenants.value.find((tenant) => tenant.id === id)?.name ||
  t('common.emptyValue')
const actionLabel = (value) =>
  t(
    `adminPages.objectStorage.actions.${value}`,
    value || t('common.emptyValue')
  )
const statusBadge = (value) =>
  ({
    manual_required: 'failed',
    failed: 'failed',
    pending: 'pending',
    running: 'processing',
    delivery_ready: 'success',
    succeeded: 'success',
    cancelled: 'disabled'
  })[value] || 'unknown'
const formatDate = (value) =>
  value
    ? new Intl.DateTimeFormat(locale.value, {
        dateStyle: 'medium',
        timeStyle: 'short'
      }).format(new Date(value))
    : t('common.emptyValue')
const formatLifetime = (seconds) =>
  seconds >= 86400
    ? t('adminPages.objectStorage.days', { count: Math.round(seconds / 86400) })
    : t('adminPages.objectStorage.hours', { count: Math.round(seconds / 3600) })

async function load() {
  loading.value = true
  error.value = ''
  try {
    tenants.value = await objectStorageAdminApi.listTenants()
    const tenantIds = tenants.value.map((tenant) => tenant.id)
    const [applications, members, identities, buckets, keys] =
      await Promise.all([
        Promise.all(
          tenantIds.map((id) => objectStorageAdminApi.listApplications(id))
        ).then((lists) => lists.flat()),
        Promise.all(
          tenantIds.map((id) => objectStorageAdminApi.listMembers(id))
        ).then((lists) => lists.flat()),
        Promise.all(
          tenantIds.map((id) => objectStorageAdminApi.listCloudIdentities(id))
        ).then((lists) => lists.flat()),
        Promise.all(
          tenantIds.map((id) => objectStorageAdminApi.listBuckets(id))
        ).then((lists) => lists.flat()),
        Promise.all(
          tenantIds.map((id) => objectStorageAdminApi.listAccessKeys(id))
        ).then((lists) => lists.flat())
      ])
    applications.value = applications
    resources.value = { members, identities, buckets, keys }
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
