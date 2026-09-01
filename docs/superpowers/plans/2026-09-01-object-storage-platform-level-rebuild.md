# Object Storage Platform-Level Rebuild Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the pre-launch enterprise/tenant object-storage implementation with a platform-level Alibaba OSS self-service workflow whose resources belong directly to HyperOps users.

**Architecture:** Keep the existing `object_storage` Django app, but replace its tenant-centered state with singleton platform Feishu and object-storage settings, direct user ownership, and batch/item applications. Keep the Alibaba provider behind a business-operation adapter and run cloud mutations asynchronously through the existing Celery object-storage queue. The user and administrator frontends use separate resource workspaces with stable actions and no enterprise selection.

**Tech Stack:** Django 5, Django REST Framework, PostgreSQL, Celery, Redis, Vue 3, Vue Router, Tailwind CSS, existing HyperOps access manifest, existing logging and encrypted database-secret utilities, Alibaba Cloud RAM/OSS SDK.

**Source spec:** [`docs/superpowers/specs/2026-08-31-object-storage-credentials-phase-one-design.zh-CN.md`](../specs/2026-08-31-object-storage-credentials-phase-one-design.zh-CN.md)

**Supersedes:** `docs/superpowers/plans/2026-08-31-object-storage-credentials-phase-one.md`. Do not execute both plans.

---

## 0. Execution Guardrails and File Map

The repository already contains uncommitted object-storage and authentication work. Before implementation, record the existing diff and do not reset, checkout, stash, or overwrite unrelated changes. Work only in `/home/zjq/apps/hyperops`. Each task below has a disjoint primary responsibility and ends with a focused commit; if a file is already modified, merge with its current contents rather than restoring it.

### Target backend files

```text
backend/object_storage/models.py                         # platform/user-owned state
backend/object_storage/migrations/0005_platform_model.py # forward schema replacement
backend/object_storage/serializers.py                    # employee response/write contract
backend/object_storage/serializers_admin.py              # administrator contract
backend/object_storage/permissions.py                    # user/admin authorization
backend/object_storage/feishu.py                         # singleton Feishu client/auth mapping
backend/object_storage/views_auth.py                     # Feishu login/callback
backend/object_storage/providers/base.py                 # provider protocol
backend/object_storage/providers/aliyun.py               # RAM/OSS implementation
backend/object_storage/services/naming.py                # rendering and validation
backend/object_storage/services/policy.py                # quota and desired policy
backend/object_storage/services/applications.py          # batch/item orchestration
backend/object_storage/services/credentials.py           # delivery and key lifecycle
backend/object_storage/services/platform.py              # singleton configuration
backend/object_storage/services/audit.py                 # audit event creation
backend/object_storage/tasks.py                          # async execution
backend/object_storage/periodic_tasks.py                 # retention/deletion jobs
backend/object_storage/views_employee.py                 # employee APIs
backend/object_storage/views_admin.py                    # admin APIs
backend/object_storage/urls.py                           # platform-level routes
backend/object_storage/admin.py                          # Django admin registrations
backend/object_storage/tests/                            # rewritten contracts
backend/core/settings/base.py                            # feature setting
backend/core/urls.py                                     # conditional route
backend/accounts/access.py                               # group/feature permissions
backend/accounts/models.py                                # only if deletion guard needs a hook
```

### Target frontend files

```text
frontend/src/api/objectStorage.js                        # employee API client
frontend/src/admin/api/objectStorage.js                  # admin API client
frontend/src/router/index.js                             # employee routes
frontend/src/admin/routes.js                             # admin routes
frontend/src/admin/layout/AdminSidebar.vue               # navigation labels
frontend/src/pages/ObjectStorage/Overview.vue
frontend/src/pages/ObjectStorage/Buckets.vue
frontend/src/pages/ObjectStorage/Credentials.vue
frontend/src/pages/ObjectStorage/Applications.vue
frontend/src/admin/pages/ObjectStorage/Overview.vue
frontend/src/admin/pages/ObjectStorage/StorageSettings.vue  # platform settings page
frontend/src/admin/pages/ObjectStorage/EnterpriseAccess.vue # delete after route switch
frontend/src/admin/pages/ObjectStorage/Resources.vue
frontend/src/admin/pages/ObjectStorage/Tasks.vue
frontend/src/admin/pages/ObjectStorage/Audit.vue
frontend/src/locales/en.json
frontend/src/locales/zh-CN.json
frontend/src/admin/locales/en.json
frontend/src/admin/locales/zh-CN.json
frontend/tests/_review/object-storage-access-contract.test.mjs
frontend/tests/_review/object-storage-admin-contract.test.mjs
frontend/tests/_review/object-storage-employee-contract.test.mjs
```

### Required verification commands

Use the repository virtual environment for backend work:

```bash
PYTHONPATH=backend /tmp/hyperops-venv/bin/python -m pytest backend/object_storage/tests -q
PYTHONPATH=backend /tmp/hyperops-venv/bin/python backend/manage.py check
PYTHONPATH=backend /tmp/hyperops-venv/bin/python backend/manage.py makemigrations --check --dry-run
cd frontend && npm run build
```

