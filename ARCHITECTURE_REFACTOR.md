# Agent 编排层架构重构方案

> 日期：2026-06-07
> 触发事件：合同录入子图上传 PDF 后流程直接跳过 interrupt 确认环节，一次性跑完所有节点
> 状态：待审核（v2，已根据外部审核修正 §4.2 / §4.3 / §4.4）

---

## 一、问题背景

### 1.1 触发 Bug

用户上传 PDF 合同文件并说"录入合同"，预期行为：

1. AI 分析文件 → 提取合同数据
2. 展示合同预览面板（interrupt 暂停，等用户确认）
3. 用户点击"确认录入"或"取消"
4. 根据用户选择创建合同或取消

实际行为：流程一口气跑完所有节点（analyze → preview → confirm → cancel → finalize），没有暂停等用户确认，前端页面上什么都没显示。

### 1.2 表层原因

SSE 适配器（`sse_adapter.py`）检测 LangGraph interrupt 时使用了错误的键名（`interrupt_info` vs `__interrupt__`），导致 interrupt 事件没有发送到前端。**此问题已在 commit `f135e2b` 中修复。**

### 1.3 深层原因

修复 SSE 适配器后，通过日志分析发现另一个问题：

- 日志中出现了 `图片预分析: file_id=xxx`，但上传的是 PDF 文件，不是图片
- `_prepare_file()` 方法找不到带扩展名的文件（`.pdf`），误判为"图片或其他格式"
- 走了 `_pre_analyze_image()` 兜底路径，多绕了 3 层调用才完成分析

**这不是偶发 bug，而是架构层面职责不清的必然结果。**

---

## 二、当前架构分析

### 2.1 文件分析的调用链（当前）

以合同录入子图上传 PDF 为例：

```
contract_entry.py                          LangGraph 子图节点
  analyze_file_node(state)
    │
    ├─ agent._prepare_file(file_id, type)  ← ReAct Agent 私有方法
    │    找文件（精确匹配，不带扩展名）
    │    提取文本（PDF/Word/Excel）
    │    查重（file_hash → DB）
    │    ❌ 找不到文件（上传时存为 UUID.pdf）
    │    → 返回 None
    │
    ├─ agent._pre_analyze_image(file_id)   ← ReAct Agent 私有方法
    │    │
    │    └─ tools.analyze_image(file_id, "contract")  ← 工具层
    │         找文件（带扩展名 glob 兜底）
    │         查缓存（Redis）
    │         │
    │         └─ ContractAnalyzer.analyze_file()  ← 服务层
    │              找文件（带扩展名 glob 兜底）
    │              检测文件类型（header）
    │              提取文本 / VL 分析
    │              查重（file_hash → DB）
    │              缓存结果（Redis）
    │              返回结构化数据
    │
    └─ 返回 state.file_context
```

**问题：同一件事（找文件 → 分析 → 查重），四层各做一遍。**

### 2.2 各层职责重叠

| 层 | 文件 | 找文件 | 类型检测 | 提取文本 | 查重 | LLM 调用 |
|---|---|---|---|---|---|---|
| Agent 私有方法 | `_prepare_file()` | ✅ 精确匹配 | ✅ | ✅ PDF/Word/Excel | ✅ hash→DB | ❌ |
| Agent 私有方法 | `_pre_analyze_image()` | ❌ 委托 | ❌ | ❌ | ❌ | ❌ |
| 工具层 | `analyze_image()` | ✅ glob 兜底 | ✅ | ❌ 委托 | ❌ | ❌ |
| 服务层 | `ContractAnalyzer` | ✅ glob 兜底 | ✅ | ✅ 全部 | ✅ hash→DB | ✅ |

### 2.3 结构性问题清单

#### 问题 1：LangGraph 子图寄生在 ReAct Agent 上

`ContractEntrySubgraph` 构造函数接收 `agent` 实例，调用其私有方法 `_prepare_file()` 和 `_pre_analyze_image()`。

```python
# contract_entry.py 当前代码
class ContractEntrySubgraph:
    def __init__(self, db, user, agent, ...):  # ← 依赖 agent 实例
        self.agent = agent

    async def analyze_file_node(self, state):
        prep = await self.agent._prepare_file(...)         # ← 调私有方法
        result = await self.agent._pre_analyze_image(...)  # ← 调私有方法
```

