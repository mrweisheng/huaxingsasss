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
from typing import Optional, Literal, Any

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


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# extract_tool_summary — 从工具返回的 JSON 字符串中提取结构化摘要
# 用于右侧活动面板的「数据引用」卡片
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
            items.append({"label": "待付金额", "value": _fmt(income["remaining_amount"])})
        expense = data.get("expense", {})
        if expense.get("total_expense"):
            items.append({"label": "累计支出", "value": _fmt(expense["total_expense"])})

    elif tool_name in ("create_customer", "update_customer"):
        if data.get("success") and data.get("customer"):
            items.append({"label": "客户", "value": data["customer"].get("name", "—")})

    elif tool_name in ("create_contract", "update_contract"):
        if data.get("success") and data.get("contract"):
            c = data["contract"]
            items.append({"label": "合同编号", "value": c.get("contract_number", "—")})
            if c.get("total_amount"):
                items.append({"label": "金额", "value": _fmt(c["total_amount"])})

    elif tool_name == "query_payments":
        items.append({"label": "匹配记录", "value": _fmt(data.get("total", 0))})

    elif tool_name == "create_payment_record":
        if data.get("success") and data.get("payment"):
            p = data["payment"]
            items.append({"label": "金额", "value": _fmt(p.get("amount", 0))})
            items.append({"label": "状态", "value": p.get("status", "—")})

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
    return DashScopeAgentClient()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 轻量确认：检查 LLM 上文是否已展示计划并请求确认
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

_CONFIRM_KEYWORDS = frozenset({
    "确认", "是否", "同意", "继续", "对吗", "正确吗",
    "确认吗", "可以吗", "行吗",
})


def _has_confirmation_in_context(messages: list, current_tool_name: str = "") -> bool:
    """检查 LLM 是否在「当前轮」展示过确认询问。

    修复（防绕过）：
    - LLM 一次返回 text + tool_calls，text 中的「是否确认？」与 tool_call 写入工具
      在同一条 AIMessage 中。所以只检查最后一条 AIMessage 的 content。
    - 不再回溯历史 AIMessage，否则 5 轮前的「对吗」会让后续所有写入工具绕过防护。
    - 如果最后一条不是 AIMessage（例如只有 HumanMessage），视为未确认。

    Args:
        messages: 完整消息列表（execute_tool_node 调用时已包含 LLM 本轮 AIMessage）
        current_tool_name: 当前要执行的工具名（保留参数以备未来按工具定制策略）

    Returns:
        bool: True 表示已确认，False 表示未确认需拦截
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
