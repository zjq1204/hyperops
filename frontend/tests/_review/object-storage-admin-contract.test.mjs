import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

const src = new URL('../../src/', import.meta.url)
const read = (path) => fs.readFileSync(new URL(path, src), 'utf8')
const exists = (path) => fs.existsSync(new URL(path, src))

test('admin object storage has five focused areas', () => {
  const routes = read('admin/routes.js')
  const areas = [
    'AdminObjectStorageOverview',
    'AdminObjectStorageEnterpriseAccess',
    'AdminObjectStorageResources',
    'AdminObjectStorageTasks',
    'AdminObjectStorageAudit'
  ]

  for (const area of areas) assert.match(routes, new RegExp(area))
  assert.match(routes, /requiresSuperuser:\s*true/)
  assert.match(routes, /requiredFeature:\s*['"]admin_object_storage['"]/)
  assert.match(routes, /requiresModuleFlag:\s*['"]enable_object_storage['"]/)
  for (const page of [
    'EnterpriseAccess.vue',
    'Resources.vue',
    'Tasks.vue',
    'Audit.vue'
  ]) {
    assert.equal(exists(`admin/pages/ObjectStorage/${page}`), true, page)
  }
})

test('admin resources keep buckets and credentials as separate views', () => {
  const resources = read('admin/pages/ObjectStorage/Resources.vue')
  assert.match(resources, /Buckets|buckets/)
  assert.match(resources, /Access|access|Credentials|credentials/)
  assert.doesNotMatch(resources, /TOTP|Huawei|notification|archive/i)
})

test('phase one admin UI excludes deferred controls', () => {
  const files = [
    'admin/pages/ObjectStorage/Overview.vue',
    'admin/pages/ObjectStorage/EnterpriseAccess.vue',
    'admin/pages/ObjectStorage/Resources.vue',
    'admin/pages/ObjectStorage/Tasks.vue',
    'admin/pages/ObjectStorage/Audit.vue'
  ]
    .map(read)
    .join('\n')
  assert.doesNotMatch(
    files,
    /TOTP|Huawei Cloud|Huawei|通知配置|离线归档|Archive|Notifications/i
  )
})
