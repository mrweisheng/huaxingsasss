# 合同/凭证录入 Agent 确认机制完整方案 v2.1

> 基于 v1 + 行业调研 + PocketOS 事故教训 + 外部审核修正。修正了 3 个严重 bug + 3 个设计缺陷。

## 一、背景（不变，略）

核心问题：`create_customer` / `create_contract` / `create_payment` / `create_expense` 四个写入工具直接写库，LLM 误判即产脏数据。

历史踩坑（不变）：interrupt 机制 100% 失败、直接执行无确认、词库式确认被否决。

## 二、行业调研补充

### 2.1 主流框架的确认机制对比

| 框架 | 确认机制 | 核心模式 | 我们可借鉴的 |
|---|---|---|---|
| **LangGraph 1.2.x** | `interrupt()` + `Command(resume=...)` | 工具内部暂停 → 前端弹窗 → resume 恢复 | 在子图+checkpoint 场景脆弱，我们已踩过坑 ❌ |
| **OpenAI Agents SDK** | `needs_approval` 配置 + `RunState` 序列化 | 工具标记 → Runner 暂停 → 开发者 approve/reject → Runner.run 恢复 | **粘性决策（Sticky Decisions）**：同一工具 approve 一次后自动放行后续调用 |
| **Claude Agent SDK** | `ToolPolicy.confirmRequired` + `confirm_action` 工具 | 策略白名单 → 敏感工具自动弹确认 → 用户 y/n | **渐进式开放权限**：先用只读工具验证，再开放写入 |
| **Google ADK** | `escalate_to_human` 工具 + Prompt 分级 | Prompt 规定 AI 必须穷尽自主能力后才移交人类 | **升级策略**：不是所有操作都确认，只有"超纲"的才确认 |
| **MCP Tool Annotations** | `readOnlyHint` / `destructiveHint` / `idempotentHint` | 工具自描述风险等级 → 客户端按等级决定确认策略 | **风险词汇分级**：不是二元（敏感/不敏感），而是有层次的 |

### 2.2 PocketOS 事故教训（2026-04-25）

Cursor（运行 Claude Opus 4.6）9 秒内删除了 PocketOS 整个生产数据库和所有卷级备份。

**根因**：Agent 执行了 `rm -rf` 级别的破坏性操作，没有任何确认机制。

**教训**：
1. 不可逆操作 **必须** 有代码层面的硬约束，不能只靠 prompt 引导
2. Defense in depth：prompt 引导 + 代码兜底缺一不可
3. 确认机制要"短链路"——链路越长越容易出 bug

### 2.3 调研结论 → 对我们方案的影响

1. **粘性决策**：OpenAI 的 `always_approve` 思路值得借鉴——同一轮对话中，用户确认一次 plan 后，后续同类型 create 不需要再确认
2. **风险分级**：MCP 的 annotations 思路值得借鉴——`create_customer`（可覆盖/去重）和 `create_contract`（不可覆盖）风险不同
3. **渐进式验证**：Claude SDK 的"先用只读验证再开放写入"思路——我们可以让 LLM 先调 `search_customers` 确认客户是否存在，再调 `create_customer`
4. **短链路优先**：PocketOS 事故证实——我们的"不依赖 interrupt + 聊天原生确认"方向是对的

## 三、设计目标

1. 安全性：任何 `create_*` 必须有用户明确确认，LLM 无法绕过
2. 简单性：链路短、调试容易，不依赖 checkpoint + SSE interrupt + 前端特殊 UI
3. 聊天原生：确认就是用户在聊天框打几个字，不弹窗
4. 符合 CLAUDE.md：决策权交给 LLM，硬约束放代码
5. 可扩展：新增敏感工具只需改一处配置

## 四、核心设计思想

### 4.1 两层防御

```
┌─────────────────────────────────────────────────┐
│  LLM 软决策层（prompt + 工具调用）                │
│  - 决定何时展示计划                              │
│  - 决定计划内容（要创建哪些对象）                  │
│  - 判断用户是否确认（语义理解，不用词库）          │
└─────────────────────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────┐
│  代码硬约束层（execute_tool_node 校验）            │
│  - create_* 必须有 pending_plan                 │
│  - pending_plan.user_confirmed == True          │
│  - 工具名必须在 pending_plan.actions 里          │
└─────────────────────────────────────────────────┘
```

