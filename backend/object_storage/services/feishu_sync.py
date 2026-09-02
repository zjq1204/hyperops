import hashlib
import json
import secrets
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from object_storage.models import (
    FeishuIdentity,
    FeishuSyncConfirmation,
    FeishuSyncResult,
    PlatformFeishuConfig,
)
from object_storage.services.platform import feishu_config_fingerprint

CONFIRMATION_TTL_SECONDS = 300


class FeishuSyncConfirmationError(RuntimeError):
    def __init__(self, error_code):
        self.error_code = error_code
        super().__init__(error_code)


def _status_reason(identity):
    if identity.status_reason:
        return identity.status_reason
    if not identity.is_active:
        return "account_disabled"
    if not identity.is_eligible:
        return "outside_scope"
    return ""


def _identity_payload(identity):
    return {
        "open_id": identity.open_id,
        "union_id": identity.union_id,
        "display_name": identity.display_name,
        "email": identity.email,
        "department_ids": sorted(str(item) for item in identity.department_ids),
        "is_active": bool(identity.is_active),
        "is_eligible": bool(identity.is_eligible),
        "status_reason": _status_reason(identity),
    }


def _canonical_hash(snapshot):
    encoded = json.dumps(
        snapshot, ensure_ascii=True, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


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


def _local_changed(identity, remote):
    return any(
        (
            identity.union_id != remote.union_id,
            identity.display_name != remote.display_name,
            list(identity.department_snapshot or []) != list(remote.department_ids),
            identity.profile_snapshot != {"email": remote.email},
            not identity.is_active,
        )
    )


def _classify(identity, existing):
    reason = _status_reason(identity)
    if existing is None:
        return "new_remote", reason
    if reason == "outside_scope":
        return "outside_scope", reason
    if reason == "account_disabled":
        return "account_disabled", reason
    if reason == "deleted":
        return "deleted", reason
    if _local_changed(existing, identity):
        return "updates", ""
    return "unchanged", ""


def _item(identity, category, reason):
    email = getattr(identity, "email", "")
    if not email:
        email = (identity.profile_snapshot or {}).get("email", "")
    return {
        "open_id": identity.open_id,
        "display_name": identity.display_name,
        "email": email,
        "category": category,
        "status": category,
        "reason": reason,
    }


def create_sync_preview(*, config, actor_id, remote_identities):
    remote_identities = sorted(
        list(remote_identities), key=lambda identity: identity.open_id
    )
    remote_open_ids = [identity.open_id for identity in remote_identities]
    existing_by_open_id = {
        identity.open_id: identity
        for identity in FeishuIdentity.objects.filter(open_id__in=remote_open_ids)
    }
    items = []
    actions = []
    for remote in remote_identities:
        category, reason = _classify(remote, existing_by_open_id.get(remote.open_id))
        items.append(_item(remote, category, reason))
        actions.append({"open_id": remote.open_id, "category": category})

    for existing in FeishuIdentity.objects.exclude(open_id__in=remote_open_ids):
        items.append(
            _item(
                existing,
                "outside_scope",
                "outside_scope",
            )
        )
        actions.append({"open_id": existing.open_id, "category": "outside_scope"})

    items.sort(key=lambda item: (item["category"], item["open_id"]))
    counts = {
        "creates": sum(item["category"] == "new_remote" for item in items),
        "updates": sum(item["category"] == "updates" for item in items),
        "account_disabled": sum(
            item["category"] == "account_disabled" for item in items
        ),
        "deleted": sum(item["category"] == "deleted" for item in items),
        "outside_scope": sum(item["category"] == "outside_scope" for item in items),
        "unchanged": sum(item["category"] == "unchanged" for item in items),
    }
    snapshot = {
        "identities": [_identity_payload(identity) for identity in remote_identities],
        "items": items,
        "counts": counts,
    }
    snapshot_hash = _canonical_hash(snapshot)
    token = secrets.token_urlsafe(32)
    FeishuSyncConfirmation.objects.create(
        actor_id=actor_id,
        config=config,
        token_digest=hashlib.sha256(token.encode("utf-8")).hexdigest(),
        config_fingerprint=feishu_config_fingerprint(config),
        snapshot_hash=snapshot_hash,
        snapshot=snapshot,
        actions=actions,
        expires_at=timezone.now() + timedelta(seconds=CONFIRMATION_TTL_SECONDS),
    )
    return {
        "items": items,
        "counts": counts,
        "new_remote": counts["creates"],
        "eligible_count": sum(
            identity.is_active and identity.is_eligible
            for identity in remote_identities
        ),
        "snapshot_hash": snapshot_hash,
        "confirmation_token": token,
    }


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


def confirm_sync(*, token, idempotency_key, actor_id):
    token_digest = hashlib.sha256(str(token or "").encode("utf-8")).hexdigest()

    with transaction.atomic():
        confirmation = (
            FeishuSyncConfirmation.objects.select_for_update()
            .select_related("config")
            .filter(token_digest=token_digest, actor_id=actor_id)
            .first()
        )
        if confirmation is None:
            raise FeishuSyncConfirmationError("FEISHU_CONFIRMATION_INVALID")
        if confirmation.status == FeishuSyncConfirmation.Status.CONSUMED:
            raise FeishuSyncConfirmationError("TOKEN_ALREADY_CONSUMED")
        if confirmation.expires_at <= timezone.now():
            confirmation.status = FeishuSyncConfirmation.Status.EXPIRED
            confirmation.save(update_fields=("status",))
            raise FeishuSyncConfirmationError("FEISHU_CONFIRMATION_EXPIRED")
        config = PlatformFeishuConfig.objects.select_for_update().get(
            pk=confirmation.config_id, singleton_key="default"
        )
        if (
            not config.enabled
            or config.validation_status != PlatformFeishuConfig.ValidationStatus.VALID
            or config.access_group_id is None
            or feishu_config_fingerprint(config) != confirmation.config_fingerprint
        ):
            raise FeishuSyncConfirmationError("PREVIEW_STALE")
        previous = (
            FeishuSyncResult.objects.select_for_update()
            .filter(actor_id=actor_id, idempotency_key=idempotency_key)
            .first()
        )
        if previous is not None:
            if previous.snapshot_hash != confirmation.snapshot_hash:
                raise FeishuSyncConfirmationError("IDEMPOTENCY_KEY_REUSED")
            return previous.result
        remote_by_open_id = {
            item["open_id"]: _identity_from_payload(item)
            for item in confirmation.snapshot["identities"]
        }
        counts = {
            "updates": 0,
            "account_disabled": 0,
            "deleted": 0,
            "outside_scope": 0,
            "unchanged": 0,
            "new_remote": 0,
        }
        existing_by_open_id = {
            identity.open_id: identity
            for identity in FeishuIdentity.objects.select_for_update()
        }
        for action in confirmation.actions:
            category = action["category"]
            identity = existing_by_open_id.get(action["open_id"])
            if category == "new_remote":
                counts["new_remote"] += 1
                continue
            if category == "unchanged":
                counts["unchanged"] += 1
                continue
            if identity is None:
                continue
            if category == "outside_scope":
                remote = _identity_from_payload(
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
                )
            else:
                remote = remote_by_open_id[action["open_id"]]
            _update_existing(identity, remote, config.access_group)
            counts[category] += 1
        result = {
            "updated_count": counts["updates"],
            "deactivated_count": counts["account_disabled"] + counts["deleted"],
            "account_disabled_count": counts["account_disabled"],
            "deleted_count": counts["deleted"],
            "outside_scope_count": counts["outside_scope"],
            "skipped_new_remote": counts["new_remote"],
            "unchanged_count": counts["unchanged"],
        }
        FeishuSyncResult.objects.create(
            actor_id=actor_id,
            idempotency_key=idempotency_key,
            snapshot_hash=confirmation.snapshot_hash,
            result=result,
        )
        confirmation.status = FeishuSyncConfirmation.Status.CONSUMED
        confirmation.consumed_at = timezone.now()
        confirmation.save(update_fields=("status", "consumed_at"))
        return result
