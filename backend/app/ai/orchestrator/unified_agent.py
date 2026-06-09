"""统一 Agent Graph v2 — 单层 Agent 循环

替代原 Root Graph + 4 子图架构。

节点：
  1. call_model_node      — LLM 推理（将决定调哪个工具）
  2. execute_tool_node    — 执行工具 + 轻量确认防护
  3. finalize_node        — chat_history 落库

设计原则：
  - 无意图推断路由 — LLM 通过 analyze_files 工具自主决定
  - 无子图 — 单一 Agent 循环
  - 无 mode guard / document guard — 工具集合简洁，无需模式锁定
  - 轻量确认 — 写入工具前检查 LLM 上文是否展示计划

图缓存（v2.1）：
  - 节点函数不再通过闭包捕获 db/user/executor，而是从 config["configurable"] 运行时读取
  - 图本身无状态，只构建一次并缓存，每次调用通过 config 注入请求级依赖
  - 请求级对象（db session、user、executor）放在 config["configurable"]["_deps"] 中
"""
import asyncio
import json
import logging
from datetime import date
from typing import Literal, Any, Optional

from langgraph.graph import StateGraph, START, END
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage, SystemMessage
from langchain_core.callbacks.manager import adispatch_custom_event
from langchain_core.runnables import RunnableConfig

from app.ai.orchestrator.state_v2 import AgentState
from app.ai.tools_v2 import TOOL_DEFINITIONS, ToolExecutorV2
from app.ai.llm_client import AgentModelClient
from app.ai.prompts_v2 import build_system_prompt
from app.config import settings

logger = logging.getLogger(__name__)

# 需要确认的写入工具
_WRITABLE_TOOLS = frozenset({
    "create_customer", "create_contract",
    "create_payment_record", "match_and_confirm_payment",
    "update_payment",
})


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# extract_tool_summary — 从工具返回的 JSON 字符串中提取结构化摘要
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _safe_parse_result(result: str) -> Optional[dict[str, Any]]:
    """安全解析工具返回的 JSON 字符串，失败返回 None。"""
    try:
        return json.loads(result)
    except (json.JSONDecodeError, TypeError):
        return None


def _fmt(value: Any) -> str:
    """格式化摘要值：数字加千分位，其余直接转字符串。"""
    if isinstance(value, float):
        return f"{value:,.2f}"
    if isinstance(value, int):
        return f"{value:,}"
    return str(value)


def extract_tool_summary(tool_name: str, result: str) -> Optional[dict[str, Any]]:
    """根据工具名从返回结果中提取摘要信息。返回 None 表示无法提取。"""
    data = _safe_parse_result(result)
    if not data:
        return None

    items: list[dict[str, str]] = []

    if tool_name == "analyze_files":
        success = sum(1 for f in data.get("files", []) if f.get("success"))
        rejected = len(data.get("files", [])) - success
        if rejected > 0:
            items.append({"label": "分析成功", "value": _fmt(success)})
            items.append({"label": "无法识别", "value": _fmt(rejected), "highlight": "warning"})
        else:
            items.append({"label": "分析文件", "value": _fmt(len(data.get("files", [])))})

    elif tool_name == "get_overview":
        items.append({"label": "客户总数", "value": _fmt(data.get("customers_total", 0))})
        items.append({"label": "合同总数", "value": _fmt(data.get("contracts_total", 0))})
        if data.get("expiring_contracts_30days", 0) > 0:
            items.append({"label": "30天内到期", "value": _fmt(data["expiring_contracts_30days"]), "highlight": "warning"})

    elif tool_name == "search_customers":
        total = data.get("total") or data.get("summary", {}).get("total_customers", 0)
        items.append({"label": "匹配客户", "value": _fmt(total)})

    elif tool_name == "search_contracts":
        total = data.get("total") or data.get("summary", {}).get("total_contracts", 0)
        items.append({"label": "匹配合同", "value": _fmt(total)})

    elif tool_name == "get_contract_detail":
        income = data.get("income", {})
        if income.get("total_amount"):
            items.append({"label": "合同总额", "value": _fmt(income["total_amount"])})
        if income.get("remaining_amount"):

            items.append({"label": "剩余金额", "value": _fmt(income["remaining_amount"])})

    elif tool_name == "create_customer":
        if data.get("customer_id"):
            items.append({"label": "客户ID", "value": _fmt(data["customer_id"])})
        if data.get("name"):
            items.append({"label": "客户名", "value": data["name"]})

    elif tool_name == "create_contract":
        if data.get("contract_id"):
            items.append({"label": "合同ID", "value": _fmt(data["contract_id"])})

    elif tool_name == "create_payment_record":
        if data.get("payment_id"):
            items.append({"label": "付款ID", "value": _fmt(data["payment_id"])})

    elif tool_name == "match_and_confirm_payment":
        items.append({"label": "匹配结果", "value": "已匹配" if data.get("matched") else "未匹配"})
        if data.get("payment") and data["payment"].get("amount"):
            items.append({"label": "金额", "value": _fmt(data["payment"]["amount"])})

    elif tool_name == "update_payment":
        items.append({"label": "更新结果", "value": "成功" if data.get("success") else "失败"})

    elif tool_name == "search_contract_text":
        items.append({"label": "匹配结果", "value": _fmt(len(data.get("matches", [])))})

    if not items:
        return None

    return {"type": "data_reference", "items": items}


