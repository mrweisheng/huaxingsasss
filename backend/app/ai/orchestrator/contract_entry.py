"""合同录入子图（Agent 循环架构）

取代旧的 9 节点确定性 DAG，改为 Agent 推理循环 + interrupt 安全门。

架构：
  analyze_file_node → call_model_node ↔ execute_tool_node → END
                           ↑                    ↓
                           └────────────────────┘

- analyze_file_node: 调 ContractAnalyzer 提取结构化数据，注入 messages
- call_model_node:   LLM 推理（决定展示什么、调什么工具、何时结束）
- execute_tool_node: 执行工具调用，敏感工具（create_customer/create_contract）
                     触发 interrupt 安全门，用户确认后放行

设计原则：
  - Agent 是决策者：根据业务类型自行判断展示哪些字段
  - 工具是执行者：search_customers / create_contract 等越确定性越好
  - interrupt 是安全门：防止 LLM 跳过确认直接执行高危操作
"""
import asyncio
import json
import logging
import uuid
from datetime import date
from typing import Optional, Literal

from langgraph.graph import StateGraph, START, END
from langgraph.types import interrupt
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage, SystemMessage

from app.ai.orchestrator.state import ContractEntryState
from app.ai.tools import TOOL_DEFINITIONS, ToolExecutor
from app.ai.llm_client import DashScopeAgentClient
from app.ai.prompts import CONTRACT_ENTRY_PROMPT, build_system_prompt
from app.services.contract_analyzer import ContractAnalyzer
from app.config import settings

logger = logging.getLogger(__name__)

# 需要用户确认才能执行的敏感工具
_SENSITIVE_TOOLS = {"create_customer", "create_contract"}


def _default_llm_client():
    """懒加载默认 LLM 客户端"""
    return DashScopeAgentClient()


