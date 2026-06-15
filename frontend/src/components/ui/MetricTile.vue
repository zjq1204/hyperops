<template>
  <article :class="tileClasses">
    <div class="metric-card__content">
      <p class="metric-label">{{ label }}</p>
      <div :class="bodyClasses">
        <p class="metric-value">{{ value }}</p>
        <p v-if="hint" class="metric-hint">{{ hint }}</p>
      </div>
    </div>
    <div
      v-if="$slots.icon && variant === 'spotlight'"
      class="metric-card__icon"
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
    ? 'metric-card metric-card--spotlight'
    : 'metric-card metric-card--compact'
)

const bodyClasses = computed(() =>
  props.variant === 'spotlight'
    ? 'metric-card__body metric-card__body--spotlight'
    : 'metric-card__body metric-card__body--compact'
)
</script>