**后果：**
- 子图无法独立测试（必须 mock 整个 agent）
- 子图无法独立运行（必须有 agent 实例）
- agent 内部的 `self.executor` 和子图自建的 `self.executor` 是两套独立的 ToolExecutor，上下文不共享

#### 问题 2：`_prepare_file` + `_pre_analyze_image` 是 ReAct 时代的优化，在 LangGraph 中多余

这两个方法的设计初衷是：在 ReAct 循环开始前预分析文件，省掉一轮 LLM 函数调用。

在 LangGraph 架构下，`analyze_file_node` 本身就是一个专用分析节点——它不需要"预分析"，**它就是分析**。把 ReAct 的预分析优化搬进 LangGraph 的专用节点，等于在专门做分析的节点里又套了一层"预分析"。

#### 问题 3：`tools.analyze_image()` 职责过重

`analyze_image()` 方法同时处理 `receipt`、`contract`、`group_chat` 三种分析类型。每种类型的文件查找、类型检测、LLM 调用方式都不同，方法内部变成了一个路由器：

```python
# tools.py 当前代码（简化）
def analyze_image(self, file_id, analysis_type):
    # 自己找文件（第三遍了）
    file_path = self._find_file(file_id)

    if analysis_type == "contract":
        # 查缓存 → 调 ContractAnalyzer
        ...
    elif analysis_type == "receipt":
        # 自己处理凭证分析
        ...
    elif analysis_type == "group_chat":
        # 自己处理群聊分析
        ...
```

#### 问题 4：Legacy 和 LangGraph 路径纠缠不清

`AGENT_ORCHESTRATOR` 环境变量控制走哪条路径，但实际上 LangGraph 路径还在调用 agent 的代码：

```python
# api/v1/agent.py 当前代码
if use_langgraph:
    contract_entry = ContractEntrySubgraph(
        db, current_user, agent,  # ← 仍然传入 agent
        ...
    )
```

两条路径名义上通过环境变量切换，但代码上共享 agent 实例，切不干净。

---

## 三、目标架构

### 3.1 设计原则

1. **LangGraph 子图独立**：不依赖 ReAct Agent 的任何方法
2. **服务层是事实来源**：文件分析统一由 `ContractAnalyzer` 完成，一处实现
3. **子图只负责编排**：节点调服务层拿数据，调 ToolExecutor 执行业务操作
4. **Legacy 路径完全隔离**：两条路径零共享代码（除了服务层和 ToolExecutor）

### 3.2 目标调用链

```
contract_entry.py                              LangGraph 子图节点
  analyze_file_node(state)
    │
    ├─ ContractAnalyzer.resolve_file_path()    ← 已有（contract_analyzer.py:281）
    │
    └─ ContractAnalyzer.analyze_file()         ← 服务层，唯一入口
         检测类型 → 提取文本 → LLM/VL 分析
         查重 → 缓存结果（Redis）
         返回结构化数据
```

**对比：4 层 → 2 层。4 次找文件 → 1 次。**

### 3.3 目标架构图

```
Root Graph (graph.py)
│
├── intake_node → route_by_intent
│
├── Contract Entry Subgraph (contract_entry.py)
│   ├── analyze_file_node
│   │     └→ ContractAnalyzer（服务层，直接调用）
│   ├── show_preview_node（纯数据组装）
│   ├── wait_user_confirm_node → interrupt()
│   ├── search_customer_node → ToolExecutor.execute("search_customers")
│   ├── create_customer_node → ToolExecutor.execute("create_customer")
│   ├── create_contract_node → ToolExecutor.execute("create_contract")
│   └── summarize_node / fallback_node / summarize_cancel_node
│
├── General Chat Subgraph (general_chat.py)
│   ├── call_model_node → DashScopeAgentClient
│   └── execute_tool_node → ToolExecutor（20 个工具，含 analyze_image）
│
├── Receipt / Group Chat 降级节点
│
└── finalize_node → chat_history 落库（注入 agent._save_message）
```

---

## 四、具体改动方案

### 4.1 ContractAnalyzer 补充能力

**文件：** `backend/app/services/contract_analyzer.py`

ContractAnalyzer 已经是最完整的文件分析器（找文件含 glob、类型检测、提取、LLM、查重）。只需补一件事：

