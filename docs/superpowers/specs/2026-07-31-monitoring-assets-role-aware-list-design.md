# Monitoring Assets Role-Aware List Design

## Context

The monitoring assets page currently gives every host the same visual treatment:
it shows Categraf and blackbox-exporter status side by side, exposes three separate
status filters, and does not retain the result of an SSH connection test. This
creates three product problems:

1. A normal collection host appears to have a blackbox problem even when it was
   never intended to run blackbox-exporter.
2. SSH reachability is confused with component runtime health. SSH is a
   maintenance channel used to deploy or repair components, not a continuous
   health signal.
3. Operators cannot discover component installation until they select a host,
   and status cells stack multiple concepts vertically.

The redesign uses a single-line asset inventory approach. It keeps each cell to
one concept, presents connection, installation, and service health as
independent columns, and makes component installation permanently discoverable.

## Goals

- Make real collection and probing problems scannable in one pass.
- Stop reporting blackbox-exporter as missing on ordinary collection hosts.
- Retain a safe, auditable record of the latest SSH verification result.
- Keep every data row on one line with one status per cell.
- Keep the component-install entry visible before host selection.
- Preserve existing host editing, component installation, discovery, and job
  workflows.

## Non-Goals

- Continuous SSH polling or treating SSH as a host heartbeat.
- Automatically installing components when the list is refreshed.
- Replacing n9e or Prometheus as the source of component runtime state.
- Introducing a manually maintained host-role flag that can drift from probe
  node configuration.
- Redesigning the installation wizard or the probe target page.

## Product Model

### Host Roles

Every `MonitoringHost` is a collection host and expects Categraf. A host is also
a probe node when it has at least one enabled `BlackboxProbeNode` through the
existing `blackbox_probe_nodes` relation.

The role is derived, not stored twice:

- Collection host: always applies to a `MonitoringHost`.
- Probe node: applies while an enabled `BlackboxProbeNode` references the host.

Consequences:

- Categraf status is relevant to every row.
- blackbox-exporter status is displayed for every host.
- An ordinary host renders blackbox installation as neutral `Not enabled` and
  blackbox service as a dash.
  It does not contribute a blackbox issue to filters, counts, or next actions.

### SSH Verification Semantics

SSH is a maintenance channel. The stored result means "these saved connection
settings were verified at this time"; it must never be labeled `Online`.

Persist these fields on `MonitoringHost`:

- `ssh_verification_status`: `unverified`, `verified`, or `failed`.
- `ssh_verification_checked_at`: nullable timestamp.
- `ssh_verification_latency_ms`: nullable positive integer.
- `ssh_verification_error_code`: safe error code with no technical detail.
- `ssh_verification_signature`: server-generated fingerprint of the tested
  saved connection settings.

The UI derives `stale` instead of storing it. A successful verification older
than 24 hours is considered stale only while a component requires deployment or
repair. Healthy component rows do not show SSH age as an issue.

Changing the address, SSH user, SSH port, authentication type, password, or key
invalidates the prior verification during save. Changing the host name, labels,
or monitoring metadata does not invalidate it.

## Verification Receipt

The existing transient connection-test endpoint remains the source of truth:

`POST /api/v1/monitoring/hosts/test-connection/`

On success it additionally returns a short-lived, Django-signed verification
receipt. The receipt contains:

- requesting user ID;
- existing host ID or null for a new host;
- server-generated connection fingerprint;
- verification timestamp and latency;
- receipt version.

The fingerprint is an HMAC over normalized address, user, port, authentication
type, and secret identity. Password text and private-key content are never put
in the receipt, database verification metadata, logs, or API response. Key mode
uses the selected credential identity; password mode uses a server-only digest.

The receipt expires after ten minutes. Host create/update accepts it through a
write-only `ssh_verification_receipt` field. The backend verifies the signature,
age, requesting user, and submitted connection fingerprint before storing a
successful verification snapshot. A missing, expired, or mismatched receipt
cannot mark the host verified.

For a failed test:

- If the tested fingerprint matches an existing host's currently saved settings,
  persist `failed`, the checked time, and the safe error code.
