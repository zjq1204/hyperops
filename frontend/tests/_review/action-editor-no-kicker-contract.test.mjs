import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import assert from 'node:assert/strict'

const repoRoot = resolve(process.cwd(), 'frontend')
const source = readFileSync(
  resolve(repoRoot, 'src/admin/pages/Actions/Templates.vue'),
  'utf8'
)

assert(
  !source.includes('action-editor-kicker'),
  'template editor header should not render a redundant uppercase kicker'
)

assert(
  !source.includes("t('adminPages.actionTemplates.modal.kickerEdit')") &&
    !source.includes("t('adminPages.actionTemplates.modal.kickerNew')"),
  'template editor should not use modal kicker translations'
)

assert(
  !source.includes("t('adminPages.actionTemplates.steps.editor.kicker')"),
  'step editor heading should not render a redundant uppercase kicker'
)

assert(
  !source.includes("t('adminPages.actionTemplates.steps.editor.hint')"),
  'step editor heading should not render explanatory helper copy'
)

console.log('action editor no kicker contract ok')
