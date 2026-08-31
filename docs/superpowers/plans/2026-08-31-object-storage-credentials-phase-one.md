# 对象存储凭证一期实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 HyperOps 内实现一个测试企业、一个阿里云 OSS 资源池下的对象存储凭证自助申请闭环。

**Architecture:** 新增独立的 `object_storage` Django App，不改造 `monitoring_stack`。对象存储模块拥有自己的企业、成员、Bucket、RAM 用户、AccessKey、申请单和审计模型；通过 Provider 接口隔离阿里云 SDK。HTTP 接口只创建申请单，Celery Worker 执行云端变更，并使用数据库中的加密密文保存 Secret。

**Tech Stack:** Django 5.1、Django REST Framework、PostgreSQL、Celery 5.3、Redis、Vue 3、Vue Router、Tailwind CSS、`cryptography` AES-GCM/HKDF、Alibaba Cloud RAM/OSS SDK。

**Source spec:** [`docs/superpowers/specs/2026-08-31-object-storage-credentials-phase-one-design.zh-CN.md`](../specs/2026-08-31-object-storage-credentials-phase-one-design.zh-CN.md)

---

## 0. 实施边界与现有代码映射

### 已有能力

- `backend/accounts/models.py`：全局 Django User、Profile、Role。
- `backend/accounts/access.py`：现有 feature manifest 和角色能力计算。
- `backend/accounts/views/oauth.py`：现有 OAuth 回调和 JWT 生成逻辑。
- `backend/core/settings/base.py`：`INSTALLED_APPS`、模块开关、`SECRET_KEY`。
- `backend/core/celery.py`：Celery 初始化、请求 ID 传递和 task 日志上下文。
- `backend/core/management/commands/register_periodic_tasks.py`：定时任务注册。
- `backend/core/logging.py` 和 `docs/logging.md`：日志格式及脱敏规则。
- `frontend/src/router/index.js`：员工端路由和鉴权守卫。
- `frontend/src/admin/routes.js`、`frontend/src/admin/layout/AdminSidebar.vue`：管理端路由和侧边栏。

### 新增文件边界

```text
backend/object_storage/
├── __init__.py
├── apps.py
├── models.py
├── admin.py
├── urls.py
├── serializers.py
├── permissions.py
├── feishu.py
├── crypto.py
├── providers/
│   ├── __init__.py
│   ├── base.py
│   └── aliyun.py
├── services/
│   ├── __init__.py
│   ├── audit.py
│   ├── naming.py
│   ├── policy.py
│   ├── credentials.py
│   ├── applications.py
│   └── tenant.py
├── tasks.py
├── periodic_tasks.py
├── management/commands/reencrypt_object_storage_secrets.py
├── migrations/
└── tests/
```

```text
frontend/src/
├── api/objectStorage.js
├── pages/ObjectStorage/
│   ├── Overview.vue
│   ├── Buckets.vue
│   ├── Credentials.vue
│   └── Applications.vue
├── admin/pages/ObjectStorage/
│   ├── Overview.vue
│   ├── EnterpriseAccess.vue
│   ├── Resources.vue
│   ├── Tasks.vue
│   └── Audit.vue
└── admin/components/ObjectStorageNav.vue
```

### 0.1 计划执行规则

- 每个任务先写一个能描述失败行为的测试，再写最小实现。
- 每个任务完成后运行任务内的精确测试，再创建独立提交。
- 不修改 Jenkins、GitLab、Monitoring 既有业务行为。
- 先实现一个企业和阿里云 Provider；不提前加入华为云、通知、TOTP 或归档。

---

## Task 1: 建立模块骨架、开关和权限入口

**Files:**
- Create: `backend/object_storage/apps.py`
- Create: `backend/object_storage/__init__.py`
- Create: `backend/object_storage/urls.py`
- Create: `backend/object_storage/tests/test_module_contract.py`
- Modify: `backend/core/settings/base.py`
- Modify: `backend/core/urls.py`
- Modify: `backend/accounts/access.py`
- Modify: `README.md`
- Modify: `frontend/src/router/index.js`
- Modify: `frontend/src/admin/routes.js`
- Modify: `frontend/src/admin/layout/AdminSidebar.vue`
- Modify: `frontend/src/store/user.js` or the existing module-flag source used by `loadPlatformFlags()`

- [ ] **Step 1: Write the failing contract test**

```python
def test_object_storage_module_is_disabled_by_default(settings):
    assert settings.ENABLE_OBJECT_STORAGE is False


def test_object_storage_urls_are_not_registered_when_disabled(client):
    response = client.get('/api/v1/object-storage/overview/')
    assert response.status_code == 404
```

- [ ] **Step 2: Run the contract test and verify it fails because the module does not exist.**

Run: `PYTHONPATH=backend .venv/bin/python -m pytest backend/object_storage/tests/test_module_contract.py -q`

Expected: FAIL because the new app, setting, and route are not defined.

- [ ] **Step 3: Add the disabled module and access metadata.**

Add `ENABLE_OBJECT_STORAGE = env_flag('ENABLE_OBJECT_STORAGE', False)` to
`backend/core/settings/base.py`. Add `object_storage` to `INSTALLED_APPS` only
when the flag is enabled, append its URL include only when enabled, and add an
`admin_object_storage` feature plus employee `object_storage` feature metadata
to `backend/accounts/access.py`. Add route metadata with both
`requiresAuth` and `requiresModuleFlag: 'enable_object_storage'`.

The module URL file must expose a harmless authenticated contract endpoint so
the contract can verify routing without introducing business behavior:

```python
urlpatterns = [
    path('overview/', ObjectStorageOverviewView.as_view(), name='overview'),
]
```

