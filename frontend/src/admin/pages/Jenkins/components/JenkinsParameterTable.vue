<template>
  <section class="border-t border-slate-200 pt-6">
    <header class="mb-4 flex flex-wrap items-start justify-between gap-3">
      <div>
        <h2 class="text-base font-semibold text-slate-900">
          {{ t('adminPages.jenkinsEntries.parameterPresetTitle') }}
        </h2>
        <p class="mt-1 text-sm text-slate-500">
          {{
            t('adminPages.jenkinsEntries.parameterPresetHint', {
              count: rows.length
            })
          }}
        </p>
      </div>
      <div class="flex items-center gap-2">
        <span v-if="loading" class="text-xs font-medium text-sky-700">
          {{ t('adminPages.jenkinsEntries.loadingParams') }}
        </span>
        <BaseButton
          v-if="canRefresh"
          variant="secondary"
          size="sm"
          :disabled="loading"
          @click="emit('refresh')"
        >
          {{ t('adminPages.jenkinsEntries.refreshParams') }}
        </BaseButton>
        <BaseButton variant="outline" size="sm" @click="addRow">
          {{ t('adminPages.jenkinsEntries.addParam') }}
        </BaseButton>
      </div>
    </header>

    <div v-if="rows.length" class="border-y border-slate-200">
      <div
        class="hidden grid-cols-[minmax(14rem,1.35fr)_10rem_minmax(17rem,1.65fr)_3rem] gap-4 bg-slate-50 px-4 py-2.5 text-xs font-semibold text-slate-500 lg:grid"
      >
        <span>{{ t('adminPages.jenkinsEntries.parameterColumn') }}</span>
        <span>{{ t('adminPages.jenkinsEntries.paramMode') }}</span>
        <span>{{ t('adminPages.jenkinsEntries.paramDefaultValue') }}</span>
        <span></span>
      </div>

      <article
        v-for="(row, index) in rows"
        :key="row.key"
        class="grid gap-4 border-t border-slate-200 px-4 py-4 first:border-t-0 lg:grid-cols-[minmax(14rem,1.35fr)_10rem_minmax(17rem,1.65fr)_3rem] lg:items-start"
      >
        <div class="min-w-0">
          <label v-if="!row.locked" class="block">
            <span
              class="mb-1 block text-xs font-medium text-slate-500 lg:hidden"
            >
              {{ t('adminPages.jenkinsEntries.parameterColumn') }}
            </span>
            <input
              v-model="row.name"
              type="text"
              class="admin-modal-control"
              :placeholder="t('adminPages.jenkinsEntries.paramNamePlaceholder')"
            />
          </label>
          <template v-else>
            <div class="flex flex-wrap items-center gap-x-2 gap-y-1">
              <span class="break-all text-sm font-semibold text-slate-900">
                {{ row.name }}
              </span>
              <span class="text-xs text-slate-500">
                {{ getParamTypeLabel(row.type) }}
              </span>
            </div>
            <p
              v-if="row.description"
              class="mt-1 text-xs leading-5 text-slate-500"
            >
              {{ row.description }}
            </p>
          </template>
        </div>

        <label class="block">
          <span class="mb-1 block text-xs font-medium text-slate-500 lg:hidden">
            {{ t('adminPages.jenkinsEntries.paramMode') }}
          </span>
          <select v-model="row.mode" class="admin-modal-control">
            <option value="editable">
              {{ t('adminPages.jenkinsEntries.modeEditable') }}
            </option>
            <option value="readonly">
              {{ t('adminPages.jenkinsEntries.modeReadonly') }}
            </option>
            <option value="hidden">
              {{ t('adminPages.jenkinsEntries.modeHidden') }}
            </option>
          </select>
        </label>

        <div class="min-w-0">
          <span class="mb-1 block text-xs font-medium text-slate-500 lg:hidden">
            {{ t('adminPages.jenkinsEntries.paramDefaultValue') }}
          </span>
          <button
            v-if="isExtendedChoiceParam(row) && row.choices?.length"
            type="button"
            class="flex min-h-11 w-full items-center justify-between gap-3 rounded-md border border-slate-300 bg-white px-3 py-2 text-left transition hover:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-500/20"
            @click="openMultiSelect(row)"
          >
            <span class="min-w-0">
              <span class="block text-sm text-slate-800">
                {{
                  t('adminPages.jenkinsEntries.selectedChoices', {
                    selected: selectedChoiceCount(row),
                    total: row.choices.length
                  })
                }}
              </span>
              <span
                v-if="selectedChoiceCount(row)"
                class="mt-0.5 block truncate text-xs text-slate-500"
              >
                {{ selectedChoicePreview(row) }}
              </span>
            </span>
            <svg
              class="h-4 w-4 shrink-0 text-slate-400"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
              aria-hidden="true"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="1.8"
                d="m9 18 6-6-6-6"
              />
            </svg>
          </button>
          <select
            v-else-if="isChoiceParam(row) && row.choices?.length"
            v-model="row.default_value"
            class="admin-modal-control"
          >
            <option v-for="choice in row.choices" :key="choice" :value="choice">
              {{ choice }}
            </option>
          </select>
          <label
            v-else-if="isBooleanParam(row)"
            class="admin-modal-toggle min-h-11"
          >
            <input v-model="row.default_value" type="checkbox" />
            <span class="text-sm font-medium text-slate-700">
              {{
                row.default_value
                  ? t('adminPages.jenkinsEntries.booleanTrue')
                  : t('adminPages.jenkinsEntries.booleanFalse')
              }}
            </span>
          </label>
          <textarea
            v-else-if="isTextParam(row)"
            v-model="row.default_value"
            rows="2"
            class="admin-modal-control min-h-[4.5rem]"
            :placeholder="
              t('adminPages.jenkinsEntries.paramDefaultPlaceholder')
            "
          ></textarea>
          <input
            v-else
            v-model="row.default_value"
            :type="isPasswordParam(row) ? 'password' : 'text'"
            class="admin-modal-control"
            :placeholder="
              t('adminPages.jenkinsEntries.paramDefaultPlaceholder')
            "
          />
          <p v-if="row.value_source" class="mt-1.5 text-xs text-slate-500">
            {{ getValueSourceLabel(row.value_source) }}
          </p>
        </div>

        <button
          type="button"
          class="flex h-11 w-11 items-center justify-center rounded-md text-slate-400 transition hover:bg-rose-50 hover:text-rose-600"
          :aria-label="t('common.delete')"
          :title="t('common.delete')"
          @click="rows.splice(index, 1)"
        >
          <svg
            class="h-4 w-4"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
            aria-hidden="true"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="1.8"
              d="M6 7h12m-9 0V5.5A1.5 1.5 0 0110.5 4h3A1.5 1.5 0 0115 5.5V7m-7 0 .7 12.1a1 1 0 001 .9h4.6a1 1 0 001-.9L16 7M10 11v5m4-5v5"
            />
          </svg>
        </button>
      </article>
    </div>

    <div
      v-else
      class="border-y border-dashed border-slate-200 py-10 text-center"
    >
      <p class="text-sm font-medium text-slate-700">
        {{ t('adminPages.jenkinsEntries.noParamsTitle') }}
      </p>
      <p class="mt-1 text-xs text-slate-500">
        {{ t('adminPages.jenkinsEntries.noParamsSubtitle') }}
      </p>
    </div>

    <JenkinsMultiSelectDialog
      :show="multiSelectOpen"
      :title="multiSelectTitle"
      :choices="activeMultiRow?.choices || []"
      :model-value="activeMultiRow?.default_value || []"
      @close="multiSelectOpen = false"
      @apply="applyMultiSelection"
    />
  </section>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import BaseButton from '@/components/ui/BaseButton.vue'
