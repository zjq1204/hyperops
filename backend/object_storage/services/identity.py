import hashlib
import secrets

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import transaction

from object_storage.models import FeishuIdentity, PlatformFeishuConfig

OAUTH_STATE_TTL_SECONDS = 600
HANDOFF_TTL_SECONDS = 120


class StorageIdentityError(RuntimeError):
    def __init__(self, error_code):
        self.error_code = error_code
        super().__init__(error_code)


def _digest(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _cache_key(kind, raw_value):
    return f"object-storage:{kind}:v2:{_digest(raw_value)}"


def create_oauth_state(config_id):
    state = secrets.token_urlsafe(32)
    cache.set(
        _cache_key("oauth-state", state),
        {"config_id": config_id, "nonce": secrets.token_urlsafe(24)},
        timeout=OAUTH_STATE_TTL_SECONDS,
    )
    return state


def _consume_cache_value(kind, raw_value):
    if not raw_value:
        return None
    key = _cache_key(kind, raw_value)
    if not cache.add(f"{key}:consume", True, timeout=30):
        return None
    payload = cache.get(key)
    cache.delete(key)
    return payload


def consume_oauth_state(raw_state):
    return _consume_cache_value("oauth-state", raw_state)


def create_handoff_code(user_id):
    code = secrets.token_urlsafe(32)
    cache.set(
        _cache_key("handoff", code),
        {"user_id": user_id},
        timeout=HANDOFF_TTL_SECONDS,
    )
    return code


def consume_handoff_code(raw_code):
    return _consume_cache_value("handoff", raw_code)


def _stable_username(open_id):
    return f"feishu_{hashlib.sha256(open_id.encode('utf-8')).hexdigest()[:32]}"


def _identity_error_code(identity):
    return {
        "outside_scope": "FEISHU_IDENTITY_OUTSIDE_SCOPE",
        "deactivated": "FEISHU_IDENTITY_DEACTIVATED",
        "deleted": "FEISHU_IDENTITY_DELETED",
    }.get(identity.status_reason, "FEISHU_IDENTITY_INELIGIBLE")


def _snapshot(identity):
    snapshot = {"email": identity.email}
    if identity.status_reason:
        snapshot["status_reason"] = identity.status_reason
    return snapshot


@transaction.atomic
def provision_feishu_identity(*, config_id, identity):
    config = (
        PlatformFeishuConfig.objects.select_for_update()
        .select_related("access_group")
        .get(pk=config_id, singleton_key="default")
    )
    if config.access_group_id is None:
        raise StorageIdentityError("FEISHU_ACCESS_GROUP_NOT_CONFIGURED")
    if not identity.is_active or not identity.is_eligible:
        raise StorageIdentityError(_identity_error_code(identity))

    existing = (
        FeishuIdentity.objects.select_for_update()
        .select_related("user")
        .filter(open_id=identity.open_id)
        .first()
    )
    if existing is not None:
        if not existing.user.is_active:
            raise StorageIdentityError("LOCAL_USER_INACTIVE")
        existing.union_id = identity.union_id
        existing.display_name = identity.display_name
        existing.department_snapshot = list(identity.department_ids)
        existing.profile_snapshot = _snapshot(identity)
        existing.is_active = True
        existing.deactivated_at = None
        existing.save(
            update_fields=(
                "union_id",
                "display_name",
                "department_snapshot",
                "profile_snapshot",
                "is_active",
                "deactivated_at",
                "updated_at",
            )
        )
        existing.user.groups.add(config.access_group)
        return existing

    User = get_user_model()
    user = User(
        username=_stable_username(identity.open_id),
        email=identity.email,
        first_name=identity.display_name[:150],
        is_active=True,
        is_staff=False,
        is_superuser=False,
    )
    user.set_unusable_password()
    user.save()
    feishu_identity = FeishuIdentity.objects.create(
        user=user,
        open_id=identity.open_id,
        union_id=identity.union_id,
        display_name=identity.display_name,
        department_snapshot=list(identity.department_ids),
        profile_snapshot=_snapshot(identity),
        is_active=True,
    )
    user.groups.add(config.access_group)
    return feishu_identity
