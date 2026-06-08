"""Root Graph — LangGraph 顶层编排

Phase 1：intake_node → route_by_intent → contract_entry_subgraph → finalize_node
Phase 2：凭证引导 / 群聊 / 通用对话子图接入

ADR #5：直接使用 AsyncPostgresSaver
ADR #2：不引入 ChatOpenAI，继续用 DashScopeAgentClient
"""
import logging
from typing import Optional, Literal

from langgraph.graph import StateGraph, START, END

from app.ai.orchestrator.state import RootState

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
        if any(kw in user_lower for kw in ("群聊", "微信群", "group", "群")):
            return "group_chat"
        return "general"  # 图片不确定用途，走通用对话

    return "general"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 条件边：根据 intent 路由到子图
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def route_by_intent(state: RootState) -> Literal[
    "contract_entry_subgraph",
    "general_chat_subgraph",
    "receipt_entry_subgraph",
    "receipt_entry_node",
    "group_chat_node",
]:
    """根据 intent 和 mode 路由到对应子图/节点（Phase 2.6 完整路由矩阵）。

    路由矩阵：
      intent             | mode                        | 路由目标
      contract_entry     | chat                        | contract_entry_subgraph
      receipt_entry      | receipt_income/receipt_expense | receipt_entry_subgraph（完整子图）
      receipt_entry      | 其他                         | receipt_entry_node（降级引导）
      group_chat         | *                           | group_chat_node（降级引导）
      general            | *                           | general_chat_subgraph
    """
    intent = state.get("intent", "general")
    mode = state.get("executor_mode", "chat")

    if intent == "contract_entry" and mode == "chat":
        return "contract_entry_subgraph"

    if intent == "receipt_entry":
        if mode in ("receipt_income", "receipt_expense"):
            return "receipt_entry_subgraph"
        return "receipt_entry_node"

    if intent == "group_chat":
        return "group_chat_node"

    return "general_chat_subgraph"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 节点：结束（chat_history 落库 + SSE done 事件）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def make_finalize_node(agent):
    """通过 closure 注入 agent，使 finalize_node 能调用 _save_message 落库。

    ⚠️ 幂等性契约（finalize_node 只应在单次图执行中调用一次）：
    当前架构保证 finalize_node 在所有子图完成后只执行一次，不存在重复入库风险。
    但如果未来重构导致 finalize_node 被多次调用（例如 Root Graph 加了循环边），
    state["messages"] 中的消息会被重复写入 chat_history，产生重复消息。
    此时应在 _save_message 中增加幂等性检查（如基于 content hash 去重），
    或在 finalize_node 中引入 state["_finalized"] 标记跳过二次执行。
    """
    async def _finalize_node(state: RootState) -> dict:
        """结束节点：chat_history 落库（ADR #6）+ 清理 interrupt_info。

        消息类型映射（LangGraph → chat_history）：
          human   → role="user"       (_save_message)
          ai      → role="assistant"  (_save_message, 含 tool_calls)
          tool    → role="tool"       (save_tool_message)
          system  → 跳过不入库
        """
        # 幂等性防护：如果 _finalized 标记已存在，跳过落库（防止重构引入的重复执行）
        if state.get("_finalized"):
            logger.warning(
                "finalize_node 检测到重复执行，跳过 chat_history 落库: session_id=%s",
                state.get("session_id", ""),
            )
            return {
                "should_end": True,
                "interrupt_info": None,
                "current_node": "finalize_node",
            }

        session_id = state.get("session_id", "")
        for msg in state.get("messages", []):
            msg_type = getattr(msg, "type", None)
            # auto_filled: HumanMessage.additional_kwargs 上的标记，标识系统补全的
            # ""请分析文件...""提示词（用户实际没输入），写入 metadata 便于历史回看
            auto_filled = bool(getattr(msg, "additional_kwargs", {}).get("auto_filled", False))
            user_metadata = {"auto_filled": True} if auto_filled else None
            try:
                if msg_type == "ai":
                    agent._save_message(
                        session_id, "assistant",
                        getattr(msg, "content", "") or "",
                        tool_calls=getattr(msg, "tool_calls", None),
                    )
                elif msg_type == "human":
                    agent._save_message(
                        session_id, "user",
                        getattr(msg, "content", "") or "",
                        metadata=user_metadata,
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
            "_finalized": True,  # 幂等性标记：防止重复执行导致 chat_history 重复入库
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
# 凭证引导降级节点（Phase 2.1 占位，引导用户到卡片按钮）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def receipt_entry_node(state: RootState) -> dict:
    """凭证录入引导：Phase 2.1 降级节点。

    凭证录入已迁移到合同列表卡片的「收」「支」按钮，此处引导用户切换入口。
    仍可通过 query_payments / get_payment_summary 等工具查询付款信息。
    """
    from langchain_core.messages import AIMessage

    return {
        "messages": [AIMessage(content=(
            "凭证录入功能已迁移到合同列表卡片的「收」「支」按钮。\n"
            "请在合同列表页面找到对应合同，点击卡片上的按钮进行凭证录入。\n\n"
            "如果您需要查询付款信息，可以直接告诉我合同编号或客户姓名，我帮您查询。"
        ))],
        "should_end": True,
        "current_node": "receipt_entry_node",
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 群聊关联降级节点（Phase 2.3 占位，引导用户手动关联）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def group_chat_node(state: RootState) -> dict:
    """群聊关联：Phase 2.3 降级节点。

    用户上传微信群截图时，引导用户提供群名和业务信息，
    通过 update_contract 工具手动关联 wechat_group 字段。
    """
    from langchain_core.messages import AIMessage

    return {
        "messages": [AIMessage(content=(
            "群聊关联功能：请告诉我微信群名称和对应的客户姓名或合同编号，"
            "我可以帮您将群聊信息关联到合同记录中。\n\n"
            "例如：「微信群 港车交流群 对应客户 张三」"
        ))],
        "should_end": True,
        "current_node": "group_chat_node",
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 构建 Root Graph
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def build_root_graph(
    contract_entry_app,
    general_chat_app=None,
    checkpointer=None,
    agent=None,
    db=None,
    user=None,
    session_context: Optional[dict] = None,
    session_id: str = "",
) -> StateGraph:
    """编译 Root Graph，注册 4 个子图/节点（Phase 2.6 完整编排）。

    Args:
        contract_entry_app: ContractEntrySubgraph.build() 的返回值
        general_chat_app: GeneralChatSubgraph.build() 的返回值（可选，None 时自建）
        checkpointer: AsyncPostgresSaver 实例
        agent: ContractAgent 实例（注入 finalize_node 用于 chat_history 落库）
        db / user: 数据库会话和用户（用于自建通用对话子图）
        session_context / session_id: ToolExecutor 上下文
    """
    from app.ai.orchestrator.general_chat import GeneralChatSubgraph
    from app.ai.orchestrator.receipt_entry import ReceiptEntrySubgraph

    workflow = StateGraph(RootState)

    # 通用对话子图：优先使用外部注入，否则自建
    if general_chat_app is None and db is not None and user is not None:
        general_chat = GeneralChatSubgraph(
            db, user, session_context=session_context, session_id=session_id,
        )
        general_chat_app = general_chat.build(checkpointer=checkpointer)

    # 凭证录入子图（收入/支出统一）
    receipt_entry = ReceiptEntrySubgraph(
        db, user,
        mode=session_context.get("mode", "chat") if session_context else "chat",
        session_context=session_context or {},
        session_id=session_id,
    )
    receipt_entry_app = receipt_entry.build(checkpointer=checkpointer)

    # 添加节点
    workflow.add_node("intake_node", intake_node)
    workflow.add_node("contract_entry_subgraph", contract_entry_app)
    workflow.add_node("general_chat_subgraph", general_chat_app)
    workflow.add_node("receipt_entry_subgraph", receipt_entry_app)
    workflow.add_node("receipt_entry_node", receipt_entry_node)
    workflow.add_node("group_chat_node", group_chat_node)

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
            "receipt_entry_subgraph": "receipt_entry_subgraph",
            "receipt_entry_node": "receipt_entry_node",
            "group_chat_node": "group_chat_node",
        },
    )

    workflow.add_edge("contract_entry_subgraph", "finalize_node")
    workflow.add_edge("general_chat_subgraph", "finalize_node")
    workflow.add_edge("receipt_entry_subgraph", "finalize_node")
    workflow.add_edge("receipt_entry_node", "finalize_node")
    workflow.add_edge("group_chat_node", "finalize_node")
    workflow.add_edge("finalize_node", END)

    return workflow.compile(checkpointer=checkpointer)
