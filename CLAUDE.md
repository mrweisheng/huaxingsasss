# CLAUDE.md

## Agent 模式（最高优先级）

**判断标准：找到每一个决定"下一步做什么"的 if/else。**
**这个 if 是你写的 = 流水线，LLM 运行时做的 = Agent。**

```
正确：工具返回结果 → LLM 看结果 → LLM 决定下一步（调哪个工具 / 问用户 / 结束）
错误：工具返回结果 → 代码 if/else 决定下一步 → LLM 没有选择权
```

**修改或新增任何业务逻辑前，先回答 3 个问题：**

1. **这是流水线场景还是 agent 场景？**
   - 流水线（纯 CRUD、Service 层、确定规则的表单操作）→ 走既有分层，代码直接执行
   - agent（自然语言理解、多步推理、工具组合）→ LLM 决策，代码只做执行
2. **业务规则放哪一层？**
   - 数据完整性 / 安全边界 / 权限 → 工具层 / Service 层硬编码
   - 业务偏好 / 展示风格 / 追问策略 → system prompt 软规则
   - 工具能力约束（如图片必须先识别）→ 写在工具描述或节点逻辑里
3. **我是不是在用 if/else 偷懒代替 LLM 决策？**
   - 如果是 → 改成让 LLM 看上下文自己判断

**工具铁律：** 工具只返回事实 JSON，不嵌入"建议下一步""请先..."等行为指令。

**不适用本规则的范围：** 纯表单 CRUD、标准 REST 增删改查、Service 层业务封装、纯查询接口——这些是流水线，按既有规范写即可。

## 硬规则

- 禁止创建 alembic 迁移脚本，DDL 以纯 SQL 提供
- 禁止修改已上线接口的响应格式
- 数据库操作只走 Service 层，路由层不操作 ORM
- 禁止把 agent 能做的判断用 Python if/else 硬编码实现（除非属于"工具能力约束"或"数据完整性"边界）

## 业务架构（四大功能 → 三个子图 → 一个 Root Graph）

```
用户 → intake_node（推断意图）→ route_by_intent
  ├─ 上传合同 + 关联客户 → contract_entry_subgraph
  ├─ 录入收支             → receipt_entry_subgraph
  └─ 查询                 → general_chat_subgraph
```

前端入口：`AgentChat`（/agent 智能问答） + `ContractChatModal`（/contracts 上传按钮），均走 `POST /api/v1/agent/chat` SSE。合同列表卡片的「收」「支」按钮会创建 `mode=receipt_income|receipt_expense` 的会话，凭证子图通过 session_context 拿到 `contract_id`/`payment_type`，不依赖用户再次输入。

### 编排层职责边界

| 层 | 文件 | 职责 | 决策方 |
|---|---|---|---|
| Root Graph | `orchestrator/graph.py` | 意图推断 + 路由 + finalize 落库 | 代码（确定性） |
| 子图 | `orchestrator/{contract,receipt,general}_entry.py` | 循环：analyze → call_model ↔ execute_tool | LLM + 代码混合（敏感工具由计划驱动安全门守门） |
| 工具执行 | `ai/tools.py` `ToolExecutor` | 调 Service 层，返回纯 JSON 事实 | 代码（确定性） |
| Service | `services/*.py` | 业务规则、权限校验、事务边界 | 代码（确定性） |
| 模型 / DB | `models/*.py` | ORM 映射、表结构 | 代码 |
| 提示词 | `ai/prompts.py` | 业务偏好、追问策略、字段解释 | LLM 软规则 |
| 安全门 | 子图 `_SENSITIVE_TOOLS` 集合 + `set_pending_plan` 计划驱动 | 防止 LLM 跳过确认执行高危工具 | 代码硬约束 + LLM 多轮对话确认 |

### Root Graph 路由矩阵

| intent | executor_mode | 路由目标 |
|---|---|---|
| `contract_entry` | `chat` | `contract_entry_subgraph` |
| `receipt_entry` | `receipt_income` / `receipt_expense` | `receipt_entry_subgraph`（完整 Agent 循环） |
| `receipt_entry` | 其他 | `receipt_entry_node`（降级引导到合同卡片按钮） |
| `group_chat` | * | `group_chat_node`（降级引导到手动关联） |
| `general` | * | `general_chat_subgraph` |

