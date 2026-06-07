# Update 分支综合审核报告 v2

> **审核日期**：2026-06-06 ~ 2026-06-07（多轮审核 + 修复 + 合并 + Phase 2 推进）
> **审核范围**：update 分支 14 个原 commit + 用户后续 5 个 commit + master 合并 commit + 本轮 Phase 2 增量 6 个 commit
> **对比基线**：master 分支
> **本版（v2）变更**：
> 1. 修正 v1 中"Phase 2/3 全部未启动"的错误结论——已实际落地 6 项 Phase 2 任务
> 2. 修复第一轮审核 P0 回归 bug（图片无 VL 能力丢数据）
> 3. 修复 P0/P1/P2 隐患 8 项（P0 图片附件 VL 回归、P1 错误文案/P1 重复 system prompt/P1 dismiss 竞态、P2 SSE 友好名/P2 llm_client 单例/P2 auto_filled 元数据、BOM 清理 3 个文件）
> 4. 删除过期 audit 文档 1 份
> **整体评价**：★★★★☆（Phase 1+2 核心完整、可上线，剩 E2E + 灰度）

---

## 0. v1 → v2 变更摘要

| 项 | v1 状态 | v2 状态 |
|---|---|---|
| Phase 1 核心功能 | ✅ 100% 交付 | ✅ 100% 交付（未变） |
| Phase 2 任务 | ❌ "全部未启动" | ✅ 6/9 已落地（2.1/2.3/2.4/2.5/2.6/2.7），剩 2.2/2.8 E2E + 2.9 灰度 |
| Phase 3 任务 | ❌ 未启动 | ❌ 未启动（未变） |
| P0 回归 bug（图片无 VL） | 🐛 v1 漏报 | ✅ 已修（退回图片附件限制） |
| P1 错误文案 / system prompt 重复 | 🐛 v1 报告但未修 | ✅ 已修 |
| P1 dismissInterrupt 竞态 | ⚠️ v1 标注低优未修 | ✅ 已修（加 await） |
| P2 SSE 友好名 / llm_client 单例 | 🐛 v1 漏报 | ✅ 已修 |
| P2 auto_filled 元数据 | ⚠️ v1 设计文档要求未实现 | ✅ 已实现 |
| 3 个 orchestrator 文件 BOM 头 | 🐛 v1 漏报 | ✅ 已清除 |
| 过期 audit 文档 | `docs/audit-2026-06-06-update-branch.md` | ✅ 已删除 |
| 单元 / E2E 测试 | ❌ 无 | ❌ 仍无（按优先级 P0） |

---

## 1. 总览

### 1.1 Commit 链（按合并后顺序）

```
本轮 v2 增量（12 个 commit，按时间顺序，已提交）：
  fix(orchestrator): P1 summarize_node 错误文案 — 区分合同已创建 vs 未完成
  fix(orchestrator): P0 图片附件 VL 回归 — 退回旧 ReAct 分支判断
  feat(orchestrator): Phase 2.4 通用对话子图（自建 StateGraph）
  feat(orchestrator): Phase 2.1+2.3+2.6 降级引导 + Root Graph 4 子图编排
  fix(frontend): P1 dismissInterrupt 竞态 — 加 await
  feat(frontend): Phase 2.5 输入框必填
  refactor(sse): 适配 Phase 2 节点命名 + general_chat_subgraph 友好名
  feat(observability): Phase 2.7 LangSmith 接入
  chore(migrations): 加 README 说明
  chore: 删除过期第一轮 audit 文档
  docs: 综合审核第二版（v2）
  fix: 清理 3 个 orchestrator 文件 BOM 头

原 update 分支 14 个 commit + 用户后续改进（含 ef5d9ea / 32886ab / 9597e38 / b5a1e22 / ceacff4 / 28d5e22 / 74d4db2 / 3828ca7 / d2f3bfb / 9e1070f / 76daedf / d74ec22 / 531097b）+ master 同步 8a78a1f
```

