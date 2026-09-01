from django.conf import settings
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.db import models, router, transaction
from django.db.models import Q


class AuditEventImmutableError(RuntimeError):
    """Raised when an immutable object-storage audit event is changed."""


class ApplicationEventImmutableError(RuntimeError):
    """Raised when an immutable application event is changed."""


class TimestampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


def default_feishu_visible_features():
    """Keep the callable referenced by historical migration 0003 importable."""
    return ["workspace_dashboard", "object_storage"]


class PlatformFeishuConfig(TimestampedModel):
    class ValidationStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        VALID = "valid", "Valid"
        INVALID = "invalid", "Invalid"

    singleton_key = models.CharField(max_length=32, unique=True, default="default")
    app_id = models.CharField(max_length=160, blank=True, default="")
    app_secret_encrypted = models.TextField(blank=True, default="")
    oauth_callback_url = models.URLField(max_length=512, blank=True, default="")
    access_group = models.ForeignKey(
        Group,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="platform_feishu_configs",
        help_text=(
            "Local group whose roles are granted to users signing in through " "Feishu."
        ),
    )
    validation_status = models.CharField(
        max_length=16,
        choices=ValidationStatus.choices,
        default=ValidationStatus.PENDING,
    )
    validation_error_code = models.CharField(max_length=64, blank=True, default="")
    last_validated_at = models.DateTimeField(null=True, blank=True)
    enabled = models.BooleanField(default=False)

    class Meta:
        ordering = ["singleton_key"]
        constraints = [
            models.CheckConstraint(
                condition=Q(singleton_key="default"),
                name="storage_feishu_singleton_key",
            )
        ]

    def __str__(self):
        return "Platform Feishu configuration"


class PlatformObjectStorageConfig(TimestampedModel):
    singleton_key = models.CharField(max_length=32, unique=True, default="default")
    naming_template = models.CharField(
        max_length=255,
        default="hyperops-{user}-{business_name}-{environment}-{suffix}",
    )
    naming_template_version = models.PositiveIntegerField(default=1)
    default_bucket_quota = models.PositiveSmallIntegerField(default=5)
    delivery_lifetime_seconds = models.PositiveIntegerField(default=86400)
    audit_retention_days = models.PositiveSmallIntegerField(default=30)
    pause_new_applications = models.BooleanField(default=True)
    pause_key_operations = models.BooleanField(default=True)
    default_bucket_acl = models.CharField(max_length=20, default="private")
    default_storage_class = models.CharField(max_length=32, default="Standard")
    default_encryption = models.CharField(max_length=32, default="AES256")
    default_versioning = models.BooleanField(default=False)
    default_lifecycle = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["singleton_key"]
        constraints = [
            models.CheckConstraint(
                condition=Q(singleton_key="default"),
                name="storage_object_singleton_key",
            ),
            models.CheckConstraint(
                condition=Q(default_bucket_quota__gte=1),
                name="storage_platform_quota_positive",
            ),
            models.CheckConstraint(
                condition=Q(
                    delivery_lifetime_seconds__gte=600,
                    delivery_lifetime_seconds__lte=604800,
                ),
                name="storage_platform_delivery_lifetime_range",
            ),
            models.CheckConstraint(
                condition=Q(
                    audit_retention_days__gte=1,
                    audit_retention_days__lte=3650,
                ),
                name="storage_platform_audit_retention_range",
            ),
            models.CheckConstraint(
                condition=Q(default_bucket_acl="private"),
                name="storage_platform_default_acl_private",
            ),
        ]

    def __str__(self):
        return "Platform object storage configuration"


class UserBucketQuota(TimestampedModel):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="object_storage_bucket_quota",
    )
    bucket_quota = models.PositiveSmallIntegerField()

    class Meta:
        ordering = ["user_id"]
        constraints = [
            models.CheckConstraint(
                condition=Q(bucket_quota__gte=1),
                name="storage_user_bucket_quota_positive",
            )
        ]

    def __str__(self):
        return f"{self.user_id}:{self.bucket_quota}"


class StorageResourcePool(TimestampedModel):
    class Provider(models.TextChoices):
        ALIYUN = "aliyun", "Alibaba Cloud"

    class ValidationStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        VALID = "valid", "Valid"
        INVALID = "invalid", "Invalid"

    config = models.ForeignKey(
        PlatformObjectStorageConfig,
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
        ordering = ["provider", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["provider"],
                condition=Q(enabled=True),
                name="storage_pool_one_enabled_provider",
            )
        ]
        indexes = [
            models.Index(
                fields=["provider", "enabled"],
                name="os_pool_provider_enabled_idx",
            )
        ]

    def __str__(self):
        return f"{self.provider}:{self.region}"


