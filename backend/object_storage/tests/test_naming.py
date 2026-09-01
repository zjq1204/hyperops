import re

import pytest


def _render(**overrides):
    from object_storage.services.naming import render_bucket_name

    values = {
        "template": (
            "{prefix}-{user}-{business_name}-{project}-{environment}-"
            "{purpose}-{suffix}"
        ),
        "prefix": "H",
        "user": "John Doe",
        "business_name": "Billing",
        "project": "Cloud",
        "environment": "Prod",
        "purpose": "Export",
        "suffix": "a1b2c3d4",
    }
    values.update(overrides)
    return render_bucket_name(**values)


def test_render_bucket_name_normalizes_all_documented_values():
    name = _render()

    assert name == ("h-john-doe-billing-cloud-prod-export-a1b2c3d4")
    assert name.isascii()
    assert re.fullmatch(r"[a-z0-9][a-z0-9-]{1,61}[a-z0-9]", name)


def test_preview_and_submission_reuse_the_exact_suffix():
    preview_suffix = "4f7k2m9q"

    preview = _render(suffix=preview_suffix, template="{business_name}-{suffix}")
    submission = _render(
        suffix=preview_suffix,
        template="{business_name}-{suffix}",
    )

    assert preview == submission == "billing-4f7k2m9q"


def test_generate_suffix_is_eight_lowercase_alphanumeric_characters():
    from object_storage.services.naming import generate_suffix

    suffixes = {generate_suffix() for _index in range(20)}

    assert all(re.fullmatch(r"[a-z0-9]{8}", suffix) for suffix in suffixes)
    assert len(suffixes) > 1


def test_candidate_generation_returns_suffix_for_conflict_retry(monkeypatch):
    from object_storage.services import naming

    generated = iter(("aaaaaaaa", "bbbbbbbb"))
    monkeypatch.setattr(naming, "generate_suffix", lambda: next(generated))
    values = {
        "template": "{prefix}-{business_name}-{suffix}",
        "prefix": "hyperops",
        "user": "unused",
        "business_name": "billing",
        "project": "unused",
        "environment": "unused",
        "purpose": "unused",
    }

    first = naming.generate_bucket_name_candidate(**values)
    second = naming.generate_bucket_name_candidate(**values)

    assert (first.name, first.suffix) == ("hyperops-billing-aaaaaaaa", "aaaaaaaa")
    assert (second.name, second.suffix) == ("hyperops-billing-bbbbbbbb", "bbbbbbbb")


def test_create_bucket_with_unique_name_retries_three_fresh_suffixes(monkeypatch):
    from object_storage.services import naming
    from object_storage.services.provider_errors import ObjectStorageProviderError

    generated = iter(("aaaaaaaa", "bbbbbbbb", "cccccccc"))
    attempted = []
    monkeypatch.setattr(naming, "generate_suffix", lambda: next(generated))

    def conflict(candidate):
        attempted.append(candidate)
        raise ObjectStorageProviderError(
            "BUCKET_NAME_CONFLICT",
            request_id=f"request-{len(attempted)}",
        )

    with pytest.raises(ObjectStorageProviderError) as captured:
        naming.create_bucket_with_unique_name(
            create_callback=conflict,
            template="{prefix}-{business_name}-{suffix}",
            prefix="hyperops",
            user="unused",
            business_name="billing",
            project="unused",
            environment="unused",
            purpose="unused",
        )

    assert [candidate.suffix for candidate in attempted] == [
        "aaaaaaaa",
        "bbbbbbbb",
        "cccccccc",
    ]
    assert captured.value.error_code == "BUCKET_NAME_CONFLICT"
    assert captured.value.request_id == "request-3"


def test_create_bucket_with_unique_name_returns_successful_callback_result(monkeypatch):
    from object_storage.services import naming
    from object_storage.services.provider_errors import ObjectStorageProviderError

    generated = iter(("aaaaaaaa", "bbbbbbbb"))
    monkeypatch.setattr(naming, "generate_suffix", lambda: next(generated))

    def create(candidate):
        if candidate.suffix == "aaaaaaaa":
            raise ObjectStorageProviderError("BUCKET_NAME_CONFLICT")
        return {"created_name": candidate.name}

    result = naming.create_bucket_with_unique_name(
        create_callback=create,
        template="{business_name}-{suffix}",
        prefix="unused",
        user="unused",
        business_name="billing",
        project="unused",
        environment="unused",
        purpose="unused",
    )

    assert result == {"created_name": "billing-bbbbbbbb"}


def test_remaining_business_name_length_uses_fixed_rendered_context():
    from object_storage.services.naming import remaining_business_name_length

    context = {
        "prefix": "hyperops",
        "user": "unused",
        "project": "unused",
        "environment": "unused",
        "purpose": "unused",
    }

    assert (
        remaining_business_name_length(
            "{prefix}-{business_name}-{suffix}",
            context,
            "a1b2c3d4",
        )
        == 45
    )
    assert (
        remaining_business_name_length(
            "x" * 70 + "-{business_name}-{suffix}",
            context,
            "a1b2c3d4",
        )
        == 0
    )


@pytest.mark.parametrize(
    "template",
    (
        "{tenant}-{business_name}-{suffix}",
        "{business_name.__class__}-{suffix}",
    ),
)
def test_unknown_template_variable_is_rejected(template):
    from object_storage.services.naming import (
        BucketNamingError,
        validate_naming_template,
    )

    with pytest.raises(BucketNamingError, match="UNKNOWN_TEMPLATE_VARIABLE"):
        validate_naming_template(template)


def test_template_must_include_random_suffix():
    from object_storage.services.naming import (
        BucketNamingError,
        validate_naming_template,
    )

    with pytest.raises(BucketNamingError, match="SUFFIX_REQUIRED"):
        validate_naming_template("{prefix}-{business_name}")


def test_long_rendered_name_is_rejected_without_silent_truncation():
    from object_storage.services.naming import BucketNamingError

    with pytest.raises(BucketNamingError, match="BUCKET_NAME_TOO_LONG"):
        _render(
            template="{business_name}-{suffix}",
            business_name="a" * 55,
        )


@pytest.mark.parametrize(
    "template,error_code",
    (
        ("-{business_name}-{suffix}", "BUCKET_NAME_INVALID"),
        ("{business_name}-{suffix}-", "BUCKET_NAME_INVALID"),
        ("x", "SUFFIX_REQUIRED"),
    ),
)
def test_invalid_final_name_is_rejected(template, error_code):
    from object_storage.services.naming import BucketNamingError

    with pytest.raises(BucketNamingError, match=error_code):
        _render(template=template)


@pytest.mark.parametrize("suffix", ("ABC12345", "short", "abcd_123"))
def test_suffix_must_be_exactly_eight_lowercase_alphanumeric(suffix):
    from object_storage.services.naming import BucketNamingError

    with pytest.raises(BucketNamingError, match="SUFFIX_INVALID"):
        _render(template="{business_name}-{suffix}", suffix=suffix)
