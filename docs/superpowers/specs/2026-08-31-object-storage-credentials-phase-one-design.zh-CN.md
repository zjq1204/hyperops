# 对象存储凭证一期设计

日期：2026-08-31
状态：等待最终书面评审
英文版：`docs/superpowers/specs/2026-08-31-object-storage-credentials-phase-one-design.md`
原始方案：`/home/zjq/apps/2026-08-31-existing-system-object-storage-credentials-module-design.md`

## 1. 建设目标

在 HyperOps 中新增对象存储自助服务模块。员工通过飞书认证，获得一个受限的
HyperOps 本地账号，并主动申请个人专属的阿里云 OSS Bucket 和访问凭证。

该模块作为现有 HyperOps 单体应用的一部分，复用现有用户模型、登录会话、权限
清单、Django 数据库、Celery、日志、API 异常处理和前端应用框架。它不扩展监控
凭据中心，也不新建独立服务。

一期先用一个测试企业和阿里云 OSS 跑通完整且接近生产形态的闭环。数据模型从
一开始保留企业边界，后续增加企业时不需要重做表结构。

## 2. 已确认的一期范围

一期包括：

- 一个测试企业和一个飞书自建应用。
- 该企业下的一个阿里云账号和一个固定 OSS Region。
- 飞书 OAuth 登录，以及受限 HyperOps 用户的即时自动创建。
- 独立的对象存储员工工作区。
- 仅供 HyperOps 超级管理员使用的对象存储管理端。
- 每名员工一个专属阿里云 RAM 用户。
- 每名员工默认最多拥有 5 个有效个人 Bucket。
- 每张申请单只创建一个 Bucket。
- 员工对自己 Bucket 的完整对象操作权限。
- 同一员工的所有 Bucket 共用同一套 RAM 用户 AK/SK。
- AK/SK 签发、员工一次性领取、轮换，以及超级管理员受控查看。
- 异步申请执行、重试、恢复状态和审计。
- 员工自助释放空 Bucket。
- 用户停用和恢复。

一期明确不包括：

- 华为云 OBS 或阿里云以外的其他云厂商。
- 单个企业配置多个启用中的资源池。
- 人工审批流程。
- 飞书通知和通知配置。
- 超级管理员查看 SK 时的 TOTP 验证。
- 审计日志离线归档。
- 飞书组织或离职状态自动同步。
- 跨用户共享 Bucket、转移 Bucket 或多人共用 Bucket。
- 用户自行管理 Bucket ACL、Policy、公网访问、加密、版本控制、生命周期或删除
  Bucket。
- 权限漂移自动修复。
- KMS、OpenBao 或外部 Secret 管理系统。

## 3. 产品规则

### 3.1 身份与本地账号创建

现有登录页增加“飞书登录”操作。一期只有一个启用中的测试企业，因此员工不需要
选择企业。

飞书回调成功后，HyperOps 使用 `tenant_id + open_id` 识别员工。如果身份不存在，
系统自动创建：

- 一个密码不可用的 Django 本地用户。
- 不具备 staff 或 superuser 权限。
- 只能访问对象存储员工功能。
- 一个与飞书身份关联的有效企业成员关系。

HyperOps 不按姓名、邮箱或手机号自动合并账号。登录只创建本地用户和企业成员
关系，不创建 RAM 用户、Bucket、Policy 或 AccessKey。

### 3.2 首次申请

员工打开独立的“申请对象存储凭证”页面，填写：

- 项目名称。
- 使用环境：开发、测试或生产。
- 用途。
- 可选备注。

员工不选择云账号、Region、ACL、Policy、加密、版本控制、存储类型或生命周期。

首次申请成功时按顺序创建：

1. 一个不启用控制台登录的确定性个人 RAM 用户。
2. 一个位于企业固定 Region 的个人专属 OSS Bucket。
3. 一份只覆盖该员工当前有效 Bucket 的最小范围 RAM Policy。
4. 第一组 AK/SK。
5. 加密后的本地凭据记录和一次性领取凭证。

### 3.3 新增 Bucket

员工可在企业配额内拥有多个 Bucket，每张申请单创建一个 Bucket。新增 Bucket 时
复用已有 RAM 用户和有效 AK/SK，只根据最新有效 Bucket 集合重新对账员工的 RAM
Policy。

每个 Bucket 只能归属一名员工。系统不认领、不共享、不转移，也不自动接管已有
Bucket。如果阿里云返回生成的名称已经存在，申请以名称冲突失败，且不授予权限。

### 3.4 Bucket 配额

