# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

企业级合同管理与智能客服系统，面向华星资源开发有限公司的两地车牌指标过户服务业务。核心流程：上传合同图片/PDF → AI (Alibaba DashScope Qwen-VL) 自动解析提取结构化数据 → 收入/支出双线跟踪与汇率结算 → 利润计算 → 智能问答 Agent。

Monorepo 结构：`backend/` (FastAPI) + `frontend/` (React/TypeScript)。

### 角色体系

3 个角色，数据权限严格隔离：

| 角色 | 说明 | 数据范围 |
|------|------|----------|
| `admin` | 管理员，全部权限 | 全部数据 |
| `income` | 收入专员，录合同和客户收入 | 只看自己名下合同的收入数据 |
| `expense` | 支出专员，录支出（向第三方付款） | 只看自己创建的支出数据，可浏览所有合同 |

注册默认角色为 `income`，仅 admin 可通过 `admin_token` 指定其他角色。

### 收入/支出分离

Payment 模型通过 `type` 字段区分：
- **income**（收入）：客户向公司付款，由 income 角色管理
- **expense**（支出）：公司向第三方付款（渠道费、办证费等），由 expense 角色管理，需填写 `payee_name`（收款方）

合同同时追踪收入汇总（`paid_amount`/`paid_amount_in_cny`）和支出汇总（`total_expense`/`total_expense_in_cny`），前端展示利润 = 已收 - 支出。

### 业务类型

4 种业务类型，定义在 `backend/app/core/business_types.py`（单一数据源）：

| 类型 | 说明 |
|------|------|
| `车辆买卖` | 车辆交易业务 |
| `两地牌过户` | 中港牌指标过户 |
| `年检保险` | 年检保险业务 |
| `其他` | 其他业务 |

通过 `BusinessType.normalize()` 自动将旧值（`车辆业务`→`车辆买卖`，`中港牌业务`→`两地牌过户`）标准化。

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

# ⚠️ 数据库变更规则：不要创建 alembic 迁移脚本！
# 当 ORM 模型变更涉及表结构改动时，只提供纯 SQL（ALTER TABLE 等）给用户手动执行。
# 不要运行 alembic revision / alembic upgrade，不要生成迁移文件。

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

- **`api/v1/`** — FastAPI 路由层（7 个路由模块：auth, customers, contracts, payments, agent, files, exchange_rates），处理 HTTP 请求/响应，参数校验。权限通过 `Depends(get_current_user)` 和 `Depends(require_role(...))` 注入。
- **`services/`** — 业务逻辑层（6 个服务模块），所有业务操作（含数据库事务）在此完成。路由层不直接操作 ORM。`exchange_rate_fetcher.py` 负责外部汇率数据抓取。
- **`models/`** — SQLAlchemy ORM 模型（10 个模型文件），全部继承 `BaseModel`（提供 `id`, `created_at`, `updated_at`）。`models/__init__.py` 导入所有模型以确保 Alembic autogenerate 能发现。
- **`schemas/`** — Pydantic v2 模型（7 个 schema 模块），请求/响应数据校验。使用 `from_attributes = True` 配合 ORM。
- **`ai/`** — AI 智能体模块：
  - `agent.py` — `ContractAgent` ReAct 循环引擎，SSE 流式输出，多轮对话管理。含历史消息摘要（`_summarize_history()`）、VL 图片预分析（`_pre_analyze_image()`）、文本内容分析（`_analyze_text_content()`）。
  - `tools.py` — `ToolExecutor` 工具执行器（20 个工具）+ `TOOL_DEFINITIONS`（OpenAI function calling 格式）。含文档上下文守卫（receipt/contract/general/group_chat 阻断不匹配的工具调用）和 VL 结果 Redis 缓存。
  - `prompts.py` — 系统提示词（含角色权限描述）、凭证/合同/群聊分析提示词模板。
  - `llm_client.py` — `SiliconFlowClient`（VL 视觉模型，历史遗留包装）+ `DashScopeAgentClient`（Agent 推理模型，流式函数调用）。主用 DashScope qwen3-vl-flash 做视觉分析，deepseek-v4-flash 做 Agent 推理。
- **`core/`** — JWT 认证（`security.py`）、自定义异常（`exceptions.py`）、中间件（`middleware.py`）、日志（`logging.py`）、中文工具（`chinese.py`）、业务类型常量（`business_types.py`）。`main.py` 已注册全局异常 handler。
- **`config.py`** — Pydantic Settings，从 `.env` 读取配置。`SECRET_KEY` 无默认值，必须配置。
- **`utils/`** — 文件工具（`file_utils.py`）、API 限流器（`rate_limiter.py`）。
- **`tasks/`** — Celery 异步任务：凭证 OCR、临时文件清理、汇率同步、合同解析。

### Frontend (`frontend/src/`)

