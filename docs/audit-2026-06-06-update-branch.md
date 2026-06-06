# Update 分支严格审核报告

> **审核日期**：2026-06-06
> **审核范围**：`update` 分支 3 个 commit（混合币种修复 + LangGraph Phase 1.2-1.4 + 前端 interrupt UI）
> **对比基线**：`master` 分支
> **变更规模**：30 文件，+5670 / -1461 行

---

## 整体评价：★★★☆☆（可上线，但需处理 8 个问题后交付测试）

核心架构正确，混合币种修复无风险，LangGraph 编排层骨架完整。但存在若干代码质量和集成隐患，直接上线会产生运行时错误。

---

## 一、混合币种修复（commit 1）—— 审核结论：✅ 通过

### 1.1 payment_service.py

| 检查项 | 结论 |
|--------|------|
| CNY 合同 `amount_in_cny = amount` | ✅ 正确，1:1 映射 |
| `exchange_rate = Decimal('1.0')` | ✅ 语义正确（之前为 None，不利于调试） |
| `_add_to_contract_paid` 去除 `if amount_in_cny is not None` | ✅ 正确，CNY 合同从此写 `_in_cny` |
| `_add_to_contract_expense` 同上 | ✅ 正确 |
| `update_payment` 兼容 `amount_in_cny = paid_amount_in_cny or paid_amount` | ✅ 正确，旧 CNY 数据 `paid_amount_in_cny` 为 0，兜底到 `paid_amount` |
| `delete_payment` 防御式 `is not None` 检查 | ✅ 正确，防止旧 CNY 数据 `None < Decimal` 崩溃 |

**无问题。**

### 1.2 contract_service.py

| 检查项 | 结论 |
|--------|------|
| 创建合同：CNY 合同写 `total_amount_in_cny = total_amount` | ✅ 正确 |
| AI 解析后重算：同上 | ✅ 正确 |
| `db.commit()` / `db.refresh()` 包含在分支内 | ✅ 正确 |

**无问题。**

### 1.3 stats_service.py

| 检查项 | 结论 |
|--------|------|
| `_build_top_customers`: `NULLIF(paid_amount_in_cny, 0)` 兜底 `paid_amount` | ✅ 正确，旧数据兼容 |
| `_build_business_type_distribution`: 同上 | ✅ 正确 |
| `_build_kpi`: 未改，按币种 GROUP BY | ✅ 保持不变，设计正确 |

**无问题。**

### 1.4 tools.py（AI Agent 汇总修复）

| 检查项 | 结论 |
|--------|------|
| `get_payment_summary`: `paid_amount` → `paid_amount_in_cny` | ✅ 正确，解决 Agent 混币种汇报 |
| `total_paid_unit: "CNY"` 标注 | ✅ 帮助 LLM 理解单位 |
| `group_by=contract` 新增 `currency` 字段 | ✅ 帮助 LLM 区分合同币种 |
| `_payment_to_dict_lite` 新增 `paid_amount_in_cny` | ✅ LLM 可自行引用 CNY 等值 |

**无问题。**

---

## 二、LangGraph 后端编排层（commit 2）—— 审核结论：⚠️ 有 5 个问题

### 2.1 orchestrator/state.py

✅ **通过。** State 定义与文档一致，`total=False` 正确，`add_messages` 归约器正确。

### 2.2 orchestrator/contract_entry.py

| # | 问题 | 严重度 | 位置 |
|---|------|--------|------|
| **P1** | **未使用的 import** `os` | 🟡 低 | 第 23 行 |
| **P2** | **未使用的 import** `get_config` | 🟡 低 | 第 25 行 |
| **P3** | **`_extract_contract_data` 解析逻辑不安全** | 🔴 高 | `show_preview_node` |

**P3 详细分析**：

```python
def _extract_contract_data(self, file_context: str) -> dict:
    # 先查 Redis 缓存
    cached = self.executor._get_cached_analysis(file_id, "contract")
```

