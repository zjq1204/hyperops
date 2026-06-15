<template>
  <div class="admin-list-layout">
    <section
      v-if="$slots.toolbar || $slots.toolbarStart || $slots.toolbarEnd"
      class="admin-toolbar"
    >
      <slot name="toolbar">
        <div v-if="$slots.toolbarStart" class="admin-toolbar-start">
          <slot name="toolbarStart" />
        </div>
        <div v-if="$slots.toolbarEnd" class="admin-toolbar-end">
          <slot name="toolbarEnd" />
        </div>
      </slot>
    </section>

    <section
      v-if="$slots.filters || $slots.filterFields || $slots.filterActions"
      class="admin-filter-panel"
    >
      <slot name="filters">
        <div v-if="$slots.filterFields" class="admin-filter-grid">
          <slot name="filterFields" />
        </div>
        <div v-if="$slots.filterActions" class="admin-toolbar-end">
          <slot name="filterActions" />
        </div>
      </slot>
    </section>

    <slot />
  </div>
</template>