### 4.2 计划驱动（Plan-Driven）

每个敏感操作必须事先被声明在 plan 里，且 plan 必须经过用户确认。

### 4.3 关键创新：set_pending_plan 内部工具

这是一个纯 LLM 决策工具，不调任何外部 Service，只改 state。

#### A. `set_pending_plan` 不放在 ToolExecutor 中

`ToolExecutor` 的职责是"调 Service 层返回纯 JSON"。`set_pending_plan` 不调任何 Service，只改 LangGraph state，是编排层的事。

**正确做法**：在 `execute_tool_node` 中直接处理，`ToolExecutor` 完全不需要知道这个工具的存在。

但 `set_pending_plan` 仍然需要出现在 `TOOL_DEFINITIONS` 中——LLM 需要看到它才能调用。

#### B. 工具定义（含例子流程）

```json
{
    "name": "set_pending_plan",
    "description": "声明录入计划并请求用户确认。工作流：1) 首次调 set_pending_plan(summary='客户张三，金额35万', actions=['create_customer','create_contract'], user_confirmed=False) 向用户展示计划；2) 用户回复确认后，再次调 set_pending_plan(summary=同前, actions=同前, user_confirmed=True)，然后调 create_customer、create_contract 执行。所有 create_customer/create_contract/create_payment/create_expense 调用前必须先调此工具。",
    "parameters": {
        "type": "object",
        "properties": {
            "summary": {
                "type": "string",
                "description": "向用户展示的计划摘要，1-2 句话"
            },
            "actions": {
                "type": "array",
                "items": {
                    "type": "string",
                    "enum": [
                        "create_customer", "create_contract",
                        "create_payment", "create_expense",
                        "update_payment"
                    ]
                },
                "description": "计划中要执行的所有 create/update 类工具名"
            },
            "user_confirmed": {
                "type": "boolean",
                "description": "用户是否已确认此计划。由你（LLM）根据用户最新回复的语义自行判断，不要依赖词库匹配。"
            }
        },
        "required": ["summary", "actions", "user_confirmed"]
    }
}
```

### 4.4 关键修正：LangGraph state 持久化规则

**问题**：`state["pending_plan"] = {...}` 是对传入 state dict 的局部 mutation。LangGraph 节点的契约是**返回值 merge 回 state**，不是直接改传入的 state dict。局部 mutation 不会写入 checkpoint，下一轮 `call_model_node` 读到的还是旧值。

**修复**：所有 `pending_plan` 的修改都必须通过 return dict 返回：

```python
# ❌ 错误写法
if tool_name == "set_pending_plan":
    state["pending_plan"] = {...}  # 局部 mutation，LangGraph 看不到

# ✅ 正确写法
pending_plan_was_updated = False
new_pending_plan = state.get("pending_plan")  # 读当前值

if tool_name == "set_pending_plan":
    new_pending_plan = {
        "summary": args.get("summary", ""),
        "actions": args.get("actions", []),
        "user_confirmed": bool(args.get("user_confirmed", False)),
    }
    pending_plan_was_updated = True
    # 后续本节点内校验用 new_pending_plan
    ...

# 末尾 return
extra = {"current_node": "execute_tool_node"}
if any_sensitive_succeeded:
    extra["pending_plan"] = None  # 清理
elif pending_plan_was_updated:
    extra["pending_plan"] = new_pending_plan  # 持久化到 checkpoint
```

**关键规则**：
- 读取 state：通过 `state.get("pending_plan")` ✅
- 写入 state：通过 return dict `{"pending_plan": ...}` ✅
- 绝不能 `state["pending_plan"] = ...` 然后 expect LangGraph 帮你持久化 ❌

## 五、完整数据流

### 5.1 正常流程：用户确认

