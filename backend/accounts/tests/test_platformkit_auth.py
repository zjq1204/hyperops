from django.contrib.auth.models import User
from django.test import TestCase

from rest_framework import serializers

from accounts.models import Profile
from platformkit.auth import (
    PasswordResetConfirmSerializer,
    ensure_password_auth_enabled,
    get_password_reset_eligible_user,
    is_username_available,
    validate_password_strength,
)


class PlatformKitAuthTests(TestCase):
    def test_is_username_available_returns_false_for_existing_user(self):
        User.objects.create_user(
            username="existing-user",
            email="existing@example.com",
            password="password123",
        )

        self.assertFalse(is_username_available("existing-user"))

    def test_is_username_available_returns_true_for_new_username(self):
        self.assertTrue(is_username_available("new-user"))

    def test_validate_password_strength_accepts_valid_password(self):
        self.assertEqual(
            validate_password_strength("validpass123"),
            "validpass123",
        )

    def test_validate_password_strength_rejects_short_password(self):
        with self.assertRaises(serializers.ValidationError) as exc:
            validate_password_strength("a1b2c3")

        self.assertEqual(
            exc.exception.detail[0],
            "Password must be at least 8 characters long",
        )

    def test_validate_password_strength_rejects_missing_number(self):
        with self.assertRaises(serializers.ValidationError) as exc:
            validate_password_strength("abcdefgh")

        self.assertEqual(
            exc.exception.detail[0],
            "Password must contain both letters and numbers",
        )

    def test_validate_password_strength_rejects_missing_letter(self):
        with self.assertRaises(serializers.ValidationError) as exc:
            validate_password_strength("12345678")

        self.assertEqual(
            exc.exception.detail[0],
            "Password must contain both letters and numbers",
        )

    def test_ensure_password_auth_enabled_rejects_oauth_only_user(self):
        user = User.objects.create_user(
            username="oauth-only",
            email="oauth-only@example.com",
            password="password123",
        )
        user.set_unusable_password()
        user.save(update_fields=["password"])

        with self.assertRaises(serializers.ValidationError) as exc:
            ensure_password_auth_enabled(user)

        self.assertEqual(
            exc.exception.detail[0],
            "OAuth users cannot reset password. "
            "Please login with your OAuth provider.",
        )

    def test_get_password_reset_eligible_user_returns_matching_user(self):
        user = User.objects.create_user(
            username="reset-user",
            email="reset@example.com",
            password="password123",
        )
        profile = user.profile
        profile.registration_completed = True
        profile.save(update_fields=["registration_completed"])

        resolved_user = get_password_reset_eligible_user(" Reset@Example.com ")

        self.assertEqual(resolved_user.pk, user.pk)

    def test_get_password_reset_eligible_user_rejects_missing_user(self):
        with self.assertRaises(serializers.ValidationError) as exc:
            get_password_reset_eligible_user("missing@example.com")

        self.assertEqual(
            exc.exception.detail[0],
            "No user found with this email address",
        )

    def test_get_password_reset_eligible_user_rejects_incomplete_profile(self):
        user = User.objects.create_user(
            username="pending-user",
            email="pending@example.com",
            password="password123",
        )
        profile = user.profile
        profile.registration_completed = False
        profile.save(update_fields=["registration_completed"])

        with self.assertRaises(serializers.ValidationError) as exc:
            get_password_reset_eligible_user("pending@example.com")

        self.assertEqual(
            exc.exception.detail[0],
            "Please complete registration first",
        )

    def test_get_password_reset_eligible_user_rejects_missing_profile(self):
        user = User.objects.create_user(
            username="no-profile-user",
            email="no-profile@example.com",
            password="password123",
        )
        user.profile.delete()

        with self.assertRaises(serializers.ValidationError) as exc:
            get_password_reset_eligible_user("no-profile@example.com")

        self.assertEqual(
            exc.exception.detail[0],
            "User profile not found",
        )

    def test_password_reset_confirm_serializer_accepts_camel_case_input(self):
        serializer = PasswordResetConfirmSerializer(
            data={
                "uid": "encoded-id",
                "token": "reset-token",
                "newPassword1": "validpass123",
                "newPassword2": "validpass123",
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(
            serializer.validated_data["new_password1"],
            "validpass123",
        )

    def test_password_reset_confirm_serializer_rejects_mismatch(self):
        serializer = PasswordResetConfirmSerializer(
            data={
                "uid": "encoded-id",
                "token": "reset-token",
                "new_password1": "validpass123",
                "new_password2": "validpass124",
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertEqual(
            serializer.errors["non_field_errors"][0],
            "Passwords do not match",
        )