The contract view returns `503` with a stable `OBJECT_STORAGE_DISABLED`
domain response when the feature is not enabled.

- [ ] **Step 4: Add the frontend parent entries with no visible route when disabled.**

Add employee and administration route groups guarded by the module flag. Add
navigation labels through both locale files. Superuser-only checks remain in
the API; the sidebar must not be treated as authorization.

- [ ] **Step 5: Run the contract and existing access tests.**

Run: `PYTHONPATH=backend .venv/bin/python -m pytest backend/object_storage/tests/test_module_contract.py backend/accounts/tests/test_access_profile.py -q`

Expected: PASS.

- [ ] **Step 6: Commit the module boundary.**

```bash
git add backend/object_storage backend/core/settings/base.py backend/core/urls.py backend/accounts/access.py README.md frontend/src/router/index.js frontend/src/admin/routes.js frontend/src/admin/layout/AdminSidebar.vue frontend/src/store/user.js frontend/src/admin/locales
git commit -m "feat: add object storage module boundary"
```

---

## Task 2: 实现数据库密文信封和密钥迁移命令

**Files:**
- Create: `backend/object_storage/crypto.py`
- Create: `backend/object_storage/management/commands/reencrypt_object_storage_secrets.py`
- Create: `backend/object_storage/tests/test_crypto.py`
- Modify: `backend/object_storage/tests/test_module_contract.py`
- Modify: `backend/core/settings/base.py`

- [ ] **Step 1: Write tests for derivation, authenticated encryption, and root-secret migration.**

```python
def test_encrypt_secret_round_trips_with_derived_object_storage_key(settings):
    settings.SECRET_KEY = 'stable-test-root-secret'
    envelope = encrypt_secret('secret-value')
    assert envelope.startswith('v1:aesgcm:')
    assert decrypt_secret(envelope) == 'secret-value'
    assert envelope != encrypt_secret('secret-value')


def test_tampered_ciphertext_is_rejected(settings):
    envelope = encrypt_secret('secret-value')
    tampered = envelope[:-1] + ('0' if envelope[-1] != '0' else '1')
    with pytest.raises(SecretDecryptionError):
        decrypt_secret(tampered)


def test_reencrypt_command_rewraps_all_object_storage_secrets(monkeypatch):
    # The command reads old and new root material from protected stdin prompts,
    # never from argv, and updates only object-storage envelopes.
    from io import StringIO

    result = call_command(
        'reencrypt_object_storage_secrets',
        stdin=StringIO('old-root\\nnew-root\\n'),
        confirm=True,
    )
    assert result.updated_count == 3
```

- [ ] **Step 2: Run the crypto tests and confirm the missing implementation failure.**

Run: `PYTHONPATH=backend .venv/bin/python -m pytest backend/object_storage/tests/test_crypto.py -q`

Expected: FAIL because `crypto.py` and its public functions are absent.

- [ ] **Step 3: Implement AES-GCM envelopes.**

Use `HKDF(SHA256)` with a fixed context such as
`b'hyperops/object-storage/v1'` to derive a 32-byte AES key from
`settings.SECRET_KEY`. Generate a fresh 12-byte nonce per value. Encode the
version, algorithm, nonce, and ciphertext in a strict parseable envelope:

```text
v1:aesgcm:<base64url nonce>:<base64url ciphertext>
```

Expose only:

```python
def encrypt_secret(value: str) -> str:
    """Return a versioned authenticated ciphertext envelope."""


def decrypt_secret(envelope: str) -> str:
    """Return the plaintext or raise SecretDecryptionError."""


def is_secret_envelope(value: str) -> bool:
    """Return whether value matches the supported envelope grammar."""
```

Reject malformed envelopes, unsupported versions, authentication failures, and
default/empty root secrets. Never log plaintext or envelope values.

- [ ] **Step 4: Implement the re-encryption command.**

The command must:

- Prompt for old and new root secrets without echoing input.
- Lock and process object-storage secret rows in batches.
- Re-encrypt Feishu, Alibaba management, and employee AK/SK fields.
- Abort without deleting or overwriting a row when any old envelope fails.
- Print only counts and identifiers, never values.
- Require an explicit `--confirm` before writing.

- [ ] **Step 5: Run crypto tests and static checks.**

Run: `PYTHONPATH=backend .venv/bin/python -m pytest backend/object_storage/tests/test_crypto.py -q`

Expected: PASS.

Run: `black --check backend/object_storage/crypto.py backend/object_storage/management/commands/reencrypt_object_storage_secrets.py`

Expected: PASS.

- [ ] **Step 6: Commit the crypto boundary.**

```bash
git add backend/object_storage/crypto.py backend/object_storage/management backend/object_storage/tests/test_crypto.py backend/core/settings/base.py
git commit -m "feat: protect object storage secrets with encrypted envelopes"
```

---

## Task 3: 建立企业、成员和云资源数据模型

**Files:**
- Create: `backend/object_storage/models.py`
- Create: `backend/object_storage/admin.py`
- Create: `backend/object_storage/tests/test_models.py`
- Create: `backend/object_storage/migrations/0001_initial.py`
- Modify: `backend/object_storage/apps.py`

- [ ] **Step 1: Write model and constraint tests.**

Cover these exact constraints:

```python
def test_storage_membership_is_unique_by_tenant_and_feishu_open_id(db):
    """Creating the same tenant/open_id pair raises IntegrityError."""


def test_storage_pool_has_one_active_aliyun_pool_per_tenant(db):
    """A second enabled Alibaba pool for one tenant is rejected."""


def test_bucket_is_unique_by_resource_pool_and_name(db):
    """The same pool/name pair cannot be registered twice."""


def test_one_membership_has_one_cloud_identity_per_pool(db):
    """A member cannot get two RAM identities in one pool."""


def test_application_idempotency_key_is_unique_per_applicant_and_tenant(db):
    """A duplicate mutation key resolves to the first application."""


def test_audit_event_is_immutable(db):
    """Updating an existing audit event raises the domain immutability error."""
```

