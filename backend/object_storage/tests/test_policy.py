import pytest
from django.db import transaction

pytestmark = pytest.mark.django_db


def test_bucket_model_exposes_exact_quota_consuming_states():
    from object_storage.models import Bucket, QUOTA_CONSUMING_STATES

    assert set(QUOTA_CONSUMING_STATES) == {
        Bucket.State.ACTIVE,
        Bucket.State.REQUESTED,
        Bucket.State.CREATING,
        Bucket.State.WAITING_RETRY,
        Bucket.State.RELEASING,
    }
    assert set(Bucket.State.values) - set(QUOTA_CONSUMING_STATES) == {
        Bucket.State.PENDING_DELETION,
        Bucket.State.RELEASED,
        Bucket.State.DELETION_BLOCKED,
        Bucket.State.FAILED,
        Bucket.State.CANCELLED,
    }


def test_count_quota_consuming_buckets_uses_exact_states(
    bucket_factory,
    cloud_identity_factory,
):
    from object_storage.models import Bucket, QUOTA_CONSUMING_STATES
    from object_storage.services.policy import count_quota_consuming_buckets

    identity = cloud_identity_factory()
    for index, state in enumerate(Bucket.State.values, start=1):
        bucket_factory(
            cloud_identity=identity,
            name=f"quota-state-{index}",
            state=state,
        )

    assert count_quota_consuming_buckets(identity.user) == len(QUOTA_CONSUMING_STATES)


def test_effective_quota_uses_override_before_platform_default(
    user_factory,
    platform_object_storage_config,
):
    from object_storage.models import UserBucketQuota
    from object_storage.services.policy import effective_bucket_quota

    user = user_factory()
    platform_object_storage_config.default_bucket_quota = 5
    platform_object_storage_config.save(update_fields=("default_bucket_quota",))

    assert effective_bucket_quota(user) == 5

    UserBucketQuota.objects.create(user=user, bucket_quota=9)

    assert effective_bucket_quota(user) == 9


def test_check_bucket_capacity_supports_one_read_only_batch(
    bucket_factory,
    cloud_identity_factory,
    platform_object_storage_config,
):
    from object_storage.models import Bucket
    from object_storage.services.policy import (
        BucketQuotaExceeded,
        check_bucket_capacity,
    )

    identity = cloud_identity_factory()
    platform_object_storage_config.default_bucket_quota = 5
    platform_object_storage_config.save(update_fields=("default_bucket_quota",))
    for index, state in enumerate(
        (Bucket.State.ACTIVE, Bucket.State.CREATING, Bucket.State.PENDING_DELETION),
        start=1,
    ):
        bucket_factory(
            cloud_identity=identity,
            name=f"batch-capacity-{index}",
            state=state,
        )

    capacity = check_bucket_capacity(identity.user, requested_count=3)

    assert capacity.limit == 5
    assert capacity.used == 2
    assert capacity.requested == 3
    assert capacity.remaining == 0
    with pytest.raises(BucketQuotaExceeded, match="BUCKET_QUOTA_EXCEEDED"):
        check_bucket_capacity(identity.user, requested_count=4)


def test_check_bucket_capacity_rejects_non_positive_batch(user_factory):
    from object_storage.services.policy import check_bucket_capacity

    with pytest.raises(ValueError, match="REQUESTED_BUCKET_COUNT_INVALID"):
        check_bucket_capacity(user_factory(), requested_count=0)


