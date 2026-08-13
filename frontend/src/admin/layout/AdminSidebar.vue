<template>
  <Transition
    enter-active-class="transition-opacity duration-200"
    enter-from-class="opacity-0"
    enter-to-class="opacity-100"
    leave-active-class="transition-opacity duration-150"
    leave-from-class="opacity-100"
    leave-to-class="opacity-0"
  >
    <div
      v-if="showMobileMenu && isMobile"
      @click="$emit('close')"
      class="layout-admin-overlay fixed inset-0 z-40 bg-slate-900/18 backdrop-blur-sm lg:hidden"
    />
  </Transition>

  <aside
    :class="[
      'layout-admin-sidebar z-20 flex h-full w-[19rem] flex-shrink-0 flex-col transition-transform duration-300 ease-in-out',
      isMobile ? 'fixed inset-y-0 left-0 z-50' : 'relative px-3 py-3',
      isMobile && !showMobileMenu ? '-translate-x-full' : 'translate-x-0'
    ]"
  >
    <div class="admin-brand-rail px-4 pt-4 pb-3">
      <router-link
        to="/management"
        class="flex min-w-0 items-center gap-3"
        @click="isMobile && $emit('close')"
      >
        <img
          src="/logo-app.png"
          alt="HyperOps Logo"
          class="h-10 w-auto max-w-[3.25rem] shrink-0 object-contain"
        />
        <div class="min-w-0">
          <p class="truncate text-[1.08rem] font-semibold text-slate-900">
            {{ t('management.logoTitle') }}
          </p>
        </div>
      </router-link>
    </div>

    <div class="mx-5 h-px bg-slate-200/55"></div>

    <div class="admin-sidebar-shell mt-3">
      <div class="relative z-10 flex h-full w-full flex-col">
        <nav class="glass-scrollbar flex-1 overflow-y-auto px-3 pb-4 pt-3">
          <div class="space-y-2">
            <section
              v-for="section in navSections"
              :key="section.key"
              class="admin-section-shell"
              :class="{
                'admin-section-shell-active': isSectionActive(section)
              }"
            >
              <button
                @click="toggleSection(section.key)"
                class="admin-section-trigger"
                :class="{
                  'admin-section-trigger-active': isSectionActive(section)
                }"
              >
                <div class="flex min-w-0 items-center gap-3">
                  <div class="admin-section-icon" :class="section.iconClass">
                    <svg
                      class="h-5 w-5"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        v-for="path in section.iconPaths"
                        :key="path"
                        stroke-linecap="round"
                        stroke-linejoin="round"
                        stroke-width="1.9"
                        :d="path"
                      />
                    </svg>
                  </div>
                  <div class="min-w-0 flex-1 text-left">
                    <p
                      class="truncate text-[0.98rem] font-semibold text-slate-900"
                    >
                      {{ section.title }}
                    </p>
                  </div>
                </div>

                <div class="ml-3 flex items-center gap-2">
                  <svg
                    class="h-4 w-4 text-slate-500 transition-transform duration-200"
                    :class="
                      isSectionOpen(section.key)
                        ? 'rotate-90 text-slate-700'
                        : ''
                    "
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      stroke-linecap="round"
                      stroke-linejoin="round"
                      stroke-width="2"
                      d="M9 5l7 7-7 7"
                    />
                  </svg>
                </div>
              </button>

              <Transition
                enter-active-class="transition-all duration-220 ease-out"
                enter-from-class="max-h-0 translate-y-1 opacity-0"
                enter-to-class="max-h-[28rem] translate-y-0 opacity-100"
                leave-active-class="transition-all duration-180 ease-in"
                leave-from-class="max-h-[28rem] translate-y-0 opacity-100"
                leave-to-class="max-h-0 -translate-y-1 opacity-0"
              >
                <div
                  v-if="isSectionOpen(section.key)"
                  class="admin-subnav-list"
                >
                  <router-link
                    v-for="item in section.items"
                    :key="item.path"
                    :to="item.path"
                    class="admin-subnav-item"
                    :class="{ 'admin-subnav-item-active': isActive(item.path) }"
                    @click="isMobile && $emit('close')"
                    @mouseenter="preloadRoute(item.path)"
                  >
                    <span class="admin-subnav-rail"></span>
                    <span class="admin-subnav-icon">
                      <svg
                        class="h-4 w-4"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path
                          v-for="path in item.iconPaths"
                          :key="path"
                          stroke-linecap="round"
                          stroke-linejoin="round"
                          stroke-width="1.9"
                          :d="path"
                        />
                      </svg>
                    </span>
                    <span class="min-w-0 flex-1 truncate">{{
                      item.label
                    }}</span>
                  </router-link>
                </div>
              </Transition>
            </section>
          </div>
        </nav>
      </div>
    </div>
  </aside>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useWindowSize } from '@vueuse/core'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useUserStore } from '@/store/user'
