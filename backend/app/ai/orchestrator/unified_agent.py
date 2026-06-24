"""统一 Agent Graph v2 — 单层 Agent 循环

替代原 Root Graph + 4 子图架构。

节点：
  1. call_model_node      — LLM 推理（将决定调哪个工具）
  2. execute_tool_node    — 执行工具
  3. finalize_node        — chat_history 增量落库

设计原则：
  - 无意图推断路由 — LLM 通过 analyze_files 工具自主决定
  - 无子图 — 单一 Agent 循环
  - 写入确认完全交给 LLM 自主判断（system prompt 约束），不在代码层做关键词拦截

图缓存（v2.1）：
  - 节点函数不再通过闭包捕获 db/user/executor，而是从 config["configurable"] 运行时读取
  - 图本身无状态，只构建一次并缓存，每次调用通过 config 注入请求级依赖
  - 请求级对象（db session、user、executor）放在 config["configurable"]["_deps"] 中
"""
import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Literal, Any, Optional
from zoneinfo import ZoneInfo

from langgraph.graph import StateGraph, START, END
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage, SystemMessage
from langchain_core.callbacks.manager import adispatch_custom_event
from langchain_core.runnables import RunnableConfig

from app.ai.orchestrator.state import AgentState
from app.ai.tool_executor import TOOL_DEFINITIONS, ToolExecutorV2
from app.ai.llm_client import AgentModelClient
from app.ai.prompts import build_system_prompt, TimeContext
from app.config import settings

logger = logging.getLogger(__name__)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# now_context — 生成注入系统提示词的时间上下文
# 固定 Asia/Shanghai，避免容器 UTC 导致"今天"漂移；
# 同时给出本周/本月范围，省去 LLM 自行推算（月初/跨年易算错）。
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# 用 tuple 而非 list：模块级常量应不可变，杜绝被意外 mutate。
_WEEKDAYS: tuple[str, ...] = ("周一", "周二", "周三", "周四", "周五", "周六", "周日")


def _get_shanghai_tz() -> ZoneInfo:
    """获取 Asia/Shanghai 时区。tzdata 缺失时给出可操作的降级错误，而非裸异常。"""
    try:
        return ZoneInfo("Asia/Shanghai")
    except Exception as e:  # ZoneInfoNotFoundError（Windows 无 tzdata 时）
        raise RuntimeError(
            "无法加载 Asia/Shanghai 时区。Windows 开发环境请确认已安装 tzdata 包"
            "（已在 pyproject.toml 声明 'tzdata ; sys_platform == win32'，"
            "执行 `uv sync` 或 `pip install tzdata` 后重试）。"
        ) from e


_SHANGHAI = _get_shanghai_tz()


def now_context() -> TimeContext:
    now = datetime.now(_SHANGHAI)
    today = now.date()
    wd = today.weekday()                                        # 周一=0
    monday = today - timedelta(days=wd)                         # 本周一
    sunday = monday + timedelta(days=6)                         # 本周日
    month_start = today.replace(day=1)
    # 下月第1天 - 1天 = 本月最后一天
    if today.month == 12:
        next_month_first = today.replace(year=today.year + 1, month=1, day=1)
    else:
        next_month_first = today.replace(month=today.month + 1, day=1)
    month_end = next_month_first - timedelta(days=1)
    return {
        "datetime": now.strftime("%Y-%m-%d %H:%M"),
        "date": today.isoformat(),
        "weekday": _WEEKDAYS[wd],
        "week_start": monday.isoformat(),
        "week_end": sunday.isoformat(),
        "month_start": month_start.isoformat(),
        "month_end": month_end.isoformat(),
    }


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
# LangChain → OpenAI 消息格式转换
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _convert_messages(
    messages: list, user, attachments: list = None,
    session_context: Optional[dict] = None,
    contract_info: Optional[dict] = None,
    session_mode: str = "chat",
) -> list:
    """将 LangChain BaseMessage 列表转为 OpenAI 格式消息列表。"""
    system_content = build_system_prompt(
        user_name=user.full_name or user.username,
        user_role=user.role,
        current_time=now_context(),
        session_context=session_context,
        contract_info=contract_info,
        session_mode=session_mode,
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

    # ── 合同上下文注入：从 session_context 查合同详情，注入系统提示词 ──
    session_context = state.get("session_context")
    contract_info: Optional[dict] = None
    if session_context and session_context.get("contract_id"):
        db = deps["db"]
        try:
            from app.models.contract import Contract
            from app.models.customer import Customer
            contract = (
                db.query(Contract)
                .filter(Contract.id == session_context["contract_id"])
                .first()
            )
            if contract:
                contract_info = {
                    "contract_id": contract.id,
                    "contract_number": contract.contract_number,
                    "business_description": contract.business_description,
                    "total_amount": float(contract.total_amount) if contract.total_amount else None,
                    "currency": contract.currency,
                    "payment_type": session_context.get("payment_type"),
                    "customer_name": "",
                }
                # 查客户名
                if contract.customer_id:
                    customer = db.query(Customer).filter(Customer.id == contract.customer_id).first()
                    if customer:
                        contract_info["customer_name"] = customer.name
        except Exception:
            logger.warning("合同上下文查找失败: contract_id=%s", session_context.get("contract_id"), exc_info=True)

    openai_messages = _convert_messages(
        msgs, user, attachments,
        session_context=session_context,
        contract_info=contract_info,
        session_mode=state.get("session_mode", "chat"),
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
            "messages": [AIMessage(content=full_text or "", tool_calls=lc_tool_calls)],
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

    写入是否需要先确认完全交由 LLM 根据 system prompt 的「确认规则」自主判断，
    本节点只负责忠实执行 LLM 决定调用的工具。
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

        # ── 执行工具 ──
        try:
            result = await asyncio.to_thread(executor.execute, tool_name, args)
        except Exception as e:
            # 完整 traceback + 工具名 + 参数，便于定位 NameError 等
            logger.exception(
                "execute_tool_node 异常: tool=%s, args=%s, error=%s",
                tool_name, json.dumps(args, ensure_ascii=False, default=str)[:500], e,
            )
            result = json.dumps({"error": f"工具执行出错: {tool_name} → {e}"}, ensure_ascii=False)

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
            name=tool_name,
            additional_kwargs={"summary": summary} if summary else {},
        ))

    # 跨 turn 同步已移除（_pending_receipt_file_ids 不再需要，录收支改走表单）
    return {
        "messages": tool_messages,
    }