```
消息 1: 用户上传合同
  → analyze_file_node
    → should_end=False, iteration_count=0 （入口重置）
    → VL 分析合同
  → call_model_node (iter 1)
    → set_pending_plan(summary="...", actions=[create_customer, create_contract], user_confirmed=False)
  → execute_tool_node (iter 1)
    → set_pending_plan: 不走 ToolExecutor，内联处理
    → return {"messages": [...], "pending_plan": {"summary":..., "actions":[...], "user_confirmed":False}}
      ← 通过 return dict 持久化到 checkpoint
  → call_model_node (iter 2)
    → 读到 pending_plan.user_confirmed==False
    → LLM 回复用户: "客户张三，金额¥350,000。是否确认创建？"
    → 无 tool_calls → should_end=True → END

消息 2: 用户回复 "确认"
  → analyze_file_node
    → should_end=False, iteration_count=0 （入口重置）
  → call_model_node (iter 3)
    → LLM 理解意图=同意
    → set_pending_plan(user_confirmed=True) + create_customer + create_contract
  → execute_tool_node (iter 2)
    → set_pending_plan: 更新 pending_plan（通过 return dict 持久化 user_confirmed=True）
    → create_customer: 校验通过 → 放行
    → create_contract: 校验通过 → 放行
    → return {"messages": [...], "pending_plan": None} ← 成功后清理
  → call_model_node (iter 4)
    → LLM 回复: "已创建客户张三、合同 HT20260608xxx"
    → should_end=True → END
```

### 5.2 异常流程 1：LLM 第一轮就调 create_*（违规）

```
→ call_model_node (iter 1)
  → LLM 没等用户确认，直接调 create_customer
→ execute_tool_node
  → create_customer 校验: pending_plan is None → 拒绝
  → 返回: {"status": "needs_plan", "hint": "先调 set_pending_plan..."}
→ call_model_node (iter 2)
  → LLM 看到拒绝消息 → 自我纠正
  → 调 set_pending_plan(user_confirmed=False) → 向用户展示
```

### 5.3 异常流程 2：用户拒绝

```
→ call_model_node
  → LLM 看到用户犹豫 → 理解意图=拒绝
  → set_pending_plan(user_confirmed=False)
  → 不调 create_*
→ LLM 回复: "好的，等您确认后继续"
```

### 5.4 异常流程 3：LLM 调未声明的 create

```
→ call_model_node
  → set_pending_plan(actions=["create_customer"]) + create_contract（不在 plan 里）
→ execute_tool_node
  → create_customer: 在 plan 里 → 放行
  → create_contract: 不在 plan.actions → 拒绝
→ call_model_node (下一轮)
  → LLM 重新调 set_pending_plan 包含 create_contract
```

### 5.5 异常流程 4：create 返回业务错误

```
→ execute_tool_node
  → create_customer 返回 {"success": false, "error": "客户已存在"}
  → any_sensitive_succeeded 不被设为 True（解析 result 里的 success 字段）
  → pending_plan 不被清理 → LLM 下轮可以调整后重试
```

### 5.6 多轮对话 should_end 重置

在子图的入口节点（`analyze_file_node` / `analyze_receipt_node`）中显式重置：

```python
async def analyze_file_node(state: ContractEntryState) -> dict:
    result = {
        "should_end": False,
        "iteration_count": 0,
    }
    # ... 原有逻辑 ...
    return result
```

### 5.7 pending_plan 清理机制

**规则**：只有敏感工具**业务成功**时才清理 pending_plan。工具抛异常或返回业务错误时**不清理**，让 LLM 可以调整后重试。

**判定"业务成功"**：解析 ToolExecutor 返回的 JSON，检查 `success` 字段。

## 六、具体改动清单

### 6.1 `backend/app/ai/orchestrator/state.py`

新增 `pending_plan` 字段：

```python
class ContractEntryState(RootState, total=False):
    pending_plan: Optional[dict] = None  # 新增
    # 结构: {"summary": str, "actions": list[str], "user_confirmed": bool}

class ReceiptEntryState(RootState, total=False):
    pending_plan: Optional[dict] = None  # 新增
```

注意：`approved_tool_ids` 和 `interrupt_info` 将在旧 interrupt 清理 commit 中删除（见 6.7）。

