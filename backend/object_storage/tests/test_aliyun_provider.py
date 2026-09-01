from types import SimpleNamespace

import pytest


class FakeRamGateway:
    def __init__(self):
        self.policy = None
        self.updated_key = None
        self.detached_policy = None
        self.deleted_user = None

    def validate_identity(self):
        return {
            "account_id": "123456789",
            "can_manage_ram": True,
            "request_ids": ("ram-request-1",),
            "access_key_secret": "must-not-leak",
        }

    def find_or_create_user(self, user_name, marker):
        return {
            "user_id": "ram-user-id",
            "user_name": user_name,
            "marker": marker,
            "created": True,
            "request_id": "ram-request-2",
            "sdk_body": {"secret": "must-not-leak"},
        }

    def apply_policy(self, user_name, policy):
        self.policy = policy
        return {
            "request_id": "ram-request-3",
            "sdk_body": {"secret": "must-not-leak"},
        }

    def detach_policy_from_user(self, user_name):
        self.detached_policy = user_name
        return {"request_id": "ram-request-detach"}

    def list_access_keys(self, user_name):
        return {
            "items": [
                {
                    "access_key_id": "LTAIabcdefghijkl1234",
                    "status": "Active",
                    "created_at": "2026-08-31T00:00:00Z",
                    "secret_access_key": "must-not-leak",
                }
            ],
            "request_id": "ram-request-list",
            "sdk_body": {"secret": "must-not-leak"},
        }

    def create_access_key(self, user_name):
        return {
            "access_key_id": "LTAIabcdefghijkl5678",
            "secret_access_key": "employee-secret",
            "request_id": "ram-request-4",
        }

    def update_access_key(self, user_name, access_key_id, status):
        self.updated_key = (user_name, access_key_id, status)
        return {"request_id": f"ram-request-{status.lower()}"}

    def delete_access_key(self, user_name, access_key_id):
        return {"request_id": "ram-request-delete"}

    def delete_user(self, user_name, marker):
        self.deleted_user = (user_name, marker)
        return {"request_id": "ram-request-delete-user"}


class FakeOssGateway:
    def __init__(self, inspection=None):
        self.created = None
        self.updated_configuration = None
        self.inspection = inspection or {
            "object_count": 0,
            "version_count": 0,
            "delete_marker_count": 0,
            "multipart_upload_count": 0,
            "request_id": "oss-request-2",
        }

    def validate_identity(self):
        return {"can_manage_oss": True, "request_id": "oss-request-1"}

    def create_bucket(self, **kwargs):
        self.created = kwargs
        return {
            "created": True,
            "request_id": "oss-request-create",
            "sdk_body": {"credential": "must-not-leak"},
        }

    def find_bucket(self, *, bucket_name, marker):
        actual_marker = self.created.get("marker", "") if self.created else ""
        return {
            "exists": self.created is not None,
            "owned": bool(actual_marker) and actual_marker == marker,
            "marker": actual_marker,
            "request_id": "oss-request-find",
        }

    def inspect_bucket(self, bucket_name):
        return dict(self.inspection)

    def delete_bucket(self, bucket_name):
        return {"request_id": "oss-request-delete"}

    def update_bucket_configuration(self, *, bucket_name, configuration):
        self.updated_configuration = (bucket_name, configuration)
        return {"request_id": "oss-request-update"}

    def get_bucket_configuration(self, *, bucket_name):
        configuration = self.updated_configuration[1]
        return {
            "configuration": configuration,
            "request_id": "oss-request-read-configuration",
        }

    def reset_bucket(self):
        self.created = None


def _provider(inspection=None):
    from object_storage.providers.aliyun import AliyunObjectStorageProvider

    ram = FakeRamGateway()
    oss = FakeOssGateway(inspection)
    return AliyunObjectStorageProvider(ram_gateway=ram, oss_gateway=oss), ram, oss


def test_validate_management_identity_returns_safe_capabilities():
    provider, _ram, _oss = _provider()

    capabilities = provider.validate_management_identity(SimpleNamespace())
    payload = capabilities.as_dict()

    assert payload == {
        "account_id": "123456789",
        "can_manage_ram": True,
        "can_manage_oss": True,
        "request_ids": ("ram-request-1", "oss-request-1"),
        "error_category": "",
    }
    assert "secret" not in str(payload).lower()


def test_validate_management_identity_never_falls_back_to_configured_account_id():
    from object_storage.services.provider_errors import ObjectStorageProviderError

    provider, ram, _oss = _provider()
    ram.validate_identity = lambda: {
        "account_id": "",
        "can_manage_ram": True,
        "request_ids": ("ram-request-missing-account",),
    }

    with pytest.raises(ObjectStorageProviderError, match="CLOUD_ACCOUNT_UNVERIFIED"):
        provider.validate_management_identity(
            SimpleNamespace(cloud_account_id="locally-configured-account")
        )


