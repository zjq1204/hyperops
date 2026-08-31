from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.serializers import UserDetailsSerializer
from object_storage.feishu import FeishuProviderError, get_feishu_client
from object_storage.models import FeishuAppConfig, StorageTenant
from object_storage.services.tenant import (
    StorageIdentityError,
    consume_handoff_code,
    consume_oauth_state,
    create_handoff_code,
    create_oauth_state,
    provision_feishu_identity,
)


def _no_store(response):
    response["Cache-Control"] = "no-store"
    return response


class FeishuLoginStartView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        tenant_code = str(request.data.get("tenant_code") or "").strip()
        config = (
            FeishuAppConfig.objects.select_related("tenant")
            .filter(
                tenant__code=tenant_code,
                tenant__enabled=True,
                enabled=True,
                validation_status=FeishuAppConfig.ValidationStatus.VALID,
            )
            .first()
        )
        if config is None:
            return Response(
                {
                    "detail": "Feishu login is unavailable",
                    "error_code": "FEISHU_LOGIN_UNAVAILABLE",
                },
                status=status.HTTP_404_NOT_FOUND,
            )
        state_value = create_oauth_state(config.tenant_id)
        authorization_url = get_feishu_client().build_authorization_url(
            app_id=config.app_id,
            state=state_value,
            callback_url=config.oauth_callback_url,
        )
        return _no_store(Response({"authorization_url": authorization_url}))


class FeishuCallbackView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        state_payload = consume_oauth_state(request.query_params.get("state"))
        if state_payload is None:
            return Response(
                {
                    "detail": "Feishu login state is invalid or expired",
                    "error_code": "FEISHU_STATE_INVALID",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            tenant = StorageTenant.objects.get(
                pk=state_payload["tenant_id"], enabled=True
            )
            app_config = FeishuAppConfig.objects.get(
                tenant=tenant,
                enabled=True,
                validation_status=FeishuAppConfig.ValidationStatus.VALID,
            )
            identity = get_feishu_client().authenticate(
                code=str(request.query_params.get("code") or ""),
                app_config=app_config,
            )
            membership = provision_feishu_identity(
                tenant_id=tenant.id,
                identity=identity,
            )
        except (StorageTenant.DoesNotExist, FeishuAppConfig.DoesNotExist):
            return Response(
                {
                    "detail": "Feishu login is unavailable",
                    "error_code": "FEISHU_LOGIN_UNAVAILABLE",
                },
                status=status.HTTP_404_NOT_FOUND,
            )
        except FeishuProviderError as exc:
            return Response(
                {"detail": "Feishu login failed", "error_code": exc.error_code},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        except StorageIdentityError as exc:
            return Response(
                {
                    "detail": "Feishu identity is not eligible",
                    "error_code": exc.error_code,
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        return _no_store(
            Response({"handoff_code": create_handoff_code(membership.user_id)})
        )


class HandoffExchangeView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        payload = consume_handoff_code(request.data.get("handoff_code"))
        if payload is None:
            return Response(
                {
                    "detail": "Login handoff code is invalid or expired",
                    "error_code": "HANDOFF_CODE_INVALID",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        User = get_user_model()
        try:
            user = User.objects.get(pk=payload["user_id"], is_active=True)
        except User.DoesNotExist:
            return Response(
                {
                    "detail": "Login handoff code is invalid or expired",
                    "error_code": "HANDOFF_CODE_INVALID",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        refresh = RefreshToken.for_user(user)
        return _no_store(
            Response(
                {
                    "access": str(refresh.access_token),
                    "refresh": str(refresh),
                    "user": UserDetailsSerializer(user).data,
                }
            )
        )
