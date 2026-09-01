from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.serializers import UserDetailsSerializer
from object_storage.feishu import FeishuProviderError, get_feishu_client
from object_storage.models import PlatformFeishuConfig
from object_storage.services.identity import (
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


def _error(detail, error_code, status_code):
    return _no_store(
        Response(
            {"detail": detail, "error_code": error_code},
            status=status_code,
        )
    )


class FeishuLoginStartView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        if "tenant" in request.data or "tenant_code" in request.data:
            return _error(
                "Tenant selection is not supported",
                "FEISHU_TENANT_NOT_SUPPORTED",
                status.HTTP_400_BAD_REQUEST,
            )
        config = PlatformFeishuConfig.objects.filter(
            singleton_key="default",
            enabled=True,
            validation_status=PlatformFeishuConfig.ValidationStatus.VALID,
        ).first()
        if config is None:
            return _error(
                "Feishu login is unavailable",
                "FEISHU_LOGIN_UNAVAILABLE",
                status.HTTP_404_NOT_FOUND,
            )
        state = create_oauth_state(config.id)
        authorization_url = get_feishu_client().build_authorization_url(
            app_id=config.app_id,
            state=state,
            callback_url=config.oauth_callback_url,
        )
        return _no_store(Response({"authorization_url": authorization_url}))


class FeishuCallbackView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        state_payload = consume_oauth_state(request.query_params.get("state"))
        if not state_payload or not state_payload.get("nonce"):
            return _error(
                "Feishu login state is invalid or expired",
                "FEISHU_STATE_INVALID",
                status.HTTP_400_BAD_REQUEST,
            )
        config = PlatformFeishuConfig.objects.filter(
            pk=state_payload.get("config_id"),
            singleton_key="default",
            enabled=True,
            validation_status=PlatformFeishuConfig.ValidationStatus.VALID,
        ).first()
        if config is None:
            return _error(
                "Feishu login is unavailable",
                "FEISHU_LOGIN_UNAVAILABLE",
                status.HTTP_404_NOT_FOUND,
            )
        try:
            identity = get_feishu_client().authenticate(
                code=str(request.query_params.get("code") or ""),
                app_config=config,
            )
            feishu_identity = provision_feishu_identity(
                config_id=config.id,
                identity=identity,
            )
        except FeishuProviderError as exc:
            return _error(
                "Feishu login failed",
                exc.error_code,
                status.HTTP_502_BAD_GATEWAY,
            )
        except StorageIdentityError as exc:
            return _error(
                "Feishu identity is not eligible",
                exc.error_code,
                status.HTTP_403_FORBIDDEN,
            )
        return _no_store(
            Response({"handoff_code": create_handoff_code(feishu_identity.user_id)})
        )


class HandoffExchangeView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        payload = consume_handoff_code(request.data.get("handoff_code"))
        if payload is None:
            return _error(
                "Login handoff code is invalid or expired",
                "HANDOFF_CODE_INVALID",
                status.HTTP_400_BAD_REQUEST,
            )
        User = get_user_model()
        try:
            user = User.objects.get(pk=payload["user_id"], is_active=True)
        except User.DoesNotExist:
            return _error(
                "Login handoff code is invalid or expired",
                "HANDOFF_CODE_INVALID",
                status.HTTP_400_BAD_REQUEST,
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
