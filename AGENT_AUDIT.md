# Agent 智能体审核报告

> 审核日期：2026-06-06
> 审核范围：`backend/app/ai/agent.py`、`tools.py`、`prompts.py`
> 核心原则：Agent 能做的事，不要用规则做。只保留安全边界和数据完整性。

---

## 一、核心问题总结

当前系统有两个层面的偏差：

1. **用 Python 代码做 LLM 该做的事**：确认意图正则、结果格式化、工具内嵌指令
2. **用固定步骤替代指导原则**：工作流写死工具调用链、工具描述塞行为指令

每出一次 bug 就加一条规则，本质是把 Agent 当规则引擎维护，违反智能体的设计初衷。合同格式可能变化，但内容（客户、金额、日期）一定存在，Agent 应该具备通用理解能力。

---

## 二、高优先级问题（应该修）

### 2.1 确认意图的正则检测链

**文件**：`agent.py`
**位置**：65-79 行（正则定义）→ 611-616 行（`_is_confirmation`）→ 618-633 行（`_last_assistant_asked_confirmation`）→ 150-162 行（系统注入）

**当前做法**：

用 ~50 个正则枚举"确认"的说法（好的/确认/没问题/可以/OK/yes/好滴/好嘞/必须的/当然...），反向搜索历史消息的关键词检测上一轮是否请求确认，两个条件都命中时向用户消息前注入 `[系统注入：用户已确认，请立即执行...]`。

**问题**：

- 正则列表无限膨胀，永远覆盖不全（"对，就这样办"会漏掉）
- 关键词 `"将.*关联"` 等通配模式可能误匹配
- 正则误判（假阳性）时，强制注入指令会触发 LLM 执行用户并未确认的操作——安全隐患
- system prompt 已经有确认/执行规则（prompts.py 20-24 行），LLM 完全能自行理解

**修改建议**：

删除整个正则确认链（`_CONFIRM_PATTERN`、`_is_confirmation`、`_last_assistant_asked_confirmation`、系统注入逻辑）。确认意图完全由 LLM 通过 system prompt 自然理解。这是一个性能优化（省一轮 LLM 调用），但代价是引入了一个脆弱的规则层和安全隐患，不值得。

---

### 2.2 图片预分析的手动摘要构建

**文件**：`agent.py`
**位置**：581-605 行（`_pre_analyze_image` 内）

**当前做法**：

VL 模型返回结构化 JSON 后，逐字段 if-else 提取 party_b.name、total_amount、signed_date、payment_terms、business_description，手动拼接成摘要字符串。

**问题**：

与刚修复的文本预分析（2.2 节）完全相同的问题模式——人工挑选字段，遗漏就出 bug。

**修改建议**：

与文本预分析保持一致，直传 JSON（去掉 full_text），让 Agent 自行决定展示什么。改为：

```python
agent_data = {k: v for k, v in structured.items() if k != "full_text"}
return (
    f"[系统已自动提取合同结构化数据，请勿再调用 analyze_image 工具]\n"
    f"文件类型：{file_type_label}\n"
    f"file_id：{file_id}\n"
    f"结构化数据：\n{json.dumps(agent_data, ensure_ascii=False, indent=2)}\n\n"
    f"请基于以上数据向用户展示关键信息，询问是否需要创建合同。"
    f"创建客户时请直接使用 party_b 中的姓名、电话等信息。"
)
```

---

### 2.3 format_result_summary — 93 行代码在做 Agent 该做的事

**文件**：`tools.py`
**位置**：323-415 行

**当前做法**：

将工具返回的 JSON 解析后，按不同结构（analyze_image / match_receipt / 通用）生成人类可读文本摘要。包含截断逻辑（前 3 条结果）、格式化逻辑（金额、日期展示）。

**问题**：

这是 Agent LLM 的本职工作——理解工具结果并组织语言回复。用 Python 硬编码回复策略意味着每次业务变化都要改代码而不是调提示词。且摘要可能跟 Agent 实际需要说的内容冲突。

