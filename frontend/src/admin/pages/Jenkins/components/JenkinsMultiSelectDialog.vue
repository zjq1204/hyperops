<template>
  <BaseModal
    :show="show"
    size="lg"
    :z-index="100"
    :title="title"
    @close="$emit('close')"
  >
    <div class="space-y-4">
      <div class="flex flex-wrap items-center gap-3">
        <label class="relative min-w-[16rem] flex-1">
          <span class="sr-only">
            {{ t('adminPages.jenkinsEntries.searchChoices') }}
          </span>
          <svg
            class="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
            aria-hidden="true"
          >
            <circle cx="11" cy="11" r="7" stroke-width="1.8" />
            <path d="m20 20-3.5-3.5" stroke-width="1.8" />
          </svg>
          <input
            v-model="search"
            type="search"
            class="admin-modal-control pl-9"
            :placeholder="t('adminPages.jenkinsEntries.searchChoices')"
          />
        </label>
        <span class="text-sm text-slate-600">
          {{
            t('adminPages.jenkinsEntries.selectedChoices', {
              selected: draft.length,
              total: choices.length
            })
          }}
        </span>
      </div>

      <div
        class="flex items-center justify-between border-y border-slate-200 py-2"
      >
        <span class="text-xs text-slate-500">
          {{ t('adminPages.jenkinsEntries.paramChoicesHint') }}
        </span>
        <div class="flex items-center gap-3">
          <button
            type="button"
            class="text-xs font-semibold text-sky-700 hover:text-sky-900 disabled:cursor-not-allowed disabled:opacity-40"
            :disabled="allVisibleSelected || !filteredChoices.length"
            @click="selectVisible"
          >
            {{ t('adminPages.jenkinsEntries.selectAllChoices') }}
          </button>
          <button
            type="button"
            class="text-xs font-semibold text-slate-500 hover:text-slate-800"
            @click="draft = []"
          >
            {{ t('adminPages.jenkinsEntries.clearChoices') }}
          </button>
        </div>
      </div>

      <div
        class="grid max-h-[50vh] grid-cols-1 gap-x-4 overflow-y-auto sm:grid-cols-2 lg:grid-cols-3"
      >
        <label
          v-for="choice in filteredChoices"
          :key="choice"
          class="flex min-h-11 cursor-pointer items-center gap-3 border-b border-slate-100 px-2 py-2 hover:bg-slate-50"
        >
          <input
            v-model="draft"
            type="checkbox"
            :value="choice"
            class="admin-modal-checkbox"
          />
          <span class="min-w-0 break-all text-sm text-slate-700">
            {{ choice }}
          </span>
        </label>
        <p
          v-if="!filteredChoices.length"
          class="col-span-full py-10 text-center text-sm text-slate-500"
        >
          {{ t('adminPages.jenkinsEntries.noChoicesFound') }}
        </p>
      </div>
    </div>

    <template #footer>
      <div class="flex w-full justify-end gap-3">
        <BaseButton variant="secondary" @click="$emit('close')">
          {{ t('common.cancel') }}
        </BaseButton>
        <BaseButton @click="applySelection">
          {{ t('adminPages.jenkinsEntries.applySelection') }}
        </BaseButton>
      </div>
    </template>
  </BaseModal>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseModal from '@/components/ui/BaseModal.vue'

const props = defineProps({
  show: { type: Boolean, default: false },
  title: { type: String, default: '' },
  choices: { type: Array, default: () => [] },
  modelValue: { type: Array, default: () => [] }
})

const emit = defineEmits(['close', 'apply'])
const { t } = useI18n()
const search = ref('')
const draft = ref([])

const filteredChoices = computed(() => {
  const query = search.value.trim().toLowerCase()
  if (!query) return props.choices
  return props.choices.filter((choice) =>
    String(choice).toLowerCase().includes(query)
  )
})

const allVisibleSelected = computed(
  () =>
    filteredChoices.value.length > 0 &&
    filteredChoices.value.every((choice) => draft.value.includes(choice))
)

function selectVisible() {
  draft.value = [...new Set([...draft.value, ...filteredChoices.value])]
}

function applySelection() {
  emit('apply', [...draft.value])
}

watch(
  () => props.show,
  (show) => {
    if (!show) return
    search.value = ''
    draft.value = [...props.modelValue]
  }
)
</script>