@pytest.mark.django_db(transaction=True)
def test_reserve_bucket_capacity_runs_callback_under_user_lock(
    cloud_identity_factory,
    bucket_factory,
    user_factory,
    monkeypatch,
):
    from django.contrib.auth import get_user_model
    from django.db.models.query import QuerySet

    from object_storage.models import Bucket
    from object_storage.services.policy import reserve_bucket_capacity

    identity = cloud_identity_factory(user=user_factory())
    lock_observations = []
    callback_observations = []
    original_select_for_update = QuerySet.select_for_update

    def tracked_select_for_update(queryset, *args, **kwargs):
        lock_observations.append(
            (queryset.model, transaction.get_connection(queryset.db).in_atomic_block)
        )
        return original_select_for_update(queryset, *args, **kwargs)

    monkeypatch.setattr(QuerySet, "select_for_update", tracked_select_for_update)

    def reserve(locked_user, capacity):
        callback_observations.append(
            (
                locked_user.pk,
                capacity.requested,
                transaction.get_connection().in_atomic_block,
            )
        )
        return bucket_factory(
            cloud_identity=identity,
            name="locked-reservation",
            state=Bucket.State.REQUESTED,
        )

    reserved = reserve_bucket_capacity(
        identity.user,
        requested_count=1,
        reserve_callback=reserve,
    )

    assert lock_observations == [(get_user_model(), True)]
    assert callback_observations == [(identity.user.pk, 1, True)]
    assert reserved.state == Bucket.State.REQUESTED


def test_reserved_bucket_makes_second_reservation_fail(
    cloud_identity_factory,
    bucket_factory,
    platform_object_storage_config,
):
    from object_storage.models import Bucket
    from object_storage.services.policy import (
        BucketQuotaExceeded,
        reserve_bucket_capacity,
    )

    identity = cloud_identity_factory()
    platform_object_storage_config.default_bucket_quota = 1
    platform_object_storage_config.save(update_fields=("default_bucket_quota",))

    reserve_bucket_capacity(
        identity.user,
        requested_count=1,
        reserve_callback=lambda _user, _capacity: bucket_factory(
            cloud_identity=identity,
            name="first-reservation",
            state=Bucket.State.REQUESTED,
        ),
    )

    with pytest.raises(BucketQuotaExceeded, match="BUCKET_QUOTA_EXCEEDED"):
        reserve_bucket_capacity(
            identity.user,
            requested_count=1,
            reserve_callback=lambda _user, _capacity: None,
        )


def test_reservation_rolls_back_callback_bucket_when_callback_fails(
    cloud_identity_factory,
    bucket_factory,
    platform_object_storage_config,
):
    from object_storage.models import Bucket
    from object_storage.services.policy import reserve_bucket_capacity

    identity = cloud_identity_factory()
    platform_object_storage_config.default_bucket_quota = 1
    platform_object_storage_config.save(update_fields=("default_bucket_quota",))

    def reserve_then_fail(_locked_user, _capacity):
        bucket_factory(
            cloud_identity=identity,
            name="rolled-back-reservation",
            state=Bucket.State.REQUESTED,
        )
        raise RuntimeError("RESERVE_FAILED")

    with pytest.raises(RuntimeError, match="RESERVE_FAILED"):
        reserve_bucket_capacity(
            identity.user,
            requested_count=1,
            reserve_callback=reserve_then_fail,
        )

    assert not Bucket.objects.filter(name="rolled-back-reservation").exists()


@pytest.mark.django_db(transaction=True)
def test_concurrent_reservations_compete_for_last_user_quota(
    cloud_identity_factory,
    platform_object_storage_config,
):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from django.db import close_old_connections, connection

    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL row locking is required for this race test")

    from object_storage.models import Bucket
    from object_storage.services.policy import (
        BucketQuotaExceeded,
        reserve_bucket_capacity,
    )

    identity = cloud_identity_factory()
    platform_object_storage_config.default_bucket_quota = 1
    platform_object_storage_config.save(update_fields=("default_bucket_quota",))
    barrier = Barrier(2)

    def reserve(number):
        close_old_connections()
        try:
            barrier.wait()

            def create_bucket(locked_user, _capacity):
                return Bucket.objects.create(
                    owner_id=locked_user.pk,
                    resource_pool_id=identity.resource_pool_id,
                    cloud_identity_id=identity.pk,
                    business_name=f"Concurrent {number}",
                    name=f"concurrent-reservation-{number}",
                    project="quota-race",
                    environment=Bucket.Environment.TEST,
                    purpose="quota concurrency test",
                    region=identity.resource_pool.region,
                    state=Bucket.State.REQUESTED,
                )

            reserve_bucket_capacity(
                identity.user,
                requested_count=1,
                reserve_callback=create_bucket,
            )
            return "reserved"
        except BucketQuotaExceeded:
            return "quota_exceeded"
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(reserve, (1, 2)))

    assert sorted(results) == ["quota_exceeded", "reserved"]
    assert (
        Bucket.objects.filter(
            owner=identity.user,
            state=Bucket.State.REQUESTED,
            name__startswith="concurrent-reservation-",
        ).count()
        == 1
    )


