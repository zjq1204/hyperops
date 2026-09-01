"""Platform-scoped object-storage configuration and safety gates."""

import copy
import hashlib
import string
from dataclasses import dataclass

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


def _error_code(exc, default):
    return str(getattr(exc, "error_code", "") or default)


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
    try:
        result = validator(config)
    except Exception as exc:
        config.validation_status = PlatformFeishuConfig.ValidationStatus.INVALID
        config.validation_error_code = _error_code(exc, "PROVIDER_VALIDATION_FAILED")
        config.last_validated_at = None
        config.enabled = False
        config.save(
            update_fields=(
                "validation_status",
                "validation_error_code",
                "last_validated_at",
                "enabled",
                "updated_at",
            )
        )
        raise PlatformConfigurationError(
            config.validation_error_code, cause=exc
        ) from exc

    config.validation_status = PlatformFeishuConfig.ValidationStatus.VALID
    config.validation_error_code = ""
    config.last_validated_at = timezone.now()
    config.save(
        update_fields=(
            "validation_status",
            "validation_error_code",
            "last_validated_at",
            "updated_at",
        )
    )
    return _validator_result(result)


def validate_resource_pool(pool, *, validator=None):
    validator = validator or _default_pool_validator
    try:
        result = validator(pool)
    except Exception as exc:
        pool.validation_status = StorageResourcePool.ValidationStatus.INVALID
        pool.validation_error_code = _error_code(exc, "PROVIDER_VALIDATION_FAILED")
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
        raise PlatformConfigurationError(pool.validation_error_code, cause=exc) from exc

    validation = _validator_result(result)
    if not validation.account_id:
        pool.validation_status = StorageResourcePool.ValidationStatus.INVALID
        pool.validation_error_code = "CLOUD_ACCOUNT_UNVERIFIED"
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
        raise PlatformConfigurationError("CLOUD_ACCOUNT_UNVERIFIED")
    if validation.account_id != str(pool.cloud_account_id):
        pool.validation_status = StorageResourcePool.ValidationStatus.INVALID
        pool.validation_error_code = "CLOUD_ACCOUNT_MISMATCH"
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
        raise PlatformConfigurationError("CLOUD_ACCOUNT_MISMATCH")

    pool.validation_status = StorageResourcePool.ValidationStatus.VALID
    pool.validation_error_code = ""
    pool.last_validated_at = timezone.now()
    pool.save(
        update_fields=(
            "validation_status",
            "validation_error_code",
            "last_validated_at",
            "updated_at",
        )
    )
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
    feishu_config = feishu_config or get_feishu_config()
    object_storage_config = object_storage_config or get_object_storage_config()
    pool = resource_pool or _configured_pool(object_storage_config)
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


def update_resource_pool(pool, *, provider=None, cloud_account_id=None, region=None):
    provider = pool.provider if provider is None else provider
    cloud_account_id = (
        pool.cloud_account_id if cloud_account_id is None else str(cloud_account_id)
    )
    if _has_real_resources(pool) and (
        provider != pool.provider or cloud_account_id != pool.cloud_account_id
    ):
        raise PlatformConfigurationError("RESOURCE_POOL_ID_LOCKED")
    changes = {}
    if provider != pool.provider:
        changes["provider"] = provider
    if cloud_account_id != pool.cloud_account_id:
        changes["cloud_account_id"] = cloud_account_id
    if region is not None and region != pool.region:
        changes["region"] = region
    if not changes:
        return pool
    for field, value in changes.items():
        setattr(pool, field, value)
    pool.validation_status = StorageResourcePool.ValidationStatus.PENDING
    pool.validation_error_code = ""
    pool.last_validated_at = None
    pool.enabled = False
    pool.save(
        update_fields=tuple(changes)
        + (
            "validation_status",
            "validation_error_code",
            "last_validated_at",
            "enabled",
            "updated_at",
        )
    )
    return pool


def _candidate_account_id(result):
    return _validator_result(result).account_id


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

    candidate = copy.copy(pool)
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
    account_id = _candidate_account_id(result)
    if account_id != str(pool.cloud_account_id):
        raise PlatformConfigurationError("CLOUD_ACCOUNT_MISMATCH")

    pool.management_access_key_encrypted = candidate.management_access_key_encrypted
    pool.management_secret_key_encrypted = candidate.management_secret_key_encrypted
    pool.credential_fingerprint = candidate.credential_fingerprint
    pool.access_key_last_four = candidate.access_key_last_four
    pool.validation_status = StorageResourcePool.ValidationStatus.PENDING
    pool.validation_error_code = ""
    pool.last_validated_at = None
    pool.enabled = False
    pool.save(
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
    return pool
