"""付款审计标记常量

用于标识无凭证支出等需审计追溯的付款记录。前后端共用同一字符串约定。
单一事实来源，避免散落在 tool 层 / 前端 / 测试断言三处。
"""

# 无凭证支出标记前缀：写入到 payment.notes 字段开头，由前端识别后展示「无凭证」chip。
# 选择 notes 而非新增字段，遵循「不动 schema」约束；
# update_payment 工具有前缀保护逻辑，确保用户编辑 notes 时审计标记不丢失。
NO_RECEIPT_NOTE_PREFIX = "[无凭证支出]"

# 无凭证收入标记前缀：现阶段（INCOME_RECEIPT_REQUIRED=False）收入允许无凭证录入，
# 在 notes 开头打此标记，便于前端识别与将来补凭证时筛选。
NO_RECEIPT_INCOME_PREFIX = "[无凭证收入]"
