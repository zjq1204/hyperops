from dataclasses import asdict, dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class ManagementCapabilities:
    account_id: str
    can_manage_ram: bool
    can_manage_oss: bool
    request_ids: tuple[str, ...] = ()
    error_category: str = ""

    def as_dict(self):
        return asdict(self)


@dataclass(frozen=True)
class PersonalPrincipal:
    user_id: str
    user_name: str
    created: bool
    marker: str
    request_id: str = ""
    error_category: str = ""


@dataclass(frozen=True)
class BucketMutation:
    created: bool = False
    request_id: str = ""
    error_category: str = ""


@dataclass(frozen=True)
class BucketOwnership:
    exists: bool
    owned: bool
    marker: str = ""
    request_id: str = ""
    error_category: str = ""


@dataclass(frozen=True)
class BucketEmptiness:
    is_empty: bool
    object_count: int = 0
    version_count: int = 0
    delete_marker_count: int = 0
    multipart_upload_count: int = 0
    request_id: str = ""
    error_category: str = ""


@dataclass(frozen=True)
class PolicyMutation:
    request_id: str = ""
    error_category: str = ""


@dataclass(frozen=True)
class AccessKeyMetadata:
    access_key_id: str
    fingerprint: str
    last_four: str
    status: str
    created_at: str = ""
    request_id: str = ""
    error_category: str = ""


@dataclass(frozen=True)
class KeyListResult:
    items: tuple[AccessKeyMetadata, ...]
    request_id: str = ""
    error_category: str = ""


@dataclass(frozen=True)
class IssuedAccessKey:
    access_key_id: str
    secret_access_key: str = field(repr=False)
    request_id: str = ""
    error_category: str = ""


@dataclass(frozen=True)
class AccessKeyMutation:
    request_id: str = ""
    error_category: str = ""


@dataclass(frozen=True)
class BucketConfiguration:
    acl: str = "private"
    storage_class: str = "Standard"
    encryption: str = "AES256"
    versioning: bool = False
    lifecycle: object = field(default_factory=dict)

    def __post_init__(self):
        if self.acl not in {"private", "public_read"}:
            raise ValueError("BUCKET_ACL_UNSUPPORTED")
        if self.storage_class not in {
            "Standard",
            "IA",
            "Archive",
            "ColdArchive",
            "DeepColdArchive",
        }:
            raise ValueError("BUCKET_STORAGE_CLASS_UNSUPPORTED")
        if self.encryption not in {"AES256", "KMS"}:
            raise ValueError("BUCKET_ENCRYPTION_UNSUPPORTED")
        if not isinstance(self.versioning, bool):
            raise ValueError("BUCKET_VERSIONING_INVALID")
        if not isinstance(self.lifecycle, (dict, list)):
            raise ValueError("BUCKET_LIFECYCLE_INVALID")

    def as_snapshot(self):
        return {
            "acl": self.acl,
            "storage_class": self.storage_class,
            "encryption": self.encryption,
            "versioning": self.versioning,
            "lifecycle": self.lifecycle,
        }

    @classmethod
    def from_snapshot(cls, snapshot):
        return cls(
            acl=snapshot.get("acl", "private"),
            storage_class=snapshot.get("storage_class", "Standard"),
            encryption=snapshot.get("encryption", "AES256"),
            versioning=snapshot.get("versioning", False),
            lifecycle=snapshot.get("lifecycle", {}),
        )


@dataclass(frozen=True)
class BucketConfigurationMutation:
    request_id: str = ""
    error_category: str = ""


class ObjectStorageProvider(Protocol):
    def validate_management_identity(self, pool): ...

    def find_or_create_personal_principal(self, identity): ...

    def create_owned_bucket(self, bucket, configuration=None): ...

    def find_owned_bucket(self, bucket): ...

    def inspect_bucket_emptiness(self, bucket): ...

    def delete_owned_bucket(self, bucket): ...

    def reconcile_object_policy(self, identity, buckets): ...

    def list_access_keys(self, identity): ...

    def create_access_key(self, identity): ...

    def activate_access_key(self, key): ...

    def deactivate_access_key(self, key): ...

    def delete_access_key(self, key): ...

    def update_bucket_configuration(
        self,
        bucket,
        configuration,
        *,
        allow_public_read=False,
    ): ...