The full repository verification required by `hyperops/CLAUDE.md` remains the final gate. A failed command must be fixed or reported; do not weaken or delete an existing test to obtain a green result.

## Task 1: Freeze the Baseline and Replace the Data Model

**Files:**
- Modify: `backend/object_storage/models.py`
- Create: `backend/object_storage/migrations/0005_platform_model.py`
- Modify: `backend/object_storage/tests/conftest.py`
- Modify: `backend/object_storage/tests/test_models.py`
- Modify: `backend/object_storage/tests/test_policy.py`
- Modify: `backend/object_storage/tests/test_security_regressions.py`

- [ ] **Step 1: Capture the baseline without changing the worktree.**

Run:

```bash
git status --short
git diff -- backend/object_storage backend/core backend/accounts frontend/src | tee /tmp/hyperops-object-storage-baseline.diff
PYTHONPATH=backend /tmp/hyperops-venv/bin/python -m pytest backend/object_storage/tests -q
```

Record the current failing tests and the current migration state in the task notes. Do not use `git reset`, `git checkout`, or `git clean`.

- [ ] **Step 2: Write failing model-contract tests for the platform graph.**

Replace tenant-oriented fixture expectations with tests asserting the intended constraints:

```python
def test_platform_feishu_and_object_storage_settings_are_singletons(db):
    PlatformFeishuConfig.objects.create(singleton_key="default")
    PlatformObjectStorageConfig.objects.create(singleton_key="default")

    with pytest.raises(IntegrityError):
        PlatformFeishuConfig.objects.create(singleton_key="default")
    with pytest.raises(IntegrityError):
        PlatformObjectStorageConfig.objects.create(singleton_key="default")


def test_user_owns_one_cloud_identity_and_many_buckets(user_factory, resource_pool):
    user = user_factory()
    identity = CloudIdentity.objects.create(user=user, resource_pool=resource_pool, ram_user_name="hyperops-u1")
    assert CloudIdentity.objects.filter(user=user).count() == 1
    assert Bucket.objects.create(owner=user, cloud_identity=identity, resource_pool=resource_pool, name="hyperops-u1-a", purpose="test").owner_id == user.id


def test_application_batch_has_independent_items(application_batch_factory):
    batch = application_batch_factory(item_count=2)
    assert batch.items.count() == 2
    assert batch.items.values_list("id", flat=True).distinct().count() == 2


def test_user_with_cloud_resources_cannot_be_deleted(user_factory, bucket_factory):
    user = user_factory()
    bucket_factory(owner=user)
    with pytest.raises(ProtectedError):
        user.delete()
```

The test names and factories must match the final model names; remove old tests that assert every business table has `tenant_id`.

- [ ] **Step 3: Define the platform-level models and constraints.**

In `models.py`, implement these concrete relationships and fields:

```python
PlatformFeishuConfig(singleton_key, app_id, app_secret_encrypted,
                     oauth_callback_url, access_group, validation_status,
                     validation_error_code, last_validated_at, enabled)
PlatformObjectStorageConfig(singleton_key, naming_template,
                            naming_template_version, default_bucket_quota,
                            delivery_lifetime_seconds, audit_retention_days,
                            pause_new_applications, pause_key_operations)
StorageResourcePool(config, provider, cloud_account_id, region,
                    management_access_key_encrypted,
                    management_secret_key_encrypted, credential_fingerprint,
                    access_key_last_four, validation_status, enabled)
FeishuIdentity(user, open_id, union_id, display_name, department_snapshot,
               profile_snapshot, is_active, deactivated_at)
CloudIdentity(user, resource_pool, ram_user_id, ram_user_name, state,
              last_synced_at)
Bucket(owner, resource_pool, cloud_identity, business_name, name, project,
       environment, purpose, notes, region, template_version, config_snapshot,
       cloud_resource_id, cloud_marker, state, pending_delete_at,
       last_synced_at)
AccessKey(cloud_identity, access_key_id_encrypted,
          secret_access_key_encrypted, access_key_fingerprint,
          access_key_last_four, cloud_state, local_state, last_synced_at,
          deactivated_at, deleted_at)
ApplicationBatch(applicant, idempotency_key, status, current_stage,
                 item_count, pending_count, success_count, failed_count,
                 error_code, error_summary)
ApplicationItem(batch, business_name, project, environment, purpose, notes,
                rendered_bucket_name, status, current_stage, retry_count,
                error_code, error_summary, bucket)
ApplicationAttempt(application_item, attempt_number, task_id, status,
                   started_at, finished_at, provider_request_id, error_code)
ApplicationEvent(application_item, attempt, stage, result, safe_metadata)
DeliveryTicket(application_batch, access_key, user, token_digest,
               expires_at, consumed_at, status, attempt_count)
AuditEvent(actor, actor_name_snapshot, action, target_type, target_id,
           reason, ip_address, request_id, result, safe_metadata)
```

