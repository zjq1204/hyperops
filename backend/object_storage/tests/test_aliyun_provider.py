from types import SimpleNamespace

import pytest


class FakeRamGateway:
    def __init__(self):
        self.policy = None
        self.updated_key = None

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

    assert ram.policy == {"Version": "1", "Statement": []}
    assert empty_result.request_id == "ram-request-3"


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


def test_bucket_configuration_requires_explicit_public_read_authorization():
    from object_storage.providers.base import BucketConfiguration
    from object_storage.services.provider_errors import ObjectStorageProviderError

    provider, _ram, oss = _provider()
    bucket = SimpleNamespace(name="managed-bucket", region="cn-hangzhou")
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
