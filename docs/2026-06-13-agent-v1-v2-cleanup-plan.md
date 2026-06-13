# Agent v1/v2 架构遗留清理计划

> 记录日期：2026-06-13
> 状态：**待执行**（已规划，未动手）
> 触发背景：用户在排查权限改造时发现「v1/v2」命名误导，要求彻底盘查并提出清理方案

---

## 一、问题陈述

代码里反复出现「v1」「v2」字样的两套文件，给新人带来强烈的误导：

- `backend/app/ai/tools.py`（2308 行，被注释为「v1」工具集）
- `backend/app/ai/tools_v2.py`（1333 行，「v2」工具集）
- `backend/app/ai/agent.py`（343 行，旧 `ContractAgent` 类）
- `backend/app/ai/orchestrator/unified_agent.py`（v2 主链路）
- `backend/app/ai/prompts_v2.py`（v2 提示词，**没有 prompts.py 对应物**）
- `backend/app/ai/orchestrator/state_v2.py`（v2 状态）

实际情况经代码扫描确认：**v2 是当前线上唯一在跑的链路，v1 是一次半成品重写没清干净的产物**。

---

## 二、扫描发现的事实（基于 import 关系 + AST 分析）

### 2.1 主链路（POST /api/v1/agent/chat 走的路径）

```
POST /chat
  → app/api/v1/agent.py
  → app/ai/orchestrator/unified_agent.py（编排图：call_model ↔ execute_tool → finalize）
  → app/ai/tools_v2.py::ToolExecutorV2
  → 14 个白名单工具（_ALLOWED_TOOLS）
  → app/services/* （Service 层）
  → DB
```

### 2.2 v2 的 14 个工具实际实现位置

| 工具名 | 实现位置 |
|---|---|
| `analyze_files` | tools_v2.py（v2 自写） |
| `create_payment_record` | tools_v2.py（v2 自写） |
| `match_and_confirm_payment` | tools_v2.py（v2 自写） |
| `query_payments` | tools_v2.py（v2 自写） |
| `update_payment` | tools_v2.py（v2 自写） |
| `execute` | tools_v2.py（v2 自写） |
| `search_contracts` | **tools.py（v2 通过继承复用）** |
| `search_customers` | **tools.py（继承复用）** |
| `get_contract_detail` | **tools.py（继承复用）** |
| `get_overview` | **tools.py（继承复用）** |
| `search_contract_text` | **tools.py（继承复用）** |
| `create_contract` | **tools.py（继承复用）** |
| `create_customer` | **tools.py（继承复用）** |
| `update_contract` | **tools.py（继承复用）** |
| `update_customer` | **tools.py（继承复用）** |

> 共享私有方法（也都在 tools.py 里）：`_can_view_income` / `_can_view_expense` / `_payment_to_dict_lite` / `_contract_to_dict_lite` / `_cache_analysis` / `_get_redis_pool` / `_can_access_contract` 等

### 2.3 tools.py 里**真正的死代码**（v2 不引用）

**死代码工具方法（11 个）：**
- `create_payment` / `create_expense`（已合并为 v2 `create_payment_record`）
- `match_receipt`（已被 v2 `match_and_confirm_payment` 替代）
- `set_pending_plan`（v2 已删除该机制）
- `get_customer_contracts`（已被 `search_contracts(customer_id=...)` 覆盖）
- `get_payment_summary` / `get_expense_summary`（已被 v2 `query_payments(group_by=...)` 替代）
- `get_expiring_contracts` / `ask_contract`（v2 工具集已删除）
- v1 版本的 `query_payments` / `update_payment`（v2 自己重写了）

**死代码守卫（4 个）：**
- `_MODE_ALLOWED_TOOLS` 字典
- `_DOCUMENT_BLOCKED` 字典
- `_check_mode_guard` 方法
- `_check_document_guard` 方法

> 注释「`tools_v2.py:5` — 删除 mode guard / document guard / set_pending_plan」明确印证 v2 已废弃这些机制；v2 的 `execute` 也注释「无模式守卫，仅角色权限控制」。但 v1 文件里这些守卫代码没人删。