class FeishuIdentity(TimestampedModel):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="feishu_identity",
    )
    open_id = models.CharField(max_length=255, unique=True)
    union_id = models.CharField(max_length=255, blank=True, default="", db_index=True)
    display_name = models.CharField(max_length=160)
    department_snapshot = models.JSONField(default=list, blank=True)
    profile_snapshot = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)
    deactivated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["display_name", "id"]
        indexes = [
            models.Index(
                fields=["is_active", "display_name"],
                name="os_feishu_active_name_idx",
            )
        ]

    def __str__(self):
        return self.display_name


class CloudIdentity(TimestampedModel):
    class State(models.TextChoices):
        PROVISIONING = "provisioning", "Provisioning"
        ACTIVE = "active", "Active"
        SUSPENDED = "suspended", "Suspended"
        ERROR = "error", "Error"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="object_storage_cloud_identity",
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
        ordering = ["user_id", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["resource_pool", "ram_user_name"],
                name="storage_identity_pool_ram_name_unique",
            ),
        ]
        indexes = [
            models.Index(
                fields=["user", "state"],
                name="os_identity_user_state_idx",
            )
        ]

    def __str__(self):
        return self.ram_user_name


class Bucket(TimestampedModel):
    class Environment(models.TextChoices):
        DEVELOPMENT = "development", "Development"
        TEST = "test", "Test"
        PRODUCTION = "production", "Production"

    class State(models.TextChoices):
        REQUESTED = "requested", "Requested"
        CREATING = "creating", "Creating"
        WAITING_RETRY = "waiting_retry", "Waiting retry"
        ACTIVE = "active", "Active"
        RELEASING = "releasing", "Releasing"
        PENDING_DELETION = "pending_deletion", "Pending deletion"
        DELETION_BLOCKED = "deletion_blocked", "Deletion blocked"
        RELEASED = "released", "Released"
        FAILED = "failed", "Failed"
        CANCELLED = "cancelled", "Cancelled"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="object_storage_buckets",
    )
    resource_pool = models.ForeignKey(
        StorageResourcePool,
        on_delete=models.PROTECT,
        related_name="buckets",
    )
    cloud_identity = models.ForeignKey(
        CloudIdentity,
        on_delete=models.PROTECT,
        related_name="buckets",
    )
    business_name = models.CharField(max_length=80)
    name = models.CharField(max_length=63)
    project = models.CharField(max_length=80, blank=True, default="")
    environment = models.CharField(
        max_length=20,
        choices=Environment.choices,
        default=Environment.DEVELOPMENT,
    )
    purpose = models.CharField(max_length=255)
    notes = models.TextField(blank=True, default="")
    region = models.CharField(max_length=80)
    template_version = models.PositiveIntegerField(default=1)
    config_snapshot = models.JSONField(default=dict, blank=True)
    cloud_resource_id = models.CharField(max_length=255, blank=True, default="")
    cloud_marker = models.CharField(max_length=255, blank=True, default="")
    state = models.CharField(
        max_length=20,
        choices=State.choices,
        default=State.REQUESTED,
    )
    pending_delete_at = models.DateTimeField(null=True, blank=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)
    desired_config_snapshot = models.JSONField(default=dict, blank=True)
    applied_config_snapshot = models.JSONField(default=dict, blank=True)
    config_error_code = models.CharField(max_length=64, blank=True, default="")
    config_error_summary = models.CharField(max_length=255, blank=True, default="")
    deletion_error_code = models.CharField(max_length=64, blank=True, default="")
    deletion_error_summary = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        ordering = ["owner_id", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["resource_pool", "name"],
                name="storage_bucket_pool_name_unique",
            )
        ]
        indexes = [
            models.Index(
                fields=["owner", "state"],
                name="os_bucket_owner_state_idx",
            ),
            models.Index(
                fields=["resource_pool", "state"],
                name="os_bucket_pool_state_idx",
            ),
            models.Index(
                fields=["state", "pending_delete_at"],
                name="os_bucket_pending_delete_idx",
            ),
        ]

    def __str__(self):
        return self.name