Use `PROTECT` for resource ownership references, singleton-key uniqueness for both platform configs, unique `(resource_pool, name)` for buckets, unique user/resource-pool identity, and a two-effective-key database/service invariant. Store `config_snapshot` so an administrator can see the applied ACL and defaults without inferring them from current settings.

- [ ] **Step 4: Create a forward migration that removes the old tenant graph.**

Generate and review `0005_platform_model.py` so it deletes the old `StorageTenant`, `StorageMembership`, and tenant foreign keys after creating the platform-level tables. The migration must be forward-executable against the current empty development tables and must not contain data-dependent SQL. Confirm that no production object-storage data exists before running it in any deployed environment.

Run:

```bash
PYTHONPATH=backend /tmp/hyperops-venv/bin/python backend/manage.py makemigrations object_storage
PYTHONPATH=backend /tmp/hyperops-venv/bin/python backend/manage.py sqlmigrate object_storage 0005
PYTHONPATH=backend /tmp/hyperops-venv/bin/python backend/manage.py migrate --plan
```

- [ ] **Step 5: Run model and migration tests.**

Run:

```bash
PYTHONPATH=backend /tmp/hyperops-venv/bin/python -m pytest backend/object_storage/tests/test_models.py backend/object_storage/tests/test_policy.py -q
PYTHONPATH=backend /tmp/hyperops-venv/bin/python backend/manage.py check
PYTHONPATH=backend /tmp/hyperops-venv/bin/python backend/manage.py makemigrations --check --dry-run
```

Expected: all rewritten model tests pass, Django reports no system-check errors, and `makemigrations --check` reports no changes.

- [ ] **Step 6: Commit the model boundary.**

```bash
git add backend/object_storage/models.py backend/object_storage/migrations/0005_platform_model.py backend/object_storage/tests/conftest.py backend/object_storage/tests/test_models.py backend/object_storage/tests/test_policy.py backend/object_storage/tests/test_security_regressions.py
git commit -m "feat: replace object storage tenant model"
```

## Task 2: Platform Configuration, Encryption, Logging, and Audit

**Files:**
- Create: `backend/object_storage/services/platform.py`
- Modify: `backend/object_storage/crypto.py`
- Modify: `backend/object_storage/services/audit.py`
- Modify: `backend/object_storage/periodic_tasks.py`
- Modify: `backend/core/settings/base.py`
- Modify: `backend/object_storage/tests/test_crypto.py`
- Create: `backend/object_storage/tests/test_platform_config.py`
- Modify: `backend/object_storage/tests/test_security_regressions.py`

- [ ] **Step 1: Write failing tests for singleton configuration and secret handling.**

Cover one-row configuration, independent pause switches, default values (`quota=5`, `delivery_lifetime=86400`, `audit_retention_days=30`), validation ranges, encrypted database fields, tamper rejection, no plaintext in audit metadata, and re-encryption before root-secret rotation.

```python
def test_get_platform_config_creates_safe_defaults(db):
    config = get_object_storage_config()
    assert config.default_bucket_quota == 5
    assert config.delivery_lifetime_seconds == 86400
    assert config.pause_new_applications is True
    assert config.pause_key_operations is True


def test_admin_config_cannot_enable_until_provider_and_feishu_validate(db):
    config = get_object_storage_config()
    with pytest.raises(DomainError, match="CONFIG_NOT_VALIDATED"):
        enable_object_storage()


def test_audit_rejects_secret_values(audit_event_factory):
    with pytest.raises(ValueError):
        audit_event_factory(safe_metadata={"secret_access_key": "plain-secret"})
```

- [ ] **Step 2: Implement configuration services and database encryption.**

Expose `get_feishu_config()`, `get_object_storage_config()`, `validate_and_save_platform_config()`, `enable_platform()`, `pause_new_applications()`, and `pause_key_operations()`. Reject edits to provider/account ID once any real resource exists; require the replacement management credential to validate against the same cloud account. Apply defaults only to future buckets.

Use the existing authenticated encryption envelope and HKDF derivation from `SECRET_KEY`; preserve versioned envelopes and the re-encryption management command. Never introduce a plaintext fallback or a new secret environment variable.

- [ ] **Step 3: Add audit and retention behavior.**

Make audit rows immutable. Record actor ID/name snapshot, action, target, reason, result, IP, request ID, and safe metadata. Add daily deletion of rows older than the configured retention period without deleting resources or application history. Service logs must use parameterized messages and stable IDs under `docs/logging.md`.

- [ ] **Step 4: Run focused security tests.**

```bash
PYTHONPATH=backend /tmp/hyperops-venv/bin/python -m pytest backend/object_storage/tests/test_crypto.py backend/object_storage/tests/test_platform_config.py backend/object_storage/tests/test_security_regressions.py -q
PYTHONPATH=backend /tmp/hyperops-venv/bin/python -m pytest backend/tests/test_logging_policy.py -q
```

