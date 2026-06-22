<template>
  <div
    class="relative min-h-screen overflow-hidden bg-[#f6f8fb] px-4 py-12"
  >
    <div class="pointer-events-none absolute inset-0">
      <div class="absolute left-[10%] top-[10%] h-52 w-52 rounded-full bg-sky-200/35 blur-3xl"></div>
      <div class="absolute right-[12%] bottom-[12%] h-64 w-64 rounded-full bg-orange-200/30 blur-3xl"></div>
    </div>
    <div
      class="surface-panel-strong relative mx-auto w-full max-w-lg rounded-lg p-8 sm:p-10"
    >
      <div class="mb-8 text-center">
        <span class="page-eyebrow bg-slate-900/85 text-slate-100">Account recovery</span>
        <h1 class="mt-5 text-3xl font-semibold text-slate-950" style="font-family: 'Space Grotesk', sans-serif;">
          {{ t('password.reset.title') }}
        </h1>
        <p class="mt-3 text-sm leading-6 text-slate-500">
          {{ t('password.reset.subtitle') }}
        </p>
      </div>

      <div
        v-if="successMessage"
        class="mb-5 rounded-lg border border-emerald-200 bg-emerald-50/90 p-4 text-sm text-emerald-700"
      >
        <p class="font-medium text-green-800">
          {{ t('password.reset.successTitle') }}
        </p>
        <p class="mt-1">
          {{ successMessage }}
        </p>
      </div>

      <div
        v-if="errorMessage"
        class="mb-5 rounded-lg border border-rose-200 bg-rose-50/90 p-4 text-sm text-rose-700"
      >
        {{ errorMessage }}
      </div>

      <form v-if="!resetComplete" class="space-y-5" @submit.prevent="handleSubmit">
        <BaseInput
          v-model="form.newPassword1"
          :label="t('password.reset.newPassword')"
          type="password"
          autocomplete="new-password"
          :placeholder="t('password.reset.newPasswordPlaceholder')"
          :error="fieldErrors.newPassword1"
          :disabled="submitting"
          required
        />

        <BaseInput
          v-model="form.newPassword2"
          :label="t('password.reset.confirmPassword')"
          type="password"
          autocomplete="new-password"
          :placeholder="t('password.reset.confirmPasswordPlaceholder')"
          :error="fieldErrors.newPassword2"
          :disabled="submitting"
          required
        />

        <BaseButton
          type="submit"
          variant="primary"
          class="w-full"
          :loading="submitting"
          :disabled="submitting"
        >
          {{ submitting ? t('common.loading') : t('password.reset.submit') }}
        </BaseButton>
      </form>

      <BaseButton
        v-else
        variant="primary"
        class="w-full"
        @click="router.push('/login')"
      >
        {{ t('password.reset.backToLogin') }}
      </BaseButton>
      <div class="mt-6 border-t border-slate-200/80 pt-5 text-center text-xs text-slate-400">
        Password changes take effect immediately across the workspace.
      </div>
    </div>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { authApi } from '@/api/auth'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseInput from '@/components/ui/BaseInput.vue'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()

const form = reactive({
  newPassword1: '',
  newPassword2: ''
})

const fieldErrors = reactive({
  newPassword1: '',
  newPassword2: ''
})

const submitting = ref(false)
const errorMessage = ref('')
const successMessage = ref('')
const resetComplete = ref(false)

const validateForm = () => {
  fieldErrors.newPassword1 = ''
  fieldErrors.newPassword2 = ''
  errorMessage.value = ''

  if (!form.newPassword1) {
    fieldErrors.newPassword1 = t('password.reset.newPasswordRequired')
  }

  if (!form.newPassword2) {
    fieldErrors.newPassword2 = t('password.reset.confirmPasswordRequired')
  }

  if (fieldErrors.newPassword1 || fieldErrors.newPassword2) {
    return false
  }

  if (form.newPassword1 !== form.newPassword2) {
    fieldErrors.newPassword2 = t('password.reset.passwordMismatch')
    return false
  }

  if (form.newPassword1.length < 8) {
    fieldErrors.newPassword1 = t('password.reset.passwordTooShort')
    return false
  }

  if (form.newPassword1.length > 32) {
    fieldErrors.newPassword1 = t('password.reset.passwordTooLong')
    return false
  }

  if (!/[a-zA-Z]/.test(form.newPassword1) || !/[0-9]/.test(form.newPassword1)) {
    fieldErrors.newPassword1 = t('password.reset.passwordRequirements')
    return false
  }

  return true
}

const handleSubmit = async () => {
  if (!validateForm()) {
    return
  }

  submitting.value = true
  errorMessage.value = ''

  try {
    const response = await authApi.confirmPasswordReset({
      uid: route.params.uid,
      token: route.params.token,
      newPassword1: form.newPassword1,
      newPassword2: form.newPassword2
    })

    successMessage.value =
      response?.data?.message ||
      response?.message ||
      t('password.reset.successMessage')
    resetComplete.value = true
  } catch (error) {
    const responseData = error.response?.data
    errorMessage.value =
      responseData?.error ||
      responseData?.detail ||
      responseData?.message ||
      t('password.reset.unknownError')
  } finally {
    submitting.value = false
  }
}
</script>
