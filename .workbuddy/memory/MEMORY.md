---
summary: "Project notes: architecture decisions, conventions, patterns"
---

# MEMORY.md — Huaxing Sasss Project

## Currency Conversion Design (2026-06-01)

**Decision**: Skip CNY conversion when payment currency matches contract currency.

**Rationale**: The original design forced CNY conversion on every payment. This creates noise for same-currency transactions (e.g., HKD contract + HKD payment → meaningless ¥43,560 display). The conversion should only trigger when currencies differ (e.g., HKD contract + CNY payment).

**Rules**:
- **Same currency** (payment.currency == contract.currency): amount_in_cny = None, exchange_rate = None, contract completion check via original currency `paid_amount >= total_amount`
- **Cross currency** (payment.currency != contract.currency): convert_to_cny(), store rate & amount_in_cny. Contract paid_amount tracked in contract currency (via reverse conversion). Contract completion check via original currency (always works since paid_amount is always in contract's currency).

**Key insight**: The contract's `paid_amount` is ALWAYS in the contract's original currency — even cross-currency payments get reverse-converted back to contract currency in `_add_to_contract_paid`. So `paid_amount >= total_amount` works universally.

**Scope**: create_payment, create_expense, update_payment, match_receipt

**Currency confirmation**:
- analyze_image receipt prompt always extracts currency
- If currency unclear, LLM must ask user before proceeding — no guessing default to CNY
- create_payment tool definition: currency field has `default: "CNY"` removed (still required in `required` array)

**Frontend**:
- PaymentList: show "折算CNY" column only when amount_in_cny is not null
- ContractDetail/CustomerDetail: CNY fields hidden when null

## AI 服务架构 (2026-06-03)

**Decision**: Agent 推理模型从硅基流动 DeepSeek 迁移到阿里云百炼 DashScope DeepSeek-V4-Flash。

**Rationale**: 统一 API 平台，与 qwen3-vl-flash 共用 DASHSCOPE_API_KEY，减少 API key 管理。

**Architecture**:
- **Agent 流式推理**: 百炼兼容模式 API（`DASHSCOPE_BASE_URL/chat/completions`），`DashScopeAgentClient` 类，模型 `deepseek-v4-flash`
- **PDF 文本解析**: 原生 `dashscope.Generation.call()` SDK，`enable_thinking=True`
- **视觉分析**: 保持不变，继续使用兼容模式 `qwen3-vl-flash`
- **配置文件**: `.env` 中 `DASHSCOPE_AGENT_MODEL=deepseek-v4-flash`，`config.py` 中对应 `AGENT_MAX_RETRIES=3`, `AGENT_RETRY_BASE_DELAY=1.0`