def test_ram_gateway_rejects_sts_response_without_account_id():
    import inspect

    from object_storage.providers.aliyun import AliyunRamGateway
    from object_storage.services.provider_errors import ObjectStorageProviderError

    assert "account_id" not in inspect.signature(AliyunRamGateway).parameters
    gateway = AliyunRamGateway(
        access_key_id="management-ak",
        access_key_secret="management-sk",
    )
    gateway._sts_client = SimpleNamespace(
        call_api=lambda _params, _request, _runtime: {
            "body": {"RequestId": "sts-request-no-account"}
        }
    )

    with pytest.raises(ObjectStorageProviderError, match="CLOUD_ACCOUNT_UNVERIFIED"):
        gateway.validate_identity()


def test_ram_gateway_uses_sts_caller_identity_and_then_checks_ram(monkeypatch):
    from object_storage.providers.aliyun import AliyunRamGateway

    calls = []
    gateway = AliyunRamGateway(
        access_key_id="management-ak",
        access_key_secret="management-sk",
    )
    gateway._sts_client = SimpleNamespace(
        call_api=lambda params, request, runtime: calls.append(
            (params, request, runtime)
        )
        or {
            "body": {
                "AccountId": "cloud-account-123",
                "RequestId": "sts-request-with-account",
            }
        }
    )
    gateway._client = SimpleNamespace(
        list_users=lambda _request: SimpleNamespace(
            body=SimpleNamespace(request_id="ram-request-with-account")
        )
    )
    monkeypatch.setattr(
        AliyunRamGateway,
        "models",
        SimpleNamespace(ListUsersRequest=lambda **kwargs: kwargs),
    )

    result = gateway.validate_identity()

    assert result["account_id"] == "cloud-account-123"
    assert result["request_ids"] == (
        "sts-request-with-account",
        "ram-request-with-account",
    )
    params, request, runtime = calls[0]
    assert params.action == "GetCallerIdentity"
    assert params.version == "2015-04-01"
    assert params.protocol == "HTTPS"
    assert params.pathname == "/"
    assert params.method == "POST"
    assert params.auth_type == "AK"
    assert params.style == "RPC"
    assert params.req_body_type == "json"
    assert params.body_type == "json"
    assert request.body is None
    assert runtime.connect_timeout == 10000
    assert runtime.read_timeout == 10000


def test_create_bucket_is_private_and_returns_sanitized_mutation():
    provider, _ram, oss = _provider()
    bucket = SimpleNamespace(
        name="hyperops-user-billing-abcd1234",
        region="cn-hangzhou",
        cloud_marker="hyperops:bucket:42",
    )

    result = provider.create_owned_bucket(bucket)

    assert oss.created == {
        "bucket_name": bucket.name,
        "region": "cn-hangzhou",
        "acl": "private",
        "storage_class": "Standard",
        "server_side_encryption": "AES256",
        "marker": "hyperops:bucket:42",
    }
    assert result.created is True
    assert result.request_id == "oss-request-create"
    assert "sdk_body" not in repr(result)


def test_create_bucket_applies_complete_desired_configuration():
    from object_storage.providers.base import BucketConfiguration

    provider, _ram, oss = _provider()
    bucket = SimpleNamespace(
        name="hyperops-user-archive-abcd1234",
        region="cn-hangzhou",
        cloud_marker="hyperops:bucket:84",
    )
    configuration = BucketConfiguration(
        acl="private",
        storage_class="IA",
        encryption="KMS",
        versioning=True,
        lifecycle={"rules": []},
    )

    provider.create_owned_bucket(bucket, configuration)

    assert oss.created == {
        "bucket_name": bucket.name,
        "region": "cn-hangzhou",
        "acl": "private",
        "storage_class": "IA",
        "server_side_encryption": "KMS",
        "marker": bucket.cloud_marker,
    }
    assert oss.updated_configuration[0] == bucket.name
    applied = oss.updated_configuration[1]
    assert applied.acl == configuration.acl
    assert applied.encryption == configuration.encryption
    assert applied.versioning is True
    assert applied.lifecycle == configuration.lifecycle


