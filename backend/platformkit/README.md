# PlatformKit

`platformkit` is the shared backend kernel extracted from HyperOps stage 2.

## Purpose

This package is where product-neutral backend building blocks should live so
both `hyperops` and `devmind` can reuse the same logic without copying entire
apps.

## What belongs here

- Access-control engines driven by product manifests
- Shared pagination helpers
- Shared periodic-task registration utilities
- Shared settings helpers for environment parsing
- Shared language normalization and locale middleware helpers
- Shared API payload helpers for paginated responses
- Shared admin payload assembly helpers
- Shared authentication schema serializers and validators
- Shared username / virtual-email identifier validators
- Shared social-account and provider display helpers
- Shared OpenAPI schema and Swagger helper functions
- Shared user display and auth-info serializers
- Other pure backend utilities that do not hardcode product routes, branding,
  or app names

## What stays product-local

- Django app models and migrations
- Feature definitions, aliases, and landing routes
- Product branding, route trees, and API descriptions
- Jenkins, GitLab, billing, AI pricing, or other domain-specific apps

## Current extraction

- `platformkit.access.AccessPolicy`
- `platformkit.api.parse_bounded_int`
- `platformkit.api.build_paginated_payload`
- `platformkit.management.build_user_payload`
- `platformkit.management.build_role_summary`
- `platformkit.paginations.APIPagination`
- `platformkit.periodic_registry.TaskRegistry`
- `platformkit.settings.env_flag`
- `platformkit.i18n.normalize_language_code`
- `platformkit.i18n.get_translation_language_code`
- `platformkit.identifiers.validate_virtual_email_username`
- `platformkit.identifiers.validate_virtual_email_alias`
- `platformkit.middleware.LanguageCodeMappingMiddleware`
- `platformkit.auth.is_username_available`
- `platformkit.auth.validate_password_strength`
- `platformkit.auth.get_password_reset_eligible_user`
- `platformkit.auth.PasswordResetConfirmSerializer`
- `platformkit.social.get_provider_display_name`
- `platformkit.social.get_social_accounts`
- `platformkit.swagger.pagination_params`
- `platformkit.swagger.response`
- `platformkit.auth.SuccessResponseSerializer`
- `platformkit.users.build_display_name`
- `platformkit.users.build_auth_info`
- `platformkit.users.upsert_profile_preferences`

HyperOps keeps thin wrappers in `accounts/access.py`, `core/paginations.py`,
and `core/periodic_registry.py` so existing imports remain stable while the
shared kernel becomes adoptable by other projects.