async def finalize_node(state: AgentState, config: RunnableConfig) -> dict:
    """chat_history 增量落库

    用 _persisted_count 游标只处理本轮新增消息，避免每轮全量重复插入。
    同时跳过纯 tool_call 中间态 AIMessage（空 content + 仅 tool_calls），前端无需展示。
    顺带把 user 消息里的 attachments 回填到 agent_file.session_id。
    """
    deps = _get_deps(config)
    db = deps["db"]
    user = deps["user"]

    if state.get("_finalized"):
        return {"should_end": True, "_finalized": True}

    from app.models.chat_history import ChatHistory
    from app.models.agent_file import AgentFile

    session_id = state.get("session_id", "")
    messages = state.get("messages", [])
    cursor = state.get("_persisted_count", 0)
    new_msgs = messages[cursor:]

    # 收集本轮 user 消息中的 attachments file_id，稍后批量回填 session_id
    new_attachment_ids: list[str] = []

    for msg in new_msgs:
        msg_type = getattr(msg, "type", None)
        addl = getattr(msg, "additional_kwargs", {}) or {}
        auto_filled = bool(addl.get("auto_filled", False))
        user_metadata = {"auto_filled": True} if auto_filled else None
        try:
            if msg_type == "ai":
                content = (getattr(msg, "content", "") or "").strip()
                tool_calls = getattr(msg, "tool_calls", None)
                # 跳过纯 tool_call 中间态:无文本只是工具调用,前端没什么可展示
                if not content and tool_calls:
                    continue
                record = ChatHistory(
                    user_id=user.id, session_id=session_id,
                    question="", answer=getattr(msg, "content", "") or "",
                    role="assistant",
                    tool_calls=tool_calls,
                    llm_model=settings.DEEPSEEK_AGENT_MODEL,
                )
                db.add(record)
            elif msg_type == "human":
                attachments = addl.get("attachments") or None
                if attachments:
                    for a in attachments:
                        fid = a.get("file_id") if isinstance(a, dict) else None
                        if fid:
                            new_attachment_ids.append(fid)
                record = ChatHistory(
                    user_id=user.id, session_id=session_id,
                    question=getattr(msg, "content", "") or "", answer=None,
                    role="user",
                    attachments=attachments,
                    extra_metadata=user_metadata or {},
                    llm_model=settings.DEEPSEEK_AGENT_MODEL,
                )
                db.add(record)
            elif msg_type == "tool":
                # summary 挂在 additional_kwargs,序列化到 metadata 供 get_history 回读
                tool_meta = {"tool_call_id": getattr(msg, "tool_call_id", "")}
                summary = addl.get("summary")
                if summary:
                    tool_meta["summary"] = summary
                record = ChatHistory(
                    user_id=user.id, session_id=session_id,
                    question="", answer=getattr(msg, "content", "") or "",
                    role="tool",
                    intent_type=getattr(msg, "name", ""),
                    extra_metadata=tool_meta,
                    llm_model=settings.DEEPSEEK_AGENT_MODEL,
                )
                db.add(record)
        except Exception:
            logger.warning("chat_history 落库跳过: type=%s session_id=%s", msg_type, session_id, exc_info=True)

    # 回填 agent_file.session_id（仅当本表存在对应 file_id 时；旧上传走 TEMP_UPLOAD_DIR 的不会有记录）
    if new_attachment_ids and session_id:
        try:
            (
                db.query(AgentFile)
                .filter(
                    AgentFile.file_id.in_(new_attachment_ids),
                    AgentFile.user_id == user.id,
                    AgentFile.session_id.is_(None),
                )
                .update({AgentFile.session_id: session_id}, synchronize_session=False)
            )
        except Exception:
            logger.warning("agent_file.session_id 回填失败: session=%s", session_id, exc_info=True)

    db.commit()
    logger.info(
        "finalize_node 完成: session_id=%s msg_total=%d new=%d cursor=%d→%d",
        session_id, len(messages), len(new_msgs), cursor, len(messages),
    )
    return {
        "should_end": True,
        "_finalized": True,
        "_persisted_count": len(messages),
    }


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
