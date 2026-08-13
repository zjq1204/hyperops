# Monitoring SSH Credential Center Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace file-backed monitoring SSH keys with an encrypted, versioned, auditable credential center that supports passphrase-protected keys and is shared by connection tests and Ansible jobs.

**Architecture:** Keep the logical host-to-credential relationship, rename the legacy key model, and add immutable credential versions, validation records, and audit records. A focused service layer owns key-ring encryption, OpenSSH parsing, lifecycle transitions, and task-scoped runtime material; DRF actions and Vue pages consume only redacted metadata. Deployment is staged so legacy files remain readable until an explicit, verifiable migration command encrypts them and reports which plaintext files may be removed.

**Tech Stack:** Django 5.1, Django REST Framework 3.15, PostgreSQL/SQLite migrations, `cryptography.fernet`, OpenSSH (`ssh`, `ssh-keygen`, `ssh-agent`, `ssh-add`), Ansible Core 2.19, Celery, Vue 3 `<script setup>`, Vue Router, Tailwind CSS, node contract tests, pytest, Playwright.

---

## File Map

### Backend: create

- `backend/monitoring_stack/services/credential_crypto.py` - parse the configured key ring and encrypt/decrypt versioned secret envelopes.
- `backend/monitoring_stack/services/credential_ingestion.py` - normalize and inspect uploaded private keys through OpenSSH, then create encrypted immutable versions.
- `backend/monitoring_stack/services/credential_runtime.py` - credential-provider boundary, task-scoped key files, one scoped `ssh-agent`, and cleanup.
- `backend/monitoring_stack/services/credential_lifecycle.py` - validation, assignment guards, rotation activation, archive/delete rules, and audit writes.
- `backend/monitoring_stack/permissions.py` - operation-level credential permission constants and DRF checks.
- `backend/monitoring_stack/checks.py` - deployment health check for missing or unusable encryption keys.
- `backend/monitoring_stack/management/commands/migrate_monitoring_ssh_credentials.py` - staged conversion of legacy plaintext key files.
- `backend/monitoring_stack/management/commands/reencrypt_monitoring_credentials.py` - resumable key-ring rotation command.
- `backend/monitoring_stack/tests/ssh_key_fixtures.py` - test-only OpenSSH key generation helpers.
- `backend/monitoring_stack/tests/test_credential_crypto.py` - envelope and key-ring tests.
- `backend/monitoring_stack/tests/test_credential_ingestion.py` - normalization, parsing, passphrase, and duplicate tests.
- `backend/monitoring_stack/tests/test_credential_runtime.py` - file mode, agent, cleanup, and runtime snapshot tests.
- `backend/monitoring_stack/tests/test_credential_api.py` - redaction, permission, lifecycle, rotation, conflict, and audit API tests.
- `backend/monitoring_stack/tests/test_credential_migration.py` - legacy migration and re-encryption command tests.
- `backend/accounts/migrations/0012_role_operation_permissions.py` - role operation-permission storage and compatibility grant.
- `backend/monitoring_stack/migrations/0016_ssh_credential_center_models.py` - rename the logical model and add versions, validations, audits, and job snapshots.

### Backend: modify

- `backend/core/settings/base.py` - encryption key ring, upload limit, secret retention, and runtime timeout settings.
- `backend/monitoring_stack/tests_settings.py` - deterministic test key ring.
- `env.sample` - required production encryption configuration and rotation format.
- `backend/accounts/models.py` - `Role.operation_permissions`.
- `backend/accounts/access.py` - normalize, serialize, and resolve operation permissions.
- `backend/accounts/views/management.py` - accept and return role operation permissions/options.
- `backend/platformkit/management.py` - include injected operation permissions in role payloads without monitoring-specific constants.
- `backend/accounts/tests/test_access_profile.py` - effective operation-permission union and superuser behavior.
- `backend/accounts/tests/test_management_pagination.py` - role API contract.
- `backend/monitoring_stack/models.py` - credential, version, validation, audit, and job snapshot models.
- `backend/monitoring_stack/apps.py` - register credential deployment checks.
- `backend/monitoring_stack/serializers.py` - metadata-only serializers, write-only upload fields, assignability checks, and host credential fields.
- `backend/monitoring_stack/views.py` - credential actions, host assignment checks, and provider-backed connection tests.
- `backend/monitoring_stack/urls.py` - `/credentials/` router registration and legacy `/ssh-keys/` compatibility route.
- `backend/monitoring_stack/services/core.py` - inventory path injection, redacted snapshots, and provider-backed Ansible execution.
- `backend/monitoring_stack/services/ssh_verification.py` - bind receipts to credential version/fingerprint.
- `backend/monitoring_stack/tasks.py` - preserve sanitized credential errors while guaranteeing runtime cleanup.
- `backend/monitoring_stack/tests/test_monitoring_stack_api.py` - update old key fixtures/imports and regression expectations.

### Frontend: create

- `frontend/src/admin/pages/Monitoring/Credentials.vue` - credential list, filters, detail selection, lifecycle actions, and responsive layout.
- `frontend/src/admin/pages/Monitoring/credentials/CredentialUploadModal.vue` - create/rotate upload and parsed-metadata review flow.
- `frontend/src/admin/pages/Monitoring/credentials/CredentialDetailDrawer.vue` - host references, versions, validation history, and audit history.
- `frontend/src/admin/pages/Monitoring/credentials/CredentialValidationPanel.vue` - host selection and per-host validation results.
- `frontend/src/admin/pages/Monitoring/credentials/credentialState.js` - pure presentation and capability helpers.
- `frontend/tests/_review/admin-monitoring-credentials-contract.test.mjs` - route/API/redaction/assets-page contract.
- `frontend/tests/unit/monitoring-credential-state.test.mjs` - pure state tests.
- `frontend/e2e/monitoring-credentials.spec.js` - desktop/mobile credential-center workflows with mocked APIs.

### Frontend: modify

- `frontend/src/admin/api/monitoringStack.js` - credential CRUD, validation, rotation, activation, archive, and deletion calls.
- `frontend/src/admin/routes.js` - `/management/monitoring/credentials`.
- `frontend/src/admin/layout/AdminSidebar.vue` - credential-center navigation.
- `frontend/src/admin/pages/Monitoring/Assets.vue` - remove embedded upload; retain selector, manage link, and connection verification.
- `frontend/src/admin/pages/Management/Roles.vue` - operation-permission checkboxes grouped below monitoring access.
- `frontend/src/store/user.js` - expose `userHasOperationPermission`.
- `frontend/src/utils/platformAccess.js` - read effective operation permissions.
- `frontend/src/admin/locales/en.json` - English labels, states, and errors.
- `frontend/src/admin/locales/zh-CN.json` - Chinese labels, states, and errors.
- `frontend/tests/_review/admin-monitoring-stack-contract.test.mjs` - selector-only asset contract and navigation assertion.

## Stable Contracts

Use these names consistently throughout implementation:

```python
# accounts/access.py
MONITORING_CREDENTIAL_PERMISSION_KEYS = (
    "monitoring_credentials_view",
    "monitoring_credentials_use",
    "monitoring_credentials_manage",
    "monitoring_credentials_delete",
)

def normalize_operation_permission_keys(values) -> list[str]:
    selected = set(values or [])
    return [key for key in MONITORING_CREDENTIAL_PERMISSION_KEYS if key in selected]

def get_effective_operation_permission_keys(user, *, effective_roles=None) -> list[str]:
    """Return the ordered union of operation permissions from effective roles."""

def user_has_operation_permission(user, permission: str) -> bool:
    return permission in get_effective_operation_permission_keys(user)

# monitoring_stack/services/credential_crypto.py
class CredentialEncryptionUnavailable(Exception):
    pass

class CredentialDecryptionError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code

def encrypt_secret(value: str) -> str:
    """Encrypt with the primary configured key into a versioned envelope."""

def decrypt_secret(envelope: str) -> str:
    """Decrypt with the envelope key ID or raise a stable domain error."""

def envelope_key_id(envelope: str) -> str:
    """Return the key ID without decrypting the envelope."""

# monitoring_stack/services/credential_ingestion.py
@dataclass(frozen=True)
class ParsedPrivateKey:
    normalized_private_key: str
    passphrase: str
    has_passphrase: bool
    algorithm: str
    key_size: int | None
    curve: str
    public_key_text: str
    public_key_fingerprint: str

class PrivateKeyValidationError(Exception):
    code: str
    field: str

def inspect_private_key(private_key: str, passphrase: str = "") -> ParsedPrivateKey:
    """Return normalized OpenSSH-derived metadata or raise PrivateKeyValidationError."""

# monitoring_stack/services/credential_runtime.py
@dataclass(frozen=True)
class RuntimeCredentialBundle:
    key_paths: dict[int, Path]       # version_id -> private key path
    process_env: dict[str, str]      # only non-secret runtime variables
    snapshots: dict[int, dict]       # credential_id -> redacted version metadata

class DatabaseSshCredentialProvider:
    @contextmanager
    def materialize(self, versions) -> Iterator[RuntimeCredentialBundle]:
        """Yield scoped key paths/agent environment and always destroy them."""

# monitoring_stack/services/credential_lifecycle.py
def validate_version_on_hosts(*, version, hosts, actor, request_context) -> list:
    """Persist and return one redacted connection result per host."""

def activate_version(*, credential_id, version_id, actor, request_context):
    """Atomically activate a fully validated draft and return the credential."""

def archive_credential(*, credential_id, actor, request_context):
    """Archive one unreferenced credential or raise CredentialReferenceConflict."""

def delete_credential(*, credential_id, actor, request_context):
    """Delete retained ciphertext from an eligible archived credential."""
```

