from pathlib import Path
import sys
from unittest.mock import Mock, patch

import json
import pytest
import requests
from django.contrib.auth.models import Group
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from accounts.models import Role
from gitlab_resource.models import GitLabInstance
from jenkins_trigger.models import JenkinsInstance, TriggerRecord
from jenkins_trigger.services.jenkins_client import (
    JenkinsBuildResult,
    JenkinsBuildTriggerResult,
    JenkinsClient,
    JenkinsJobNode,
    JenkinsParamDefinition,
    JenkinsQueueItem,
)
from jenkins_trigger.views import build_job_catalog_cache_key
from jenkins_trigger.views import apply_build_result_to_record
from jenkins_trigger.notification_service import build_notification_result


User = get_user_model()

TEST_CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "jenkins-trigger-tests",
    }
}


@pytest.mark.django_db
def test_build_notification_result_uses_entry_level_channel_preferences():
    group_a = Group.objects.create(name="dev-a")
    group_b = Group.objects.create(name="dev-b")
    group_a.jenkins_notification_config.notification_emails = ["dev-a@example.com"]
    group_a.jenkins_notification_config.notification_webhooks = ["https://hooks.example.com/dev-a"]
    group_a.jenkins_notification_config.save()
    group_b.jenkins_notification_config.notification_emails = ["dev-b@example.com"]
    group_b.jenkins_notification_config.notification_webhooks = ["https://hooks.example.com/dev-b"]
    group_b.jenkins_notification_config.save()

    user = User.objects.create_user(
        username="alice",
        email="alice@example.com",
        password="secret123",
    )
    user.groups.set([group_a, group_b])
    profile = user.profile
    profile.jenkins_notification_emails = ["alice-ci@example.com", "dev-a@example.com"]
    profile.jenkins_notification_webhooks = ["https://hooks.example.com/alice", "https://hooks.example.com/dev-b"]
    profile.save()
    instance = JenkinsInstance.objects.create(
        name="jenkins",
        url="http://jenkins.example.com",
        username="api",
        token="token",
    )
    entry = instance.trigger_entries.create(
        name="Build API",
        job_name="build-api",
        params_config={},
        is_active=True,
    )
    entry.user_notification_preferences.create(
        user=user,
        notify_personal_email=True,
        notify_group_email=True,
        notify_personal_webhook=False,
        notify_group_webhook=True,
    )

    result = build_notification_result(user, entry, "2026-05-28T06:00:00Z")

    assert result["source"] == "entry_channels"
    assert result["emails"] == [
        "alice@example.com",
        "alice-ci@example.com",
        "dev-a@example.com",
        "dev-b@example.com",
    ]
    assert result["webhooks"] == [
        "https://hooks.example.com/dev-a",
        "https://hooks.example.com/dev-b",
    ]
    assert result["selected_channels"] == [
        "personal_email",
        "group_email",
        "group_webhook",
    ]


@pytest.mark.django_db
def test_build_notification_result_skips_when_entry_has_no_notification_preference():
    group = Group.objects.create(name="ops")
    group.jenkins_notification_config.notification_emails = ["ops@example.com"]
    group.jenkins_notification_config.notification_webhooks = ["https://hooks.example.com/ops"]
    group.jenkins_notification_config.save()

    user = User.objects.create_user(
        username="bob",
        email="bob@example.com",
        password="secret123",
    )
    user.groups.add(group)
    instance = JenkinsInstance.objects.create(
        name="jenkins-ops",
        url="http://jenkins.example.com",
        username="api",
        token="token",
    )
    entry = instance.trigger_entries.create(
        name="Deploy",
        job_name="deploy",
        params_config={},
        is_active=True,
    )

    result = build_notification_result(user, entry, "2026-05-28T06:00:00Z")

    assert result["source"] == "none"
    assert result["email_status"] == "skipped"
    assert result["webhook_status"] == "skipped"
    assert result["emails"] == []
    assert result["webhooks"] == []


@pytest.mark.django_db
def test_refresh_status_writes_notification_result_when_build_finishes():
    role = Role.objects.create(
        name="Workspace",
        visible_features=["workspace"],
    )
    user = User.objects.create_user(
        username="carol",
        email="carol@example.com",
        password="secret123",
    )
    user.platform_roles.add(role)
    profile = user.profile
    profile.jenkins_notification_emails = ["carol-builds@example.com"]
    profile.jenkins_notification_webhooks = ["https://hooks.example.com/carol"]
    profile.save()

    instance = JenkinsInstance.objects.create(
        name="jenkins",
        url="http://jenkins.example.com",
        username="api",
        token="token",
    )
    entry = instance.trigger_entries.create(
        name="Build API",
        job_name="build-api",
        params_config={},
        is_active=True,
    )
    entry.user_notification_preferences.create(
        user=user,
        notify_personal_email=True,
        notify_personal_webhook=True,
        notify_group_email=False,
        notify_group_webhook=False,
    )
    record = TriggerRecord.objects.create(
        entry=entry,
        user=user,
        params={"BRANCH": "main"},
        status="running",
        build_number=17,
    )

    api_client = APIClient()
    api_client.force_authenticate(user=user)

    result = JenkinsBuildResult(
        build_number=17,
        result="SUCCESS",
        timestamp=int(timezone.now().timestamp() * 1000),
        duration=120000,
        artifacts=[{"relativePath": "dist/app.tar.gz", "fileName": "app.tar.gz"}],
    )

    with patch("jenkins_trigger.views.get_jenkins_client") as mocked_client, patch(
        "jenkins_trigger.views.deliver_build_notifications"
    ) as deliver_mock:
        mocked_client.return_value.get_build_result.return_value = result
        response = api_client.post(f"/api/v1/jenkins/records/{record.id}/refresh_status/")

    assert response.status_code == 200
    payload = response.json().get("data") or response.json()
    assert payload["status"] == "success"
    assert payload["notification_result"]["source"] == "entry_channels"
    assert payload["notification_result"]["emails"] == [
        "carol@example.com",
        "carol-builds@example.com",
    ]
    assert payload["notification_result"]["selected_channels"] == [
        "personal_email",
        "personal_webhook",
    ]
    assert payload["notification_result"]["summary"].startswith("入口通知")
    deliver_mock.assert_called_once()


class FakeResponse:
    def __init__(self, payload, status_code=200, reason="OK", headers=None):
        self._payload = payload
        self.status_code = status_code
        self.reason = reason
        self.ok = 200 <= status_code < 400
        self.text = ""
        self.headers = headers or {}

    def json(self):
        return self._payload

    def raise_for_status(self):
        if not self.ok:
            response = requests.Response()
            response.status_code = self.status_code
            raise requests.HTTPError(
                f"HTTP {self.status_code} {self.reason}",
                response=response,
            )


def test_build_job_paths_support_nested_folders():
    client = JenkinsClient("http://jenkins.example.com", "user", "token")

    assert client._build_job_api_url() == "http://jenkins.example.com/api/json"
    assert (
        client._build_job_api_url("folder-a/build-app")
        == "http://jenkins.example.com/job/folder-a/job/build-app/api/json"
    )
    assert (
        client._build_job_path("folder-a/build-app", "buildWithParameters")
        == "http://jenkins.example.com/job/folder-a/job/build-app/buildWithParameters"
    )


def test_list_jobs_recursively_expands_folders():
    client = JenkinsClient("http://jenkins.example.com", "user", "token")

    root_payload = {
        "jobs": [
            {
                "fullName": "folder-a",
                "displayName": "Folder A",
                "name": "folder-a",
                "url": "http://jenkins.example.com/job/folder-a/",
                "_class": "com.cloudbees.hudson.plugins.folder.Folder",
            },
            {
                "fullName": "freestyle",
                "displayName": "Freestyle",
                "name": "freestyle",
                "url": "http://jenkins.example.com/job/freestyle/",
                "_class": "hudson.model.FreeStyleProject",
            },
        ]
    }
    folder_payload = {
        "jobs": [
            {
                "fullName": "folder-a/nested-job",
                "displayName": "Nested Job",
                "name": "nested-job",
                "url": "http://jenkins.example.com/job/folder-a/job/nested-job/",
                "_class": "hudson.model.FreeStyleProject",
            }
        ]
    }

    client.session.get = Mock(
        side_effect=[
            FakeResponse(root_payload),
            FakeResponse(folder_payload),
        ]
    )

    jobs = client.list_jobs()

    assert [job.full_name for job in jobs] == ["folder-a", "freestyle"]
    assert jobs[0].has_children is True
    assert jobs[0].type == "folder"
    assert jobs[0].children[0].full_name == "folder-a/nested-job"
    assert jobs[1].has_children is False
    assert jobs[1].type == "job"
    assert jobs[1].buildable is None
    assert jobs[1].color == ""


