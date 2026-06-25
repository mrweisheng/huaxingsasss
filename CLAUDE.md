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
- **前端改动必须构建后再推送**：只要本次提交修改了 `frontend/src/**` 任意文件，commit 前必须 `cd frontend && npm run build` 生成 `frontend/dist/`，并把构建产物一起 `git add` 加入同一个 commit 推送。原因：生产环境直接消费 `frontend/dist/`，不在服务器跑 build——源码改了但 dist 没更新等同于没改。后端独立改动不受此约束。

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
| 工具执行 | `ai/tool_executor.py` `ToolExecutorV2`（继承 `ai/tool_executor_base.py` `ToolExecutor`） | 调 Service 层，返回纯 JSON 事实；execute() 已重写，**不再有 mode guard / document guard**（v1 父类的白名单与文档守卫在 v2 入口被绕过），仅保留 `_ALLOWED_TOOLS` 白名单兜底防 LLM 调未知工具 | 代码（确定性） |
| Service | `services/*.py` | 业务规则、权限校验、事务边界 | 代码（确定性） |
| 模型 / DB | `models/*.py` | ORM 映射、表结构 | 代码 |
| 提示词 | `ai/prompts.py` | 业务偏好、追问策略、字段解释、确认规则 | LLM 软规则 |
| 写入确认 | `ai/prompts.py` `build_system_prompt` 的「确认规则」段 | LLM 自主判断"先列计划、再等同意、后执行"，不在代码层做关键词拦截 | LLM 软规则 |

### Agent 循环架构

```
call_model_node（LLM 决策，迭代上限 settings.AGENT_MAX_ITERATIONS=8）
      ↑                    ↓
      │              [有 tool_calls?]
      │                ↓           ↓
      │       execute_tool_node   finalize_node（chat_history 落库，幂等）
      │              │
      │              └─ 忠实执行 LLM 决定的工具调用（不在代码层做确认拦截）
      │                  → ToolMessage 回灌
      └──────────────┘
```

- `call_model_node`：LLM 决定展示什么、调哪个工具、追问还是结束。附件信息自动注入到用户消息上下文。
- `execute_tool_node`：忠实执行 LLM 决定调用的工具，不在代码层做确认关键词拦截。**写入是否需要先向用户确认完全交由 LLM 根据 system prompt 的「确认规则」自主判断**（CLAUDE.md「Agent 模式铁律」：禁止用 if/else 偷懒代替 LLM 决策）。同时发 SSE `tool_start`/`tool_end` 事件给前端。
- `finalize_node`：`chat_history` 落库（checkpoint 存机器可读状态，`chat_history` 存人类可读消息），用 `_finalized` 标记做幂等防护。
- `should_continue`：有 tool_calls → execute_tool_node，否则 → finalize_node。

### 状态结构

`state.py` — 单一 `AgentState(TypedDict)`：

| 字段 | 类型 | 用途 |
|---|---|---|
| `messages` | `Annotated[list, add_messages]` | 对话消息流（LangChain 标准 reducer） |
| `user_id` | `int` | 当前用户 ID |
| `user_role` | `str` | admin / income / expense |
| `session_id` | `str` | 会话 ID |
| `session_context` | `Optional[dict]` | 从 chat_sessions.context 加载 `{contract_id, payment_type}` |
| `session_mode` | `str` | 会话模式: chat / receipt_income / receipt_expense |
| `attachments` | `list[dict]` | 当前轮附件 `[{file_id, file_type, file_name}]` |
| `iteration_count` | `int` | 迭代计数 |
| `should_end` | `bool` | 强制结束标记 |
| `errors` | `Annotated[list[str], operator.add]` | 错误累积 |
| `chat_history_meta` | `dict` | chat_history 落库元数据 |
| `_finalized` | `bool` | 落库幂等标记 |
| `_persisted_count` | `int` | 已落库的 messages 数量游标（跨轮持久化在 checkpointer 里，新会话默认 0） |

> 历史字段 `_pending_receipt_file_ids` 已移除——凭证录入改走表单路径，不再需要跨 turn 同步 receipt 文件 ID。

