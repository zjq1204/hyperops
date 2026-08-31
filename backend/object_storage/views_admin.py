from datetime import timedelta

from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import generics, status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from object_storage.feishu import get_feishu_client
from object_storage.models import (
    FeishuAppConfig,
    StorageAccessKey,
    StorageApplication,
    StorageAuditEvent,
    StorageBucket,
    StorageCloudIdentity,
    StorageMembership,
    StorageResourcePool,
    StorageTenant,
)
from object_storage.permissions import (
    IsObjectStorageSuperuser,
    RequireIdempotencyKeyMixin,
)
from object_storage.providers.aliyun import build_aliyun_provider
from object_storage.serializers_admin import (
    FeishuAppConfigAdminSerializer,
    StorageAccessKeyAdminSerializer,
    StorageAdminReasonSerializer,
    StorageApplicationAdminSerializer,
    StorageApplicationDetailAdminSerializer,
    StorageAuditEventAdminSerializer,
    StorageBucketAdminSerializer,
    StorageCloudIdentityAdminSerializer,
    StorageMembershipAdminSerializer,
    StorageResourcePoolAdminSerializer,
    StorageTenantAdminSerializer,
)
from object_storage.services.audit import record_audit_event
from object_storage.services.provider_errors import ObjectStorageProviderError


def validate_feishu_config(config):
    return get_feishu_client().validate_config(config)


def validate_resource_pool(pool):
    return build_aliyun_provider(pool).validate_management_identity(pool)


class StorageTenantListCreateView(
    RequireIdempotencyKeyMixin, generics.ListCreateAPIView
):
    permission_classes = [IsObjectStorageSuperuser]
    serializer_class = StorageTenantAdminSerializer
    queryset = StorageTenant.objects.all()


class StorageTenantDetailView(
    RequireIdempotencyKeyMixin, generics.RetrieveUpdateAPIView
):
    permission_classes = [IsObjectStorageSuperuser]
    serializer_class = StorageTenantAdminSerializer
    queryset = StorageTenant.objects.all()
    lookup_url_kwarg = "tenant_id"


