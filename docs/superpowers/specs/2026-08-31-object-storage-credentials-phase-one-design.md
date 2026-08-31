# Object Storage Credentials Phase One Design

Date: 2026-08-31
Status: Awaiting final written review
Source context: `/home/zjq/apps/2026-08-31-existing-system-object-storage-credentials-module-design.md`

## 1. Purpose

Add a self-service object storage module to HyperOps. Employees authenticate
with Feishu, receive a restricted local HyperOps account, and explicitly apply
for a personal Alibaba Cloud OSS bucket and access credentials.

The module is part of the existing HyperOps monolith. It reuses the existing
user model, sessions, access manifest, Django database, Celery, logging, API
error handling, and frontend application shell. It does not extend the
monitoring credential center and does not create a separate service.

Phase one proves one complete production-shaped flow with one test enterprise
and Alibaba Cloud OSS. The data model keeps an enterprise boundary so that
additional enterprises can be added without a schema redesign.

## 2. Confirmed Phase One Scope

Phase one includes:

- One test enterprise and one Feishu self-built application.
- One Alibaba Cloud account and one fixed OSS region for that enterprise.
- Feishu OAuth login and just-in-time creation of a restricted HyperOps user.
- A dedicated object storage employee workspace.
- A dedicated object storage administration console for HyperOps superusers.
- One personal Alibaba Cloud RAM user per employee.
- Up to five active personal buckets per employee by default.
- One bucket per application.
- Full object operations on the employee's own buckets.
- Shared AK/SK credentials across all buckets owned by the same employee.
- AK/SK issuance, one-time employee delivery, rotation, and controlled
  superuser reveal.
- Asynchronous application execution, retries, recovery states, and audit.
- Self-service release of empty buckets.
- User suspension and recovery behavior.

Phase one explicitly excludes:

- Huawei Cloud OBS or any provider other than Alibaba Cloud.
- Multiple active resource pools per enterprise.
- Manual approval workflows.
- Feishu notifications and notification configuration.
- TOTP for superuser credential reveal.
- Offline audit archive.
- Automatic Feishu organization or departure synchronization.
- Cross-user bucket sharing, bucket transfer, or shared buckets.
- User-managed bucket ACL, policy, public access, encryption, versioning,
  lifecycle, or deletion.
- Automatic permission-drift remediation.
- KMS, OpenBao, or an external secret manager.

## 3. Product Rules

### 3.1 Identity and account creation

The existing login page adds a Feishu login action. Because phase one has one
active test enterprise, the employee does not choose an enterprise.

After a successful Feishu callback, HyperOps identifies the employee by
`tenant_id + open_id`. If no identity exists, HyperOps automatically creates:

- A local Django user with an unusable password.
- No staff or superuser privileges.
- Access only to the object storage employee feature.
- An active enterprise membership linked to the Feishu identity.

HyperOps never merges users by name, email address, or phone number. Logging in
creates only the local user and membership. It does not create a RAM user,
bucket, policy, or access key.

### 3.2 First application

The employee opens the dedicated "Apply for object storage credentials" page
and enters:

- Project name.
- Environment: development, test, or production.
- Purpose.
- Optional note.

The employee does not choose a cloud account, region, ACL, policy, encryption,
versioning, storage class, or lifecycle setting.

The first successful application creates, in order:

1. A deterministic personal RAM user without console login.
2. One personal OSS bucket in the enterprise's configured region.
3. A least-scope RAM policy for that employee's current active buckets.
4. The first AK/SK pair.
5. An encrypted local credential record and one-time delivery ticket.

### 3.3 Additional buckets

An employee can own multiple buckets up to the enterprise quota. Each
application creates one bucket. Additional bucket applications reuse the
existing RAM user and active AK/SK; they only reconcile the employee's RAM
policy with the new set of active buckets.

Every bucket has exactly one employee owner. An existing bucket is never
claimed, shared, transferred, or automatically adopted. If Alibaba Cloud says
the generated name already exists, the application fails with a name conflict
and does not grant access.

### 3.4 Bucket quota

Each enterprise configures a per-user active bucket quota. The default is five.

