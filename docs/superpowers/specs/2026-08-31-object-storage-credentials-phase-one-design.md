# Object Storage Credentials Phase One Design

Date: 2026-09-01
Status: Pending written review
Version: 2.0
Chinese version: `docs/superpowers/specs/2026-08-31-object-storage-credentials-phase-one-design.zh-CN.md`

## 1. Decision Summary

HyperOps will provide a platform-level object-storage self-service workflow.
Users authenticate with Feishu, then manage their own Alibaba Cloud OSS buckets,
access keys, and application history. Platform administrators configure the
Alibaba connection, bucket defaults, quotas, and resource actions.

The object-storage product removes the enterprise and tenant concepts entirely:

- exactly one Feishu application is configured at platform scope;
- exactly one Alibaba Cloud OSS resource pool is enabled in phase one;
- buckets, RAM users, keys, and applications belong directly to HyperOps users;
- Feishu and object storage are separate singleton platform configurations;
- LDAP, local accounts, and Feishu accounts remain independent identities.

The implementation uses the previously selected platform-level replacement
(option B). There is no production object-storage data yet, so the migration
does not retain a compatibility layer or parallel V1/V2 APIs.

## 2. Scope

Phase one includes Feishu OAuth and just-in-time local-user creation, binding
the Feishu app to one existing local group, one Alibaba Cloud OSS pool, batch
bucket applications, one RAM user per HyperOps user, up to five buckets by
default, at most two effective key sets, one-time credential delivery, key
management, bucket release and recovery, administrator configuration, async
execution, retries, and audit.

It excludes multiple tenants or enterprises, multiple active apps or pools,
other cloud providers, approvals, scheduled Feishu sync, notifications, TOTP,
KMS/OpenBao, offline archives, bucket transfer or sharing, public read-write,
user-managed cloud configuration, and automatic cloud-resource deletion when
a local user is disabled or deleted.

## 3. Domain Model

```text
Platform
├─ PlatformFeishuConfig (singleton)
│  └─ FeishuIdentity -> HyperOps User
└─ PlatformObjectStorageConfig (singleton)
   └─ CloudResourcePool (one enabled Alibaba pool)
      └─ HyperOps User
         ├─ CloudIdentity (one RAM user)
         ├─ AccessKey (at most two effective sets)
         ├─ Bucket (many)
         └─ ApplicationBatch
            └─ ApplicationItem (one bucket per item)
```

Platform configuration models are singletons. Cloud resources and applications
reference the existing HyperOps user directly; no object-storage tenant or
membership relation is introduced. A Feishu identity remains necessary to
track the external identity and to restrict manual sync to Feishu-created users.

The batch/item split is mandatory. A batch has aggregate counts and state;
each item has its own generated name, cloud operation, result, retry, cancel,
and audit history. Audit rows preserve actor identifiers and name snapshots so
that deleting a local user cannot erase the audit chain.

## 4. Identity and Authorization

The login page exposes Feishu login without enterprise selection. The server
binds a short-lived, single-use OAuth state to the singleton configuration and
trusts only the provider callback result. The first successful login creates a
password-disabled, non-staff, non-superuser local account and a FeishuIdentity.
Login does not create a RAM user, bucket, policy, or key.

The Feishu app is bound to one existing local group. Existing role configuration
continues to determine both workbench and console permissions. LDAP and local
account administration remain separate from the Feishu page. Manual Feishu sync
shows a change preview first and only processes Feishu-origin users after admin
confirmation; it never merges identities by name, email, or phone.

Ordinary users can access only their own buckets, keys, and applications.
Existing platform-admin permissions are used for administration; no new role is
added. Backend authorization is authoritative even when a menu is hidden.
Users with linked cloud resources cannot be physically deleted until an
administrator has handled those resources.

## 5. Application Workflow

Users can submit multiple bucket items at once. Each item contains a required
business name and purpose, plus optional project, environment, and note. Cloud
account, region, ACL, policy, storage class, encryption, versioning, and
lifecycle are administrator-controlled.