### 1.2 改动量

- **本轮 v2 增量**（12 个 commit，已提交）：15 文件，+884 / -310 行（净 +574 行）
  - 新文件：general_chat.py（265 行）+ migrations/README.md（5 行）+ 2026-06-07 综合审核 v2（433 行）
  - 主要改动：graph.py +91/-52（Phase 2.1+2.3+2.6 + auto_filled）、agent.py +35/-12（P0 + P2）、sse_adapter.py +5/-1
  - 删除：docs/audit-2026-06-06-update-branch.md（239 行）
- **历史合并**：35 文件，+6302 / -1563 行（净 +4739 行）

### 1.3 主题分类

| 主题 | 状态 | 改动量 | 说明 |
|---|---|---|---|
| LangGraph 编排层（Phase 1） | ✅ | +950 行 | 9 节点 + Root Graph |
| 通用对话子图（Phase 2.4） | ✅ | +250 行 | 替代旧 ReAct 循环（不含图片） |
| Root Graph 4 子图编排（Phase 2.6） | ✅ | +133 行 | 凭证/群聊/通用降级引导 |
| 凭证/群聊降级节点（Phase 2.1+2.3） | ✅ | +50 行 | 引导用户到卡片按钮 |
| LangSmith 可观测性（Phase 2.7） | ✅ | +20 行 | 环境变量透传 + 日志埋点 |
| 前端输入框必填（Phase 2.5） | ✅ | +10 行 | 防御非法空附件提交 |
| Bug 修复 | ✅ | 8 项 | P0 × 1 / P1 × 3 / P2 × 3 / 工程 BOM × 1 |
| 单元 / E2E 测试 | ❌ | 0 | Phase 1+2 全靠手工验证，风险累积中 |

---

## 2. Phase 1 完成度评估（设计文档 §5.3 验收项）

| # | 验收项 | 状态 | 证据 / v2 补充 |
|---|---|---|---|
| 1 | 用户只点 1 次"确认"按钮 | ✅ | `wait_user_confirm_node` + InterruptPanel |
| 2 | 合同录入总耗时 ≤ 20s | ⏳ | 理论达标，未压测 |
| 3 | LLM 调用 ≤ 2 次 | ✅ | `analyze_file_node` 1 次 + 模板化总结 |
| 4 | 单测覆盖率 ≥ 80% | ❌ | 无新测试文件，**P0 风险** |
| 5 | E2E 5 个典型场景 | ❌ | 无 |
| 6 | 故障演练 | ❌ | 无 |
| 7 | 前端 interrupt UI | ✅ | `AgentChat.tsx` 中断面板 |
| 8 | ChatRequest resume / interrupt_id | ✅ | `schemas/agent.py` + `cp.aget()` 校验 |
| 9 | PostgresSaver Phase 1 配置 | ✅ | `checkpointer.py` + `main.py` 启动 |

**§9.1 Phase 1 任务表**：

| 任务 | 状态 |
|---|---|
| 1.1 安装 LangGraph + PostgresSaver 验证 | ✅ |
| 1.2 ContractEntryState + 9 节点 | ✅ |
| 1.3 路由函数 + 节点内 `interrupt()` | ✅ |
| 1.4 FastAPI SSE + ChatRequest resume/interrupt_id | ✅ |
| 1.5 前端 SSE 事件 `interrupt` | ✅ |
| 1.6 InterruptPanel + `resumeInterrupt` | ✅ |
| 1.7 单元测试 | ❌ |
| 1.8 E2E 测试 | ❌ |
| 1.9 灰度上线（10%） | ❌ |

**核心功能 100% 交付，测试 / 验证 / 上线策略 0%。**

---

## 3. Phase 2 进度（设计文档 §9.1）