- [ ] **Step 5: Commit configuration and security primitives.**

```bash
git add backend/object_storage/services/platform.py backend/object_storage/crypto.py backend/object_storage/services/audit.py backend/object_storage/periodic_tasks.py backend/core/settings/base.py backend/object_storage/tests/test_crypto.py backend/object_storage/tests/test_platform_config.py backend/object_storage/tests/test_security_regressions.py backend/tests/test_logging_policy.py
git commit -m "feat: add platform object storage configuration"
```

## Task 3: Feishu Singleton Login, Group Authorization, and Manual Sync

**Files:**
- Modify: `backend/object_storage/feishu.py`
- Modify: `backend/object_storage/views_auth.py`
- Modify: `backend/object_storage/urls.py`
- Modify: `backend/object_storage/permissions.py`
- Modify: `backend/accounts/access.py`
- Modify: `backend/core/urls.py`
- Modify: `backend/object_storage/tests/test_feishu_auth.py`
- Create: `backend/object_storage/tests/test_feishu_sync.py`

- [ ] **Step 1: Write failing authentication and authorization tests.**

Test that OAuth uses the singleton app without a tenant query parameter, state is single-use and server-bound, first login creates a password-disabled non-staff user, repeated login reuses the same user, the configured local group supplies existing role permissions, and Feishu sync ignores LDAP/local users. Add preview-before-confirm and failed-sync-no-state-change tests.

```python
def test_feishu_callback_creates_local_user_without_cloud_resources(feishu_callback, feishu_config):
    response = feishu_callback(open_id="ou_123")
    user = User.objects.get(feishuidentity__open_id="ou_123")
    assert user.has_usable_password() is False
    assert user.is_staff is False
    assert user.is_superuser is False
    assert not CloudIdentity.objects.filter(user=user).exists()
    assert response.status_code == 302


def test_feishu_sync_requires_confirmation_and_only_updates_feishu_identities(api_client):
    preview = api_client.post("/api/v1/object-storage/management/feishu/sync-preview/")
    assert preview.status_code == 200
    assert api_client.post("/api/v1/object-storage/management/feishu/sync/").status_code == 400
```

- [ ] **Step 2: Remove tenant-dependent OAuth state and implement singleton Feishu mapping.**

Use a short-lived, single-use state bound to the singleton config ID and callback nonce. Reject `tenant`, `tenant_id`, and frontend-provided ownership scope. Create or update only `FeishuIdentity` rows whose source is Feishu. Assign the configured local `Group` through existing account-role mechanisms; do not invent a new object-storage administrator role.

- [ ] **Step 3: Implement preview/confirm synchronization.**

The preview returns creates, updates, deactivations, and unchanged counts. Confirmation uses an idempotency key and applies the snapshot transactionally. A provider/API failure leaves local Feishu state unchanged and records a failed audit event.

- [ ] **Step 4: Run authentication and access tests.**

```bash
PYTHONPATH=backend /tmp/hyperops-venv/bin/python -m pytest backend/object_storage/tests/test_feishu_auth.py backend/object_storage/tests/test_feishu_sync.py backend/accounts/tests/test_access_profile.py -q
```

- [ ] **Step 5: Commit the Feishu boundary.**

```bash
git add backend/object_storage/feishu.py backend/object_storage/views_auth.py backend/object_storage/urls.py backend/object_storage/permissions.py backend/accounts/access.py backend/core/urls.py backend/object_storage/tests/test_feishu_auth.py backend/object_storage/tests/test_feishu_sync.py
git commit -m "feat: make Feishu authentication platform scoped"
```

## Task 4: Naming, Quota, and Alibaba Provider Contracts

**Files:**
- Modify: `backend/object_storage/services/naming.py`
- Modify: `backend/object_storage/services/policy.py`
- Modify: `backend/object_storage/providers/base.py`
- Modify: `backend/object_storage/providers/aliyun.py`
- Modify: `backend/object_storage/tests/test_naming.py`
- Modify: `backend/object_storage/tests/test_policy.py`
- Modify: `backend/object_storage/tests/test_aliyun_provider.py`
- Create: `backend/object_storage/tests/test_provider_contract.py`

- [ ] **Step 1: Write failing naming/quota/provider tests.**

Test lowercase ASCII normalization, 3-63 final length, invalid leading/trailing hyphen, live remaining-length calculation, eight-character random suffix, three cloud-conflict retries, and no silent truncation. Test quota states exactly: active/creating/retryable/releasing reserve; pending deletion/released/deletion blocked do not reserve; batch checks and reserves under a user lock.

```python
def test_batch_quota_counts_creating_but_not_pending_deletion(user, bucket_factory):
    bucket_factory(owner=user, state="creating")
    bucket_factory(owner=user, state="pending_deletion")
    assert quota_remaining(user, limit=5) == 4


def test_long_rendered_name_is_rejected_without_truncation(user):
    with pytest.raises(DomainError, match="BUCKET_NAME_TOO_LONG"):
        render_bucket_name(template="x-{business_name}", business_name="a" * 70, user=user)
```

