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
      <div v-if="show" class="fixed inset-0 z-[80]" @click.self="emit('close')">
        <div class="absolute inset-0 bg-slate-950/45" aria-hidden="true" />
        <Transition
          enter-active-class="transition duration-200 ease-out"
          enter-from-class="translate-x-8 opacity-0"
          enter-to-class="translate-x-0 opacity-100"
          leave-active-class="transition duration-150 ease-in"
          leave-from-class="translate-x-0 opacity-100"
          leave-to-class="translate-x-8 opacity-0"
        >
          <aside
            v-if="show"
            class="glass-scrollbar absolute inset-y-0 right-0 flex w-full max-w-lg flex-col overflow-y-auto bg-white shadow-2xl"
            role="dialog"
            aria-modal="true"
            :aria-label="t('adminPages.monitoring.probeDetails')"
          >
            <header
              class="sticky top-0 z-10 flex items-center justify-between gap-4 border-b border-slate-200 bg-white px-5 py-4 sm:px-6"
            >
              <h2 class="text-base font-semibold text-slate-950">
                {{ t('adminPages.monitoring.probeDetails') }}
              </h2>
              <button
                type="button"
                class="inline-flex h-9 w-9 items-center justify-center rounded-md text-xl text-slate-400 transition hover:bg-slate-100 hover:text-slate-700 focus:outline-none focus:ring-2 focus:ring-sky-500"
                :aria-label="t('common.close')"
                @click="emit('close')"
              >
                ×
              </button>
            </header>

            <div
              v-if="target"
              class="grid flex-1 content-start gap-6 px-5 py-5 sm:px-6"
            >
              <section class="border-b border-slate-100 pb-6">
                <h3 class="text-xs font-semibold text-slate-500">
                  {{ t('adminPages.monitoring.effectDetails') }}
                </h3>
                <div class="mt-3 flex items-center gap-2">
                  <span class="h-2 w-2 rounded-full" :class="effectDotClass" />
                  <span class="text-sm font-semibold" :class="effectTextClass">
                    {{ effectText }}
                  </span>
                </div>
                <p class="mt-2 text-sm leading-6 text-slate-500">
                  {{ effectHint }}
                </p>
                <p
                  v-if="effectState?.error"
                  class="mt-2 rounded-lg bg-rose-50 px-3 py-2 text-sm leading-6 text-rose-700"
                >
                  {{ effectState.error }}
                </p>
              </section>

              <section class="border-b border-slate-100 pb-6">
                <h3 class="text-xs font-semibold text-slate-500">
                  {{ t('adminPages.monitoring.baseConfiguration') }}
                </h3>
                <dl
                  class="mt-4 grid grid-cols-[7rem_minmax(0,1fr)] gap-x-4 gap-y-3 text-sm"
                >
                  <dt class="text-slate-400">
                    {{ t('adminPages.monitoring.target') }}
                  </dt>
                  <dd class="break-all font-medium text-slate-800">
                    {{ target.target }}
                  </dd>
                  <dt class="text-slate-400">
                    {{ t('adminPages.monitoring.probeType') }}
                  </dt>
                  <dd class="font-medium uppercase text-slate-800">
                    {{ target.type }}
                  </dd>
                  <dt class="text-slate-400">
                    {{ t('adminPages.monitoring.probeNode') }}
                  </dt>
                  <dd class="font-medium text-slate-800">
                    {{
                      target.probe_node_name ||
                      t('adminPages.monitoring.probeNodeNotSelected')
                    }}
                  </dd>
                  <dt class="text-slate-400">
                    {{ t('adminPages.monitoring.configStatus') }}
                  </dt>
                  <dd class="font-medium text-slate-800">
                    {{
                      target.enabled
                        ? t('adminPages.monitoring.probeConfigEnabled')
                        : t('adminPages.monitoring.probeConfigDisabled')
                    }}
                  </dd>
                  <dt class="text-slate-400">
                    {{ t('adminPages.monitoring.finalBlackboxAddress') }}
                  </dt>
                  <dd class="break-all font-mono text-xs text-slate-700">
                    {{ target.blackbox_address || t('common.emptyValue') }}
                  </dd>
                </dl>
              </section>

              <section>
                <h3 class="text-xs font-semibold text-slate-500">
                  {{ t('adminPages.monitoring.labels') }}
                </h3>
                <div class="mt-3 flex flex-wrap gap-2">
                  <span
                    v-for="[key, value] in labelPairs"
                    :key="key"
                    class="rounded-md border border-slate-200 bg-slate-50 px-2 py-1 text-xs font-medium text-slate-600"
                  >
                    {{ key }}={{ value }}
                  </span>
                  <span
                    v-if="!labelPairs.length"
                    class="text-sm text-slate-400"
                  >
                    {{ t('common.emptyValue') }}
                  </span>
                </div>
              </section>
            </div>

            <footer
              v-if="target"
              class="sticky bottom-0 flex flex-col-reverse gap-2 border-t border-slate-200 bg-slate-50 px-5 py-4 sm:flex-row sm:justify-end sm:px-6"
            >
              <BaseButton
                variant="outline"
                @click="emit('toggle-enabled', target)"
              >
                {{
                  target.enabled
                    ? t('adminPages.monitoring.disableTarget')
                    : t('adminPages.monitoring.enableTarget')
                }}
              </BaseButton>
              <BaseButton variant="primary" @click="emit('edit', target)">
                {{ t('common.edit') }}
              </BaseButton>
            </footer>
          </aside>
        </Transition>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import BaseButton from '@/components/ui/BaseButton.vue'