**修改建议**：

删除 `format_result_summary` 方法。工具结果直接返回原始 JSON，由 Agent 自行解读并生成回复。只在 Agent 无回复（兜底场景）时用最简单的 JSON 序列化替代。

---

### 2.4 工具返回值中嵌入行为指令

**文件**：`tools.py`
**位置**：

- 143-151 行（`_inject_receipt_warnings`）：凭证缺币种/日期时注入 `⚠️ 币种未识别：请向用户确认...`
- 1836 行（`ask_contract`）：嵌入 `_instruction: "请基于以上合同全文回答，不要编造"`

**问题**：

在工具输出里嵌入行为指令 = 运行时动态修改 Agent 的行为规则。这绕过了提示词工程的统一管理，导致：
- 同一条规则散落在代码和提示词两个地方，难以维护
- 与 system prompt 中的规则可能冲突
- 增加工具输出的复杂度

**修改建议**：

- `_inject_receipt_warnings`：删除。在 system prompt 中加一条通用规则："工具返回的数据如果缺少关键字段（币种、日期等），必须向用户确认"。
- `ask_contract` 的 `_instruction`：删除。system prompt 已有"基于工具返回的数据回答，不要编造"的规则。

---

### 2.5 工具描述中的行为指令膨胀

**文件**：`tools.py`
**位置**：2620-3027 行（`TOOL_DEFINITIONS`）

**当前做法**：

工具定义的 `description` 字段包含大量行为指令：
- `create_contract`："系统会自动使用之前 analyze_image 的分析结果，无需重复传递合同数据"
- `create_payment`："如果该期数已有记录...应改用 update_payment"
- `currency` 参数："必须询问用户确认，不可猜测默认"

**问题**：

这些行为指令随每次 API 调用发送，额外消耗 ~500-800 tokens/次。且如果与 system prompt 冲突，LLM 会优先遵循工具描述（更"具体"），导致提示词控制失效。

**修改建议**：

工具定义只保留接口描述（参数含义、枚举值、类型约束）。行为指令（"必须/不可/应使用"）统一移到 system prompt。具体：
- `create_contract` 的描述简化为："创建合同记录，传入 file_id 关联已分析的文件"
- `create_payment` 的"改用 update_payment"提示移到 system prompt
- `currency` 的确认要求已在 system prompt 币种规则中覆盖，删除重复

---

## 三、中优先级问题（建议修）

### 3.1 工作流步骤写死工具调用链

**文件**：`prompts.py`
**位置**：37-41 行（合同录入）、43-51 行（凭证录入）、53-58 行（群聊关联）

**当前做法**：

把 Agent 的操作步骤写死为固定序列，例如合同录入：先 analyze_image → search_customers → create_customer → create_contract。

**问题**：

Agent 有 tool calling 能力，应该根据上下文自行编排调用顺序。固定步骤在文件已经预分析的情况下（现在的默认行为）会导致步骤跳过/冲突。

**修改建议**：

从"编码步骤"改为"指导原则"。合同录入改为："用户上传合同文件时，分析文件内容，确认关键信息后录入系统。文件已预分析时直接使用提取的数据。" 凭证录入简化为一句话："凭证录入已迁移到合同卡片按钮，引导用户使用。"

---

### 3.2 get_customer_contracts 自动回退

**文件**：`tools.py`
**位置**：614-657 行

**当前做法**：

按 `business_type` 过滤后零结果时，自动回退查询该客户全部合同，返回中附带 `filter.fallback_to_all` 元信息。

**问题**：

工具替 Agent 做了决策。Agent 收到零结果后完全可以自行决定是告诉用户没找到还是重查全量。

**修改建议**：

删除自动回退逻辑。零结果就返回零结果，让 Agent 自行判断是否需要换条件重查。

---

### 3.3 重复规则清理

**文件**：`prompts.py`

以下规则出现多次，应只保留一处：

