from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from rest_framework.test import APIClient

from accounts.models import Role
from action_orchestration.models import (
    ActionRun,
    ActionStep,
    ActionStepRun,
    ActionTemplate,
)
from action_orchestration.services import (
    approve_action_run,
    can_user_access_template,
    create_action_run,
    execute_action_run,
    render_template_value,
)
from gitlab_resource.models import (
    GitLabInstance,
    GitLabTag,
    GitLabWebhook,
    RegisteredGroup,
    RegisteredProject,
)
from jenkins_trigger.models import JenkinsInstance, TriggerEntry, TriggerRecord
from jenkins_trigger.services.jenkins_client import JenkinsBuildTriggerResult
from jenkins_trigger.services.jenkins_client import JenkinsParamDefinition

User = get_user_model()


@pytest.fixture
def actions_user(db):
    user = User.objects.create_user(
        username="actions-user",
        email="actions-user@example.com",
        password="password123",
    )
    role = Role.objects.create(
        name="Actions User",
        visible_features=["workspace_actions"],
        preferred_platform="workspace",
    )
    user.platform_roles.add(role)
    return user


@pytest.fixture
def admin_user(db):
    return User.objects.create_user(
        username="actions-admin",
        email="actions-admin@example.com",
        password="password123",
        is_staff=True,
    )


@pytest.mark.django_db
def test_admin_template_visibility_supports_user_and_group(actions_user):
    group = Group.objects.create(name="Release Team")
    grouped_user = User.objects.create_user(username="grouped-user")
    grouped_user.groups.add(group)
    hidden_user = User.objects.create_user(username="hidden-user")
    template = ActionTemplate.objects.create(
        name="Release",
        scope=ActionTemplate.SCOPE_ADMIN,
        is_active=True,
    )
    template.visible_users.add(actions_user)
    template.visible_groups.add(group)

    assert can_user_access_template(actions_user, template) is True
    assert can_user_access_template(grouped_user, template) is True
    assert can_user_access_template(hidden_user, template) is False


@pytest.mark.django_db
def test_render_template_value_replaces_global_params():
    payload = {
        "branch": "${branch_name}",
        "nested": ["release-${version}", {"ref": "${source_ref}"}],
    }

    assert render_template_value(
        payload,
        {
            "branch_name": "release/2026.06",
            "version": "2026.06",
            "source_ref": "main",
        },
    ) == {
        "branch": "release/2026.06",
        "nested": ["release-2026.06", {"ref": "main"}],
    }


@pytest.mark.django_db
def test_manual_approval_step_pauses_run(actions_user, admin_user):
    template = ActionTemplate.objects.create(
        name="Approval Flow",
        scope=ActionTemplate.SCOPE_PERSONAL,
        owner=actions_user,
        is_active=True,
    )
    step = ActionStep.objects.create(
        template=template,
        name="Approve release",
        order=1,
        action_type=ActionStep.TYPE_MANUAL_APPROVAL,
        config={"approver_user_ids": [admin_user.id]},
    )
    run = ActionRun.objects.create(
        template=template,
        triggered_by=actions_user,
        input_params={},
    )

    execute_action_run(run.id)

    run.refresh_from_db()
    step_run = run.step_runs.get(step=step)
    assert run.status == ActionRun.STATUS_WAITING_APPROVAL
    assert run.current_step == step
    assert step_run.status == "waiting_approval"


@pytest.mark.django_db
def test_manual_approval_queues_run_without_inline_resume(actions_user, admin_user):
    template = ActionTemplate.objects.create(
        name="Approval Flow",
        scope=ActionTemplate.SCOPE_PERSONAL,
        owner=actions_user,
        is_active=True,
    )
    step = ActionStep.objects.create(
        template=template,
        name="Approve release",
        order=1,
        action_type=ActionStep.TYPE_MANUAL_APPROVAL,
        config={"approver_user_ids": [admin_user.id]},
    )
    run = ActionRun.objects.create(
        template=template,
        triggered_by=actions_user,
        input_params={},
    )

    execute_action_run(run.id)
    run.refresh_from_db()
    approve_action_run(run, admin_user, "go")

    run.refresh_from_db()
    step_run = run.step_runs.get(step=step)
    assert run.status == ActionRun.STATUS_QUEUED
    assert step_run.status == "success"
    assert step_run.approved_by == admin_user