| 能力 | 当前状态 | 改动 |
|------|---------|------|
| 文件查找（带扩展名） | ✅ 已有（接收 file_path） | 不变 |
| 类型检测（PDF/图片/Word/Excel） | ✅ 已有 | 不变 |
| 文本提取 | ✅ 已有 | 不变 |
| LLM/VL 分析 | ✅ 已有 | 不变 |
| 文件 hash 查重 | ✅ 已有 | 不变 |
| Redis 结果缓存 | ❌ 没有（在 tools.py 里） | **新增**：分析完成后写入 Redis 缓存 |

`analyze_file()` 方法签名不变，内部补上缓存写入：

```python
# contract_analyzer.py（改动后）
def analyze_file(file_path, db, user_id=None, skip_duplicate_check=False):
    # ... 现有逻辑 ...

    structured = ...  # LLM/VL 分析结果

    # 新增：写入 Redis 缓存（供后续 create_contract 工具复用）
    if structured and file_hash:
        _cache_analysis(file_id_from_path(file_path), "contract", structured)

    return {
        "success": True,
        "data": structured,
        "file_type": file_type,
        "file_hash": file_hash,
        ...
    }
```

缓存函数从 `tools.py` 提取为 `contract_analyzer.py` 的模块级函数（`_cache_analysis` / `_get_cached_analysis` / `_cache_key`），供两边复用。

**⚠️ 缓存 key 前缀同步：** `tools.py:138` 的 `_cache_key` 用 `vl:contract:{file_id}` 格式。`contract_analyzer.py` 新增的同名函数必须使用**完全相同的 key 格式**，确保两条路径共享同一套 Redis 缓存（Legacy 写的缓存 LangGraph 能读，反之亦然）。

### 4.2 ContractEntrySubgraph 独立化

**文件：** `backend/app/ai/orchestrator/contract_entry.py`

**改动 1：构造函数删除 `agent` 参数**

```python
# 改动前
class ContractEntrySubgraph:
    def __init__(self, db, user, agent, mode="chat", ...):
        self.agent = agent  # ← 删除

# 改动后
class ContractEntrySubgraph:
    def __init__(self, db, user, mode="chat", session_context=None, session_id=""):
        self.db = db
        self.user = user
        self.executor = ToolExecutor(db, user)
        self.executor.mode = mode
        self.executor.session_context = session_context or {}
        self.executor.session_id = session_id
```

**改动 2：`analyze_file_node` 直接调 ContractAnalyzer**

```python
# 改动前
async def analyze_file_node(self, state):
    prep = await self.agent._prepare_file(file_id, file_type)
    if prep is None:
        result = await self.agent._pre_analyze_image(file_id)
    else:
        result = await self.agent._analyze_text_content(...)

# 改动后
async def analyze_file_node(self, state):
    # 复用 ContractAnalyzer.resolve_file_path()（contract_analyzer.py:281）
    # 已含 glob 兜底 + 路径穿越防御，api/v1/contracts.py 已在用
    file_path = ContractAnalyzer.resolve_file_path(file_id, self.user.id)
    if not file_path:
        return {"current_node": "analyze_file_node", "errors": ["文件不存在"]}

    import asyncio
    result = await asyncio.to_thread(
        ContractAnalyzer.analyze_file, file_path, self.db, self.user.id
    )

    if result.get("duplicate_detected"):
        return {
            "current_node": "analyze_file_node",
            "fallback_strategy": "duplicate",
            "errors": [result.get("message", "文件重复")],
        }

    if not result.get("success"):
        return {
            "current_node": "analyze_file_node",
            "errors": [result.get("error", "分析失败")],
        }

    file_context = json.dumps(result["data"], ensure_ascii=False)
    return {
        "current_node": "analyze_file_node",
        "file_context": file_context,
    }
```

> **不新增 `_resolve_file_path`**：`ContractAnalyzer.resolve_file_path()` 已存在（contract_analyzer.py:281），且已被 `api/v1/contracts.py`（line 95, 176）使用。直接复用，不重复造轮子。

### 4.3 ReAct Agent 遗留方法处理

**文件：** `backend/app/ai/agent.py`

| 方法 | 行号 | 动作 | 原因 |
|------|------|------|------|
| `_prepare_file()` | 358-455 | **保留，LangGraph 路径不再调用** | Legacy `_process_attachments()`（agent.py:331）仍在调用 |
| `_pre_analyze_image()` | 520-549 | **保留，LangGraph 路径不再调用** | Legacy `_process_attachments()`（agent.py:335）仍在调用 |
| `_analyze_text_content()` | 457-518 | **保留** | Legacy 和 LangGraph 均可能调用 |

