import hashlib
import secrets

from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

from object_storage.models import FeishuIdentity, PlatformFeishuConfig

CONFIRMATION_TTL_SECONDS = 300
IDEMPOTENCY_TTL_SECONDS = 86400


class FeishuSyncConfirmationError(RuntimeError):
    def __init__(self, error_code):
        self.error_code = error_code
        super().__init__(error_code)


def _cache_key(kind, value):
    digest = hashlib.sha256(str(value).encode("utf-8")).hexdigest()
    return f"object-storage:feishu-sync:{kind}:v1:{digest}"


def _status_reason(identity):
    if identity.status_reason:
        return identity.status_reason
    if not identity.is_active:
        return "deactivated"
    if not identity.is_eligible:
        return "outside_scope"
    return ""


def _identity_payload(identity):
    return {
        "open_id": identity.open_id,
        "union_id": identity.union_id,
        "display_name": identity.display_name,
        "email": identity.email,
        "department_ids": list(identity.department_ids),
        "is_active": identity.is_active,
        "is_eligible": identity.is_eligible,
        "status_reason": _status_reason(identity),
    }


def _identity_from_payload(payload):
    from object_storage.feishu import FeishuIdentity

    return FeishuIdentity(
        open_id=payload["open_id"],
        union_id=payload.get("union_id", ""),
        display_name=payload.get("display_name", ""),
        email=payload.get("email", ""),
        department_ids=tuple(payload.get("department_ids", ())),
        is_active=bool(payload.get("is_active", True)),
        is_eligible=bool(payload.get("is_eligible", True)),
        status_reason=payload.get("status_reason", ""),
    )


def _row(identity, existing_open_ids):
    reason = _status_reason(identity)
    if reason:
        status = reason
    elif identity.open_id not in existing_open_ids:
        status = "new_remote"
    else:
        status = "eligible"
    return {
        "open_id": identity.open_id,
        "display_name": identity.display_name,
        "email": identity.email,
        "status": status,
        "reason": reason,
    }


def create_sync_preview(*, config, actor_id, remote_identities):
    remote_identities = list(remote_identities)
    existing_open_ids = set(
        FeishuIdentity.objects.filter(
            open_id__in=[identity.open_id for identity in remote_identities]
        ).values_list("open_id", flat=True)
    )
    rows = [_row(identity, existing_open_ids) for identity in remote_identities]
    remote_open_ids = {identity.open_id for identity in remote_identities}
    for identity in FeishuIdentity.objects.exclude(open_id__in=remote_open_ids):
        rows.append(
            {
                "open_id": identity.open_id,
                "display_name": identity.display_name,
                "email": (identity.profile_snapshot or {}).get("email", ""),
                "status": "outside_scope",
                "reason": "outside_scope",
            }
        )
    rows.sort(key=lambda row: (row["status"], row["display_name"], row["open_id"]))
    payload = {
        "items": rows,
        "new_remote": sum(
            identity.open_id not in existing_open_ids for identity in remote_identities
        ),
        "eligible_count": sum(
            identity.is_active and identity.is_eligible
            for identity in remote_identities
        ),
    }
    token = secrets.token_urlsafe(32)
    cache.set(
        _cache_key("confirmation", token),
        {
            "config_id": config.id,
            "actor_id": actor_id,
            "identities": [
                _identity_payload(identity) for identity in remote_identities
            ],
        },
        timeout=CONFIRMATION_TTL_SECONDS,
    )
    payload["confirmation_token"] = token
    return payload


def _risk_snapshot(current, reason):
    snapshot = dict(current or {})
    snapshot["risk_marker"] = {
        "reason": reason,
        "resource_action": "pending",
    }
    snapshot["status_reason"] = reason
    return snapshot


def _update_existing(identity, remote, access_group):
    reason = _status_reason(remote)
    identity.union_id = remote.union_id
    identity.display_name = remote.display_name
    identity.department_snapshot = list(remote.department_ids)
    identity.profile_snapshot = (
        {"email": remote.email}
        if not reason
        else _risk_snapshot(identity.profile_snapshot, reason)
    )
    identity.is_active = not reason
    identity.deactivated_at = timezone.now() if reason else None
    identity.save(
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
    if reason:
        identity.user.groups.remove(access_group)
    else:
        identity.user.groups.add(access_group)
    return reason


def _consume_confirmation(token):
    if not token:
        return None
    key = _cache_key("confirmation", token)
    if not cache.add(f"{key}:consume", True, timeout=30):
        return None
    payload = cache.get(key)
    cache.delete(key)
    return payload


def confirm_sync(*, token, idempotency_key, actor_id):
    result_key = _cache_key("idempotency", f"{actor_id}:{idempotency_key}")
    previous_result = cache.get(result_key)
    if previous_result is not None:
        return previous_result
    confirmation = _consume_confirmation(token)
    if confirmation is None or confirmation.get("actor_id") != actor_id:
        raise FeishuSyncConfirmationError("FEISHU_CONFIRMATION_INVALID")

    remote = [_identity_from_payload(item) for item in confirmation["identities"]]
    remote_open_ids = {identity.open_id for identity in remote}
    updated_count = 0
    deactivated_count = 0
    outside_scope_count = 0
    skipped_new_remote = 0
    with transaction.atomic():
        config = PlatformFeishuConfig.objects.select_for_update().get(
            pk=confirmation["config_id"], singleton_key="default"
        )
        existing_identities = {
            identity.open_id: identity
            for identity in FeishuIdentity.objects.select_for_update()
        }
        for remote_identity in remote:
            existing = existing_identities.get(remote_identity.open_id)
            if existing is None:
                skipped_new_remote += 1
                continue
            reason = _update_existing(existing, remote_identity, config.access_group)
            if reason == "outside_scope":
                outside_scope_count += 1
            elif reason:
                deactivated_count += 1
            else:
                updated_count += 1
        for identity in existing_identities.values():
            if identity.open_id in remote_open_ids:
                continue
            _update_existing(
                identity,
                _identity_from_payload(
                    {
                        "open_id": identity.open_id,
                        "union_id": identity.union_id,
                        "display_name": identity.display_name,
                        "email": (identity.profile_snapshot or {}).get("email", ""),
                        "department_ids": identity.department_snapshot or [],
                        "is_active": False,
                        "is_eligible": False,
                        "status_reason": "outside_scope",
                    }
                ),
                config.access_group,
            )
            outside_scope_count += 1
    result = {
        "updated_count": updated_count,
        "deactivated_count": deactivated_count,
        "outside_scope_count": outside_scope_count,
        "skipped_new_remote": skipped_new_remote,
    }
    cache.set(result_key, result, timeout=IDEMPOTENCY_TTL_SECONDS)
    return result
