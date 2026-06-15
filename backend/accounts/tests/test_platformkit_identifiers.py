from django.contrib.auth.models import User
from django.test import TestCase

from rest_framework import serializers

from platformkit.identifiers import (
    normalize_virtual_email_username,
    validate_virtual_email_alias,
    validate_virtual_email_username,
)


class PlatformKitIdentifiersTests(TestCase):
    def test_normalize_virtual_email_username_trims_and_lowercases(self):
        self.assertEqual(
            normalize_virtual_email_username("  Example.User  "),
            "example.user",
        )

    def test_validate_virtual_email_username_accepts_valid_value(self):
        self.assertEqual(
            validate_virtual_email_username("  Example.User  "),
            "example.user",
        )

    def test_validate_virtual_email_username_rejects_reserved_word(self):
        with self.assertRaises(serializers.ValidationError) as exc:
            validate_virtual_email_username("admin")

        self.assertEqual(
            exc.exception.detail[0],
            "This username is reserved and cannot be used",
        )

    def test_validate_virtual_email_username_rejects_taken_username(self):
        User.objects.create_user(
            username="existing.user",
            email="existing@example.com",
            password="password123",
        )

        with self.assertRaises(serializers.ValidationError) as exc:
            validate_virtual_email_username("existing.user")

        self.assertEqual(
            exc.exception.detail[0],
            "This username is already taken",
        )

    def test_validate_virtual_email_alias_returns_service_friendly_error(self):
        User.objects.create_user(
            username="ops-team",
            email="ops@example.com",
            password="password123",
        )

        is_valid, error = validate_virtual_email_alias("ops-team")

        self.assertFalse(is_valid)
        self.assertEqual(error, "This virtual email is already taken")