def test_create_bucket_does_not_reapply_creation_only_storage_class():
    from object_storage.providers.base import BucketConfiguration

    provider, _ram, _oss = _provider()
    bucket = SimpleNamespace(
        name="hyperops-user-archive-efgh5678",
        region="cn-hangzhou",
        cloud_marker="hyperops:bucket:85",
    )
    configuration = BucketConfiguration(storage_class="IA", versioning=True)
    reconciled = []
    provider.update_bucket_configuration = (
        lambda selected, applied, **_kwargs: reconciled.append((selected, applied))
    )

    provider.create_owned_bucket(bucket, configuration)

    assert reconciled[0][0] is bucket
    assert reconciled[0][1].storage_class == "Standard"
    assert reconciled[0][1].versioning is True


def test_create_bucket_rejects_public_read_before_cloud_mutation():
    from object_storage.providers.base import BucketConfiguration
    from object_storage.services.provider_errors import ObjectStorageProviderError

    provider, _ram, oss = _provider()
    bucket = SimpleNamespace(
        name="hyperops-user-public-abcd1234",
        region="cn-hangzhou",
        cloud_marker="hyperops:bucket:86",
    )

    with pytest.raises(
        ObjectStorageProviderError,
        match="PUBLIC_READ_REQUIRES_ADMIN_AUTHORIZATION",
    ):
        provider.create_owned_bucket(
            bucket,
            BucketConfiguration(acl="public_read"),
        )

    assert oss.created is None


def test_bucket_business_operations_return_sanitized_dataclasses():
    provider, _ram, oss = _provider()
    bucket = SimpleNamespace(
        name="managed-bucket",
        region="cn-hangzhou",
        cloud_marker="hyperops:bucket:42",
    )
    provider.create_owned_bucket(bucket)

    found = provider.find_owned_bucket(bucket)
    inspected = provider.inspect_bucket_emptiness(bucket)
    deleted = provider.delete_owned_bucket(bucket)

    assert found.exists is True
    assert found.owned is True
    assert found.marker == "hyperops:bucket:42"
    assert found.request_id == "oss-request-find"
    assert inspected.is_empty is True
    assert deleted.request_id == "oss-request-delete"
    assert oss.created["acl"] == "private"


def test_delete_and_update_always_reconcile_ownership_before_mutation():
    from object_storage.providers.base import BucketConfiguration
    from object_storage.services.provider_errors import ObjectStorageProviderError

    provider, _ram, oss = _provider()
    bucket = SimpleNamespace(
        name="stale-bucket",
        region="cn-hangzhou",
        cloud_marker="hyperops:bucket:42",
    )

    deleted = provider.delete_owned_bucket(bucket)
    assert deleted.request_id == "oss-request-find"
    assert oss.created is None
    with pytest.raises(ObjectStorageProviderError, match="NO_SUCH_BUCKET"):
        provider.update_bucket_configuration(
            bucket,
            BucketConfiguration(acl="public_read"),
        )

    oss.created = {
        "bucket_name": bucket.name,
        "marker": "another-service:bucket:9",
    }
    with pytest.raises(ObjectStorageProviderError, match="BUCKET_OWNERSHIP_CONFLICT"):
        provider.delete_owned_bucket(bucket)
    with pytest.raises(ObjectStorageProviderError, match="BUCKET_OWNERSHIP_CONFLICT"):
        provider.update_bucket_configuration(
            bucket,
            BucketConfiguration(acl="private"),
        )

    oss.created["marker"] = bucket.cloud_marker
    updated = provider.update_bucket_configuration(
        bucket,
        BucketConfiguration(acl="private"),
    )
    assert updated.request_id == "oss-request-update"


def test_read_bucket_configuration_reconciles_ownership_and_returns_snapshot():
    from object_storage.providers.base import BucketConfiguration
    from object_storage.services.provider_errors import ObjectStorageProviderError

    provider, _ram, oss = _provider()
    bucket = SimpleNamespace(
        name="managed-bucket",
        region="cn-hangzhou",
        cloud_marker="hyperops:bucket:42",
    )
    configuration = BucketConfiguration(
        acl="public_read",
        storage_class="IA",
        encryption="KMS",
        versioning=True,
        lifecycle={"rules": [{"id": "archive"}]},
    )

    with pytest.raises(ObjectStorageProviderError, match="NO_SUCH_BUCKET"):
        provider.get_bucket_configuration(bucket)

    oss.created = {"bucket_name": bucket.name, "marker": bucket.cloud_marker}
    oss.updated_configuration = (bucket.name, configuration)

    observed = provider.get_bucket_configuration(bucket)

    assert observed == configuration