**⚠️ 审核修正（v2）：** 原文档错误地认为这两个方法"只有 `contract_entry.py` 调用，删除安全"。实际上 `_process_attachments()`（agent.py:315）是 Legacy ReAct 路径的附件处理入口，在 `chat()`（agent.py:108）中被调用，内部同时调了 `_prepare_file()` 和 `_pre_analyze_image()`。

**本次处理方式：**
1. `contract_entry.py` 不再调用这两个方法（§4.2 已切走）
2. 方法本身保留在 `agent.py` 中，Legacy 路径继续使用
3. **删除动作推迟到 Legacy 路径正式下线时执行**（与 §7 "不改 Legacy 路径" 边界一致）

**Legacy 下线后（Phase 3，本次不实施）：**
- 删除 `_prepare_file()`、`_pre_analyze_image()`
- 删除 `_process_attachments()`（仅被 Legacy chat 调用）
- `analyze_image()` 工具保留（通用对话子图仍需要）

### 4.4 精简 `tools.analyze_image()`

**文件：** `backend/app/ai/tools.py`

合同分析分支（`analysis_type == "contract"`）精简。

**⚠️ 审核修正（v2）：缓存写搬迁必须明确。** 当前 `tools.py:2091` 调 `self._cache_analysis(file_id, analysis_type, structured)` 写缓存。如果只搬读不搬写，会导致缓存永远写不进 ContractAnalyzer 的命名空间，LangGraph 路径的 `analyze_file_node` 拿不到缓存。

**搬迁方案：**

| 操作 | 改动前位置 | 改动后位置 |
|------|-----------|-----------|
| 缓存读取 | `tools.py:2048` (`self._get_cached_analysis`) | `contract_analyzer.py` 的 `_get_cached_analysis()` 模块级函数 |
| 缓存写入 | `tools.py:2091` (`self._cache_analysis`) | `contract_analyzer.py` 的 `analyze_file()` 内部，分析成功后自动写入 |
| `tools.py` 合同分支 | 保留缓存读 + 缓存写 | **删除写缓存行**（避免双写），保留读缓存行 |

**缓存 key 前缀统一：** 当前 `tools.py:138` 的 `_cache_key` 用 `vl:contract:{file_id}` 格式。`contract_analyzer.py` 新增的同名函数必须使用相同前缀，确保 Legacy 路径（`tools.py` 写）和 LangGraph 路径（`contract_analyzer.py` 写）共享同一套缓存。

**contract_analyzer.py 头部契约更新：** 当前文件头注释写"不涉及 Redis 缓存、session 上下文"（line 5）。新增缓存后需改为"含 Redis 结果缓存（供 LangGraph 子图和工具层共享）"。

```python
# tools.py 改动后（合同分支精简为 ~15 行）
if analysis_type == "contract":
    from app.services.contract_analyzer import get_cached_analysis
    # 缓存读取：优先命中（ContractAnalyzer 或旧 tools.py 写入的均可命中）
    cached = get_cached_analysis(file_id, "contract")
    if cached:
        self._document_context = analysis_type
        return json.dumps({"success": True, "data": cached, ...})

    result = ContractAnalyzer.analyze_file(file_path, self.db, self.user.id)
    # ⚠️ 不再写缓存 — ContractAnalyzer.analyze_file 内部已写
    self._document_context = analysis_type
    return json.dumps({
        "success": result.get("success", False),
        "data": result.get("data"),
        "duplicate_detected": result.get("duplicate_detected", False),
        "existing_contract": result.get("existing_contract"),
        "file_id": file_id,
        "file_type": result.get("file_type"),
        "analysis_type": analysis_type,
    })
```

### 4.5 API 层调整

**文件：** `backend/app/api/v1/agent.py`

```python
# 改动前（line 220-225）
contract_entry = ContractEntrySubgraph(
    db, current_user, agent,              # ← 传 agent
    mode=agent._mode,
    session_context=agent._session_context,
    session_id=session_id,
)

# 改动后
contract_entry = ContractEntrySubgraph(
    db, current_user,                     # ← 不传 agent
    mode=agent._mode,
    session_context=agent._session_context,
    session_id=session_id,
)
```

`agent` 仍然传给 `build_root_graph()`，因为 `finalize_node` 需要 `agent._save_message()` 做 chat_history 落库。

### 4.6 Legacy 路径完全保留