| 规则 | 重复次数 | 建议 |
|------|---------|------|
| 繁简体不转换 | 5 次（:97, :234, :244, :247, :317）| 只在 system prompt:97 保留 |
| JSON 输出格式（纯JSON/null/金额/日期） | 4 次（:177, :236, :275, :315）| 抽为 Python 常量拼接 |
| 币种/汇率规则 | 3 次（:66, :107, :152）| 只在 system prompt:66 保留 |
| 确认即执行 | 3 次（:20, :138, agent.py:150）| 只在 system prompt:20 保留，删除 agent.py 注入 |

---

### 3.4 合同分析提示词严格要求精简

**文件**：`prompts.py`
**位置**：236-247 行（11 条严格要求）

**问题**：

- 第 6 条（business_description 极简规则）与字段注释 191 行 100% 重复
- 第 7 条（vehicle_info 仅当明确提及）多余，没写自然是 null
- 第 8 条（full_text 完整转录）与字段注释 233 行重复
- 第 11 条（繁简体不转换）与第 8 条重复，且与 system prompt 重复

**修改建议**：

删除与字段注释重复的规则（第 6、7、8 条），删除繁简体规则（全局已有）。保留第 1-5、9-10 条。

---

## 四、合理的规则（不动）

以下规则是必要的安全边界或工程折衷，不做修改：

| 规则 | 文件:行号 | 为什么必须保留 |
|------|----------|--------------|
| 文档上下文守卫 `_DOCUMENT_BLOCKED_TOOLS` | tools.py:2548-2584 | 防止 LLM 从凭证误创建合同，业务数据安全边界 |
| 模式工具白名单 `_MODE_ALLOWED_TOOLS` | tools.py:2520-2542 | 收入/支出录入模式的工具限制 |
| 消息链配对校验 `_validate_message_chain` | agent.py:674-789 | OpenAI API 格式硬性要求 |
| 凭证文件 hash 去重 | tools.py:1409-1424 | 防止 ReAct 循环重复录入 |
| 字段归一化 `_normalize_payment_terms` | tools.py:201-222 | VL 输出字段名不稳定，工具层清洗比让 Agent 处理更可靠 |
| full_text 剥离 | tools.py:153-160 | token 优化，全文在缓存里供 create_contract 使用 |
| 角色权限描述 | prompts.py 角色段 | 数据隔离 |
| 繁简体不转换（system prompt 中保留一处） | prompts.py:97 | 从真实 bug 得出的硬规则 |
| 禁止编造 | prompts.py:100 | 数据准确性底线 |
| 无筛选条件时返回统计+样例 | tools.py:476-483 | token 成本控制，全量返回会爆 context |
| 搜索结果片段截取 | tools.py:1767-1779 | 合同全文数千字，片段足以判断相关性 |
| VL 缓存数据优先于 Agent 传入 | tools.py:1062-1095 | VL 看过原图，提取数据比 Agent 对话得到更可靠 |

---

## 五、修改优先级和影响范围

| 优先级 | 改动项 | 影响范围 | 风险 |
|--------|-------|---------|------|
| 🔴 P0 | 2.1 删除正则确认链 | agent.py 4 处 | 低——system prompt 已覆盖确认规则 |
| 🔴 P0 | 2.2 图片预分析直传 JSON | agent.py 1 处 | 低——与文本预分析保持一致 |
| 🔴 P0 | 2.3 删除 format_result_summary | tools.py 1 处 | 中——需确认兜底场景表现 |
| 🔴 P0 | 2.4 删除工具内嵌指令 | tools.py 2 处 | 低——system prompt 已覆盖 |
| 🟡 P1 | 2.5 精简工具描述 | tools.py TOOL_DEFINITIONS | 中——需测试 Agent 行为变化 |
| 🟡 P1 | 3.1 工作流改指导原则 | prompts.py 3 段 | 低——Agent 更灵活 |
| 🟡 P1 | 3.2 删除自动回退 | tools.py 1 处 | 低——Agent 自行决策 |
| 🟡 P1 | 3.3 重复规则清理 | prompts.py 多处 | 低——去重不影响行为 |
| 🟢 P2 | 3.4 分析提示词精简 | prompts.py 严格要求 | 低——删重复项 |

