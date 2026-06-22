<template>
  <div class="workspace-layout">
    <div class="workspace-layout__backdrop"></div>
    <!-- Sidebar -->
    <AppSidebar
      v-if="resolvedShowSidebar"
      :show-mobile-menu="showMobileMenu"
      @close="showMobileMenu = false"
    />

    <!-- Main content area -->
    <div class="workspace-layout__content">
      <!-- Header -->
      <AppHeader
        :show-menu-button="resolvedShowSidebar"
        @toggle-menu="showMobileMenu = !showMobileMenu"
      />

      <!-- Main content - scrollable -->
      <main
        class="workspace-layout__main glass-scrollbar"
        :class="
          resolvedShowSidebar
            ? 'workspace-layout__main--with-sidebar'
            : 'workspace-layout__main--plain'
        "
      >
        <div :key="route.path" class="pb-8">
          <slot />
        </div>
      </main>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import AppHeader from './AppHeader.vue'
import AppSidebar from './AppSidebar.vue'

const props = defineProps({
  showSidebar: {
    type: Boolean,
    default: true
  }
})

const showMobileMenu = ref(false)
const route = useRoute()
const resolvedShowSidebar = computed(() => props.showSidebar)
</script>
