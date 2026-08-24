<template>
  <BaseModal
    :show="show"
    :title="mode === 'rotate' ? t('monitoringCredentials.rotateTitle', { name: credential?.name || '' }) : t('monitoringCredentials.createTitle')"
    size="lg"
    :z-index="90"
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
        <div v-if="mode === 'create'">
          <span class="admin-modal-field-label">{{ t('monitoringCredentials.type') }}</span>
          <div class="grid grid-cols-2 gap-2 rounded-md bg-slate-100 p-1">
            <button v-for="type in credentialTypes" :key="type" type="button" class="rounded-md px-3 py-2 text-sm font-semibold transition" :class="credentialType === type ? 'bg-white text-slate-950 shadow-sm' : 'text-slate-500 hover:text-slate-800'" @click="credentialType = type">
              {{ t(`monitoringCredentials.types.${type}`) }}
            </button>
          </div>
        </div>
        <div v-if="credentialType === 'private_key'">
          <label for="credential-file" class="admin-modal-field-label">
            {{ t('monitoringCredentials.privateKeyFile') }}
          </label>
          <input id="credential-file" type="file" class="block w-full text-sm text-slate-600 file:mr-3 file:rounded-md file:border-0 file:bg-slate-100 file:px-3 file:py-2 file:font-medium file:text-slate-700 hover:file:bg-slate-200 focus:outline-none focus:ring-2 focus:ring-sky-500" required @change="readFile" />
          <p v-if="fileName" class="mt-2 truncate text-xs text-slate-500">{{ fileName }}</p>
        </div>
        <div v-if="credentialType === 'private_key'">
          <label for="credential-passphrase" class="admin-modal-field-label">
            {{ t('monitoringCredentials.passphraseOptional') }}
          </label>
          <input id="credential-passphrase" v-model="passphrase" type="password" class="admin-modal-control" autocomplete="new-password" />
        </div>
        <template v-else>
          <div>
            <label for="credential-password" class="admin-modal-field-label">{{ t('monitoringCredentials.password') }}</label>
            <input id="credential-password" v-model="password" type="password" class="admin-modal-control" autocomplete="new-password" />
          </div>
          <div>
            <label for="credential-password-confirm" class="admin-modal-field-label">{{ t('monitoringCredentials.passwordConfirm') }}</label>
            <input id="credential-password-confirm" v-model="passwordConfirm" type="password" class="admin-modal-control" autocomplete="new-password" />
          </div>
        </template>
        <p v-if="error" role="alert" class="text-sm text-rose-600">{{ error }}</p>
      </form>

      <section v-else-if="stage === 2 && submittedCredential" class="space-y-4">
        <dl class="grid grid-cols-[minmax(7rem,auto)_minmax(0,1fr)] gap-x-4 gap-y-3 text-sm">
          <dt class="text-slate-500">{{ t('monitoringCredentials.type') }}</dt>
          <dd class="font-medium text-slate-900">{{ t(`monitoringCredentials.types.${credentialType}`) }}</dd>
          <template v-if="credentialType === 'private_key'">
            <dt class="text-slate-500">{{ t('monitoringCredentials.algorithm') }}</dt>
            <dd class="font-medium text-slate-900">{{ credentialAlgorithmLabel(submittedMetadata) || t('common.emptyValue') }}</dd>
            <dt class="text-slate-500">{{ t('monitoringCredentials.fingerprint') }}</dt>
            <dd class="break-all font-mono text-xs text-slate-800">{{ credentialFingerprint(submittedMetadata) || t('common.emptyValue') }}</dd>
            <dt class="text-slate-500">{{ t('monitoringCredentials.passphrase') }}</dt>
            <dd class="font-medium text-slate-900">{{ credentialHasPassphrase(submittedMetadata) ? t('common.yes') : t('common.no') }}</dd>
          </template>
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
  credentialTypeKey,
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
const credentialType = ref('private_key')
const password = ref('')
const passwordConfirm = ref('')
const submittedCredential = ref(null)
const activationEligible = ref(false)
const submitting = ref(false)
const activating = ref(false)
const error = ref('')
const validationPanel = ref(null)
const credentialTypes = ['private_key', 'password']

const steps = computed(() => [
  { value: 1, label: t('monitoringCredentials.upload') },
  { value: 2, label: t('monitoringCredentials.review') },
  { value: 3, label: t('monitoringCredentials.validate') }
])
const canSubmit = computed(() => Boolean(
  (props.mode === 'rotate' || name.value.trim()) &&
  (credentialType.value === 'password'
    ? password.value && password.value === passwordConfirm.value
    : fileText.value)
))
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
    const body = credentialType.value === 'password'
      ? { password: password.value, password_confirm: passwordConfirm.value }
      : { private_key: fileText.value, passphrase: passphrase.value }
    if (props.mode === 'create') {
      body.name = name.value.trim()
      body.credential_type = credentialType.value
    }
    submittedCredential.value = props.mode === 'rotate'
      ? await monitoringStackApi.rotateCredential(props.credential.id, body)
      : await monitoringStackApi.createCredential(body)
    clearSecrets()
    stage.value = 2
  } catch (submitError) {
    const fields = submitError?.response?.data || {}
    error.value = fields.private_key?.[0] || fields.passphrase?.[0] || fields.password?.[0] || fields.password_confirm?.[0] || fields.detail || submitError?.message || t('monitoringCredentials.uploadFailed')
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
  password.value = ''
  passwordConfirm.value = ''
}

function reset() {
  clearSecrets()
  stage.value = 1
  name.value = ''
  credentialType.value = props.mode === 'rotate' && props.credential
    ? credentialTypeKey(props.credential)
    : 'private_key'
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

watch(() => props.show, (show) => {
  if (!show) reset()
  else credentialType.value = props.mode === 'rotate' && props.credential
    ? credentialTypeKey(props.credential)
    : 'private_key'
})
</script>
