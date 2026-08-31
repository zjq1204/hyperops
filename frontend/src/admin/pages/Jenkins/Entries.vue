<template>
  <AdminLayout>
    <PageFrame variant="soft" :title="t('adminPages.jenkinsEntries.title')">
      <template #actions>
        <BaseButton @click="createEntry">
          {{ t('adminPages.jenkinsEntries.add') }}
        </BaseButton>
      </template>

      <AdminListSection>
        <AdminTable v-if="entries.length">
          <thead>
            <tr>
              <th class="admin-table-head">{{ t('common.name') }}</th>
              <th class="admin-table-head">
                Jenkins {{ t('adminNav.instances') }}
              </th>
              <th class="admin-table-head">
                {{ t('adminPages.jenkinsEntries.jobName') }}
              </th>
              <th class="admin-table-head">
                {{ t('adminPages.jenkinsEntries.paramCount') }}
              </th>
              <th class="admin-table-head">{{ t('common.status') }}</th>
              <th class="admin-table-head">{{ t('common.actions') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="entry in entries"
              :key="entry.id"
              class="admin-table-row"
            >
              <td class="admin-table-cell">
                <div class="font-semibold text-slate-900">{{ entry.name }}</div>
                <div
                  v-if="entry.description"
                  class="mt-1 text-xs text-slate-500"
                >
                  {{ entry.description }}
                </div>
              </td>
              <td class="admin-table-cell text-sm text-slate-500">
                {{ entry.instance_name }}
              </td>
              <td class="admin-table-cell font-mono text-sm text-slate-600">
                {{ entry.job_name }}
              </td>
              <td class="admin-table-cell text-sm text-slate-500">
                {{ Object.keys(entry.params_config || {}).length }}
              </td>
              <td class="admin-table-cell">
                <span
                  :class="
                    entry.is_active
                      ? 'admin-status-badge admin-status-badge--success'
                      : 'admin-status-badge admin-status-badge--muted'
                  "
                >
                  {{
                    entry.is_active ? t('common.enabled') : t('common.disabled')
                  }}
                </span>
              </td>
              <td class="admin-table-cell">
                <div class="admin-row-actions">
                  <button
                    class="admin-row-action admin-row-action--primary"
                    @click="editEntry(entry)"
                  >
                    {{ t('common.edit') }}
                  </button>
                  <button
                    class="admin-row-action admin-row-action--danger"
                    @click="deleteEntry(entry)"
                  >
                    {{ t('common.delete') }}
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </AdminTable>

        <EmptyState
          v-else
          variant="admin"
          :title="t('adminPages.jenkinsEntries.emptyTitle')"
        >
          <template #icon>
            <svg
              class="h-8 w-8"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
              aria-hidden="true"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="1.8"
                d="M8 4h8l-1 1v5.2a2 2 0 00.6 1.4l5 5A2 2 0 0119.2 20H4.8a2 2 0 01-1.4-3.4l5-5A2 2 0 009 10.2V5L8 4Z"
              />
            </svg>
          </template>
          <template #actions>
            <BaseButton @click="createEntry">
              {{ t('adminPages.jenkinsEntries.add') }}
            </BaseButton>
          </template>
        </EmptyState>
      </AdminListSection>

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
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import AdminListSection from '@/admin/components/AdminListSection.vue'
import AdminTable from '@/admin/components/AdminTable.vue'
import AdminLayout from '@/admin/layout/AdminLayout.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import PageFrame from '@/components/ui/PageFrame.vue'
import { useConfirmDialog } from '@/composables/useConfirmDialog'
import { useToast } from '@/composables/useToast'
import jenkinsApi from '@/api/jenkins'

const { t } = useI18n()
const { showToast } = useToast()
const route = useRoute()
const router = useRouter()
const {
  confirmDialog,
  requestConfirm,
  closeConfirmDialog,
  runConfirmedAction
} = useConfirmDialog()

const entries = ref([])

async function loadEntries() {
  try {
    entries.value = await jenkinsApi.listEntries()
  } catch (error) {
    showToast(
      t('adminPages.jenkinsEntries.toast.loadEntriesFailed', {
        message: error.message
      }),
      'error'
    )
  }
}

function createEntry() {
  router.push({ name: 'AdminJenkinsEntryCreate' })
}

function editEntry(entry) {
  router.push({
    name: 'AdminJenkinsEntryEdit',
    params: { id: entry.id }
  })
}

function deleteEntry(entry) {
  requestConfirm({
    title: t('common.delete'),
    message: t('adminPages.jenkinsEntries.deleteConfirm', { name: entry.name }),
    confirmText: t('common.delete'),
    onConfirm: async () => {
      try {
        await jenkinsApi.deleteEntry(entry.id)
        showToast(t('adminPages.jenkinsEntries.toast.deleteSucceeded'))
        await loadEntries()
      } catch (error) {
        showToast(
          t('adminPages.jenkinsEntries.toast.deleteFailed', {
            message: error.message
          }),
          'error'
        )
      }
    }
  })
}

onMounted(() => {
  if (route.query.job_name) {
    router.replace({
      name: 'AdminJenkinsEntryCreate',
      query: route.query
    })
    return
  }
  loadEntries()
})
</script>
