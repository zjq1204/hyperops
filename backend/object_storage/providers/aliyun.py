import hashlib
import json

from object_storage.crypto import decrypt_secret
from object_storage.providers.base import (
    AccessKeyMetadata,
    BucketEmptiness,
    BucketMutation,
    IssuedAccessKey,
    ManagementCapabilities,
    PersonalPrincipal,
)
from object_storage.services.provider_errors import (
    ObjectStorageProviderError,
    map_provider_error,
)


def _fingerprint(access_key_id):
    return hashlib.sha256(access_key_id.encode("utf-8")).hexdigest()


class AliyunObjectStorageProvider:
    def __init__(self, *, ram_gateway, oss_gateway):
        self.ram_gateway = ram_gateway
        self.oss_gateway = oss_gateway

    def _call(self, operation, *args, **kwargs):
        try:
            return operation(*args, **kwargs)
        except Exception as exc:
            raise map_provider_error(exc) from exc

    def validate_management_identity(self, pool):
        ram = self._call(self.ram_gateway.validate_identity)
        account_id = str(ram.get("account_id") or "")
        if not account_id:
            raise ObjectStorageProviderError("CLOUD_ACCOUNT_UNVERIFIED")
        oss = self._call(self.oss_gateway.validate_identity)
        ram_request_ids = ram.get("request_ids") or (
            (ram.get("request_id"),) if ram.get("request_id") else ()
        )
        request_ids = tuple(
            str(value) for value in (*ram_request_ids, oss.get("request_id")) if value
        )
        return ManagementCapabilities(
            account_id=account_id,
            can_manage_ram=bool(ram.get("can_manage_ram")),
            can_manage_oss=bool(oss.get("can_manage_oss")),
            request_ids=request_ids,
        )

    def find_or_create_personal_principal(self, identity):
        result = self._call(
            self.ram_gateway.find_or_create_user,
            identity.ram_user_name,
            f"hyperops:identity:{identity.pk}",
        )
        return PersonalPrincipal(
            user_id=str(result.get("user_id") or ""),
            user_name=str(result.get("user_name") or identity.ram_user_name),
            created=bool(result.get("created")),
            request_id=str(result.get("request_id") or ""),
        )

    def create_owned_bucket(self, bucket):
        result = self._call(
            self.oss_gateway.create_bucket,
            bucket_name=bucket.name,
            region=bucket.region,
            acl="private",
            storage_class="Standard",
            server_side_encryption="AES256",
            marker=bucket.cloud_marker,
        )
        return BucketMutation(
            created=bool(result.get("created")),
            request_id=str(result.get("request_id") or ""),
        )

    def find_owned_bucket(self, bucket):
        return self._call(
            self.oss_gateway.find_bucket,
            bucket_name=bucket.name,
            marker=bucket.cloud_marker,
        )

    def inspect_bucket_emptiness(self, bucket):
        result = self._call(self.oss_gateway.inspect_bucket, bucket.name)
        counts = {
            name: int(result.get(name) or 0)
            for name in (
                "object_count",
                "version_count",
                "delete_marker_count",
                "multipart_upload_count",
            )
        }
        return BucketEmptiness(
            is_empty=not any(counts.values()),
            request_id=str(result.get("request_id") or ""),
            **counts,
        )

    def delete_owned_bucket(self, bucket):
        result = self._call(self.oss_gateway.delete_bucket, bucket.name)
        return BucketMutation(request_id=str(result.get("request_id") or ""))

    def reconcile_object_policy(self, identity, buckets):
        from object_storage.services.policy import build_object_policy

        policy = build_object_policy(buckets)
        return self._call(
            self.ram_gateway.apply_policy,
            identity.ram_user_name,
            policy,
        )

    def list_access_keys(self, identity):
        rows = self._call(self.ram_gateway.list_access_keys, identity.ram_user_name)
        return tuple(
            AccessKeyMetadata(
                access_key_id=str(row.get("access_key_id") or ""),
                fingerprint=_fingerprint(str(row.get("access_key_id") or "")),
                last_four=str(row.get("access_key_id") or "")[-4:],
                status=str(row.get("status") or "unknown").lower(),
                created_at=str(row.get("created_at") or ""),
            )
            for row in rows
        )

    def create_access_key(self, identity):
        result = self._call(self.ram_gateway.create_access_key, identity.ram_user_name)
        return IssuedAccessKey(
            access_key_id=str(result["access_key_id"]),
            secret_access_key=str(result["secret_access_key"]),
            request_id=str(result.get("request_id") or ""),
        )

    def deactivate_access_key(self, key):
        return self._call(
            self.ram_gateway.update_access_key,
            key.cloud_identity.ram_user_name,
            key.access_key_id,
            "Inactive",
        )

    def delete_access_key(self, key):
        return self._call(
            self.ram_gateway.delete_access_key,
            key.cloud_identity.ram_user_name,
            key.access_key_id,
        )


