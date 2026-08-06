<template>
  <div class="page-error-state">
    <div class="page-error-state__mark" aria-hidden="true">!</div>
    <h3>{{ title || t('common.loadFailed') }}</h3>
    <p>{{ message }}</p>
    <small v-if="requestId">{{ t('common.requestId') }}: {{ requestId }}</small>
    <BaseButton
      v-if="retryable"
      variant="outline"
      size="sm"
      @click="$emit('retry')"
    >
      {{ t('common.tryAgain') }}
    </BaseButton>
  </div>
</template>

<script setup>
import { useI18n } from 'vue-i18n'
import BaseButton from '@/components/ui/BaseButton.vue'

const { t } = useI18n()

defineProps({
  title: { type: String, default: '' },
  message: { type: String, required: true },
  requestId: { type: String, default: '' },
  retryable: { type: Boolean, default: true }
})

defineEmits(['retry'])
</script>
