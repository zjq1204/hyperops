from django.core.exceptions import ObjectDoesNotExist
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
