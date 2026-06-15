"""Shared username and virtual-email identifier helpers."""

from __future__ import annotations

import re

from django.utils.translation import gettext_lazy as _

from rest_framework import serializers

from platformkit.auth import is_username_available

VIRTUAL_EMAIL_USERNAME_MIN_LENGTH = 3
VIRTUAL_EMAIL_USERNAME_MAX_LENGTH = 64
RESERVED_USERNAMES = (
    "admin",
    "administrator",
    "root",
    "postmaster",
    "webmaster",
    "hostmaster",
    "noreply",
    "no-reply",
    "support",
    "help",
    "info",
    "contact",
)


def normalize_virtual_email_username(value) -> str:
    """Normalize a virtual-email username candidate."""
    return str(value or "").lower().strip()


def validate_virtual_email_username(
    value,
    *,
    availability_checker=is_username_available,
    unavailable_message=None,
):
    """Validate format, reserved words, and uniqueness for a username."""
    normalized = normalize_virtual_email_username(value)

    if not re.match(r"^[a-zA-Z0-9._-]+$", normalized):
        raise serializers.ValidationError(
            _(
                "Username can only contain letters, numbers, "
                "dots, hyphens, and underscores"
            )
        )

    if normalized.startswith(".") or normalized.endswith("."):
        raise serializers.ValidationError(
            _("Username cannot start or end with a dot")
        )

    if normalized in RESERVED_USERNAMES:
        raise serializers.ValidationError(
            _("This username is reserved and cannot be used")
        )

    if not availability_checker(normalized):
        raise serializers.ValidationError(
            unavailable_message or _("This username is already taken")
        )

    return normalized


def validate_virtual_email_alias(alias: str) -> tuple[bool, str]:
    """Return a service-friendly validation result for virtual email aliases."""
    normalized = normalize_virtual_email_username(alias)

    if not normalized:
        return False, "Alias cannot be empty"

    if (
        len(normalized) < VIRTUAL_EMAIL_USERNAME_MIN_LENGTH
        or len(normalized) > VIRTUAL_EMAIL_USERNAME_MAX_LENGTH
    ):
        return False, "Alias must be between 3 and 64 characters"

    try:
        validate_virtual_email_username(
            normalized,
            unavailable_message="This virtual email is already taken",
        )
    except serializers.ValidationError as exc:
        error = exc.detail[0]
        return False, str(error)

    return True, ""