每个企业可配置单用户有效 Bucket 上限，默认值为 5。

- 有效和释放中的 Bucket 占用配额。
- 已释放 Bucket 不占用配额。
- 失败申请不占用配额。
- 并发申请必须先锁定企业成员记录，再检查配额。
- 超级管理员可以调整企业配额，但不能绕过归属和审计规则。

### 3.5 Bucket 命名

每个企业独立配置命名模板。模板只允许使用以下占位符：

```text
{tenant} {user} {project} {environment} {purpose} {suffix}
```

系统将各字段规范化为小写、符合 OSS 规则的字符，合并多余分隔符，将最终名称限制
在 3 至 63 个字符，并通过 `{suffix}` 添加确定性的短哈希。无法生成可读 ASCII
slug 的值使用稳定短哈希代替。申请页面在提交前展示准确的最终名称。

模板校验拒绝未知占位符，也拒绝无法生成有效且全局唯一名称的模板。模板修改只
影响以后创建的 Bucket。每个 Bucket 保存创建时使用的模板版本和最终名称。

### 3.6 Bucket 权限

员工 RAM 用户拥有本人所有 Bucket 的完整对象级权限，包括列表、读取、上传、
覆盖、删除和分段上传相关操作。

员工 RAM 用户不能：

- 创建或删除 Bucket。
- 访问其他员工的 Bucket。
- 修改 Bucket ACL 或 Bucket Policy。
- 开启公网访问。
- 修改加密、版本控制、生命周期、日志或复制配置。
- 把权限授予其他主体。
- 操作完成 OSS 使用所不需要的其他阿里云服务。

HyperOps 使用平台管控身份创建和配置 Bucket。业务层只表达员工当前应拥有的
Bucket 集合，阿里云适配器负责生成云厂商特定的 Policy 文档。

### 3.7 释放 Bucket

员工可以在不经过管理员审批的情况下释放本人 Bucket。释放前必须输入完整 Bucket
名称进行确认。

如果 OSS 返回 Bucket 中仍有对象、对象版本、删除标记或未完成的分段上传，
HyperOps 拒绝释放。对于空 Bucket，异步任务删除 Bucket，将它从 RAM Policy 的
目标资源集合中移除，并把本地 Bucket 标记为已释放。释放操作不可恢复。

### 3.8 AccessKey 模型

同一资源池中，一个 RAM 用户及其 AK/SK 服务于该员工名下的所有 Bucket。新增
Bucket 不签发新的 AccessKey。

轮换规则：

- 当前只有一组密钥时，直接创建第二组。
- 当前已有两组且其中一组已停用时，默认建议删除已停用密钥。
- 两组都有效时，默认建议删除创建时间最早的密钥。
- 页面只展示待删除密钥的后四位、状态和创建时间。
- 删除前必须获得员工确认。
- 阿里云 RAM 最多允许两组 AccessKey，因此先删除选中密钥，再创建替代密钥。
- 删除成功但新建失败时进入 `MANUAL_REQUIRED`，绝不能继续自动删除剩余密钥。

系统不得静默选择并删除密钥。

### 3.9 员工领取与管理员查看

每个企业配置员工领取时限，默认 24 小时，最短 10 分钟，最长 7 天。配置修改只
影响之后创建的领取凭证。

员工可以在过期前领取一次新签发的 AK/SK。领取 Token 使用安全随机值，数据库
只保存其摘要。领取成功后立即消费该凭证，员工之后若需要再次获取只能发起轮换。

加密后的凭据继续保存在数据库中。HyperOps 超级管理员填写原因后，可以查看单条
凭据。查看功能不出现在列表、批量操作、导出、员工 API 或普通管理角色中。一期
暂不要求 TOTP，但查看服务必须保留后续增加二次验证的明确扩展点。

### 3.10 用户停用与恢复

超级管理员可以停用对象存储企业成员。停用操作：

- 禁止该用户登录对象存储工作区和执行任何员工操作。
- 异步停用关联 RAM 用户的全部 AccessKey。
- 保留 RAM 用户、Bucket、对象和本地记录。

恢复成员状态后，用户可以重新进入工作区，但旧 AccessKey 不会自动重新启用。
用户必须重新签发凭据。旧密钥继续以停用状态保留，用于状态展示和审计。

## 4. 系统架构

新增独立 Django App `object_storage`，不得放入 `monitoring_stack`。

```text
backend/object_storage/
├── adapters/aliyun/       # OSS 和 RAM API 实现
├── services/              # 申请、Bucket、Policy、凭据领域服务
├── models.py
├── serializers.py
├── permissions.py
├── views.py
├── urls.py
├── tasks.py
├── periodic_tasks.py
└── migrations/
```

