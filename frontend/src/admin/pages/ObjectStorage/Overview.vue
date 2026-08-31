<template>
  <AdminLayout>
    <PageFrame
      variant="soft"
      :title="t('adminPages.objectStorage.title')"
      :subtitle="t('adminPages.objectStorage.notConfigured')"
    />
  </AdminLayout>
</template>

<script setup>
import { useI18n } from 'vue-i18n'
import AdminLayout from '@/admin/layout/AdminLayout.vue'
import PageFrame from '@/components/ui/PageFrame.vue'

const { t } = useI18n()
</script>
