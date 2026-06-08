# 智能体架构重构方案 v1.0

> 日期：2026-06-08
> 状态：Accepted
> 原则：激进重构，不缝补。业务场景简单，架构就该简单。

---

## 一、现状诊断：7 个致命问题

### 🔴 P0-1：LLM 没有「识别文件」的工具

**代码证据**：`tools.py:2088-2518`，TOOL_DEFINITIONS 共 20 个工具，无一可分析文件。

文件分析被硬编码在子图的确定性节点里：
- `contract_entry.py:82-201` — `analyze_file_node` 自动调 ContractAnalyzer
- `receipt_entry.py:202-339` — `analyze_receipt_node` 自动调 ReceiptAnalyzer
- `general_chat.py:94-107` — **只把 file_id 拼成文字**，根本不调 VL

**后果**：LLM 无法根据对话上下文判断「这张图是合同还是凭证还是群聊截图」，用户携带不同类型文件时系统完全不知道该做什么。

### 🔴 P0-2：_infer_intent 是脆弱的 if/else，绕过了 LLM

**代码证据**：`graph.py:54-81`

```python
# 文档类默认当合同
if any(t in ("pdf", "word", "excel") for t in file_types):
    return "contract_entry"  # ← 银行转账 PDF 也走合同分析！

# 图片类走 general
if any(t.startswith("image") for t in file_types):
    return "general"  # ← 转账截图直接放弃分析！
```

更严重的是 `route_by_intent` 第 114 行注释说「通用对话子图有图片分析能力」——这是谎言。`general_chat.py:94-107` 只是拼文字，从不调 VL。

### 🔴 P0-3：三个子图上下文彻底断裂

**代码证据**：`state.py:62-93`，ContractEntryState / ReceiptEntryState / GeneralChatState 各自独立。

- 用户上传合同 A → 路由到 contract_entry_subgraph → 创建合同 A
- 用户接着上传合同 B → intake_node 重新推断 intent → 又路由到 contract_entry_subgraph → **这是全新的图执行，合同 A 的 customer_id 等状态不会自动透传到合同 B 的决策**
- 子图之间没有共享的业务上下文。session_context 只有 contract_id/payment_type

### 🔴 P0-4：多文件支持是谎言

**代码证据**：
- `contract_entry.py:115` — `att = attachments[0]` 只取第一个
- `receipt_entry.py:235` — `att = attachments[0]` 只取第一个
- 前端 `pendingFiles` 支持多文件上传 → 后端静默丢弃后续文件

### 🔴 P0-5：工具职责混乱，关键工具缺失

当前 20 个工具的问题：
- 6 个查询工具重叠（`get_overview` / `search_contracts` / `query_payments` / `get_payment_summary` / `get_expense_summary` / `get_expiring_contracts`）
- `create_payment` 和 `create_expense` 参数几乎一样，type 区分即可
- `match_receipt` 名不副实——只查不写，真正的匹配+确认需要 LLM 调多个工具
- `set_pending_plan` 是编排元工具，不该混在业务工具列表里
- ❌ 缺少 `analyze_files` — 文件类型识别+内容提取
- ❌ 缺少 `match_and_confirm_payment` — 凭证→待确认收款自动匹配+确认

### 🔴 P0-6：VL 失败直接结束对话，无 fallback

**代码证据**：`contract_entry.py:156-162`

```python
if not result.get("success"):
    return {
        "messages": [AIMessage(content="文件分析失败...")],
        "should_end": True,  # ← 用户卡死
    }
```

没有重试、没有切换 SiliconFlowClient 兜底、没有让用户手动提供关键字的 fallback。

### 🔴 P0-7：set_pending_plan 三阶段确认过于复杂

`set_pending_plan` 引入了 plan_id、actions 白名单、plan 持久化、needs_plan/needs_confirmation/action_not_in_plan 三段拦截（约 80 行 × 2 个子图 = 160 行重复代码），但核心目的只是「防止 LLM 跳过用户确认」。

---

## 二、根本原因

所有问题指向同一个根源：

> **系统把「文件分析」作为子图的内部隐式行为，而非显式的、可被 LLM 调度的工具。**

