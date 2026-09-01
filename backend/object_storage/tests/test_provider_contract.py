from dataclasses import fields, is_dataclass


def test_provider_protocol_exposes_only_business_operations():
    from object_storage.providers.base import ObjectStorageProvider

    operations = {
        name
        for name, value in vars(ObjectStorageProvider).items()
        if callable(value) and not name.startswith("_")
    }

    assert operations == {
        "validate_management_identity",
        "find_or_create_personal_principal",
        "create_owned_bucket",
        "find_owned_bucket",
        "inspect_bucket_emptiness",
        "delete_owned_bucket",
        "reconcile_object_policy",
        "list_access_keys",
        "create_access_key",
        "activate_access_key",
        "deactivate_access_key",
        "delete_access_key",
        "get_bucket_configuration",
        "update_bucket_configuration",
    }


def test_provider_results_are_sanitized_dataclasses_with_error_categories():
    from object_storage.providers.base import (
        AccessKeyMetadata,
        AccessKeyMutation,
        BucketOwnership,
        BucketConfigurationMutation,
        BucketEmptiness,
        BucketMutation,
        IssuedAccessKey,
        ManagementCapabilities,
        KeyListResult,
        PersonalPrincipal,
        PolicyMutation,
    )

    result_types = (
        ManagementCapabilities,
        PersonalPrincipal,
        BucketMutation,
        BucketOwnership,
        BucketEmptiness,
        PolicyMutation,
        AccessKeyMetadata,
        KeyListResult,
        IssuedAccessKey,
        AccessKeyMutation,
        BucketConfigurationMutation,
    )

    for result_type in result_types:
        assert is_dataclass(result_type)
        field_names = {field.name for field in fields(result_type)}
        assert "error_category" in field_names
        assert {"request_id", "request_ids"}.intersection(field_names)


def test_issued_secret_is_available_to_persistence_but_redacted_from_repr():
    from object_storage.providers.base import IssuedAccessKey

    issued = IssuedAccessKey(
        access_key_id="LTAI-safe-id",
        secret_access_key="credential-must-not-be-logged",
        request_id="request-id",
    )

    assert issued.secret_access_key == "credential-must-not-be-logged"
    assert "credential-must-not-be-logged" not in repr(issued)


def test_bucket_configuration_contract_allows_no_public_write():
    import pytest

    from object_storage.providers.base import BucketConfiguration

    assert BucketConfiguration(acl="private").acl == "private"
    assert BucketConfiguration(acl="public_read").acl == "public_read"
    with pytest.raises(ValueError, match="BUCKET_ACL_UNSUPPORTED"):
        BucketConfiguration(acl="public_read_write")
