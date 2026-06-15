<template>
  <div class="layout-admin relative h-screen flex w-full overflow-hidden">
    <div
      class="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top_left,_rgba(56,189,248,0.12),_transparent_24%),radial-gradient(circle_at_78%_0%,_rgba(99,102,241,0.08),_transparent_18%),linear-gradient(180deg,_rgba(255,255,255,0.96),_rgba(243,247,253,0.98))]"
    ></div>
    <AdminSidebar
      :show-mobile-menu="showMobileMenu"
      @close="showMobileMenu = false"
    />
    <div class="relative z-10 flex-1 flex flex-col min-w-0 w-0 h-full overflow-hidden">
      <AdminHeader @toggle-menu="showMobileMenu = !showMobileMenu" />
      <main class="glass-scrollbar flex-1 py-4 px-4 min-w-0 overflow-y-auto sm:px-5 lg:px-6">
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
