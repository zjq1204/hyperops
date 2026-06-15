"""
GitLab Resource app configuration.
"""

from django.apps import AppConfig


class GitlabResourceConfig(AppConfig):
    """Configuration for GitLab Resource app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "gitlab_resource"
    verbose_name = "GitLab 资源管理"
