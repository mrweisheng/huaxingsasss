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
- **后端不做任何请求来源限制**：CORS 必须用 `allow_origin_regex=".*"` + `allow_credentials=True`（不能用 `allow_origins=["*"]`——与凭据模式互斥，浏览器会拒收 `*`，导致预检失败）

## 设计系统 · 业务色彩

**业务色与状态色严格分离**：业务色标识"这是哪种业务"，状态色标识"这单处于什么状态"。两套色系不得互相借用——同色就是同语义，混用会导致用户无法区分"未结清的两地牌"和"已结清的车辆"。

### 业务色（两个核心业务）

| 业务 | 主色 (base) | 深色 (deep) | 浅底 (soft) | 极浅底 (bg) | 语义来源 |
|---|---|---|---|---|---|
| **车辆业务** | `#2d5b8a` 钢蓝 | `#1e3f63` | `#e5edf6` | `#f4f7fb` | 汽车工业漆面（保时捷/奔驰深空蓝家族） |
| **两地牌过户** | `#b8423b` 朱砂 | `#8f2d28` | `#fbe9e7` | `#fdf4f3` | 中港车牌红边 + 通关印章 + 中港旗帜 |

色相距离 218°，扫视区分度最强。两个业务色都避开了 teal（结清状态）和暖橙（未收警示）色相。

### 状态色（金额/付款/系统状态专用，业务色不可占用）

| 状态 | 色值 | 用途 |
|---|---|---|
| 已收 / 落袋 | `#c9952b` 金 (`--brand-gold`) | 已收金额数字、付款 paid 状态主指标 |
| 已收-深字 | `#a87a18` | 金色在白底上的文字对比度补强 |
| 全额结清 | `#0d9488` teal (`--money-done`) | 100% 回款的金额、绿色 chip、✓ 结清提示 |
| 未收 / 警示 | `#dc6b3d` 暖橙 (`--money-due`) | 未收金额、逾期、需关注 |
| 录入收入·动作 | `#5b8c63` 鼠尾草绿 (`--action-income`) | 「录入收入」按钮、收入侧操作专色（避开 teal 结清） |
| 录入收入·深字 | `#3d6644` (`--action-income-deep`) | 鼠尾草绿在白底上的文字对比度补强 |
| 中性基准 | `--text-secondary` / `--text-tertiary` | 合同总额作为分母、辅助说明 |

### 用色规则（三层语义）

每个业务色对应三种用法，互不混用：

1. **base 主色** — `border-left` 色条（3px）、icon 描边色、hero 渐变起点、激活状态边框
2. **soft 浅底** — chip / 业务徽章背景、hover 高亮底
3. **deep 深字** — 浅底上的文字色（如徽章文字、强调标签）— 保证对比度 ≥ AA

**徽章三件套示例**：
```css
.biz-vehicle-chip {
  color: var(--biz-vehicle-deep);     /* 文字：深钢蓝 */
  background: var(--biz-vehicle-soft); /* 底色：浅钢蓝 */
}
.biz-vehicle-card { border-left: 3px solid var(--biz-vehicle); } /* 主色条 */
```

### 与「华星」品牌色的关系

- `--brand-primary #1e3a5f` 深蓝 = **品牌/系统色**（侧边栏、主按钮、页头）— 与车辆钢蓝同家族但更冷更暗，不抢戏
- `--brand-gold #c9952b` 金色 = **价值/金钱色**（金额数字、强调元素）— 朱砂 + 金 形成中式财务美学
- 业务色只在"标识业务类型"的场合出现，不参与品牌主视觉

### 何时染业务色 / 何时不染

| 场景 | 是否染业务色 |
|---|---|
| 业务徽章 / chip / 列表左侧色条 | ✅ 必须 |
| 合同详情页 hero / 头部背景 | ✅ 必须 |
| 收据/卡片整体浅底（如 `--biz-*-bg`）+ 虚线齿条 | ✅ 推荐 |
| 金额数字本身 | ❌ 永远用状态色（已收金/未收橙/结清 teal） |
| 进度条颜色 | ❌ 用状态色（按回款状态变） |
| 按钮 / 通用 UI | ❌ 用品牌色 |

## 业务架构（统一单层 Agent 循环）

```
START → call_model_node（LLM 决策）
          ↑         ↓
          │    [有 tool_calls?]
          │      ↓           ↓
          │ execute_tool_node  finalize_node → END
          │      │
          └──────┘
```

**统一 Agent 图**（`unified_agent.py`）：不再有子图、意图推断、路由分支。LLM 自主决定调什么工具、何时结束，代码层只提供执行能力 + 写入防护。

