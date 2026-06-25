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

const canvasBlock = source.match(/\.action-flow-canvas\s*\{[\s\S]*?\n\}/)?.[0]
assert(canvasBlock, 'action flow canvas styles should be defined')

assert(
  canvasBlock.includes('align-items: center'),
  'preview flow nodes should be vertically centered in the canvas'
)

assert(
  source.includes('action-flow-conditional-connectors') &&
    source.includes('action-flow-branch-inputs') &&
    source.includes('action-flow-conditional-label') &&
    source.includes('action-flow-conditional-curves') &&
    source.includes('action-flow-conditional-origin') &&
    source.includes('action-flow-conditional-arrow-line') &&
    source.includes('previewConnectorCurve('),
  'the connector inside a conditional branch should render labelled curved arrows from one origin point'
)

assert(
  !source.includes('marker-end="url(#action-flow-conditional-arrow)"'),
  'conditional arrow heads should remain visible after the label instead of being hidden under the label'
)

assert(
  !source.includes('action-flow-conditional-fan'),
  'conditional branch connectors should not use overlapping fan lines'
)

const conditionalConnectorBlock = source.match(
  /\.action-flow-conditional-connectors\s*\{[\s\S]*?\n\}/
)?.[0]
assert(
  conditionalConnectorBlock,
  'conditional connector container styles should be defined'
)

assert(
  !conditionalConnectorBlock.includes('margin-left: -') &&
    !conditionalConnectorBlock.includes('margin-right: -'),
  'conditional connector spacing should not rely on negative margins'
)

const branchDiagramBlock = source.match(
  /\.action-flow-branch-diagram\s*\{[\s\S]*?\n\}/
)?.[0]
assert(branchDiagramBlock, 'branch diagram layout should be defined')

assert(
  branchDiagramBlock.includes('grid-template-columns: 220px minmax(400px, 1fr)'),
  'branch diagram should place condition connectors and branch lanes in aligned columns'
)

const conditionalConnectorRowBlock = source.match(
  /\.action-flow-conditional-connector\s*\{[\s\S]*?\n\}/
)?.[0]
assert(
  conditionalConnectorRowBlock,
  'conditional connector row styles should be defined'
)

assert(
  conditionalConnectorRowBlock.includes('min-height: 86px'),
  'conditional connector rows should align with branch lane rows'
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
    source.includes('action-flow-branch-title'),
  'branch preview should separate branch title and nested steps into distinct blocks'
)

assert(
  !source.includes('action-flow-branch-condition-pill') &&
    !source.includes('<small>{{ branchConditionText(branch) }}</small>'),
  'branch condition should only appear on incoming connector labels'
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
  branchLaneBlock.includes('grid-template-columns: 112px minmax(0, 1fr)') &&
    branchLaneBlock.includes('border: 1px solid #dbe5f0') &&
    branchLaneBlock.includes('box-shadow: none') &&
    branchLaneBlock.includes('min-height: 86px'),
  'branch lanes should use horizontal flow rows with a light bordered treatment'
)

const branchLaneEntryBlock = source.match(
  /\.action-flow-branch-lane::before\s*\{[\s\S]*?\n\}/
)?.[0]
assert(branchLaneEntryBlock, 'branch lanes should expose an incoming port')

assert(
  branchLaneEntryBlock.includes('left: -12px') &&
    !branchLaneEntryBlock.includes('display: none'),
  'each incoming condition line should visually connect to its branch lane'
)

assert(
  source.includes('box-shadow: 0 2px 6px') &&
    !source.includes('box-shadow: 0 18px 36px'),
  'preview step cards should use a lighter shadow treatment'
)

console.log('action preview branch flow contract ok')