Provider 边界暴露业务动作，不直接向上层暴露原始 SDK 调用：

```text
validate_management_identity
find_or_create_personal_principal
create_owned_bucket
inspect_bucket_emptiness
delete_owned_bucket
reconcile_object_policy
list_access_keys
create_access_key
deactivate_access_key
delete_access_key
```

所有 API 路由统一位于 `/api/v1/object-storage/`。员工端和管理端使用独立的
Serializer，避免敏感管理字段意外出现在员工响应中。

云端操作进入低并发的独立 Celery 队列。API 请求只创建申请单并返回 ID，不等待
阿里云操作执行完成。

## 5. 数据模型

### 5.1 企业与身份

`StorageTenant`

- 企业名称、唯一编码和状态。
- Bucket 命名模板和模板版本。
- 单用户 Bucket 配额，默认 5。
- 领取时限，默认 24 小时。
- 审计保留天数，一期固定为 30 天。

`FeishuAppConfig`

- 与企业一对一关联。
- App ID 和加密后的 App Secret。
- OAuth 回调配置、验证状态和启用状态。

`StorageMembership`

- 企业、Django 用户、飞书 open ID 和可选 union ID。
- 姓名、部门快照和状态。
- 唯一约束 `(tenant_id, open_id)`，并限制 Django 用户只有一个对象存储企业成员
  关系。

### 5.2 云资源

`StorageResourcePool`

- 企业、云厂商（一期仅 `aliyun`）、云账号 ID 和固定 Region。
- 加密后的管控 AccessKey 和 Secret。
- 凭据指纹、后四位、验证状态、启用状态和最近验证时间。
- 一期限制每个企业、每个云厂商只能有一个启用中的资源池。

`StorageCloudIdentity`

- 企业、成员、资源池、RAM 用户 ID/名称和状态。
- 唯一约束 `(tenant_id, membership_id, resource_pool_id)`。

`StorageBucket`

- 企业、资源池、所属成员和云身份。
- 名称、项目、环境、用途和可选备注。
- Region、模板版本、云资源标识和状态。
- 唯一约束 `(resource_pool_id, name)`。

`StorageAccessKey`

- 企业、云身份、加密后的 AK 和加密后的 SK。
- AK 指纹和后四位。
- 云端状态、本地状态、创建时间和最近同步时间。
- 标准 Serializer 不返回明文 Secret 或数据库密文。

### 5.3 工作流与审计

`StorageApplication`

- 企业、申请人、动作类型、目标 Bucket/密钥和幂等键。
- 申请业务字段、状态、当前阶段、安全错误码和错误摘要。
- 唯一约束 `(tenant_id, applicant_id, idempotency_key)`。

`StorageApplicationAttempt`

- 企业、申请单、执行次数和 Celery 任务 ID。
- 开始/结束时间、状态、安全的 Provider 请求标识和错误码。
- 唯一约束 `(application_id, attempt_number)`。

`StorageApplicationEvent`

- 不可修改的状态变化记录，包含企业、申请单、执行、阶段、结果、安全元数据和
  时间。

`StorageDeliveryTicket`

- 企业、申请单、AccessKey、员工和 Token 摘要。
- 过期时间、消费时间、状态和尝试次数。

`StorageAuditEvent`

- 不可修改的企业级审计事件。
- 操作者、动作、目标类型/ID、原因、IP、request ID、结果和时间。
- 敏感目标只保存指纹或 AK 后四位。

包括工作流和审计表在内的每张业务表都显式保存 `tenant_id`。普通员工和企业级
查询必须通过要求企业上下文的 Manager 或 Service 执行。

## 6. 申请状态与执行

员工可见的申请状态保持精简：

```text
PENDING
RUNNING
DELIVERY_READY
SUCCEEDED
FAILED
MANUAL_REQUIRED
CANCELLED
```

技术执行阶段独立记录，包括：

```text
IDENTITY_CHECKING
QUOTA_CHECKING
BUCKET_CREATING
PRINCIPAL_BINDING
POLICY_APPLYING
KEY_DELETING
KEY_CREATING
SECRET_ENCRYPTING
DELIVERY_CREATING
BUCKET_RELEASING
KEYS_DEACTIVATING
```

Worker 执行前锁定申请单和相关成员/云身份。在每个产生云端可见变化的操作前，
重新读取阿里云实际状态。相同 Celery 消息被重复投递时返回已有结果，不重复执行
云操作。

