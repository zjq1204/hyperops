<template>
  <section class="admin-scope-panel">
    <div v-if="$slots.meta || $slots.actions" class="admin-scope-header">
      <div v-if="$slots.meta" class="admin-scope-meta">
        <slot name="meta" />
      </div>
      <div v-if="$slots.actions" class="admin-scope-actions">
        <slot name="actions" />
      </div>
    </div>

    <div v-if="$slots.default" class="admin-scope-grid">
      <slot />
    </div>
  </section>
</template>
