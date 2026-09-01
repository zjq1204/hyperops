from dataclasses import replace
import hashlib
import json

from object_storage.crypto import decrypt_secret
from object_storage.providers.base import (
    AccessKeyMetadata,
    AccessKeyMutation,
    BucketConfiguration,
    BucketConfigurationMutation,
    BucketEmptiness,
    BucketMutation,
    BucketOwnership,
    IssuedAccessKey,
    KeyListResult,
    ManagementCapabilities,
    PersonalPrincipal,
    PolicyMutation,
)
from object_storage.services.provider_errors import (
    ObjectStorageProviderError,
    map_provider_error,
)


def _fingerprint(access_key_id):
    return hashlib.sha256(access_key_id.encode("utf-8")).hexdigest()


def _lifecycle_rule(models, item):
    if not isinstance(item, dict) or not str(item.get("id") or "").strip():
        raise ValueError("BUCKET_LIFECYCLE_RULE_INVALID")
    expiration_days = item.get("expiration_days")
    expiration = (
        models.LifecycleExpiration(days=int(expiration_days))
        if expiration_days is not None
        else None
    )
    abort_days = item.get("abort_multipart_upload_days")
    abort = (
        models.AbortMultipartUpload(days=int(abort_days))
        if abort_days is not None
        else None
    )
    transitions = []
    for transition in item.get("storage_transitions", []):
        if not isinstance(transition, dict):
            raise ValueError("BUCKET_LIFECYCLE_TRANSITION_INVALID")
        transitions.append(
            models.StorageTransition(
                days=int(transition["days"]),
                storage_class=str(transition["storage_class"]),
            )
        )
    return models.LifecycleRule(
        id=str(item["id"]),
        prefix=str(item.get("prefix") or ""),
        status=str(item.get("status") or "Enabled"),
        expiration=expiration,
        abort_multipart_upload=abort,
        storage_transitions=transitions or None,
    )