def test_object_policy_is_stable_and_scoped_to_active_owned_buckets(
    bucket_factory,
    cloud_identity_factory,
):
    from object_storage.models import Bucket
    from object_storage.services.policy import (
        BUCKET_ACTIONS,
        OBJECT_ACTIONS,
        build_object_policy,
    )

    identity = cloud_identity_factory()
    active_b = bucket_factory(
        cloud_identity=identity,
        name="owned-b",
        state=Bucket.State.ACTIVE,
    )
    inactive = bucket_factory(
        cloud_identity=identity,
        name="owned-pending-delete",
        state=Bucket.State.PENDING_DELETION,
    )
    active_a = bucket_factory(
        cloud_identity=identity,
        name="owned-a",
        state=Bucket.State.ACTIVE,
    )

    policy = build_object_policy([active_b, inactive, active_a])

    assert policy == build_object_policy([active_a, active_b, inactive])
    assert policy == {
        "Version": "1",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": list(BUCKET_ACTIONS),
                "Resource": ["acs:oss:*:*:owned-a", "acs:oss:*:*:owned-b"],
            },
            {
                "Effect": "Allow",
                "Action": list(OBJECT_ACTIONS),
                "Resource": [
                    "acs:oss:*:*:owned-a/*",
                    "acs:oss:*:*:owned-b/*",
                ],
            },
        ],
    }
    serialized = str(policy)
    for forbidden in (
        "tenant",
        "oss:CreateBucket",
        "oss:DeleteBucket",
        "oss:PutBucketAcl",
        "oss:PutBucketPolicy",
        "ram:",
    ):
        assert forbidden not in serialized


def test_object_policy_owner_scope_excludes_another_users_active_bucket(
    bucket_factory,
    cloud_identity_factory,
):
    from object_storage.models import Bucket
    from object_storage.services.policy import build_object_policy

    owner = cloud_identity_factory()
    another_owner = cloud_identity_factory()
    bucket_factory(
        cloud_identity=owner,
        name="owned-bucket",
        state=Bucket.State.ACTIVE,
    )
    bucket_factory(
        cloud_identity=another_owner,
        name="foreign-bucket",
        state=Bucket.State.ACTIVE,
    )

    policy = build_object_policy(Bucket.objects.all(), owner=owner.user)

    serialized = str(policy)
    assert "owned-bucket" in serialized
    assert "foreign-bucket" not in serialized
    assert build_object_policy([]) == {"Version": "1", "Statement": []}


def test_object_policy_allows_complete_object_and_multipart_workflow():
    from object_storage.services.policy import BUCKET_ACTIONS, OBJECT_ACTIONS

    assert set(BUCKET_ACTIONS) == {"oss:ListObjects"}
    assert set(OBJECT_ACTIONS) == {
        "oss:GetObject",
        "oss:PutObject",
        "oss:DeleteObject",
        "oss:InitiateMultipartUpload",
        "oss:UploadPart",
        "oss:CompleteMultipartUpload",
        "oss:AbortMultipartUpload",
        "oss:ListParts",
    }