- [ ] **Step 2: Run model tests and verify they fail before models exist.**

Run: `PYTHONPATH=backend .venv/bin/python -m pytest backend/object_storage/tests/test_models.py -q`

Expected: FAIL with import/model errors.

- [ ] **Step 3: Implement models and explicit tenant fields.**

Create these models and required fields from the approved spec:

- `StorageTenant`: code, name, enabled, naming template/version, quota default
  5, delivery lifetime default 86400 seconds.
- `FeishuAppConfig`: tenant one-to-one, app ID, encrypted app secret, callback,
  validation and enabled state.
- `StorageMembership`: tenant, Django user, open ID, union ID, profile snapshot,
  active state and timestamps.
- `StorageResourcePool`: tenant, provider, cloud account ID, region, encrypted
  management credentials, fingerprint, validation and enabled state.
- `StorageCloudIdentity`: tenant, membership, pool, RAM user ID/name and state.
- `StorageBucket`: tenant, pool, owner membership, cloud identity, rendered name,
  project, environment, purpose, template version, cloud marker and state.
- `StorageAccessKey`: tenant, cloud identity, encrypted AK/SK, fingerprint,
  last four, cloud/local states and timestamps.
- `StorageApplication`, `StorageApplicationAttempt`,
  `StorageApplicationEvent`, `StorageDeliveryTicket`, and immutable
  `StorageAuditEvent`.

All foreign keys and indexes must include the access path needed for tenant and
owner filtering. Store no plaintext Secret field.

- [ ] **Step 4: Add migrations, admin registrations, and test fixtures.**

Register only non-secret metadata in Django admin. Do not expose encrypted
fields as editable values. Add `factory` helpers under
`backend/object_storage/tests/conftest.py` for a tenant, membership, resource
pool, and bucket.

- [ ] **Step 5: Run migrations and model tests.**

Run: `PYTHONPATH=backend .venv/bin/python manage.py makemigrations --check object_storage`

Expected: no pending model changes.

Run: `PYTHONPATH=backend .venv/bin/python -m pytest backend/object_storage/tests/test_models.py -q`

Expected: PASS.

- [ ] **Step 6: Commit the schema.**

```bash
git add backend/object_storage/models.py backend/object_storage/admin.py backend/object_storage/migrations backend/object_storage/tests
git commit -m "feat: add object storage resource models"
```

---

## Task 4: 实现企业上下文、飞书登录和即时开户

**Files:**
- Create: `backend/object_storage/feishu.py`
- Create: `backend/object_storage/services/tenant.py`
- Create: `backend/object_storage/views_auth.py`
- Create: `backend/object_storage/tests/test_feishu_auth.py`
- Modify: `backend/object_storage/urls.py`
- Modify: `backend/accounts/models.py` only if an existing profile flag is required for unusable-password JIT users
- Modify: `backend/accounts/views/oauth.py` only to reuse the shared token/session helper

- [ ] **Step 1: Write auth tests for tenant-bound state and JIT provisioning.**

```python
def test_feishu_callback_rejects_unknown_or_expired_state(client):
    """Unknown, reused, and expired state values return the auth error."""


def test_feishu_callback_creates_one_unusable_password_user(db):
    """A first callback creates a non-staff user with an unusable password."""


def test_same_tenant_and_open_id_is_idempotent(db):
    """Repeated callbacks reuse one membership and one local user."""


def test_same_open_id_in_another_tenant_creates_a_distinct_user(db):
    """The same open_id under another tenant remains a separate identity."""


def test_feishu_name_email_never_merges_existing_local_user(db):
    """Matching display attributes never attach to an existing local user."""


def test_disabled_tenant_or_app_rejects_login(client):
    """Disabled tenant or Feishu app prevents provisioning."""
```

- [ ] **Step 2: Run tests and verify the expected missing-auth failure.**

Run: `PYTHONPATH=backend .venv/bin/python -m pytest backend/object_storage/tests/test_feishu_auth.py -q`

Expected: FAIL because state storage, Feishu client, and views are absent.

- [ ] **Step 3: Implement server-side Feishu OAuth state.**

Add start and callback routes under `/api/v1/object-storage/auth/feishu/`.
Generate a random one-time state bound to the enabled tenant app config, store
only its digest with expiry and callback metadata, and reject any mismatch,
reuse, or expiry. The callback must derive the tenant from stored state, never
from a frontend query parameter.

Use a small provider client in `feishu.py` that exchanges the code and retrieves
the open ID, optional union ID, display name, department snapshot, and active
status. Provider errors become safe domain error codes.

- [ ] **Step 4: Implement JIT local-user provisioning.**

In a transaction:

1. Lock the `StorageTenant` and look up `(tenant, open_id)`.
2. Reuse the existing Django user if the membership exists.
3. Otherwise create a username from a stable tenant/open ID hash, call
   `set_unusable_password()`, set `is_staff=False` and `is_superuser=False`,
   create the restricted membership, and assign the system `Object Storage User`
   role whose only visible feature is `object_storage`.
4. Do not match or merge by name, email, or phone.
5. Refuse disabled tenant, disabled app, inactive Feishu identity, or a failed
   enterprise eligibility check.

The JIT user test must assert that `object_storage` is visible while
`workspace_dashboard`, `admin_monitoring`, Jenkins, GitLab, and user-management
features are not visible. The system role is created or updated by an explicit
data migration and is not exposed as an administrator-selected elevated role.