import { hasFeature, hasOperationPermission } from '@/utils/platformAccess'

defineProps({
  showMobileMenu: {
    type: Boolean,
    default: false
  }
})

defineEmits(['close'])

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const { t } = useI18n()

const MOBILE_BREAKPOINT = 1024
const { width: viewportWidth } = useWindowSize()

const isMobile = computed(() => viewportWidth.value < MOBILE_BREAKPOINT)

const isActive = (path) => {
  return route.path === path || route.path.startsWith(path + '/')
}

const currentUser = computed(() => userStore.userInfo || userStore.user)

const allNavSections = computed(() => [
  {
    key: 'users',
    requiredFeature: 'admin_users',
    title: t('adminNav.userManagement'),
    iconClass: 'admin-section-icon-slate',
    iconPaths: [
      'M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z'
    ],
    items: [
      {
        path: '/management/users',
        label: t('adminNav.users'),
        iconPaths: [
          'M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z'
        ]
      },
      {
        path: '/management/groups',
        label: t('adminNav.groups'),
        iconPaths: [
          'M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857',
          'M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0',
          'M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z'
        ]
      },
      {
        path: '/management/roles',
        label: t('adminNav.roles'),
        iconPaths: [
          'M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z'
        ]
      },
      {
        path: '/management/ldap',
        label: t('adminNav.ldap'),
        iconPaths: [
          'M4 7a3 3 0 013-3h3v3a3 3 0 11-6 0zm10-3h3a3 3 0 110 6h-3V4zM4 17a3 3 0 003 3h3v-3a3 3 0 10-6 0zm10 3h3a3 3 0 100-6h-3v6z',
          'M10 7h4M10 17h4M12 9v6'
        ]
      }
    ]
  },
  {
    key: 'jenkins',
    requiredFeature: 'admin_jenkins',
    title: t('adminNav.jenkinsManagement'),
    iconClass: 'admin-section-icon-slate',
    iconPaths: [
      'M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547',
      'M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z'
    ],
    items: [
      {
        path: '/management/jenkins/instances',
        label: t('adminNav.instances'),
        iconPaths: [
          'M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2',
          'M19 11V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10'
        ]
      },
      {
        path: '/management/jenkins/jobs',
        label: t('adminNav.jobs'),
        iconPaths: [
          'M9 17h6m-6 4h6M5 3h14a2 2 0 012 2v12a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2z',
          'M8 7h8M8 11h8'
        ]
      },
      {
        path: '/management/jenkins/entries',
        label: t('adminNav.entries'),
        iconPaths: ['M4 6h16M4 12h16M4 18h16']
      }
    ]
  },
  {
    key: 'gitlab',
    requiredFeature: 'admin_gitlab',
    title: t('adminNav.gitlabManagement'),
    iconClass: 'admin-section-icon-slate',
    iconPaths: ['M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4'],
    items: [
      {
        path: '/management/gitlab/instances',
        label: t('adminNav.instances'),
        iconPaths: [
          'M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2',
          'M19 11V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10'
        ]
      },
      {
        path: '/management/gitlab/groups',
        label: t('adminNav.groups'),
        iconPaths: [
          'M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857',
          'M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0',
          'M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z'
        ]
      },
      {
        path: '/management/gitlab/projects',
        label: t('adminNav.projects'),
        iconPaths: [
          'M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z'
        ]
      },
      {
        path: '/management/gitlab/branches',
        label: t('adminNav.branches'),
        iconPaths: [
          'M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1'
        ]
      },
      {
        path: '/management/gitlab/tags',
        label: t('adminNav.tags'),
        iconPaths: [
          'M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 002.828 0l-7 7A1.994 1.994 0 013 12V7a4 4 0 014-4z'
        ]
      },
      {
        path: '/management/gitlab/webhooks',
        label: t('adminNav.webhooks'),
        iconPaths: [
          'M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9'
        ]
      },
      {
        path: '/management/gitlab/operation-records',
        label: t('adminNav.operationRecords'),
        iconPaths: [
          'M9 12h6M9 16h6M7 4h10a2 2 0 012 2v14l-4-2-4 2-4-2-4 2V6a2 2 0 012-2z'
        ]
      }
    ]
  },
  {
    key: 'notifier',
    requiredFeature: 'admin_notifications',
    requiredModuleFlag: 'enable_notifier',
    title: t('adminNav.notificationManagement'),
    iconClass: 'admin-section-icon-slate',
    iconPaths: [
      'M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5',
      'M9 17v1a3 3 0 106 0v-1'
    ],
    items: [
      {
        path: '/management/notifier/stats',
        label: t('adminNav.notificationStats'),
        iconPaths: [
          'M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10'
        ]
      },
      {
        path: '/management/notifier/records',
        label: t('adminNav.notificationRecords'),
        iconPaths: ['M4 6h16M4 10h16M4 14h16M4 18h16']
      },
      {
        path: '/management/notifier/channels',
        label: t('adminNav.notificationChannels'),
        iconPaths: [
          'M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7',
          'M15 7a3 3 0 11-6 0 3 3 0 016 0z'
        ]
      },
      {
        path: '/management/notifier/settings',
        label: t('adminNav.notificationSettings'),
        iconPaths: [
          'M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066',
          'M15 12a3 3 0 11-6 0 3 3 0 016 0z'
        ]
      }
    ]
  },
  {
    key: 'actions',
    requiredFeature: 'admin_actions',
    title: t('adminNav.actionOrchestration'),
    iconClass: 'admin-section-icon-slate',
    iconPaths: [
      'M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2v-2',
      'M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m2 3h2m0 0v2m0-2l-4 4'
    ],
    items: [
      {
        path: '/management/actions/templates',
        label: t('adminNav.actionTemplates'),
        iconPaths: ['M4 6h16M4 12h16M4 18h10']
      }
    ]
  },
  {
    key: 'monitoring',
    requiredFeature: 'admin_monitoring',
    requiredModuleFlag: 'enable_monitoring',
    title: t('adminNav.monitoringManagement'),
    iconClass: 'admin-section-icon-slate',
    iconPaths: [
      'M4 13a8 8 0 0116 0',
      'M12 13l3-3',
      'M5 19h14',
      'M7 19a5 5 0 0110 0'
    ],
    items: [
      {
        path: '/management/monitoring/overview',
        label: t('adminNav.monitoringOverview'),
        iconPaths: [
          'M4 13a8 8 0 0116 0',
          'M12 13l3-3',
          'M5 19h14',
          'M7 19a5 5 0 0110 0'
        ]
      },
      {
        path: '/management/monitoring/assets',
        label: t('adminNav.monitoringAssets'),
        iconPaths: ['M4 6h16M4 12h16M4 18h16']
      },
      {
        path: '/management/monitoring/credentials',
        label: t('adminNav.monitoringCredentials'),
        requiredOperationPermission: 'monitoring_credentials_view',
        iconPaths: [
          'M15 7a4 4 0 11-7.75 1.37L3 12.62V16h3v3h3v-3h2.38l1.25-1.25',
          'M17 7h.01'
        ]
      },
      {
        path: '/management/monitoring/probes',
        label: t('adminNav.monitoringProbeManagement'),
        iconPaths: ['M4 12h4l2-6 4 12 2-6h4']
      },
      {
        path: '/management/monitoring/rules',
        label: t('adminNav.monitoringRules'),
        iconPaths: ['M9 12l2 2 4-4', 'M5 4h14v16H5z']
      },
      {
        path: '/management/monitoring/jobs',
        label: t('adminNav.monitoringJobs'),
        iconPaths: ['M4 6h16M4 10h16M4 14h10M4 18h8']
      },
      {
        path: '/management/monitoring/settings',
        label: t('adminNav.monitoringSettings'),
        iconPaths: [
          'M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z',
          'M15 12a3 3 0 11-6 0 3 3 0 016 0z'
        ]
      }
    ]
  }
])