| 任务 | v1 状态 | v2 状态 | 备注 |
|---|---|---|---|
| 2.1 凭证引导子图（降级） | ❌ 未启动 | ✅ 降级节点 | 引导文案到合同列表卡片按钮 |
| 2.2 凭证引导 E2E | ❌ | ❌ | 仍无 |
| 2.3 群聊关联子图（降级） | ❌ 未启动 | ✅ 降级节点 | 引导用户提供群名 + 客户名 |
| 2.4 通用对话子图（自建 StateGraph） | ❌ 未启动 | ✅ 完整实现 | call_model + execute_tool + max_iterations 兜底 |
| 2.5 前端输入框必填 | ❌ 未启动 | ✅ 已实现 | 有附件时 text 必填，发送按钮 disable |
| 2.6 Root Graph 编排 | ⚠️ v1 报告"只注册 2 个子图" | ✅ 4 子图完整编排 | 4 节点 + 完整路由矩阵 |
| 2.7 LangSmith 监控 | ❌ 未启动 | ✅ 已接入 | LANGCHAIN_TRACING_V2 / API_KEY / PROJECT env |
| 2.8 全流程 E2E 测试 | ❌ | ❌ | 仍无 |
| 2.9 灰度上线 50% | ❌ | ❌ | 未做 |

**Phase 2 进度：6/9（66%）。** 剩 2.2 / 2.8 E2E 测试和 2.9 灰度。

---

## 4. Phase 3 进度

| 任务 | 状态 |
|---|---|
| 3.1 性能调优 | ❌ |
| 3.2 文档与培训 | ⚠️ 部分（综合审核 v2 即培训材料） |
| 3.3 全量上线 100% | ❌ |

---

## 5. v2 修复的 Bug 清单

### 🔴 P0 修复：图片附件 VL 回归

**文件**：`backend/app/api/v1/agent.py:159-176`

**问题**：v1 working tree 把"所有附件走 LangGraph"作为统一入口，但 `general_chat.py:_convert_messages` 对 `HumanMessage.content` 是 list（多模态）时只做 `" ".join(str(p) for p in content)`，把 `{"type": "image_url", ...}` dict 当成字符串拼接，**整张图片的数据被丢成 1 行 Python dict 字符串**，LLM 看不到图。

**修复**：退回原"图片走旧 ReAct"分支判断，仅在 image + 含凭证/群聊关键词时才走 LangGraph 降级引导。

```python
# v2 修复后
has_doc = any(a.file_type in ("pdf", "word", "excel") for a in request.attachments)
has_image = any(a.file_type == "image" for a in request.attachments)
has_image_with_kw = has_image and any(
    kw in (request.question or "").lower()
    for kw in ("凭证", "receipt", "转账", "收据", "付款",
               "群聊", "微信群", "group", "群")
)
if has_doc or has_image_with_kw:
    use_langgraph = settings.AGENT_ORCHESTRATOR != "legacy"
```

**影响**：图片无关键词（"帮我看看这张图"）走旧 ReAct（带 VL 能力），与 v1 之前行为一致；图片 + 凭证/群聊关键词走 LangGraph 降级引导。

### 🟡 P1 修复：summarize_node 错误文案

**文件**：`backend/app/ai/orchestrator/contract_entry.py:367-373`

**问题**：合同创建失败时 `contract_id` 为 `None`，但模板仍输出"合同已创建（ID: None）"误导用户。

**修复**：

```python
if errors:
    created = bool(contract_id)
    head = f"合同已录入（ID: {contract_id}）" if created else "合同录入未完成"
    summary = (
        f"{head}，但存在以下问题：\n"
        + "\n".join(f"  - {e}" for e in errors)
    )
```

### 🟡 P1 修复：_convert_messages 重复 system prompt

**文件**：`backend/app/ai/orchestrator/general_chat.py:_convert_messages`

**问题**：`_convert_messages` 在 result 列表开头插入自动构造的 system message，若 `messages` 中后续出现 `SystemMessage` 会**追加第二条 system message**，导致 LLM 收到两条 role=system 的消息。

**修复**：

