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

test('employee overview avoids duplicate navigation and redundant bucket errors', () => {
  const pageNames = [
    'Overview.vue',
    'Buckets.vue',
    'Credentials.vue',
    'Applications.vue'
  ]

  for (const pageName of pageNames) {
    const page = read(`pages/ObjectStorage/${pageName}`)

    assert.doesNotMatch(page, /<ObjectStorageNav\s*\/>/, pageName)
    assert.doesNotMatch(page, /import ObjectStorageNav/, pageName)
    assert.doesNotMatch(page, /loadBucketsTitle/, pageName)
  }

  const overview = read('pages/ObjectStorage/Overview.vue')

  assert.doesNotMatch(overview, /<InlineAlert[\s\S]*loadBucketsTitle/)
  assert.doesNotMatch(overview, /import InlineAlert/)
})

test('employee object storage states remain informative and recoverable', () => {
  const pageNames = [
    'Overview.vue',
    'Buckets.vue',
    'Credentials.vue',
    'Applications.vue'
  ]

  for (const pageName of pageNames) {
    const page = read(`pages/ObjectStorage/${pageName}`)

    assert.match(page, /PageErrorState/, pageName)
    assert.match(page, /@retry/, pageName)
  }

  const credentials = read('pages/ObjectStorage/Credentials.vue')
  assert.match(credentials, /showSecretMaterial/)
  assert.match(credentials, /:type="showSecretMaterial \? 'text' : 'password'"/)
  assert.match(credentials, /lg:grid-cols-\[/)
})

test('unconfigured object storage uses a neutral setup state', () => {
  const pageNames = [
    'Overview.vue',
    'Buckets.vue',
    'Credentials.vue',
    'Applications.vue'
  ]

  const api = read('api/objectStorage.js')
  assert.match(api, /OBJECT_STORAGE_NOT_CONFIGURED/)

  for (const pageName of pageNames) {
    const page = read(`pages/ObjectStorage/${pageName}`)

    assert.match(page, /isObjectStorageNotConfigured/, pageName)
    assert.match(page, /objectStorage\.notConfigured/, pageName)
  }
})

test('shared page components render authored context and empty-state guidance', () => {
  const pageFrame = read('components/ui/PageFrame.vue')
  const emptyState = read('components/ui/EmptyState.vue')

  assert.match(pageFrame, /v-if="eyebrow"[\s\S]*page-eyebrow/)
  assert.match(pageFrame, /v-if="subtitle"[\s\S]*page-subtitle/)
  assert.match(emptyState, /v-if="description"/)
  assert.match(emptyState, /empty-state__description/)
})

test('credential data sources fail independently', () => {
  const credentials = read('pages/ObjectStorage/Credentials.vue')

  assert.match(credentials, /Promise\.allSettled/)
  assert.match(credentials, /overviewLoadError/)
  assert.match(credentials, /applicationsLoadError/)
  assert.match(credentials, /rotationLoadError/)
  assert.doesNotMatch(credentials, /v-if="loadError"[\s\S]*class="grid gap-5/)
})

test('object storage is registered in the workspace access manifest', () => {
  const access = read('utils/platformAccess.js')

  assert.match(access, /key:\s*['"]object_storage['"]/)
  assert.match(access, /defaultPath:\s*['"]\/object-storage\/overview['"]/)
  assert.match(access, /matchers:\s*\[[^\]]*['"]\/object-storage['"]/s)
})
