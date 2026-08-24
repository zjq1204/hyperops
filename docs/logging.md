# HyperOps 日志规范

本文档是 HyperOps 第一方代码的强制日志规范。新增或修改服务日志时必须遵守；`backend/agentcore` 子模块保留其内部日志语义，但运行时接入 HyperOps 统一输出格式。

## 1. 设计目标

- 维护人员可以直接通过持久化文件排查问题，不依赖额外日志平台。
- 一次 HTTP 请求、Celery 任务和业务任务可以通过编号关联。
- 日志对人工阅读友好，同时保留稳定的 `key=value` 检索字段。
- 服务日志、访问日志、执行日志和审计日志职责清晰。
- 日志不会泄露密码、Token、Cookie、私钥或不必要的个人信息。

## 2. 日志分类

| 类型 | 记录内容 | 保存位置 |
| --- | --- | --- |
| 服务日志 | Django 业务状态、第三方调用和异常 | `logs/api/application.log` |
| 后台任务日志 | Celery Worker 和 Beat 的任务状态 | `logs/worker/worker.log`、`logs/scheduler/beat.log` |
| 访问日志 | HTTP 方法、路径、状态码和耗时 | Nginx access 日志 |
| 执行日志 | Ansible 安装过程、Jenkins 构建输出 | 对应业务任务记录 |
| 审计日志 | 凭据、权限、删除等敏感操作 | PostgreSQL 审计表 |
| 基础设施日志 | Nginx、PostgreSQL、Redis 自身状态 | 组件原生日志 |

开发环境日志根目录为 `data.dev/logs/`，生产环境为 `data/logs/`。完整 Ansible 或 Jenkins 控制台输出不得复制到服务日志。

## 3. 服务日志格式

Django、Worker 和 Beat 使用同一格式：

```text
时间 级别 [服务] [进程] [关联编号] 模块 - 可读消息 | 业务字段
```

示例：

```text
2026-08-18 15:31:02.483+08:00 INFO     [api] [pid=123] [req=6c7f0d] monitoring_stack.views - 创建组件部署任务 | job_id=18 host_id=13 component=categraf
2026-08-18 15:31:02.615+08:00 INFO     [worker] [pid=218] [task=82ad1c req=6c7f0d] monitoring_stack.tasks - 开始执行组件部署 | job_id=18 host_id=13 component=categraf
2026-08-18 15:31:16.846+08:00 ERROR    [worker] [pid=218] [task=82ad1c] monitoring_stack.tasks - 组件部署失败 | job_id=18 error_type=SSHConnectionError duration_ms=14231
```

固定要求：

- 时间精确到毫秒，默认使用 `Asia/Shanghai`，必须包含 UTC 偏移。
- 服务名由进程环境设置，只使用 `api`、`worker`、`scheduler`。
- 模块名来自 `logging.getLogger(__name__)`。
- 消息应简短、明确，同一模块保持同一种语言；HyperOps 自有业务优先使用中文。
- 动态上下文放在 `|` 后，以空格分隔的 `key=value` 输出。
- 正常记录必须单行，只有异常堆栈允许多行。
- 单条消息正文最多 4096 字符，超出部分标记为 `[TRUNCATED]`。
- Celery 未注册任务只保留任务名和堆栈，不保留消息体、headers 或投递参数。
- 不强制业务代码提供事件代码；以后接入集中日志平台时可增加结构化字段。

## 4. 关联编号

| 字段 | 含义 |
| --- | --- |
| `request_id` | 一次 HTTP 请求，由中间件生成并通过 `X-Request-ID` 返回 |
| `task_id` | 一次 Celery 执行或重试，由 Worker 自动绑定 |
| `job_id` | 部署任务、Jenkins 构建等业务任务 |
| `user_id` | 操作发起人的数据库 ID |
| `host_id` | 监控主机 ID |
| `instance_id` | Jenkins 或 GitLab 实例 ID |

HTTP 请求发布 Celery 任务时会自动透传 `request_id`。定时任务没有 HTTP 请求编号时只显示 `task_id`。日志应优先记录数据库 ID，不使用名称、邮箱或用户名代替。