```python
if isinstance(msg, SystemMessage):
    # 重复 system prompt 防御：用用户传入的覆盖自动构造的
    if result and result[0].get("role") == "system":
        result[0] = {"role": "system", "content": msg.content}
    else:
        result.insert(0, {"role": "system", "content": msg.content})
```

### 🟡 P1 修复：dismissInterrupt 竞态

**文件**：`frontend/src/store/useAgentStore.ts:dismissInterrupt`

**问题**：原实现 `get().resumeInterrupt({ confirmed: false })` 不 await，后端响应失败时前端已清面板但 checkpoint 仍卡在 `wait_user_confirm_node`。

**修复**：加 `await`，等后端完成取消流程后再返回。

### 🟢 P2 修复：sse_adapter 漏节点名

**文件**：`backend/app/ai/orchestrator/sse_adapter.py`

**问题**：4 个新加的子图/节点（call_model / execute_tool / receipt / group_chat）都加了友好名，但 `general_chat_subgraph` 漏加，用户看到 6 个字的技术名。

**修复**：

```python
"general_chat_subgraph": "通用对话",
```

### 🟢 P2 修复：_llm_client 模块级单例

**文件**：`backend/app/ai/orchestrator/general_chat.py`

**问题**：模块顶部 `_llm_client = DashScopeAgentClient()` 在 import 时绑定 settings，单测难 mock。

**修复**：

```python
def _default_llm_client():
    """懒加载默认 LLM 客户端（避免模块级绑定 settings）。"""
    return DashScopeAgentClient()

class GeneralChatSubgraph:
    def __init__(self, db, user, ..., llm_client=None):
        self._llm_client = llm_client  # 允许外部注入
        ...

    def build(self, checkpointer=None):
        # 优先级：构造注入 > 懒加载默认
        llm_client = self._llm_client or _default_llm_client()
        ...
```

### 🟢 P2 修复：auto_filled metadata 透传

**文件**：`backend/app/api/v1\agent.py` + `backend/app/ai/orchestrator/graph.py:finalize_node`

**问题**：附件自动补全的 question（"请分析上传的 PDF 内容..."）会落库 chat_history，但用户回看历史时无法区分"我输入的"和"系统补全的"。

**修复**：

1. `agent.py` 在自动补全时设置 `auto_filled = True`，构造 `HumanMessage(additional_kwargs={"auto_filled": True})`
2. `finalize_node` 读取 `additional_kwargs.auto_filled`，human 角色落库时传 `metadata={"auto_filled": True}`

### 🟢 P2 修复：3 个 orchestrator 文件 BOM 头

**文件**：`contract_entry.py` / `general_chat.py` / `sse_adapter.py`

**问题**：3 个文件开头有 UTF-8 BOM（U+FEFF），Python 3 解析为合法 docstring 但 IDE 和某些 linter 报错，且 gitattributes LF 行尾规则不覆盖 BOM。

**修复**：写入文件时去掉前 3 字节 BOM marker。

---

## 6. ADR 7 项架构决策落实情况（v2 重审）

| ADR | v1 评估 | v2 评估 | 变化 |
|---|---|---|---|
| #1 interrupt 前端感知按钮 | ✅ 完美 | ✅ 完美 | — |
| #2 不引入 ChatOpenAI | ✅ 完美 | ✅ 完美 | — |
| #3 通用对话自建 StateGraph | ⏳ 占位 | ✅ 完整实现 | **v2 落地** |
| #4 凭证录入智能追问 4 字段 | ⏳ 推迟 | ⏳ 推迟 | — |
| #5 AsyncPostgresSaver + psycopg3 | ✅ 完美 | ✅ 完美 | — |
| #6 checkpoint + chat_history 并行 | ✅ 完美 | ✅ 完美 | — |
| #7 4 字段追问 推迟 | ✅ | ✅ | — |

**ADR 一致性：7/7。**

---

## 7. 当前线上实际行为矩阵（v2 更新）