连锁反应：
1. 分析是隐式的 → 需要路由来决定走哪个分析器 → 路由变成猜谜
2. 分析结果塞在 state 里 → 多文件切换时 context 混乱
3. LLM 不能主动分析 → 用户传了文件但没说明意图时系统瘫痪
4. 分析器和工具分离 → match_receipt 等工具名不副实

---

## 三、重构方案：单层 Agent + 文件先行

### 3.1 新架构

```
用户输入（消息 + 附件）
        ↓
   ┌─────────────────────────────┐
   │      intake_node            │  仅做：注入 system prompt + 附件元信息到 messages
   │   （不做任何路由判断）        │
   └─────────────────────────────┘
        ↓
   ┌─────────────────────────────┐
   │      call_model_node        │  LLM 看到「有 2 个附件」→ 调 analyze_files
   │   （LLM 自主决策）           │  LLM 看到分析结果是合同 → 调 create_customer + create_contract
   └─────────────────────────────┘
        ↑              ↓
        │     execute_tool_node
        │   （统一执行所有工具）
        └────────────────┘
        ↓（无 tool_calls）
   finalize_node → END
```

**删除的东西**：
- ❌ `_infer_intent()` 函数
- ❌ `route_by_intent()` 条件边
- ❌ `contract_entry_subgraph` 子图
- ❌ `receipt_entry_subgraph` 子图
- ❌ `general_chat_subgraph` 子图
- ❌ `group_chat_node` 降级节点
- ❌ `receipt_entry_node` 降级节点
- ❌ `ContractEntryState` / `ReceiptEntryState` / `GeneralChatState` 三个子 State
- ❌ `set_pending_plan` 工具
- ❌ `mode guard` / `document guard`
- ❌ `_MODE_ALLOWED_TOOLS` / `_DOCUMENT_BLOCKED_TOOLS`
- ❌ `ContractAnalyzer` / `ReceiptAnalyzer` 两个独立分析器

**保留的东西**：
- ✅ `RootState`（精简版）
- ✅ `finalize_node`（chat_history 落库）
- ✅ `ToolExecutor`（业务逻辑执行层）
- ✅ `DashScopeAgentClient`（LLM 调用）
- ✅ Service 层（contract_service / customer_service / payment_service）
- ✅ Model 层 + API 层

### 3.2 精简后的 State

```python
class AgentState(TypedDict, total=False):
    """统一 Agent 状态"""
    # 消息流
    messages: Annotated[list, add_messages]
    # 用户上下文
    user_id: int
    user_role: str
    session_id: str
    # 附件（本轮）
    attachments: list[dict]
    # 流程控制
    iteration_count: int
    should_end: bool
    # chat_history 落库标记
    chat_history_meta: dict
    _finalized: bool
```

**删除的字段**：intent、file_context、interrupt_info、tools_invoked、pending_tool_calls、errors、fallback_strategy、current_node、executor_mode、session_context、pending_plan。

### 3.3 精简后的工具集（14 个）

#### 分析工具（新增）

| 工具名 | 职责 |
|--------|------|
| `analyze_files` | 接受 file_ids，自动识别类型（合同/凭证/证件/车辆照片/群聊截图/其他），提取结构化数据。支持批量。纯分析不写库 |

#### 客户工具

| 工具名 | 职责 |
|--------|------|
| `search_customers` | 搜索客户（模糊匹配，繁简兼容） |
| `create_customer` | 创建/去重客户 |
| `update_customer` | 更新客户信息 |

#### 合同工具

| 工具名 | 职责 |
|--------|------|
| `search_contracts` | 搜索合同（多条件，含状态/日期/关键词） |
| `get_contract_detail` | 合同详情 + 付款进度 + 待确认收款列表 |
| `create_contract` | 创建合同 + 自动创建 pending 付款记录（含去重） |
| `update_contract` | 更新合同元信息（微信群/备注等） |

#### 付款工具

| 工具名 | 职责 |
|--------|------|
| `query_payments` | 付款记录查询（按合同/状态/类型/日期，含分组聚合） |
| `create_payment_record` | 统一的收款/支出创建（type=income/expense 区分），有凭证时自动设为 paid |
| `match_and_confirm_payment` | 凭证匹配待确认记录并确认（代码确定性匹配 + 自动更新状态为 paid） |
| `update_payment` | 手动更新付款记录 |