### 6.2 `backend/app/ai/tools.py`

**A. TOOL_DEFINITIONS 加 set_pending_plan**（第 20 个工具）

**B. _MODE_ALLOWED_TOOLS 不加 set_pending_plan**

`set_pending_plan` 在 `execute_tool_node` 里 `continue` 掉了，根本不会进 `executor.execute()`，mode guard 检查不到它。加了反而是死代码，误导性强。

如果未来有人把 `set_pending_plan` 移进 ToolExecutor，到时候再加不迟。

**C. ToolExecutor 不变**——`set_pending_plan` 不在 ToolExecutor 中实现，由 `execute_tool_node` 内联处理。

**D. ToolExecutor.execute() 不加 state 参数**——保持现有接口签名不变。

### 6.3 `backend/app/ai/orchestrator/contract_entry.py`

**A. analyze_file_node 入口重置**

```python
async def analyze_file_node(state: ContractEntryState) -> dict:
    result = {
        "should_end": False,       # 每次进入子图重置
        "iteration_count": 0,      # 重置迭代计数
    }
    # ... 原有逻辑 ...
    return result
```

**B. execute_tool_node（完整版）**

```python
async def execute_tool_node(state: ContractEntryState) -> dict:
    last_msg = state["messages"][-1]
    if not getattr(last_msg, "tool_calls", None):
        return {}

    all_tool_calls = last_msg.tool_calls
    pending_plan = state.get("pending_plan")  # 读当前值
    tool_messages = []
    any_sensitive_succeeded = False
    pending_plan_was_updated = False   # 追踪 pending_plan 是否被修改
    new_pending_plan = pending_plan    # 暂存修改后的值

    for tc in all_tool_calls:
        tool_name = tc["name"]
        try:
            args = tc["args"] if isinstance(tc["args"], dict) else (
                json.loads(tc["args"]) if isinstance(tc["args"], str) else {}
            )
        except json.JSONDecodeError:
            args = {}

        # ━━━ set_pending_plan: 编排层内联处理，不走 ToolExecutor ━━━
        if tool_name == "set_pending_plan":
            new_pending_plan = {
                "summary": args.get("summary", ""),
                "actions": args.get("actions", []),
                "user_confirmed": bool(args.get("user_confirmed", False)),
            }
            pending_plan_was_updated = True
            result = json.dumps({
                "status": "ok",
                "message": "计划已更新" if new_pending_plan["user_confirmed"] else "计划已设置，等待用户确认",
                "plan": new_pending_plan,
            }, ensure_ascii=False)
            tool_messages.append(ToolMessage(content=result, tool_call_id=tc["id"]))
            # 后续本节点内校验用 new_pending_plan
            continue

        # ━━━ 硬约束：敏感工具必须经过 pending_plan 确认 ━━━
        if tool_name in _SENSITIVE_TOOLS:
            if new_pending_plan is None:
                result = json.dumps({
                    "status": "needs_plan",
                    "error": f"未声明计划，禁止调用 {tool_name}",
                    "hint": "先调 set_pending_plan(summary, actions=[...], user_confirmed=false) 声明计划并请求用户确认",
                }, ensure_ascii=False)
                tool_messages.append(ToolMessage(content=result, tool_call_id=tc["id"]))
                continue

            if not new_pending_plan.get("user_confirmed"):
                result = json.dumps({
                    "status": "needs_confirmation",
                    "error": f"用户尚未确认计划，禁止调用 {tool_name}",
                    "hint": "先向用户展示计划摘要并问'是否确认'，用户确认后再次调 set_pending_plan(user_confirmed=true)",
                }, ensure_ascii=False)
                tool_messages.append(ToolMessage(content=result, tool_call_id=tc["id"]))
                continue

            if tool_name not in new_pending_plan.get("actions", []):
                result = json.dumps({
                    "status": "action_not_in_plan",
                    "error": f"{tool_name} 不在已确认的计划中",
                    "hint": f"已确认计划包含: {new_pending_plan.get('actions')}",
                }, ensure_ascii=False)
                tool_messages.append(ToolMessage(content=result, tool_call_id=tc["id"]))
                continue

        # ━━━ 通过校验，正常执行 ━━━
        try:
            result = await asyncio.to_thread(executor.execute, tool_name, args)
            logger.info("合同录入工具结果: %s → %s", tool_name, result[:200] if result else "empty")
            # 解析 result 判断业务是否成功（不只是没抛异常）
            if tool_name in _SENSITIVE_TOOLS:
                try:
                    parsed = json.loads(result) if isinstance(result, str) else result
                    if isinstance(parsed, dict) and parsed.get("success"):
                        any_sensitive_succeeded = True
                except (json.JSONDecodeError, TypeError):
                    # 无法解析结果，保守起见不算成功
                    pass
        except Exception as e:
            result = json.dumps({"error": f"工具执行出错: {e}"}, ensure_ascii=False)
            logger.warning("合同录入工具异常: %s → %s", tool_name, e, exc_info=True)

        tool_messages.append(ToolMessage(content=result, tool_call_id=tc["id"]))

    # ━━━ 通过 return dict 持久化 pending_plan 变更 ━━━
    extra = {"current_node": "execute_tool_node"}
    if any_sensitive_succeeded:
        extra["pending_plan"] = None  # 业务成功，消费完毕
    elif pending_plan_was_updated:
        extra["pending_plan"] = new_pending_plan  # 持久化到 checkpoint

    return {
        "messages": tool_messages,
        **extra,
    }
```