- Active and releasing buckets consume quota.
- Released buckets do not consume quota.
- Failed applications do not consume quota.
- Concurrent applications lock the membership before checking quota.
- Superusers can change the enterprise quota but cannot bypass ownership or
  auditing rules.

### 3.5 Bucket naming

Each enterprise configures its own naming template. Templates use only an
allowlist of placeholders:

```text
{tenant} {user} {project} {environment} {purpose} {suffix}
```

The system normalizes values to lowercase OSS-safe characters, collapses
separators, enforces the 3-63 character limit, and adds a deterministic short
hash through `{suffix}`. Values that produce no readable ASCII slug use a
stable short hash. The application page shows the exact final name before
submission.

Template validation rejects unknown placeholders and templates that cannot
produce a valid, globally unique name. A template change affects only future
buckets. Each bucket stores the template version and rendered name used at
creation.

### 3.6 Bucket permissions

The employee's RAM user has full object-level access to each owned bucket,
including list, read, upload, overwrite, delete, and multipart operations.

The RAM user cannot:

- Create or delete buckets.
- Access another employee's bucket.
- Change bucket ACL or bucket policy.
- Enable public access.
- Change encryption, versioning, lifecycle, logging, or replication.
- Grant another principal access.
- Operate Alibaba Cloud services outside the required OSS scope.

HyperOps creates and configures buckets with the platform management identity.
The application layer expresses the desired set of owned buckets; the Alibaba
provider generates the provider-specific policy document.

### 3.7 Bucket release

An employee can release an owned bucket without administrator approval. The
employee must type the complete bucket name to confirm.

HyperOps refuses release if OSS reports any object, object version, delete
marker, or incomplete multipart upload. For an empty bucket, the asynchronous
task deletes the bucket, removes it from the RAM policy's desired resource set,
and marks the local bucket released. Release is irreversible.

### 3.8 Access key model

One RAM user and its AK/SK set serve all buckets owned by the employee in the
resource pool. Adding a bucket does not issue another key.

For rotation:

- With one key, create a second key.
- With two keys and one inactive key, propose the inactive key for deletion.
- With two active keys, propose the oldest key for deletion.
- Show only the selected key's last four characters, status, and creation time.
- Require employee confirmation before deletion.
- Delete the selected key before creating the replacement because Alibaba RAM
  permits at most two keys.
- If deletion succeeds but creation fails, enter `MANUAL_REQUIRED`; never
  delete the remaining key automatically.

The system never silently chooses and deletes a key.

### 3.9 Delivery and reveal

Each enterprise configures the employee delivery lifetime. The default is 24
hours, with a minimum of 10 minutes and a maximum of 7 days. A configuration
change affects only newly created tickets.

An employee can retrieve a newly issued AK/SK once before expiry. The delivery
token is random and only its digest is stored. Successful retrieval consumes
the ticket immediately. Subsequent employee access requires rotation.

The encrypted credential remains in the database. A HyperOps superuser can
reveal one credential after entering a reason. Reveal is never available in a
list, bulk action, export, employee API, or ordinary administration role. TOTP
is deferred, but the reveal service must have an explicit extension point for
adding step-up verification later.

### 3.10 Suspension and recovery

A superuser can suspend an object storage membership. Suspension:

- Blocks login to the object storage workspace and all employee operations.
- Asynchronously deactivates every access key for the linked RAM user.
- Keeps the RAM user, buckets, objects, and local records.

Reactivation restores workspace access but never reactivates old keys. The
employee must issue a new credential. Old keys remain inactive for state and
audit visibility.

## 4. Architecture

Create an independent Django app named `object_storage`. Do not place the
feature in `monitoring_stack`.

```text
backend/object_storage/
├── adapters/aliyun/       # OSS and RAM API implementation
├── services/              # applications, buckets, policies, credentials
├── models.py
├── serializers.py
├── permissions.py
├── views.py
├── urls.py
├── tasks.py
├── periodic_tasks.py
└── migrations/
```

The provider boundary exposes business operations, not raw SDK calls:

```text
validate_management_identity
find_or_create_personal_principal
create_owned_bucket
inspect_bucket_emptiness
delete_owned_bucket
reconcile_object_policy
list_access_keys
create_access_key
deactivate_access_key
delete_access_key
```

All API routes live below `/api/v1/object-storage/`. The employee and
administration serializers are separate so sensitive administration fields
cannot appear in employee responses by accident.

Cloud operations run in a dedicated Celery queue with low concurrency. API
requests create an application and return its ID; they do not wait for Alibaba
Cloud operations.

## 5. Data Model

### 5.1 Enterprise and identity

`StorageTenant`

- Name, unique code, status.
- Bucket naming template and template version.
- Per-user bucket quota, default 5.
- Delivery lifetime, default 24 hours.
- Audit retention days, fixed to 30 in phase one.

`FeishuAppConfig`

- Tenant one-to-one relation.
- App ID and encrypted App Secret.
- OAuth callback configuration, validation status, and enabled state.

`StorageMembership`

- Tenant, Django user, Feishu open ID, optional union ID.
- Display name, department snapshot, and status.
- Unique `(tenant_id, open_id)` and unique Django user membership.

### 5.2 Cloud resources

`StorageResourcePool`

- Tenant, provider (`aliyun` in phase one), cloud account ID, fixed region.
- Encrypted management access key and secret.
- Credential fingerprint, last four characters, validation status, enabled
  state, and last validation time.
- One active pool per tenant and provider in phase one.

`StorageCloudIdentity`

- Tenant, membership, resource pool, RAM user ID/name, status.
- Unique `(tenant_id, membership_id, resource_pool_id)`.

`StorageBucket`

- Tenant, resource pool, owner membership, cloud identity.
- Name, project, environment, purpose, optional note.
- Region, template version, cloud resource marker, and status.
- Unique `(resource_pool_id, name)`.

`StorageAccessKey`

- Tenant, cloud identity, encrypted AK, encrypted SK.
- AK fingerprint and last four characters.
- Cloud status, local status, creation time, last synchronization time.
- No plaintext secret or ciphertext is returned by standard serializers.

### 5.3 Workflow and audit

`StorageApplication`

- Tenant, applicant, action type, target bucket/key, idempotency key.
- Requested business fields, status, current stage, safe error code and summary.
- Unique `(tenant_id, applicant_id, idempotency_key)`.

`StorageApplicationAttempt`

- Tenant, application, attempt number, Celery task ID.
- Start/end time, status, safe provider request identifiers, and error code.
- Unique `(application_id, attempt_number)`.

`StorageApplicationEvent`

- Immutable state transition with tenant, application, attempt, stage, result,
  safe metadata, and timestamp.

`StorageDeliveryTicket`

- Tenant, application, access key, employee, token digest.
- Expiry, consumed time, status, and attempt count.

`StorageAuditEvent`

- Immutable tenant-scoped event.
- Actor, action, target type/ID, reason, IP, request ID, result, and timestamp.
- Sensitive targets use fingerprints or AK last four characters only.

Every business table explicitly stores `tenant_id`, including workflow and
audit tables. Tenant-scoped managers or services require tenant context for all
ordinary employee and enterprise queries.

## 6. Application State and Execution

Employee-facing application statuses are intentionally small:

```text
PENDING
RUNNING
DELIVERY_READY
SUCCEEDED
FAILED
MANUAL_REQUIRED
CANCELLED
```

Technical stages are recorded separately, including:

```text
IDENTITY_CHECKING
QUOTA_CHECKING
BUCKET_CREATING
PRINCIPAL_BINDING
POLICY_APPLYING
KEY_DELETING
KEY_CREATING
SECRET_ENCRYPTING
DELIVERY_CREATING
BUCKET_RELEASING
KEYS_DEACTIVATING
```

The worker locks the application and relevant membership/cloud identity before
executing. It reloads actual Alibaba Cloud state before each externally visible
mutation. Repeated delivery of the same Celery message returns the existing
result instead of repeating the operation.

Transient network, timeout, rate-limit, and service-unavailable failures retry
up to three times with exponential backoff. Configuration, ownership,
permission, key-limit, naming, encryption, and inconsistent-resource errors do
not retry automatically and enter `MANUAL_REQUIRED` when operator action is
needed.

