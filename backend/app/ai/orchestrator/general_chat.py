"""通用对话子图（Phase 2.4 — ADR #3 自建 StateGraph）

替代旧 ReAct 循环，支持 20 个工具的开放对话。

节点清单：
  1. call_model_node      — 调 DashScopeAgentClient，手动解析 tool_calls
  2. execute_tool_node    — 调 ToolExecutor.execute()
  3. should_continue      — 路由：有 tool_calls → execute_tool_node，否则 → END

设计原则：
  - 不依赖 langgraph.prebuilt.create_react_agent（已废弃）
  - 不引入 langchain-openai / ChatOpenAI（ADR #2）
  - 消息格式转换：LangChain BaseMessage ↔ OpenAI dict（在 call_model_node 内部完成）
"""
import asyncio
import json
import logging
from datetime import date
from typing import Literal, Optional

from langgraph.graph import StateGraph, START, END
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage, SystemMessage

from app.ai.orchestrator.state import GeneralChatState
from app.ai.tools import TOOL_DEFINITIONS, ToolExecutor
from app.ai.llm_client import DashScopeAgentClient
from app.ai.prompts import build_system_prompt
from app.config import settings

logger = logging.getLogger(__name__)


def _default_llm_client():
    """懒加载默认 LLM 客户端（避免模块级绑定 settings）。

    生产环境走 DashScopeAgentClient；单测可注入 mock。
    """
    return DashScopeAgentClient()