### 6.4 `backend/app/ai/orchestrator/receipt_entry.py`

完全相同的模式：

- 推荐：`_SENSITIVE_TOOLS = {"create_payment", "create_expense", "update_payment"}`
  - 理由：`update_payment` 将 pending→paid 是状态变更，不可逆，且额度大
  - 如果确认负担太大，可以先不加 `update_payment`，后续按需加
- `analyze_receipt_node` 入口重置 `should_end` / `iteration_count`
- `execute_tool_node` 加同样三段硬约束 + set_pending_plan 内联 + pending_plan 持久化 + 业务成功判定

### 6.5 `backend/app/ai/prompts.py`

**A. 重写 CONTRACT_ENTRY_PROMPT 和 RECEIPT_ENTRY_PROMPT**（三阶段工作流）

```python
CONTRACT_ENTRY_PROMPT = """你是合同录入助手。严格遵守三阶段工作流，禁止跳过任何阶段。

【阶段 1：分析】
  合同文件已由 VL 分析完成，[文件分析结果] 在上下文中。
  你必须先看分析数据，理解客户、金额、币种、业务类型。
  可先用 search_customers / get_customer_contracts 等查询工具验证信息。

【阶段 2：展示 + 等待确认】
  - 调 set_pending_plan(summary, actions=[...], user_confirmed=False)
    - summary: 1-2 句话总结关键信息（客户、金额、业务类型）
    - actions: 计划要执行的所有 create 类工具名
      （如需新建客户则含 create_customer，必含 create_contract）
  - 阶段 2 严禁调用任何 create_* 工具
  - 在向用户展示的文字里明确问"是否确认创建？"

【阶段 3：执行（仅当用户确认后）】
  用户回复后，你必须用语义理解（不是关键词匹配）判断意图：
    - 用户是否表达了"同意继续创建"？
    - 还是"先等等" / "修改" / "拒绝"？

  若同意：
    1. 先调 set_pending_plan(user_confirmed=True)，actions 不变
    2. 同一轮继续调 actions 里的 create_* 工具
  若拒绝/犹豫/修改：
    1. 调 set_pending_plan(user_confirmed=False)，更新 actions/summary
    2. 不调 create_*
    3. 文字回复"好的，等您确认后继续"

【铁律】
  - create_customer / create_contract 前必须有 user_confirmed=True 的 set_pending_plan
  - create_* 工具名必须在 plan.actions 里
  - 违反任一条，工具会被拒绝执行

【展示风格】
  - 简洁自然的中文，1-3 句话
  - 不确定项标 ⚠️
  - 每次回复控制在 3-5 句
  - 不要用"好的""收到"等无意义词结尾
"""
```

