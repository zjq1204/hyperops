from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import transaction
from django.shortcuts import get_object_or_404
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
    PlatformFeishuConfig,
    PlatformObjectStorageConfig,
    StorageResourcePool,
    UserBucketQuota,
)
from object_storage.permissions import (
    HasObjectStorageAdminAccess,
    RejectTenantScopeMixin,
    RequireIdempotencyKeyMixin,
)
from object_storage.providers.aliyun import build_aliyun_provider
from object_storage.serializers_admin import (
    AccessGroupSummarySerializer,
    AccessKeyAdminSerializer,
    ApplicationBatchAdminSerializer,
    ApplicationBatchDetailAdminSerializer,
    AuditEventAdminSerializer,
    AuditEventQuerySerializer,
    BucketActionAcknowledgementSerializer,
    BucketAdminActionSerializer,
    BucketAdminSerializer,
    BucketConfigurationAcknowledgementSerializer,
    BucketConfigurationSerializer,
    BucketDetailAdminSerializer,
    CloudIdentityAdminSerializer,
    CloudIdentityDetailAdminSerializer,
    CredentialAcknowledgementSerializer,
    PlatformFeishuConfigAdminSerializer,
    PlatformObjectStorageConfigAdminSerializer,
    ReasonSerializer,
    StorageResourcePoolAdminSerializer,
    UserBucketQuotaAdminSerializer,
    get_quota_user,
)
from object_storage.services.applications import refresh_batch_status
from object_storage.services.audit import record_audit_event
from object_storage.services.credentials import (
    CredentialRotationError,
    acknowledge_credential_operation_uncertainty,
    disable_access_key,
    enable_access_key,
    reconcile_credential_operation_uncertainty,
    reveal_access_key,
    revoke_access_key,
    rotate_access_key_for_actor,
)
from object_storage.services.lifecycle import (
    BucketConfigurationError,
    LifecycleError,
    acknowledge_bucket_action_uncertainty,
    acknowledge_bucket_configuration_uncertainty,
    delete_bucket,
    reactivate_user_resources,
    reconcile_bucket_action_uncertainty,
    reconcile_bucket_configuration_uncertainty,
    recover_bucket,
    release_bucket,
    retry_bucket_configuration,
    retry_delete_bucket,
    suspend_user_resources,
    update_bucket_configuration,
)
from object_storage.services.platform import (
    PlatformConfigurationError,
    get_feishu_config,
    get_object_storage_config,
    validate_and_save_platform_config,
    validate_feishu_config,
    validate_resource_pool,
)


def _no_store(response):
    response["Cache-Control"] = "no-store"
    response["Pragma"] = "no-cache"
    return response


def _error(error_code, status_code=status.HTTP_400_BAD_REQUEST):
    return Response({"error_code": error_code}, status=status_code)


def _service_error(error, default="OBJECT_STORAGE_OPERATION_FAILED"):
    return str(getattr(error, "error_code", "") or default)


def _client_ip(request):
    forwarded = str(request.META.get("HTTP_X_FORWARDED_FOR") or "")
    return (
        forwarded.split(",", 1)[0].strip() if forwarded else None
    ) or request.META.get("REMOTE_ADDR")


def _mutation_seen(request, action, target_type, target_id):
    return AuditEvent.objects.filter(
        actor=request.user,
        action=action,
        target_type=target_type,
        target_id=str(target_id),
        request_id=request.idempotency_key,
    ).exists()


def _record_mutation(request, action, target_type, target_id, **metadata):
    return record_audit_event(
        actor=request.user,
        action=action,
        target_type=target_type,
        target_id=target_id,
        result="accepted",
        request_id=request.idempotency_key,
        safe_metadata=metadata,
    )


def _provider_for_key(access_key):
    return build_aliyun_provider(access_key.cloud_identity.resource_pool)