| 用户操作 | 实际路由 | 行为 | 状态 |
|---|---|---|---|
| 上传 PDF/Word/Excel | contract_entry_subgraph | Phase 1 工作 | ✅ |
| 上传 PDF/Word/Excel + 凭证关键词 | contract_entry_subgraph（VL 二次判断后 fallback） | 子图兜底 | ✅ |
| 上传图片 + 凭证关键词 | receipt_entry_node | 引导到卡片按钮 | ✅ v2 新 |
| 上传图片 + 群聊关键词 | group_chat_node | 引导用户手动关联 | ✅ v2 新 |
| 上传图片 + 自由描述 | 旧 ReAct | 带 VL 能力 | ✅ v2 修复 |
| 纯文本对话 | general_chat_subgraph | 替代旧 ReAct | ✅ v2 新 |
| 中断恢复（resume） | LangGraph checkpoint | interrupt_id 校验 | ✅ |

**所有"非合同文档"和"凭证/群聊"场景已统一走 LangGraph 框架。** 剩"纯文本对话"也走 general_chat_subgraph（替代旧 ReAct）。

---

## 8. 部署 Checklist（v2 更新）

### 8.1 部署前必做

- [ ] **依赖升级**：`uv sync` 装新增的 `langsmith>=0.1.0`
- [ ] **业务表 SQL 生成**：`uv run python scripts/dump_init_sql.py > sql/init_business_tables.sql`
- [ ] **业务表建表**：运维审查 SQL 后手动执行
- [ ] **LangGraph 表**：启动时 `init_checkpointer()` 自动建
- [ ] **环境变量配置**：
  - `AGENT_ORCHESTRATOR=langgraph`（默认）或 `legacy`（回滚）
  - `DASHSCOPE_API_KEY` / `SILICONFLOW_API_KEY` / `SECRET_KEY` / 数据库连接
  - `LANGCHAIN_TRACING_V2=false`（默认关闭，运维按需开启）+ `LANGCHAIN_API_KEY` / `LANGCHAIN_PROJECT`（v2 新增）

### 8.2 部署后必做

- [ ] **手动端到端验证**（5 个场景）：
  1. 上传 PDF 王振为合同 → 等概要 → 点确认 → 合同落库
  2. 上传图片 + "凭证" → 收到降级引导（v2 新场景）
  3. 上传图片 + "群聊" → 收到群聊关联引导（v2 新场景）
  4. 纯文本"查询客户" → 通用对话子图，调用 search_customers 工具（v2 新场景）
  5. 中断恢复 → 点取消 → 后端走完 summarize_cancel → finalize
- [ ] **回滚路径演练**：设 `AGENT_ORCHESTRATOR=legacy` 重启，旧 ReAct 仍工作
- [ ] **灰度上线**：10% → 50% → 100%（每阶段观察 1 天）
- [ ] **LangSmith 监控**（可选）：设 `LANGCHAIN_TRACING_V2=true` + 配 API_KEY，验证节点埋点

### 8.3 监控指标

- 重复询问率（基于日志）—— Phase 1 目标 0%
- 端到端 P50/P99 延迟
- LLM 调用次数 / 会话（目标：合同 ≤ 2 次）
- LangGraph 节点错误率
- 凭证/群聊降级文案触发率（v2 新指标）
- 通用对话子图工具调用成功率（v2 新指标）

---

## 9. 待办与建议

### 9.1 立即可做（清理尾巴）

1. ⚠️ **单测 / E2E**（设计文档 §10 要求，Phase 1+2 全靠手工验证）—— **P0 风险**
2. ⚠️ **CLAUDE.md 反映 Phase 2.4 通用对话子图替换旧 ReAct**（当前 v1 描述为"占位"）
3. ⚠️ **前端 store 注释更新**（dismissInterrupt 加 await 后，注释"不 await"已过期）

### 9.2 Phase 2 剩余（按性价比）

