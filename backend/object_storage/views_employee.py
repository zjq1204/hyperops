from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from object_storage.models import (
    StorageAccessKey,
    StorageApplication,
    StorageBucket,
    StorageCloudIdentity,
    StorageMembership,
    StorageResourcePool,
)
from object_storage.permissions import (
    IsActiveObjectStorageMember,
    IsObjectStorageSuperuser,
)
from object_storage.providers.aliyun import build_aliyun_provider
from object_storage.serializers import (
    DeliveryTokenSerializer,
    MembershipActionSerializer,
    ReleaseBucketSerializer,
    RevealAccessKeySerializer,
    RotationRequestSerializer,
    StorageAccessKeySummarySerializer,
    StorageApplicationCreateSerializer,
    StorageApplicationEmployeeSerializer,
    StorageBucketEmployeeSerializer,
)
from object_storage.services.applications import create_application
from object_storage.services.credentials import (
    CredentialDeliveryError,
    consume_delivery_token,
    get_ephemeral_delivery_token,
    reveal_access_key,
    rotation_candidate,
)
from object_storage.services.provider_errors import ObjectStorageProviderError


def get_provider_for_pool(pool):
    return build_aliyun_provider(pool)


def _no_store(response):
    response["Cache-Control"] = "no-store"
    response["Pragma"] = "no-cache"
    return response


def _client_ip(request):
    forwarded = str(request.META.get("HTTP_X_FORWARDED_FOR") or "")
    return (
        forwarded.split(",", 1)[0].strip() if forwarded else None
    ) or request.META.get("REMOTE_ADDR")


def _idempotency_key(request):
    key = str(request.headers.get("Idempotency-Key") or "").strip()
    if not key:
        raise ValidationError({"idempotency_key": "IDEMPOTENCY_KEY_REQUIRED"})
    return key


def _existing_application(membership, idempotency_key):
    return StorageApplication.objects.filter(
        tenant=membership.tenant,
        applicant=membership,
        idempotency_key=idempotency_key,
    ).first()


def _application_response(application):
    return Response(
        StorageApplicationEmployeeSerializer(application).data,
        status=status.HTTP_202_ACCEPTED,
    )


class NoStoreAPIView(APIView):
    def finalize_response(self, request, response, *args, **kwargs):
        return _no_store(super().finalize_response(request, response, *args, **kwargs))


class EmployeeBucketListView(generics.ListAPIView):
    permission_classes = [IsActiveObjectStorageMember]
    serializer_class = StorageBucketEmployeeSerializer
    pagination_class = None

    def get_queryset(self):
        return StorageBucket.objects.filter(owner=self.request.storage_membership)


class EmployeeCredentialDetailView(generics.RetrieveAPIView):
    permission_classes = [IsActiveObjectStorageMember]
    serializer_class = StorageAccessKeySummarySerializer
    lookup_url_kwarg = "key_id"

    def get_queryset(self):
        return StorageAccessKey.objects.filter(
            cloud_identity__membership=self.request.storage_membership
        )


class EmployeeApplicationCreateView(APIView):
    permission_classes = [IsActiveObjectStorageMember]

    def post(self, request):
        serializer = StorageApplicationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        membership = request.storage_membership
        pool = get_object_or_404(
            StorageResourcePool,
            tenant=membership.tenant,
            enabled=True,
        )
        action_type = (
            StorageApplication.ActionType.ADD_BUCKET
            if StorageAccessKey.objects.filter(
                cloud_identity__membership=membership,
                cloud_state__in=(
                    StorageAccessKey.CloudState.ACTIVE,
                    StorageAccessKey.CloudState.INACTIVE,
                ),
            ).exists()
            else StorageApplication.ActionType.FIRST_BUCKET_AND_CREDENTIAL
        )
        application = create_application(
            membership=membership,
            resource_pool=pool,
            action_type=action_type,
            idempotency_key=_idempotency_key(request),
            request_fields=serializer.validated_data,
        )
        return _application_response(application)


