import socket

import requests


class ObjectStorageProviderError(RuntimeError):
    def __init__(self, error_code, *, retryable=False, request_id=""):
        self.error_code = error_code
        self.retryable = retryable
        self.request_id = request_id
        super().__init__(error_code)


ERROR_CODE_MAP = {
    "BucketAlreadyExists": "BUCKET_NAME_CONFLICT",
    "BucketAlreadyOwnedByYou": "BUCKET_NAME_CONFLICT",
    "NoSuchBucket": "BUCKET_NOT_FOUND",
    "NoSuchEntity": "CLOUD_IDENTITY_NOT_FOUND",
    "AccessDenied": "PROVIDER_PERMISSION_DENIED",
    "Forbidden": "PROVIDER_PERMISSION_DENIED",
    "InvalidAccessKeyId": "PROVIDER_CREDENTIAL_INVALID",
    "SignatureDoesNotMatch": "PROVIDER_CREDENTIAL_INVALID",
    "LimitExceeded": "PROVIDER_LIMIT_EXCEEDED",
    "Throttling": "PROVIDER_RATE_LIMITED",
    "ServiceUnavailable": "PROVIDER_UNAVAILABLE",
}


RETRYABLE_CODES = {
    "PROVIDER_RATE_LIMITED",
    "PROVIDER_TIMEOUT",
    "PROVIDER_UNAVAILABLE",
}


def is_temporary_provider_error(error):
    return getattr(error, "error_code", "") in RETRYABLE_CODES


def map_provider_error(exc):
    if isinstance(exc, ObjectStorageProviderError):
        return exc
    request_id = str(getattr(exc, "request_id", "") or "")
    raw_code = str(getattr(exc, "code", "") or getattr(exc, "error_code", "") or "")
    if isinstance(exc, (TimeoutError, socket.timeout, requests.Timeout)):
        error_code = "PROVIDER_TIMEOUT"
    elif isinstance(exc, (ConnectionError, requests.ConnectionError)):
        error_code = "PROVIDER_UNAVAILABLE"
    else:
        error_code = ERROR_CODE_MAP.get(raw_code, "PROVIDER_OPERATION_FAILED")
    return ObjectStorageProviderError(
        error_code,
        retryable=error_code in RETRYABLE_CODES,
        request_id=request_id,
    )