网络、超时、限流和服务暂不可用等临时错误最多自动重试 3 次，并采用指数退避。
配置、归属、权限、密钥数量、命名、加密和资源状态不一致等错误不自动重试；需要
管理员介入时进入 `MANUAL_REQUIRED`。

恢复规则包括：

- Bucket 创建超时：重试前按准确生成名称和归属标识查询云端。
- RAM 用户创建超时：重试前按确定性 RAM 用户名和 HyperOps 标识查询云端。
- Policy 更新失败：保留 Bucket 和 RAM 用户，仅重试 Policy 对账，不签发密钥。
- AccessKey 已创建但加密失败：立即删除这一条准确的密钥；无法确认删除结果时以
  最高优先级进入 `MANUAL_REQUIRED`。
- 旧密钥已删除但替代密钥创建失败：保留剩余密钥并要求明确重试，绝不继续删除
  其他密钥。
- 一期没有通知失败处理，因为通知功能不在一期范围内。

## 7. 认证、授权与隔离

- OAuth state 短时有效、只能使用一次，并在服务端绑定企业和飞书应用配置。
- 前端传入的企业参数不能建立授权范围。
- 员工资源查询同时校验有效成员关系和 owner ID。
- 跨企业或跨 owner 访问资源 ID 时统一返回不存在。
- 只有 `is_superuser=true` 可以调用管理端 API。
- 现有普通后台角色不会自动获得对象存储管理权限。
- 飞书即时创建的本地用户密码不可用，不能通过本地密码登录。
- 页面可见性接入 HyperOps 现有权限清单；隐藏菜单不能替代 API 鉴权。

## 8. Secret 保护

一期将 Secret 加密后保存在数据库，不新增 KMS、OpenBao、环境变量或挂载密钥
文件。

HyperOps 使用 HKDF 从生产 Django `SECRET_KEY` 派生对象存储模块专用密钥，使用
固定的对象存储上下文和明确的加密版本。每个值使用独立随机 nonce 和带完整性校验
的认证加密。密文信封只保存版本、nonce 和 ciphertext。

该规则适用于：

- 飞书 App Secret。
- 阿里云管控 AccessKey ID 和 Secret。
- 员工 AccessKey ID 和 Secret。

只有在 `SECRET_KEY` 非默认、稳定且强度足够时，生产环境才允许启用该模块。未
重新加密前直接替换 `SECRET_KEY` 属于部署错误。根 Secret 变更前必须运行管理命令
重新加密所有对象存储 Secret。解密失败时阻断操作，不允许明文降级。

敏感接口设置 `Cache-Control: no-store`。前端不得把 Secret 写入 localStorage、
sessionStorage、埋点、异常上报、路由 state 或 URL 查询参数。

## 9. 日志与审计

应用日志遵循 `docs/logging.md`，只记录稳定标识：

- request ID、task ID、application ID、tenant ID、membership/user ID。
- Bucket 名称、执行阶段、安全 Provider 请求 ID、耗时和错误类型。
- 确有需要时记录 AccessKey 指纹或后四位。

日志不得包含凭据接口请求体/响应体、完整 AK/SK、密文信封、飞书 Secret、管控
凭据、Authorization Header 或领取 Token。

审计范围包括：登录自动开户、提交申请、创建云资源、变更 Policy、签发/停用/
删除密钥、员工领取、超级管理员查看、成员停用/恢复、释放 Bucket、重试和人工
处理。

审计记录在数据库保留 30 天。每天运行定时任务删除更早的审计记录。一期不做离线
归档、导出或页面删除。申请历史和当前资源状态不随审计记录一起删除。

## 10. 信息架构

### 10.1 员工工作区

侧边栏父菜单“对象存储”包含：

1. **资源概览**：Bucket 配额、RAM 用户状态、有效密钥摘要、最近申请和主要操作。
2. **我的 Bucket**：Bucket 列表、新增 Bucket、归属信息和释放操作。
3. **访问凭证**：RAM 用户、AK 状态、领取和轮换；明确提示所有个人 Bucket 共用
   这些凭证。
4. **申请记录**：首次签发、新增 Bucket、轮换、释放、进度、安全错误、重试和
   脱敏执行详情。

### 10.2 管理端

侧边栏父菜单“对象存储管理”包含：

1. **管理概览**：企业、用户、Bucket、有效密钥和异常任务数量。
2. **企业接入**：飞书应用、阿里云资源池、Region、命名模板、Bucket 配额、领取
   时限、验证和启停。
