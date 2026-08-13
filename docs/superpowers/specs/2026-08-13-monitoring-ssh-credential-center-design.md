# Monitoring SSH Credential Center Design

## Goal

Replace the monitoring asset page's embedded private-key upload with a reusable, encrypted, auditable SSH credential center modeled after AWX and Jenkins credential stores. Support both unencrypted and passphrase-protected private keys without exposing secrets through the API, UI, logs, or task records.

## Scope

This design covers:

- SSH private-key ingestion, normalization, parsing, encryption, and metadata
- Optional private-key passphrase storage
- Credential assignment to monitoring hosts
- Connection testing and Ansible execution
- Credential versioning and rotation
- Referential deletion rules and archival
- Operation permissions and audit records
- Migration of the existing file-backed credential
- Encryption-key failure and rotation behavior

It does not implement external Vault integration in the first release. The runtime credential provider interface must permit a Vault-backed implementation later.

## Product Experience

### Dedicated Credential Page

Add `/management/monitoring/credentials` under the monitoring console. The primary list displays only non-secret operational metadata:

- name
- active version
- key algorithm and bit size or curve
- SHA256 public-key fingerprint
- passphrase-protected indicator
- lifecycle state
- validation state
- referenced host count
- last validation time
- last update time

The list never displays the storage filename, private-key material, passphrase, encrypted payload, or worker command.

### Asset Editing

The host form contains:

- authentication mode: password or SSH credential
- saved credential selector
- `Manage credentials` navigation action
- connection-test status

It no longer contains key name, file upload, or save-key controls. Selecting or changing a credential invalidates the prior SSH verification receipt and requires another connection test before saving the host.

### Credential Creation

Creation is a three-step flow:

1. Enter a credential name, upload a private key, and optionally provide its passphrase.
2. Review parsed metadata and validation results.
3. Optionally select one or more hosts for connection verification before activation.

The server, not the browser, determines whether the key is encrypted. Supplying an unnecessary passphrase or omitting a required one returns a field-specific error. A credential can be saved without host verification, but remains `unverified` and cannot be assigned to a host until it has passed at least one connection test.

### Credential Detail

The detail view contains:

- active-version metadata
- associated hosts
- latest validation result per associated host
- version history
- audit history
- rotate, archive, and delete actions according to permission and lifecycle state

Secrets are never downloadable or recoverable from this view.

## Data Model

### MonitoringSshCredential

Replace the current `MonitoringSshKey` role with a stable logical credential record:

- `id`
- `name` (unique among non-archived credentials)
- `status`: `active`, `archived`, `needs_reupload`
- `active_version` nullable foreign key
- `created_by`, `updated_by`
- `created_at`, `updated_at`, `archived_at`

Keep the current table/model name only if doing so materially reduces migration risk; API and UI terminology must use `SSH credential` rather than `SSH key file`.

### MonitoringSshCredentialVersion

Each upload creates an immutable version:

- `credential`
- monotonic `version`
- `private_key_encrypted`
- `passphrase_encrypted`
- `has_passphrase`
- `algorithm`
- `key_size`
- `curve`
- `public_key_fingerprint`
- `public_key_text`
- `validation_status`: `draft`, `valid`, `invalid`
- `validation_error_code`
- `created_by`, `created_at`
- `activated_at`, `retired_at`

Private-key and passphrase ciphertext fields are excluded from every serializer. Versions are immutable after creation except for lifecycle timestamps and validation state.

### Host Assignment

`MonitoringHost` references the logical credential, not a version. Runtime execution resolves the active version at task start. A task snapshots:

- credential ID
- credential version ID
- public-key fingerprint

It never snapshots the private key, passphrase, ciphertext, or secret-bearing command.

### Validation Record

Store connection validation separately so one credential can be checked against multiple hosts:

- credential version
- host or candidate connection fingerprint
- status and error code
- latency
- checked by
- checked at

### Audit Record