意图推断在 `graph.py:_infer_intent()`：文档类（pdf/word/excel）激进路由到 `contract_entry`（子图 VL 二次判断兜底），图片类保持收窄（避免误识别凭证/合同）。

### 子图循环架构（Agent 模式 vs 流水线的边界）

```
analyze_{file,receipt}_node（确定性）→ call_model_node（LLM 决策）
                                          ↑                ↓
                                          └── execute_tool_node ┘
                                                 │
                                                 ├─ 敏感工具 → 计划驱动安全门（set_pending_plan）
                                                 │             └─ LLM 展示计划 → 用户自然语言确认 → LLM 调 set_pending_plan(confirmed=true)
                                                 └─ 普通工具 → 直接执行 → ToolMessage 回灌
```

- `analyze_*_node`：确定性预分析（VL/OCR/DB 查询），不消耗 LLM token，结果注入 messages
- `call_model_node`：LLM 决定展示什么、调哪个工具、追问还是结束（迭代上限 `settings.AGENT_MAX_ITERATIONS=8`）
- `execute_tool_node`：工具执行；敏感工具走计划驱动安全门——LLM 先调 `set_pending_plan` 声明计划，代码层硬约束校验 `user_confirmed` 后才放行 `create_*`（合同：`create_customer`/`create_contract`；凭证：`create_payment`/`create_expense`）。用户确认通过自然语言（如"确认"），LLM 自行判断语义
- `finalize_node`（Root 层）：`chat_history` 并行落库（ADR #6，checkpoint 存机器可读状态，`chat_history` 存人类可读消息，职责不同不互相替代），用 `_finalized` 标记做幂等防护

## 技术锚点

- 后端：uv · FastAPI · SQLAlchemy 2.x · Pydantic v2 · pydantic_settings
- 前端：npm · Vite · React · TypeScript · Zustand
- Agent 编排：LangGraph 1.2.x · `StateGraph` / `astream_events(version="v2")`
- Checkpoint：`AsyncPostgresSaver` + `psycopg3` `AsyncConnectionPool`（`autocommit=True`、`prepare_threshold=0`），复用现有 PG，`main.py:on_startup` 调 `init_checkpointer()` 自动建表
- LLM 客户端：`backend/app/ai/llm_client.py` — `DashScopeAgentClient`（百炼 qwen3-vl-flash 视觉 + 文本）、`SiliconFlowClient`（SiliconFlow VL 兜底）。**不引入** `langchain-openai` / `ChatOpenAI`（ADR #2：百炼兼容模式 `tools` 与 `stream=True` 互斥）
- 工具执行：`backend/app/ai/tools.py` — 17 个工具，`TOOL_DEFINITIONS`（OpenAI function calling 格式）+ `ToolExecutor`（含 `mode guard` 拦截越权工具、`document guard` 防止重复识别）
- 编排层：`backend/app/ai/orchestrator/` — `graph.py`(Root) / `state.py`(RootState + 3 子 State) / `checkpointer.py` / `contract_entry.py` / `receipt_entry.py` / `general_chat.py` / `sse_adapter.py`
- 业务封装：`backend/app/services/` — 工具层不直接 ORM，统一走 Service
- 可观测性：`.env` 设 `LANGCHAIN_TRACING_V2=true` 后 LangGraph 节点自动埋点到 LangSmith（`main.py:on_startup` 同步 env）

## SSE 事件协议（前后端约定）

`POST /api/v1/agent/chat` 流式事件类型（`sse_adapter.py` 适配 LangGraph astream_events → 旧事件格式）：

| event | 用途 | 前端处理 |
|---|---|---|
| `thinking` | 节点开始（友好中文提示） | 显示"正在 X..." |
| `text` | LLM 文本流式增量 | 追加到当前气泡 |
| `done` | 流正常结束 | 收尾 thought 步骤，关闭流 |
| `done` | 流正常结束 | 收尾 thought 步骤，关闭流 |
| `error` | 异常 | 展示错误提示 |

