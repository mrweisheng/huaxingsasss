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

    # ── 附件（当前轮） ──
    attachments: list[dict]  # [{file_id, file_type, file_name}, ...]

    # ── 流程控制 ──
    iteration_count: int
    should_end: bool
    errors: Annotated[list[str], operator.add]

    # ── 跨 turn 凭证文件追踪 ──
    # analyze_files 分析到 receipt 时记录 file_id，供后续
    # match_and_confirm_payment / create_payment_record 消费。
    # 不依赖 LLM 在 receipt_data 中传递 _source_file_id 或 receipt_file_ids。
    _pending_receipt_file_ids: list[str]

    # ── chat_history 落库标记 ──
    chat_history_meta: dict
    _finalized: bool
    _persisted_count: int   # 已落库的 messages 数量游标（跨轮持久化在 checkpointer 里，新会话默认 0）