def test_list_jobs_captures_buildable_and_color():
    client = JenkinsClient("http://jenkins.example.com", "user", "token")

    root_payload = {
        "jobs": [
            {
                "fullName": "enabled-job",
                "displayName": "Enabled Job",
                "name": "enabled-job",
                "url": "http://jenkins.example.com/job/enabled-job/",
                "_class": "hudson.model.FreeStyleProject",
                "buildable": True,
                "color": "blue",
            },
            {
                "fullName": "disabled-job",
                "displayName": "Disabled Job",
                "name": "disabled-job",
                "url": "http://jenkins.example.com/job/disabled-job/",
                "_class": "hudson.model.FreeStyleProject",
                "buildable": False,
                "color": "disabled",
            },
        ]
    }

    client.session.get = Mock(return_value=FakeResponse(root_payload))

    jobs = client.list_jobs()

    assert jobs[0].buildable is True
    assert jobs[0].color == "blue"
    assert jobs[1].buildable is False
    assert jobs[1].color == "disabled"


def test_get_last_successful_build_params_returns_parameters():
    client = JenkinsClient("http://jenkins.example.com", "user", "token")
    payload = {
        "lastSuccessfulBuild": {
            "number": 17,
            "actions": [
                {"_class": "hudson.model.ParametersAction", "parameters": [
                    {"name": "BRANCH", "value": "release/1.0"},
                    {"name": "ENV", "value": "prod"},
                ]},
                {"_class": "hudson.model.CauseAction"},
            ],
        }
    }

    client.session.get = Mock(return_value=FakeResponse(payload))

    params = client.get_last_successful_build_params("build-app")

    assert params == {"BRANCH": "release/1.0", "ENV": "prod"}


def test_get_last_successful_build_params_returns_empty_when_missing():
    client = JenkinsClient("http://jenkins.example.com", "user", "token")
    client.session.get = Mock(return_value=FakeResponse({"lastSuccessfulBuild": None}))

    params = client.get_last_successful_build_params("build-app")

    assert params == {}


def test_trigger_build_returns_queue_url_from_location_header():
    client = JenkinsClient("http://jenkins.example.com", "user", "token")
    client._get_crumb = Mock(return_value="crumb-value")
    client.session.post = Mock(
        return_value=FakeResponse(
            {},
            status_code=201,
            headers={"Location": "http://jenkins.example.com/queue/item/38508/"},
        )
    )

    result = client.trigger_build("folder-a/build-app", {"BRANCH": "main"})

    _, kwargs = client.session.post.call_args
    assert kwargs["allow_redirects"] is False
    assert result.queue_url == "http://jenkins.example.com/queue/item/38508/"
    assert result.queue_id == 38508
    assert result.build_number is None


def test_trigger_build_accepts_200_response_without_treating_it_as_failure():
    client = JenkinsClient("http://jenkins.example.com", "user", "token")
    client._get_crumb = Mock(return_value="crumb-value")
    client.session.post = Mock(
        return_value=FakeResponse(
            {},
            status_code=200,
            headers={"Location": "http://jenkins.example.com/queue/item/38509/"},
        )
    )

    result = client.trigger_build("folder-a/build-app", {"BRANCH": "main"})

    assert result.queue_url == "http://jenkins.example.com/queue/item/38509/"
    assert result.queue_id == 38509
    assert result.build_number is None


def test_trigger_build_accepts_302_redirect_with_queue_location():
    client = JenkinsClient("http://jenkins.example.com", "user", "token")
    client._get_crumb = Mock(return_value="crumb-value")
    client.session.post = Mock(
        return_value=FakeResponse(
            {},
            status_code=302,
            headers={"Location": "http://jenkins.example.com/queue/item/38510/"},
        )
    )

    result = client.trigger_build("folder-a/build-app", {"BRANCH": "main"})

    assert result.queue_url == "http://jenkins.example.com/queue/item/38510/"
    assert result.queue_id == 38510
    assert result.build_number is None


def test_trigger_build_raises_when_success_response_has_no_location():
    client = JenkinsClient("http://jenkins.example.com", "user", "token")
    client._get_crumb = Mock(return_value="crumb-value")
    client.session.post = Mock(
        return_value=FakeResponse(
            {},
            status_code=200,
        )
    )

    with pytest.raises(Exception, match="did not provide queue/build location"):
        client.trigger_build("folder-a/build-app", {"BRANCH": "main"})


def test_get_queue_item_extracts_executable_build_number():
    client = JenkinsClient("http://jenkins.example.com", "user", "token")
    client.session.get = Mock(
        return_value=FakeResponse(
            {
                "id": 38508,
                "cancelled": False,
                "why": None,
                "executable": {
                    "number": 42,
                    "url": "http://jenkins.example.com/job/build-app/42/",
                },
            }
        )
    )

    queue_item = client.get_queue_item("http://jenkins.example.com/queue/item/38508/")

    assert queue_item.queue_id == 38508
    assert queue_item.executable_number == 42
    assert queue_item.cancelled is False


@pytest.fixture
def authenticated_client():
    user = User.objects.create_user(
        username="jenkins-admin",
        email="jenkins-admin@example.com",
        password="testpass123",
    )
    # Admin user has full visibility into both admin_console and workspace
    # platforms so admin-only assertions (e.g. listing all records) keep
    # working after we tightened the per-view feature gates.
    role = Role.objects.create(
        name="Jenkins Admin",
        visible_features=[
            "admin_console",
            "workspace_jenkins",
            "admin_jenkins",
        ],
        preferred_platform="admin_console",
    )
    user.platform_roles.add(role)
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def workspace_client():
    user = User.objects.create_user(
        username="jenkins-workspace",
        email="jenkins-workspace@example.com",
        password="testpass123",
    )
    role = Role.objects.create(
        name="Workspace Access",
        visible_features=["workspace"],
    )
    user.platform_roles.add(role)
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def gitlab_admin_client():
    user = User.objects.create_user(
        username="gitlab-only-admin",
        email="gitlab-only-admin@example.com",
        password="testpass123",
    )
    role = Role.objects.create(
        name="GitLab Only Admin",
        visible_features=["admin_gitlab"],
        preferred_platform="admin_console",
    )
    user.platform_roles.add(role)
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture(autouse=True)
def use_locmem_cache():
    with override_settings(CACHES=TEST_CACHES):
        cache.clear()
        yield
        cache.clear()


@pytest.fixture
def jenkins_instance():
    return JenkinsInstance.objects.create(
        name="Primary Jenkins",
        url="http://jenkins.example.com",
        username="user",
        token="token",
        is_active=True,
    )


@pytest.mark.django_db
def test_jobs_uses_cached_payload_without_calling_jenkins(
    authenticated_client, jenkins_instance
):
    cache.set(
        build_job_catalog_cache_key(jenkins_instance.id),
        {
            "instance": {
                "id": jenkins_instance.id,
                "name": jenkins_instance.name,
                "url": jenkins_instance.url,
            },
            "jobs": [{"full_name": "cached/job", "display_name": "cached/job"}],
            "fetched_at": "2026-05-22T00:00:00+00:00",
        },
    )

    with patch("jenkins_trigger.views.get_jenkins_client") as get_client:
        response = authenticated_client.get(
            f"/api/v1/jenkins/instances/{jenkins_instance.id}/jobs/"
        )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["cached"] is True
    assert payload["stale"] is False
    assert payload["jobs"][0]["full_name"] == "cached/job"
    get_client.assert_not_called()


@pytest.mark.django_db
def test_jobs_fetches_and_caches_when_cache_missed(
    authenticated_client, jenkins_instance
):
    mock_client = Mock()
    mock_client.list_jobs.return_value = [
        JenkinsJobNode(
            full_name="enabled/job",
            display_name="Enabled Job",
            url="http://jenkins.example.com/job/enabled/job/",
            type="job",
            has_children=False,
            buildable=True,
            color="blue",
        )
    ]

    with patch(
        "jenkins_trigger.views.get_jenkins_client", return_value=mock_client
    ):
        response = authenticated_client.get(
            f"/api/v1/jenkins/instances/{jenkins_instance.id}/jobs/"
        )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["cached"] is False
    assert payload["stale"] is False
    assert payload["jobs"][0]["buildable"] is True
    assert payload["jobs"][0]["color"] == "blue"
    assert payload["jobs"][0]["enabled"] is True
    assert cache.get(build_job_catalog_cache_key(jenkins_instance.id)) is not None
    mock_client.list_jobs.assert_called_once()


