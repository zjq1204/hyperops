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


def test_audit_cleanup_is_registered_on_a_daily_schedule():
    from object_storage import periodic_tasks
    from core.periodic_registry import TASK_REGISTRY

    TASK_REGISTRY.clear()
    periodic_tasks.register_periodic_tasks()

    entry = TASK_REGISTRY._entries["object-storage.audit-cleanup"]
    assert entry["task"] == "object_storage.delete_expired_audit_events"
    assert entry["schedule"] == "0 3 * * *"
    assert entry["queue"] == "object_storage"
