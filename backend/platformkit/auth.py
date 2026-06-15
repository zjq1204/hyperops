"""Shared authentication serializers and validators."""

import re

from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist
from django.utils.translation import gettext_lazy as _

from rest_framework import serializers


PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 32


def is_username_available(username: str) -> bool:
    """Return whether a username is currently available."""
    return not User.objects.filter(username=username).exists()


def validate_password_strength(password: str) -> str:
    """Validate password length and composition requirements."""
    if len(password) < PASSWORD_MIN_LENGTH:
        raise serializers.ValidationError(
            _("Password must be at least 8 characters long")
        )

    if len(password) > PASSWORD_MAX_LENGTH:
        raise serializers.ValidationError(
            _("Password cannot exceed 32 characters")
        )

    has_letter = re.search(r"[a-zA-Z]", password)
    has_number = re.search(r"[0-9]", password)

    if not (has_letter and has_number):
        raise serializers.ValidationError(
            _("Password must contain both letters and numbers")
        )

    return password


def ensure_password_auth_enabled(user):
    """Ensure the user can authenticate with a local password."""
    profile = getattr(user, "profile", None)
    if getattr(profile, "auth_source", None) == "ldap":
        raise serializers.ValidationError(
            _("LDAP users cannot reset password. Please login with LDAP.")
        )

    if not user.has_usable_password():
        raise serializers.ValidationError(
            _(
                "OAuth users cannot reset password. "
                "Please login with your OAuth provider."
            )
        )

    return user


def get_password_reset_eligible_user(email: str, *, user_model=User):
    """Return a user eligible for password reset or raise validation errors."""
    normalized_email = email.lower().strip()

    try:
        user = user_model.objects.get(email=normalized_email)
    except user_model.DoesNotExist as exc:
        raise serializers.ValidationError(
            _("No user found with this email address")
        ) from exc

    ensure_password_auth_enabled(user)

    try:
        profile = user.profile
    except ObjectDoesNotExist as exc:
        raise serializers.ValidationError(
            _("User profile not found")
        ) from exc

    if not profile.registration_completed:
        raise serializers.ValidationError(
            _("Please complete registration first")
        )

    return user


class SuccessResponseSerializer(serializers.Serializer):
    """Standard success response for API schema definitions."""

    success = serializers.BooleanField(default=True)
    message = serializers.CharField()


class TokenVerificationResponseSerializer(serializers.Serializer):
    """Token verification response with email."""

    success = serializers.BooleanField(default=True)
    email = serializers.EmailField()


class AuthTokenResponseSerializer(serializers.Serializer):
    """Authentication token response payload."""

    access = serializers.CharField(help_text=_("JWT access token"))
    refresh = serializers.CharField(help_text=_("JWT refresh token"))
    user = serializers.DictField(help_text=_("User basic info"))


class UsernameAvailabilityResponseSerializer(serializers.Serializer):
    """Username availability check response."""

    available = serializers.BooleanField()
    username = serializers.CharField()
    message = serializers.CharField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    """Shared request serializer for password reset confirmation."""

    uid = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text=_("User ID encoded in base64"),
    )
    token = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text=_("Password reset token"),
    )
    new_password1 = serializers.CharField(
        required=False,
        allow_blank=True,
        write_only=True,
        style={"input_type": "password"},
        help_text=_("New password"),
    )
    new_password2 = serializers.CharField(
        required=False,
        allow_blank=True,
        write_only=True,
        style={"input_type": "password"},
        help_text=_("Confirm new password"),
    )

    def to_internal_value(self, data):
        """Accept both snake_case and camelCase password field names."""
        normalized = data.copy() if hasattr(data, "copy") else dict(data)

        if "new_password1" not in normalized:
            normalized["new_password1"] = (
                data.get("newPassword1") or
                data.get("new_password_1")
            )

        if "new_password2" not in normalized:
            normalized["new_password2"] = (
                data.get("newPassword2") or
                data.get("new_password_2")
            )

        return super().to_internal_value(normalized)

    def validate(self, attrs):
        """Validate presence, password strength, and confirmation match."""
        required_fields = ("uid", "token", "new_password1", "new_password2")
        if not all(attrs.get(field) for field in required_fields):
            raise serializers.ValidationError(_("All fields are required"))

        attrs["new_password1"] = validate_password_strength(
            attrs["new_password1"]
        )

        if attrs["new_password1"] != attrs["new_password2"]:
            raise serializers.ValidationError(_("Passwords do not match"))

        return attrs