---

## 六、修改后的预期效果

- **代码量减少**：agent.py ~60 行（正则链+摘要构建）、tools.py ~100 行（格式化+注入+回退）
- **Token 开销降低**：工具描述精简约 500-800 tokens/次调用
- **维护成本降低**：行为规则集中在 system prompt，不再散落在代码各处
- **鲁棒性提升**：Agent 自行理解确认意图、自行决定展示内容，不再依赖脆弱的正则和字段枚举
- **合同格式变化适应性**：直传 JSON 而非手动选字段，无论合同怎么变，只要 LLM 能提取，Agent 就能用

---

## 七、二次审核（2026-06-06）

> 审核目的：验证一至六节中的问题是否仍存在，并搜索同类型未覆盖的问题。

### 7.1 原问题状态

**全部 9 项问题均未修复**，代码与初次审核时一致：

| 编号 | 问题 | 当前状态 | 验证位置 |
|------|------|---------|---------|
| 2.1 | 正则确认链 | 未修复 | agent.py:65-79, 150-162, 611-633 |
| 2.2 | 图片预分析手动摘要 | 未修复 | agent.py:581-605 |
| 2.3 | format_result_summary | 未修复 | tools.py:323-415 |
| 2.4 | 工具内嵌指令 | 未修复 | tools.py:143-151, 1836 |
| 2.5 | 工具描述行为指令 | 未修复 | tools.py:2787, 2830, 2841, 2870, 2912 |
| 3.1 | 工作流写死步骤 | 未修复 | prompts.py:37-58 |
| 3.2 | get_customer_contracts 自动回退 | 未修复 | tools.py:614-657 |
| 3.3 | 重复规则 | 未修复 | prompts.py 多处 |
| 3.4 | 分析提示词冗余 | 未修复 | prompts.py:236-247 |

### 7.2 新发现的同类问题

初次审核遗漏了大量同模式问题，按类型归类如下。

#### 7.2.1 工具返回值中嵌入行为指令（2.4 节未覆盖部分）

初次审核只发现了 `_inject_receipt_warnings` 和 `ask_contract._instruction` 两处。实际同模式有 **15+ 处**：

**`_warning` / `warning` 字段（向 Agent 注入行动指令）：**

| 位置 | 工具 | 内容 |
|------|------|------|
| tools.py:1285 | create_contract | `_warning: "合同总金额为0...请人工核实合同金额"` |
| tools.py:1393-1398 | create_payment | `warning: True, message: "...请使用 update_payment 更新已有记录"` |
| tools.py:1419-1423 | create_payment | `warning: True, message: "...请确认是否重复上传"` |
| tools.py:1487-1491 | create_expense | `warning: True, message: "...请确认是否重复上传"` |

**`hint` 字段（指示 Agent 如何引导用户）：**

| 位置 | 工具 | 内容 |
|------|------|------|
| tools.py:480 | search_customers | `hint: "...如需查找特定客户，请提供姓名、电话或微信群名..."` |
| tools.py:534 | search_contracts | `hint: "...如需查找特定合同，请提供客户名、合同号或状态筛选"` |
| tools.py:2082 | get_overview | `hint: "...可用 search_customers / search_contracts 精确查找"` |

**`message` 字段（面向用户的话术 / 告诉 Agent 下一步操作）：**

