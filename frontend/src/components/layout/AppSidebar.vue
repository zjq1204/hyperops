<template>
  <!-- Mobile overlay -->
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
      class="workspace-sidebar-overlay"
    />
  </Transition>

  <!-- Sidebar -->
  <aside
    :class="[
      'workspace-sidebar',
      isMobile ? 'fixed inset-y-0 left-0 z-50' : 'static',
      isMobile && !showMobileMenu ? '-translate-x-full' : 'translate-x-0'
    ]"
  >
    <!-- Logo and close button -->
    <div class="workspace-sidebar-header">
      <router-link
        to="/dashboard"
        class="flex min-w-0 flex-1 items-center space-x-3"
        @click="isMobile && $emit('close')"
      >
        <img
          src="/logo-mark.svg"
          alt="HyperOps"
          width="32"
          height="32"
          class="h-8 w-8 shrink-0 object-contain"
        />
        <span class="truncate text-lg font-semibold text-slate-900">{{
          t('common.appName')
        }}</span>
      </router-link>
      <button
        v-if="isMobile"
        @click="$emit('close')"
        class="p-2 rounded-md text-gray-600 hover:text-gray-900 hover:bg-gray-100"
      >
        <svg
          class="w-5 h-5"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="2"
            d="M6 18L18 6M6 6l12 12"
          />
        </svg>
      </button>
    </div>

    <!-- Navigation -->
    <nav
      class="workspace-sidebar-nav glass-scrollbar"
    >
      <!-- Dashboard -->
      <router-link
        v-if="canUseDashboard"
        to="/dashboard"
        class="workspace-sidebar-item"
        :class="isActive('/dashboard') ? 'workspace-sidebar-item-active' : ''"
        @click="isMobile && $emit('close')"
      >
        <svg
          class="w-5 h-5"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="2"
            d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6"
          />
        </svg>
        <span>{{ t('navigation.dashboard') }}</span>
      </router-link>

      <!-- Jenkins Section -->
      <div v-if="canUseJenkins" class="workspace-sidebar-group">
        <button
          @click="toggleJenkinsMenu"
          class="workspace-sidebar-item workspace-sidebar-item-parent w-full"
        >
          <svg
            class="w-5 h-5"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z"
            />
          </svg>
          <span class="flex-1 text-left">{{ t('navigation.jenkins') }}</span>
          <svg
            class="w-4 h-4 transition-transform"
            :class="jenkinsMenuOpen ? 'rotate-90' : ''"
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
        </button>
        <Transition
          enter-active-class="transition-all duration-200 ease-out"
          enter-from-class="opacity-0 max-h-0"
          enter-to-class="opacity-100 max-h-96"
          leave-active-class="transition-all duration-200 ease-in"
          leave-from-class="opacity-100 max-h-96"
          leave-to-class="opacity-0 max-h-0"
        >
          <div v-if="jenkinsMenuOpen" class="workspace-sidebar-submenu">
            <router-link
              to="/jenkins/workspace"
              class="workspace-sidebar-item workspace-sidebar-item-child"
              :class="
                isActive('/jenkins/workspace')
                  ? 'workspace-sidebar-item-active'
                  : ''
              "
              @click="isMobile && $emit('close')"
            >
              <svg
                class="w-4 h-4"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="2"
                  d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6"
                />
              </svg>
              <span>{{ t('navigation.jenkinsWorkspace') }}</span>
            </router-link>
            <router-link
              to="/jenkins/records"
              class="workspace-sidebar-item workspace-sidebar-item-child"
              :class="
                isActive('/jenkins/records')
                  ? 'workspace-sidebar-item-active'
                  : ''
              "
              @click="isMobile && $emit('close')"
            >
              <svg
                class="w-4 h-4"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="2"
                  d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                />
              </svg>
              <span>{{ t('navigation.jenkinsRecords') }}</span>
            </router-link>
          </div>
        </Transition>
      </div>

      <div v-if="canUseActions" class="workspace-sidebar-group">
        <button
          @click="toggleActionsMenu"
          class="workspace-sidebar-item workspace-sidebar-item-parent w-full"
        >
          <svg
            class="w-5 h-5"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2v-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m2 3h2m0 0v2m0-2l-4 4"
            />
          </svg>
          <span class="flex-1 text-left">{{ t('navigation.actionOrchestration') }}</span>
          <svg
            class="w-4 h-4 transition-transform"
            :class="actionsMenuOpen ? 'rotate-90' : ''"
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
        </button>
        <Transition
          enter-active-class="transition-all duration-200 ease-out"
          enter-from-class="opacity-0 max-h-0"
          enter-to-class="opacity-100 max-h-96"
          leave-active-class="transition-all duration-200 ease-in"
          leave-from-class="opacity-100 max-h-96"
          leave-to-class="opacity-0 max-h-0"
        >
          <div v-if="actionsMenuOpen" class="workspace-sidebar-submenu">
            <router-link
              to="/actions/workspace"
              class="workspace-sidebar-item workspace-sidebar-item-child"
              :class="isActive('/actions/workspace') ? 'workspace-sidebar-item-active' : ''"
              @click="isMobile && $emit('close')"
            >
              <svg
                class="w-4 h-4"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="2"
                  d="M4 6h16M4 12h16M4 18h7"
                />
              </svg>
              <span>{{ t('navigation.actionWorkspace') }}</span>
            </router-link>
            <router-link
              to="/actions/runs"
              class="workspace-sidebar-item workspace-sidebar-item-child"
              :class="isActive('/actions/runs') ? 'workspace-sidebar-item-active' : ''"
              @click="isMobile && $emit('close')"
            >
              <svg
                class="w-4 h-4"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="2"
                  d="M9 12h6m-6 4h6M7 4h10a2 2 0 012 2v12a2 2 0 01-2 2H7a2 2 0 01-2-2V6a2 2 0 012-2z"
                />
              </svg>
              <span>{{ t('navigation.actionRuns') }}</span>
            </router-link>
          </div>
        </Transition>
      </div>

    </nav>
  </aside>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useUserStore } from '@/store/user'
