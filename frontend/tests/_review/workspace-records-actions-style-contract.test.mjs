import { strict as assert } from 'node:assert'
import { existsSync, readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const repoRoot = resolve(here, '..', '..')

const files = {
  records: resolve(repoRoot, 'src/pages/Jenkins/Records.vue'),
  actionsWorkspace: resolve(repoRoot, 'src/pages/Actions/Workspace.vue'),
  actionsRuns: resolve(repoRoot, 'src/pages/Actions/Runs.vue'),
  workspaceCss: resolve(repoRoot, 'src/assets/css/workspace.css')
}

for (const filePath of Object.values(files)) {
  assert.ok(existsSync(filePath), `${filePath} must exist`)
}

const recordsSource = readFileSync(files.records, 'utf8')
const actionsWorkspaceSource = readFileSync(files.actionsWorkspace, 'utf8')
const actionsRunsSource = readFileSync(files.actionsRuns, 'utf8')
const workspaceCssSource = readFileSync(files.workspaceCss, 'utf8')

for (const className of [
  'workspace-table-shell',
  'workspace-table',
  'workspace-list',
  'workspace-list__head',
  'workspace-list-row',
  'workspace-list-row__main',
  'workspace-list-row__meta',
  'workspace-list-row__muted',
  'workspace-list-row__actions'
]) {
  assert.match(
    workspaceCssSource,
    new RegExp(`\\.${className}`),
    `workspace.css should define .${className}`
  )
}

assert.match(
  recordsSource,
  /class="[^"]*workspace-panel[^"]*"/,
  'Jenkins records filter panel should use the shared workspace panel'
)
assert.match(
  recordsSource,
  /class="workspace-table-shell"/,
  'Jenkins records table shell should use the shared workspace table shell'
)
assert.match(
  recordsSource,
  /class="workspace-table"/,
  'Jenkins records table should use the shared workspace table'
)
assert.doesNotMatch(
  recordsSource,
  /class="table-shell"/,
  'Jenkins records should not use the admin table shell'
)

assert.match(
  actionsWorkspaceSource,
  /class="[^"]*workspace-panel[^"]*"/,
  'Actions workspace panel should use the shared workspace panel'
)
assert.match(
  actionsWorkspaceSource,
  /class="[^"]*workspace-list[^"]*"/,
  'Actions workspace should use the shared workspace list'
)
assert.match(
  actionsWorkspaceSource,
  /class="[^"]*workspace-list-row[^"]*"/,
  'Actions workspace rows should use the shared workspace list row'
)
assert.doesNotMatch(
  actionsWorkspaceSource,
  /action-template-list|action-template-row/,
  'Actions workspace should not keep template-specific list classes'
)

assert.match(
  actionsRunsSource,
  /class="[^"]*workspace-panel[^"]*"/,
  'Actions runs panel should use the shared workspace panel'
)
assert.match(
  actionsRunsSource,
  /class="[^"]*workspace-list[^"]*"/,
  'Actions runs should use the shared workspace list'
)
assert.match(
  actionsRunsSource,
  /class="[^"]*workspace-list-row[^"]*"/,
  'Actions runs rows should use the shared workspace list row'
)
assert.doesNotMatch(
  actionsRunsSource,
  /action-runs-list|action-run-row/,
  'Actions runs should not keep run-specific list classes'
)

console.log('workspace-records-actions-style-contract.test.mjs: OK')