- **`services/api.ts`** — Axios 实例，含请求拦截器（自动加 Bearer token）和响应拦截器（401 自动刷新 token，队列化防并发）。
- **`services/`** — API 服务模块（auth, customer, contract, payment, agent），按业务域封装 API 调用。
- **`store/useAuthStore.ts`** — 认证状态管理，token 存 localStorage。
- **`store/useAgentStore.ts`** — Agent 会话状态管理（会话列表、消息、SSE 流式处理、文件上传）。
- **`types/index.ts`** — TypeScript 类型定义，与后端 Pydantic Schema 对应。Payment 含 `type`（income/expense）和 `payee_name` 字段，Contract 含 `total_expense`/`total_expense_in_cny` 字段。
- **`types/agent.ts`** — Agent 相关类型：ChatMessage、ChatSession、SSEEvent、ToolCall。
- **`pages/`** — Ant Design 页面组件（10 个页面），使用 React Router v6。含收付管理按币种分组 KPI 展示。
- **`components/Layout.tsx`** — 侧边栏 + 顶栏布局，按角色显示菜单（income 看客户/合同/收入，expense 看支出，admin 看全部）。
- **`components/ProtectedRoute.tsx`** — 支持 `allowedRoles` 属性的角色守卫。
- Vite 路径别名：`@` → `src/`。开发代理：`/api` → `http://localhost:8000`。
- 依赖：react-markdown + remark-gfm 用于 Agent 聊天中的 Markdown 渲染，dayjs 处理日期。

### Key Data Flow

合同上传流程：
1. `POST /contracts/upload-and-parse` → 保存文件 → 创建 draft 合同 → 返回 contract_id
2. `GET /contracts/parse-status/{contract_id}` → 前端轮询解析进度
3. AI 解析完成后合同状态变为 `active`，同时记录 `confidence` 和 `needs_review`（阈值 0.85）

付款流程（收入/支出统一入口）：
1. `POST /payments/upload-receipt` → 上传凭证 + 表单数据（含 `type` 和 `payee_name`）
2. `PaymentService.create_payment_with_exchange_rate()` 自动按付款日期查询汇率并折算 CNY（同币种跳过转换）
3. 按 `type` 分支：income → 累加 `paid_amount`，expense → 累加 `total_expense`
4. 创建即生效，直接 `status='paid'`，无需审核
5. 自动生成 `description` 可读描述

合同付款记录查询：
1. `GET /payments/contract/{id}` → 返回按 income/expense 分组的数据
2. 包含利润计算：`profit_in_cny = total_paid_in_cny - total_expense_in_cny`

智能体对话流程：
1. `POST /agent/sessions` → 创建会话，获取 session_id
2. `POST /agent/upload` → 上传凭证/合同图片到临时目录，获取 file_id
3. `POST /agent/chat` (SSE) → 流式对话，携带 session_id 和 attachments
4. Agent 内部 ReAct 循环：DashScope Agent 函数调用 → ToolExecutor 执行 → 结果回传 LLM → 最终回复
5. 工具调用现有 Service 层（ContractService、PaymentService 等），权限按 user.role 过滤
6. 图片分析：主用 DashScope VL 模型（qwen3-vl-flash）识别凭证/合同内容，含图片压缩（最大 1600px）和 Redis 缓存（30 分钟 TTL）
7. 支持 PDF 多策略分析：有文字 → 百炼 DeepSeek-V4-Flash 文本模型；扫描 PDF → 渲染为图片 → VL 模型。同时支持 Word (.docx) 和 Excel (.xlsx)。
8. 历史消息超限时自动摘要（`_summarize_history()`）

群聊识别流程：
1. 用户上传微信群截图 → `analyze_image(analysis_type="group_chat")` → 提取群名、业务类型、成员列表
2. 根据识别结果关联/创建客户和合同

凭证匹配流程：
1. `match_receipt` 工具根据客户/金额智能匹配凭证到已有付款记录
2. 匹配成功自动复制凭证到永久目录

### Multi-currency

支持 CNY/HKD/USD 三种币种。付款时自动调用 `ExchangeRateService.convert_to_cny()` 按付款日期查找汇率（同币种跳过转换）。汇率来源优先级：当日录入 > 30天内最近 > 系统默认 > 代码硬编码 fallback。合同币种为基准币种。

### 文档上下文守卫

`ToolExecutor` 内置文档类型感知守卫，防止 LLM 跨类型误操作：
- 分析 receipt 后 → 阻止 `create_contract`、`update_contract` 等
- 分析 group_chat 后 → 限制仅相关工具
- 通过 `_document_context` 跟踪最近分析的文档类型，`_check_document_guard()` 强制执行规则

## Environment Variables

关键必配项（详见 `backend/.env.example`）：
- `SECRET_KEY` — JWT 签名密钥，无默认值，必须设置
- `POSTGRES_PASSWORD` — 数据库密码
- `DASHSCOPE_API_KEY` — 阿里云 DashScope API 密钥（视觉模型 qwen3-vl-flash + Agent 推理模型 deepseek-v4-flash，合同/凭证 OCR + 智能对话）
- `SILICONFLOW_API_KEY` — SiliconFlow API 密钥（历史遗留视觉模型，仍为必配）