def test_oss_gateway_reads_complete_bucket_configuration_without_mutation(
    monkeypatch,
):
    from object_storage.providers.aliyun import AliyunOssGateway

    lifecycle = SimpleNamespace(
        rules=[
            SimpleNamespace(
                id="archive",
                prefix="logs/",
                status="Enabled",
                expiration=SimpleNamespace(days=30),
                abort_multipart_upload=SimpleNamespace(days=7),
                storage_transitions=[SimpleNamespace(days=14, storage_class="IA")],
            )
        ]
    )

    class ReadOnlyBucket:
        def get_bucket_info(self):
            return SimpleNamespace(
                acl="public-read",
                storage_class="IA",
                bucket_encryption_rule=SimpleNamespace(sse_algorithm="KMS"),
                versioning_status="Enabled",
                request_id="read-config-request",
            )

        def get_bucket_lifecycle(self):
            return lifecycle

    gateway = AliyunOssGateway(
        access_key_id="unused",
        access_key_secret="unused",
        region="cn-hangzhou",
    )
    monkeypatch.setattr(gateway, "_bucket", lambda _name: ReadOnlyBucket())

    result = gateway.get_bucket_configuration(bucket_name="managed-bucket")

    assert result == {
        "configuration": {
            "acl": "public_read",
            "storage_class": "IA",
            "encryption": "KMS",
            "versioning": True,
            "lifecycle": {
                "rules": [
                    {
                        "id": "archive",
                        "prefix": "logs/",
                        "status": "Enabled",
                        "expiration_days": 30,
                        "abort_multipart_upload_days": 7,
                        "storage_transitions": [{"days": 14, "storage_class": "IA"}],
                    }
                ]
            },
        },
        "request_id": "read-config-request",
    }


def test_oss_gateway_configuration_read_fails_closed_without_encryption(monkeypatch):
    from object_storage.providers.aliyun import AliyunOssGateway

    class UncertainBucket:
        def get_bucket_info(self):
            return SimpleNamespace(
                acl="private",
                storage_class="Standard",
                bucket_encryption_rule=None,
                versioning_status="Suspended",
            )

        def get_bucket_lifecycle(self):
            return SimpleNamespace(rules=[])

    gateway = AliyunOssGateway(
        access_key_id="unused",
        access_key_secret="unused",
        region="cn-hangzhou",
    )
    monkeypatch.setattr(gateway, "_bucket", lambda _name: UncertainBucket())

    with pytest.raises(ValueError, match="BUCKET_ENCRYPTION_STATE_UNKNOWN"):
        gateway.get_bucket_configuration(bucket_name="managed-bucket")


@pytest.mark.parametrize(
    "inspection",
    [
        {"object_count": 1},
        {"version_count": 1},
        {"delete_marker_count": 1},
        {"multipart_upload_count": 1},
    ],
)
def test_bucket_empty_check_rejects_all_retained_content(inspection):
    provider, _ram, _oss = _provider(inspection)

    result = provider.inspect_bucket_emptiness(SimpleNamespace(name="bucket"))

    assert result.is_empty is False


def test_policy_reconciliation_returns_only_safe_metadata():
    from object_storage.models import Bucket

    provider, ram, _oss = _provider()
    identity = SimpleNamespace(ram_user_name="hyperops-user")
    buckets = [
        SimpleNamespace(name="owned-a", state=Bucket.State.ACTIVE),
        SimpleNamespace(name="owned-b", state=Bucket.State.ACTIVE),
    ]

    result = provider.reconcile_object_policy(identity, buckets)

    resources = {
        resource
        for statement in ram.policy["Statement"]
        for resource in statement["Resource"]
    }
    assert resources == {
        "acs:oss:*:*:owned-a",
        "acs:oss:*:*:owned-a/*",
        "acs:oss:*:*:owned-b",
        "acs:oss:*:*:owned-b/*",
    }
    assert result.request_id == "ram-request-3"
    assert "must-not-leak" not in repr(result)

    empty_result = provider.reconcile_object_policy(identity, [])

    assert ram.detached_policy == "hyperops-user"
    assert empty_result.request_id == "ram-request-detach"


def test_empty_policy_detach_treats_missing_policy_as_idempotent_success():
    from object_storage.services.provider_errors import ObjectStorageProviderError

    provider, ram, _oss = _provider()
    ram.detach_policy_from_user = lambda _user_name: {
        "request_id": "ram-request-already-detached",
        "error_code": "NoSuchEntity",
    }

    result = provider.reconcile_object_policy(
        SimpleNamespace(ram_user_name="hyperops-user"),
        [],
    )

    assert result.request_id == "ram-request-already-detached"
    assert not isinstance(result, ObjectStorageProviderError)


