# 无凭证支出改造方案 · 代码级审核意见

**审核对象**：`create_payment_record` 工具新增 `no_receipt=True` 参数，支持小额无凭证支出（如介绍人返点、现金杂费）的纯文字录入流程。
**审核日期**：2026-06-12
**审核范围**：仅支出路径，收入路径一行不碰。

---

## 一、审核方法

1. 通读方案 6 个章节，对照实际代码核验
2. 关键文件：`tools_v2.py`、`tools.py`、`unified_agent.py`、`prompts_v2.py`、`payment_service.py`、`payment.py`(schema)、`ContractDetail.tsx`、`PaymentList.tsx`
3. 对照 `CLAUDE.md` 三条铁律（Agent 模式边界 / 工具返回值事实 JSON / 不动既有接口）

---

## 二、5 项冲突审核结论

### 🔴 冲突1（Mode Guard 白名单）：**事实错误已纠正**

| 项 | 说明 |
|---|---|
| 首次判断 | `_MODE_ALLOWED_TOOLS` 白名单缺 `create_payment_record`，v2 会被 mode guard 拦截 |
| 核实证据 | [tools_v2.py:38-49](backend/app/ai/tools_v2.py:38) `__init__` 重置 `self.mode = None`；[tools_v2.py:213-242](backend/app/ai/tools_v2.py:213) `execute()` 完全重写，**不调用** `_check_mode_guard`；类文档字符串明确"重写 execute() 入口，删除 mode guard / document guard" |
| 第二位审核者复核 | ✅ 正确。我只看了 `_MODE_ALLOWED_TOOLS` 定义，未沿调用链核验 v2 execute() 是否真会触发 |
| 结论 | **方案无需改 mode guard**。v2 体系下没有 mode 维度限制 |

### 🔴 冲突2（CLAUDE.md 文档与代码不符）：**属实，已采纳为文档修正**

| 项 | 说明 |
|---|---|
| 首次判断 | `CLAUDE.md` 声称 `_WRITABLE_TOOLS` + `_CONFIRM_KEYWORDS` 在代码层做关键词拦截；实际 `grep -rn` 零结果 |
| 核实证据 | [unified_agent.py:13](backend/app/ai/orchestrator/unified_agent.py:13) 和 :336-337 注释明确"写入确认完全交给 LLM 自主判断（system prompt 约束），不在代码层做关键词拦截" |
| 结论 | `CLAUDE.md` 该段落是陈旧文档。本次改动**顺手修文档**，不改业务逻辑 |

### 🟡 冲突3（description 自动生成逻辑冲突）：**属实，已采纳（必修）**

| 项 | 说明 |
|---|---|
| 首次判断 | [tools_v2.py:763-779](backend/app/ai/tools_v2.py:763) 现有逻辑：`if not description` 走 `_build_payment_description` 自动拼接，栅栏2 的 description 必填形同虚设 |
| 修订方案（方案 A） | ① 栅栏2 在 `no_receipt=True` 时把 `description` 列为必填；② 自动生成 description 跳过分支加 `and not no_receipt` |
| 结论 | ✅ 必修。修订方案是干净的方案 A 实施，LLM 不传 description 时不会被拼接覆盖 |

### 🟡 冲突4（notes 前缀被覆盖）：**部分属实，已采纳（抽常量 + 前缀保护，不动 schema）**

| 项 | 说明 |
|---|---|
| 首次判断 | [tools.py:1203-1204](backend/app/ai/tools.py:1203) `updates = {f: kwargs[f] for f in updatable_fields if kwargs.get(f) is not None}` 直接覆盖 notes，无前缀保护 |
| 修订方案 | ① 抽 `NO_RECEIPT_NOTE_PREFIX = "[无凭证支出]"` 常量到 `backend/app/core/constants.py`；② v2 子类 `update_payment` 加前缀保护逻辑（用户编辑 notes 时若原记录含前缀且新值不带，自动补回） |
| 不采纳项 | ❌ DB 加 `is_no_receipt` 字段（违反"不动 schema"约束） |
| 结论 | ✅ 部分采纳。修订方案合理 |

