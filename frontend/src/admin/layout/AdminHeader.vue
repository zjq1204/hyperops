<template>
  <header
    class="layout-admin-header bg-white/72 backdrop-blur-2xl border-b border-slate-200/70 flex-shrink-0 z-30"
  >
    <div class="px-4 sm:px-6 lg:px-8">
      <div class="flex justify-between items-center h-20">
        <div class="flex items-center gap-3">
          <button
            @click="$emit('toggle-menu')"
            class="lg:hidden p-2 rounded-md text-slate-400 hover:text-slate-700 hover:bg-slate-100 focus:outline-none focus:ring-2 focus:ring-sky-400"
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
              class="flex items-center space-x-2 text-sm text-slate-600 hover:text-slate-900 focus:outline-none focus:ring-2 focus:ring-sky-400 rounded-lg px-2 py-1"
            >
              <div
                :class="avatarBgColor"
                class="w-8 h-8 rounded-full flex items-center justify-center"
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
                class="absolute right-0 mt-3 w-80 rounded-2xl border border-white/50 bg-white/92 py-2 shadow-[0_20px_60px_rgba(15,23,42,0.18)] backdrop-blur-xl z-50"
              >
                <div class="px-4 py-2 border-b border-gray-100">
                  <div class="font-semibold text-gray-900 truncate">
                    {{ displayName }}
                  </div>
                </div>
                <div class="px-4 py-2">
                  <router-link
                    to="/settings"
                    class="flex items-center gap-2 text-sm text-gray-700 hover:text-gray-900 hover:bg-gray-50 rounded-md px-2 py-1.5 transition-colors"
                    @click="showUserMenu = false"
                  >
                    <svg
                      class="w-4 h-4 text-gray-400"
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
                <div class="border-t border-gray-100 my-1"></div>
                <button
                  @click="handleLogout"
                  class="block w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-100"
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
  return routeName && te(`routeTitles.${routeName}`) ? t(`routeTitles.${routeName}`) : t('management.logoTitle')
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