@pytest.mark.django_db
def test_jobs_normalizes_disabled_state_from_buildable(
    authenticated_client, jenkins_instance
):
    mock_client = Mock()
    mock_client.list_jobs.return_value = [
        JenkinsJobNode(
            full_name="disabled/job",
            display_name="Disabled Job",
            url="http://jenkins.example.com/job/disabled/job/",
            type="job",
            has_children=False,
            buildable=False,
            color="disabled",
        )
    ]

    with patch(
        "jenkins_trigger.views.get_jenkins_client", return_value=mock_client
    ):
        response = authenticated_client.get(
            f"/api/v1/jenkins/instances/{jenkins_instance.id}/jobs/"
        )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["jobs"][0]["enabled"] is False


@pytest.mark.django_db
def test_jobs_normalizes_disabled_state_from_color_when_buildable_missing(
    authenticated_client, jenkins_instance
):
    mock_client = Mock()
    mock_client.list_jobs.return_value = [
        JenkinsJobNode(
            full_name="legacy/job",
            display_name="Legacy Job",
            url="http://jenkins.example.com/job/legacy/job/",
            type="job",
            has_children=False,
            buildable=None,
            color="disabled",
        )
    ]

    with patch(
        "jenkins_trigger.views.get_jenkins_client", return_value=mock_client
    ):
        response = authenticated_client.get(
            f"/api/v1/jenkins/instances/{jenkins_instance.id}/jobs/"
        )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["jobs"][0]["enabled"] is False


@pytest.mark.django_db
def test_jobs_do_not_mark_folder_nodes_as_enabled(
    authenticated_client, jenkins_instance
):
    mock_client = Mock()
    mock_client.list_jobs.return_value = [
        JenkinsJobNode(
            full_name="folder-a",
            display_name="Folder A",
            url="http://jenkins.example.com/job/folder-a/",
            type="folder",
            has_children=True,
            children=[
                JenkinsJobNode(
                    full_name="folder-a/enabled-job",
                    display_name="Enabled Job",
                    url="http://jenkins.example.com/job/folder-a/job/enabled-job/",
                    type="job",
                    has_children=False,
                    buildable=True,
                    color="blue",
                )
            ],
        )
    ]

    with patch(
        "jenkins_trigger.views.get_jenkins_client", return_value=mock_client
    ):
        response = authenticated_client.get(
            f"/api/v1/jenkins/instances/{jenkins_instance.id}/jobs/"
        )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["jobs"][0]["enabled"] is None
    assert payload["jobs"][0]["children"][0]["enabled"] is True


@pytest.mark.django_db
def test_jobs_force_refresh_bypasses_existing_cache(
    authenticated_client, jenkins_instance
):
    cache.set(
        build_job_catalog_cache_key(jenkins_instance.id),
        {
            "instance": {
                "id": jenkins_instance.id,
                "name": jenkins_instance.name,
                "url": jenkins_instance.url,
            },
            "jobs": [{"full_name": "old/job", "display_name": "Old Job"}],
            "fetched_at": "2026-05-21T00:00:00+00:00",
        },
    )
    mock_client = Mock()
    mock_client.list_jobs.return_value = []

    with patch(
        "jenkins_trigger.views.get_jenkins_client", return_value=mock_client
    ):
        response = authenticated_client.get(
            f"/api/v1/jenkins/instances/{jenkins_instance.id}/jobs/?force_refresh=true"
    )

    assert response.status_code == 200
    body = response.json()
    payload = body["data"] if isinstance(body, dict) and "data" in body else body
    assert payload["cached"] is False
    assert payload["stale"] is False
    mock_client.list_jobs.assert_called_once()


@pytest.mark.django_db
def test_jobs_cached_response_hydrates_latest_labels(
    authenticated_client, jenkins_instance
):
    from jenkins_trigger.models import (
        JenkinsJobIdentity,
        JenkinsResourceLabel,
    )

    label = JenkinsResourceLabel.objects.create(name="hyperbdr")
    identity = JenkinsJobIdentity.objects.create(
        instance=jenkins_instance, full_name="Agentless_venv"
    )
    identity.labels.add(label)
    cache.set(
        build_job_catalog_cache_key(jenkins_instance.id),
        {
            "instance": {
                "id": jenkins_instance.id,
                "name": jenkins_instance.name,
                "url": jenkins_instance.url,
            },
            "jobs": [
                {
                    "full_name": "Agentless_venv",
                    "display_name": "Agentless_venv",
                    "type": "job",
                    "has_children": False,
                    "enabled": True,
                    "labels": [],
                    "children": [],
                }
            ],
            "fetched_at": "2026-05-21T00:00:00+00:00",
        },
    )

    response = authenticated_client.get(
        f"/api/v1/jenkins/instances/{jenkins_instance.id}/jobs/"
    )

    assert response.status_code == 200
    body = response.json()
    payload = body["data"] if isinstance(body, dict) and "data" in body else body
    assert payload["cached"] is True
    assert payload["jobs"][0]["labels"] == [
        {"id": label.id, "name": "hyperbdr", "slug": "hyperbdr"}
    ]


@pytest.mark.django_db
def test_jobs_force_refresh_returns_stale_cache_on_failure(
    authenticated_client, jenkins_instance
):
    cache.set(
        build_job_catalog_cache_key(jenkins_instance.id),
        {
            "instance": {
                "id": jenkins_instance.id,
                "name": jenkins_instance.name,
                "url": jenkins_instance.url,
            },
            "jobs": [{"full_name": "cached/job", "display_name": "Cached Job"}],
            "fetched_at": "2026-05-21T00:00:00+00:00",
        },
    )
    mock_client = Mock()
    mock_client.list_jobs.side_effect = RuntimeError("jenkins unavailable")

    with patch(
        "jenkins_trigger.views.get_jenkins_client", return_value=mock_client
    ):
        response = authenticated_client.get(
            f"/api/v1/jenkins/instances/{jenkins_instance.id}/jobs/?force_refresh=true"
    )

    assert response.status_code == 200
    body = response.json()
    payload = body["data"] if isinstance(body, dict) and "data" in body else body
    assert payload["cached"] is True
    assert payload["stale"] is True
    assert "warning" in payload
    assert payload["warning_code"] == "JENKINS_REQUEST_FAILED"
    assert "jenkins unavailable" not in payload["warning"]
    assert payload["request_id"]


@pytest.mark.django_db
def test_jobs_returns_400_when_refresh_fails_without_cache(
    authenticated_client, jenkins_instance
):
    mock_client = Mock()
    mock_client.list_jobs.side_effect = RuntimeError("jenkins unavailable")

    with patch(
        "jenkins_trigger.views.get_jenkins_client", return_value=mock_client
    ):
        response = authenticated_client.get(
            f"/api/v1/jenkins/instances/{jenkins_instance.id}/jobs/?force_refresh=true"
        )

    assert response.status_code == 400
    body = response.json()
    payload = body["data"] if "data" in body else body
    assert "获取 Job 列表失败" in payload.get("detail", payload.get("message", ""))


@pytest.mark.django_db
def test_jobs_auth_failure_returns_safe_error_without_upstream_url(
    authenticated_client, jenkins_instance
):
    response = Mock(status_code=401)
    error = requests.HTTPError(
        "401 Client Error: Unauthorized for url: "
        "http://jenkins.internal/api/json?tree=jobs"
    )
    error.response = response
    mock_client = Mock()
    mock_client.list_jobs.side_effect = error

    with patch(
        "jenkins_trigger.views.get_jenkins_client", return_value=mock_client
    ):
        api_response = authenticated_client.get(
            f"/api/v1/jenkins/instances/{jenkins_instance.id}/jobs/?force_refresh=true"
        )

    assert api_response.status_code == 422
    payload = api_response.json()
    payload = payload["data"] if "data" in payload else payload
    assert payload["error_code"] == "JENKINS_AUTH_FAILED"
    assert "API Token" in payload["detail"]
    assert "jenkins.internal" not in str(payload)
    assert payload["request_id"]


