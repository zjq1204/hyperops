# Action Conditional Branches Design

## Context

Action templates are currently linear. `ActionStep` records are ordered by
`order`, `create_action_run` snapshots every active step into `ActionStepRun`,
and `execute_action_run` executes each step in order. Template parameters are
stored in `ActionTemplate.parameter_schema` and runtime values are passed through
`ActionRun.input_params`; step configs already support `${param_name}` rendering.

The requested workflow needs a conditional branch in the middle of a linear
flow:

```text
Step 1: run A
Step 2: evaluate package_type
  - when package_type = b: run B, then D
  - when package_type = c: run C, then E
  - when nothing matches: skip this branch
Step 3: run F
```

The branch must rejoin the main flow after the selected branch path finishes.

## Goals

- Add a conditional branch step type that can be placed anywhere in an action
  template.
- Allow each branch case to evaluate global runtime parameters and contain one
  or more nested action steps.
- Execute only the first matching branch case, then continue with the next main
  template step.
- Support an explicit default behavior of skipping the branch when no condition
  matches.
- Preserve existing linear templates and historical run snapshots.
- Show enough run detail to tell which branch matched and which nested steps ran
  or were skipped.

## Non-Goals

- Arbitrary node-to-node graph editing.
- Parallel branch execution.
- Loops, retries, or branch jumps to unrelated main-flow steps.
- Boolean expression parsing beyond simple field/operator/value conditions.

## Data Model

Add `conditional_branch` to `ActionStep.TYPE_CHOICES`.

The conditional branch is stored in `ActionStep.config` as structured JSON:

```json
{
  "match_mode": "first",
  "default_behavior": "skip",
  "branches": [
    {
      "id": "branch-b",
      "label": "Package B",
      "condition": {
        "param": "package_type",
        "operator": "equals",
        "value": "b"
      },
      "steps": [
        {
          "name": "Run B",
          "action_type": "jenkins_trigger",
          "failure_policy": "stop",
          "config": {}
        },
        {
          "name": "Run D",
          "action_type": "jenkins_trigger",
          "failure_policy": "stop",
          "config": {}
        }
      ]
    }
  ]
}
```

Nested branch steps reuse the existing action step config shape, but they are
not saved as separate `ActionStep` rows. They are frozen as part of the parent
conditional step config when the main template step is snapshotted.

Supported condition operators for the first version:

- `equals`
- `not_equals`
- `contains`
- `is_empty`
- `is_not_empty`

All comparisons use the string form of the runtime parameter value. Empty means
missing, `null`, or an empty string after trimming.

## Execution Semantics

When `execute_action_run` reaches a `conditional_branch` step:

1. Render the branch config with `ActionRun.input_params`.
2. Evaluate branch cases in the order configured in `config.branches`.
3. Select the first branch whose condition matches.
4. If no branch matches and `default_behavior` is `skip`, mark the parent branch
   step as `skipped` with an output indicating that no branch matched.
5. If a branch matches, execute its nested steps sequentially using the same
   action executors used by top-level steps.
6. If a nested step pauses for manual approval, the parent conditional branch
   pauses the run. Approval resumes inside the selected branch, then continues
   to the next nested step.
7. If a nested step fails:
   - `failure_policy = stop` fails the parent conditional step and the run.
   - `failure_policy = continue` records the nested failure and continues to the
     next nested step.
8. After the selected branch finishes, mark the parent conditional step
   successful and continue with the next top-level step.

`execute_action_run` treats both `success` and `skipped` step-run statuses as
terminal states that allow the main flow to continue.

The parent `ActionStepRun.output` records branch execution detail:

```json
{
  "matched": true,
  "branch_id": "branch-b",
  "branch_label": "Package B",
  "nested_steps": [
    {
      "index": 1,
      "name": "Run B",
      "action_type": "jenkins_trigger",
      "status": "success",
      "output": {}
    }
  ]
}
```

For a skipped branch:

```json
{
  "matched": false,
  "reason": "no_condition_matched"
}
```

## Snapshot And Resume

Top-level run snapshotting remains unchanged: only active top-level
`ActionStep` rows are converted into `ActionStepRun` rows.

Nested branch progress is stored inside the parent `ActionStepRun.output` and
`ActionStepRun.resolved_config`. This keeps historical runs stable even if the
template is edited after the run starts. Manual approval inside a branch stores
the active nested step metadata in the parent step output so resume can continue
from the correct nested step.

## Frontend Editing

In `frontend/src/admin/pages/Actions/Templates.vue`:

- Add a new action category option, "Conditional Branch".
- The conditional branch editor shows ordered branch cases.
- Each case has:
  - branch label
  - parameter selector sourced from global parameters
  - operator selector
  - value input when the operator needs a value
  - nested step list
- Nested steps use the existing Jenkins, GitLab, and manual approval editors
  where practical, scoped inside the branch case.
- The overview canvas shows the branch as one top-level card, with compact
  nested previews such as:

```text
Conditional Branch
package_type = b -> B, D
package_type = c -> C, E
default -> skip
```

The first version keeps the current horizontal linear canvas. It does not
introduce free-form drag lines.

## Workspace Preview And Runs

Workspace template previews show branch cases and nested step names. Run detail
pages display the parent branch step with matched branch information from
`ActionStepRun.output`. Nested step output is shown under the parent branch
record instead of as separate top-level run rows.

## Validation

Backend serializer validation should reject:

- branch steps with no `branches` list;
- duplicate branch IDs within one conditional step;
- unsupported operators;
- conditions referencing a missing `param`;
- branch nested steps with unsupported action types;
- nested conditional branch steps in the first version.

The UI should prevent most invalid states, but backend validation remains the
source of truth.

## Testing

Backend pytest coverage:

- existing linear templates still execute unchanged;
- matching `package_type = b` runs B and D, skips C and E, then runs F;
- matching `package_type = c` runs C and E, skips B and D, then runs F;
- no match records the parent branch as skipped and still runs F;
- nested failure with `stop` fails the run;
- nested failure with `continue` continues the selected branch;
- nested manual approval pauses and resumes inside the branch;
- template edits after run creation do not alter the branch config used by the
  active run.

Frontend verification:

- `npm run build` after editing Vue and locale files.
- Focused component or node-runner tests if existing test patterns are available
  for the admin template editor.
