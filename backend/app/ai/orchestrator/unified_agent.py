"""统一 Agent Graph v2 — 单层 Agent 循环

替代原 Root Graph + 4 子图架构。

节点：
  1. prepare_node         — 构建 initial messages（含附件元信息）
  2. call_model_node      — LLM 推理（将决定调哪个工具）
  3. execute_tool_node    — 执行工具 + 轻量确认防护
  4. finalize_node        — chat_history 落库

设计原则：
  - 无意图推断路由 — LLM 通过 analyze_files 工具自主决定
  - 无子图 — 单一 Agent 循环
  - 无 mode guard / document guard — 工具集合简洁，无需模式锁定
  - 轻量确认 — 写入工具前检查 LLM 上文是否展示计划
"""
import asyncio
import json
import logging
from datetime import date
from typing import Optional, Literal

from langgraph.graph import StateGraph, START, END
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage, SystemMessage
from langchain_core.callbacks.manager import adispatch_custom_event

from app.ai.orchestrator.state_v2 import AgentState
from app.ai.tools_v2 import TOOL_DEFINITIONS, ToolExecutorV2
from app.ai.llm_client import DashScopeAgentClient
from app.ai.prompts_v2 import build_system_prompt
from app.config import settings

logger = logging.getLogger(__name__)

# 需要确认的写入工具
_WRITABLE_TOOLS = frozenset({
    "create_customer", "create_contract",
    "create_payment_record", "match_and_confirm_payment",
    "update_payment",
})


def _default_llm_client():
    return DashScopeAgentClient()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 轻量确认：检查 LLM 上文是否已展示计划并请求确认
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

_CONFIRM_KEYWORDS = frozenset({
    "确认", "是否", "同意", "继续", "对吗", "正确吗",
    "确认吗", "可以吗", "行吗",
})