`RECEIPT_ENTRY_PROMPT` 同样改写，actions 改为 `create_payment` / `create_expense`。

**B. 修改 build_system_prompt 中的确认规则**

现有 `build_system_prompt` 里的"确认与执行规则（最高优先级）"是为旧 interrupt 方案写的：

> 用户确认（"好的""确认""OK"...）= 立即调用工具执行上一轮提出的操作（让系统弹出确认面板）

这段必须改，否则 LLM 看到后会直接调 create_*，绕开 set_pending_plan。

**修改为**：

> 用户确认后，先调 set_pending_plan(user_confirmed=True) 更新计划状态，再在同一轮调 create_* 工具执行。严禁在用户确认后直接调 create_* 跳过 set_pending_plan。

**C. 删除或注释掉旧 prompt 中违反"工具铁律"的部分**

旧 prompt 里的"让系统弹出确认面板"是行为指令，违反 CLAUDE.md 的"工具只返回事实 JSON，不嵌入行为指令"。

### 6.6 `backend/app/api/v1/agent.py`

在 `initial_state` 中增加重置字段：

```python
initial_state = {
    "messages": [HumanMessage(...)],
    "user_id": current_user.id,
    "user_role": current_user.role,
    "session_id": session_id,
    "executor_mode": agent._mode,
    "session_context": agent._session_context or {},
    "_finalized": False,
    "should_end": False,        # 每轮新请求重置
    "iteration_count": 0,        # 重置迭代计数
}
```

这是 Defense in depth——虽然 analyze 节点也会重置，但 initial_state 也重置更保险。

### 6.7 旧 interrupt 机制清理（独立 commit）

**原则**：全量删除，单独立 commit，方便回滚。

涉及删除/修改的代码：

| 文件 | 删除内容 | 估计行数 |
|---|---|---|
| `agent.py` | interrupt_id 校验逻辑（L147-L267） | ~120 行 |
| `sse_adapter.py` | interrupt 检测 + poll-stall 兜底机制 | ~100 行 |
| `contract_entry.py` | `from langgraph.types import interrupt` + interrupt 安全门代码 | ~30 行 |
| `receipt_entry.py` | 同上 | ~30 行 |
| `state.py` | `interrupt_info: Optional[dict]` + `approved_tool_ids` 字段 | ~3 行 |
| `graph.py` | `interrupt_info` 相关处理 | ~5 行 |
| 前端 `ContractChatModal` | interrupt 确认 UI 面板 | 待估 |
| 前端 `ReceiptConfirmPanel` | 整个组件 | 待估 |

清理后 `sse_adapter.py` 大幅简化，只剩 thinking/text/done/error 四种事件。

## 七、风险与缓解

| 风险 | 缓解 |
|---|---|
| LLM 死循环（一直调 set_pending_plan 不调 create） | iteration_count >= AGENT_MAX_ITERATIONS=8 现有机制兜底 |
| LLM 调 set_pending_plan(user_confirmed=True) 但用户实际没确认 | prompt 明确说"用语义理解判断用户最新回复"；LLM 出错时至少人没绕过代码层 |
| 刷新页面导致 pending_plan 丢失 | state 走 LangGraph checkpoint，下次进会话还能继续 |
| 多轮对话 should_end 残留 | analyze 入口节点 + initial_state 双重重置 |
| pending_plan 残留导致误用 | execute_tool_node 中敏感工具业务成功后清理 |
| **pending_plan 局部 mutation 不持久化** | **通过 return dict 返回，不直接改 state** |
| LLM 第一轮就调 create_* | 代码硬约束拒绝，LLM 看到错误消息后自我纠正 |
| 极端：LLM 把 user_confirmed=True 当默认值 | prompt 明确说"首次声明时 user_confirmed=False"；代码层也校验 |
| **旧 prompt 与新流程冲突** | **重写 build_system_prompt 的确认规则** |
| **业务失败时 plan 被误清** | **解析 result 的 success 字段，只有业务成功才清 plan** |

## 八、与之前方案的对比

