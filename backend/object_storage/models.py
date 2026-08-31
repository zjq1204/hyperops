from django.conf import settings
from django.db import models
from django.db.models import Q


class StorageAuditEventImmutableError(RuntimeError):
    """Raised when an immutable object-storage audit event is changed."""


class StorageApplicationEventImmutableError(RuntimeError):
    """Raised when an immutable application event is changed."""


class TimestampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class StorageTenant(TimestampedModel):
    code = models.SlugField(max_length=80, unique=True)
    name = models.CharField(max_length=160)
    enabled = models.BooleanField(default=True)
    bucket_naming_template = models.CharField(
        max_length=255,
        default="{tenant}-{user}-{project}-{environment}-{suffix}",
    )
    naming_template_version = models.PositiveIntegerField(default=1)
    default_bucket_quota = models.PositiveSmallIntegerField(default=5)
    delivery_lifetime_seconds = models.PositiveIntegerField(default=86400)
    audit_retention_days = models.PositiveSmallIntegerField(default=30)

    class Meta:
        ordering = ["name", "id"]
        constraints = [
            models.CheckConstraint(
                condition=Q(default_bucket_quota__gte=1),
                name="storage_tenant_quota_positive",
            ),
            models.CheckConstraint(
                condition=Q(
                    delivery_lifetime_seconds__gte=600,
                    delivery_lifetime_seconds__lte=604800,
                ),
                name="storage_tenant_delivery_lifetime_range",
            ),
            models.CheckConstraint(
                condition=Q(audit_retention_days=30),
                name="storage_tenant_audit_retention_phase_one",
            ),
        ]

    def __str__(self):
        return self.name


class FeishuAppConfig(TimestampedModel):
    class ValidationStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        VALID = "valid", "Valid"
        INVALID = "invalid", "Invalid"

    tenant = models.OneToOneField(
        StorageTenant,
        on_delete=models.CASCADE,
        related_name="feishu_app_config",
    )
    app_id = models.CharField(max_length=160)
    app_secret_encrypted = models.TextField()
    oauth_callback_url = models.URLField(max_length=512)
    validation_status = models.CharField(
        max_length=16,
        choices=ValidationStatus.choices,
        default=ValidationStatus.PENDING,
    )
    validation_error_code = models.CharField(max_length=64, blank=True, default="")
    last_validated_at = models.DateTimeField(null=True, blank=True)
    enabled = models.BooleanField(default=False)

    class Meta:
        ordering = ["tenant_id"]

    def __str__(self):
        return f"Feishu app for {self.tenant}"


class StorageMembership(TimestampedModel):
    tenant = models.ForeignKey(
        StorageTenant,
        on_delete=models.PROTECT,
        related_name="memberships",
    )
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="object_storage_membership",
    )
    feishu_open_id = models.CharField(max_length=255)
    feishu_union_id = models.CharField(max_length=255, blank=True, default="")
    display_name = models.CharField(max_length=160)
    department_snapshot = models.JSONField(default=list, blank=True)
    profile_snapshot = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)
    deactivated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["tenant_id", "display_name", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "feishu_open_id"],
                name="storage_member_tenant_open_id_unique",
            )
        ]
        indexes = [
            models.Index(
                fields=["tenant", "is_active"],
                name="os_member_tenant_active_idx",
            ),
            models.Index(
                fields=["tenant", "feishu_union_id"],
                name="os_member_tenant_union_idx",
            ),
        ]

    def __str__(self):
        return f"{self.display_name} ({self.tenant.code})"


class StorageResourcePool(TimestampedModel):
    class Provider(models.TextChoices):
        ALIYUN = "aliyun", "Alibaba Cloud"

    class ValidationStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        VALID = "valid", "Valid"
        INVALID = "invalid", "Invalid"

    tenant = models.ForeignKey(
        StorageTenant,
        on_delete=models.PROTECT,
        related_name="resource_pools",
    )
    provider = models.CharField(
        max_length=20,
        choices=Provider.choices,
        default=Provider.ALIYUN,
    )
    cloud_account_id = models.CharField(max_length=160)
    region = models.CharField(max_length=80)
    management_access_key_encrypted = models.TextField()
    management_secret_key_encrypted = models.TextField()
    credential_fingerprint = models.CharField(max_length=128)
    access_key_last_four = models.CharField(max_length=4)
    validation_status = models.CharField(
        max_length=16,
        choices=ValidationStatus.choices,
        default=ValidationStatus.PENDING,
    )
    validation_error_code = models.CharField(max_length=64, blank=True, default="")
    last_validated_at = models.DateTimeField(null=True, blank=True)
    enabled = models.BooleanField(default=False)

    class Meta:
        ordering = ["tenant_id", "provider", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "provider"],
                condition=Q(enabled=True),
                name="storage_pool_one_enabled_provider",
            )
        ]
        indexes = [
            models.Index(
                fields=["tenant", "provider", "enabled"],
                name="os_pool_tenant_provider_idx",
            )
        ]

    def __str__(self):
        return f"{self.tenant.code}:{self.provider}:{self.region}"


