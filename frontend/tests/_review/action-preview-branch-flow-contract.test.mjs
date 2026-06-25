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
  source.includes('previewCanvasRef') &&
    source.includes('action-flow-connection-layer') &&
    source.includes('action-flow-connection-labels') &&
    source.includes('data-flow-port') &&
    source.includes('getPreviewConnectionDescriptors') &&
    source.includes('getBoundingClientRect') &&
    source.includes('ResizeObserver'),
  'preview flow connections should use a global anchored SVG projection layer'
)

assert(
  !source.includes('previewConnectorCurve(') &&
    !source.includes('previewOutputConnectorCurve(') &&
    !source.includes('action-flow-conditional-curves') &&
    !source.includes('action-flow-branch-output-curves'),
  'preview should not use local fixed connector SVGs after switching to global anchoring'
)

assert(
  !source.includes('action-flow-conditional-fan'),
  'conditional branch connectors should not use overlapping fan lines'
)

const conditionalConnectorBlock = source.match(
  /\.action-flow-connection-layer\s*\{[\s\S]*?\n\}/
)?.[0]
assert(
  conditionalConnectorBlock,
  'global connection layer styles should be defined'
)

assert(
  conditionalConnectorBlock.includes('position: absolute') &&
    conditionalConnectorBlock.includes('pointer-events: none'),
  'global connection layer should sit over the canvas without intercepting input'
)

const branchDiagramBlock = source.match(
  /\.action-flow-branch-diagram\s*\{[\s\S]*?\n\}/
)?.[0]
assert(branchDiagramBlock, 'branch diagram layout should be defined')

assert(
  branchDiagramBlock.includes('position: relative') &&
    branchDiagramBlock.includes('display: block'),
  'branch diagram should anchor outside connectors around the central branch card'
)

const conditionalConnectorRowBlock = source.match(
  /\.action-flow-port\s*\{[\s\S]*?\n\}/
)?.[0]
assert(
  conditionalConnectorRowBlock,
  'hidden port anchor styles should be defined'
)

assert(
  conditionalConnectorRowBlock.includes('position: absolute') &&
    conditionalConnectorRowBlock.includes('pointer-events: none'),
  'port anchors should be absolutely positioned and non-interactive'
)

const conditionalLabelBlock = source.match(
  /\.action-flow-connection-label\s*\{[\s\S]*?\n\}/
)?.[0]
assert(conditionalLabelBlock, 'global connection label styles should be defined')

assert(
  conditionalLabelBlock.includes('font-family:') &&
    conditionalLabelBlock.includes('max-width: 172px') &&
    conditionalLabelBlock.includes('white-space: nowrap'),
  'conditional connector labels should read like compact rule tags on the line'
)

assert(
  source.includes('previewBranchCases(step)'),
  'conditional branch preview should iterate branch cases instead of flattening everything into one summary line'
)

assert(
  source.includes("!currentIsBranch && !nextIsBranch") &&
    source.includes("!currentIsBranch && nextIsBranch") &&
    source.includes("currentIsBranch && !nextIsBranch") &&
    source.includes('previewBranchCases(nextStep).forEach'),
  'connection topology should cover standard, split, merge, and branch cascade routes'
)

assert(
  source.includes('previewBranchNestedSteps(branch)'),
  'conditional branch preview should expose nested branch steps inside each lane'
)

assert(
  source.includes('action-flow-branch-condition') &&
    source.includes('action-flow-branch-step-list') &&
    source.includes('action-flow-branch-title') &&
    source.includes('action-flow-branch-rule-chip'),
  'branch preview should separate branch title, rule tag, and nested steps'
)

assert(
  !source.includes('action-flow-branch-condition-pill') &&
    !source.includes('<small>{{ branchConditionText(branch) }}</small>'),
  'branch condition should use the new rule chip instead of the old meta line'
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
  branchLaneBlock.includes('border: 1px solid #edf2f7') &&
    branchLaneBlock.includes('box-shadow: none') &&
    branchLaneBlock.includes('min-height: 96px'),
  'branch lanes should use airy rows with a light bordered treatment'
)

const branchLaneEntryBlock = source.match(
  /\.action-flow-port--branch-in\s*\{[\s\S]*?\n\}/
)?.[0]
assert(branchLaneEntryBlock, 'branch lanes should expose an incoming port')

assert(
  branchLaneEntryBlock.includes('left: 0') &&
    branchLaneEntryBlock.includes('transform: translate(-50%, -50%)'),
  'each incoming condition line should visually connect to its branch lane'
)

assert(
  source.includes('box-shadow: 0 2px 6px') &&
    !source.includes('box-shadow: 0 18px 36px'),
  'preview step cards should use a lighter shadow treatment'
)

assert(
  source.includes('previewStepIndex(index)') &&
    source.includes("padStart(2, '0')"),
  'preview nodes should render two-digit step badges like the design reference'
)

assert(
  source.includes('previewBranchConditionText(branch)') &&
    source.includes('operatorSymbols') &&
    source.includes('condition.value ||'),
  'preview branch conditions should use compact rule labels like branch_name = "centos9"'
)

console.log('action preview branch flow contract ok')
