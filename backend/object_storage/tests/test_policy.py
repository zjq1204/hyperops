import pytest

pytestmark = pytest.mark.django_db


def test_quota_counts_current_and_releasing_buckets(
    storage_cloud_identity_factory, storage_bucket_factory
):
    from object_storage.models import StorageBucket
    from object_storage.services.policy import count_quota_consuming_buckets

    identity = storage_cloud_identity_factory()
    for state in (
        StorageBucket.State.REQUESTED,
        StorageBucket.State.CREATING,
        StorageBucket.State.ACTIVE,
        StorageBucket.State.RELEASING,
    ):
        storage_bucket_factory(cloud_identity=identity, state=state)
    for state in (StorageBucket.State.RELEASED, StorageBucket.State.FAILED):
        storage_bucket_factory(cloud_identity=identity, state=state)

    assert count_quota_consuming_buckets(identity.membership) == 4


def test_quota_check_raises_at_tenant_limit(
    storage_cloud_identity_factory, storage_bucket_factory
):
    from object_storage.models import StorageBucket
    from object_storage.services.policy import (
        BucketQuotaExceeded,
        enforce_bucket_quota,
    )

    identity = storage_cloud_identity_factory()
    identity.tenant.default_bucket_quota = 1
    identity.tenant.save(update_fields=("default_bucket_quota",))
    storage_bucket_factory(
        cloud_identity=identity,
        state=StorageBucket.State.ACTIVE,
    )

    with pytest.raises(BucketQuotaExceeded):
        enforce_bucket_quota(identity.membership)


def test_policy_resources_equal_current_owned_active_buckets(
    storage_cloud_identity_factory, storage_bucket_factory
):
    from object_storage.models import StorageBucket
    from object_storage.services.policy import build_object_policy

    identity = storage_cloud_identity_factory()
    active = storage_bucket_factory(
        cloud_identity=identity,
        name="owned-active",
        state=StorageBucket.State.ACTIVE,
    )
    storage_bucket_factory(
        cloud_identity=identity,
        name="owned-released",
        state=StorageBucket.State.RELEASED,
    )

    policy = build_object_policy(
        StorageBucket.objects.filter(owner=identity.membership)
    )
    resources = {
        resource
        for statement in policy["Statement"]
        for resource in statement["Resource"]
    }

    assert resources == {
        f"acs:oss:*:*:{active.name}",
        f"acs:oss:*:*:{active.name}/*",
    }


def test_policy_never_contains_bucket_delete_acl_or_other_service_actions(
    storage_bucket_factory,
):
    from object_storage.services.policy import build_object_policy

    bucket = storage_bucket_factory(state="active")

    policy = build_object_policy([bucket])
    actions = {
        action for statement in policy["Statement"] for action in statement["Action"]
    }

    assert "oss:DeleteBucket" not in actions
    assert "oss:PutBucketAcl" not in actions
    assert "oss:PutBucketPolicy" not in actions
    assert all(action.startswith("oss:") for action in actions)