QUOTA_CONSUMING_STATES = (
    Bucket.State.REQUESTED,
    Bucket.State.CREATING,
    Bucket.State.WAITING_RETRY,
    Bucket.State.ACTIVE,
    Bucket.State.RELEASING,
)


class AccessKeyUnsafeBulkMutationError(RuntimeError):
    """Raised when a bulk write would bypass access-key slot enforcement."""


class AccessKeyQuerySet(models.QuerySet):
    GUARDED_UPDATE_FIELDS = frozenset(
        {
            "cloud_identity",
            "cloud_identity_id",
            "cloud_state",
            "local_state",
            "deleted_at",
        }
    )

    def bulk_create(self, objs, *args, **kwargs):
        raise AccessKeyUnsafeBulkMutationError("ACCESS_KEY_BULK_CREATE_REQUIRES_SAVE")

    def update(self, **kwargs):
        if self.GUARDED_UPDATE_FIELDS.intersection(kwargs):
            raise AccessKeyUnsafeBulkMutationError(
                "ACCESS_KEY_STATE_UPDATE_REQUIRES_SAVE"
            )
        return super().update(**kwargs)


class AccessKey(TimestampedModel):
    class CloudState(models.TextChoices):
        ACTIVE = "active", "Active"
        INACTIVE = "inactive", "Inactive"
        DELETED = "deleted", "Deleted"
        UNKNOWN = "unknown", "Unknown"

    class LocalState(models.TextChoices):
        ISSUING = "issuing", "Issuing"
        DELIVERY_READY = "delivery_ready", "Delivery ready"
        ACTIVE = "active", "Active"
        DISABLED = "disabled", "Disabled"
        RETIRING = "retiring", "Retiring"
        RETIRED = "retired", "Retired"
        ERROR = "error", "Error"

    PROVIDER_SLOT_CLOUD_STATES = (
        CloudState.ACTIVE,
        CloudState.INACTIVE,
        CloudState.UNKNOWN,
    )
    PROVIDER_SLOT_LOCAL_STATES = (
        LocalState.ISSUING,
        LocalState.DELIVERY_READY,
        LocalState.ACTIVE,
        LocalState.DISABLED,
        LocalState.RETIRING,
        LocalState.ERROR,
    )

    cloud_identity = models.ForeignKey(
        CloudIdentity,
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
        max_length=24,
        choices=LocalState.choices,
        default=LocalState.ISSUING,
    )
    last_synced_at = models.DateTimeField(null=True, blank=True)
    deactivated_at = models.DateTimeField(null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    objects = AccessKeyQuerySet.as_manager()

    class Meta:
        ordering = ["cloud_identity_id", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["cloud_identity", "access_key_fingerprint"],
                name="storage_access_key_fingerprint_unique",
            )
        ]
        indexes = [
            models.Index(
                fields=["cloud_identity", "local_state"],
                name="os_key_identity_state_idx",
            )
        ]

    def __str__(self):
        return f"****{self.access_key_last_four}"

    @property
    def occupies_provider_slot(self):
        return (
            self.cloud_state in self.PROVIDER_SLOT_CLOUD_STATES
            and self.local_state in self.PROVIDER_SLOT_LOCAL_STATES
            and self.deleted_at is None
        )

    def _validate_provider_slot_limit(self, using):
        if not self.occupies_provider_slot or self.cloud_identity_id is None:
            return
        occupied_slots = (
            type(self)
            .objects.using(using)
            .filter(
                cloud_identity_id=self.cloud_identity_id,
                cloud_state__in=self.PROVIDER_SLOT_CLOUD_STATES,
                local_state__in=self.PROVIDER_SLOT_LOCAL_STATES,
                deleted_at__isnull=True,
            )
            .exclude(pk=self.pk)
            .count()
        )
        if occupied_slots >= 2:
            raise ValidationError({"cloud_identity": "ACCESS_KEY_LIMIT_EXCEEDED"})

    def save(self, *args, **kwargs):
        if not self.occupies_provider_slot or self.cloud_identity_id is None:
            return super().save(*args, **kwargs)

        using = kwargs.get("using") or router.db_for_write(type(self), instance=self)
        with transaction.atomic(using=using):
            (
                CloudIdentity.objects.using(using)
                .select_for_update()
                .only("pk")
                .get(pk=self.cloud_identity_id)
            )
            self._validate_provider_slot_limit(using)
            return super().save(*args, **kwargs)


