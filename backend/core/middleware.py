"""Compatibility wrapper around the shared locale middleware."""

from platformkit.middleware import LanguageCodeMappingMiddleware, RequestIdMiddleware

__all__ = ["LanguageCodeMappingMiddleware", "RequestIdMiddleware"]
