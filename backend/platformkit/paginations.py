"""Shared API pagination helpers."""

from rest_framework.pagination import PageNumberPagination


class APIPagination(PageNumberPagination):
    """Standardized page-number pagination for backend APIs."""

    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 10000
    page_query_param = "page"