确认机制：纯聊天交互。敏感工具走计划驱动安全门——LLM 先展示计划，用户自然语言确认，LLM 调 `set_pending_plan(user_confirmed=true)`，代码层硬约束校验后放行。

## 扩展指引（新增功能时如何不破坏现有架构）

### 新增子图（例：报价单子图）
1. `orchestrator/` 新建 `quotation_entry.py`，类比 `contract_entry.py` 的 `analyze_node → call_model ↔ execute_tool` 模式
2. `orchestrator/state.py` 新增 `QuotationState(RootState)`
3. `orchestrator/graph.py`：`route_by_intent` 加分支；`build_root_graph` 加节点 + 边（子图 → `finalize_node`）
4. `intake_node` 的 `_infer_intent` 加关键词或文件类型路由
5. `_SENSITIVE_TOOLS` 列出需要中断确认的工具名

### 新增敏感工具
1. `tools.py` `TOOL_DEFINITIONS` 加 OpenAI function 定义（描述写清楚字段语义和限制）
2. 工具方法实现里**只返回事实 JSON**，不嵌入"请先..."等行为指令（铁律）
3. 子图 `_SENSITIVE_TOOLS` 集合加入工具名
4. `execute_tool_node` 中加计划驱动安全门校验（`pending_plan.user_confirmed` 检查）
5. 前端对应增加确认 UI（`ReceiptConfirmPanel.tsx` / `ContractChatModal` 参考）

### 新增 LLM 客户端
- `llm_client.py` 加新类，暴露 `async chat_completion_stream(messages, tools) -> AsyncGenerator[{type, content/id/name/arguments}, ...]`
- 兼容 OpenAI function calling 协议即可（流式 + tool_calls 增量）
- 子图构造函数 `llm_client` 参数支持注入，方便单测 mock

### 新增可视化分析器（合同/凭证/群聊等）
1. `services/` 新建 `xxx_analyzer.py`，类比 `ContractAnalyzer.analyze_file` / `ReceiptAnalyzer.analyze_from_file`
2. 用 `asyncio.to_thread` 在子图 `analyze_xxx_node` 中包装同步方法
3. `ToolExecutor._cache_analysis` 加新 `analysis_type` 缓存分支
4. `_summarize_analysis_for_context` 决定哪些大字段剥离出 LLM context

## 关键模块对照表（按职责找文件）

| 找什么 | 在哪 |
|---|---|
| 入口路由 | `app/api/v1/agent.py` — `POST /chat`(SSE) / `POST /upload` / `GET/POST/DELETE /sessions` / `GET /history/{id}` |
| Root 图状态 | `app/ai/orchestrator/state.py` — `RootState` + `ContractEntryState` / `ReceiptEntryState` / `GeneralChatState` |
| 工具表 | `app/ai/tools.py` 2081 行起 — `TOOL_DEFINITIONS`（17 个） |
| 工具实现 | `app/ai/tools.py` `ToolExecutor` 类 — 每个 `def execute_<tool>` |
| 业务 Service | `app/services/{contract,payment,customer,contract_analyzer,receipt_analyzer,...}_service.py` |
| 提示词 | `app/ai/prompts.py` — `build_system_prompt` + `CONTRACT_ENTRY_PROMPT` / `RECEIPT_ENTRY_PROMPT` / 各种 `_ANALYSIS_PROMPT` |
| LLM 客户端 | `app/ai/llm_client.py` — `DashScopeAgentClient` / `SiliconFlowClient` |
| 权限 | `app/core/permissions.py` — `Role` / `is_admin` / `can_view_income` / `can_view_expense` |
| 配置 | `app/config.py` `Settings`（pydantic_settings，从 `.env` 读取） |
| 启动/关闭 | `app/main.py` — `on_startup` 调 `init_checkpointer()` + LangSmith env 同步；`on_shutdown` 关闭连接池 |
| 设计文档 | `docs/2026-06-06-langgraph-agent-orchestration.md`（v2.2，含 7 项 ADR） |
| SQL 脚本 | `backend/sql/` + 根目录 `public.sql`（不通过 alembic 维护） |

## 命令

```bash
cd backend && uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
cd backend && uv run pytest
cd frontend && npm run dev
cd frontend && npx tsc --noEmit
```
