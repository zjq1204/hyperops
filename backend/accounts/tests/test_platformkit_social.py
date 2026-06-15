from django.contrib.auth.models import User
from django.test import TestCase

from allauth.socialaccount.models import SocialAccount

from platformkit.social import (
    build_social_login_identifier,
    get_primary_social_account,
    get_provider_display_name,
    get_provider_uid,
    get_social_account,
    get_social_provider_names,
    has_provider,
)


class PlatformKitSocialTests(TestCase):
    def test_get_provider_display_name_uses_known_provider_map(self):
        self.assertEqual(get_provider_display_name("google"), "Google")

    def test_social_account_helpers_resolve_provider_data(self):
        user = User.objects.create_user(
            username="oauth-user",
            email="oauth@example.com",
            password="password123",
        )
        social_account = SocialAccount.objects.create(
            user=user,
            provider="github",
            uid="github-uid-1",
            extra_data={"email": "oauth@example.com"},
        )

        self.assertTrue(has_provider(user, "github"))
        self.assertEqual(get_provider_uid(user, "github"), "github-uid-1")
        self.assertEqual(get_social_account(user, "github").pk, social_account.pk)
        self.assertEqual(get_primary_social_account(user).pk, social_account.pk)
        self.assertEqual(
            get_social_provider_names([social_account]),
            ["GitHub"],
        )
        self.assertEqual(
            build_social_login_identifier(social_account),
            "GitHub (oauth@example.com)",
        )
