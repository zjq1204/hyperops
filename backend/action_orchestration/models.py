from django.conf import settings
from django.contrib.auth.models import Group
from django.db import models
from django.db.models import Q


class ActionTemplate(models.Model):
    """Reusable linear action orchestration template."""

    SCOPE_ADMIN = "admin"
    SCOPE_PERSONAL = "personal"
    SCOPE_CHOICES = [
        (SCOPE_ADMIN, "Admin"),
        (SCOPE_PERSONAL, "Personal"),
    ]

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    scope = models.CharField(
        max_length=16,
        choices=SCOPE_CHOICES,
        default=SCOPE_PERSONAL,
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="owned_action_templates",
    )
    is_active = models.BooleanField(default=True)
    parameter_schema = models.JSONField(default=list, blank=True)
    visible_users = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name="visible_action_templates",
    )
    visible_groups = models.ManyToManyField(
        Group,
        blank=True,
        related_name="visible_action_templates",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at", "-id"]

    def __str__(self):
        return self.name


class ActionStep(models.Model):
    """Single linear step in an action template."""

    TYPE_JENKINS_TRIGGER = "jenkins_trigger"
    TYPE_GITLAB_BRANCH_CREATE = "gitlab_branch_create"
    TYPE_GITLAB_BRANCH_OPERATION = "gitlab_branch_operation"
    TYPE_GITLAB_TAG_OPERATION = "gitlab_tag_operation"
    TYPE_GITLAB_WEBHOOK_OPERATION = "gitlab_webhook_operation"
    TYPE_MANUAL_APPROVAL = "manual_approval"
    TYPE_CONDITIONAL_BRANCH = "conditional_branch"
    TYPE_CHOICES = [
        (TYPE_JENKINS_TRIGGER, "Jenkins trigger"),
        (TYPE_GITLAB_BRANCH_CREATE, "GitLab branch create"),
        (TYPE_GITLAB_BRANCH_OPERATION, "GitLab branch operation"),
        (TYPE_GITLAB_TAG_OPERATION, "GitLab tag operation"),
        (TYPE_GITLAB_WEBHOOK_OPERATION, "GitLab webhook operation"),
        (TYPE_MANUAL_APPROVAL, "Manual approval"),
        (TYPE_CONDITIONAL_BRANCH, "Conditional branch"),
    ]

    FAILURE_STOP = "stop"
    FAILURE_CONTINUE = "continue"
    FAILURE_CHOICES = [
        (FAILURE_STOP, "Stop"),
        (FAILURE_CONTINUE, "Continue"),
    ]

    template = models.ForeignKey(
        ActionTemplate,
        on_delete=models.CASCADE,
        related_name="steps",
    )
    name = models.CharField(max_length=255)
    order = models.PositiveIntegerField(default=1)
    action_type = models.CharField(max_length=64, choices=TYPE_CHOICES)
    config = models.JSONField(default=dict, blank=True)
    failure_policy = models.CharField(
        max_length=16,
        choices=FAILURE_CHOICES,
        default=FAILURE_STOP,
    )
    is_archived = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["template_id", "order", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["template", "order"],
                condition=Q(is_archived=False),
                name="unique_active_action_step_order",
            )
        ]

    def __str__(self):
        return f"{self.template_id}:{self.order} {self.name}"


class ActionRun(models.Model):
    """Runtime execution instance for an action template."""

    STATUS_QUEUED = "queued"
    STATUS_RUNNING = "running"
    STATUS_WAITING_APPROVAL = "waiting_approval"
    STATUS_SUCCESS = "success"
    STATUS_FAILED = "failed"
    STATUS_REJECTED = "rejected"
    STATUS_CHOICES = [
        (STATUS_QUEUED, "Queued"),
        (STATUS_RUNNING, "Running"),
        (STATUS_WAITING_APPROVAL, "Waiting approval"),
        (STATUS_SUCCESS, "Success"),
        (STATUS_FAILED, "Failed"),
        (STATUS_REJECTED, "Rejected"),
    ]

    template = models.ForeignKey(
        ActionTemplate,
        on_delete=models.PROTECT,
        related_name="runs",
    )
    triggered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="action_runs",
    )
    input_params = models.JSONField(default=dict, blank=True)
    status = models.CharField(
        max_length=32,
        choices=STATUS_CHOICES,
        default=STATUS_QUEUED,
    )
    current_step = models.ForeignKey(
        ActionStep,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    error_message = models.TextField(blank=True, default="")
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"{self.template.name} #{self.id}"


class ActionStepRun(models.Model):
    """Runtime execution result for one action step."""

    STATUS_PENDING = "pending"
    STATUS_RUNNING = "running"
    STATUS_WAITING_APPROVAL = "waiting_approval"
    STATUS_SUCCESS = "success"
    STATUS_FAILED = "failed"
    STATUS_SKIPPED = "skipped"
    STATUS_REJECTED = "rejected"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_RUNNING, "Running"),
        (STATUS_WAITING_APPROVAL, "Waiting approval"),
        (STATUS_SUCCESS, "Success"),
        (STATUS_FAILED, "Failed"),
        (STATUS_SKIPPED, "Skipped"),
        (STATUS_REJECTED, "Rejected"),
    ]

    run = models.ForeignKey(
        ActionRun,
        on_delete=models.CASCADE,
        related_name="step_runs",
    )
    step = models.ForeignKey(
        ActionStep,
        on_delete=models.PROTECT,
        related_name="step_runs",
    )
    status = models.CharField(
        max_length=32,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
    )
    resolved_config = models.JSONField(default=dict, blank=True)
    output = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True, default="")
    jenkins_record = models.ForeignKey(
        "jenkins_trigger.TriggerRecord",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="action_step_runs",
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="approved_action_step_runs",
    )
    approval_comment = models.TextField(blank=True, default="")
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["run_id", "step__order", "id"]
        unique_together = [("run", "step")]

    def __str__(self):
        return f"{self.run_id}:{self.step_id} {self.status}"