The primary API is `/api/v1/monitoring/credentials/`. Keep `/api/v1/monitoring/ssh-keys/` as a read-only compatibility alias for one release; it returns the same redacted metadata and sends `Deprecation: true` plus a `Link` header to `/credentials/`.

---

### Task 1: Add the encryption envelope and required settings

**Files:**
- Create: `backend/monitoring_stack/services/credential_crypto.py`
- Create: `backend/monitoring_stack/tests/test_credential_crypto.py`
- Modify: `backend/core/settings/base.py:185-220`
- Modify: `backend/monitoring_stack/tests_settings.py:50-60`
- Modify: `env.sample` monitoring configuration section

- [ ] **Step 1: Write failing tests for explicit key-ring parsing and envelopes**

```python
FERNET_A = Fernet.generate_key().decode()
FERNET_B = Fernet.generate_key().decode()

@override_settings(MONITORING_CREDENTIAL_ENCRYPTION_KEYS=f"new:{FERNET_A},old:{FERNET_B}")
def test_envelope_uses_primary_key_and_round_trips():
    envelope = encrypt_secret("private material")
    assert envelope.startswith("v1:new:")
    assert decrypt_secret(envelope) == "private material"
    assert envelope_key_id(envelope) == "new"
    assert "private material" not in envelope

@override_settings(MONITORING_CREDENTIAL_ENCRYPTION_KEYS="")
def test_missing_key_ring_never_falls_back_to_secret_key():
    with pytest.raises(CredentialEncryptionUnavailable):
        encrypt_secret("secret")

@override_settings(MONITORING_CREDENTIAL_ENCRYPTION_KEYS=f"other:{FERNET_B}")
def test_unknown_envelope_key_is_unavailable():
    with pytest.raises(CredentialDecryptionError) as error:
        decrypt_secret(f"v1:removed:{Fernet(FERNET_A).encrypt(b'secret').decode()}")
    assert error.value.code == "CREDENTIAL_ENCRYPTION_KEY_UNAVAILABLE"
```

- [ ] **Step 2: Run the tests and verify the missing module failure**

Run:

```bash
PYTHONPATH=backend .venv/bin/python -m pytest backend/monitoring_stack/tests/test_credential_crypto.py -q
```

Expected: FAIL with `ModuleNotFoundError: monitoring_stack.services.credential_crypto`.

- [ ] **Step 3: Implement strict key-ring parsing and `v1:<key-id>:<fernet-token>` envelopes**

```python
def configured_key_ring():
    raw = str(getattr(settings, "MONITORING_CREDENTIAL_ENCRYPTION_KEYS", "") or "")
    entries = []
    for item in filter(None, (part.strip() for part in raw.split(","))):
        key_id, separator, encoded_key = item.partition(":")
        if not separator or not key_id or not encoded_key:
            raise CredentialEncryptionUnavailable("invalid credential encryption key ring")
        try:
            entries.append((key_id, Fernet(encoded_key.encode())))
        except (TypeError, ValueError) as exc:
            raise CredentialEncryptionUnavailable("invalid credential encryption key") from exc
    if not entries:
        raise CredentialEncryptionUnavailable("credential encryption key ring is not configured")
    if len({key_id for key_id, _ in entries}) != len(entries):
        raise CredentialEncryptionUnavailable("duplicate credential encryption key id")
    return entries

def encrypt_secret(value):
    key_id, cipher = configured_key_ring()[0]
    token = cipher.encrypt(str(value).encode("utf-8")).decode("ascii")
    return f"v1:{key_id}:{token}"

def decrypt_secret(envelope):
    version, key_id, token = str(envelope or "").split(":", 2)
    if version != "v1":
        raise CredentialDecryptionError("CREDENTIAL_ENVELOPE_UNSUPPORTED")
    cipher = dict(configured_key_ring()).get(key_id)
    if cipher is None:
        raise CredentialDecryptionError("CREDENTIAL_ENCRYPTION_KEY_UNAVAILABLE")
    try:
        return cipher.decrypt(token.encode("ascii")).decode("utf-8")
    except (InvalidToken, UnicodeDecodeError) as exc:
        raise CredentialDecryptionError("CREDENTIAL_DECRYPTION_FAILED") from exc
```

Add settings with no `SECRET_KEY` fallback:

```python
MONITORING_CREDENTIAL_ENCRYPTION_KEYS = os.getenv(
    "MONITORING_CREDENTIAL_ENCRYPTION_KEYS", ""
)
MONITORING_CREDENTIAL_MAX_UPLOAD_BYTES = int(
    os.getenv("MONITORING_CREDENTIAL_MAX_UPLOAD_BYTES", "65536")
)
MONITORING_CREDENTIAL_SECRET_RETENTION_DAYS = int(
    os.getenv("MONITORING_CREDENTIAL_SECRET_RETENTION_DAYS", "30")
)
MONITORING_CREDENTIAL_AGENT_TIMEOUT_SECONDS = int(
    os.getenv("MONITORING_CREDENTIAL_AGENT_TIMEOUT_SECONDS", "10")
)
```

Document `key-id:urlsafe-fernet-key` comma-separated format in `env.sample`; use a generated test key in `tests_settings.py`, never a production sample value.

- [ ] **Step 4: Run focused tests**

Run the Step 2 command. Expected: all tests PASS.

- [ ] **Step 5: Commit the encryption boundary**

```bash
git add backend/monitoring_stack/services/credential_crypto.py backend/monitoring_stack/tests/test_credential_crypto.py backend/core/settings/base.py backend/monitoring_stack/tests_settings.py env.sample
git commit -m "feat: add monitoring credential encryption envelope"
```

### Task 2: Add operation permissions to roles

**Files:**
- Create: `backend/accounts/migrations/0012_role_operation_permissions.py`
- Modify: `backend/accounts/models.py:31-85`
- Modify: `backend/accounts/access.py`
- Modify: `backend/platformkit/management.py:19-63`
- Modify: `backend/accounts/views/management.py:20-610`
- Modify: `backend/accounts/tests/test_access_profile.py`
- Modify: `backend/accounts/tests/test_management_pagination.py`

- [ ] **Step 1: Write failing access-profile and role-API tests**

```python
def test_operation_permissions_are_unioned_across_roles(user):
    view_role = Role.objects.create(
        name="viewer", operation_permissions=["monitoring_credentials_view"]
    )
    use_role = Role.objects.create(
        name="operator", operation_permissions=["monitoring_credentials_use"]
    )
    user.platform_roles.add(view_role, use_role)
    assert get_access_profile(user)["operation_permissions"] == [
        "monitoring_credentials_view", "monitoring_credentials_use"
    ]

def test_superuser_has_all_operation_permissions(superuser):
    assert get_effective_operation_permission_keys(superuser) == list(
        MONITORING_CREDENTIAL_PERMISSION_KEYS
    )

def test_role_api_accepts_and_returns_operation_permissions(admin_client):
    response = admin_client.post("/api/v1/management/roles/", {
        "name": "Credential operator",
        "visible_features": ["admin_monitoring"],
        "operation_permissions": ["monitoring_credentials_view", "unknown"],
    }, format="json")
    assert response.status_code == 201
    assert response.json()["operation_permissions"] == ["monitoring_credentials_view"]
```

- [ ] **Step 2: Run tests and confirm schema/payload failures**

```bash
PYTHONPATH=backend .venv/bin/python -m pytest backend/accounts/tests/test_access_profile.py backend/accounts/tests/test_management_pagination.py -q
```

Expected: FAIL because `operation_permissions` and its normalizers do not exist.

- [ ] **Step 3: Add the role field, permission manifest, effective union, and API payload**

Use this canonical manifest in `accounts/access.py`:

```python
OPERATION_PERMISSION_DEFINITIONS = (
    {"key": "monitoring_credentials_view", "label": "查看 SSH 凭据", "feature": "admin_monitoring"},
    {"key": "monitoring_credentials_use", "label": "使用 SSH 凭据", "feature": "admin_monitoring"},
    {"key": "monitoring_credentials_manage", "label": "管理 SSH 凭据", "feature": "admin_monitoring"},
    {"key": "monitoring_credentials_delete", "label": "删除 SSH 凭据", "feature": "admin_monitoring"},
)
MONITORING_CREDENTIAL_PERMISSION_KEYS = tuple(
    item["key"] for item in OPERATION_PERMISSION_DEFINITIONS
)

def normalize_operation_permission_keys(values):
    selected = set(values or [])
    return [key for key in MONITORING_CREDENTIAL_PERMISSION_KEYS if key in selected]

def get_effective_operation_permission_keys(user, *, effective_roles=None):
    if user and user.is_authenticated and user.is_superuser:
        return list(MONITORING_CREDENTIAL_PERMISSION_KEYS)
    roles = effective_roles if effective_roles is not None else get_effective_roles(user)
    selected = {key for role in roles for key in (role.operation_permissions or [])}
    return [key for key in MONITORING_CREDENTIAL_PERMISSION_KEYS if key in selected]
```

Add `Role.operation_permissions = models.JSONField(default=list, blank=True)`, normalize it in `save()`, include it in role summary/payload functions via an injected `normalize_operations`, and include `operation_permission_options` in list responses. Extend `get_access_profile()` with `operation_permissions` while preserving every existing key.

The migration must grant all four operations only to active roles whose normalized `visible_features` contains `admin_monitoring`; this preserves existing monitoring administrators without granting access to unrelated roles.

- [ ] **Step 4: Run migrations and focused tests**

```bash
PYTHONPATH=backend .venv/bin/python backend/manage.py makemigrations --check --dry-run
PYTHONPATH=backend .venv/bin/python -m pytest backend/accounts/tests/test_access_profile.py backend/accounts/tests/test_management_pagination.py -q
```

Expected: no uncommitted migrations and all tests PASS.

- [ ] **Step 5: Commit role operation permissions**

```bash
git add backend/accounts/models.py backend/accounts/access.py backend/platformkit/management.py backend/accounts/views/management.py backend/accounts/tests/test_access_profile.py backend/accounts/tests/test_management_pagination.py backend/accounts/migrations/0012_role_operation_permissions.py
git commit -m "feat: add monitoring credential operation permissions"
```

### Task 3: Add credential, version, validation, audit, and snapshot models

**Files:**
- Create: `backend/monitoring_stack/migrations/0016_ssh_credential_center_models.py`
- Modify: `backend/monitoring_stack/models.py:1-260`
- Test: `backend/monitoring_stack/tests/test_credential_api.py`

- [ ] **Step 1: Write failing model contract tests**

```python
def test_credential_version_is_immutable_after_insert(db, user):
    credential = MonitoringSshCredential.objects.create(name="prod", created_by=user)
    version = MonitoringSshCredentialVersion.objects.create(
        credential=credential, version=1,
        private_key_encrypted="cipher", passphrase_encrypted="",
        algorithm="ssh-ed25519", public_key_fingerprint="SHA256:abc",
        public_key_text="ssh-ed25519 AAAA", created_by=user,
    )
    version.algorithm = "ssh-rsa"
    with pytest.raises(ValidationError):
        version.save()

def test_audit_record_cannot_be_updated(db):
    record = MonitoringCredentialAudit.objects.create(
        action="create", status="success", credential_id_snapshot=17
    )
    record.status = "failed"
    with pytest.raises(ValidationError):
        record.save()
```

- [ ] **Step 2: Run tests and verify missing model failures**

```bash
PYTHONPATH=backend .venv/bin/python -m pytest backend/monitoring_stack/tests/test_credential_api.py -q
```

Expected: collection FAIL for undefined credential models.

- [ ] **Step 3: Implement schema and immutable guards**

Rename `MonitoringSshKey` to `MonitoringSshCredential` and `file_name` to nullable `legacy_file_name`; alter `name` to non-unique and add a conditional unique constraint for non-archived names. Add lifecycle constants and fields from the approved design. Add:

```python
class MonitoringSshCredentialVersion(models.Model):
    credential = models.ForeignKey(MonitoringSshCredential, on_delete=models.CASCADE, related_name="versions")
    version = models.PositiveIntegerField()
    private_key_encrypted = models.TextField()
    passphrase_encrypted = models.TextField(blank=True, default="")
    has_passphrase = models.BooleanField(default=False)
    algorithm = models.CharField(max_length=64)
    key_size = models.PositiveIntegerField(null=True, blank=True)
    curve = models.CharField(max_length=64, blank=True, default="")
    public_key_fingerprint = models.CharField(max_length=160, db_index=True)
    public_key_text = models.TextField()
    validation_status = models.CharField(max_length=16, choices=VALIDATION_CHOICES, default=VALIDATION_DRAFT)
    validation_error_code = models.CharField(max_length=64, blank=True, default="")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="created_monitoring_credential_versions")
    created_at = models.DateTimeField(auto_now_add=True)
    activated_at = models.DateTimeField(null=True, blank=True)
    retired_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["credential", "version"], name="unique_monitoring_credential_version"),
        ]
```

Add `MonitoringCredentialValidation` with version, nullable host, `connection_fingerprint`, status/error/latency/actor/time. Add immutable `MonitoringCredentialAudit` with nullable FKs plus snapshot IDs/name, source IP, request ID, affected host IDs, sanitized metadata, and time. Override `save()` on versions/audits to reject changes outside the documented mutable version fields (`validation_status`, `validation_error_code`, `activated_at`, `retired_at`).

Add `AnsibleInstallJob.credential_snapshots = models.JSONField(default=list, blank=True)`. Keep `MonitoringHost.ssh_key_credential` pointing to the renamed logical model and retain `ssh_key` only as a compatibility field.

- [ ] **Step 4: Verify migrations and model tests**

```bash
PYTHONPATH=backend .venv/bin/python backend/manage.py makemigrations --check --dry-run
PYTHONPATH=backend .venv/bin/python -m pytest backend/monitoring_stack/tests/test_credential_api.py -q
```

Expected: no migration drift and model tests PASS.

- [ ] **Step 5: Commit the credential schema**

```bash
git add backend/monitoring_stack/models.py backend/monitoring_stack/migrations/0016_ssh_credential_center_models.py backend/monitoring_stack/tests/test_credential_api.py
git commit -m "feat: add versioned monitoring SSH credentials"
```

### Task 4: Normalize and inspect private keys through OpenSSH

**Files:**
- Create: `backend/monitoring_stack/tests/ssh_key_fixtures.py`
- Create: `backend/monitoring_stack/tests/test_credential_ingestion.py`
- Create: `backend/monitoring_stack/services/credential_ingestion.py`

- [ ] **Step 1: Write failing ingestion tests using generated RSA, Ed25519, and encrypted keys**

```python
def test_crlf_key_is_normalized_and_fingerprinted(rsa_private_key):
    parsed = inspect_private_key(rsa_private_key.replace("\n", "\r\n"))
    assert "\r" not in parsed.normalized_private_key
    assert parsed.normalized_private_key.endswith("\n")
    assert parsed.algorithm == "ssh-rsa"
    assert parsed.key_size >= 2048
    assert parsed.public_key_fingerprint.startswith("SHA256:")

@pytest.mark.parametrize("passphrase,code,field", [
    ("", "PASSPHRASE_REQUIRED", "passphrase"),
    ("wrong", "PASSPHRASE_INVALID", "passphrase"),
])
def test_encrypted_key_requires_correct_passphrase(encrypted_private_key, passphrase, code, field):
    with pytest.raises(PrivateKeyValidationError) as error:
        inspect_private_key(encrypted_private_key, passphrase)
    assert (error.value.code, error.value.field) == (code, field)

def test_unnecessary_passphrase_is_rejected(ed25519_private_key):
    with pytest.raises(PrivateKeyValidationError) as error:
        inspect_private_key(ed25519_private_key, "not-needed")
    assert error.value.code == "PASSPHRASE_NOT_REQUIRED"
```

Generate fixtures with `ssh-keygen -q -t rsa -b 2048`, `-t ed25519`, and `-N test-passphrase` inside pytest temp directories; skip with an explicit message only if `ssh-keygen` is absent.

- [ ] **Step 2: Run tests and confirm missing ingestion module failure**

```bash
PYTHONPATH=backend .venv/bin/python -m pytest backend/monitoring_stack/tests/test_credential_ingestion.py -q
```

Expected: FAIL for missing `credential_ingestion`.

- [ ] **Step 3: Implement bounded UTF-8 normalization and OpenSSH inspection**

The implementation must:

```python
def normalize_private_key(value):
    if isinstance(value, bytes):
        try:
            value = value.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise PrivateKeyValidationError("PRIVATE_KEY_NOT_UTF8", "private_key") from exc
    normalized = str(value or "").replace("\r\n", "\n").replace("\r", "\n").rstrip("\n") + "\n"
    if len(normalized.encode("utf-8")) > settings.MONITORING_CREDENTIAL_MAX_UPLOAD_BYTES:
        raise PrivateKeyValidationError("PRIVATE_KEY_TOO_LARGE", "private_key")
    return normalized
```