| 位置 | 工具 | 内容 |
|------|------|------|
| tools.py:655-657 | get_customer_contracts | `message: "按业务类型「X」未找到合同，已展示该客户全部 N 份合同..."` |
| tools.py:738 | create_customer | `message: "客户创建成功"` / `"客户已存在（ID: X）"` |
| tools.py:789 | update_customer | `message: f"客户信息已更新: {updated_fields}"` |
| tools.py:1726 | match_receipt | `message: "未找到匹配的付款记录。请提供客户姓名以便搜索。"` |
| tools.py:1731 | match_receipt | `message: "找到 N 条可能匹配的付款记录，请确认正确的关联。"` |
| tools.py:1762 | search_contract_text | `message: "未找到包含「X」的合同内容。"` |
| tools.py:1792 | search_contract_text | `message: "在 N 份合同中找到「X」的匹配内容。"` |

**`error` 字段中嵌入下一步行动指令：**

| 位置 | 工具 | 内容 |
|------|------|------|
| tools.py:1058 | create_contract | `error: "缺少 customer_id，请先创建或查找客户"` |
| tools.py:1598 | match_receipt | `error: "缺少凭证数据。请先调用 analyze_image 分析凭证..."` |
| tools.py:1818 | ask_contract | `error: "...请重新上传合同文件以触发全文提取"` |

**修复建议**：

将 `_warning`、`hint`、`message` 从工具返回值中移除。工具只返回结构化数据（`success`、`data`、`error`）。Agent 的回复策略（如何引导用户、如何解释结果）由 system prompt 统一管理。

**通用修复原则（适用于 A6-A10 全部）**：

> 删除任何 `message`/`hint`/`warning` 字段前，逐条检查：**该字段是否包含未被返回 JSON 其他字段覆盖的事实信息？**
> - **有** → 提取为独立的结构化字段，再删除文案
> - **无** → 直接删除

**事实信息 vs 行为指令/文案的判断示例**：

| 位置 | 字段 | 事实信息 | 行为指令/文案 | 处理方式 |
|------|------|---------|-------------|---------|
| tools.py:789 update_customer | `message: "客户信息已更新: ['phone', 'wechat_group_name']"` | `updated.keys()` 这份字段列表**不在返回的其他字段中**（`customer` 是全量快照，无法区分本次更新了哪些） | "客户信息已更新" | 提取为 `updated_fields: ["phone", "wechat_group_name"]`，删除 message |
| tools.py:738 create_customer | `message: "客户已存在（ID: X）"` | ID 已在 `customer.id` 中，新建/已存在已在 `created` 布尔值中 | 整条 message | 纯冗余文案，直接删除 |
| tools.py:1792 search_contract_text | `message: "在 N 份合同中找到「X」的匹配内容"` | 匹配数量 N 和搜索词 X 不在返回的其他字段中（`results` 数组可以 len，但 keyword 未显式返回） | "找到...匹配内容" | 添加 `match_count` 和 `keyword` 字段，或保留 message 中的事实部分 |
| tools.py:1726 match_receipt | `message: "未找到匹配的付款记录。请提供客户姓名以便搜索。"` | 无结果已体现在 `matches: []` 中 | "请提供客户姓名以便搜索" | 纯指令文案，直接删除 |
| tools.py:1058 create_contract | `error: "缺少 customer_id，请先创建或查找客户"` | 错误原因（缺少 customer_id）是事实 | "请先创建或查找客户"是指令 | 保留错误原因，删除操作指引 |

**其他边界情况**：
- `warning: True` 配合的期数已存在/凭证去重等**状态信息**应保留为结构化字段（如 `duplicate: true`、`existing_payment: {...}`），但去掉面向用户的文案，让 Agent 自行措辞
- `error` 中的操作指引（"请先调用 analyze_image"）应移到 system prompt 的工具使用策略中

---

#### 7.2.2 预分析结果中的系统指令注入（2.2 节未覆盖部分）

初次审核只关注了图片预分析的手动摘要问题。实际上文本预分析和文件重复检测同样存在指令注入：