#### 统计工具

| 工具名 | 职责 |
|--------|------|
| `get_overview` | 全局统计概览（客户/合同/收支/即将到期） |
| `search_contract_text` | 合同全文搜索（含 contract_id 参数，合并 ask_contract） |

#### 合并/删除逻辑

| 原工具 | 处理 |
|--------|------|
| `create_payment` + `create_expense` | → 合并为 `create_payment_record(type=income/expense)` |
| `match_receipt` | → 升级为 `match_and_confirm_payment`，真正执行匹配+确认 |
| `get_payment_summary` + `get_expense_summary` | → 合并到 `query_payments` 加 group_by 参数 |
| `get_expiring_contracts` | → 合并到 `get_overview`（已有此数据） |
| `get_customer_contracts` | → 删除，`search_contracts(customer_name=)` 可替代 |
| `ask_contract` | → 合并到 `search_contract_text(contract_id=, keyword=)` |
| `set_pending_plan` | → 删除，用轻量确认机制替代 |

### 3.4 analyze_files 工具详细设计

```python
{
    "name": "analyze_files",
    "description": "分析上传的文件。自动识别文件类型（合同/凭证/证件/车辆照片/群聊截图/其他），并提取结构化信息。同一轮对话内可多次调用（如用户改主意说"这是凭证不是合同"时重调）。纯分析工具，不写数据库。",
    "parameters": {
        "type": "object",
        "required": ["file_ids"],
        "properties": {
            "file_ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": "要分析的文件ID列表，支持批量"
            },
            "purpose": {
                "type": "string",
                "enum": ["auto", "contract", "receipt", "vehicle", "id_document", "group_chat"],
                "description": "分析目的提示。auto=自动判断（默认），其余为强制指定类型",
                "default": "auto"
            }
        }
    }
}
```

**内部实现**：
1. 合并 `ContractAnalyzer` + `ReceiptAnalyzer` 为统一的 `FileAnalyzer`
2. `FileAnalyzer.analyze(file_path, purpose)` 根据 purpose 选择 prompt：
   - `auto` → 先用 VL 做类型分类（合同/凭证/证件/车辆/群聊/其他），再按类型提取
   - `contract` → 用合同提取 prompt
   - `receipt` → 用凭证提取 prompt
   - 其余 → 通用提取 prompt
3. 返回 `{type: "contract"|"receipt"|..., data: {...}, file_ids: [...]}`
4. 支持多文件：每个文件独立分析，结果合并返回

### 3.5 轻量确认机制（替代 set_pending_plan）

**删除**：plan_id、actions 白名单、needs_plan/needs_confirmation/action_not_in_plan 三段拦截、pending_plan state 字段。

**替代方案**：

在 `execute_tool_node` 中，写入工具（create_customer / create_contract / create_payment_record / match_and_confirm_payment）首次在本轮被调用时，检查 LLM 的上 N 条消息中是否包含确认询问（如「确认吗」「是否继续」等语义）。

```python
_WRITABLE_TOOLS = {"create_customer", "create_contract", "create_payment_record", "match_and_confirm_payment"}

def _has_confirmation_in_context(messages: list, min_turns: int = 3) -> bool:
    """检查最近几轮对话中 LLM 是否展示过计划并请求确认。
    
    策略：查看最近 min_turns 条 AIMessage，
    如果任何一条包含确认相关的语义（由 LLM 自然表达），
    则视为已展示计划。
    """
    ai_msgs = [m for m in messages[-min_turns*2:] if isinstance(m, AIMessage)]
    # 简单启发式：AI 消息中是否包含确认请求的标志性内容
    # 实际实现可以用更智能的方式
    for msg in ai_msgs[-min_turns:]:
        content = (msg.content or "").lower()
        if any(kw in content for kw in ("确认", "是否", "同意", "继续", "对吗", "正确吗")):
            return True
    return False

# 在 execute_tool_node 中：
if tool_name in _WRITABLE_TOOLS:
    if not _has_confirmation_in_context(state["messages"]):
        return ToolMessage(
            content=json.dumps({
                "error": "请先向用户展示操作计划并得到确认，再执行写入操作。",
                "tool": tool_name,
            }),
            tool_call_id=tc["id"],
        )
```

