import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

const sourceRoot = new URL('../../src/', import.meta.url)
const read = (path) => fs.readFileSync(new URL(path, sourceRoot), 'utf8')
const exists = (path) => fs.existsSync(new URL(path, sourceRoot))

test('employee object storage workspace exposes the four core pages', () => {
  const router = read('router/index.js')

  assert.match(router, /path:\s*['"]\/object-storage['"]/)
  assert.match(router, /ObjectStorageOverview/)
  assert.match(router, /ObjectStorageBuckets/)
  assert.match(router, /ObjectStorageCredentials/)
  assert.match(router, /ObjectStorageApplications/)
  assert.match(router, /requiredFeature:\s*['"]object_storage['"]/)
  assert.match(router, /requiresModuleFlag:\s*['"]enable_object_storage['"]/)

  for (const page of ['Buckets.vue', 'Credentials.vue', 'Applications.vue']) {
    assert.equal(exists(`pages/ObjectStorage/${page}`), true, page)
  }
})

test('employee object storage API keeps secrets out of browser persistence', () => {
  const api = read('api/objectStorage.js')

  assert.match(api, /workspace\/buckets/)
  assert.match(api, /workspace\/applications/)
  assert.match(api, /workspace\/credentials/)
  assert.match(api, /Idempotency-Key/)
  assert.doesNotMatch(api, /localStorage|sessionStorage/)
})

test('employee navigation groups object storage pages without technical cloud detail', () => {
  const sidebar = read('components/layout/AppSidebar.vue')

  assert.match(sidebar, /objectStorageOverview/)
  assert.match(sidebar, /objectStorageBuckets/)
  assert.match(sidebar, /objectStorageCredentials/)
  assert.match(sidebar, /objectStorageApplications/)
})

test('object storage is registered in the workspace access manifest', () => {
  const access = read('utils/platformAccess.js')

  assert.match(access, /key:\s*['"]object_storage['"]/)
  assert.match(access, /defaultPath:\s*['"]\/object-storage\/overview['"]/)
  assert.match(access, /matchers:\s*\[[^\]]*['"]\/object-storage['"]/s)
})
