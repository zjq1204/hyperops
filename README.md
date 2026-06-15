# HyperOps

[English](README.md) | [中文](README.zh-CN.md)

HyperOps is a focused Jenkins and GitLab operations platform built on Django and Vue.

## Scope

- Jenkins instance management and trigger entries
- Jenkins build triggering and record tracking
- GitLab instance, group, project, branch, tag, and webhook management
- Authentication, profile, and role-based access control

## Architecture

```text
hyperops/
├── backend/
│   ├── core/              # Django settings, URLs, Celery bootstrap
│   ├── accounts/          # Auth, profile, role, access profile
│   ├── jenkins_trigger/   # Jenkins instances, entries, records
│   ├── gitlab_resource/   # GitLab resource management
│   └── agentcore/         # Optional integrations
└── frontend/              # Vue 3 + Vite application
```

## Optional Integrations

These integrations are controlled by `.env`; the sample enables the notifier
so the notification admin pages are available out of the box:

- `ENABLE_NOTIFIER=true`
- `ENABLE_AGENTCORE_TASK=true`
- `ENABLE_AGENTCORE_METERING=true`

Only enable the modules you actually use.

## Quick Start

```bash
git submodule update --init --recursive
cp env.sample .env.dev
docker-compose -f docker-compose.dev.yml up -d
```

Common backend commands:

```bash
python3 backend/manage.py migrate
python3 backend/manage.py createsuperuser
python3 backend/manage.py check
```

Common frontend commands:

```bash
cd frontend
npm install
npm run dev
npm run build
```

## Runtime URLs

- Web UI: `http://localhost:8000`
- Swagger: `http://localhost:8000/swagger`
- Admin: `http://localhost:8000/admin`

## Notes

- The repository still contains some legacy modules and UI components from earlier platform experiments. HyperOps runtime entrypoints now only expose the Jenkins, GitLab, auth, and management surfaces described above.
- `agentcore_notifier` remains available as an optional integration for Jenkins build notifications.
