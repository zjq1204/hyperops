<template>
  <BaseModal
    :show="show"
    :title="mode === 'rotate' ? t('monitoringCredentials.rotateTitle', { name: credential?.name || '' }) : t('monitoringCredentials.createTitle')"
    size="lg"
    :close-on-backdrop="false"
    @close="handleClose"
  >
    <div class="space-y-5">
      <ol class="grid grid-cols-3 border-b border-slate-200 text-xs font-semibold text-slate-500">
        <li v-for="item in steps" :key="item.value" class="border-b-2 px-2 pb-2 text-center" :class="stage === item.value ? 'border-sky-600 text-sky-700' : 'border-transparent'">
          {{ item.label }}
        </li>
      </ol>

      <form v-if="stage === 1" class="space-y-4" @submit.prevent="submitKey">
        <div v-if="mode === 'create'">
          <label for="credential-name" class="admin-modal-field-label">
            {{ t('monitoringCredentials.credentialName') }}
          </label>
          <input id="credential-name" v-model="name" class="admin-modal-control" required autocomplete="off" />
        </div>
        <div>
          <label for="credential-file" class="admin-modal-field-label">
            {{ t('monitoringCredentials.privateKeyFile') }}
          </label>
          <input id="credential-file" type="file" class="block w-full text-sm text-slate-600 file:mr-3 file:rounded-md file:border-0 file:bg-slate-100 file:px-3 file:py-2 file:font-medium file:text-slate-700 hover:file:bg-slate-200 focus:outline-none focus:ring-2 focus:ring-sky-500" required @change="readFile" />
          <p v-if="fileName" class="mt-2 truncate text-xs text-slate-500">{{ fileName }}</p>
        </div>
        <div>
          <label for="credential-passphrase" class="admin-modal-field-label">
            {{ t('monitoringCredentials.passphraseOptional') }}
          </label>
          <input id="credential-passphrase" v-model="passphrase" type="password" class="admin-modal-control" autocomplete="new-password" />
        </div>
        <p v-if="error" role="alert" class="text-sm text-rose-600">{{ error }}</p>
      </form>

      <section v-else-if="stage === 2 && submittedCredential" class="space-y-4">
        <dl class="grid grid-cols-[minmax(7rem,auto)_minmax(0,1fr)] gap-x-4 gap-y-3 text-sm">
          <dt class="text-slate-500">{{ t('monitoringCredentials.algorithm') }}</dt>
          <dd class="font-medium text-slate-900">{{ credentialAlgorithmLabel(submittedMetadata) || t('common.emptyValue') }}</dd>
          <dt class="text-slate-500">{{ t('monitoringCredentials.fingerprint') }}</dt>
          <dd class="break-all font-mono text-xs text-slate-800">{{ credentialFingerprint(submittedMetadata) || t('common.emptyValue') }}</dd>
          <dt class="text-slate-500">{{ t('monitoringCredentials.passphrase') }}</dt>
          <dd class="font-medium text-slate-900">{{ credentialHasPassphrase(submittedMetadata) ? t('common.yes') : t('common.no') }}</dd>
          <dt class="text-slate-500">{{ t('monitoringCredentials.validation') }}</dt>
          <dd class="font-medium text-slate-900">{{ validationLabel(submittedMetadata) }}</dd>
        </dl>
      </section>

      <CredentialValidationPanel
        v-else-if="stage === 3"
        ref="validationPanel"
        :credential-id="submittedCredential?.id"
        :version-id="submittedVersionId"
        :hosts="hosts"
        @validated="handleValidated"
      />
    </div>

    <template #footer>
      <div class="flex w-full flex-col-reverse gap-2 sm:flex-row sm:justify-end">
        <BaseButton variant="secondary" @click="handleClose">{{ t('common.cancel') }}</BaseButton>
        <BaseButton v-if="stage > 1" variant="outline" @click="stage -= 1">{{ t('common.previous') }}</BaseButton>
        <BaseButton v-if="stage === 1" variant="primary" :loading="submitting" :disabled="!canSubmit" @click="submitKey">
          {{ t('monitoringCredentials.parseKey') }}
        </BaseButton>
        <BaseButton v-else-if="stage === 2" variant="primary" @click="stage = 3">{{ t('common.next') }}</BaseButton>
        <BaseButton v-else-if="canActivate" variant="primary" :loading="activating" @click="activateVersion">{{ t('monitoringCredentials.activate') }}</BaseButton>
        <BaseButton v-else variant="primary" @click="complete">{{ t('monitoringCredentials.complete') }}</BaseButton>
      </div>
    </template>
  </BaseModal>