def test_access_key_operations_return_sanitized_results():
    provider, ram, _oss = _provider()
    identity = SimpleNamespace(ram_user_name="user")
    key = SimpleNamespace(
        cloud_identity=identity,
        access_key_id="LTAIabcdefghijkl1234",
    )

    listed = provider.list_access_keys(identity)
    issued = provider.create_access_key(identity)
    activated = provider.activate_access_key(key)
    deactivated = provider.deactivate_access_key(key)
    deleted = provider.delete_access_key(key)

    assert listed.request_id == "ram-request-list"
    assert len(listed.items) == 1
    assert listed.items[0].last_four == "1234"
    assert issued.secret_access_key == "employee-secret"
    assert "employee-secret" not in repr(issued)
    assert activated.request_id == "ram-request-active"
    assert deactivated.request_id == "ram-request-inactive"
    assert deleted.request_id == "ram-request-delete"
    assert ram.updated_key == (
        "user",
        "LTAIabcdefghijkl1234",
        "Inactive",
    )
    assert "must-not-leak" not in repr(listed)


def test_personal_principal_delete_uses_exact_identity_marker():
    provider, ram, _oss = _provider()
    identity = SimpleNamespace(pk=42, ram_user_name="managed-user")

    result = provider.delete_personal_principal(identity)

    assert ram.deleted_user == (
        "managed-user",
        "hyperops:identity:42",
    )
    assert result.request_id == "ram-request-delete-user"


def test_bucket_configuration_requires_explicit_public_read_authorization():
    from object_storage.providers.base import BucketConfiguration
    from object_storage.services.provider_errors import ObjectStorageProviderError

    provider, _ram, oss = _provider()
    bucket = SimpleNamespace(
        name="managed-bucket",
        region="cn-hangzhou",
        cloud_marker="hyperops:bucket:42",
    )
    provider.create_owned_bucket(
        SimpleNamespace(
            name="managed-bucket",
            region="cn-hangzhou",
            cloud_marker="hyperops:bucket:42",
        )
    )
    configuration = BucketConfiguration(acl="public_read")

    with pytest.raises(
        ObjectStorageProviderError,
        match="PUBLIC_READ_REQUIRES_ADMIN_AUTHORIZATION",
    ):
        provider.update_bucket_configuration(bucket, configuration)

    result = provider.update_bucket_configuration(
        bucket,
        configuration,
        allow_public_read=True,
    )

    assert oss.updated_configuration == ("managed-bucket", configuration)
    assert result.request_id == "oss-request-update"

    provider.update_bucket_configuration(
        bucket,
        BucketConfiguration(acl="private"),
    )


def test_existing_bucket_storage_class_change_fails_before_cloud_mutation():
    from object_storage.providers.base import BucketConfiguration
    from object_storage.services.provider_errors import ObjectStorageProviderError

    provider, _ram, oss = _provider()
    bucket = SimpleNamespace(
        name="managed-bucket",
        region="cn-hangzhou",
        cloud_marker="hyperops:bucket:42",
    )
    provider.create_owned_bucket(
        bucket,
        BucketConfiguration(storage_class="IA"),
    )
    oss.updated_configuration = None

    with pytest.raises(
        ObjectStorageProviderError,
        match="BUCKET_STORAGE_CLASS_UPDATE_UNSUPPORTED",
    ):
        provider.update_bucket_configuration(
            bucket,
            BucketConfiguration(storage_class="Standard"),
            previous_configuration=BucketConfiguration(storage_class="IA"),
        )

    assert oss.updated_configuration is None


def test_bucket_configuration_failure_rolls_back_to_previous_configuration():
    from object_storage.providers.base import BucketConfiguration
    from object_storage.services.provider_errors import ObjectStorageProviderError

    provider, _ram, oss = _provider()
    bucket = SimpleNamespace(
        name="managed-bucket",
        region="cn-hangzhou",
        cloud_marker="hyperops:bucket:42",
    )
    provider.create_owned_bucket(bucket)
    desired = BucketConfiguration(
        acl="public_read",
        encryption="KMS",
        versioning=True,
        lifecycle={"rules": [{"id": "expire", "prefix": "", "expiration_days": 7}]},
    )
    previous = BucketConfiguration(
        acl="private",
        storage_class="Standard",
        encryption="AES256",
        versioning=False,
        lifecycle={},
    )
    calls = []

    def update(*, bucket_name, configuration):
        calls.append((bucket_name, configuration))
        if len(calls) == 1:
            raise ObjectStorageProviderError("PROVIDER_PERMISSION_DENIED")
        return {"request_id": "rollback-request"}

    oss.update_bucket_configuration = update

    with pytest.raises(ObjectStorageProviderError, match="PROVIDER_PERMISSION_DENIED"):
        provider.update_bucket_configuration(
            bucket,
            desired,
            previous_configuration=previous,
            allow_public_read=True,
        )

    assert calls == [(bucket.name, desired), (bucket.name, previous)]