### 🟡 冲突5（栅栏返回值含行为指令）：**属实，已采纳（必修）**

| 项 | 说明 |
|---|---|
| 首次判断 | 原栅栏2 返回 `"请先向用户追问。"`，违反 CLAUDE.md 工具铁律"不嵌入'请先...'等行为指令" |
| 修订方案 | 改为结构化返回：`{"error": "...", "code": "NO_RECEIPT_MISSING_FIELDS", "missing_fields": [...]}`，让 LLM 自主决定如何追问 |
| 结论 | ✅ 必修。比首次建议更彻底（加 code 字段便于测试与前端区分） |

---

## 三、4 项建议审核结论

### 💡 建议1（PaymentList 必须同步改 + 抽 helper）：**采纳**

- 原方案 3.4 措辞模糊（"如果你也希望..."），改为**必须同步改**
- 抽 `isNoReceipt(payment)` helper 到 `frontend/src/utils/payment.ts`，避免 ContractDetail 和 PaymentList 双重维护判定逻辑

### 💡 建议2（prompt 限定 mode 适用范围）：**采纳**

- 原方案把"无凭证支出场景识别"放在 `build_system_prompt` 通用块，chat 模式也会触发
- 改为：仅在 `contract_info.get("payment_type") == "expense"` 上下文才注入 NO_RECEIPT_EXPENSE_RULES 块
- 避免 chat 模式下 LLM 直接走无凭证支出路径，先追问合同

### 💡 建议3（tooltip 文案简化）：**采纳**

- 原 tooltip："本笔为无凭证支出，由用户口头确认录入"
- 改为："无凭证 · 用户口头确认"

### 💡 建议4（NO_RECEIPT_NOTE_PREFIX 抽常量）：**采纳**

- 放 `backend/app/core/constants.py`
- 前端 helper 在 `frontend/src/utils/payment.ts` 单独硬编码同一字符串
- **约束**：在 v2 `update_payment` 前缀保护代码注释里加 `# 必须与 frontend/src/utils/payment.ts 中的 NO_RECEIPT_NOTE_PREFIX 保持一致`

---

## 四、修订后的最终方案范围

### 范围调整
- ❌ 不改 mode guard 白名单（v2 已禁用 mode guard，事实已纠正）
- ✅ 新增 `backend/app/core/constants.py`，加 `NO_RECEIPT_NOTE_PREFIX = "[无凭证支出]"`
- ✅ 修订 `tools_v2.py` 栅栏2：`no_receipt=True` 时 `description` 必填，错误返回结构化 `missing_fields`
- ✅ 修订 `tools_v2.py` 自动生成 description：跳过分支加 `and not no_receipt`
- ✅ 修订 `tools_v2.py` `update_payment`：notes 字段更新时保护 `[无凭证支出]` 前缀
- ✅ 修订 prompt 规则：仅在 `payment_type == "expense"` 上下文注入
- ✅ 修订前端：`ContractDetail.tsx` + `PaymentList.tsx` 同步改，抽 `isNoReceipt()` helper
- ✅ 顺手修 CLAUDE.md 中 `_WRITABLE_TOOLS` / `_CONFIRM_KEYWORDS` 陈旧描述

### 关键代码修订点

**栅栏2 修正版**：
```python
if no_receipt:
    if type != "expense":
        return json.dumps({
            "error": "no_receipt 仅支持 type=expense",
            "code": "NO_RECEIPT_INCOME_FORBIDDEN",
        }, ensure_ascii=False)
    missing = []
    if not payee_name: missing.append("payee_name")
    if not description: missing.append("description")  # 🆕 必填
    if not paid_date: missing.append("paid_date")
    if missing:
        return json.dumps({
            "error": "no_receipt 支出缺少必填字段",
            "code": "NO_RECEIPT_MISSING_FIELDS",
            "missing_fields": missing,
        }, ensure_ascii=False)
    if receipt_image_path or receipt_data or receipt_file_ids:
        return json.dumps({
            "error": "no_receipt=true 与凭证字段互斥",
            "code": "NO_RECEIPT_WITH_RECEIPT_DATA",
        }, ensure_ascii=False)
```

