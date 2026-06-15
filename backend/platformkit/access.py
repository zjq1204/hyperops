"""Reusable access-control engine for product-specific feature manifests."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

from django.contrib.auth.models import Group


@dataclass(frozen=True)
class FeatureDefinition:
    """Single feature or platform entry exposed by a product."""

    key: str
    label: str
    default_path: str
    platform: str = ""
    parent_key: str = ""


class AccessPolicy:
    """Product-neutral access engine driven by feature manifests."""

    PLATFORM_LABELS = {
        "workspace": "User Workspace",
        "admin_console": "Admin Console",
    }

    PLATFORM_DEFAULT_PATHS = {
        "workspace": "/dashboard",
        "admin_console": "/management",
    }

    def __init__(
        self,
        feature_definitions: Sequence[dict[str, str] | FeatureDefinition],
        *,
        feature_aliases: dict[str, str | Sequence[str]] | None = None,
        legacy_default_features: Iterable[str] | None = None,
    ) -> None:
        definitions = []
        for item in feature_definitions:
            if isinstance(item, FeatureDefinition):
                definitions.append(item)
                continue

            definitions.append(
                FeatureDefinition(
                    key=item["key"],
                    label=item["label"],
                    default_path=item["default_path"],
                    platform=item.get("platform", ""),
                    parent_key=item.get("parent_key", ""),
                )
            )

        self.feature_definitions = tuple(definitions)
        self.feature_keys = tuple(item.key for item in self.feature_definitions)
        self.feature_key_set = set(self.feature_keys)
        self.feature_order = {
            key: index for index, key in enumerate(self.feature_keys)
        }
        self.feature_default_paths = {
            item.key: item.default_path for item in self.feature_definitions
        }
        self.feature_platforms = {
            item.key: item.platform or item.key
            for item in self.feature_definitions
        }
        self.feature_aliases = dict(feature_aliases or {})
        self.platform_definitions_by_key = self._build_platform_definitions()
        self._platform_keys = tuple(self.platform_definitions_by_key.keys())
        self._platform_key_set = set(self._platform_keys)
        self._platform_order = {
            key: index for index, key in enumerate(self._platform_keys)
        }
        self.legacy_default_features = tuple(
            self.normalize_feature_keys(legacy_default_features or ())
        )

    @property
    def platform_definitions(self) -> tuple[FeatureDefinition, ...]:
        """Expose the current platform manifest."""
        return tuple(self.platform_definitions_by_key.values())

    @property
    def platform_keys(self) -> tuple[str, ...]:
        """Expose the current platform keys."""
        return self._platform_keys

    @property
    def platform_key_set(self) -> set[str]:
        """Expose the current platform set."""
        return self._platform_key_set

    @property
    def platform_order(self) -> dict[str, int]:
        """Expose the current platform ordering."""
        return self._platform_order

    @property
    def platform_default_paths(self) -> dict[str, str]:
        """Expose the current platform landing paths."""
        return {
            key: definition.default_path
            for key, definition in self.platform_definitions_by_key.items()
        }

    def _build_platform_definitions(self) -> dict[str, FeatureDefinition]:
        """Build ordered platform entries from feature metadata."""
        platforms = {}
        for item in self.feature_definitions:
            platform_key = item.platform or item.key
            if platform_key in platforms:
                continue
            platforms[platform_key] = FeatureDefinition(
                key=platform_key,
                label=self.PLATFORM_LABELS.get(platform_key, platform_key),
                default_path=self.PLATFORM_DEFAULT_PATHS.get(
                    platform_key,
                    item.default_path,
                ),
            )
        return platforms

    def _expand_key(self, value: str | None) -> list[str]:
        raw_value = str(value or "").strip()
        aliased_value = self.feature_aliases.get(raw_value, raw_value)
        if isinstance(aliased_value, (list, tuple)):
            return [str(item).strip() for item in aliased_value if str(item).strip()]
        return [str(aliased_value).strip()] if str(aliased_value).strip() else []

    def normalize_feature_keys(self, values: Iterable[str] | None) -> list[str]:
        """Return a de-duplicated, ordered list of known feature keys."""
        if not values:
            return []

        normalized = []
        seen = set()
        for raw_value in values:
            for value in self._expand_key(raw_value):
                if (
                    not value
                    or value not in self.feature_key_set
                    or value in seen
                ):
                    continue
                normalized.append(value)
                seen.add(value)

        normalized.sort(key=lambda item: self.feature_order[item])
        return normalized

    def normalize_platform_key(self, value: str | None) -> str:
        """Return a valid platform key or an empty string."""
        raw_value = str(value or "").strip()
        if raw_value in self.platform_key_set:
            return raw_value

        for key in self._expand_key(raw_value):
            if key in self.platform_key_set:
                return key
            platform_key = self.feature_platforms.get(key)
            if platform_key in self.platform_key_set:
                return platform_key
        return ""

    def serialize_feature_options(self) -> list[dict[str, str]]:
        """Serialize feature definitions for API clients."""
        return [
            {
                "key": item.key,
                "label": item.label,
                "default_path": item.default_path,
                "platform": item.platform or item.key,
                "parent_key": item.parent_key or item.platform or item.key,
            }
            for item in self.feature_definitions
        ]

    def serialize_platform_options(self) -> list[dict[str, str]]:
        """Serialize platform definitions for API clients."""
        return [
            {
                "key": item.key,
                "label": item.label,
                "default_path": item.default_path,
            }
            for item in self.platform_definitions
        ]

    def serialize_platforms(
        self,
        platform_keys: Iterable[str],
        feature_keys: Iterable[str] | None = None,
    ) -> list[dict[str, str]]:
        """Convert platform keys into API payloads."""
        serialized = []
        for platform_key in self._normalize_platform_keys(platform_keys):
            default_path = self._first_feature_path_for_platform(
                platform_key,
                feature_keys,
            )
            definition = self.platform_definitions_by_key[platform_key]
            serialized.append(
                {
                    "key": platform_key,
                    "label": definition.label,
                    "default_path": default_path or definition.default_path,
                }
            )
        return serialized

    def _normalize_platform_keys(self, values: Iterable[str]) -> list[str]:
        """Return ordered platform keys for raw platform or feature values."""
        normalized = []
        seen = set()
        for raw_value in values:
            platform_key = self.normalize_platform_key(raw_value)
            if not platform_key or platform_key in seen:
                continue
            normalized.append(platform_key)
            seen.add(platform_key)
        normalized.sort(key=lambda item: self.platform_order[item])
        return normalized

    def _platforms_for_features(self, feature_keys: Iterable[str]) -> list[str]:
        """Resolve ordered platform keys represented by feature keys."""
        return self._normalize_platform_keys(
            self.feature_platforms.get(feature_key, "")
            for feature_key in feature_keys
        )

    def _platform_has_features(
        self,
        platform_key: str,
        feature_keys: Iterable[str],
    ) -> bool:
        """Return whether any selected feature belongs to the platform."""
        return any(
            self.feature_platforms.get(feature_key) == platform_key
            for feature_key in feature_keys
        )

    def _first_feature_path_for_platform(
        self,
        platform_key: str,
        feature_keys: Iterable[str] | None = None,
    ) -> str:
        """Return the first available module path for a platform."""
        allowed = set(feature_keys) if feature_keys is not None else None
        for feature in self.feature_definitions:
            if feature.platform != platform_key:
                continue
            if allowed is not None and feature.key not in allowed:
                continue
            return feature.default_path
        return ""

    @staticmethod
    def _normalize_roles(roles) -> list:
        """Return active roles sorted by configured display order."""
        active_roles = [role for role in roles if getattr(role, "is_active", True)]
        active_roles.sort(key=lambda role: (role.name.lower(), role.pk))
        return active_roles

    def _collect_group_roles(self, groups: Iterable[Group]) -> list:
        """Collect active roles inherited from groups."""
        group_roles = []
        for group in groups:
            prefetched_roles = getattr(group, "ordered_roles", None)
            if prefetched_roles is None:
                prefetched_roles = group.platform_roles.filter(
                    is_active=True
                ).order_by("name", "id")
            group_roles.extend(prefetched_roles)
        return self._normalize_roles(group_roles)

    def get_effective_roles(
        self,
        user,
        *,
        direct_roles=None,
        groups=None,
    ) -> list:
        """Return the union of direct user roles and inherited group roles."""
        resolved_direct_roles = direct_roles
        if resolved_direct_roles is None:
            resolved_direct_roles = user.platform_roles.filter(
                is_active=True
            ).order_by("name", "id")

        resolved_groups = groups
        if resolved_groups is None:
            resolved_groups = user.groups.order_by("name").prefetch_related(
                "platform_roles"
            )

        unique_roles = {}
        for role in self._normalize_roles(resolved_direct_roles):
            unique_roles[role.pk] = role
        for role in self._collect_group_roles(resolved_groups):
            unique_roles.setdefault(role.pk, role)

        return sorted(
            unique_roles.values(),
            key=lambda role: (role.name.lower(), role.pk),
        )

    def get_effective_feature_keys(
        self,
        user,
        *,
        effective_roles=None,
    ) -> list[str]:
        """Return visible feature keys for the given user."""
        if getattr(user, "is_staff", False):
            return list(self.feature_keys)

        resolved_roles = effective_roles or self.get_effective_roles(user)
        feature_keys = []
        for role in resolved_roles:
            feature_keys.extend(
                self.normalize_feature_keys(role.visible_features)
            )

        normalized_features = self.normalize_feature_keys(feature_keys)
        if not normalized_features:
            normalized_features = list(self.legacy_default_features)

        return normalized_features

    def _resolve_profile_preferred_platform(self, user) -> str:
        """Read the preferred platform from profile when available."""
        profile = getattr(user, "profile", None)
        if profile is None:
            return ""
        return self.normalize_platform_key(
            getattr(profile, "preferred_platform", "")
        )

    def get_preferred_platform(
        self,
        user,
        *,
        effective_roles=None,
        feature_keys=None,
    ) -> str:
        """Resolve the platform to open after login."""
        resolved_roles = effective_roles or self.get_effective_roles(user)
        resolved_feature_keys = feature_keys or self.get_effective_feature_keys(
            user,
            effective_roles=resolved_roles,
        )

        profile_platform = self._resolve_profile_preferred_platform(user)
        if profile_platform and self._platform_has_features(
            profile_platform,
            resolved_feature_keys,
        ):
            return profile_platform

        for role in resolved_roles:
            preferred_platform = self.normalize_platform_key(
                role.preferred_platform
            )
            if (
                preferred_platform
                and self._platform_has_features(
                    preferred_platform,
                    resolved_feature_keys,
                )
            ):
                return preferred_platform

        if self._platform_has_features("workspace", resolved_feature_keys):
            return "workspace"

        if resolved_feature_keys:
            return self.feature_platforms.get(
                resolved_feature_keys[0],
                "workspace",
            )

        return "workspace"

    def get_access_profile(
        self,
        user,
        *,
        direct_roles=None,
        groups=None,
        effective_roles=None,
    ) -> dict[str, object]:
        """Build the effective access profile for a user."""
        resolved_roles = effective_roles or self.get_effective_roles(
            user,
            direct_roles=direct_roles,
            groups=groups,
        )
        feature_keys = self.get_effective_feature_keys(
            user,
            effective_roles=resolved_roles,
        )
        preferred_platform = self.get_preferred_platform(
            user,
            effective_roles=resolved_roles,
            feature_keys=feature_keys,
        )
        platform_keys = self._platforms_for_features(feature_keys)
        available_platforms = self.serialize_platforms(
            platform_keys,
            feature_keys,
        )
        landing_path = self._first_feature_path_for_platform(
            preferred_platform,
            feature_keys,
        ) or self.platform_default_paths.get(preferred_platform, "/dashboard")
        return {
            "visible_features": feature_keys,
            "available_platforms": available_platforms,
            "preferred_platform": preferred_platform,
            "landing_path": landing_path,
        }
