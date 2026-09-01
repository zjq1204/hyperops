from types import SimpleNamespace
from unittest.mock import ANY

import pytest


def _batch(batch_id=10, status="succeeded"):
    return SimpleNamespace(
        pk=batch_id,
        status=status,
        item_count=2,
        pending_count=0,
        success_count=2 if status == "succeeded" else 1,
        failed_count=0 if status == "succeeded" else 1,
    )


def test_transient_batch_failure_retries_with_exponential_backoff(monkeypatch):
    from object_storage.services.provider_errors import ObjectStorageProviderError
    from object_storage import tasks

    retry_calls = []
    runner = SimpleNamespace(
        request=SimpleNamespace(id="task-id", retries=0),
        retry=lambda **kwargs: retry_calls.append(kwargs),
    )
    monkeypatch.setattr(
        tasks,
        "execute_application_batch",
        lambda batch_id, **kwargs: (_ for _ in ()).throw(
            ObjectStorageProviderError("PROVIDER_TIMEOUT", retryable=True)
        ),
    )

    with pytest.raises(Exception):
        tasks._run_storage_application_batch(runner, 10)

    assert retry_calls == [{"exc": ANY, "countdown": 2}]


def test_transient_batch_failure_becomes_manual_after_three_retries(monkeypatch):
    from object_storage.services.provider_errors import ObjectStorageProviderError
    from object_storage import tasks

    retry_calls = []
    manual_calls = []
    runner = SimpleNamespace(
        request=SimpleNamespace(id="task-id", retries=3),
        retry=lambda **kwargs: retry_calls.append(kwargs),
    )
    monkeypatch.setattr(
        tasks,
        "execute_application_batch",
        lambda batch_id, **kwargs: (_ for _ in ()).throw(
            ObjectStorageProviderError("PROVIDER_TIMEOUT", retryable=True)
        ),
    )
    monkeypatch.setattr(
        tasks,
        "mark_batch_manual_required",
        lambda batch_id, error: manual_calls.append((batch_id, error.error_code))
        or _batch(batch_id, "manual_required"),
    )

    result = tasks._run_storage_application_batch(runner, 10)

    assert retry_calls == []
    assert manual_calls == [(10, "PROVIDER_TIMEOUT")]
    assert result == {
        "batch_id": 10,
        "status": "manual_required",
        "counts": {
            "item_count": 2,
            "pending_count": 0,
            "success_count": 1,
            "failed_count": 1,
        },
    }


def test_permanent_batch_failure_does_not_retry(monkeypatch):
    from object_storage.services.provider_errors import ObjectStorageProviderError
    from object_storage import tasks

    retry_calls = []
    manual_calls = []
    runner = SimpleNamespace(
        request=SimpleNamespace(id="task-id", retries=0),
        retry=lambda **kwargs: retry_calls.append(kwargs),
    )
    monkeypatch.setattr(
        tasks,
        "execute_application_batch",
        lambda batch_id, **kwargs: (_ for _ in ()).throw(
            ObjectStorageProviderError("PROVIDER_PERMISSION_DENIED")
        ),
    )
    monkeypatch.setattr(
        tasks,
        "mark_batch_manual_required",
        lambda batch_id, error: manual_calls.append((batch_id, error.error_code))
        or _batch(batch_id, "manual_required"),
    )

    result = tasks._run_storage_application_batch(runner, 10)

    assert retry_calls == []
    assert manual_calls == [(10, "PROVIDER_PERMISSION_DENIED")]
    assert result["status"] == "manual_required"


def test_task_result_is_json_safe_batch_summary(monkeypatch):
    from object_storage import tasks

    runner = SimpleNamespace(request=SimpleNamespace(id="task-id", retries=0))
    monkeypatch.setattr(
        tasks,
        "execute_application_batch",
        lambda batch_id, **kwargs: _batch(batch_id),
    )

    result = tasks._run_storage_application_batch(runner, 42)

    assert result == {
        "batch_id": 42,
        "status": "succeeded",
        "counts": {
            "item_count": 2,
            "pending_count": 0,
            "success_count": 2,
            "failed_count": 0,
        },
    }


