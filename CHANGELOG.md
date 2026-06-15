# Changelog

All notable changes to HyperOps are documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [1.0.0] - 2026-06-15

The first public release of HyperOps: a Django 5 + Vue 3 platform for
Jenkins and GitLab operations (instances, triggers, records, resource
management) on top of an account / role / LDAP auth core.

### Added

- **Jenkins instance and trigger entry management** with workspace
  gating (`workspace_jenkins` feature flag).
- **Jenkins build triggering and record tracking**, including per-user
  notification preferences and admin-only `notification_result` view.
- **GitLab resource management**: instances, groups, projects, branches,
  tags, and webhooks, with `GitLabOperationRecord` audit trail.
- **LDAP authentication** with multi-instance support, group-DN
  mapping scope, and configurable TLS verification.
- **Local account authentication** that recognizes both `username` and
  `email` for password login.
- **OAuth login** with a same-origin `redirect` sanitization on the
  callback page.
- **Optional integrations** controlled via `.env`:
  - `ENABLE_NOTIFIER=true` (default) — Feishu + email notifications
  - `ENABLE_AGENTCORE_TASK=true` — task execution
  - `ENABLE_AGENTCORE_METERING=true` — LLM usage metering
- **Admin module** (Vue 3 + Pinia) covering users, groups, roles, LDAP
  instances, Jenkins instances / jobs / entries, GitLab instances /
  groups, and notification management. See
  `frontend/docs/ADMIN_REUSE.md` for reuse instructions.
- **Platform meta endpoint** exposing module flags (e.g.
  `enable_notifier`) to the frontend for routing and sidebar gating.
- **Deep-link preservation**: unauthenticated users hitting a guarded
  route are redirected to `/login?redirect=<original-path>`.

### Fixed (review hardening, 12 items)

Security:

- **P0-1** LDAP TLS verification: `_build_server` now defaults to
  `ssl.CERT_REQUIRED` and honors `tls_ca_bundle` / `tls_require_cert`.
  - `backend/accounts/services/ldap_client.py`
- **P0-2** LDAP filter injection: user / group-DN searches now escape
  filter characters via `ldap3.utils.conv.escape_filter_chars`.
  - `backend/accounts/services/ldap_client.py`
- **P0-3** Jenkins gate: `TriggerRecordViewSet`,
  `UserTriggerEntriesView`, `UserNotificationPreferencesView` require
  `HasRequiredFeature("workspace_jenkins")`.
  - `backend/jenkins_trigger/views.py`
- **P0-4** `notification_result` redacted for non-admin via
  `SerializerMethodField`; visible only to `admin_jenkins`.
  - `backend/jenkins_trigger/serializers.py`

Functional regressions:

- **P0-5** Frontend `/auth/oauth/callback` route restored.
  - `frontend/src/router/index.js`
- **P0-6** OAuthCallback adds `sanitizeRedirect` (same-origin check)
  before writing tokens to URL; failure path falls back to
  `/login?oauth_error=...`.
  - `frontend/src/pages/OAuthCallback.vue`
- **P0-7** `TriggerRecordSerializer` calls in `refresh_status` pass
  `context={"request": request}` so `SerializerMethodField` can resolve
  the caller.
  - `backend/jenkins_trigger/views.py`
- **P0-8** Notification management gated end-to-end: backend
  `PlatformMetaView` exposes `enable_notifier`; frontend `user` store
  loads `platformFlags`; router guard respects
  `meta.requiresModuleFlag`; admin routes / sidebar hide the notifier
  section when disabled.
  - `backend/core/views.py`, `frontend/src/store/user.js`,
    `frontend/src/router/index.js`,
    `frontend/src/admin/routes.js`,
    `frontend/src/admin/layout/AdminSidebar.vue`

Hardening:

- **P1-9** Local accounts authenticate by email when the supplied
  identifier contains `@`.
  - `backend/accounts/auth_backends.py`
- **P1-10** Deep-link preservation in router guard (three call sites).
  - `frontend/src/router/index.js`
- **P1-11** LDAP instance deletion refused when in use by any
  `Profile`; returns HTTP 400 with `code='ldap_in_use'`.
  - `backend/accounts/views.py` (or wherever instance delete lives)
- **P1-12** `LdapAuthConfig.save` enforces single-row
  `is_default=True` inside a `transaction.atomic` block.
  - `backend/accounts/models.py`

### Documentation

- `CLAUDE.md` rewritten from a project description into an agent
  operating contract (working rules, verification gate, key paths,
  out-of-scope boundary).
- `README.md` / `README.zh-CN.md` architecture tree extended to
  include `action_orchestration/`, `tests/`, and `utils/`.
- Removed stale artifacts: `AGENTS.md`,
  `.hermes/plans/2025-05-13_000000_initial-plan.md`,
  `docs/superpowers/plans/2026-06-12-gitlab-operation-records.md`,
  `backend/docs/review_histories/ray-review-python_data_collector.md`,
  `frontend/docs/review_histories/frontend-review-current.md`.

### Known Limitations

These pre-existing test failures are not blocking v1.0.0; tracked for
v1.1.

- `backend/accounts/tests/test_access_profile.py` — 4 cases reference
  legacy manifest entries (`admin_actions`, `workspace_actions`) that
  were renamed during the manifest cleanup. Cosmetic assertion-only
  mismatch; runtime behavior is correct.
  - `AccessProfileTests::test_admin_aliases_expand_to_admin_modules`
  - `AccessProfileTests::test_legacy_default_features_preserved_without_roles`
  - `AccessProfileTests::test_staff_user_gets_all_module_features`
  - (one additional related case in the same file)
- `backend/accounts/tests/test_email_service.py` — 2 cases patch
  `accounts.services.email.get_config` which does not exist on the
  current module. The runtime email service exposes configuration
  differently; tests need to be aligned to the new accessor.
  - `EmailDeliveryOptionsTests::test_falls_back_to_django_settings_when_runtime_smtp_disabled`
  - `EmailDeliveryOptionsTests::test_uses_runtime_smtp_config_when_enabled`

Verification on v1.0.0 candidate (`99968a3`):

- `PYTHONPATH=backend /tmp/hyperops-venv/bin/python -m pytest backend/ -q --ignore=backend/agentcore`
  → **76 passed, 5 failed** (matches Known Limitations above).
- The 27 review-scoped tests added during the 12-item hardening pass
  all pass on v1.0.0.
- The `backend/agentcore/agentcore-*` submodules' own test suites are
  not run from the host project (each submodule ships its own
  `tests/` and is expected to be exercised in its own CI lane, or
  after `pip install -e backend/agentcore/<name>`).

### Security

- LDAP defaults to `CERT_REQUIRED`; operators must opt into insecure
  modes explicitly.
- All user-controlled redirect targets pass through
  `sanitizeRedirect` (same-origin only).
- Admin-only fields (`notification_result`) are gated at the
  serializer level, not just the view level.
