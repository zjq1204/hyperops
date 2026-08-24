import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from accounts.models import Role

from gitlab_resource.models import (
    GitLabCollectionRecord,
    GitLabInstance,
    GitLabTag,
    RegisteredGroup,
    RegisteredProject,
)
from gitlab_resource.services.gitlab_client import GitLabClient

User = get_user_model()


class _GitLabObject:
    def __init__(self, **attrs):
        self.__dict__.update(attrs)


class _ListManager:
    def __init__(self, items=None, details=None):
        self.items = items or []
        self.details = details or {}
        self.list_kwargs = None

    def list(self, **kwargs):
        self.list_kwargs = kwargs
        return self.items

    def get(self, name):
        return self.details[name]


class _ProjectManager:
    def __init__(self, project):
        self.project = project

    def get(self, project_id):
        return self.project


def _payload(response):
    body = response.json()
    if isinstance(body, dict) and "data" in body:
        return body["data"]
    return body


def test_gitlab_client_lists_all_branch_pages():
    branch_stub = _GitLabObject(name="release")
    branch_detail = _GitLabObject(
        name="release",
        protected=True,
        commit={"id": "abc123", "committed_date": "2026-06-11T00:00:00Z"},
    )
    branch_manager = _ListManager(
        items=[branch_stub],
        details={"release": branch_detail},
    )
    project = _GitLabObject(branches=branch_manager)
    client = object.__new__(GitLabClient)
    client.gl = _GitLabObject(projects=_ProjectManager(project))

    branches = client.list_branches(1)

    assert branch_manager.list_kwargs == {"get_all": True}
    assert len(branches) == 1
    assert branches[0].name == "release"
    assert branches[0].protected is True


def test_gitlab_client_lists_all_tag_pages():
    tag_stub = _GitLabObject(name="v1.0.0")
    tag_detail = _GitLabObject(
        name="v1.0.0",
        commit={"id": "def456", "committed_date": "2026-06-11T00:00:00Z"},
    )
    tag_manager = _ListManager(
        items=[tag_stub],
        details={"v1.0.0": tag_detail},
    )
    project = _GitLabObject(tags=tag_manager)
    client = object.__new__(GitLabClient)
    client.gl = _GitLabObject(projects=_ProjectManager(project))

    tags = client.list_tags(1)

    assert tag_manager.list_kwargs == {"get_all": True}
    assert len(tags) == 1
    assert tags[0].name == "v1.0.0"
    assert tags[0].commit_sha == "def456"


@pytest.fixture
def authenticated_client():
    user = User.objects.create_user(
        username="gitlab-admin",
        email="gitlab-admin@example.com",
        password="testpass123",
    )
    role = Role.objects.create(
        name="GitLab Admin",
        visible_features=["admin_console"],
        preferred_platform="admin_console",
    )
    user.platform_roles.add(role)
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def gitlab_instance():
    return GitLabInstance.objects.create(
        name="Primary GitLab",
        url="http://gitlab.example.com",
        private_token="token",
        is_active=True,
    )


@pytest.fixture
def registered_group(gitlab_instance):
    return RegisteredGroup.objects.create(
        instance=gitlab_instance,
        gitlab_id=101,
        name="Backend Group",
        path="backend-group",
    )


@pytest.fixture
def registered_projects(registered_group, gitlab_instance):
    project_a = RegisteredProject.objects.create(
        instance=gitlab_instance,
        group=registered_group,
        gitlab_id=201,
        name="Alpha Service",
        path="backend-group/alpha-service",
        default_branch="main",
    )
    project_b = RegisteredProject.objects.create(
        instance=gitlab_instance,
        group=registered_group,
        gitlab_id=202,
        name="Beta Worker",
        path="backend-group/beta-worker",
        default_branch="main",
    )
    return project_a, project_b


@pytest.mark.django_db
def test_project_labels_crud_and_normalized_uniqueness(authenticated_client):
    create_response = authenticated_client.post(
        "/api/v1/gitlab/project-labels/",
        {"name": "Core API"},
        format="json",
    )

    assert create_response.status_code == 201
    created = _payload(create_response)
    assert created["name"] == "Core API"
    assert created["slug"] == "core-api"
    assert created["project_count"] == 0

    duplicate_response = authenticated_client.post(
        "/api/v1/gitlab/project-labels/",
        {"name": "core api"},
        format="json",
    )
    assert duplicate_response.status_code == 400
    duplicate_payload = _payload(duplicate_response)
    assert "name" in duplicate_payload

    update_response = authenticated_client.patch(
        f"/api/v1/gitlab/project-labels/{created['id']}/",
        {"name": "Critical Service"},
        format="json",
    )
    assert update_response.status_code == 200
    updated = _payload(update_response)
    assert updated["name"] == "Critical Service"
    assert updated["slug"] == "critical-service"

    list_response = authenticated_client.get("/api/v1/gitlab/project-labels/")
    assert list_response.status_code == 200
    listed = _payload(list_response)
    assert listed["count"] == 1
    assert listed["results"][0]["name"] == "Critical Service"


