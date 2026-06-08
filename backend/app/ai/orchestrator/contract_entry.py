"""合同录入子图（Agent 循环架构）

取代旧的 9 节点确定性 DAG，改为 Agent 推理循环 + 计划驱动安全门。

架构：
  analyze_file_node → call_model_node ↔ execute_tool_node → END
                           ↑                    ↓
                           └────────────────────┘

- analyze_file_node: 调 ContractAnalyzer 提取结构化数据，注入 messages
- call_model_node:   LLM 推理（决定展示什么、调什么工具、何时结束）
- execute_tool_node: 执行工具调用，敏感工具（create_customer/create_contract）
                     必须经过 set_pending_plan 确认（计划驱动安全门），用户确认
                     后放行；业务成功后清空 pending_plan 防复用

设计原则：
  - Agent 是决策者：根据业务类型自行判断展示哪些字段
  - 工具是执行者：search_customers / create_contract 等越确定性越好
  - 计划驱动安全门：LLM 调 set_pending_plan 声明计划 + 用户确认，代码层硬约束
    create_* 必须在已确认的 plan.actions 里
"""
import asyncio
import json
import logging
import uuid
from datetime import date
from typing import Optional, Literal

from langgraph.graph import StateGraph, START, END
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage, SystemMessage
from langchain_core.callbacks.manager import adispatch_custom_event

