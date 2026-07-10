# Monitoring Console Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 HyperOps 监控平台管理从“本地配置工具集合”升级为“监控接入控制台”，清楚区分 HyperOps 管理态、Prometheus 运行态、n9e 平台态，并让用户能顺畅完成主机接入、探测配置、规则导入和部署排障。

**Architecture:** 后端继续使用 `backend/monitoring_stack` 作为监控栈管理 app，通过 Django 模型保存 HyperOps 自己管理的配置与任务记录，通过只读 summary API 对接 Prometheus/n9e 外部真实状态。前端继续使用 Vue 3 管理后台公共组件，不迁移旧 `monitor-admin` 静态页面，所有监控页面统一为现代运维控制台风格。

**Tech Stack:** Django 5, Django REST Framework, Vue 3 `<script setup>`, Vite, Tailwind/CSS, existing HyperOps admin components, Prometheus HTTP API, n9e HTTP API.

---

## Product Boundary

### HyperOps 负责什么

- 维护要纳入监控接入的 SSH 主机资产。
- 对选中的主机安装 Categraf 或 blackbox-exporter。
- 维护 HyperOps 侧的 blackbox 探测目标配置。
- 提供 Prometheus HTTP SD 输出，供 Prometheus 拉取探测目标。
- 导入 n9e 规则模板，并记录导入结果。
- 展示部署任务、安装参数、Ansible 预览、手动安装命令和失败日志。

### HyperOps 不伪装成什么

- 不把本地资产数量说成 n9e 真实主机数量。
- 不把本地探测目标数量说成 Prometheus 当前真实 target 数量。
- 不在拿不到 n9e API 数据时猜测“有多少主机 / 有多少规则”。
- 不把安装包页放在主导航里当普通用户入口；安装包和脚本属于高级维护能力。

### 页面命名

- 后台菜单：`监控接入控制台`
- 权限 key：`admin_monitoring`
- API 前缀：`/api/v1/monitoring/`
- 后端 app：`monitoring_stack`
- 主页面：
  - `/management/monitoring/overview`
  - `/management/monitoring/assets`
  - `/management/monitoring/probes`
  - `/management/monitoring/rules`
  - `/management/monitoring/jobs`
  - `/management/monitoring/settings`

---

## Phase 1: Navigation And Console Boundary

**Status:** Completed.

**User-visible result:**

- 侧边栏不再叫泛泛的“监控平台管理”，改为“监控接入控制台”。
- 默认入口从安装包页调整到接入概览页。
- 主导航只保留日常操作路径：接入概览、采集主机、探测目标、告警规则、部署任务、集成配置。
- 安装包页仍可访问，但不再作为普通用户第一入口。

**Files:**

- Modify: `/home/zjq/apps/hyperops/frontend/src/admin/layout/AdminSidebar.vue`
- Modify: `/home/zjq/apps/hyperops/frontend/src/admin/routes.js`
- Create: `/home/zjq/apps/hyperops/frontend/src/admin/pages/Monitoring/Overview.vue`
- Create: `/home/zjq/apps/hyperops/frontend/src/admin/pages/Monitoring/Settings.vue`
- Modify: `/home/zjq/apps/hyperops/frontend/src/admin/locales/zh-CN.json`
- Modify: `/home/zjq/apps/hyperops/frontend/src/admin/locales/en.json`
- Modify: `/home/zjq/apps/hyperops/frontend/tests/_review/admin-monitoring-stack-contract.test.mjs`

**Acceptance criteria:**

- `/management/monitoring/overview` 能打开。
- 拥有 `admin_monitoring` 权限时，侧边栏显示“监控接入控制台”。
- 点击“监控接入控制台”默认进入接入概览。
- 侧边栏没有把“安装包”作为主入口。

**Verification:**

```bash
cd /home/zjq/apps/hyperops/frontend
node tests/_review/admin-monitoring-stack-contract.test.mjs
npm run build
```