class StorageCloudIdentity(TimestampedModel):
    class State(models.TextChoices):
        PROVISIONING = "provisioning", "Provisioning"
        ACTIVE = "active", "Active"
        SUSPENDED = "suspended", "Suspended"
        ERROR = "error", "Error"

    tenant = models.ForeignKey(
        StorageTenant,
        on_delete=models.PROTECT,
        related_name="cloud_identities",
    )
    membership = models.ForeignKey(
        StorageMembership,
        on_delete=models.PROTECT,
        related_name="cloud_identities",
    )
    resource_pool = models.ForeignKey(
        StorageResourcePool,
        on_delete=models.PROTECT,
        related_name="cloud_identities",
    )
    ram_user_id = models.CharField(max_length=255, blank=True, default="")
    ram_user_name = models.CharField(max_length=128)
    state = models.CharField(
        max_length=20,
        choices=State.choices,
        default=State.PROVISIONING,
    )
    last_synced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["tenant_id", "membership_id", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "membership", "resource_pool"],
                name="storage_identity_member_pool_unique",
            ),
            models.UniqueConstraint(
                fields=["resource_pool", "ram_user_name"],
                name="storage_identity_pool_ram_name_unique",
            ),
        ]
        indexes = [
            models.Index(
                fields=["tenant", "membership", "state"],
                name="os_identity_member_state_idx",
            )
        ]

    def __str__(self):
        return self.ram_user_name


class StorageBucket(TimestampedModel):
    class Environment(models.TextChoices):
        DEVELOPMENT = "development", "Development"
        TEST = "test", "Test"
        PRODUCTION = "production", "Production"

    class State(models.TextChoices):
        REQUESTED = "requested", "Requested"
        CREATING = "creating", "Creating"
        ACTIVE = "active", "Active"
        RELEASING = "releasing", "Releasing"
        RELEASED = "released", "Released"
        FAILED = "failed", "Failed"

    tenant = models.ForeignKey(
        StorageTenant,
        on_delete=models.PROTECT,
        related_name="buckets",
    )
    resource_pool = models.ForeignKey(
        StorageResourcePool,
        on_delete=models.PROTECT,
        related_name="buckets",
    )
    owner = models.ForeignKey(
        StorageMembership,
        on_delete=models.PROTECT,
        related_name="buckets",
    )
    cloud_identity = models.ForeignKey(
        StorageCloudIdentity,
        on_delete=models.PROTECT,
        related_name="buckets",
    )
    name = models.CharField(max_length=63)
    project = models.CharField(max_length=80)
    environment = models.CharField(max_length=20, choices=Environment.choices)
    purpose = models.CharField(max_length=255)
    notes = models.TextField(blank=True, default="")
    region = models.CharField(max_length=80)
    template_version = models.PositiveIntegerField(default=1)
    cloud_resource_id = models.CharField(max_length=255, blank=True, default="")
    cloud_marker = models.CharField(max_length=255, blank=True, default="")
    state = models.CharField(
        max_length=20,
        choices=State.choices,
        default=State.REQUESTED,
    )
    last_synced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["tenant_id", "owner_id", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["resource_pool", "name"],
                name="storage_bucket_pool_name_unique",
            )
        ]
        indexes = [
            models.Index(
                fields=["tenant", "owner", "state"],
                name="os_bucket_owner_state_idx",
            ),
            models.Index(
                fields=["resource_pool", "state"],
                name="os_bucket_pool_state_idx",
            ),
        ]

    def __str__(self):
        return self.name


