"""Shared user display and authentication metadata helpers."""

from __future__ import annotations

import logging

from platformkit.i18n import normalize_language_code
from platformkit.social import (
    build_social_login_identifier,
    get_primary_social_account,
    get_provider_display_name,
)

logger = logging.getLogger(__name__)

def build_display_name(user) -> str:
    """Return a user-friendly display name with stable fallbacks."""
    profile = getattr(user, "profile", None)
    nickname = (getattr(profile, "nickname", "") or "").strip()
    if nickname:
        return nickname
    if getattr(user, "first_name", None) and getattr(user, "last_name", None):
        return f"{user.first_name} {user.last_name}".strip()
    if getattr(user, "first_name", None):
        return user.first_name.strip()
    return (
        getattr(user, "username", None)
        or getattr(user, "email", None)
        or str(getattr(user, "pk", ""))
    )


def get_virtual_email(_user):
    """Return the primary virtual email address when available."""
    return None


def build_profile_snapshot(profile) -> dict[str, object] | None:
    """Serialize core profile fields for API responses."""
    if profile is None:
        return None
    return {
        "registration_completed": profile.registration_completed,
        "language": profile.language,
        "timezone": profile.timezone,
        "nickname": profile.nickname,
        "avatar_url": profile.avatar_url,
        "jenkins_notification_settings": {
            "recipient_strategy": profile.jenkins_notification_strategy,
            "notification_emails": profile.jenkins_notification_emails,
            "notification_webhooks": profile.jenkins_notification_webhooks,
        },
    }


def build_auth_info(user, *, social_accounts=None) -> dict[str, object]:
    """Build authentication metadata for a user."""
    profile = getattr(user, "profile", None)
    auth_source = getattr(profile, "auth_source", "local")
    auth_info = {
        "method": "email",
        "provider": None,
        "provider_account_id": None,
        "provider_email": None,
        "can_change_password": user.has_usable_password(),
        "login_identifier": None,
    }

    try:
        if auth_source == "ldap":
            auth_info["method"] = "ldap"
            auth_info["provider"] = "LDAP"
            auth_info["can_change_password"] = False
            auth_info["login_identifier"] = (
                getattr(profile, "ldap_uid", None)
                or getattr(user, "username", None)
                or getattr(user, "email", None)
            )
            return auth_info

        social_account = get_primary_social_account(
            user,
            social_accounts=social_accounts,
        )

        if social_account is not None:
            provider_name = get_provider_display_name(social_account.provider)
            auth_info["method"] = "oauth"
            auth_info["provider"] = provider_name
            auth_info["provider_account_id"] = social_account.uid
            auth_info["provider_email"] = social_account.extra_data.get("email")
            auth_info["login_identifier"] = build_social_login_identifier(
                social_account
            )
        else:
            auth_info["login_identifier"] = user.email
    except Exception as exc:
        logger.error(
            "用户认证信息降级 | operation=get_auth_info user_id=%s error_type=%s",
            getattr(user, "id", None),
            type(exc).__name__,
            exc_info=True,
        )

    return auth_info


def upsert_profile_preferences(
    user,
    *,
    profile_model,
    profile_language=None,
    profile_timezone=None,
    preferred_platform=None,
    default_language="zh-CN",
    default_timezone="Asia/Shanghai",
    normalize_platform=None,
):
    """Create or update profile preferences with stable defaults."""
    profile, _ = profile_model.objects.get_or_create(
        user=user,
        defaults={
            "language": default_language,
            "timezone": default_timezone,
        },
    )

    update_fields = []
    if profile_language is not None:
        profile.language = normalize_language_code(profile_language)
        update_fields.append("language")
    if profile_timezone is not None:
        profile.timezone = str(profile_timezone).strip() or default_timezone
        update_fields.append("timezone")
    if preferred_platform is not None and normalize_platform is not None:
        profile.preferred_platform = normalize_platform(preferred_platform)
        update_fields.append("preferred_platform")

    if update_fields:
        profile.save(update_fields=update_fields)

    return profile, update_fields