## 技术锚点

- **Git 远程仓库**：远程名是 `github`（不是 `origin`）。拉取/推送用 `git fetch github` / `git push github`，不要用 `origin`
- **工具链**：uv（Python 包管理）· npm（前端）。后端 `cd backend && uv run ...`，前端 `cd frontend && npm run ...`
- 后端：FastAPI · SQLAlchemy 2.x · Pydantic v2 · pydantic_settings
- 前端：Vite · React · TypeScript · Zustand
- Agent 编排：LangGraph 1.2.x · `StateGraph` / `astream_events(version="v2")`
- Checkpoint：`AsyncPostgresSaver` + `psycopg3` `AsyncConnectionPool`（`autocommit=True`、`prepare_threshold=0`），复用现有 PG，`main.py:on_startup` 调 `init_checkpointer()` 自动建表
- LLM 客户端：`backend/app/ai/llm_client.py` — `DeepSeekAgentClient`（`DEEPSEEK_AGENT_MODEL = "deepseek-v4-flash"`，`DEEPSEEK_BASE_URL` 默认 `https://api.deepseek.com`）。统一走 DeepSeek 兼容的 OpenAI function calling 协议，支持流式 + 工具调用增量 + 指数退避重试（429/5xx/Timeout）。**不引入** `langchain-openai` / `ChatOpenAI`（避免引入 OpenAI SDK 间接依赖）。视觉模型走独立的 `DASHSCOPE_*` 配置（百炼 qwen3-vl-flash），由 `call_vl_model` 工具函数直调
- 工具执行：`backend/app/ai/tool_executor.py` — 20 个工具（`TOOL_DEFINITIONS`，OpenAI function calling 格式）+ `ToolExecutorV2`（execute 走 `_ALLOWED_TOOLS` 白名单 + 轻量 `MODE_TOOL_WHITELIST` mode guard：receipt_income/receipt_expense 会话裁剪到对应工具子集）
- 编排层：`backend/app/ai/orchestrator/` — `unified_agent.py`（Agent 图 + 节点） / `state.py`（AgentState） / `checkpointer.py` / `sse_adapter.py`
- 业务封装：`backend/app/services/` — 工具层不直接 ORM，统一走 Service。`receipt_matcher.py` 提供凭证三态对比器（ok / soft_mismatch / hard_conflict），对话流前置校验用
- 可观测性：`.env` 设 `LANGCHAIN_TRACING_V2=true` 后 LangGraph 节点自动埋点到 LangSmith（`main.py:on_startup` 同步 env）
- 凭证校验：**两条路径并存**——
  - **对话流路径（默认）**：合同卡片"录入收入/支出"按钮 → `ReceiptChatModal` 对话流 → LLM 调 `analyze_receipt` 同步前置识别+三态对比 → ok 走 `create_*_payment`，soft_mismatch 走 `override_receipt_mismatch`（带放行理由+审计），hard_conflict 工具层硬挡禁止录入
  - **表单路径（保留兜底）**：`POST /api/v1/payments` 表单 API → 异步 `verify_receipt(payment_id)` task 回写 `verification_status`（pending/passed/failed），admin 可经 `POST /api/v1/payments/{id}/manual-confirm` 强制入账
  - 放行审计：对话流放行时同时写 `payment_override_audit` 表（业务级审计）+ `audit_logs`（通用 CRUD 审计），合同详情页"放行历史"折叠区块直接从 `payment.verification_result.manual_override` 读取展示

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

心跳机制：事件间隔超过 `_HEARTBEAT_INTERVAL = 3.0` 秒时自动发 `thinking` 心跳事件，防止前端长时间无事件。v2.3 起改用 `asyncio.wait + Task` 实现心跳（v2.2 的 `wait_for` 会取消 async generator，已弃）。

