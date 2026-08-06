from types import SimpleNamespace

from core.api_errors import (
    get_request_id,
    sanitize_public_message,
    sanitize_response_data,
)


def test_sanitize_public_message_hides_upstream_auth_url():
    message = (
        "401 Client Error: Unauthorized for url: "
        "http://jenkins.internal/api/json?tree=jobs"
    )

    assert sanitize_public_message(message, status_code=400) == (
        "外部服务认证失败，请检查连接凭据"
    )


def test_sanitize_response_data_cleans_nested_bulk_errors():
    payload = {
        "results": [
            {
                "project": "demo",
                "error": "requests.exceptions.ConnectionError: "
                "http://gitlab.internal/api/v4/projects/1",
            }
        ]
    }

    sanitized = sanitize_response_data(payload, status_code=200)

    assert sanitized["results"][0]["project"] == "demo"
    assert sanitized["results"][0]["error"] == "请求处理失败，请稍后重试"
    assert "gitlab.internal" not in str(sanitized)


def test_sanitize_response_data_preserves_empty_success_error_field():
    payload = {
        "connected": True,
        "error": "",
        "targets": [{"health": "up", "last_error": ""}],
    }

    sanitized = sanitize_response_data(payload, status_code=200)

    assert sanitized["error"] == ""
    assert sanitized["targets"][0]["last_error"] == ""


def test_get_request_id_rejects_untrusted_header_content():
    request = SimpleNamespace(
        META={"HTTP_X_REQUEST_ID": "bad request id with spaces"}
    )

    request_id = get_request_id(request)

    assert len(request_id) == 32
    assert request_id == request.request_id