class EmployeeCredentialDeliveryView(NoStoreAPIView):
    permission_classes = [IsActiveObjectStorageMember]

    def post(self, request):
        serializer = DeliveryTokenSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            secret = consume_delivery_token(
                raw_token=serializer.validated_data["token"],
                membership=request.storage_membership,
            )
        except CredentialDeliveryError as exc:
            return _no_store(
                Response(
                    {"error_code": exc.error_code},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            )
        return _no_store(Response(secret))


class EmployeeDeliveryTokenView(NoStoreAPIView):
    permission_classes = [IsActiveObjectStorageMember]

    def get(self, request, application_id):
        application = get_object_or_404(
            StorageApplication.objects.select_related("delivery_ticket"),
            pk=application_id,
            applicant=request.storage_membership,
        )
        try:
            raw_token = get_ephemeral_delivery_token(
                application=application,
                membership=request.storage_membership,
            )
        except CredentialDeliveryError as exc:
            return Response(
                {"error_code": exc.error_code},
                status=status.HTTP_410_GONE,
            )
        return Response({"token": raw_token})


class EmployeeRotationPreviewView(APIView):
    permission_classes = [IsActiveObjectStorageMember]

    def get(self, request):
        identity = (
            StorageCloudIdentity.objects.filter(
                membership=request.storage_membership,
            )
            .order_by("id")
            .first()
        )
        candidate = rotation_candidate(identity) if identity else None
        return Response(
            {
                "candidate": (
                    StorageAccessKeySummarySerializer(candidate).data
                    if candidate
                    else None
                )
            }
        )

    def post(self, request):
        serializer = RotationRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        membership = request.storage_membership
        idempotency_key = _idempotency_key(request)
        existing = _existing_application(membership, idempotency_key)
        if existing:
            return _application_response(existing)
        identity = get_object_or_404(
            StorageCloudIdentity.objects.filter(
                membership=membership,
                resource_pool__enabled=True,
            )
        )
        candidate = rotation_candidate(identity)
        candidate_id = serializer.validated_data.get("candidate_access_key_id")
        if candidate and (
            not serializer.validated_data["confirmed"] or candidate_id != candidate.pk
        ):
            return Response(
                {"error_code": "ROTATION_CONFIRMATION_REQUIRED"},
                status=status.HTTP_409_CONFLICT,
            )
        application = create_application(
            membership=membership,
            resource_pool=identity.resource_pool,
            action_type=StorageApplication.ActionType.ROTATE_CREDENTIAL,
            idempotency_key=idempotency_key,
            request_fields={
                "candidate_access_key_id": candidate_id,
                "confirmed": serializer.validated_data["confirmed"],
            },
        )
        return _application_response(application)


class EmployeeBucketReleaseView(APIView):
    permission_classes = [IsActiveObjectStorageMember]

    def post(self, request, bucket_id):
        serializer = ReleaseBucketSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        bucket = get_object_or_404(
            StorageBucket.objects.select_related("resource_pool"),
            pk=bucket_id,
            owner=request.storage_membership,
        )
        idempotency_key = _idempotency_key(request)
        existing = _existing_application(
            request.storage_membership,
            idempotency_key,
        )
        if existing:
            return _application_response(existing)
        try:
            emptiness = get_provider_for_pool(
                bucket.resource_pool
            ).inspect_bucket_emptiness(bucket)
        except ObjectStorageProviderError as exc:
            return Response(
                {"error_code": exc.error_code},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        if not emptiness.is_empty:
            return Response(
                {"error_code": "BUCKET_NOT_EMPTY"},
                status=status.HTTP_409_CONFLICT,
            )
        if serializer.validated_data.get("bucket_name") != bucket.name:
            return Response(
                {"error_code": "BUCKET_NAME_CONFIRMATION_REQUIRED"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        application = create_application(
            membership=request.storage_membership,
            resource_pool=bucket.resource_pool,
            action_type=StorageApplication.ActionType.RELEASE_BUCKET,
            idempotency_key=idempotency_key,
            request_fields={
                "target_bucket_id": bucket.pk,
                "reason": serializer.validated_data.get("reason", ""),
            },
        )
        return _application_response(application)


class ManagementAccessKeyRevealView(NoStoreAPIView):
    permission_classes = [IsObjectStorageSuperuser]

    def post(self, request, key_id):
        serializer = RevealAccessKeySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        access_key = get_object_or_404(StorageAccessKey, pk=key_id)
        secret = reveal_access_key(
            access_key=access_key,
            actor=request.user,
            reason=serializer.validated_data["reason"],
            request_id=str(request.headers.get("X-Request-ID") or ""),
            ip_address=_client_ip(request),
        )
        return _no_store(Response(secret))


class ManagementMembershipStateView(APIView):
    permission_classes = [IsObjectStorageSuperuser]
    action_type = None
    active_state = None

    def post(self, request, membership_id):
        serializer = MembershipActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        idempotency_key = _idempotency_key(request)
        should_enqueue = False
        with transaction.atomic():
            membership = get_object_or_404(
                StorageMembership.objects.select_for_update(), pk=membership_id
            )
            identity = (
                StorageCloudIdentity.objects.select_related("resource_pool")
                .filter(membership=membership)
                .order_by("-resource_pool__enabled", "id")
                .first()
            )
            resource_pool = (
                identity.resource_pool
                if identity is not None
                else get_object_or_404(
                    StorageResourcePool,
                    tenant=membership.tenant,
                    enabled=True,
                )
            )
            application = _existing_application(membership, idempotency_key)
            if application is None:
                membership.is_active = self.active_state
                membership.deactivated_at = (
                    None if self.active_state else timezone.now()
                )
                membership.save(
                    update_fields=("is_active", "deactivated_at", "updated_at")
                )
                application = create_application(
                    membership=membership,
                    resource_pool=resource_pool,
                    action_type=self.action_type,
                    idempotency_key=idempotency_key,
                    request_fields={"reason": serializer.validated_data["reason"]},
                    enqueue=False,
                    actor=request.user,
                )
                should_enqueue = True
        from object_storage.tasks import run_storage_application

        if should_enqueue:
            run_storage_application.delay(application.pk)
        return _application_response(application)


class ManagementMembershipSuspendView(ManagementMembershipStateView):
    action_type = StorageApplication.ActionType.SUSPEND_MEMBERSHIP
    active_state = False


class ManagementMembershipReactivateView(ManagementMembershipStateView):
    action_type = StorageApplication.ActionType.REACTIVATE_MEMBERSHIP
    active_state = True