确认机制：纯聊天交互。LLM 先展示操作计划（列客户名、金额、币种等），用户自然语言回复确认，LLM 再调写入工具。**确认逻辑完全由 LLM 根据 system prompt 的「确认规则」自主判断，代码层不做关键词拦截**（v2 重构中已删除 `_WRITABLE_TOOLS` / `_CONFIRM_KEYWORDS` / `_document_context` 拦截）。

## 扩展指引（新增功能时如何不破坏现有架构）

### 新增工具
1. `tool_executor.py` `TOOL_DEFINITIONS` 加 OpenAI function 定义（描述写清楚字段语义和限制）
2. `ToolExecutorV2` 中实现 `def <tool_name>(self, **kwargs) -> str`，**只返回事实 JSON**，不嵌入"请先..."等行为指令（铁律）
3. 如果是写入工具，在 `prompts.py` 的「确认规则」段把工具名加入"必须先列计划"的清单（不要在代码层加白名单）
4. 如果是查询工具（不写库），直接可用，无需额外配置
5. 如需前端展示工具摘要，在 `unified_agent.py` `extract_tool_summary()` 加分支

### 新增 LLM 客户端
- `llm_client.py` 加新类，暴露 `async chat_completion_stream(messages, tools) -> AsyncGenerator[{type, content/id/name/arguments}, ...]`
- 兼容 OpenAI function calling 协议即可（流式 + tool_calls 增量）
- 修改 `_default_llm_client()` 或在注入依赖时替换

### 新增可视化分析器
1. `services/` 新建 `xxx_analyzer.py`，类比 `FileAnalyzer.analyze_file`
2. 在 `ToolExecutorV2.execute_analyze_files` 中调用
3. `prompts.py` 加对应的分析 prompt

## 工具清单（tool_executor.py, 16 个）

| 工具名 | 类型 | 写入防护 | 说明 |
|---|---|---|---|
| `analyze_files` | 分析 | - | LLM 主动调度的文件分析。自动识别类型（合同/凭证/群聊/证件/车辆照片/其他），按 purpose 返回结构化数据；非合同/凭证类型会被拒绝并提示。批量支持，缓存于 Redis（30 分钟 TTL） |
| `get_overview` | 查询 | - | 系统全局统计概览（客户/合同/即将到期/收支汇总） |
| `search_customers` | 查询 | - | 搜索客户（按姓名/电话/微信群模糊匹配，自动兼容繁简） |
| `create_customer` | 写入 | ✅ | 创建客户（同名+同电话/邮箱去重） |
| `update_customer` | 写入 | - | 更新已有客户信息 |
| `search_contracts` | 查询 | - | 搜索合同（按编号/客户/状态/关键词/日期） |
| `get_contract_detail` | 查询 | - | 合同详情 + 付款记录（按角色过滤 income/expense） |
| `create_contract` | 写入 | ✅ | 创建合同（自动关联 `analyze_files` 缓存结果）。**只生成合同 + 付款计划（payment_terms），不创建任何 payment 记录**。合同编号自动生成；wechat_group 必填且必须用户口述提供，不从文件提取；business_type 限定 `车辆买卖` / `两地牌过户` / `年检保险` / `其他` |
| `update_contract` | 写入 | - | 更新合同元信息（微信群/备注/标题/业务描述） |
| `query_payments` | 查询 | - | 付款记录查询，支持 `group_by=contract` 按合同分组聚合（替代旧 get_payment_summary/get_expense_summary） |
| `update_payment` | 写入 | ✅ | 更新已有付款记录（备注/凭证/付款方式/期数名/付款日期）。传入 receipt_data 时自动反查付款计划生成 description；notes 若原含 `[无凭证支出]` 审计标记会自动补回 |
| `search_contract_text` | 查询 | - | 合同全文关键词搜索（限定某合同：传 `contract_id`） |
| `list_additional_items` | 查询 | - | 列出合同附加项（车险/保养/人工费等应收清单项）+ 按币种汇总 |
| `add_additional_item` | 写入 | ✅ | 新增附加项（应收清单上的额外项目，非独立财务实体） |
| `update_additional_item` | 写入 | - | 更新已有附加项字段 |
| `delete_additional_item` | 写入 | ✅ | 软删附加项，引用此附加项的付款标签自动置空 |
| `analyze_receipt` | 分析 | - | 凭证录入对话流第一步：同步 VL 提取 + ReceiptMatcher 三态判定（ok/soft_mismatch/hard_conflict）。返回 extracted/expected/diff_fields + `_receipt_path`/`_receipt_file_hash`/`_receipt_data` 等内部字段供后续写入工具透传 |
| `create_income_payment` | 写入 | ✅ | 对话流创建收入（必须先调 analyze_receipt 且 match_status=ok）。直落 paid + verification_status=passed，不走异步校验 |
| `create_expense_payment` | 写入 | ✅ | 对话流创建支出。有凭证走 analyze_receipt 路径；无凭证传 `no_receipt=true + override_reason`，走 manual 模式审计 |
| `override_receipt_mismatch` | 写入 | ✅ | soft_mismatch 状态下用户提供放行理由后创建付款。同事务写 `payment_override_audit`（who/when/reason+识别快照+用户输入快照+差异） + `audit_logs`。hard_conflict 工具入口硬挡 |

