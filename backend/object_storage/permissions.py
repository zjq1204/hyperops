import hashlib
import json
from types import SimpleNamespace

from django.db import IntegrityError, transaction
from rest_framework.exceptions import APIException, PermissionDenied, ValidationError
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.access import get_effective_feature_keys, get_effective_roles
from object_storage.models import (
    ApiIdempotencyRecord,
    CloudIdentity,
    PlatformFeishuConfig,
    StorageResourcePool,
)
from object_storage.views_auth import LEGACY_SCOPE_KEYS


class ObjectStorageNotConfigured(PermissionDenied):
    default_detail = "Object storage is not configured"
    default_code = "OBJECT_STORAGE_NOT_CONFIGURED"


class ObjectStorageSuspended(PermissionDenied):
    default_detail = "Object storage access is suspended"
    default_code = "OBJECT_STORAGE_SUSPENDED"


class TenantScopeUnsupported(APIException):
    status_code = 400
    default_detail = "Tenant-scoped object storage APIs are not supported"
    default_code = "TENANT_SCOPE_UNSUPPORTED"


class IdempotencyKeyReused(APIException):
    status_code = 409
    default_detail = "Idempotency key was already used with another payload"
    default_code = "IDEMPOTENCY_KEY_REUSED"


class IdempotencyInProgress(APIException):
    status_code = 409
    default_detail = "An operation with this idempotency key is in progress"
    default_code = "IDEMPOTENCY_IN_PROGRESS"


class IdempotencyResultNotReplayable(APIException):
    status_code = 409
    default_detail = "The completed sensitive result cannot be replayed"
    default_code = "IDEMPOTENCY_RESULT_NOT_REPLAYABLE"


def has_object_storage_admin_access(user):
    """Require an explicit object-storage feature, never Django staff status."""

    if not user or not user.is_authenticated:
        return False
    if "admin_object_storage" not in get_effective_feature_keys(user):
        return False
    if user.is_superuser:
        return True
    roles = get_effective_roles(user)
    if not roles:
        return False
    role_features = get_effective_feature_keys(
        SimpleNamespace(is_staff=False),
        effective_roles=roles,
    )
    return "admin_object_storage" in role_features


class HasObjectStorageAdminAccess(BasePermission):
    def has_permission(self, request, view):
        return has_object_storage_admin_access(request.user)


class HasPlatformObjectStorageAccess(BasePermission):
    """Gate employee APIs on a configured platform and user feature."""

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if "object_storage" not in get_effective_feature_keys(user):
            return False
        feishu_ready = PlatformFeishuConfig.objects.filter(
            singleton_key="default",
            enabled=True,
            validation_status=PlatformFeishuConfig.ValidationStatus.VALID,
        ).exists()
        pool = (
            StorageResourcePool.objects.filter(
                enabled=True,
                validation_status=StorageResourcePool.ValidationStatus.VALID,
            )
            .select_related("config")
            .order_by("id")
            .first()
        )
        if not feishu_ready or pool is None:
            raise ObjectStorageNotConfigured()
        identity = CloudIdentity.objects.filter(user=user).first()
        if identity is not None and identity.state == CloudIdentity.State.SUSPENDED:
            raise ObjectStorageSuspended()
        request.object_storage_pool = pool
        request.object_storage_config = pool.config
        request.object_storage_identity = identity
        return True


class RejectTenantScopeMixin:
    def initial(self, request, *args, **kwargs):
        if LEGACY_SCOPE_KEYS.intersection(
            request.query_params
        ) or LEGACY_SCOPE_KEYS.intersection(request.data):
            raise TenantScopeUnsupported()
        return super().initial(request, *args, **kwargs)


class RequireIdempotencyKeyMixin:
    """Require and atomically replay non-sensitive mutation responses."""

    idempotency_sensitive = False

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            key = str(request.headers.get("Idempotency-Key") or "").strip()
            if not key:
                raise ValidationError({"idempotency_key": "IDEMPOTENCY_KEY_REQUIRED"})
            if len(key) > 128:
                raise ValidationError({"idempotency_key": "IDEMPOTENCY_KEY_INVALID"})
            request.idempotency_key = key

    @staticmethod
    def _payload_digest(request):
        return hashlib.sha256(request._request.body or b"").hexdigest()

    def _idempotency_scope(self, request):
        return f"{request.method}:{request.path}"

    def _lookup_or_create_idempotency(self, request, payload_digest):
        scope = self._idempotency_scope(request)
        try:
            with transaction.atomic():
                record = (
                    ApiIdempotencyRecord.objects.select_for_update()
                    .filter(
                        actor=request.user,
                        scope=scope,
                        idempotency_key=request.idempotency_key,
                    )
                    .first()
                )
                if record is None:
                    record = ApiIdempotencyRecord.objects.create(
                        actor=request.user,
                        scope=scope,
                        idempotency_key=request.idempotency_key,
                        payload_digest=payload_digest,
                    )
                    record._new_idempotency_record = True
        except IntegrityError:
            record = ApiIdempotencyRecord.objects.get(
                actor=request.user,
                scope=scope,
                idempotency_key=request.idempotency_key,
            )
        if record.payload_digest != payload_digest:
            raise IdempotencyKeyReused()
        if not getattr(record, "_new_idempotency_record", False):
            if record.status == ApiIdempotencyRecord.Status.COMPLETED:
                return record
            raise IdempotencyInProgress()
        return record

    def _complete_idempotency(self, request, response):
        record = getattr(request, "_object_storage_idempotency_record", None)
        if record is None:
            return
        body = None
        if not self.idempotency_sensitive:
            body = json.loads(json.dumps(response.data, default=str))
        ApiIdempotencyRecord.objects.filter(pk=record.pk).update(
            status=ApiIdempotencyRecord.Status.COMPLETED,
            response_status=response.status_code,
            response_body=body,
        )

    def dispatch(self, request, *args, **kwargs):
        request = self.initialize_request(request, *args, **kwargs)
        self.request = request
        self.headers = self.default_response_headers
        try:
            payload_digest = None
            if request.method not in ("GET", "HEAD", "OPTIONS"):
                payload_digest = self._payload_digest(request)
            self.initial(request, *args, **kwargs)
            if request.method.lower() in self.http_method_names:
                handler = getattr(
                    self, request.method.lower(), self.http_method_not_allowed
                )
            else:
                handler = self.http_method_not_allowed
            if payload_digest is not None:
                record = self._lookup_or_create_idempotency(request, payload_digest)
                if record.status == ApiIdempotencyRecord.Status.COMPLETED:
                    if self.idempotency_sensitive:
                        raise IdempotencyResultNotReplayable()
                    response = Response(
                        record.response_body,
                        status=record.response_status,
                    )
                else:
                    request._object_storage_idempotency_record = record
                    response = handler(request, *args, **kwargs)
                    self._complete_idempotency(request, response)
            else:
                response = handler(request, *args, **kwargs)
        except Exception as exc:
            response = self.handle_exception(exc)
            self._complete_idempotency(request, response)
        self.response = self.finalize_response(request, response, *args, **kwargs)
        return self.response
