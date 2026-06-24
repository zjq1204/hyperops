import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import assert from 'node:assert/strict'

const repoRoot = resolve(process.cwd(), 'frontend')
const source = readFileSync(
  resolve(repoRoot, 'src/admin/pages/Actions/Templates.vue'),
  'utf8'
)

assert(
  source.includes('action-branch-case-meta'),
  'branch cases should expose a compact condition summary in the header'
)

assert(
  source.includes('action-branch-rule-card'),
  'branch condition controls should be grouped as a distinct rule card'
)

assert(
  source.includes('action-branch-flow-rail'),
  'nested branch steps should use a visual rail to separate flow from form fields'
)

assert(
  source.includes('@media (max-width: 960px)'),
  'branch editor layout should include a responsive breakpoint for narrower modals'
)

console.log('action branch layout contract ok')