def disable_access_key_action(*, access_key, actor, reason=""):
    return disable_access_key(
        access_key=access_key,
        actor=actor,
        provider=_provider_for_key(access_key),
        reason=reason,
    )


def enable_access_key_action(*, access_key, actor, reason=""):
    return enable_access_key(
        access_key=access_key,
        actor=actor,
        provider=_provider_for_key(access_key),
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
        provider=_provider_for_key(access_key),
        selected_access_key_id=access_key.pk if active_key_count >= 2 else None,
        reason=reason,
    )


def revoke_access_key_action(*, access_key, actor, reason=""):
    return revoke_access_key(
        access_key=access_key,
        actor=actor,
        provider=_provider_for_key(access_key),
        reason=reason,
    )


class AdminAPIView(RejectTenantScopeMixin, APIView):
    permission_classes = [HasObjectStorageAdminAccess]


class AdminMutationAPIView(RejectTenantScopeMixin, RequireIdempotencyKeyMixin, APIView):
    permission_classes = [HasObjectStorageAdminAccess]


class NoStoreAdminMutationAPIView(AdminMutationAPIView):
    idempotency_sensitive = True

    def finalize_response(self, request, response, *args, **kwargs):
        return _no_store(super().finalize_response(request, response, *args, **kwargs))


class AccessGroupListView(RejectTenantScopeMixin, generics.ListAPIView):
    permission_classes = [HasObjectStorageAdminAccess]
    serializer_class = AccessGroupSummarySerializer
    queryset = Group.objects.order_by("name", "id")
    pagination_class = None


