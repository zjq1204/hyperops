import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import assert from 'node:assert/strict'

const repoRoot = resolve(process.cwd(), 'frontend')
const source = readFileSync(
  resolve(repoRoot, 'src/admin/pages/Actions/Templates.vue'),
  'utf8'
)

assert(
  source.includes('action-editor--flat'),
  'template editor should opt into the flatter modal layout'
)

assert(
  source.includes('.action-editor--flat .action-editor-topbar'),
  'flat editor should override the nested header card treatment'
)

assert(
  source.includes('.action-editor--flat .action-pane'),
  'flat editor should override pane card borders'
)

assert(
  source.includes('.action-editor--flat .action-step-detail--page'),
  'flat editor should flatten the step editor shell'
)

console.log('action editor flat layout contract ok')
