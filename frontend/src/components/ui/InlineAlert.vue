<template>
  <section :class="['inline-alert', `inline-alert--${variant}`]" role="alert">
    <div class="inline-alert__icon" aria-hidden="true">
      {{ variant === 'info' ? 'i' : '!' }}
    </div>
    <div class="min-w-0 flex-1">
      <h4 v-if="title" class="inline-alert__title">{{ title }}</h4>
      <p class="inline-alert__message">{{ message }}</p>
      <p v-if="requestId" class="inline-alert__request-id">
        {{ t('common.requestId') }}: {{ requestId }}
      </p>
      <div v-if="$slots.actions" class="inline-alert__actions">
        <slot name="actions" />
      </div>
    </div>
  </section>
</template>

<script setup>
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

defineProps({
  variant: {
    type: String,
    default: 'error',
    validator: (value) => ['error', 'warning', 'info'].includes(value)
  },
  title: {
    type: String,
    default: ''
  },
  message: {
    type: String,
    required: true
  },
  requestId: {
    type: String,
    default: ''
  }
})
</script>
