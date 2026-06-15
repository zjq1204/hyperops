<template>
  <AppLayout>
    <PageFrame
      variant="soft"
    >
      <template #hero>
        <div class="settings-profile-hero-v3">
          <div>
            <h1 class="page-title-soft">{{ t('settings.profile.title') }}</h1>
            <p class="page-subtitle-soft">
              {{ t('settings.profile.subtitle') }}
            </p>
          </div>

          <div class="settings-profile-top-status">
            <span>{{ t('settings.profile.uidLabel') }}: {{ userId }}</span>
            <span class="settings-profile-top-status__divider"></span>
            <span class="settings-profile-top-status__online">
              {{ t('settings.profile.onlineLabel') }}
            </span>
          </div>
        </div>
      </template>

      <BaseLoading v-if="loading" full-page size="lg" variant="primary" />

      <template v-else>
        <section class="surface-panel-strong settings-profile-layout-v3">
          <aside class="settings-profile-layout-v3__sidebar">
            <section class="settings-profile-summary-card">
              <div class="settings-profile-summary-card__accent"></div>
              <div :class="avatarBgColor" class="settings-profile-summary-card__avatar">
                <span class="text-3xl font-semibold tracking-tight text-white">
                  {{ userInitials }}
                </span>
              </div>

              <div class="settings-profile-summary-card__content">
                <h2 class="settings-profile-summary-card__name">
                  {{ displayName }}
                </h2>
                <p class="settings-profile-summary-card__username">
                  @{{ username }}
                </p>

                <div class="settings-profile-summary-card__chips">
                  <span
                    v-if="isStaff"
                    class="settings-profile-summary-card__chip settings-profile-summary-card__chip--primary"
                  >
                    {{ t('settings.profile.adminRoleLabel') }}
                  </span>
                  <span class="settings-profile-summary-card__chip">
                    {{ primaryContextLabel }}
                  </span>
                </div>
              </div>
            </section>

            <nav class="settings-profile-navcard" :aria-label="t('common.settings')">
              <button
                type="button"
                class="settings-profile-navcard__item"
                :class="
                  activeSection === 'basic'
                    ? 'settings-profile-navcard__item--active'
                    : ''
                "
                @click="activeSection = 'basic'"
              >
                <span class="settings-profile-navcard__icon">
                  <svg
                    class="h-5 w-5"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      stroke-linecap="round"
                      stroke-linejoin="round"
                      stroke-width="1.8"
                      d="M5.121 17.804A11.955 11.955 0 0112 15.75c2.54 0 4.896.79 6.879 2.054M15 10.5a3 3 0 11-6 0 3 3 0 016 0z"
                    />
                  </svg>
                </span>
                <span class="settings-profile-navcard__label">
                  {{ t('settings.profile.basicTabLabel') }}
                </span>
              </button>

              <button
                type="button"
                class="settings-profile-navcard__item"
                :class="
                  activeSection === 'notifications'
                    ? 'settings-profile-navcard__item--active'
                    : ''
                "
                @click="activeSection = 'notifications'"
              >
                <span class="settings-profile-navcard__icon">
                  <svg
                    class="h-5 w-5"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      stroke-linecap="round"
                      stroke-linejoin="round"
                      stroke-width="1.8"
                      d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V4a2 2 0 10-4 0v1.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0a3 3 0 11-6 0m6 0H9"
                    />
                  </svg>
                </span>
                <span class="settings-profile-navcard__label">
                  {{ t('settings.profile.notificationsTabLabel') }}
                </span>
                <span class="settings-profile-navcard__badge">
                  {{ totalTargets }}
                </span>
              </button>
            </nav>
          </aside>

          <section class="settings-profile-layout-v3__main">
            <template v-if="activeSection === 'basic'">
              <section class="settings-profile-panel-card">
                <div class="settings-profile-panel-card__header">
                  <div class="settings-profile-panel-card__title">
                    <span class="settings-profile-panel-card__title-icon">
                      <svg
                        class="h-5 w-5"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path
                          stroke-linecap="round"
                          stroke-linejoin="round"
                          stroke-width="1.8"
                          d="M5.121 17.804A11.955 11.955 0 0112 15.75c2.54 0 4.896.79 6.879 2.054M15 10.5a3 3 0 11-6 0 3 3 0 016 0z"
                        />
                      </svg>
                    </span>
                    <div>
                      <h3>{{ t('settings.profile.basicPanelTitle') }}</h3>
                      <p>{{ t('settings.profile.basicPanelDesc') }}</p>
                    </div>
                  </div>
                </div>

                <BasicInfoCard embedded flat />
              </section>
            </template>

            <template v-else>
              <section class="settings-profile-panel-card">
                <div class="settings-profile-panel-card__header">
                  <div class="settings-profile-panel-card__title">
                    <span class="settings-profile-panel-card__title-icon">
                      <svg
                        class="h-5 w-5"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path
                          stroke-linecap="round"
                          stroke-linejoin="round"
                          stroke-width="1.8"
                          d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8m-2 9H5a2 2 0 01-2-2V7a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2z"
                        />
                      </svg>
                    </span>
                    <div>
                      <h3>{{ t('settings.profile.emailPanelTitle') }}</h3>
                      <p>{{ t('settings.profile.emailPanelDesc') }}</p>
                    </div>
                  </div>
                </div>

                <div class="settings-profile-target-list">
                  <article class="settings-profile-target-row settings-profile-target-row--primary">
                    <div class="settings-profile-target-row__main">
                      <strong>{{ securityEmail }}</strong>
                      <span class="settings-profile-target-row__tag">
                        {{ t('settings.profile.defaultBadge') }}
                      </span>
                    </div>
                    <span class="settings-profile-target-row__hint">
                      {{ t('settings.profile.defaultEmailInlineHint') }}
                    </span>
                  </article>

                  <div
                    v-for="(email, index) in notificationEmails"
                    :key="`email-${index}`"
                    class="settings-profile-inline-editor"
                  >
                    <input
                      v-model="notificationEmails[index]"
                      type="email"
                      class="settings-profile-inline-editor__input"
                      :placeholder="t('settings.profile.emailPlaceholder')"
                    />
                    <button
                      type="button"
                      class="settings-profile-inline-editor__remove"
                      :aria-label="t('settings.profile.removeTarget')"
                      @click="removeEmailField(index)"
                    >
                      <svg
                        class="h-4 w-4"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path
                          stroke-linecap="round"
                          stroke-linejoin="round"
                          stroke-width="1.8"
                          d="M6 18L18 6M6 6l12 12"
                        />
                      </svg>
                    </button>
                  </div>

                  <div class="settings-profile-quick-add">
                    <input
                      v-model="draftEmail"
                      type="email"
                      class="settings-profile-quick-add__input"
                      :placeholder="t('settings.profile.quickEmailPlaceholder')"
                      @keydown.enter.prevent="addEmailTarget"
                    />
                    <BaseButton
                      variant="secondary"
                      :disabled="!draftEmail.trim()"
                      @click="addEmailTarget"
                    >
                      {{ t('settings.profile.quickAddEmail') }}
                    </BaseButton>
                  </div>

                  <div
                    v-if="!notificationEmails.length"
                    class="settings-profile-empty-line"
                  >
                    {{ t('settings.profile.noExtraEmails') }}
                  </div>
                </div>
              </section>

              <section class="settings-profile-panel-card">
                <div class="settings-profile-panel-card__header">
                  <div class="settings-profile-panel-card__title">
                    <span class="settings-profile-panel-card__title-icon">
                      <svg
                        class="h-5 w-5"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path
                          stroke-linecap="round"
                          stroke-linejoin="round"
                          stroke-width="1.8"
                          d="M13.828 10.172a4 4 0 010 5.656l-3 3a4 4 0 11-5.656-5.656l1.5-1.5m7.156-1.5l1.5-1.5a4 4 0 015.656 5.656l-3 3a4 4 0 01-5.656 0"
                        />
                      </svg>
                    </span>
                    <div>
                      <h3>{{ t('settings.profile.webhookPanelTitle') }}</h3>
                      <p>{{ t('settings.profile.webhookPanelDesc') }}</p>
                    </div>
                  </div>
                </div>

                <div class="settings-profile-target-list">
                  <article
                    v-for="(webhook, index) in notificationWebhooks"
                    :key="`webhook-${index}`"
                    class="settings-profile-webhook-row"
                  >
                    <div class="min-w-0 flex-1">
                      <div class="settings-profile-webhook-row__head">
                        <strong>{{ webhook.name }}</strong>
                        <span class="settings-profile-webhook-row__status">
                          {{ t('settings.profile.webhookActiveLabel') }}
                        </span>
                      </div>
                      <p class="settings-profile-webhook-row__url">
                        {{ webhook.url }}
                      </p>
                    </div>
                    <button
                      type="button"
                      class="settings-profile-inline-editor__remove"
                      :aria-label="t('settings.profile.removeTarget')"
                      @click="removeWebhookField(index)"
                    >
                      <svg
                        class="h-4 w-4"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path
                          stroke-linecap="round"
                          stroke-linejoin="round"
                          stroke-width="1.8"
                          d="M6 18L18 6M6 6l12 12"
                        />
                      </svg>
                    </button>
                  </article>

                  <div class="settings-profile-webhook-create">
                    <input
                      v-model="draftWebhookName"
                      type="text"
                      class="settings-profile-quick-add__input"
                      :placeholder="t('settings.profile.webhookNamePlaceholder')"
                      @keydown.enter.prevent="addWebhookTarget"
                    />
                    <input
                      v-model="draftWebhookUrl"
                      type="url"
                      class="settings-profile-quick-add__input"
                      :placeholder="t('settings.profile.webhookPlaceholder')"
                      @keydown.enter.prevent="addWebhookTarget"
                    />
                    <BaseButton
                      variant="secondary"
                      :disabled="!draftWebhookUrl.trim()"
                      @click="addWebhookTarget"
                    >
                      {{ t('settings.profile.quickAddWebhook') }}
                    </BaseButton>
                  </div>

                  <div
                    v-if="!notificationWebhooks.length"
                    class="settings-profile-empty-line"
                  >
                    {{ t('settings.profile.noWebhooks') }}
                  </div>
                </div>
              </section>

              <div class="settings-profile-layout-v3__footer">
                <BaseButton
                  :loading="savingNotifications"
                  @click="saveNotificationTargets"
                >
                  {{ t('settings.profile.saveAllChanges') }}
                </BaseButton>
              </div>
            </template>
          </section>
        </section>
      </template>
    </PageFrame>
  </AppLayout>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useUserStore } from '@/store/user'
