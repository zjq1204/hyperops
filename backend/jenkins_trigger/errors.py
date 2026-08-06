"""Safe classification for failures returned by Jenkins."""

from dataclasses import dataclass

import requests
from rest_framework import status


@dataclass(frozen=True)
class JenkinsPublicError:
    error_code: str
    detail: str
    status_code: int


def classify_jenkins_error(
    exc: Exception,
    default_detail: str = "Jenkins 请求失败，请稍后重试",
) -> JenkinsPublicError:
    response = getattr(exc, "response", None)
    upstream_status = getattr(response, "status_code", None)

    if upstream_status == 401:
        return JenkinsPublicError(
            error_code="JENKINS_AUTH_FAILED",
            detail="Jenkins 认证失败，请检查用户名或 API Token",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
    if upstream_status == 403:
        return JenkinsPublicError(
            error_code="JENKINS_PERMISSION_DENIED",
            detail="当前 Jenkins 账号没有读取 Job 的权限",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
    if upstream_status == 404:
        return JenkinsPublicError(
            error_code="JENKINS_ENDPOINT_NOT_FOUND",
            detail="Jenkins 接口地址无效，请检查实例地址",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
    if isinstance(exc, requests.exceptions.Timeout):
        return JenkinsPublicError(
            error_code="JENKINS_TIMEOUT",
            detail="Jenkins 响应超时，请稍后重试",
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
        )
    if isinstance(exc, requests.exceptions.ConnectionError):
        return JenkinsPublicError(
            error_code="JENKINS_UNAVAILABLE",
            detail="Jenkins 服务暂时无法访问，请检查地址和网络",
            status_code=status.HTTP_502_BAD_GATEWAY,
        )
    return JenkinsPublicError(
        error_code="JENKINS_REQUEST_FAILED",
        detail=default_detail,
        status_code=status.HTTP_400_BAD_REQUEST,
    )