- [ ] **Step 2: Implement platform template rendering and conflict retries.**

Accept only the documented placeholders `{prefix}`, `{user}`, `{project}`, `{environment}`, `{purpose}`, and `{suffix}`. Normalize values, compute the available business-name length from the template, append eight lowercase alphanumeric random characters, and return the exact preview. Validate again in the worker. On provider conflict, generate a fresh suffix up to three times; persistent conflict fails only the item.

- [ ] **Step 3: Implement quota reservation and declarative policy generation.**

Lock the user or a dedicated quota row with `select_for_update()`, count reserving states, reserve all submitted items atomically, and release reservation on final cancellation. Policy resources must equal exactly the user's active owned bucket set and never include bucket-admin, ACL, delete-bucket, or non-OSS actions.

- [ ] **Step 4: Complete the provider protocol and Alibaba implementation.**

Expose only business methods: management validation, deterministic RAM lookup/create, bucket create/inspect/delete/update, policy reconciliation, key list/create/activate/deactivate/delete. Return sanitized dataclasses containing provider request IDs and error categories; never return SDK response bodies to services or clients. Implement public-read as an administrator-only bucket configuration; never expose public-read-write.

- [ ] **Step 5: Run provider and policy tests.**

```bash
PYTHONPATH=backend /tmp/hyperops-venv/bin/python -m pytest backend/object_storage/tests/test_naming.py backend/object_storage/tests/test_policy.py backend/object_storage/tests/test_provider_contract.py backend/object_storage/tests/test_aliyun_provider.py -q
```

- [ ] **Step 6: Commit provider and domain rules.**

```bash
git add backend/object_storage/services/naming.py backend/object_storage/services/policy.py backend/object_storage/providers/base.py backend/object_storage/providers/aliyun.py backend/object_storage/tests/test_naming.py backend/object_storage/tests/test_policy.py backend/object_storage/tests/test_provider_contract.py backend/object_storage/tests/test_aliyun_provider.py
git commit -m "feat: add platform object storage provider rules"
```

## Task 5: Batch Application Orchestration and Credential Delivery

**Files:**
- Modify: `backend/object_storage/services/applications.py`
- Modify: `backend/object_storage/services/credentials.py`
- Modify: `backend/object_storage/tasks.py`
- Modify: `backend/object_storage/services/provider_errors.py`
- Modify: `backend/object_storage/tests/test_application_service.py`
- Modify: `backend/object_storage/tests/test_tasks.py`
- Modify: `backend/object_storage/tests/test_credential_delivery.py`
- Create: `backend/object_storage/tests/test_batch_applications.py`

- [ ] **Step 1: Write failing batch state-machine tests.**

Cover one submission with multiple items, idempotent duplicate submission, shared RAM user/key prerequisites, independent item success/failure/retry/cancel, at-least-one-success delivery readiness, all-failed delivery withholding, and cleanup after an all-failed cancellation.

```python
def test_partial_batch_success_does_not_rollback_successful_item(application_runner):
    result = application_runner.run(["project-a", "project-b"], provider_results=["success", "permission_denied"])
    assert result.batch.status == "partially_completed"
    assert result.items[0].status == "succeeded"
    assert result.items[1].status == "failed"
    assert result.delivery_ready is True


def test_all_failed_batch_withholds_delivery_until_retry_or_cancel(application_runner):
    result = application_runner.run(["project-a"], provider_results=["unavailable"])
    assert result.delivery_ready is False
    assert result.batch.status in {"failed", "manual_action_required"}
```

- [ ] **Step 2: Implement batch creation and aggregate-state calculation.**

Accept a list of item payloads, validate all names and quota before committing, store one batch and one item per requested Bucket, and return the existing batch when the same applicant/idempotency key is submitted again. Aggregate display states from item states; do not expose attempt numbers as primary product data.

- [ ] **Step 3: Implement the fixed execution order and safe recovery.**

The worker must perform RAM user lookup/create, first key creation, independent bucket creation, policy reconciliation, encrypted credential persistence, and delivery-ticket creation in that order. Before every cloud mutation, query by deterministic identity/name and marker. Temporary errors retry three times with exponential backoff; configuration, ownership, permission, quota, encryption, and inconsistent-resource errors become manual-action-required.

- [ ] **Step 4: Implement credential delivery and key rotation.**

Generate a random delivery token, persist only its digest, enforce 10-minute-to-7-day configured lifetime with a 24-hour default, consume after one successful retrieval, and return no secret from list APIs. Implement one/two-key rotation with explicit user selection of an inactive or oldest key, preserve the remaining key on replacement failure, and never silently delete another key.

- [ ] **Step 5: Run application, task, and secret tests.**

```bash
PYTHONPATH=backend /tmp/hyperops-venv/bin/python -m pytest backend/object_storage/tests/test_application_service.py backend/object_storage/tests/test_batch_applications.py backend/object_storage/tests/test_tasks.py backend/object_storage/tests/test_credential_delivery.py -q
```