@pytest.mark.django_db
def test_claim_recovery_task_scans_only_expired_running_batches(
    user_factory, monkeypatch
):
    from datetime import timedelta

    from django.utils import timezone

    from object_storage import tasks
    from object_storage.models import ApplicationBatch

    user = user_factory()
    now = timezone.now()
    expired = ApplicationBatch.objects.create(
        applicant=user,
        idempotency_key="expired-claim",
        status=ApplicationBatch.Status.RUNNING,
        running_task_id="expired-worker",
        run_lease_until=now - timedelta(minutes=1),
    )
    ApplicationBatch.objects.create(
        applicant=user,
        idempotency_key="active-claim",
        status=ApplicationBatch.Status.RUNNING,
        running_task_id="active-worker",
        run_lease_until=now + timedelta(minutes=1),
    )
    ApplicationBatch.objects.create(
        applicant=user,
        idempotency_key="expired-but-pending",
        status=ApplicationBatch.Status.PENDING,
        running_task_id="",
        run_lease_until=now - timedelta(minutes=1),
    )
    recovery_calls = []
    enqueue_calls = []

    def recover(batch_id, *, now):
        recovery_calls.append((batch_id, now))
        return SimpleNamespace(pk=batch_id, running_task_id="", owner_token="")

    monkeypatch.setattr(
        tasks,
        "recover_expired_application_claim",
        recover,
        raising=False,
    )
    monkeypatch.setattr(
        tasks.run_storage_application_batch,
        "delay",
        lambda batch_id: enqueue_calls.append(batch_id),
    )

    result = tasks.recover_expired_application_claims()

    assert [batch_id for batch_id, _now in recovery_calls] == [expired.pk]
    assert enqueue_calls == [expired.pk]
    assert result == {
        "candidate_count": 1,
        "recovered_count": 1,
        "enqueued_count": 1,
        "failed_enqueue_count": 0,
        "failed_count": 0,
    }


@pytest.mark.django_db
def test_claim_recovery_enqueue_failure_marks_batch_manual_and_audits(
    user_factory, monkeypatch
):
    from datetime import timedelta

    from django.utils import timezone

    from object_storage import tasks
    from object_storage.models import ApplicationBatch, AuditEvent

    user = user_factory()
    batch = ApplicationBatch.objects.create(
        applicant=user,
        idempotency_key="recovered-enqueue-failure",
        status=ApplicationBatch.Status.RUNNING,
        running_task_id="expired-worker",
        owner_token="expired-owner-token",
        run_lease_until=timezone.now() - timedelta(minutes=1),
    )

    def recover(batch_id, *, now):
        del now
        ApplicationBatch.objects.filter(pk=batch_id).update(
            running_task_id="",
            owner_token="",
            run_lease_until=None,
        )
        return ApplicationBatch.objects.get(pk=batch_id)

    monkeypatch.setattr(tasks, "recover_expired_application_claim", recover)
    monkeypatch.setattr(
        tasks.run_storage_application_batch,
        "delay",
        lambda _batch_id: (_ for _ in ()).throw(RuntimeError("broker unavailable")),
    )

    result = tasks.recover_expired_application_claims()

    batch.refresh_from_db()
    audit = AuditEvent.objects.get(
        action="storage.application.claim_recovery_enqueue_failed"
    )
    assert batch.status == ApplicationBatch.Status.MANUAL_REQUIRED
    assert batch.error_code == "CLAIM_RECOVERY_ENQUEUE_FAILED"
    assert batch.running_task_id == ""
    assert batch.owner_token == ""
    assert audit.target_id == str(batch.pk)
    assert audit.result == "manual_required"
    assert audit.safe_metadata == {
        "application_id": batch.pk,
        "error_code": "CLAIM_RECOVERY_ENQUEUE_FAILED",
    }
    assert result == {
        "candidate_count": 1,
        "recovered_count": 1,
        "enqueued_count": 0,
        "failed_enqueue_count": 1,
        "failed_count": 0,
    }


def test_object_storage_periodic_tasks_are_registered():
    from object_storage import periodic_tasks
    from core.periodic_registry import TASK_REGISTRY

    TASK_REGISTRY.clear()
    periodic_tasks.register_periodic_tasks()

    entry = TASK_REGISTRY._entries["object-storage.audit-cleanup"]
    assert entry["task"] == "object_storage.delete_expired_audit_events"
    assert entry["schedule"] == "0 3 * * *"
    assert entry["queue"] == "object_storage"

    recovery = TASK_REGISTRY._entries["object-storage.claim-recovery"]
    assert recovery["task"] == "object_storage.recover_expired_application_claims"
    assert recovery["schedule"] == "*/5 * * * *"
    assert recovery["queue"] == "object_storage"
