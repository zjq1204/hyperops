from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from object_storage.feishu import FeishuProviderError, get_feishu_client
from object_storage.models import PlatformFeishuConfig
from object_storage.permissions import (
    HasObjectStorageAdminAccess,
    RequireIdempotencyKeyMixin,
)
from object_storage.services.audit import record_audit_event
from object_storage.services.feishu_sync import (
    FeishuSyncConfirmationError,
    confirm_sync,
    create_sync_preview,
)
from object_storage.views_auth import LEGACY_SCOPE_KEYS


def _no_store(response):
    response["Cache-Control"] = "no-store"
    return response


def _config():
    return PlatformFeishuConfig.objects.filter(
        singleton_key="default",
        enabled=True,
        validation_status=PlatformFeishuConfig.ValidationStatus.VALID,
    ).first()


def _error(error_code, status_code):
    return _no_store(Response({"error_code": error_code}, status=status_code))


def _has_legacy_scope_params(request):
    return bool(
        LEGACY_SCOPE_KEYS.intersection(request.query_params)
        or LEGACY_SCOPE_KEYS.intersection(request.data)
    )


def _record_failure(request, error_code):
    record_audit_event(
        actor=request.user,
        action="feishu.identity.sync",
        target_type="PlatformFeishuConfig",
        target_id="default",
        result="failed",
        reason=error_code,
        safe_metadata={"error_code": error_code},
    )


class FeishuSyncMutationView(RequireIdempotencyKeyMixin, APIView):
    permission_classes = [HasObjectStorageAdminAccess]
    idempotency_sensitive = True

    def finalize_response(self, request, response, *args, **kwargs):
        return _no_store(super().finalize_response(request, response, *args, **kwargs))


class FeishuSyncPreviewView(FeishuSyncMutationView):

    def post(self, request):
        if _has_legacy_scope_params(request):
            return _error("TENANT_SCOPE_UNSUPPORTED", status.HTTP_400_BAD_REQUEST)
        config = _config()
        if config is None:
            return _error("FEISHU_SYNC_UNAVAILABLE", status.HTTP_404_NOT_FOUND)
        try:
            remote_identities = get_feishu_client().list_visible_users(
                app_config=config
            )
        except FeishuProviderError as exc:
            _record_failure(request, exc.error_code)
            return _error(exc.error_code, status.HTTP_502_BAD_GATEWAY)
        payload = create_sync_preview(
            config=config,
            actor_id=request.user.id,
            remote_identities=remote_identities,
        )
        return _no_store(Response(payload))


class FeishuSyncConfirmView(FeishuSyncMutationView):

    def post(self, request):
        if _has_legacy_scope_params(request):
            return _error("TENANT_SCOPE_UNSUPPORTED", status.HTTP_400_BAD_REQUEST)
        idempotency_key = str(request.data.get("idempotency_key") or "").strip()
        if not idempotency_key:
            return _error("IDEMPOTENCY_KEY_REQUIRED", status.HTTP_400_BAD_REQUEST)
        try:
            payload = confirm_sync(
                token=request.data.get("confirmation_token"),
                idempotency_key=idempotency_key,
                actor_id=request.user.id,
            )
        except FeishuSyncConfirmationError as exc:
            return _error(exc.error_code, status.HTTP_400_BAD_REQUEST)
        record_audit_event(
            actor=request.user,
            action="feishu.identity.sync",
            target_type="PlatformFeishuConfig",
            target_id="default",
            result="succeeded",
            safe_metadata={
                "success_count": payload["updated_count"],
                "count": (
                    payload["deactivated_count"] + payload["outside_scope_count"]
                ),
            },
        )
        return _no_store(Response(payload))
