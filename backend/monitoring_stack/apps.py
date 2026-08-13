from django.apps import AppConfig


class MonitoringStackConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "monitoring_stack"

    def ready(self):
        from monitoring_stack import checks  # noqa: F401

    verbose_name = "Monitoring Stack"