**trade-off**：
- 放弃了 set_pending_plan 的精确性（plan_id / actions 白名单硬约束）
- 换来了极大的简化（~200 行安全门代码 → ~20 行启发式检查）
- LLM 可能绕过确认。缓解：在 system prompt 中强指令「所有写入操作前必须先展示计划并请求确认」

### 3.6 match_and_confirm_payment 详细设计

替代原来的 match_receipt + create_payment/update_payment 的手动组合。

```python
{
    "name": "match_and_confirm_payment",
    "description": "根据凭证分析结果，自动匹配合同中待确认(pending)的付款记录。匹配成功则更新为paid；无匹配则创建新付款记录。需要先调 analyze_files 获取凭证数据。",
    "parameters": {
        "type": "object",
        "required": ["contract_id", "receipt_data"],
        "properties": {
            "contract_id": {"type": "integer", "description": "关联合同ID"},
            "receipt_data": {"type": "object", "description": "analyze_files 返回的凭证分析结果"},
            "payment_type": {
                "type": "string",
                "enum": ["income", "expense"],
                "description": "收入或支出",
            },
        }
    }
}
```

**内部匹配逻辑**（代码确定性，不交给 LLM）：
1. 查询该合同所有 pending 状态的同类型付款记录
2. 按「金额匹配 → 日期接近 → 付款方名匹配」排序
3. 匹配成功 → 更新 pending 为 paid，写入凭证路径和 receipt_data
4. 无匹配 → 创建新付款记录（paid 状态，有凭证）
5. 返回匹配结果详情

### 3.7 FileAnalyzer 统一设计

合并 ContractAnalyzer + ReceiptAnalyzer，消除 80% 重复代码。

```python
class FileAnalyzer:
    """统一文件分析器 — 纯分析逻辑，不涉及缓存/session/持久化"""
    
    # 类型 → prompt 映射
    ANALYSIS_PROMPTS = {
        "contract": CONTRACT_ANALYSIS_PROMPT,
        "receipt": RECEIPT_ANALYSIS_PROMPT,
        "vehicle": VEHICLE_ANALYSIS_PROMPT,      # 新增
        "id_document": ID_DOC_ANALYSIS_PROMPT,    # 新增
        "group_chat": GROUP_CHAT_ANALYSIS_PROMPT, # 新增
    }
    
    # 类型分类 prompt（purpose=auto 时使用）
    CLASSIFY_PROMPT = "请判断这张图片/文档属于哪种类型：合同、付款凭证、车辆照片、证件、群聊截图、其他"
    
    @staticmethod
    def analyze(file_path: str, file_name: str, purpose: str = "auto") -> dict:
        """统一分析入口
        
        Args:
            file_path: 文件绝对路径
            file_name: 原始文件名
            purpose: 分析目的 (auto/contract/receipt/vehicle/id_document/group_chat)
        
        Returns:
            {
                "success": True,
                "type": "contract"|"receipt"|"vehicle"|...,
                "data": {...},       # 类型对应的结构化数据
                "file_type": "image"|"pdf"|"document",
                "confidence": 0.0-1.0,
            }
        """
        # 1. 读取文件，判断 MIME 类型
        # 2. 图片 → VL；PDF/Word/Excel → 文本模型
        # 3. purpose=auto → 先分类，再提取
        # 4. purpose=指定 → 直接用对应 prompt 提取
        # 5. VL 失败 → 重试 SiliconFlowClient；再失败 → 返回错误+提示用户手动提供
```

### 3.8 新的 Graph 定义

```python
def build_agent_graph(checkpointer=None, agent=None) -> StateGraph:
    """统一 Agent Graph — 单层循环，无子图"""
    workflow = StateGraph(AgentState)
    
    workflow.add_node("call_model_node", call_model_node)
    workflow.add_node("execute_tool_node", execute_tool_node)
    workflow.add_node("finalize_node", make_finalize_node(agent))
    
    workflow.add_edge(START, "call_model_node")
    workflow.add_conditional_edges("call_model_node", should_continue, {
        "execute_tool_node": "execute_tool_node",
        "finalize_node": "finalize_node",
    })
    workflow.add_edge("execute_tool_node", "call_model_node")
    workflow.add_edge("finalize_node", END)
    
    return workflow.compile(checkpointer=checkpointer)
```