---

## Phase 2: Component Installation State

**Status:** Completed.

**User-visible result:**

- 资产页不再只是一张 SSH 主机表。
- 每台主机能看到 Categraf 安装状态。
- 每台主机能看到 blackbox-exporter 安装状态。
- 安装任务执行中、成功、失败后，资产页状态能跟着变化。

**Files:**

- Modify: `/home/zjq/apps/hyperops/backend/monitoring_stack/models.py`
- Create: `/home/zjq/apps/hyperops/backend/monitoring_stack/migrations/0004_monitoringcomponentstatus.py`
- Modify: `/home/zjq/apps/hyperops/backend/monitoring_stack/serializers.py`
- Modify: `/home/zjq/apps/hyperops/backend/monitoring_stack/services/core.py`
- Modify: `/home/zjq/apps/hyperops/frontend/src/admin/pages/Monitoring/Assets.vue`

**Data model:**

- `MonitoringComponentStatus.host`: related monitored host.
- `MonitoringComponentStatus.component`: `categraf` or `blackbox`.
- `MonitoringComponentStatus.status`: `not_installed`, `installing`, `success`, `failed`.
- `MonitoringComponentStatus.last_task`: latest install task.
- `MonitoringComponentStatus.last_error`: latest failure message snippet.
- `MonitoringComponentStatus.installed_at`: success timestamp.

**Acceptance criteria:**

- 新主机默认显示组件未安装状态。
- 发起 Categraf 安装后，选中主机 Categraf 状态进入 installing。
- 发起 blackbox 安装后，选中主机 blackbox 状态进入 installing。
- 任务成功后对应组件状态为 success。
- 任务失败后对应组件状态为 failed，并保存错误摘要。

**Verification:**

```bash
cd /home/zjq/apps/hyperops
docker exec backend-api-dev sh -lc 'cd /opt/backend && python manage.py migrate monitoring_stack'
docker exec backend-api-dev sh -lc 'cd /opt/backend && python manage.py check'
```

---

## Phase 3: Prometheus Runtime State

**Status:** Completed.

**User-visible result:**

- 概览页显示 Prometheus 是否配置、是否可连接、当前 active targets、down targets、blackbox targets。
- 探测目标页每条目标显示 Prometheus 真实运行状态：`up`、`down` 或 `unknown`。
- 用户能知道“我在 HyperOps 配了目标”和“Prometheus 真的拉到了目标”是两回事。

**Files:**

- Modify: `/home/zjq/apps/hyperops/backend/monitoring_stack/services/core.py`
- Modify: `/home/zjq/apps/hyperops/backend/monitoring_stack/views.py`
- Modify: `/home/zjq/apps/hyperops/backend/monitoring_stack/urls.py`
- Modify: `/home/zjq/apps/hyperops/frontend/src/admin/api/monitoringStack.js`
- Modify: `/home/zjq/apps/hyperops/frontend/src/admin/pages/Monitoring/Overview.vue`
- Modify: `/home/zjq/apps/hyperops/frontend/src/admin/pages/Monitoring/Probes.vue`

**API contract:**

- `GET /api/v1/monitoring/prometheus/targets/summary/`
- Response includes:
  - `configured`
  - `connected`
  - `prometheus_url`
  - `active_targets`
  - `down_targets`
  - `blackbox_targets`
  - `targets`
  - `error`

**Acceptance criteria:**

- Prometheus 未配置时，页面显示“未配置”，不报前端错误。
- Prometheus 不可连接时，页面显示错误摘要，不把状态伪装成 0。
- Prometheus 可连接时，概览页显示真实 target 数量。
- 探测目标页能够根据 Prometheus target 匹配出每条探测目标的运行状态。

**Verification:**

```bash
docker exec backend-api-dev sh -lc 'cd /opt/backend && python manage.py shell -c "from monitoring_stack.services.core import prometheus_targets_summary; import json; print(json.dumps(prometheus_targets_summary(), ensure_ascii=False))"'
```

