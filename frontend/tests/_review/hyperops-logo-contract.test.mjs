import assert from 'node:assert/strict'
import { existsSync, readFileSync } from 'node:fs'

const read = (path) => readFileSync(new URL(path, import.meta.url), 'utf8')

const publicAssets = [
  '../../public/logo-source.svg',
  '../../public/logo-mark.svg',
  '../../public/logo-mark-dark.svg',
  '../../public/logo-mark-mono.svg'
]

for (const asset of publicAssets) {
  const assetUrl = new URL(asset, import.meta.url)
  assert.ok(existsSync(assetUrl), `${asset} must exist`)
  const source = read(asset)
  assert.match(source, /viewBox="0 0 64 64"/)
  assert.match(source, /M27\.5 9\.2A23\.5 23\.5 0 0 0 12\.7 44\.9/)
  assert.match(source, /M36\.5 54\.8A23\.5 23\.5 0 0 0 51\.3 19\.1/)
  assert.match(source, /M22\.5 24v16M41\.5 24v16M23 32h18/)
  assert.doesNotMatch(source, /linearGradient|radialGradient|filter=|mask=/)
}

const workspaceSidebar = read('../../src/components/layout/AppSidebar.vue')
const adminSidebar = read('../../src/admin/layout/AdminSidebar.vue')
const authPage = read('../../src/pages/Auth.vue')
const indexSource = read('../../index.html')

for (const source of [workspaceSidebar, adminSidebar, authPage]) {
  assert.match(source, /\/logo-mark\.svg/)
  assert.doesNotMatch(source, /\/logo-app\.png/)
}

assert.doesNotMatch(authPage, /M7\.5 17\.5h9\.25/)
assert.match(authPage, /alt="HyperOps"/)
assert.match(indexSource, /type="image\/svg\+xml" href="\/favicon\.svg"/)

console.log('HyperOps logo contracts passed')
