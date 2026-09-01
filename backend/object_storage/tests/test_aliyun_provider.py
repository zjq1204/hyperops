from types import SimpleNamespace

import pytest


class FakeRamGateway:
    def __init__(self):
        self.policy = None

    def validate_identity(self):
        return {
            "account_id": "123456789",
            "can_manage_ram": True,
            "request_id": "ram-request-1",
            "access_key_secret": "must-not-leak",
        }

    def find_or_create_user(self, user_name, marker):
        return {
            "user_id": "ram-user-id",
            "user_name": user_name,
            "created": True,
            "request_id": "ram-request-2",
        }

    def apply_policy(self, user_name, policy):
        self.policy = policy
        return {"request_id": "ram-request-3"}

    def list_access_keys(self, user_name):
        return [
            {
                "access_key_id": "LTAIabcdefghijkl1234",
                "status": "Active",
                "created_at": "2026-08-31T00:00:00Z",
                "secret_access_key": "must-not-leak",
            }
        ]

    def create_access_key(self, user_name):
        return {
            "access_key_id": "LTAIabcdefghijkl5678",
            "secret_access_key": "employee-secret",
            "request_id": "ram-request-4",
        }

    def update_access_key(self, user_name, access_key_id, status):
        return {"request_id": "ram-request-5"}

    def delete_access_key(self, user_name, access_key_id):
        return {"request_id": "ram-request-6"}


class FakeOssGateway:
    def __init__(self, inspection=None):
        self.created = None
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
        return {"created": True, "request_id": "oss-request-create"}

    def find_bucket(self, *, bucket_name, marker):
        return self.created is not None and self.created.get("marker") == marker

    def inspect_bucket(self, bucket_name):
        return dict(self.inspection)

    def delete_bucket(self, bucket_name):
        return {"request_id": "oss-request-delete"}


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
    }
    assert "secret" not in str(payload).lower()


def test_validate_management_identity_never_falls_back_to_configured_account_id():
    provider, ram, _oss = _provider()
    ram.validate_identity = lambda: {
        "account_id": "",
        "can_manage_ram": True,
        "request_id": "ram-request-missing-account",
    }

    capabilities = provider.validate_management_identity(
        SimpleNamespace(cloud_account_id="locally-configured-account")
    )

    assert capabilities.account_id == ""


def test_ram_gateway_never_echoes_a_locally_configured_account_id(monkeypatch):
    import inspect

    from object_storage.providers.aliyun import AliyunRamGateway

    assert "account_id" not in inspect.signature(AliyunRamGateway).parameters
    gateway = AliyunRamGateway(
        access_key_id="management-ak",
        access_key_secret="management-sk",
    )
    gateway._client = SimpleNamespace(
        list_users=lambda _request: SimpleNamespace(
            body=SimpleNamespace(request_id="ram-request-no-account")
        )
    )
    monkeypatch.setattr(
        AliyunRamGateway,
        "models",
        SimpleNamespace(ListUsersRequest=lambda **kwargs: kwargs),
    )

    result = gateway.validate_identity()

    assert result["account_id"] == ""


def test_ram_gateway_uses_account_id_returned_by_cloud(monkeypatch):
    from object_storage.providers.aliyun import AliyunRamGateway

    gateway = AliyunRamGateway(
        access_key_id="management-ak",
        access_key_secret="management-sk",
    )
    gateway._client = SimpleNamespace(
        list_users=lambda _request: SimpleNamespace(
            body=SimpleNamespace(
                account_id="cloud-account-123",
                request_id="ram-request-with-account",
            )
        )
    )
    monkeypatch.setattr(
        AliyunRamGateway,
        "models",
        SimpleNamespace(ListUsersRequest=lambda **kwargs: kwargs),
    )

    result = gateway.validate_identity()

    assert result["account_id"] == "cloud-account-123"


def test_create_bucket_uses_fixed_region_and_platform_defaults():
    provider, _ram, oss = _provider()
    bucket = SimpleNamespace(
        name="tenant-user-project-abcd1234",
        region="cn-hangzhou",
        cloud_marker="hyperops:bucket:42",
    )

    provider.create_owned_bucket(bucket)

    assert oss.created == {
        "bucket_name": bucket.name,
        "region": "cn-hangzhou",
        "acl": "private",
        "storage_class": "Standard",
        "server_side_encryption": "AES256",
        "marker": "hyperops:bucket:42",
    }


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
    assert gateway.find_bucket(
        bucket_name="managed-bucket", marker="hyperops:bucket:42"
    )
    with pytest.raises(Exception, match="BUCKET_OWNERSHIP_MISMATCH"):
        gateway.find_bucket(
            bucket_name="managed-bucket", marker="hyperops:bucket:other"
        )


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


def test_object_policy_contains_only_owned_bucket_arns():
    provider, ram, _oss = _provider()
    identity = SimpleNamespace(ram_user_name="hyperops-user")
    buckets = [
        SimpleNamespace(name="owned-a"),
        SimpleNamespace(name="owned-b"),
    ]

    provider.reconcile_object_policy(identity, buckets)

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


def test_access_key_list_never_returns_secret_material():
    provider, _ram, _oss = _provider()

    keys = provider.list_access_keys(SimpleNamespace(ram_user_name="user"))

    assert len(keys) == 1
    assert keys[0].last_four == "1234"
    assert "must-not-leak" not in repr(keys)


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