def _request_id(response):
    body = getattr(response, "body", None)
    return str(getattr(body, "request_id", "") or "")


def _response_value(body, *names):
    for name in names:
        if isinstance(body, dict):
            value = body.get(name)
        else:
            value = getattr(body, name, None)
        if value:
            return str(value)
    return ""


def _policy_name(user_name):
    digest = hashlib.sha256(user_name.encode("utf-8")).hexdigest()[:16]
    return f"HyperOpsObjectAccess-{digest}"


class AliyunRamGateway:
    def __init__(self, *, access_key_id, access_key_secret):
        self.access_key_id = access_key_id
        self.access_key_secret = access_key_secret

    def validate_identity(self):
        from alibabacloud_tea_openapi import models as open_api_models
        from alibabacloud_tea_util import models as util_models

        sts_response = self.sts_client.call_api(
            open_api_models.Params(
                action="GetCallerIdentity",
                version="2015-04-01",
                protocol="HTTPS",
                pathname="/",
                method="POST",
                auth_type="AK",
                style="RPC",
                req_body_type="json",
                body_type="json",
            ),
            open_api_models.OpenApiRequest(),
            util_models.RuntimeOptions(
                connect_timeout=10000,
                read_timeout=10000,
            ),
        )
        sts_body = (
            sts_response.get("body", {})
            if isinstance(sts_response, dict)
            else getattr(sts_response, "body", None)
        )
        account_id = _response_value(sts_body, "AccountId", "account_id")
        sts_request_id = _response_value(sts_body, "RequestId", "request_id")
        if not account_id:
            raise ObjectStorageProviderError(
                "CLOUD_ACCOUNT_UNVERIFIED",
                request_id=sts_request_id,
            )

        ram_response = self.client.list_users(self.models.ListUsersRequest(max_items=1))
        return {
            "account_id": account_id,
            "can_manage_ram": True,
            "request_ids": tuple(
                value for value in (sts_request_id, _request_id(ram_response)) if value
            ),
        }

    @property
    def sts_client(self):
        if not hasattr(self, "_sts_client"):
            from alibabacloud_tea_openapi.client import Client
            from alibabacloud_tea_openapi.models import Config

            self._sts_client = Client(
                Config(
                    access_key_id=self.access_key_id,
                    access_key_secret=self.access_key_secret,
                    endpoint="sts.aliyuncs.com",
                    connect_timeout=10000,
                    read_timeout=10000,
                )
            )
        return self._sts_client

    @property
    def models(self):
        from alibabacloud_ram20150501 import models

        return models

    @property
    def client(self):
        if not hasattr(self, "_client"):
            from alibabacloud_ram20150501.client import Client
            from alibabacloud_tea_openapi.models import Config

            self._client = Client(
                Config(
                    access_key_id=self.access_key_id,
                    access_key_secret=self.access_key_secret,
                    endpoint="ram.aliyuncs.com",
                    connect_timeout=10000,
                    read_timeout=10000,
                )
            )
        return self._client

    def find_or_create_user(self, user_name, marker):
        try:
            response = self.client.get_user(
                self.models.GetUserRequest(user_name=user_name)
            )
            user = response.body.user
            return {
                "user_id": str(user.user_id or ""),
                "user_name": str(user.user_name or user_name),
                "created": False,
                "request_id": _request_id(response),
            }
        except Exception as exc:
            if str(getattr(exc, "code", "")) != "NoSuchEntity":
                raise
        response = self.client.create_user(
            self.models.CreateUserRequest(
                user_name=user_name,
                display_name=user_name,
                comments=marker,
            )
        )
        user = response.body.user
        return {
            "user_id": str(user.user_id or ""),
            "user_name": str(user.user_name or user_name),
            "created": True,
            "request_id": _request_id(response),
        }

    def apply_policy(self, user_name, policy):
        policy_name = _policy_name(user_name)
        document = json.dumps(policy, sort_keys=True, separators=(",", ":"))
        try:
            self.client.get_policy(
                self.models.GetPolicyRequest(
                    policy_name=policy_name,
                    policy_type="Custom",
                )
            )
        except Exception as exc:
            if str(getattr(exc, "code", "")) != "NoSuchEntity":
                raise
            self.client.create_policy(
                self.models.CreatePolicyRequest(
                    policy_name=policy_name,
                    description="HyperOps managed object access",
                    policy_document=document,
                )
            )
        else:
            self.client.create_policy_version(
                self.models.CreatePolicyVersionRequest(
                    policy_name=policy_name,
                    policy_document=document,
                    rotate_strategy="DeleteOldestNonDefaultVersionWhenLimitExceeded",
                    set_as_default=True,
                )
            )
        response = self.client.attach_policy_to_user(
            self.models.AttachPolicyToUserRequest(
                policy_name=policy_name,
                policy_type="Custom",
                user_name=user_name,
            )
        )
        return {"request_id": _request_id(response)}

    def list_access_keys(self, user_name):
        response = self.client.list_access_keys(
            self.models.ListAccessKeysRequest(user_name=user_name)
        )
        container = getattr(response.body, "access_keys", None)
        rows = getattr(container, "access_key", None) or []
        return [
            {
                "access_key_id": str(row.access_key_id or ""),
                "status": str(row.status or ""),
                "created_at": str(row.create_date or ""),
            }
            for row in rows
        ]

    def create_access_key(self, user_name):
        response = self.client.create_access_key(
            self.models.CreateAccessKeyRequest(user_name=user_name)
        )
        key = response.body.access_key
        return {
            "access_key_id": str(key.access_key_id),
            "secret_access_key": str(key.access_key_secret),
            "request_id": _request_id(response),
        }

    def update_access_key(self, user_name, access_key_id, status):
        response = self.client.update_access_key(
            self.models.UpdateAccessKeyRequest(
                user_name=user_name,
                user_access_key_id=access_key_id,
                status=status,
            )
        )
        return {"request_id": _request_id(response)}

    def delete_access_key(self, user_name, access_key_id):
        response = self.client.delete_access_key(
            self.models.DeleteAccessKeyRequest(
                user_name=user_name,
                user_access_key_id=access_key_id,
            )
        )
        return {"request_id": _request_id(response)}