@pytest.mark.django_db
def test_jobs_cache_keys_are_isolated_by_instance(authenticated_client):
    instance_a = JenkinsInstance.objects.create(
        name="Jenkins A",
        url="http://jenkins-a.example.com",
        username="user-a",
        token="token-a",
        is_active=True,
    )
    instance_b = JenkinsInstance.objects.create(
        name="Jenkins B",
        url="http://jenkins-b.example.com",
        username="user-b",
        token="token-b",
        is_active=True,
    )

    cache.set(
        build_job_catalog_cache_key(instance_a.id),
        {
            "instance": {
                "id": instance_a.id,
                "name": instance_a.name,
                "url": instance_a.url,
            },
            "jobs": [{"full_name": "a/job", "display_name": "A Job"}],
            "fetched_at": "2026-05-21T00:00:00+00:00",
        },
    )

    mock_client = Mock()
    mock_client.list_jobs.return_value = []

    response_a = authenticated_client.get(
        f"/api/v1/jenkins/instances/{instance_a.id}/jobs/"
    )
    with patch(
        "jenkins_trigger.views.get_jenkins_client", return_value=mock_client
    ):
        response_b = authenticated_client.get(
            f"/api/v1/jenkins/instances/{instance_b.id}/jobs/"
        )

    assert response_a.status_code == 200
    assert response_b.status_code == 200
    payload_a = response_a.json()["data"]
    payload_b = response_b.json()["data"]
    assert payload_a["jobs"][0]["full_name"] == "a/job"
    assert payload_a["cached"] is True
    assert payload_b["cached"] is False
    mock_client.list_jobs.assert_called_once()


@pytest.mark.django_db
def test_workspace_user_cannot_access_jenkins_admin_endpoints(
    workspace_client, jenkins_instance
):
    list_response = workspace_client.get("/api/v1/jenkins/instances/")
    jobs_response = workspace_client.get(
        f"/api/v1/jenkins/instances/{jenkins_instance.id}/jobs/"
    )
    entries_response = workspace_client.get("/api/v1/jenkins/entries/")

    assert list_response.status_code == 403
    assert jobs_response.status_code == 403
    assert entries_response.status_code == 403


@pytest.mark.django_db
def test_gitlab_admin_cannot_access_jenkins_admin_endpoints(
    gitlab_admin_client, jenkins_instance
):
    response = gitlab_admin_client.get("/api/v1/jenkins/instances/")

    assert response.status_code == 403


@pytest.mark.django_db
def test_workspace_user_cannot_access_gitlab_admin_endpoints(workspace_client):
    GitLabInstance.objects.create(
        name="Primary GitLab",
        url="http://gitlab.example.com",
        private_token="token",
        is_active=True,
    )

    response = workspace_client.get("/api/v1/gitlab/instances/")

    assert response.status_code == 403


@pytest.mark.django_db
def test_trigger_record_stores_queue_url_after_trigger(
    authenticated_client, jenkins_instance
):
    entry = jenkins_instance.trigger_entries.create(
        name="Build App",
        job_name="build-app",
        params_config={},
        is_active=True,
    )
    mock_client = Mock()
    mock_client.get_job_params.return_value = []
    mock_client.trigger_build.return_value = JenkinsBuildTriggerResult(
        queue_url="http://jenkins.example.com/queue/item/38508/",
        queue_id=38508,
        build_number=None,
    )

    with patch(
        "jenkins_trigger.views.get_jenkins_client", return_value=mock_client
    ):
        response = authenticated_client.post(
            "/api/v1/jenkins/records/trigger/",
            {"entry_id": entry.id, "params": {"BRANCH": "main"}},
            format="json",
        )

    assert response.status_code == 200
    payload = response.json()["data"]
    record = TriggerRecord.objects.get(id=payload["record_id"])
    assert payload["build_number"] is None
    assert payload["queue_url"] == "http://jenkins.example.com/queue/item/38508/"
    assert record.queue_url == "http://jenkins.example.com/queue/item/38508/"
    assert record.build_number is None


@pytest.mark.django_db
def test_trigger_maps_user_params_to_canonical_jenkins_names(
    authenticated_client, jenkins_instance
):
    entry = jenkins_instance.trigger_entries.create(
        name="Build App",
        job_name="build-app",
        params_config={
            "branch_name": {"mode": "editable", "default_value": "main"},
            "project_git_url": {
                "mode": "readonly",
                "default_value": "ssh://git@example.com/repo.git",
            },
        },
        is_active=True,
    )
    mock_client = Mock()
    mock_client.get_job_params.return_value = [
        JenkinsParamDefinition(
            name="BRANCH_NAME",
            type="StringParameterDefinition",
            default_value="qa",
        ),
        JenkinsParamDefinition(
            name="PROJECT_GIT_URL",
            type="StringParameterDefinition",
            default_value="ssh://git@example.com/repo.git",
        ),
    ]
    mock_client.trigger_build.return_value = JenkinsBuildTriggerResult(
        queue_url="http://jenkins.example.com/queue/item/38509/",
        queue_id=38509,
        build_number=None,
    )

    with patch(
        "jenkins_trigger.views.get_jenkins_client", return_value=mock_client
    ):
        response = authenticated_client.post(
            "/api/v1/jenkins/records/trigger/",
            {
                "entry_id": entry.id,
                "params": {
                    "branch_name": "release/2026.05",
                    "project_git_url": "ssh://git@example.com/repo.git",
                },
            },
            format="json",
        )

    assert response.status_code == 200
    mock_client.trigger_build.assert_called_once_with(
        "build-app",
        {
            "BRANCH_NAME": "release/2026.05",
            "PROJECT_GIT_URL": "ssh://git@example.com/repo.git",
        },
    )


@pytest.mark.django_db
def test_trigger_maps_hidden_params_to_canonical_jenkins_names(
    authenticated_client, jenkins_instance
):
    entry = jenkins_instance.trigger_entries.create(
        name="Build App",
        job_name="build-app",
        params_config={
            "branch_name": {"mode": "editable", "default_value": "main"},
            "scp_user": {"mode": "hidden", "default_value": "root"},
        },
        is_active=True,
    )
    mock_client = Mock()
    mock_client.get_job_params.return_value = [
        JenkinsParamDefinition(
            name="BRANCH_NAME",
            type="StringParameterDefinition",
            default_value="qa",
        ),
        JenkinsParamDefinition(
            name="SCP_USER",
            type="StringParameterDefinition",
            default_value="jenkins",
        ),
    ]
    mock_client.trigger_build.return_value = JenkinsBuildTriggerResult(
        queue_url="http://jenkins.example.com/queue/item/38510/",
        queue_id=38510,
        build_number=None,
    )

    with patch(
        "jenkins_trigger.views.get_jenkins_client", return_value=mock_client
    ):
        response = authenticated_client.post(
            "/api/v1/jenkins/records/trigger/",
            {
                "entry_id": entry.id,
                "params": {
                    "branch_name": "release/2026.05",
                },
            },
            format="json",
        )

    assert response.status_code == 200
    mock_client.trigger_build.assert_called_once_with(
        "build-app",
        {
            "BRANCH_NAME": "release/2026.05",
            "SCP_USER": "root",
        },
    )


@pytest.mark.django_db
def test_refresh_status_keeps_record_pending_while_queue_has_no_executable(
    authenticated_client, jenkins_instance
):
    entry = jenkins_instance.trigger_entries.create(
        name="Build App",
        job_name="build-app",
        params_config={},
        is_active=True,
    )
    record = TriggerRecord.objects.create(
        entry=entry,
        user=None,
        status="pending",
        queue_url="http://jenkins.example.com/queue/item/38508/",
    )
    mock_client = Mock()
    mock_client.get_queue_item.return_value = JenkinsQueueItem(
        queue_id=38508,
        executable_number=None,
    )

    with patch(
        "jenkins_trigger.views.get_jenkins_client", return_value=mock_client
    ):
        response = authenticated_client.post(
            f"/api/v1/jenkins/records/{record.id}/refresh_status/"
        )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["status"] == "pending"
    assert payload["build_number"] is None
    assert payload["progress_percent"] == 0
    assert payload["current_stage"] == "排队中"
    mock_client.get_build_result.assert_not_called()