**死代码 TOOL_DEFINITIONS：**
- v1 文件末尾还有一份独立的 `TOOL_DEFINITIONS`（20 个 v1 工具定义），v2 主链路完全不引用——只有 v1 内部 `execute` 引用，而 v1 `execute` 也没人调

**估算：tools.py 中约 1000 行死代码，占 43%。**

### 2.4 agent.py（ContractAgent，343 行）的现状

文件顶部注释自己写明：
> "ReAct 循环已移除（PR-R-3 之后由 LangGraph root graph 接手），当下该服务器只负责：会话管理 / chat_history 落库 / mode 加载"

**它已经不是 Agent 编排器，本质就是一个会话服务**。当前用法（`api/v1/agent.py`）：
- `list_sessions` 接口 → `ContractAgent.get_sessions()`
- `delete_session` 接口 → `ContractAgent.delete_session()`
- `history` 接口 → `ContractAgent.get_history()`

`__init__` 里还创建了 `self.executor = ToolExecutor(db, user)`，但**没有任何方法用到 `self.executor`**——构造时白白实例化。

`_serialize_messages` 方法注释「目前已无调用方」——明确死代码。

### 2.5 prompts 文件命名

只有 `prompts_v2.py`，**没有 `prompts.py` 对应物**——这个 `_v2` 后缀就是纯历史包袱，毫无意义。

---

## 三、为什么会演变成这样（合理推断）

证据链：
1. `tools_v2.py:5` 注释「删除 mode guard / document guard / set_pending_plan」
2. `tools_v2.py:7` 注释「合并 create_payment + create_expense → create_payment_record」
3. `agent.py:4` 注释「ReAct 循环已移除（PR-R-3 之后由 LangGraph root graph 接手）」

**结论**：项目经历过一次大重构（PR-R-3 节点）——把多子图编排重写为单层 Agent 循环。重构时新写了 `*_v2` 文件，老文件**仅删除引用、未删代码**。后续没有「清理周」把死代码清掉，于是「v1/v2」永久共存，新人误以为这是有意保留两代实现。

**v1 文件没有任何不可替代的内容**——9 个继承方法和共享私有方法都是普通 Python 代码，迁移到任意文件均可；`ContractAgent` 是会话服务，跟 LLM 编排已无关。

---

## 四、清理方案（三档，按风险递增）

### 方案 A：保守清理（推荐先做，约 2-3 小时，风险低）

**只删死代码 + 重命名文件，不改继承结构**。

| # | 改动 | 涉及文件 |
|---|---|---|
| 1 | 删除 11 个死代码工具方法 | `tools.py` |
| 2 | 删除 4 个死代码守卫（`_MODE_ALLOWED_TOOLS` 等） | `tools.py` |
| 3 | 删除 v1 的 `TOOL_DEFINITIONS`（20 个工具定义） | `tools.py` |
| 4 | 删除 `_serialize_messages` 等死方法、删除 `self.executor = ...` | `agent.py` |
| 5 | 顶部加注释明确：「ToolExecutor 基类，被 ToolExecutorV2 继承复用」 | `tools.py` |
| 6 | 文件改名：`tools.py → tool_executor_base.py` | 同步 5 处 import |
| 7 | 文件改名：`tools_v2.py → tool_executor.py` | 同步 4 处 import |
| 8 | 文件改名：`agent.py → chat_session_service.py`、类名 `ContractAgent → ChatSessionService` | 同步 1 处 import |
| 9 | 文件改名：`prompts_v2.py → prompts.py` | 同步若干 import |
| 10 | 文件改名：`state_v2.py → state.py`、`unified_agent.py` 内 `AgentState` 引用同步 | 同步 import |

**改动量**：约 -1000 行 / +10 行 / 5-10 处 import 修改
**风险**：
- 删除的方法都不在 `_ALLOWED_TOOLS` 白名单里，运行时不可达 → 安全
- 重命名是机械操作，一次性原子改完
- 验收：`uv run python -c "from app.main import app"` 能成功 import 即可

