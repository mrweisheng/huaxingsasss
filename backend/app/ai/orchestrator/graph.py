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
    """根据文件类型 + 用户消息推断意图。

    设计原则：文档类（pdf/word/excel）**激进路由到 contract_entry**，
    因为华星资源是合同管理专门业务，用户上传非合同文档的概率低，
    而子图内的 analyze_file_node 用 VL 二次判断能兜底（识别不到 customer_name
    会走 fallback_node）。图片类保持收窄（避免误识别凭证/合同），
    凭证意图走 receipt_entry，其他走 general。
    """
    file_types = {a.get("file_type", "") for a in attachments if isinstance(a, dict)}

    user_lower = user_msg.lower() if user_msg else ""

    if any(t in ("pdf", "word", "excel") for t in file_types):
        if any(kw in user_lower for kw in ("合同", "contract", "录入")):
            return "contract_entry"
        if any(kw in user_lower for kw in ("凭证", "receipt", "转账", "收据")):
            return "receipt_entry"
        return "contract_entry"  # 文档文件默认当作合同，由子图 VL 二次判断

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

def make_finalize_node(agent):
    """通过 closure 注入 agent，使 finalize_node 能调用 _save_message 落库"""
    async def _finalize_node(state: RootState) -> dict:
        """结束节点：chat_history 落库（ADR #6）+ 清理 interrupt_info。

        消息类型映射（LangGraph → chat_history）：
          human   → role="user"       (_save_message)
          ai      → role="assistant"  (_save_message, 含 tool_calls)
          tool    → role="tool"       (save_tool_message)
          system  → 跳过不入库
        """
        session_id = state.get("session_id", "")
        for msg in state.get("messages", []):
            msg_type = getattr(msg, "type", None)
            try:
                if msg_type == "ai":
                    agent._save_message(
                        session_id, "assistant",
                        getattr(msg, "content", "") or "",
                        tool_calls=getattr(msg, "tool_calls", None),
                    )
                elif msg_type == "human":
                    agent._save_message(
                        session_id, "user", getattr(msg, "content", "") or ""
                    )
                elif msg_type == "tool":
                    agent.save_tool_message(
                        session_id,
                        getattr(msg, "tool_call_id", ""),
                        getattr(msg, "name", ""),
                        getattr(msg, "content", "") or "",
                    )
            except Exception:
                logger.warning(
                    "chat_history 落库跳过一条消息: type=%s session_id=%s",
                    msg_type, session_id, exc_info=True,
                )

        logger.info(
            "finalize_node 完成: session_id=%s msg_count=%d",
            session_id, len(state.get("messages", [])),
        )
        return {
            "should_end": True,
            "interrupt_info": None,
            "current_node": "finalize_node",
        }
    return _finalize_node


# 降级兜底节点（无 agent 注入时使用——例如测试场景）
async def finalize_node(state: RootState) -> dict:
    """结束节点（无 agent 版本）：仅清理 interrupt_info。

    生产环境应使用 make_finalize_node(agent) 版本以落库 chat_history。
    """
    logger.warning("finalize_node 无 agent 注入，跳过 chat_history 落库")
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

    当 endpoint 的 use_langgraph 判断允许非 pdf/word/excel 附件进入
    LangGraph 路径时（如未来扩展到图片附件），此节点会根据 intent 返回
    引导消息，避免用户收不到任何回复。

    Phase 2 将替换此占位为完整的 call_model → execute_tool ReAct 子图。
    """
    from langchain_core.messages import AIMessage

    intent = state.get("intent", "general")
    messages = []

    if intent == "receipt_entry":
        messages.append(AIMessage(content=(
            "凭证录入功能已迁移到合同列表卡片的「收」「支」按钮。\n"
            "请在合同列表页面找到对应合同，点击卡片上的按钮进行凭证录入。\n\n"
            "如果您需要查询付款信息，可以使用 query_payments 或 get_contract_detail 工具。"
        )))
    elif intent == "group_chat":
        messages.append(AIMessage(content=(
            "群聊关联功能正在开发中。\n"
            "您可以直接告诉我群聊名称和对应客户，我可以帮您通过 update_contract 关联群聊信息。"
        )))
    else:
        # 通用对话：无附件文本消息理论上不会进入此节点
        # （endpoint 的 use_langgraph 会走旧 ReAct），但作为兜底
        messages.append(AIMessage(content="请告诉我您需要什么帮助？"))

    return {
        "messages": messages,
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


def build_root_graph(contract_entry_app, checkpointer=None, agent=None) -> StateGraph:
    """编译 Root Graph，注册合同录入子图。

    Args:
        contract_entry_app: ContractEntrySubgraph.build() 的返回值
        checkpointer: AsyncPostgresSaver 实例
        agent: ContractAgent 实例（注入 finalize_node 用于 chat_history 落库）
    """
    workflow = StateGraph(RootState)

    # 通用对话子图（Phase 1 占位）
    general_app = build_general_chat_subgraph()

    # 添加节点
    workflow.add_node("intake_node", intake_node)
    workflow.add_node("contract_entry_subgraph", contract_entry_app)
    workflow.add_node("general_chat_subgraph", general_app)
    # finalize_node: 生产环境注入 agent 落库，否则使用无 agent 版本
    if agent is not None:
        workflow.add_node("finalize_node", make_finalize_node(agent))
    else:
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
