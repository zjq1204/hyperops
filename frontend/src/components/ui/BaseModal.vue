<template>
  <Teleport to="body">
    <Transition
      enter-active-class="transition duration-200 ease-out"
      enter-from-class="opacity-0"
      enter-to-class="opacity-100"
      leave-active-class="transition duration-150 ease-in"
      leave-from-class="opacity-100"
      leave-to-class="opacity-0"
    >
      <div
        v-if="show"
        class="fixed inset-0 overflow-y-auto"
        :style="{ zIndex }"
        @click="handleBackdropClick"
      >
        <div class="flex min-h-full items-center justify-center p-4">
          <div
            class="fixed inset-0 bg-slate-950/42 backdrop-blur-[2px] transition-opacity"
            aria-hidden="true"
          />

          <Transition
            enter-active-class="transition duration-200 ease-out"
            enter-from-class="opacity-0 translate-y-4 sm:translate-y-0 sm:scale-95"
            enter-to-class="opacity-100 translate-y-0 sm:scale-100"
            leave-active-class="transition duration-150 ease-in"
            leave-from-class="opacity-100 translate-y-0 sm:scale-100"
            leave-to-class="opacity-0 translate-y-4 sm:translate-y-0 sm:scale-95"
          >
            <div
              v-if="show"
              :class="[
                'relative my-4 flex max-h-[90vh] w-full transform flex-col overflow-hidden rounded-lg border border-slate-200/85 bg-white text-left shadow-[0_18px_44px_rgba(15,23,42,0.16)] transition-all sm:my-8 sm:max-h-[90vh]',
                modalWidthClass,
              ]"
              @click.stop
            >
              <!-- Header -->
              <div
                class="flex-shrink-0 flex items-start justify-between gap-3 bg-white px-5 py-4 sm:px-6 border-b border-slate-200/80"
              >
                <h3
                  v-if="title"
                  class="text-base font-semibold leading-6 text-gray-900 text-left flex-1 min-w-0"
                >
                  {{ title }}
                </h3>
                <button
                  type="button"
                  class="flex-shrink-0 inline-flex items-center justify-center rounded-md p-1.5 text-gray-400 hover:text-gray-600 hover:bg-gray-100 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-1 transition-colors"
                  aria-label="Close"
                  @click="$emit('close')"
                >
                  <svg
                    class="h-5 w-5"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                    aria-hidden="true"
                  >
                    <path
                      stroke-linecap="round"
                      stroke-linejoin="round"
                      stroke-width="2"
                      d="M6 18L18 6M6 6l12 12"
                    />
                  </svg>
                </button>
              </div>

              <!-- Scrollable Content -->
              <div
                class="glass-scrollbar flex-1 overflow-y-auto -webkit-overflow-scrolling-touch min-h-0"
              >
                <div class="bg-white px-5 py-5 sm:px-6 sm:py-5">
                  <div v-if="icon" class="sm:flex sm:items-start">
                    <div
                      class="mx-auto flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-full sm:mx-0 sm:h-10 sm:w-10"
                      :class="iconClasses"
                    >
                      <component :is="icon" class="h-6 w-6" />
                    </div>

                    <div class="mt-3 text-left sm:ml-4 sm:mt-0 w-full">
                      <slot />
                    </div>
                  </div>
                  <div v-else class="text-left w-full">
                    <slot />
                  </div>
                </div>
              </div>

              <!-- Footer (fixed at bottom) -->
              <div
                v-if="$slots.footer"
                class="bg-slate-50/80 px-5 py-4 sm:flex sm:flex-row-reverse sm:px-6 flex-shrink-0 border-t border-slate-200/80"
              >
                <slot name="footer" />
              </div>
            </div>
          </Transition>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  show: {
    type: Boolean,
    default: false
  },
  title: {
    type: String,
    default: ''
  },
  icon: {
    type: [String, Object],
    default: null
  },
  iconType: {
    type: String,
    default: 'info',
    validator: (value) =>
      ['info', 'success', 'warning', 'error'].includes(value)
  },
  closeOnBackdrop: {
    type: Boolean,
    default: true
  },
  size: {
    type: String,
    default: 'md',
    validator: (value) => ['sm', 'md', 'lg', 'xl', 'wide'].includes(value)
  },
  zIndex: {
    type: [Number, String],
    default: 80
  }
})

const emit = defineEmits(['close'])

const iconClasses = computed(() => {
  const typeClasses = {
    info: 'bg-blue-100 text-blue-600',
    success: 'bg-green-100 text-green-600',
    warning: 'bg-yellow-100 text-yellow-600',
    error: 'bg-red-100 text-red-600'
  }

  return typeClasses[props.iconType]
})

const modalWidthClass = computed(() => {
  const sizeClasses = {
    sm: 'max-w-lg',
    md: 'max-w-2xl',
    lg: 'max-w-4xl',
    xl: 'max-w-5xl',
    wide: 'max-w-6xl',
  }

  return sizeClasses[props.size] || sizeClasses.md
})

const handleBackdropClick = () => {
  if (props.closeOnBackdrop) {
    emit('close')
  }
}
</script>