import AppLayout from '@/components/layout/AppLayout.vue'
import BasicInfoCard from '@/components/settings/BasicInfoCard.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseLoading from '@/components/ui/BaseLoading.vue'
import PageFrame from '@/components/ui/PageFrame.vue'

const WEBHOOK_LABEL_STORAGE_KEY = 'hyperops_settings_profile_webhook_labels'

const { t } = useI18n()
const userStore = useUserStore()
const loading = ref(true)
const activeSection = ref('basic')
const savingNotifications = ref(false)
const notificationEmails = ref([])
const notificationWebhooks = ref([])
const draftEmail = ref('')
const draftWebhookName = ref('')
const draftWebhookUrl = ref('')

const notificationSettings = computed(
  () =>
    userStore.userInfo?.profile?.jenkins_notification_settings || {
      notification_emails: [],
      notification_webhooks: []
    }
)

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
const userId = computed(() => userStore.userInfo?.id || '—')
const isStaff = computed(() => Boolean(userStore.userInfo?.is_staff))
const securityEmail = computed(() => userStore.userInfo?.email || '—')
const groupNames = computed(() =>
  (userStore.userInfo?.groups || []).map((group) => group.name).filter(Boolean)
)
const primaryContextLabel = computed(() => {
  if (groupNames.value.length) {
    return groupNames.value[0]
  }

  return t('settings.profile.noGroup')
})
const userInitials = computed(() => {
  const firstChar = displayName.value.trim().charAt(0).toUpperCase()
  return firstChar || 'U'
})
const totalTargets = computed(
  () =>
    normalizeEmails(notificationEmails.value).length +
    normalizeWebhookItems(notificationWebhooks.value).length
)

