"""统一 Agent 状态定义 v2

替代原 RootState + ContractEntryState + ReceiptEntryState + GeneralChatState 四个 State。
精简字段：删除 intent、file_context、interrupt_info、pending_plan、executor_mode 等。
"""

import operator
from typing import TypedDict, Annotated, Optional
from langgraph.graph.message import add_messages


class AgentState(TypedDict, total=False):
    """统一 Agent 状态 — 单层 Agent 循环"""

    # ── 消息流 ──
    messages: Annotated[list, add_messages]

    # ── 用户与上下文 ──
    user_id: int
    user_role: str          # admin / income / expense
    session_id: str
    session_context: Optional[dict]   # 从 chat_sessions.context 加载 {contract_id, payment_type}
    session_mode: str                 # 会话模式: chat | receipt_income | receipt_expense

    # ── 附件（当前轮） ──
    attachments: list[dict]  # [{file_id, file_type, file_name}, ...]

    # ── 流程控制 ──
    iteration_count: int
    should_end: bool
    ui_handoff_pending: bool  # UI handoff 工具已把控制权交还用户，本轮应 finalize 等待下一条输入
    errors: Annotated[list[str], operator.add]

    # ── chat_history 落库标记 ──
    chat_history_meta: dict
    _finalized: bool
    _persisted_count: int   # 已落库的 messages 数量游标（跨轮持久化在 checkpointer 里，新会话默认 0）
