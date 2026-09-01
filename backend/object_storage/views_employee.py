import hashlib

from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from object_storage.models import (
    AccessKey,
    ApplicationBatch,
    ApplicationItem,
    AuditEvent,
    Bucket,
    CloudIdentity,
    DeliveryTicket,
)
from object_storage.permissions import (
    HasPlatformObjectStorageAccess,
    RejectTenantScopeMixin,
    RequireIdempotencyKeyMixin,
)
from object_storage.providers.aliyun import build_aliyun_provider
from object_storage.serializers import (
    AccessKeySummarySerializer,
    ApplicationBatchCreateSerializer,
    ApplicationBatchDetailEmployeeSerializer,
    ApplicationBatchEmployeeSerializer,
    ApplicationItemEmployeeSerializer,
    BucketActionSerializer,
    BucketEmployeeSerializer,
    CloudIdentityEmployeeSerializer,
    DeliveryTokenSerializer,
    KeyActionSerializer,
)
from object_storage.services.applications import (
    ApplicationServiceError,
    create_application_batch,
    refresh_batch_status,
)
from object_storage.services.audit import record_audit_event
from object_storage.services.credentials import (
    CredentialDeliveryError,
    CredentialRotationError,
    consume_delivery_token,
    create_delivery_ticket,
    digest_delivery_token,
    disable_access_key,
    enable_access_key,
    revoke_access_key,
    rotate_access_key_for_actor,
)
from object_storage.services.lifecycle import (
    LifecycleError,
    recover_bucket,
    release_bucket,
)
from object_storage.services.platform import PlatformConfigurationError
from object_storage.services.policy import (
    BucketQuotaExceeded,
    count_quota_consuming_buckets,
    effective_bucket_quota,
)


def _no_store(response):
    response["Cache-Control"] = "no-store"
    response["Pragma"] = "no-cache"
    return response


def _error(error_code, status_code=status.HTTP_400_BAD_REQUEST):
    return Response({"error_code": error_code}, status=status_code)


def _service_error(error, default="OBJECT_STORAGE_OPERATION_FAILED"):
    return str(getattr(error, "error_code", "") or default)


def _request_key(request):
    return str(getattr(request, "idempotency_key", "") or "")


def _already_processed(request, action, target_type, target_id):
    return _processed_event(request, action, target_type, target_id) is not None


def _processed_event(request, action, target_type, target_id):
    return AuditEvent.objects.filter(
        actor=request.user,
        action=action,
        target_type=target_type,
        target_id=str(target_id),
        request_id=_request_key(request),
    ).first()


def _record_request(request, action, target_type, target_id, **metadata):
    record_audit_event(
        actor=request.user,
        action=action,
        target_type=target_type,
        target_id=target_id,
        result="accepted",
        request_id=_request_key(request),
        safe_metadata=metadata,
    )


def _provider(access_key):
    return build_aliyun_provider(access_key.cloud_identity.resource_pool)


def disable_access_key_action(*, access_key, actor, reason=""):
    return disable_access_key(
        access_key=access_key,
        actor=actor,
        provider=_provider(access_key),
        reason=reason,
    )


def enable_access_key_action(*, access_key, actor, reason=""):
    return enable_access_key(
        access_key=access_key,
        actor=actor,
        provider=_provider(access_key),
        reason=reason,
    )


def rotate_access_key_action(*, access_key, actor, reason=""):
    active_key_count = AccessKey.objects.filter(
        cloud_identity=access_key.cloud_identity,
        cloud_state__in=(AccessKey.CloudState.ACTIVE, AccessKey.CloudState.INACTIVE),
        deleted_at__isnull=True,
    ).count()
    return rotate_access_key_for_actor(
        identity=access_key.cloud_identity,
        actor=actor,
        provider=_provider(access_key),
        selected_access_key_id=access_key.pk if active_key_count >= 2 else None,
        reason=reason,
    )


def revoke_access_key_action(*, access_key, actor, reason=""):
    return revoke_access_key(
        access_key=access_key,
        actor=actor,
        provider=_provider(access_key),
        reason=reason,
    )