Write the normalized key to a `0600` file at `private_key_path` in `TemporaryDirectory` and first run `ssh-keygen -y -P "" -f str(private_key_path)`. If it fails and the request supplied a passphrase, retry without `-P`: pass the secret through an inherited anonymous pipe, force OpenSSH askpass with `SSH_ASKPASS_REQUIRE=force`, set a dummy `DISPLAY`, and point `SSH_ASKPASS` at a temporary `0700` script that reads `/proc/self/fd/$CREDENTIAL_PASSPHRASE_FD`. The environment stores only the file-descriptor number; close both pipe ends and remove the script in `finally`. Never place the passphrase in argv, a persistent environment variable, or logs. Distinguish missing/wrong/unnecessary passphrases, reject malformed keys, write the derived public key to `public_key_path`, and run `ssh-keygen -lf str(public_key_path) -E sha256`. Parse the bit count, algorithm, and ECDSA curve from those outputs. Delete the directory through its context manager.

- [ ] **Step 4: Add encrypted version creation and duplicate-fingerprint guard**

```python
@transaction.atomic
def create_credential_version(*, credential, private_key, passphrase="", actor=None):
    parsed = inspect_private_key(private_key, passphrase)
    duplicate = MonitoringSshCredentialVersion.objects.filter(
        public_key_fingerprint=parsed.public_key_fingerprint,
        credential__status=MonitoringSshCredential.STATUS_ACTIVE,
    ).exclude(credential=credential).select_related("credential").first()
    if duplicate:
        raise DuplicateCredentialFingerprint(duplicate.credential_id)
    next_version = (credential.versions.aggregate(value=Max("version"))["value"] or 0) + 1
    return MonitoringSshCredentialVersion.objects.create(
        credential=credential, version=next_version,
        private_key_encrypted=encrypt_secret(parsed.normalized_private_key),
        passphrase_encrypted=encrypt_secret(parsed.passphrase) if parsed.has_passphrase else "",
        has_passphrase=parsed.has_passphrase, algorithm=parsed.algorithm,
        key_size=parsed.key_size, curve=parsed.curve,
        public_key_fingerprint=parsed.public_key_fingerprint,
        public_key_text=parsed.public_key_text, created_by=actor,
    )
```

Add tests asserting neither plaintext nor passphrase appears in database fields and duplicate fingerprints return the original credential ID.

- [ ] **Step 5: Run tests and commit ingestion**

```bash
PYTHONPATH=backend .venv/bin/python -m pytest backend/monitoring_stack/tests/test_credential_ingestion.py backend/monitoring_stack/tests/test_credential_crypto.py -q
git add backend/monitoring_stack/services/credential_ingestion.py backend/monitoring_stack/tests/ssh_key_fixtures.py backend/monitoring_stack/tests/test_credential_ingestion.py
git commit -m "feat: validate and encrypt uploaded SSH credentials"
```

Expected: tests PASS before commit.

### Task 5: Add the task-scoped runtime credential provider

**Files:**
- Create: `backend/monitoring_stack/services/credential_runtime.py`
- Create: `backend/monitoring_stack/tests/test_credential_runtime.py`

- [ ] **Step 1: Write failing cleanup and permission tests**

```python
def test_unencrypted_bundle_has_private_0700_directory_and_0600_key(version):
    provider = DatabaseSshCredentialProvider()
    with provider.materialize([version]) as bundle:
        key_path = bundle.key_paths[version.id]
        root = key_path.parent
        assert stat.S_IMODE(root.stat().st_mode) == 0o700
        assert stat.S_IMODE(key_path.stat().st_mode) == 0o600
        assert key_path.read_text() == NORMALIZED_PRIVATE_KEY
    assert not root.exists()

def test_encrypted_bundle_starts_agent_without_passphrase_in_env(encrypted_version, monkeypatch):
    calls = fake_agent_processes(monkeypatch)
    with DatabaseSshCredentialProvider().materialize([encrypted_version]) as bundle:
        assert "SSH_AUTH_SOCK" in bundle.process_env
        assert PASSPHRASE not in repr(bundle.process_env)
        assert PASSPHRASE not in repr(calls.commands)
    assert calls.agent_killed

@pytest.mark.parametrize("exit_mode", ["success", "exception", "timeout"])
def test_agent_and_files_are_cleaned_for_every_exit(exit_mode, encrypted_version, monkeypatch):
    calls = fake_agent_processes(monkeypatch)
    provider = DatabaseSshCredentialProvider()
    with pytest.raises(RuntimeError) if exit_mode != "success" else nullcontext():
        with provider.materialize([encrypted_version]) as bundle:
            root = bundle.key_paths[encrypted_version.id].parent
            if exit_mode != "success":
                raise RuntimeError(exit_mode)
    assert not root.exists()
    assert calls.agent_killed
```

- [ ] **Step 2: Run tests and verify missing provider failure**

```bash
PYTHONPATH=backend .venv/bin/python -m pytest backend/monitoring_stack/tests/test_credential_runtime.py -q
```

Expected: FAIL for missing runtime provider.

- [ ] **Step 3: Implement one bundle directory and one agent per execution**

`DatabaseSshCredentialProvider.materialize(versions)` must:

1. Deduplicate versions by ID and decrypt all values before launching Ansible.
2. Create `tempfile.mkdtemp(prefix="hyperops-monitoring-credentials-")`, immediately `chmod 0700`.
3. Write `f"{version.id}.key"` with `os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)`.
4. If any version has a passphrase, start exactly one `ssh-agent -s`, parse only `SSH_AUTH_SOCK` and `SSH_AGENT_PID`, and load each protected key.
5. Pass the passphrase to `ssh-add` through an inherited anonymous pipe read by a task-local `0700` askpass script; environment contains only the non-secret file-descriptor number, `DISPLAY`, and agent variables.
6. Yield redacted snapshots containing `credential_id`, `version_id`, and `public_key_fingerprint`.
7. In `finally`, call `ssh-agent -k` with the scoped environment, overwrite best-effort, unlink keys/askpass, and remove the directory.

Use an `ExitStack` so partial setup failures clean already-created material. Raise stable codes `CREDENTIAL_UNAVAILABLE`, `CREDENTIAL_AGENT_START_FAILED`, and `CREDENTIAL_AGENT_LOAD_FAILED`; never include stderr that may echo a path or secret.

- [ ] **Step 4: Run provider tests including exception paths**

Run the Step 2 command. Expected: all tests PASS and no temp paths remain.

- [ ] **Step 5: Commit runtime provider**

```bash
git add backend/monitoring_stack/services/credential_runtime.py backend/monitoring_stack/tests/test_credential_runtime.py
git commit -m "feat: materialize task-scoped SSH credentials"
```

### Task 6: Use one provider path for connection tests and Ansible

**Files:**
- Modify: `backend/monitoring_stack/services/core.py:581-690,1805-2040,2210-2340`
- Modify: `backend/monitoring_stack/services/ssh_verification.py`
- Modify: `backend/monitoring_stack/views.py:610-690`
- Modify: `backend/monitoring_stack/tasks.py`
- Modify: `backend/monitoring_stack/tests/test_credential_runtime.py`
- Modify: `backend/monitoring_stack/tests/test_monitoring_stack_api.py`

- [ ] **Step 1: Write failing integration tests for active-version resolution and redacted snapshots**

```python
def test_connection_test_and_ansible_use_same_active_version(api_client, host, active_version, monkeypatch):
    materialized = capture_provider_materialization(monkeypatch)
    response = api_client.post("/api/v1/monitoring/hosts/test-connection/", connection_payload(host), format="json")
    assert response.status_code == 200
    execute_ansible_job(make_job(host).id)
    assert materialized.version_ids == [active_version.id, active_version.id]

def test_job_snapshot_contains_only_redacted_credential_metadata(job, host, active_version):
    execute_ansible_job(job.id)
    job.refresh_from_db()
    assert job.credential_snapshots == [{
        "credential_id": host.ssh_key_credential_id,
        "version_id": active_version.id,
        "public_key_fingerprint": active_version.public_key_fingerprint,
    }]
    assert "PRIVATE KEY" not in json.dumps(job.hosts_snapshot)
    assert "passphrase" not in json.dumps(job.hosts_snapshot).lower()
```

- [ ] **Step 2: Run focused runtime/API tests and confirm legacy-path assertions fail**

```bash
PYTHONPATH=backend .venv/bin/python -m pytest backend/monitoring_stack/tests/test_credential_runtime.py backend/monitoring_stack/tests/test_monitoring_stack_api.py -k 'ssh or credential or ansible' -q
```

Expected: FAIL because `host_ssh_key_path()` still reads `storage_path` and inventory snapshots expose legacy filenames.

- [ ] **Step 3: Refactor connection execution to accept materialized key path and process environment**

Keep `check_monitoring_ssh_connection()` as the sole OpenSSH probe, but remove its `ssh-keygen` precheck because ingestion/provider resolution already guarantees format. Add `process_env=None` and merge only the provider's scoped variables. The host endpoint resolves `credential.active_version`, opens `DatabaseSshCredentialProvider().materialize([version])`, and passes `bundle.key_paths[version.id]` plus `bundle.process_env`.

