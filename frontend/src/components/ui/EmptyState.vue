<template>
  <div :class="shellClass">
    <div v-if="$slots.icon" :class="iconClass">
      <slot name="icon" />
    </div>
    <h3 class="text-xl font-semibold text-slate-900">{{ title }}</h3>
    <div v-if="$slots.actions" class="mt-6 flex flex-wrap justify-center gap-3">
      <slot name="actions" />
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  title: {
    type: String,
    default: ''
  },
  description: {
    type: String,
    default: ''
  },
  variant: {
    type: String,
    default: 'default'
  }
})

const shellClass = computed(() =>
  props.variant === 'admin' ? 'admin-empty-state' : 'empty-state'
)

const iconClass = computed(() =>
  props.variant === 'admin' ? 'admin-empty-state-icon' : 'empty-state-icon'
)
</script>