import { hasFeature } from '@/utils/platformAccess'

defineProps({
  showMobileMenu: {
    type: Boolean,
    default: false
  }
})

defineEmits(['close'])

const route = useRoute()
const userStore = useUserStore()
const { t } = useI18n()

const jenkinsMenuOpen = ref(true)
const actionsMenuOpen = ref(true)

const currentUser = computed(() => userStore.userInfo || userStore.user)
const canUseDashboard = computed(() =>
  hasFeature(currentUser.value, 'workspace_dashboard')
)
const canUseJenkins = computed(() =>
  hasFeature(currentUser.value, 'workspace_jenkins')
)
const canUseActions = computed(() =>
  hasFeature(currentUser.value, 'workspace_actions')
)

const MOBILE_BREAKPOINT = 1024

const isMobile = computed(() => {
  return typeof window !== 'undefined' && window.innerWidth < MOBILE_BREAKPOINT
})

function isActive(path) {
  if (path === '/dashboard') {
    return route.path === '/dashboard' || route.path === '/'
  }
  if (path === '/management/') {
    return route.path.startsWith('/management')
  }
  return route.path === path || route.path.startsWith(path + '/')
}

function toggleJenkinsMenu() {
  jenkinsMenuOpen.value = !jenkinsMenuOpen.value
}

function toggleActionsMenu() {
  actionsMenuOpen.value = !actionsMenuOpen.value
}

watch(
  () => route.path,
  (newPath) => {
    if (newPath.startsWith('/jenkins')) jenkinsMenuOpen.value = true
    if (newPath.startsWith('/actions')) actionsMenuOpen.value = true
  },
  { immediate: true }
)
</script>