from app.ai.orchestrator.state import ContractEntryState
from app.ai.tools import TOOL_DEFINITIONS, ToolExecutor
from app.ai.llm_client import DashScopeAgentClient
from app.ai.prompts import CONTRACT_ENTRY_PROMPT, build_system_prompt
from app.services.contract_analyzer import ContractAnalyzer
from app.utils.file_utils import resolve_file_path
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

    def build(self) -> StateGraph:
        """编译合同录入子图

        注意：不传 checkpointer。由父图编译时传入，LangGraph 自动传播到子图。
        """
        executor = self.executor
        user = self.user
        llm_client = self._llm_client or _default_llm_client()

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 节点 1：分析文件（确定性工具，无 LLM 推理）
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

        async def analyze_file_node(state: ContractEntryState) -> dict:
            """解析附件 → ContractAnalyzer 提取数据 → 注入 messages 供 Agent 读取

            多轮续接：当用户在确认阶段回复"确认"时，不带新附件。
            此时 state 中保留了上一轮的 file_context（来自 checkpoint），
            应跳过重复分析，直接进入 Agent 循环处理用户消息。
            """
            # ━━━ 多轮续接检测 ━━━
            # 场景：用户第二轮回复"确认"/"修改"等，不带新附件。
            # checkpoint 保留了 file_context 和 pending_plan，直接进入 Agent 循环。
            existing_file_context = state.get("file_context")
            attachments = state.get("attachments", [])

            if not attachments and existing_file_context:
                logger.info(
                    "合同录入多轮续接: 跳过文件分析，直接进入 Agent 循环 "
                    "(has_file_context=True, pending_plan=%s)",
                    "yes" if state.get("pending_plan") else "none",
                )
                return {
                    "should_end": False,
                    "iteration_count": 0,
                    "current_node": "analyze_file_node",
                }

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
            file_path = resolve_file_path(file_id, user.id)
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
                # 新一轮 Agent 循环：清残留状态，iteration 从 0 重新计
                "should_end": False,
                "iteration_count": 0,
                "pending_plan": None,  # 新文件上传，清除旧 plan
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
                        await adispatch_custom_event(
                            "text_chunk",
                            {"content": event["content"]},
                        )
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
            """执行工具调用（计划驱动安全门）

            敏感工具（create_customer / create_contract）必须经过 set_pending_plan 声明，
            且必须满足：
              1. state.pending_plan 存在
              2. pending_plan.user_confirmed == True
              3. 工具名在 pending_plan.actions 里
            任一不满足 → 拒绝执行，返回明确错误让 LLM 自我纠正。

            业务成功后清空 pending_plan（置 None），避免下一轮 LLM 跳过确认直接复用。
            set_pending_plan 本身不走 ToolExecutor，在本节点开头内联处理
            （凭证 mode guard 不拦截，state 写入也无需走 service 层）。
            """
            last_msg = state["messages"][-1]
            if not getattr(last_msg, "tool_calls", None):
                return {}

            all_tool_calls = last_msg.tool_calls
            pending_plan = state.get("pending_plan")

            tool_messages = []
            # 内联 set_pending_plan 的写入：通过 pending_plan_was_updated 标志位
            # 追踪 plan 是否变更，最终通过 return dict 持久化到 checkpoint
            new_pending_plan = pending_plan
            pending_plan_was_updated = False
            any_sensitive_executed = False
            any_sensitive_failed = False

            for tc in all_tool_calls:
                tool_name = tc["name"]
                try:
                    args = tc["args"] if isinstance(tc["args"], dict) else (
                        json.loads(tc["args"]) if isinstance(tc["args"], str) else {}
                    )
                except json.JSONDecodeError:
                    args = {}

                # ━━━ 内联处理 set_pending_plan：不进 ToolExecutor ━━━
                if tool_name == "set_pending_plan":
                    valid_actions = {
                        "create_customer", "create_contract",
                        "create_payment", "create_expense",
                        "update_payment",
                    }
                    clean_actions = [
                        a for a in (args.get("actions") or []) if a in valid_actions
                    ]
                    # 复用已有 plan_id：避免每次生成新 ID 导致 LLM 感知到变化
                    # 仅当 plan 尚不存在时才生成新 ID
                    existing_plan_id = new_pending_plan.get("plan_id") if new_pending_plan else None
                    plan_id = existing_plan_id or str(uuid.uuid4())[:8]

                    new_pending_plan = {
                        "plan_id": plan_id,
                        "summary": str(args.get("summary", "")),
                        "actions": clean_actions,
                        "user_confirmed": bool(args.get("user_confirmed", False)),
                    }
                    # 同步局部变量：后续同轮的 create_* 校验需看到更新后的 plan
                    pending_plan = new_pending_plan
                    pending_plan_was_updated = True
                    if new_pending_plan["user_confirmed"]:
                        msg = "计划已确认，可继续执行 create_* 工具"
                    else:
                        msg = "计划已设置，等待用户确认后继续"
                    result = json.dumps({
                        "status": "ok",
                        "message": msg,
                        "plan": new_pending_plan,
                    }, ensure_ascii=False)
                    tool_messages.append(ToolMessage(content=result, tool_call_id=tc["id"]))
                    logger.info(
                        "合同录入计划更新: plan_id=%s confirmed=%s actions=%s summary=%s",
                        new_pending_plan["plan_id"],
                        new_pending_plan["user_confirmed"],
                        new_pending_plan["actions"],
                        new_pending_plan["summary"][:50],
                    )
                    continue

                # ━━━ 硬约束：敏感工具必须经过 set_pending_plan 确认 ━━━
                if tool_name in _SENSITIVE_TOOLS:
                    if pending_plan is None:
                        result = json.dumps({
                            "status": "needs_plan",
                            "error": f"未声明计划，禁止调用 {tool_name}",
                            "hint": "先调 set_pending_plan(summary, actions=[...], user_confirmed=false) 声明计划并请求用户确认",
                        }, ensure_ascii=False)
                        tool_messages.append(ToolMessage(content=result, tool_call_id=tc["id"]))
                        logger.warning("合同录入安全门拦截[needs_plan]: %s", tool_name)
                        continue

                    if not pending_plan.get("user_confirmed"):
                        result = json.dumps({
                            "status": "needs_confirmation",
                            "error": f"用户尚未确认计划，禁止调用 {tool_name}",
                            "hint": "先向用户展示计划摘要并问'是否确认'，用户确认后再次调 set_pending_plan(user_confirmed=true)",
                        }, ensure_ascii=False)
                        tool_messages.append(ToolMessage(content=result, tool_call_id=tc["id"]))
                        logger.warning("合同录入安全门拦截[needs_confirmation]: %s", tool_name)
                        continue

                    if tool_name not in pending_plan.get("actions", []):
                        result = json.dumps({
                            "status": "action_not_in_plan",
                            "error": f"{tool_name} 不在已确认的计划中",
                            "hint": f"已确认计划包含: {pending_plan.get('actions')}",
                        }, ensure_ascii=False)
                        tool_messages.append(ToolMessage(content=result, tool_call_id=tc["id"]))
                        logger.warning(
                            "合同录入安全门拦截[action_not_in_plan]: %s, plan.actions=%s",
                            tool_name, pending_plan.get("actions"),
                        )
                        continue

                # ━━━ 通过校验，正常执行 ━━━
                try:
                    result = await asyncio.to_thread(
                        executor.execute, tool_name, args
                    )
                    logger.info(
                        "合同录入工具结果: %s → %s",
                        tool_name, result[:200] if result else "empty",
                    )
                except Exception as e:
                    result = json.dumps({"error": f"工具执行出错: {e}"}, ensure_ascii=False)
                    logger.warning("合同录入工具异常: %s → %s", tool_name, e, exc_info=True)

                # ━━━ 业务成功判定：仅全部敏感工具成功才清 plan ━━━
                # 部分成功不清 plan：如果 create_customer 成功但 create_contract 失败，
                # LLM 需要在下轮重试 create_contract，plan 必须保留。
                if tool_name in _SENSITIVE_TOOLS:
                    any_sensitive_executed = True
                    try:
                        result_obj = json.loads(result) if isinstance(result, str) else {}
                    except json.JSONDecodeError:
                        result_obj = {}
                    if result_obj.get("error"):
                        any_sensitive_failed = True
                        logger.warning(
                            "合同录入敏感工具业务失败，保留 pending_plan: plan_id=%s tool=%s err=%s",
                            pending_plan.get("plan_id", "?") if pending_plan else "?",
                            tool_name, result_obj.get("error"),
                        )
                    else:
                        logger.info(
                            "合同录入敏感工具业务成功: plan_id=%s tool=%s",
                            pending_plan.get("plan_id", "?") if pending_plan else "?",
                            tool_name,
                        )

                tool_messages.append(ToolMessage(
                    content=result,
                    tool_call_id=tc["id"],
                ))

            # 决定 pending_plan 写回值：
            # 1. set_pending_plan 调过 → 写入新 plan（持久化到 checkpoint）
            # 2. 所有敏感工具业务成功 → 清空 plan（消费完毕，防下一轮复用）
            # 3. 敏感工具部分失败 → 保留 plan（LLM 下轮可重试）
            updates = {
                "messages": tool_messages,
                "current_node": "execute_tool_node",
            }
            if pending_plan_was_updated:
                updates["pending_plan"] = new_pending_plan
                logger.info(
                    "合同录入计划持久化: plan_id=%s confirmed=%s actions=%s",
                    new_pending_plan.get("plan_id"),
                    new_pending_plan.get("user_confirmed"),
                    new_pending_plan.get("actions"),
                )
            elif any_sensitive_executed and not any_sensitive_failed:
                updates["pending_plan"] = None
                logger.info(
                    "合同录入计划消费完毕，清空: plan_id=%s",
                    pending_plan.get("plan_id", "?") if pending_plan else "?",
                )
            return updates

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

        return workflow.compile()


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

