# HyperOps Service Logging Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Standardize HyperOps service logs as persistent, correlated, human-readable files with one configuration source, safe rotation, and enforceable coding rules.

**Architecture:** Django, Celery Worker, and Celery Beat share one logging formatter and context filter while selecting their service name and destination file through environment variables. Request and task identifiers are carried with `contextvars`; application, access, execution, and audit logs remain separate. External `logrotate` rotates mounted files while Python uses `WatchedFileHandler` so multi-process services reopen rotated files safely.

**Tech Stack:** Python standard `logging`, Django middleware, Celery signals, Docker Compose, Nginx, logrotate, pytest.

---

### Task 1: Logging formatter, context, and redaction

**Files:**
- Create: `backend/core/logging.py`
- Create: `backend/core/tests_logging.py`
- Modify: `backend/core/settings/logging_config.py`
- Modify: `backend/core/settings/base.py`

- [ ] **Step 1: Write failing formatter and context tests**

Add tests proving timestamps include milliseconds and timezone, API and task contexts render in the fixed header, sensitive values are redacted, file output creates `application.log`, and a missing file path falls back to console output.

- [ ] **Step 2: Run the tests and verify RED**

Run: `pytest backend/core/tests_logging.py -q`

Expected: FAIL because the formatter, context helpers, and single configuration API do not exist.

- [ ] **Step 3: Implement the logging primitives**

Implement `HyperOpsFormatter`, `LogContextFilter`, context bind/reset helpers, and redaction in `backend/core/logging.py`. Rebuild `configure_logging()` around one root configuration, `WatchedFileHandler` for a configured file, and `StreamHandler` only when no file is configured.

- [ ] **Step 4: Remove duplicate Django logging configuration**

Keep `backend/core/settings/logging_config.py` as the only configuration source. Remove the later `LOGGING` dictionary from `base.py`, set `LOGGING_CONFIG = None`, and configure service, file, and level from `HYPEROPS_LOG_SERVICE`, `HYPEROPS_LOG_FILE`, and `DJANGO_LOG_LEVEL`.

- [ ] **Step 5: Run logging tests and verify GREEN**

Run: `pytest backend/core/tests_logging.py -q`

Expected: PASS.

### Task 2: HTTP and Celery correlation

**Files:**
- Modify: `backend/platformkit/middleware.py`
- Modify: `backend/core/celery.py`
- Modify: `backend/core/settings/celery.py`
- Modify: `backend/core/tests_logging.py`

- [ ] **Step 1: Write failing correlation tests**

Add tests proving request context is bound only for the current request, always reset after response or exception, response headers contain `X-Request-ID`, publish headers receive the originating request ID, and task context is reset after task completion.

- [ ] **Step 2: Run targeted tests and verify RED**

Run: `pytest backend/core/tests_logging.py -q`

Expected: FAIL because middleware and Celery signals do not bind and reset logging context.

- [ ] **Step 3: Implement request and task context propagation**

Use `try/finally` in `RequestIdMiddleware`. Register Celery `before_task_publish`, `task_prerun`, and `task_postrun`/`task_failure` signal handlers and disable Celery root logger hijacking so all task logs retain the HyperOps format.

- [ ] **Step 4: Run targeted tests and verify GREEN**

Run: `pytest backend/core/tests_logging.py backend/core/tests_api_errors.py -q`

Expected: PASS.

### Task 3: Persistent files and rotation

**Files:**
- Modify: `docker-compose.dev.yml`
- Modify: `docker-compose.yml`
- Modify: `docker/entrypoint.sh`
- Modify: `docker/logrotate.conf`
- Modify: `docker/nginx/default.dev.conf`
- Modify: `docker/nginx/default.conf`
- Modify: `env.sample`

- [ ] **Step 1: Add service-specific logging environment**

Set API to `/var/log/gunicorn/application.log`, Worker to `/var/log/celery/worker.log`, and Beat to `/var/log/celery/beat.log`. Preserve the existing host mounts under `data.dev/logs` and `data/logs`.

- [ ] **Step 2: Stop duplicate process logging**

Let Django logging own Worker and Beat application output. Use Nginx as the canonical access log, keep Gunicorn errors separate, and leave container output for entrypoint/startup failures only.

- [ ] **Step 3: Replace the stale logrotate paths**

Add concrete mounted-log patterns for API, Worker, Scheduler, Nginx, PostgreSQL, and Redis with daily rotation, `maxsize 50M`, compression, date suffixes, and the agreed retention counts. Reopen Nginx files after rotation.

- [ ] **Step 4: Add request correlation to access logs**

Log the Django response `X-Request-ID`, request time, and upstream response time. Suppress static and health-check access noise without suppressing API failures.

- [ ] **Step 5: Validate configuration syntax**

Run: `bash -n docker/entrypoint.sh`

Run: `docker compose -f docker-compose.dev.yml config -q`

Run: `docker compose -f docker-compose.yml config -q` with a temporary `APP_VERSION` value.

Expected: all commands exit 0.

### Task 4: Existing application-log migration and guardrails

**Files:**
- Modify: Python files under `backend/core`, `backend/accounts`, `backend/gitlab_resource`, `backend/jenkins_trigger`, `backend/monitoring_stack`, and `backend/platformkit` that currently use `print()` or logging f-strings
- Create: `backend/tests/test_logging_policy.py`

- [ ] **Step 1: Write a failing source-policy test**

Use the Python AST to reject runtime `print()` and f-string arguments passed to logger methods in first-party backend modules, excluding migrations, tests, and `backend/agentcore` submodules.

- [ ] **Step 2: Run the policy test and verify RED**

Run: `pytest backend/tests/test_logging_policy.py -q`

Expected: FAIL and list current source violations.

- [ ] **Step 3: Migrate current violations**

Replace `print()` with module loggers and replace eager f-string logging with parameterized logging. Normalize touched high-value monitoring, Jenkins, and GitLab messages to concise readable messages with stable `key=value` fields while preserving business behavior and all uncommitted user changes.

- [ ] **Step 4: Run policy and affected module tests**

Run: `pytest backend/tests/test_logging_policy.py backend/core/tests_logging.py backend/monitoring_stack/tests/test_ansible_job_progress.py backend/jenkins_trigger/tests.py backend/gitlab_resource/tests.py -q`

Expected: PASS.

### Task 5: Operational standard and full verification

**Files:**
- Create: `docs/logging.md`
- Modify: `env.sample`

- [ ] **Step 1: Write the approved standard**

Document log categories, fixed format, field names, levels, exception ownership, redaction, module-specific rules, file paths, retention, examples, prohibited patterns, and troubleshooting commands. State that all new HyperOps first-party code must follow the document.

- [ ] **Step 2: Document environment controls**

Describe `DJANGO_LOG_LEVEL`, `HYPEROPS_LOG_SERVICE`, and `HYPEROPS_LOG_FILE` without committing secrets or environment-specific paths outside the container defaults.

- [ ] **Step 3: Run backend verification**

Run: `pytest backend/core/tests_logging.py backend/core/tests_api_errors.py backend/tests/test_logging_policy.py -q`

Run: `python -m compileall -q backend/core backend/platformkit backend/accounts backend/gitlab_resource backend/jenkins_trigger backend/monitoring_stack`

Expected: all commands exit 0.

- [ ] **Step 4: Review the final diff**

Confirm no secrets are present, no user changes were reverted, log files are not added to Git, and application output has exactly one configured destination per deployed service.
