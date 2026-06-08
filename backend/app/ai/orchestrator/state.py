"""LangGraph 状态定义

RootState — 顶层图状态，所有子图继承
子图 State — 合同/凭证/群聊/通用对话各子图状态

设计原则：
- 所有子图 state 必须继承 RootState（不混用 MessagesState）
- messages 统一用 add_messages 归约器
- 子图与 root 之间按字段名自动映射
"""
from typing import TypedDict, Annotated, Optional
import operator
from langgraph.graph.message import add_messages


class RootState(TypedDict, total=False):
    """顶层图状态（所有子图继承）"""

    # ── 消息流 ──
    messages: Annotated[list, add_messages]

    # ── 用户与上下文 ──
    user_id: int
    user_role: str              # admin / income / expense
    session_id: str

    # ── 当前任务 ──
    intent: Optional[str]       # contract_entry / receipt_entry / group_chat / general
    attachments: list[dict]     # [{file_id, file_type}, ...]
    file_context: Optional[str] # VL/文本预分析结果

    # ── HITL 中断 ──
    interrupt_info: Optional[dict]  # {type, message, options, interrupt_id}

    # ── 工具调用 ──
    tools_invoked: Annotated[list[str], operator.add]
    pending_tool_calls: list[dict]  # 待执行 tool_call

    # ── 错误与降级 ──
    errors: Annotated[list[str], operator.add]
    fallback_strategy: Optional[str]

    # ── 流程控制 ──
    current_node: str
    iteration_count: int
    should_end: bool

    # ── chat_history 并行落库标记 (ADR #6) ──
    chat_history_meta: dict

    # ── ToolExecutor 上下文（必须注入 initial_state，否则 mode guard 拦截） ──
    executor_mode: str          # "chat" | "receipt_income" | "receipt_expense"
    session_context: dict       # 会话上下文，透传给 ToolExecutor 供 DB 兜底查询

    # ── 幂等性防护（finalize_node 用，防止重复执行导致 chat_history 重复入库） ──
    _finalized: bool


class ContractEntryState(RootState, total=False):
    """合同录入子图状态（Agent 循环架构）

    Agent 循环：analyze_file → call_model ↔ execute_tool
    interrupt 安全门在 execute_tool 中拦截敏感工具（create_customer/create_contract），
    用户确认后通过 approved_tool_ids 放行。
    """

    # HITL 安全门：已批准的工具调用 ID，execute_tool_node 据此跳过 interrupt
    approved_tool_ids: Annotated[list[str], operator.add]


class GeneralChatState(RootState, total=False):
    """通用对话子图状态（无新增字段，保留独立类为未来扩展）"""
    tokens_used: int


class ReceiptEntryState(RootState, total=False):
    """凭证录入子图状态（收入/支出统一）

    Agent 循环：analyze_receipt → call_model ↔ execute_tool
    interrupt 安全门在 execute_tool 中拦截敏感工具（create_expense/create_payment），
    展示结构化凭证确认表单，用户确认或修改后 resume 放行。
    """

    # HITL 安全门：已批准的工具调用 ID，execute_tool_node 据此跳过 interrupt
    approved_tool_ids: Annotated[list[str], operator.add]
