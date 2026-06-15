"""Shared API payload and query-parameter helpers."""


def parse_bounded_int(value, default, min_value=1, max_value=100):
    """Parse an int and clamp it into a bounded range."""
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default

    if parsed < min_value:
        return min_value
    if parsed > max_value:
        return max_value
    return parsed


def build_paginated_payload(items, total, page, page_size, **extra_fields):
    """Build a standard paginated payload with optional extra fields."""
    payload = {
        "count": total,
        "page": page,
        "page_size": page_size,
        "results": items,
    }
    payload.update(extra_fields)
    return payload