@pytest.mark.django_db
def test_projects_support_label_binding_and_filtering(
    authenticated_client, registered_projects
):
    project_a, project_b = registered_projects

    team_response = authenticated_client.post(
        "/api/v1/gitlab/project-labels/",
        {"name": "Team A"},
        format="json",
    )
    runtime_response = authenticated_client.post(
        "/api/v1/gitlab/project-labels/",
        {"name": "Java Runtime"},
        format="json",
    )

    team_label = _payload(team_response)
    runtime_label = _payload(runtime_response)

    patch_response = authenticated_client.patch(
        f"/api/v1/gitlab/projects/{project_a.id}/",
        {"label_ids": [team_label["id"], runtime_label["id"]]},
        format="json",
    )
    assert patch_response.status_code == 200
    project_payload = _payload(patch_response)
    assert sorted(label["name"] for label in project_payload["labels"]) == [
        "Java Runtime",
        "Team A",
    ]

    patch_second_response = authenticated_client.patch(
        f"/api/v1/gitlab/projects/{project_b.id}/",
        {"label_ids": [runtime_label["id"]]},
        format="json",
    )
    assert patch_second_response.status_code == 200

    filtered_response = authenticated_client.get(
        "/api/v1/gitlab/projects/",
        {"group": project_a.group_id, "label_ids": f"{team_label['id']}"},
    )
    assert filtered_response.status_code == 200
    filtered_payload = _payload(filtered_response)
    assert filtered_payload["count"] == 1
    assert filtered_payload["results"][0]["id"] == project_a.id

    multi_filtered_response = authenticated_client.get(
        "/api/v1/gitlab/projects/",
        {
            "group": project_a.group_id,
            "label_ids": f"{team_label['id']},{runtime_label['id']}",
        },
    )
    assert multi_filtered_response.status_code == 200
    multi_filtered_payload = _payload(multi_filtered_response)
    assert multi_filtered_payload["count"] == 2
    assert {item["id"] for item in multi_filtered_payload["results"]} == {
        project_a.id,
        project_b.id,
    }


@pytest.mark.django_db
def test_deleting_project_label_auto_unbinds_projects(
    authenticated_client, registered_projects
):
    project, _ = registered_projects
    create_response = authenticated_client.post(
        "/api/v1/gitlab/project-labels/",
        {"name": "To Remove"},
        format="json",
    )
    label = _payload(create_response)

    bind_response = authenticated_client.patch(
        f"/api/v1/gitlab/projects/{project.id}/",
        {"label_ids": [label["id"]]},
        format="json",
    )
    assert bind_response.status_code == 200

    delete_response = authenticated_client.delete(
        f"/api/v1/gitlab/project-labels/{label['id']}/"
    )
    assert delete_response.status_code == 204

    project.refresh_from_db()
    assert project.labels.count() == 0

    project_response = authenticated_client.get(f"/api/v1/gitlab/projects/{project.id}/")
    assert project_response.status_code == 200
    project_payload = _payload(project_response)
    assert project_payload["labels"] == []


@pytest.mark.django_db
def test_bulk_collect_projects_writes_collection_records(
    authenticated_client, registered_projects, monkeypatch
):
    project_a, project_b = registered_projects

    class _FakeGitLabClient:
        def list_branches(self, project_id):
            return [_GitLabObject(name=f"branch-{project_id}", protected=False, commit_sha="abc", commit_date=None)]

        def list_tags(self, project_id):
            return [_GitLabObject(name=f"tag-{project_id}", commit_sha="def", released_at=None)]

        def list_webhooks(self, project_id):
            return [
                _GitLabObject(
                    id=project_id,
                    url=f"https://example.com/{project_id}",
                    push_events=True,
                    tag_push_events=False,
                    merge_requests_events=False,
                    enable_ssl_verification=True,
                    token=None,
                    push_events_branch_filter=None,
                    issues_events=False,
                    confidential_issues_events=False,
                    note_events=False,
                    confidential_note_events=False,
                    pipeline_events=False,
                    job_events=False,
                    wiki_page_events=False,
                    deployment_events=False,
                    releases_events=False,
                    feature_flag_events=False,
                    repository_update_events=False,
                    resource_access_token_events=False,
                )
            ]

    monkeypatch.setattr(
        "gitlab_resource.views.get_gitlab_client",
        lambda instance: _FakeGitLabClient(),
    )

    response = authenticated_client.post(
        "/api/v1/gitlab/projects/bulk_collect/",
        {"project_ids": [project_a.id, project_b.id]},
        format="json",
    )

    assert response.status_code == 200
    payload = _payload(response)
    assert payload["total"] == 2
    assert payload["success_count"] == 2
    assert payload["failed_count"] == 0

    records = GitLabCollectionRecord.objects.order_by("project_name")
    assert records.count() == 2
    assert [record.status for record in records] == ["success", "success"]
    assert [record.branches_count for record in records] == [1, 1]

    list_response = authenticated_client.get("/api/v1/gitlab/collection-records/")
    assert list_response.status_code == 200
    list_payload = _payload(list_response)
    assert list_payload["count"] == 2
    assert list_payload["results"][0]["project_path"]


