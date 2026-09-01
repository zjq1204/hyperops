from dataclasses import dataclass

from django.contrib.auth import get_user_model
from django.db import transaction

from object_storage.models import (
    Bucket,
    PlatformObjectStorageConfig,
    QUOTA_CONSUMING_STATES,
    UserBucketQuota,
)

BUCKET_ACTIONS = ("oss:ListObjects",)
OBJECT_ACTIONS = (
    "oss:GetObject",
    "oss:PutObject",
    "oss:DeleteObject",
    "oss:InitiateMultipartUpload",
    "oss:UploadPart",
    "oss:CompleteMultipartUpload",
    "oss:AbortMultipartUpload",
    "oss:ListParts",
)


class BucketQuotaExceeded(RuntimeError):
    pass


@dataclass(frozen=True)
class BucketCapacity:
    limit: int
    used: int
    requested: int
    remaining: int


def count_quota_consuming_buckets(user):
    return Bucket.objects.filter(
        owner=user,
        state__in=QUOTA_CONSUMING_STATES,
    ).count()


def effective_bucket_quota(user, *, platform_config=None):
    override = (
        UserBucketQuota.objects.filter(user=user)
        .values_list("bucket_quota", flat=True)
        .first()
    )
    if override is not None:
        return override
    config = platform_config or PlatformObjectStorageConfig.objects.get(
        singleton_key="default"
    )
    return config.default_bucket_quota


@transaction.atomic
def ensure_bucket_capacity(user, *, requested=1, platform_config=None):
    if isinstance(requested, bool) or not isinstance(requested, int) or requested < 1:
        raise ValueError("REQUESTED_BUCKET_COUNT_INVALID")
    locked_user = get_user_model().objects.select_for_update().get(pk=user.pk)
    used = count_quota_consuming_buckets(locked_user)
    limit = effective_bucket_quota(locked_user, platform_config=platform_config)
    if used + requested > limit:
        raise BucketQuotaExceeded("BUCKET_QUOTA_EXCEEDED")
    return BucketCapacity(
        limit=limit,
        used=used,
        requested=requested,
        remaining=limit - used - requested,
    )


def enforce_bucket_quota(user, *, requested=1, platform_config=None):
    return ensure_bucket_capacity(
        user,
        requested=requested,
        platform_config=platform_config,
    )


def _active_buckets(buckets, *, owner=None):
    if hasattr(buckets, "filter"):
        active = buckets.filter(state=Bucket.State.ACTIVE)
        if owner is not None:
            active = active.filter(owner=owner)
        return list(active)
    return [
        bucket
        for bucket in buckets
        if getattr(bucket, "state", Bucket.State.ACTIVE) == Bucket.State.ACTIVE
        and (owner is None or getattr(bucket, "owner_id", None) == owner.pk)
    ]


def build_object_policy(buckets, *, owner=None):
    active_buckets = sorted(
        _active_buckets(buckets, owner=owner), key=lambda item: item.name
    )
    bucket_resources = [f"acs:oss:*:*:{bucket.name}" for bucket in active_buckets]
    object_resources = [f"acs:oss:*:*:{bucket.name}/*" for bucket in active_buckets]
    return {
        "Version": "1",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": list(BUCKET_ACTIONS),
                "Resource": bucket_resources,
            },
            {
                "Effect": "Allow",
                "Action": list(OBJECT_ACTIONS),
                "Resource": object_resources,
            },
        ],
    }