---

## Phase 4: n9e Platform State

**Status:** Completed.

**User-visible result:**

- 概览页显示 n9e URL 是否配置、账号是否配置、API 是否可连接。
- 如果没有 n9e 凭证，页面明确提示“凭证未配置”。
- 如果当前 n9e API 暂时没有接入主机 / 规则数量查询，页面显示“API 未提供”，不再显示误导性统计。

**Files:**

- Modify: `/home/zjq/apps/hyperops/backend/core/settings/base.py`
- Modify: `/home/zjq/apps/hyperops/env.sample`
- Modify: `/home/zjq/apps/hyperops/.env.dev`
- Modify: `/home/zjq/apps/hyperops/backend/monitoring_stack/services/core.py`
- Modify: `/home/zjq/apps/hyperops/backend/monitoring_stack/views.py`
- Modify: `/home/zjq/apps/hyperops/backend/monitoring_stack/urls.py`
- Modify: `/home/zjq/apps/hyperops/frontend/src/admin/api/monitoringStack.js`
- Modify: `/home/zjq/apps/hyperops/frontend/src/admin/pages/Monitoring/Overview.vue`
- Modify: `/home/zjq/apps/hyperops/frontend/src/admin/pages/Monitoring/Settings.vue`

**Environment variables:**

```bash
MONITORING_N9E_URL=http://monitor-n9e:17000
MONITORING_N9E_USERNAME=
MONITORING_N9E_PASSWORD=
```

**API contract:**

- `GET /api/v1/monitoring/n9e/summary/`
- Response includes:
  - `configured`
  - `connected`
  - `auth_configured`
  - `n9e_url`
  - `business_groups`
  - `prometheus_datasources`
  - `hosts_available`
  - `rules_available`
  - `error`

**Acceptance criteria:**

- n9e URL 为空时显示未配置。
- n9e URL 有值但账号密码为空时显示凭证未配置。
- n9e API 登录失败时显示认证错误。
- n9e 连接成功但主机/规则数量 API 未接入时，显示“API 未提供”。

**Verification:**

```bash
docker exec backend-api-dev sh -lc 'cd /opt/backend && python manage.py shell -c "from monitoring_stack.services.core import n9e_platform_summary; import json; print(json.dumps(n9e_platform_summary(), ensure_ascii=False))"'
```

---

## Phase 5: Alert Rules Page Redesign

**Status:** In progress.

**User-visible result:**

- 告警规则页不再是一块空列表或一堆文件名。
- 规则模板按用途分类：主机、Categraf、MySQL、Redis、Nginx、探测。
- 用户可以按分类筛选模板。
- 导入 n9e 后展示摘要：成功数量、跳过数量、失败数量。
- 原始导入结果默认折叠，用户需要排查时再展开。
- 每次导入都保存记录，后续可以追踪“谁在什么时候导入了什么模板，结果如何”。

**Files:**

- Modify: `/home/zjq/apps/hyperops/backend/monitoring_stack/models.py`
- Create: `/home/zjq/apps/hyperops/backend/monitoring_stack/migrations/0005_ruleimportrecord.py`
- Modify: `/home/zjq/apps/hyperops/backend/monitoring_stack/services/core.py`
- Modify: `/home/zjq/apps/hyperops/backend/monitoring_stack/views.py`
- Modify: `/home/zjq/apps/hyperops/backend/monitoring_stack/tests/test_monitoring_stack_api.py`
- Modify: `/home/zjq/apps/hyperops/frontend/src/admin/pages/Monitoring/Rules.vue`
- Modify: `/home/zjq/apps/hyperops/frontend/src/admin/locales/zh-CN.json`
- Modify: `/home/zjq/apps/hyperops/frontend/src/admin/locales/en.json`
- Modify: `/home/zjq/apps/hyperops/frontend/tests/_review/admin-monitoring-stack-contract.test.mjs`

