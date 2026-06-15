<template>
  <div v-if="loading" class="admin-state-shell">
    <slot name="loading">
      <BaseLoading />
    </slot>
  </div>

  <div v-else-if="error" class="admin-empty-state admin-empty-state--error">
    <div class="admin-empty-state-icon admin-empty-state-icon--error">
      <slot name="errorIcon">
        <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="1.8"
            d="M12 9v4m0 4h.01M3.34 17a2 2 0 001.73 3h13.86a2 2 0 001.73-3L13.73 4a2 2 0 00-3.46 0L3.34 17z"
          />
        </svg>
      </slot>
    </div>
    <p class="text-sm font-medium text-red-600">{{ error }}</p>
  </div>

  <EmptyState
    v-else-if="empty"
    variant="admin"
    :title="emptyTitle"
    :description="emptyDescription"
  >
    <template v-if="$slots.emptyIcon" #icon>
      <slot name="emptyIcon" />
    </template>
    <template v-if="$slots.emptyActions" #actions>
      <slot name="emptyActions" />
    </template>
  </EmptyState>

  <slot v-else />
</template>

<script setup>
import BaseLoading from '@/components/ui/BaseLoading.vue'
import EmptyState from '@/components/ui/EmptyState.vue'

defineProps({
  loading: {
    type: Boolean,
    default: false
  },
  error: {
    type: String,
    default: ''
  },
  empty: {
    type: Boolean,
    default: false
  },
  emptyTitle: {
    type: String,
    default: ''
  },
  emptyDescription: {
    type: String,
    default: ''
  }
})
</script>
