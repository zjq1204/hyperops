"""
GitLab API client.
"""

import logging
from dataclasses import dataclass
from typing import Any, Optional

import gitlab
import requests

logger = logging.getLogger(__name__)


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
        except Exception as e:
            logger.error(f"GitLab connection test failed: {e}")
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
        except Exception as e:
            logger.error(f"Failed to list groups: {e}")
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
        except Exception as e:
            logger.error(f"Failed to list projects in group {group_id}: {e}")
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
        except Exception as e:
            logger.error(f"Failed to list branches for project {project_id}: {e}")
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
        except Exception as e:
            logger.error(f"Failed to list tags for project {project_id}: {e}")
            raise

    def list_webhooks(self, project_id: int) -> list[GitLabWebhookInfo]:
        """List all webhooks of a project."""
        try:
            project = self.gl.projects.get(project_id)
            hooks = self._list_all(project.hooks)
            return [
                GitLabWebhookInfo(
                    id=h.id,
                    url=h.url,
                    push_events=h.push_events,
                    tag_push_events=h.tag_push_events,
                    merge_requests_events=h.merge_requests_events,
                    enable_ssl_verification=h.enable_ssl_verification,
                    push_events_branch_filter=getattr(h, "push_events_branch_filter", None),
                )
                for h in hooks
            ]
        except Exception as e:
            logger.error(f"Failed to list webhooks for project {project_id}: {e}")
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
        except Exception as e:
            logger.error(f"Failed to create branch {branch_name} in project {project_id}: {e}")
            raise

    def delete_branch(self, project_id: int, branch_name: str) -> bool:
        """Delete a branch."""
        try:
            project = self.gl.projects.get(project_id)
            project.branches.delete(branch_name)
            return True
        except Exception as e:
            logger.error(f"Failed to delete branch {branch_name} in project {project_id}: {e}")
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
        except Exception as e:
            logger.error(f"Failed to create tag {tag_name} in project {project_id}: {e}")
            raise

    def delete_tag(self, project_id: int, tag_name: str) -> bool:
        """Delete a tag."""
        try:
            project = self.gl.projects.get(project_id)
            project.tags.delete(tag_name)
            return True
        except Exception as e:
            logger.error(f"Failed to delete tag {tag_name} in project {project_id}: {e}")
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
                logger.warning(f"Branch {branch_name} is already protected")
                return True
            raise
        except Exception as e:
            logger.error(f"Failed to protect branch {branch_name} in project {project_id}: {e}")
            raise

    def unprotect_branch(self, project_id: int, branch_name: str) -> bool:
        """Unprotect a branch."""
        try:
            project = self.gl.projects.get(project_id)
            project.protectedbranches.delete(branch_name)
            return True
        except Exception as e:
            logger.error(f"Failed to unprotect branch {branch_name} in project {project_id}: {e}")
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
            }
            if push_events_branch_filter:
                hook_data["push_events_branch_filter"] = push_events_branch_filter

            hook = project.hooks.create(hook_data)
            return GitLabWebhookInfo(
                id=hook.id,
                url=hook.url,
                push_events=hook.push_events,
                tag_push_events=hook.tag_push_events,
                merge_requests_events=hook.merge_requests_events,
                enable_ssl_verification=hook.enable_ssl_verification,
                push_events_branch_filter=getattr(hook, "push_events_branch_filter", None),
            )
        except Exception as e:
            logger.error(f"Failed to create webhook in project {project_id}: {e}")
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

            hook.save()
            return GitLabWebhookInfo(
                id=hook.id,
                url=hook.url,
                push_events=hook.push_events,
                tag_push_events=hook.tag_push_events,
                merge_requests_events=hook.merge_requests_events,
                enable_ssl_verification=hook.enable_ssl_verification,
                push_events_branch_filter=getattr(hook, "push_events_branch_filter", None),
            )
        except Exception as e:
            logger.error(f"Failed to update webhook {hook_id} in project {project_id}: {e}")
            raise

    def delete_webhook(self, project_id: int, hook_id: int) -> bool:
        """Delete a webhook."""
        try:
            project = self.gl.projects.get(project_id)
            project.hooks.delete(hook_id)
            return True
        except Exception as e:
            logger.error(f"Failed to delete webhook {hook_id} in project {project_id}: {e}")
            raise
