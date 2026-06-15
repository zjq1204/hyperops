"""Shared platform kernel for cross-product backend utilities."""

from __future__ import annotations

from importlib import import_module

_EXPORT_MAP = {
    "APIPagination": ("platformkit.paginations", "APIPagination"),
    "AccessPolicy": ("platformkit.access", "AccessPolicy"),
    "AuthTokenResponseSerializer": (
        "platformkit.auth",
        "AuthTokenResponseSerializer",
    ),
    "BaseResponseWrapper": ("platformkit.swagger", "BaseResponseWrapper"),
    "ErrorResponseSerializer": (
        "platformkit.swagger",
        "ErrorResponseSerializer",
    ),
    "FeatureDefinition": ("platformkit.access", "FeatureDefinition"),
    "LanguageCodeMappingMiddleware": (
        "platformkit.middleware",
        "LanguageCodeMappingMiddleware",
    ),
    "PasswordResetConfirmSerializer": (
        "platformkit.auth",
        "PasswordResetConfirmSerializer",
    ),
    "SuccessResponseSerializer": (
        "platformkit.auth",
        "SuccessResponseSerializer",
    ),
    "TASK_REGISTRY": ("platformkit.periodic_registry", "TASK_REGISTRY"),
    "TokenVerificationResponseSerializer": (
        "platformkit.auth",
        "TokenVerificationResponseSerializer",
    ),
    "TaskRegistry": ("platformkit.periodic_registry", "TaskRegistry"),
    "UsernameAvailabilityResponseSerializer": (
        "platformkit.auth",
        "UsernameAvailabilityResponseSerializer",
    ),
    "apply_registry": ("platformkit.periodic_registry", "apply_registry"),
    "build_group_payload": ("platformkit.management", "build_group_payload"),
    "build_group_summary": ("platformkit.management", "build_group_summary"),
    "build_paginated_payload": ("platformkit.api", "build_paginated_payload"),
    "build_auth_info": ("platformkit.users", "build_auth_info"),
    "build_display_name": ("platformkit.users", "build_display_name"),
    "build_profile_snapshot": ("platformkit.users", "build_profile_snapshot"),
    "build_role_payload": ("platformkit.management", "build_role_payload"),
    "build_role_summary": ("platformkit.management", "build_role_summary"),
    "build_social_login_identifier": (
        "platformkit.social",
        "build_social_login_identifier",
    ),
    "build_user_payload": ("platformkit.management", "build_user_payload"),
    "ensure_password_auth_enabled": (
        "platformkit.auth",
        "ensure_password_auth_enabled",
    ),
    "error_response": ("platformkit.swagger", "error_response"),
    "get_default_language_code": (
        "platformkit.i18n",
        "get_default_language_code",
    ),
    "get_password_reset_eligible_user": (
        "platformkit.auth",
        "get_password_reset_eligible_user",
    ),
    "get_primary_social_account": (
        "platformkit.social",
        "get_primary_social_account",
    ),
    "get_provider_display_name": (
        "platformkit.social",
        "get_provider_display_name",
    ),
    "get_provider_uid": ("platformkit.social", "get_provider_uid"),
    "get_social_account": ("platformkit.social", "get_social_account"),
    "get_social_accounts": ("platformkit.social", "get_social_accounts"),
    "get_social_provider_names": (
        "platformkit.social",
        "get_social_provider_names",
    ),
    "get_supported_language_codes": (
        "platformkit.i18n",
        "get_supported_language_codes",
    ),
    "get_translation_language_code": (
        "platformkit.i18n",
        "get_translation_language_code",
    ),
    "get_virtual_email": ("platformkit.users", "get_virtual_email"),
    "has_provider": ("platformkit.social", "has_provider"),
    "is_username_available": ("platformkit.auth", "is_username_available"),
    "normalize_language_code": ("platformkit.i18n", "normalize_language_code"),
    "normalize_virtual_email_username": (
        "platformkit.identifiers",
        "normalize_virtual_email_username",
    ),
    "ordering_param": ("platformkit.swagger", "ordering_param"),
    "pagination_params": ("platformkit.swagger", "pagination_params"),
    "pagination_response": ("platformkit.swagger", "pagination_response"),
    "parse_bounded_int": ("platformkit.api", "parse_bounded_int"),
    "redoc_view": ("platformkit.swagger", "redoc_view"),
    "remap_accept_language_header": (
        "platformkit.i18n",
        "remap_accept_language_header",
    ),
    "response": ("platformkit.swagger", "response"),
    "schema_view": ("platformkit.swagger", "schema_view"),
    "search_param": ("platformkit.swagger", "search_param"),
    "swagger_view": ("platformkit.swagger", "swagger_view"),
    "upsert_profile_preferences": (
        "platformkit.users",
        "upsert_profile_preferences",
    ),
    "validate_password_strength": (
        "platformkit.auth",
        "validate_password_strength",
    ),
    "validate_virtual_email_alias": (
        "platformkit.identifiers",
        "validate_virtual_email_alias",
    ),
    "validate_virtual_email_username": (
        "platformkit.identifiers",
        "validate_virtual_email_username",
    ),
}

__all__ = sorted(_EXPORT_MAP)


def __getattr__(name):
    """Lazily resolve exported helpers to keep settings import safe."""
    try:
        module_name, attr_name = _EXPORT_MAP[name]
    except KeyError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc

    value = getattr(import_module(module_name), attr_name)
    globals()[name] = value
    return value


def __dir__():
    """Expose lazy exports to interactive tooling."""
    return sorted(list(globals().keys()) + __all__)
