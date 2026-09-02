<template>
  <AdminLayout>
    <PageFrame
      variant="soft"
      :title="t('adminPages.authentication.title')"
      :subtitle="t('adminPages.authentication.subtitle')"
    >
      <AdminListSection>
        <template #toolbarStart>
          <span class="admin-summary-pill">
            {{
              t('adminPages.authentication.sourceCount', {
                count: sources.length
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
        </template>

        <AdminPageState :loading="loading" :error="error">
          <AdminTable>
            <thead>
              <tr>
                <th class="admin-table-head">
                  {{ t('adminPages.authentication.source') }}
                </th>
                <th class="admin-table-head hidden md:table-cell">
                  {{ t('adminPages.authentication.type') }}
                </th>
                <th class="admin-table-head hidden md:table-cell">
                  {{ t('adminPages.authentication.scope') }}
                </th>
                <th class="admin-table-head">
                  {{ t('common.status') }}
                </th>
                <th class="admin-table-head text-right">
                  <span class="sr-only">
                    {{ t('adminPages.authentication.nextStep') }}
                  </span>
                </th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="source in sources"
                :key="source.key"
                class="admin-table-row cursor-pointer"
                tabindex="0"
                @click="openSource(source)"
                @keydown.enter.prevent="openSource(source)"
                @keydown.space.prevent="openSource(source)"
              >
                <td class="admin-table-cell min-w-40">
                  <div class="min-w-0">
                    <p class="font-medium text-slate-900">{{ source.name }}</p>
                    <p class="mt-0.5 hidden text-xs text-slate-500 md:block">
                      {{ source.description }}
                    </p>
                    <p class="mt-1 text-xs leading-5 text-slate-500 md:hidden">
                      {{ source.type }} · {{ source.scope }}
                    </p>
                  </div>
                </td>
                <td
                  class="admin-table-cell hidden text-slate-600 md:table-cell"
                >
                  {{ source.type }}
                </td>
                <td
                  class="admin-table-cell hidden text-slate-600 md:table-cell"
                >
                  {{ source.scope }}
                </td>
                <td class="admin-table-cell whitespace-nowrap">
                  <span
                    :class="[
                      'admin-status-badge',
                      'admin-status-badge--' + source.statusTone
                    ]"
                  >
                    {{ source.statusLabel }}
                  </span>
                </td>
                <td class="admin-table-cell whitespace-nowrap text-right">
                  <RouterLink
                    :to="source.to"
                    class="inline-flex min-h-9 items-center gap-1.5 text-sm font-medium text-sky-700 hover:text-sky-900"
                    :aria-label="`${source.name} · ${source.actionLabel}`"
                  >
                    {{ source.actionLabel }}
                    <span aria-hidden="true" class="text-base leading-none"
                      >→</span
                    >
                  </RouterLink>
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
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import AdminLayout from '@/admin/layout/AdminLayout.vue'
import AdminListSection from '@/admin/components/AdminListSection.vue'
import AdminPageState from '@/admin/components/AdminPageState.vue'
import AdminTable from '@/admin/components/AdminTable.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import PageFrame from '@/components/ui/PageFrame.vue'
import { managementApi } from '@/admin/api/management'
import objectStorageAdminApi from '@/admin/api/objectStorage'
import { useUserStore } from '@/store/user'
import { hasFeature } from '@/utils/platformAccess'

const { t } = useI18n()
const router = useRouter()
const userStore = useUserStore()
const ldapInstances = ref([])
const feishuSources = ref([])
const loading = ref(false)
const error = ref('')
const currentUser = computed(() => userStore.userInfo || userStore.user)
const canManageFeishu = computed(
  () =>
    hasFeature(currentUser.value, 'admin_object_storage') &&
    userStore.hasModuleFlag('enable_object_storage')
)

const sources = computed(() => [
  ...ldapInstances.value.map((instance) => ({
    key: 'ldap-' + instance.id,
    name: instance.name || instance.host || 'LDAP',
    description: formatLdapEndpoint(instance),
    type: 'LDAP / AD',
    scope: t('adminPages.authentication.directoryGroupMapping'),
    statusTone: instance.enabled ? 'success' : 'muted',
    statusLabel: instance.enabled ? t('common.enabled') : t('common.disabled'),
    ...authenticationAction(instance, 'ldap'),
    to: {
      path: '/management/ldap',
      query: { instance: instance.id }
    }
  })),
  ...feishuSources.value.map((config) => ({
    key: 'feishu',
    name: t('adminPages.authentication.feishu'),
    description: t('adminPages.authentication.feishuListHint'),
    type: 'OAuth 2.0',
    scope: formatAccessScope(config),
    statusTone: feishuStatus(config).tone,
    statusLabel: feishuStatus(config).label,
    ...authenticationAction(config, 'feishu'),
    to: {
      path: '/management/authentication/feishu',
      query: {}
    }
  }))
])

function normalizeCollection(payload) {
  return Array.isArray(payload) ? payload : payload?.results || []
}

function openSource(source) {
  router.push(source.to)
}

function formatLdapEndpoint(instance) {
  if (!instance?.host) return t('adminPages.authentication.directorySource')
  const protocol = instance.use_ssl ? 'ldaps' : 'ldap'
  return [protocol, '://', instance.host, ':', instance.port || 389].join('')
}

function formatAccessScope(config) {
  return (
    config?.access_group_name || t('adminPages.authentication.notConfigured')
  )
}

function authenticationAction(config, provider) {
  if (provider === 'ldap') {
    const actionKey = config?.enabled ? 'manageConfiguration' : 'continueSetup'
    return {
      actionKey,
      actionLabel: t(`adminPages.authentication.${actionKey}`)
    }
  }

  if (!config?.id) {
    return {
      actionKey: 'startSetup',
      actionLabel: t('adminPages.authentication.startSetup')
    }
  }

  const actionKey =
    config.validation_status === 'invalid'
      ? 'fixConfiguration'
      : config.validation_status === 'valid'
        ? 'manageConfiguration'
        : 'continueSetup'
  return {
    actionKey,
    actionLabel: t(`adminPages.authentication.${actionKey}`)
  }
}

function feishuStatus(config) {
  if (!config?.id) {
    return {
      tone: 'muted',
      label: t('adminPages.authentication.notConfigured')
    }
  }
  if (config.validation_status === 'valid') {
    return {
      tone: 'success',
      label: t('adminPages.authentication.validatedStatus')
    }
  }
  if (config.validation_status === 'invalid') {
    return {
      tone: 'danger',
      label: t('adminPages.authentication.validationFailedStatus')
    }
  }
  return {
    tone: 'info',
    label: t('adminPages.authentication.pendingValidation')
  }
}

async function loadFeishuSources() {
  if (!canManageFeishu.value) {
    feishuSources.value = []
    return
  }
  try {
    feishuSources.value = [await objectStorageAdminApi.getFeishu()]
  } catch {
    feishuSources.value = []
  }
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const ldapPayload = await managementApi.getLdapInstances({
      page: 1,
      page_size: 200
    })
    ldapInstances.value = normalizeCollection(ldapPayload)
    await loadFeishuSources()
  } catch (requestError) {
    error.value =
      requestError?.response?.data?.detail ||
      requestError?.message ||
      t('adminPages.authentication.loadFailed')
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>