## 5. 日志级别

| 级别 | 使用场景 |
| --- | --- |
| `DEBUG` | 第三方响应摘要、循环细节和开发诊断，生产默认关闭 |
| `INFO` | 服务启动、关键任务开始、完成和状态变化 |
| `WARNING` | 自动重试、缓存兜底、降级和可恢复异常 |
| `ERROR` | 操作最终失败，但服务仍能继续运行 |
| `CRITICAL` | 服务无法启动、核心依赖整体不可用或可能发生数据损坏 |

普通查询、健康检查、页面轮询、每次函数调用和正常 CRUD 成功不写服务日志。

## 6. Python 编码规则

统一使用模块 Logger 和参数化消息：

```python
import logging

logger = logging.getLogger(__name__)

logger.info(
    "开始执行组件部署 | job_id=%s host_id=%s component=%s",
    job.id,
    job.host_id,
    job.component,
)
```

禁止运行时代码使用：

```python
print(error)
logger.error(f"安装失败: {error}")
logger.info("任务 " + str(job.id) + " 已完成")
```

禁止在循环中持续输出 `INFO`。循环明细使用 `DEBUG`，批量任务只记录汇总数量和最终状态。

## 7. 异常所有权

异常只在能够决定最终结果的边界记录一次完整堆栈，例如 API View、Celery Task 或管理命令：

```python
try:
    execute_install(job)
except Exception:
    logger.exception(
        "组件部署失败 | job_id=%s host_id=%s",
        job.id,
        job.host_id,
    )
    raise
```

下层 Service 无法恢复时直接抛出，不能在 Service、Task、View 多层重复记录同一异常。可恢复异常使用 `WARNING` 并包含 `retry_count`、`retry_delay`；最后一次重试失败才使用 `ERROR`。

不得直接把 `str(exc)`、第三方完整响应体或认证 URL 写入日志。优先记录 `error_type`、`status_code`、`operation` 和脱敏摘要。

## 8. 第三方集成日志

Jenkins、GitLab、SMTP、Prometheus 等调用建议包含：

```text
integration=jenkins operation=trigger_build instance_id=3 status_code=201 duration_ms=420
```

- 成功的只读请求通常不记录。
- 状态变更请求可以记录开始和结果。
- 超时后将自动重试时使用 `WARNING`。
- 最终失败由调用边界记录 `ERROR` 或异常堆栈。
- 不记录完整 URL 查询参数、认证头、请求体或响应体。

## 9. 敏感信息规则

任何日志均禁止输出：

- 密码、Token、Cookie、Authorization 和数据库连接密码。
- SSH 私钥、完整公钥和凭据文件内容。
- Jenkins、GitLab、Grafana、SMTP 等外部系统凭据。
- 完整请求体、响应体和带查询参数的认证 URL。
- 邮箱、手机号、用户名、姓名等非排障必需的个人信息。

统一 Formatter 会对常见敏感键、Token 前缀、邮箱、URL 密钥参数和私钥块做兜底脱敏，但调用方仍有责任避免传入敏感数据。Formatter 脱敏不是记录敏感数据的许可。

## 10. 访问日志

Nginx access 日志包含时间、客户端 IP、HTTP 方法、无查询参数的路径、状态码、响应大小、请求耗时、上游耗时和 `request_id`。

健康检查和静态资源不写 access 日志。查询字符串不进入 access 日志，避免 Token 或筛选内容泄露。API 失败必须保留，便于通过 `request_id` 关联应用日志。

## 11. 文件和轮转

```text
data/logs/
├── api/application.log
├── api/gunicorn_error.log
├── worker/worker.log
├── scheduler/beat.log
├── nginx/access.log
├── nginx/error.log
└── postgresql/postgresql-YYYY-MM-DD.log
```

轮转规则：

