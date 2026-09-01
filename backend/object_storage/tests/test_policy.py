import pytest

pytestmark = pytest.mark.django_db


def test_bucket_model_exposes_phase_one_quota_states():
    from object_storage.models import Bucket

    quota_consuming = {
        Bucket.State.REQUESTED,
        Bucket.State.CREATING,
        Bucket.State.ACTIVE,
        Bucket.State.RELEASING,
    }
    quota_released = {
        Bucket.State.PENDING_DELETE,
        Bucket.State.RELEASED,
        Bucket.State.DELETE_BLOCKED,
        Bucket.State.FAILED,
    }

    assert quota_consuming.isdisjoint(quota_released)
    assert quota_consuming | quota_released == set(Bucket.State.values)


def test_platform_quota_and_delivery_defaults_are_future_resource_defaults(
    platform_object_storage_config,
):
    config = platform_object_storage_config

    assert config.default_bucket_quota == 5
    assert config.delivery_lifetime_seconds == 86400
    assert config.audit_retention_days == 30
    assert config.pause_new_applications is True
    assert config.pause_key_operations is True
