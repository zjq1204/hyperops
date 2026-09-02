import hashlib
from datetime import timedelta

from django.utils import timezone
from django.utils.dateparse import parse_datetime

OBSERVATION_TTL_SECONDS = 900


class ObservationError(RuntimeError):
    def __init__(self, error_code):
        self.error_code = error_code
        super().__init__(error_code)


def operation_token_digest(token):
    return hashlib.sha256(str(token or "").encode("utf-8")).hexdigest()


def build_operation_observation(
    *, operation_type, operation_generation, operation_token, payload, now=None
):
    now = now or timezone.now()
    return {
        "operation_type": operation_type,
        "operation_generation": operation_generation,
        "operation_token_digest": operation_token_digest(operation_token),
        "observed_at": now.isoformat(),
        "expires_at": (now + timedelta(seconds=OBSERVATION_TTL_SECONDS)).isoformat(),
        "payload": payload,
    }


def validate_operation_observation(
    snapshot,
    *,
    operation_type,
    operation_generation,
    operation_token,
    now=None,
):
    if not snapshot:
        raise ObservationError("OBSERVATION_REQUIRED")
    if not isinstance(snapshot, dict):
        raise ObservationError("OBSERVATION_STALE")
    expires_at = parse_datetime(str(snapshot.get("expires_at") or ""))
    if (
        snapshot.get("operation_type") != operation_type
        or snapshot.get("operation_generation") != operation_generation
        or snapshot.get("operation_token_digest")
        != operation_token_digest(operation_token)
        or expires_at is None
        or expires_at <= (now or timezone.now())
        or not isinstance(snapshot.get("payload"), dict)
    ):
        raise ObservationError("OBSERVATION_STALE")
    return snapshot["payload"]
