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
  !source.includes('action-editor-eyebrow'),
  'action modals should not render decorative uppercase eyebrow labels'
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

const disallowedHelperCopies = [
  "t('adminPages.actionTemplates.basic.hint')",
  "t('adminPages.actionTemplates.params.hint')",
  "t('adminPages.actionTemplates.steps.hint')",
  "t('adminPages.actionTemplates.auth.hint')",
  "t('adminPages.actionTemplates.tabs.basic.hint')",
  "t('adminPages.actionTemplates.tabs.params.hint')",
  "t('adminPages.actionTemplates.tabs.steps.hint')",
  "t('adminPages.actionTemplates.tabs.auth.hint')",
  "t('adminPages.actionTemplates.preview.kicker')"
]

disallowedHelperCopies.forEach((helperCopy) => {
  assert(
    !source.includes(helperCopy),
    `editor should not render persistent helper copy: ${helperCopy}`
  )
})

console.log('action editor no kicker contract ok')