def test_bucket_configuration_rollback_failure_reports_unknown_cloud_state():
    from object_storage.providers.base import BucketConfiguration
    from object_storage.services.provider_errors import ObjectStorageProviderError

    provider, _ram, oss = _provider()
    bucket = SimpleNamespace(
        name="managed-bucket",
        region="cn-hangzhou",
        cloud_marker="hyperops:bucket:42",
    )
    provider.create_owned_bucket(bucket)
    desired = BucketConfiguration(acl="public_read", versioning=True)
    previous = BucketConfiguration(acl="private", versioning=False)
    calls = []

    def fail(*, bucket_name, configuration):
        calls.append((bucket_name, configuration))
        raise ObjectStorageProviderError("PROVIDER_OPERATION_FAILED")

    oss.update_bucket_configuration = fail

    with pytest.raises(
        ObjectStorageProviderError,
        match="BUCKET_CONFIGURATION_ROLLBACK_FAILED",
    ) as captured:
        provider.update_bucket_configuration(
            bucket,
            desired,
            previous_configuration=previous,
            allow_public_read=True,
        )

    assert captured.value.retryable is False
    assert calls == [(bucket.name, desired), (bucket.name, previous)]


def test_oss_gateway_restores_complete_private_standard_configuration(monkeypatch):
    from object_storage.providers.aliyun import AliyunOssGateway
    from object_storage.providers.base import BucketConfiguration

    calls = []

    class FakeBucket:
        def put_bucket_acl(self, value):
            calls.append(("acl", value))
            return SimpleNamespace(request_id="acl-request")

        def put_bucket_storage_class(self, value):
            calls.append(("storage_class", value))

        def put_bucket_encryption(self, rule):
            calls.append(("encryption", rule.sse_algorithm))

        def put_bucket_versioning(self, config):
            calls.append(("versioning", config.status))

        def delete_bucket_lifecycle(self):
            calls.append(("lifecycle", "deleted"))

    gateway = AliyunOssGateway(
        access_key_id="management-ak",
        access_key_secret="management-sk",
        region="cn-hangzhou",
    )
    monkeypatch.setattr(gateway, "_bucket", lambda _name: FakeBucket())

    gateway.update_bucket_configuration(
        bucket_name="managed-bucket",
        configuration=BucketConfiguration(
            acl="private",
            storage_class="Standard",
            encryption="AES256",
            versioning=False,
            lifecycle={},
        ),
    )

    assert [name for name, _value in calls] == [
        "acl",
        "storage_class",
        "encryption",
        "versioning",
        "lifecycle",
    ]
    assert calls[1] == ("storage_class", "Standard")
    assert calls[2] == ("encryption", "AES256")
    assert calls[3] == ("versioning", "Suspended")
    assert calls[4] == ("lifecycle", "deleted")


def test_oss_gateway_persists_and_reconciles_exact_owner_marker(monkeypatch):
    from object_storage.providers.aliyun import AliyunOssGateway

    stored = {}

    class Bucket:
        def create_bucket(self, **kwargs):
            return SimpleNamespace(request_id="create-request")

        def put_bucket_encryption(self, rule):
            return None

        def put_bucket_tagging(self, tagging):
            stored.update(tagging.tag_set.tagging_rule)

        def get_bucket_tagging(self):
            return SimpleNamespace(tag_set=SimpleNamespace(tagging_rule=dict(stored)))

    gateway = AliyunOssGateway(
        access_key_id="management-ak",
        access_key_secret="management-secret",
        region="cn-hangzhou",
    )
    monkeypatch.setattr(gateway, "_bucket", lambda bucket_name: Bucket())

    gateway.create_bucket(
        bucket_name="managed-bucket",
        region="cn-hangzhou",
        acl="private",
        storage_class="Standard",
        server_side_encryption="AES256",
        marker="hyperops:bucket:42",
    )

    assert stored == {"hyperops-owner": "hyperops:bucket:42"}
    owned = gateway.find_bucket(
        bucket_name="managed-bucket", marker="hyperops:bucket:42"
    )
    mismatched = gateway.find_bucket(
        bucket_name="managed-bucket", marker="hyperops:bucket:other"
    )
    stored.clear()
    missing = gateway.find_bucket(
        bucket_name="managed-bucket", marker="hyperops:bucket:42"
    )

    assert owned["owned"] is True
    assert owned["marker"] == "hyperops:bucket:42"
    assert mismatched["owned"] is False
    assert missing["owned"] is False
    assert missing["marker"] == ""