import { probeLabelPairs } from './targetState'

const props = defineProps({
  show: { type: Boolean, default: false },
  target: { type: Object, default: null },
  effectState: { type: Object, default: () => ({ key: 'unknown', error: '' }) }
})

const emit = defineEmits(['close', 'edit', 'toggle-enabled'])
const { t } = useI18n()
const labelPairs = computed(() => probeLabelPairs(props.target?.labels))

const effectText = computed(() =>
  t(
    `adminPages.monitoring.${effectTextKeys[props.effectState?.key] || 'effectUnknown'}`
  )
)
const effectHint = computed(() =>
  t(
    `adminPages.monitoring.${effectHintKeys[props.effectState?.key] || 'effectUnknownHint'}`
  )
)
const effectTextClass = computed(
  () => effectClasses[props.effectState?.key]?.text || 'text-slate-600'
)
const effectDotClass = computed(
  () => effectClasses[props.effectState?.key]?.dot || 'bg-slate-400'
)

const effectTextKeys = {
  disabled: 'probeConfigDisabled',
  incomplete: 'effectIncomplete',
  unknown: 'effectUnknown',
  pending: 'effectPending',
  effective: 'effectEffective',
  abnormal: 'effectAbnormal'
}
const effectHintKeys = {
  disabled: 'probeConfigDisabled',
  incomplete: 'effectIncompleteHint',
  unknown: 'effectUnknownHint',
  pending: 'effectPendingHint',
  effective: 'effectEffectiveHint',
  abnormal: 'effectAbnormalHint'
}
const effectClasses = {
  disabled: { text: 'text-slate-500', dot: 'bg-slate-400' },
  incomplete: { text: 'text-blue-700', dot: 'bg-blue-500' },
  unknown: { text: 'text-slate-600', dot: 'bg-slate-400' },
  pending: { text: 'text-amber-700', dot: 'bg-amber-500' },
  effective: { text: 'text-emerald-700', dot: 'bg-emerald-500' },
  abnormal: { text: 'text-rose-700', dot: 'bg-rose-500' }
}

function handleEscape(event) {
  if (event.key === 'Escape' && props.show) emit('close')
}

watch(
  () => props.show,
  (show) => {
    document.body.style.overflow = show ? 'hidden' : ''
  }
)
onMounted(() => document.addEventListener('keydown', handleEscape))
onBeforeUnmount(() => {
  document.body.style.overflow = ''
  document.removeEventListener('keydown', handleEscape)
})
</script>