**文件：** `backend/app/ai/agent.py`

Legacy ReAct 路径（`AGENT_ORCHESTRATOR=legacy`）的流程：

```
ContractAgent.chat()
  → _process_attachments()       ← 附件处理（调 _prepare_file + _pre_analyze_image）
  → _load_history()
  → _build_messages()
  → _run_react_loop()            ← ReAct 函数调用循环
    → DashScopeAgentClient       ← LLM 推理
    → ToolExecutor.execute()     ← 工具执行（含 analyze_image）
```

**⚠️ 审核修正（v2）：** 原文档错误地写了"删除 `_prepare_file()` 和 `_pre_analyze_image()` 不影响它"。实际上 Legacy 路径的 `_process_attachments()`（agent.py:315）依赖这两个方法，删除会直接打断 Legacy 路径。

本次重构的处理方式：
- `_prepare_file()` 和 `_pre_analyze_image()` **保留在 agent.py 中**
- Legacy 路径零改动，`_process_attachments()` 继续正常工作
- 仅 LangGraph 路径（`contract_entry.py`）不再调用这两个方法

---

## 五、改动文件清单

| 文件 | 动作 | 风险 |
|------|------|------|
| `services/contract_analyzer.py` | 补 Redis 缓存读写函数 + `analyze_file` 内写缓存 + 更新文件头契约 | 低 |
| `orchestrator/contract_entry.py` | 删 `agent` 依赖，`analyze_file_node` 直调 ContractAnalyzer + `resolve_file_path` | **中**（核心改动） |
| `ai/agent.py` | **不变**（`_prepare_file` / `_pre_analyze_image` 保留给 Legacy） | — |
| `ai/tools.py` | 精简 `analyze_image()` 合同分支，删除缓存写入行 | 低 |
| `api/v1/agent.py` | 子图构造不传 agent | 低 |
| `orchestrator/general_chat.py` | **不变** | — |
| `orchestrator/graph.py` | **不变** | — |
| `orchestrator/sse_adapter.py` | **不变**（已在 commit `f135e2b` 修复） | — |

---

## 六、验证方案

### 6.1 功能验证（手动测试）

| 场景 | 预期行为 |
|------|---------|
| 上传 PDF 合同（有文本） | 出现确认面板，用户确认后创建合同 |
| 上传 PDF 合同（扫描件，无文本） | VL 分析 → 确认面板 → 创建合同 |
| 上传 Word 合同 | 确认面板 → 创建合同 |
| 上传 Excel 合同 | 确认面板 → 创建合同 |
| 上传图片合同 | VL 分析 → 确认面板 → 创建合同 |
| 上传重复文件 | 提示"文件已有对应合同记录"，走 fallback |
| 上传后取消确认 | 提示"已取消合同录入" |
| Legacy 模式（`AGENT_ORCHESTRATOR=legacy`） | 走旧 ReAct 循环，功能不变 |
| 通用对话（无附件） | 走 general_chat 子图，不受影响 |
| 通用对话中调 analyze_image 工具 | 通过 ToolExecutor，不受影响 |

### 6.2 日志验证

重构后上传 PDF 合同的日志应该只有：

```
[INFO] app.ai.orchestrator.contract_entry: analyze_file_node: resolving file_id=xxx
[INFO] app.services.contract_analyzer: PDF 有文本，使用文本模型解析: text_len=1067
[INFO] app.ai.orchestrator.contract_entry: analyze_file_node complete: file_id=xxx
```

不应再出现：
- ~~`图片预分析`~~（LangGraph 路径不再调 `_pre_analyze_image`）
- ~~`vl_cache写入Redis`~~（缓存写入从 `tools.py` 移到 `contract_analyzer.py`，日志名会变化）

> **缓存 key 前缀不变：** Redis key 仍使用 `vl:contract:{file_id}` 格式（与 Legacy 路径兼容），仅写入位置从 `tools.py` 迁移到 `contract_analyzer.py`。

### 6.3 调用链验证

重构后：
- `contract_entry.py` 中 **不应** 出现 `self.agent` 的任何引用
  - 验证：`grep "self.agent" backend/app/ai/orchestrator/contract_entry.py` 应返回空
  - ⚠️ 注意：仅验证 `contract_entry.py`，不要 grep 整个目录（`graph.py` 的 `finalize_node` 仍需要 agent 注入）
