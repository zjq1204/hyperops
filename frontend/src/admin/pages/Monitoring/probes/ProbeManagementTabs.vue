<template>
  <nav
    class="mb-5 overflow-x-auto border-b border-slate-200"
    :aria-label="t('adminPages.monitoring.probeManagement')"
  >
    <div class="flex min-w-max gap-6 px-1">
      <RouterLink
        v-for="item in items"
        :key="item.path"
        :to="item.path"
        class="relative inline-flex min-h-11 items-center whitespace-nowrap px-1 text-sm font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 focus-visible:ring-offset-2"
        :class="
          route.path === item.path
            ? 'text-sky-700 after:absolute after:inset-x-0 after:bottom-0 after:h-0.5 after:bg-sky-600'
            : 'text-slate-500 hover:text-slate-900'
        "
      >
        {{ item.label }}
      </RouterLink>
    </div>
  </nav>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute } from 'vue-router'

const { t } = useI18n()
const route = useRoute()

const items = computed(() => [
  {
    path: '/management/monitoring/probes',
    label: t('adminPages.monitoring.probeTargetsTab')
  },
  {
    path: '/management/monitoring/probes/nodes',
    label: t('adminPages.monitoring.probeNodesTab')
  },
  {
    path: '/management/monitoring/probes/settings',
    label: t('adminPages.monitoring.probeAccessTab')
  }
])
</script>
