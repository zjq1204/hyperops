import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import assert from 'node:assert/strict'

const repoRoot = resolve(process.cwd(), 'frontend')
const source = readFileSync(
  resolve(repoRoot, 'src/admin/pages/Actions/Templates.vue'),
  'utf8'
)

assert(
  source.includes("nestedStep.action_type === 'jenkins_trigger'"),
  'conditional branch nested steps should render the structured Jenkins editor'
)

assert(
  source.includes('isGitLabStep(nestedStep)'),
  'conditional branch nested steps should render the structured GitLab editor'
)

assert(
  source.includes("nestedStep.action_type === 'manual_approval'"),
  'conditional branch nested steps should render the structured manual approval editor'
)

assert(
  !source.includes("t('adminPages.actionTemplates.branch.configJson')"),
  'conditional branch nested steps should not fall back to raw JSON as the primary editor'
)

console.log('action branch nested editor contract ok')