import JenkinsMultiSelectDialog from './JenkinsMultiSelectDialog.vue'
import {
  createParamRow,
  getParamTypeLabelKey,
  isBooleanParam,
  isChoiceParam,
  isExtendedChoiceParam,
  isPasswordParam,
  isTextParam
} from '@/utils/jenkinsParams'

defineProps({
  loading: { type: Boolean, default: false },
  canRefresh: { type: Boolean, default: false }
})

const emit = defineEmits(['refresh'])
const rows = defineModel('rows', { type: Array, required: true })
const { t } = useI18n()
const multiSelectOpen = ref(false)
const activeMultiKey = ref('')

const activeMultiRow = computed(
  () => rows.value.find((row) => row.key === activeMultiKey.value) || null
)

const multiSelectTitle = computed(() =>
  t('adminPages.jenkinsEntries.multiSelectTitle', {
    name: activeMultiRow.value?.name || ''
  })
)

function getParamTypeLabel(type = '') {
  return t(`adminPages.jenkinsEntries.${getParamTypeLabelKey(type)}`)
}

function getValueSourceLabel(source) {
  if (source === 'latest_success_build') {
    return t('adminPages.jenkinsEntries.valueSource.latestSuccessBuild')
  }
  if (source === 'job_default') {
    return t('adminPages.jenkinsEntries.valueSource.jobDefault')
  }
  return source === 'empty'
    ? t('adminPages.jenkinsEntries.valueSource.empty')
    : ''
}

function selectedChoiceCount(row) {
  return Array.isArray(row.default_value) ? row.default_value.length : 0
}

function selectedChoicePreview(row) {
  const values = Array.isArray(row.default_value) ? row.default_value : []
  const preview = values.slice(0, 2).join('、')
  return values.length > 2 ? `${preview} +${values.length - 2}` : preview
}

function openMultiSelect(row) {
  activeMultiKey.value = row.key
  multiSelectOpen.value = true
}

function applyMultiSelection(values) {
  if (activeMultiRow.value) activeMultiRow.value.default_value = values
  multiSelectOpen.value = false
}

function addRow() {
  rows.value.push(createParamRow())
}
</script>
