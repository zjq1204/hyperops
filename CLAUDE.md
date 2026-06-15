# CLAUDE.md

Project facts live in [`README.md`](README.md) (English) and
[`README.zh-CN.md`](README.zh-CN.md) (Chinese). This file is the agent
operating contract — what to do, what to avoid, how to verify — when
working in this repository.

## What this project is

HyperOps is a Django 5 + Vue 3 platform for Jenkins and GitLab
operations: instance / trigger / record management on top of an
account / role / LDAP auth core. Notifier is an optional add-on, not
part of the default scope. See README for full scope, architecture,
and optional integrations.

## Working rules

- **TDD by default.** New behavior lands as a failing test first
  (pytest on backend, vitest / node-runner on frontend), then the
  smallest implementation that turns it green, then a cleanup pass.
- **No new top-level apps** without a written justification in
  README's "Architecture" section first.
- **No silent scope expansion.** If a task pulls you into modules
  outside the requested area, stop and confirm with the user before
  continuing.
- **No `rm -rf` of `.git`, dependency directories, or anything the
  user did not explicitly name.** When in doubt, list candidates and
  ask.
- **Match existing style.** Backend: PEP 8 + Django conventions.
  Frontend: Vue 3 `<script setup>`, Pinia stores, Tailwind utility
  classes, no new top-level deps without a reason.
- **English for code, comments, and commits.** User-facing strings go
  through i18n; never hard-code Chinese / English in components.

## Verification gate

Before claiming work is done, run — and have all green:

```bash
# Backend (use the project venv; system python is PEP 668 protected)
PYTHONPATH=backend /tmp/hyperops-venv/bin/python -m pytest \
    backend/accounts/tests \
    backend/jenkins_trigger/tests.py \
    backend/gitlab_resource/tests.py \
    -q
```

Frontend has no runner in CI; if you touched `.vue` / `.js`, at
minimum run `npm run build` from `frontend/`.

## Key paths

- Backend apps: `backend/{accounts,jenkins_trigger,gitlab_resource,action_orchestration,core}`
- Optional / submodules: `backend/agentcore/{agentcore-notifier,agentcore-task,agentcore-metering}`
- Frontend admin module: `frontend/src/admin/` (see `frontend/docs/ADMIN_REUSE.md`)
- Frontend router: `frontend/src/router/index.js`
- Env sample: `env.sample`; dev override: `.env.dev`
- Docker: `docker-compose.yml` (prod), `docker-compose.dev.yml` (dev)

## Out of scope for this contract

- License, certificates, and submodule internals are not edited
  from this file's authority.
- Dependency version bumps require a separate decision and a note in
  README.
