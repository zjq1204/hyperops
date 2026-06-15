"""LDAP user synchronization helpers."""

from __future__ import annotations

from dataclasses import dataclass, field

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import transaction
from django.utils import timezone

from accounts.models import LdapAuthConfig, LdapGroupMapping, Profile

User = get_user_model()


@dataclass
class LdapUserRecord:
    """Normalized LDAP user record returned by directory services."""

    username: str
    dn: str
    email: str = ""
    first_name: str = ""
    last_name: str = ""
    display_name: str = ""
    group_dns: list[str] = field(default_factory=list)


def preview_mapped_groups(group_dns, ldap_config=None):
    """Return local Django groups that would be applied for these LDAP groups."""
    normalized_dns = {(item or "").strip() for item in (group_dns or []) if item}
    mappings = LdapGroupMapping.objects.select_related("target_group").filter(
        is_active=True,
    )
    if ldap_config is not None:
        mappings = mappings.filter(ldap_config=ldap_config)
    ordered_groups = []
    seen_group_ids = set()
    for mapping in mappings:
        if (
            mapping.mapping_scope == LdapGroupMapping.SCOPE_GROUP
            and mapping.ldap_group_dn not in normalized_dns
        ):
            continue
        if mapping.target_group_id in seen_group_ids:
            continue
        seen_group_ids.add(mapping.target_group_id)
        ordered_groups.append(mapping.target_group)
    return ordered_groups


def apply_ldap_group_mappings(user, group_dns, ldap_config=None):
    """Apply LDAP-managed group assignments while preserving unmanaged groups."""
    normalized_dns = {(item or "").strip() for item in (group_dns or []) if item}
    active_mappings_query = LdapGroupMapping.objects.select_related(
        "target_group"
    ).filter(is_active=True)
    if ldap_config is not None:
        active_mappings_query = active_mappings_query.filter(ldap_config=ldap_config)
    active_mappings = list(active_mappings_query)
    managed_group_ids = {mapping.target_group_id for mapping in active_mappings}
    target_group_ids = {
        mapping.target_group_id
        for mapping in active_mappings
        if (
            mapping.mapping_scope == LdapGroupMapping.SCOPE_ALL
            or mapping.ldap_group_dn in normalized_dns
        )
    }
    existing_group_ids = set(user.groups.values_list("id", flat=True))
    preserved_group_ids = existing_group_ids - managed_group_ids
    final_group_ids = sorted(preserved_group_ids | target_group_ids)
    user.groups.set(final_group_ids)


@transaction.atomic
def sync_ldap_user(user, record: LdapUserRecord, ldap_config=None):
    """Persist LDAP attributes and managed group memberships onto a user."""
    update_fields = []

    if (user.email or "") != (record.email or ""):
        user.email = record.email or ""
        update_fields.append("email")
    if (user.first_name or "") != (record.first_name or ""):
        user.first_name = record.first_name or ""
        update_fields.append("first_name")
    if (user.last_name or "") != (record.last_name or ""):
        user.last_name = record.last_name or ""
        update_fields.append("last_name")

    if update_fields:
        user.save(update_fields=update_fields)

    profile, _ = Profile.objects.get_or_create(user=user)
    profile_update_fields = []

    if profile.registration_completed is not True:
        profile.registration_completed = True
        profile_update_fields.append("registration_completed")
    if profile.auth_source != Profile.AUTH_SOURCE_LDAP:
        profile.auth_source = Profile.AUTH_SOURCE_LDAP
        profile_update_fields.append("auth_source")
    if profile.ldap_instance_id != (ldap_config.id if ldap_config else None):
        profile.ldap_instance = ldap_config
        profile_update_fields.append("ldap_instance")
    if (profile.ldap_uid or "") != (record.username or ""):
        profile.ldap_uid = record.username or ""
        profile_update_fields.append("ldap_uid")
    if (profile.ldap_dn or "") != (record.dn or ""):
        profile.ldap_dn = record.dn or ""
        profile_update_fields.append("ldap_dn")
    if (profile.nickname or "") != (record.display_name or ""):
        profile.nickname = record.display_name or ""
        profile_update_fields.append("nickname")

    normalized_groups = [
        (group_dn or "").strip()
        for group_dn in (record.group_dns or [])
        if (group_dn or "").strip()
    ]
    if profile.ldap_group_dns_snapshot != normalized_groups:
        profile.ldap_group_dns_snapshot = normalized_groups
        profile_update_fields.append("ldap_group_dns_snapshot")

    profile.ldap_last_synced_at = timezone.now()
    profile_update_fields.append("ldap_last_synced_at")

    profile.save(update_fields=list(dict.fromkeys(profile_update_fields)))

    apply_ldap_group_mappings(user, normalized_groups, ldap_config)
    return user


def build_ldap_local_username(ldap_config: LdapAuthConfig, ldap_uid: str):
    """Build a deterministic local username for an LDAP instance identity."""
    prefix = (ldap_config.slug or "ldap").strip() or "ldap"
    uid = (ldap_uid or "user").strip() or "user"
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_@+-.")
    normalized_uid = "".join(char if char in allowed else "_" for char in uid)
    normalized_uid = normalized_uid.strip("_") or "user"
    username = f"{prefix}_{normalized_uid}"
    return username[:150]


@transaction.atomic
def create_ldap_user(record: LdapUserRecord, ldap_config):
    """Create a local user shell from LDAP attributes and sync it."""
    user = User.objects.create_user(
        username=build_ldap_local_username(ldap_config, record.username),
        email=record.email or "",
        password=None,
    )
    user.set_unusable_password()
    user.save(update_fields=["password"])
    return sync_ldap_user(user, record, ldap_config)
