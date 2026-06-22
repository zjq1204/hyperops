<template>
  <header class="layout-admin-header flex-shrink-0 z-30">
    <div class="px-4 sm:px-6 lg:px-7">
      <div class="flex h-16 items-center justify-between">
        <div class="flex items-center gap-3">
          <button
            @click="$emit('toggle-menu')"
            class="rounded-xl p-2 text-slate-400 hover:bg-slate-100/80 hover:text-slate-700 focus:outline-none focus:ring-2 focus:ring-sky-300 lg:hidden"
          >
            <svg
              class="w-6 h-6"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M4 6h16M4 12h16M4 18h16"
              />
            </svg>
          </button>
          <h1 class="text-lg font-semibold text-slate-900 lg:hidden">
            {{ pageTitle }}
          </h1>
        </div>

        <div class="flex items-center space-x-4">
          <LanguageSwitcher />
          <PlatformSwitcher />
          <div class="relative" ref="userMenuRef">
            <button
              @click="toggleUserMenu"
              class="flex items-center space-x-2 rounded-xl px-2 py-1.5 text-sm text-slate-600 hover:bg-slate-100/70 hover:text-slate-900 focus:outline-none focus:ring-2 focus:ring-sky-300"
            >
              <div
                :class="avatarBgColor"
                class="flex h-8 w-8 items-center justify-center rounded-full shadow-sm"
              >
                <span class="text-white font-medium text-sm">{{
                  userInitials
                }}</span>
              </div>
              <span class="hidden sm:block">{{ displayName }}</span>
              <svg
                class="w-4 h-4 transition-transform"
                :class="{ 'rotate-180': showUserMenu }"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="2"
                  d="M19 9l-7 7-7-7"
                />
              </svg>
            </button>

            <Transition
              enter-active-class="transition ease-out duration-100"
              enter-from-class="transform opacity-0 scale-95"
              enter-to-class="transform opacity-100 scale-100"
              leave-active-class="transition ease-in duration-75"
              leave-from-class="transform opacity-100 scale-100"
              leave-to-class="transform opacity-0 scale-95"
            >
              <div
                v-if="showUserMenu"
                class="absolute right-0 z-50 mt-3 w-80 rounded-lg border border-slate-200/80 bg-white/95 py-2 shadow-[0_12px_32px_rgba(15,23,42,0.12)] backdrop-blur-xl"
              >
                <div class="border-b border-slate-200/70 px-4 py-2">
                  <div class="truncate font-semibold text-slate-900">
                    {{ displayName }}
                  </div>
                </div>
                <div class="px-4 py-2">
                  <router-link
                    to="/settings"
                    class="flex items-center gap-2 rounded-md px-2 py-1.5 text-sm text-slate-700 transition-colors hover:bg-slate-50 hover:text-slate-900"
                    @click="showUserMenu = false"
                  >
                    <svg
                      class="h-4 w-4 text-slate-400"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        stroke-linecap="round"
                        stroke-linejoin="round"
                        stroke-width="2"
                        d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"
                      />
                      <path
                        stroke-linecap="round"
                        stroke-linejoin="round"
                        stroke-width="2"
                        d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
                      />
                    </svg>
                    <span>{{ t('common.settings') }}</span>
                  </router-link>
                </div>
                <div class="my-1 border-t border-slate-200/70"></div>
                <button
                  @click="handleLogout"
                  class="block w-full px-4 py-2 text-left text-sm text-slate-700 hover:bg-slate-50"
                >
                  {{ t('common.logout') }}
                </button>
              </div>
            </Transition>
          </div>
        </div>
      </div>
    </div>
  </header>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useUserStore } from '@/store/user'
import LanguageSwitcher from '@/components/ui/LanguageSwitcher.vue'
import PlatformSwitcher from '@/components/layout/PlatformSwitcher.vue'

defineEmits(['toggle-menu'])

const { t, te } = useI18n()
const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const showUserMenu = ref(false)
const userMenuRef = ref(null)

const pageTitle = computed(() => {
  const routeName = typeof route.name === 'string' ? route.name : ''
  return routeName && te(`routeTitles.${routeName}`)
    ? t(`routeTitles.${routeName}`)
    : t('management.logoTitle')
})

const displayName = computed(() => {
  const userInfo = userStore.userInfo
  if (!userInfo) return t('common.profile')
  if (userInfo.display_name) return userInfo.display_name
  if (userInfo.first_name && userInfo.last_name)
    return `${userInfo.first_name} ${userInfo.last_name}`
  if (userInfo.first_name) return userInfo.first_name
  return userInfo.username || t('common.profile')
})

const userInitials = computed(() => {
  const name = displayName.value
  return name.trim().charAt(0).toUpperCase() || 'U'
})

const avatarBgColor = computed(() => {
  const colors = [
    'bg-indigo-500',
    'bg-slate-500',
    'bg-violet-500',
    'bg-purple-500'
  ]
  const charCode = userInitials.value.charCodeAt(0)
  return colors[charCode % colors.length]
})

const toggleUserMenu = () => {
  showUserMenu.value = !showUserMenu.value
}

const handleLogout = async () => {
  try {
    await userStore.logout()
  } catch (error) {
    console.error('Logout failed:', error)
  } finally {
    showUserMenu.value = false
    router.push('/login')
  }
}

const handleClickOutside = (event) => {
  if (userMenuRef.value && !userMenuRef.value.contains(event.target)) {
    showUserMenu.value = false
  }
}

onMounted(() => {
  document.addEventListener('click', handleClickOutside)
})

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside)
})
</script>