@pytest.mark.django_db
def test_refresh_status_updates_pipeline_progress_snapshot(
    authenticated_client, jenkins_instance
):
    entry = jenkins_instance.trigger_entries.create(
        name="Build App",
        job_name="build-app",
        params_config={},
        is_active=True,
    )
    record = TriggerRecord.objects.create(
        entry=entry,
        user=None,
        status="running",
        build_number=42,
    )
    mock_client = Mock()
    mock_client.get_build_result.return_value = JenkinsBuildResult(
        build_number=42,
        result=None,
        duration=0,
        timestamp=0,
        artifacts=[],
    )
    mock_client.get_pipeline_progress.return_value = Mock(
        pipeline_supported=True,
        progress_percent=50,
        current_stage="Docker build",
        stage_summary={"total": 4, "completed": 2},
    )

    with patch(
        "jenkins_trigger.views.get_jenkins_client", return_value=mock_client
    ):
        response = authenticated_client.post(
            f"/api/v1/jenkins/records/{record.id}/refresh_status/"
        )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["status"] == "running"
    assert payload["pipeline_supported"] is True
    assert payload["progress_percent"] == 50
    assert payload["current_stage"] == "Docker build"
    assert payload["stage_summary"] == {"total": 4, "completed": 2}

    record.refresh_from_db()
    assert record.progress_percent == 50
    assert record.current_stage == "Docker build"
    assert record.stage_summary == {"total": 4, "completed": 2}
    assert record.pipeline_supported is True


@pytest.mark.django_db
def test_refresh_status_sets_terminal_progress_to_100(
    authenticated_client, jenkins_instance
):
    entry = jenkins_instance.trigger_entries.create(
        name="Build App",
        job_name="build-app",
        params_config={},
        is_active=True,
    )
    record = TriggerRecord.objects.create(
        entry=entry,
        user=None,
        status="running",
        build_number=42,
    )
    mock_client = Mock()
    mock_client.get_build_result.return_value = JenkinsBuildResult(
        build_number=42,
        result="SUCCESS",
        duration=120000,
        timestamp=int(timezone.now().timestamp() * 1000),
        artifacts=[],
    )
    mock_client.get_pipeline_progress.return_value = Mock(
        pipeline_supported=True,
        progress_percent=67,
        current_stage="Deploy",
        stage_summary={"total": 3, "completed": 2},
    )

    with patch(
        "jenkins_trigger.views.get_jenkins_client", return_value=mock_client
    ):
        response = authenticated_client.post(
            f"/api/v1/jenkins/records/{record.id}/refresh_status/"
        )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["status"] == "success"
    assert payload["pipeline_supported"] is True
    assert payload["progress_percent"] == 100
    assert payload["current_stage"] == "Deploy"
    assert payload["stage_summary"] == {"total": 3, "completed": 3}


@pytest.mark.django_db
def test_refresh_status_degrades_when_pipeline_progress_is_unavailable(
    authenticated_client, jenkins_instance
):
    entry = jenkins_instance.trigger_entries.create(
        name="Build App",
        job_name="build-app",
        params_config={},
        is_active=True,
    )
    record = TriggerRecord.objects.create(
        entry=entry,
        user=None,
        status="running",
        build_number=42,
    )
    mock_client = Mock()
    mock_client.get_build_result.return_value = JenkinsBuildResult(
        build_number=42,
        result=None,
        duration=0,
        timestamp=0,
        artifacts=[],
    )
    mock_client.get_pipeline_progress.side_effect = Exception("wfapi unavailable")

    with patch(
        "jenkins_trigger.views.get_jenkins_client", return_value=mock_client
    ):
        response = authenticated_client.post(
            f"/api/v1/jenkins/records/{record.id}/refresh_status/"
        )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["status"] == "running"
    assert payload["pipeline_supported"] is False
    assert payload["progress_percent"] is None
    assert payload["current_stage"] == ""
    assert payload["stage_summary"] is None


@pytest.mark.django_db
def test_refresh_status_does_not_downgrade_aborted_record(
    authenticated_client, jenkins_instance
):
    entry = jenkins_instance.trigger_entries.create(
        name="Build App",
        job_name="build-app",
        params_config={},
        is_active=True,
    )
    record = TriggerRecord.objects.create(
        entry=entry,
        user=None,
        status="aborted",
        queue_url="http://jenkins.example.com/queue/item/38508/",
        finished_at=timezone.now(),
    )
    mock_client = Mock()

    with patch(
        "jenkins_trigger.views.get_jenkins_client", return_value=mock_client
    ):
        response = authenticated_client.post(
            f"/api/v1/jenkins/records/{record.id}/refresh_status/"
        )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["status"] == "aborted"
    mock_client.get_queue_item.assert_not_called()
    mock_client.find_build_number_by_queue_id.assert_not_called()


