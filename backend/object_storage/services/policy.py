from django.db import transaction

from object_storage.models import StorageBucket, StorageMembership

QUOTA_CONSUMING_STATES = (
    StorageBucket.State.REQUESTED,
    StorageBucket.State.CREATING,
    StorageBucket.State.ACTIVE,
    StorageBucket.State.RELEASING,
)

BUCKET_ACTIONS = ("oss:ListObjects",)
OBJECT_ACTIONS = (
    "oss:GetObject",
    "oss:PutObject",
    "oss:DeleteObject",
    "oss:AbortMultipartUpload",
    "oss:ListParts",
)


class BucketQuotaExceeded(RuntimeError):
    pass


def count_quota_consuming_buckets(membership):
    return StorageBucket.objects.filter(
        tenant=membership.tenant,
        owner=membership,
        state__in=QUOTA_CONSUMING_STATES,
    ).count()


@transaction.atomic
def enforce_bucket_quota(membership):
    locked_membership = (
        StorageMembership.objects.select_for_update()
        .select_related("tenant")
        .get(pk=membership.pk)
    )
    current_count = count_quota_consuming_buckets(locked_membership)
    if current_count >= locked_membership.tenant.default_bucket_quota:
        raise BucketQuotaExceeded("BUCKET_QUOTA_EXCEEDED")
    return locked_membership


def _active_buckets(buckets):
    if hasattr(buckets, "filter"):
        return list(buckets.filter(state=StorageBucket.State.ACTIVE))
    return [
        bucket
        for bucket in buckets
        if getattr(bucket, "state", StorageBucket.State.ACTIVE)
        == StorageBucket.State.ACTIVE
    ]


def build_object_policy(buckets):
    active_buckets = sorted(_active_buckets(buckets), key=lambda item: item.name)
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