**Backend data model:**

- `RuleImportRecord.template_name`: imported template filename.
- `RuleImportRecord.template_category`: normalized category.
- `RuleImportRecord.status`: `success`, `partial`, or `failed`.
- `RuleImportRecord.summary`: JSON summary returned to frontend.
- `RuleImportRecord.result`: raw n9e import response.
- `RuleImportRecord.created_by`: admin user if available.
- `RuleImportRecord.created_at`: timestamp.

**Frontend behavior:**

- `Rules.vue` imports `computed`.
- `selectedCategory` defaults to `all`.
- `ruleCategories` contains all visible filter chips.
- `filteredRules` filters by `selectedCategory`.
- `categoryLabel(category)` reads i18n labels.
- `importSummaryCards` maps summary counts into visible cards.
- `importRules()` stores both summary and raw result.

**Required i18n keys:**

- `adminPages.monitoring.ruleCategoryAll`
- `adminPages.monitoring.ruleCategoryHost`
- `adminPages.monitoring.ruleCategoryCategraf`
- `adminPages.monitoring.ruleCategoryMysql`
- `adminPages.monitoring.ruleCategoryRedis`
- `adminPages.monitoring.ruleCategoryNginx`
- `adminPages.monitoring.ruleCategoryProbe`
- `adminPages.monitoring.importResult`
- `adminPages.monitoring.importSuccessCount`
- `adminPages.monitoring.importSkippedCount`
- `adminPages.monitoring.importFailedCount`
- `adminPages.monitoring.rawResult`

**Acceptance criteria:**

- 告警规则页不显示 `adminPages.monitoring.*` 原始 key。
- 分类切换后模板列表正确过滤。
- 导入成功后页面显示摘要卡片。
- 失败导入也写入 `RuleImportRecord`，并显示失败原因。
- 原始 JSON 不默认占满页面，必须折叠或放在详情区域。

**Verification:**

```bash
cd /home/zjq/apps/hyperops/frontend
node tests/_review/admin-monitoring-stack-contract.test.mjs
npm run build

cd /home/zjq/apps/hyperops
docker exec backend-api-dev sh -lc 'cd /opt/backend && python manage.py makemigrations --check --dry-run monitoring_stack && python manage.py check'
docker exec backend-api-dev sh -lc 'cd /opt/backend && python manage.py migrate monitoring_stack'
```

---

## Phase 6: Deployment Jobs As Troubleshooting Center

**Status:** Pending.

**User-visible result:**

- 部署任务页不再只是任务流水表。
- 用户可以快速知道：
  - 哪个任务失败。
  - 哪些主机失败。
  - 失败阶段是什么。
  - 最后一段错误是什么。
  - 本次任务使用了哪些 inventory 和 vars。
  - 如何复制手动命令绕过自动执行。
  - 是否可以只重试失败主机。

**Files:**

- Modify: `/home/zjq/apps/hyperops/backend/monitoring_stack/models.py`
- Modify: `/home/zjq/apps/hyperops/backend/monitoring_stack/services/core.py`
- Modify: `/home/zjq/apps/hyperops/backend/monitoring_stack/views.py`
- Modify: `/home/zjq/apps/hyperops/backend/monitoring_stack/urls.py`
- Modify: `/home/zjq/apps/hyperops/backend/monitoring_stack/tests/test_monitoring_stack_api.py`
- Modify: `/home/zjq/apps/hyperops/frontend/src/admin/pages/Monitoring/Jobs.vue`
- Modify: `/home/zjq/apps/hyperops/frontend/src/admin/api/monitoringStack.js`
- Modify: `/home/zjq/apps/hyperops/frontend/src/admin/locales/zh-CN.json`
- Modify: `/home/zjq/apps/hyperops/frontend/src/admin/locales/en.json`