class AliyunOssGateway:
    def __init__(self, *, access_key_id, access_key_secret, region):
        self.access_key_id = access_key_id
        self.access_key_secret = access_key_secret
        self.region = region

    def validate_identity(self):
        import oss2

        result = oss2.Service(
            self.auth, self.endpoint, connect_timeout=10
        ).list_buckets(max_keys=1)
        return {
            "can_manage_oss": True,
            "request_id": str(getattr(result, "request_id", "") or ""),
        }

    @property
    def endpoint(self):
        return f"https://oss-{self.region}.aliyuncs.com"

    @property
    def auth(self):
        if not hasattr(self, "_auth"):
            import oss2

            self._auth = oss2.Auth(self.access_key_id, self.access_key_secret)
        return self._auth

    def _bucket(self, bucket_name):
        import oss2

        return oss2.Bucket(self.auth, self.endpoint, bucket_name, connect_timeout=10)

    def create_bucket(
        self,
        *,
        bucket_name,
        region,
        acl,
        storage_class,
        server_side_encryption,
        marker,
    ):
        import oss2

        if region != self.region:
            raise ValueError("Configured OSS region mismatch")
        bucket = self._bucket(bucket_name)
        result = bucket.create_bucket(
            permission=oss2.BUCKET_ACL_PRIVATE,
            input=oss2.models.BucketCreateConfig(storage_class),
        )
        bucket.put_bucket_encryption(
            oss2.models.ServerSideEncryptionRule(server_side_encryption)
        )
        if marker:
            rules = oss2.models.TaggingRule()
            rules.add("hyperops-owner", marker)
            bucket.put_bucket_tagging(oss2.models.Tagging(rules))
        return {
            "created": True,
            "request_id": str(getattr(result, "request_id", "") or ""),
        }

    def inspect_bucket(self, bucket_name):
        bucket = self._bucket(bucket_name)
        objects = bucket.list_objects_v2(max_keys=1)
        versions = bucket.list_object_versions(max_keys=1)
        uploads = bucket.list_multipart_uploads(max_uploads=1)
        return {
            "object_count": len(getattr(objects, "object_list", None) or []),
            "version_count": len(getattr(versions, "version_list", None) or []),
            "delete_marker_count": len(
                getattr(versions, "delete_marker_list", None) or []
            ),
            "multipart_upload_count": len(getattr(uploads, "upload_list", None) or []),
            "request_id": str(getattr(objects, "request_id", "") or ""),
        }

    def find_bucket(self, *, bucket_name, marker):
        bucket = self._bucket(bucket_name)
        try:
            tags = bucket.get_bucket_tagging().tag_set.tagging_rule
        except Exception as exc:
            # A missing bucket is a negative reconciliation result; all other
            # provider failures retain their mapped error semantics.
            if str(getattr(exc, "code", "")) == "NoSuchBucket":
                return False
            raise
        if str(tags.get("hyperops-owner") or "") != marker:
            raise ObjectStorageProviderError("BUCKET_OWNERSHIP_MISMATCH")
        return True

    def delete_bucket(self, bucket_name):
        result = self._bucket(bucket_name).delete_bucket()
        return {"request_id": str(getattr(result, "request_id", "") or "")}


def build_aliyun_provider(pool):
    access_key_id = decrypt_secret(pool.management_access_key_encrypted)
    access_key_secret = decrypt_secret(pool.management_secret_key_encrypted)
    return AliyunObjectStorageProvider(
        ram_gateway=AliyunRamGateway(
            access_key_id=access_key_id,
            access_key_secret=access_key_secret,
        ),
        oss_gateway=AliyunOssGateway(
            access_key_id=access_key_id,
            access_key_secret=access_key_secret,
            region=pool.region,
        ),
    )