const avatarBgColor = computed(() => {
  const initial = userInitials.value
  const colors = [
    'from-blue-500 to-indigo-500',
    'from-sky-500 to-cyan-500',
    'from-violet-500 to-blue-500',
    'from-indigo-500 to-sky-500'
  ]
  const colorIndex = initial.charCodeAt(0) % colors.length

  return `bg-gradient-to-br ${colors[colorIndex]}`
})

const getStoredWebhookLabels = () => {
  try {
    return JSON.parse(localStorage.getItem(WEBHOOK_LABEL_STORAGE_KEY) || '{}')
  } catch (error) {
    console.error('Failed to read stored webhook labels:', error)
    return {}
  }
}

const persistWebhookLabels = (items) => {
  try {
    const labelMap = Object.fromEntries(
      items
        .map((item) => [item.url.trim(), item.name.trim()])
        .filter(([url, name]) => url && name)
    )

    localStorage.setItem(
      WEBHOOK_LABEL_STORAGE_KEY,
      JSON.stringify(labelMap)
    )
  } catch (error) {
    console.error('Failed to persist webhook labels:', error)
  }
}

const inferWebhookName = (url) => {
  try {
    const parsed = new URL(url)
    const host = parsed.hostname.replace(/^hooks?\./, '')
    const lastPath = parsed.pathname.split('/').filter(Boolean).at(-1)

    return lastPath ? `${host} / ${lastPath}` : host
  } catch (error) {
    return t('settings.profile.webhookFallbackName')
  }
}

