from types import SimpleNamespace

from django.core.exceptions import ObjectDoesNotExist
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import BasePermission

from accounts.access import get_effective_feature_keys, get_effective_roles


class ObjectStorageNotConfigured(PermissionDenied):
    default_detail = "Object storage is not configured"
    default_code = "OBJECT_STORAGE_NOT_CONFIGURED"


class ObjectStorageSuspended(PermissionDenied):
    default_detail = "Object storage access is suspended"
    default_code = "OBJECT_STORAGE_SUSPENDED"


def has_object_storage_admin_access(user):
    """Require an explicit object-storage feature, not Django staff status."""

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


class IsObjectStorageSuperuser(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_superuser)


class HasObjectStorageAdminAccess(BasePermission):
    """Allow users granted the object-storage administration feature."""

    def has_permission(self, request, view):
        return has_object_storage_admin_access(request.user)


class IsActiveObjectStorageMember(BasePermission):
    message = "Object storage membership is inactive"

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        try:
            membership = user.object_storage_membership
        except (AttributeError, ObjectDoesNotExist):
            raise ObjectStorageNotConfigured()
        if not membership.is_active or not membership.tenant.enabled:
            raise ObjectStorageNotConfigured()
        try:
            identity = user.object_storage_cloud_identity
        except (AttributeError, ObjectDoesNotExist):
            identity = None
        if identity is not None and identity.state == "suspended":
            raise ObjectStorageSuspended()
        request.storage_membership = membership
        return True


class RequireIdempotencyKeyMixin:
    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            key = str(request.headers.get("Idempotency-Key") or "").strip()
            if not key:
                raise ValidationError({"idempotency_key": "IDEMPOTENCY_KEY_REQUIRED"})
