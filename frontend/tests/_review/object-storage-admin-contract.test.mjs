import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

const src = new URL('../../src/', import.meta.url)
const read = (path) => fs.readFileSync(new URL(path, src), 'utf8')
const exists = (path) => fs.existsSync(new URL(path, src))

test('admin object storage exposes platform-level workspaces', () => {
  const routes = read('admin/routes.js')
  const sidebar = read('admin/layout/AdminSidebar.vue')
  for (const name of [
    'AdminObjectStorageOverview',
    'AdminObjectStorageSettings',
    'AdminObjectStorageBuckets',
    'AdminObjectStorageAccessKeys',
    'AdminObjectStorageApplications',
    'AdminObjectStorageAudit'
  ]) assert.match(routes, new RegExp(name))
  for (const label of [
    'objectStorageOverview',
    'objectStorageSettings',
    'objectStorageBuckets',
    'objectStorageAccessKeys',
    'objectStorageApplications',
    'objectStorageAudit'
  ]) assert.match(sidebar, new RegExp(label))
  assert.match(routes, /requiresSuperuser:\s*true/)
  assert.match(sidebar, /requiresSuperuser:\s*true/)
  assert.doesNotMatch(routes, /EnterpriseAccess|enterprise-access|tenant/i)
  assert.doesNotMatch(sidebar, /EnterpriseAccess|enterprise-access|tenant/i)
})

test('admin pages use platform API without tenant query parameters', () => {
  const api = read('admin/api/objectStorage.js')
  assert.match(api, /settings\//)
  for (const resource of ['resource-pools', 'buckets', 'access-keys', 'applications', 'audit-events']) {
    assert.match(api, new RegExp(`${resource}`))
  }
  assert.doesNotMatch(api, /listTenants|tenant_id|tenants\//)
  for (const page of ['Overview.vue', 'StorageSettings.vue', 'Buckets.vue', 'AccessKeys.vue', 'Applications.vue', 'Audit.vue']) {
    assert.equal(exists(`admin/pages/ObjectStorage/${page}`), true, page)
    assert.doesNotMatch(read(`admin/pages/ObjectStorage/${page}`), /selectTenant|tenantId|Enterprise access/i, page)
  }
  assert.equal(exists('admin/pages/ObjectStorage/EnterpriseAccess.vue'), false)
})

test('admin controls preserve protected secret and recovery actions', () => {
  const settings = read('admin/pages/ObjectStorage/StorageSettings.vue')
  const keys = read('admin/pages/ObjectStorage/AccessKeys.vue')
  const buckets = read('admin/pages/ObjectStorage/Buckets.vue')
  assert.match(settings, /management_access_key/)
  assert.match(settings, /management_secret_key/)
  assert.match(keys, /revealAccessKey/)
  assert.match(keys, /revokeAccessKey/)
  assert.match(buckets, /releaseBucket/)
  assert.match(buckets, /recoverBucket/)
})

test('authentication pages use the platform-wide Feishu contract', () => {
  const authentication = read('admin/pages/Management/Authentication.vue')
  const feishu = read('admin/pages/Management/FeishuAuthentication.vue')
  const combined = `${authentication}\n${feishu}`

  assert.match(authentication, /getFeishu\(\)/)
  assert.match(feishu, /saveFeishu\(body\)/)
  assert.match(feishu, /validateFeishu\(\)/)
  assert.match(authentication, /feishuSources\.value = \[null\]/)
  assert.doesNotMatch(combined, /listTenants|tenantId|query:\s*\{\s*tenant/)
})

test('storage settings use a summary and modal setup workflow', () => {
  const settings = read('admin/pages/ObjectStorage/StorageSettings.vue')
  const api = read('admin/api/objectStorage.js')

  assert.match(settings, /BaseModal/)
  assert.match(settings, /isConfigured/)
  assert.match(settings, /startSetup/)
  assert.match(settings, /activeStep/)
  assert.match(settings, /saveAndFinish/)
  assert.match(settings, /const totalSteps = 3/)
  assert.doesNotMatch(settings, /<nav :aria-label="t\('adminPages\.objectStorage\.setupTitle'\)/)
  assert.doesNotMatch(settings, /key: 'review'/)
  assert.match(settings, /feishuReady[^\n]+validation_status === 'valid'/)
  assert.match(settings, /isConfigured[^\n]+feishu\.value\?\.enabled/)
  assert.match(api, /enablePlatform/)
})

test('storage overview does not show a persistent pause warning', () => {
  const overview = read('admin/pages/ObjectStorage/Overview.vue')

  assert.doesNotMatch(overview, /applicationsPaused|pause_new_applications|InlineAlert/)
})

test('storage overview statistics stay compact', () => {
  const overview = read('admin/pages/ObjectStorage/Overview.vue')

  assert.doesNotMatch(overview, /stat\.hint|bucketCountHint|keyCountHint|pendingCountHint|poolCountHint/)
})

test('storage platform status uses a readable row summary', () => {
  const overview = read('admin/pages/ObjectStorage/Overview.vue')

  assert.match(overview, /platformDetails/)
  assert.match(overview, /divide-y divide-slate-200/)
  assert.doesNotMatch(overview, /InfoCell|platformStateHint/)
})
