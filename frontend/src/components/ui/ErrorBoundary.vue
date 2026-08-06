<template>
  <div
    v-if="hasError"
    class="flex min-h-screen items-center justify-center bg-slate-50 px-6"
  >
    <PageErrorState
      :title="t('common.unexpectedErrorTitle')"
      :message="t('common.unexpectedErrorMessage')"
      @retry="retry"
    />
  </div>

  <slot v-else />
</template>

<script setup>
import { ref, onErrorCaptured } from 'vue'
import { useI18n } from 'vue-i18n'
import PageErrorState from './PageErrorState.vue'

const { t } = useI18n()

const hasError = ref(false)
const error = ref(null)

onErrorCaptured((err, instance, info) => {
  console.error('Component error:', err)
  console.error('Error info:', info)

  hasError.value = true
  error.value = err

  // Return false to prevent the error from propagating
  return false
})

const retry = () => {
  hasError.value = false
  error.value = null
}
</script>