| 日志 | 策略 |
| --- | --- |
| API、Worker、Beat | 每天或 50 MB，保留 14 份 |
| Nginx access | 每天或 50 MB，保留 7 份 |
| Nginx/Gunicorn error | 每天或 50 MB，保留 30 份 |
| PostgreSQL | 原生按日生成，保留周期由部署环境清理策略控制 |
| 审计记录 | 长期保留 |
| 部署任务元数据 | 长期保留 |
| 大体积原始执行日志 | 建议保留 90 天，单独配置清理策略 |

Python 使用 `WatchedFileHandler` 配合外部 `logrotate`。不要改为多进程不安全的 `RotatingFileHandler`。

从仓库根目录检查或执行轮转：

```bash
./docker/run-logrotate.sh -d
./docker/run-logrotate.sh
```

生产环境应由主机 cron 或 systemd timer 每天调用 `docker/run-logrotate.sh`。

## 12. 环境变量

| 变量 | 默认值 | 用途 |
| --- | --- | --- |
| `DJANGO_LOG_LEVEL` | `INFO` | API、Worker、Beat 统一日志级别 |
| `HYPEROPS_LOG_TIMEZONE` | `Asia/Shanghai` | 服务日志时区 |
| `HYPEROPS_LOG_SERVICE` | `api` | 当前进程服务名，由 Compose 设置 |
| `HYPEROPS_LOG_FILE` | 空 | 目标文件；为空时仅用于本地测试的控制台输出 |

部署环境的服务名和文件路径已经在 Compose 中设置，不应在共享 `.env` 中统一覆盖。

## 13. 排障命令

```bash
# 持续查看 API 日志
tail -F data.dev/logs/api/application.log

# 根据页面返回的请求编号定位
rg 'req=6c7f0d' data.dev/logs

# 查看一次部署任务在 API 和 Worker 中的记录
rg 'job_id=18' data.dev/logs/api data.dev/logs/worker

# 只看错误和严重错误
rg ' (ERROR|CRITICAL) ' data.dev/logs/api data.dev/logs/worker
```

`docker logs` 主要用于排查容器入口脚本、进程未启动和文件权限问题，不作为日常业务日志来源。

## 14. 自动约束

`backend/tests/test_logging_policy.py` 会检查第一方运行时代码：

- 禁止 `print()`。
- 禁止 `logger.info(f"...")` 等日志 f-string。
- 禁止把邮箱、用户名、Token、URL、响应正文和原始异常直接传给 Logger。
- Jenkins/GitLab 底层客户端禁止“记录后再抛出”，由调用边界记录最终结果。
- 动作编排、组件部署、监控同步和外部集成必须保留关键生命周期事件。
- 排除 migrations、tests 和 `backend/agentcore` 子模块。

关键格式、上下文清理、文件 Handler 和脱敏行为由 `backend/core/tests_logging.py` 覆盖。修改日志基础设施时必须同时运行这两组测试。

## 15. 当前业务覆盖

| 业务域 | 服务日志事件 | 不进入服务日志的内容 |
| --- | --- | --- |
| 监控部署 | 任务发布、执行开始、最终结果、异常、快照同步 | Ansible 逐行输出、主机密码和私钥 |
| 动作编排 | 编排发布、步骤开始/结束、部分失败、审批和拒绝 | 输入参数、审批意见、步骤输出正文 |
| Jenkins | 构建触发结果、真实状态变化、降级和最终失败 | 构建参数、队列 URL、控制台输出、无变化轮询 |
| GitLab | 采集汇总、分支/Tag/Webhook 写操作汇总和最终失败 | 项目循环明细、Webhook URL、Tag 消息、响应正文 |
| 账户安全 | 注册、密码重置、OAuth 最终结果、LDAP 服务不可用 | 邮箱、用户名、Token 前缀、普通凭据错误和校验失败 |
| 定时任务 | 注册汇总和最终失败 | 每个任务的创建/跳过明细 |
| SSH 凭据 | 仅兼容模式告警；创建、轮换、归档写数据库审计 | 凭据内容、私钥、公钥和密码 |

“已覆盖”不表示每个函数都写日志。普通查询、页面轮询、正常 CRUD、预期校验失败和循环明细必须保持安静；这些内容可通过访问日志、业务记录或审计表排查。