Return a short-lived one-time frontend handoff code rather than access tokens in
the URL. Add an exchange endpoint that consumes the code and returns the normal
HyperOps access/refresh token response. Do not place Feishu tokens, app secrets,
or provider payloads in logs.

- [ ] **Step 5: Run auth tests and existing account tests.**

Run: `PYTHONPATH=backend .venv/bin/python -m pytest backend/object_storage/tests/test_feishu_auth.py backend/accounts/tests -q`

Expected: PASS.

- [ ] **Step 6: Commit authentication.**

```bash
git add backend/object_storage backend/accounts/models.py backend/accounts/views/oauth.py
git commit -m "feat: provision object storage users from Feishu"
```

---

## Task 5: 实现企业接入配置和阿里云 Provider

**Files:**
- Create: `backend/object_storage/providers/base.py`
- Create: `backend/object_storage/providers/aliyun.py`
- Create: `backend/object_storage/services/provider_errors.py`
- Create: `backend/object_storage/views_admin.py`
- Create: `backend/object_storage/serializers_admin.py`
- Create: `backend/object_storage/tests/test_aliyun_provider.py`
- Create: `backend/object_storage/tests/test_admin_config_api.py`
- Modify: `pyproject.toml`
- Modify: `backend/object_storage/urls.py`

- [ ] **Step 1: Write provider contract tests with sanitized responses.**

```python
def test_validate_management_identity_returns_safe_capabilities():
    """Validation returns capabilities without returning management secrets."""


def test_create_bucket_uses_fixed_region_and_platform_defaults():
    """Bucket creation uses pool region and platform security defaults."""


def test_existing_bucket_is_reported_as_name_conflict():
    """An existing cloud name maps to BUCKET_NAME_CONFLICT."""


def test_bucket_empty_check_rejects_objects_versions_and_multipart_uploads():
    """Any object, version, marker, or incomplete upload blocks release."""


def test_object_policy_contains_only_owned_bucket_arns():
    """The generated policy resources equal the owned active bucket ARNs."""


def test_provider_errors_map_to_stable_domain_codes():
    """SDK exceptions become safe domain errors without provider text leakage."""
```

- [ ] **Step 2: Run tests and verify the provider contract is red.**

Run: `PYTHONPATH=backend .venv/bin/python -m pytest backend/object_storage/tests/test_aliyun_provider.py -q`

Expected: FAIL because provider boundary and SDK dependency are absent.

- [ ] **Step 3: Add pinned Alibaba SDK dependencies and provider interface.**

Add the selected Alibaba Cloud RAM and OSS SDK packages to `pyproject.toml`.
The interface in `providers/base.py` must define business operations only:

```python
class ObjectStorageProvider(Protocol):
    def validate_management_identity(self, pool):
        """Return safe management capabilities."""

    def find_or_create_personal_principal(self, identity):
        """Return the deterministic RAM principal."""

    def create_owned_bucket(self, bucket):
        """Create one bucket in the configured region."""

    def inspect_bucket_emptiness(self, bucket):
        """Return whether the bucket has no objects or pending uploads."""

    def delete_owned_bucket(self, bucket):
        """Delete one verified empty bucket."""

    def reconcile_object_policy(self, identity, buckets):
        """Apply the exact desired object policy."""

    def list_access_keys(self, identity):
        """Return safe metadata for the principal's keys."""

    def create_access_key(self, identity):
        """Create and return a new key pair exactly once."""

    def deactivate_access_key(self, key):
        """Deactivate one exact cloud key."""

    def delete_access_key(self, key):
        """Delete one exact cloud key after confirmation."""
```

The concrete Alibaba adapter owns SDK clients, timeouts, request IDs, pagination,
provider error mapping, and safe response conversion. No raw SDK object or
exception text crosses the service boundary.

- [ ] **Step 4: Implement enterprise and resource-pool administration APIs.**

Only `is_superuser=True` may access these APIs. Create/update responses return
fingerprints, last four characters, validation status, and safe metadata; never
return decrypted values. Enabling a Feishu app or Alibaba pool requires a
successful validation action. Enforce one enabled Alibaba pool per tenant.

- [ ] **Step 5: Run provider and administration tests.**

Run: `PYTHONPATH=backend .venv/bin/python -m pytest backend/object_storage/tests/test_aliyun_provider.py backend/object_storage/tests/test_admin_config_api.py -q`

Expected: PASS.

- [ ] **Step 6: Commit provider and configuration.**

```bash
git add pyproject.toml backend/object_storage/providers backend/object_storage/services/provider_errors.py backend/object_storage/views_admin.py backend/object_storage/serializers_admin.py backend/object_storage/tests
git commit -m "feat: add Alibaba object storage provider"
```

---

## Task 6: 实现命名模板、配额和声明式权限策略

**Files:**
- Create: `backend/object_storage/services/naming.py`
- Create: `backend/object_storage/services/policy.py`
- Create: `backend/object_storage/tests/test_naming.py`
- Create: `backend/object_storage/tests/test_policy.py`
- Modify: `backend/object_storage/models.py` if validation fields need database-level constraints

- [ ] **Step 1: Write naming, quota, and policy tests.**

```python
def test_render_bucket_name_normalizes_values_and_is_deterministic():
    """Equal tenant/member/fields produce the same normalized name."""


def test_unknown_template_variable_is_rejected():
    """A template containing an unallowlisted variable raises validation error."""


def test_rendered_name_is_between_3_and_63_characters():
    """Rendered output stays within the shared OSS naming bounds."""


def test_quota_counts_active_and_releasing_buckets_only():
    """Released and failed rows do not consume the configured quota."""


def test_policy_resources_equal_current_owned_active_buckets():
    """The desired policy has exactly the active owned bucket resources."""


def test_policy_never_contains_bucket_delete_or_acl_actions():
    """Policy actions exclude bucket administration and ACL mutation."""
```

