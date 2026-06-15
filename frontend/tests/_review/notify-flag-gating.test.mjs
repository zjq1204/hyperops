import { strict as assert } from 'node:assert'
import { readFileSync, existsSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'

const here = dirname(fileURLToPath(import.meta.url))
const repoRoot = resolve(here, '..', '..')

const targets = [
  'src/router/index.js',
  'src/store/user.js',
  'src/admin/routes.js',
  'src/admin/layout/AdminSidebar.vue',
]

for (const rel of targets) {
  const abs = resolve(repoRoot, rel)
  assert.ok(existsSync(abs), `${rel} must exist`)
}

const router = readFileSync(resolve(repoRoot, 'src/router/index.js'), 'utf8')
const adminRoutes = readFileSync(
  resolve(repoRoot, 'src/admin/routes.js'),
  'utf8'
)
const sidebar = readFileSync(
  resolve(repoRoot, 'src/admin/layout/AdminSidebar.vue'),
  'utf8'
)
const store = readFileSync(resolve(repoRoot, 'src/store/user.js'), 'utf8')

// 1. Router must consult a platform flag before allowing notifier routes.
assert.match(
  router,
  /requiresModuleFlag|moduleFlag|enable_notifier/,
  'router must check platform module flag for notifier routes'
)

// 2. Admin notifier routes must declare the module-flag meta.
assert.match(
  adminRoutes,
  /requiresModuleFlag[^}]*enable_notifier/,
  'admin notifier routes must declare requiresModuleFlag: enable_notifier'
)

// 3. Sidebar must filter notifier section based on the flag.
assert.match(
  sidebar,
  /enable_notifier|moduleFlags/,
  'sidebar must consult enable_notifier/moduleFlags for notifier section'
)

// 4. Store must load platform flags at startup.
assert.match(
  store,
  /loadPlatformFlags|platformFlags|enable_notifier/,
  'user store must load platform flags at startup'
)

console.log('notify-flag-gating.test.mjs: OK')