### 方案 B：彻底合并继承（在 A 之后追加，半天工作量，风险中）

在方案 A 基础上：

| # | 改动 |
|---|---|
| 11 | 把 9 个继承方法 + 共享私有方法搬进 `tool_executor.py` |
| 12 | 删除 `tool_executor_base.py`，`ToolExecutor` 不再继承任何类 |

**收益**：彻底消除「基类 + 子类」结构，新人看代码无认知负担
**风险**：私有辅助方法多达 15+，迁移漏一个就 500
**对策**：迁移后用 `pytest --collect-only` + `python -c "import ..."` 全量加载验证

### 方案 C：按业务拆分（不推荐）

把 14 个工具按 `contract_tools.py` / `customer_tools.py` / `payment_tools.py` / `analysis_tools.py` 拆分。

**评估**：过度工程。每个工具就是一个方法，强行拆分反而需要跨文件协作。当前「一个 Executor 类 + 一个 TOOL_DEFINITIONS 列表」结构本身是对的。

---

## 五、风险评估

### 没有的风险（已确认）

- **不动数据库结构**
- **不动 API 路径 / 响应格式**
- **不动前端**
- **不动 SSE 协议**
- **不动 prompts 内容**
- **不动 Service 层**
- **不动 checkpointer / state**
- **不动权限规则**

### 真实风险点

1. **方案 A 重命名期间**：5-10 处 import 路径必须原子修改（一次 commit），否则启动失败
   - 缓解：改完跑 `uv run python -c "from app.main import app; print('ok')"` 即可暴露
2. **方案 B 方法迁移**：私有辅助方法漏迁会导致运行时 `AttributeError`
   - 缓解：迁移后启动一次完整应用、手动跑一次 Agent SSE 对话即可暴露所有路径

### 完全无风险的部分

- 死代码删除（11 个方法 + 4 个守卫 + v1 TOOL_DEFINITIONS）：**这些代码运行时不可达**，删除等同于不影响任何运行行为

---

## 六、推荐执行顺序

1. **第一阶段**（先做）：方案 A 的 1-5 步，**只删死代码**，不改文件名
   - 一个独立 commit「chore: 删除 Agent 重构后遗留的死代码」
   - 推送后线上跑一周验证无副作用
2. **第二阶段**（一周后）：方案 A 的 6-10 步，**机械重命名**
   - 一个独立 commit「refactor: tools.py / tools_v2.py 重命名为 tool_executor_base / tool_executor，移除 v1/v2 命名误导」
   - CLAUDE.md 中所有提及 `tools_v2.py` / `prompts_v2.py` / `state_v2.py` / `unified_agent.py` 的位置同步更新
3. **第三阶段**（可选，再过一周）：方案 B 合并继承
   - 一个独立 commit「refactor: 合并 ToolExecutor 基类，消除 v1/v2 继承结构」

---

## 七、清理后预期结构

```
backend/app/ai/
├── llm_client.py              # 不变
├── tool_executor.py           # 原 tools_v2.py（方案 B 后包含全部工具方法）
├── prompts.py                 # 原 prompts_v2.py
└── orchestrator/
    ├── unified_agent.py       # 不变
    ├── state.py               # 原 state_v2.py
    ├── checkpointer.py        # 不变
    └── sse_adapter.py         # 不变

backend/app/services/
└── chat_session_service.py    # 原 agent.py 的 ContractAgent
```

**完全消除「v1」「v2」字样**，文件名直接表达职责，新人 5 分钟看懂全貌。

---

## 八、CLAUDE.md 同步事项

清理完成后需更新 `CLAUDE.md` 的以下章节（避免再次误导）：

- 「关键模块对照表」中所有 `tools_v2.py` / `prompts_v2.py` / `state_v2.py` 路径
- 「扩展指引」中提及 v1/v2 的描述
- 「业务架构」中的「14 个工具」清单文件路径