@pytest.mark.django_db
def test_gitlab_branch_create_step_records_partial_result(actions_user):
    instance = GitLabInstance.objects.create(
        name="GitLab",
        url="https://gitlab.example.com",
        private_token="token",
        is_active=True,
    )
    group = RegisteredGroup.objects.create(
        instance=instance,
        gitlab_id=1,
        name="Core",
        path="core",
    )
    project = RegisteredProject.objects.create(
        instance=instance,
        group=group,
        gitlab_id=100,
        name="API",
        path="core/api",
    )
    template = ActionTemplate.objects.create(
        name="Branch Flow",
        scope=ActionTemplate.SCOPE_PERSONAL,
        owner=actions_user,
        is_active=True,
    )
    ActionStep.objects.create(
        template=template,
        name="Create branch",
        order=1,
        action_type=ActionStep.TYPE_GITLAB_BRANCH_CREATE,
        config={
            "project_ids": [project.id],
            "branch_name": "${branch_name}",
            "ref": "main",
        },
    )
    run = ActionRun.objects.create(
        template=template,
        triggered_by=actions_user,
        input_params={"branch_name": "release/test"},
    )

    with patch("action_orchestration.services.get_gitlab_client") as get_client:
        mock_client = get_client.return_value
        mock_client.create_branch.return_value.name = "release/test"
        mock_client.create_branch.return_value.protected = False
        mock_client.create_branch.return_value.commit_sha = "abc123"
        mock_client.create_branch.return_value.commit_date = None
        execute_action_run(run.id)

    run.refresh_from_db()
    assert run.status == ActionRun.STATUS_SUCCESS
    assert run.step_runs.first().output["success_count"] == 1


@pytest.mark.django_db
def test_gitlab_branch_operation_step_can_protect_and_unprotect(actions_user):
    instance = GitLabInstance.objects.create(
        name="GitLab",
        url="https://gitlab.example.com",
        private_token="token",
        is_active=True,
    )
    group = RegisteredGroup.objects.create(
        instance=instance,
        gitlab_id=1,
        name="Core",
        path="core",
    )
    project = RegisteredProject.objects.create(
        instance=instance,
        group=group,
        gitlab_id=100,
        name="API",
        path="core/api",
    )
    template = ActionTemplate.objects.create(
        name="Protect Flow",
        scope=ActionTemplate.SCOPE_PERSONAL,
        owner=actions_user,
        is_active=True,
    )
    ActionStep.objects.create(
        template=template,
        name="Protect branch",
        order=1,
        action_type=ActionStep.TYPE_GITLAB_BRANCH_OPERATION,
        config={
            "operation": "protect",
            "project_ids": [project.id],
            "branch_name": "${branch_name}",
        },
    )
    ActionStep.objects.create(
        template=template,
        name="Unprotect branch",
        order=2,
        action_type=ActionStep.TYPE_GITLAB_BRANCH_OPERATION,
        config={
            "operation": "unprotect",
            "project_ids": [project.id],
            "branch_name": "${branch_name}",
        },
    )
    run = ActionRun.objects.create(
        template=template,
        triggered_by=actions_user,
        input_params={"branch_name": "release/test"},
    )

    with patch("action_orchestration.services.get_gitlab_client") as get_client:
        execute_action_run(run.id)

    mock_client = get_client.return_value
    mock_client.protect_branch.assert_called_once_with(project.gitlab_id, "release/test")
    mock_client.unprotect_branch.assert_called_once_with(project.gitlab_id, "release/test")
    run.refresh_from_db()
    assert run.status == ActionRun.STATUS_SUCCESS
    assert [step_run.output["success_count"] for step_run in run.step_runs.order_by("step__order")] == [1, 1]