| 位置 | 方法 | 注入内容 |
|------|------|---------|
| agent.py:522-528 | `_analyze_text_content` 成功路径 | `[系统已自动提取合同结构化数据，请勿再调用 analyze_image 工具]` + `请基于以上数据向用户展示关键信息，询问是否需要创建合同` + `创建客户时请直接使用 party_b 中的姓名、电话等信息` |
| agent.py:552-557 | `_analyze_text_content` 降级路径 | `[系统已自动提取文件内容，请勿再调用 analyze_image 工具]` + `请直接基于以上内容向用户展示关键信息，询问是否需要创建合同` |
| agent.py:600-604 | `_pre_analyze_image` | `[系统已自动分析图片文件，请勿再调用 analyze_image 工具]` + `请基于以上摘要向用户展示关键信息，询问是否需要创建合同` |
| agent.py:469-474 | `_prepare_file` 重复文件 | `[系统预分析结果 - 文件重复]` + 合同编号/客户/状态信息 |

**与 2.2 节的关系**：文本预分析（519-529 行）已改为直传 JSON，比图片预分析先进。但两者都在 file_context 中注入了行为指令（`请勿再调用`、`请向用户展示`、`询问是否需要`），这些指令本质上与 2.4 节描述的"工具返回值中嵌入行为指令"是同一模式。

**修复建议**：

预分析的 file_context 只保留事实信息（文件类型、file_id、结构化数据/原文摘要）。行为指令（不调用 analyze_image、向用户展示、询问是否创建）移到 system prompt 的文件处理规则中。例如：

```
# system prompt 中添加
### 文件预分析
- 用户上传的文件已在服务端预分析，file_context 中包含提取结果
- 不要对已预分析的文件再次调用 analyze_image
- 基于预分析数据向用户展示关键信息，询问下一步操作
```

---

#### 7.2.3 RECEIPT_ENTRY_PROMPT 中的重复确认规则（3.3 节未覆盖部分）

初次审核列出了"确认即执行"重复 3 次（prompts.py:20, :138, agent.py:150），但未详述 RECEIPT_ENTRY_PROMPT 中的完整重复：

| 位置 | 内容 |
|------|------|
| prompts.py:21 | `用户确认（"好的""确认""OK"...）= 立即执行上一轮提出的操作` — system prompt |
| prompts.py:138-141 | `用户确认（"好的""确认""OK"...）= 立即执行` + `用户拒绝或修正 → 按修正后的信息重新确认` + `只在首次展示识别结果时请求确认` — RECEIPT_ENTRY_PROMPT，与 system prompt 20-24 行完全一致 |

RECEIPT_ENTRY_PROMPT 是独立的 system prompt（凭证录入模式），不与主 system prompt 叠加使用，因此严格来说不算重复。但初次审核将其归为"重复 3 次"，此处澄清：实际是 2 个独立的 system prompt 各写了一套确认规则，加 agent.py 的正则注入 = 3 处。删除 agent.py 注入后剩 2 处，各自独立生效，可接受。

---

#### 7.2.4 繁简体规则实际重复次数修正（3.3 节修正）

初次审核标注繁简体规则重复 5 次。实际为 **7 处**（含字段描述和严格要求）：

| 行号 | 所属 Prompt | 内容 |
|------|------------|------|
| 97-100 | system prompt 繁简体小节 | 完整规则（保留此处） |
| 233 | CONTRACT_ANALYSIS — full_text 字段 | "原文用字原样保留，不得在繁简体之间互相转换" |
| 244 | CONTRACT_ANALYSIS — 严格要求第 8 条 | 与 233 行重复 |
| 247 | CONTRACT_ANALYSIS — 严格要求第 11 条 | 所有人名不得繁简转换（与 244 行重复） |
| 287 | GROUP_CHAT_ANALYSIS — group_name 字段 | "必须原样保留繁体字" |
| 317 | GROUP_CHAT_ANALYSIS — 严格要求第 2 条 | "群名、成员昵称、消息原必须原样保留，繁体字不得转为简体" |

**修复建议**：CONTRACT_ANALYSIS_PROMPT 中只保留 233 行（full_text 字段注释中的一句），删除 244 行（严格要求第 8 条）和 247 行（严格要求第 11 条）。GROUP_CHAT_ANALYSIS_PROMPT 中只保留 317 行，删除 287 行字段注释中的重复。

