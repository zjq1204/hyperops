import assert from 'node:assert/strict'

import {
  getOperationPermissions,
  hasOperationPermission
} from '../../src/utils/platformAccess.js'
import {
  canActivateCredentialVersion,
  credentialAlgorithmLabel,
  credentialFingerprint,
  credentialHostCount,
  credentialLifecycleKey,
  credentialTypeKey,
  credentialValidationKey,
  hasCredentialPermission,
  shortFingerprint
} from '../../src/admin/pages/Monitoring/credentials/credentialState.js'

const user = {
  access_profile: {
    visible_features: ['admin_monitoring'],
    operation_permissions: [
      'monitoring_credentials_view',
      'monitoring_credentials_use'
    ]
  }
}

assert.deepEqual(getOperationPermissions(user), [
  'monitoring_credentials_view',
  'monitoring_credentials_use'
])
assert.equal(hasOperationPermission(user, 'monitoring_credentials_use'), true)
assert.equal(hasOperationPermission({}, 'monitoring_credentials_use'), false)
assert.equal(
  hasOperationPermission(
    { access_profile: { visible_features: ['monitoring_credentials_delete'] } },
    'monitoring_credentials_delete'
  ),
  false,
  'route features must not grant operation permissions'
)

const camelCredential = {
  status: 'active',
  activeVersion: 3,
  algorithm: 'ssh-ed25519',
  curve: 'Ed25519',
  publicKeyFingerprint: 'SHA256:abcdefghijklmnopqrstuvwxyz',
  referencedHostCount: 2,
  validationStatus: 'valid'
}
assert.equal(credentialLifecycleKey(camelCredential), 'active')
assert.equal(credentialTypeKey(camelCredential), 'private_key')
assert.equal(credentialValidationKey(camelCredential), 'valid')
assert.equal(credentialAlgorithmLabel(camelCredential), 'ssh-ed25519 / Ed25519')
assert.equal(
  credentialFingerprint(camelCredential),
  'SHA256:abcdefghijklmnopqrstuvwxyz'
)
assert.equal(shortFingerprint(camelCredential), 'SHA256:abcdefghij...')
assert.equal(credentialHostCount(camelCredential), 2)

const snakeCredential = {
  status: 'needs_reupload',
  active_version: { version: 4 },
  key_size: 4096,
  algorithm: 'ssh-rsa',
  public_key_fingerprint: 'SHA256:snake',
  host_count: 0,
  validation_status: 'invalid'
}
assert.equal(credentialLifecycleKey(snakeCredential), 'needs_reupload')
assert.equal(credentialValidationKey(snakeCredential), 'invalid')
assert.equal(credentialAlgorithmLabel(snakeCredential), 'ssh-rsa / 4096')
assert.equal(credentialHostCount(snakeCredential), 0)
assert.equal(
  credentialTypeKey({ credential_type: 'password' }),
  'password'
)
assert.equal(hasCredentialPermission(user, 'manage'), false)
assert.equal(
  canActivateCredentialVersion({ activationEligible: true }, user),
  false
)
assert.equal(
  canActivateCredentialVersion(
    { activation_eligible: true },
    {
      access_profile: {
        operation_permissions: ['monitoring_credentials_manage']
      }
    }
  ),
  true
)

console.log('monitoring credential state tests passed')
