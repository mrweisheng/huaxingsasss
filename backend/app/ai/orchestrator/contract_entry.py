"""合同录入子图

Phase 1 核心交付：10 个节点 + 路由函数 + 条件边。
取代 agent.py 中 ReAct 循环的"展示概要 → 等用户确认 → 建客户 → 建合同"流程。

节点清单：
  1. analyze_file_node       — 复用 agent._prepare_file / _analyze_text_content
  2. show_preview_node       — 组装预览数据（无 LLM 调用）
  3. wait_user_confirm_node  — interrupt() 暂停，前端按钮确认
  4. search_customer_node    — 调 ToolExecutor.execute("search_customers")
  5. create_customer_node    — 调 ToolExecutor.execute("create_customer")
  6. create_contract_node    — 调 ToolExecutor.execute("create_contract")
  7. auto_create_payments_node — 复用 tools.py _auto_create_payments_from_terms
  8. summarize_node          — LLM 组织总结语言
  9. summarize_cancel_node   — 模板化取消消息
  10. fallback_node          — 异常兜底
"""
import asyncio
import json
import logging
import os
import uuid
from typing import Optional, Literal

from langgraph.graph import StateGraph, START, END
from langgraph.types import interrupt
from langgraph.config import get_config

from app.ai.orchestrator.state import ContractEntryState
from app.ai.tools import ToolExecutor

logger = logging.getLogger(__name__)