@pytest.mark.django_db
def test_records_can_be_filtered_by_status(authenticated_client, jenkins_instance):
    entry = jenkins_instance.trigger_entries.create(
        name="Build App",
        job_name="build-app",
        params_config={},
        is_active=True,
    )
    running_record = TriggerRecord.objects.create(
        entry=entry,
        user=None,
        status="running",
        build_number=42,
    )
    TriggerRecord.objects.create(
        entry=entry,
        user=None,
        status="success",
        build_number=41,
    )

    response = authenticated_client.get(
        "/api/v1/jenkins/records/",
        {"status": "running"},
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    results = payload.get("results", payload)
    assert [record["id"] for record in results] == [running_record.id]


@pytest.mark.django_db
def test_workspace_record_response_masks_hidden_params(
    workspace_client, jenkins_instance
):
    entry = jenkins_instance.trigger_entries.create(
        name="Build App",
        job_name="build-app",
        params_config={
            "BRANCH": {"mode": "editable", "default_value": "main"},
            "SECRET_TOKEN": {"mode": "hidden", "default_value": "token-value"},
        },
        is_active=True,
    )
    record = TriggerRecord.objects.create(
        entry=entry,
        user=None,
        status="pending",
        params={
            "BRANCH": "release/2026.05",
            "SECRET_TOKEN": "token-value",
        },
    )

    response = workspace_client.get("/api/v1/jenkins/records/")

    assert response.status_code == 200
    payload = response.json()["data"]
    results = payload.get("results", payload)
    record_payload = next(item for item in results if item["id"] == record.id)
    assert record_payload["params"]["BRANCH"] == "release/2026.05"
    assert record_payload["params"]["SECRET_TOKEN"] == "******"
    assert "token-value" not in str(record_payload)


@pytest.mark.django_db
def test_admin_record_response_keeps_hidden_params(
    authenticated_client, jenkins_instance
):
    entry = jenkins_instance.trigger_entries.create(
        name="Build App",
        job_name="build-app",
        params_config={
            "SECRET_TOKEN": {"mode": "hidden", "default_value": "token-value"},
        },
        is_active=True,
    )
    record = TriggerRecord.objects.create(
        entry=entry,
        user=None,
        status="pending",
        params={"SECRET_TOKEN": "token-value"},
    )

    response = authenticated_client.get("/api/v1/jenkins/records/")

    assert response.status_code == 200
    payload = response.json()["data"]
    results = payload.get("results", payload)
    record_payload = next(item for item in results if item["id"] == record.id)
    assert record_payload["params"]["SECRET_TOKEN"] == "token-value"


@pytest.mark.django_db
def test_refresh_status_resolves_queue_to_real_build_number(
    authenticated_client, jenkins_instance
):
    entry = jenkins_instance.trigger_entries.create(
        name="Build App",
        job_name="build-app",
        params_config={},
        is_active=True,
    )
    record = TriggerRecord.objects.create(
        entry=entry,
        user=None,
        status="pending",
        queue_url="http://jenkins.example.com/queue/item/38508/",
    )
    mock_client = Mock()
    mock_client.get_queue_item.return_value = JenkinsQueueItem(
        queue_id=38508,
        executable_number=42,
    )
    mock_client.get_build_result.return_value = JenkinsBuildResult(
        build_number=42,
        result=None,
        duration=0,
        timestamp=0,
        artifacts=[],
    )

    with patch(
        "jenkins_trigger.views.get_jenkins_client", return_value=mock_client
    ):
        response = authenticated_client.post(
            f"/api/v1/jenkins/records/{record.id}/refresh_status/"
        )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["status"] == "running"
    assert payload["build_number"] == 42

    record.refresh_from_db()
    assert record.build_number == 42
    mock_client.get_build_result.assert_called_once_with("build-app", 42)


@pytest.mark.django_db
def test_refresh_status_falls_back_to_recent_build_lookup_when_queue_item_is_gone(
    authenticated_client, jenkins_instance
):
    entry = jenkins_instance.trigger_entries.create(
        name="Build App",
        job_name="build-app",
        params_config={},
        is_active=True,
    )
    record = TriggerRecord.objects.create(
        entry=entry,
        user=None,
        status="pending",
        queue_url="http://jenkins.example.com/queue/item/38645/",
    )
    queue_response = requests.Response()
    queue_response.status_code = 404
    queue_error = requests.HTTPError("queue item missing", response=queue_response)

    mock_client = Mock()
    mock_client.get_queue_item.side_effect = queue_error
    mock_client.find_build_number_by_queue_id.return_value = 108
    mock_client.get_build_result.return_value = JenkinsBuildResult(
        build_number=108,
        result=None,
        duration=0,
        timestamp=0,
        artifacts=[],
    )

    with patch(
        "jenkins_trigger.views.get_jenkins_client", return_value=mock_client
    ):
        response = authenticated_client.post(
            f"/api/v1/jenkins/records/{record.id}/refresh_status/"
        )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["status"] == "running"
    assert payload["build_number"] == 108
    mock_client.find_build_number_by_queue_id.assert_called_once_with("build-app", 38645)


@pytest.mark.django_db
def test_refresh_status_stays_pending_when_queue_item_is_gone_and_build_not_found(
    authenticated_client, jenkins_instance
):
    entry = jenkins_instance.trigger_entries.create(
        name="Build App",
        job_name="build-app",
        params_config={},
        is_active=True,
    )
    record = TriggerRecord.objects.create(
        entry=entry,
        user=None,
        status="pending",
        queue_url="http://jenkins.example.com/queue/item/38645/",
    )
    queue_response = requests.Response()
    queue_response.status_code = 404
    queue_error = requests.HTTPError("queue item missing", response=queue_response)

    mock_client = Mock()
    mock_client.get_queue_item.side_effect = queue_error
    mock_client.find_build_number_by_queue_id.return_value = None

    with patch(
        "jenkins_trigger.views.get_jenkins_client", return_value=mock_client
    ):
        response = authenticated_client.post(
            f"/api/v1/jenkins/records/{record.id}/refresh_status/"
        )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["status"] == "pending"
    assert payload["build_number"] is None


@pytest.mark.django_db
def test_apply_build_result_uses_jenkins_finished_timestamp():
    instance = JenkinsInstance.objects.create(
        name="Primary Jenkins",
        url="http://jenkins.example.com",
        username="user",
        token="token",
        is_active=True,
    )
    entry = instance.trigger_entries.create(
        name="Build App",
        job_name="build-app",
        params_config={},
        is_active=True,
    )
    record = TriggerRecord.objects.create(
        entry=entry,
        user=None,
        status="running",
    )
    result = JenkinsBuildResult(
        build_number=42,
        result="SUCCESS",
        timestamp=1_748_275_073_000,
        duration=577_000,
        artifacts=[],
    )

    apply_build_result_to_record(record, result)

    assert record.status == "success"
    assert record.finished_at.isoformat() == "2025-05-26T16:07:30+00:00"


@pytest.mark.django_db
def test_fetch_params_prefers_last_successful_build_values(
    authenticated_client, jenkins_instance
):
    mock_client = Mock()
    mock_client.get_job_params.return_value = [
        JenkinsParamDefinition(
            name="BRANCH",
            type="StringParameterDefinition",
            default_value="main",
            choices=None,
            description="Git branch",
        ),
        JenkinsParamDefinition(
            name="ENV",
            type="StringParameterDefinition",
            default_value="dev",
            choices=None,
            description="Target env",
        ),
    ]
    mock_client.get_last_successful_build_params.return_value = {
        "BRANCH": "release/2026.05",
    }

    with patch(
        "jenkins_trigger.views.get_jenkins_client", return_value=mock_client
    ):
        response = authenticated_client.post(
            f"/api/v1/jenkins/instances/{jenkins_instance.id}/fetch_params/",
            {"job_name": "folder-a/build-app"},
            format="json",
        )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["params"][0]["name"] == "BRANCH"
    assert payload["params"][0]["default_value"] == "release/2026.05"
    assert payload["params"][0]["value_source"] == "latest_success_build"
    assert payload["params"][1]["default_value"] == "dev"
    assert payload["params"][1]["value_source"] == "job_default"


@pytest.mark.django_db
def test_fetch_params_falls_back_to_job_default_when_latest_build_fails(
    authenticated_client, jenkins_instance
):
    mock_client = Mock()
    mock_client.get_job_params.return_value = [
        JenkinsParamDefinition(
            name="BRANCH",
            type="StringParameterDefinition",
            default_value="main",
            choices=None,
            description="Git branch",
        )
    ]
    mock_client.get_last_successful_build_params.side_effect = RuntimeError(
        "last build unavailable"
    )

    with patch(
        "jenkins_trigger.views.get_jenkins_client", return_value=mock_client
    ):
        response = authenticated_client.post(
            f"/api/v1/jenkins/instances/{jenkins_instance.id}/fetch_params/",
            {"job_name": "folder-a/build-app"},
            format="json",
        )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["params"][0]["default_value"] == "main"
    assert payload["params"][0]["value_source"] == "job_default"


@pytest.mark.django_db
def test_fetch_params_marks_empty_when_no_latest_or_job_default(
    authenticated_client, jenkins_instance
):
    mock_client = Mock()
    mock_client.get_job_params.return_value = [
        JenkinsParamDefinition(
            name="OPTIONAL",
            type="StringParameterDefinition",
            default_value=None,
            choices=None,
            description=None,
        )
    ]
    mock_client.get_last_successful_build_params.return_value = {}

    with patch(
        "jenkins_trigger.views.get_jenkins_client", return_value=mock_client
    ):
        response = authenticated_client.post(
            f"/api/v1/jenkins/instances/{jenkins_instance.id}/fetch_params/",
            {"job_name": "folder-a/build-app"},
            format="json",
        )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["params"][0]["default_value"] == ""
    assert payload["params"][0]["value_source"] == "empty"


@pytest.mark.django_db
def test_entry_params_hide_hidden_params_from_workspace(
    workspace_client, jenkins_instance
):
    entry = JenkinsInstance.objects.get(id=jenkins_instance.id).trigger_entries.create(
        name="Build App",
        job_name="build-app",
        params_config={
            "VISIBLE": {"mode": "editable", "default_value": "main"},
            "SECRET": {"mode": "hidden", "default_value": "token-value"},
        },
        is_active=True,
    )
    mock_client = Mock()
    mock_client.get_job_params.return_value = [
        JenkinsParamDefinition(
            name="VISIBLE",
            type="StringParameterDefinition",
            default_value="main",
        ),
        JenkinsParamDefinition(
            name="SECRET",
            type="StringParameterDefinition",
            default_value="",
        ),
    ]

    with patch(
        "jenkins_trigger.views.get_jenkins_client", return_value=mock_client
    ):
        response = workspace_client.get(
            f"/api/v1/jenkins/entries/{entry.id}/params/"
        )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert [param["name"] for param in payload["params"]] == ["VISIBLE"]
    assert "config" not in payload
    assert "SECRET" not in str(payload)
    assert "token-value" not in str(payload)


@pytest.mark.django_db
def test_entry_params_default_unconfigured_jenkins_params_to_hidden(
    authenticated_client, workspace_client, jenkins_instance
):
    entry = JenkinsInstance.objects.get(id=jenkins_instance.id).trigger_entries.create(
        name="Build App",
        job_name="build-app",
        params_config={},
        is_active=True,
    )
    mock_client = Mock()
    mock_client.get_job_params.return_value = [
        JenkinsParamDefinition(
            name="BRANCH_NAME",
            type="StringParameterDefinition",
            default_value="main",
        )
    ]

    with patch(
        "jenkins_trigger.views.get_jenkins_client", return_value=mock_client
    ):
        workspace_response = workspace_client.get(
            f"/api/v1/jenkins/entries/{entry.id}/params/"
        )
        admin_response = authenticated_client.get(
            f"/api/v1/jenkins/entries/{entry.id}/admin_params/"
        )

    assert workspace_response.status_code == 200
    assert workspace_response.json()["data"]["params"] == []

    assert admin_response.status_code == 200
    admin_payload = admin_response.json()["data"]
    assert admin_payload["params"][0]["name"] == "BRANCH_NAME"
    assert admin_payload["params"][0]["mode"] == "hidden"


@pytest.mark.django_db
def test_workspace_user_cannot_fetch_entry_admin_params(
    workspace_client, jenkins_instance
):
    entry = JenkinsInstance.objects.get(id=jenkins_instance.id).trigger_entries.create(
        name="Build App",
        job_name="build-app",
        params_config={
            "SECRET": {"mode": "hidden", "default_value": "token-value"},
        },
        is_active=True,
    )

    response = workspace_client.get(
        f"/api/v1/jenkins/entries/{entry.id}/admin_params/"
    )

    assert response.status_code == 403


@pytest.mark.django_db
def test_entry_admin_params_include_hidden_params_for_editing(
    authenticated_client, jenkins_instance
):
    entry = JenkinsInstance.objects.get(id=jenkins_instance.id).trigger_entries.create(
        name="Build App",
        job_name="build-app",
        params_config={
            "VISIBLE": {"mode": "editable", "default_value": "main"},
            "SECRET": {"mode": "hidden", "default_value": "token-value"},
        },
        is_active=True,
    )
    mock_client = Mock()
    mock_client.get_job_params.return_value = [
        JenkinsParamDefinition(
            name="VISIBLE",
            type="StringParameterDefinition",
            default_value="main",
        ),
        JenkinsParamDefinition(
            name="SECRET",
            type="StringParameterDefinition",
            default_value="",
        ),
    ]

    with patch(
        "jenkins_trigger.views.get_jenkins_client", return_value=mock_client
    ):
        response = authenticated_client.get(
            f"/api/v1/jenkins/entries/{entry.id}/admin_params/"
        )

    assert response.status_code == 200
    payload = response.json()["data"]
    params = {param["name"]: param for param in payload["params"]}
    assert params["VISIBLE"]["mode"] == "editable"
    assert params["SECRET"]["mode"] == "hidden"
    assert params["SECRET"]["default_value"] == "token-value"


@pytest.mark.django_db
def test_entry_params_match_saved_config_case_insensitively(
    authenticated_client, workspace_client, jenkins_instance
):
    entry = JenkinsInstance.objects.get(id=jenkins_instance.id).trigger_entries.create(
        name="Build App",
        job_name="build-app",
        params_config={
            "secret_token": {"mode": "hidden", "default_value": "token-value"},
            "branch_name": {"mode": "readonly", "default_value": "main"},
        },
        is_active=True,
    )
    mock_client = Mock()
    mock_client.get_job_params.return_value = [
        JenkinsParamDefinition(
            name="SECRET_TOKEN",
            type="StringParameterDefinition",
            default_value="",
        ),
        JenkinsParamDefinition(
            name="BRANCH_NAME",
            type="StringParameterDefinition",
            default_value="dev",
        ),
    ]

    with patch(
        "jenkins_trigger.views.get_jenkins_client", return_value=mock_client
    ):
        user_response = workspace_client.get(
            f"/api/v1/jenkins/entries/{entry.id}/params/"
        )
        admin_response = authenticated_client.get(
            f"/api/v1/jenkins/entries/{entry.id}/admin_params/"
        )

    assert user_response.status_code == 200
    user_payload = user_response.json()["data"]
    assert [param["name"] for param in user_payload["params"]] == ["BRANCH_NAME"]
    assert user_payload["params"][0]["mode"] == "readonly"
    assert user_payload["params"][0]["default_value"] == "main"

    assert admin_response.status_code == 200
    admin_payload = admin_response.json()["data"]
    assert len(admin_payload["params"]) == 2
    params = {param["name"]: param for param in admin_payload["params"]}
    assert params["SECRET_TOKEN"]["mode"] == "hidden"
    assert params["SECRET_TOKEN"]["default_value"] == "token-value"
    assert params["BRANCH_NAME"]["mode"] == "readonly"


@pytest.mark.django_db
def test_user_entries_do_not_expose_params_config(
    authenticated_client, jenkins_instance
):
    JenkinsInstance.objects.get(id=jenkins_instance.id).trigger_entries.create(
        name="Build App",
        job_name="build-app",
        params_config={
            "SECRET": {"mode": "hidden", "default_value": "token-value"},
        },
        is_active=True,
    )

    response = authenticated_client.get("/api/v1/jenkins/user/entries/")

    assert response.status_code == 200
    payload = response.json()["data"]
    assert "params_config" not in payload[0]


@pytest.fixture
def workspace_user():
    user = User.objects.create_user(
        username="jenkins-workspace-target",
        email="workspace-target@example.com",
        password="testpass123",
    )
    role = Role.objects.create(
        name="Workspace Target",
        visible_features=["workspace"],
    )
    user.platform_roles.add(role)
    return user


@pytest.mark.django_db
def test_trigger_record_list_requires_workspace_jenkins(workspace_client, workspace_user, jenkins_instance):
    entry = JenkinsInstance.objects.get(id=jenkins_instance.id).trigger_entries.create(
        name="Build App",
        job_name="build-app",
        params_config={},
        is_active=True,
    )
    TriggerRecord.objects.create(
        entry=entry,
        user=workspace_user,
        params={},
        status="pending",
    )

    response = workspace_client.get("/api/v1/jenkins/records/")

    assert response.status_code == 200


@pytest.mark.django_db
def test_trigger_record_list_rejects_user_without_workspace_jenkins(
    jenkins_instance,
):
    other = User.objects.create_user(
        username="no-jenkins",
        email="no-jenkins@example.com",
        password="testpass123",
    )
    role = Role.objects.create(
        name="No Workspace Role",
        visible_features=["admin_users"],
    )
    other.platform_roles.add(role)
    client = APIClient()
    client.force_authenticate(user=other)

    response = client.get("/api/v1/jenkins/records/")

    assert response.status_code == 403


@pytest.mark.django_db
def test_user_entries_endpoint_requires_workspace_jenkins(
    jenkins_instance,
):
    other = User.objects.create_user(
        username="no-jenkins-entries",
        email="no-jenkins-entries@example.com",
        password="testpass123",
    )
    role = Role.objects.create(
        name="No Workspace Entries",
        visible_features=["admin_users"],
    )
    other.platform_roles.add(role)
    client = APIClient()
    client.force_authenticate(user=other)

    response = client.get("/api/v1/jenkins/user/entries/")

    assert response.status_code == 403


@pytest.mark.django_db
def test_notification_result_redacted_for_non_admin(
    workspace_client, workspace_user, jenkins_instance
):
    entry = JenkinsInstance.objects.get(id=jenkins_instance.id).trigger_entries.create(
        name="Build App",
        job_name="build-app",
        params_config={},
        is_active=True,
    )
    record = TriggerRecord.objects.create(
        entry=entry,
        user=workspace_user,
        params={},
        status="pending",
    )
    record.notification_result = {
        "emails": ["ops@example.com"],
        "webhooks": ["https://hooks.example.com/secret"],
        "selected_channels": ["personal_email"],
    }
    record.save(update_fields=["notification_result"])

    response = workspace_client.get(f"/api/v1/jenkins/records/{record.id}/")

    assert response.status_code == 200
    body = response.json()
    payload = body["data"] if isinstance(body, dict) and "data" in body else body
    assert payload["notification_result"] is None


@pytest.mark.django_db
def test_notification_result_visible_to_admin(
    workspace_user, jenkins_instance
):
    admin = User.objects.create_user(
        username="jenkins-notif-admin",
        email="jenkins-notif-admin@example.com",
        password="testpass123",
    )
    role = Role.objects.create(
        name="Jenkins Notif Admin",
        visible_features=["workspace_jenkins", "admin_jenkins"],
    )
    admin.platform_roles.add(role)
    admin_client = APIClient()
    admin_client.force_authenticate(user=admin)

    entry = JenkinsInstance.objects.get(id=jenkins_instance.id).trigger_entries.create(
        name="Build App",
        job_name="build-app",
        params_config={},
        is_active=True,
    )
    record = TriggerRecord.objects.create(
        entry=entry,
        user=workspace_user,
        params={},
        status="pending",
    )
    record.notification_result = {
        "emails": ["ops@example.com"],
        "webhooks": ["https://hooks.example.com/secret"],
        "selected_channels": ["personal_email"],
    }
    record.save(update_fields=["notification_result"])

    response = admin_client.get(f"/api/v1/jenkins/records/{record.id}/")

    assert response.status_code == 200
    body = response.json()
    payload = body["data"] if isinstance(body, dict) and "data" in body else body
    assert payload["notification_result"]["emails"] == ["ops@example.com"]


@pytest.mark.django_db
def test_refresh_status_passes_request_context(
    workspace_client, workspace_user, jenkins_instance
):
    entry = JenkinsInstance.objects.get(id=jenkins_instance.id).trigger_entries.create(
        name="Build App",
        job_name="build-app",
        params_config={
            "SECRET": {"mode": "hidden", "default_value": "token"},
        },
        is_active=True,
    )
    record = TriggerRecord.objects.create(
        entry=entry,
        user=workspace_user,
        params={"SECRET": "real-secret"},
        status="success",
    )
    record.progress_percent = 50
    record.save(update_fields=["progress_percent"])

    with patch(
        "jenkins_trigger.views.apply_terminal_progress_to_record"
    ) as apply_terminal:
        response = workspace_client.post(
            f"/api/v1/jenkins/records/{record.id}/refresh_status/"
        )

    apply_terminal.assert_called_once_with(record)
    assert response.status_code == 200
    body = response.json()
    payload = body["data"] if isinstance(body, dict) and "data" in body else body
    assert payload["params"]["SECRET"] == "******"


# ---------------------------------------------------------------------------
# Resource labels & job tag management
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_list_resource_labels_returns_labels_with_job_count(
    authenticated_client, jenkins_instance
):
    from jenkins_trigger.models import JenkinsResourceLabel

    label_a = JenkinsResourceLabel.objects.create(name="production")
    label_b = JenkinsResourceLabel.objects.create(name="staging")
    # job_count is annotated; without annotation it falls back to related count (0)
    response = authenticated_client.get("/api/v1/jenkins/resource-labels/")
    assert response.status_code == 200
    body = response.json()
    payload = body["data"] if isinstance(body, dict) and "data" in body else body
    names = [item["name"] for item in payload]
    assert "production" in names
    assert "staging" in names
    assert label_a.id in [item["id"] for item in payload]


@pytest.mark.django_db
def test_create_resource_label_normalizes_name_and_slug(
    authenticated_client,
):
    response = authenticated_client.post(
        "/api/v1/jenkins/resource-labels/",
        data=json.dumps({"name": "  Frontend  "}),
        content_type="application/json",
    )
    assert response.status_code == 201
    body = response.json()
    payload = body["data"] if isinstance(body, dict) and "data" in body else body
    assert payload["name"] == "Frontend"
    assert payload["slug"] == "frontend"


@pytest.mark.django_db
def test_create_resource_label_rejects_duplicate_slug(
    authenticated_client,
):
    from jenkins_trigger.models import JenkinsResourceLabel

    JenkinsResourceLabel.objects.create(name="Frontend")
    response = authenticated_client.post(
        "/api/v1/jenkins/resource-labels/",
        data=json.dumps({"name": "frontend"}),
        content_type="application/json",
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_update_resource_label(authenticated_client):
    from jenkins_trigger.models import JenkinsResourceLabel

    label = JenkinsResourceLabel.objects.create(name="old")
    response = authenticated_client.patch(
        f"/api/v1/jenkins/resource-labels/{label.id}/",
        data=json.dumps({"name": "new"}),
        content_type="application/json",
    )
    assert response.status_code == 200
    label.refresh_from_db()
    assert label.name == "new"
    assert label.slug == "new"


@pytest.mark.django_db
def test_delete_resource_label_cascades_job_assignments(
    authenticated_client, jenkins_instance
):
    from jenkins_trigger.models import (
        JenkinsJobIdentity,
        JenkinsResourceLabel,
    )

    label = JenkinsResourceLabel.objects.create(name="ephemeral")
    job = JenkinsJobIdentity.objects.create(
        instance=jenkins_instance, full_name="team/build"
    )
    job.labels.add(label)
    response = authenticated_client.delete(
        f"/api/v1/jenkins/resource-labels/{label.id}/"
    )
    assert response.status_code == 204
    assert not JenkinsResourceLabel.objects.filter(id=label.id).exists()
    job.refresh_from_db()
    assert job.labels.count() == 0


@pytest.mark.django_db
def test_jobs_endpoint_returns_labels_for_known_jobs(
    authenticated_client, jenkins_instance
):
    from jenkins_trigger.models import (
        JenkinsJobIdentity,
        JenkinsResourceLabel,
    )

    label = JenkinsResourceLabel.objects.create(name="core")
    identity = JenkinsJobIdentity.objects.create(
        instance=jenkins_instance, full_name="core/build"
    )
    identity.labels.add(label)

    mock_client = Mock()
    mock_client.list_jobs.return_value = [
        JenkinsJobNode(
            full_name="core/build",
            display_name="Build",
            url="http://jenkins.example.com/job/core/job/build/",
            type="job",
            has_children=False,
            buildable=True,
            color="blue",
        ),
        JenkinsJobNode(
            full_name="misc/other",
            display_name="Other",
            url="http://jenkins.example.com/job/misc/job/other/",
            type="job",
            has_children=False,
            buildable=True,
            color="blue",
        ),
    ]

    with patch(
        "jenkins_trigger.views.get_jenkins_client", return_value=mock_client
    ):
        response = authenticated_client.get(
            f"/api/v1/jenkins/instances/{jenkins_instance.id}/jobs/"
        )

    assert response.status_code == 200
    body = response.json()
    payload = body["data"] if isinstance(body, dict) and "data" in body else body
    jobs = {job["full_name"]: job for job in payload["jobs"]}
    assert jobs["core/build"]["labels"] == [
        {"id": label.id, "name": "core", "slug": "core"}
    ]
    assert jobs["misc/other"]["labels"] == []


@pytest.mark.django_db
def test_assign_labels_to_job(authenticated_client, jenkins_instance):
    from jenkins_trigger.models import JenkinsResourceLabel

    label = JenkinsResourceLabel.objects.create(name="infra")
    url = (
        f"/api/v1/jenkins/instances/{jenkins_instance.id}/"
        "jobs/team%2Fbuild/labels/"
    )
    response = authenticated_client.put(
        url,
        data=json.dumps({"label_ids": [label.id]}),
        content_type="application/json",
    )
    assert response.status_code == 200
    body = response.json()
    payload = body["data"] if isinstance(body, dict) and "data" in body else body
    assert payload["full_name"] == "team/build"
    assert [label["id"] for label in payload["labels"]] == [label.id]

    # Re-apply with empty list clears the assignment.
    response = authenticated_client.put(
        url,
        data=json.dumps({"label_ids": []}),
        content_type="application/json",
    )
    assert response.status_code == 200
    body = response.json()
    payload = body["data"] if isinstance(body, dict) and "data" in body else body
    assert payload["labels"] == []


@pytest.mark.django_db
def test_bulk_add_label_to_jobs_appends_without_overwriting(
    authenticated_client, jenkins_instance
):
    from jenkins_trigger.models import JenkinsJobIdentity, JenkinsResourceLabel

    target_label = JenkinsResourceLabel.objects.create(name="hyperbdr")
    existing_label = JenkinsResourceLabel.objects.create(name="stable")
    first_job = JenkinsJobIdentity.objects.create(
        instance=jenkins_instance,
        full_name="team/build",
    )
    first_job.labels.add(existing_label)

    response = authenticated_client.post(
        f"/api/v1/jenkins/instances/{jenkins_instance.id}/jobs/bulk-add-label/",
        data=json.dumps(
            {
                "label_id": target_label.id,
                "full_names": ["team/build", "team/deploy"],
            }
        ),
        content_type="application/json",
    )

    assert response.status_code == 200
    body = response.json()
    payload = body["data"] if isinstance(body, dict) and "data" in body else body
    assert payload["updated_count"] == 2

    first_job.refresh_from_db()
    second_job = JenkinsJobIdentity.objects.get(
        instance=jenkins_instance,
        full_name="team/deploy",
    )
    assert set(first_job.labels.values_list("id", flat=True)) == {
        existing_label.id,
        target_label.id,
    }
    assert list(second_job.labels.values_list("id", flat=True)) == [target_label.id]


@pytest.mark.django_db
def test_assign_labels_to_job_rejects_unknown_label(
    authenticated_client, jenkins_instance
):
    url = (
        f"/api/v1/jenkins/instances/{jenkins_instance.id}/"
        "jobs/team%2Fbuild/labels/"
    )
    response = authenticated_client.put(
        url,
        data=json.dumps({"label_ids": [9999]}),
        content_type="application/json",
    )
    assert response.status_code == 400