**问题**：`_get_cached_analysis` 是 `executor` 的私有方法，且 file_id 从 `attachments[0]` 解析，但 `attachments` 是 state 中的 `list[dict]`，key 是 `file_id` 而非 `fileId`。需要在 `show_preview_node` 中显式传入 file_id。

**当前代码路径**：
```
show_preview_node
  → _extract_contract_data(file_context)
    → self._cached_attachments[0]["file_id"]  # 从 analyze 保存的附件拿
```

如果 `_cached_attachments` 为空（analyze_file_node 出错），此处 `file_id` 解析会失败 → `cached` 为 None → 降级到 `state.get("contract_data", {})` 兜底。**不会崩溃，但 Redis 缓存可能未被读取。** 降为 🟡 中。

| **P4** | **`auto_create_payments_node` 是空壳节点** | 🟡 中 | 节点 7 |

这个节点只是读取 `state["auto_payments"]` 并原样返回。实际的付款创建在 `create_contract_node` 调 `tools.py:create_contract()` 时已完成。**功能上没问题，但多余了一次节点跳转**，且如果 create_contract 中间因为某种原因没建 payments，这个节点不会重试。

### 2.3 orchestrator/graph.py

| # | 问题 | 严重度 | 位置 |
|---|------|--------|------|
| **P5** | **`general_chat_subgraph` 立即 END** | 🔴 高 | `general_chat_start_node` |

**详细分析**：

```python
async def general_chat_start_node(state: GeneralChatState) -> dict:
    return {"should_end": True, "current_node": "general_chat_start_node"}
```

当用户发纯文本（无附件）时，`intake_node` 返回 `intent=general` → `route_by_intent` → `general_chat_subgraph` → 立即 `should_end=True` → `finalize_node` → END。

**结果**：用户发"你好"，Assistant 没有任何回复文本，只收到一个 `done` 事件。**聊天完全不可用。**

**修复**：通用对话子图在 Phase 1 需要把消息路由回旧的 `agent.chat()`。当前实现的正确做法是：

- 方案 A：在 `route_by_intent` 中，`general` intent 时直接不走子图，由 endpoint 兜底走旧 ReAct
- 方案 B：`general_chat_start_node` 改为调用旧 `agent.chat()` 并把结果写入 messages

**推荐方案 A**，与 design doc 的 Phase 1「通用对话走旧 ReAct」一致。

实际上看 endpoint 代码，`use_langgraph` 的判断是：

```python
if request.attachments and any(a.file_type in ("pdf", "word", "excel") for a in request.attachments):
    use_langgraph = True
```

所以**纯文本消息不会走进 LangGraph**，P5 实际上是**死代码不会被触发**。降为 🟡 低。但如果未来扩展（如图片附件触发 LangGraph），这个占位符就会暴露问题。

### 2.4 orchestrator/sse_adapter.py

✅ **通过。** `astream_events(v2)` → SSE 映射表正确，`interrupt` 事件和 `done(interrupted=true)` 事件格式正确。

### 2.5 schemas/agent.py

✅ **通过。** `resume`/`interrupt_id` 字段定义正确，`@model_validator` 互斥校验正确。

### 2.6 api/v1/agent.py

| # | 问题 | 严重度 | 位置 |
|---|------|--------|------|
| **P6** | **`agent.executor.mode` 可能不存在** | 🟡 中 | LangGraph 路径 |

```python
agent.executor.mode = agent._mode
```

`ContractAgent.executor` 是 `ToolExecutor` 实例，确实有 `mode` 属性（`tools.py` 中定义）。✅ 实际上没问题，但属性赋值和属性存在性的耦合较隐性。

| **P7** | **resume 时没有对 `checkpointer.aget()` 做 interrupt_id 验证** | 🟡 中 | 同上 |

文档 §6.6.3 设计了 interrupt_id 验证逻辑：

```python
state_snapshot = await checkpointer.aget(config)
if request.interrupt_id not in [i.id for i in state_snapshot.interrupts]:
    raise HTTPException(403, "interrupt_id 不匹配")
```