- [ ] **Step 6: Commit the asynchronous application workflow.**

```bash
git add backend/object_storage/services/applications.py backend/object_storage/services/credentials.py backend/object_storage/tasks.py backend/object_storage/services/provider_errors.py backend/object_storage/tests/test_application_service.py backend/object_storage/tests/test_batch_applications.py backend/object_storage/tests/test_tasks.py backend/object_storage/tests/test_credential_delivery.py
git commit -m "feat: orchestrate batched object storage applications"
```

## Task 6: Bucket and Key Lifecycle Administration

**Files:**
- Modify: `backend/object_storage/services/applications.py`
- Modify: `backend/object_storage/services/credentials.py`
- Modify: `backend/object_storage/tasks.py`
- Modify: `backend/object_storage/periodic_tasks.py`
- Modify: `backend/object_storage/permissions.py`
- Modify: `backend/object_storage/tests/test_employee_api.py`
- Modify: `backend/object_storage/tests/test_admin_resources_api.py`
- Create: `backend/object_storage/tests/test_resource_lifecycle.py`

- [ ] **Step 1: Write failing lifecycle tests.**

Test that release requires the full final name, rejects objects/versions/delete markers/incomplete multipart uploads, immediately removes policy access, retains data for seven days, allows recovery after quota recheck, deletes empty buckets at expiry, marks non-empty buckets deletion-blocked, and keeps user deletion protected while resources exist. Test that admins can manage one key or one bucket independently and that user suspension does not delete resources.

- [ ] **Step 2: Implement release, pending deletion, recovery, and expiry.**

Persist `pending_delete_at`, remove the bucket from desired policy before marking pending deletion, use a daily task for expiry, and never auto-empty a bucket. Add fixed actions `release_bucket`, `recover_bucket`, `delete_bucket`, and `retry_delete_bucket`; administrator immediate deletion requires reason and confirmation.

- [ ] **Step 3: Implement administrator-only bucket configuration updates.**

Allow administrators to update supported ACL (`private` or `public_read`), storage class, encryption, versioning, lifecycle, and other provider-supported defaults asynchronously. Save the desired and applied snapshots; on failure keep the applied snapshot and expose a retryable error. New platform defaults affect only future buckets.

- [ ] **Step 4: Implement independent key actions and user suspension.**

Expose disable, enable, rotate, and revoke for a selected key. Do not couple a key action to bucket deletion. Suspension disables all keys asynchronously and blocks the employee workspace; recovery never re-enables old keys. Resource deletion remains a separate administrator workflow.

- [ ] **Step 5: Run lifecycle tests.**

```bash
PYTHONPATH=backend /tmp/hyperops-venv/bin/python -m pytest backend/object_storage/tests/test_resource_lifecycle.py backend/object_storage/tests/test_employee_api.py backend/object_storage/tests/test_admin_resources_api.py -q
```

- [ ] **Step 6: Commit lifecycle behavior.**

```bash
git add backend/object_storage/services/applications.py backend/object_storage/services/credentials.py backend/object_storage/tasks.py backend/object_storage/periodic_tasks.py backend/object_storage/permissions.py backend/object_storage/tests/test_employee_api.py backend/object_storage/tests/test_admin_resources_api.py backend/object_storage/tests/test_resource_lifecycle.py
git commit -m "feat: add object storage resource lifecycle actions"
```

## Task 7: Employee and Administrator API Contracts

**Files:**
- Modify: `backend/object_storage/serializers.py`
- Modify: `backend/object_storage/serializers_admin.py`
- Modify: `backend/object_storage/views_employee.py`
- Modify: `backend/object_storage/views_admin.py`
- Modify: `backend/object_storage/urls.py`
- Modify: `backend/object_storage/admin.py`
- Modify: `backend/object_storage/tests/test_employee_read_api.py`
- Modify: `backend/object_storage/tests/test_employee_api.py`
- Modify: `backend/object_storage/tests/test_admin_config_api.py`
- Modify: `backend/object_storage/tests/test_admin_resources_api.py`
- Create: `backend/object_storage/tests/test_platform_api_contract.py`

- [ ] **Step 1: Write failing API contract tests.**

Employee tests must prove that all resource queries are owner-scoped, no `tenant` query parameter is accepted, secrets never appear in list/detail responses, batch item retry/cancel is independent, and disabled/paused platform states return stable domain codes. Admin tests must prove platform-admin-only access, singleton settings, reason-required secret reveal, public-read audit, per-user quota override, and separate key/bucket actions.

- [ ] **Step 2: Implement employee serializers and endpoints.**

Expose `/api/v1/object-storage/workspace/overview/`, `/buckets/`, `/applications/`, `/applications/<id>/`, `/applications/<id>/items/<item_id>/retry/`, `/applications/<id>/items/<item_id>/cancel/`, `/credentials/`, `/credentials/<id>/deliver/`, `/credentials/<id>/disable/`, `/credentials/<id>/enable/`, `/credentials/<id>/rotate/`, `/credentials/<id>/revoke/`, `/buckets/<id>/release/`, and `/buckets/<id>/recover/`. Use stable domain error codes and `Cache-Control: no-store` for delivery.