前端入口：`AgentChat`（/agent 智能问答，含三个工具标签「录合同」「录收入」「录支出」） + `ReceiptChatModal`（合同列表卡片「收」「支」按钮），均走 `POST /api/v1/agent/chat` SSE。

### 编排层职责边界

| 层 | 文件 | 职责 | 决策方 |
|---|---|---|---|
| Agent 图 | `orchestrator/unified_agent.py` | 单层循环：call_model ↔ execute_tool → finalize 落库 | LLM 决策 + 代码执行 |
| 工具执行 | `ai/tools_v2.py` `ToolExecutorV2` | 调 Service 层，返回纯 JSON 事实；含 mode guard + document guard | 代码（确定性） |
| Service | `services/*.py` | 业务规则、权限校验、事务边界 | 代码（确定性） |
| 模型 / DB | `models/*.py` | ORM 映射、表结构 | 代码 |
| 提示词 | `ai/prompts_v2.py` | 业务偏好、追问策略、字段解释、确认规则 | LLM 软规则 |
| 写入防护 | `unified_agent.py` `_WRITABLE_TOOLS` + `_CONFIRM_KEYWORDS` | 轻量确认检测：LLM 上轮回复含确认关键词 → 放行写入；不含 → 拦截 | 代码硬约束 |

### Agent 循环架构

```
call_model_node（LLM 决策，迭代上限 settings.AGENT_MAX_ITERATIONS=8）
      ↑                    ↓
      │              [有 tool_calls?]
      │                ↓           ↓
      │       execute_tool_node   finalize_node（chat_history 落库，幂等）
      │              │
      │              ├─ 写入工具（_WRITABLE_TOOLS）→ 确认关键词检测
      │              │   └─ 上文无确认 → 拦截，让 LLM 先展示计划
      │              │   └─ 上文有确认 → 执行
      │              └─ 普通工具 → 直接执行 → ToolMessage 回灌
      └──────────────┘
```

- `call_model_node`：LLM 决定展示什么、调哪个工具、追问还是结束。附件信息自动注入到用户消息上下文。
- `execute_tool_node`：执行工具调用。写入工具（`create_customer`/`create_contract`/`create_payment_record`/`match_and_confirm_payment`/`update_payment`）受确认防护——检查 LLM 上轮回复是否含确认关键词（`确认/是否/同意/继续/对吗/正确吗/确认吗/可以吗/行吗`），未展示则拦截并提示 LLM 先向用户确认。同时发 SSE `tool_start`/`tool_end` 事件给前端。
- `finalize_node`：`chat_history` 落库（checkpoint 存机器可读状态，`chat_history` 存人类可读消息），用 `_finalized` 标记做幂等防护。
- `should_continue`：有 tool_calls → execute_tool_node，否则 → finalize_node。

### 状态结构

`state_v2.py` — 单一 `AgentState(TypedDict)`：

| 字段 | 类型 | 用途 |
|---|---|---|
| `messages` | `Annotated[list, add_messages]` | 对话消息流（LangChain 标准 reducer） |
| `user_id` | `int` | 当前用户 ID |
| `user_role` | `str` | admin / income / expense |
| `session_id` | `str` | 会话 ID |
| `attachments` | `list[dict]` | 当前轮附件 `[{file_id, file_type, file_name}]` |
| `iteration_count` | `int` | 迭代计数 |
| `should_end` | `bool` | 强制结束标记 |
| `errors` | `Annotated[list[str], operator.add]` | 错误累积 |
| `_finalized` | `bool` | 落库幂等标记 |

## 技术锚点