class PlatformSettingsView(AdminMutationAPIView):
    def get(self, request):
        return Response(
            PlatformObjectStorageConfigAdminSerializer(get_object_storage_config()).data
        )

    def patch(self, request):
        config = get_object_storage_config()
        action = "storage.api.platform_settings.update"
        if _mutation_seen(request, action, "PlatformObjectStorageConfig", config.pk):
            return Response(PlatformObjectStorageConfigAdminSerializer(config).data)
        serializer = PlatformObjectStorageConfigAdminSerializer(
            config,
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        try:
            validate_and_save_platform_config(
                object_storage_config=config,
                object_storage_fields=serializer.validated_data,
            )
        except PlatformConfigurationError as error:
            return _error(_service_error(error), status.HTTP_400_BAD_REQUEST)
        config.refresh_from_db()
        _record_mutation(request, action, "PlatformObjectStorageConfig", config.pk)
        return Response(PlatformObjectStorageConfigAdminSerializer(config).data)

    put = patch


class PlatformFeishuSettingsView(AdminMutationAPIView):
    def get(self, request):
        return Response(PlatformFeishuConfigAdminSerializer(get_feishu_config()).data)

    def patch(self, request):
        config = get_feishu_config()
        action = "storage.api.feishu_settings.update"
        if _mutation_seen(request, action, "PlatformFeishuConfig", config.pk):
            return Response(PlatformFeishuConfigAdminSerializer(config).data)
        serializer = PlatformFeishuConfigAdminSerializer(
            config,
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        _record_mutation(request, action, "PlatformFeishuConfig", config.pk)
        return Response(serializer.data)


class PlatformFeishuValidationView(AdminMutationAPIView):
    def post(self, request):
        config = get_feishu_config()
        action = "storage.api.feishu.validate"
        if _mutation_seen(request, action, "PlatformFeishuConfig", config.pk):
            return Response({"validation_status": config.validation_status})
        try:
            result = validate_feishu_config(config)
        except PlatformConfigurationError as error:
            return _error(_service_error(error), status.HTTP_400_BAD_REQUEST)
        _record_mutation(request, action, "PlatformFeishuConfig", config.pk)
        return Response(
            {
                "validation_status": PlatformFeishuConfig.ValidationStatus.VALID,
                "capabilities": result,
            }
        )


class StorageResourcePoolListCreateView(
    RejectTenantScopeMixin, RequireIdempotencyKeyMixin, generics.ListCreateAPIView
):
    permission_classes = [HasObjectStorageAdminAccess]
    serializer_class = StorageResourcePoolAdminSerializer
    queryset = StorageResourcePool.objects.all()
    pagination_class = None

    def create(self, request, *args, **kwargs):
        action = "storage.api.resource_pool.create"
        existing = AuditEvent.objects.filter(
            actor=request.user,
            action=action,
            target_type="StorageResourcePool",
            request_id=request.idempotency_key,
        ).first()
        if existing:
            pool = StorageResourcePool.objects.filter(pk=existing.target_id).first()
            if pool:
                return Response(StorageResourcePoolAdminSerializer(pool).data)
        response = super().create(request, *args, **kwargs)
        if response.status_code == status.HTTP_201_CREATED:
            _record_mutation(
                request,
                action,
                "StorageResourcePool",
                response.data["id"],
            )
        return response


class StorageResourcePoolDetailView(
    RejectTenantScopeMixin, RequireIdempotencyKeyMixin, generics.RetrieveUpdateAPIView
):
    permission_classes = [HasObjectStorageAdminAccess]
    serializer_class = StorageResourcePoolAdminSerializer
    queryset = StorageResourcePool.objects.all()
    lookup_url_kwarg = "pool_id"

    def update(self, request, *args, **kwargs):
        pool = self.get_object()
        action = "storage.api.resource_pool.update"
        if _mutation_seen(request, action, "StorageResourcePool", pool.pk):
            return Response(StorageResourcePoolAdminSerializer(pool).data)
        try:
            response = super().update(request, *args, **kwargs)
        except PlatformConfigurationError as error:
            status_code = (
                status.HTTP_409_CONFLICT
                if _service_error(error) == "RESOURCE_POOL_ID_LOCKED"
                else status.HTTP_400_BAD_REQUEST
            )
            return _error(_service_error(error), status_code)
        if response.status_code == status.HTTP_200_OK:
            _record_mutation(request, action, "StorageResourcePool", pool.pk)
        return response


class StorageResourcePoolValidationView(AdminMutationAPIView):
    def post(self, request, pool_id):
        pool = get_object_or_404(StorageResourcePool, pk=pool_id)
        action = "storage.api.resource_pool.validate"
        if _mutation_seen(request, action, "StorageResourcePool", pool.pk):
            return Response({"validation_status": pool.validation_status})
        try:
            result = validate_resource_pool(pool)
        except PlatformConfigurationError as error:
            return _error(_service_error(error), status.HTTP_400_BAD_REQUEST)
        pool.refresh_from_db()
        _record_mutation(request, action, "StorageResourcePool", pool.pk)
        return Response(
            {
                "validation_status": pool.validation_status,
                "account_id": result.account_id,
                "request_ids": result.request_ids,
            }
        )


class UserQuotaListView(RejectTenantScopeMixin, generics.ListAPIView):
    permission_classes = [HasObjectStorageAdminAccess]
    serializer_class = UserBucketQuotaAdminSerializer
    queryset = UserBucketQuota.objects.select_related("user").all()
    pagination_class = None


class UserQuotaDetailView(AdminMutationAPIView):
    def get(self, request, user_id):
        quota = get_object_or_404(
            UserBucketQuota.objects.select_related("user"), user_id=user_id
        )
        return Response(UserBucketQuotaAdminSerializer(quota).data)

    def put(self, request, user_id):
        user = get_object_or_404(get_user_model(), pk=user_id)
        quota = UserBucketQuota.objects.filter(user=user).first()
        quota = quota or UserBucketQuota(user=user)
        serializer = UserBucketQuotaAdminSerializer(
            quota,
            data=request.data,
            partial=False,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def patch(self, request, user_id):
        quota = get_object_or_404(UserBucketQuota, user=get_quota_user(user_id))
        serializer = UserBucketQuotaAdminSerializer(
            quota,
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request, user_id):
        action = "storage.api.user_quota.delete"
        if _mutation_seen(request, action, "UserBucketQuota", user_id):
            return Response(status=status.HTTP_204_NO_CONTENT)
        quota = get_object_or_404(UserBucketQuota, user_id=user_id)
        _record_mutation(request, action, "UserBucketQuota", user_id, user_id=user_id)
        quota.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class CloudIdentityAdminListView(RejectTenantScopeMixin, generics.ListAPIView):
    permission_classes = [HasObjectStorageAdminAccess]
    serializer_class = CloudIdentityAdminSerializer
    queryset = CloudIdentity.objects.select_related("user", "resource_pool").all()


class CloudIdentityAdminDetailView(RejectTenantScopeMixin, generics.RetrieveAPIView):
    permission_classes = [HasObjectStorageAdminAccess]
    serializer_class = CloudIdentityDetailAdminSerializer
    queryset = CloudIdentity.objects.select_related("user", "resource_pool").all()
    lookup_url_kwarg = "identity_id"


class BucketAdminListView(RejectTenantScopeMixin, generics.ListAPIView):
    permission_classes = [HasObjectStorageAdminAccess]
    serializer_class = BucketAdminSerializer
    queryset = Bucket.objects.select_related(
        "owner", "cloud_identity", "resource_pool"
    ).all()


class BucketAdminDetailView(RejectTenantScopeMixin, generics.RetrieveAPIView):
    permission_classes = [HasObjectStorageAdminAccess]
    serializer_class = BucketDetailAdminSerializer
    queryset = Bucket.objects.select_related(
        "owner", "cloud_identity", "resource_pool"
    ).all()
    lookup_url_kwarg = "bucket_id"


class AccessKeyAdminListView(RejectTenantScopeMixin, generics.ListAPIView):
    permission_classes = [HasObjectStorageAdminAccess]
    serializer_class = AccessKeyAdminSerializer
    queryset = AccessKey.objects.select_related("cloud_identity__user").all()


class AccessKeyAdminDetailView(RejectTenantScopeMixin, generics.RetrieveAPIView):
    permission_classes = [HasObjectStorageAdminAccess]
    serializer_class = AccessKeyAdminSerializer
    queryset = AccessKey.objects.select_related("cloud_identity__user").all()
    lookup_url_kwarg = "key_id"


class ApplicationBatchAdminListView(RejectTenantScopeMixin, generics.ListAPIView):
    permission_classes = [HasObjectStorageAdminAccess]
    serializer_class = ApplicationBatchAdminSerializer
    queryset = ApplicationBatch.objects.select_related("applicant").all()


class ApplicationBatchAdminDetailView(RejectTenantScopeMixin, generics.RetrieveAPIView):
    permission_classes = [HasObjectStorageAdminAccess]
    serializer_class = ApplicationBatchDetailAdminSerializer
    queryset = ApplicationBatch.objects.select_related("applicant").prefetch_related(
        "items__attempts", "items__events"
    )
    lookup_url_kwarg = "application_id"


class AuditEventAdminListView(RejectTenantScopeMixin, generics.ListAPIView):
    permission_classes = [HasObjectStorageAdminAccess]
    serializer_class = AuditEventAdminSerializer

    def get_queryset(self):
        serializer = AuditEventQuerySerializer(data=self.request.query_params)
        serializer.is_valid(raise_exception=True)
        filters = serializer.validated_data
        queryset = AuditEvent.objects.all()
        if filters.get("action"):
            queryset = queryset.filter(action=filters["action"])
        if filters.get("target_type"):
            queryset = queryset.filter(target_type=filters["target_type"])
        if filters.get("actor_id"):
            queryset = queryset.filter(actor_id_snapshot=filters["actor_id"])
        if filters.get("since"):
            queryset = queryset.filter(created_at__gte=filters["since"])
        if filters.get("result"):
            queryset = queryset.filter(result=filters["result"])
        return queryset


class AuditEventAdminDetailView(RejectTenantScopeMixin, generics.RetrieveAPIView):
    permission_classes = [HasObjectStorageAdminAccess]
    serializer_class = AuditEventAdminSerializer
    queryset = AuditEvent.objects.all()
    lookup_url_kwarg = "event_id"


class AccessKeyActionView(AdminMutationAPIView):
    action = ""

    def post(self, request, key_id):
        serializer = ReasonSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        access_key = get_object_or_404(
            AccessKey.objects.select_related("cloud_identity__resource_pool"), pk=key_id
        )
        audit_action = f"storage.api.admin.credential.{self.action}"
        if _mutation_seen(request, audit_action, "AccessKey", access_key.pk):
            return Response(AccessKeyAdminSerializer(access_key).data)
        operation = globals()[f"{self.action}_access_key_action"]
        try:
            result = operation(
                access_key=access_key,
                actor=request.user,
                reason=serializer.validated_data["reason"],
            )
        except (CredentialRotationError, PlatformConfigurationError) as error:
            return _error(_service_error(error), status.HTTP_409_CONFLICT)
        except Exception:
            return _error(
                "PROVIDER_OPERATION_FAILED", status.HTTP_503_SERVICE_UNAVAILABLE
            )
        _record_mutation(request, audit_action, "AccessKey", access_key.pk)
        return Response(AccessKeyAdminSerializer(result).data)


class AccessKeyDisableView(AccessKeyActionView):
    action = "disable"


class AccessKeyEnableView(AccessKeyActionView):
    action = "enable"


class AccessKeyRotateView(AccessKeyActionView):
    action = "rotate"


class AccessKeyRevokeView(AccessKeyActionView):
    action = "revoke"


class AccessKeyRevealView(NoStoreAdminMutationAPIView):
    def post(self, request, key_id):
        serializer = ReasonSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        access_key = get_object_or_404(AccessKey, pk=key_id)
        if AuditEvent.objects.filter(
            actor=request.user,
            action="storage.credential.revealed",
            target_type="AccessKey",
            target_id=str(access_key.pk),
            request_id=request.idempotency_key,
        ).exists():
            return _error("REVEAL_ALREADY_COMPLETED", status.HTTP_409_CONFLICT)
        secret = reveal_access_key(
            access_key=access_key,
            actor=request.user,
            reason=serializer.validated_data["reason"],
            request_id=request.idempotency_key,
            ip_address=_client_ip(request),
        )
        return Response(secret)


class BucketLifecycleActionView(AdminMutationAPIView):
    action = ""

    def post(self, request, bucket_id):
        serializer = BucketAdminActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        bucket = get_object_or_404(
            Bucket.objects.select_related("cloud_identity", "resource_pool"),
            pk=bucket_id,
        )
        audit_action = f"storage.api.admin.bucket.{self.action}"
        if _mutation_seen(request, audit_action, "Bucket", bucket.pk):
            return Response(BucketAdminSerializer(bucket).data)
        common = {
            "bucket": bucket,
            "actor": request.user,
            "bucket_name": serializer.validated_data["bucket_name"],
            "confirmed": serializer.validated_data["confirmed"],
            "reason": serializer.validated_data["reason"],
        }
        operation = globals()[self.action.replace("-", "_") + "_bucket"]
        if self.action == "delete":
            common["immediate"] = True
        try:
            result = operation(**common)
        except LifecycleError as error:
            return _error(_service_error(error), status.HTTP_409_CONFLICT)
        except Exception:
            return _error(
                "PROVIDER_OPERATION_FAILED", status.HTTP_503_SERVICE_UNAVAILABLE
            )
        _record_mutation(
            request,
            audit_action,
            "Bucket",
            bucket.pk,
            bucket_id=bucket.pk,
        )
        return Response(
            BucketAdminSerializer(result).data,
            status=(
                status.HTTP_202_ACCEPTED
                if self.action == "release"
                else status.HTTP_200_OK
            ),
        )


class BucketReleaseView(BucketLifecycleActionView):
    action = "release"


class BucketRecoverView(BucketLifecycleActionView):
    action = "recover"


class BucketDeleteView(BucketLifecycleActionView):
    action = "delete"


class BucketRetryDeleteView(BucketLifecycleActionView):
    action = "retry-delete"


class BucketConfigurationView(AdminMutationAPIView):
    def patch(self, request, bucket_id):
        serializer = BucketConfigurationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        bucket = get_object_or_404(Bucket, pk=bucket_id)
        action = "storage.api.admin.bucket.configuration_update"
        if _mutation_seen(request, action, "Bucket", bucket.pk):
            return Response(BucketAdminSerializer(bucket).data)
        try:
            result = update_bucket_configuration(
                bucket=bucket,
                actor=request.user,
                desired=serializer.validated_data["desired"],
                reason=serializer.validated_data["reason"],
                bucket_name=serializer.validated_data["bucket_name"],
                confirmed=serializer.validated_data["confirmed"],
            )
        except BucketConfigurationError as error:
            return _error(_service_error(error), status.HTTP_409_CONFLICT)
        _record_mutation(request, action, "Bucket", bucket.pk, bucket_id=bucket.pk)
        return Response(
            BucketAdminSerializer(result).data, status=status.HTTP_202_ACCEPTED
        )


class BucketConfigurationRetryView(AdminMutationAPIView):
    def post(self, request, bucket_id):
        serializer = BucketAdminActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        bucket = get_object_or_404(Bucket, pk=bucket_id)
        action = "storage.api.admin.bucket.configuration_retry"
        if _mutation_seen(request, action, "Bucket", bucket.pk):
            return Response(BucketAdminSerializer(bucket).data)
        try:
            result = retry_bucket_configuration(
                bucket=bucket,
                actor=request.user,
                reason=serializer.validated_data["reason"],
                bucket_name=serializer.validated_data["bucket_name"],
                confirmed=serializer.validated_data["confirmed"],
            )
        except BucketConfigurationError as error:
            return _error(_service_error(error), status.HTTP_409_CONFLICT)
        _record_mutation(request, action, "Bucket", bucket.pk, bucket_id=bucket.pk)
        return Response(
            BucketAdminSerializer(result).data, status=status.HTTP_202_ACCEPTED
        )


class BucketActionUncertaintyObserveView(AdminMutationAPIView):
    idempotency_sensitive = True

    def post(self, request, bucket_id):
        serializer = ReasonSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        bucket = get_object_or_404(Bucket, pk=bucket_id)
        action = "storage.api.admin.bucket.uncertainty_observe"
        if _mutation_seen(request, action, "Bucket", bucket.pk):
            return Response(BucketDetailAdminSerializer(bucket).data)
        try:
            result = reconcile_bucket_action_uncertainty(
                bucket=bucket,
                actor=request.user,
                reason=serializer.validated_data["reason"],
            )
        except LifecycleError as error:
            return _error(_service_error(error), status.HTTP_409_CONFLICT)
        _record_mutation(request, action, "Bucket", bucket.pk, bucket_id=bucket.pk)
        return Response(BucketDetailAdminSerializer(result).data)


class BucketActionUncertaintyAcknowledgeView(AdminMutationAPIView):
    idempotency_sensitive = True

    def post(self, request, bucket_id):
        serializer = BucketActionAcknowledgementSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        bucket = get_object_or_404(Bucket, pk=bucket_id)
        action = "storage.api.admin.bucket.uncertainty_acknowledge"
        if _mutation_seen(request, action, "Bucket", bucket.pk):
            return Response(BucketDetailAdminSerializer(bucket).data)
        try:
            result = acknowledge_bucket_action_uncertainty(
                bucket=bucket,
                actor=request.user,
                **serializer.validated_data,
            )
        except LifecycleError as error:
            return _error(_service_error(error), status.HTTP_409_CONFLICT)
        _record_mutation(request, action, "Bucket", bucket.pk, bucket_id=bucket.pk)
        return Response(BucketDetailAdminSerializer(result).data)


class BucketConfigurationUncertaintyObserveView(AdminMutationAPIView):
    idempotency_sensitive = True

    def post(self, request, bucket_id):
        serializer = ReasonSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        bucket = get_object_or_404(Bucket, pk=bucket_id)
        action = "storage.api.admin.bucket.configuration_uncertainty_observe"
        if _mutation_seen(request, action, "Bucket", bucket.pk):
            return Response(BucketDetailAdminSerializer(bucket).data)
        try:
            result = reconcile_bucket_configuration_uncertainty(
                bucket=bucket,
                actor=request.user,
                reason=serializer.validated_data["reason"],
            )
        except BucketConfigurationError as error:
            return _error(_service_error(error), status.HTTP_409_CONFLICT)
        _record_mutation(request, action, "Bucket", bucket.pk, bucket_id=bucket.pk)
        return Response(BucketDetailAdminSerializer(result).data)


class BucketConfigurationUncertaintyAcknowledgeView(AdminMutationAPIView):
    idempotency_sensitive = True

    def post(self, request, bucket_id):
        serializer = BucketConfigurationAcknowledgementSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        bucket = get_object_or_404(Bucket, pk=bucket_id)
        action = "storage.api.admin.bucket.configuration_uncertainty_acknowledge"
        if _mutation_seen(request, action, "Bucket", bucket.pk):
            return Response(BucketDetailAdminSerializer(bucket).data)
        try:
            result = acknowledge_bucket_configuration_uncertainty(
                bucket=bucket,
                actor=request.user,
                **serializer.validated_data,
            )
        except BucketConfigurationError as error:
            return _error(_service_error(error), status.HTTP_409_CONFLICT)
        _record_mutation(request, action, "Bucket", bucket.pk, bucket_id=bucket.pk)
        return Response(BucketDetailAdminSerializer(result).data)


class UserResourceStateView(AdminMutationAPIView):
    action = ""

    def post(self, request, user_id):
        serializer = ReasonSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = get_object_or_404(get_user_model(), pk=user_id)
        audit_action = f"storage.api.admin.user.{self.action}"
        existing_identity = CloudIdentity.objects.filter(user=user).first()
        if existing_identity and _mutation_seen(
            request, audit_action, "CloudIdentity", existing_identity.pk
        ):
            return Response(CloudIdentityAdminSerializer(existing_identity).data)
        operation = (
            suspend_user_resources
            if self.action == "suspend"
            else reactivate_user_resources
        )
        try:
            identity = operation(
                user=user,
                actor=request.user,
                reason=serializer.validated_data["reason"],
            )
        except (LifecycleError, CloudIdentity.DoesNotExist) as error:
            return _error(
                _service_error(error, "CLOUD_IDENTITY_NOT_FOUND"),
                status.HTTP_409_CONFLICT,
            )
        _record_mutation(
            request,
            audit_action,
            "CloudIdentity",
            identity.pk,
            user_id=user.pk,
        )
        return Response(
            CloudIdentityAdminSerializer(identity).data,
            status=(
                status.HTTP_202_ACCEPTED
                if self.action == "suspend"
                else status.HTTP_200_OK
            ),
        )


class UserResourceSuspendView(UserResourceStateView):
    action = "suspend"


class UserResourceReactivateView(UserResourceStateView):
    action = "reactivate"


class ApplicationBatchRetryView(AdminMutationAPIView):
    def post(self, request, application_id):
        serializer = ReasonSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        audit_action = "storage.api.admin.application_batch.retry"
        existing_batch = get_object_or_404(ApplicationBatch, pk=application_id)
        if _mutation_seen(request, audit_action, "ApplicationBatch", existing_batch.pk):
            return Response(ApplicationBatchAdminSerializer(existing_batch).data)
        with transaction.atomic():
            batch = get_object_or_404(
                ApplicationBatch.objects.select_for_update(), pk=application_id
            )
            if batch.running_task_id or batch.owner_token:
                return _error("APPLICATION_IN_PROGRESS", status.HTTP_409_CONFLICT)
            items = list(
                batch.items.select_for_update().filter(
                    status__in=(
                        ApplicationItem.Status.FAILED,
                        ApplicationItem.Status.WAITING_RETRY,
                    )
                )
            )
            if not items:
                return _error("APPLICATION_NOT_RETRYABLE", status.HTTP_409_CONFLICT)
            for item in items:
                item.status = ApplicationItem.Status.WAITING_RETRY
                item.error_code = ""
                item.error_summary = ""
                item.retry_count += 1
                item.save()
            batch.started_at = None
            batch.finished_at = None
            batch.save(update_fields=("started_at", "finished_at", "updated_at"))
            refresh_batch_status(batch)
            record_audit_event(
                actor=request.user,
                action="storage.application_batch.retry_requested",
                target_type="ApplicationBatch",
                target_id=batch.pk,
                result="accepted",
                reason=serializer.validated_data["reason"],
                request_id=request.idempotency_key,
                safe_metadata={"application_id": batch.pk, "count": len(items)},
            )
            _record_mutation(
                request,
                audit_action,
                "ApplicationBatch",
                batch.pk,
                application_id=batch.pk,
            )
        from object_storage.tasks import run_storage_application_batch

        try:
            run_storage_application_batch.delay(batch.pk)
        except Exception:
            return _error("TASK_ENQUEUE_FAILED", status.HTTP_503_SERVICE_UNAVAILABLE)
        return Response(
            ApplicationBatchAdminSerializer(batch).data,
            status=status.HTTP_202_ACCEPTED,
        )


class CredentialUncertaintyObserveView(AdminMutationAPIView):
    idempotency_sensitive = True

    def post(self, request, identity_id):
        serializer = ReasonSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        identity = get_object_or_404(
            CloudIdentity.objects.select_related("resource_pool"), pk=identity_id
        )
        action = "storage.api.admin.credential.uncertainty_observe"
        if _mutation_seen(request, action, "CloudIdentity", identity.pk):
            return Response(CloudIdentityDetailAdminSerializer(identity).data)
        try:
            result = reconcile_credential_operation_uncertainty(
                identity=identity,
                actor=request.user,
                provider=build_aliyun_provider(identity.resource_pool),
                reason=serializer.validated_data["reason"],
            )
        except CredentialRotationError as error:
            return _error(_service_error(error), status.HTTP_409_CONFLICT)
        _record_mutation(
            request,
            action,
            "CloudIdentity",
            identity.pk,
            user_id=identity.user_id,
        )
        return Response(CloudIdentityDetailAdminSerializer(result).data)


class CredentialUncertaintyAcknowledgeView(AdminMutationAPIView):
    idempotency_sensitive = True

    def post(self, request, identity_id):
        serializer = CredentialAcknowledgementSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        identity = get_object_or_404(CloudIdentity, pk=identity_id)
        action = "storage.api.admin.credential.uncertainty_acknowledge"
        if _mutation_seen(request, action, "CloudIdentity", identity.pk):
            return Response(CloudIdentityDetailAdminSerializer(identity).data)
        try:
            result = acknowledge_credential_operation_uncertainty(
                identity=identity,
                actor=request.user,
                **serializer.validated_data,
            )
        except CredentialRotationError as error:
            return _error(_service_error(error), status.HTTP_409_CONFLICT)
        _record_mutation(
            request,
            action,
            "CloudIdentity",
            identity.pk,
            user_id=identity.user_id,
        )
        return Response(CloudIdentityDetailAdminSerializer(result).data)
