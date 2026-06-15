<template>
  <div class="settings-identity-banner">
    <div class="settings-identity-main">
      <div :class="avatarBgColor" class="settings-profile-avatar">
        <span class="text-xl font-semibold tracking-tight text-white">
          {{ userInitials }}
        </span>
      </div>

      <div class="min-w-0 flex-1">
        <p class="settings-identity-kicker">
          {{ t('settings.profile.eyebrow') }}
        </p>
        <h2 class="settings-identity-name">
          {{ displayName }}
        </h2>
        <div class="settings-identity-tags">
          <span class="settings-chip settings-chip--soft">@{{ username }}</span>
          <span
            v-for="groupName in groupNames"
            :key="groupName"
            class="settings-chip settings-chip--group"
          >
            {{ groupName }}
          </span>
          <span
            v-if="!groupNames.length"
            class="settings-chip settings-chip--soft"
          >
            {{ t('settings.profile.noGroup') }}
          </span>
          <span v-if="isStaff" class="settings-chip settings-chip--admin">
            {{ t('settings.profile.adminBadge') }}
          </span>
        </div>
      </div>

      <div class="settings-identity-counter">
        <strong class="settings-identity-counter__value">{{ targetCount }}</strong>
        <span class="settings-identity-counter__label">
          {{ t('settings.profile.targetOverview') }}
        </span>
      </div>
    </div>

    <div class="settings-identity-meta">
      <article class="settings-identity-meta-item">
        <span class="settings-identity-meta-label">
          {{ t('settings.profile.authSummary') }}
        </span>
        <strong class="settings-identity-meta-value">
          {{ authMethodLabel }}
        </strong>
      </article>

      <article class="settings-identity-meta-item">
        <span class="settings-identity-meta-label">
          {{ t('settings.profile.localeLabel') }}
        </span>
        <strong class="settings-identity-meta-value">{{ language }}</strong>
        <span class="settings-identity-meta-subtle">{{ timezone }}</span>
      </article>

      <article class="settings-identity-meta-item">
        <span class="settings-identity-meta-label">
          {{ t('settings.profile.securitySummary') }}
        </span>
        <strong class="settings-identity-meta-value break-all">
          {{ userStore.userInfo?.email || '—' }}
        </strong>
      </article>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useUserStore } from '@/store/user'

const { t } = useI18n()
const userStore = useUserStore()

const displayName = computed(() => {
  const userInfo = userStore.userInfo
  if (!userInfo) return t('common.profile')

  if (userInfo.display_name) {
    return userInfo.display_name
  }

  if (userInfo.first_name && userInfo.last_name) {
    return `${userInfo.first_name} ${userInfo.last_name}`
  }

  if (userInfo.first_name) {
    return userInfo.first_name
  }

  return userInfo.username || t('common.profile')
})

const username = computed(() => userStore.userInfo?.username || 'user')
const language = computed(
  () => userStore.userInfo?.profile?.language || 'zh-CN'
)
const timezone = computed(
  () => userStore.userInfo?.profile?.timezone || 'Asia/Shanghai'
)
const isStaff = computed(() => Boolean(userStore.userInfo?.is_staff))

const authMethodLabel = computed(() => {
  const method = userStore.userInfo?.auth_info?.method
  return method === 'oauth' ? t('settings.oauthAuth') : t('settings.emailAuth')
})

const groupNames = computed(() =>
  (userStore.userInfo?.groups || []).map((group) => group.name).filter(Boolean)
)

const targetCount = computed(() => {
  const settings =
    userStore.userInfo?.profile?.jenkins_notification_settings || {}
  const emailCount = (settings.notification_emails || []).length
  const webhookCount = (settings.notification_webhooks || []).length
  return `${emailCount + webhookCount}`
})

const userInitials = computed(() => {
  const firstChar = displayName.value.trim().charAt(0).toUpperCase()
  return firstChar || 'U'
})

const avatarBgColor = computed(() => {
  const initial = userInitials.value
  const colors = [
    'from-sky-500 to-cyan-400',
    'from-emerald-500 to-teal-400',
    'from-blue-600 to-indigo-500',
    'from-orange-500 to-amber-400',
    'from-fuchsia-500 to-pink-500'
  ]
  const colorIndex = initial.charCodeAt(0) % colors.length

  return `bg-gradient-to-br ${colors[colorIndex]}`
})
</script>