Recovery rules include:

- Bucket creation timeout: query by exact generated name and ownership marker
  before retrying.
- RAM user creation timeout: query the deterministic RAM username and HyperOps
  marker before retrying.
- Policy update failure: preserve the bucket and principal, then retry policy
  reconciliation without issuing a key.
- Access key created but encryption failed: immediately delete that exact key;
  if deletion cannot be confirmed, enter `MANUAL_REQUIRED` at highest severity.
- Key deleted but replacement creation failed: preserve the remaining key and
  require explicit retry; never delete another key.
- Notification failure is not applicable in phase one.

## 7. Authentication, Authorization, and Isolation

- The OAuth state is short-lived, single-use, and bound server-side to the
  configured tenant and Feishu application.
- Frontend tenant parameters never establish authorization scope.
- Employee object queries require both active membership and owner ID.
- Cross-tenant or cross-owner object IDs return not found.
- Only `is_superuser=true` can use administration APIs.
- Existing ordinary administration roles gain no implicit object storage
  administration access.
- Local JIT users have an unusable password and cannot use local password login.
- Feature visibility is added through the existing HyperOps access manifest;
  hiding a menu never substitutes for API authorization.

## 8. Secret Protection

Phase one stores encrypted secrets in the database and does not add KMS,
OpenBao, a new environment variable, or a mounted key file.

HyperOps derives a module-specific key from the production Django `SECRET_KEY`
using HKDF with a fixed object-storage context and explicit crypto version. It
uses authenticated encryption with a random nonce for every value. Envelopes
store only the version, nonce, and ciphertext.

This applies to:

- Feishu App Secret.
- Alibaba Cloud management AccessKey ID and Secret.
- Employee AccessKey ID and Secret.

Production enables the module only when `SECRET_KEY` is non-default, stable,
and sufficiently strong. Replacing `SECRET_KEY` without re-encryption is a
deployment error. A management command must re-encrypt all object storage
secrets before the root secret changes. Decryption failure blocks the operation;
there is no plaintext fallback.

Sensitive endpoints set `Cache-Control: no-store`. Frontend code never writes
secrets to local/session storage, telemetry, exception reporting, route state,
or query parameters.

## 9. Logging and Audit

Application logs follow `docs/logging.md` and include only stable identifiers:

- Request ID, task ID, application ID, tenant ID, membership/user ID.
- Bucket name, stage, safe provider request ID, duration, and error type.
- Access key fingerprint or last four characters when necessary.

Logs never include request/response bodies from credential APIs, full AK/SK,
encrypted envelopes, Feishu secrets, management credentials, authorization
headers, or delivery tokens.

Audit events cover login provisioning, application submission, cloud resource
creation, policy changes, key issue/deactivation/deletion, employee delivery,
superuser reveal, suspension/reactivation, bucket release, retry, and manual
resolution.

Audit events remain in the database for 30 days. A daily periodic task deletes
older audit rows. Phase one has no offline archive, export, or UI deletion.
Application history and current resource state are not deleted with audit rows.

## 10. Information Architecture

### 10.1 Employee workspace

The sidebar parent "Object Storage" contains:

1. **Overview**: bucket quota, RAM user state, active key summary, recent
   applications, and primary actions.
2. **My Buckets**: bucket list, add bucket, ownership details, and release.
3. **Access Credentials**: RAM user, AK status, delivery, and rotation. It
   explicitly states that all owned buckets share these credentials.
4. **Application History**: first issue, add bucket, rotate, release, progress,
   safe errors, retries, and sanitized execution details.

### 10.2 Administration console

The sidebar parent "Object Storage Management" contains:

1. **Overview**: enterprise, user, bucket, active key, and abnormal task counts.
2. **Enterprise Access**: Feishu app, Alibaba resource pool, region, naming
   template, bucket quota, delivery lifetime, validation, and enablement.
3. **Resource Management**: separate tabs for buckets, RAM users, and access
   credentials; suspension and controlled single-secret reveal live here.