- **Git 远程仓库**：远程名是 `github`（不是 `origin`）。拉取/推送用 `git fetch github` / `git push github`，不要用 `origin`
- **工具链**：uv（Python 包管理）· npm（前端）。后端 `cd backend && uv run ...`，前端 `cd frontend && npm run ...`
- 后端：FastAPI · SQLAlchemy 2.x · Pydantic v2 · pydantic_settings
- 前端：Vite · React · TypeScript · Zustand
- Agent 编排：LangGraph 1.2.x · `StateGraph` / `astream_events(version="v2")`
- Checkpoint：`AsyncPostgresSaver` + `psycopg3` `AsyncConnectionPool`（`autocommit=True`、`prepare_threshold=0`），复用现有 PG，`main.py:on_startup` 调 `init_checkpointer()` 自动建表
- LLM 客户端：`backend/app/ai/llm_client.py` — `AgentModelClient`（统一 LLM 客户端，封装百炼 + SiliconFlow）。**不引入** `langchain-openai` / `ChatOpenAI`（ADR #2：百炼兼容模式 `tools` 与 `stream=True` 互斥）
- 工具执行：`backend/app/ai/tools_v2.py` — 14 个工具（`TOOL_DEFINITIONS`，OpenAI function calling 格式）+ `ToolExecutorV2`（含 `mode guard` 拦截越权工具、`document guard` 按文件类型封锁高危工具）
- 编排层：`backend/app/ai/orchestrator/` — `unified_agent.py`（Agent 图 + 节点） / `state_v2.py`（AgentState） / `checkpointer.py` / `sse_adapter.py`
- 业务封装：`backend/app/services/` — 工具层不直接 ORM，统一走 Service
- 可观测性：`.env` 设 `LANGCHAIN_TRACING_V2=true` 后 LangGraph 节点自动埋点到 LangSmith（`main.py:on_startup` 同步 env）

## SSE 事件协议（前后端约定）

`POST /api/v1/agent/chat` 流式事件类型（`sse_adapter.py` 适配 LangGraph astream_events → SSE 格式）：

| event | 用途 | 前端处理 |
|---|---|---|
| `thinking` | 节点开始 / 心跳（友好中文提示） | 显示"正在 X..." |
| `text` | LLM 文本流式增量（含 on_chat_model_stream + text_chunk 自定义事件） | 追加到当前气泡 |
| `tool_call` | 工具开始执行 | 显示工具调用状态 |
| `tool_result` | 工具执行结果（含结构化 summary） | 展示工具结果摘要 |
| `done` | 流正常结束 | 收尾 thought 步骤，关闭流 |
| `error` | 异常 | 展示错误提示 |

心跳机制：事件间隔超过 `_HEARTBEAT_INTERVAL` 秒时自动发 `thinking` 心跳事件，防止前端长时间无事件。

确认机制：纯聊天交互。LLM 先展示操作计划（列客户名、金额、币种等），用户自然语言回复确认，LLM 再调写入工具。代码层通过 `_CONFIRM_KEYWORDS` 检测 LLM 上轮回复是否含确认词——未展示则拦截写入并提示 LLM 先确认。

## 扩展指引（新增功能时如何不破坏现有架构）

### 新增工具
1. `tools_v2.py` `TOOL_DEFINITIONS` 加 OpenAI function 定义（描述写清楚字段语义和限制）
2. `ToolExecutorV2` 中实现 `def <tool_name>(self, **kwargs) -> str`，**只返回事实 JSON**，不嵌入"请先..."等行为指令（铁律）
3. 如果是写入工具，加入 `unified_agent.py` 的 `_WRITABLE_TOOLS` 集合
4. 如果是查询工具（不写库），直接可用，无需额外配置
5. 如需前端展示工具摘要，在 `unified_agent.py` `extract_tool_summary()` 加分支

### 新增 LLM 客户端
- `llm_client.py` 加新类，暴露 `async chat_completion_stream(messages, tools) -> AsyncGenerator[{type, content/id/name/arguments}, ...]`
- 兼容 OpenAI function calling 协议即可（流式 + tool_calls 增量）
- 修改 `_default_llm_client()` 或在注入依赖时替换

### 新增可视化分析器
1. `services/` 新建 `xxx_analyzer.py`，类比 `ContractAnalyzer.analyze_file` / `ReceiptAnalyzer.analyze_from_file`
2. 在 `ToolExecutorV2.execute_analyze_files` 中调用
3. `prompts_v2.py` 加对应的分析 prompt

## 工具清单（tools_v2.py, 14 个）

| 工具名 | 类型 | 写入防护 | 说明 |
|---|---|---|---|
| `analyze_files` | 分析 | - | 统一文件分析（合同/凭证/群聊），自动识别类型 |
| `get_overview` | 查询 | - | 系统全局统计概览 |
| `search_customers` | 查询 | - | 搜索客户（模糊匹配，兼容繁简） |
| `create_customer` | 写入 | ✅ | 创建客户（同名去重） |
| `update_customer` | 写入 | - | 更新客户信息 |
| `search_contracts` | 查询 | - | 搜索合同 |
| `get_contract_detail` | 查询 | - | 合同详情 + 付款记录 |
| `create_contract` | 写入 | ✅ | 创建合同（自动关联文件分析结果，付款计划每期独立币种）。**只生成合同与付款计划，不创建任何 payment 记录**——付款记录的唯一来源是凭证录入（`match_and_confirm_payment`）或手动录入（`create_payment_record`） |
| `update_contract` | 写入 | - | 更新合同元信息（微信群/备注） |
| `query_payments` | 查询 | - | 付款记录查询（支持 group_by=contract） |
| `create_payment_record` | 写入 | ✅ | 统一收入/支出创建（type 字段区分） |
| `match_and_confirm_payment` | 写入 | ✅ | 凭证录入收款记录。无匹配 pending → 创建新 paid 记录（主路径，合同录入不再产生 pending）；有匹配 pending（历史数据）→ 转 paid。description 自动从付款计划反查"定金/尾款"标签丰富 |
| `update_payment` | 写入 | ✅ | 更新付款记录（补充凭证等） |
| `search_contract_text` | 查询 | - | 合同全文搜索 |

