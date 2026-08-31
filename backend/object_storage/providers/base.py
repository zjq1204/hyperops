from dataclasses import asdict, dataclass
from typing import Protocol


@dataclass(frozen=True)
class ManagementCapabilities:
    account_id: str
    can_manage_ram: bool
    can_manage_oss: bool
    request_ids: tuple[str, ...] = ()

    def as_dict(self):
        return asdict(self)


@dataclass(frozen=True)
class PersonalPrincipal:
    user_id: str
    user_name: str
    created: bool
    request_id: str = ""


@dataclass(frozen=True)
class BucketMutation:
    created: bool = False
    request_id: str = ""


@dataclass(frozen=True)
class BucketEmptiness:
    is_empty: bool
    object_count: int = 0
    version_count: int = 0
    delete_marker_count: int = 0
    multipart_upload_count: int = 0
    request_id: str = ""


@dataclass(frozen=True)
class AccessKeyMetadata:
    access_key_id: str
    fingerprint: str
    last_four: str
    status: str
    created_at: str = ""


@dataclass(frozen=True)
class IssuedAccessKey:
    access_key_id: str
    secret_access_key: str
    request_id: str = ""


class ObjectStorageProvider(Protocol):
    def validate_management_identity(self, pool): ...

    def find_or_create_personal_principal(self, identity): ...

    def create_owned_bucket(self, bucket): ...

    def inspect_bucket_emptiness(self, bucket): ...

    def delete_owned_bucket(self, bucket): ...

    def reconcile_object_policy(self, identity, buckets): ...

    def list_access_keys(self, identity): ...

    def create_access_key(self, identity): ...

    def deactivate_access_key(self, key): ...

    def delete_access_key(self, key): ...
