<template>
  <article :class="tileClasses">
    <div class="admin-metric-card__content">
      <p class="admin-metric-label">{{ label }}</p>
      <div :class="bodyClasses">
        <p class="admin-metric-value">{{ value }}</p>
        <p v-if="hint" class="admin-metric-hint">{{ hint }}</p>
      </div>
    </div>
    <div
      v-if="$slots.icon && variant === 'spotlight'"
      class="admin-metric-card__icon"
    >
      <slot name="icon" />
    </div>
  </article>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  label: {
    type: String,
    default: ''
  },
  value: {
    type: [String, Number],
    default: ''
  },
  hint: {
    type: String,
    default: ''
  },
  variant: {
    type: String,
    default: 'compact',
    validator: (value) => ['compact', 'spotlight'].includes(value)
  }
})

const tileClasses = computed(() =>
  props.variant === 'spotlight'
    ? 'admin-metric-card admin-metric-card--spotlight'
    : 'admin-metric-card admin-metric-card--compact'
)

const bodyClasses = computed(() =>
  props.variant === 'spotlight'
    ? 'admin-metric-card__body admin-metric-card__body--spotlight'
    : 'admin-metric-card__body admin-metric-card__body--compact'
)
</script>