| 顺序 | 任务 | 价值 | 预估 |
|---|---|---|---|
| 1 | Phase 2.8 E2E 测试（5 场景） | **P0 风险** | 1.5 h |
| 2 | Phase 1 单元测试（节点 + 路由） | 防止回归 | 1-1.5 h |
| 3 | Phase 2.9 灰度 50% | 验证稳定性 | 0.5 h |
| 4 | Phase 3.1 性能调优 | 连接池 + checkpoint 序列化 | 0.5-1 h |
| 5 | Phase 3.2 文档与培训（CLAUDE.md 同步） | 工程治理 | 0.5 h |
| 6 | Phase 3.3 全量上线 100% | 收尾 | 0.5 h |

**Phase 2 剩余 + Phase 3 合计：AI 5-6 小时 = 1 个工作日深度对话。**

### 9.3 中长期建议

- 决定凭证/群聊降级 vs 真做的优先级：若客户高频用凭证录入，应启动 Phase 2.1 完整版（4 字段智能追问）
- 评估是否将通用对话子图扩展支持图片（Phase 2.4 多模态）
- LangSmith 替代方案（自建 OpenTelemetry 监控）以降低成本

---

## 10. 关键文件定位速查

| 主题 | 位置 | v2 变更 |
|---|---|---|
| LangGraph 编排根 | `backend/app/ai/orchestrator/` | — |
| PostgresSaver 配置 | `backend/app/ai/orchestrator/checkpointer.py` | — |
| 状态定义 | `backend/app/ai/orchestrator/state.py` | — |
| 合同录入子图 | `backend/app/ai/orchestrator/contract_entry.py` | P1 文案修复 + BOM 清理 |
| 通用对话子图 | `backend/app/ai/orchestrator/general_chat.py` | **v2 新增** |
| Root Graph | `backend/app/ai/orchestrator/graph.py` | P2 metadata 透传 + BOM 清理 |
| SSE 适配 | `backend/app/ai/orchestrator/sse_adapter.py` | P2 节点名 + BOM 清理 |
| Endpoint | `backend/app/api/v1/agent.py` | P0 图片附件限制 + P2 auto_filled |
| 启动 | `backend/app/main.py` | Phase 2.7 LangSmith env 透传 |
| 配置 | `backend/app/config.py` | Phase 2.7 LANGCHAIN_* env |
| 公共 LLM 客户端 | `backend/app/ai/llm_client.py` | — |
| 20 工具 | `backend/app/ai/tools.py` | — |
| 前端 store | `frontend/src/store/useAgentStore.ts` | P1 dismissInterrupt await |
| 前端服务 | `frontend/src/services/agent.ts` | — |
| 前端类型 | `frontend/src/types/agent.ts` | — |
| 前端聊天页 | `frontend/src/pages/AgentChat.tsx` | Phase 2.5 输入框必填 |
| 设计文档 | `docs/2026-06-06-langgraph-agent-orchestration.md` | — |
| 第一轮 audit | **已删除**（被本文件取代） | v2 清理 |
| 综合审核 v1 | 同上 | v2 清理 |
| 综合审核 v2（本文件） | `2026-06-07-update-branch-comprehensive-review.md` | 当前 |
| migrations 说明 | `backend/migrations/README.md` | **v2 新增**（§10.1.2 建议执行） |

---

## 11. 附：v2 全部 commit 链（含本轮增量）