def _default_llm_client():
    return AgentModelClient()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 从 config 获取请求级依赖
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _get_deps(config: RunnableConfig) -> dict:
    """从 config["configurable"]["_deps"] 获取请求级依赖（db, user, executor, llm_client）。"""
    deps = config.get("configurable", {}).get("_deps")
    if not deps:
        raise RuntimeError("Agent 图缺少请求级依赖：config.configurable._deps 未注入")
    return deps


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 轻量确认：检查 LLM 上文是否已展示计划并请求确认
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

_CONFIRM_KEYWORDS = frozenset({
    "确认", "是否", "同意", "继续", "对吗", "正确吗",
    "确认吗", "可以吗", "行吗",
})


def _has_confirmation_in_context(messages: list) -> bool:
    """检查 LLM 是否在当前轮（最后一条 HumanMessage 之前）展示过确认询问。

    只检查 messages[-1]：确认一定是上一轮 AI 回复的内容。
    不扫描全部历史，避免早期"对吗"永久绕过防护。
    """
    if not messages:
        return False
    last_msg = messages[-1]
    if not isinstance(last_msg, AIMessage):
        return False
    content = (last_msg.content or "").lower()
    return any(kw in content for kw in _CONFIRM_KEYWORDS)


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
# 节点函数（无闭包，从 config 读取依赖）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def call_model_node(state: AgentState, config: RunnableConfig) -> dict:
    """调用 LLM，决定下一步操作"""
    deps = _get_deps(config)
    user = deps["user"]
    llm_client = deps["llm_client"]

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


async def execute_tool_node(state: AgentState, config: RunnableConfig) -> dict:
    """执行工具调用。

    写入工具执行前检查 LLM 上文是否展示过确认请求。
    未展示 → 返回错误让 LLM 先确认。
    """
    deps = _get_deps(config)
    executor = deps["executor"]

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

        # ── SSE: 工具开始事件（通知前端活动面板） ──
        await adispatch_custom_event("tool_start", {
            "id": tc["id"],
            "name": tool_name,
            "arguments": tc.get("arguments", "{}"),
        })

        # ── 轻量确认防护 ──
        if tool_name in _WRITABLE_TOOLS:
            if not _has_confirmation_in_context(state.get("messages", [])):
                logger.warning("确认防护拦截: tool=%s（上文无确认询问）", tool_name)
                error_content = json.dumps({
                    "error": f"请先向用户展示操作计划并请求确认后，再调用 {tool_name}。",
                    "tool": tool_name,
                    "hint": "你应该先回复用户（不调任何写入工具），列出将要创建/修改的内容（客户名、金额、业务类型），"
                            "明确问「是否确认？」，等用户回复「确认」后再在下一轮调用此工具。",
                }, ensure_ascii=False)
                tool_messages.append(ToolMessage(
                    content=error_content,
                    tool_call_id=tc["id"],
                ))
                # SSE: 工具结束事件（被拦截）
                await adispatch_custom_event("tool_end", {
                    "id": tc["id"],
                    "name": tool_name,
                    "result": error_content,
                    "summary": None,
                })
                continue

        # ── 执行工具 ──
        try:
            result = await asyncio.to_thread(executor.execute, tool_name, args)
        except Exception as e:
            result = json.dumps({"error": f"工具执行出错: {tool_name} → {e}"}, ensure_ascii=False)
            logger.warning("工具执行出错: %s → %s", tool_name, e)

        # SSE: 工具结束事件（附带结构化摘要）
        summary = extract_tool_summary(tool_name, result)
        await adispatch_custom_event("tool_end", {
            "id": tc["id"],
            "name": tool_name,
            "result": result,
            "summary": summary,
        })

        tool_messages.append(ToolMessage(
            content=result,
            tool_call_id=tc["id"],
        ))

    return {"messages": tool_messages}