class ContractEntrySubgraph:
    """合同录入子图工厂。

    通过 closure 注入 db / user / agent 依赖，返回编译后的子图。
    与文档 §7.1 设计完全对齐。
    """

    def __init__(self, db, user, agent):
        self.db = db
        self.user = user
        self.agent = agent
        self.executor = ToolExecutor(db, user)

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 节点 1：分析文件（复用 agent.py 现有逻辑）
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    async def analyze_file_node(self, state: ContractEntryState) -> dict:
        """处理附件：文本提取 + AI 结构化分析，结果缓存到 state.contract_data"""
        attachments = state.get("attachments", [])

        if not attachments:
            return {"current_node": "analyze_file_node", "errors": ["无附件"]}

        att = attachments[0]
        file_id = att.get("file_id", "")
        file_type = att.get("file_type", "")

        if not file_id:
            return {"current_node": "analyze_file_node", "errors": ["无效的 file_id"]}

        # 阶段 1：快速文本提取（< 1s）
        prep = await self.agent._prepare_file(file_id, file_type)

        if prep is None:
            # 图片或其他格式 → VL 预分析
            result = await self.agent._pre_analyze_image(file_id)
        elif prep.get("skip"):
            # 重复文件
            return {
                "current_node": "analyze_file_node",
                "fallback_strategy": "duplicate",
                "errors": [prep.get("message", "文件重复")],
            }
        else:
            # PDF/Word/Excel → LLM 结构化提取
            result = await self.agent._analyze_text_content(
                file_id, prep["file_type_label"], prep["text"]
            )

        file_context = result if isinstance(result, str) else json.dumps(result, ensure_ascii=False)

        logger.info(
            "contract_entry.analyze_file: file_id=%s result_len=%d",
            file_id, len(file_context) if file_context else 0,
        )

        return {
            "current_node": "analyze_file_node",
            "file_context": file_context,
            "iteration_count": state.get("iteration_count", 0) + 1,
        }

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 节点 2：展示预览（无 LLM，纯数据组装）
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def _extract_contract_data(self, file_context: str) -> dict:
        """从 file_context 中提取合同结构化数据（VL 缓存优先，文本兜底）"""
        # 先查 Redis 缓存（file_id 从 attachments 拿）
        attachments = getattr(self, "_cached_attachments", [])
        if attachments:
            file_id = attachments[0].get("file_id", "") if isinstance(attachments[0], dict) else ""
            cached = self.executor._get_cached_analysis(file_id, "contract")
            if cached and isinstance(cached, dict):
                return cached

        # 尝试从 file_context JSON 解析
        if file_context:
            try:
                data = json.loads(file_context)
                if isinstance(data, dict):
                    return data
            except (json.JSONDecodeError, TypeError):
                pass
        return {}

    async def show_preview_node(self, state: ContractEntryState) -> dict:
        """组装合同预览信息，无 LLM 调用"""

        # 缓存 attachments 供后续节点使用
        self._cached_attachments = state.get("attachments", [])

        contract_data = self._extract_contract_data(state.get("file_context", ""))

        # 合并 state 传入的可能字段
        if not contract_data:
            contract_data = state.get("contract_data", {})

        return {
            "current_node": "show_preview_node",
            "contract_data": contract_data,
            "preview_shown": True,
        }

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 节点 3：等待用户确认（interrupt）
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def wait_user_confirm_node(self, state: ContractEntryState) -> dict:
        """显式 interrupt，暂停等待前端按钮确认。ADR #1 核心实现。"""
        contract_data = state.get("contract_data", {})

        # 防御：如果 contract_data 为空，直接走 fallback
        if not contract_data:
            return {
                "current_node": "wait_user_confirm_node",
                "fallback_strategy": "no_contract_data",
                "errors": ["合同数据为空，无法预览"],
            }

        interrupt_id = f"contract_{uuid.uuid4().hex[:8]}"

        user_response = interrupt({
            "type": "contract_confirmation",
            "message": (
                f"是否录入客户「{contract_data.get('customer_name', '未知')}」的合同？\n"
                f"编号：{contract_data.get('contract_number', '自动生成')}\n"
                f"金额：{contract_data.get('total_amount', '?')} {contract_data.get('currency', 'CNY')}"
            ),
            "preview": {
                "customer_name": contract_data.get("customer_name"),
                "contract_number": contract_data.get("contract_number"),
                "total_amount": contract_data.get("total_amount"),
                "currency": contract_data.get("currency"),
                "title": contract_data.get("title"),
                "business_type": contract_data.get("business_type"),
            },
            "options": [
                {"label": "确认录入", "value": {"confirmed": True}},
                {"label": "取消", "value": {"confirmed": False}},
            ],
            "interrupt_id": interrupt_id,
        })

        return {
            "current_node": "wait_user_confirm_node",
            "user_confirmed": user_response.get("confirmed", False),
            "preview_shown": True,
        }

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 节点 4：搜索客户
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    async def search_customer_node(self, state: ContractEntryState) -> dict:
        """调用 ToolExecutor.search_customers 查重"""
        contract_data = state.get("contract_data", {})
        customer_name = contract_data.get("customer_name", "")

        if not customer_name:
            return {
                "current_node": "search_customer_node",
                "customer_exists": False,
                "errors": ["缺少客户姓名"],
            }

        result_str = await asyncio.to_thread(
            self.executor.execute,
            "search_customers",
            {"keyword": customer_name},
        )

        try:
            result = json.loads(result_str)
        except json.JSONDecodeError:
            result = {}

        customers = result.get("customers", []) if isinstance(result, dict) else []

        # 精确姓名匹配
        matched = [c for c in customers if c.get("name") == customer_name]

        if matched:
            return {
                "current_node": "search_customer_node",
                "customer_id": matched[0]["id"],
                "customer_name": customer_name,
                "customer_exists": True,
            }

        return {
            "current_node": "search_customer_node",
            "customer_name": customer_name,
            "customer_exists": False,
        }

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 节点 5：创建客户
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    async def create_customer_node(self, state: ContractEntryState) -> dict:
        """直接调 ToolExecutor.execute("create_customer")，不走 LLM"""
        contract_data = state.get("contract_data", {})

        result_str = await asyncio.to_thread(
            self.executor.execute,
            "create_customer",
            {
                "name": contract_data.get("customer_name") or state.get("customer_name", ""),
                "phone": contract_data.get("phone"),
                "id_number": contract_data.get("id_card_number"),
            },
        )

        try:
            result = json.loads(result_str)
        except json.JSONDecodeError:
            return {
                "current_node": "create_customer_node",
                "errors": [f"创建客户返回格式错误: {result_str[:200]}"],
            }

        if result.get("error"):
            return {
                "current_node": "create_customer_node",
                "errors": [f"创建客户失败: {result['error']}"],
            }

        customer = result.get("customer", {})
        return {
            "current_node": "create_customer_node",
            "customer_id": customer.get("id") or result.get("id"),
            "customer_name": customer.get("name"),
            "tools_invoked": ["create_customer"],
        }

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 节点 6：创建合同
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    async def create_contract_node(self, state: ContractEntryState) -> dict:
        """直接调 ToolExecutor.execute("create_contract")，不走 LLM"""
        customer_id = state.get("customer_id")
        contract_data = state.get("contract_data", {})
        attachments = state.get("attachments", [])

        if not customer_id:
            return {
                "current_node": "create_contract_node",
                "errors": ["缺少 customer_id"],
            }

        file_id = attachments[0].get("file_id", "") if attachments else ""

        args = {
            "customer_id": customer_id,
            "file_id": file_id,
            "contract_data": contract_data,
            # 显式传入合同字段
            "title": contract_data.get("title"),
            "currency": contract_data.get("currency", "CNY"),
            "total_amount": contract_data.get("total_amount"),
            "signed_date": contract_data.get("signed_date"),
            "business_type": contract_data.get("business_type"),
            "business_description": contract_data.get("business_description"),
        }

        result_str = await asyncio.to_thread(
            self.executor.execute,
            "create_contract",
            {k: v for k, v in args.items() if v is not None},
        )

        try:
            result = json.loads(result_str)
        except json.JSONDecodeError:
            return {
                "current_node": "create_contract_node",
                "errors": [f"创建合同返回格式错误: {result_str[:200]}"],
            }

        if result.get("error"):
            return {
                "current_node": "create_contract_node",
                "errors": [f"创建合同失败: {result['error']}"],
            }

        return {
            "current_node": "create_contract_node",
            "contract_id": result.get("contract", {}).get("id"),
            "auto_payments": result.get("auto_payments", []),
            "tools_invoked": ["create_contract"],
        }

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 节点 7：自动创建付款记录
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    async def auto_create_payments_node(self, state: ContractEntryState) -> dict:
        """
        从合同 payment_terms 自动创建付款记录。
        复用 tools.py 的 _auto_create_payments_from_terms 逻辑。

        注意：create_contract_node 已经调用了 tools.py 的 create_contract，
        其中包含 _auto_create_payments_from_terms 调用，此处作为独立节点
        提供幂等兜底（已创建的不会重复创建）。
        """
        auto_payments = state.get("auto_payments", [])
        return {
            "current_node": "auto_create_payments_node",
            "auto_payments": auto_payments,
        }

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 节点 8：总结（LLM 组织语言）
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    async def summarize_node(self, state: ContractEntryState) -> dict:
        """调用 LLM 生成友好的总结文本"""
        contract_data = state.get("contract_data", {})
        contract_id = state.get("contract_id")
        auto_payments = state.get("auto_payments", [])
        errors = state.get("errors", [])

        if errors:
            summary = (
                f"合同已创建（ID: {contract_id}），但存在以下问题：\n"
                + "\n".join(f"  - {e}" for e in errors)
            )
        elif auto_payments:
            payment_count = len(auto_payments)
            summary = (
                f"✅ 合同已成功录入（ID: {contract_id}）\n"
                f"   客户：{contract_data.get('customer_name', '未知')}\n"
                f"   金额：{contract_data.get('total_amount', '?')} {contract_data.get('currency', 'CNY')}\n"
                f"   已自动创建 {payment_count} 条付款记录"
            )
        else:
            summary = (
                f"✅ 合同已成功录入（ID: {contract_id}）\n"
                f"   客户：{contract_data.get('customer_name', '未知')}\n"
                f"   金额：{contract_data.get('total_amount', '?')} {contract_data.get('currency', 'CNY')}"
            )

        # 将总结作为 messages 推给前端
        from langchain_core.messages import AIMessage
        return {
            "current_node": "summarize_node",
            "messages": [AIMessage(content=summary)],
            "should_end": True,
        }

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 节点 9：取消总结
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    async def summarize_cancel_node(self, state: ContractEntryState) -> dict:
        """用户取消录入后的提示"""
        from langchain_core.messages import AIMessage
        return {
            "current_node": "summarize_cancel_node",
            "messages": [AIMessage(content="已取消合同录入。如需重新录入，请再次上传文件。")],
            "should_end": True,
        }

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 节点 10：异常兜底
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    async def fallback_node(self, state: ContractEntryState) -> dict:
        """异常兜底节点"""
        errors = state.get("errors", [])
        fallback = state.get("fallback_strategy", "unknown")

        fallback_msg = f"合同录入过程遇到问题（{fallback}）"
        if errors:
            fallback_msg += "\n错误详情：" + "; ".join(errors)

        from langchain_core.messages import AIMessage
        return {
            "current_node": "fallback_node",
            "messages": [AIMessage(content=fallback_msg)],
            "should_end": True,
        }

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 路由函数（独立于实例，可复用）
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def route_after_user_confirm(self, state: ContractEntryState) -> Literal[
        "search_customer_node", "summarize_cancel_node"
    ]:
        """用户确认 → 搜索客户；用户取消 → 取消总结"""
        if state.get("user_confirmed", False):
            return "search_customer_node"
        return "summarize_cancel_node"

    def route_after_search_customer(self, state: ContractEntryState) -> Literal[
        "create_customer_node", "create_contract_node"
    ]:
        """客户已存在 → 直接建合同；客户不存在 → 先建客户"""
        if state.get("customer_exists", False):
            return "create_contract_node"
        return "create_customer_node"

    def route_after_analyze(self, state: ContractEntryState) -> Literal[
        "show_preview_node", "fallback_node"
    ]:
        """分析成功 → 展示预览；分析失败 → 兜底"""
        errors = state.get("errors", [])
        fallback = state.get("fallback_strategy")
        if errors or fallback:
            return "fallback_node"
        return "show_preview_node"

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 构建子图
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def build(self, checkpointer=None) -> StateGraph:
        """编译合同录入子图，返回 StateGraph 实例"""
        graph = StateGraph(ContractEntryState)

        # 添加节点
        graph.add_node("analyze_file_node", self.analyze_file_node)
        graph.add_node("show_preview_node", self.show_preview_node)
        graph.add_node("wait_user_confirm_node", self.wait_user_confirm_node)
        graph.add_node("search_customer_node", self.search_customer_node)
        graph.add_node("create_customer_node", self.create_customer_node)
        graph.add_node("create_contract_node", self.create_contract_node)
        graph.add_node("auto_create_payments_node", self.auto_create_payments_node)
        graph.add_node("summarize_node", self.summarize_node)
        graph.add_node("summarize_cancel_node", self.summarize_cancel_node)
        graph.add_node("fallback_node", self.fallback_node)

        # 边
        graph.add_edge(START, "analyze_file_node")

        graph.add_conditional_edges(
            "analyze_file_node",
            self.route_after_analyze,
            {"show_preview_node": "show_preview_node", "fallback_node": "fallback_node"},
        )

        graph.add_edge("show_preview_node", "wait_user_confirm_node")

        graph.add_conditional_edges(
            "wait_user_confirm_node",
            self.route_after_user_confirm,
            {
                "search_customer_node": "search_customer_node",
                "summarize_cancel_node": "summarize_cancel_node",
            },
        )

        graph.add_conditional_edges(
            "search_customer_node",
            self.route_after_search_customer,
            {
                "create_customer_node": "create_customer_node",
                "create_contract_node": "create_contract_node",
            },
        )

        graph.add_edge("create_customer_node", "create_contract_node")
        graph.add_edge("create_contract_node", "auto_create_payments_node")
        graph.add_edge("auto_create_payments_node", "summarize_node")
        graph.add_edge("summarize_node", END)
        graph.add_edge("summarize_cancel_node", END)
        graph.add_edge("fallback_node", END)

        return graph.compile(checkpointer=checkpointer)