- If the operator is testing unsaved settings, return the failure to the form
  but do not overwrite the saved host's last result.
- A new host has no persisted failure until it exists.

This ensures the list never reports an unsaved connection attempt as the state
of saved configuration.

## List Information Architecture

### Toolbar

Normal mode contains:

- Search by host name or address.
- One status menu: `All`, `Needs attention`, `Healthy`, `SSH issue`,
  `Collection issue`, and `Probe issue`.
- Compact summary: total host count and attention count.
- Icon-only refresh with tooltip.
- Primary, always-active `Install components` command.
- Secondary `Add host` command.

The toolbar does not switch modes. When rows are selected it adds a compact
selected count and clear action without hiding search, refresh, install, or add
host. Opening `Install components` without a selection shows host selection in
the chooser; existing row selection is prefilled.

The existing discovered-assets section remains conditional and appears only
when unmanaged discoveries exist.

### Columns

1. Selection checkbox.
2. **Host**: host name and address on one line. SSH details remain in edit.
3. **Connection status**: `Reachable`, `Connection failed`, or `Not verified`.
   The latest verification time remains available as a tooltip.
4. **Categraf / Installation**: one installation status.
5. **Categraf / Service**: one runtime status or a dash.
6. **blackbox / Installation**: one installation status; ordinary hosts show
   `Not enabled`.
7. **blackbox / Service**: one runtime status or a dash.
8. **Actions**: edit and delete on one line.

The header uses two rows: Categraf and blackbox are group headings, each with
Installation and Service subcolumns. No body cell contains stacked labels,
secondary explanations, or a next-action recommendation.

The table uses the existing admin table and button vocabulary. Status color is
semantic and restrained: green for healthy, red for runtime failure, amber for
deployment or verification work, and gray for unknown/not applicable.

### Installation Entry

The table does not reintroduce per-component install buttons. The persistent
toolbar command opens a chooser with host selection followed by Categraf or
blackbox selection, then reuses the existing component configuration flow.

## State Normalization

The API preserves two independent component dimensions:

- `installation_status`: `installed`, `not_installed`, `installing`, `failed`,
  `unknown`, or `not_applicable`.
- `runtime_status`: `online`, `abnormal`, `unknown`, or `not_applicable`.

It also retains the aggregate normalized `code` used by filters and the
next-action decision:

- `healthy`: installed and runtime online.
- `abnormal`: runtime explicitly failed or offline.
- `deploying`: an installation job is queued or running.
- `deployment_failed`: the latest installation failed.
- `pending_deployment`: the component is expected but not installed.
- `unknown`: required external evidence is unavailable.
- `not_applicable`: the component is not expected for this host.

`unknown` is not healthy and must render as `Status unconfirmed`, without
inventing an outage.

## Next-Action Decision Order

Evaluate only expected components. The first matching rule wins:

1. Any expected component is deploying: `Deployment in progress`.
2. An expected component needs deployment or repair and the current SSH result
   is failed: `Fix SSH connection`.
3. An expected component needs deployment or repair and SSH is unverified or
   its successful result is older than 24 hours: `Verify SSH`.
