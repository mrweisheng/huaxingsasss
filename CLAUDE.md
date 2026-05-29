# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

企业级合同管理与智能客服系统，面向华星资源开发有限公司的两地车牌指标过户服务业务。核心流程：上传合同图片/PDF → AI (SiliconFlow Qwen-VL) 自动解析提取结构化数据 → 付款跟踪与汇率结算 → 智能问答 Agent。

Monorepo 结构：`backend/` (FastAPI) + `frontend/` (React/TypeScript)。

## Development Commands

### Backend

使用 [UV](https://docs.astral.sh/uv/) 管理依赖，无需手动激活虚拟环境，所有命令前缀 `uv run`。

```bash
cd backend

# 安装依赖
uv sync

# 启动开发服务器（热重载）
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 启动生产服务器
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000

# 启动 Celery Worker（另开终端）
uv run celery -A app.tasks.celery_app worker --loglevel=info

# 数据库迁移（生产环境启动时自动执行，无需手动运行）
uv run alembic -c migrations/alembic.ini upgrade head

# 创建新迁移
uv run alembic -c migrations/alembic.ini revision --autogenerate -m "description"

# 查看当前迁移版本
uv run alembic -c migrations/alembic.ini current

# 运行测试
uv run pytest
uv run pytest tests/test_auth.py -k "test_login"  # 单个测试
```

镜像源已配置为阿里云（`pyproject.toml` → `[tool.uv]`）。

### Frontend

```bash
cd frontend

npm install
npm run dev        # 开发服务器 http://localhost:3000，自动代理 /api → localhost:8000
npm run build      # TypeScript 检查 + Vite 构建
```

## Architecture

### Backend (`backend/app/`)

三层架构，依赖方向：`api/` → `services/` → `models/`

- **`api/v1/`** — FastAPI 路由层，处理 HTTP 请求/响应，参数校验。权限通过 `Depends(get_current_user)` 和 `Depends(require_role(...))` 注入。
- **`services/`** — 业务逻辑层，所有业务操作（含数据库事务）在此完成。路由层不直接操作 ORM。
- **`models/`** — SQLAlchemy ORM 模型，全部继承 `BaseModel`（提供 `id`, `created_at`, `updated_at`）。`models/__init__.py` 导入所有模型以确保 Alembic autogenerate 能发现。
- **`schemas/`** — Pydantic v2 模型，请求/响应数据校验。使用 `from_attributes = True` 配合 ORM。
- **`ai/`** — AI 智能体模块：
  - `agent.py` — `ContractAgent` ReAct 循环引擎，SSE 流式输出，多轮对话管理。
  - `tools.py` — `ToolExecutor` 工具执行器（10个工具）+ `TOOL_DEFINITIONS`（OpenAI function calling 格式）。所有工具调用现有 Service 层。
  - `prompts.py` — 系统提示词、凭证/合同分析提示词模板。
  - `llm_client.py` — `SiliconFlowClient`（VL 视觉模型，合同/凭证 OCR）+ `DeepSeekClient`（Agent 推理模型，流式函数调用）。
- **`core/`** — JWT 认证（`security.py`）、自定义异常（`exceptions.py`，已在 `main.py` 注册全局 handler）。
- **`config.py`** — Pydantic Settings，从 `.env` 读取配置。`SECRET_KEY` 无默认值，必须配置。

### Frontend (`frontend/src/`)

- **`services/api.ts`** — Axios 实例，含请求拦截器（自动加 Bearer token）和响应拦截器（401 自动刷新 token，队列化防并发）。
- **`store/useAuthStore.ts`** — 认证状态管理，token 存 localStorage。
- **`store/useAgentStore.ts`** — Agent 会话状态管理（会话列表、消息、SSE 流式处理、文件上传）。
- **`types/index.ts`** — TypeScript 类型定义，与后端 Pydantic Schema 对应。
- **`types/agent.ts`** — Agent 相关类型：ChatMessage、ChatSession、SSEEvent、ToolCall。
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

智能体对话流程：
1. `POST /agent/sessions` → 创建会话，获取 session_id
2. `POST /agent/upload` → 上传凭证/合同图片到临时目录，获取 file_id
3. `POST /agent/chat` (SSE) → 流式对话，携带 session_id 和 attachments
4. Agent 内部 ReAct 循环：DeepSeek 函数调用 → ToolExecutor 执行 → 结果回传 LLM → 最终回复
5. 工具调用现有 Service 层（ContractService、PaymentService 等），权限按 user.role 过滤
6. 图片分析：Agent 通过 SiliconFlow VL 模型（Qwen3-VL-32B）识别凭证内容

### Multi-currency

支持 CNY/HKD/USD 三种币种。付款时自动调用 `ExchangeRateService.convert_to_cny()` 按付款日期查找汇率。汇率来源优先级：当日录入 > 30天内最近 > 系统默认 > 代码硬编码 fallback。

## Environment Variables

关键必配项（详见 `backend/.env.example`）：
- `SECRET_KEY` — JWT 签名密钥，无默认值，必须设置
- `POSTGRES_PASSWORD` — 数据库密码
- `SILICONFLOW_API_KEY` — SiliconFlow AI 视觉模型 API 密钥（合同/凭证 OCR）
- `DEEPSEEK_API_KEY` — DeepSeek Agent 模型 API 密钥（智能对话、函数调用）

## Database Models

8 张表：`users`, `customers`, `contracts`, `payments`, `exchange_rates`, `files`, `audit_logs`, `chat_history`。

### 自动迁移

`main.py` 的 `on_startup` 事件中调用 `_run_migrations()`，每次服务启动时自动执行 `alembic upgrade head`。生产部署流程：拉代码 → 重启服务 → 自动迁移 → 正常运行。开发环境同样适用。显式设置 `script_location` 为绝对路径避免相对路径解析问题。

`chat_history` 表存储 Agent 对话消息，每行一条消息（role: user/assistant/tool），通过 `session_id` 分组为会话。包含 `tool_calls`（JSON）和 `metadata`（JSON）列支持函数调用和附件。

### Agent 工具列表

10 个工具，定义在 `backend/app/ai/tools.py` 的 `TOOL_DEFINITIONS` 中：

| 工具 | 类型 | 用途 |
|------|------|------|
| `search_customers` | 查询 | 按姓名/电话/微信群名搜索客户 |
| `search_contracts` | 查询 | 按编号/客户/状态/关键词搜索合同 |
| `get_contract_detail` | 查询 | 合同详情含全部付款记录 |
| `get_customer_contracts` | 查询 | 某客户的所有合同 |
| `query_payments` | 查询 | 按合同/状态查询付款，可查逾期 |
| `create_payment` | 动作 | 创建付款记录（自动汇率折算） |
| `get_payment_summary` | 分析 | 付款汇总（已付/待付/逾期） |
| `get_overdue_payments` | 分析 | 逾期未付款项列表 |
| `get_expiring_contracts` | 分析 | 即将到期的合同 |
| `analyze_image` | 图片 | 调用 VL 模型分析凭证/合同图片 |

权限控制：admin/finance 全量访问，sales 仅限自己名下合同，viewer 只读。

ORM 基类 `BaseModel` 使用 `DeclarativeBase`（非已弃用的 `declarative_base()`）。

## Git 远程仓库

当前仅配置 GitHub 一个远程仓库，remote 名为 `github`：
- 推送：`git push github master`
- 已移除 Gitee remote，避免混淆。

## API Docs

启动后端后访问：
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- 健康检查: http://localhost:8000/health
