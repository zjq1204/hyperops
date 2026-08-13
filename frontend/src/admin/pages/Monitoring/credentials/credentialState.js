import { hasOperationPermission } from '../../../../utils/platformAccess.js'

const permissionKeys = {
  view: 'monitoring_credentials_view',
  use: 'monitoring_credentials_use',
  manage: 'monitoring_credentials_manage',
  delete: 'monitoring_credentials_delete'
}

export function readField(value, camelKey, snakeKey, fallback = null) {
  if (!value || typeof value !== 'object') return fallback
  return value[camelKey] ?? value[snakeKey] ?? fallback
}

export function collectionFromPayload(payload) {
  if (Array.isArray(payload)) return payload
  return readField(payload, 'results', 'results', []) || []
}

export function credentialActiveVersion(credential) {
  return readField(credential, 'activeVersion', 'active_version')
}

export function credentialActiveVersionNumber(credential) {
  const active = credentialActiveVersion(credential)
  if (active && typeof active === 'object') {
    return readField(active, 'version', 'version', null)
  }
  return active ?? null
}

function metadataSource(credential) {
  const active = credentialActiveVersion(credential)
  return active && typeof active === 'object' ? active : credential || {}
}

function readMetadataField(credential, camelKey, snakeKey, fallback = null) {
  const source = metadataSource(credential)
  return readField(
    source,
    camelKey,
    snakeKey,
    readField(credential, camelKey, snakeKey, fallback)
  )
}

export function credentialLifecycleKey(credential) {
  return readField(credential, 'status', 'status', 'unknown') || 'unknown'
}

export function credentialValidationKey(credential) {
  return (
    readMetadataField(
      credential,
      'validationStatus',
      'validation_status',
      'unverified'
    ) ||
    'unverified'
  )
}

export function credentialFingerprint(credential) {
  return (
    readMetadataField(
      credential,
      'publicKeyFingerprint',
      'public_key_fingerprint',
      ''
    ) || ''
  )
}

export function shortFingerprint(credential, visibleLength = 10) {
  const value = credentialFingerprint(credential)
  if (!value) return ''
  const [prefix, hash = ''] = value.split(':', 2)
  if (hash.length <= visibleLength) return value
  return `${prefix}:${hash.slice(0, visibleLength)}...`
}

export function credentialAlgorithmLabel(credential) {
  const algorithm = readMetadataField(credential, 'algorithm', 'algorithm', '')
  const curve = readMetadataField(credential, 'curve', 'curve', '')
  const keySize = readMetadataField(credential, 'keySize', 'key_size', null)
  return [algorithm, curve || keySize].filter(Boolean).join(' / ')
}

export function credentialHasPassphrase(credential) {
  return Boolean(
    readMetadataField(credential, 'hasPassphrase', 'has_passphrase', false)
  )
}

export function credentialHostCount(credential) {
  return Number(
    readField(
      credential,
      'referencedHostCount',
      'referenced_host_count',
      readField(
        credential,
        'usageCount',
        'usage_count',
        readField(credential, 'hostCount', 'host_count', 0)
      )
    ) || 0
  )
}

export function credentialUpdatedAt(credential) {
  return readField(credential, 'updatedAt', 'updated_at', '') || ''
}

export function credentialLastValidatedAt(credential) {
  const source = metadataSource(credential)
  return (
    readField(
      credential,
      'lastValidatedAt',
      'last_validated_at',
      readField(
        credential,
        'lastValidationTime',
        'last_validation_time',
        readField(source, 'lastValidatedAt', 'last_validated_at', '')
      )
    ) || ''
  )
}

export function credentialTone(status) {
  const tones = {
    active: 'success',
    valid: 'success',
    passed: 'success',
    archived: 'muted',
    draft: 'info',
    unverified: 'warning',
    invalid: 'danger',
    failed: 'danger',
    unavailable: 'danger',
    needs_reupload: 'warning'
  }
  return tones[status] || 'muted'
}

export function hasCredentialPermission(user, action) {
  const key = permissionKeys[action]
  return Boolean(key && hasOperationPermission(user, key))
}

export function canActivateCredentialVersion(version, user) {
  const eligible = Boolean(
    readField(version, 'activationEligible', 'activation_eligible', false)
  )
  return eligible && hasCredentialPermission(user, 'manage')
}

export function canArchiveCredential(credential, user) {
  return (
    credentialLifecycleKey(credential) === 'active' &&
    credentialHostCount(credential) === 0 &&
    hasCredentialPermission(user, 'manage')
  )
}

export function canDeleteCredential(credential, user) {
  return (
    credentialLifecycleKey(credential) === 'archived' &&
    credentialHostCount(credential) === 0 &&
    hasCredentialPermission(user, 'delete')
  )
}
