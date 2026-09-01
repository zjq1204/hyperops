"""Compatibility helpers for the removed tenant-scoped Feishu integration."""

from django.contrib.auth.models import Group

from object_storage.models import FeishuIdentity
from object_storage.services.identity import (
    StorageIdentityError,
    consume_handoff_code,
    consume_oauth_state,
    create_handoff_code,
    create_oauth_state,
    provision_feishu_identity,
)


def sync_feishu_access_group(config, *, previous_group_id=None):
    """Move existing Feishu users when the singleton access group changes."""
    user_ids = list(FeishuIdentity.objects.values_list("user_id", flat=True))
    if previous_group_id and previous_group_id != config.access_group_id:
        previous_group = Group.objects.filter(pk=previous_group_id).first()
        if previous_group is not None:
            previous_group.user_set.remove(*user_ids)
    if config.access_group_id and user_ids:
        config.access_group.user_set.add(*user_ids)
    return config.access_group


__all__ = (
    "StorageIdentityError",
    "consume_handoff_code",
    "consume_oauth_state",
    "create_handoff_code",
    "create_oauth_state",
    "provision_feishu_identity",
    "sync_feishu_access_group",
)
