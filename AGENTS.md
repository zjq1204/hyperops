# HyperOps - Jenkins & GitLab 统一管理平台

## 项目概述

HyperOps 是一个面向 Jenkins 与 GitLab 运维场景的统一管理平台，包含 Django REST API 后端和配套的 Vue 3 前端。

## 技术栈

- **后端**：Django 5 + Django REST Framework + Celery + Redis
- **前端**：Vue 3 + Vite + Tailwind CSS + Pinia + Vue Router
- **数据库**：PostgreSQL
- **通知**：可选接入 `agentcore-notifier`（飞书 + 邮件）

## 功能模块

- **Jenkins 触发**：配置触发入口，自动拉取 job 参数，用户触发构建
- **GitLab 资源管理**：群组、项目、分支、Tag、Webhook 的增删改查

## 常用命令

### 初始化

```bash
git submodule update --init --recursive   # 拉取 agentcore 子模块
```

### Docker 开发

```bash
cp env.sample .env.dev
docker-compose -f docker-compose.dev.yml up -d
# Web: http://localhost:8000
# API docs: http://localhost:8000/swagger/
```

### Docker 生产

```bash
cp env.sample .env
docker-compose up -d
# HTTP: 10080, HTTPS: 10443
```

### Django

```bash
python backend/manage.py migrate
python backend/manage.py createsuperuser
```

### 前端

```bash
cd frontend
npm install
npm run dev
```
