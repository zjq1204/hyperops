<template>
  <section class="space-y-4">
    <div class="flex items-center justify-between gap-3">
      <h3 class="text-sm font-semibold text-slate-900">
        {{ t('monitoringCredentials.hostValidation') }}
      </h3>
      <span class="text-xs text-slate-500">
        {{ t('monitoringCredentials.selectedHosts', { count: selectedHostIds.length }) }}
      </span>
    </div>

    <div class="max-h-44 overflow-y-auto border-y border-slate-200">
      <label
        v-for="host in hosts"
        :key="host.id"
        class="flex min-h-11 cursor-pointer items-center gap-3 border-b border-slate-100 px-1 py-2 last:border-0"
      >
        <input
          v-model="selectedHostIds"
          type="checkbox"
          class="admin-modal-checkbox"
          :value="host.id"
          :disabled="loading"
        />
        <span class="min-w-0 flex-1">
          <span class="block truncate text-sm font-medium text-slate-800">
            {{ host.hostname || host.name }}
          </span>
          <span class="block truncate text-xs text-slate-500">
            {{ host.address || host.ipAddress || host.ip_address || t('common.emptyValue') }}
          </span>
        </span>
      </label>
      <p v-if="!hosts.length" class="px-1 py-4 text-sm text-slate-500">
        {{ t('monitoringCredentials.noHosts') }}
      </p>
    </div>

    <div class="flex justify-end">
      <BaseButton
        variant="outline"
        size="sm"
        :loading="loading"
        :disabled="!selectedHostIds.length"
        @click="runValidation"
      >
        {{ t('monitoringCredentials.validateHosts') }}
      </BaseButton>
    </div>

    <p v-if="error" role="alert" class="text-sm text-rose-600">{{ error }}</p>

    <div v-if="results.length" class="divide-y divide-slate-100 border-y border-slate-200">
      <div
        v-for="result in results"
        :key="result.id || `${result.hostId || result.host_id}-${result.checkedAt || result.checked_at}`"
        class="flex items-center gap-3 py-3"
      >
        <span
          class="h-2 w-2 flex-none rounded-full"
          :class="resultPassed(result) ? 'bg-emerald-500' : 'bg-rose-500'"
        />
        <span class="min-w-0 flex-1">
          <span class="block truncate text-sm font-medium text-slate-800">
            {{ result.hostName || result.host_name || hostName(result.hostId || result.host_id) }}
          </span>
          <span class="block truncate text-xs text-slate-500">
            {{ validationMessage(result) }}
          </span>
        </span>
        <span class="text-xs font-semibold" :class="resultPassed(result) ? 'text-emerald-700' : 'text-rose-700'">
          {{ resultPassed(result) ? t('monitoringCredentials.passed') : t('monitoringCredentials.failed') }}
        </span>
      </div>
    </div>
  </section>
</template>

<script setup>
import { ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import BaseButton from '@/components/ui/BaseButton.vue'
import { monitoringStackApi } from '@/admin/api/monitoringStack'
import { collectionFromPayload } from './credentialState'

const props = defineProps({
  credentialId: { type: [Number, String], default: null },
  versionId: { type: [Number, String], default: null },
  hosts: { type: Array, default: () => [] }
})
const emit = defineEmits(['validated'])
const { t } = useI18n()
const selectedHostIds = ref([])
const results = ref([])
const loading = ref(false)
const error = ref('')

function resultPassed(result) {
  return ['passed', 'success', 'valid'].includes(result.status)
}

function hostName(id) {
  const host = props.hosts.find((item) => String(item.id) === String(id))
  return host?.hostname || host?.name || t('monitoringCredentials.hostFallback', { id })
}

function validationMessage(result) {
  if (resultPassed(result)) {
    const latency = result.latencyMs ?? result.latency_ms
    return latency == null
      ? t('monitoringCredentials.validationPassed')
      : t('monitoringCredentials.validationLatency', { latency })
  }
  return result.errorCode || result.error_code || t('monitoringCredentials.validationFailed')
}

async function runValidation() {
  if (!props.credentialId || !selectedHostIds.value.length) return
  loading.value = true
  error.value = ''
  try {
    const payload = await monitoringStackApi.validateCredential(
      props.credentialId,
      {
        version_id: props.versionId,
        host_ids: [...selectedHostIds.value]
      }
    )
    results.value = collectionFromPayload(payload?.validations || payload)
    const allPassed =
      results.value.length > 0 && results.value.every((item) => resultPassed(item))
    emit('validated', {
      results: results.value,
      activationEligible: Boolean(
        payload?.activationEligible ?? payload?.activation_eligible ?? allPassed
      )
    })
  } catch (validationError) {
    error.value =
      validationError?.response?.data?.detail ||
      validationError?.message ||
      t('monitoringCredentials.validationFailed')
  } finally {
    loading.value = false
  }
}

function reset() {
  selectedHostIds.value = []
  results.value = []
  error.value = ''
  loading.value = false
}

watch(() => [props.credentialId, props.versionId], reset)

defineExpose({ reset })
</script>
