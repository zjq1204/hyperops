"""Shared language and localization helpers for backend products."""

from __future__ import annotations

from typing import Iterable

from django.conf import settings


def get_supported_language_codes(
    languages: Iterable[tuple[str, str]] | None = None,
) -> dict[str, str]:
    """Return configured language codes keyed by lowercase variants."""
    resolved_languages = languages if languages is not None else settings.LANGUAGES
    return {
        code.lower(): code
        for code, _ in resolved_languages
    }


def get_default_language_code(
    languages: Iterable[tuple[str, str]] | None = None,
    default_language: str | None = None,
) -> str:
    """Return a safe default language present in the configured languages."""
    resolved_languages = list(
        languages if languages is not None else settings.LANGUAGES
    )
    if not resolved_languages:
        return default_language or settings.LANGUAGE_CODE

    configured_codes = get_supported_language_codes(resolved_languages)
    fallback = default_language or settings.LANGUAGE_CODE
    if fallback.lower() in configured_codes:
        return configured_codes[fallback.lower()]
    return resolved_languages[0][0]


def normalize_language_code(
    value: str | None,
    *,
    languages: Iterable[tuple[str, str]] | None = None,
    default_language: str | None = None,
    mapping: dict[str, str] | None = None,
) -> str:
    """Normalize a requested language to one of the configured codes."""
    resolved_languages = list(
        languages if languages is not None else settings.LANGUAGES
    )
    resolved_default = get_default_language_code(
        resolved_languages,
        default_language=default_language,
    )
    configured_codes = get_supported_language_codes(resolved_languages)
    if not configured_codes:
        return resolved_default

    if not value:
        return resolved_default

    raw_value = value.strip().lower()
    if not raw_value:
        return resolved_default

    normalized_value = raw_value.replace("_", "-")
    resolved_mapping = (
        mapping if mapping is not None
        else getattr(settings, "LANGUAGE_CODE_MAPPING", {})
    )
    mapped_value = resolved_mapping.get(normalized_value)
    if mapped_value and mapped_value.lower() in configured_codes:
        return configured_codes[mapped_value.lower()]

    direct_match = configured_codes.get(normalized_value)
    if direct_match:
        return direct_match

    return resolved_default


def get_translation_language_code(
    language: str | None,
    *,
    mapping: dict[str, str] | None = None,
    default_language: str | None = None,
) -> str:
    """Normalize a language for Django translation override usage."""
    if not language:
        return default_language or settings.LANGUAGE_CODE

    normalized = language.lower().replace("_", "-")
    resolved_mapping = (
        mapping if mapping is not None
        else getattr(settings, "LANGUAGE_CODE_MAPPING", {})
    )
    return resolved_mapping.get(
        normalized,
        default_language or normalized,
    )


def remap_accept_language_header(
    header_value: str | None,
    mapping: dict[str, str] | None = None,
) -> str:
    """Rewrite the first Accept-Language code using configured aliases."""
    if not header_value:
        return header_value or ""

    resolved_mapping = (
        mapping if mapping is not None
        else getattr(settings, "LANGUAGE_CODE_MAPPING", {})
    )
    if not resolved_mapping:
        return header_value

    parts = header_value.split(",")
    first_part = parts[0].strip()
    first_lang = first_part.lower().split(";", 1)[0].strip()
    mapped_lang = resolved_mapping.get(first_lang)
    if not mapped_lang:
        return header_value

    quality_part = first_part.split(";", 1)
    if len(quality_part) > 1:
        new_first_part = f"{mapped_lang};{quality_part[1]}"
    else:
        new_first_part = mapped_lang

    remaining_parts = ",".join(parts[1:]) if len(parts) > 1 else ""
    return f"{new_first_part},{remaining_parts}".rstrip(",")
