from django.contrib.auth.models import User
from django.test import TestCase

from allauth.socialaccount.models import SocialAccount

from accounts.models import Profile
from platformkit.users import (
    build_auth_info,
    build_display_name,
    build_profile_snapshot,
    upsert_profile_preferences,
)


class PlatformKitUsersTests(TestCase):
    def test_build_display_name_prefers_full_name(self):
        user = User(
            username="coder",
            email="coder@example.com",
            first_name="Ada",
            last_name="Lovelace",
        )

        self.assertEqual(build_display_name(user), "Ada Lovelace")

    def test_build_display_name_prefers_profile_nickname(self):
        user = User.objects.create_user(
            username="ldap-user",
            email="ldap@example.com",
            first_name="张佳奇",
            last_name="张佳奇",
        )
        profile = user.profile
        profile.nickname = "张佳奇"
        profile.save(update_fields=["nickname"])

        self.assertEqual(build_display_name(user), "张佳奇")

    def test_build_display_name_falls_back_to_username(self):
        user = User(username="fallback-user", email="fallback@example.com")

        self.assertEqual(build_display_name(user), "fallback-user")

    def test_build_profile_snapshot_returns_none_for_missing_profile(self):
        self.assertIsNone(build_profile_snapshot(None))

    def test_build_auth_info_returns_email_mode_without_social_account(self):
        user = User.objects.create_user(
            username="local-user",
            email="local@example.com",
            password="password123",
        )

        auth_info = build_auth_info(user)

        self.assertEqual(auth_info["method"], "email")
        self.assertEqual(auth_info["login_identifier"], "local@example.com")
        self.assertTrue(auth_info["can_change_password"])

    def test_build_auth_info_returns_ldap_mode_for_ldap_profile(self):
        user = User.objects.create_user(
            username="ldap-user",
            email="ldap@example.com",
            password="password123",
        )
        user.set_unusable_password()
        user.save(update_fields=["password"])
        profile = user.profile
        profile.auth_source = Profile.AUTH_SOURCE_LDAP
        profile.ldap_uid = "ldap-user"
        profile.save(update_fields=["auth_source", "ldap_uid"])

        auth_info = build_auth_info(user)

        self.assertEqual(auth_info["method"], "ldap")
        self.assertEqual(auth_info["login_identifier"], "ldap-user")
        self.assertFalse(auth_info["can_change_password"])

    def test_build_auth_info_returns_oauth_mode_with_social_account(self):
        user = User.objects.create_user(
            username="oauth-user",
            email="oauth@example.com",
            password="password123",
        )
        SocialAccount.objects.create(
            user=user,
            provider="google",
            uid="google-uid-1",
            extra_data={"email": "oauth@example.com"},
        )

        auth_info = build_auth_info(user)

        self.assertEqual(auth_info["method"], "oauth")
        self.assertEqual(auth_info["provider"], "Google")
        self.assertEqual(auth_info["provider_account_id"], "google-uid-1")
        self.assertEqual(auth_info["provider_email"], "oauth@example.com")

    def test_upsert_profile_preferences_creates_profile_with_defaults(self):
        user = User.objects.create_user(
            username="profile-user",
            email="profile@example.com",
            password="password123",
        )

        profile, update_fields = upsert_profile_preferences(
            user,
            profile_model=Profile,
            profile_language="en-US",
            profile_timezone="UTC",
        )

        self.assertEqual(profile.language.lower(), "en-us")
        self.assertEqual(profile.timezone, "UTC")
        self.assertEqual(update_fields, ["language", "timezone"])