- [ ] **Step 3: Implement administrator serializers and endpoints.**

Expose singleton Feishu/object-storage settings, connection validation, user quota overrides, all-resource lists, bucket configuration, key actions, suspension/recovery, manual task recovery, single-key reveal, and audit search. Keep employee and admin serializers separate. Reject frontend ownership IDs and cross-user object access in the service layer, not only the view.

- [ ] **Step 4: Remove old enterprise endpoints and register only platform routes.**

Delete route behavior for enterprise access and `tenant_id` filters. Rename URL names and API payload keys to platform/user terminology. Keep the module behind `ENABLE_OBJECT_STORAGE`; when disabled, routes are not registered or return the existing stable disabled response according to the current module contract.

- [ ] **Step 5: Run the API suite.**

```bash
PYTHONPATH=backend /tmp/hyperops-venv/bin/python -m pytest backend/object_storage/tests -q
PYTHONPATH=backend /tmp/hyperops-venv/bin/python backend/manage.py check
```

- [ ] **Step 6: Commit the API boundary.**

```bash
git add backend/object_storage/serializers.py backend/object_storage/serializers_admin.py backend/object_storage/views_employee.py backend/object_storage/views_admin.py backend/object_storage/urls.py backend/object_storage/admin.py backend/object_storage/tests
git commit -m "feat: expose platform object storage APIs"
```

## Task 8: Redesign the Employee and Administrator Workspaces

**Files:**
- Modify: `frontend/src/api/objectStorage.js`
- Modify: `frontend/src/admin/api/objectStorage.js`
- Modify: `frontend/src/router/index.js`
- Modify: `frontend/src/admin/routes.js`
- Modify: `frontend/src/admin/layout/AdminSidebar.vue`
- Modify: `frontend/src/pages/ObjectStorage/Overview.vue`
- Modify: `frontend/src/pages/ObjectStorage/Buckets.vue`
- Modify: `frontend/src/pages/ObjectStorage/Credentials.vue`
- Modify: `frontend/src/pages/ObjectStorage/Applications.vue`
- Modify: `frontend/src/admin/pages/ObjectStorage/Overview.vue`
- Delete or replace: `frontend/src/admin/pages/ObjectStorage/EnterpriseAccess.vue`
- Modify: `frontend/src/admin/pages/ObjectStorage/Resources.vue`
- Modify: `frontend/src/admin/pages/ObjectStorage/Tasks.vue`
- Modify: `frontend/src/admin/pages/ObjectStorage/Audit.vue`
- Modify: `frontend/src/locales/en.json`
- Modify: `frontend/src/locales/zh-CN.json`
- Modify: `frontend/src/admin/locales/en.json`
- Modify: `frontend/src/admin/locales/zh-CN.json`
- Modify: `frontend/tests/_review/object-storage-access-contract.test.mjs`
- Modify: `frontend/tests/_review/object-storage-admin-contract.test.mjs`
- Modify: `frontend/tests/_review/object-storage-employee-contract.test.mjs`

- [ ] **Step 1: Write failing frontend contract tests for navigation and fixed actions.**

Assert that no employee/admin route or visible label contains enterprise selection, `tenant`, or “Enterprise Access”; user navigation is Overview/Buckets/Access Keys/Application History; admin navigation is Overview/Storage Settings/Buckets/Access Keys/Applications/Audit Log; status text does not render as an action; and batch rows show aggregate counts rather than attempt numbers or “successful N times”.

- [ ] **Step 2: Implement the employee workspace.**

Use dedicated pages for application and settings workflows. The application page supports a dynamic list of Bucket items, per-item required business name/purpose and optional project/environment/note, final-name preview, remaining length, quota summary, submit result, and batch detail. Bucket and key resources remain separate. Delivery and rotation use explicit confirmation and masked values.

- [ ] **Step 3: Implement the administrator workspace.**

Create `StorageSettings.vue`, switch the admin route from `EnterpriseAccess.vue` to it, and delete `EnterpriseAccess.vue` after the route contract passes. Group settings into connection, bucket defaults, naming, quota/retention, and switches. Show validation status and safe fingerprints. Add separate Bucket, Access Keys, Applications, and Audit views with fixed action menus. Public read requires reason/confirmation; no public read-write action is rendered.

- [ ] **Step 4: Implement unavailable, paused, loading, empty, and error states.**

When the platform is unconfigured or paused, show an explicit unavailable state and administrator contact action instead of an unusable form. For asynchronous actions show “processing”, preserve the old configuration on failure, and provide fixed retry actions. Do not put a long application form in a large modal.

- [ ] **Step 5: Run frontend contract tests and build.**