| 维度 | 旧 interrupt 方案 | 旧直接执行方案 | 本方案 |
|---|---|---|---|
| 确认机制 | interrupt() + 前端弹窗 | 无确认 | 聊天内文字确认 + 代码硬约束 |
| 链路长度 | 5+ 层 | 1 层 | 2 层 |
| LLM 跳过确认风险 | 不可能 | 100% | 不可能 |
| 调试难度 | 高 | 低 | 低 |
| 前端改动 | 需要 | 不需要 | 不需要 |
| 用户交互 | 弹窗 + 按钮 | 无 | 打字"确认" |
| LangGraph 版本敏感 | 高 | 无 | 低 |

## 九、落地步骤

1. 🔴 **独立 commit：旧 interrupt 机制清理**（待执行）
   - 删除 agent.py 的 interrupt_id 校验
   - 简化 sse_adapter.py（只保留 4 种事件）
   - 删除前端确认面板
   - 删除 state.py 中 interrupt_info / approved_tool_ids
   - commit message: `refactor: 移除旧 interrupt 确认机制（为 Plan-Driven 方案让路）`

2. ✅ 改 `state.py`：加 `pending_plan: Optional[dict] = None`（含 plan_id 字段）

3. ✅ 改 `tools.py`：TOOL_DEFINITIONS 加 set_pending_plan

4. ✅ 改 `agent.py`：initial_state 加 `should_end: False` + `iteration_count: 0` + `attachments: []`

5. ✅ 改 `prompts.py`：
   - 重写 `build_system_prompt` 的确认规则
   - 重写 `CONTRACT_ENTRY_PROMPT`（三阶段工作流）
   - 重写 `RECEIPT_ENTRY_PROMPT`（三阶段工作流）

6. ✅ 改 `contract_entry.py`：
   - analyze_file_node 多轮续接 + 入口重置 + 新文件清旧 plan
   - execute_tool_node 三段硬约束 + set_pending_plan 内联 + pending_plan_was_updated 标志位
   - pending_plan = new_pending_plan 同步（修复同轮先 set 再 create 被误拒 bug）
   - any_sensitive_executed + any_sensitive_failed 双标志（部分成功不清 plan）
   - plan_id 审计追踪 + 结构化日志

7. ✅ 改 `receipt_entry.py`：同上

8. ✅ 清理：
   - 删除 `from langgraph.types import interrupt` 死导入
   - state.py interrupt_info 标记 DEPRECATED

9. 🧪 测试场景：
   - ✅ 正常：上传 → 展示 → 用户"确认" → 创建成功
   - ✅ LLM 违规：跳过 set_pending_plan → 工具拒绝 → LLM 自我纠正
   - ✅ 用户拒绝："先等等" → 不创建
   - ✅ LLM 调未声明的 create：被拒绝
   - ✅ 多轮续接：用户第二轮"确认" → analyze 节点跳过分析 → Agent 处理
   - ✅ should_end 残留：第二轮对话能正常进入 Agent 循环
   - ✅ pending_plan 清理：全部敏感工具业务成功后清空，部分失败保留
   - ✅ pending_plan 跨 checkpoint 持久化
   - ✅ 工具返回业务错误时 plan 不被清
   - ✅ 同轮先 set_pending_plan(True) 再 create_* 能正确放行
   - ✅ 新文件上传清除旧 plan

10. 前端零改动（除 commit 1 中删除旧确认面板）

## 九、实施结果（2026-06-08）

已于 `refactor: 彻底删除interrupt确认UI机制` commit 完成清理：

- 删除了所有 interrupt/resume 相关代码（前后端共 ~1100 行）
- SSE 适配器简化为直接消费 astream_events，无后台任务/checkpoint 轮询
- 确认机制改为纯聊天交互：用户自然语言确认 → LLM 调 set_pending_plan(user_confirmed=true) → 代码层硬约束放行
- 不再有 interrupt 事件类型、InterruptInfo 类型、ReceiptConfirmPanel 组件

## 十、未来可扩展

- **Plan 模板化**：高频场景做成模板
- **MCP 风险注解**：工具自描述风险等级
- **粘性决策**：同一轮确认后自动放行
- **Plan 审计日志**：单独建表可查询
- **可配置确认阈值**：从代码常量提升为配置项
