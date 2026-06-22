<template>
  <div class="layout-admin relative h-screen flex w-full overflow-hidden">
    <div
      class="layout-admin-backdrop pointer-events-none absolute inset-0"
    ></div>
    <AdminSidebar
      :show-mobile-menu="showMobileMenu"
      @close="showMobileMenu = false"
    />
    <div
      class="relative z-10 flex h-full min-w-0 w-0 flex-1 flex-col overflow-hidden"
    >
      <AdminHeader @toggle-menu="showMobileMenu = !showMobileMenu" />
      <main
        class="glass-scrollbar min-w-0 flex-1 overflow-y-auto px-4 py-4 sm:px-5 lg:px-6"
      >
        <div :key="route.path" class="pb-8">
          <slot />
        </div>
      </main>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRoute } from 'vue-router'
import AdminHeader from './AdminHeader.vue'
import AdminSidebar from './AdminSidebar.vue'

const showMobileMenu = ref(false)
const route = useRoute()
</script>