def _rotation_delivery_batch(*, request, access_key):
    digest = hashlib.sha256(_request_key(request).encode("utf-8")).hexdigest()
    now = timezone.now()
    batch, created = ApplicationBatch.objects.get_or_create(
        applicant=request.user,
        idempotency_key=f"credential-rotate-{digest}",
        defaults={
            "payload_digest": digest,
            "status": ApplicationBatch.Status.SUCCEEDED,
            "issued_access_key": access_key,
            "cloud_identity": access_key.cloud_identity,
            "started_at": now,
            "finished_at": now,
        },
    )
    if not created and batch.issued_access_key_id != access_key.pk:
        raise CredentialDeliveryError("IDEMPOTENCY_KEY_REUSED")
    create_delivery_ticket(
        application_batch=batch,
        access_key=access_key,
        user=request.user,
        platform_config=request.object_storage_config,
    )
    return batch


class EmployeeAPIView(RejectTenantScopeMixin, APIView):
    permission_classes = [HasPlatformObjectStorageAccess]


class EmployeeMutationAPIView(
    RejectTenantScopeMixin, RequireIdempotencyKeyMixin, APIView
):
    permission_classes = [HasPlatformObjectStorageAccess]


class NoStoreEmployeeMutationAPIView(EmployeeMutationAPIView):
    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        return _no_store(response)


class EmployeeOverviewView(EmployeeAPIView):
    def get(self, request):
        user = request.user
        identity = CloudIdentity.objects.filter(user=user).first()
        buckets = Bucket.objects.filter(owner=user)
        credentials = AccessKey.objects.filter(cloud_identity__user=user).order_by(
            "-created_at", "-id"
        )
        applications = ApplicationBatch.objects.filter(applicant=user).order_by(
            "-created_at", "-id"
        )[:5]
        limit = effective_bucket_quota(
            user, platform_config=request.object_storage_config
        )
        used = count_quota_consuming_buckets(user)
        return Response(
            {
                "quota": {
                    "used": used,
                    "limit": limit,
                    "remaining": max(0, limit - used),
                },
                "cloud_identity": (
                    CloudIdentityEmployeeSerializer(identity).data if identity else None
                ),
                "buckets": BucketEmployeeSerializer(buckets, many=True).data,
                "credentials": AccessKeySummarySerializer(credentials, many=True).data,
                "applications": ApplicationBatchEmployeeSerializer(
                    applications, many=True
                ).data,
            }
        )


class EmployeeBucketListView(RejectTenantScopeMixin, generics.ListAPIView):
    permission_classes = [HasPlatformObjectStorageAccess]
    serializer_class = BucketEmployeeSerializer
    pagination_class = None

    def get_queryset(self):
        return Bucket.objects.filter(owner=self.request.user)


class EmployeeBucketDetailView(RejectTenantScopeMixin, generics.RetrieveAPIView):
    permission_classes = [HasPlatformObjectStorageAccess]
    serializer_class = BucketEmployeeSerializer
    lookup_url_kwarg = "bucket_id"

    def get_queryset(self):
        return Bucket.objects.filter(owner=self.request.user)


class EmployeeApplicationListCreateView(
    RejectTenantScopeMixin, RequireIdempotencyKeyMixin, APIView
):
    permission_classes = [HasPlatformObjectStorageAccess]

    def get(self, request):
        batches = ApplicationBatch.objects.filter(applicant=request.user).order_by(
            "-created_at", "-id"
        )
        return Response(ApplicationBatchEmployeeSerializer(batches, many=True).data)

    def post(self, request):
        if request.object_storage_config.pause_new_applications:
            return _error("NEW_APPLICATIONS_PAUSED", status.HTTP_409_CONFLICT)
        serializer = ApplicationBatchCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            batch = create_application_batch(
                user=request.user,
                resource_pool=request.object_storage_pool,
                idempotency_key=_request_key(request),
                items=serializer.validated_data["items"],
            )
        except BucketQuotaExceeded:
            return _error("BUCKET_QUOTA_EXCEEDED", status.HTTP_409_CONFLICT)
        except (ApplicationServiceError, PlatformConfigurationError) as error:
            return _error(_service_error(error), status.HTTP_409_CONFLICT)
        return Response(
            ApplicationBatchEmployeeSerializer(batch).data,
            status=status.HTTP_202_ACCEPTED,
        )


class EmployeeApplicationDetailView(RejectTenantScopeMixin, generics.RetrieveAPIView):
    permission_classes = [HasPlatformObjectStorageAccess]
    serializer_class = ApplicationBatchDetailEmployeeSerializer
    lookup_url_kwarg = "application_id"

    def get_queryset(self):
        return ApplicationBatch.objects.filter(
            applicant=self.request.user
        ).prefetch_related("items__attempts", "items__events")