- [ ] **Step 2: Run tests and verify they fail before services exist.**

Run: `PYTHONPATH=backend .venv/bin/python -m pytest backend/object_storage/tests/test_naming.py backend/object_storage/tests/test_policy.py -q`

Expected: FAIL because naming and policy services are absent.

- [ ] **Step 3: Implement safe per-enterprise naming.**

Allow only `{tenant}`, `{user}`, `{project}`, `{environment}`, `{purpose}`, and
`{suffix}`. Normalize to lowercase ASCII-safe slugs, collapse separators, and
append a stable hash derived from tenant, member, and normalized business
fields. Validate the final 3-63 character output before the application is
created. Save the template version and rendered result on `StorageBucket`.

- [ ] **Step 4: Implement quota and policy generation.**

Use a locked membership transaction for quota checks. Generate a desired policy
from the exact current set of active owned buckets. The policy allows object
list/read/write/overwrite/delete/multipart actions within those bucket ARNs and
denies bucket administration, public access, cross-bucket access, and unrelated
cloud services through omission and provider-specific safe defaults.

- [ ] **Step 5: Run service tests.**

Run: `PYTHONPATH=backend .venv/bin/python -m pytest backend/object_storage/tests/test_naming.py backend/object_storage/tests/test_policy.py -q`

Expected: PASS.

- [ ] **Step 6: Commit domain helpers.**

```bash
git add backend/object_storage/services/naming.py backend/object_storage/services/policy.py backend/object_storage/tests
git commit -m "feat: enforce object storage naming and access policy"
```

---

## Task 7: 实现申请单、幂等、异步执行和补偿

**Files:**
- Create: `backend/object_storage/services/applications.py`
- Create: `backend/object_storage/services/credentials.py`
- Create: `backend/object_storage/services/audit.py`
- Create: `backend/object_storage/tasks.py`
- Create: `backend/object_storage/periodic_tasks.py`
- Create: `backend/object_storage/tests/test_application_service.py`
- Create: `backend/object_storage/tests/test_tasks.py`
- Modify: `backend/object_storage/models.py` if state indexes need tuning
- Modify: `backend/core/settings/celery.py`

- [ ] **Step 1: Write application state and failure-injection tests.**

Cover these exact flows:

```python
def test_first_application_creates_principal_bucket_policy_and_key():
    """The first application creates all required resources in stage order."""


def test_additional_bucket_reuses_principal_and_active_keys():
    """An additional bucket changes policy but does not issue a key."""


def test_duplicate_idempotency_key_returns_existing_application():
    """Repeated mutation submission returns the original application ID."""


def test_bucket_timeout_rechecks_cloud_before_retrying():
    """A timeout performs exact-name reconciliation before creating again."""


def test_policy_failure_does_not_issue_a_key():
    """Policy failure preserves resources and prevents key creation."""


def test_encryption_failure_deletes_the_exact_new_key():
    """Encryption failure compensates the key created by this attempt only."""


def test_key_delete_success_create_failure_preserves_remaining_key():
    """Rotation failure never deletes the second existing key."""


def test_transient_provider_failure_retries_three_times():
    """Transient provider errors receive at most three backoff retries."""


def test_business_error_enters_manual_required_without_retry():
    """Permission, conflict, and configuration errors require manual recovery."""
```

- [ ] **Step 2: Run tests and verify the missing-service failure.**

Run: `PYTHONPATH=backend .venv/bin/python -m pytest backend/object_storage/tests/test_application_service.py backend/object_storage/tests/test_tasks.py -q`

Expected: FAIL because orchestration services and tasks are absent.

- [ ] **Step 3: Implement application creation and employee-facing state.**

Create one application per mutation with stable action types:

```text
FIRST_BUCKET_AND_CREDENTIAL
ADD_BUCKET
ROTATE_CREDENTIAL
RELEASE_BUCKET
SUSPEND_MEMBERSHIP
REACTIVATE_MEMBERSHIP
```

Use `(tenant, applicant, idempotency_key)` to return an existing application on
duplicate submission. Keep employee-visible statuses limited to `PENDING`,
`RUNNING`, `DELIVERY_READY`, `SUCCEEDED`, `FAILED`, `MANUAL_REQUIRED`, and
`CANCELLED`; store technical stages in application events.

- [ ] **Step 4: Implement the Celery workflow with locks and reconciliation.**

The worker must lock the application and relevant membership/cloud identity,
re-read cloud state before each mutation, and create an attempt record. Use the
existing request/task logging context and a dedicated low-concurrency queue.

Implement exact stage ordering for first application:

```text
IDENTITY_CHECKING → QUOTA_CHECKING → BUCKET_CREATING
→ PRINCIPAL_BINDING → POLICY_APPLYING → KEY_CREATING
→ SECRET_ENCRYPTING → DELIVERY_CREATING
```

Use three exponential-backoff retries only for timeout, rate limit, temporary
network, and service-unavailable errors. Map all other errors to safe domain
codes and `MANUAL_REQUIRED` where operator action is required.

- [ ] **Step 5: Implement audit and periodic cleanup.**

`audit.py` records immutable events with tenant, actor, application, target,
reason, request ID, IP, safe result, and timestamp. Add a periodic task that
deletes audit rows older than 30 days and logs only the time range and count.
Do not delete applications, attempts, buckets, keys, or memberships.

- [ ] **Step 6: Run task tests and logging tests.**

