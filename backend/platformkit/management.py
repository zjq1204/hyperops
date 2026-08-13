"""Shared admin payload assembly helpers."""

from __future__ import annotations

from platformkit.users import build_display_name


def build_group_summary(groups):
    """Serialize lightweight group membership payloads."""
    return [
        {
            "id": getattr(group, "pk", None),
            "name": getattr(group, "name", ""),
        }
        for group in groups
    ]


def build_role_summary(
    role,
    *,
    normalize_features,
    normalize_platform,
    normalize_operations=lambda values: list(values or []),
):
    """Serialize a compact role payload using injected normalizers."""
    return {
        "id": role.pk,
        "name": role.name,
        "visible_features": normalize_features(role.visible_features),
        "operation_permissions": normalize_operations(
            getattr(role, "operation_permissions", [])
        ),
        "preferred_platform": normalize_platform(role.preferred_platform),
        "is_active": role.is_active,
    }


def build_role_payload(
    role,
    *,
    normalize_features,
    normalize_platform,
    normalize_operations=lambda values: list(values or []),
    user_count=None,
    group_count=None,
):
    """Serialize a role payload for management list/detail responses."""
    payload = build_role_summary(
        role,
        normalize_features=normalize_features,
        normalize_platform=normalize_platform,
        normalize_operations=normalize_operations,
    )
    payload.update(
        {
            "user_count": (
                user_count
                if user_count is not None
                else getattr(role, "user_count", role.users.count())
            ),
            "group_count": (
                group_count
                if group_count is not None
                else getattr(role, "group_count", role.groups.count())
            ),
        }
    )
    return payload


def build_group_payload(
    group,
    *,
    roles,
    role_serializer,
    user_count=None,
    permission_count=None,
):
    """Serialize a group payload for management list/detail responses."""
    try:
        notification_config = group.jenkins_notification_config
    except Exception:
        notification_config = None
    return {
        "id": group.pk,
        "name": group.name,
        "user_count": (
            user_count
            if user_count is not None
            else getattr(group, "user_count", group.user_set.count())
        ),
        "permission_count": (
            permission_count
            if permission_count is not None
            else getattr(
                group,
                "permission_count",
                group.permissions.count(),
            )
        ),
        "roles": [role_serializer(role) for role in roles],
        "jenkins_notification_settings": {
            "notification_emails": (
                getattr(notification_config, "notification_emails", []) or []
            ),
            "notification_webhooks": (
                getattr(notification_config, "notification_webhooks", []) or []
            ),
        },
    }


def build_user_payload(
    user,
    *,
    profile=None,
    groups=None,
    direct_roles=None,
    effective_roles=None,
    role_serializer,
    access_profile_builder,
    normalize_platform,
    default_language="zh-CN",
    default_timezone="Asia/Shanghai",
):
    """Serialize a user payload for management list/detail responses."""
    resolved_groups = list(groups or [])
    resolved_direct_roles = list(direct_roles or [])
    resolved_effective_roles = list(effective_roles or [])

    language = default_language
    timezone = default_timezone
    preferred_platform = ""
    auth_source = "local"
    ldap_last_synced_at = None
    if profile is not None:
        language = getattr(profile, "language", None) or default_language
        timezone = getattr(profile, "timezone", None) or default_timezone
        preferred_platform = normalize_platform(
            getattr(profile, "preferred_platform", "")
        )
        auth_source = getattr(profile, "auth_source", "local") or "local"
        ldap_last_synced_at = getattr(profile, "ldap_last_synced_at", None)

    return {
        "id": user.pk,
        "username": (
            getattr(user, "username", None)
            or getattr(user, "email", None)
            or str(user.pk)
        ),
        "email": getattr(user, "email", None) or "",
        "first_name": getattr(user, "first_name", None) or "",
        "last_name": getattr(user, "last_name", None) or "",
        "display_name": build_display_name(user),
        "is_staff": getattr(user, "is_staff", False),
        "is_active": getattr(user, "is_active", True),
        "date_joined": (
            user.date_joined.isoformat()
            if getattr(user, "date_joined", None)
            else None
        ),
        "language": language,
        "timezone": timezone,
        "preferred_platform": preferred_platform,
        "auth_source": auth_source,
        "ldap_last_synced_at": (
            ldap_last_synced_at.isoformat()
            if ldap_last_synced_at is not None
            else None
        ),
        "groups": build_group_summary(resolved_groups),
        "roles": [
            role_serializer(role)
            for role in resolved_direct_roles
        ],
        "effective_roles": [
            role_serializer(role)
            for role in resolved_effective_roles
        ],
        "access_profile": access_profile_builder(
            user,
            direct_roles=resolved_direct_roles,
            groups=resolved_groups,
            effective_roles=resolved_effective_roles,
        ),
    }
