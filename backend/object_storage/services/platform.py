"""Platform-scoped object-storage configuration and safety gates."""

import copy
import hashlib
import string
from dataclasses import dataclass
from datetime import datetime

from django.db import transaction
from django.utils import timezone

from object_storage.crypto import encrypt_secret
from object_storage.models import (
    AccessKey,
    Bucket,
    CloudIdentity,
    PlatformFeishuConfig,
    PlatformObjectStorageConfig,
    StorageResourcePool,
)


def sync_platform_feishu_access_group(config, *, previous_group_id=None):
    """Apply the singleton Feishu group to existing Feishu identities."""
    from django.contrib.auth.models import Group

    from object_storage.models import FeishuIdentity

    user_ids = list(FeishuIdentity.objects.values_list("user_id", flat=True))
    if previous_group_id and previous_group_id != config.access_group_id:
        previous_group = Group.objects.filter(pk=previous_group_id).first()
        if previous_group is not None:
            previous_group.user_set.remove(*user_ids)
    if config.access_group_id and user_ids:
        config.access_group.user_set.add(*user_ids)
    return config.access_group


DEFAULT_SINGLETON_KEY = "default"
OBJECT_STORAGE_CONFIG_FIELDS = frozenset(
    {
        "naming_template",
        "naming_template_version",
        "default_bucket_quota",
        "delivery_lifetime_seconds",
        "audit_retention_days",
        "pause_new_applications",
        "pause_key_operations",
        "default_bucket_acl",
        "default_storage_class",
        "default_encryption",
        "default_versioning",
        "default_lifecycle",
    }
)
NAMING_TEMPLATE_FIELDS = frozenset(
    {
        "prefix",
        "user",
        "business_name",
        "project",
        "environment",
        "purpose",
        "suffix",
    }
)


class PlatformConfigurationError(RuntimeError):
    """Raised when a platform configuration cannot be safely changed or used."""

    def __init__(self, error_code, *, cause=None):
        self.error_code = error_code
        super().__init__(error_code)
        self.__cause__ = cause


@dataclass(frozen=True)
class PlatformValidationResult:
    """Provider validation data safe to return to callers and logs."""

    account_id: str = ""
    request_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class _ResourcePoolSnapshot:
    provider: str
    cloud_account_id: str
    region: str
    credential_fingerprint: str
    updated_at: datetime