**当前实现跳过了这个验证**。恶意用户可以伪造 `interrupt_id`。降级为 🟡 中，因为业务场景下用户无动机伪造。

| **P8** | **LangGraph 路径中 `agent._load_session_meta(request.session_id)` 在 session_id 为 None 时的行为** | 🟡 低 | 同上 |

如果 `request.session_id` 为 None（新会话 + 附件），`_load_session_meta(None)` 的行为是创建一个新 session_id。这个行为已由 `agent.py:88-89` 处理，LangGraph 路径未创建会话，但 `initial_state["session_id"]` 用了 `uuid.uuid4()` 兜底。**行为一致，无问题。**

（重新评估：P8 不是问题）

---

## 三、前端 interrupt UI（commit 3）—— 审核结论：✅ 通过，有 1 个低优先级问题

### 3.1 types/agent.ts

✅ **通过。**

### 3.2 services/agent.ts

✅ **通过。** `_chatRequest` 抽取复用正确。

### 3.3 store/useAgentStore.ts

✅ **通过。** `resumeInterrupt` 方法复用 SSE 解析逻辑，但**有代码重复**——`sendMessage` 和 `resumeInterrupt` 的 SSE 解析几乎一样。建议提取公共解析函数。不影响功能。

### 3.4 pages/AgentChat.tsx

| # | 问题 | 严重度 | 位置 |
|---|------|--------|------|
| **P9** | 中断期间 `stopGeneration` 按钮仍可点击 | 🟡 低 | 按钮区域 |

```tsx
<Button danger size="large" icon={<StopOutlined />}
  onClick={stopGeneration}
  disabled={!!interruptInfo}
>
```

按钮已 `disabled`，但使用了 `stopGeneration` 的 `onClick`。实际上由于 `disabled` 生效，不会触发。**无实际问题，但语义上应该换成一个不同的事件处理。**

---

## 四、问题汇总

| # | 严重度 | 文件 | 问题 | 修复建议 |
|---|--------|------|------|----------|
| P1 | 🟡 低 | `contract_entry.py` | 未使用的 import `os` | 删除 |
| P2 | 🟡 低 | `contract_entry.py` | 未使用的 import `get_config` | 删除 |
| P3 | 🟡 中 | `contract_entry.py` | `_extract_contract_data` 缓存读取依赖实例变量，耦合脆弱 | 改为显式传 file_id |
| P4 | 🟡 低 | `contract_entry.py` | `auto_create_payments_node` 空壳节点 | 可接受（幂等兜底），加注释说明 |
| P5 | 🟡 低 | `graph.py` | 通用对话占位符返回空 | 当前不会触发（纯文本不走 LangGraph），但需加注释警告 |
| P7 | 🟡 中 | `agent.py` endpoint | 缺少 `interrupt_id` 后端验证 | 在 resume 路径加 `checkpointer.aget()` 校验 |

---

## 五、未覆盖场景

| 场景 | 状态 |
|------|------|
| 合同图片附件（JPEG/PNG） | ❌ 未覆盖。`use_langgraph` 只检查 pdf/word/excel，图片不在 LangGraph 路径 |
| 多附件 | ❌ 未覆盖。只处理 `attachments[0]` |
| 凭证录入 | ❌ Phase 2 范畴 |
| 通用对话 | ❌ 走旧 ReAct（Phase 2 替换） |
| PostgresSaver 不可用 | ❌ 捕获了 RuntimeError 设 cp=None，但 checkpointer 为 None 时子图正确编译（无持久化） |

---

## 六、最终结论

**混合币种修复（commit 1）可以直接合并到 master，零风险。**

**LangGraph 编排层（commit 2+3）建议修复 P1/P2/P3/P7 后交付测试。** 当前代码在"用户上传 PDF/Word/Excel 并走合同录入"的 Happy Path 上可用，但防御性不足。

**不建议直接上线到生产环境**，优先完成：
1. 修复 P1-P7
2. 开发环境实际运行验证（启动 FastAPI，上传一个测试合同，走完整流程）
3. 确认前端 interrupt 面板正确渲染
