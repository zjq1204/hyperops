import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const read = (path) => readFileSync(new URL(path, import.meta.url), 'utf8')

const routesSource = read('../../src/admin/routes.js')
const sidebarSource = read('../../src/admin/layout/AdminSidebar.vue')
const apiSource = read('../../src/admin/api/monitoringStack.js')
const credentialsPageSource = read('../../src/admin/pages/Monitoring/Credentials.vue')
const uploadSource = read('../../src/admin/pages/Monitoring/credentials/CredentialUploadModal.vue')
const detailSource = read('../../src/admin/pages/Monitoring/credentials/CredentialDetailDrawer.vue')
const validationSource = read('../../src/admin/pages/Monitoring/credentials/CredentialValidationPanel.vue')
const assetsSource = read('../../src/admin/pages/Monitoring/Assets.vue')

assert.match(routesSource, /path:\s*'\/management\/monitoring\/credentials'/)
assert.match(routesSource, /name:\s*'AdminMonitoringCredentials'/)
assert.match(
  routesSource,
  /path:\s*'\/management\/monitoring\/credentials'[\s\S]{0,500}requiredOperationPermission:\s*'monitoring_credentials_view'/
)
assert.match(sidebarSource, /adminNav\.monitoringCredentials/)
assert.match(sidebarSource, /requiredOperationPermission/)
assert.match(sidebarSource, /hasOperationPermission/)

for (const method of [
  'getCredentials',
  'getCredential',
  'createCredential',
  'rotateCredential',
  'validateCredential',
  'activateCredential',
  'archiveCredential',
  'deleteCredential'
]) {
  assert.match(apiSource, new RegExp(`${method}\\(`), `${method} is required`)
}
assert.match(apiSource, /\/v1\/monitoring\/credentials/)

assert.match(credentialsPageSource, /credential-mobile-list/)
assert.match(credentialsPageSource, /CredentialUploadModal/)
assert.match(credentialsPageSource, /CredentialDetailDrawer/)
assert.match(uploadSource, /CredentialValidationPanel/)
assert.match(detailSource, /associatedHosts|associated_hosts/)
assert.match(detailSource, /versionHistory|versions/)
assert.match(detailSource, /auditHistory|audit_history/)
assert.match(validationSource, /host/)
assert.match(credentialsPageSource, /ConfirmDialog/)
assert.match(credentialsPageSource, /requestConfirm/)
assert.match(credentialsPageSource, /archiveConfirmTitle/)
assert.match(credentialsPageSource, /deleteConfirmTitle/)

const productionSources = [
  apiSource,
  credentialsPageSource,
  uploadSource,
  detailSource,
  validationSource,
  assetsSource
].join('\n')
assert.doesNotMatch(
  productionSources,
  /private_key_encrypted|passphrase_encrypted|public_key_text|legacy_file_name/
)
assert.doesNotMatch(productionSources, /localStorage|console\./)

assert.doesNotMatch(
  assetsSource,
  /handleSshKeyFile|uploadSshKey|sshKeyUploadContent|createSshKey/
)
assert.match(assetsSource, /AdminMonitoringCredentials/)
assert.match(
  assetsSource,
  /getCredentials\(\{\s*status:\s*'active',\s*assignable:\s*true/
)
assert.match(assetsSource, /sshKeyId/)

console.log('admin monitoring credential contracts passed')
