import pytest

pytestmark = pytest.mark.django_db


def _item(
    user,
    config,
    *,
    business_name="Billing",
    purpose="Monthly exports",
    project="",
    environment="development",
    notes="",
    suffix="preview1",
):
    from object_storage.services.naming import render_bucket_name

    values = {
        "business_name": business_name,
        "purpose": purpose,
        "project": project,
        "environment": environment,
        "notes": notes,
        "initial_suffix": suffix,
    }
    values["rendered_bucket_name"] = render_bucket_name(
        template=config.naming_template,
        prefix="hyperops",
        user=user.get_username(),
        business_name=business_name,
        project=project,
        environment=environment,
        purpose=purpose,
        suffix=suffix,
    )
    return values


def test_submit_batch_reserves_every_bucket_and_local_identity(
    user_factory,
    storage_resource_pool_factory,
    platform_object_storage_config,
):
    from object_storage.models import ApplicationItem, Bucket, CloudIdentity
    from object_storage.services.applications import create_application_batch
    from object_storage.services.policy import count_quota_consuming_buckets

    user = user_factory(username="alice")
    pool = storage_resource_pool_factory(enabled=True)
    items = [
        _item(user, platform_object_storage_config, suffix="preview1"),
        _item(
            user,
            platform_object_storage_config,
            business_name="Archive",
            purpose="Retention",
            project="finance",
            environment="production",
            notes="Seven years",
            suffix="preview2",
        ),
    ]

    batch = create_application_batch(
        user=user,
        resource_pool=pool,
        idempotency_key="batch-1",
        items=items,
        enqueue=False,
    )

    identity = CloudIdentity.objects.get(user=user)
    assert identity.state == CloudIdentity.State.PROVISIONING
    assert batch.item_count == 2
    assert batch.pending_count == 2
    assert batch.items.count() == 2
    assert count_quota_consuming_buckets(user) == 2
    assert list(batch.items.values_list("status", flat=True)) == [
        ApplicationItem.Status.PENDING,
        ApplicationItem.Status.PENDING,
    ]
    assert list(
        Bucket.objects.filter(owner=user)
        .order_by("id")
        .values_list("name", "state", "business_name", "purpose")
    ) == [
        (
            items[0]["rendered_bucket_name"],
            Bucket.State.REQUESTED,
            "Billing",
            "Monthly exports",
        ),
        (
            items[1]["rendered_bucket_name"],
            Bucket.State.REQUESTED,
            "Archive",
            "Retention",
        ),
    ]
    assert all(item.bucket_id for item in batch.items.all())
    assert all(
        item.bucket.cloud_marker == f"hyperops:bucket:item:{item.pk}"
        for item in batch.items.select_related("bucket")
    )


@pytest.mark.parametrize("missing_field", ["business_name", "purpose"])
def test_submit_batch_rejects_missing_required_item_fields_atomically(
    missing_field,
    user_factory,
    storage_resource_pool_factory,
    platform_object_storage_config,
):
    from object_storage.models import ApplicationBatch, Bucket, CloudIdentity
    from object_storage.services.applications import (
        ApplicationServiceError,
        create_application_batch,
    )

    user = user_factory()
    pool = storage_resource_pool_factory(enabled=True)
    invalid = _item(user, platform_object_storage_config)
    invalid[missing_field] = ""

    with pytest.raises(
        ApplicationServiceError, match=f"{missing_field.upper()}_REQUIRED"
    ):
        create_application_batch(
            user=user,
            resource_pool=pool,
            idempotency_key="invalid-batch",
            items=[invalid],
            enqueue=False,
        )

    assert not ApplicationBatch.objects.exists()
    assert not Bucket.objects.exists()
    assert not CloudIdentity.objects.exists()


def test_submit_batch_reserves_quota_atomically(
    user_factory,
    storage_resource_pool_factory,
    platform_object_storage_config,
):
    from object_storage.models import ApplicationBatch, Bucket, UserBucketQuota
    from object_storage.services.applications import create_application_batch
    from object_storage.services.policy import BucketQuotaExceeded

    user = user_factory()
    UserBucketQuota.objects.create(user=user, bucket_quota=1)
    pool = storage_resource_pool_factory(enabled=True)

    with pytest.raises(BucketQuotaExceeded, match="BUCKET_QUOTA_EXCEEDED"):
        create_application_batch(
            user=user,
            resource_pool=pool,
            idempotency_key="over-quota",
            items=[
                _item(user, platform_object_storage_config, suffix="preview1"),
                _item(
                    user,
                    platform_object_storage_config,
                    business_name="Archive",
                    suffix="preview2",
                ),
            ],
            enqueue=False,
        )

    assert not ApplicationBatch.objects.exists()
    assert not Bucket.objects.exists()


def test_same_idempotency_payload_returns_batch_but_changed_payload_is_rejected(
    user_factory,
    storage_resource_pool_factory,
    platform_object_storage_config,
):
    from object_storage.models import ApplicationBatch, Bucket
    from object_storage.services.applications import (
        ApplicationServiceError,
        create_application_batch,
    )

    user = user_factory()
    pool = storage_resource_pool_factory(enabled=True)
    item = _item(user, platform_object_storage_config)

    first = create_application_batch(
        user=user,
        resource_pool=pool,
        idempotency_key="same-key",
        items=[item],
        enqueue=False,
    )
    replay = create_application_batch(
        user=user,
        resource_pool=pool,
        idempotency_key="same-key",
        items=[dict(reversed(tuple(item.items())))],
        enqueue=False,
    )
    changed = dict(item, notes="changed")

    with pytest.raises(ApplicationServiceError, match="IDEMPOTENCY_KEY_REUSED"):
        create_application_batch(
            user=user,
            resource_pool=pool,
            idempotency_key="same-key",
            items=[changed],
            enqueue=False,
        )

    assert replay.pk == first.pk
    assert ApplicationBatch.objects.count() == 1
    assert Bucket.objects.count() == 1


def test_submit_batch_requires_exact_preview_name(
    user_factory,
    storage_resource_pool_factory,
    platform_object_storage_config,
):
    from object_storage.models import ApplicationBatch, Bucket
    from object_storage.services.applications import (
        ApplicationServiceError,
        create_application_batch,
    )

    user = user_factory()
    pool = storage_resource_pool_factory(enabled=True)
    item = _item(user, platform_object_storage_config)
    item["rendered_bucket_name"] = "different-preview1"

    with pytest.raises(ApplicationServiceError, match="PREVIEW_BUCKET_NAME_MISMATCH"):
        create_application_batch(
            user=user,
            resource_pool=pool,
            idempotency_key="mismatched-preview",
            items=[item],
            enqueue=False,
        )

    assert not ApplicationBatch.objects.exists()
    assert not Bucket.objects.exists()
