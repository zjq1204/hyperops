import { strict as assert } from 'node:assert'
import { readFileSync, existsSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'

const here = dirname(fileURLToPath(import.meta.url))
const repoRoot = resolve(here, '..', '..')
const routerPath = resolve(repoRoot, 'src/router/index.js')
const callbackPath = resolve(repoRoot, 'src/pages/OAuthCallback.vue')

assert.ok(existsSync(routerPath), 'router file must exist')
assert.ok(existsSync(callbackPath), 'OAuth callback page must exist')

const routerSource = readFileSync(routerPath, 'utf8')
const callbackSource = readFileSync(callbackPath, 'utf8')

assert.match(
  routerSource,
  /path:\s*['"]\/auth\/oauth\/callback['"]/,
  'router must register /auth/oauth/callback'
)
assert.match(
  routerSource,
  /['"]@\/pages\/OAuthCallback\.vue['"]/,
  'router must reference @/pages/OAuthCallback.vue'
)
assert.match(
  callbackSource,
  /route\.query\.access_token|accessToken/,
  'callback page must read access_token from query'
)
assert.match(
  callbackSource,
  /setToken|localStorage\.setItem\(['"]access_token['"]/,
  'callback page must persist access_token'
)
assert.doesNotMatch(
  callbackSource,
  /['"]\/home['"]/,
  'callback page must not redirect to /home'
)
assert.match(
  callbackSource,
  /router\.replace\(['"]\/login/,
  'callback page must redirect to /login on failure'
)

console.log('oauth-callback-redirect.test.mjs: OK')