class ApplicationBatch(TimestampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        RUNNING = "running", "Running"
        SUCCEEDED = "succeeded", "Succeeded"
        PARTIALLY_SUCCEEDED = "partially_succeeded", "Partially succeeded"
        FAILED = "failed", "Failed"
        CANCELLED = "cancelled", "Cancelled"
        MANUAL_REQUIRED = "manual_required", "Manual required"

    applicant = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="object_storage_application_batches",
    )
    idempotency_key = models.CharField(max_length=128)
    payload_digest = models.CharField(max_length=64, blank=True, default="")
    status = models.CharField(
        max_length=24,
        choices=Status.choices,
        default=Status.PENDING,
    )
    current_stage = models.CharField(max_length=48, blank=True, default="")
    item_count = models.PositiveSmallIntegerField(default=0)
    pending_count = models.PositiveSmallIntegerField(default=0)
    success_count = models.PositiveSmallIntegerField(default=0)
    failed_count = models.PositiveSmallIntegerField(default=0)
    error_code = models.CharField(max_length=64, blank=True, default="")
    error_summary = models.CharField(max_length=255, blank=True, default="")
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    issued_access_key = models.ForeignKey(
        AccessKey,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="issued_for_application_batches",
    )
    cloud_identity = models.ForeignKey(
        CloudIdentity,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="application_batches",
    )
    identity_created_by_batch = models.BooleanField(default=False)
    principal_created_by_batch = models.BooleanField(default=False)
    key_created_by_batch = models.BooleanField(default=False)
    running_task_id = models.CharField(max_length=255, blank=True, default="")
    owner_token = models.CharField(
        max_length=64,
        blank=True,
        default="",
        editable=False,
    )
    claim_version = models.PositiveBigIntegerField(default=0, editable=False)
    run_lease_until = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["applicant", "idempotency_key"],
                name="storage_batch_applicant_idempotency_unique",
            )
        ]
        indexes = [
            models.Index(
                fields=["applicant", "status", "-created_at"],
                name="os_batch_applicant_status_idx",
            ),
            models.Index(
                fields=["status", "-created_at"],
                name="os_batch_status_time_idx",
            ),
            models.Index(
                fields=["status", "run_lease_until"],
                name="os_batch_claim_lease_idx",
            ),
        ]

    def __str__(self):
        return f"Application batch {self.pk or 'new'}"


class ApplicationItem(TimestampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        CREATING = "creating", "Creating"
        WAITING_RETRY = "waiting_retry", "Waiting retry"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"
        CANCELLED = "cancelled", "Cancelled"
        MANUAL_REQUIRED = "manual_required", "Manual required"
        RELEASING = "releasing", "Releasing"
        PENDING_DELETE = "pending_delete", "Pending delete"
        DELETE_BLOCKED = "delete_blocked", "Delete blocked"

    batch = models.ForeignKey(
        ApplicationBatch,
        on_delete=models.CASCADE,
        related_name="items",
    )
    business_name = models.CharField(max_length=80)
    project = models.CharField(max_length=80, blank=True, default="")
    environment = models.CharField(
        max_length=20,
        choices=Bucket.Environment.choices,
        default=Bucket.Environment.DEVELOPMENT,
    )
    purpose = models.CharField(max_length=255)
    notes = models.TextField(blank=True, default="")
    initial_suffix = models.CharField(max_length=8, blank=True, default="")
    rendered_bucket_name = models.CharField(max_length=63)
    status = models.CharField(
        max_length=24,
        choices=Status.choices,
        default=Status.PENDING,
    )
    current_stage = models.CharField(max_length=48, blank=True, default="")
    retry_count = models.PositiveSmallIntegerField(default=0)
    error_code = models.CharField(max_length=64, blank=True, default="")
    error_summary = models.CharField(max_length=255, blank=True, default="")
    bucket = models.ForeignKey(
        Bucket,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="application_items",
    )

    class Meta:
        ordering = ["batch_id", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["batch", "rendered_bucket_name"],
                name="storage_item_batch_bucket_name_unique",
            )
        ]
        indexes = [
            models.Index(
                fields=["batch", "status"],
                name="os_item_batch_status_idx",
            )
        ]

    def __str__(self):
        return self.rendered_bucket_name