@pytest.mark.django_db
def test_gitlab_tag_operation_step_creates_tag(actions_user):
    instance = GitLabInstance.objects.create(
        name="GitLab",
        url="https://gitlab.example.com",
        private_token="token",
        is_active=True,
    )
    group = RegisteredGroup.objects.create(
        instance=instance,
        gitlab_id=1,
        name="Core",
        path="core",
    )
    project = RegisteredProject.objects.create(
        instance=instance,
        group=group,
        gitlab_id=100,
        name="API",
        path="core/api",
    )
    template = ActionTemplate.objects.create(
        name="Tag Flow",
        scope=ActionTemplate.SCOPE_PERSONAL,
        owner=actions_user,
        is_active=True,
    )
    ActionStep.objects.create(
        template=template,
        name="Create tag",
        order=1,
        action_type=ActionStep.TYPE_GITLAB_TAG_OPERATION,
        config={
            "operation": "create",
            "project_ids": [project.id],
            "tag_name": "v${version}",
            "ref": "${source_ref}",
        },
    )
    run = ActionRun.objects.create(
        template=template,
        triggered_by=actions_user,
        input_params={"version": "1.0.0", "source_ref": "main"},
    )

    with patch("action_orchestration.services.get_gitlab_client") as get_client:
        mock_client = get_client.return_value
        mock_client.create_tag.return_value.name = "v1.0.0"
        mock_client.create_tag.return_value.commit_sha = "abc123"
        mock_client.create_tag.return_value.released_at = None
        execute_action_run(run.id)

    run.refresh_from_db()
    assert run.status == ActionRun.STATUS_SUCCESS
    assert GitLabTag.objects.filter(project=project, name="v1.0.0").exists()
    assert run.step_runs.first().output["success_count"] == 1


@pytest.mark.django_db
def test_gitlab_webhook_operation_step_creates_webhook(actions_user):
    instance = GitLabInstance.objects.create(
        name="GitLab",
        url="https://gitlab.example.com",
        private_token="token",
        is_active=True,
    )
    group = RegisteredGroup.objects.create(
        instance=instance,
        gitlab_id=1,
        name="Core",
        path="core",
    )
    project = RegisteredProject.objects.create(
        instance=instance,
        group=group,
        gitlab_id=100,
        name="API",
        path="core/api",
    )
    template = ActionTemplate.objects.create(
        name="Webhook Flow",
        scope=ActionTemplate.SCOPE_PERSONAL,
        owner=actions_user,
        is_active=True,
    )
    ActionStep.objects.create(
        template=template,
        name="Create webhook",
        order=1,
        action_type=ActionStep.TYPE_GITLAB_WEBHOOK_OPERATION,
        config={
            "operation": "create",
            "project_ids": [project.id],
            "url": "https://hooks.example.com/${channel}",
            "push_events": True,
            "tag_push_events": True,
            "merge_requests_events": False,
            "enable_ssl_verification": False,
            "push_events_branch_filter": "${branch_name}",
        },
    )
    run = ActionRun.objects.create(
        template=template,
        triggered_by=actions_user,
        input_params={"channel": "release", "branch_name": "main"},
    )

    with patch("action_orchestration.services.get_gitlab_client") as get_client:
        mock_client = get_client.return_value
        mock_client.create_webhook.return_value.id = 901
        mock_client.create_webhook.return_value.url = "https://hooks.example.com/release"
        mock_client.create_webhook.return_value.push_events = True
        mock_client.create_webhook.return_value.tag_push_events = True
        mock_client.create_webhook.return_value.merge_requests_events = False
        mock_client.create_webhook.return_value.enable_ssl_verification = False
        mock_client.create_webhook.return_value.push_events_branch_filter = "main"
        execute_action_run(run.id)

    run.refresh_from_db()
    assert run.status == ActionRun.STATUS_SUCCESS
    assert GitLabWebhook.objects.filter(
        project=project,
        webhook_id=901,
        url="https://hooks.example.com/release",
    ).exists()
    assert run.step_runs.first().output["success_count"] == 1