- `agent.py` 中 `_prepare_file` 和 `_pre_analyze_image` **应仍然存在**（保留给 Legacy）
  - 验证：`grep "_prepare_file\|_pre_analyze_image" backend/app/ai/agent.py` 应有结果
- `contract_entry.py` 中 **不应** 出现对 `_prepare_file` 或 `_pre_analyze_image` 的调用
  - 验证：`grep "_prepare_file\|_pre_analyze_image" backend/app/ai/orchestrator/contract_entry.py` 应返回空

---

## 七、不做的事（明确边界）

1. **不改前端**：SSE 事件格式不变，前端无需修改
2. **不改 ToolExecutor**：20 个工具定义和执行逻辑不变
3. **不改 LLM 客户端**：DashScope / SiliconFlow 客户端不变
4. **不改 Legacy 路径**：`AGENT_ORCHESTRATOR=legacy` 回滚能力保留，`_prepare_file()` / `_pre_analyze_image()` / `_process_attachments()` 保留不删
5. **不改 `general_chat.py`**：通用对话子图已经独立，不需要改
6. **不改数据库**：无表结构变更
7. **不删 `tools.analyze_image()`**：通用对话子图的 ReAct 循环仍需要通过工具调用
8. **不改 Redis 缓存 key 格式**：保持 `vl:contract:{file_id}`，确保新旧路径缓存互通

---

## 八、风险与回退

### 8.1 风险

| 风险 | 概率 | 缓解 |
|------|------|------|
| ContractAnalyzer 缓存键前缀与 tools.py 不一致 | 中 | 两边 `_cache_key` 必须使用相同前缀（`vl:contract:{file_id}`），否则旧缓存无法命中 |
| ContractAnalyzer 返回格式与子图预期不匹配 | 中 | `analyze_file_node` 内做格式适配（如 `full_text` 字段剥离） |
| Legacy 路径意外受影响 | 低 | 本次不删 agent.py 任何方法，Legacy 零改动 |

### 8.2 回退方案

所有改动通过 git 管理。如出问题：

1. `git revert` 回退本次提交
2. 设置 `AGENT_ORCHESTRATOR=legacy` 环境变量回退到 ReAct 路径
3. 重启 pm2 后端进程

---

## 九、实施顺序

> **命名说明：** 项目已有"Phase 1 = 子图首版、Phase 2 = 子图扩展"命名。此处使用 PR-A / PR-B 避免混淆。

建议分两个 PR 提交，降低风险：

### PR-A：修 glob bug（可单独上线）

1. `_prepare_file()` 加 glob 兜底（对齐 `tools.py` / `ContractAnalyzer` 的文件查找逻辑）
2. 验证 PDF/Word/Excel 上传正常

**效果：** 消除"图片预分析"误触，Legacy 路径调用链正确。但 LangGraph 架构问题仍在。

### PR-B：架构重构（本次方案主体）

1. `contract_analyzer.py`：补 Redis 缓存读写 + 更新文件头契约
2. `contract_entry.py`：删 `agent` 依赖，`analyze_file_node` 直调 ContractAnalyzer
3. `tools.py`：精简 `analyze_image()` 合同分支，删缓存写入行
4. `api/v1/agent.py`：子图构造不传 agent

**效果：** 调用链从 4 层简化为 2 层，子图完全独立。

### PR-C（未来，本次不实施）：Legacy 下线

1. 删除 `_prepare_file()`、`_pre_analyze_image()`、`_process_attachments()`
2. 删除 `AGENT_ORCHESTRATOR=legacy` 分支
3. `tools.analyze_image()` 保留（通用对话子图仍需要）

---

## 十、总结

| 维度 | PR-A 前（当前） | PR-B 后（LangGraph 路径） | Legacy 路径 |
|------|----------------|--------------------------|-------------|
| 文件分析调用层数 | 4 层 | 2 层（子图 → 服务层） | 3 层（不变） |
| 文件查找次数 | 4 次 | 1 次 | 3 次（不变） |
| 子图对 Agent 的依赖 | 2 个私有方法 | 无 | N/A |
| ToolExecutor 实例数 | 2 套（agent + 子图各一套） | 1 套（子图自建） | 1 套（不变） |
| 文件分析逻辑统一性 | 4 处各自实现 | 1 处（ContractAnalyzer） | 3 处（不变） |
| Legacy 回滚 | 名义上有，代码纠缠 | 真正隔离（agent.py 零改动） | 不受影响 |
