<template>
  <AppLayout>
    <PageFrame
      :eyebrow="t('dashboard.eyebrow')"
      :title="t('dashboard.title')"
      :subtitle="t('dashboard.subtitle')"
      variant="soft"
    >
      <div class="mx-auto grid max-w-5xl gap-5">
        <section class="surface-panel-strong overflow-hidden">
          <div class="border-b border-slate-200/70 px-6 py-5">
            <h2 class="section-title">{{ t('dashboard.sections.workspaceTitle') }}</h2>
            <p class="section-copy">{{ t('dashboard.sections.workspaceSubtitle') }}</p>
          </div>
          <div class="divide-y divide-slate-200/70">
            <router-link
              v-for="entry in workspaceEntries"
              :key="entry.title"
              :to="entry.to"
              class="group flex items-center justify-between gap-4 px-6 py-5 transition-colors duration-150 hover:bg-slate-50/80"
            >
              <div class="flex min-w-0 items-center gap-4">
                <div
                  :class="entry.iconClass"
                  class="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl border text-slate-700"
                >
                  <svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path
                      :d="entry.iconPath"
                      stroke-linecap="round"
                      stroke-linejoin="round"
                      stroke-width="2"
                    />
                  </svg>
                </div>
                <div class="min-w-0">
                  <h3 class="text-sm font-semibold text-slate-900">
                    {{ entry.title }}
                  </h3>
                  <p class="mt-1 text-sm leading-6 text-slate-500">
                    {{ entry.description }}
                  </p>
                </div>
              </div>

              <div class="flex items-center gap-3 text-slate-400 transition-colors duration-150 group-hover:text-slate-600">
                <span class="hidden text-sm font-medium text-slate-400 md:inline">
                  {{ t('dashboard.open') }}
                </span>
                <svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
                </svg>
              </div>
            </router-link>
          </div>
        </section>

        <section
          v-if="adminEntries.length"
          class="surface-panel-strong overflow-hidden"
        >
          <div class="border-b border-slate-200/70 px-6 py-5">
            <h2 class="section-title">{{ t('dashboard.sections.adminTitle') }}</h2>
            <p class="section-copy">{{ t('dashboard.sections.adminSubtitle') }}</p>
          </div>
          <div class="divide-y divide-slate-200/70">
            <router-link
              v-for="entry in adminEntries"
              :key="entry.title"
              :to="entry.to"
              class="group flex items-center justify-between gap-4 px-6 py-5 transition-colors duration-150 hover:bg-slate-50/80"
            >
              <div class="flex min-w-0 items-center gap-4">
                <div
                  :class="entry.iconClass"
                  class="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl border text-slate-700"
                >
                  <svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path
                      :d="entry.iconPath"
                      stroke-linecap="round"
                      stroke-linejoin="round"
                      stroke-width="2"
                    />
                  </svg>
                </div>
                <div class="min-w-0">
                  <h3 class="text-sm font-semibold text-slate-900">
                    {{ entry.title }}
                  </h3>
                  <p class="mt-1 text-sm leading-6 text-slate-500">
                    {{ entry.description }}
                  </p>
                </div>
              </div>

              <div class="flex items-center gap-3 text-slate-400 transition-colors duration-150 group-hover:text-slate-600">
                <span class="hidden text-sm font-medium text-slate-400 md:inline">
                  {{ t('dashboard.open') }}
                </span>
                <svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
                </svg>
              </div>
            </router-link>
          </div>
        </section>
      </div>
    </PageFrame>
  </AppLayout>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useUserStore } from '@/store/user'
import AppLayout from '@/components/layout/AppLayout.vue'
import PageFrame from '@/components/ui/PageFrame.vue'
import { getAccessProfile } from '@/utils/platformAccess'

const { t } = useI18n()
const userStore = useUserStore()

const showAdminConsole = computed(() => userStore.userHasFeature('admin_console'))
const adminLandingPath = computed(() => {
  const profile = getAccessProfile(userStore.userInfo || userStore.user)
  return (
    profile.available_platforms?.find((item) => item.key === 'admin_console')
      ?.default_path || '/management/users'
  )
})

const workspaceEntries = computed(() => {
  const entries = []
  if (userStore.userHasFeature('workspace_jenkins')) {
    entries.push(
      {
        title: t('dashboard.overview.moduleJenkinsWorkspace'),
        description: t('dashboard.overview.moduleJenkinsWorkspaceDesc'),
        to: { name: 'JenkinsWorkspace' },
        iconClass: 'border-sky-200 bg-sky-50',
        iconPath:
          'M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z'
      },
      {
        title: t('dashboard.overview.moduleJenkinsRecords'),
        description: t('dashboard.overview.moduleJenkinsRecordsDesc'),
        to: { name: 'JenkinsRecords' },
        iconClass: 'border-indigo-200 bg-indigo-50',
        iconPath:
          'M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z'
      }
    )
  }
  entries.push({
    title: t('dashboard.overview.quickActionSettings'),
    description: t('dashboard.overview.quickActionSettingsDesc'),
    to: { name: 'SettingsProfile' },
    iconClass: 'border-slate-200 bg-slate-100',
    iconPath:
      'M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z'
  })
  return entries
})

const adminEntries = computed(() => {
  if (!showAdminConsole.value) return []

  return [
    {
      title: t('management.adminConsole'),
      description: t('dashboard.overview.adminConsoleDesc'),
      to: adminLandingPath.value,
      iconClass: 'border-amber-200 bg-amber-50',
      iconPath:
        'M12 8c-2.21 0-4 1.79-4 4v1H6a2 2 0 00-2 2v1h16v-1a2 2 0 00-2-2h-2v-1c0-2.21-1.79-4-4-4zm0-4l7 3v5c0 4.418-3.134 8.167-7 9-3.866-.833-7-4.582-7-9V7l7-3z'
    }
  ]
})
</script>
