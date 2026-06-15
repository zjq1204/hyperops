<template>
  <div v-if="totalCount > 0" :class="variantClass">
    <p class="text-sm text-slate-600">
      {{ t('common.pagination.showing', paginationShowing) }}
    </p>
    <div class="flex flex-wrap items-center gap-2">
      <label class="text-sm text-slate-600"
        >{{ t('common.pagination.itemsPerPage') }}:</label
      >
      <select
        :value="pageSize"
        class="rounded-md border border-slate-300 bg-white px-2 py-1.5 text-sm focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-500"
        @change="handlePageSizeChange"
      >
        <option :value="10">10</option>
        <option :value="20">20</option>
        <option :value="50">50</option>
        <option :value="100">100</option>
      </select>
      <BaseButton
        variant="outline"
        size="sm"
        :disabled="currentPage <= 1"
        @click="$emit('prev')"
      >
        {{ t('common.pagination.previous') }}
      </BaseButton>
      <BaseButton
        variant="outline"
        size="sm"
        :disabled="currentPage >= totalPages"
        @click="$emit('next')"
      >
        {{ t('common.pagination.next') }}
      </BaseButton>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import BaseButton from '@/components/ui/BaseButton.vue'

const { t } = useI18n()

const props = defineProps({
  currentPage: {
    type: Number,
    required: true
  },
  pageSize: {
    type: Number,
    required: true
  },
  totalCount: {
    type: Number,
    required: true
  },
  variant: {
    type: String,
    default: 'default'
  }
})

const emit = defineEmits(['update:pageSize', 'prev', 'next'])

const totalPages = computed(() =>
  props.totalCount > 0 ? Math.ceil(props.totalCount / props.pageSize) : 1
)

const variantClass = computed(() =>
  props.variant === 'admin' ? 'admin-pagination' : 'pagination-bar'
)

const paginationShowing = computed(() => ({
  from:
    props.totalCount === 0 ? 0 : (props.currentPage - 1) * props.pageSize + 1,
  to: Math.min(props.currentPage * props.pageSize, props.totalCount),
  total: props.totalCount
}))

function handlePageSizeChange(event) {
  emit('update:pageSize', Number(event.target.value))
}
</script>
