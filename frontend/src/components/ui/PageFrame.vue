<template>
  <section class="page-shell">
    <header
      v-if="title || $slots.hero"
      :class="variant === 'soft' ? 'page-hero-soft' : 'page-hero'"
    >
      <div class="page-hero-content">
        <slot name="hero">
          <p
            v-if="eyebrow"
            :class="variant === 'soft' ? 'page-eyebrow-soft' : 'page-eyebrow'"
          >
            {{ eyebrow }}
          </p>
          <h1
            v-if="title"
            :class="variant === 'soft' ? 'page-title-soft' : 'page-title'"
          >
            {{ title }}
          </h1>
          <p
            v-if="subtitle"
            :class="variant === 'soft' ? 'page-subtitle-soft' : 'page-subtitle'"
          >
            {{ subtitle }}
          </p>
          <div v-if="$slots.actions" class="page-action-row">
            <slot name="actions" />
          </div>
        </slot>
      </div>
    </header>

    <slot />
  </section>
</template>

<script setup>
defineProps({
  eyebrow: {
    type: String,
    default: ''
  },
  title: {
    type: String,
    default: ''
  },
  subtitle: {
    type: String,
    default: ''
  },
  variant: {
    type: String,
    default: 'default'
  }
})
</script>