def _lifecycle_configuration(models, snapshot):
    if isinstance(snapshot, dict):
        rows = snapshot.get("rules", [])
    else:
        rows = snapshot
    if not isinstance(rows, list):
        raise ValueError("BUCKET_LIFECYCLE_INVALID")
    return models.BucketLifecycle([_lifecycle_rule(models, item) for item in rows])


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
        ram_request_ids = ram["request_ids"]
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
            marker=str(result["marker"]),
            request_id=str(result.get("request_id") or ""),
        )

    def delete_personal_principal(self, identity):
        result = self._call(
            self.ram_gateway.delete_user,
            identity.ram_user_name,
            f"hyperops:identity:{identity.pk}",
        )
        return AccessKeyMutation(request_id=str(result.get("request_id") or ""))

    def create_owned_bucket(self, bucket, configuration=None):
        configuration = configuration or BucketConfiguration.from_snapshot(
            getattr(bucket, "config_snapshot", {}).get("bucket_configuration", {})
        )
        if configuration.acl != "private":
            raise ObjectStorageProviderError("PUBLIC_READ_REQUIRES_ADMIN_AUTHORIZATION")
        result = self._call(
            self.oss_gateway.create_bucket,
            bucket_name=bucket.name,
            region=bucket.region,
            acl=configuration.acl,
            storage_class=configuration.storage_class,
            server_side_encryption=configuration.encryption,
            marker=bucket.cloud_marker,
        )
        self.update_bucket_configuration(
            bucket,
            replace(configuration, storage_class="Standard"),
        )
        return BucketMutation(
            created=bool(result.get("created")),
            request_id=str(result.get("request_id") or ""),
        )

    def find_owned_bucket(self, bucket):
        result = self._call(
            self.oss_gateway.find_bucket,
            bucket_name=bucket.name,
            marker=bucket.cloud_marker,
        )
        marker = str(result["marker"])
        return BucketOwnership(
            exists=bool(result["exists"]),
            owned=bool(result["owned"] and marker and marker == bucket.cloud_marker),
            marker=marker,
            request_id=str(result["request_id"]),
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
        ownership = self.find_owned_bucket(bucket)
        if not ownership.exists:
            return BucketMutation(request_id=ownership.request_id)
        if not ownership.owned:
            raise ObjectStorageProviderError("BUCKET_OWNERSHIP_CONFLICT")
        result = self._call(self.oss_gateway.delete_bucket, bucket.name)
        return BucketMutation(request_id=str(result.get("request_id") or ""))

    def reconcile_object_policy(self, identity, buckets):
        from object_storage.services.policy import build_object_policy

        policy = build_object_policy(buckets, owner=getattr(identity, "user", None))
        if not policy["Statement"]:
            result = self._call(
                self.ram_gateway.detach_policy_from_user,
                identity.ram_user_name,
            )
            if result.get("error_code") in {
                "NoSuchEntity",
                "EntityNotFound",
                "EntityNotAttached",
                "PolicyNotAttached",
            }:
                return PolicyMutation(request_id=str(result.get("request_id") or ""))
            return PolicyMutation(request_id=str(result["request_id"]))
        result = self._call(
            self.ram_gateway.apply_policy,
            identity.ram_user_name,
            policy,
        )
        return PolicyMutation(request_id=str(result.get("request_id") or ""))

    def list_access_keys(self, identity):
        result = self._call(
            self.ram_gateway.list_access_keys,
            identity.ram_user_name,
        )
        items = tuple(
            AccessKeyMetadata(
                access_key_id=str(row.get("access_key_id") or ""),
                fingerprint=_fingerprint(str(row.get("access_key_id") or "")),
                last_four=str(row.get("access_key_id") or "")[-4:],
                status=str(row.get("status") or "unknown").lower(),
                created_at=str(row.get("created_at") or ""),
            )
            for row in result["items"]
        )
        return KeyListResult(
            items=items,
            request_id=str(result["request_id"]),
        )

    def create_access_key(self, identity):
        result = self._call(self.ram_gateway.create_access_key, identity.ram_user_name)
        return IssuedAccessKey(
            access_key_id=str(result["access_key_id"]),
            secret_access_key=str(result["secret_access_key"]),
            request_id=str(result.get("request_id") or ""),
        )

    def _update_access_key_status(self, key, status):
        result = self._call(
            self.ram_gateway.update_access_key,
            key.cloud_identity.ram_user_name,
            key.access_key_id,
            status,
        )
        return AccessKeyMutation(request_id=str(result.get("request_id") or ""))

    def activate_access_key(self, key):
        return self._update_access_key_status(key, "Active")

    def deactivate_access_key(self, key):
        return self._update_access_key_status(key, "Inactive")

    def delete_access_key(self, key):
        result = self._call(
            self.ram_gateway.delete_access_key,
            key.cloud_identity.ram_user_name,
            key.access_key_id,
        )
        return AccessKeyMutation(request_id=str(result.get("request_id") or ""))

    def update_bucket_configuration(
        self,
        bucket,
        configuration,
        *,
        previous_configuration=None,
        allow_public_read=False,
    ):
        ownership = self.find_owned_bucket(bucket)
        if not ownership.exists:
            raise ObjectStorageProviderError("NO_SUCH_BUCKET")
        if not ownership.owned:
            raise ObjectStorageProviderError("BUCKET_OWNERSHIP_CONFLICT")
        if configuration.acl == "public_read" and not allow_public_read:
            raise ObjectStorageProviderError("PUBLIC_READ_REQUIRES_ADMIN_AUTHORIZATION")
        if (
            previous_configuration is not None
            and configuration.storage_class != previous_configuration.storage_class
        ):
            # OSS Python SDK supports Bucket storage class at creation only.
            raise ObjectStorageProviderError("BUCKET_STORAGE_CLASS_UPDATE_UNSUPPORTED")
        try:
            result = self._call(
                self.oss_gateway.update_bucket_configuration,
                bucket_name=bucket.name,
                configuration=configuration,
            )
        except Exception as update_error:
            if previous_configuration is None:
                raise
            try:
                self._call(
                    self.oss_gateway.update_bucket_configuration,
                    bucket_name=bucket.name,
                    configuration=previous_configuration,
                )
            except Exception as rollback_error:
                raise ObjectStorageProviderError(
                    "BUCKET_CONFIGURATION_ROLLBACK_FAILED",
                    request_id=str(getattr(rollback_error, "request_id", "") or ""),
                ) from rollback_error
            raise update_error
        return BucketConfigurationMutation(
            request_id=str(result.get("request_id") or "")
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
        except Exception as exc:
            if str(getattr(exc, "code", "")) != "NoSuchEntity":
                raise
        else:
            return self._principal_from_response(response, user_name, marker, False)

        try:
            response = self.client.create_user(
                self.models.CreateUserRequest(
                    user_name=user_name,
                    display_name=user_name,
                    comments=marker,
                )
            )
        except Exception as exc:
            if str(getattr(exc, "code", "")) not in {
                "EntityAlreadyExists",
                "EntityAlreadyExist",
                "EntityAlreadyExists.User",
            }:
                raise
            response = self.client.get_user(
                self.models.GetUserRequest(user_name=user_name)
            )
            return self._principal_from_response(response, user_name, marker, False)
        return self._principal_from_response(response, user_name, marker, True)

    @staticmethod
    def _principal_from_response(response, user_name, marker, created):
        user = response.body.user
        existing_marker = str(getattr(user, "comments", "") or "")
        if existing_marker != marker:
            raise ObjectStorageProviderError("PRINCIPAL_OWNERSHIP_CONFLICT")
        return {
            "user_id": str(user.user_id or ""),
            "user_name": str(user.user_name or user_name),
            "marker": existing_marker,
            "created": created,
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

    def detach_policy_from_user(self, user_name):
        policy_name = _policy_name(user_name)
        try:
            response = self.client.detach_policy_from_user(
                self.models.DetachPolicyFromUserRequest(
                    policy_name=policy_name,
                    policy_type="Custom",
                    user_name=user_name,
                )
            )
        except Exception as exc:
            if str(getattr(exc, "code", "")) in {
                "NoSuchEntity",
                "EntityNotFound",
                "EntityNotAttached",
                "PolicyNotAttached",
            }:
                return {
                    "request_id": str(getattr(exc, "request_id", "") or ""),
                    "error_code": str(getattr(exc, "code", "")),
                }
            raise
        return {"request_id": _request_id(response)}

    def list_access_keys(self, user_name):
        response = self.client.list_access_keys(
            self.models.ListAccessKeysRequest(user_name=user_name)
        )
        container = getattr(response.body, "access_keys", None)
        rows = getattr(container, "access_key", None) or []
        return {
            "items": [
                {
                    "access_key_id": str(row.access_key_id or ""),
                    "status": str(row.status or ""),
                    "created_at": str(row.create_date or ""),
                }
                for row in rows
            ],
            "request_id": _request_id(response),
        }

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

    def delete_user(self, user_name, marker):
        try:
            response = self.client.get_user(
                self.models.GetUserRequest(user_name=user_name)
            )
        except Exception as exc:
            if str(getattr(exc, "code", "")) == "NoSuchEntity":
                return {"request_id": str(getattr(exc, "request_id", "") or "")}
            raise
        user = response.body.user
        if str(getattr(user, "comments", "") or "") != marker:
            raise ObjectStorageProviderError("PRINCIPAL_OWNERSHIP_CONFLICT")
        try:
            deleted = self.client.delete_user(
                self.models.DeleteUserRequest(user_name=user_name)
            )
        except Exception as exc:
            if str(getattr(exc, "code", "")) == "NoSuchEntity":
                return {"request_id": str(getattr(exc, "request_id", "") or "")}
            raise
        return {"request_id": _request_id(deleted)}


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
        permissions = {
            "private": oss2.BUCKET_ACL_PRIVATE,
            "public_read": oss2.BUCKET_ACL_PUBLIC_READ,
        }
        result = bucket.create_bucket(
            permission=permissions[acl],
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
            response = bucket.get_bucket_tagging()
            tags = response.tag_set.tagging_rule
        except Exception as exc:
            # A missing bucket is a negative reconciliation result; all other
            # provider failures retain their mapped error semantics.
            if str(getattr(exc, "code", "")) == "NoSuchBucket":
                return {
                    "exists": False,
                    "owned": False,
                    "marker": "",
                    "request_id": str(getattr(exc, "request_id", "") or ""),
                }
            raise
        actual_marker = str(tags.get("hyperops-owner") or "")
        return {
            "exists": True,
            "owned": bool(actual_marker) and actual_marker == marker,
            "marker": actual_marker,
            "request_id": str(getattr(response, "request_id", "") or ""),
        }

    def delete_bucket(self, bucket_name):
        result = self._bucket(bucket_name).delete_bucket()
        return {"request_id": str(getattr(result, "request_id", "") or "")}

    def update_bucket_configuration(self, *, bucket_name, configuration):
        import oss2

        permissions = {
            "private": oss2.BUCKET_ACL_PRIVATE,
            "public_read": oss2.BUCKET_ACL_PUBLIC_READ,
        }
        bucket = self._bucket(bucket_name)
        result = bucket.put_bucket_acl(permissions[configuration.acl])
        put_storage_class = getattr(bucket, "put_bucket_storage_class", None)
        if put_storage_class is not None:
            put_storage_class(configuration.storage_class)
        elif configuration.storage_class != "Standard":
            if put_storage_class is None:
                raise ValueError("BUCKET_STORAGE_CLASS_UNSUPPORTED")
        if configuration.encryption:
            bucket.put_bucket_encryption(
                oss2.models.ServerSideEncryptionRule(configuration.encryption)
            )
        put_versioning = getattr(bucket, "put_bucket_versioning", None)
        if put_versioning is not None:
            put_versioning(
                oss2.models.BucketVersioningConfig(
                    "Enabled" if configuration.versioning else "Suspended"
                )
            )
        if configuration.lifecycle:
            put_lifecycle = getattr(bucket, "put_bucket_lifecycle", None)
            if put_lifecycle is None:
                raise ValueError("BUCKET_LIFECYCLE_UNSUPPORTED")
            put_lifecycle(
                _lifecycle_configuration(oss2.models, configuration.lifecycle)
            )
        else:
            delete_lifecycle = getattr(bucket, "delete_bucket_lifecycle", None)
            if delete_lifecycle is not None:
                delete_lifecycle()
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
