import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import assert from 'node:assert/strict'

const repoRoot = resolve(process.cwd(), 'frontend')
const source = readFileSync(
  resolve(repoRoot, 'src/admin/pages/Actions/Templates.vue'),
  'utf8'
)

assert(
  source.includes("step.action_type === 'conditional_branch'"),
  'preview rendering should special-case conditional branch steps'
)

assert(
  source.includes('action-flow-branch-lanes'),
  'conditional branch preview should render separate branch lanes'
)

assert(
  source.includes('action-flow-branch-split') &&
    source.includes('action-flow-branch-merge'),
  'conditional branch preview should show split and merge structure'
)

assert(
  source.includes('action-flow-conditional-connectors') &&
    source.includes('action-flow-conditional-label') &&
    source.includes('action-flow-conditional-fan') &&
    source.includes('previewNextStep(index)'),
  'the connector into a conditional branch should render one labelled line per condition'
)

const conditionalLabelBlock = source.match(
  /\.action-flow-conditional-label\s*\{[\s\S]*?\n\}/
)?.[0]
assert(conditionalLabelBlock, 'conditional connector label styles should be defined')

assert(
  !conditionalLabelBlock.includes('white-space: nowrap') &&
    !conditionalLabelBlock.includes('text-overflow: ellipsis'),
  'conditional connector labels should stay readable instead of truncating'
)

assert(
  source.includes('previewBranchCases(step)'),
  'conditional branch preview should iterate branch cases instead of flattening everything into one summary line'
)

assert(
  source.includes('previewBranchNestedSteps(branch)'),
  'conditional branch preview should expose nested branch steps inside each lane'
)

assert(
  source.includes('action-flow-branch-condition') &&
    source.includes('action-flow-branch-step-list') &&
    source.includes('action-flow-branch-condition-pill') &&
    source.includes('action-flow-branch-title'),
  'branch preview should separate condition and nested steps into distinct blocks'
)

assert(
  !source.includes('<small>{{ branchConditionText(branch) }}</small>'),
  'branch condition should be shown as a pill instead of repeated helper text under the branch name'
)

assert(
  source.includes('action-flow-branch-step-item') &&
    source.includes('action-flow-branch-step-arrow'),
  'branch nested steps should render as an ordered mini flow instead of loose chips'
)

assert(
  /nestedIndex\s*<\s*previewBranchNestedSteps\(branch\)\.length\s*-\s*1/.test(
    source
  ),
  'branch nested step flow should connect each child step to the next one'
)

const branchConditionBlock = source.match(
  /\.action-flow-branch-condition\s*\{[\s\S]*?\n\}/
)?.[0]
assert(branchConditionBlock, 'branch condition styles should be defined')

assert(
  !branchConditionBlock.includes('white-space: nowrap') &&
    !branchConditionBlock.includes('text-overflow: ellipsis'),
  'branch conditions should remain readable instead of truncating'
)

const branchLaneBlock = source.match(
  /\.action-flow-branch-lane\s*\{[\s\S]*?\n\}/
)?.[0]
assert(branchLaneBlock, 'branch lane styles should be defined')

assert(
  branchLaneBlock.includes('border: 1px solid #d8e2ef') &&
    branchLaneBlock.includes('box-shadow: 0 3px 10px'),
  'branch lanes should use light bordered cards like the preview reference'
)

assert(
  source.includes('box-shadow: 0 6px 16px') &&
    !source.includes('box-shadow: 0 18px 36px'),
  'preview step cards should use a lighter shadow treatment'
)

console.log('action preview branch flow contract ok')
