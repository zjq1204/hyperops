import { strict as assert } from 'node:assert'
import { existsSync, readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const repoRoot = resolve(here, '..', '..')

const dashboardPath = resolve(repoRoot, 'src/pages/Dashboard.vue')
const jenkinsWorkspacePath = resolve(repoRoot, 'src/pages/Jenkins/Workspace.vue')
const workspaceCssPath = resolve(repoRoot, 'src/assets/css/workspace.css')

for (const filePath of [dashboardPath, jenkinsWorkspacePath, workspaceCssPath]) {
  assert.ok(existsSync(filePath), `${filePath} must exist`)
}

const dashboardSource = readFileSync(dashboardPath, 'utf8')
const jenkinsWorkspaceSource = readFileSync(jenkinsWorkspacePath, 'utf8')
const workspaceCssSource = readFileSync(workspaceCssPath, 'utf8')

for (const className of [
  'workspace-page-grid',
  'workspace-panel',
  'workspace-panel__header',
  'workspace-entry-list',
  'workspace-entry-row',
  'workspace-entry-row__main',
  'workspace-entry-row__icon',
  'workspace-entry-row__body',
  'workspace-entry-row__action',
  'workspace-meta-box',
  'workspace-chip'
]) {
  assert.match(
    workspaceCssSource,
    new RegExp(`\\.${className}`),
    `workspace.css should define .${className}`
  )
}

assert.match(
  dashboardSource,
  /class="workspace-page-grid"/,
  'Dashboard should use the shared workspace page grid'
)
assert.match(
  dashboardSource,
  /class="workspace-panel"/,
  'Dashboard sections should use the shared workspace panel'
)
assert.match(
  dashboardSource,
  /class="[^"]*workspace-entry-row[^"]*"/,
  'Dashboard entries should use the shared workspace entry row'
)
assert.doesNotMatch(
  dashboardSource,
  /class="surface-panel-strong overflow-hidden"/,
  'Dashboard should not keep one-off panel shell classes'
)

assert.match(
  jenkinsWorkspaceSource,
  /class="[^"]*workspace-panel[^"]*"/,
  'Jenkins workspace search panel should use the shared workspace panel'
)
assert.match(
  jenkinsWorkspaceSource,
  /class="workspace-entry-row workspace-entry-row--card"/,
  'Jenkins workspace catalog rows should use the shared card row'
)
assert.match(
  jenkinsWorkspaceSource,
  /class="[^"]*workspace-meta-box[^"]*"/,
  'Jenkins workspace notification summary should use the shared meta box'
)

console.log('workspace-content-style-contract.test.mjs: OK')