class StorageAccessKey(TimestampedModel):
    class CloudState(models.TextChoices):
        ACTIVE = "active", "Active"
        INACTIVE = "inactive", "Inactive"
        DELETED = "deleted", "Deleted"
        UNKNOWN = "unknown", "Unknown"

    class LocalState(models.TextChoices):
        ISSUING = "issuing", "Issuing"
        DELIVERY_READY = "delivery_ready", "Delivery ready"
        ACTIVE = "active", "Active"
        RETIRING = "retiring", "Retiring"
        RETIRED = "retired", "Retired"
        ERROR = "error", "Error"

    tenant = models.ForeignKey(
        StorageTenant,
        on_delete=models.PROTECT,
        related_name="access_keys",
    )
    cloud_identity = models.ForeignKey(
        StorageCloudIdentity,
        on_delete=models.PROTECT,
        related_name="access_keys",
    )
    access_key_id_encrypted = models.TextField()
    secret_access_key_encrypted = models.TextField()
    access_key_fingerprint = models.CharField(max_length=128)
    access_key_last_four = models.CharField(max_length=4)
    cloud_state = models.CharField(
        max_length=16,
        choices=CloudState.choices,
        default=CloudState.ACTIVE,
    )
    local_state = models.CharField(
        max_length=20,
        choices=LocalState.choices,
        default=LocalState.ISSUING,
    )
    last_synced_at = models.DateTimeField(null=True, blank=True)
    deactivated_at = models.DateTimeField(null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["tenant_id", "cloud_identity_id", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "access_key_fingerprint"],
                name="storage_key_tenant_fingerprint_unique",
            )
        ]
        indexes = [
            models.Index(
                fields=["tenant", "cloud_identity", "local_state"],
                name="os_key_identity_state_idx",
            )
        ]

    def __str__(self):
        return f"AccessKey ending {self.access_key_last_four}"


class StorageApplication(TimestampedModel):
    class ActionType(models.TextChoices):
        FIRST_BUCKET_AND_CREDENTIAL = (
            "first_bucket_and_credential",
            "First bucket and credential",
        )
        ADD_BUCKET = "add_bucket", "Add bucket"
        ROTATE_CREDENTIAL = "rotate_credential", "Rotate credential"
        RELEASE_BUCKET = "release_bucket", "Release bucket"
        SUSPEND_MEMBERSHIP = "suspend_membership", "Suspend membership"
        REACTIVATE_MEMBERSHIP = "reactivate_membership", "Reactivate membership"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        RUNNING = "running", "Running"
        DELIVERY_READY = "delivery_ready", "Delivery ready"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"
        MANUAL_REQUIRED = "manual_required", "Manual required"
        CANCELLED = "cancelled", "Cancelled"

    tenant = models.ForeignKey(
        StorageTenant,
        on_delete=models.PROTECT,
        related_name="applications",
    )
    applicant = models.ForeignKey(
        StorageMembership,
        on_delete=models.PROTECT,
        related_name="applications",
    )
    action_type = models.CharField(max_length=40, choices=ActionType.choices)
    target_bucket = models.ForeignKey(
        StorageBucket,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="applications",
    )
    target_access_key = models.ForeignKey(
        StorageAccessKey,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="applications",
    )
    idempotency_key = models.CharField(max_length=128)
    request_fields = models.JSONField(default=dict, blank=True)
    status = models.CharField(
        max_length=24,
        choices=Status.choices,
        default=Status.PENDING,
    )
    current_stage = models.CharField(max_length=48, blank=True, default="")
    error_code = models.CharField(max_length=64, blank=True, default="")
    error_summary = models.CharField(max_length=255, blank=True, default="")
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "applicant", "idempotency_key"],
                name="storage_application_idempotency_unique",
            )
        ]
        indexes = [
            models.Index(
                fields=["tenant", "applicant", "status", "-created_at"],
                name="os_app_applicant_status_idx",
            ),
            models.Index(
                fields=["tenant", "status", "-created_at"],
                name="os_app_tenant_status_idx",
            ),
        ]

    def __str__(self):
        return f"{self.action_type}:{self.pk or 'new'}"


