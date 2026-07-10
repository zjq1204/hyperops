from django.contrib.auth.models import Group, User
from django.test import TestCase

from accounts.access import (
    get_access_profile,
    normalize_feature_keys,
    normalize_platform_key,
)
from accounts.models import Role


class AccessProfileTests(TestCase):
    def test_workspace_aliases_expand_to_workspace_modules(self):
        self.assertEqual(
            normalize_feature_keys(['ai_model_pricing', 'hyperbdr_dashboard']),
            ['workspace_dashboard', 'workspace_jenkins'],
        )
        self.assertEqual(
            normalize_platform_key('cloud_billing'),
            'workspace',
        )

    def test_admin_aliases_expand_to_admin_modules(self):
        # The aliases include the action orchestration admin module that was
        # added when the platform manifest was split out of devmind.
        self.assertEqual(
            normalize_feature_keys(['llm_console', 'notification_console']),
            [
                'admin_users',
                'admin_jenkins',
                'admin_gitlab',
                'admin_notifications',
                'admin_actions',
                'admin_monitoring',
            ],
        )
        self.assertEqual(
            normalize_platform_key('gitlab_admin'),
            'admin_console',
        )

    def test_access_profile_includes_workspace_feature(self):
        user = User.objects.create_user(
            username='carol',
            email='carol@example.com',
            password='password123',
        )
        role = Role.objects.create(
            name='Workspace',
            visible_features=['jenkins'],
            preferred_platform='gitlab',
        )
        user.platform_roles.add(role)

        access_profile = get_access_profile(user)

        self.assertEqual(
            access_profile['visible_features'],
            ['workspace_dashboard', 'workspace_jenkins'],
        )
        self.assertTrue(
            any(
                platform['key'] == 'workspace'
                and platform['default_path'] == '/dashboard'
                for platform in access_profile['available_platforms']
            )
        )
        self.assertEqual(access_profile['preferred_platform'], 'workspace')
        self.assertEqual(access_profile['landing_path'], '/dashboard')

    def test_effective_roles_include_group_union(self):
        user = User.objects.create_user(
            username='alice',
            email='alice@example.com',
            password='password123',
        )
        group = Group.objects.create(name='operators')
        role = Role.objects.create(
            name='Ops',
            visible_features=['cloud_billing', 'data_collector'],
            preferred_platform='cloud_billing',
        )
        role.groups.add(group)
        user.groups.add(group)

        access_profile = get_access_profile(user)

        self.assertEqual(
            access_profile['visible_features'],
            ['workspace_dashboard', 'workspace_jenkins'],
        )
        self.assertEqual(access_profile['preferred_platform'], 'workspace')
        self.assertEqual(access_profile['landing_path'], '/dashboard')
        self.assertEqual(
            access_profile['preferred_platform'],
            'workspace',
        )
        self.assertEqual(
            access_profile['landing_path'],
            '/dashboard',
        )

    def test_legacy_default_features_preserved_without_roles(self):
        user = User.objects.create_user(
            username='bob',
            email='bob@example.com',
            password='password123',
        )

        access_profile = get_access_profile(user)

        self.assertEqual(
            access_profile['visible_features'],
            ['workspace_dashboard', 'workspace_jenkins', 'workspace_actions'],
        )

    def test_admin_module_access_keeps_platform_summary_platform_level(self):
        user = User.objects.create_user(
            username='dana',
            email='dana@example.com',
            password='password123',
        )
        role = Role.objects.create(
            name='GitLab Admin Only',
            visible_features=['admin_gitlab'],
            preferred_platform='admin_console',
        )
        user.platform_roles.add(role)

        access_profile = get_access_profile(user)

        self.assertEqual(access_profile['visible_features'], ['admin_gitlab'])
        self.assertEqual(
            access_profile['available_platforms'],
            [
                {
                    'key': 'admin_console',
                    'label': 'Admin Console',
                    'default_path': '/management/gitlab/instances',
                }
            ],
        )
        self.assertEqual(access_profile['preferred_platform'], 'admin_console')
        self.assertEqual(
            access_profile['landing_path'],
            '/management/gitlab/instances',
        )

    def test_staff_user_gets_all_module_features(self):
        user = User.objects.create_user(
            username='root',
            email='root@example.com',
            password='password123',
            is_staff=True,
        )

        access_profile = get_access_profile(user)

        self.assertEqual(
            access_profile['visible_features'],
            [
                'workspace_dashboard',
                'workspace_jenkins',
                'workspace_actions',
                'admin_users',
                'admin_jenkins',
                'admin_gitlab',
                'admin_notifications',
                'admin_actions',
                'admin_monitoring',
            ],
        )