```bash
cd frontend
node --test tests/_review/object-storage-access-contract.test.mjs tests/_review/object-storage-admin-contract.test.mjs tests/_review/object-storage-employee-contract.test.mjs
npm run build
```

- [ ] **Step 6: Commit the workspace redesign.**

```bash
git add frontend/src/api/objectStorage.js frontend/src/admin/api/objectStorage.js frontend/src/router/index.js frontend/src/admin/routes.js frontend/src/admin/layout/AdminSidebar.vue frontend/src/pages/ObjectStorage frontend/src/admin/pages/ObjectStorage frontend/src/locales/en.json frontend/src/locales/zh-CN.json frontend/src/admin/locales/en.json frontend/src/admin/locales/zh-CN.json frontend/tests/_review/object-storage-access-contract.test.mjs frontend/tests/_review/object-storage-admin-contract.test.mjs frontend/tests/_review/object-storage-employee-contract.test.mjs
git commit -m "feat: redesign object storage workspaces"
```

## Task 9: End-to-End Verification and Test-Environment Rollout

**Files:**
- Modify: `backend/object_storage/tests/test_security_regressions.py`
- Modify: `backend/object_storage/tests/test_tasks.py`
- Create: `frontend/e2e/object-storage-platform.spec.ts`
- Modify: `README.md` and `README.zh-CN.md` only for the final feature-flag/configuration instructions
- Modify: deployment files only after the application and worker contract tests pass

- [ ] **Step 1: Add browser acceptance scenarios.**

The Playwright flow must cover: paused/unconfigured empty state; admin configuration and connection validation; user batch submission with two items; partial success with aggregate counts; one-time key delivery; adding another Bucket without creating another key; independent retry/cancel; key disable/enable/revoke; Bucket release/recovery; and admin public-read confirmation.

- [ ] **Step 2: Add failure-injection and security regression coverage.**

Run mocked provider scenarios for timeouts, name conflicts, permission denial, policy failure, key encryption failure, duplicate Celery delivery, non-empty deletion, and replacement-key failure. Assert logs and API responses contain no Secret, ciphertext, token, authorization header, or raw provider response.

- [ ] **Step 3: Run the complete verification gate.**

```bash
cd /home/zjq/apps/hyperops
PYTHONPATH=backend /tmp/hyperops-venv/bin/python -m pytest backend/object_storage/tests backend/accounts/tests backend/jenkins_trigger/tests.py backend/gitlab_resource/tests.py -q
PYTHONPATH=backend /tmp/hyperops-venv/bin/python backend/manage.py check
PYTHONPATH=backend /tmp/hyperops-venv/bin/python backend/manage.py makemigrations --check --dry-run
cd frontend && npm run build
```

Expected: all backend tests, Django checks, migration checks, and frontend build pass. If the environment cannot run a test dependency, report the exact missing dependency and do not claim completion.

- [ ] **Step 4: Verify the empty development database and migration plan.**

Before enabling the feature, inspect counts for every new resource model and run `migrate --plan`. Confirm the old tenant tables contain no production data in the target environment. Apply the migration, create platform settings disabled by default, and verify the employee routes remain unavailable until both provider validation and the feature flag permit access.

- [ ] **Step 5: Enable only the test environment.**

Configure the Alibaba test account and fixed Region, validate management credentials, configure the Feishu app and local group, keep notifications/TOTP/external secret managers disabled, and enable `ENABLE_OBJECT_STORAGE` only for the test deployment. Run the browser acceptance flow with sanitized test credentials.

- [ ] **Step 6: Commit deployment documentation and tag the rollout point.**

```bash
git add README.md README.zh-CN.md frontend/e2e/object-storage-platform.spec.ts backend/object_storage/tests/test_security_regressions.py backend/object_storage/tests/test_tasks.py
git commit -m "test: verify object storage platform rollout"
```

## Spec Coverage Review

The plan covers the approved design as follows:

| Spec area | Plan tasks |
| --- | --- |
| Platform singleton model and clean migration | 1 |
| Feishu singleton, local group, JIT user, manual sync | 3 |
| Batch applications and independent items | 5, 7, 8 |
| Random names, length validation, quota reservation | 4, 5 |
| RAM user and shared key relationship | 1, 4, 5, 6 |
| Key delivery, rotation, revoke, admin reveal | 2, 5, 6, 7, 8 |
| Bucket admin configuration and public read boundary | 4, 6, 7, 8 |
| Release, recovery, deletion blocking, user lifecycle | 6 |
| Paused platform switches | 2, 7, 8 |
| Async idempotency, retry, recovery | 5, 6, 9 |
| Logging, audit, encryption, retention | 2, 5, 6, 9 |
| UI information architecture and stable actions | 7, 8, 9 |
| Test and staged rollout | 1-9 |

The plan contains no unresolved placeholders. The only intentionally deferred capabilities are those listed in the approved design: multiple providers/pools, multiple Feishu apps, bucket transfer/sharing, notifications, TOTP, offline archive, permission-drift reporting, public read-write, and external secret managers.