@pytest.mark.django_db
def test_jenkins_trigger_step_creates_trigger_record(actions_user):
    instance = JenkinsInstance.objects.create(
        name="Jenkins",
        url="https://jenkins.example.com",
        username="admin",
        token="token",
        is_active=True,
    )
    entry = TriggerEntry.objects.create(
        instance=instance,
        name="Build API",
        job_name="build-api",
        params_config={"BRANCH": {"mode": "editable", "default_value": ""}},
        is_active=True,
    )
    template = ActionTemplate.objects.create(
        name="Build Flow",
        scope=ActionTemplate.SCOPE_PERSONAL,
        owner=actions_user,
        is_active=True,
    )
    ActionStep.objects.create(
        template=template,
        name="Build",
        order=1,
        action_type=ActionStep.TYPE_JENKINS_TRIGGER,
        config={
            "entry_id": entry.id,
            "params": {"BRANCH": "${branch_name}"},
            "wait_for_completion": False,
        },
    )
    run = ActionRun.objects.create(
        template=template,
        triggered_by=actions_user,
        input_params={"branch_name": "main"},
    )

    with patch("action_orchestration.services.get_jenkins_client") as get_client:
        mock_client = get_client.return_value
        mock_client.get_job_params.return_value = [
            JenkinsParamDefinition(name="BRANCH", type="StringParameterDefinition")
        ]
        mock_client.trigger_build.return_value = JenkinsBuildTriggerResult(
            build_number=12,
            queue_url="https://jenkins.example.com/queue/item/1/",
        )
        execute_action_run(run.id)

    record = TriggerRecord.objects.get()
    run.refresh_from_db()
    assert record.params == {"BRANCH": "main"}
    assert run.step_runs.first().jenkins_record == record
    assert run.status == ActionRun.STATUS_SUCCESS


@pytest.mark.django_db
def test_jenkins_wait_step_uses_shared_record_refresh(actions_user):
    instance = JenkinsInstance.objects.create(
        name="Jenkins",
        url="https://jenkins.example.com",
        username="admin",
        token="token",
        is_active=True,
    )
    entry = TriggerEntry.objects.create(
        instance=instance,
        name="Build API",
        job_name="build-api",
        params_config={},
        is_active=True,
    )
    template = ActionTemplate.objects.create(
        name="Wait Flow",
        scope=ActionTemplate.SCOPE_PERSONAL,
        owner=actions_user,
        is_active=True,
    )
    ActionStep.objects.create(
        template=template,
        name="Build",
        order=1,
        action_type=ActionStep.TYPE_JENKINS_TRIGGER,
        config={
            "entry_id": entry.id,
            "params": {},
            "wait_for_completion": True,
            "poll_interval_seconds": 0,
        },
    )
    run = create_action_run(template, actions_user, {})

    with (
        patch("action_orchestration.services.get_jenkins_client") as get_client,
        patch("action_orchestration.services.refresh_trigger_record_status") as refresh_status,
    ):
        mock_client = get_client.return_value
        mock_client.get_job_params.return_value = []
        mock_client.trigger_build.return_value = JenkinsBuildTriggerResult(
            queue_url="https://jenkins.example.com/queue/item/1/",
        )

        def mark_success(record):
            record.status = "success"
            record.build_number = 12
            record.save(update_fields=["status", "build_number"])
            return record

        refresh_status.side_effect = mark_success
        execute_action_run(run.id)

    run.refresh_from_db()
    step_run = run.step_runs.get()
    assert run.status == ActionRun.STATUS_SUCCESS
    assert step_run.status == ActionStepRun.STATUS_SUCCESS
    assert step_run.output["status"] == "success"
    refresh_status.assert_called()


@pytest.mark.django_db
def test_workspace_templates_api_only_returns_accessible_templates(actions_user):
    visible = ActionTemplate.objects.create(
        name="Visible",
        scope=ActionTemplate.SCOPE_ADMIN,
        is_active=True,
    )
    hidden = ActionTemplate.objects.create(
        name="Hidden",
        scope=ActionTemplate.SCOPE_ADMIN,
        is_active=True,
    )
    visible.visible_users.add(actions_user)

    client = APIClient()
    client.force_authenticate(user=actions_user)

    response = client.get("/api/v1/actions/workspace/templates/")

    assert response.status_code == 200
    names = {item["name"] for item in response.data}
    assert names == {visible.name}
    assert hidden.name not in names