---

## 四、ADR：关键架构决策

### ADR-001：单层 Agent 替代多子图架构

**Status**: Accepted

**Context**: 当前 Root Graph → 4 子图架构过度复杂。子图之间代码重复严重（Agent 循环 × 3，安全门 × 2），意图推断路由脆弱（if/else），上下文在子图间断裂。业务场景只有 3 个：录合同、录凭证、聊天查询，不需要子图级别的隔离。

**Decision**: 用单一 Agent 循环 + `analyze_files` 工具替代多子图。LLM 通过文件分析结果自主决定业务路径，不再由代码层路由。

**Consequences**:
- ✅ 新增文件类型只需扩展 FileAnalyzer，无需增删子图
- ✅ LLM 上下文完整（不被 subgraph 边界截断）
- ✅ 多文件场景天然支持（analyze_files 接受 file_ids 数组）
- ✅ 代码量从 ~3500 行编排层降到 ~800 行
- ⚠️ 单次 LLM 调用的 system prompt 稍长（需包含所有业务规则）
- ⚠️ 需要确保 LLM 不会在单轮内做过多无关工具调用（通过 iteration_count 限制）

### ADR-002：废弃 set_pending_plan，采用轻量确认

**Status**: Accepted

**Context**: set_pending_plan 的三阶段确认引入 plan_id、actions 白名单、plan 持久化等大量复杂度（约 160 行重复代码），但核心目的只是「防止 LLM 跳过用户确认」。

**Decision**: 用 execute_tool_node 层的轻量启发式检查替代。写入工具执行前检查 LLM 上文是否包含确认询问。

**Consequences**:
- ✅ LLM 工作流更自然（不需要理解 set_pending_plan 的内部机制）
- ✅ 代码量大幅减少（~160 行 → ~20 行）
- ⚠️ LLM 理论上可能绕过确认。缓解：system prompt 强指令 + 启发式检查双重防护
- ⚠️ 启发式检查可能有误判。缓解：宁可多拦（多问一次确认）不可漏放

### ADR-003：凭证匹配从查询改为写入

**Status**: Accepted

**Context**: match_receipt 只查询不写入，真正的匹配+确认需要 LLM 调多个工具（match_receipt → create_payment/update_payment），增加了出错概率和 tool call 轮数。

**Decision**: 新增 match_and_confirm_payment 替代 match_receipt，内部完成：按金额/日期/付款方匹配 pending 记录 → 自动确认 → 更新状态为 paid。无匹配时创建新记录。

**Consequences**:
- ✅ LLM 一次调用完成匹配+确认，减少 tool call 轮数
- ✅ 匹配逻辑从 LLM 判断变为代码确定性判断（模糊匹配阈值、日期容差）
- ⚠️ 自动匹配可能出错。缓解：返回匹配详情，LLM 可追问用户确认

### ADR-004：合并文件分析器为 FileAnalyzer

**Status**: Accepted

**Context**: ContractAnalyzer 和 ReceiptAnalyzer 有 80% 重复代码（文件头判断、图片压缩、VL 调用、PDF 多策略），唯一区别是 prompt。

**Decision**: 合并为 FileAnalyzer.analyze(file_path, purpose, prompt)，调用方传 purpose 即可。新增 auto 模式先分类再提取。

**Consequences**:
- ✅ 消除 80% 重复代码
- ✅ 新增文件类型（车辆照片、证件等）只需加 prompt
- ✅ auto 模式解决 _infer_intent 的根本问题
- ⚠️ auto 模式多一次 VL 调用（分类 + 提取）。缓解：分类结果极短（1 个标签），token 开销极低

### ADR-005：工具集精简 20→14

**Status**: Accepted

**Context**: 当前 20 个工具中，6 个查询工具重叠、2 个写入工具参数几乎一样、1 个是编排元工具、1 个名不副实。

