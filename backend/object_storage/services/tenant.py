import hashlib
import secrets

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import transaction

from accounts.models import Role
from object_storage.models import StorageMembership, StorageTenant

OBJECT_STORAGE_ROLE_NAME = "Object Storage User"
OAUTH_STATE_TTL_SECONDS = 600
HANDOFF_TTL_SECONDS = 120


class StorageIdentityError(RuntimeError):
    def __init__(self, error_code):
        self.error_code = error_code
        super().__init__(error_code)


def _digest(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _cache_key(kind, raw_value):
    return f"object-storage:{kind}:v1:{_digest(raw_value)}"


def create_oauth_state(tenant_id):
    raw_state = secrets.token_urlsafe(32)
    cache.set(
        _cache_key("oauth-state", raw_state),
        {"tenant_id": tenant_id},
        timeout=OAUTH_STATE_TTL_SECONDS,
    )
    return raw_state


def consume_oauth_state(raw_state):
    if not raw_state:
        return None
    key = _cache_key("oauth-state", raw_state)
    lock_key = f"{key}:consume"
    if not cache.add(lock_key, True, timeout=30):
        return None
    payload = cache.get(key)
    cache.delete(key)
    return payload


def create_handoff_code(user_id):
    raw_code = secrets.token_urlsafe(32)
    cache.set(
        _cache_key("handoff", raw_code),
        {"user_id": user_id},
        timeout=HANDOFF_TTL_SECONDS,
    )
    return raw_code


def consume_handoff_code(raw_code):
    if not raw_code:
        return None
    key = _cache_key("handoff", raw_code)
    lock_key = f"{key}:consume"
    if not cache.add(lock_key, True, timeout=30):
        return None
    payload = cache.get(key)
    cache.delete(key)
    return payload


def _stable_username(tenant, open_id):
    digest = hashlib.sha256(open_id.encode("utf-8")).hexdigest()[:24]
    return f"os_{tenant.code}_{digest}"[:150]


def _system_role():
    role, _created = Role.objects.update_or_create(
        name=OBJECT_STORAGE_ROLE_NAME,
        defaults={
            "visible_features": ["object_storage"],
            "operation_permissions": [],
            "preferred_platform": "object_storage",
            "is_active": True,
            "is_system": True,
        },
    )
    return role


@transaction.atomic
def provision_feishu_identity(*, tenant_id, identity):
    tenant = StorageTenant.objects.select_for_update().get(pk=tenant_id)
    if not tenant.enabled or not identity.is_active or not identity.is_eligible:
        raise StorageIdentityError("FEISHU_IDENTITY_INELIGIBLE")
    existing = (
        StorageMembership.objects.select_for_update()
        .select_related("user")
        .filter(tenant=tenant, feishu_open_id=identity.open_id)
        .first()
    )
    if existing is not None:
        if not existing.is_active or not existing.user.is_active:
            raise StorageIdentityError("STORAGE_MEMBERSHIP_DISABLED")
        existing.display_name = identity.display_name
        existing.feishu_union_id = identity.union_id
        existing.department_snapshot = list(identity.department_ids)
        existing.profile_snapshot = {"email": identity.email}
        existing.save(
            update_fields=(
                "display_name",
                "feishu_union_id",
                "department_snapshot",
                "profile_snapshot",
                "updated_at",
            )
        )
        existing.user.platform_roles.add(_system_role())
        return existing

    User = get_user_model()
    user = User(
        username=_stable_username(tenant, identity.open_id),
        email=identity.email,
        first_name=identity.display_name[:150],
        is_active=True,
        is_staff=False,
        is_superuser=False,
    )
    user.set_unusable_password()
    user.save()
    membership = StorageMembership.objects.create(
        tenant=tenant,
        user=user,
        feishu_open_id=identity.open_id,
        feishu_union_id=identity.union_id,
        display_name=identity.display_name,
        department_snapshot=list(identity.department_ids),
        profile_snapshot={"email": identity.email},
        is_active=True,
    )
    user.platform_roles.add(_system_role())
    return membership