class ContractEntrySubgraph:
    """合同录入子图工厂。

    通过 closure 注入 db / user 依赖，返回编译后的子图。
    """

    def __init__(self, db, user, mode: str = "chat",
                 session_context: Optional[dict] = None, session_id: str = "",
                 llm_client=None):
        self.db = db
        self.user = user
        self.executor = ToolExecutor(db, user)
        self.executor.mode = mode
        self.executor.session_context = session_context or {}
        self.executor.session_id = session_id
        self._llm_client = llm_client

    def build(self, checkpointer=None) -> StateGraph:
        """编译合同录入子图"""
        executor = self.executor
        user = self.user
        llm_client = self._llm_client or _default_llm_client()

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 节点 1：分析文件（确定性工具，无 LLM 推理）
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

        async def analyze_file_node(state: ContractEntryState) -> dict:
            """解析附件 → ContractAnalyzer 提取数据 → 注入 messages 供 Agent 读取"""
            attachments = state.get("attachments", [])

            if not attachments:
                return {
                    "current_node": "analyze_file_node",
                    "errors": ["无附件"],
                    "messages": [AIMessage(content="未检测到附件，请重新上传合同文件。")],
                    "should_end": True,
                }

            att = attachments[0]
            file_id = att.get("file_id", "")

            if not file_id:
                return {
                    "current_node": "analyze_file_node",
                    "errors": ["无效的 file_id"],
                    "messages": [AIMessage(content="文件 ID 无效，请重新上传。")],
                    "should_end": True,
                }

            # 解析文件路径
            file_path = ContractAnalyzer.resolve_file_path(file_id, user.id)
            if not file_path:
                return {
                    "current_node": "analyze_file_node",
                    "errors": [f"文件不存在: {file_id}"],
                    "messages": [AIMessage(content=f"文件未找到，请重新上传。")],
                    "should_end": True,
                }

            # 调 ContractAnalyzer（同步方法，asyncio.to_thread 包装）
            result = await asyncio.to_thread(
                ContractAnalyzer.analyze_file, file_path, executor.db, user.id
            )

            if result.get("duplicate_detected"):
                existing = result.get("existing_contract", {})
                msg = (
                    f"该文件之前已创建过合同：\n"
                    f"- 编号：{existing.get('contract_number', '?')}\n"
                    f"- 客户：{existing.get('customer_name', '?')}\n"
                    f"- 金额：{existing.get('total_amount', '?')} {existing.get('currency', '')}\n\n"
                    f"无需重复录入。如需查看，请在合同列表中搜索。"
                )
                return {
                    "current_node": "analyze_file_node",
                    "messages": [AIMessage(content=msg)],
                    "should_end": True,
                }

            if not result.get("success"):
                return {
                    "current_node": "analyze_file_node",
                    "errors": [result.get("error", "分析失败")],
                    "messages": [AIMessage(content=f"文件分析失败：{result.get('error', '未知错误')}。请检查文件格式或重新上传。")],
                    "should_end": True,
                }

            # 提取成功：将完整分析数据注入 messages
            analysis_data = result["data"]
            file_type = result.get("file_type", "unknown")
            confidence = analysis_data.get("confidence")

            # 构建注入消息：文件元信息 + 完整 JSON 数据
            analysis_msg = (
                f"[文件分析结果]\n"
                f"file_id: {file_id}\n"
                f"file_type: {file_type}\n"
                f"confidence: {confidence}\n"
                f"---\n"
                f"{json.dumps(analysis_data, ensure_ascii=False)}"
            )

            # 构建增量消息（add_messages reducer 会合并到 state）
            # auto_filled：用相同 ID 替换系统补全的空提示；否则追加新消息
            new_messages = []
            existing = state.get("messages", [])
            if existing and isinstance(existing[-1], HumanMessage):
                last = existing[-1]
                auto_filled = getattr(last, "additional_kwargs", {}).get("auto_filled", False)
                if auto_filled:
                    # 同 ID 替换：add_messages 检测到相同 ID 会替换而非追加
                    new_messages.append(HumanMessage(content=analysis_msg, id=last.id))
                else:
                    new_messages.append(HumanMessage(content=analysis_msg))
            else:
                new_messages.append(HumanMessage(content=analysis_msg))

            logger.info(
                "contract_entry.analyze_file: file_id=%s type=%s confidence=%s",
                file_id, file_type, confidence,
            )

            return {
                "current_node": "analyze_file_node",
                "messages": new_messages,
                "file_context": json.dumps(analysis_data, ensure_ascii=False),
                "iteration_count": state.get("iteration_count", 0) + 1,
            }

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 节点 2：LLM 推理（Agent 大脑）
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

        async def call_model_node(state: ContractEntryState) -> dict:
            """调用 LLM，让 Agent 决定：展示什么、调什么工具、还是结束对话"""
            iteration = state.get("iteration_count", 0)
            if iteration >= settings.AGENT_MAX_ITERATIONS:
                logger.warning(
                    "合同录入达到最大迭代次数 %d，强制终止: session=%s",
                    settings.AGENT_MAX_ITERATIONS, state.get("session_id", ""),
                )
                return {
                    "messages": [AIMessage(
                        content="已达到最大对话轮次，请开启新会话继续操作。"
                    )],
                    "should_end": True,
                    "current_node": "call_model_node",
                }

            # 转换消息格式：LangChain → OpenAI
            openai_messages = _convert_messages(
                state.get("messages", []), user
            )

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
                logger.exception("合同录入 LLM 调用异常")
                return {
                    "messages": [AIMessage(
                        content=f"抱歉，AI 服务暂时不可用，请稍后重试。（错误: {e}）"
                    )],
                    "should_end": True,
                    "errors": [str(e)],
                    "current_node": "call_model_node",
                }

            if tool_calls:
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

            # 无工具调用 → Agent 认为对话结束（比如已展示分析结果等用户回复）
            return {
                "messages": [AIMessage(content=full_text)],
                "iteration_count": iteration + 1,
                "current_node": "call_model_node",
                "should_end": True,
            }

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 路由：call_model → execute_tool 或 END
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

        def should_continue(state: ContractEntryState) -> Literal["execute_tool_node", "__end__"]:
            """有 tool_calls → execute_tool_node，否则 END"""
            if state.get("should_end"):
                return "__end__"
            last = state["messages"][-1] if state.get("messages") else None
            if last and getattr(last, "tool_calls", None):
                return "execute_tool_node"
            return "__end__"

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 节点 3：执行工具（含 interrupt 安全门）
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

        async def execute_tool_node(state: ContractEntryState) -> dict:
            """执行工具调用。

            敏感工具（create_customer / create_contract）触发 interrupt 安全门：
            - 首次调用：interrupt() 暂停，展示待执行的操作，等用户确认
            - 用户确认后 resume：approved_tool_ids 包含这些 ID，跳过 interrupt 直接执行
            """
            last_msg = state["messages"][-1]
            if not getattr(last_msg, "tool_calls", None):
                return {}

            all_tool_calls = last_msg.tool_calls

            # 检查是否有未批准的敏感工具
            approved_ids = set(state.get("approved_tool_ids", []))
            sensitive_calls = [
                tc for tc in all_tool_calls
                if tc["function"]["name"] in _SENSITIVE_TOOLS
                and tc["id"] not in approved_ids
            ]
            new_approved_ids = []

            if sensitive_calls:
                # 构建 interrupt payload
                interrupt_id = f"contract_{uuid.uuid4().hex[:8]}"

                # 从 sensitive_calls 构建工具调用摘要
                tool_summaries = []
                for tc in sensitive_calls:
                    name = tc["function"]["name"]
                    try:
                        args = json.loads(tc["function"]["arguments"])
                    except (json.JSONDecodeError, TypeError):
                        args = {}

                    if name == "create_customer":
                        tool_summaries.append({
                            "tool": "create_customer",
                            "description": f"创建客户「{args.get('name', '?')}」",
                            "args": args,
                        })
                    elif name == "create_contract":
                        tool_summaries.append({
                            "tool": "create_contract",
                            "description": (
                                f"创建合同（客户ID: {args.get('customer_id', '?')}，"
                                f"金额: {args.get('total_amount', '?')} {args.get('currency', 'CNY')}）"
                            ),
                            "args": args,
                        })

                sensitive_ids = [tc["id"] for tc in sensitive_calls]

                # interrupt 暂停，等用户确认
                user_response = interrupt({
                    "type": "contract_confirmation",
                    "message": "确认执行以上操作？",
                    "tool_calls": tool_summaries,
                    "options": [
                        {
                            "label": "确认执行",
                            "value": {
                                "confirmed": True,
                                "approved_tool_ids": sensitive_ids,
                            },
                        },
                        {"label": "取消", "value": {"confirmed": False}},
                    ],
                    "interrupt_id": interrupt_id,
                })

                # resume 后：检查用户是否确认
                if not user_response.get("confirmed", False):
                    return {
                        "messages": [AIMessage(content="已取消操作，未创建任何记录。如需重新录入，请再次上传合同文件。")],
                        "current_node": "execute_tool_node",
                        "should_end": True,
                    }

                # 用户确认：标记这些工具为已批准，继续执行（不 return）
                new_approved_ids = sensitive_ids
                approved_ids.update(sensitive_ids)

            # 执行所有工具调用
            tool_messages = []
            for tc in all_tool_calls:
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
                    logger.info(
                        "合同录入工具结果: %s → %s",
                        tool_name, result[:200] if result else "empty",
                    )
                except Exception as e:
                    result = json.dumps({"error": f"工具执行出错: {e}"}, ensure_ascii=False)
                    logger.warning("合同录入工具异常: %s → %s", tool_name, e, exc_info=True)

                tool_messages.append(ToolMessage(
                    content=result,
                    tool_call_id=tc["id"],
                ))

            result = {
                "messages": tool_messages,
                "current_node": "execute_tool_node",
            }
            if new_approved_ids:
                result["approved_tool_ids"] = new_approved_ids
            return result

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 构建子图
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

        workflow = StateGraph(ContractEntryState)
        workflow.add_node("analyze_file_node", analyze_file_node)
        workflow.add_node("call_model_node", call_model_node)
        workflow.add_node("execute_tool_node", execute_tool_node)

        workflow.add_edge(START, "analyze_file_node")

        # analyze_file_node 完成后：
        # - 如果 should_end=True（分析失败/重复/错误）→ END
        # - 否则 → call_model_node（Agent 开始推理）
        def route_after_analyze(state: ContractEntryState) -> Literal["call_model_node", "__end__"]:
            if state.get("should_end"):
                return "__end__"
            return "call_model_node"

        workflow.add_conditional_edges("analyze_file_node", route_after_analyze, {
            "call_model_node": "call_model_node",
            "__end__": END,
        })

        workflow.add_conditional_edges("call_model_node", should_continue, {
            "execute_tool_node": "execute_tool_node",
            "__end__": END,
        })

        # execute_tool_node 完成后：
        # - 如果 should_end=True（用户取消）→ END
        # - 否则 → call_model_node（Agent 看工具结果，决定下一步）
        def route_after_execute(state: ContractEntryState) -> Literal["call_model_node", "__end__"]:
            if state.get("should_end"):
                return "__end__"
            return "call_model_node"

        workflow.add_conditional_edges("execute_tool_node", route_after_execute, {
            "call_model_node": "call_model_node",
            "__end__": END,
        })

        return workflow.compile(checkpointer=checkpointer)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 消息格式转换（复用 general_chat 的模式，注入合同录入专用 system prompt）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _convert_messages(messages: list, user) -> list:
    """LangChain BaseMessage → OpenAI 格式，注入合同录入系统提示词"""
    system_content = build_system_prompt(
        user_name=user.full_name or user.username,
        user_role=user.role,
        current_date=date.today().isoformat(),
    )
    # 追加合同录入专用指令
    system_content += "\n\n" + CONTRACT_ENTRY_PROMPT

    result = [{"role": "system", "content": system_content}]

    for msg in messages:
        if isinstance(msg, SystemMessage):
            if result and result[0].get("role") == "system":
                # 替换系统提示词，但保留合同录入指令
                result[0] = {"role": "system", "content": msg.content + "\n\n" + CONTRACT_ENTRY_PROMPT}
            else:
                result.insert(0, {"role": "system", "content": msg.content + "\n\n" + CONTRACT_ENTRY_PROMPT})
        elif isinstance(msg, HumanMessage):
            content = msg.content
            if isinstance(content, list):
                content = " ".join(str(p) for p in content)
            result.append({"role": "user", "content": content})
        elif isinstance(msg, AIMessage):
            item = {"role": "assistant", "content": msg.content or None}
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