For a first application the worker performs these steps in order:

1. create or confirm the user's RAM user;
2. create the first AK/SK set;
3. create each bucket independently;
4. reconcile the RAM policy against all currently effective owned buckets;
5. encrypt the credential and create its one-time delivery ticket.

At least one successfully authorized bucket makes credential delivery available.
If every item fails or remains retryable, delivery is withheld. Cancelling an
all-failed batch removes an undelivered key and an unassociated RAM user;
cancelling failed items after partial success keeps the successful resources.

Batch states are intentionally summarized as waiting, processing, completed,
partially completed, failed, cancelled, or manual action required. Item states
cover waiting, creating, succeeded, failed, cancelled, releasing, pending
deletion, and deletion blocked. Technical stages live in event records and
detail views. Lists show counts such as “processing: 2, completed: 3, failed: 1”;
they do not use attempt numbers, `#` identifiers, or “successful N times” as
primary product information. Actions remain fixed commands such as view, retry,
and cancel.

## 6. Naming and Quota

Users enter a business name. The administrator-controlled template renders the
final bucket name and appends an eight-character lowercase alphanumeric random
suffix. Final names are 3-63 ASCII characters, contain only lowercase letters,
digits, and hyphens, and start and end with a letter or digit. The UI previews
the exact final name and remaining length; the backend repeats validation and
never silently truncates.

The system checks local and cloud state before creation. A cloud name conflict
causes a new suffix to be generated and retried up to three times. The atomic
cloud create result remains authoritative for concurrent requests. Persistent
conflict fails only that item and permits an individual retry.

The default per-user quota is five and may be overridden by an administrator.
Normal, pending, creating, and retryable buckets reserve quota. A bucket being
released reserves quota until it reaches pending deletion. Pending-deletion,
released, and deletion-blocked buckets do not reserve quota. Batch submission
validates and reserves all capacity under a user lock; cancellation releases
the reservation. Recovery rechecks quota before restoring a bucket.

## 7. Bucket, Key, and Platform Configuration

The user's RAM policy grants full object operations over all of that user's
owned buckets. All key sets for the same RAM user share that scope. Users cannot
create/delete buckets, access another user's bucket, change policy or ACL, or
grant third-party access.

Buckets are private by default. Administrators may set an individual bucket to
public read only after entering a reason and confirming; public read-write is
not available in phase one. ACL, policy, public access, storage class,
encryption, versioning, and lifecycle are management-only. Bucket name and
region are immutable after creation. Existing bucket settings that the provider
supports changing are applied asynchronously; failure preserves the old value.

Users can disable, enable, rotate, or revoke their own keys. Revoking one key
does not affect the other. With one key, rotation creates a second. With two,
the user explicitly selects an inactive or oldest key to retire before a
replacement is created; the system never silently selects. If replacement
creation fails after deletion, the remaining key is preserved and the task is
manual-action-required.

Credential material is shown in full only once after issue or rotation. Later
views are masked. An administrator can reveal one key after entering a reason;
TOTP is deferred.

Platform settings are grouped into connection, bucket defaults, naming, quota
and retention, and platform switches. Cloud vendor and account ID lock after
real resources exist. Management credentials must validate as the same cloud
account before replacement. Region and defaults affect only future buckets.
“Pause new applications” and “pause key operations” are separate switches;
there is no global disable-all-resources action. Invalid connection config blocks
new applications and key issuance without modifying existing cloud resources.

## 8. Release and User Lifecycle

Release requires typing the full final bucket name. The worker rejects non-empty
buckets, versions, delete markers, or incomplete multipart uploads. For an empty
bucket it immediately removes policy access, retains bucket and data for seven
days, marks it pending deletion without quota usage, and allows recovery during
that period after a new quota check. Empty buckets are deleted after seven days.
Non-empty buckets become deletion-blocked; the system never clears them
automatically. Administrators may explicitly confirm immediate deletion.

Disabling or deleting a local user creates a management risk marker only. An
administrator separately disables or revokes keys, releases or deletes buckets,
and then cleans up the RAM user. No ambiguous “disable object storage” action is
used.