**Decision**: 精简为 14 个业务工具。合并规则见 3.3 节。

**Consequences**:
- ✅ LLM 选工具更准确（减少重叠 = 减少困惑）
- ✅ 工具描述更清晰（每个工具职责唯一）
- ⚠️ 部分工具参数增多（如 create_payment_record 需 type 字段）。缓解：type 有默认推断逻辑

---

## 五、文件变更清单

### 新建文件

| 文件 | 说明 |
|------|------|
| `backend/app/ai/orchestrator/unified_agent.py` | 统一 Agent 图定义（替代 graph.py + 3 个子图） |
| `backend/app/services/file_analyzer.py` | 统一文件分析器（替代 contract_analyzer.py + receipt_analyzer.py） |
| `backend/app/ai/prompts_v2.py` | 新版 prompt（含文件分类 prompt、车辆/证件/群聊 prompt） |

### 修改文件

| 文件 | 变更 |
|------|------|
| `backend/app/ai/tools.py` | 精简工具 20→14，新增 analyze_files / match_and_confirm_payment，删除 set_pending_plan |
| `backend/app/ai/orchestrator/state.py` | 替换为精简 AgentState |
| `backend/app/ai/orchestrator/sse_adapter.py` | 适配新 Graph |
| `backend/app/ai/prompts.py` | 合并到 prompts_v2.py 或保留兼容 |
| `backend/app/api/v1/agent.py` | 适配新 Graph 入口 |
| `backend/app/ai/agent.py` | 保留会话管理功能，移除遗留方法 |

### 删除文件

| 文件 | 原因 |
|------|------|
| `backend/app/ai/orchestrator/graph.py` | 被 unified_agent.py 替代 |
| `backend/app/ai/orchestrator/contract_entry.py` | 子图删除 |
| `backend/app/ai/orchestrator/receipt_entry.py` | 子图删除 |
| `backend/app/ai/orchestrator/general_chat.py` | 子图删除 |
| `backend/app/services/contract_analyzer.py` | 被 file_analyzer.py 替代 |
| `backend/app/services/receipt_analyzer.py` | 被 file_analyzer.py 替代 |

---

## 六、实施计划

### Phase 1：核心重组（Day 1-3）

1. **新建 FileAnalyzer** — 合并两个 Analyzer，支持 auto 分类 + 指定 purpose
2. **新建 analyze_files 工具** — ToolExecutor 新增方法，TOOL_DEFINITIONS 新增定义
3. **精简工具集** — 20→14，合并/删除/新增
4. **新建 unified_agent.py** — 单层 Agent 循环，替代 graph.py + 3 个子图
5. **新建 AgentState** — 替换 RootState + 3 个子 State

### Phase 2：确认机制 + 匹配逻辑（Day 3-4）

6. **实现轻量确认机制** — 替代 set_pending_plan
7. **实现 match_and_confirm_payment** — 凭证→待确认收款自动匹配+确认

### Phase 3：入口适配 + 清理（Day 4-5）

8. **适配 agent.py API 入口** — 接入新 Graph
9. **适配 sse_adapter.py** — 适配新事件流
10. **删除旧代码** — 移除子图、旧 Graph、旧 Analyzer
11. **端到端测试** — 合同录入、凭证录入、支出录入、通用查询

---

## 七、风险与缓解

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| auto 分类不准 | 中 | LLM 拿到错误的分析结果 | 保留 purpose 参数让 LLM 纠正；分类 prompt 增加示例 |
| 轻量确认被 LLM 绕过 | 低 | 写入操作未经用户确认 | system prompt 强指令 + 启发式检查 + 前端二次确认弹窗 |
| match_and_confirm 误匹配 | 中 | 凭证关联到错误的付款记录 | 返回匹配详情和置信度，低置信度时 LLM 追问用户 |
| 单层 Agent prompt 过长 | 低 | LLM 忽略部分指令 | 分层 prompt：核心规则（必须遵守）+ 场景提示（按需注入） |
| 旧会话 checkpoint 不兼容 | 高 | 切换后旧会话报错 | 上线时清空 checkpoint 表；或在新 State 解析中做向后兼容 |