class EmployeeApplicationItemActionView(EmployeeMutationAPIView):
    action = ""

    def post(self, request, application_id, item_id):
        should_enqueue = False
        with transaction.atomic():
            item = get_object_or_404(
                ApplicationItem.objects.select_for_update().select_related("batch"),
                pk=item_id,
                batch_id=application_id,
                batch__applicant=request.user,
            )
            audit_action = f"storage.application_item.{self.action}_requested"
            if _already_processed(request, audit_action, "ApplicationItem", item.pk):
                return Response(ApplicationItemEmployeeSerializer(item).data)
            batch = ApplicationBatch.objects.select_for_update().get(pk=application_id)
            if batch.running_task_id or batch.owner_token:
                return _error("APPLICATION_IN_PROGRESS", status.HTTP_409_CONFLICT)
            if self.action == "retry":
                if item.status not in {
                    ApplicationItem.Status.FAILED,
                    ApplicationItem.Status.WAITING_RETRY,
                }:
                    return _error(
                        "APPLICATION_ITEM_NOT_RETRYABLE", status.HTTP_409_CONFLICT
                    )
                item.status = ApplicationItem.Status.WAITING_RETRY
                item.retry_count += 1
                item.error_code = ""
                item.error_summary = ""
                should_enqueue = True
            else:
                if item.status not in {
                    ApplicationItem.Status.PENDING,
                    ApplicationItem.Status.WAITING_RETRY,
                    ApplicationItem.Status.FAILED,
                }:
                    return _error(
                        "APPLICATION_ITEM_NOT_CANCELLABLE", status.HTTP_409_CONFLICT
                    )
                item.status = ApplicationItem.Status.CANCELLED
                item.error_code = ""
                item.error_summary = ""
                if item.bucket_id:
                    Bucket.objects.filter(
                        pk=item.bucket_id,
                        owner=request.user,
                        state__in=(Bucket.State.REQUESTED, Bucket.State.FAILED),
                    ).update(state=Bucket.State.CANCELLED)
            item.save(
                update_fields=(
                    "status",
                    "retry_count",
                    "error_code",
                    "error_summary",
                    "updated_at",
                )
            )
            batch.started_at = None if self.action == "retry" else batch.started_at
            batch.finished_at = None
            batch.save(update_fields=("started_at", "finished_at", "updated_at"))
            refresh_batch_status(batch)
            _record_request(
                request,
                audit_action,
                "ApplicationItem",
                item.pk,
                application_id=batch.pk,
                item_id=item.pk,
            )
        if should_enqueue:
            from object_storage.tasks import run_storage_application_batch

            try:
                run_storage_application_batch.delay(batch.pk)
            except Exception:
                return _error(
                    "TASK_ENQUEUE_FAILED", status.HTTP_503_SERVICE_UNAVAILABLE
                )
        return Response(
            ApplicationItemEmployeeSerializer(item).data,
            status=status.HTTP_202_ACCEPTED if should_enqueue else status.HTTP_200_OK,
        )


class EmployeeApplicationItemRetryView(EmployeeApplicationItemActionView):
    action = "retry"


class EmployeeApplicationItemCancelView(EmployeeApplicationItemActionView):
    action = "cancel"


class EmployeeCredentialListView(RejectTenantScopeMixin, generics.ListAPIView):
    permission_classes = [HasPlatformObjectStorageAccess]
    serializer_class = AccessKeySummarySerializer
    pagination_class = None

    def get_queryset(self):
        return AccessKey.objects.filter(
            cloud_identity__user=self.request.user
        ).order_by("-created_at", "-id")


class EmployeeCredentialDetailView(RejectTenantScopeMixin, generics.RetrieveAPIView):
    permission_classes = [HasPlatformObjectStorageAccess]
    serializer_class = AccessKeySummarySerializer
    lookup_url_kwarg = "key_id"

    def get_queryset(self):
        return AccessKey.objects.filter(cloud_identity__user=self.request.user)