**description 自动生成跳过分支**：
```python
if not description and not no_receipt:   # 🆕 加 not no_receipt
    hint = ...
    # ... 现有逻辑
```

**update_payment 前缀保护**：
```python
def update_payment(self, **kwargs) -> str:
    payment_id = kwargs.get("payment_id")
    new_notes = kwargs.get("notes")
    # 🆕 前缀保护
    if payment_id and new_notes is not None:
        from app.core.constants import NO_RECEIPT_NOTE_PREFIX
        existing = self.db.query(Payment).filter(Payment.id == payment_id).first()
        if existing and (existing.notes or "").startswith(NO_RECEIPT_NOTE_PREFIX):
            if not new_notes.startswith(NO_RECEIPT_NOTE_PREFIX):
                kwargs["notes"] = f"{NO_RECEIPT_NOTE_PREFIX} {new_notes}".strip()
    # 调父类...（原有逻辑）
```

**前端 helper**：
```typescript
export const NO_RECEIPT_NOTE_PREFIX = '[无凭证支出]'
export function isNoReceipt(payment: { notes?: string | null; receipt_image_path?: string | null }): boolean {
  return !payment.receipt_image_path && (payment.notes ?? '').startsWith(NO_RECEIPT_NOTE_PREFIX)
}
```

**prompt 规则限定**：
```python
# build_system_prompt 内
if contract_info and contract_info.get("payment_type") == "expense":
    prompt += NO_RECEIPT_EXPENSE_RULES  # 仅在合同支出上下文注入
```

---

## 五、验证清单（修订后）

| # | 步骤 | 预期 |
|---|---|---|
| 1 | `no_receipt=True` + `type=income` | `code=NO_RECEIPT_INCOME_FORBIDDEN` |
| 2 | `no_receipt=True` 缺 `description` | `code=NO_RECEIPT_MISSING_FIELDS` + `missing_fields=["description"]` |
| 3 | `no_receipt=True` 缺 `paid_date` | `code=NO_RECEIPT_MISSING_FIELDS` |
| 4 | `no_receipt=True` 同时传 `receipt_data` | `code=NO_RECEIPT_WITH_RECEIPT_DATA` |
| 5 | `no_receipt=True` 全字段齐全 | 落 paid + notes 含 `[无凭证支出]` 前缀 + 合同 expense 累加 |
| 6 | 用户后续 `update_payment` 改 notes 不带前缀 | 自动补回前缀（保护审计标记） |
| 7 | 同合同两笔（一有凭证一无凭证） | 前端两个组件 chip 显示一致 |
| 8 | chat 模式（无合同上下文）发"返点 500" | LLM 不会直接走无凭证支出路径，先追问合同 |

---

## 六、最终结论

| 维度 | 结论 |
|---|---|
| 业务必要性 | ✅ 强。解决实际痛点 |
| CLAUDE.md 铁律符合度 | ✅ 高。决策归 LLM、边界留代码、工具返回纯事实 JSON |
| 与现有代码一致性 | ✅ 高。修订后 5 项冲突全部对齐 |
| 改动量控制 | ✅ 优。4 个文件 + 1 个新增常量文件，新分支不影响主路径 |
| 回退可行性 | ✅ 优。全是新增分支，删 `no_receipt` 参数即可回滚 |
| 审计可追溯 | ✅ 中。notes 前缀 + update_payment 保护 + 前端容错判定 |

**审核通过，可进入实施阶段。**