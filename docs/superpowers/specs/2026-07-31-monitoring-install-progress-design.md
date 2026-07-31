# Monitoring Installation Progress Design

## Context

Monitoring component installation jobs are already submitted to Celery, but the
execution path has two usability and reliability problems:

- The generated inventory forces `ansible_connection=paramiko`. The backend
  image currently runs Ansible Core 2.21.1, which no longer ships that
  connection plugin, so every job fails before connecting to the target host.
- The worker uses `subprocess.run` and writes logs only after Ansible exits. The
  UI therefore cannot distinguish queueing, preparation, connection,
  installation, and verification while a job is active.

The installation button must represent task submission, not a synchronous
installation request. After submission, the user stays on the current page and
receives a status notification with a direct link to the task detail.

## Goals

- Restore target-host connectivity with supported Ansible dependencies.
- Return from installation submission immediately after the job is queued.
- Persist structured progress and incremental logs while the worker runs.
- Provide a direct task-detail action from the submission notification.
- Show current stage, host state, and live logs in the deployment task detail.
- Preserve the existing final status, retry, preview, and manual-command flows.

## Non-Goals

- Replace Celery with another job system.
- Introduce WebSocket or Server-Sent Events infrastructure.
- Rewrite the installer scripts into a new deployment engine.
- Reconcile or rewrite historical job records.

## Architecture

### SSH Execution Environment

The backend image will install `openssh-client` and `sshpass`. Generated
inventory will use `ansible_connection=ssh`, backed by the supported
`ansible.builtin.ssh` connection plugin. Password authentication continues to
use the existing temporary inventory and SSH host-key checking remains disabled
for the generated installation run.

This approach is preferred over pinning an old Ansible Core release or adding a
third-party Paramiko connection collection because it follows the built-in
Ansible connection path and avoids another version-sensitive plugin dependency.

### Persistent Progress Contract

`AnsibleInstallJob` will gain a JSON `progress` field with this stable shape:

```json
{
  "stage": "queued",
  "current": 1,
  "total": 6,
  "percent": 0,
  "message": "queued",
  "current_host": "",
  "updated_at": "2026-07-31T00:00:00Z"
}
```

Supported stages are:

1. `queued`: accepted and waiting for a worker.
2. `preparing`: inventory and playbook are being generated.
3. `connecting`: Ansible is starting and connecting to selected hosts.
4. `installing`: the installer task is running on at least one host.
5. `verifying`: Ansible is collecting the final recap and host results.
6. `completed` or `failed`: the terminal result has been persisted.

Stage codes remain language-neutral. The frontend maps them to localized labels.
The existing `status`, `results`, `returncode`, and timestamps remain the source
of truth for terminal state and host counts.

### Incremental Execution

The worker will replace `subprocess.run` with `subprocess.Popen`. It will read
combined stdout and stderr line by line, append non-empty lines to the job log,
and periodically persist buffered lines. Persistence is throttled by line count
or elapsed time to avoid one database write per character while keeping the UI
responsive.

Ansible output markers update structured progress:

- process start sets `connecting`;
- the first `TASK [...]` line sets `installing`;
- `PLAY RECAP` sets `verifying`;
- final recap parsing sets `completed` or `failed`.

The existing recap parser remains responsible for detecting failures even when
the wrapper process incorrectly exits with code zero.

### Submission Semantics

The create and retry endpoints will create a queued job and attempt to enqueue a
Celery task. They will never execute installation inline as a fallback. A
successful enqueue returns the serialized queued job immediately.

If enqueueing fails, the job is marked failed with stage `failed`, a nonzero
return code, and a sanitized dispatch error. The API returns an explicit service
error so the UI can tell the user that no installation was dispatched.

### Frontend Behavior

After successful submission, the current dialog stops loading immediately and a
notification reports that task `#<id>` was dispatched. The notification includes
a `View task details` action that navigates to:

```text
/management/monitoring/jobs?job=<id>
```

The jobs page reads the query parameter, opens the matching detail dialog, and
polls active jobs once per second. Polling stops when the selected job reaches a
terminal state or the dialog/page is closed.

The task detail adds a compact horizontal stage indicator above the existing
tabs. It shows the localized stage name, percentage, current host when present,
and the last update time. The log tab updates without replacing the user's
selected tab and keeps its current scroll position unless the user is already at
the bottom.

## Error Handling

- Missing `ansible-playbook`, `ssh`, or `sshpass` is reported as an execution
  environment failure before target-host connection.
- Celery dispatch failures are never hidden by synchronous execution.
- Worker exceptions persist a terminal failed state and the latest buffered
  logs before exiting.
- Timeout handling terminates the Ansible process, records return code `124`,
  and marks unfinished hosts failed.
- API responses expose sanitized operational messages; raw exception traces stay
  in server logs.
- A polling failure leaves the last known progress visible and uses the existing
  page error/toast mechanism instead of closing the detail dialog.

## Testing

Backend tests will cover:

- inventory generation uses the built-in SSH connection;
- a queued create response does not call `execute_ansible_job` inline;
- dispatch failure creates a terminal failed job;
- incremental output persists progress and logs before process completion;
- `PLAY RECAP` failure still overrides an incorrect zero process return code;
- timeout and worker exceptions persist a failed terminal state.

Frontend contract and browser tests will cover:

- submission notification includes the task ID and detail action;
- `?job=<id>` opens the requested task detail;
- active jobs poll and terminal jobs stop polling;
- stage labels are localized and live logs update;
- production build succeeds.

A browser verification will submit a real Categraf installation job, confirm the
request returns without waiting for installation, open the linked task detail,
and observe stage and log updates through the final result.

## Rollout

The backend image must be rebuilt so `openssh-client` and `sshpass` are present.
Database migrations must run before workers start using the new `progress`
field. API and worker containers are then restarted together to avoid mixed
versions of the progress contract.