class FeishuAppConfigView(RequireIdempotencyKeyMixin, APIView):
    permission_classes = [IsObjectStorageSuperuser]

    def get(self, request, tenant_id):
        tenant = get_object_or_404(StorageTenant, pk=tenant_id)
        config = get_object_or_404(FeishuAppConfig, tenant=tenant)
        return Response(FeishuAppConfigAdminSerializer(config).data)

    def put(self, request, tenant_id):
        tenant = get_object_or_404(StorageTenant, pk=tenant_id)
        config = FeishuAppConfig.objects.filter(tenant=tenant).first()
        serializer = FeishuAppConfigAdminSerializer(
            config,
            data=request.data,
            context={"tenant": tenant},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class FeishuAppValidationView(RequireIdempotencyKeyMixin, APIView):
    permission_classes = [IsObjectStorageSuperuser]

    def post(self, request, tenant_id):
        config = get_object_or_404(FeishuAppConfig, tenant_id=tenant_id)
        try:
            safe_result = validate_feishu_config(config)
        except Exception:
            config.validation_status = FeishuAppConfig.ValidationStatus.INVALID
            config.validation_error_code = "FEISHU_VALIDATION_FAILED"
            config.enabled = False
            config.save(
                update_fields=(
                    "validation_status",
                    "validation_error_code",
                    "enabled",
                    "updated_at",
                )
            )
            return Response(
                {"error_code": "FEISHU_VALIDATION_FAILED"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        config.validation_status = FeishuAppConfig.ValidationStatus.VALID
        config.validation_error_code = ""
        config.last_validated_at = timezone.now()
        config.save(
            update_fields=(
                "validation_status",
                "validation_error_code",
                "last_validated_at",
                "updated_at",
            )
        )
        return Response(
            {
                "validation_status": config.validation_status,
                "capabilities": safe_result,
            }
        )


class StorageResourcePoolListCreateView(
    RequireIdempotencyKeyMixin, generics.ListCreateAPIView
):
    permission_classes = [IsObjectStorageSuperuser]
    serializer_class = StorageResourcePoolAdminSerializer

    def get_queryset(self):
        return StorageResourcePool.objects.filter(tenant_id=self.kwargs["tenant_id"])

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["tenant"] = get_object_or_404(
            StorageTenant, pk=self.kwargs["tenant_id"]
        )
        return context


class StorageResourcePoolDetailView(
    RequireIdempotencyKeyMixin, generics.RetrieveUpdateAPIView
):
    permission_classes = [IsObjectStorageSuperuser]
    serializer_class = StorageResourcePoolAdminSerializer
    queryset = StorageResourcePool.objects.all()
    lookup_url_kwarg = "pool_id"


class StorageResourcePoolValidationView(RequireIdempotencyKeyMixin, APIView):
    permission_classes = [IsObjectStorageSuperuser]

    def post(self, request, pool_id):
        pool = get_object_or_404(StorageResourcePool, pk=pool_id)
        try:
            capabilities = validate_resource_pool(pool)
            if not capabilities.can_manage_ram or not capabilities.can_manage_oss:
                raise ObjectStorageProviderError("PROVIDER_CAPABILITY_MISSING")
        except ObjectStorageProviderError as exc:
            pool.validation_status = StorageResourcePool.ValidationStatus.INVALID
            pool.validation_error_code = exc.error_code
            pool.enabled = False
            pool.save(
                update_fields=(
                    "validation_status",
                    "validation_error_code",
                    "enabled",
                    "updated_at",
                )
            )
            return Response(
                {"error_code": exc.error_code},
                status=status.HTTP_400_BAD_REQUEST,
            )
        pool.validation_status = StorageResourcePool.ValidationStatus.VALID
        pool.validation_error_code = ""
        pool.last_validated_at = timezone.now()
        pool.save(
            update_fields=(
                "validation_status",
                "validation_error_code",
                "last_validated_at",
                "updated_at",
            )
        )
        return Response(
            {
                "validation_status": pool.validation_status,
                "capabilities": capabilities.as_dict(),
            }
        )


class TenantFilteredAdminListView(generics.ListAPIView):
    permission_classes = [IsObjectStorageSuperuser]
    tenant_field = "tenant_id"

    def get_queryset(self):
        queryset = super().get_queryset()
        tenant_id = self.request.query_params.get("tenant_id")
        if tenant_id:
            try:
                tenant_id = int(tenant_id)
            except (TypeError, ValueError) as exc:
                raise ValidationError({"tenant_id": "INVALID_TENANT_ID"}) from exc
            queryset = queryset.filter(**{self.tenant_field: tenant_id})
        return queryset


class StorageMembershipAdminListView(TenantFilteredAdminListView):
    serializer_class = StorageMembershipAdminSerializer
    queryset = StorageMembership.objects.select_related("tenant", "user").all()


class StorageCloudIdentityAdminListView(TenantFilteredAdminListView):
    serializer_class = StorageCloudIdentityAdminSerializer
    queryset = StorageCloudIdentity.objects.select_related(
        "tenant", "membership", "resource_pool"
    ).all()


class StorageBucketAdminListView(TenantFilteredAdminListView):
    serializer_class = StorageBucketAdminSerializer
    queryset = StorageBucket.objects.select_related(
        "tenant", "owner", "resource_pool", "cloud_identity"
    ).all()


class StorageAccessKeyAdminListView(TenantFilteredAdminListView):
    serializer_class = StorageAccessKeyAdminSerializer
    queryset = StorageAccessKey.objects.select_related("tenant", "cloud_identity").all()


class StorageApplicationAdminListView(TenantFilteredAdminListView):
    serializer_class = StorageApplicationAdminSerializer
    queryset = StorageApplication.objects.select_related("tenant", "applicant").all()


class StorageApplicationAdminDetailView(generics.RetrieveAPIView):
    permission_classes = [IsObjectStorageSuperuser]
    serializer_class = StorageApplicationDetailAdminSerializer
    queryset = StorageApplication.objects.prefetch_related("attempts", "events")
    lookup_url_kwarg = "application_id"


def _admin_idempotency_key(request):
    key = str(request.headers.get("Idempotency-Key") or "").strip()
    if not key:
        raise ValidationError({"idempotency_key": "IDEMPOTENCY_KEY_REQUIRED"})
    return key


class StorageApplicationRetryView(APIView):
    permission_classes = [IsObjectStorageSuperuser]

    def post(self, request, application_id):
        serializer = StorageAdminReasonSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        idempotency_key = _admin_idempotency_key(request)
        should_enqueue = False
        with transaction.atomic():
            application = get_object_or_404(
                StorageApplication.objects.select_for_update(),
                pk=application_id,
            )
            existing = StorageAuditEvent.objects.filter(
                application=application,
                action="storage.application.retry_requested",
                request_id=idempotency_key,
            ).exists()
            if not existing:
                if application.status not in (
                    StorageApplication.Status.MANUAL_REQUIRED,
                    StorageApplication.Status.FAILED,
                ):
                    return Response(
                        {"error_code": "APPLICATION_NOT_RETRYABLE"},
                        status=status.HTTP_409_CONFLICT,
                    )
                application.status = StorageApplication.Status.PENDING
                application.error_code = ""
                application.error_summary = ""
                application.finished_at = None
                application.save(
                    update_fields=(
                        "status",
                        "error_code",
                        "error_summary",
                        "finished_at",
                        "updated_at",
                    )
                )
                record_audit_event(
                    tenant=application.tenant,
                    actor=request.user,
                    application=application,
                    action="storage.application.retry_requested",
                    target_type="StorageApplication",
                    target_id=application.pk,
                    result="accepted",
                    reason=serializer.validated_data["reason"],
                    request_id=idempotency_key,
                )
                should_enqueue = True
                from object_storage.tasks import run_storage_application

        try:
            if should_enqueue:
                run_storage_application.delay(application.pk)
        except Exception:
            with transaction.atomic():
                application = StorageApplication.objects.select_for_update().get(
                    pk=application.pk
                )
                application.status = StorageApplication.Status.MANUAL_REQUIRED
                application.error_code = "TASK_ENQUEUE_FAILED"
                application.error_summary = "任务入队失败，需要人工处理"
                application.finished_at = timezone.now()
                application.save(
                    update_fields=(
                        "status",
                        "error_code",
                        "error_summary",
                        "finished_at",
                        "updated_at",
                    )
                )
                record_audit_event(
                    tenant=application.tenant,
                    actor=request.user,
                    application=application,
                    action="storage.application.enqueue_failed",
                    target_type="StorageApplication",
                    target_id=application.pk,
                    result="manual_required",
                    reason=serializer.validated_data["reason"],
                    request_id=idempotency_key,
                )
            return Response(
                StorageApplicationAdminSerializer(application).data,
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return Response(
            StorageApplicationAdminSerializer(application).data,
            status=status.HTTP_202_ACCEPTED,
        )


class StorageApplicationResolveView(APIView):
    permission_classes = [IsObjectStorageSuperuser]

    def post(self, request, application_id):
        serializer = StorageAdminReasonSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        idempotency_key = _admin_idempotency_key(request)
        with transaction.atomic():
            application = get_object_or_404(
                StorageApplication.objects.select_for_update(),
                pk=application_id,
            )
            if not StorageAuditEvent.objects.filter(
                application=application,
                action="storage.application.cancelled",
                request_id=idempotency_key,
            ).exists():
                if application.status not in (
                    StorageApplication.Status.MANUAL_REQUIRED,
                    StorageApplication.Status.FAILED,
                ):
                    return Response(
                        {"error_code": "APPLICATION_NOT_RESOLVABLE"},
                        status=status.HTTP_409_CONFLICT,
                    )
                application.status = StorageApplication.Status.CANCELLED
                application.finished_at = timezone.now()
                application.save(update_fields=("status", "finished_at", "updated_at"))
                record_audit_event(
                    tenant=application.tenant,
                    actor=request.user,
                    application=application,
                    action="storage.application.cancelled",
                    target_type="StorageApplication",
                    target_id=application.pk,
                    result="cancelled",
                    reason=serializer.validated_data["reason"],
                    request_id=idempotency_key,
                )
        return Response(StorageApplicationAdminSerializer(application).data)


class StorageAuditEventAdminListView(TenantFilteredAdminListView):
    serializer_class = StorageAuditEventAdminSerializer
    queryset = StorageAuditEvent.objects.select_related(
        "tenant", "actor", "application"
    ).all()

    def get_queryset(self):
        queryset = super().get_queryset()
        now = timezone.now()
        minimum = now - timedelta(days=30)
        requested_start = self._parse_time("start")
        queryset = queryset.filter(
            created_at__gte=max(minimum, requested_start or minimum)
        )
        requested_end = self._parse_time("end")
        if requested_end:
            queryset = queryset.filter(created_at__lte=min(now, requested_end))
        for parameter, field_name in (
            ("actor_id", "actor_id"),
            ("application_id", "application_id"),
            ("action", "action"),
            ("target_type", "target_type"),
            ("target_id", "target_id"),
            ("result", "result"),
        ):
            value = self.request.query_params.get(parameter)
            if value:
                queryset = queryset.filter(**{field_name: value})
        return queryset

    def _parse_time(self, parameter):
        raw_value = str(self.request.query_params.get(parameter) or "")
        if not raw_value:
            return None
        parsed = parse_datetime(raw_value)
        if parsed is None:
            raise ValidationError({parameter: "INVALID_DATETIME"})
        if timezone.is_naive(parsed):
            parsed = timezone.make_aware(parsed)
        return parsed
