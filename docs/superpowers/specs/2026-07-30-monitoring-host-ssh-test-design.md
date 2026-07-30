# Monitoring Host SSH Connection Test

## Goal

Require operators to verify the exact SSH settings entered in the monitoring
host form before the Save action becomes available.

## Backend Contract

- Add `POST /api/v1/monitoring/hosts/test-connection/` as a collection action.
- Accept the current form values: optional host ID, address, SSH user, port,
  authentication type, optional password, and optional saved SSH key ID.
- For an existing password-authenticated host, an empty password means use the
  currently stored password.
- Key authentication resolves only an existing HyperOps SSH key credential.
- The test opens an SSH session with Paramiko and executes a fixed,
  non-mutating command. It never creates or updates a host record.
- Unknown host keys are accepted for this provisioning workflow, matching the
  existing Ansible installation behavior.
- Authentication, timeout, network, key, and command failures return safe,
  operator-facing messages without exposing credentials or stack traces.

## Frontend Flow

- Place a Test connection action directly below the authentication controls.
- Show idle, testing, success, and failure states in the same section.
- Save remains disabled until the current connection signature has passed.
- The signature includes address, user, port, authentication type, password,
  saved-password marker, and selected key ID.
- Changing any signed value immediately invalidates the previous result.
- Creating and editing hosts use the same flow. Editing with an unchanged,
  blank password tests through the saved credential.

## Verification

- Backend tests verify password, retained password, and saved-key resolution
  without database mutation.
- Frontend contract tests verify the API call, invalidation behavior, and Save
  gating.
- Live browser verification checks failure feedback and successful gating on an
  existing reachable host without saving form changes.
