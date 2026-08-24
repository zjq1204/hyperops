"""Shared middleware utilities for backend products."""

from django.conf import settings

from platformkit.i18n import remap_accept_language_header


class RequestIdMiddleware:
    """Attach a correlation id to every request and response."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        from core.api_errors import get_request_id
        from core.logging import bind_log_context, reset_log_context

        request_id = get_request_id(request)
        tokens = bind_log_context(request_id=request_id, task_id="-")
        try:
            response = self.get_response(request)
            response["X-Request-ID"] = request_id
            return response
        finally:
            reset_log_context(tokens)


class LanguageCodeMappingMiddleware:
    """Map browser language codes to the project's configured Django codes."""

    def __init__(self, get_response):
        self.get_response = get_response
        self.language_mapping = getattr(
            settings,
            "LANGUAGE_CODE_MAPPING",
            {},
        )

    def __call__(self, request):
        accept_language = request.META.get("HTTP_ACCEPT_LANGUAGE", "")
        request.META["HTTP_ACCEPT_LANGUAGE"] = remap_accept_language_header(
            accept_language,
            self.language_mapping,
        )
        return self.get_response(request)