**Backend behavior:**

- Job list includes `component`, `status`, `total_hosts`, `success_hosts`, `failed_hosts`, `duration_seconds`, `last_error`.
- Job detail includes `inventory`, `vars`, `manual_command`, `host_results`, `logs`.
- Retry endpoint creates a new job from failed hosts only.
- Retry job keeps reference to original job.

**Frontend behavior:**

- List top area has filters for component and status.
- Table columns show component, status, host success ratio, duration, created time, actions.
- Detail drawer/tabs:
  - `执行结果`
  - `失败主机`
  - `Ansible 预览`
  - `手动命令`
  - `日志`
- Copy manual command uses Clipboard API and visible success/failure feedback.
- Retry failed hosts button only appears when failed hosts count is greater than 0.

**Acceptance criteria:**

- 用户能在 10 秒内从任务页定位失败任务和失败主机。
- 复制手动命令不会展开无关区域。
- 没有失败主机时不显示“重试失败主机”按钮。
- 重试只针对失败主机，不重复执行成功主机。
- 长日志、长命令、长主机名不撑破页面。

**Verification:**

```bash
cd /home/zjq/apps/hyperops/frontend
npm run build

cd /home/zjq/apps/hyperops
docker exec backend-api-dev sh -lc 'cd /opt/backend && python manage.py check'
```

---

## Phase 7: Final Verification And Manual Review

**Status:** Pending.

**Automated checks:**

```bash
cd /home/zjq/apps/hyperops/frontend
node tests/_review/admin-monitoring-stack-contract.test.mjs
npm run build

cd /home/zjq/apps/hyperops
docker exec backend-api-dev sh -lc 'cd /opt/backend && python manage.py makemigrations --check --dry-run monitoring_stack && python manage.py check'
git diff --check
```

**Runtime checks:**

```bash
docker restart backend-api-dev backend-worker-dev backend-scheduler-dev 40393a23b758_frontend-dev
curl -I --max-time 10 http://192.168.7.168:18080/management/monitoring/overview
curl -I --max-time 10 http://192.168.7.168:18080/management/monitoring/assets
curl -I --max-time 10 http://192.168.7.168:18080/management/monitoring/probes
curl -I --max-time 10 http://192.168.7.168:18080/management/monitoring/rules
curl -I --max-time 10 http://192.168.7.168:18080/management/monitoring/jobs
curl -I --max-time 10 http://192.168.7.168:18080/management/monitoring/settings
```

**Manual browser review:**

- `/management/monitoring/overview`
  - Shows HyperOps local config, Prometheus runtime state, and n9e platform state separately.
  - Does not show fake totals for unavailable n9e data.
- `/management/monitoring/assets`
  - Add host modal only adds SSH host fields.
  - Install Categraf uses a step-by-step wizard.
  - Install blackbox uses a step-by-step wizard.
  - Categraf template selection and template-specific parameters live in install flow, not add-host flow.
- `/management/monitoring/probes`
  - Add target opens a modal, not an awkward side panel.
  - Table shows current configured targets.
  - Prometheus runtime status is visible when available.
- `/management/monitoring/rules`
  - Rule templates are categorized.
  - Import result is summarized.
  - Raw result is available but not visually dominant.
- `/management/monitoring/jobs`
  - Failed jobs are easy to identify.
  - Detail view helps troubleshooting.
  - Manual command can be copied.
- `/management/monitoring/settings`
  - Prometheus/n9e/Grafana integration status is understandable.
  - Missing credentials are shown as configuration gaps, not system failures.

**Definition of done:**

- No page shows untranslated `adminPages.monitoring.*` keys.
- No monitoring page is empty without explaining why.
- No page mixes HyperOps local configuration counts with Prometheus/n9e real runtime counts.
- Build passes.
- Django check passes.
- Migration dry-run reports no missing migrations.
- Browser pages return HTTP 200.

