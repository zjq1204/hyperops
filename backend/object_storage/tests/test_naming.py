import pytest


def test_render_bucket_name_normalizes_values_and_is_deterministic(
    storage_membership_factory,
):
    from object_storage.services.naming import render_bucket_name

    membership = storage_membership_factory(
        display_name="Zhang San",
        feishu_open_id="ou_stable_user",
    )

    first = render_bucket_name(
        tenant=membership.tenant,
        membership=membership,
        project="Billing API",
        environment="Production",
        purpose="Daily Export",
    )
    second = render_bucket_name(
        tenant=membership.tenant,
        membership=membership,
        project="Billing API",
        environment="Production",
        purpose="Daily Export",
    )

    assert first == second
    assert first == first.lower()
    assert first.isascii()
    assert "billing-api" in first


def test_unknown_template_variable_is_rejected(storage_tenant_factory):
    from object_storage.services.naming import (
        BucketNamingError,
        validate_naming_template,
    )

    tenant = storage_tenant_factory(
        bucket_naming_template="{tenant}-{unknown}-{suffix}"
    )

    with pytest.raises(BucketNamingError, match="UNKNOWN_TEMPLATE_VARIABLE"):
        validate_naming_template(tenant.bucket_naming_template)


def test_template_must_include_deterministic_suffix(storage_tenant_factory):
    from object_storage.services.naming import (
        BucketNamingError,
        validate_naming_template,
    )

    tenant = storage_tenant_factory(bucket_naming_template="{tenant}-{project}")

    with pytest.raises(BucketNamingError, match="SUFFIX_REQUIRED"):
        validate_naming_template(tenant.bucket_naming_template)


def test_rendered_name_is_between_3_and_63_characters(
    storage_membership_factory,
):
    from object_storage.services.naming import render_bucket_name

    membership = storage_membership_factory(
        display_name="\u5f20\u4e09",
        feishu_open_id="ou_non_ascii_user",
    )
    name = render_bucket_name(
        tenant=membership.tenant,
        membership=membership,
        project="\u8d85\u957f\u9879\u76ee" * 40,
        environment="production",
        purpose="\u6570\u636e\u5907\u4efd" * 40,
    )

    assert 3 <= len(name) <= 63
    assert name.isascii()
    assert name[0].isalnum() and name[-1].isalnum()


def test_rendered_name_changes_when_business_identity_changes(
    storage_membership_factory,
):
    from object_storage.services.naming import render_bucket_name

    membership = storage_membership_factory()
    common = {
        "tenant": membership.tenant,
        "membership": membership,
        "environment": "test",
        "purpose": "backup",
    }

    assert render_bucket_name(project="project-a", **common) != render_bucket_name(
        project="project-b", **common
    )