> **凭证录入双轨**：
> - 对话流（默认）：合同卡片"录入收入/支出"按钮 → `ReceiptChatModal` → `POST /api/v1/agent/chat` SSE → 四工具组合（analyze_receipt → create_*_payment 或 override_receipt_mismatch）
> - 表单（保留兜底/编辑）：`POST /api/v1/payments` + `POST /api/v1/payments/extract-receipt`（VL）+ 异步 `verify_receipt` task，`PaymentList.tsx` 的编辑入口仍走表单（凭证不符修复 / 改字段）
> - **不要再说"支付录入改走表单路径"** — v3 起对话流是主路径

### Mode Guard（轻量恢复）

`MODE_TOOL_WHITELIST` 按 `session_mode` 限定可见/可调工具集：
- `chat` → 20 个工具全集
- `receipt_income` → 11 个工具：基础查询/分析 + `analyze_receipt` + `create_income_payment` + `override_receipt_mismatch`
- `receipt_expense` → 11 个工具：基础查询/分析 + `analyze_receipt` + `create_expense_payment` + `override_receipt_mismatch`

两层防护：
1. `unified_agent.call_model_node` 用 `filter_tool_definitions(mode)` 给 LLM 暴露的 tools 列表过滤
2. `ToolExecutorV2.execute()` 入口用 `is_tool_allowed_in_mode()` 兜底拒绝（防 LLM 不听话）

> 不再恢复 v1 的 document guard（"文件分析后封锁不兼容工具"），凭证录入由对话流 + Matcher 同步前置保证一致性。

## 关键模块对照表（按职责找文件）

