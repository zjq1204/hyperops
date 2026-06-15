from datetime import datetime, timezone
from types import SimpleNamespace

from django.test import SimpleTestCase

from platformkit.management import (
    build_group_payload,
    build_group_summary,
    build_role_payload,
    build_role_summary,
    build_user_payload,
)


class _Counter:
    def __init__(self, value):
        self.value = value

    def count(self):
        return self.value


class PlatformKitManagementTests(SimpleTestCase):
    def test_build_group_summary_serializes_group_memberships(self):
        groups = [
            SimpleNamespace(pk=1, name="Admins"),
            SimpleNamespace(pk=2, name="Operators"),
        ]

        self.assertEqual(
            build_group_summary(groups),
            [
                {"id": 1, "name": "Admins"},
                {"id": 2, "name": "Operators"},
            ],
        )

    def test_build_role_summary_uses_injected_normalizers(self):
        role = SimpleNamespace(
            pk=7,
            name="Ops",
            visible_features=["jenkins", "gitlab"],
            preferred_platform="jenkins_admin",
            is_active=True,
        )

        payload = build_role_summary(
            role,
            normalize_features=lambda values: ["workspace", "admin_console"],
            normalize_platform=lambda value: "admin_console",
        )

        self.assertEqual(payload["visible_features"], ["workspace", "admin_console"])
        self.assertEqual(payload["preferred_platform"], "admin_console")

    def test_build_role_payload_uses_count_fallbacks(self):
        role = SimpleNamespace(
            pk=3,
            name="Maintainer",
            visible_features=["workspace"],
            preferred_platform="workspace",
            is_active=True,
            users=_Counter(4),
            groups=_Counter(2),
        )

        payload = build_role_payload(
            role,
            normalize_features=lambda values: list(values),
            normalize_platform=lambda value: value,
        )

        self.assertEqual(payload["user_count"], 4)
        self.assertEqual(payload["group_count"], 2)

    def test_build_group_payload_uses_permission_count_fallback(self):
        group = SimpleNamespace(
            pk=5,
            name="Release",
            user_set=_Counter(3),
            permissions=_Counter(8),
        )
        roles = [SimpleNamespace(pk=11, name="RoleA")]

        payload = build_group_payload(
            group,
            roles=roles,
            role_serializer=lambda role: {"id": role.pk, "name": role.name},
        )

        self.assertEqual(payload["user_count"], 3)
        self.assertEqual(payload["permission_count"], 8)
        self.assertEqual(payload["roles"], [{"id": 11, "name": "RoleA"}])

    def test_build_user_payload_applies_defaults_and_injected_access_profile(self):
        user = SimpleNamespace(
            pk=9,
            username="ops-user",
            email="ops@example.com",
            first_name="Ops",
            last_name="User",
            is_staff=True,
            is_active=True,
            date_joined=datetime(2025, 1, 1, tzinfo=timezone.utc),
        )
        groups = [SimpleNamespace(pk=1, name="Admins")]
        direct_roles = [SimpleNamespace(pk=2, name="Writer")]
        effective_roles = [SimpleNamespace(pk=3, name="Admin")]
        access_calls = []

        def access_profile_builder(
            current_user,
            *,
            direct_roles,
            groups,
            effective_roles,
        ):
            access_calls.append(
                (current_user.pk, len(direct_roles), len(groups), len(effective_roles))
            )
            return {"landing_path": "/management/jenkins/instances"}

        payload = build_user_payload(
            user,
            groups=groups,
            direct_roles=direct_roles,
            effective_roles=effective_roles,
            role_serializer=lambda role: {"id": role.pk, "name": role.name},
            access_profile_builder=access_profile_builder,
            normalize_platform=lambda value: f"normalized:{value}" if value else "",
        )

        self.assertEqual(payload["language"], "zh-CN")
        self.assertEqual(payload["timezone"], "Asia/Shanghai")
        self.assertEqual(payload["groups"], [{"id": 1, "name": "Admins"}])
        self.assertEqual(payload["roles"], [{"id": 2, "name": "Writer"}])
        self.assertEqual(payload["effective_roles"], [{"id": 3, "name": "Admin"}])
        self.assertEqual(payload["auth_source"], "local")
        self.assertIsNone(payload["ldap_last_synced_at"])
        self.assertEqual(
            payload["access_profile"],
            {"landing_path": "/management/jenkins/instances"},
        )
        self.assertEqual(access_calls, [(9, 1, 1, 1)])
