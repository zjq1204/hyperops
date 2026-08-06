<template>
  <BaseModal
    :show="show"
    :title="
      form.id
        ? t('adminPages.monitoring.editProbe')
        : t('adminPages.monitoring.addProbe')
    "
    :close-on-backdrop="false"
    size="md"
    @close="emit('close')"
  >
    <form id="probe-target-form" class="grid gap-5" @submit.prevent="submit">
      <fieldset class="grid gap-2">
        <legend class="admin-filter-label ml-0">
          {{ t('adminPages.monitoring.probeType') }}
        </legend>
        <div class="grid grid-cols-3 rounded-lg bg-slate-100 p-1" role="group">
          <button
            v-for="type in probeTypes"
            :key="type"
            type="button"
            class="min-h-10 rounded-md text-sm font-semibold transition-colors"
            :class="
              form.type === type
                ? 'bg-white text-slate-950 shadow-sm'
                : 'text-slate-500 hover:text-slate-800'
            "
            :aria-pressed="form.type === type"
            @click="selectType(type)"
          >
            {{ type.toUpperCase() }}
          </button>
        </div>
      </fieldset>

      <label class="admin-filter-field">
        <span class="admin-filter-label ml-0">{{
          t('adminPages.monitoring.target')
        }}</span>
        <input
          ref="targetInput"
          v-model.trim="form.target"
          class="admin-filter-control"
          :class="errors.target ? 'border-rose-400' : ''"
          :placeholder="targetHint"
          :aria-invalid="Boolean(errors.target)"
          @blur="validateTargetField"
        />
        <span v-if="errors.target" class="text-xs leading-5 text-rose-600">
          {{ errors.target }}
        </span>
        <span v-else class="text-xs leading-5 text-slate-500">{{
          targetHint
        }}</span>
      </label>

      <div
        v-if="!enabledNodes.length"
        class="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3"
      >
        <p class="text-sm font-semibold text-amber-900">
          {{ t('adminPages.monitoring.noUsableProbeNodes') }}
        </p>
        <p class="mt-1 text-xs leading-5 text-amber-800">
          {{ t('adminPages.monitoring.noUsableProbeNodesHint') }}
        </p>
        <BaseButton
          class="mt-3"
          variant="outline"
          size="sm"
          @click="emit('open-settings')"
        >
          {{ t('adminPages.monitoring.basicConfiguration') }}
        </BaseButton>
      </div>

      <label v-else class="admin-filter-field">
        <span class="admin-filter-label ml-0">{{
          t('adminPages.monitoring.probeNode')
        }}</span>
        <select
          v-model="form.probeNode"
          class="admin-filter-control"
          :class="errors.probeNode ? 'border-rose-400' : ''"
          :aria-invalid="Boolean(errors.probeNode)"
          @blur="validateNodeField"
        >
          <option value="">
            {{ t('adminPages.monitoring.probeNodeRequired') }}
          </option>
          <option
            v-for="node in enabledNodes"
            :key="node.id"
            :value="String(node.id)"
          >
            {{ node.name }} · {{ node.blackbox_address }}
          </option>
        </select>
        <span v-if="errors.probeNode" class="text-xs leading-5 text-rose-600">
          {{ errors.probeNode }}
        </span>
        <span v-else class="text-xs leading-5 text-slate-500">
          {{ t('adminPages.monitoring.probeExecutionNodeHint') }}
        </span>
      </label>

      <label
        class="flex min-h-12 items-center justify-between gap-4 border-y border-slate-100 py-3"
      >
        <span>
          <span class="block text-sm font-semibold text-slate-800">{{
            t('common.enabled')
          }}</span>
          <span class="mt-1 block text-xs leading-5 text-slate-500">
            {{ t('adminPages.monitoring.probeEnabledHint') }}
          </span>
        </span>
        <input
          v-model="form.enabled"
          type="checkbox"
          class="h-5 w-5 rounded border-slate-300 text-sky-600 focus:ring-sky-500"
        />
      </label>

      <details
        class="rounded-lg border border-slate-200 bg-slate-50/60 px-4 py-2"
      >
        <summary
          class="flex min-h-10 cursor-pointer items-center justify-between text-sm font-semibold text-slate-800"
        >
          {{ t('adminPages.monitoring.optionalSettings') }}
          <span aria-hidden="true" class="text-slate-400">⌄</span>
        </summary>
        <div
          class="grid gap-4 border-t border-slate-200/80 py-4 sm:grid-cols-2"
        >
          <label
            v-for="field in optionalFields"
            :key="field.key"
            class="admin-filter-field"
          >
            <span class="admin-filter-label ml-0">{{ field.label }}</span>
            <input
              v-model.trim="form[field.key]"
              class="admin-filter-control"
            />
          </label>
          <label
            class="flex min-h-11 items-center gap-2 text-sm text-slate-700"
          >
            <input
              v-model="form.critical"
              type="checkbox"
              class="h-4 w-4 rounded border-slate-300 text-sky-600 focus:ring-sky-500"
            />
            {{ t('adminPages.monitoring.critical') }}
          </label>
        </div>
      </details>
    </form>

    <template #footer>
      <div
        class="flex w-full flex-col-reverse gap-2 sm:flex-row sm:justify-end"
      >
        <BaseButton variant="outline" :disabled="saving" @click="emit('close')">
          {{ t('common.cancel') }}
        </BaseButton>
        <BaseButton
          form="probe-target-form"
          type="submit"
          variant="primary"
          :loading="saving"
          :disabled="!enabledNodes.length"
        >
          {{ t('common.save') }}
        </BaseButton>
      </div>
    </template>
  </BaseModal>