class GeneralChatSubgraph:
    """通用对话子图工厂。

    通过构造函数注入 db / user 依赖，返回编译后的子图。
    """
    def __init__(self, db, user, session_context: Optional[dict] = None,
                 session_id: str = "", llm_client=None):
        self.db = db
        self.user = user
        # llm_client 可选注入：None 时 build() 内部懒加载，避免模块级绑定 settings
        self._llm_client = llm_client
        self.executor = ToolExecutor(db, user)
        self.executor.mode = "chat"
        self.executor.session_context = session_context or {}
        self.executor.session_id = session_id


    def build(self, checkpointer=None) -> StateGraph:
        """编译通用对话子图

        llm_client 在 build 时确定优先级：构造注入 > 懒加载默认。
        闭包捕获避免节点内每次调用都重复 resolve。
        """
        executor = self.executor
        user = self.user
        llm_client = self._llm_client or _default_llm_client()

        async def call_model_node(state: GeneralChatState) -> dict:
            """调用 DashScopeAgentClient，将 LangChain 消息转为 OpenAI 格式发送。

            强制 max_iterations：超过 settings.AGENT_MAX_ITERATIONS 时跳过 LLM 调用，
            直接返回总结提示，避免无限循环。
            """
            iteration = state.get("iteration_count", 0)
            if iteration >= settings.AGENT_MAX_ITERATIONS:
                logger.warning(
                    "通用对话达到最大迭代次数 %d，强制终止: session=%s",
                    settings.AGENT_MAX_ITERATIONS, state.get("session_id", ""),
                )
                return {
                    "messages": [AIMessage(
                        content="已达到最大对话轮次，请开启新会话继续操作。"
                    )],
                    "should_end": True,
                    "current_node": "call_model_node",
                }

            # LangChain → OpenAI 格式转换
            openai_messages = _convert_messages(state.get("messages", []), user)

            full_text = ""
            tool_calls = []

            try:
                async for event in llm_client.chat_completion_stream(
                    messages=openai_messages,
                    tools=TOOL_DEFINITIONS,
                ):
                    if event["type"] == "text":
                        full_text += event["content"]
                    elif event["type"] == "tool_call":
                        tool_calls.append({
                            "id": event["id"],
                            "name": event["name"],
                            "arguments": event["arguments"],
                        })
            except Exception as e:
                logger.exception("通用对话 LLM 调用异常")
                return {
                    "messages": [AIMessage(
                        content=f"抱歉，AI 服务暂时不可用，请稍后重试。（错误: {e}）"
                    )],
                    "should_end": True,
                    "errors": [str(e)],
                    "current_node": "call_model_node",
                }

            if tool_calls:
                # 有工具调用 → 返回 AIMessage(含 tool_calls)，路由到 execute_tool_node
                lc_tool_calls = [
                    {
                        "id": tc["id"],
                        "type": "function",
                        "function": {"name": tc["name"], "arguments": tc["arguments"]},
                    }
                    for tc in tool_calls
                ]
                return {
                    "messages": [AIMessage(
                        content=full_text or None,
                        tool_calls=lc_tool_calls,
                    )],
                    "iteration_count": iteration + 1,
                    "current_node": "call_model_node",
                }

            # 无工具调用 → 对话结束
            return {
                "messages": [AIMessage(content=full_text)],
                "iteration_count": iteration + 1,
                "should_end": True,
                "current_node": "call_model_node",
            }

        def should_continue(state: GeneralChatState) -> Literal["execute_tool_node", "__end__"]:
            """路由：最后一条消息有 tool_calls → execute_tool_node，否则 END"""
            if state.get("should_end"):
                return "__end__"
            last = state["messages"][-1] if state.get("messages") else None
            if last and getattr(last, "tool_calls", None):
                return "execute_tool_node"
            return "__end__"

        async def execute_tool_node(state: GeneralChatState) -> dict:
            """执行工具调用，结果作为 ToolMessage 返回。

            复用 ToolExecutor 内置的 mode guard 和 document guard。
            单个工具执行失败不中断整批，错误信息作为 ToolMessage 回灌。
            """
            last_msg = state["messages"][-1]
            if not getattr(last_msg, "tool_calls", None):
                return {}

            tool_messages = []
            for tc in last_msg.tool_calls:
                tool_name = tc["function"]["name"]
                try:
                    args = (
                        json.loads(tc["function"]["arguments"])
                        if isinstance(tc["function"]["arguments"], str)
                        else tc["function"]["arguments"]
                    )
                except json.JSONDecodeError:
                    args = {}

                try:
                    result = await asyncio.to_thread(executor.execute, tool_name, args)
                    logger.info("通用对话工具结果: %s → %s", tool_name,
                                result[:200] if result else "empty")
                except Exception as e:
                    result = f"工具执行出错: {tool_name} → {e}"
                    logger.warning(result, exc_info=True)

                tool_messages.append(ToolMessage(
                    content=result,
                    tool_call_id=tc["id"],
                ))

            return {
                "messages": tool_messages,
                "current_node": "execute_tool_node",
            }

        # 构建子图
        workflow = StateGraph(GeneralChatState)
        workflow.add_node("call_model_node", call_model_node)
        workflow.add_node("execute_tool_node", execute_tool_node)

        workflow.add_edge(START, "call_model_node")
        workflow.add_conditional_edges("call_model_node", should_continue, {
            "execute_tool_node": "execute_tool_node",
            "__end__": END,
        })
        workflow.add_edge("execute_tool_node", "call_model_node")

        return workflow.compile(checkpointer=checkpointer)


def _convert_messages(messages: list, user) -> list:
    """将 LangChain BaseMessage 列表转为 OpenAI 格式消息列表。

    注入 system prompt（用户角色 + 日期）。
    """
    system_content = build_system_prompt(
        user_name=user.full_name or user.username,
        user_role=user.role,
        current_date=date.today().isoformat(),
    )
    result = [{"role": "system", "content": system_content}]

    for msg in messages:
        if isinstance(msg, SystemMessage):
            # 重复 system prompt 防御：若已注入过自动构造的 system，用用户传入的覆盖
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
            item = {"role": "assistant", "content": msg.content or None}
            tool_calls = getattr(msg, "tool_calls", None)
            if tool_calls:
                # 统一转为 OpenAI 格式，兼容两种输入：
                #   LangChain 格式: {"name": "x", "args": {...}, "id": "..."}
                #   OpenAI 格式:    {"type": "function", "function": {"name": "x", "arguments": "..."}, "id": "..."}
                oai_calls = []
                for tc in tool_calls:
                    if "function" in tc:
                        # 已是 OpenAI 格式，直接用
                        oai_calls.append(tc)
                    else:
                        # LangChain 格式 → OpenAI
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