## 9. Execution and Recovery

The independent `object_storage` Django app reuses HyperOps users, roles, API
errors, Celery, logging, and frontend shell. A provider adapter exposes business
operations such as identity validation, principal lookup/creation, bucket
creation/deletion, emptiness inspection, policy reconciliation, key listing,
key lifecycle, and supported bucket configuration updates.

HTTP requests create a batch and return its ID. Cloud work runs on a low-
concurrency object-storage queue. Idempotency keys, database locks, ownership
markers, and pre-mutation cloud reads prevent duplicate changes. Temporary
network, timeout, rate-limit, and service-unavailable errors retry at most three
times with exponential backoff. Configuration, ownership, permission, quota,
encryption, naming, and inconsistent-resource errors do not auto-retry.

Timeout recovery queries deterministic RAM names and exact bucket names before
retrying. Policy failure retains the principal and bucket and retries policy
reconciliation without issuing a new key. If key encryption fails, the exact
new key is deleted if possible; uncertain deletion enters manual action
required. Partial batch success is never rolled back.

## 10. Secrets, Logging, and Audit

Feishu secrets, cloud management credentials, and user secrets are encrypted in
the database with authenticated encryption, random nonces, and a module-specific
key derived from HyperOps `SECRET_KEY`. No KMS, OpenBao, new environment
variable, or plaintext fallback is introduced. A re-encryption command must run
before changing the root secret.

Logs follow `docs/logging.md` and contain stable IDs, bucket name, stage, safe
provider request ID, duration, and error type only. They never contain full
credentials, ciphertext, authorization headers, delivery tokens, or credential
request bodies. Audit covers identity provisioning and sync, applications,
cloud mutations, policy, key lifecycle and reveal, bucket configuration,
release/recovery/deletion, retries, cancellation, and manual resolution.
Audit retention defaults to one month and is configurable; offline archive is
deferred.

## 11. Information Architecture

Employee navigation is **My Object Storage** with Overview, Buckets, Access
Keys, and Application History. Administration navigation is **Object Storage
Management** with Overview, Storage Settings, Buckets, Access Keys, Applications,
and Audit Log. “Enterprise Access”, enterprise selection, and enterprise policy
are removed.

Long application and settings workflows use dedicated pages rather than large
modal forms. Lists prioritize business name, final name, purpose, environment,
status, and fixed actions. Execution stages and provider diagnostics appear in
details. When the platform is not configured or is paused, users see an explicit
unavailable state and contact-admin action instead of an unusable application
form.

## 12. API and Test Contract

All routes live under `/api/v1/object-storage/`. Employee endpoints cover
overview, owned buckets, batch applications, item retry/cancel, key summaries,
one-time delivery, key lifecycle, and bucket release/recovery. Administration
endpoints cover singleton settings, validation, quotas, all resources, manual
recovery, single-key reveal, and audit search.

All mutations accept idempotency keys and return stable domain error codes.
Employee and administrator serializers are separate. Tests must cover singleton
constraints, Feishu just-in-time provisioning and no-merge behavior, user
isolation, group permissions, concurrent quota reservation, batch partial
success, naming conflict retries, RAM reuse, exact policy reconciliation,
encrypted one-time delivery, two-key rotation recovery, release/deletion
blocking, management-only public read, audit, and log redaction. Frontend
contract tests cover unconfigured states, dynamic batch forms, previews,
summaries, fixed actions, retries, masked credentials, and settings validation.

## 13. Rollout and Deferred Work

The rollout is: platform schema and migration, crypto/audit/provider contracts,
Feishu group authorization and JIT users, object-storage settings and validation,
batch orchestration, employee pages, administrator resource management, and
then browser/security acceptance. The feature flag remains off until validation
passes.

Multiple providers or pools, multiple Feishu apps, bucket transfer, notifications,
TOTP, offline archives, permission-drift reports, public read-write, and external
secret managers are deferred and must not leak into phase-one contracts.