</template>

<script setup>
import { computed, nextTick, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseModal from '@/components/ui/BaseModal.vue'
import { validateProbeTarget } from './targetState'

const props = defineProps({
  show: { type: Boolean, default: false },
  target: { type: Object, default: null },
  nodes: { type: Array, default: () => [] },
  saving: { type: Boolean, default: false }
})

const emit = defineEmits(['close', 'submit', 'open-settings'])
const { t } = useI18n()
const probeTypes = ['http', 'tcp', 'icmp']
const targetInput = ref(null)
const form = reactive(defaultForm())
const errors = reactive({ target: '', probeNode: '' })

const enabledNodes = computed(() => props.nodes.filter((node) => node.enabled))
const optionalFields = computed(() => [
  { key: 'region', label: t('adminPages.monitoring.region') },
  { key: 'env', label: t('adminPages.monitoring.env') },
  { key: 'team', label: t('adminPages.monitoring.team') },
  { key: 'service', label: t('adminPages.monitoring.service') },
  { key: 'probeScope', label: t('adminPages.monitoring.probeScope') }
])
const targetHint = computed(() => {
  if (form.type === 'tcp') return t('adminPages.monitoring.tcpTargetHint')
  if (form.type === 'icmp') return t('adminPages.monitoring.icmpTargetHint')
  return t('adminPages.monitoring.httpTargetHint')
})

function defaultForm() {
  return {
    id: '',
    type: 'http',
    target: '',
    probeNode: '',
    enabled: true,
    region: '',
    env: '',
    team: '',
    service: '',
    probeScope: '',
    critical: false
  }
}

function resetForm() {
  const labels = props.target?.labels || {}
  Object.assign(form, defaultForm(), {
    id: props.target?.id || '',
    type: props.target?.type || 'http',
    target: props.target?.target || '',
    probeNode: props.target?.probe_node ? String(props.target.probe_node) : '',
    enabled: props.target ? Boolean(props.target.enabled) : true,
    region: labels.region || '',
    env: labels.env || '',
    team: labels.team || '',
    service: labels.service || '',
    probeScope: labels.probe_scope || '',
    critical: String(labels.critical || '') === 'true'
  })
  if (!props.target && enabledNodes.value.length === 1) {
    form.probeNode = String(enabledNodes.value[0].id)
  }
  errors.target = ''
  errors.probeNode = ''
}

function selectType(type) {
  form.type = type
  errors.target = ''
}

function targetErrorText(key) {
  if (key === 'required') return t('adminPages.monitoring.probeTargetRequired')
  if (key === 'invalid_tcp') return t('adminPages.monitoring.invalidTcpTarget')
  if (key === 'invalid_icmp')
    return t('adminPages.monitoring.invalidIcmpTarget')
  return t('adminPages.monitoring.invalidHttpTarget')
}

function validateTargetField() {
  const key = validateProbeTarget(form.type, form.target)
  errors.target = key ? targetErrorText(key) : ''
  return !key
}

function validateNodeField() {
  errors.probeNode = form.probeNode
    ? ''
    : t('adminPages.monitoring.probeNodeRequired')
  return Boolean(form.probeNode)
}

async function submit() {
  const targetValid = validateTargetField()
  const nodeValid = validateNodeField()
  if (!targetValid || !nodeValid) {
    if (!targetValid) await nextTick(() => targetInput.value?.focus())
    return
  }

  const labels = {}
  for (const [key, value] of [
    ['region', form.region],
    ['env', form.env],
    ['team', form.team],
    ['service', form.service],
    ['probe_scope', form.probeScope]
  ]) {
    if (String(value || '').trim()) labels[key] = String(value).trim()
  }
  if (form.critical) labels.critical = 'true'

  emit('submit', {
    id: form.id,
    payload: {
      type: form.type,
      target: form.target.trim(),
      probe_node: Number(form.probeNode),
      enabled: form.enabled,
      labels
    }
  })
}

watch(
  () => [props.show, props.target, props.nodes],
  ([show]) => {
    if (show) resetForm()
  },
  { deep: true }
)
</script>