Run: `PYTHONPATH=backend .venv/bin/python -m pytest backend/object_storage/tests/test_application_service.py backend/object_storage/tests/test_tasks.py backend/core/tests_logging.py -q`

Expected: PASS.

- [ ] **Step 7: Commit orchestration.**

```bash
git add backend/object_storage/services backend/object_storage/tasks.py backend/object_storage/periodic_tasks.py backend/object_storage/tests backend/core/settings/celery.py
git commit -m "feat: orchestrate object storage applications asynchronously"
```

---

## Task 8: 实现凭证交付、轮换、释放和用户停用 API

**Files:**
- Create: `backend/object_storage/serializers.py`
- Create: `backend/object_storage/permissions.py`
- Create: `backend/object_storage/views_employee.py`
- Create: `backend/object_storage/tests/test_employee_api.py`
- Create: `backend/object_storage/tests/test_credential_delivery.py`
- Modify: `backend/object_storage/urls.py`

- [ ] **Step 1: Write API and security tests.**

```python
def test_employee_can_only_list_owned_buckets(client, another_member):
    """The response excludes buckets owned by another member."""


def test_employee_cannot_read_another_members_credential(client):
    """Cross-owner credential access returns not found."""


def test_delivery_ticket_is_single_use_and_no_store(client):
    """The first delivery succeeds and the second returns a consumed error."""


def test_delivery_ticket_uses_enterprise_expiry_range(client):
    """Ticket expiry uses the configured bounded enterprise lifetime."""


def test_superuser_reveal_requires_reason_and_returns_one_key(client):
    """A non-empty reason is required for one-record reveal."""


def test_non_superuser_cannot_reveal_secret(client):
    """A normal user receives forbidden without a secret payload."""


def test_rotation_with_two_active_keys_proposes_oldest_key(client):
    """Two active keys produce an oldest-key proposal using safe metadata."""


def test_nonempty_bucket_release_is_rejected(client):
    """A bucket containing data or pending uploads cannot be released."""


def test_suspended_member_cannot_apply_or_retrieve(client):
    """Suspended members cannot mutate resources or retrieve credentials."""
```

- [ ] **Step 2: Run tests and verify missing API behavior.**

Run: `PYTHONPATH=backend .venv/bin/python -m pytest backend/object_storage/tests/test_employee_api.py backend/object_storage/tests/test_credential_delivery.py -q`

Expected: FAIL because serializers, permissions, views, and routes are absent.

- [ ] **Step 3: Implement tenant/owner permission helpers and separate serializers.**

Employee querysets must filter by active membership and owner. Cross-tenant and
cross-owner IDs return `404`. Administration querysets require
`request.user.is_superuser`. Never serialize encrypted fields to list/detail
responses.

- [ ] **Step 4: Implement one-time employee delivery and controlled reveal.**

Store only a digest of the delivery token. Enforce enterprise-configured expiry
between 10 minutes and 7 days, defaulting to 24 hours. Consume the ticket in a
transaction before returning AK/SK. Set `Cache-Control: no-store`, disable
content caching, and omit the secret from logs and error reporting.

Superuser reveal requires a non-empty reason, applies to exactly one key, emits
an audit event, and is never available through list, bulk, export, or employee
serializers. Keep a dedicated service function so TOTP can be added later.

- [ ] **Step 5: Implement key rotation and release endpoints.**

Rotation follows the confirmed one/two-key rule. With two keys, prioritize
inactive keys, otherwise the oldest active key, show only safe metadata, and
require confirmation before deletion. Release verifies the bucket is empty
including versions, delete markers, and incomplete multipart uploads before the
worker deletes it and reconciles policy.

- [ ] **Step 6: Implement suspension and reactivation.**

Suspension creates a task to deactivate all keys and blocks employee APIs.
Reactivation restores workspace access but never reactivates old keys; a new
credential must be issued.

- [ ] **Step 7: Run API tests and commit.**

Run: `PYTHONPATH=backend .venv/bin/python -m pytest backend/object_storage/tests/test_employee_api.py backend/object_storage/tests/test_credential_delivery.py -q`

Expected: PASS.

```bash
git add backend/object_storage/serializers.py backend/object_storage/permissions.py backend/object_storage/views_employee.py backend/object_storage/urls.py backend/object_storage/tests
git commit -m "feat: add object storage credential and bucket APIs"
```

---

## Task 9: 实现管理端 API 和配置校验

**Files:**
- Create: `backend/object_storage/views_admin.py` or split the existing admin views into resource-specific modules
- Create: `backend/object_storage/tests/test_admin_resources_api.py`
- Modify: `backend/object_storage/serializers_admin.py`
- Modify: `backend/object_storage/urls.py`

- [ ] **Step 1: Write tests for superuser-only resource and task operations.**

```python
def test_only_superuser_can_list_all_tenants(client, normal_user):
    """Only a superuser can use cross-tenant administration queries."""


def test_admin_can_suspend_member_without_deleting_bucket_data(client):
    """Suspension schedules key deactivation and preserves bucket rows."""


def test_admin_can_retry_manual_required_application(client):
    """A superuser can create a new attempt for a manual-recovery application."""


def test_admin_secret_reveal_audits_reason_and_safe_key_metadata(client):
    """Reveal returns one secret and writes only safe audit metadata."""


def test_admin_responses_never_include_ciphertext(client):
    """List and detail responses never expose database ciphertext."""
```

- [ ] **Step 2: Run tests and verify missing admin endpoint behavior.**

Run: `PYTHONPATH=backend .venv/bin/python -m pytest backend/object_storage/tests/test_admin_resources_api.py -q`

Expected: FAIL because resource/task administration endpoints are incomplete.