class StorageApplicationAttempt(models.Model):
    class Status(models.TextChoices):
        RUNNING = "running", "Running"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"

    tenant = models.ForeignKey(
        StorageTenant,
        on_delete=models.PROTECT,
        related_name="application_attempts",
    )
    application = models.ForeignKey(
        StorageApplication,
        on_delete=models.CASCADE,
        related_name="attempts",
    )
    attempt_number = models.PositiveSmallIntegerField()
    celery_task_id = models.CharField(max_length=255, blank=True, default="")
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.RUNNING,
    )
    provider_request_id = models.CharField(max_length=255, blank=True, default="")
    error_code = models.CharField(max_length=64, blank=True, default="")
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["application_id", "attempt_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["application", "attempt_number"],
                name="storage_attempt_number_unique",
            )
        ]
        indexes = [
            models.Index(
                fields=["tenant", "status", "-started_at"],
                name="os_attempt_tenant_status_idx",
            )
        ]

    def __str__(self):
        return f"{self.application_id}:{self.attempt_number}"


class StorageApplicationEventQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise StorageApplicationEventImmutableError(
            "Application events cannot be updated"
        )


class StorageApplicationEvent(models.Model):
    tenant = models.ForeignKey(
        StorageTenant,
        on_delete=models.PROTECT,
        related_name="application_events",
    )
    application = models.ForeignKey(
        StorageApplication,
        on_delete=models.CASCADE,
        related_name="events",
    )
    attempt = models.ForeignKey(
        StorageApplicationAttempt,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="events",
    )
    stage = models.CharField(max_length=48)
    result = models.CharField(max_length=24)
    error_code = models.CharField(max_length=64, blank=True, default="")
    safe_metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = StorageApplicationEventQuerySet.as_manager()

    class Meta:
        ordering = ["application_id", "created_at", "id"]
        indexes = [
            models.Index(
                fields=["tenant", "application", "created_at"],
                name="os_event_application_time_idx",
            )
        ]

    def __str__(self):
        return f"{self.application_id}:{self.stage}"

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise StorageApplicationEventImmutableError(
                "Application events cannot be updated"
            )
        return super().save(*args, **kwargs)


class StorageDeliveryTicket(models.Model):
    class Status(models.TextChoices):
        READY = "ready", "Ready"
        CONSUMED = "consumed", "Consumed"
        EXPIRED = "expired", "Expired"
        REVOKED = "revoked", "Revoked"

    tenant = models.ForeignKey(
        StorageTenant,
        on_delete=models.PROTECT,
        related_name="delivery_tickets",
    )
    application = models.OneToOneField(
        StorageApplication,
        on_delete=models.CASCADE,
        related_name="delivery_ticket",
    )
    access_key = models.ForeignKey(
        StorageAccessKey,
        on_delete=models.PROTECT,
        related_name="delivery_tickets",
    )
    membership = models.ForeignKey(
        StorageMembership,
        on_delete=models.PROTECT,
        related_name="delivery_tickets",
    )
    token_digest = models.CharField(max_length=128, unique=True)
    expires_at = models.DateTimeField()
    consumed_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.READY,
    )
    attempt_count = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(
                fields=["tenant", "membership", "status", "expires_at"],
                name="os_ticket_member_status_idx",
            )
        ]

    def __str__(self):
        return f"Delivery ticket {self.pk or 'new'}"


class StorageAuditEventQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise StorageAuditEventImmutableError("Audit events cannot be updated")


class StorageAuditEvent(models.Model):
    tenant = models.ForeignKey(
        StorageTenant,
        on_delete=models.PROTECT,
        related_name="audit_events",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="object_storage_audit_events",
    )
    application = models.ForeignKey(
        StorageApplication,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="audit_events",
    )
    action = models.CharField(max_length=120)
    target_type = models.CharField(max_length=120)
    target_id = models.CharField(max_length=255)
    reason = models.CharField(max_length=500, blank=True, default="")
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    request_id = models.CharField(max_length=128, blank=True, default="")
    result = models.CharField(max_length=64)
    safe_metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = StorageAuditEventQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(
                fields=["tenant", "-created_at"],
                name="os_audit_tenant_time_idx",
            ),
            models.Index(
                fields=["tenant", "action", "-created_at"],
                name="os_audit_tenant_action_idx",
            ),
        ]

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise StorageAuditEventImmutableError("Audit events cannot be updated")
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.action}:{self.target_type}:{self.target_id}"


OBJECT_STORAGE_BUSINESS_MODELS = (
    FeishuAppConfig,
    StorageMembership,
    StorageResourcePool,
    StorageCloudIdentity,
    StorageBucket,
    StorageAccessKey,
    StorageApplication,
    StorageApplicationAttempt,
    StorageApplicationEvent,
    StorageDeliveryTicket,
    StorageAuditEvent,
)
