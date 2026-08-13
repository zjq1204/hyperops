from accounts.access import get_access_profile
from rest_framework.permissions import BasePermission


ACTION_PERMISSIONS = {
    "list": "monitoring_credentials_view",
    "retrieve": "monitoring_credentials_view",
    "create": "monitoring_credentials_manage",
    "rotate": "monitoring_credentials_manage",
    "validate": "monitoring_credentials_manage",
    "activate": "monitoring_credentials_manage",
    "archive": "monitoring_credentials_manage",
    "destroy": "monitoring_credentials_delete",
}


def has_credential_permission(user, key):
    if not user or not user.is_authenticated:
        return False
    profile = get_access_profile(user)
    return (
        "admin_monitoring" in profile.get("visible_features", [])
        and key in profile.get("operation_permissions", [])
    )


class CredentialOperationPermission(BasePermission):
    def has_permission(self, request, view):
        key = ACTION_PERMISSIONS.get(getattr(view, "action", ""))
        return bool(key and has_credential_permission(request.user, key))
