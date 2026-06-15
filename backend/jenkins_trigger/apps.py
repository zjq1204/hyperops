"""
Jenkins Trigger app configuration.
"""

from django.apps import AppConfig


class JenkinsTriggerConfig(AppConfig):
    """Configuration for Jenkins Trigger app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "jenkins_trigger"
    verbose_name = "Jenkins 触发"