4. **Task Center**: applications, attempts, retries, and manual resolution.
5. **Audit Log**: 30-day sanitized records with enterprise, user, bucket,
   action, and time filters.

Bucket and AK/SK management remain visibly separate. The first application is
one workflow, but its resulting bucket and credential appear in their own
resource views.

Long forms use dedicated pages. Compact resource details and safe metadata may
use drawers. Long workflows are not placed in large modals. Tables prioritize
scanning and keep technical execution data in detail views.

## 11. Administration Configuration

A superuser configures and validates:

- Enterprise name/code and enabled state.
- Feishu App ID/App Secret and OAuth callback.
- Alibaba Cloud account name/ID and management credentials.
- Fixed OSS region.
- Bucket naming template.
- Per-user bucket quota, default 5.
- Employee credential delivery lifetime, default 24 hours, constrained to 10
  minutes through 7 days.
- Whether employee application is enabled.

Feishu and Alibaba credentials must validate successfully before their config
can be enabled. After save, pages show only fingerprints or the last four
characters and never return the stored secret.

## 12. API Shape

Employee APIs cover:

- Session tenant and object storage profile.
- Overview.
- Owned buckets and bucket applications.
- Credential summaries, one-time delivery, and rotation.
- Application history, attempts, safe events, and retry.

Administration APIs cover:

- Enterprise and integration configuration.
- Feishu and Alibaba validation actions.
- Tenant users, cloud identities, buckets, credentials, and tasks.
- Suspension/reactivation and manual task recovery.
- Reason-required single-secret reveal.
- Audit search.

Mutation APIs require idempotency keys. API responses use stable domain error
codes; provider exception text is never sent directly to clients.

## 13. Testing Strategy

Unit and API tests must prove:

- Feishu JIT provisioning creates one restricted local user per tenant/open ID.
- No automatic identity merge by personal attributes.
- Tenant and owner isolation on every resource class.
- Superuser-only administration and reason-required secret reveal.
- Database values and logs do not contain plaintext secrets.
- Idempotent duplicate submission and duplicate Celery delivery.
- Default five-bucket quota under concurrent applications.
- Deterministic naming, template validation, and name conflict rejection.
- Additional buckets reuse the RAM user and current access keys.
- Declarative policy reconciliation matches exactly the active owned buckets.
- Full object actions are allowed while bucket administration and other cloud
  services are denied.
- One/two-key rotation rules and failure recovery.
- One-time ticket consumption and configurable expiration.
- Non-empty bucket release rejection.
- Suspension deactivates keys; reactivation does not reactivate them.
- Thirty-day audit cleanup does not delete applications or resources.

The Alibaba adapter uses mocked contract tests with sanitized fixtures for the
normal suite. A dedicated test account runs end-to-end checks for upload,
download, overwrite, object deletion, cross-user denial, bucket-admin denial,
other-service denial, key rotation, retries, and reconciliation after partial
failures.

## 14. Rollout

1. Add the independent app, schema, access feature, feature flag, and disabled
   routes without changing existing business behavior.
2. Implement secret envelopes, audit, provider contracts, and domain services.
3. Implement enterprise, Feishu, and Alibaba configuration with validation.
4. Enable Feishu JIT provisioning only for the test enterprise.
5. Implement employee workspace and first application.
6. Add additional buckets, key rotation, bucket release, suspension, retries,
   and task administration.
7. Complete authorization, secret-leak, failure-injection, and Alibaba test
   account validation.
8. Enable the module for the test enterprise only.
9. Observe operation before planning multi-enterprise production rollout.

The global object storage feature flag defaults off. Each enterprise and its
resource pool must also be explicitly enabled.

## 15. Deferred Phases

Phase two may add multiple production enterprises, Feishu event notifications
with all event switches defaulting off, notification recipients, TOTP step-up
verification, automatic Feishu employment synchronization, longer audit
retention or encrypted offline archive, and permission-drift reporting.

Phase three may add Huawei Cloud OBS through a new provider adapter and may
replace local encryption with KMS or OpenBao without changing the application,
bucket, credential, or delivery product flows.