def test_ram_gateway_detach_targets_only_hyperops_policy_and_is_idempotent(
    monkeypatch,
):
    from object_storage.providers.aliyun import AliyunRamGateway

    requests = []
    gateway = AliyunRamGateway(
        access_key_id="management-ak",
        access_key_secret="management-secret",
    )
    gateway._client = SimpleNamespace(
        detach_policy_from_user=lambda request: requests.append(request)
        or SimpleNamespace(body=SimpleNamespace(request_id="detach-request")),
    )
    monkeypatch.setattr(
        AliyunRamGateway,
        "models",
        SimpleNamespace(DetachPolicyFromUserRequest=lambda **kwargs: kwargs),
    )

    result = gateway.detach_policy_from_user("managed-user")

    assert result == {"request_id": "detach-request"}
    assert requests == [
        {
            "policy_name": "HyperOpsObjectAccess-" "1ea3b41bd0b57254",
            "policy_type": "Custom",
            "user_name": "managed-user",
        }
    ]

    class PolicyNotAttached(Exception):
        code = "PolicyNotAttached"
        request_id = "already-detached-request"

    gateway._client = SimpleNamespace(
        detach_policy_from_user=lambda _request: (_ for _ in ()).throw(
            PolicyNotAttached()
        ),
    )

    assert gateway.detach_policy_from_user("managed-user") == {
        "request_id": "already-detached-request",
        "error_code": "PolicyNotAttached",
    }


def test_ram_gateway_only_reuses_principal_with_exact_marker(monkeypatch):
    from object_storage.providers.aliyun import AliyunRamGateway
    from object_storage.services.provider_errors import ObjectStorageProviderError

    gateway = AliyunRamGateway(
        access_key_id="management-ak",
        access_key_secret="management-secret",
    )
    existing_user = SimpleNamespace(
        user_id="ram-user-id",
        user_name="managed-user",
        comments="hyperops:identity:42",
    )
    gateway._client = SimpleNamespace(
        get_user=lambda _request: SimpleNamespace(
            body=SimpleNamespace(user=existing_user, request_id="ram-find-request")
        )
    )
    monkeypatch.setattr(
        AliyunRamGateway,
        "models",
        SimpleNamespace(GetUserRequest=lambda **kwargs: kwargs),
    )

    result = gateway.find_or_create_user("managed-user", "hyperops:identity:42")

    assert result["created"] is False
    assert result["marker"] == "hyperops:identity:42"
    existing_user.comments = "someone-else"
    with pytest.raises(
        ObjectStorageProviderError,
        match="PRINCIPAL_OWNERSHIP_CONFLICT",
    ):
        gateway.find_or_create_user("managed-user", "hyperops:identity:42")


def test_ram_gateway_writes_marker_when_creating_principal(monkeypatch):
    from object_storage.providers.aliyun import AliyunRamGateway

    class MissingUser(Exception):
        code = "NoSuchEntity"

    created_requests = []
    gateway = AliyunRamGateway(
        access_key_id="management-ak",
        access_key_secret="management-secret",
    )
    gateway._client = SimpleNamespace(
        get_user=lambda _request: (_ for _ in ()).throw(MissingUser()),
        create_user=lambda request: created_requests.append(request)
        or SimpleNamespace(
            body=SimpleNamespace(
                user=SimpleNamespace(
                    user_id="new-user-id",
                    user_name="managed-user",
                    comments="hyperops:identity:42",
                ),
                request_id="ram-create-request",
            )
        ),
    )
    monkeypatch.setattr(
        AliyunRamGateway,
        "models",
        SimpleNamespace(
            GetUserRequest=lambda **kwargs: kwargs,
            CreateUserRequest=lambda **kwargs: kwargs,
        ),
    )

    result = gateway.find_or_create_user("managed-user", "hyperops:identity:42")

    assert created_requests[0]["comments"] == "hyperops:identity:42"
    assert result["marker"] == "hyperops:identity:42"


