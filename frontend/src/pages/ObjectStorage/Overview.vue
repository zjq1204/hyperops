<template>
  <AppLayout>
    <section class="mx-auto w-full max-w-6xl px-4 py-6 sm:px-6">
      <header class="border-b border-slate-200 pb-5">
        <h1 class="text-xl font-semibold text-slate-950">
          {{ t('objectStorage.title') }}
        </h1>
        <p class="mt-1 text-sm leading-6 text-slate-500">
          {{ t('objectStorage.notConfigured') }}
        </p>
      </header>
    </section>
  </AppLayout>
</template>

<script setup>
import { useI18n } from 'vue-i18n'
import AppLayout from '@/components/layout/AppLayout.vue'

const { t } = useI18n()
</script>
