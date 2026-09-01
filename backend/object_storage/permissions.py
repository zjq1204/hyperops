from types import SimpleNamespace

from rest_framework.exceptions import APIException, PermissionDenied, ValidationError
from rest_framework.permissions import BasePermission

from accounts.access import get_effective_feature_keys, get_effective_roles
from object_storage.models import (
    CloudIdentity,
    PlatformFeishuConfig,
    StorageResourcePool,
)

TENANT_SCOPE_KEYS = frozenset({"tenant", "tenant_id", "tenant_code", "enterprise"})


class ObjectStorageNotConfigured(PermissionDenied):
    default_detail = "Object storage is not configured"
    default_code = "OBJECT_STORAGE_NOT_CONFIGURED"


class ObjectStorageSuspended(PermissionDenied):
    default_detail = "Object storage access is suspended"
    default_code = "OBJECT_STORAGE_SUSPENDED"


class TenantScopeUnsupported(APIException):
    status_code = 400
    default_detail = "Tenant-scoped object storage APIs are not supported"
    default_code = "TENANT_SCOPE_UNSUPPORTED"


def has_object_storage_admin_access(user):
    """Require an explicit object-storage feature, never Django staff status."""

    if not user or not user.is_authenticated:
        return False
    if "admin_object_storage" not in get_effective_feature_keys(user):
        return False
    if user.is_superuser:
        return True
    roles = get_effective_roles(user)
    if not roles:
        return False
    role_features = get_effective_feature_keys(
        SimpleNamespace(is_staff=False),
        effective_roles=roles,
    )
    return "admin_object_storage" in role_features


class HasObjectStorageAdminAccess(BasePermission):
    def has_permission(self, request, view):
        return has_object_storage_admin_access(request.user)


class HasPlatformObjectStorageAccess(BasePermission):
    """Gate employee APIs on one validated platform pool and user state."""

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        feishu_ready = PlatformFeishuConfig.objects.filter(
            singleton_key="default",
            enabled=True,
            validation_status=PlatformFeishuConfig.ValidationStatus.VALID,
        ).exists()
        pool = (
            StorageResourcePool.objects.filter(
                enabled=True,
                validation_status=StorageResourcePool.ValidationStatus.VALID,
            )
            .select_related("config")
            .order_by("id")
            .first()
        )
        if not feishu_ready or pool is None:
            raise ObjectStorageNotConfigured()
        identity = CloudIdentity.objects.filter(user=user).first()
        if identity is not None and identity.state == CloudIdentity.State.SUSPENDED:
            raise ObjectStorageSuspended()
        request.object_storage_pool = pool
        request.object_storage_config = pool.config
        request.object_storage_identity = identity
        return True


class RejectTenantScopeMixin:
    def initial(self, request, *args, **kwargs):
        if TENANT_SCOPE_KEYS.intersection(
            request.query_params
        ) or TENANT_SCOPE_KEYS.intersection(request.data):
            raise TenantScopeUnsupported()
        return super().initial(request, *args, **kwargs)


class RequireIdempotencyKeyMixin:
    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            key = str(request.headers.get("Idempotency-Key") or "").strip()
            if not key:
                raise ValidationError({"idempotency_key": "IDEMPOTENCY_KEY_REQUIRED"})
            if len(key) > 128:
                raise ValidationError({"idempotency_key": "IDEMPOTENCY_KEY_INVALID"})
            request.idempotency_key = key