Add an immutable monitoring credential audit model:

- credential and optional version
- action
- status
- actor
- source IP and request ID
- affected host IDs
- sanitized metadata
- created at

Actions include `create`, `validate`, `assign`, `unassign`, `rotate_start`, `rotate_validate`, `activate_version`, `archive`, and `delete`. Metadata must not include secret values, private material, complete SSH commands, or decrypted paths.

## Secret Storage

### Encryption Key

Introduce `MONITORING_CREDENTIAL_ENCRYPTION_KEYS` as an ordered key ring. The first key encrypts new values; all configured keys may decrypt existing values during key rotation. Do not silently fall back to Django `SECRET_KEY` in production.

Each ciphertext envelope includes a format version and key ID so key selection is deterministic. Use authenticated encryption through `cryptography.fernet.MultiFernet` or an equivalent AEAD implementation.

### Private-Key Ingestion

Before any database write:

1. Enforce a conservative request-size limit.
2. Decode as UTF-8 text; reject binary or undecodable content.
3. Normalize `CRLF` and lone `CR` to `LF`.
4. Ensure one final newline.
5. Write to a `0600` temporary file outside shared storage.
6. Parse with the same OpenSSH toolchain used by workers.
7. Detect encryption and validate the supplied passphrase.
8. Derive public key, algorithm, size/curve, and SHA256 fingerprint.
9. Encrypt normalized private material and passphrase independently.
10. Remove temporary files in a `finally` block.

Invalid material is never persisted. Duplicate fingerprints are rejected by default, with an explicit rotate-existing-credential path instead of silently storing copies.

### API Redaction

Create and rotate requests accept `private_key` and optional `passphrase` as write-only fields. Responses expose `has_passphrase` but never indicate passphrase length or return a placeholder secret. Application logs and exception handlers must sanitize both field names.

## Runtime Execution

### Credential Provider Boundary

Define a provider interface that resolves a credential version into a short-lived runtime SSH context. The first implementation reads encrypted database fields; a later implementation may obtain a certificate or key from Vault.

### Temporary Material

At task start:

- resolve and snapshot the active version
- decrypt into worker memory
- create a task-scoped `0700` temporary directory
- write a `0600` private key

For unencrypted keys, OpenSSH and Ansible use the temporary key path directly.

For passphrase-protected keys:

- launch a task-scoped `ssh-agent`
- load the key non-interactively with a short-lived askpass helper or controlled stdin mechanism
- expose only the agent socket to Ansible
- never put the passphrase in command arguments or environment visible to unrelated processes
- terminate the agent and remove all temporary files in `finally`, including timeout and worker-error paths

Connection testing must use the same provider and OpenSSH path as installation. Paramiko-only validation is not permitted because it can accept formats the execution worker rejects.

## Rotation

Rotation creates a draft version under the existing logical credential:

1. Upload and parse the new key.
2. Validate it against all currently associated enabled hosts.
3. Show per-host validation results.
4. Allow activation only after all required hosts pass, unless a privileged operator explicitly removes or migrates failed hosts from the credential first.
5. Atomically switch `active_version` and retire the previous version.
6. Invalidate host SSH verification receipts and mark hosts for re-verification.

Failed rotation leaves the previous version active. Existing versions are retained for task traceability and audit, but retired secret material follows a configurable retention period before cryptographic erasure.

## Archive and Delete

- A credential referenced by any host cannot be archived or deleted.
- The API returns HTTP 409 with associated host IDs and names.
- Operators must migrate those hosts to another credential or password authentication first.
- An unreferenced credential is archived before deletion.
- Physical deletion is restricted to privileged administrators and removes encrypted version material only after retention and audit requirements are satisfied.
- Audit records and non-secret task snapshots remain after deletion.

## Permissions

Keep `admin_monitoring` as the page-level feature gate and add operation-level permissions:

- `monitoring_credentials_view`
- `monitoring_credentials_use`
- `monitoring_credentials_manage`
- `monitoring_credentials_delete`

View allows metadata, associations, versions, and audit records. Use allows host assignment and connection tests. Manage allows create, passphrase update through a new version, rotation, activation, and archive. Delete allows physical deletion subject to reference and retention rules. Superusers receive all permissions by default.

No permission grants secret readback.

## Failure and Recovery

### Encryption Key Unavailable

If the key ring is absent, malformed, or cannot decrypt a referenced active version:

- credential health becomes `unavailable`
- connection tests, installs, assignment, and rotation activation are blocked
- the service never falls back to plaintext or a different implicit key
- health checks identify affected credential IDs without exposing secret details

### Encryption-Key Rotation

Use a dual-key window:

1. Add the new key as primary while retaining the old key for decryption.
2. Re-encrypt every active and retained version in a resumable management command.
3. Verify decryptability and metadata fingerprints.
4. Remove the old key only after the command reports zero remaining envelopes using it.

### Transaction Boundaries

Credential activation, host migration, and archival use database transactions and row locks. External host validation happens before the final activation transaction; the transaction only commits already-collected validation evidence.

## Existing Credential Migration

The current file-backed `MonitoringSshKey` record and host references require a staged migration:

1. Add new encrypted models and compatibility reads.
2. For each existing key file, normalize and parse with OpenSSH.
3. If valid, encrypt it as version 1, derive metadata, set it active, and preserve host assignments.
4. If invalid, create the logical credential with `needs_reupload`, preserve references for visibility, and block execution.
5. Verify every migrated ciphertext can be decrypted and matches its recorded fingerprint.
6. Remove plaintext files only after successful verification and an operator-visible migration report.
7. Remove compatibility reads in a later migration after the deployment has run successfully.

The currently stored `zhangjiaqi` key normalizes successfully after `CRLF` conversion, so it should migrate automatically rather than require re-upload.

## Frontend Routes and Components

- Add `/management/monitoring/credentials` and monitoring sidebar navigation.
- Create a dedicated credential list and detail page.
- Create focused upload/rotation, validation-result, associated-host, version-history, and audit components rather than expanding `Assets.vue` further.
- Replace the embedded upload block in `Assets.vue` with the credential selector and navigation action.
- Use existing buttons, tables, modals, page states, and status vocabulary.
- Desktop uses a compact table; mobile uses unframed list rows with metadata grouped by operational relevance.

## Testing

Backend tests must cover:

- CRLF normalization and OpenSSH parsing
- encrypted and unencrypted key ingestion
- wrong, missing, and unnecessary passphrases
- duplicate fingerprints
- ciphertext and API redaction
- role permissions
- referenced delete conflict
- runtime temporary-file permissions and cleanup
- task-scoped agent cleanup after success, timeout, and exception
- connection test and Ansible use of the same active version
- rotation all-host validation and atomic activation
- encryption-key rotation and unavailable-key behavior
- existing file migration, including the current CRLF key
- audit metadata sanitization

Frontend tests must cover:

- independent credential navigation and metadata-only list
- write-only passphrase behavior
- create/parse/validate flow
- referenced-delete conflict with host links
- rotation status and per-host results
- host form selector without embedded secret upload
- desktop and mobile layouts

## Acceptance Criteria

- A CRLF private key uploads successfully after server-side normalization.
- A passphrase-protected private key can be stored and used by an asynchronous installation task without exposing its passphrase.
- No private key or passphrase is stored in plaintext in the database, long-lived filesystem, API response, logs, task snapshot, or audit metadata.
- Every credential shows algorithm, fingerprint, lifecycle state, validation state, and usage count.
- A referenced credential cannot be deleted.
- Rotation cannot replace a working active version until associated-host validation succeeds.
- Every sensitive credential operation produces an immutable sanitized audit event.
- Missing or incorrect encryption keys block credential use explicitly and never trigger insecure fallback.