def test_ram_gateway_recovers_entity_already_exists_race_with_matching_marker(
    monkeypatch,
):
    from object_storage.providers.aliyun import AliyunRamGateway

    class EntityAlreadyExists(Exception):
        code = "EntityAlreadyExists"

    class NoSuchEntity(Exception):
        code = "NoSuchEntity"

    requests = []
    user = SimpleNamespace(
        user_id="raced-user-id",
        user_name="managed-user",
        comments="hyperops:identity:42",
    )
    gateway = AliyunRamGateway(
        access_key_id="management-ak",
        access_key_secret="management-secret",
    )
    get_call_count = 0

    def get_user(_request):
        nonlocal get_call_count
        get_call_count += 1
        if get_call_count == 1:
            raise NoSuchEntity()
        return SimpleNamespace(
            body=SimpleNamespace(
                user=user,
                request_id="ram-request-raced-get",
            )
        )

    gateway._client = SimpleNamespace(
        get_user=get_user,
        create_user=lambda request: requests.append(request)
        or (_ for _ in ()).throw(EntityAlreadyExists()),
    )
    monkeypatch.setattr(
        AliyunRamGateway,
        "models",
        SimpleNamespace(
            GetUserRequest=lambda **kwargs: kwargs,
            CreateUserRequest=lambda **kwargs: kwargs,
        ),
    )

    result = gateway.find_or_create_user("managed-user", "hyperops:identity:42")

    assert result["created"] is False
    assert result["marker"] == "hyperops:identity:42"
    assert result["request_id"] == "ram-request-raced-get"


def test_ram_gateway_entity_already_exists_with_foreign_marker_is_rejected(
    monkeypatch,
):
    from object_storage.providers.aliyun import AliyunRamGateway
    from object_storage.services.provider_errors import ObjectStorageProviderError

    class EntityAlreadyExist(Exception):
        code = "EntityAlreadyExist"

    class NoSuchEntity(Exception):
        code = "NoSuchEntity"

    foreign_user = SimpleNamespace(
        user_id="foreign-user-id",
        user_name="managed-user",
        comments="foreign-owner",
    )
    gateway = AliyunRamGateway(
        access_key_id="management-ak",
        access_key_secret="management-secret",
    )
    get_call_count = 0

    def get_user(_request):
        nonlocal get_call_count
        get_call_count += 1
        if get_call_count == 1:
            raise NoSuchEntity()
        return SimpleNamespace(
            body=SimpleNamespace(user=foreign_user, request_id="get")
        )

    gateway._client = SimpleNamespace(
        get_user=get_user,
        create_user=lambda _request: (_ for _ in ()).throw(EntityAlreadyExist()),
    )
    monkeypatch.setattr(
        AliyunRamGateway,
        "models",
        SimpleNamespace(
            GetUserRequest=lambda **kwargs: kwargs,
            CreateUserRequest=lambda **kwargs: kwargs,
        ),
    )

    with pytest.raises(
        ObjectStorageProviderError, match="PRINCIPAL_OWNERSHIP_CONFLICT"
    ):
        gateway.find_or_create_user("managed-user", "hyperops:identity:42")


def test_ram_gateway_delete_user_requires_exact_marker(monkeypatch):
    from object_storage.providers.aliyun import AliyunRamGateway
    from object_storage.services.provider_errors import ObjectStorageProviderError

    deleted = []
    user = SimpleNamespace(
        user_id="ram-user-id",
        user_name="managed-user",
        comments="hyperops:identity:42",
    )
    gateway = AliyunRamGateway(
        access_key_id="management-ak",
        access_key_secret="management-secret",
    )
    gateway._client = SimpleNamespace(
        get_user=lambda _request: SimpleNamespace(
            body=SimpleNamespace(user=user, request_id="find-user-request")
        ),
        delete_user=lambda request: deleted.append(request)
        or SimpleNamespace(body=SimpleNamespace(request_id="delete-user-request")),
    )
    monkeypatch.setattr(
        AliyunRamGateway,
        "models",
        SimpleNamespace(
            GetUserRequest=lambda **kwargs: kwargs,
            DeleteUserRequest=lambda **kwargs: kwargs,
        ),
    )

    result = gateway.delete_user("managed-user", "hyperops:identity:42")

    assert result == {"request_id": "delete-user-request"}
    assert deleted == [{"user_name": "managed-user"}]
    user.comments = "foreign-owner"
    with pytest.raises(
        ObjectStorageProviderError, match="PRINCIPAL_OWNERSHIP_CONFLICT"
    ):
        gateway.delete_user("managed-user", "hyperops:identity:42")
    assert deleted == [{"user_name": "managed-user"}]


def test_provider_errors_map_to_stable_domain_codes():
    from object_storage.services.provider_errors import map_provider_error

    raw_error = RuntimeError("AccessKeySecret=very-secret provider detail")
    raw_error.code = "BucketAlreadyExists"
    raw_error.request_id = "safe-request-id"

    mapped = map_provider_error(raw_error)

    assert mapped.error_code == "BUCKET_NAME_CONFLICT"
    assert mapped.request_id == "safe-request-id"
    assert str(mapped) == "BUCKET_NAME_CONFLICT"
    assert "very-secret" not in repr(mapped)