Bind verification fingerprints to all three identities:

```python
connection_fingerprint(
    ssh_credential_id=credential.id,
    ssh_credential_version_id=version.id,
    ssh_public_key_fingerprint=version.public_key_fingerprint,
)
```

- [ ] **Step 4: Refactor inventory and worker execution around one materialization context**

Change `render_inventory(hosts, key_paths=None)` so it never resolves storage itself. At job start, lock in each host's active version, open one provider bundle for all unique versions, write inventory with the supplied map, set `job.credential_snapshots`, and run `ansible-playbook` with `{**os.environ, **bundle.process_env, "ANSIBLE_HOST_KEY_CHECKING": "False", "ANSIBLE_FORCE_COLOR": "0", "PYTHONUNBUFFERED": "1"}`. `job_vars()` and `hosts_snapshot` may expose credential name/ID/version/fingerprint but never key filename/path/ciphertext/passphrase.

The provider context must wrap the entire `Popen`, output loop, timeout, and result parsing block. Convert provider exceptions into sanitized job logs such as `f"credential unavailable: {credential.id}"` and always mark the job failed without raw exception text.

- [ ] **Step 5: Run focused and monitoring regression tests**

```bash
PYTHONPATH=backend .venv/bin/python -m pytest backend/monitoring_stack/tests/test_credential_runtime.py backend/monitoring_stack/tests/test_monitoring_stack_api.py backend/monitoring_stack/tests/test_ansible_job_progress.py -q
```

Expected: all tests PASS.

- [ ] **Step 6: Commit shared runtime integration**

```bash
git add backend/monitoring_stack/services/core.py backend/monitoring_stack/services/ssh_verification.py backend/monitoring_stack/views.py backend/monitoring_stack/tasks.py backend/monitoring_stack/tests/test_credential_runtime.py backend/monitoring_stack/tests/test_monitoring_stack_api.py
git commit -m "feat: use encrypted credentials for monitoring SSH runtime"
```

### Task 7: Implement lifecycle, validation, rotation, conflicts, and audit sanitization

**Files:**
- Create: `backend/monitoring_stack/services/credential_lifecycle.py`
- Modify: `backend/monitoring_stack/tests/test_credential_api.py`

- [ ] **Step 1: Write failing lifecycle tests**

```python
def test_rotation_requires_every_enabled_linked_host_to_pass(credential, hosts, draft_version, monkeypatch):
    fake_validation(monkeypatch, {hosts[0].id: "success", hosts[1].id: "failed"})
    validate_version_on_hosts(version=draft_version, hosts=hosts, actor=None, request_context={})
    with pytest.raises(CredentialActivationError) as error:
        activate_version(credential_id=credential.id, version_id=draft_version.id, actor=None, request_context={})
    assert error.value.code == "CREDENTIAL_VALIDATION_INCOMPLETE"

def test_successful_activation_is_atomic_and_invalidates_host_receipts(
    credential, old_version, draft_version, linked_host
):
    successful_validation(version=draft_version, host=linked_host)
    activated = activate_version(
        credential_id=credential.id,
        version_id=draft_version.id,
        actor=None,
        request_context={},
    )
    old_version.refresh_from_db()
    linked_host.refresh_from_db()
    assert activated.active_version_id == draft_version.id
    assert old_version.retired_at is not None
    assert linked_host.ssh_verification_status == "unverified"
    assert linked_host.ssh_verification_signature == ""

def test_referenced_archive_returns_host_conflict(credential, linked_host):
    with pytest.raises(CredentialReferenceConflict) as error:
        archive_credential(credential_id=credential.id, actor=None, request_context={})
    assert error.value.hosts == [{"id": linked_host.id, "name": linked_host.hostname}]

def test_audit_metadata_removes_secret_fields(db):
    record_credential_audit(action="create", status="failed", metadata={
        "private_key": "secret", "passphrase": "secret", "command": "ssh -i /tmp/key", "error_code": "INVALID"
    })
    assert MonitoringCredentialAudit.objects.get().metadata == {"error_code": "INVALID"}
```

- [ ] **Step 2: Run tests and verify missing lifecycle service failure**

```bash
PYTHONPATH=backend .venv/bin/python -m pytest backend/monitoring_stack/tests/test_credential_api.py -q
```

Expected: FAIL for missing lifecycle functions.

- [ ] **Step 3: Implement validation records and allowlisted audit metadata**

`validate_version_on_hosts()` must use the runtime provider and `check_monitoring_ssh_connection()` for each selected host, upsert one validation result per attempt (history is retained), and set version `valid` after at least one successful check or `invalid` when any requested check fails. Audit metadata must be rebuilt from an allowlist, not recursively scrubbed:

```python
AUDIT_METADATA_KEYS = {
    "error_code", "latency_ms", "old_version_id", "new_version_id",
    "validation_total", "validation_passed", "validation_failed",
    "public_key_fingerprint", "algorithm", "key_size", "curve",
}
```

Request context is built as `{"source_ip": request.META.get("REMOTE_ADDR", ""), "request_id": request.headers.get("X-Request-ID", "")}`. It must never accept request body fields wholesale.

- [ ] **Step 4: Implement transactional activation, assignment guard, archive, and delete**

`activate_version()` performs external validation checks before entering `transaction.atomic()`, then locks credential and versions with `select_for_update()`, verifies all currently linked enabled hosts have latest successful records for the draft, retires the prior version, activates the draft, and resets linked host receipts with `unverified_verification_defaults()`.

`assert_credential_assignable()` requires active lifecycle, active version, decryptability, and version status `valid`. `archive_credential()` and `delete_credential()` lock the logical row and return `CredentialReferenceConflict(hosts)` if referenced. Deletion additionally requires archived status and `archived_at <= now - retention_days`; otherwise raise `CREDENTIAL_RETENTION_ACTIVE`.

- [ ] **Step 5: Run lifecycle tests and commit**

```bash
PYTHONPATH=backend .venv/bin/python -m pytest backend/monitoring_stack/tests/test_credential_api.py -q
git add backend/monitoring_stack/services/credential_lifecycle.py backend/monitoring_stack/tests/test_credential_api.py
git commit -m "feat: add SSH credential lifecycle and audit"
```

Expected: all tests PASS before commit.

### Task 8: Expose redacted credential APIs with operation permissions

**Files:**
- Create: `backend/monitoring_stack/permissions.py`
- Modify: `backend/monitoring_stack/serializers.py:1-390`
- Modify: `backend/monitoring_stack/views.py:1-710`
- Modify: `backend/monitoring_stack/urls.py`
- Modify: `backend/monitoring_stack/tests/test_credential_api.py`

- [ ] **Step 1: Write failing API contract and permission matrix tests**

```python
@pytest.mark.parametrize("permission,method,path", [
    ("monitoring_credentials_view", "get", "/api/v1/monitoring/credentials/"),
    ("monitoring_credentials_manage", "post", "/api/v1/monitoring/credentials/"),
    ("monitoring_credentials_manage", "post", "/api/v1/monitoring/credentials/1/validate/"),
    ("monitoring_credentials_delete", "delete", "/api/v1/monitoring/credentials/1/"),
])
def test_operation_permission_matrix(permission, method, path, credential_user, role_factory):
    client = APIClient()
    client.force_authenticate(credential_user)
    denied = getattr(client, method)(path, {}, format="json")
    assert denied.status_code == 403
    credential_user.platform_roles.add(role_factory(operation_permissions=[permission]))
    allowed = getattr(client, method)(path, {}, format="json")
    assert allowed.status_code != 403

def test_create_response_is_redacted(manage_client, private_key):
    response = manage_client.post("/api/v1/monitoring/credentials/", {
        "name": "prod", "private_key": private_key, "passphrase": ""
    }, format="json")
    body = response.json()
    assert response.status_code == 201
    assert set(body).isdisjoint({"private_key", "passphrase", "private_key_encrypted", "passphrase_encrypted", "legacy_file_name"})

def test_referenced_delete_returns_409_with_host_links(delete_client, credential, linked_host):
    response = delete_client.delete(f"/api/v1/monitoring/credentials/{credential.id}/")
    assert response.status_code == 409
    assert response.json() == {"code": "CREDENTIAL_IN_USE", "hosts": [{"id": linked_host.id, "name": linked_host.hostname}]}
```

- [ ] **Step 2: Run API tests and confirm missing endpoint/permission failures**

Run the Task 7 pytest command. Expected: FAIL with 404/undefined serializers.

- [ ] **Step 3: Implement permission mapping and metadata-only serializers**

`CredentialOperationPermission.has_permission()` first enforces `admin_monitoring`, then maps actions:

```python
ACTION_PERMISSIONS = {
    "list": "monitoring_credentials_view", "retrieve": "monitoring_credentials_view",
    "create": "monitoring_credentials_manage", "rotate": "monitoring_credentials_manage",
    "validate": "monitoring_credentials_manage", "activate": "monitoring_credentials_manage",
    "archive": "monitoring_credentials_manage", "destroy": "monitoring_credentials_delete",
}
```