const navSections = computed(() =>
  allNavSections.value
    .filter((section) => {
      if (
        section.requiredModuleFlag &&
        !userStore.hasModuleFlag(section.requiredModuleFlag)
      ) {
        return false
      }
      return hasFeature(currentUser.value, section.requiredFeature)
    })
    .map((section) => ({
      ...section,
      items: section.items.filter(
        (item) =>
          !item.requiredOperationPermission ||
          hasOperationPermission(
            currentUser.value,
            item.requiredOperationPermission
          )
      )
    }))
    .filter((section) => section.items.length)
)

const openSections = ref({
  users: false,
  jenkins: false,
  gitlab: false,
  notifier: false,
  actions: false,
  monitoring: false
})

const isSectionActive = (section) => {
  return section.items.some((item) => isActive(item.path))
}

const isSectionOpen = (key) => {
  return openSections.value[key]
}

const toggleSection = (key) => {
  openSections.value = {
    ...openSections.value,
    [key]: !openSections.value[key]
  }
}

watch(
  () => route.path,
  (newPath) => {
    const activeSection = navSections.value.find((section) =>
      section.items.some(
        (item) => newPath === item.path || newPath.startsWith(`${item.path}/`)
      )
    )

    if (activeSection) {
      openSections.value[activeSection.key] = true
    }
  },
  { immediate: true }
)

const preloadCache = new Set()

const preloadRoute = (path) => {
  if (preloadCache.has(path)) return
  try {
    const resolved = router.resolve(path)
    const matched = resolved.matched[resolved.matched.length - 1]
    if (matched?.components) {
      Object.values(matched.components).forEach((component) => {
        if (typeof component === 'function') {
          preloadCache.add(path)
          component().catch(() => preloadCache.delete(path))
        }
      })
    }
  } catch (_) {
    return
  }
}
</script>