@pytest.mark.django_db
def test_action_run_create_api_queues_accessible_template(actions_user):
    template = ActionTemplate.objects.create(
        name="Runnable",
        scope=ActionTemplate.SCOPE_PERSONAL,
        owner=actions_user,
        is_active=True,
    )
    client = APIClient()
    client.force_authenticate(user=actions_user)

    with patch("action_orchestration.views.execute_action_run_task.delay") as delay:
        response = client.post(
            "/api/v1/actions/runs/",
            {"template": template.id, "input_params": {"branch": "main"}},
            format="json",
        )

    assert response.status_code == 201
    run = ActionRun.objects.get()
    assert run.template == template
    assert run.input_params == {"branch": "main"}
    delay.assert_called_once_with(run.id)


@pytest.mark.django_db
def test_action_run_resumes_from_snapshot_after_template_edit(actions_user, admin_user):
    template = ActionTemplate.objects.create(
        name="Snapshot Flow",
        scope=ActionTemplate.SCOPE_PERSONAL,
        owner=actions_user,
        is_active=True,
    )
    approval_step = ActionStep.objects.create(
        template=template,
        name="Approve original",
        order=1,
        action_type=ActionStep.TYPE_MANUAL_APPROVAL,
        config={"approver_user_ids": [admin_user.id]},
    )
    run = create_action_run(template, actions_user, {})
    assert list(run.step_runs.values_list("step_id", flat=True)) == [approval_step.id]

    execute_action_run(run.id)
    run.refresh_from_db()
    assert run.status == ActionRun.STATUS_WAITING_APPROVAL
    assert run.current_step == approval_step

    approval_step.is_archived = True
    approval_step.save(update_fields=["is_archived"])
    ActionStep.objects.create(
        template=template,
        name="New Jenkins should not run",
        order=1,
        action_type=ActionStep.TYPE_JENKINS_TRIGGER,
        config={"entry_id": 999, "wait_for_completion": True},
    )

    run = approve_action_run(run, admin_user)
    execute_action_run(run.id)

    run.refresh_from_db()
    assert run.status == ActionRun.STATUS_SUCCESS
    assert run.step_runs.count() == 1
    assert run.step_runs.get().step == approval_step


@pytest.mark.django_db
def test_admin_template_update_archives_referenced_steps(admin_user):
    template = ActionTemplate.objects.create(
        name="Editable",
        scope=ActionTemplate.SCOPE_ADMIN,
        is_active=True,
    )
    first_step = ActionStep.objects.create(
        template=template,
        name="Old Jenkins",
        order=1,
        action_type=ActionStep.TYPE_JENKINS_TRIGGER,
        config={"entry_id": 1, "params": {}},
    )
    second_step = ActionStep.objects.create(
        template=template,
        name="Old approval",
        order=2,
        action_type=ActionStep.TYPE_MANUAL_APPROVAL,
        config={},
    )
    run = ActionRun.objects.create(template=template, triggered_by=admin_user)
    ActionStepRun.objects.create(run=run, step=first_step, status="success")
    ActionStepRun.objects.create(run=run, step=second_step, status="waiting_approval")

    client = APIClient()
    client.force_authenticate(user=admin_user)
    response = client.patch(
        f"/api/v1/actions/templates/{template.id}/",
        {
            "name": "Editable",
            "description": "",
            "scope": ActionTemplate.SCOPE_ADMIN,
            "is_active": True,
            "parameter_schema": [],
            "visible_user_ids": [],
            "visible_group_ids": [],
            "steps": [
                {
                    "id": first_step.id,
                    "name": "New Jenkins",
                    "order": 1,
                    "action_type": ActionStep.TYPE_JENKINS_TRIGGER,
                    "failure_policy": ActionStep.FAILURE_STOP,
                    "config": {"entry_id": 2, "params": {"BRANCH": "main"}},
                },
                {
                    "id": second_step.id,
                    "name": "New approval",
                    "order": 2,
                    "action_type": ActionStep.TYPE_MANUAL_APPROVAL,
                    "failure_policy": ActionStep.FAILURE_STOP,
                    "config": {},
                },
            ],
        },
        format="json",
    )

    assert response.status_code == 200
    assert template.steps.filter(is_archived=True).count() == 2
    active_steps = list(template.steps.filter(is_archived=False).order_by("order"))
    assert [step.name for step in active_steps] == ["New Jenkins", "New approval"]
    assert run.step_runs.filter(step=first_step).exists()