</template>

<script setup>
import { computed, nextTick, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseModal from '@/components/ui/BaseModal.vue'
import { monitoringStackApi } from '@/admin/api/monitoringStack'
import CredentialValidationPanel from './CredentialValidationPanel.vue'
import {
  credentialAlgorithmLabel,
  credentialFingerprint,
  credentialHasPassphrase,
  credentialValidationKey,
  readField
} from './credentialState'

const props = defineProps({
  show: { type: Boolean, default: false },
  mode: { type: String, default: 'create' },
  credential: { type: Object, default: null },
  hosts: { type: Array, default: () => [] }
})
const emit = defineEmits(['close', 'completed'])
const { t } = useI18n()
const stage = ref(1)
const name = ref('')
const fileName = ref('')
const fileText = ref('')
const passphrase = ref('')
const submittedCredential = ref(null)
const activationEligible = ref(false)
const submitting = ref(false)
const activating = ref(false)
const error = ref('')
const validationPanel = ref(null)

const steps = computed(() => [
  { value: 1, label: t('monitoringCredentials.upload') },
  { value: 2, label: t('monitoringCredentials.review') },
  { value: 3, label: t('monitoringCredentials.validate') }
])
const canSubmit = computed(() => Boolean(fileText.value && (props.mode === 'rotate' || name.value.trim())))
const submittedMetadata = computed(() => {
  const versions = readField(submittedCredential.value, 'versions', 'versions', [])
  const newestDraft = Array.isArray(versions)
    ? [...versions]
        .sort((a, b) => Number(b.version || 0) - Number(a.version || 0))
        .find((version) => credentialValidationKey(version) === 'draft') ||
      [...versions].sort(
        (a, b) => Number(b.version || 0) - Number(a.version || 0)
      )[0]
    : null
  return (
    readField(submittedCredential.value, 'draftVersion', 'draft_version') ||
    newestDraft ||
    readField(submittedCredential.value, 'activeVersion', 'active_version') ||
    submittedCredential.value
  )
})
const submittedVersionId = computed(() => {
  const version = submittedMetadata.value
  return typeof version === 'object' ? version.id : version
})
const canActivate = computed(
  () => activationEligible.value && submittedVersionId.value
)

function validationLabel(item) {
  return t(`monitoringCredentials.validationStates.${credentialValidationKey(item)}`)
}

async function readFile(event) {
  const file = event.target.files?.[0]
  fileName.value = file?.name || ''
  fileText.value = file ? await file.text() : ''
}

async function submitKey() {
  if (!canSubmit.value) return
  submitting.value = true
  error.value = ''
  try {
    const body = {
      private_key: fileText.value,
      passphrase: passphrase.value
    }
    if (props.mode === 'create') body.name = name.value.trim()
    submittedCredential.value = props.mode === 'rotate'
      ? await monitoringStackApi.rotateCredential(props.credential.id, body)
      : await monitoringStackApi.createCredential(body)
    clearSecrets()
    stage.value = 2
  } catch (submitError) {
    const fields = submitError?.response?.data || {}
    error.value = fields.private_key?.[0] || fields.passphrase?.[0] || fields.detail || submitError?.message || t('monitoringCredentials.uploadFailed')
  } finally {
    submitting.value = false
  }
}

function handleValidated(payload) {
  activationEligible.value = payload.activationEligible
}

async function activateVersion() {
  activating.value = true
  error.value = ''
  try {
    await monitoringStackApi.activateCredential(submittedCredential.value.id, submittedVersionId.value)
    complete()
  } catch (activationError) {
    error.value = activationError?.response?.data?.detail || activationError?.message || t('monitoringCredentials.activationFailed')
  } finally {
    activating.value = false
  }
}

function clearSecrets() {
  fileText.value = ''
  passphrase.value = ''
}

function reset() {
  clearSecrets()
  stage.value = 1
  name.value = ''
  fileName.value = ''
  submittedCredential.value = null
  activationEligible.value = false
  submitting.value = false
  activating.value = false
  error.value = ''
  nextTick(() => validationPanel.value?.reset())
}

function handleClose() {
  reset()
  emit('close')
}

function complete() {
  const id = submittedCredential.value?.id
  reset()
  emit('completed', id)
}

watch(() => props.show, (show) => { if (!show) reset() })
</script>
