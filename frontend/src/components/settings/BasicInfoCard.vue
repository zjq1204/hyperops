<template>
  <div
    :class="
      embedded
        ? 'settings-basic-card settings-basic-card--embedded'
        : 'settings-basic-card'
    "
  >
    <div
      v-if="!embedded"
      class="section-heading settings-section-heading-compact"
    >
      <div>
        <h3 class="section-title">
          {{ t('settings.profile.accountSecurityTitle') }}
        </h3>
        <p class="section-copy">
          {{ t('settings.profile.accountSecurityDesc') }}
        </p>
      </div>
    </div>

    <section
      :class="
        flat
          ? 'settings-basic-card__body settings-basic-card__body--flat'
          : 'settings-basic-card__body'
      "
    >
      <div class="settings-basic-grid">
        <article class="settings-basic-field">
          <span class="settings-basic-field__label">
            {{ t('settings.profile.displayNameLabel') }}
          </span>
          <strong class="settings-basic-field__value">{{ displayName }}</strong>
        </article>

        <article class="settings-basic-field">
          <span class="settings-basic-field__label">
            {{ t('settings.securityEmail') }}
          </span>
          <strong class="settings-basic-field__value break-all">
            {{ userStore.userInfo?.email || '—' }}
          </strong>
          <span class="settings-basic-field__hint">
            {{ t('settings.securityEmailDesc') }}
          </span>
        </article>

        <article class="settings-basic-field">
          <span class="settings-basic-field__label">
            {{ t('settings.profile.usernameLabel') }}
          </span>
          <strong class="settings-basic-field__value">
            @{{ userStore.userInfo?.username || '—' }}
          </strong>
        </article>

        <article class="settings-basic-field">
          <span class="settings-basic-field__label">
            {{ t('settings.profile.groupLabel') }}
          </span>
          <strong class="settings-basic-field__value">{{ groupSummary }}</strong>
        </article>

        <article
          v-if="userStore.userInfo?.virtual_email"
          class="settings-basic-field settings-basic-field--wide"
        >
          <span class="settings-basic-field__label">{{ t('settings.aiEmail') }}</span>
          <strong class="settings-basic-field__value break-all">
            {{ userStore.userInfo.virtual_email }}
          </strong>
        </article>
      </div>

      <div class="settings-basic-auth">
        <div class="settings-basic-auth__main">
          <p class="settings-basic-auth__label">
            {{ t('settings.profile.passwordBlockTitle') }}
          </p>
          <div class="settings-basic-auth__value">
            <span>{{ authMethodLabel }}</span>
            <span
              v-if="authInfo?.method === 'oauth'"
              class="settings-basic-auth__subtle break-all"
            >
              {{ authInfo.login_identifier || authInfo.provider_email || '—' }}
            </span>
            <span v-else class="settings-basic-auth__subtle">
              {{
                authInfo?.can_change_password
                  ? t('settings.profile.passwordBlockDesc')
                  : t('settings.oauthPasswordChangeInfo')
              }}
            </span>
          </div>
        </div>

        <BaseButton
          v-if="authInfo?.can_change_password"
          variant="outline"
          size="sm"
          @click="showPasswordResetConfirm = true"
        >
          {{ t('settings.resetPassword') }}
        </BaseButton>
      </div>
    </section>

    <div v-if="resetEmailSent || resetEmailError" class="mt-5">
      <div
        v-if="resetEmailSent"
        class="rounded-[1.25rem] border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800"
      >
        <p class="font-medium">{{ t('settings.passwordResetEmailSent') }}</p>
        <p class="mt-1 text-emerald-700">
          {{ t('settings.passwordResetEmailSentDesc') }}
        </p>
      </div>

      <div
        v-if="resetEmailError"
        class="rounded-[1.25rem] border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800"
      >
        {{ resetEmailError }}
      </div>
    </div>

    <div
      v-if="showPasswordResetConfirm"
      class="fixed inset-0 z-50 overflow-y-auto bg-slate-950/40 px-4 py-12 backdrop-blur-sm"
      @click.self="showPasswordResetConfirm = false"
    >
      <div
        class="surface-panel-strong relative mx-auto w-full max-w-md rounded-[1.8rem] p-6 shadow-[0_28px_60px_rgba(15,23,42,0.24)]"
      >
        <div class="flex items-start justify-between gap-4">
          <div>
            <h3 class="text-lg font-semibold text-slate-900">
              {{ t('settings.confirmPasswordReset') }}
            </h3>
            <p class="mt-2 text-sm leading-6 text-slate-500">
              {{ t('settings.passwordResetConfirmDesc') }}
            </p>
          </div>
          <button
            type="button"
            class="inline-flex h-10 w-10 items-center justify-center rounded-2xl border border-slate-200 bg-slate-50 text-slate-500 transition hover:border-slate-300 hover:bg-slate-100"
            @click="showPasswordResetConfirm = false"
          >
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
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
          </button>
        </div>

        <div
          class="mt-5 rounded-[1.4rem] border border-slate-200/90 bg-slate-50/80 p-4"
        >
          <p
            class="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400"
          >
            {{ t('settings.securityEmail') }}
          </p>
          <p class="mt-2 break-all text-sm font-semibold text-slate-900">
            {{ userStore.userInfo?.email || '' }}
          </p>
        </div>

        <div class="mt-6 flex justify-end gap-3">
          <BaseButton
            variant="secondary"
            @click="showPasswordResetConfirm = false"
          >
            {{ t('common.cancel') }}
          </BaseButton>
          <BaseButton
            variant="primary"
            :loading="sendingResetEmail"
            :disabled="sendingResetEmail"
            @click="confirmPasswordReset"
          >
            {{ t('settings.sendPasswordReset') }}
          </BaseButton>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { authApi } from '@/api/auth'