Define separate `CredentialCreateSerializer`, `CredentialRotateSerializer`, list/detail/version/validation/audit serializers. Upload fields are `write_only=True`; ciphertext, public key text, legacy filename, storage path, and passphrase are absent from every response serializer. List includes `usage_count`, `health`, active version metadata, and last validation timestamp. Detail adds redacted versions, associated hosts, validations, and audit events.

- [ ] **Step 4: Implement viewset actions and compatibility alias**

Register `credentials`. Implement `create`, `rotate`, `validate`, `activate`, `archive`, and `destroy` by calling ingestion/lifecycle services. Translate stable domain errors into field errors or `{code, detail}` responses; reference conflicts are HTTP 409.

Add a read-only `MonitoringSshKeyCompatibilityViewSet` at `ssh-keys` that delegates to the list/retrieve serializer and adds deprecation headers. Do not accept POST on the old route.

Host create/update/test requires `monitoring_credentials_use` whenever key auth is selected. Use serializer querysets restricted to active credentials and call `assert_credential_assignable()` before saving.

- [ ] **Step 5: Run API and monitoring regressions**

```bash
PYTHONPATH=backend .venv/bin/python -m pytest backend/monitoring_stack/tests/test_credential_api.py backend/monitoring_stack/tests/test_monitoring_stack_api.py -q
```

Expected: all tests PASS; responses contain no secret fields.

- [ ] **Step 6: Commit API surface**

```bash
git add backend/monitoring_stack/permissions.py backend/monitoring_stack/serializers.py backend/monitoring_stack/views.py backend/monitoring_stack/urls.py backend/monitoring_stack/tests/test_credential_api.py backend/monitoring_stack/tests/test_monitoring_stack_api.py
git commit -m "feat: expose monitoring SSH credential APIs"
```

### Task 9: Migrate legacy plaintext credentials safely

**Files:**
- Create: `backend/monitoring_stack/management/commands/migrate_monitoring_ssh_credentials.py`
- Create: `backend/monitoring_stack/tests/test_credential_migration.py`
- Modify: `backend/monitoring_stack/services/core.py`

- [ ] **Step 1: Write failing migration tests including the CRLF case**

```python
def test_migration_normalizes_crlf_and_preserves_host_assignment(tmp_path, settings, rsa_private_key, host):
    settings.MONITORING_SSH_DIR = str(tmp_path)
    legacy = MonitoringSshCredential.objects.create(name="zhangjiaqi", legacy_file_name="zhangjiaqi.pem")
    host.ssh_key_credential = legacy
    host.save(update_fields=["ssh_key_credential"])
    (tmp_path / "zhangjiaqi.pem").write_bytes(rsa_private_key.replace("\n", "\r\n").encode())
    call_command("migrate_monitoring_ssh_credentials")
    legacy.refresh_from_db()
    assert legacy.status == legacy.STATUS_ACTIVE
    assert legacy.active_version.version == 1
    assert "\r" not in decrypt_secret(legacy.active_version.private_key_encrypted)
    assert host.ssh_key_credential_id == legacy.id

def test_invalid_legacy_key_needs_reupload_and_is_not_deleted(tmp_path, settings):
    settings.MONITORING_SSH_DIR = str(tmp_path)
    credential = MonitoringSshCredential.objects.create(
        name="invalid", legacy_file_name="invalid.pem"
    )
    path = tmp_path / "invalid.pem"
    path.write_text("not a private key\n")
    call_command("migrate_monitoring_ssh_credentials")
    credential.refresh_from_db()
    assert credential.status == credential.STATUS_NEEDS_REUPLOAD
    assert credential.active_version_id is None
    assert path.exists()

def test_dry_run_does_not_write_or_delete(tmp_path, settings, rsa_private_key):
    settings.MONITORING_SSH_DIR = str(tmp_path)
    credential = MonitoringSshCredential.objects.create(
        name="dry-run", legacy_file_name="dry-run.pem"
    )
    path = tmp_path / "dry-run.pem"
    path.write_text(rsa_private_key)
    call_command("migrate_monitoring_ssh_credentials", dry_run=True)
    credential.refresh_from_db()
    assert credential.active_version_id is None
    assert path.exists()
```

- [ ] **Step 2: Run tests and verify missing command failure**

```bash
PYTHONPATH=backend .venv/bin/python -m pytest backend/monitoring_stack/tests/test_credential_migration.py -q
```

Expected: FAIL with unknown command.

- [ ] **Step 3: Implement idempotent staged migration with an operator report**

The command supports `--dry-run`, `--credential-id`, and `--remove-verified-plaintext`. For each credential without an active version it normalizes/inspects/encrypts the legacy file, decrypts the stored envelope, re-derives the public fingerprint, and only then activates version 1. Invalid/missing files become `needs_reupload` and keep host references. Print one JSON line per credential:

```json
{"credential_id":1,"name":"zhangjiaqi","result":"migrated","fingerprint":"SHA256:base64digest","plaintext_action":"retained"}
```

Only `--remove-verified-plaintext` may unlink a file, only after the round-trip fingerprint matches, and it clears `legacy_file_name` in the same transaction. A second run reports `already_migrated` and creates no new version.

- [ ] **Step 4: Keep a temporary compatibility read for unmigrated credentials**

Runtime resolution may use `legacy_file_name` only during the staged deployment window when there is no active version and status is still `active`; it must normalize and fully inspect the key into a task-scoped file, emit a warning/audit status, and never modify the source. A credential marked `needs_reupload` always raises `CREDENTIAL_NEEDS_REUPLOAD` and never executes. Assignment of a new legacy credential remains prohibited. Mark this helper with a removal condition: delete after production migration reports zero credentials without an active version and zero nonblank `legacy_file_name` values.

- [ ] **Step 5: Run migration and runtime tests, then commit**

```bash
PYTHONPATH=backend .venv/bin/python -m pytest backend/monitoring_stack/tests/test_credential_migration.py backend/monitoring_stack/tests/test_credential_runtime.py -q
git add backend/monitoring_stack/management/commands/migrate_monitoring_ssh_credentials.py backend/monitoring_stack/tests/test_credential_migration.py backend/monitoring_stack/services/core.py
git commit -m "feat: migrate legacy monitoring SSH keys"
```

Expected: all tests PASS before commit.

### Task 10: Add encryption health checks and resumable key rotation

**Files:**
- Create: `backend/monitoring_stack/checks.py`
- Create: `backend/monitoring_stack/management/commands/reencrypt_monitoring_credentials.py`
- Modify: `backend/monitoring_stack/apps.py`
- Modify: `backend/monitoring_stack/tests/test_credential_migration.py`

- [ ] **Step 1: Write failing unavailable-key and re-encryption tests**

```python
def test_health_check_lists_ids_not_ciphertext(settings, encrypted_version):
    settings.MONITORING_CREDENTIAL_ENCRYPTION_KEYS = "replacement:" + NEW_KEY
    errors = check_monitoring_credential_encryption(None)
    assert errors[0].id == "monitoring_stack.E001"
    assert str(encrypted_version.credential_id) in errors[0].hint
    assert encrypted_version.private_key_encrypted not in errors[0].hint

def test_reencrypt_command_is_resumable_and_moves_to_primary_key(old_encrypted_versions, settings):
    settings.MONITORING_CREDENTIAL_ENCRYPTION_KEYS = f"new:{NEW_KEY},old:{OLD_KEY}"
    call_command("reencrypt_monitoring_credentials", batch_size=1)
    for version in MonitoringSshCredentialVersion.objects.all():
        assert envelope_key_id(version.private_key_encrypted) == "new"
        assert decrypt_secret(version.private_key_encrypted).endswith("\n")
```

- [ ] **Step 2: Run migration tests and confirm missing command/check failure**

Run Task 9's pytest command. Expected: FAIL.

- [ ] **Step 3: Implement deployment check and re-encryption command**

Register checks in `MonitoringStackConfig.ready()`. Return `Warning monitoring_stack.W001` when no credentials exist and no key ring is configured; return `Error monitoring_stack.E001` with only affected credential IDs when retained versions cannot decrypt.

The command accepts `--batch-size`, `--resume-after-id`, and `--dry-run`, orders by version ID, decrypts private key/passphrase with any configured key, verifies the private key fingerprint, then atomically rewrites both envelopes with the primary key. Its final JSON summary includes `processed`, `reencrypted`, `already_primary`, `failed`, `last_id`, and `remaining_old_key_envelopes`. It exits nonzero when `failed > 0`.

- [ ] **Step 4: Run checks and command tests**

```bash
PYTHONPATH=backend .venv/bin/python -m pytest backend/monitoring_stack/tests/test_credential_migration.py backend/monitoring_stack/tests/test_credential_crypto.py -q
PYTHONPATH=backend .venv/bin/python backend/manage.py check --deploy
```

Expected: tests PASS; the local environment reports no credential encryption error when configured.

- [ ] **Step 5: Commit recovery tooling**

