<template>
  <Teleport to="body">
    <div
      class="pointer-events-none fixed inset-x-4 top-4 z-[9999] flex flex-col items-end gap-2 sm:left-auto sm:w-[26rem]"
      aria-live="polite"
    >
      <TransitionGroup
        enter-active-class="transition duration-200 ease-out"
        enter-from-class="translate-y-2 opacity-0 sm:translate-x-4 sm:translate-y-0"
        enter-to-class="translate-x-0 translate-y-0 opacity-100"
        leave-active-class="transition duration-150 ease-in"
        leave-from-class="opacity-100"
        leave-to-class="translate-y-1 opacity-0 sm:translate-x-4 sm:translate-y-0"
      >
        <article
          v-for="item in state.items"
          :key="item.id"
          :class="['app-toast', `app-toast--${item.type}`]"
          :role="item.type === 'error' ? 'alert' : 'status'"
        >
          <div class="app-toast__icon" aria-hidden="true">
            {{ iconText[item.type] }}
          </div>
          <div class="min-w-0 flex-1">
            <p class="app-toast__title">
              {{ item.title || toastTitles[item.type] }}
            </p>
            <p class="app-toast__message">{{ item.message }}</p>
            <p v-if="item.requestId" class="app-toast__request-id">
              {{ t('common.requestId') }}: {{ item.requestId }}
            </p>
            <button
              v-if="item.action"
              type="button"
              class="app-toast__action"
              @click="runAction(item)"
            >
              {{ item.action.label }}
            </button>
          </div>
          <button
            type="button"
            class="app-toast__close"
            :aria-label="t('common.close')"
            @click="remove(item.id)"
          >
            ×
          </button>
        </article>
      </TransitionGroup>
    </div>
  </Teleport>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useToast } from '@/composables/useToast'

const { t } = useI18n()
const { state, remove } = useToast()

const toastTitles = computed(() => ({
  success: t('common.success'),
  error: t('common.error'),
  warning: t('common.warning'),
  info: t('common.info')
}))

const iconText = {
  success: '✓',
  error: '!',
  warning: '!',
  info: 'i'
}

function runAction(item) {
  item.action?.onClick?.()
  remove(item.id)
}
</script>
