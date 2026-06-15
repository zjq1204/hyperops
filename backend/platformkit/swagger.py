"""
Shared OpenAPI schema helpers and documentation wrappers.

This module keeps the response-schema and parameter helper logic product
neutral so projects can reuse the same API documentation conventions without
copying `core.swagger`.
"""

from drf_spectacular.openapi import OpenApiParameter
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)
from rest_framework import serializers
from rest_framework.permissions import AllowAny


schema_view = SpectacularAPIView.as_view(
    permission_classes=(AllowAny,),
    authentication_classes=(),
)

swagger_view = SpectacularSwaggerView.as_view(
    permission_classes=(AllowAny,),
    authentication_classes=(),
)

redoc_view = SpectacularRedocView.as_view(
    permission_classes=(AllowAny,),
    authentication_classes=(),
)


def pagination_params():
    """Return common pagination query parameters for API docs."""
    return [
        OpenApiParameter(
            name="page",
            type=OpenApiTypes.INT,
            location=OpenApiParameter.QUERY,
            description="Page number (starts from 1)",
            default=1,
        ),
        OpenApiParameter(
            name="page_size",
            type=OpenApiTypes.INT,
            location=OpenApiParameter.QUERY,
            description="Number of items per page (max 100)",
            default=10,
        ),
    ]


def ordering_param(default="created_at"):
    """Return a reusable ordering query parameter for API docs."""
    return OpenApiParameter(
        name="ordering",
        type=OpenApiTypes.STR,
        location=OpenApiParameter.QUERY,
        description=(
            "Order field, prefix with '-' for descending "
            f"(default: {default})"
        ),
        required=False,
        default=default,
    )


def search_param():
    """Return a reusable search query parameter for API docs."""
    return OpenApiParameter(
        name="search",
        type=OpenApiTypes.STR,
        location=OpenApiParameter.QUERY,
        description="Search term to filter results",
        required=False,
    )


class BaseResponseWrapper(serializers.Serializer):
    """Base serializer for standardized API response documentation."""

    code = serializers.IntegerField(help_text="Response status code")
    message = serializers.CharField(help_text="Response message")
    data = serializers.Field(help_text="Response data")


class ErrorResponseSerializer(serializers.Serializer):
    """Standard error response serializer for API documentation."""

    code = serializers.IntegerField(help_text="Error status code")
    message = serializers.CharField(help_text="Error message")
    data = serializers.CharField(allow_null=True, help_text="Error details")


def response(serializer_class):
    """Wrap a serializer in the standard single-object response shape."""
    serializer_name = getattr(serializer_class, "__name__", "Unknown")
    if not serializer_name or serializer_name == "Serializer":
        serializer_name = f"Serializer_{id(serializer_class)}"

    class_name = f"SingleResponse_{serializer_name}"
    return type(
        class_name,
        (BaseResponseWrapper,),
        {
            "data": serializer_class(help_text="Response data"),
            "__module__": "platformkit.swagger",
        },
    )


def error_response():
    """Return the standard error response serializer."""
    return ErrorResponseSerializer


def list_response(serializer_class):
    """Wrap a serializer list in the standard array response shape."""
    class_name = f"ArrayResponse_{serializer_class.__name__}"
    return type(
        class_name,
        (BaseResponseWrapper,),
        {
            "data": serializers.ListField(
                child=serializer_class(),
                help_text="List of items",
            ),
            "__module__": "platformkit.swagger",
        },
    )


def pagination_response(serializer_class):
    """Wrap a serializer list in the standard paginated response shape."""
    pagination_info_name = f"PaginationInfo_{serializer_class.__name__}"
    pagination_info_class = type(
        pagination_info_name,
        (serializers.Serializer,),
        {
            "total": serializers.IntegerField(help_text="Total number of items"),
            "page": serializers.IntegerField(help_text="Current page number"),
            "pageSize": serializers.IntegerField(
                help_text="Number of items per page"
            ),
            "next": serializers.URLField(
                allow_null=True,
                help_text="URL to next page",
            ),
            "previous": serializers.URLField(
                allow_null=True,
                help_text="URL to previous page",
            ),
            "__module__": "platformkit.swagger",
        },
    )

    paginated_data_name = f"PaginatedData_{serializer_class.__name__}"
    paginated_data_class = type(
        paginated_data_name,
        (serializers.Serializer,),
        {
            "list": serializers.ListField(
                child=serializer_class(),
                help_text="List of items for current page",
            ),
            "pagination": pagination_info_class(
                help_text="Pagination information"
            ),
            "__module__": "platformkit.swagger",
        },
    )

    wrapper_name = f"PaginatedResponse_{serializer_class.__name__}"
    return type(
        wrapper_name,
        (BaseResponseWrapper,),
        {
            "data": paginated_data_class(help_text="Paginated data"),
            "__module__": "platformkit.swagger",
        },
    )