| 找什么 | 在哪 |
|---|---|
| Agent 入口路由 | `app/api/v1/agent.py` — `POST /chat`(SSE) / `POST /upload` / `GET/POST/DELETE /sessions` / `GET /files/{file_id}` / `GET /files/{file_id}/thumbnail` / `GET /history/{session_id}` |
| 付款路由（表单录入兜底） | `app/api/v1/payments.py` — `POST /payments` / `PUT /payments/{id}` / `POST /payments/upload` / `POST /payments/extract-receipt` / `POST /payments/{id}/manual-confirm`（admin 强制入账） / `GET /payments`（对话流不走此路径，但保留作为编辑/旧入口/兜底） |
| 合同/客户/附加项/汇率/用户/账户/统计 | `app/api/v1/{contracts,customers,contract_additional_items,exchange_rates,users,payment_accounts,stats,auth,files}.py` |
| Agent 图 + 节点 | `app/ai/orchestrator/unified_agent.py` — `_build_graph` / `get_compiled_graph` / `call_model_node` / `execute_tool_node` / `finalize_node` / `should_continue` / `now_context()`（结构化时间上下文） |
| Agent 状态 | `app/ai/orchestrator/state.py` — `AgentState`（13 个字段，详见上文"状态结构"表） |
| Checkpoint | `app/ai/orchestrator/checkpointer.py` — `init_checkpointer()` / `get_checkpointer()` / `close_checkpointer()` |
| SSE 适配 | `app/ai/orchestrator/sse_adapter.py` — `adapt_langgraph_stream_v2()` + `_HEARTBEAT_INTERVAL = 3.0` 秒 |
| 工具定义 + 执行 | `app/ai/tool_executor.py` — `TOOL_DEFINITIONS`（20 个工具）+ `ToolExecutorV2`（execute 走白名单+轻量 mode guard）+ `MODE_TOOL_WHITELIST` / `filter_tool_definitions()` / `is_tool_allowed_in_mode()` |
| 旧工具文件（保留兼容） | `app/ai/tool_executor_base.py` — `ToolExecutor`（v1 父类，凭证目录复制/Redis 缓存等基础能力 v2 仍复用，但 v1 的 mode/document guard 不再走） |
| 凭证-合同三态对比器 | `app/services/receipt_matcher.py` — `match_receipt()` 返回 ok/soft_mismatch/hard_conflict + diff_fields + expected/extracted 快照；`pick_payment_term()` 按金额命中付款计划项 |
| 凭证放行审计模型 | `app/models/payment_override_audit.py` — 对话流软放行/manual 模式落审计行（who/when/reason+三份快照+差异） |
| 提示词 | `app/ai/prompts.py` — `build_system_prompt(user, current_time, ...)` + 分析 prompt（`FILE_CLASSIFY_PROMPT` / `CONTRACT_ANALYSIS_PROMPT` / `RECEIPT_ANALYSIS_PROMPT` / `GROUP_CHAT_ANALYSIS_PROMPT` / `EXPENSE_TEMPLATE_EXTRACT_PROMPT`） |
| LLM 客户端 | `app/ai/llm_client.py` — `DeepSeekAgentClient`（OpenAI 兼容协议 + 流式 + 工具调用 + 重试） |
| VL 模型（视觉） | `app/utils/file_analysis.py` — `call_vl_model(bytes, mime, prompt)`，直调百炼 qwen3-vl-flash |
| 业务 Service | `app/services/{contract,payment,customer,file_analyzer,contract_additional_item,exchange_rate,exchange_rate_fetcher,payment_account,user,stats,audit}_service.py` |
| 凭证异步校验 | `app/tasks/receipt_verification_tasks.py` — `verify_receipt(payment_id)` 异步任务 |
| 权限 | `app/core/permissions.py` — `Role` / `is_admin` / `can_view_income` / `can_view_expense` |
| 配置 | `app/config.py` `Settings`（pydantic_settings，从 `.env` 读取；`validate_required` 启动校验 SECRET_KEY + DB + LLM 必填） |
| 启动/关闭 | `app/main.py` — `on_startup` 调 `init_checkpointer()` + 注册 heif 解码器 + 同步 LangSmith env；`on_shutdown` 关闭连接池 |
| 中间件 | `app/core/middleware.py` — `RequestLoggingMiddleware`（注入 X-Request-ID）+ `AuditLogMiddleware`（POST/PUT/PATCH/DELETE 自动写 audit_log） |
| SQL 脚本 | `backend/sql/` + 根目录 `public.sql`（不通过 alembic 维护） |

## 命令

```bash
# 后端
cd backend && uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
cd backend && PYTHONIOENCODING=utf-8 uv run pytest

# 前端
cd frontend && npm run dev          # 本地开发
cd frontend && npx tsc --noEmit     # 类型检查
cd frontend && npm run build        # 生产构建（提交前必跑，产物入 frontend/dist/）
```

⚠️ **Windows 编码问题**：本机 bash 下 Python 默认用 GBK，中文源码会报 `UnicodeDecodeError: 'gbk' codec can't decode byte ...`。所有 `uv run python` 命令前面必须加 `PYTHONIOENCODING=utf-8`，包括 `pytest`。

⚠️ **Python 工具链**：本项目使用 **uv** 管理 Python 依赖（非 pip/poetry）。后端所有命令通过 `cd backend && uv run ...` 执行。
