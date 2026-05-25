# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

企业级合同管理与智能客服系统，面向华星资源开发有限公司的两地车牌指标过户服务业务。核心流程：上传合同图片/PDF → AI (SiliconFlow Qwen-VL) 自动解析提取结构化数据 → 付款跟踪与汇率结算 → 智能问答 Agent。

Monorepo 结构：`backend/` (FastAPI) + `frontend/` (React/TypeScript)。

## Development Commands

### Backend

```bash
cd backend

# 安装依赖
poetry install

# 启动 PostgreSQL + Redis
docker-compose up -d postgres redis

# 数据库迁移
cd migrations && alembic upgrade head

# 创建新迁移
cd migrations && alembic revision --autogenerate -m "description"

# 启动开发服务器（热重载）
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 运行测试
pytest
pytest tests/test_auth.py -k "test_login"  # 单个测试
```

### Frontend

```bash
cd frontend

npm install
npm run dev        # 开发服务器 http://localhost:3000，自动代理 /api → localhost:8000
npm run build      # TypeScript 检查 + Vite 构建
```

### Full Stack (Docker)

```bash
cd backend
docker-compose up --build   # 启动全部服务（PostgreSQL + Redis + Backend）
```

## Architecture

### Backend (`backend/app/`)

三层架构，依赖方向：`api/` → `services/` → `models/`

- **`api/v1/`** — FastAPI 路由层，处理 HTTP 请求/响应，参数校验。权限通过 `Depends(get_current_user)` 和 `Depends(require_role(...))` 注入。
- **`services/`** — 业务逻辑层，所有业务操作（含数据库事务）在此完成。路由层不直接操作 ORM。
- **`models/`** — SQLAlchemy ORM 模型，全部继承 `BaseModel`（提供 `id`, `created_at`, `updated_at`）。`models/__init__.py` 导入所有模型以确保 Alembic autogenerate 能发现。
- **`schemas/`** — Pydantic v2 模型，请求/响应数据校验。使用 `from_attributes = True` 配合 ORM。
- **`ai/`** — SiliconFlow Qwen-VL 客户端，合同图片 OCR 解析 + 问答生成。
- **`core/`** — JWT 认证（`security.py`）、自定义异常（`exceptions.py`，已在 `main.py` 注册全局 handler）。
- **`config.py`** — Pydantic Settings，从 `.env` 读取配置。`SECRET_KEY` 无默认值，必须配置。

### Frontend (`frontend/src/`)

- **`services/api.ts`** — Axios 实例，含请求拦截器（自动加 Bearer token）和响应拦截器（401 自动刷新 token，队列化防并发）。
- **`store/useAuthStore.ts`** — Zustand 状态管理，token 存 localStorage。
- **`types/index.ts`** — TypeScript 类型定义，与后端 Pydantic Schema 对应。
- **`pages/`** — Ant Design 页面组件，使用 React Router v6。
- **`components/Layout.tsx`** — 侧边栏 + 顶栏布局，Ant Design Sider。
- Vite 路径别名：`@` → `src/`。开发代理：`/api` → `http://localhost:8000`。

### Key Data Flow

合同上传流程：
1. `POST /contracts/upload-and-parse` → 保存文件 → 创建 draft 合同 → 返回 contract_id
2. `GET /contracts/parse-status/{contract_id}` → 前端轮询解析进度
3. AI 解析完成后合同状态变为 `active`

付款流程：
1. `POST /payments/upload-receipt` → 上传凭证 + 表单数据
2. `PaymentService` 自动按付款日期查询汇率并折算 CNY
3. 跨币种付款通过汇率折算为合同币种后累加 `paid_amount`

### Multi-currency

支持 CNY/HKD/USD 三种币种。付款时自动调用 `ExchangeRateService.convert_to_cny()` 按付款日期查找汇率。汇率来源优先级：当日录入 > 30天内最近 > 系统默认 > 代码硬编码 fallback。

## Environment Variables

关键必配项（详见 `backend/.env.example`）：
- `SECRET_KEY` — JWT 签名密钥，无默认值，必须设置
- `POSTGRES_PASSWORD` — 数据库密码
- `SILICONFLOW_API_KEY` — AI 合同解析 API 密钥

## Database Models

7 张表：`users`, `customers`, `contracts`, `payments`, `exchange_rates`, `files`, `audit_logs`, `chat_history`。

ORM 基类 `BaseModel` 使用 `DeclarativeBase`（非已弃用的 `declarative_base()`）。

## API Docs

启动后端后访问：
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- 健康检查: http://localhost:8000/health