def _feishu_config_fingerprint(config):
    payload = "|".join(
        (
            config.singleton_key,
            config.app_id,
            config.app_secret_encrypted,
            config.oauth_callback_url,
            str(config.access_group_id or ""),
        )
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def get_feishu_config():
    config, _created = PlatformFeishuConfig.objects.get_or_create(
        singleton_key=DEFAULT_SINGLETON_KEY
    )
    return config


def get_object_storage_config():
    config, _created = PlatformObjectStorageConfig.objects.get_or_create(
        singleton_key=DEFAULT_SINGLETON_KEY
    )
    return config


def default_bucket_configuration_snapshot(config=None):
    config = config or get_object_storage_config()
    if config.default_bucket_acl != "private":
        raise PlatformConfigurationError("INVALID_PLATFORM_CONFIG")
    return {
        "acl": config.default_bucket_acl,
        "storage_class": config.default_storage_class,
        "encryption": config.default_encryption,
        "versioning": config.default_versioning,
        "lifecycle": config.default_lifecycle,
    }


def _error_code(exc, default):
    return str(getattr(exc, "error_code", "") or default)


def _resource_pool_snapshot(pool):
    return _ResourcePoolSnapshot(
        provider=pool.provider,
        cloud_account_id=str(pool.cloud_account_id),
        region=pool.region,
        credential_fingerprint=pool.credential_fingerprint,
        updated_at=pool.updated_at,
    )


def _load_resource_pool(pool):
    if pool is None or pool.pk is None:
        raise PlatformConfigurationError("RESOURCE_POOL_REQUIRED")
    return StorageResourcePool.objects.get(pk=pool.pk)


def _lock_resource_pool(pool_id):
    return StorageResourcePool.objects.select_for_update().get(pk=pool_id)


def _assert_pool_snapshot_unchanged(pool, snapshot):
    if _resource_pool_snapshot(pool) != snapshot:
        raise PlatformConfigurationError("CONFIG_CHANGED_DURING_VALIDATION")


def _mark_pool_invalid(pool, error_code):
    pool.validation_status = StorageResourcePool.ValidationStatus.INVALID
    pool.validation_error_code = error_code
    pool.last_validated_at = None
    pool.enabled = False
    pool.save(
        update_fields=(
            "validation_status",
            "validation_error_code",
            "last_validated_at",
            "enabled",
            "updated_at",
        )
    )


def _validator_result(result):
    if isinstance(result, dict):
        account_id = result.get("account_id", "")
        request_ids = result.get("request_ids", ()) or result.get("request_id", "")
    else:
        account_id = getattr(result, "account_id", "")
        request_ids = getattr(result, "request_ids", ())
    if isinstance(request_ids, str):
        request_ids = (request_ids,)
    return PlatformValidationResult(
        account_id=str(account_id or ""),
        request_ids=tuple(str(value) for value in request_ids if value),
    )


def _default_feishu_validator(config):
    from object_storage.feishu import get_feishu_client

    return get_feishu_client().validate_config(config)


def _default_pool_validator(pool):
    from object_storage.providers.aliyun import build_aliyun_provider

    return build_aliyun_provider(pool).validate_management_identity(pool)


def _storage_field_updates(object_storage_fields, keyword_fields):
    updates = {}
    if object_storage_fields is not None:
        if not isinstance(object_storage_fields, dict):
            raise PlatformConfigurationError("INVALID_PLATFORM_CONFIG")
        updates.update(object_storage_fields)
    duplicate_fields = set(updates).intersection(keyword_fields)
    if duplicate_fields:
        raise PlatformConfigurationError("DUPLICATE_PLATFORM_CONFIG_FIELD")
    updates.update(keyword_fields)
    unsupported = set(updates).difference(OBJECT_STORAGE_CONFIG_FIELDS)
    if unsupported:
        raise PlatformConfigurationError("UNSUPPORTED_PLATFORM_CONFIG_FIELD")
    return updates


def _validate_storage_field_values(updates):
    for field, value in updates.items():
        if field == "naming_template":
            valid = _is_valid_naming_template(value)
        elif field == "naming_template_version":
            valid = (
                isinstance(value, int) and not isinstance(value, bool) and value >= 1
            )
        elif field == "default_bucket_quota":
            valid = (
                isinstance(value, int)
                and not isinstance(value, bool)
                and 1 <= value <= 32767
            )
        elif field == "delivery_lifetime_seconds":
            valid = (
                isinstance(value, int)
                and not isinstance(value, bool)
                and 600 <= value <= 604800
            )
        elif field == "audit_retention_days":
            valid = (
                isinstance(value, int)
                and not isinstance(value, bool)
                and 1 <= value <= 3650
            )
        elif field == "default_bucket_acl":
            valid = value == "private"
        elif field in {"default_storage_class", "default_encryption"}:
            valid = isinstance(value, str) and bool(value)
        elif field == "default_lifecycle":
            valid = isinstance(value, (dict, list))
        else:
            valid = isinstance(value, bool)
        if not valid:
            raise PlatformConfigurationError("INVALID_PLATFORM_CONFIG")


def _is_valid_naming_template(value):
    if not isinstance(value, str) or not value or len(value) > 255:
        return False
    fields = []
    try:
        for _literal, field, format_spec, conversion in string.Formatter().parse(value):
            if field is None:
                continue
            if format_spec or conversion or field not in NAMING_TEMPLATE_FIELDS:
                return False
            fields.append(field)
    except ValueError:
        return False
    return "suffix" in fields


def validate_feishu_config(config=None, *, validator=None):
    config = config or get_feishu_config()
    validator = validator or _default_feishu_validator
    with transaction.atomic():
        locked = PlatformFeishuConfig.objects.select_for_update().get(pk=config.pk)
        snapshot = _feishu_config_fingerprint(locked)
    try:
        result = validator(locked)
    except Exception as exc:
        with transaction.atomic():
            current = PlatformFeishuConfig.objects.select_for_update().get(pk=config.pk)
            if _feishu_config_fingerprint(current) != snapshot:
                raise PlatformConfigurationError(
                    "CONFIG_CHANGED_DURING_VALIDATION"
                ) from exc
            current.validation_status = PlatformFeishuConfig.ValidationStatus.INVALID
            current.validation_error_code = _error_code(
                exc, "PROVIDER_VALIDATION_FAILED"
            )
            current.last_validated_at = None
            current.enabled = False
            current.save(
                update_fields=(
                    "validation_status",
                    "validation_error_code",
                    "last_validated_at",
                    "enabled",
                    "updated_at",
                )
            )
        raise PlatformConfigurationError(
            current.validation_error_code, cause=exc
        ) from exc

    with transaction.atomic():
        current = PlatformFeishuConfig.objects.select_for_update().get(pk=config.pk)
        if _feishu_config_fingerprint(current) != snapshot:
            raise PlatformConfigurationError("CONFIG_CHANGED_DURING_VALIDATION")
        current.validation_status = PlatformFeishuConfig.ValidationStatus.VALID
        current.validation_error_code = ""
        current.last_validated_at = timezone.now()
        current.save(
            update_fields=(
                "validation_status",
                "validation_error_code",
                "last_validated_at",
                "updated_at",
            )
        )
    return _validator_result(result)


def validate_resource_pool(pool, *, validator=None):
    selected_pool = _load_resource_pool(pool)
    snapshot = _resource_pool_snapshot(selected_pool)
    validator = validator or _default_pool_validator
    try:
        result = validator(selected_pool)
    except Exception as exc:
        error_code = _error_code(exc, "PROVIDER_VALIDATION_FAILED")
        with transaction.atomic():
            locked_pool = _lock_resource_pool(selected_pool.pk)
            _assert_pool_snapshot_unchanged(locked_pool, snapshot)
            _mark_pool_invalid(locked_pool, error_code)
        raise PlatformConfigurationError(error_code, cause=exc) from exc

    validation = _validator_result(result)
    validation_error = ""
    with transaction.atomic():
        locked_pool = _lock_resource_pool(selected_pool.pk)
        _assert_pool_snapshot_unchanged(locked_pool, snapshot)
        if not validation.account_id:
            validation_error = "CLOUD_ACCOUNT_UNVERIFIED"
        elif validation.account_id != str(locked_pool.cloud_account_id):
            validation_error = "CLOUD_ACCOUNT_MISMATCH"
        if validation_error:
            _mark_pool_invalid(locked_pool, validation_error)
        else:
            locked_pool.validation_status = StorageResourcePool.ValidationStatus.VALID
            locked_pool.validation_error_code = ""
            locked_pool.last_validated_at = timezone.now()
            locked_pool.save(
                update_fields=(
                    "validation_status",
                    "validation_error_code",
                    "last_validated_at",
                    "updated_at",
                )
            )
    if validation_error:
        raise PlatformConfigurationError(validation_error)
    return validation


def validate_and_save_platform_config(
    *,
    feishu_config=None,
    object_storage_config=None,
    resource_pool=None,
    feishu_validator=None,
    pool_validator=None,
    object_storage_fields=None,
    **storage_fields,
):
    """Validate configured providers and persist only safe status metadata."""

    object_storage_config = object_storage_config or get_object_storage_config()
    updates = _storage_field_updates(object_storage_fields, storage_fields)
    _validate_storage_field_values(updates)
    if updates:
        for field, value in updates.items():
            setattr(object_storage_config, field, value)
        object_storage_config.save(update_fields=tuple(updates) + ("updated_at",))

    feishu_result = None
    if feishu_config is not None or feishu_validator is not None:
        feishu_result = validate_feishu_config(
            feishu_config, validator=feishu_validator
        )
    pool_result = None
    if resource_pool is not None or pool_validator is not None:
        pool_result = validate_resource_pool(resource_pool, validator=pool_validator)
    return {"feishu": feishu_result, "resource_pool": pool_result}


def _configured_pool(config):
    return (
        StorageResourcePool.objects.select_for_update()
        .filter(config=config)
        .order_by("id")
        .first()
    )


@transaction.atomic
def enable_platform(
    *, feishu_config=None, object_storage_config=None, resource_pool=None
):
    selected_feishu = feishu_config or get_feishu_config()
    selected_storage = object_storage_config or get_object_storage_config()
    feishu_config = PlatformFeishuConfig.objects.select_for_update().get(
        pk=selected_feishu.pk
    )
    object_storage_config = PlatformObjectStorageConfig.objects.select_for_update().get(
        pk=selected_storage.pk
    )
    if resource_pool is not None:
        pool = _lock_resource_pool(resource_pool.pk)
        if pool.config_id != object_storage_config.pk:
            raise PlatformConfigurationError("RESOURCE_POOL_CONFIG_MISMATCH")
    else:
        pool = _configured_pool(object_storage_config)
    if (
        feishu_config.validation_status != PlatformFeishuConfig.ValidationStatus.VALID
        or pool is None
        or pool.validation_status != StorageResourcePool.ValidationStatus.VALID
    ):
        raise PlatformConfigurationError("CONFIG_NOT_VALIDATED")

    feishu_config.enabled = True
    feishu_config.save(update_fields=("enabled", "updated_at"))
    pool.enabled = True
    pool.save(update_fields=("enabled", "updated_at"))
    return feishu_config, pool


def pause_new_applications(paused=True, *, config=None):
    config = config or get_object_storage_config()
    config.pause_new_applications = bool(paused)
    config.save(update_fields=("pause_new_applications", "updated_at"))
    return config


def pause_key_operations(paused=True, *, config=None):
    config = config or get_object_storage_config()
    config.pause_key_operations = bool(paused)
    config.save(update_fields=("pause_key_operations", "updated_at"))
    return config


def _platform_ready(*, config=None):
    feishu = get_feishu_config()
    storage = config or get_object_storage_config()
    pool = (
        StorageResourcePool.objects.filter(config=storage, enabled=True)
        .order_by("id")
        .first()
    )
    if (
        not feishu.enabled
        or feishu.validation_status != PlatformFeishuConfig.ValidationStatus.VALID
        or pool is None
        or pool.validation_status != StorageResourcePool.ValidationStatus.VALID
    ):
        raise PlatformConfigurationError("CONFIG_NOT_VALIDATED")
    return feishu, storage, pool


def ensure_new_applications_allowed(*, config=None):
    _feishu, storage, _pool = _platform_ready(config=config)
    if storage.pause_new_applications:
        raise PlatformConfigurationError("NEW_APPLICATIONS_PAUSED")
    return storage


def ensure_key_operations_allowed(*, config=None):
    _feishu, storage, _pool = _platform_ready(config=config)
    if storage.pause_key_operations:
        raise PlatformConfigurationError("KEY_OPERATIONS_PAUSED")
    return storage


assert_new_applications_allowed = ensure_new_applications_allowed
assert_key_operations_allowed = ensure_key_operations_allowed


def _has_real_resources(pool):
    return (
        CloudIdentity.objects.filter(resource_pool=pool).exists()
        or Bucket.objects.filter(resource_pool=pool).exists()
        or AccessKey.objects.filter(cloud_identity__resource_pool=pool).exists()
    )


@transaction.atomic
def update_resource_pool(pool, *, provider=None, cloud_account_id=None, region=None):
    locked_pool = _lock_resource_pool(pool.pk)
    provider = locked_pool.provider if provider is None else provider
    cloud_account_id = (
        locked_pool.cloud_account_id
        if cloud_account_id is None
        else str(cloud_account_id)
    )
    if _has_real_resources(locked_pool) and (
        provider != locked_pool.provider
        or cloud_account_id != locked_pool.cloud_account_id
    ):
        raise PlatformConfigurationError("RESOURCE_POOL_ID_LOCKED")
    changes = {}
    if provider != locked_pool.provider:
        changes["provider"] = provider
    if cloud_account_id != locked_pool.cloud_account_id:
        changes["cloud_account_id"] = cloud_account_id
    if region is not None and region != locked_pool.region:
        changes["region"] = region
    if not changes:
        return locked_pool
    for field, value in changes.items():
        setattr(locked_pool, field, value)
    locked_pool.validation_status = StorageResourcePool.ValidationStatus.PENDING
    locked_pool.validation_error_code = ""
    locked_pool.last_validated_at = None
    locked_pool.enabled = False
    locked_pool.save(
        update_fields=tuple(changes)
        + (
            "validation_status",
            "validation_error_code",
            "last_validated_at",
            "enabled",
            "updated_at",
        )
    )
    return locked_pool


def replace_management_credentials(
    pool,
    *,
    access_key,
    secret_key,
    validator=None,
):
    if not isinstance(access_key, str) or not access_key:
        raise PlatformConfigurationError("MANAGEMENT_ACCESS_KEY_REQUIRED")
    if not isinstance(secret_key, str) or not secret_key:
        raise PlatformConfigurationError("MANAGEMENT_SECRET_KEY_REQUIRED")

    selected_pool = _load_resource_pool(pool)
    snapshot = _resource_pool_snapshot(selected_pool)
    candidate = copy.copy(selected_pool)
    candidate.management_access_key_encrypted = encrypt_secret(access_key)
    candidate.management_secret_key_encrypted = encrypt_secret(secret_key)
    candidate.credential_fingerprint = hashlib.sha256(
        access_key.encode("utf-8")
    ).hexdigest()
    candidate.access_key_last_four = access_key[-4:]
    try:
        result = (validator or _default_pool_validator)(candidate)
    except Exception as exc:
        raise PlatformConfigurationError(
            _error_code(exc, "PROVIDER_VALIDATION_FAILED"), cause=exc
        ) from exc
    validation = _validator_result(result)
    with transaction.atomic():
        locked_pool = _lock_resource_pool(selected_pool.pk)
        _assert_pool_snapshot_unchanged(locked_pool, snapshot)
        if not validation.account_id:
            raise PlatformConfigurationError("CLOUD_ACCOUNT_UNVERIFIED")
        if validation.account_id != str(locked_pool.cloud_account_id):
            raise PlatformConfigurationError("CLOUD_ACCOUNT_MISMATCH")

        locked_pool.management_access_key_encrypted = (
            candidate.management_access_key_encrypted
        )
        locked_pool.management_secret_key_encrypted = (
            candidate.management_secret_key_encrypted
        )
        locked_pool.credential_fingerprint = candidate.credential_fingerprint
        locked_pool.access_key_last_four = candidate.access_key_last_four
        locked_pool.validation_status = StorageResourcePool.ValidationStatus.PENDING
        locked_pool.validation_error_code = ""
        locked_pool.last_validated_at = None
        locked_pool.enabled = False
        locked_pool.save(
            update_fields=(
                "management_access_key_encrypted",
                "management_secret_key_encrypted",
                "credential_fingerprint",
                "access_key_last_four",
                "validation_status",
                "validation_error_code",
                "last_validated_at",
                "enabled",
                "updated_at",
            )
        )
    return locked_pool


def update_resource_pool_configuration(
    pool,
    *,
    provider=None,
    cloud_account_id=None,
    region=None,
    access_key=None,
    secret_key=None,
    enabled=None,
    validator=None,
):
    """Validate a complete pool candidate, then commit it with one CAS write."""
    selected_pool = _load_resource_pool(pool)
    snapshot = _resource_pool_snapshot(selected_pool)
    candidate = copy.copy(selected_pool)
    candidate.provider = selected_pool.provider if provider is None else provider
    candidate.cloud_account_id = (
        selected_pool.cloud_account_id
        if cloud_account_id is None
        else str(cloud_account_id)
    )
    candidate.region = selected_pool.region if region is None else region
    credential_changed = access_key is not None or secret_key is not None
    if credential_changed:
        if not isinstance(access_key, str) or not access_key:
            raise PlatformConfigurationError("MANAGEMENT_ACCESS_KEY_REQUIRED")
        if not isinstance(secret_key, str) or not secret_key:
            raise PlatformConfigurationError("MANAGEMENT_SECRET_KEY_REQUIRED")
        candidate.management_access_key_encrypted = encrypt_secret(access_key)
        candidate.management_secret_key_encrypted = encrypt_secret(secret_key)
        candidate.credential_fingerprint = hashlib.sha256(
            access_key.encode("utf-8")
        ).hexdigest()
        candidate.access_key_last_four = access_key[-4:]

    if _has_real_resources(selected_pool) and (
        candidate.provider != selected_pool.provider
        or candidate.cloud_account_id != selected_pool.cloud_account_id
    ):
        raise PlatformConfigurationError("RESOURCE_POOL_ID_LOCKED")
    changed_fields = [
        field
        for field in ("provider", "cloud_account_id", "region")
        if getattr(candidate, field) != getattr(selected_pool, field)
    ]
    changed = bool(changed_fields or credential_changed or enabled is not None)
    if not changed:
        return selected_pool

    validation = None
    if credential_changed:
        try:
            validation = _validator_result(
                (validator or _default_pool_validator)(candidate)
            )
        except Exception as exc:
            raise PlatformConfigurationError(
                _error_code(exc, "PROVIDER_VALIDATION_FAILED"), cause=exc
            ) from exc
        if not validation.account_id:
            raise PlatformConfigurationError("CLOUD_ACCOUNT_UNVERIFIED")
        if validation.account_id != candidate.cloud_account_id:
            raise PlatformConfigurationError("CLOUD_ACCOUNT_MISMATCH")

    with transaction.atomic():
        locked_pool = _lock_resource_pool(selected_pool.pk)
        _assert_pool_snapshot_unchanged(locked_pool, snapshot)
        for field in ("provider", "cloud_account_id", "region"):
            setattr(locked_pool, field, getattr(candidate, field))
        if credential_changed:
            for field in (
                "management_access_key_encrypted",
                "management_secret_key_encrypted",
                "credential_fingerprint",
                "access_key_last_four",
            ):
                setattr(locked_pool, field, getattr(candidate, field))
        connection_changed = bool(changed_fields or credential_changed)
        if connection_changed:
            locked_pool.validation_status = StorageResourcePool.ValidationStatus.PENDING
            locked_pool.validation_error_code = ""
            locked_pool.last_validated_at = None
            locked_pool.enabled = False
        elif enabled is not None:
            if enabled and (
                locked_pool.validation_status
                != StorageResourcePool.ValidationStatus.VALID
            ):
                raise PlatformConfigurationError("VALIDATION_REQUIRED")
            locked_pool.enabled = enabled
        update_fields = list(changed_fields)
        if credential_changed:
            update_fields.extend(
                [
                    "management_access_key_encrypted",
                    "management_secret_key_encrypted",
                    "credential_fingerprint",
                    "access_key_last_four",
                ]
            )
        if connection_changed:
            update_fields.extend(
                [
                    "validation_status",
                    "validation_error_code",
                    "last_validated_at",
                    "enabled",
                ]
            )
        elif enabled is not None:
            update_fields.append("enabled")
        locked_pool.save(
            update_fields=tuple(dict.fromkeys(update_fields)) + ("updated_at",)
        )
    return locked_pool