async def finalize_node(state: AgentState, config: RunnableConfig) -> dict:
    """chat_history 落库"""
    deps = _get_deps(config)
    db = deps["db"]
    user = deps["user"]

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


# ── 路由 ──

def should_continue(state: AgentState) -> Literal["execute_tool_node", "finalize_node"]:
    """有 tool_calls → execute_tool_node，否则 finalize_node"""
    if state.get("should_end"):
        return "finalize_node"
    last = state["messages"][-1] if state.get("messages") else None
    if last and getattr(last, "tool_calls", None):
        return "execute_tool_node"
    return "finalize_node"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 图缓存（进程级单例）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

_compiled_graph_cache: dict = {}


def _build_graph():
    """构建无状态的 Agent StateGraph（不含 checkpointer，不依赖请求级对象）。"""
    workflow = StateGraph(AgentState)

    workflow.add_node("call_model_node", call_model_node)
    workflow.add_node("execute_tool_node", execute_tool_node)
    workflow.add_node("finalize_node", finalize_node)

    workflow.add_edge(START, "call_model_node")
    workflow.add_conditional_edges("call_model_node", should_continue, {
        "execute_tool_node": "execute_tool_node",
        "finalize_node": "finalize_node",
    })
    workflow.add_edge("execute_tool_node", "call_model_node")
    workflow.add_edge("finalize_node", END)

    return workflow


def get_compiled_graph(checkpointer=None):
    """获取编译后的 Agent 图（进程级缓存，按 checkpointer 实例区分）。

    图本身无状态，请求级依赖（db/user/executor/llm_client）
    通过 config["configurable"]["_deps"] 注入，不参与 checkpoint。
    """
    # checkpointer 通常是进程级单例，用 id 做缓存 key
    cp_id = id(checkpointer) if checkpointer else "none"
    if cp_id not in _compiled_graph_cache:
        graph = _build_graph()
        _compiled_graph_cache[cp_id] = graph.compile(checkpointer=checkpointer)
        logger.info("Agent 图编译完成并缓存: cp_id=%s", cp_id)
    return _compiled_graph_cache[cp_id]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 便捷函数（保持向后兼容）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def build_unified_agent(db, user, llm_client=None):
    """构建统一 Agent 图（便捷函数）

    ⚠️ 此函数仍创建闭包捕获的旧式图，仅供向后兼容。
    新代码应直接使用 get_compiled_graph() + config["configurable"]["_deps"] 注入。
    """
    llm_client = llm_client or _default_llm_client()
    executor = ToolExecutorV2(db, user)

    # 复用无状态节点，但用闭包包装以兼容旧调用方式
    deps = {"db": db, "user": user, "executor": executor, "llm_client": llm_client}

    async def _call_model(state: AgentState) -> dict:
        return await call_model_node(state, {"configurable": {"_deps": deps}})

    async def _execute_tool(state: AgentState) -> dict:
        return await execute_tool_node(state, {"configurable": {"_deps": deps}})

    async def _finalize(state: AgentState) -> dict:
        return await finalize_node(state, {"configurable": {"_deps": deps}})

    workflow = StateGraph(AgentState)
    workflow.add_node("call_model_node", _call_model)
    workflow.add_node("execute_tool_node", _execute_tool)
    workflow.add_node("finalize_node", _finalize)
    workflow.add_edge(START, "call_model_node")
    workflow.add_conditional_edges("call_model_node", should_continue, {
        "execute_tool_node": "execute_tool_node",
        "finalize_node": "finalize_node",
    })
    workflow.add_edge("execute_tool_node", "call_model_node")
    workflow.add_edge("finalize_node", END)

    return workflow