```bash
git add backend/monitoring_stack/checks.py backend/monitoring_stack/apps.py backend/monitoring_stack/management/commands/reencrypt_monitoring_credentials.py backend/monitoring_stack/tests/test_credential_migration.py
git commit -m "feat: add credential encryption recovery tooling"
```

### Task 11: Add frontend permission state and role controls

**Files:**
- Modify: `frontend/src/utils/platformAccess.js`
- Modify: `frontend/src/store/user.js`
- Modify: `frontend/src/admin/pages/Management/Roles.vue`
- Modify: `frontend/src/admin/locales/en.json`
- Modify: `frontend/src/admin/locales/zh-CN.json`
- Create: `frontend/tests/unit/monitoring-credential-state.test.mjs`

- [ ] **Step 1: Write failing pure permission tests**

```javascript
assert.equal(
  hasOperationPermission(
    { access_profile: { operation_permissions: ['monitoring_credentials_use'] } },
    'monitoring_credentials_use'
  ),
  true
)
assert.equal(hasOperationPermission({}, 'monitoring_credentials_use'), false)
```

- [ ] **Step 2: Run the node test and verify missing export failure**

```bash
cd frontend && node tests/unit/monitoring-credential-state.test.mjs
```

Expected: FAIL because `hasOperationPermission` is not exported.

- [ ] **Step 3: Expose operation permissions and edit them in Roles**

Add `getOperationPermissions(user)` and `hasOperationPermission(user, key)` without mixing operation keys into route feature keys. Expose `userHasOperationPermission` from the user store.

In `Roles.vue`, store `operation_permissions` in form state and render a compact "SSH credential operations" checkbox group only when `admin_monitoring` is selected. Use `operation_permission_options` from the API, submit normalized values, and clear them when monitoring access is removed. Add all visible strings to both locale files.

- [ ] **Step 4: Run permission test and build**

```bash
cd frontend && node tests/unit/monitoring-credential-state.test.mjs && npm run build
```

Expected: test and production build PASS.

- [ ] **Step 5: Commit frontend permission support**

```bash
git add frontend/src/utils/platformAccess.js frontend/src/store/user.js frontend/src/admin/pages/Management/Roles.vue frontend/src/admin/locales/en.json frontend/src/admin/locales/zh-CN.json frontend/tests/unit/monitoring-credential-state.test.mjs
git commit -m "feat: manage SSH credential role permissions"
```

### Task 12: Add credential API client, route, navigation, and presentation state

**Files:**
- Modify: `frontend/src/admin/api/monitoringStack.js`
- Modify: `frontend/src/admin/routes.js`
- Modify: `frontend/src/admin/layout/AdminSidebar.vue`
- Create: `frontend/src/admin/pages/Monitoring/credentials/credentialState.js`
- Create: `frontend/tests/_review/admin-monitoring-credentials-contract.test.mjs`
- Modify: `frontend/src/admin/locales/en.json`
- Modify: `frontend/src/admin/locales/zh-CN.json`

- [ ] **Step 1: Write a failing static contract test**

Assert the route, sidebar item, API methods, and forbidden secret response names:

```javascript
assert.match(routesSource, /path:\s*'\/management\/monitoring\/credentials'/)
assert.match(sidebarSource, /adminNav\.monitoringCredentials/)
for (const method of ['getCredentials', 'createCredential', 'rotateCredential', 'validateCredential', 'activateCredential', 'archiveCredential', 'deleteCredential']) {
  assert.match(apiSource, new RegExp(`${method}\\(`))
}
assert.doesNotMatch(credentialsPageSource, /private_key_encrypted|passphrase_encrypted|public_key_text|legacy_file_name/)
```

- [ ] **Step 2: Run contract test and verify failures**

```bash
cd frontend && node tests/_review/admin-monitoring-credentials-contract.test.mjs
```

Expected: FAIL for missing route/API/page.

- [ ] **Step 3: Add API methods and route/nav shells**

Use these paths:

```javascript
getCredentials(params)              // GET  /v1/monitoring/credentials/
getCredential(id)                   // GET  /v1/monitoring/credentials/:id/
createCredential(body)              // POST /v1/monitoring/credentials/
rotateCredential(id, body)          // POST /v1/monitoring/credentials/:id/rotate/
validateCredential(id, body)        // POST /v1/monitoring/credentials/:id/validate/
activateCredential(id, versionId)   // POST /v1/monitoring/credentials/:id/activate/
archiveCredential(id)               // POST /v1/monitoring/credentials/:id/archive/
deleteCredential(id)                // DELETE /v1/monitoring/credentials/:id/
```

Add route metadata identical to other monitoring pages and a key-shaped sidebar icon from existing inline path conventions. Add pure helpers for lifecycle/validation labels, status tones, metadata lines, and permission-based action visibility.

- [ ] **Step 4: Rerun contract and pure tests**

```bash
cd frontend && node tests/_review/admin-monitoring-credentials-contract.test.mjs && node tests/unit/monitoring-credential-state.test.mjs
```

Expected: PASS after a temporary `Credentials.vue` route shell exists; Task 13 replaces the shell.

- [ ] **Step 5: Commit navigation and contracts**

```bash
git add frontend/src/admin/api/monitoringStack.js frontend/src/admin/routes.js frontend/src/admin/layout/AdminSidebar.vue frontend/src/admin/pages/Monitoring/Credentials.vue frontend/src/admin/pages/Monitoring/credentials/credentialState.js frontend/tests/_review/admin-monitoring-credentials-contract.test.mjs frontend/src/admin/locales/en.json frontend/src/admin/locales/zh-CN.json
git commit -m "feat: add SSH credential center navigation"
```

### Task 13: Build the dedicated credential center UI

**Files:**
- Modify: `frontend/src/admin/pages/Monitoring/Credentials.vue`
- Create: `frontend/src/admin/pages/Monitoring/credentials/CredentialUploadModal.vue`
- Create: `frontend/src/admin/pages/Monitoring/credentials/CredentialDetailDrawer.vue`
- Create: `frontend/src/admin/pages/Monitoring/credentials/CredentialValidationPanel.vue`
- Modify: `frontend/src/admin/pages/Monitoring/credentials/credentialState.js`
- Modify: `frontend/tests/_review/admin-monitoring-credentials-contract.test.mjs`
- Create: `frontend/e2e/monitoring-credentials.spec.js`

- [ ] **Step 1: Write failing E2E scenarios with API interception**

Mock all credential APIs and assert:

```javascript
test('creates, reviews metadata, validates, and activates a credential', async ({ page }) => {
  await installCredentialApiMocks(page)
  await page.goto('/management/monitoring/credentials')
  await page.getByRole('button', { name: '新增凭据' }).click()
  await page.getByLabel('凭据名称').fill('生产环境')
  await page.getByLabel('私钥文件').setInputFiles(KEY_FIXTURE)
  await page.getByRole('button', { name: '解析密钥' }).click()
  await expect(page.getByText('SHA256:test-fingerprint')).toBeVisible()
  await page.getByRole('button', { name: '保存凭据' }).click()
  await expect(page.getByText('生产环境')).toBeVisible()
})

test('shows linked hosts instead of deleting a referenced credential', async ({ page }) => {
  await installCredentialApiMocks(page, { deleteConflict: true })
  await page.goto('/management/monitoring/credentials')
  await page.getByRole('row', { name: /生产环境/ }).click()
  await page.getByRole('button', { name: '删除' }).click()
  await expect(page.getByRole('link', { name: 'host-a' })).toBeVisible()
})

test('uses list rows on a mobile viewport without horizontal overflow', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await installCredentialApiMocks(page)
  await page.goto('/management/monitoring/credentials')
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)
  expect(overflow).toBe(false)
  await expect(page.getByTestId('credential-mobile-list')).toBeVisible()
})
```

- [ ] **Step 2: Run E2E and confirm the shell lacks the workflow**

```bash
cd frontend && npx playwright test e2e/monitoring-credentials.spec.js --project=chromium
```

Expected: FAIL at the missing create button/form.

- [ ] **Step 3: Implement the compact list and detail experience**

Desktop uses one unframed toolbar plus a compact table with name, fingerprint, algorithm, passphrase indicator, lifecycle, validation, host count, and updated time. Mobile switches to unframed rows with no nested cards. Row click opens the detail drawer; action menus are permission gated. Use a maximum 8px radius, restrained borders, existing `BaseButton`/modal/drawer patterns, no descriptive hero copy, no uppercase kicker, and no secret placeholders.

Detail drawer sections are associated hosts, version history, latest per-host validation, and audit history. Referenced delete conflicts render linked host names as navigation actions. Rotation creates a draft and keeps the old active version visibly marked until activation.

- [ ] **Step 4: Implement the three-stage upload/rotation flow**

Stage 1 collects name/file/optional passphrase in memory. Stage 2 submits to create/rotate and shows only returned parsed metadata. Stage 3 optionally selects existing hosts, submits validation, shows one result row per host, and enables activation only when the API reports eligible. Closing or completing clears file text and passphrase from component state; the component never stores secrets in localStorage, query params, emitted events, toast text, or console output.

- [ ] **Step 5: Run contract, E2E, and production build**

```bash
cd frontend && node tests/_review/admin-monitoring-credentials-contract.test.mjs
cd frontend && npx playwright test e2e/monitoring-credentials.spec.js --project=chromium
cd frontend && npm run build
```

Expected: all commands PASS.

- [ ] **Step 6: Commit the credential center UI**

```bash
git add frontend/src/admin/pages/Monitoring/Credentials.vue frontend/src/admin/pages/Monitoring/credentials/CredentialUploadModal.vue frontend/src/admin/pages/Monitoring/credentials/CredentialDetailDrawer.vue frontend/src/admin/pages/Monitoring/credentials/CredentialValidationPanel.vue frontend/src/admin/pages/Monitoring/credentials/credentialState.js frontend/tests/_review/admin-monitoring-credentials-contract.test.mjs frontend/e2e/monitoring-credentials.spec.js
git commit -m "feat: build monitoring SSH credential center"
```

### Task 14: Replace asset-page upload with credential selection

**Files:**
- Modify: `frontend/src/admin/pages/Monitoring/Assets.vue:400-500,1080-1140,1520-1600`
- Modify: `frontend/tests/_review/admin-monitoring-stack-contract.test.mjs`
- Modify: `frontend/e2e/monitoring-credentials.spec.js`
- Modify: `frontend/src/admin/locales/en.json`
- Modify: `frontend/src/admin/locales/zh-CN.json`

- [ ] **Step 1: Add failing asset contract and E2E assertions**

```javascript
assert.doesNotMatch(assetsSource, /handleSshKeyFile|uploadSshKey|sshKeyUploadContent|createSshKey/)
assert.match(assetsSource, /AdminMonitoringCredentials/)
assert.match(assetsSource, /sshKeyId/)
```

E2E must verify selecting a different credential resets the prior verification receipt, the save button remains blocked until connection testing succeeds, and "管理凭据" navigates to the dedicated route.

- [ ] **Step 2: Run contracts and confirm embedded-upload failures**

```bash
cd frontend && node tests/_review/admin-monitoring-stack-contract.test.mjs && node tests/_review/admin-monitoring-credentials-contract.test.mjs
```

Expected: FAIL while upload state/functions remain.

- [ ] **Step 3: Remove embedded secret handling and enrich selector metadata**

Delete upload name/content/loading state and handlers. Fetch active assignable credentials from `getCredentials({ status: 'active', assignable: true })`. Selector options show `name · algorithm · shortened fingerprint`; below it show validation/passphrase state for the selected item. Add an icon button/link to route `{ name: 'AdminMonitoringCredentials' }`. Disable key-based connection test with a precise inline field error when no assignable credential is selected.

- [ ] **Step 4: Run contracts, E2E, and build**

```bash
cd frontend && node tests/_review/admin-monitoring-stack-contract.test.mjs && node tests/_review/admin-monitoring-credentials-contract.test.mjs
cd frontend && npx playwright test e2e/monitoring-credentials.spec.js --project=chromium
cd frontend && npm run build
```

Expected: all commands PASS.

- [ ] **Step 5: Commit asset cleanup**

```bash
git add frontend/src/admin/pages/Monitoring/Assets.vue frontend/tests/_review/admin-monitoring-stack-contract.test.mjs frontend/e2e/monitoring-credentials.spec.js frontend/src/admin/locales/en.json frontend/src/admin/locales/zh-CN.json
git commit -m "refactor: select managed SSH credentials on assets"
```

### Task 15: Verify security, migrations, responsive UI, and deployment flow

**Files:**
- Modify only files required by failures found in this task.

- [ ] **Step 1: Run complete backend credential and account suites**

```bash
PYTHONPATH=backend .venv/bin/python -m pytest \
  backend/monitoring_stack/tests/test_credential_crypto.py \
  backend/monitoring_stack/tests/test_credential_ingestion.py \
  backend/monitoring_stack/tests/test_credential_runtime.py \
  backend/monitoring_stack/tests/test_credential_api.py \
  backend/monitoring_stack/tests/test_credential_migration.py \
  backend/monitoring_stack/tests/test_monitoring_stack_api.py \
  backend/monitoring_stack/tests/test_ansible_job_progress.py \
  backend/accounts/tests -q
```

Expected: all tests PASS.

- [ ] **Step 2: Run schema and secret-leak gates**

```bash
PYTHONPATH=backend .venv/bin/python backend/manage.py makemigrations --check --dry-run
PYTHONPATH=backend .venv/bin/python backend/manage.py check --deploy
rg -n "private_key_encrypted|passphrase_encrypted|public_key_text|legacy_file_name" frontend/src frontend/tests
```

Expected: no migration drift; no deployment errors; the `rg` command returns no frontend production-code matches (test deny-lists are acceptable and must be inspected).

- [ ] **Step 3: Run frontend contracts, E2E, and build**

```bash
cd frontend && node tests/unit/monitoring-credential-state.test.mjs
cd frontend && node tests/_review/admin-monitoring-credentials-contract.test.mjs
cd frontend && node tests/_review/admin-monitoring-stack-contract.test.mjs
cd frontend && npx playwright test e2e/monitoring-credentials.spec.js --project=chromium
cd frontend && npm run build
```

Expected: all commands PASS.

- [ ] **Step 4: Verify the real migration in dry-run mode before touching plaintext**

```bash
PYTHONPATH=backend .venv/bin/python backend/manage.py migrate_monitoring_ssh_credentials --dry-run
PYTHONPATH=backend .venv/bin/python backend/manage.py reencrypt_monitoring_credentials --dry-run
```

Expected: JSON summary reports the existing `zhangjiaqi` credential as migratable after CRLF normalization, reports no secret material, and makes no database/filesystem changes. Do not use `--remove-verified-plaintext` until the non-dry run has completed, decryptability/fingerprint verification succeeds, and the operator has reviewed the report.

- [ ] **Step 5: Inspect the real UI with Playwright at desktop and mobile widths**

Start or reuse the local application at `http://192.168.7.168:18080`, log in with the provided admin account, and inspect `/management/monitoring/credentials` and the Assets host form at `1398x986`, `1086x986`, and `390x844`. Verify no horizontal overflow, clipped drawers, nested-card clutter, stale passphrase values, or raw API errors. Capture screenshots to `output/monitoring-credentials-desktop.png` and `output/monitoring-credentials-mobile.png` without committing them.

- [ ] **Step 6: Run the repository verification gate**

```bash
PYTHONPATH=backend .venv/bin/python -m pytest \
  backend/accounts/tests \
  backend/jenkins_trigger/tests.py \
  backend/gitlab_resource/tests.py \
  backend/monitoring_stack/tests -q
cd frontend && npm run build
```

Expected: all relevant tests and build PASS. If unrelated pre-existing dirty GitLab files cause failures, record the exact failing tests and verify credential-specific suites independently; do not revert or stage those user changes.

- [ ] **Step 7: Audit the final diff without sweeping in existing work**

```bash
git status --short
git diff --check
git log --oneline d5b355b..HEAD
```

Expected: `git diff --check` is empty and the log contains the scoped commits from Tasks 1-14. Any verification correction must be returned to the task that owns the file, staged with that task's exact `git add` list, committed with `fix: harden monitoring SSH credential center`, and then all affected verification commands rerun. Never stage unrelated monitoring job-history or GitLab webhook changes already present in the worktree.

## Deployment Sequence

1. Generate a Fernet key and set `MONITORING_CREDENTIAL_ENCRYPTION_KEYS=primary:<key>` on web and worker processes before migration.
2. Deploy code and run `python backend/manage.py migrate`.
3. Run `migrate_monitoring_ssh_credentials --dry-run`, review the JSON report, then run it without `--dry-run` while retaining plaintext.
4. Confirm every active credential decrypts and its public fingerprint matches; exercise one connection test and one asynchronous install.
5. Run `migrate_monitoring_ssh_credentials --remove-verified-plaintext` only after the report shows no failures.
6. During future key rotation, prepend the new key, run `reencrypt_monitoring_credentials` until `remaining_old_key_envelopes` is zero, then remove the old key from all processes.

## Acceptance Traceability

- CRLF normalization and the existing `zhangjiaqi` migration: Tasks 4 and 9.
- Encrypted/passphrase-protected storage and no fallback: Tasks 1, 4, and 5.
- Shared OpenSSH path for tests and installs: Task 6.
- Metadata-only API/UI and secret redaction: Tasks 6, 8, 13, and 15.
- Version rotation, all-host validation, atomic activation: Task 7.
- Referential archive/delete and retention: Tasks 7 and 8.
- Four operation permissions and superuser behavior: Tasks 2, 8, and 11.
- Immutable audit trail and sanitized metadata: Tasks 3 and 7.
- Missing-key health and dual-key recovery: Task 10.
- Dedicated responsive credential center and selector-only Assets form: Tasks 12-14.
