from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from object_storage.feishu import get_feishu_client
from object_storage.models import (
    FeishuAppConfig,
    StorageResourcePool,
    StorageTenant,
)
from object_storage.permissions import IsObjectStorageSuperuser
from object_storage.providers.aliyun import build_aliyun_provider
from object_storage.serializers_admin import (
    FeishuAppConfigAdminSerializer,
    StorageResourcePoolAdminSerializer,
    StorageTenantAdminSerializer,
)
from object_storage.services.provider_errors import ObjectStorageProviderError


def validate_feishu_config(config):
    return get_feishu_client().validate_config(config)


def validate_resource_pool(pool):
    return build_aliyun_provider(pool).validate_management_identity(pool)


class StorageTenantListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsObjectStorageSuperuser]
    serializer_class = StorageTenantAdminSerializer
    queryset = StorageTenant.objects.all()


class StorageTenantDetailView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsObjectStorageSuperuser]
    serializer_class = StorageTenantAdminSerializer
    queryset = StorageTenant.objects.all()
    lookup_url_kwarg = "tenant_id"


class FeishuAppConfigView(APIView):
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


class FeishuAppValidationView(APIView):
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


class StorageResourcePoolListCreateView(generics.ListCreateAPIView):
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


class StorageResourcePoolDetailView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsObjectStorageSuperuser]
    serializer_class = StorageResourcePoolAdminSerializer
    queryset = StorageResourcePool.objects.all()
    lookup_url_kwarg = "pool_id"


class StorageResourcePoolValidationView(APIView):
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
