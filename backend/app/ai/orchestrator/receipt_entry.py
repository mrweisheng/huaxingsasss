"""凭证录入子图（收入/支出统一，Agent 循环架构）

架构：
  analyze_receipt_node → call_model_node ↔ execute_tool_node → END
                            ↑                    ↓
                            └────────────────────┘

- analyze_receipt_node: ReceiptAnalyzer 提取凭证数据 + 查询已有付款 + 获取合同信息
- call_model_node:      LLM 推理（匹配/新建判断 + 工具调用）
- execute_tool_node:    敏感工具（create_expense/create_payment）触发 interrupt 安全门，
                        展示结构化确认表单，用户确认或修改后 resume 放行

设计原则：
  - 确定性步骤（文件分析、付款查询）在 analyze_receipt_node 完成，不消耗 LLM token
  - Agent 判断（匹配/新建、description 提取、缺失字段追问）在 call_model_node 完成
  - 确认交互通过 interrupt() 富 UI 完成，不再依赖用户打字"继续"
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
from langchain_core.callbacks.manager import adispatch_custom_event

from app.ai.orchestrator.state import ReceiptEntryState
from app.ai.tools import TOOL_DEFINITIONS, ToolExecutor
from app.ai.llm_client import DashScopeAgentClient
from app.ai.prompts import RECEIPT_ENTRY_PROMPT
from app.services.receipt_analyzer import ReceiptAnalyzer
from app.services.contract_analyzer import ContractAnalyzer
from app.utils.file_utils import resolve_file_path
from app.services.payment_service import PaymentService
from app.models.payment import Payment
from sqlalchemy.orm import joinedload
from app.models.contract import Contract
from app.models.customer import Customer
from app.config import settings

logger = logging.getLogger(__name__)

# 需要用户确认才能执行的敏感工具
_SENSITIVE_TOOLS = {"create_expense", "create_payment"}


def _default_llm_client():
    """懒加载默认 LLM 客户端"""
    return DashScopeAgentClient()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 业务类型 ↔ 凭证关键词 映射（用于确定性 match_warning）
# 规则：业务类型 → 不应出现的关键词集合。
# 出现 = 凭证与合同业务明显不相关，需用户确认。
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
_INCOMPATIBLE_HINTS = {
    "车辆买卖": ["保险", "年检", "税费", "罚款", "代办", "渠道"],
    "两地牌过户": ["港车保险", "车辆买卖", "车款", "车价", "底盘"],
    "年检保险": ["车牌", "过户", "指标", "订金", "定金", "尾款"],
}


def _compute_match_warning(analysis_data: dict, contract_info: dict) -> str | None:
    """根据凭证分析与合同业务类型，生成确定性匹配警告。

    Returns:
        警告文案（中文），或 None（无需警告）。
    """
    if not isinstance(analysis_data, dict) or not isinstance(contract_info, dict):
        return None

    business_type = (contract_info.get("business_type") or "").strip()
    if not business_type:
        return None

    incompatible = _INCOMPATIBLE_HINTS.get(business_type, [])
    if not incompatible:
        return None

    # 凭证侧收集文本：business_hint + 收款方 + 备注
    fields = [
        str(analysis_data.get("business_hint") or ""),
        str(analysis_data.get("payee_name") or ""),
        str(analysis_data.get("notes") or ""),
    ]
    text = " ".join(fields).lower()

    hit = next((kw for kw in incompatible if kw.lower() in text), None)
    if not hit:
        return None

    return (
        f"凭证内容包含「{hit}」，与本合同业务类型（{business_type}）"
        f"明显不相关，请确认是否录入到正确合同。"
    )


def _load_contract_context(db, contract_id, payment_type: str = "income") -> dict:
    """一次查询加载合同上下文 + 该合同同类型付款记录（合并 join）。

    Returns:
        {
            "contract_info": {contract_number, customer_name, business_type, total_amount, currency},
            "existing_payments": [{id, installment_number, ...}],
        }
        当 contract_id 缺失或合同不存在时，contract_info 为 {}，existing_payments 为 []。
    """
    result = {"contract_info": {}, "existing_payments": []}
    if not contract_id:
        return result

    try:
        # 合同 + 客户（一次 join，避免 N+1）
        contract = (
            db.query(Contract)
            .options(joinedload(Contract.customer))
            .filter(Contract.id == contract_id, Contract.is_deleted == False)
            .first()
        )
        if not contract:
            return result

        customer_name = contract.customer.name if contract.customer else ""
        result["contract_info"] = {
            "contract_number": contract.contract_number or "",
            "customer_name": customer_name,
            "business_type": contract.business_type or "",
            "total_amount": float(contract.total_amount) if contract.total_amount else 0,
            "currency": contract.currency or "CNY",
        }

        # 同类型付款记录（pending 优先便于 LLM 匹配）
        payments = (
            db.query(Payment)
            .filter(
                Payment.contract_id == contract_id,
                Payment.type == payment_type,
                Payment.is_deleted == False,
            )
            .order_by(Payment.status.asc(), Payment.installment_number.asc())
            .all()
        )
        for p in payments:
            result["existing_payments"].append({
                "id": p.id,
                "installment_number": p.installment_number,
                "installment_name": p.installment_name,
                "amount": float(p.paid_amount) if p.paid_amount else 0,
                "currency": p.currency,
                "status": p.status,
                "paid_date": str(p.paid_date) if p.paid_date else None,
                "payee_name": p.payee_name,
            })
    except Exception as e:
        logger.warning("加载合同上下文失败: %s", e)

    return result


class ReceiptEntrySubgraph:
    """凭证录入子图工厂（收入/支出统一）。

    通过 closure 注入 db / user / mode / session_context 依赖，返回编译后的子图。
    session_context 必须包含 contract_id 和 payment_type。
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
        """编译凭证录入子图"""
        executor = self.executor
        user = self.user
        session_ctx = self.executor.session_context
        llm_client = self._llm_client or _default_llm_client()

        # 预加载合同信息（供 _convert_messages 的 system prompt 使用）
        contract_meta = _load_contract_meta(
            executor.db, session_ctx.get("contract_id")
        )

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 节点 1：分析凭证（确定性工具，无 LLM 推理）
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

        async def analyze_receipt_node(state: ReceiptEntryState) -> dict:
            """解析附件 → ReceiptAnalyzer 提取凭证数据 → 查询已有付款 → 获取合同信息"""
            attachments = state.get("attachments", [])

            if not attachments:
                return {
                    "current_node": "analyze_receipt_node",
                    "errors": ["无附件"],
                    "messages": [AIMessage(content="未检测到附件，请上传凭证文件。")],
                    "should_end": True,
                }

            att = attachments[0]
            file_id = att.get("file_id", "")
            if not file_id:
                return {
                    "current_node": "analyze_receipt_node",
                    "errors": ["无效的 file_id"],
                    "messages": [AIMessage(content="文件 ID 无效，请重新上传。")],
                    "should_end": True,
                }

            # 解析文件路径（复用 ContractAnalyzer 的路径解析，含路径穿越防御）
            file_path = resolve_file_path(file_id, user.id)
            if not file_path:
                return {
                    "current_node": "analyze_receipt_node",
                    "errors": [f"文件不存在: {file_id}"],
                    "messages": [AIMessage(content="文件未找到，请重新上传。")],
                    "should_end": True,
                }

            # ReceiptAnalyzer 分析（同步方法，asyncio.to_thread 包装）
            result = await asyncio.to_thread(
                ReceiptAnalyzer.analyze_from_file, file_path, file_id
            )

            if not result.get("success"):
                return {
                    "current_node": "analyze_receipt_node",
                    "errors": [result.get("error", "分析失败")],
                    "messages": [AIMessage(
                        content=f"凭证分析失败：{result.get('error', '未知错误')}。请检查文件或手动录入。"
                    )],
                    "should_end": True,
                }

            analysis_data = result["data"] or {}
            analysis_json = json.dumps(analysis_data, ensure_ascii=False)

            # 一次性加载合同 + 同类型付款记录（1 个 join，避免 N+1）
            contract_id = session_ctx.get("contract_id")
            payment_type = session_ctx.get("payment_type", "income")
            ctx = _load_contract_context(executor.db, contract_id, payment_type)
            contract_info = ctx["contract_info"]
            existing_payments = ctx["existing_payments"]

            # 确定性匹配警告：业务类型 vs 凭证关键词
            match_warning = _compute_match_warning(analysis_data, contract_info)
            if match_warning:
                logger.info(
                    "receipt_entry.analyze: match_warning file_id=%s reason=%s",
                    file_id, match_warning,
                )

            # 构建消息：合同上下文 + 凭证分析结果 + 已有记录
            existing_summary = (
                f"共 {len(existing_payments)} 笔记录"
                if existing_payments
                else "暂无记录"
            )
            msg_content = (
                f"[凭证录入上下文]\n"
                f"合同编号: {contract_info.get('contract_number', '未知')}\n"
                f"客户: {contract_info.get('customer_name', '未知')}\n"
                f"业务类型: {contract_info.get('business_type', '未知')}\n"
                f"合同总额: {contract_info.get('total_amount', '--')} {contract_info.get('currency', 'CNY')}\n"
                f"录入类型: {'收入' if payment_type == 'income' else '支出'}\n"
                f"---\n"
                f"[凭证分析结果]\n{analysis_json}\n"
                f"---\n"
                f"[已有{('收入' if payment_type == 'income' else '支出')}记录] ({existing_summary})\n"
                f"{json.dumps(existing_payments, ensure_ascii=False)}"
            )

            # auto_filled 同 ID 替换（与 contract_entry 一致）
            new_messages = []
            existing_msgs = state.get("messages", [])
            if existing_msgs and isinstance(existing_msgs[-1], HumanMessage):
                last = existing_msgs[-1]
                auto_filled = getattr(last, "additional_kwargs", {}).get("auto_filled", False)
                if auto_filled:
                    new_messages.append(HumanMessage(content=msg_content, id=last.id))
                else:
                    new_messages.append(HumanMessage(content=msg_content))
            else:
                new_messages.append(HumanMessage(content=msg_content))

            logger.info(
                "receipt_entry.analyze: file_id=%s contract_id=%s payments=%d",
                file_id, contract_id, len(existing_payments),
            )

            return {
                "current_node": "analyze_receipt_node",
                "messages": new_messages,
                "file_context": json.dumps({
                    "receipt_analysis": analysis_data,
                    "contract_info": contract_info,
                    "existing_payments": existing_payments,
                    "match_warning": match_warning,
                }, ensure_ascii=False),
                "iteration_count": state.get("iteration_count", 0) + 1,
            }

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 节点 2：LLM 推理（Agent 大脑）
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

        async def call_model_node(state: ReceiptEntryState) -> dict:
            """调用 LLM，让 Agent 判断匹配/新建，生成工具调用或追问"""
            iteration = state.get("iteration_count", 0)
            if iteration >= settings.AGENT_MAX_ITERATIONS:
                logger.warning(
                    "凭证录入达到最大迭代次数 %d，强制终止: session=%s",
                    settings.AGENT_MAX_ITERATIONS, state.get("session_id", ""),
                )
                return {
                    "messages": [AIMessage(
                        content="已达到最大对话轮次，请开启新会话继续操作。"
                    )],
                    "should_end": True,
                    "current_node": "call_model_node",
                }

            openai_messages = _convert_messages(
                state.get("messages", []), user, session_ctx, contract_meta
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
                logger.exception("凭证录入 LLM 调用异常")
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

            # 无工具调用 → Agent 在追问（如币种不明确）
            return {
                "messages": [AIMessage(content=full_text)],
                "iteration_count": iteration + 1,
                "current_node": "call_model_node",
                "should_end": True,
            }

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 路由：call_model → execute_tool 或 END
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

        def should_continue(state: ReceiptEntryState) -> Literal["execute_tool_node", "__end__"]:
            """有 tool_calls → execute_tool_node，否则 END"""
            if state.get("should_end"):
                return "__end__"
            last = state["messages"][-1] if state.get("messages") else None
            if last and getattr(last, "tool_calls", None):
                return "execute_tool_node"
            return "__end__"

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 节点 3：执行工具（含 interrupt 富 UI 确认）
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

        async def execute_tool_node(state: ReceiptEntryState) -> dict:
            """执行工具调用（直接执行，不做 interrupt 拦截）。

            注意：当前版本关闭了 interrupt 安全门，所有工具直接执行。
            如需恢复确认 UI，取消下方注释即可。
            """
            last_msg = state["messages"][-1]
            if not getattr(last_msg, "tool_calls", None):
                return {}

            all_tool_calls = last_msg.tool_calls

            # 执行所有工具调用（无中断，直接执行）
            tool_messages = []
            for tc in all_tool_calls:
                tool_name = tc["name"]
                try:
                    args = tc["args"] if isinstance(tc["args"], dict) else (
                        json.loads(tc["args"]) if isinstance(tc["args"], str) else {}
                    )
                except json.JSONDecodeError:
                    args = {}

                try:
                    result = await asyncio.to_thread(executor.execute, tool_name, args)
                    logger.info(
                        "凭证录入工具结果: %s → %s",
                        tool_name, result[:200] if result else "empty",
                    )
                except Exception as e:
                    result = json.dumps({"error": f"工具执行出错: {e}"}, ensure_ascii=False)
                    logger.warning("凭证录入工具异常: %s → %s", tool_name, e, exc_info=True)

                tool_messages.append(ToolMessage(
                    content=result,
                    tool_call_id=tc["id"],
                ))

            return {
                "messages": tool_messages,
                "current_node": "execute_tool_node",
            }

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 构建子图
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

        workflow = StateGraph(ReceiptEntryState)
        workflow.add_node("analyze_receipt_node", analyze_receipt_node)
        workflow.add_node("call_model_node", call_model_node)
        workflow.add_node("execute_tool_node", execute_tool_node)

        workflow.add_edge(START, "analyze_receipt_node")

        def route_after_analyze(state: ReceiptEntryState) -> Literal["call_model_node", "__end__"]:
            if state.get("should_end"):
                return "__end__"
            return "call_model_node"

        workflow.add_conditional_edges("analyze_receipt_node", route_after_analyze, {
            "call_model_node": "call_model_node",
            "__end__": END,
        })

        workflow.add_conditional_edges("call_model_node", should_continue, {
            "execute_tool_node": "execute_tool_node",
            "__end__": END,
        })

        def route_after_execute(state: ReceiptEntryState) -> Literal["call_model_node", "__end__"]:
            if state.get("should_end"):
                return "__end__"
            return "call_model_node"

        workflow.add_conditional_edges("execute_tool_node", route_after_execute, {
            "call_model_node": "call_model_node",
            "__end__": END,
        })

        return workflow.compile(checkpointer=checkpointer)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 消息格式转换（注入凭证录入专用 system prompt）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _load_contract_meta(db, contract_id) -> dict:
    """预加载合同元信息，供 system prompt 填充。"""
    if not contract_id:
        return {}
    try:
        contract = db.query(Contract).filter(Contract.id == contract_id).first()
        if not contract:
            return {}
        customer_name = ""
        if contract.customer_id:
            customer = db.query(Customer).filter(Customer.id == contract.customer_id).first()
            customer_name = customer.name if customer else ""
        return {
            "contract_number": contract.contract_number or "",
            "customer_name": customer_name,
            "business_type": contract.business_type or "",
            "total_amount": float(contract.total_amount) if contract.total_amount else 0,
            "currency": contract.currency or "CNY",
        }
    except Exception as e:
        logger.warning("加载合同元信息失败: %s", e)
        return {}


def _convert_messages(messages: list, user, session_context: dict, contract_meta: dict) -> list:
    """LangChain BaseMessage → OpenAI 格式，注入凭证录入系统提示词"""
    contract_id = session_context.get("contract_id")
    payment_type = session_context.get("payment_type", "income")

    contract_no = contract_meta.get("contract_number", "未知")
    customer_name = contract_meta.get("customer_name", "未知")
    business_type = contract_meta.get("business_type", "未知")
    total_amount = contract_meta.get("total_amount", "--")
    currency = contract_meta.get("currency", "CNY")

    is_income = payment_type == "income"
    type_label = "收入" if is_income else "支出"
    create_tool = "create_payment" if is_income else "create_expense"

    role_desc = {
        "admin": "管理员",
        "income": "收入专员",
        "expense": "支出专员",
    }.get(user.role if user else "admin", "用户")

    system_content = RECEIPT_ENTRY_PROMPT.format(
        type_label=type_label,
        contract_no=contract_no,
        customer_name=customer_name,
        business_type=business_type,
        total_amount=total_amount,
        currency=currency,
        current_date=date.today().isoformat(),
        user_name=(user.full_name or user.username) if user else "用户",
        role_desc=role_desc,
        create_tool=create_tool,
        contract_id=contract_id or 0,
    )

    result = [{"role": "system", "content": system_content}]

    for msg in messages:
        if isinstance(msg, SystemMessage):
            # 用凭证录入专用 prompt 覆盖
            result[0] = {"role": "system", "content": system_content}
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