import { useUserStore } from '@/store/user'
import BaseButton from '@/components/ui/BaseButton.vue'

defineProps({
  embedded: {
    type: Boolean,
    default: false
  },
  flat: {
    type: Boolean,
    default: false
  }
})

const { t } = useI18n()
const userStore = useUserStore()

const authInfo = computed(() => userStore.userInfo?.auth_info || null)
const sendingResetEmail = ref(false)
const resetEmailSent = ref(false)
const resetEmailError = ref('')
const showPasswordResetConfirm = ref(false)

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

const groupSummary = computed(() => {
  const groups = (userStore.userInfo?.groups || [])
    .map((group) => group.name)
    .filter(Boolean)

  return groups.length ? groups.join(' / ') : t('settings.profile.noGroup')
})

const authMethodLabel = computed(() => {
  const method = authInfo.value?.method
  return method === 'oauth' ? t('settings.oauthAuth') : t('settings.emailAuth')
})

const confirmPasswordReset = async () => {
  sendingResetEmail.value = true
  resetEmailError.value = ''
  resetEmailSent.value = false

  try {
    await authApi.resetPassword(userStore.userInfo?.email)
    resetEmailSent.value = true
    showPasswordResetConfirm.value = false

    setTimeout(() => {
      resetEmailSent.value = false
    }, 5000)
  } catch (error) {
    console.error('Password reset email failed:', error)

    const responseData = error.response?.data
    const nestedError = responseData?.data?.error

    if (nestedError) {
      resetEmailError.value = nestedError
    } else if (responseData?.error) {
      resetEmailError.value = responseData.error
    } else if (responseData?.errors) {
      resetEmailError.value = Object.values(responseData.errors)
        .flat()
        .join(', ')
    } else if (responseData?.detail) {
      resetEmailError.value = responseData.detail
    } else if (responseData?.message) {
      resetEmailError.value = responseData.message
    } else {
      resetEmailError.value = t('settings.passwordResetError')
    }
  } finally {
    sendingResetEmail.value = false
  }
}
</script>