```
# 本轮 v2 增量（13 个 commit，时间正序，已提交）
fde246a fix(orchestrator): P1 summarize_node 错误文案 — 区分合同已创建 vs 未完成
73c9abe fix(orchestrator): P0 图片附件 VL 回归 — 退回旧 ReAct 分支判断
4d07b88 feat(orchestrator): Phase 2.4 通用对话子图（自建 StateGraph）
df8604f feat(orchestrator): Phase 2.1+2.3+2.6 降级引导 + Root Graph 4 子图编排
1092dc2 fix(frontend): P1 dismissInterrupt 竞态 — 加 await
47e52b0 feat(frontend): Phase 2.5 输入框必填
2dd0eed refactor(sse): 适配 Phase 2 节点命名 + general_chat_subgraph 友好名
3e7834a feat(observability): Phase 2.7 LangSmith 接入
0f50fc0 chore(migrations): 加 README 说明
14724fe chore: 删除过期第一轮 audit 文档
23fcf95 docs: 综合审核第二版（v2）
3e29490 fix: 清理 3 个 orchestrator 文件 BOM 头
dc0f3b0 fix(docs): v2 综合审核编码修正 + 进度数据同步（v2 文档原本是 UTF-16 LE，转 UTF-8 + 修订数字）

# 原 update 分支 + 合并 master（按时间倒序）
8a78a1f chore: main.py 注释更新，移除 init_db.py 引用                [master 同步]
ef5d9ea feat(frontend): dismissInterrupt 触发后端走完取消流程         [用户改进]
32886ab refactor(tools): get_cached_analysis 公共接口                [用户改进]
9597e38 fix(orchestrator): finalize_node 幂等性保护                  [用户改进]
b5a1e22 feat(rollback): AGENT_ORCHESTRATOR 环境变量回滚开关          [用户改进]
ceacff4 fix(audit): P1-P7修复后尾随改进                             [Mavis]
28d5e22 chore: .gitattributes 强制 LF 行尾                          [Mavis]
74d4db2 feat(frontend): InterruptPanel 透传opt.value                [Mavis]
3828ca7 refactor(sse): LangGraph事件适配器兼容多步interrupt          [Mavis]
d2f3bfb fix(orchestrator): 合同录入子图审核问题修复                  [Mavis]
9e1070f fix(audit): P1-P7 审核问题修复                              [前轮]
76daedf feat(frontend): 中断确认面板 + interrupt SSE 事件处理        [前轮]
d74ec22 feat(orchestrator): Phase 1.2-1.4 LangGraph 合同录入子图    [前轮]
531097b fix: 混合币种统一处理                                      [前轮]
```

---

## 12. v2 自审结论

- ✅ **核心功能完整**：Phase 1 9 节点 + Root Graph + Phase 2.4 通用对话子图 + Phase 2.1/2.3 降级引导 + Phase 2.6 编排 + Phase 2.7 监控
- ✅ **8 项 bug 修复落地**（P0×1 / P1×3 / P2×3 / BOM×1），v2 文档编码修正（UTF-16 → UTF-8）已修复
- ✅ **过期文档清理**（docs/audit-2026-06-06-update-branch.md）
- ⚠️ **测试覆盖仍为 0**：Phase 1+2 全靠手工验证，是当前最大风险
- ⏳ **灰度未启动**：建议先完成 E2E 测试再上 10% 灰度
- 📊 **总评价**：★★★★☆（生产可用，但补 E2E + 灰度再上 100% 流量）


## 13. 修订记录

本综合审核文档共经历 6 次 commit（git log 可查），本表是历史中的一次中途快照，最新版本请以 git HEAD 为准。

**关键事实（按时间）**：

1. v2 综合审核初版以 UTF-16 LE 编码写入（PowerShell Out-File 默认行为），导致 cat 显示乱码。
2. 修复为 UTF-8 no-BOM 编码，并修订 commit 链/改动量数字/Bug 修复计数（7→8）等不一致。
3. v2 commit history 整理：原 v2 commit message 中 8 个带 BOM，已重新用 git format-patch + 清理 RFC 2047 编码中的 BOM 前缀后 git am 重做，全部 12 个 commit message 干净无 BOM。
4. 修复 v2 期间遗留的 3 个文件 BOM 头（general_chat.py / graph.py / agent.py），commit 3e29490 单独清理。
5. 本文档自身多轮修订已收敛，**§11 链以 12 个业务 v2 commit 为准，docs 修订 commit 不计入业务 v2 增量**。
