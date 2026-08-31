from types import SimpleNamespace
from unittest.mock import ANY

import pytest


def test_transient_provider_failure_retries_until_three_attempts(monkeypatch):
    from object_storage.services.provider_errors import ObjectStorageProviderError
    from object_storage import tasks

    retry_calls = []
    runner = SimpleNamespace(
        request=SimpleNamespace(retries=0),
        retry=lambda **kwargs: retry_calls.append(kwargs),
    )
    monkeypatch.setattr(
        tasks,
        "execute_application",
        lambda application_id, **kwargs: (_ for _ in ()).throw(
            ObjectStorageProviderError("PROVIDER_TIMEOUT", retryable=True)
        ),
    )

    with pytest.raises(Exception):
        tasks._run_storage_application(runner, 10)

    assert retry_calls == [{"exc": ANY, "countdown": 2}]


def test_transient_provider_failure_is_not_retried_after_three_attempts(monkeypatch):
    from object_storage.services.provider_errors import ObjectStorageProviderError
    from object_storage import tasks

    retry_calls = []
    manual_calls = []
    runner = SimpleNamespace(
        request=SimpleNamespace(retries=3),
        retry=lambda **kwargs: retry_calls.append(kwargs),
    )
    monkeypatch.setattr(
        tasks,
        "execute_application",
        lambda application_id, **kwargs: (_ for _ in ()).throw(
            ObjectStorageProviderError("PROVIDER_TIMEOUT", retryable=True)
        ),
    )
    monkeypatch.setattr(
        tasks,
        "mark_application_manual_required",
        lambda application_id, error: manual_calls.append(
            (application_id, error.error_code)
        )
        or SimpleNamespace(pk=application_id, status="manual_required"),
    )

    result = tasks._run_storage_application(runner, 10)

    assert retry_calls == []
    assert manual_calls == [(10, "PROVIDER_TIMEOUT")]
    assert result == {"application_id": 10, "status": "manual_required"}


def test_business_error_enters_manual_required_without_retry(monkeypatch):
    from object_storage.services.provider_errors import ObjectStorageProviderError
    from object_storage import tasks

    retry_calls = []
    manual_calls = []
    runner = SimpleNamespace(
        request=SimpleNamespace(retries=0),
        retry=lambda **kwargs: retry_calls.append(kwargs),
    )
    monkeypatch.setattr(
        tasks,
        "execute_application",
        lambda application_id, **kwargs: (_ for _ in ()).throw(
            ObjectStorageProviderError("BUCKET_NAME_CONFLICT", retryable=False)
        ),
    )
    monkeypatch.setattr(
        tasks,
        "mark_application_manual_required",
        lambda application_id, error: manual_calls.append(
            (application_id, error.error_code)
        )
        or SimpleNamespace(pk=application_id, status="manual_required"),
    )

    result = tasks._run_storage_application(runner, 10)

    assert retry_calls == []
    assert manual_calls == [(10, "BUCKET_NAME_CONFLICT")]
    assert result == {"application_id": 10, "status": "manual_required"}


def test_task_returns_json_safe_application_result(monkeypatch):
    from object_storage import tasks

    runner = SimpleNamespace(request=SimpleNamespace(retries=0))
    monkeypatch.setattr(
        tasks,
        "execute_application",
        lambda application_id, **kwargs: SimpleNamespace(
            pk=application_id, status="succeeded"
        ),
    )

    result = tasks._run_storage_application(runner, 42)

    assert result == {"application_id": 42, "status": "succeeded"}


def test_audit_cleanup_is_registered_on_a_daily_schedule():
    from object_storage import periodic_tasks
    from core.periodic_registry import TASK_REGISTRY

    TASK_REGISTRY.clear()
    periodic_tasks.register_periodic_tasks()

    entry = TASK_REGISTRY._entries["object-storage.audit-cleanup"]
    assert entry["task"] == "object_storage.delete_expired_audit_events"
    assert entry["schedule"] == "0 3 * * *"
    assert entry["queue"] == "object_storage"
