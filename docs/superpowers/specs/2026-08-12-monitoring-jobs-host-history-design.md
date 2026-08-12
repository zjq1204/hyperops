# Monitoring Jobs Host History Design

## Goal

Replace the deployment task table's one-row-per-execution presentation with a host-centered view while retaining every installation and retry record.

## Confirmed UX

- The default deployment task list contains one row per host.
- Each row shows the current Categraf and blackbox installation result independently.
- The row also shows the latest execution, concise failure reason, and attempt count.
- Opening a host shows component-specific execution history ordered newest first.
- Each history entry opens the existing task detail with its original parameters, result, progress, and logs.
- A batch task appears in the history of every host included in that task. Opening it focuses the selected host's result.
- Retrying from the host view creates a new immutable task record for only that host and failed component.
- Existing task records are never deleted, overwritten, or collapsed in storage.

## Backend Contract

Add `GET /api/v1/monitoring/ansible/jobs/host-summaries/`.

The response is a list of host summaries. Each summary contains stable host identity and two component slots. A component slot contains:

- `latest`: lightweight task and host result fields
- `attempt_count`: number of persisted executions involving that host and component
- `history`: lightweight task records ordered newest first

History entries include task ID, retry parent, task/host status, timestamps, duration, progress reason code, and a concise source error. Logs, inventory, vars, and commands remain available only from the existing task detail endpoint.

Extend `POST /api/v1/monitoring/ansible/jobs/{id}/retry/` with optional `host_id`. The server accepts it only when that host belongs to the failed host set of the source task. Without `host_id`, existing retry-all-failed-hosts behavior remains unchanged.

## Aggregation Rules

- Use the host ID from `hosts_snapshot` as the primary identity.
- Preserve historical visibility for deleted hosts using snapshot hostname and address.
- Determine per-host status from the matching `results` entry. For queued/running jobs, use the task status. For legacy terminal jobs without a matching result, fall back to the task status.
- A batch task contributes one history entry to each included host, never multiple entries to the same host.
- The latest component state is the first history entry after descending task creation ordering.

## Frontend Structure

- Filters: host search, component, and latest status.
- Table columns: host, Categraf, blackbox, latest execution, failure reason, actions.
- Host detail modal: component segmented control, latest status summary, chronological execution history.
- Task detail reuses the current progress/result/Ansible/command/log interface.
- Closing task detail returns to host history when opened from a host; deep-linked tasks close normally.

## Error Handling

- If host summaries fail, use the existing page-level error state.
- If a history task no longer exists, keep the host modal open and show the API error.
- Disable retry unless the latest component record failed and includes the host in its failed result.
- Keep raw Ansible output out of the host list; translate known reason codes into concise operator-facing text.

## Verification

- Backend tests cover batch fan-out, retry chains, per-host result differences, deleted-host snapshots, and scoped retry validation.
- Frontend contract tests cover the host summaries API, host-centered columns, history navigation, and scoped retry payload.
- Browser checks cover desktop and mobile host lists, history inspection, and returning from task detail.
