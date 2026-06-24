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
  source.includes('action-branch-case--active'),
  'only the active branch case should expand into the full editor'
)

assert(
  source.includes('uiOpen: false'),
  'branch cases and nested steps should be collapsed when the editor opens'
)

assert(
  !source.includes('uiOpen: true'),
  'initial branch editor state should not force the first branch open'
)

assert(
  source.includes('isBranchCaseOpen(branch)'),
  'branch cases should be rendered through an explicit open-state helper'
)

assert(
  source.includes('action-branch-flow-rail'),
  'nested branch steps should use a visual rail to separate flow from form fields'
)

assert(
  source.includes('isBranchNestedStepOpen(nestedStep)'),
  'nested steps should collapse their heavy action configuration until selected'
)

assert(
  source.includes('function toggleBranchNestedStep') &&
    source.includes('toggleBranchNestedStep('),
  'nested branch steps should have a direct edit/collapse affordance'
)

assert(
  source.includes('@media (max-width: 960px)'),
  'branch editor layout should include a responsive breakpoint for narrower modals'
)

console.log('action branch layout contract ok')