---

### 7.3 完整问题清单（含初次 + 二次审核）

| 编号 | 优先级 | 问题 | 位置 | 初次已记录 |
|------|-------|------|------|-----------|
| A1 | P0 | 正则确认链 | agent.py:65-79, 150-162, 611-633 | 2.1 |
| A2 | P0 | 图片预分析手动摘要 | agent.py:581-605 | 2.2 |
| A3 | P0 | format_result_summary | tools.py:323-415 | 2.3 |
| A4 | P0 | _inject_receipt_warnings | tools.py:143-151 | 2.4 |
| A5 | P0 | ask_contract _instruction | tools.py:1836 | 2.4 |
| A6 | **P0** | **工具返回值嵌入 _warning/warning** | tools.py:1285, 1394, 1419, 1487 | **新增** |
| A7 | **P1** | **工具返回值嵌入 hint** | tools.py:480, 534, 2082 | **新增** |
| A8 | **P1** | **工具返回值嵌入 message（引导/话术）** | tools.py:655, 738, 789, 1726, 1731, 1762, 1792 | **新增** |
| A9 | **P1** | **error 字段嵌入行动指令** | tools.py:1058, 1598, 1818 | **新增** |
| A10 | **P1** | **预分析 file_context 注入行为指令** | agent.py:469-474, 522-528, 552-557, 600-604 | **新增** |
| A11 | P1 | 工具描述中的行为指令 | tools.py TOOL_DEFINITIONS 5 处 | 2.5 |
| A12 | P1 | 工作流写死步骤 | prompts.py:37-58 | 3.1 |
| A13 | P1 | get_customer_contracts 自动回退 | tools.py:614-657 | 3.2 |
| A14 | P2 | 重复规则清理（含修正） | prompts.py 多处 | 3.3 |
| A15 | P2 | 分析提示词精简 | prompts.py:236-247 | 3.4 |

**新增 5 项（A6-A10），总计 15 项待修复。**

---

### 7.4 新增问题的修复优先级

**通用修复原则（A6-A10 全部适用）**：删除 `message`/`hint`/`warning` 前，逐条检查是否包含未被返回 JSON 其他字段覆盖的事实信息。有则提取为结构化字段，无则直接删除。

| 优先级 | 编号 | 修改建议 |
|-------|------|---------|
| P0 | A6 | `_warning`/`warning` 改为结构化状态字段（`duplicate: true`、`zero_amount: true`），去掉面向用户的文案 |
| P1 | A7 | 删除 `hint` 字段，引导逻辑移到 system prompt 工具使用策略 |
| P1 | A8 | 逐条检查 message 中的事实信息：`update_customer` 的 `updated_fields` 需提取为独立字段，`create_customer` 的纯冗余文案直删，`search_contract_text` 的匹配数量/搜索词需确认是否有独立字段覆盖 |
| P1 | A9 | `error` 保留错误原因描述，删除下一步操作指引（"请先调用 X"） |
| P1 | A10 | 预分析 file_context 只保留事实（file_id、类型、数据），行为指令移到 system prompt |

---

### 7.5 合理的保留项（不属于反模式）

以下 `message` / `warning` 字段有工程必要性，不应删除：

| 位置 | 内容 | 为什么保留 |
|------|------|----------|
| tools.py:1393-1398 | 期数已存在返回 `existing_payment` 数据 | 结构化数据（existing_payment dict）是 Agent 决策所需的关键信息，只是 `message` 文案应删 |
| tools.py:1419-1423 | 凭证去重返回 `warning` | hash 去重是工程逻辑，状态信息应保留，文案应删 |
| tools.py:655-657 | 回退到全量时的 `message` | 3.2 节已建议删除自动回退逻辑，此项随 3.2 一起解决 |
| tools.py:1836 | ask_contract `_instruction` | 已在 A5 中覆盖 |
