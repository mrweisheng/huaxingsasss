"""Root Graph — LangGraph 顶层编排

Phase 1：intake_node → route_by_intent → contract_entry_subgraph → finalize_node
Phase 2：凭证引导 / 群聊 / 通用对话子图接入

ADR #5：直接使用 AsyncPostgresSaver
ADR #2：不引入 ChatOpenAI，继续用 DashScopeAgentClient
"""
import logging
from typing import AsyncGenerator, Optional, Literal

from langgraph.graph import StateGraph, START, END

from app.ai.orchestrator.state import RootState, ContractEntryState, GeneralChatState
from app.ai.orchestrator.checkpointer import get_checkpointer

logger = logging.getLogger(__name__)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 节点：入口（解析附件，决定意图）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def intake_node(state: RootState) -> dict:
    """入口节点：根据附件类型和用户消息推断意图"""
    attachments = state.get("attachments", [])
    if not attachments:
        return {"intent": "general", "file_context": None}

    # 根据文件类型 + 用户消息字符串推断意图
    user_msg = ""
    if state.get("messages"):
        last_msg = state["messages"][-1]
        user_msg = getattr(last_msg, "content", "") or ""
        if isinstance(user_msg, list):
            user_msg = " ".join(str(p) for p in user_msg)

    intent = _infer_intent(attachments, user_msg)

    return {
        "intent": intent,
        "current_node": "intake_node",
        "iteration_count": 0,
    }


def _infer_intent(attachments: list, user_msg: str) -> str:
    """根据文件类型 + 用户消息推断意图"""
    file_types = {a.get("file_type", "") for a in attachments if isinstance(a, dict)}

    user_lower = user_msg.lower() if user_msg else ""

    if any(t in ("pdf", "word", "excel") for t in file_types):
        if any(kw in user_lower for kw in ("合同", "contract", "录入")):
            return "contract_entry"
        if any(kw in user_lower for kw in ("凭证", "receipt", "转账", "收据")):
            return "receipt_entry"
        return "contract_entry"  # 文档文件默认当作合同

    if any(t.startswith("image") for t in file_types):
        if any(kw in user_lower for kw in ("凭证", "receipt", "转账", "收据", "付款")):
            return "receipt_entry"
        return "general"  # 图片不确定用途，走通用对话

    return "general"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 条件边：根据 intent 路由到子图
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def route_by_intent(state: RootState) -> Literal[
    "contract_entry_subgraph", "general_chat_subgraph"
]:
    """根据 intent 和 mode 路由。

    Phase 1 仅实现 contract_entry 和 general_chat 两个子图。
    Phase 2 扩展 receipt_entry / group_chat。
    """
    intent = state.get("intent", "general")
    mode = state.get("executor_mode", "chat")

    # 合同意图 + chat 模式 → 合同录入子图
    if intent == "contract_entry" and mode == "chat":
        return "contract_entry_subgraph"

    # 通用对话兜底
    return "general_chat_subgraph"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 节点：结束（chat_history 落库 + SSE done 事件）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def finalize_node(state: RootState) -> dict:
    """结束节点：清理 interrupt_info，标记 should_end"""
    return {
        "should_end": True,
        "interrupt_info": None,
        "current_node": "finalize_node",
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 通用对话子图（Phase 1 — 保留 ReAct 循环作为过渡）
# Phase 2 将替换为自建 StateGraph（文档 §7.4）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def general_chat_start_node(state: GeneralChatState) -> dict:
    """通用对话入口：Phase 1 占位节点。

    ⚠️ 当前不会触发：endpoint 的 use_langgraph 判断只对 pdf/word/excel 附件
    走 LangGraph 路径。纯文本消息仍走旧 agent.py ReAct 循环。
    Phase 2 将替换此占位为完整的 call_model → execute_tool ReAct 子图。
    """
    return {
        "should_end": True,
        "current_node": "general_chat_start_node",
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 构建 Root Graph
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def build_general_chat_subgraph() -> StateGraph:
    """构建通用对话子图（Phase 1 占位）"""
    g = StateGraph(GeneralChatState)
    g.add_node("general_chat_start_node", general_chat_start_node)
    g.add_edge(START, "general_chat_start_node")
    g.add_edge("general_chat_start_node", END)
    return g.compile()


def build_root_graph(contract_entry_app, checkpointer=None) -> StateGraph:
    """编译 Root Graph，注册合同录入子图。

    Args:
        contract_entry_app: ContractEntrySubgraph.build() 的返回值
        checkpointer: AsyncPostgresSaver 实例
    """
    workflow = StateGraph(RootState)

    # 通用对话子图（Phase 1 占位）
    general_app = build_general_chat_subgraph()

    # 添加节点
    workflow.add_node("intake_node", intake_node)
    workflow.add_node("contract_entry_subgraph", contract_entry_app)
    workflow.add_node("general_chat_subgraph", general_app)
    workflow.add_node("finalize_node", finalize_node)

    # 边
    workflow.add_edge(START, "intake_node")

    workflow.add_conditional_edges(
        "intake_node",
        route_by_intent,
        {
            "contract_entry_subgraph": "contract_entry_subgraph",
            "general_chat_subgraph": "general_chat_subgraph",
        },
    )

    workflow.add_edge("contract_entry_subgraph", "finalize_node")
    workflow.add_edge("general_chat_subgraph", "finalize_node")
    workflow.add_edge("finalize_node", END)

    return workflow.compile(checkpointer=checkpointer)
