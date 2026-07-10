# HyperOps

[English](README.md) | [中文](README.zh-CN.md)

HyperOps 是一个聚焦于 Jenkins 与 GitLab 运维管理的 Django + Vue 平台。

## 当前范围

- Jenkins 实例管理与触发入口管理
- Jenkins 构建触发与记录追踪
- GitLab 实例、群组、项目、分支、Tag、Webhook 管理
- Prometheus + n9e + Grafana 监控体系组件管理
- 登录鉴权、个人资料、基于角色的访问控制

## 架构概览

```text
hyperops/
├── backend/
│   ├── core/                  # Django settings、URL、Celery 启动
│   ├── accounts/              # 鉴权、Profile、Role、访问画像
│   ├── jenkins_trigger/       # Jenkins 实例、入口、记录
│   ├── gitlab_resource/       # GitLab 资源管理
│   ├── action_orchestration/  # 可复用动作模板与执行
│   ├── monitoring_stack/      # Prometheus/n9e/Grafana 组件管理
│   ├── tests/                 # 跨 app 复用的 pytest 入口与配置
│   └── agentcore/             # 可选集成（git submodule）
└── frontend/                  # Vue 3 + Vite 前端
```

## 可选集成

以下能力由 `.env` 控制；示例配置默认开启通知模块，便于直接使用通知管理后台：

- `ENABLE_NOTIFIER=true`
- `ENABLE_AGENTCORE_TASK=true`
- `ENABLE_AGENTCORE_METERING=true`

只开启实际需要的模块即可。

监控平台安装资源默认位于 `STORAGE_ROOT/monitoring_stack/`。后端通过
`/api/v1/monitoring/` 暴露 Prometheus HTTP SD、安装资源下载和监控组件管理 API。

## 快速开始

```bash
git submodule update --init --recursive
cp env.sample .env.dev
docker-compose -f docker-compose.dev.yml up -d
```

常用后端命令：

```bash
python3 backend/manage.py migrate
python3 backend/manage.py createsuperuser
python3 backend/manage.py check
```

常用前端命令：

```bash
cd frontend
npm install
npm run dev
npm run build
```

## 运行地址

- Web UI：`http://localhost:8000`
- Swagger：`http://localhost:8000/swagger`
- Admin：`http://localhost:8000/admin`

## 说明

- 仓库里仍保留了一些历史实验阶段的模块和组件，但 HyperOps 的运行时入口已经收敛到 Jenkins、GitLab、监控平台、鉴权和管理后台这几块能力。
- `agentcore_notifier` 仍可作为 Jenkins 构建通知的可选集成使用。