可选配置项（有默认值）：
- `DASHSCOPE_BASE_URL` — DashScope API 地址，默认 `https://dashscope.aliyuncs.com/compatible-mode/v1`
- `DASHSCOPE_VISION_MODEL` — 视觉模型名，默认 `qwen3-vl-flash`
- `DASHSCOPE_AGENT_MODEL` — Agent 推理模型名，默认 `deepseek-v4-flash`
- `AGENT_ORCHESTRATOR` — Agent 编排引擎，`langgraph`（默认）或 `legacy`（紧急回滚）
- `AGENT_MAX_ITERATIONS` — Agent 最大迭代次数，默认 8
- `AGENT_HISTORY_WINDOW` — 历史消息窗口，默认 100
- `AGENT_MAX_SUMMARY_MESSAGES` — 摘要触发阈值，默认 10
- `REDIS_PASSWORD` — Redis 密码
- `SCREENSHOT_UPLOAD_DIR` — 截图上传目录

## Database Models

8 张表：`users`, `customers`, `contracts`, `payments`, `exchange_rates`, `files`, `audit_logs`, `chat_history`。

### Payment 表关键字段

- `type` — `income` 或 `expense`，区分收入/支出
- `payee_name` — 收款方名称（仅 expense 使用）
- `description` — 自动生成的可读描述
- 唯一约束：`(contract_id, installment_number, type)` — 同一合同同一期数可各有一条收入和支出

### Contract 表金额字段

| 字段 | 说明 |
|------|------|
| `total_amount` / `total_amount_in_cny` | 合同总额 |
| `paid_amount` / `paid_amount_in_cny` | 已收金额（收入汇总） |
| `remaining_amount` / `remaining_amount_in_cny` | 剩余应收 |
| `total_expense` / `total_expense_in_cny` | 总支出金额（支出汇总） |
| `confidence` | AI 解析置信度（0-1） |
| `needs_review` | 是否需人工审核（confidence < 0.85 时为 true） |

利润 = `paid_amount_in_cny - total_expense_in_cny`

注意：逾期概念已被移除。逾期是计算结果而非存储状态，通过比较截止日期与当前日期实时计算。

### 数据库变更规则

**禁止创建 alembic 迁移脚本。** 当 ORM 模型变更涉及表结构改动（新增列、修改列类型、新增表等）时，只提供纯 SQL DDL/DML 语句给用户手动执行，不要生成 `migrations/versions/` 下的迁移文件。

`main.py` 的 `on_startup` 直接调用 `init_checkpointer()`（创建 LangGraph checkpoint 表），不再使用 alembic。新增的表结构变更应通过提供 SQL 语句由用户手动执行。

`chat_history` 表存储 Agent 对话消息，每行一条消息（role: user/assistant/tool），通过 `session_id` 分组为会话。包含 `tool_calls`（JSON）和 `metadata`（JSON）列支持函数调用和附件。

### Agent 工具列表

20 个工具，定义在 `backend/app/ai/tools.py` 的 `TOOL_DEFINITIONS` 中：

| 工具 | 类型 | 用途 | 权限 |
|------|------|------|------|
| `get_overview` | 统计 | 全局统计概览（处理开放式提问） | 按角色隔离 |
| `search_customers` | 查询 | 按姓名/电话/微信群名搜索客户 | 全部 |
| `create_customer` | 动作 | 创建客户（自动去重） | admin/income |
| `update_customer` | 动作 | 更新客户信息 | admin/income |
| `search_contracts` | 查询 | 按编号/客户/状态/关键词搜索合同 | income 只看自己 |
| `get_contract_detail` | 查询 | 合同详情含收入/支出记录和利润 | income 只看自己 |
| `get_customer_contracts` | 查询 | 某客户的所有合同 | income 只看自己 |
| `create_contract` | 动作 | 创建合同（编号自动生成，从缓存取 VL 结果） | admin/income |
| `update_contract` | 动作 | 更新合同信息 | admin/income |
| `query_payments` | 查询 | 按合同/类型/状态查询付款 | income 看收入，expense 看支出 |
| `create_payment` | 动作 | 创建收入付款记录 | admin/income |
| `create_expense` | 动作 | 创建支出记录（需收款方名称，期数自动生成） | admin/expense |
| `update_payment` | 动作 | 更新已有付款记录（凭证、备注等） | 按角色隔离 |
| `match_receipt` | 匹配 | 根据客户/金额智能匹配凭证到付款记录 | 全部 |
| `get_payment_summary` | 分析 | 付款汇总（按角色自动过滤类型） | 按角色隔离 |
| `get_expense_summary` | 分析 | 支出汇总（按合同/收款方聚合） | admin/expense |
| `get_expiring_contracts` | 分析 | 即将到期的合同 | income 只看自己 |
| `search_contract_text` | 知识库 | 全文关键词搜索所有合同 | income 只看自己 |
| `ask_contract` | 知识库 | 获取合同全文用于问答 | income 只看自己 |
| `analyze_image` | 文件分析 | 调用 VL 模型分析凭证/合同/群聊图片（支持 PDF/Word/Excel） | 全部 |

权限辅助方法：`_is_admin()`, `_can_view_income()`, `_can_view_expense()`, `_can_create_contract()`。

文档上下文守卫：`_document_context`, `_DOCUMENT_BLOCKED_TOOLS`, `_check_document_guard()`。

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
