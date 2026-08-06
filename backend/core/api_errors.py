"""Public API error responses and DRF exception normalization."""

from __future__ import annotations

import logging
import re
from uuid import uuid4

from rest_framework import status
from rest_framework.exceptions import (
    AuthenticationFailed,
    NotAuthenticated,
    NotFound,
    PermissionDenied,
    Throttled,
    ValidationError,
)
from rest_framework.response import Response


logger = logging.getLogger(__name__)
REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{8,128}$")
TECHNICAL_ERROR_PATTERN = re.compile(
    r"https?://|client error|server error|traceback|requests\.|urllib3|"
    r"connectionpool|for url|exception|errno|connection refused|"
    r"unauthorized|forbidden|c_class",
    re.IGNORECASE,
)


def get_request_id(request) -> str:
    """Return a stable request id without trusting arbitrary header content."""
    current = getattr(request, "request_id", "") if request is not None else ""
    if current:
        return current

    incoming = ""
    if request is not None:
        incoming = request.META.get("HTTP_X_REQUEST_ID", "")
    request_id = incoming if REQUEST_ID_PATTERN.fullmatch(incoming) else uuid4().hex
    if request is not None:
        request.request_id = request_id
    return request_id


def build_error_payload(
    request,
    *,
    error_code: str,
    detail: str,
    field_errors: dict | None = None,
    extra: dict | None = None,
) -> dict:
    payload = {
        "error_code": error_code,
        "detail": detail,
        "request_id": get_request_id(request),
    }
    if field_errors:
        payload["field_errors"] = field_errors
    if extra:
        payload.update(extra)
    return payload


def api_error_response(
    request,
    *,
    error_code: str,
    detail: str,
    status_code: int,
    field_errors: dict | None = None,
    extra: dict | None = None,
) -> Response:
    return Response(
        build_error_payload(
            request,
            error_code=error_code,
            detail=detail,
            field_errors=field_errors,
            extra=extra,
        ),
        status=status_code,
    )


def infer_public_error_code(message: str, status_code: int) -> str:
    text = str(message or "")
    if re.search(r"\b401\b|unauthorized", text, re.IGNORECASE):
        return "EXTERNAL_AUTH_FAILED"
    if re.search(r"\b403\b|forbidden", text, re.IGNORECASE):
        return "EXTERNAL_PERMISSION_DENIED"
    if re.search(r"timeout|timed out", text, re.IGNORECASE):
        return "UPSTREAM_TIMEOUT"
    if status_code >= status.HTTP_500_INTERNAL_SERVER_ERROR:
        return "INTERNAL_ERROR"
    return "REQUEST_FAILED"


def sanitize_public_message(
    message,
    *,
    status_code: int,
    default: str = "请求处理失败，请稍后重试",
) -> str:
    text = str(message or "").strip()
    if not text or text.lower() in {"failed", "failure", "error"}:
        return default
    if not TECHNICAL_ERROR_PATTERN.search(text):
        return text

    error_code = infer_public_error_code(text, status_code)
    safe_messages = {
        "EXTERNAL_AUTH_FAILED": "外部服务认证失败，请检查连接凭据",
        "EXTERNAL_PERMISSION_DENIED": "外部服务拒绝访问，请检查账号权限",
        "UPSTREAM_TIMEOUT": "外部服务响应超时，请稍后重试",
        "INTERNAL_ERROR": "服务暂时出现异常，请稍后重试",
        "REQUEST_FAILED": default,
    }
    return safe_messages[error_code]


def sanitize_response_data(value, *, status_code: int):
    """Recursively remove technical exception details from API payloads."""
    if isinstance(value, list):
        return [sanitize_response_data(item, status_code=status_code) for item in value]
    if not isinstance(value, dict):
        return value

    sanitized = {}
    message_keys = {"message", "detail", "error", "warning", "error_detail"}
    for key, item in value.items():
        if key in message_keys and isinstance(item, str) and item.strip():
            sanitized[key] = sanitize_public_message(
                item,
                status_code=status_code,
                default="请求处理失败，请稍后重试",
            )
        else:
            sanitized[key] = sanitize_response_data(item, status_code=status_code)
    return sanitized


def _exception_error_code(exc, status_code: int) -> str:
    if isinstance(exc, (AuthenticationFailed, NotAuthenticated)):
        return "AUTHENTICATION_REQUIRED"
    if isinstance(exc, PermissionDenied):
        return "PERMISSION_DENIED"
    if isinstance(exc, NotFound):
        return "NOT_FOUND"
    if isinstance(exc, ValidationError):
        return "VALIDATION_ERROR"
    if isinstance(exc, Throttled):
        return "RATE_LIMITED"
    if status_code >= status.HTTP_500_INTERNAL_SERVER_ERROR:
        return "INTERNAL_ERROR"
    return "REQUEST_FAILED"


def _exception_detail(error_code: str) -> str:
    messages = {
        "AUTHENTICATION_REQUIRED": "登录状态已失效，请重新登录",
        "PERMISSION_DENIED": "当前账号没有执行此操作的权限",
        "NOT_FOUND": "请求的资源不存在或已被删除",
        "VALIDATION_ERROR": "请检查填写内容",
        "RATE_LIMITED": "操作过于频繁，请稍后重试",
        "INTERNAL_ERROR": "服务暂时出现异常，请稍后重试",
        "REQUEST_FAILED": "请求处理失败，请稍后重试",
    }
    return messages[error_code]


def api_exception_handler(exc, context):
    """Convert framework and unhandled exceptions to the public error contract."""
    from rest_framework.views import exception_handler as drf_exception_handler

    request = context.get("request")
    response = drf_exception_handler(exc, context)

    if response is None:
        request_id = get_request_id(request)
        logger.exception("Unhandled API error request_id=%s", request_id)
        return api_error_response(
            request,
            error_code="INTERNAL_ERROR",
            detail="服务暂时出现异常，请稍后重试",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    error_code = _exception_error_code(exc, response.status_code)
    field_errors = response.data if isinstance(exc, ValidationError) else None
    response.data = build_error_payload(
        request,
        error_code=error_code,
        detail=_exception_detail(error_code),
        field_errors=field_errors,
    )
    return response