3. **资源管理**：Bucket、RAM 用户和访问凭证使用独立页签；成员停用和受控查看
   单条 Secret 位于该页面。
4. **任务中心**：申请、执行记录、重试和人工处理。
5. **审计日志**：最近 30 天脱敏记录，支持企业、用户、Bucket、动作和时间筛选。

Bucket 和 AK/SK 在界面中始终分开管理。首次申请虽然是一个工作流，但完成后的
Bucket 和凭据分别进入自己的资源页面。

长表单使用独立页面。紧凑的资源详情和安全元数据可以使用抽屉。长工作流不放在
大型弹窗中。列表优先保证扫描效率，技术执行信息放入详情页面。

## 11. 管理配置

超级管理员负责配置并验证：

- 企业名称/编码和启用状态。
- 飞书 App ID/App Secret 和 OAuth 回调。
- 阿里云账号名称/ID 和管控凭据。
- 固定 OSS Region。
- Bucket 命名模板。
- 单用户 Bucket 配额，默认 5。
- 员工凭据领取时限，默认 24 小时，限制在 10 分钟至 7 天之间。
- 是否允许员工申请。

飞书和阿里云凭据验证成功后才能启用对应配置。保存后页面只显示指纹或后四位，
永远不返回已保存 Secret。

## 12. API 设计范围

员工 API 包括：

- 当前会话的企业和对象存储个人信息。
- 资源概览。
- 本人 Bucket 和 Bucket 申请。
- 凭据摘要、一次性领取和轮换。
- 申请历史、执行记录、安全事件和重试。

管理端 API 包括：

- 企业和集成配置。
- 飞书和阿里云连接验证。
- 企业用户、云身份、Bucket、凭据和任务。
- 用户停用/恢复和任务人工恢复。
- 必须填写原因的单条 Secret 查看。
- 审计查询。

所有变更接口要求幂等键。API 返回稳定的领域错误码，不直接向客户端返回 Provider
异常原文。

## 13. 测试策略

单元测试和 API 测试必须证明：

- 飞书即时开户对每个 tenant/open ID 只创建一个受限本地用户。
- 不按个人属性自动合并身份。
- 每类资源都满足企业隔离和 owner 隔离。
- 管理 API 仅超级管理员可访问，查看 Secret 必须填写原因。
- 数据库值和日志不包含明文 Secret。
- 重复提交和 Celery 重复投递保持幂等。
- 并发申请下仍严格执行默认 5 个 Bucket 的配额。
- 命名结果确定、模板校验正确、已有名称冲突时拒绝接管。
- 新增 Bucket 复用 RAM 用户和当前 AccessKey。
- 声明式 Policy 对账准确覆盖员工当前全部有效 Bucket。
- 完整对象操作可用，同时拒绝 Bucket 管理和其他云服务操作。
- 一组/两组密钥轮换规则及异常恢复正确。
- 领取凭证只能消费一次，且按企业配置正确过期。
- 非空 Bucket 不能释放。
- 停用用户会停用密钥，恢复用户不会恢复旧密钥。
- 清理 30 天前审计记录时不删除申请和资源。

常规测试使用阿里云适配器 Mock 契约测试和已脱敏 Fixture。使用专用测试账号执行
端到端验证，覆盖上传、下载、覆盖、删除对象、拒绝跨用户访问、拒绝 Bucket 管理、
拒绝其他云服务、密钥轮换、重试和部分失败后的状态恢复。

## 14. 上线顺序

1. 增加独立 App、数据表、权限功能、功能开关和默认关闭的路由，不改变现有业务
   行为。
2. 实现 Secret 密文信封、审计、Provider 契约和领域服务。
3. 实现企业、飞书和阿里云配置及连接验证。
4. 仅对测试企业启用飞书即时开户。
5. 实现员工工作区和首次申请。
6. 增加新增 Bucket、密钥轮换、释放 Bucket、用户停用、重试和任务管理。
7. 完成鉴权、Secret 泄漏、故障注入和阿里云测试账号验证。
8. 只为测试企业启用模块。
9. 观察稳定性后，再规划多企业生产接入。

对象存储全局功能开关默认关闭。每个企业及其资源池也必须分别明确启用。

## 15. 延后阶段

二期可以增加多个生产企业、所有事件开关默认关闭的飞书通知、通知对象、TOTP
二次验证、飞书员工状态自动同步、更长审计保留或加密离线归档，以及权限漂移
报告。

三期可以通过新增 Provider 适配器支持华为云 OBS，也可以把本地加密替换为 KMS
或 OpenBao，而不改变申请、Bucket、凭据和领取的产品流程。