const createWebhookItem = (url, name = '', labels = {}) => {
  const normalizedUrl = url.trim()
  const storedLabel = labels[normalizedUrl] || ''

  return {
    name: (name || storedLabel || inferWebhookName(normalizedUrl)).trim(),
    url: normalizedUrl
  }
}

const normalizeEmails = (items) => {
  const seen = new Set()

  return items
    .map((item) => item.trim())
    .filter((item) => {
      if (!item || seen.has(item)) {
        return false
      }

      seen.add(item)
      return true
    })
}

const normalizeWebhookItems = (items) => {
  const seen = new Set()

  return items
    .map((item) => ({
      name: item.name.trim(),
      url: item.url.trim()
    }))
    .filter((item) => {
      if (!item.url || seen.has(item.url)) {
        return false
      }

      seen.add(item.url)
      return true
    })
}

const loadUserData = async () => {
  loading.value = true
  try {
    if (!userStore.user) {
      await userStore.checkAuthStatus()
    }
  } catch (error) {
    console.error('Failed to load user data:', error)
  } finally {
    loading.value = false
  }
}

const syncNotificationFields = (value) => {
  const storedLabels = getStoredWebhookLabels()

  notificationEmails.value = [...(value.notification_emails || [])]
  notificationWebhooks.value = (value.notification_webhooks || []).map((url) =>
    createWebhookItem(url, '', storedLabels)
  )
}

const addEmailTarget = () => {
  const nextEmail = draftEmail.value.trim()
  if (!nextEmail) return

  notificationEmails.value.push(nextEmail)
  draftEmail.value = ''
}

const removeEmailField = (index) => {
  notificationEmails.value.splice(index, 1)
}

const addWebhookTarget = () => {
  const nextUrl = draftWebhookUrl.value.trim()
  if (!nextUrl) return

  notificationWebhooks.value.push(
    createWebhookItem(nextUrl, draftWebhookName.value)
  )
  draftWebhookName.value = ''
  draftWebhookUrl.value = ''
}

const removeWebhookField = (index) => {
  notificationWebhooks.value.splice(index, 1)
}

const saveNotificationTargets = async () => {
  savingNotifications.value = true
  try {
    const normalizedEmails = normalizeEmails(notificationEmails.value)
    const normalizedWebhooks = normalizeWebhookItems(notificationWebhooks.value)
    const normalizedWebhookUrls = normalizedWebhooks.map((item) => item.url)

    persistWebhookLabels(normalizedWebhooks)

    await userStore.updateProfile({
      jenkins_notification_emails: normalizedEmails,
      jenkins_notification_webhooks: normalizedWebhookUrls
    })

    notificationEmails.value = [...normalizedEmails]
    notificationWebhooks.value = normalizedWebhookUrls.map((url) =>
      createWebhookItem(url, '', getStoredWebhookLabels())
    )
  } catch (error) {
    console.error('Failed to save Jenkins notification targets:', error)
  } finally {
    savingNotifications.value = false
  }
}

onMounted(async () => {
  await loadUserData()
})

watch(notificationSettings, syncNotificationFields, { immediate: true })
</script>