@pytest.mark.django_db
def test_bulk_create_tags_across_projects_reuses_gitlab_client_per_instance(
    authenticated_client, registered_projects, monkeypatch
):
    project_a, project_b = registered_projects
    client_creations = []

    class _FakeGitLabClient:
        def create_tag(self, project_id, tag_name, ref, message=""):
            return _GitLabObject(
                name=tag_name,
                commit_sha=f"sha-{project_id}",
                released_at=None,
            )

    def fake_get_gitlab_client(instance):
        client_creations.append(instance.id)
        return _FakeGitLabClient()

    monkeypatch.setattr(
        "gitlab_resource.views.get_gitlab_client",
        fake_get_gitlab_client,
    )

    response = authenticated_client.post(
        "/api/v1/gitlab/tags/bulk_create/",
        {
            "project_ids": [project_a.id, project_b.id],
            "tag_names": ["v1.0.0"],
            "ref": "main",
        },
        format="json",
    )

    assert response.status_code == 200
    payload = _payload(response)
    assert payload["success_count"] == 2
    assert payload["error_count"] == 0
    assert client_creations == [project_a.instance_id]
    assert GitLabTag.objects.filter(name="v1.0.0").count() == 2


@pytest.mark.django_db
def test_bulk_create_tags_passes_optional_message_to_gitlab(
    authenticated_client, registered_projects, monkeypatch
):
    project, _ = registered_projects
    calls = []

    class _FakeGitLabClient:
        def create_tag(self, project_id, tag_name, ref, message=""):
            calls.append({
                "project_id": project_id,
                "tag_name": tag_name,
                "ref": ref,
                "message": message,
            })
            return _GitLabObject(
                name=tag_name,
                commit_sha="sha",
                released_at=None,
            )

    monkeypatch.setattr(
        "gitlab_resource.views.get_gitlab_client",
        lambda instance: _FakeGitLabClient(),
    )

    response = authenticated_client.post(
        "/api/v1/gitlab/tags/bulk_create/",
        {
            "project_ids": [project.id],
            "tag_names": ["v1.0.0"],
            "ref": "main",
            "message": "Release 1.0.0",
        },
        format="json",
    )

    assert response.status_code == 200
    assert calls == [
        {
            "project_id": project.gitlab_id,
            "tag_name": "v1.0.0",
            "ref": "main",
            "message": "Release 1.0.0",
        }
    ]


@pytest.mark.django_db
def test_bulk_create_tags_writes_operation_record(
    authenticated_client, registered_projects, monkeypatch
):
    project, _ = registered_projects

    class _FakeGitLabClient:
        def create_tag(self, project_id, tag_name, ref, message=""):
            return _GitLabObject(
                name=tag_name,
                commit_sha="sha",
                released_at=None,
            )

    monkeypatch.setattr(
        "gitlab_resource.views.get_gitlab_client",
        lambda instance: _FakeGitLabClient(),
    )

    response = authenticated_client.post(
        "/api/v1/gitlab/tags/bulk_create/",
        {
            "project_ids": [project.id],
            "tag_names": ["v1.0.0"],
            "ref": "main",
        },
        format="json",
    )
    assert response.status_code == 200

    records_response = authenticated_client.get(
        "/api/v1/gitlab/operation-records/",
        {"action": "tag_create"},
    )

    assert records_response.status_code == 200
    payload = _payload(records_response)
    assert payload["count"] == 1
    record = payload["results"][0]
    assert record["action"] == "tag_create"
    assert record["status"] == "success"
    assert record["actor_name"] == "gitlab-admin"
    assert record["target_summary"] == "1 个项目 / 1 个标签"
    assert record["success_count"] == 1
    assert record["failed_count"] == 0