class ApplicationAttempt(models.Model):
    class Status(models.TextChoices):
        RUNNING = "running", "Running"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"

    application_item = models.ForeignKey(
        ApplicationItem,
        on_delete=models.CASCADE,
        related_name="attempts",
    )
    attempt_number = models.PositiveSmallIntegerField()
    task_id = models.CharField(max_length=255, blank=True, default="")
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.RUNNING,
    )
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    provider_request_id = models.CharField(max_length=255, blank=True, default="")
    error_code = models.CharField(max_length=64, blank=True, default="")

    class Meta:
        ordering = ["application_item_id", "attempt_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["application_item", "attempt_number"],
                name="storage_attempt_number_unique",
            ),
            models.UniqueConstraint(
                fields=["application_item", "task_id"],
                condition=~Q(task_id=""),
                name="storage_attempt_item_task_unique",
            ),
        ]
        indexes = [
            models.Index(
                fields=["status", "-started_at"],
                name="os_attempt_status_time_idx",
            )
        ]

    def __str__(self):
        return f"{self.application_item_id}:{self.attempt_number}"


class ApplicationEventQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ApplicationEventImmutableError("Application events cannot be updated")


class ApplicationEvent(models.Model):
    application_item = models.ForeignKey(
        ApplicationItem,
        on_delete=models.CASCADE,
        related_name="events",
    )
    attempt = models.ForeignKey(
        ApplicationAttempt,
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

    objects = ApplicationEventQuerySet.as_manager()

    class Meta:
        ordering = ["application_item_id", "created_at", "id"]
        indexes = [
            models.Index(
                fields=["application_item", "created_at"],
                name="os_event_item_time_idx",
            )
        ]

    def __str__(self):
        return f"{self.application_item_id}:{self.stage}"

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise ApplicationEventImmutableError("Application events cannot be updated")
        return super().save(*args, **kwargs)


class DeliveryTicket(models.Model):
    class Status(models.TextChoices):
        READY = "ready", "Ready"
        CONSUMED = "consumed", "Consumed"
        EXPIRED = "expired", "Expired"
        REVOKED = "revoked", "Revoked"

    application_batch = models.OneToOneField(
        ApplicationBatch,
        on_delete=models.CASCADE,
        related_name="delivery_ticket",
    )
    access_key = models.ForeignKey(
        AccessKey,
        on_delete=models.PROTECT,
        related_name="delivery_tickets",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="object_storage_delivery_tickets",
    )
    token_digest = models.CharField(max_length=128, unique=True)
    expires_at = models.DateTimeField()
    consumed_at = models.DateTimeField(null=True, blank=True)
    token_rotated_at = models.DateTimeField(null=True, blank=True)
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
                fields=["user", "status", "expires_at"],
                name="os_ticket_user_status_idx",
            )
        ]

    def __str__(self):
        return f"Delivery ticket {self.pk or 'new'}"


class AuditEventQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise AuditEventImmutableError("Audit events cannot be updated")


class AuditEvent(models.Model):
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="object_storage_audit_events",
    )
    actor_id_snapshot = models.PositiveBigIntegerField(null=True, blank=True)
    actor_name_snapshot = models.CharField(max_length=160, blank=True, default="")
    action = models.CharField(max_length=120)
    target_type = models.CharField(max_length=120)
    target_id = models.CharField(max_length=255)
    reason = models.CharField(max_length=500, blank=True, default="")
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    request_id = models.CharField(max_length=128, blank=True, default="")
    result = models.CharField(max_length=64)
    safe_metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = AuditEventQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["-created_at"], name="os_audit_time_idx"),
            models.Index(
                fields=["action", "-created_at"],
                name="os_audit_action_time_idx",
            ),
        ]

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise AuditEventImmutableError("Audit events cannot be updated")
        if self.actor_id is not None:
            self.actor_id_snapshot = self.actor_id
            self.actor_name_snapshot = (
                self.actor.get_full_name() or self.actor.get_username()
            )
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.action}:{self.target_type}:{self.target_id}"


OBJECT_STORAGE_BUSINESS_MODELS = (
    PlatformFeishuConfig,
    PlatformObjectStorageConfig,
    UserBucketQuota,
    StorageResourcePool,
    FeishuIdentity,
    CloudIdentity,
    Bucket,
    AccessKey,
    ApplicationBatch,
    ApplicationItem,
    ApplicationAttempt,
    ApplicationEvent,
    DeliveryTicket,
    AuditEvent,
)
