"""
GitLab API client.
"""

from dataclasses import dataclass
from typing import Any, Optional

import gitlab
import requests

def _bool_or_default(value, default: bool = False) -> bool:
    """Convert None to default, pass through actual bool values."""
    return default if value is None else bool(value)


@dataclass
class GitLabGroup:
    """GitLab group info."""

    id: int
    name: str
    path: str
    description: str = ""


@dataclass
class GitLabProject:
    """GitLab project info."""

    id: int
    name: str
    path: str
    path_with_namespace: str
    default_branch: str = "main"


@dataclass
class GitLabBranchInfo:
    """GitLab branch info."""

    name: str
    protected: bool
    commit_sha: str
    commit_date: Optional[str] = None


@dataclass
class GitLabTagInfo:
    """GitLab tag info."""

    name: str
    commit_sha: str
    released_at: Optional[str] = None


@dataclass
class GitLabWebhookInfo:
    """GitLab webhook info."""

    id: int
    url: str
    push_events: bool
    tag_push_events: bool
    merge_requests_events: bool
    enable_ssl_verification: bool
    push_events_branch_filter: Optional[str] = None
    issues_events: bool = False
    confidential_issues_events: bool = False
    note_events: bool = False
    confidential_note_events: bool = False
    pipeline_events: bool = False
    job_events: bool = False
    wiki_page_events: bool = False
    deployment_events: bool = False
    releases_events: bool = False
    feature_flag_events: bool = False
    repository_update_events: bool = False
    resource_access_token_events: bool = False
    token: Optional[str] = None
    created_at: Optional[str] = None


