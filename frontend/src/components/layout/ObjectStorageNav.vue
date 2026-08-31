<template>
  <nav
    class="mb-5 overflow-x-auto border-b border-slate-200"
    :aria-label="t('objectStorage.nav.label')"
  >
    <div class="flex min-w-max gap-1">
      <router-link
        v-for="item in items"
        :key="item.name"
        :to="{ name: item.name }"
        class="relative flex min-h-11 items-center gap-2 px-3 text-sm font-medium text-slate-500 transition-colors hover:text-slate-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 focus-visible:ring-offset-2"
        active-class="text-slate-950 after:absolute after:inset-x-3 after:bottom-0 after:h-0.5 after:bg-sky-600"
      >
        <svg
          class="h-4 w-4 shrink-0"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
          aria-hidden="true"
        >
          <path
            :d="item.icon"
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="2"
          />
        </svg>
        <span>{{ t(item.label) }}</span>
      </router-link>
    </div>
  </nav>
</template>

<script setup>
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

const items = [
  {
    name: 'ObjectStorageOverview',
    label: 'navigation.objectStorageOverview',
    icon: 'M4 6h6v6H4V6Zm10 0h6v4h-6V6ZM4 16h6v2H4v-2Zm10-2h6v4h-6v-4Z'
  },
  {
    name: 'ObjectStorageBuckets',
    label: 'navigation.objectStorageBuckets',
    icon: 'M4 7.5C4 5.57 7.58 4 12 4s8 1.57 8 3.5S16.42 11 12 11 4 9.43 4 7.5Zm0 0V16.5C4 18.43 7.58 20 12 20s8-1.57 8-3.5v-9'
  },
  {
    name: 'ObjectStorageCredentials',
    label: 'navigation.objectStorageCredentials',
    icon: 'M15 7a4 4 0 1 1-7.87 1H3v4h3v3h3v-3h2.13A4 4 0 0 1 15 7Z'
  },
  {
    name: 'ObjectStorageApplications',
    label: 'navigation.objectStorageApplications',
    icon: 'M9 5h6m-7 4h8m-8 4h8m-8 4h5M6 3h12a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2Z'
  }
]
</script>