def _has_confirmation_in_context(messages: list, current_tool_name: str = "") -> bool:
    """检查 LLM 上文是否已在「之前轮次」展示过计划并请求确认。

    关键约束：排除当前轮 AIMessage（可能同时含确认文字 + tool_calls），
    只检查之前的消息。防止 LLM 在同一回复中输出"是否确认？"+ tool_calls 绕过防护。

    Args:
        messages: 完整消息列表
        current_tool_name: 当前工具名（仅用于日志，不影响判断逻辑）
    """
    # 找到最后一条 HumanMessage 的位置（用户最新输入）
    last_human_idx = -1
    for i in range(len(messages) - 1, -1, -1):
        if isinstance(messages[i], HumanMessage):
            last_human_idx = i
            break

    # 只检查 last_human_idx 之前的 AIMessage（即「上一轮」LLM 的回复）
    # 不检查当前轮（last_human_idx 之后）的 AIMessage，防止同轮 tool_calls 自确认
    for i in range(last_human_idx + 1 if last_human_idx >= 0 else 0, len(messages)):
        msg = messages[i]
        if not isinstance(msg, AIMessage):
            continue
        content = (msg.content or "").lower()
        if any(kw in content for kw in _CONFIRM_KEYWORDS):
            return True
    return False


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# LangChain → OpenAI 消息格式转换
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _convert_messages(messages: list, user, attachments: list = None) -> list:
    """将 LangChain BaseMessage 列表转为 OpenAI 格式消息列表。"""
    system_content = build_system_prompt(
        user_name=user.full_name or user.username,
        user_role=user.role,
        current_date=date.today().isoformat(),
    )
    result = [{"role": "system", "content": system_content}]

    for msg in messages:
        if isinstance(msg, SystemMessage):
            if result and result[0].get("role") == "system":
                result[0] = {"role": "system", "content": msg.content}
            else:
                result.insert(0, {"role": "system", "content": msg.content})
        elif isinstance(msg, HumanMessage):
            content = msg.content
            if isinstance(content, list):
                content = " ".join(str(p) for p in content)
            result.append({"role": "user", "content": content})
        elif isinstance(msg, AIMessage):
            item: dict = {"role": "assistant", "content": msg.content or None}
            tool_calls = getattr(msg, "tool_calls", None)
            if tool_calls:
                oai_calls = []
                for tc in tool_calls:
                    if "function" in tc:
                        oai_calls.append(tc)
                    else:
                        args = tc.get("args", {})
                        oai_calls.append({
                            "id": tc.get("id", ""),
                            "type": "function",
                            "function": {
                                "name": tc.get("name", ""),
                                "arguments": json.dumps(args) if isinstance(args, dict) else str(args),
                            },
                        })
                item["tool_calls"] = oai_calls
            result.append(item)
        elif isinstance(msg, ToolMessage):
            result.append({
                "role": "tool",
                "content": msg.content,
                "tool_call_id": getattr(msg, "tool_call_id", ""),
            })

    return result


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 构建统一 Agent Graph
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class UnifiedAgentGraph:
    """统一 Agent 图工厂。

    通过构造函数注入 db / user，返回编译后的图。
    """

    def __init__(self, db, user, llm_client=None):
        self.db = db
        self.user = user
        self._llm_client = llm_client

    def build(self):
        """编译统一 Agent 图"""
        db = self.db
        user = self.user
        llm_client = self._llm_client or _default_llm_client()
        executor = ToolExecutorV2(db, user)

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 节点 1：LLM 推理
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

        async def call_model_node(state: AgentState) -> dict:
            """调用 LLM，决定下一步操作"""
            iteration = state.get("iteration_count", 0)
            if iteration >= settings.AGENT_MAX_ITERATIONS:
                logger.warning(
                    "Agent 达到最大迭代次数 %d，强制终止: session=%s",
                    settings.AGENT_MAX_ITERATIONS, state.get("session_id", ""),
                )
                return {
                    "messages": [AIMessage(content="已达到最大对话轮次，请开启新会话继续操作。")],
                    "should_end": True,
                }

            # 附件上下文注入：把 state.attachments 信息追加到用户消息
            msgs = list(state.get("messages", []))
            attachments = state.get("attachments", [])
            if attachments and msgs:
                for i in range(len(msgs) - 1, -1, -1):
                    if isinstance(msgs[i], HumanMessage):
                        ctx_parts = [f"\n\n[附件: {len(attachments)} 个文件]"]
                        for att in attachments:
                            fid = att.get("file_id", "") if isinstance(att, dict) else getattr(att, "file_id", "")
                            ftype = att.get("file_type", "") if isinstance(att, dict) else getattr(att, "file_type", "")
                            fname = att.get("file_name", "") if isinstance(att, dict) else getattr(att, "file_name", "")
                            ctx_parts.append(f"- file_id={fid}, file_type={ftype}, file_name={fname}")
                        msgs[i] = HumanMessage(
                            content=(msgs[i].content or "") + "\n".join(ctx_parts),
                            id=msgs[i].id,
                        )
                        break

            openai_messages = _convert_messages(msgs, user, attachments)

            full_text = ""
            tool_calls = []

            try:
                async for event in llm_client.chat_completion_stream(
                    messages=openai_messages,
                    tools=TOOL_DEFINITIONS,
                ):
                    if event["type"] == "text":
                        full_text += event["content"]
                        await adispatch_custom_event("text_chunk", {"content": event["content"]})
                    elif event["type"] == "tool_call":
                        tool_calls.append({
                            "id": event["id"],
                            "name": event["name"],
                            "arguments": event["arguments"],
                        })
            except Exception as e:
                logger.exception("LLM 调用异常")
                return {
                    "messages": [AIMessage(content=f"抱歉，AI 服务暂时不可用，请稍后重试。（错误: {e}）")],
                    "should_end": True,
                    "errors": [str(e)],
                }

            if tool_calls:
                lc_tool_calls = []
                for tc in tool_calls:
                    try:
                        args = json.loads(tc["arguments"]) if isinstance(tc["arguments"], str) else tc["arguments"]
                    except (json.JSONDecodeError, TypeError):
                        args = {}
                    lc_tool_calls.append({
                        "name": tc["name"],
                        "args": args,
                        "id": tc["id"],
                    })
                return {
                    "messages": [AIMessage(content=full_text or None, tool_calls=lc_tool_calls)],
                    "iteration_count": iteration + 1,
                }

            # 无工具调用 → 对话结束
            return {
                "messages": [AIMessage(content=full_text)],
                "iteration_count": iteration + 1,
                "should_end": True,
            }

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 节点 2：执行工具（含轻量确认防护）
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

        async def execute_tool_node(state: AgentState) -> dict:
            """执行工具调用。

            写入工具执行前检查 LLM 上文是否展示过确认请求。
            未展示 → 返回错误让 LLM 先确认。
            """
            last_msg = state["messages"][-1]
            if not getattr(last_msg, "tool_calls", None):
                return {}

            tool_messages = []
            for tc in last_msg.tool_calls:
                tool_name = tc["name"]
                try:
                    args = tc["args"] if isinstance(tc["args"], dict) else (
                        json.loads(tc["args"]) if isinstance(tc["args"], str) else {}
                    )
                except json.JSONDecodeError:
                    args = {}

                # ── 轻量确认防护 ──
                if tool_name in _WRITABLE_TOOLS:
                    if not _has_confirmation_in_context(state.get("messages", [])):
                        logger.warning("确认防护拦截: tool=%s（上文无确认询问）", tool_name)
                        tool_messages.append(ToolMessage(
                            content=json.dumps({
                                "error": f"请先向用户展示操作计划并请求确认后，再调用 {tool_name}。",
                                "tool": tool_name,
                                "hint": "你应该先回复用户（不调任何写入工具），列出将要创建/修改的内容（客户名、金额、业务类型），"
                                        "明确问「是否确认？」，等用户回复「确认」后再在下一轮调用此工具。",
                            }, ensure_ascii=False),
                            tool_call_id=tc["id"],
                        ))
                        continue

                # ── 执行工具 ──
                try:
                    result = await asyncio.to_thread(executor.execute, tool_name, args)
                except Exception as e:
                    result = f"工具执行出错: {tool_name} → {e}"
                    logger.warning(result, exc_info=True)

                tool_messages.append(ToolMessage(
                    content=result,
                    tool_call_id=tc["id"],
                ))

            return {"messages": tool_messages}

        # ── 路由 ──

        def should_continue(state: AgentState) -> Literal["execute_tool_node", "finalize_node"]:
            """有 tool_calls → execute_tool_node，否则 finalize_node"""
            if state.get("should_end"):
                return "finalize_node"
            last = state["messages"][-1] if state.get("messages") else None
            if last and getattr(last, "tool_calls", None):
                return "execute_tool_node"
            return "finalize_node"

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 构建图
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

        workflow = StateGraph(AgentState)

        workflow.add_node("call_model_node", call_model_node)
        workflow.add_node("execute_tool_node", execute_tool_node)
        workflow.add_node("finalize_node", self._make_finalize_node())

        workflow.add_edge(START, "call_model_node")
        workflow.add_conditional_edges("call_model_node", should_continue, {
            "execute_tool_node": "execute_tool_node",
            "finalize_node": "finalize_node",
        })
        workflow.add_edge("execute_tool_node", "call_model_node")
        workflow.add_edge("finalize_node", END)

        return workflow  # 不 compile，由调用方传入 checkpointer 后 compile

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # finalize_node：chat_history 落库
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def _make_finalize_node(self):
        """创建 finalize_node（闭包捕获 db 和 user）"""
        db = self.db
        user = self.user

        async def _finalize_node(state: AgentState) -> dict:
            if state.get("_finalized"):
                return {"should_end": True, "_finalized": True}

            from app.models.chat_history import ChatHistory

            session_id = state.get("session_id", "")
            for msg in state.get("messages", []):
                msg_type = getattr(msg, "type", None)
                auto_filled = bool(getattr(msg, "additional_kwargs", {}).get("auto_filled", False))
                user_metadata = {"auto_filled": True} if auto_filled else None
                try:
                    if msg_type == "ai":
                        record = ChatHistory(
                            user_id=user.id, session_id=session_id,
                            question="", answer=getattr(msg, "content", "") or "",
                            role="assistant",
                            tool_calls=getattr(msg, "tool_calls", None),
                            llm_model=settings.SILICONFLOW_AGENT_MODEL,
                        )
                        db.add(record)
                    elif msg_type == "human":
                        record = ChatHistory(
                            user_id=user.id, session_id=session_id,
                            question=getattr(msg, "content", "") or "", answer=None,
                            role="user",
                            extra_metadata=user_metadata or {},
                            llm_model=settings.SILICONFLOW_AGENT_MODEL,
                        )
                        db.add(record)
                    elif msg_type == "tool":
                        record = ChatHistory(
                            user_id=user.id, session_id=session_id,
                            question="", answer=getattr(msg, "content", "") or "",
                            role="tool",
                            intent_type=getattr(msg, "name", ""),
                            extra_metadata={"tool_call_id": getattr(msg, "tool_call_id", "")},
                            llm_model=settings.SILICONFLOW_AGENT_MODEL,
                        )
                        db.add(record)
                except Exception:
                    logger.warning("chat_history 落库跳过: type=%s session_id=%s", msg_type, session_id, exc_info=True)

            db.commit()
            logger.info("finalize_node 完成: session_id=%s msg_count=%d", session_id, len(state.get("messages", [])))
            return {"should_end": True, "_finalized": True}

        return _finalize_node


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 便捷函数：直接编译图
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def build_unified_agent(db, user, llm_client=None):
    """构建统一 Agent 图（便捷函数）"""
    graph_factory = UnifiedAgentGraph(db, user, llm_client)
    return graph_factory.build()
