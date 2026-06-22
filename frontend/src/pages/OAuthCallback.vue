<template>
  <div class="min-h-screen flex items-center justify-center px-4 py-12">
    <div class="surface-panel-strong w-full max-w-md rounded-lg p-10 text-center">
      <div class="mx-auto flex h-16 w-16 items-center justify-center rounded-lg bg-slate-900 text-white shadow-[0_14px_30px_rgba(15,23,42,0.16)]">
        <svg class="h-7 w-7" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
        </svg>
      </div>
      <h1 class="mt-6 text-2xl font-semibold text-slate-950" style="font-family: 'Space Grotesk', sans-serif;">{{ t('oauthCallback.title') }}</h1>
      <p class="mt-3 text-sm leading-6 text-slate-500">
        {{ t('oauthCallback.subtitle') }}
      </p>
      <div v-if="loading" class="mt-6 text-slate-600">{{ t('oauthCallback.processing') }}</div>
      <div v-if="error" class="mt-6 rounded-lg border border-rose-200 bg-rose-50/90 p-4 text-rose-700">{{ error }}</div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useUserStore } from '@/store/user'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()
const { t } = useI18n()
const loading = ref(true)
const error = ref('')

const sanitizeRedirect = (value) => {
  if (typeof value !== 'string' || !value) return ''
  if (!value.startsWith('/') || value.startsWith('//')) return ''
  return value
}

onMounted(async () => {
  const queryToken = typeof route.query.access_token === 'string'
    ? route.query.access_token
    : ''
  const queryRefresh = typeof route.query.refresh_token === 'string'
    ? route.query.refresh_token
    : ''

  if (queryToken) {
    userStore.setToken(queryToken, queryRefresh || null)
  }

  const safeRedirect = sanitizeRedirect(route.query.redirect)
  const fallback = safeRedirect || userStore.getUserLandingPath() || '/dashboard'

  try {
    const ok = await userStore.checkAuth()
    if (!ok) {
      router.replace('/login?oauth_error=check_auth_failed')
      return
    }
    router.replace(fallback)
  } catch (e) {
    error.value = t('oauthCallback.errorPrefix') + (e?.message || t('oauthCallback.unknownError'))
    loading.value = false
    setTimeout(() => {
      router.replace('/login?oauth_error=callback_failed')
    }, 2000)
  }
})
</script>
