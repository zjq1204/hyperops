<template>
  <div class="relative flex h-screen w-full overflow-hidden">
    <div
      class="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top_left,_rgba(56,189,248,0.14),_transparent_24%),radial-gradient(circle_at_82%_0%,_rgba(249,115,22,0.14),_transparent_18%),linear-gradient(180deg,_rgba(248,251,255,0.96),_rgba(241,245,249,0.88))]"
    ></div>
    <!-- Sidebar -->
    <AppSidebar
      v-if="resolvedShowSidebar"
      :show-mobile-menu="showMobileMenu"
      @close="showMobileMenu = false"
    />

    <!-- Main content area -->
    <div class="relative z-10 flex min-w-0 w-0 flex-1 flex-col h-full overflow-hidden">
      <!-- Header -->
      <AppHeader
        :show-menu-button="resolvedShowSidebar"
        @toggle-menu="showMobileMenu = !showMobileMenu"
      />

      <!-- Main content - scrollable -->
      <main
        class="glass-scrollbar flex-1 min-w-0 overflow-y-auto"
        :class="
          resolvedShowSidebar ? 'px-4 py-4 sm:px-5 lg:px-6' : 'px-6 py-6 sm:px-8 lg:px-10'
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