4. An expected component's latest deployment failed: `Review deployment
   failure`.
5. Categraf is pending deployment and SSH is current: `Deploy Categraf`.
6. A required blackbox service is pending deployment and SSH is current:
   `Deploy blackbox`.
7. Categraf is abnormal and SSH is current: `Inspect collection`.
8. A required blackbox service is abnormal and SSH is current: `Inspect probe`.
9. Required evidence is unavailable: `Status unconfirmed`.
10. Otherwise: `Running normally`.

Additional lower-priority findings remain available in the host form or tooltip;
the main cell shows only one action.

## Filtering and Counts

Filtering operates on the normalized row model, not raw installation fields:

- `Needs attention`: any row whose next action is not `Running normally` or
  `Deployment in progress`.
- `Healthy`: all expected components are healthy.
- `SSH issue`: current saved SSH verification failed, or SSH verification is
  required before the next component operation.
- `Collection issue`: Categraf is abnormal, pending deployment, deployment
  failed, or unknown.
- `Probe issue`: the host is a probe node and its blackbox state is abnormal,
  pending deployment, deployment failed, or unknown.

Ordinary hosts never enter `Probe issue` because blackbox is not applicable.

## Error and Loading Behavior

- A refresh failure keeps the last successfully loaded table visible and shows
  an inline retry message. It does not replace the page with a generic error
  state.
- Initial loading uses the existing table loading treatment and preserves stable
  column dimensions.
- SSH errors are localized from safe codes: authentication failed, key/protocol
  invalid, timeout, unreachable, or command failed.
- Missing n9e/Prometheus evidence renders `Status unconfirmed`.
- Only the row or form action being executed shows loading; unrelated rows stay
  interactive.
- A receipt mismatch returns a validation error and keeps Save disabled until
  the current settings are tested again.

## Responsive Behavior

At desktop widths, use the six-column table. At narrower admin-content widths:

- Keep host, collection service, next action, and actions visible.
- Fold probe service into the host/status stack for probe nodes.
- Do not shrink labels below readable sizes or allow status text to overlap.
- Bulk controls wrap as a single action group without resizing row controls.

No viewport-scaled typography is introduced.

## API Shape

The host serializer adds read-only fields:

- `roles`: array containing `collection_host` and optionally `probe_node`.
- `ssh_verification`: status, checked time, latency, safe error code, and
  whether the result currently matches saved settings.
- `collection_state`: normalized Categraf presentation state.
- `probe_state`: normalized blackbox presentation state or `not_applicable`.
- `next_action`: code, localized-data arguments, target component, and optional
  job ID.

The UI translates action/status codes; the backend does not return mixed
Chinese/English display strings.

Host create/update accepts write-only `ssh_verification_receipt`. No secret or
receipt is returned by normal host list responses.

## Testing

### Backend

- Receipt is issued only after a successful SSH command check.
- Receipt cannot be reused by another user, after expiry, or with changed
  address/user/port/auth/password/key.
- Blank password on an existing host binds to the saved password without
  exposing it.
- Failed tests persist only when they match current saved settings.
- Changing connection fields invalidates verification; unrelated edits do not.
- Probe role is derived from enabled `BlackboxProbeNode` records.
- Ordinary hosts receive `not_applicable` for probe state.
- Decision-order tests cover every next-action rule and multi-problem priority.
- Filters and attention counts exclude non-applicable blackbox state.

### Frontend

- Normal and bulk toolbar modes switch correctly.
- Search and the single status filter use normalized row data.
- Ordinary hosts never render `blackbox not installed`.
- Healthy rows do not surface stale SSH status.
- SSH appears when it blocks deployment or repair.
- Clicking each next action opens the correct existing workflow.
- Receipt is cleared when any signed connection field changes.
- Safe localized error messages render for all SSH error codes.

### Browser Verification

- Verify desktop and narrow admin-content viewports.
- Test saved-password and saved-key host flows.
- Verify failure, success, changed-after-success, receipt-expired, and save
  behavior.
- Verify ordinary collection hosts, probe nodes, and dual-role hosts.
- Verify bulk selection and installation entry without persisting unintended
  changes.
- Check console errors and confirm table/status text does not overlap.

## Migration and Compatibility

The migration initializes existing hosts as `unverified` without changing
component installation records. Existing API consumers continue to receive all
current host fields; the new fields are additive. The frontend treats missing
new fields as `unverified` and computes a conservative `Status unconfirmed`
state during rolling deployment.

## Acceptance Criteria

- An ordinary collection host does not show blackbox-exporter as missing and is
  not counted as a probe issue.
- A healthy host does not show an SSH warning solely because its last SSH check
  is old.
- A host that needs deployment or repair presents SSH verification first when
  the maintenance channel is failed, unverified, or stale.
- A successful test can mark only the exact saved connection settings as
  verified.
- Each row presents at most one next action and operators can reach the existing
  edit/install/detail workflow from it.
- The toolbar is quieter in normal mode and exposes bulk controls only after
  selection.
