from django.core.exceptions import ObjectDoesNotExist
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import BasePermission


class IsObjectStorageSuperuser(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_superuser)


class IsActiveObjectStorageMember(BasePermission):
    message = "Object storage membership is inactive"

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        try:
            membership = user.object_storage_membership
        except (AttributeError, ObjectDoesNotExist):
            return False
        if not membership.is_active or not membership.tenant.enabled:
            return False
        request.storage_membership = membership
        return True


class RequireIdempotencyKeyMixin:
    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            key = str(request.headers.get("Idempotency-Key") or "").strip()
            if not key:
                raise ValidationError({"idempotency_key": "IDEMPOTENCY_KEY_REQUIRED"})