- [ ] **Step 3: Implement management endpoints.**

Provide separate endpoints for:

- Tenant and Feishu/Alibaba configuration.
- Connection validation and enable/disable.
- Buckets, RAM users, and access-key summaries.
- Member suspension/reactivation.
- Application list, attempts, safe events, retry, and manual resolution.
- Reason-required single-key reveal.
- Audit search with 30-day filters.

All mutation endpoints require idempotency keys. Provider exception text is
converted to stable safe error codes before response or log output.

- [ ] **Step 4: Run admin API tests and commit.**

Run: `PYTHONPATH=backend .venv/bin/python -m pytest backend/object_storage/tests/test_admin_resources_api.py -q`

Expected: PASS.

```bash
git add backend/object_storage/views_admin.py backend/object_storage/serializers_admin.py backend/object_storage/urls.py backend/object_storage/tests
git commit -m "feat: add object storage administration APIs"
```

---

## Task 10: 实现员工端对象存储工作区

**Files:**
- Create: `frontend/src/api/objectStorage.js`
- Create: `frontend/src/pages/ObjectStorage/Overview.vue`
- Create: `frontend/src/pages/ObjectStorage/Buckets.vue`
- Create: `frontend/src/pages/ObjectStorage/Credentials.vue`
- Create: `frontend/src/pages/ObjectStorage/Applications.vue`
- Create: `frontend/src/components/layout/ObjectStorageNav.vue`
- Modify: `frontend/src/router/index.js`
- Modify: `frontend/src/components/layout/AppSidebar.vue`
- Modify: `frontend/src/locales/en.json`
- Modify: `frontend/src/locales/zh-CN.json`
- Create: `frontend/tests/_review/object-storage-employee-contract.test.mjs`

- [ ] **Step 1: Write the frontend route and information-architecture contract.**

```js
assert.match(source, /path:\s*['"]\/object-storage['"]/)
assert.match(source, /Overview|Buckets|Credentials|Applications/)
assert.doesNotMatch(source, /monitoring_stack|BaseModal.*application/)
```

- [ ] **Step 2: Run the contract and verify the routes/components are absent.**

Run: `node frontend/tests/_review/object-storage-employee-contract.test.mjs`

Expected: FAIL because the new employee routes and components do not exist.

- [ ] **Step 3: Implement the API client and employee routes.**

Use the existing `apiClient` and response extraction convention. Add routes
guarded by `requiresAuth`, `requiredFeature: 'object_storage'`, and
`requiresModuleFlag: 'enable_object_storage'`. Keep all actions deep-linkable.

- [ ] **Step 4: Implement the four employee views.**

Overview shows quota such as `2 / 5`, RAM user status, key summary, latest
applications, and actions. Buckets shows only the current user's Bucket rows and
the one-Bucket application form. Credentials explicitly states that all owned
Buckets share the credential, shows only safe AK metadata, and provides delivery
and rotation. Applications shows compact statuses, safe error summaries,
attempts, retry, and sanitized execution details.

Use dedicated pages for long forms, stable table dimensions, no large modal for
the application workflow, and no secret in route/query/local storage. The
delivery surface must make expiry and one-time use obvious without revealing
technical cloud policy details.

- [ ] **Step 5: Run contract, lint, and build.**

Run: `node frontend/tests/_review/object-storage-employee-contract.test.mjs`

Expected: PASS.

Run: `npm run lint`

Expected: no errors.

Run: `npm run build`

Expected: successful Vite build.

- [ ] **Step 6: Commit employee UI.**

```bash
git add frontend/src/api/objectStorage.js frontend/src/pages/ObjectStorage frontend/src/components/layout/ObjectStorageNav.vue frontend/src/router/index.js frontend/src/components/layout/AppSidebar.vue frontend/src/locales frontend/tests/_review/object-storage-employee-contract.test.mjs
git commit -m "feat: add object storage employee workspace"
```

---

## Task 11: 实现平台管理端页面

**Files:**
- Create: `frontend/src/admin/api/objectStorage.js`
- Create: `frontend/src/admin/pages/ObjectStorage/Overview.vue`
- Create: `frontend/src/admin/pages/ObjectStorage/EnterpriseAccess.vue`
- Create: `frontend/src/admin/pages/ObjectStorage/Resources.vue`
- Create: `frontend/src/admin/pages/ObjectStorage/Tasks.vue`
- Create: `frontend/src/admin/pages/ObjectStorage/Audit.vue`
- Modify: `frontend/src/admin/routes.js`
- Modify: `frontend/src/admin/layout/AdminSidebar.vue`
- Modify: `frontend/src/admin/locales/en.json`
- Modify: `frontend/src/admin/locales/zh-CN.json`
- Create: `frontend/tests/_review/object-storage-admin-contract.test.mjs`

- [ ] **Step 1: Write the admin information-architecture contract.**

Assert that the admin surface contains exactly five logical areas: overview,
enterprise access, resources, tasks, and audit; assert that Bucket and access
credentials are separate tabs; assert that TOTP, notifications, Huawei Cloud,
and archive controls are absent from phase-one UI.

- [ ] **Step 2: Run the contract and verify it is red.**

Run: `node frontend/tests/_review/object-storage-admin-contract.test.mjs`

Expected: FAIL because admin pages and routes are absent.

- [ ] **Step 3: Implement the admin API client and guarded routes.**

Use the existing admin API conventions. Routes require authentication, the
`admin_object_storage` feature, and the object-storage module flag. The backend
remains the authority for superuser access.

- [ ] **Step 4: Implement the five admin views.**

