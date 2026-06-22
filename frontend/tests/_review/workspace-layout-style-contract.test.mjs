import { strict as assert } from 'node:assert'
import { readFileSync, existsSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'

const here = dirname(fileURLToPath(import.meta.url))
const repoRoot = resolve(here, '..', '..')

const appLayoutPath = resolve(repoRoot, 'src/components/layout/AppLayout.vue')
const appHeaderPath = resolve(repoRoot, 'src/components/layout/AppHeader.vue')
const appSidebarPath = resolve(repoRoot, 'src/components/layout/AppSidebar.vue')
const workspaceCssPath = resolve(repoRoot, 'src/assets/css/workspace.css')

for (const filePath of [
  appLayoutPath,
  appHeaderPath,
  appSidebarPath,
  workspaceCssPath
]) {
  assert.ok(existsSync(filePath), `${filePath} must exist`)
}

const appLayoutSource = readFileSync(appLayoutPath, 'utf8')
const appHeaderSource = readFileSync(appHeaderPath, 'utf8')
const appSidebarSource = readFileSync(appSidebarPath, 'utf8')
const workspaceCssSource = readFileSync(workspaceCssPath, 'utf8')

assert.match(
  appLayoutSource,
  /class="workspace-layout"/,
  'AppLayout should use the shared workspace layout shell'
)
assert.match(
  appLayoutSource,
  /class="workspace-layout__backdrop"/,
  'AppLayout should move the background treatment into workspace.css'
)
assert.match(
  appLayoutSource,
  /class="workspace-layout__content"/,
  'AppLayout should use a shared content wrapper'
)
assert.match(
  appLayoutSource,
  /class="workspace-layout__main/,
  'AppLayout should use a shared main scroller class'
)

assert.match(
  appHeaderSource,
  /class="workspace-header"/,
  'AppHeader should use the shared workspace header class'
)
assert.match(
  appHeaderSource,
  /class="workspace-user-menu-panel"/,
  'AppHeader user menu panel should use the shared menu panel class'
)

assert.match(
  appSidebarSource,
  /class="workspace-sidebar-overlay"/,
  'AppSidebar mobile overlay should use the shared overlay class'
)
assert.doesNotMatch(
  appSidebarSource,
  /border-r border-slate-200\/70 bg-white\/72/,
  'AppSidebar should not keep heavy shell styling inline'
)

for (const className of [
  'workspace-layout',
  'workspace-layout__backdrop',
  'workspace-layout__content',
  'workspace-layout__main',
  'workspace-layout__main--with-sidebar',
  'workspace-layout__main--plain',
  'workspace-header',
  'workspace-user-menu-panel',
  'workspace-sidebar-overlay'
]) {
  assert.match(
    workspaceCssSource,
    new RegExp(`\\.${className}`),
    `workspace.css should define .${className}`
  )
}

console.log('workspace-layout-style-contract.test.mjs: OK')
