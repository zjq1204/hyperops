# Action Conditional Branches Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add conditional branch steps to action templates so one branch path runs based on global runtime parameters, then the flow rejoins the next top-level step.

**Architecture:** Keep top-level `ActionStep` rows linear and introduce `conditional_branch` as a container action type. Store nested branch steps inside the parent step `config`, execute the selected nested steps sequentially inside the parent `ActionStepRun`, and record branch detail in `output` for run inspection.

**Tech Stack:** Django 5, Django REST Framework serializers, pytest, Vue 3 `<script setup>`, Vite, existing action orchestration APIs.

---

### Task 1: Backend Conditional Branch Execution

**Files:**
- Modify: `backend/action_orchestration/models.py`
- Modify: `backend/action_orchestration/services.py`
- Test: `backend/action_orchestration/tests.py`

- [ ] **Step 1: Write failing backend execution tests**

Add tests that create a linear A -> conditional branch -> F flow. Use manual approval steps for branch path steps so the test can verify which nested names ran without external Jenkins/GitLab dependencies.

```python
@pytest.mark.django_db
def test_conditional_branch_runs_first_matching_nested_path(actions_user, admin_user):
    template = ActionTemplate.objects.create(
        name="Conditional Flow",
        scope=ActionTemplate.SCOPE_PERSONAL,
        owner=actions_user,
        is_active=True,
        parameter_schema=[{"name": "package_type", "label": "Package type"}],
    )
    first = ActionStep.objects.create(
        template=template,
        name="A",
        order=1,
        action_type=ActionStep.TYPE_MANUAL_APPROVAL,
        config={"approver_user_ids": [admin_user.id]},
    )
    branch = ActionStep.objects.create(
        template=template,
        name="Package branch",
        order=2,
        action_type=ActionStep.TYPE_CONDITIONAL_BRANCH,
        config={
            "branches": [
                {
                    "id": "branch-b",
                    "label": "Package B",
                    "condition": {
                        "param": "package_type",
                        "operator": "equals",
                        "value": "b",
                    },
                    "steps": [
                        {
                            "name": "B",
                            "action_type": ActionStep.TYPE_MANUAL_APPROVAL,
                            "failure_policy": ActionStep.FAILURE_STOP,
                            "config": {"approver_user_ids": [admin_user.id]},
                        },
                        {
                            "name": "D",
                            "action_type": ActionStep.TYPE_MANUAL_APPROVAL,
                            "failure_policy": ActionStep.FAILURE_STOP,
                            "config": {"approver_user_ids": [admin_user.id]},
                        },
                    ],
                },
                {
                    "id": "branch-c",
                    "label": "Package C",
                    "condition": {
                        "param": "package_type",
                        "operator": "equals",
                        "value": "c",
                    },
                    "steps": [
                        {
                            "name": "C",
                            "action_type": ActionStep.TYPE_MANUAL_APPROVAL,
                            "failure_policy": ActionStep.FAILURE_STOP,
                            "config": {"approver_user_ids": [admin_user.id]},
                        },
                        {
                            "name": "E",
                            "action_type": ActionStep.TYPE_MANUAL_APPROVAL,
                            "failure_policy": ActionStep.FAILURE_STOP,
                            "config": {"approver_user_ids": [admin_user.id]},
                        },
                    ],
                },
            ],
            "default_behavior": "skip",
        },
    )
    final = ActionStep.objects.create(
        template=template,
        name="F",
        order=3,
        action_type=ActionStep.TYPE_MANUAL_APPROVAL,
        config={"approver_user_ids": [admin_user.id]},
    )

    run = create_action_run(template, actions_user, {"package_type": "b"})

    execute_action_run(run.id)
    approve_action_run(ActionRun.objects.get(id=run.id), admin_user)
    execute_action_run(run.id)
    approve_action_run(ActionRun.objects.get(id=run.id), admin_user)
    execute_action_run(run.id)
    approve_action_run(ActionRun.objects.get(id=run.id), admin_user)
    execute_action_run(run.id)
    approve_action_run(ActionRun.objects.get(id=run.id), admin_user)
    execute_action_run(run.id)

    run.refresh_from_db()
    branch_run = run.step_runs.get(step=branch)
    assert run.status == ActionRun.STATUS_WAITING_APPROVAL
    assert run.current_step == final
    assert branch_run.status == ActionStepRun.STATUS_SUCCESS
    assert branch_run.output["branch_id"] == "branch-b"
    assert [item["name"] for item in branch_run.output["nested_steps"]] == ["B", "D"]
    assert all(item["status"] == ActionStepRun.STATUS_SUCCESS for item in branch_run.output["nested_steps"])
```

Also add a no-match test:

```python
@pytest.mark.django_db
def test_conditional_branch_skips_when_no_condition_matches(actions_user, admin_user):
    template = ActionTemplate.objects.create(
        name="Conditional Skip Flow",
        scope=ActionTemplate.SCOPE_PERSONAL,
        owner=actions_user,
        is_active=True,
    )
    branch = ActionStep.objects.create(
        template=template,
        name="Package branch",
        order=1,
        action_type=ActionStep.TYPE_CONDITIONAL_BRANCH,
        config={
            "branches": [
                {
                    "id": "branch-b",
                    "label": "Package B",
                    "condition": {
                        "param": "package_type",
                        "operator": "equals",
                        "value": "b",
                    },
                    "steps": [
                        {
                            "name": "B",
                            "action_type": ActionStep.TYPE_MANUAL_APPROVAL,
                            "failure_policy": ActionStep.FAILURE_STOP,
                            "config": {"approver_user_ids": [admin_user.id]},
                        }
                    ],
                }
            ],
            "default_behavior": "skip",
        },
    )
    final = ActionStep.objects.create(
        template=template,
        name="F",
        order=2,
        action_type=ActionStep.TYPE_MANUAL_APPROVAL,
        config={"approver_user_ids": [admin_user.id]},
    )

    run = create_action_run(template, actions_user, {"package_type": "other"})
    execute_action_run(run.id)

    run.refresh_from_db()
    branch_run = run.step_runs.get(step=branch)
    assert branch_run.status == ActionStepRun.STATUS_SKIPPED
    assert branch_run.output == {"matched": False, "reason": "no_condition_matched"}
    assert run.status == ActionRun.STATUS_WAITING_APPROVAL
    assert run.current_step == final
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
DJANGO_SETTINGS_MODULE=core.settings PYTHONPATH=backend /tmp/hyperops-venv/bin/python -m pytest backend/action_orchestration/tests.py -q
```

Expected: fail because `ActionStep.TYPE_CONDITIONAL_BRANCH` does not exist.

- [ ] **Step 3: Implement minimal backend execution**

Add `TYPE_CONDITIONAL_BRANCH = "conditional_branch"` to `ActionStep`. In `services.py`, add helpers to evaluate simple conditions, execute nested steps inside a parent `ActionStepRun`, persist nested progress in `output`, and treat `skipped` as a terminal continue status in `execute_action_run`.

- [ ] **Step 4: Run backend tests**

Run the same pytest command. Expected: all `backend/action_orchestration/tests.py` tests pass.

### Task 2: Backend Serializer Validation

**Files:**
- Modify: `backend/action_orchestration/serializers.py`
- Test: `backend/action_orchestration/tests.py`

- [ ] **Step 1: Write failing serializer validation tests**

Add tests using `APIClient` that PATCH/POST action templates with malformed conditional branch configs and assert HTTP 400 for missing branches, unsupported operators, nested conditional branch steps, and unknown parameter names.

- [ ] **Step 2: Run focused tests and verify failure**

Run:

```bash
DJANGO_SETTINGS_MODULE=core.settings PYTHONPATH=backend /tmp/hyperops-venv/bin/python -m pytest backend/action_orchestration/tests.py -q
```

Expected: validation tests fail because malformed configs currently save.

- [ ] **Step 3: Implement serializer validation**

Add `validate` methods on `ActionStepSerializer` and `ActionTemplateSerializer` to validate conditional branch config against `parameter_schema`, supported operators, branch IDs, and supported nested action types.

- [ ] **Step 4: Run backend tests**

Run the same pytest command. Expected: all action orchestration tests pass.

### Task 3: Frontend Template Editor Support

**Files:**
- Modify: `frontend/src/admin/pages/Actions/Templates.vue`
- Modify: `frontend/src/admin/locales/en.json`
- Modify: `frontend/src/admin/locales/zh-CN.json`
- Modify: `frontend/src/pages/Actions/Workspace.vue`

- [ ] **Step 1: Add conditional branch editing UI**

Extend `defaultConfig`, `normalizeStep`, `actionCategory`, `setActionCategory`, `actionTypeText`, `stepSummaryItems`, `previewStepSummary`, and `buildPayload` to support `conditional_branch`. Add editor controls for branch cases, conditions, and nested step names/configuration. Keep nested steps to the same action type editors where practical, starting with Jenkins, GitLab, and manual approval fields.

- [ ] **Step 2: Add locale strings**

Add English and Chinese strings for the conditional branch type, branch editor labels, operators, branch actions, default skip, and preview summaries.

- [ ] **Step 3: Add workspace preview support**

Show branch cases and nested step names in workspace run and preview modals.

- [ ] **Step 4: Build frontend**

Run:

```bash
npm run build
```

Expected: Vite build exits 0.

### Task 4: Final Verification

**Files:**
- All modified implementation and test files.

- [ ] **Step 1: Run backend focused tests**

Run:

```bash
DJANGO_SETTINGS_MODULE=core.settings PYTHONPATH=backend /tmp/hyperops-venv/bin/python -m pytest backend/action_orchestration/tests.py -q
```

Expected: all action orchestration tests pass.

- [ ] **Step 2: Run project-required backend subset if time allows**

Run:

```bash
DJANGO_SETTINGS_MODULE=core.settings PYTHONPATH=backend /tmp/hyperops-venv/bin/python -m pytest backend/accounts/tests backend/jenkins_trigger/tests.py backend/gitlab_resource/tests.py backend/action_orchestration/tests.py -q
```

Expected: all selected tests pass.

- [ ] **Step 3: Run frontend build**

Run from `frontend/`:

```bash
npm run build
```

Expected: build exits 0.

- [ ] **Step 4: Review diff**

Run:

```bash
git diff --stat
git diff --check
```

Expected: scoped changes, no whitespace errors.