class GitLabClient:
    """GitLab API client using python-gitlab."""

    def __init__(self, url: str, private_token: str):
        session = requests.Session()
        session.trust_env = False
        self.gl = gitlab.Gitlab(url=url, private_token=private_token, session=session)

    def test_connection(self) -> bool:
        """Test GitLab connection."""
        try:
            self.gl.auth()
            return True
        except Exception:
            return False

    @staticmethod
    def _list_all(manager: Any, **kwargs) -> list[Any]:
        """Return all pages for a python-gitlab list manager.

        python-gitlab returns only the first page unless an explicit all-page
        flag is provided. Support both current and older keyword names because
        this project already uses both forms in different places.
        """
        try:
            return manager.list(get_all=True, **kwargs)
        except TypeError:
            return manager.list(all=True, **kwargs)

    def list_groups(self) -> list[GitLabGroup]:
        """List all groups."""
        try:
            groups = self._list_all(self.gl.groups)
            return [
                GitLabGroup(
                    id=g.id,
                    name=g.name,
                    path=g.full_path,
                    description=g.description or "",
                )
                for g in groups
            ]
        except Exception:
            raise

    def list_projects_in_group(self, group_id: int) -> list[GitLabProject]:
        """List all projects in a group (including subgroups)."""
        try:
            group = self.gl.groups.get(group_id)
            projects = self._list_all(group.projects, include_subgroups=True)
            result = []
            for p in projects:
                # Get full project details
                full_project = self.gl.projects.get(p.id)
                result.append(
                    GitLabProject(
                        id=full_project.id,
                        name=full_project.name,
                        path=full_project.path,
                        path_with_namespace=full_project.path_with_namespace,
                        default_branch=full_project.default_branch or "main",
                    )
                )
            return result
        except Exception:
            raise

    def list_branches(self, project_id: int) -> list[GitLabBranchInfo]:
        """List all branches of a project."""
        try:
            project = self.gl.projects.get(project_id)
            branches = self._list_all(project.branches)
            result = []
            for b in branches:
                branch = project.branches.get(b.name)
                commit = branch.commit
                commit_date = None
                if commit:
                    commit_date = commit.get("committed_date")
                result.append(
                    GitLabBranchInfo(
                        name=b.name,
                        protected=branch.protected,
                        commit_sha=commit.get("id", "") if commit else "",
                        commit_date=commit_date,
                    )
                )
            return result
        except Exception:
            raise

    def list_tags(self, project_id: int) -> list[GitLabTagInfo]:
        """List all tags of a project."""
        try:
            project = self.gl.projects.get(project_id)
            tags = self._list_all(project.tags)
            result = []
            for t in tags:
                tag = project.tags.get(t.name)
                commit = tag.commit
                result.append(
                    GitLabTagInfo(
                        name=t.name,
                        commit_sha=commit.get("id", "") if commit else "",
                        released_at=tag.commit.get("committed_date") if tag.commit else None,
                    )
                )
            return result
        except Exception:
            raise

    def list_webhooks(self, project_id: int) -> list[GitLabWebhookInfo]:
        """List all webhooks of a project."""
        try:
            project = self.gl.projects.get(project_id)
            hooks = self._list_all(project.hooks)
            results = []
            for h in hooks:
                attrs = h.attributes
                results.append(
                    GitLabWebhookInfo(
                        id=attrs.get("id"),
                        url=attrs.get("url", ""),
                        push_events=attrs.get("push_events") or False,
                        tag_push_events=attrs.get("tag_push_events") or False,
                        merge_requests_events=attrs.get("merge_requests_events") or False,
                        enable_ssl_verification=_bool_or_default(attrs.get("enable_ssl_verification"), True),
                        push_events_branch_filter=attrs.get("push_events_branch_filter") or None,
                        issues_events=attrs.get("issues_events") or False,
                        confidential_issues_events=attrs.get("confidential_issues_events") or False,
                        note_events=attrs.get("note_events") or False,
                        confidential_note_events=attrs.get("confidential_note_events") or False,
                        pipeline_events=attrs.get("pipeline_events") or False,
                        job_events=attrs.get("job_events") or False,
                        wiki_page_events=attrs.get("wiki_page_events") or False,
                        deployment_events=attrs.get("deployment_events") or False,
                        releases_events=attrs.get("releases_events") or False,
                        feature_flag_events=attrs.get("feature_flag_events") or False,
                        repository_update_events=attrs.get("repository_update_events") or False,
                        resource_access_token_events=attrs.get("resource_access_token_events") or False,
                        token=attrs.get("token"),
                        created_at=attrs.get("created_at"),
                    )
                )
            return results
        except Exception:
            raise

    def create_branch(
        self,
        project_id: int,
        branch_name: str,
        ref: str,
    ) -> GitLabBranchInfo:
        """Create a new branch."""
        try:
            project = self.gl.projects.get(project_id)
            branch = project.branches.create({
                "branch": branch_name,
                "ref": ref,
            })
            return GitLabBranchInfo(
                name=branch.name,
                protected=branch.protected,
                commit_sha=branch.commit["id"],
                commit_date=branch.commit.get("committed_date"),
            )
        except Exception:
            raise

    def delete_branch(self, project_id: int, branch_name: str) -> bool:
        """Delete a branch."""
        try:
            project = self.gl.projects.get(project_id)
            project.branches.delete(branch_name)
            return True
        except Exception:
            raise

    def create_tag(
        self,
        project_id: int,
        tag_name: str,
        ref: str,
        message: str = "",
    ) -> GitLabTagInfo:
        """Create a new tag."""
        try:
            project = self.gl.projects.get(project_id)
            payload = {
                "tag_name": tag_name,
                "ref": ref,
            }
            if message:
                payload["message"] = message
            tag = project.tags.create(payload)
            return GitLabTagInfo(
                name=tag.name,
                commit_sha=tag.commit["id"] if tag.commit else "",
                released_at=tag.commit.get("committed_date") if tag.commit else None,
            )
        except Exception:
            raise

    def delete_tag(self, project_id: int, tag_name: str) -> bool:
        """Delete a tag."""
        try:
            project = self.gl.projects.get(project_id)
            project.tags.delete(tag_name)
            return True
        except Exception:
            raise

    def protect_branch(self, project_id: int, branch_name: str) -> bool:
        """Protect a branch."""
        try:
            project = self.gl.projects.get(project_id)
            project.protectedbranches.create({
                "name": branch_name,
                "push_access_level": 40,
                "merge_access_level": 40,
            })
            return True
        except gitlab.exceptions.GitlabCreateError as e:
            if "already been taken" in str(e):
                return True
            raise
        except Exception:
            raise

    def unprotect_branch(self, project_id: int, branch_name: str) -> bool:
        """Unprotect a branch."""
        try:
            project = self.gl.projects.get(project_id)
            project.protectedbranches.delete(branch_name)
            return True
        except Exception:
            raise

    def create_webhook(
        self,
        project_id: int,
        url: str,
        push_events: bool = True,
        tag_push_events: bool = False,
        merge_requests_events: bool = False,
        enable_ssl_verification: bool = True,
        push_events_branch_filter: Optional[str] = None,
        issues_events: bool = False,
        confidential_issues_events: bool = False,
        note_events: bool = False,
        confidential_note_events: bool = False,
        pipeline_events: bool = False,
        job_events: bool = False,
        wiki_page_events: bool = False,
        deployment_events: bool = False,
        releases_events: bool = False,
        feature_flag_events: bool = False,
        repository_update_events: bool = False,
        resource_access_token_events: bool = False,
        token: Optional[str] = None,
    ) -> GitLabWebhookInfo:
        """Create a new webhook."""
        try:
            project = self.gl.projects.get(project_id)
            hook_data = {
                "url": url,
                "push_events": push_events,
                "tag_push_events": tag_push_events,
                "merge_requests_events": merge_requests_events,
                "enable_ssl_verification": enable_ssl_verification,
                "issues_events": issues_events,
                "confidential_issues_events": confidential_issues_events,
                "note_events": note_events,
                "confidential_note_events": confidential_note_events,
                "pipeline_events": pipeline_events,
                "job_events": job_events,
                "wiki_page_events": wiki_page_events,
                "deployment_events": deployment_events,
                "releases_events": releases_events,
                "feature_flag_events": feature_flag_events,
                "repository_update_events": repository_update_events,
                "resource_access_token_events": resource_access_token_events,
            }
            if push_events_branch_filter:
                hook_data["push_events_branch_filter"] = push_events_branch_filter
            if token:
                hook_data["token"] = token

            hook = project.hooks.create(hook_data)
            attrs = hook.attributes
            return GitLabWebhookInfo(
                id=attrs.get("id"),
                url=attrs.get("url", ""),
                push_events=attrs.get("push_events") or False,
                tag_push_events=attrs.get("tag_push_events") or False,
                merge_requests_events=attrs.get("merge_requests_events") or False,
                enable_ssl_verification=_bool_or_default(attrs.get("enable_ssl_verification"), True),
                push_events_branch_filter=attrs.get("push_events_branch_filter") or None,
                issues_events=attrs.get("issues_events") or False,
                confidential_issues_events=attrs.get("confidential_issues_events") or False,
                note_events=attrs.get("note_events") or False,
                confidential_note_events=attrs.get("confidential_note_events") or False,
                pipeline_events=attrs.get("pipeline_events") or False,
                job_events=attrs.get("job_events") or False,
                wiki_page_events=attrs.get("wiki_page_events") or False,
                deployment_events=attrs.get("deployment_events") or False,
                releases_events=attrs.get("releases_events") or False,
                feature_flag_events=attrs.get("feature_flag_events") or False,
                repository_update_events=attrs.get("repository_update_events") or False,
                resource_access_token_events=attrs.get("resource_access_token_events") or False,
                token=attrs.get("token"),
                created_at=attrs.get("created_at"),
            )
        except Exception:
            raise

    def update_webhook(
        self,
        project_id: int,
        hook_id: int,
        url: Optional[str] = None,
        push_events: Optional[bool] = None,
        tag_push_events: Optional[bool] = None,
        merge_requests_events: Optional[bool] = None,
        enable_ssl_verification: Optional[bool] = None,
        push_events_branch_filter: Optional[str] = None,
        issues_events: Optional[bool] = None,
        confidential_issues_events: Optional[bool] = None,
        note_events: Optional[bool] = None,
        confidential_note_events: Optional[bool] = None,
        pipeline_events: Optional[bool] = None,
        job_events: Optional[bool] = None,
        wiki_page_events: Optional[bool] = None,
        deployment_events: Optional[bool] = None,
        releases_events: Optional[bool] = None,
        feature_flag_events: Optional[bool] = None,
        repository_update_events: Optional[bool] = None,
        resource_access_token_events: Optional[bool] = None,
        token: Optional[str] = None,
    ) -> GitLabWebhookInfo:
        """Update a webhook."""
        try:
            project = self.gl.projects.get(project_id)
            hook = project.hooks.get(hook_id)

            if url is not None:
                hook.url = url
            if push_events is not None:
                hook.push_events = push_events
            if tag_push_events is not None:
                hook.tag_push_events = tag_push_events
            if merge_requests_events is not None:
                hook.merge_requests_events = merge_requests_events
            if enable_ssl_verification is not None:
                hook.enable_ssl_verification = enable_ssl_verification
            if push_events_branch_filter is not None:
                hook.push_events_branch_filter = push_events_branch_filter
            if issues_events is not None:
                hook.issues_events = issues_events
            if confidential_issues_events is not None:
                hook.confidential_issues_events = confidential_issues_events
            if note_events is not None:
                hook.note_events = note_events
            if confidential_note_events is not None:
                hook.confidential_note_events = confidential_note_events
            if pipeline_events is not None:
                hook.pipeline_events = pipeline_events
            if job_events is not None:
                hook.job_events = job_events
            if wiki_page_events is not None:
                hook.wiki_page_events = wiki_page_events
            if deployment_events is not None:
                hook.deployment_events = deployment_events
            if releases_events is not None:
                hook.releases_events = releases_events
            if feature_flag_events is not None:
                hook.feature_flag_events = feature_flag_events
            if repository_update_events is not None:
                hook.repository_update_events = repository_update_events
            if resource_access_token_events is not None:
                hook.resource_access_token_events = resource_access_token_events
            if token is not None:
                hook.token = token

            hook.save()
            attrs = hook.attributes
            return GitLabWebhookInfo(
                id=attrs.get("id"),
                url=attrs.get("url", ""),
                push_events=attrs.get("push_events") or False,
                tag_push_events=attrs.get("tag_push_events") or False,
                merge_requests_events=attrs.get("merge_requests_events") or False,
                enable_ssl_verification=_bool_or_default(attrs.get("enable_ssl_verification"), True),
                push_events_branch_filter=attrs.get("push_events_branch_filter") or None,
                issues_events=attrs.get("issues_events") or False,
                confidential_issues_events=attrs.get("confidential_issues_events") or False,
                note_events=attrs.get("note_events") or False,
                confidential_note_events=attrs.get("confidential_note_events") or False,
                pipeline_events=attrs.get("pipeline_events") or False,
                job_events=attrs.get("job_events") or False,
                wiki_page_events=attrs.get("wiki_page_events") or False,
                deployment_events=attrs.get("deployment_events") or False,
                releases_events=attrs.get("releases_events") or False,
                feature_flag_events=attrs.get("feature_flag_events") or False,
                repository_update_events=attrs.get("repository_update_events") or False,
                resource_access_token_events=attrs.get("resource_access_token_events") or False,
                token=attrs.get("token"),
                created_at=attrs.get("created_at"),
            )
        except Exception:
            raise

    def delete_webhook(self, project_id: int, hook_id: int) -> bool:
        """Delete a webhook."""
        try:
            project = self.gl.projects.get(project_id)
            project.hooks.delete(hook_id)
            return True
        except Exception:
            raise