Enterprise Access groups Feishu app, Alibaba pool, fixed Region, naming
template, quota, and delivery lifetime. Resources keeps Bucket, RAM user, and
credential tabs separate. Tasks prioritizes `MANUAL_REQUIRED`. Audit displays
only 30-day sanitized events and has no delete/export control.

Long configuration forms use dedicated pages. Secret inputs are write-only;
after save they show validation state, fingerprints, and last four characters.
The reveal action requires a reason and displays one credential only.

- [ ] **Step 5: Run frontend contract, lint, and build.**

Run: `node frontend/tests/_review/object-storage-admin-contract.test.mjs`

Expected: PASS.

Run: `npm run lint && npm run build`

Expected: no lint errors and a successful build.

- [ ] **Step 6: Commit admin UI.**

```bash
git add frontend/src/admin/api/objectStorage.js frontend/src/admin/pages/ObjectStorage frontend/src/admin/routes.js frontend/src/admin/layout/AdminSidebar.vue frontend/src/admin/locales frontend/tests/_review/object-storage-admin-contract.test.mjs
git commit -m "feat: add object storage administration workspace"
```

---

## Task 12: 安全回归、端到端测试和测试环境启用

**Files:**
- Create: `backend/object_storage/tests/test_security_regressions.py`
- Create: `backend/object_storage/tests/test_e2e_contracts.py`
- Create: `frontend/e2e/object-storage.spec.ts`
- Modify: `docker-compose.dev.yml` only for the disabled feature flag and test configuration
- Modify: `docs/logging.md` if a new object-storage log field needs documenting
- Modify: `backend/object_storage/periodic_tasks.py` to register cleanup explicitly

- [ ] **Step 1: Add security regression tests.**

Test cross-tenant and cross-owner access for every resource class; plaintext
Secret absence in database/API/log records; disabled feature behavior; default
feature flag off; no full AK/SK in notifications or exception responses; and
`Cache-Control: no-store` on delivery/reveal endpoints.

- [ ] **Step 2: Add end-to-end provider contract tests.**

With sanitized mocks, verify first application, additional Bucket, rotation with
one and two keys, release rejection for non-empty Bucket, suspension, retries,
manual recovery, and 30-day cleanup. With a dedicated Alibaba test account,
verify upload/download/overwrite/delete object, cross-user denial, Bucket admin
denial, other-service denial, and exact policy resources.

- [ ] **Step 3: Add Playwright employee and admin flows.**

Cover login handoff, overview, first application progress, one-time delivery,
additional Bucket, credential rotation confirmation, release confirmation, and
admin resource/task/audit views. Assert no horizontal overflow at desktop and
mobile viewports, and assert the secret is absent from URL, local storage, and
console-visible error payloads.

- [ ] **Step 4: Register periodic cleanup and keep the feature disabled by default.**

Register the 30-day audit cleanup through the existing periodic registry. Do not
enable the module in the default development environment until the test tenant,
Feishu app, and Alibaba pool have been configured and validated.

- [ ] **Step 5: Run the complete verification gate.**

Run backend core and object-storage suites:

```bash
PYTHONPATH=backend .venv/bin/python -m pytest \
  backend/accounts/tests \
  backend/jenkins_trigger/tests.py \
  backend/gitlab_resource/tests.py \
  backend/object_storage/tests \
  -q
```

Run frontend checks:

```bash
for test in frontend/tests/_review/*.test.mjs; do node "$test" || exit 1; done
npm run lint
npm run build
git diff --check
```

Run Playwright against the explicitly enabled test environment:

```bash
npm run test:e2e -- e2e/object-storage.spec.ts
```

- [ ] **Step 6: Enable only the test enterprise and capture rollout evidence.**

Record the enabled feature flag, validated Feishu app, validated Alibaba pool,
test account name, policy verification result, first application ID, rotation
result, release result, and failed-task recovery result. Do not record any
Secret or delivery token.

- [ ] **Step 7: Commit test and rollout wiring.**

```bash
git add backend/object_storage/tests frontend/e2e/object-storage.spec.ts docker-compose.dev.yml docs/logging.md backend/object_storage/periodic_tasks.py
git commit -m "test: validate object storage phase one rollout"
```

---

## 13. Final Acceptance Checklist

- [ ] Feature is disabled by default and independently enabled for the test enterprise.
- [ ] Feishu login creates only a restricted local user; it creates no cloud resources.
- [ ] Same `tenant + open_id` is idempotent and never merges by name/email/phone.
- [ ] Employee can create one personal Bucket per application, up to five by default.
- [ ] Existing Bucket names are never claimed or shared.
- [ ] One employee uses one RAM user and shared AK/SK across owned Buckets.
- [ ] Employee has full object operations but no Bucket administration or unrelated cloud permissions.
- [ ] Additional Bucket applications reconcile policy without issuing a new key.
- [ ] AK/SK delivery is one-time and enterprise-configurable from 10 minutes through 7 days, default 24 hours.
- [ ] Superuser reveal requires a reason, is single-record only, and is audited; TOTP is absent in phase one.
- [ ] Rotation respects the two-key cloud limit and never silently deletes a key.
- [ ] Non-empty Bucket release is rejected; empty Bucket release is asynchronous and irreversible.
- [ ] Suspension disables all keys; reactivation never re-enables old keys.
- [ ] Sensitive values are AES-GCM encrypted in the database and no plaintext reaches logs, APIs, URLs, or telemetry.
- [ ] Audit is immutable, sanitized, retained for 30 days, and automatically cleaned without offline archive.
- [ ] Temporary failures retry up to three times; business/configuration failures become safe manual-recovery states.
- [ ] Backend authorization and frontend visibility both enforce the intended boundaries.
- [ ] Existing HyperOps Jenkins, GitLab, monitoring, logging, and authentication behavior remains green.
