"""HyperOps access manifest built on the shared access-control engine."""

from __future__ import annotations

from typing import Iterable

from platformkit.access import AccessPolicy

FEATURE_DEFINITIONS = (
    {
        'key': 'workspace_dashboard',
        'label': '工作台首页',
        'default_path': '/dashboard',
        'platform': 'workspace',
        'parent_key': 'workspace',
    },
    {
        'key': 'workspace_jenkins',
        'label': 'Jenkins 工作台',
        'default_path': '/jenkins/workspace',
        'platform': 'workspace',
        'parent_key': 'workspace',
    },
    {
        'key': 'workspace_actions',
        'label': '动作编排',
        'default_path': '/actions/workspace',
        'platform': 'workspace',
        'parent_key': 'workspace',
    },
    {
        'key': 'admin_users',
        'label': '用户管理',
        'default_path': '/management/users',
        'platform': 'admin_console',
        'parent_key': 'admin_console',
    },
    {
        'key': 'admin_jenkins',
        'label': 'Jenkins 管理',
        'default_path': '/management/jenkins/instances',
        'platform': 'admin_console',
        'parent_key': 'admin_console',
    },
    {
        'key': 'admin_gitlab',
        'label': 'GitLab 管理',
        'default_path': '/management/gitlab/instances',
        'platform': 'admin_console',
        'parent_key': 'admin_console',
    },
    {
        'key': 'admin_notifications',
        'label': '通知管理',
        'default_path': '/management/notifier/stats',
        'platform': 'admin_console',
        'parent_key': 'admin_console',
    },
    {
        'key': 'admin_actions',
        'label': '动作编排管理',
        'default_path': '/management/actions/templates',
        'platform': 'admin_console',
        'parent_key': 'admin_console',
    },
)

FEATURE_ALIASES = {
    'workspace': (
        'workspace_dashboard',
        'workspace_jenkins',
        'workspace_actions',
    ),
    'admin_console': (
        'admin_users',
        'admin_jenkins',
        'admin_gitlab',
        'admin_notifications',
        'admin_actions',
    ),
    'jenkins': ('workspace_dashboard', 'workspace_jenkins'),
    'gitlab': ('workspace_dashboard', 'workspace_jenkins'),
    'cloud_billing': ('workspace_dashboard', 'workspace_jenkins'),
    'data_collector': ('workspace_dashboard', 'workspace_jenkins'),
    'operations_console': ('workspace_dashboard', 'workspace_jenkins'),
    'hyperbdr_dashboard': ('workspace_dashboard', 'workspace_jenkins'),
    'ai_model_pricing': ('workspace_dashboard', 'workspace_jenkins'),
    'ai_pricehub': ('workspace_dashboard', 'workspace_jenkins'),
    'jenkins_admin': (
        'admin_users',
        'admin_jenkins',
        'admin_gitlab',
        'admin_notifications',
        'admin_actions',
    ),
    'gitlab_admin': (
        'admin_users',
        'admin_jenkins',
        'admin_gitlab',
        'admin_notifications',
        'admin_actions',
    ),
    'llm_console': (
        'admin_users',
        'admin_jenkins',
        'admin_gitlab',
        'admin_notifications',
        'admin_actions',
    ),
    'task_management_console': (
        'admin_users',
        'admin_jenkins',
        'admin_gitlab',
        'admin_notifications',
        'admin_actions',
    ),
    'notification_console': (
        'admin_users',
        'admin_jenkins',
        'admin_gitlab',
        'admin_notifications',
        'admin_actions',
    ),
}

LEGACY_DEFAULT_FEATURES = (
    'workspace',
)

ACCESS_POLICY = AccessPolicy(
    FEATURE_DEFINITIONS,
    feature_aliases=FEATURE_ALIASES,
    legacy_default_features=LEGACY_DEFAULT_FEATURES,
)

FEATURE_KEYS = ACCESS_POLICY.feature_keys
FEATURE_KEY_SET = ACCESS_POLICY.feature_key_set
FEATURE_ORDER = ACCESS_POLICY.feature_order
FEATURE_DEFAULT_PATHS = ACCESS_POLICY.feature_default_paths

PLATFORM_DEFINITIONS = ACCESS_POLICY.platform_definitions
PLATFORM_KEYS = ACCESS_POLICY.platform_keys
PLATFORM_KEY_SET = ACCESS_POLICY.platform_key_set
PLATFORM_ORDER = ACCESS_POLICY.platform_order
PLATFORM_DEFAULT_PATHS = ACCESS_POLICY.platform_default_paths


def normalize_feature_keys(values: Iterable[str] | None) -> list[str]:
    """Return a de-duplicated, ordered list of known feature keys."""
    return ACCESS_POLICY.normalize_feature_keys(values)


def normalize_platform_key(value: str | None) -> str:
    """Return a valid platform key or an empty string."""
    return ACCESS_POLICY.normalize_platform_key(value)


def serialize_feature_options() -> list[dict[str, str]]:
    """Serialize feature definitions for API clients."""
    return ACCESS_POLICY.serialize_feature_options()


def serialize_platform_options() -> list[dict[str, str]]:
    """Serialize platform definitions for API clients."""
    return ACCESS_POLICY.serialize_platform_options()


def serialize_platforms(platform_keys: Iterable[str]) -> list[dict[str, str]]:
    """Convert platform keys into API payloads."""
    return ACCESS_POLICY.serialize_platforms(platform_keys)


def get_effective_roles(
    user,
    *,
    direct_roles=None,
    groups=None,
) -> list:
    """Return the union of direct user roles and inherited group roles."""
    return ACCESS_POLICY.get_effective_roles(
        user,
        direct_roles=direct_roles,
        groups=groups,
    )


def get_effective_feature_keys(
    user,
    *,
    effective_roles=None,
) -> list[str]:
    """Return visible feature keys for the given user."""
    return ACCESS_POLICY.get_effective_feature_keys(
        user,
        effective_roles=effective_roles,
    )


def get_preferred_platform(
    user,
    *,
    effective_roles=None,
    feature_keys=None,
) -> str:
    """Resolve the platform to open after login."""
    return ACCESS_POLICY.get_preferred_platform(
        user,
        effective_roles=effective_roles,
        feature_keys=feature_keys,
    )


def get_access_profile(
    user,
    *,
    direct_roles=None,
    groups=None,
    effective_roles=None,
) -> dict[str, object]:
    """Build the effective access profile for a user."""
    return ACCESS_POLICY.get_access_profile(
        user,
        direct_roles=direct_roles,
        groups=groups,
        effective_roles=effective_roles,
    )