class EmployeeCredentialActionView(EmployeeMutationAPIView):
    action = ""

    def post(self, request, key_id):
        serializer = KeyActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        access_key = get_object_or_404(
            AccessKey.objects.select_related("cloud_identity__resource_pool"),
            pk=key_id,
            cloud_identity__user=request.user,
        )
        audit_action = f"storage.api.credential.{self.action}"
        processed = _processed_event(request, audit_action, "AccessKey", access_key.pk)
        if processed:
            result = access_key
            payload = AccessKeySummarySerializer(result).data
            application_id = processed.safe_metadata.get("application_id")
            if self.action == "rotate" and application_id:
                batch = ApplicationBatch.objects.filter(pk=application_id).first()
                if batch and batch.issued_access_key_id:
                    payload = AccessKeySummarySerializer(batch.issued_access_key).data
                    payload["delivery_application_id"] = batch.pk
            return Response(payload)
        operation = globals()[f"{self.action}_access_key_action"]
        try:
            result = operation(
                access_key=access_key,
                actor=request.user,
                reason=serializer.validated_data.get("reason", ""),
            )
        except (CredentialRotationError, PlatformConfigurationError) as error:
            return _error(_service_error(error), status.HTTP_409_CONFLICT)
        except Exception:
            return _error(
                "PROVIDER_OPERATION_FAILED", status.HTTP_503_SERVICE_UNAVAILABLE
            )
        payload = AccessKeySummarySerializer(result).data
        metadata = {}
        if self.action == "rotate":
            try:
                batch = _rotation_delivery_batch(request=request, access_key=result)
            except CredentialDeliveryError as error:
                return _error(_service_error(error), status.HTTP_409_CONFLICT)
            payload["delivery_application_id"] = batch.pk
            metadata["application_id"] = batch.pk
        _record_request(
            request,
            audit_action,
            "AccessKey",
            access_key.pk,
            **metadata,
        )
        return Response(payload)


class EmployeeCredentialDisableView(EmployeeCredentialActionView):
    action = "disable"


class EmployeeCredentialEnableView(EmployeeCredentialActionView):
    action = "enable"


class EmployeeCredentialRotateView(EmployeeCredentialActionView):
    action = "rotate"


class EmployeeCredentialRevokeView(EmployeeCredentialActionView):
    action = "revoke"


class EmployeeCredentialDeliveryView(NoStoreEmployeeMutationAPIView):
    idempotency_sensitive = True

    def post(self, request, key_id):
        serializer = DeliveryTokenSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        key = get_object_or_404(
            AccessKey.objects.select_related("cloud_identity"),
            pk=key_id,
            cloud_identity__user=request.user,
        )
        ticket = DeliveryTicket.objects.filter(
            access_key=key,
            user=request.user,
            token_digest=digest_delivery_token(serializer.validated_data["token"]),
        ).first()
        if ticket is None:
            return _error("DELIVERY_TOKEN_INVALID", status.HTTP_404_NOT_FOUND)
        try:
            secret = consume_delivery_token(
                raw_token=serializer.validated_data["token"],
                user=request.user,
                application_batch=ticket.application_batch,
            )
        except CredentialDeliveryError as error:
            return _error(_service_error(error), status.HTTP_400_BAD_REQUEST)
        return Response(secret)


class EmployeeBucketActionView(EmployeeMutationAPIView):
    action = ""

    def post(self, request, bucket_id):
        serializer = BucketActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        bucket = get_object_or_404(
            Bucket.objects.select_related("cloud_identity", "resource_pool"),
            pk=bucket_id,
            owner=request.user,
        )
        audit_action = f"storage.api.bucket.{self.action}"
        if _already_processed(request, audit_action, "Bucket", bucket.pk):
            return Response(BucketEmployeeSerializer(bucket).data)
        operation = release_bucket if self.action == "release" else recover_bucket
        try:
            result = operation(
                bucket=bucket,
                actor=request.user,
                bucket_name=serializer.validated_data["bucket_name"],
                confirmed=serializer.validated_data["confirmed"],
                reason=serializer.validated_data.get("reason", ""),
            )
        except (LifecycleError, BucketQuotaExceeded) as error:
            return _error(_service_error(error), status.HTTP_409_CONFLICT)
        except Exception:
            return _error(
                "PROVIDER_OPERATION_FAILED", status.HTTP_503_SERVICE_UNAVAILABLE
            )
        _record_request(request, audit_action, "Bucket", bucket.pk, bucket_id=bucket.pk)
        return Response(
            BucketEmployeeSerializer(result).data,
            status=(
                status.HTTP_202_ACCEPTED
                if self.action == "release"
                else status.HTTP_200_OK
            ),
        )


class EmployeeBucketReleaseView(EmployeeBucketActionView):
    action = "release"


class EmployeeBucketRecoverView(EmployeeBucketActionView):
    action = "recover"
