"""Compatibility wrapper for shared OpenAPI schema helpers."""

from platformkit.swagger import (
    BaseResponseWrapper,
    ErrorResponseSerializer,
    error_response,
    list_response,
    ordering_param,
    pagination_params,
    pagination_response,
    redoc_view,
    response,
    schema_view,
    search_param,
    swagger_view,
)

__all__ = [
    "BaseResponseWrapper",
    "ErrorResponseSerializer",
    "error_response",
    "list_response",
    "ordering_param",
    "pagination_params",
    "pagination_response",
    "redoc_view",
    "response",
    "schema_view",
    "search_param",
    "swagger_view",
]