### Mode Guard（模式白名单）

`ToolExecutorV2` 的 `_MODE_ALLOWED_TOOLS` 按 mode 限制可用工具：
- `receipt_income` → 只能查合同/客户 + `create_payment_record`/`match_and_confirm_payment`（type=income）
- `receipt_expense` → 同上（type=expense，需 admin/expense 角色）
- 其他 mode → 全量工具

### Document Guard（文档上下文封锁）

文件分析后设置 `document_context`（receipt/general/group_chat），封锁不兼容工具：
- receipt 文件 → 不能 `create_customer`/`create_contract`（引导到合同卡片按钮）
- general/group_chat 文件 → 只能 `update_contract` 关联元信息

## 关键模块对照表（按职责找文件）

| 找什么 | 在哪 |
|---|---|
| 入口路由 | `app/api/v1/agent.py` — `POST /chat`(SSE) / `POST /upload` / `GET/POST/DELETE /sessions` / `GET /history/{id}` |
| Agent 图 + 节点 | `app/ai/orchestrator/unified_agent.py` — `_build_graph` / `get_compiled_graph` / `call_model_node` / `execute_tool_node` / `finalize_node` / `should_continue` |
| Agent 状态 | `app/ai/orchestrator/state_v2.py` — `AgentState` |
| Checkpoint | `app/ai/orchestrator/checkpointer.py` — `get_checkpointer()` / `init_checkpointer()` |
| SSE 适配 | `app/ai/orchestrator/sse_adapter.py` — `adapt_langgraph_stream_v2()` |
| 工具定义 + 执行 | `app/ai/tools_v2.py` — `TOOL_DEFINITIONS`（14 个）+ `ToolExecutorV2` |
| 旧工具文件（保留兼容） | `app/ai/tools.py` — `TOOL_DEFINITIONS`（17 个，v1 格式）+ `ToolExecutor` |
| 提示词 | `app/ai/prompts_v2.py` — `build_system_prompt` + 分析 prompt（`FILE_CLASSIFY_PROMPT` / `CONTRACT_ANALYSIS_PROMPT` / `RECEIPT_ANALYSIS_PROMPT` / `GROUP_CHAT_ANALYSIS_PROMPT`） |
| LLM 客户端 | `app/ai/llm_client.py` — `AgentModelClient`（统一入口） |
| 业务 Service | `app/services/{contract,payment,customer,contract_analyzer,receipt_analyzer,...}_service.py` |
| 权限 | `app/core/permissions.py` — `Role` / `is_admin` / `can_view_income` / `can_view_expense` |
| 配置 | `app/config.py` `Settings`（pydantic_settings，从 `.env` 读取） |
| 启动/关闭 | `app/main.py` — `on_startup` 调 `init_checkpointer()` + LangSmith env 同步；`on_shutdown` 关闭连接池 |
| 设计文档 | `docs/2026-06-06-langgraph-agent-orchestration.md`（v2.2，含 7 项 ADR） |
| SQL 脚本 | `backend/sql/` + 根目录 `public.sql`（不通过 alembic 维护） |

## 命令

```bash
cd backend && uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
cd backend && PYTHONIOENCODING=utf-8 uv run pytest
cd frontend && npm run dev
cd frontend && npx tsc --noEmit
```

⚠️ **Windows 编码问题**：本机 bash 下 Python 默认用 GBK，中文源码会报 `UnicodeDecodeError: 'gbk' codec can't decode byte ...`。所有 `uv run python` 命令前面必须加 `PYTHONIOENCODING=utf-8`，包括 `pytest`。

⚠️ **Python 工具链**：本项目使用 **uv** 管理 Python 依赖（非 pip/poetry）。后端所有命令通过 `cd backend && uv run ...` 执行。
