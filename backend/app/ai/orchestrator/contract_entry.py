"""合同录入子图

Phase 1 核心交付：9 个节点 + 路由函数 + 条件边。
取代 agent.py 中 ReAct 循环的"展示概要 → 等用户确认 → 建客户 → 建合同"流程。

节点清单：
  1. analyze_file_node       — 直调 ContractAnalyzer.resolve_file_path + .analyze_file
  2. show_preview_node       — 组装预览数据（无 LLM 调用）
  3. wait_user_confirm_node  — interrupt() 暂停，前端按钮确认
  4. search_customer_node    — 调 ToolExecutor.execute("search_customers")
  5. create_customer_node    — 调 ToolExecutor.execute("create_customer")
  6. create_contract_node    — 调 ToolExecutor.execute("create_contract")
                              （含 tools._auto_create_payments_from_terms）
  7. summarize_node          — 模板化总结（Phase 1 暂不接 LLM）
  8. summarize_cancel_node   — 模板化取消消息
  9. fallback_node           — 异常兜底
"""
import asyncio
import json
import logging
import uuid
from typing import Optional, Literal

from langgraph.graph import StateGraph, START, END
from langgraph.types import interrupt
from langchain_core.messages import AIMessage

from app.ai.orchestrator.state import ContractEntryState
from app.ai.tools import ToolExecutor
from app.services.contract_analyzer import ContractAnalyzer, _get_cached_analysis

logger = logging.getLogger(__name__)


class ContractEntrySubgraph:
    """合同录入子图工厂。

    通过 closure 注入 db / user 依赖，返回编译后的子图。
    PR-B-2 改造：去除对 ReAct Agent 私有方法的依赖，子图完全独立。
    """

    def __init__(self, db, user, mode: str = "chat",
                 session_context: Optional[dict] = None, session_id: str = ""):
        self.db = db
        self.user = user
        # mode / session_context 必须注入到本子图闭包内的 ToolExecutor
        self.executor = ToolExecutor(db, user)
        self.executor.mode = mode
        self.executor.session_context = session_context or {}
        # session_id 注入 executor，供工具层内部缓存使用
        self.executor.session_id = session_id

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 节点 1：分析文件（PR-B-2：直调 ContractAnalyzer，不再依赖 ReAct Agent）
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    async def analyze_file_node(self, state: ContractEntryState) -> dict:
        """处理附件：解析文件 → 调 ContractAnalyzer（已含类型检测/文本提取/LLM/查重/缓存）"""
        attachments = state.get("attachments", [])

        if not attachments:
            return {"current_node": "analyze_file_node", "errors": ["无附件"]}

        att = attachments[0]
        file_id = att.get("file_id", "")

        if not file_id:
            return {"current_node": "analyze_file_node", "errors": ["无效的 file_id"]}

        # 1) 解析文件路径（含 glob 兜底 + 路径穿越防御）
        file_path = ContractAnalyzer.resolve_file_path(file_id, self.user.id)
        if not file_path:
            return {
                "current_node": "analyze_file_node",
                "errors": [f"文件不存在: {file_id}"],
            }

        # 2) 调 ContractAnalyzer.analyze_file（同步方法，asyncio.to_thread 包装避免阻塞事件循环）
        result = await asyncio.to_thread(
            ContractAnalyzer.analyze_file, file_path, self.db, self.user.id
        )

        if result.get("duplicate_detected"):
            return {
                "current_node": "analyze_file_node",
                "fallback_strategy": "duplicate",
                "errors": [result.get("message", "文件重复")],
            }

        if not result.get("success"):
            return {
                "current_node": "analyze_file_node",
                "errors": [result.get("error", "分析失败")],
            }

        file_context = json.dumps(result["data"], ensure_ascii=False)

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

    @staticmethod
    def _normalize_contract_data(data: dict) -> dict:
        """将 LLM 嵌套输出（party_b.name 等）展平为下游期望的扁平 key。

        CONTRACT_ANALYSIS_PROMPT 输出 party_b: {name, phone, id_number}，
        但 search_customer / create_customer / wait_user_confirm 各节点读
        customer_name / phone / id_card_number。此方法做一次性映射。
        """
        party_b = data.get("party_b")
        if isinstance(party_b, dict):
            if not data.get("customer_name") and party_b.get("name"):
                data["customer_name"] = party_b["name"]
            if not data.get("phone") and party_b.get("phone"):
                data["phone"] = party_b["phone"]
            if not data.get("id_card_number") and party_b.get("id_number"):
                data["id_card_number"] = party_b["id_number"]
        return data

    def _extract_contract_data(self, file_context: str, file_id: str = "") -> dict:
        """从 file_context 中提取合同结构化数据（VL 缓存优先，文本兜底）"""
        # 先查 Redis 缓存（PR-B-1: 用 contract_analyzer 的模块级函数，key 格式 l:contract:{file_id}）
        if file_id:
            cached = _get_cached_analysis(file_id)
            if cached and isinstance(cached, dict):
                return self._normalize_contract_data(cached)

        # 尝试从 file_context JSON 解析
        if file_context:
            try:
                data = json.loads(file_context)
                if isinstance(data, dict):
                    return self._normalize_contract_data(data)
            except (json.JSONDecodeError, TypeError):
                pass
        return {}

    async def show_preview_node(self, state: ContractEntryState) -> dict:
        """组装合同预览信息，无 LLM 调用"""
        attachments = state.get("attachments", [])
        file_id = attachments[0].get("file_id", "") if attachments else ""

        contract_data = self._extract_contract_data(
            state.get("file_context", ""), file_id
        )

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
                f"编号：{contract_data.get('contract_number') or '自动生成'}\n"
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
        """调用 ToolExecutor.search_customers 查重。

        同名客户去重策略：精确匹配 → 按 contract_count 倒序 → 取第一条。
        contract_count 越大表示该客户与业务关联越密切，优先复用避免误创建重复客户。
        """
        contract_data = state.get("contract_data", {})
        customer_name = contract_data.get("customer_name", "")

        if not customer_name:
            return {
                "current_node": "search_customer_node",
                "customer_exists": False,
                "errors": ["缺少客户姓名"],
            }

        # ⚠️ 字段名必须用 `name`，不是 `keyword`
        # search_customers 工具定义（tools.py:316-322 + 2509-2521）只接受
        # name/phone/wechat_group/limit 四个参数。传 `keyword` 会被静默忽略，
        # 导致 has_filter=False 走"返回全局统计+样例"分支，匹配不到任何客户，
        # 后果：customer_exists=False → 误判客户不存在 → 重复创建。
        result_str = await asyncio.to_thread(
            self.executor.execute,
            "search_customers",
            {"name": customer_name},
        )

        try:
            result = json.loads(result_str)
        except json.JSONDecodeError:
            result = {}

        customers = result.get("customers", []) if isinstance(result, dict) else []

        # 精确姓名匹配：避免 "张三" 匹配到 "张三丰" / "小张三" 等误关联
        matched = [c for c in customers if c.get("name") == customer_name]

        if matched:
            # 同名客户按业务关联度排序：合同数倒序，再按客户 ID 升序（保证稳定）
            # 合同数多 = 老客户 = 优先复用，避免误创建重复
            best = sorted(
                matched,
                key=lambda c: (-(c.get("contract_count") or 0), c.get("id") or 0),
            )[0]
            return {
                "current_node": "search_customer_node",
                "customer_id": best["id"],
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
    # 节点 7：总结（LLM 组织语言）
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    async def summarize_node(self, state: ContractEntryState) -> dict:
        """模板化生成合同录入总结。

        注意：文档 §7.1 计划用 LLM 组织语言，但 Phase 1 实际走模板字符串。
        auto_payments 已在 create_contract_node 调 tools.create_contract 时
        由 _auto_create_payments_from_terms 创建，本节点仅做总结展示。
        """
        contract_data = state.get("contract_data", {})
        contract_id = state.get("contract_id")
        auto_payments = state.get("auto_payments", [])
        errors = state.get("errors", [])

        if errors:
            # 合同可能创建失败（contract_id 为 None），不显示"已创建"误导用户
            created = bool(contract_id)
            head = f"合同已录入（ID: {contract_id}）" if created else "合同录入未完成"
            summary = (
                f"{head}，但存在以下问题：\n"
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

        return {
            "current_node": "summarize_node",
            "messages": [AIMessage(content=summary)],
            "should_end": True,
        }

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 节点 8：取消总结
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    async def summarize_cancel_node(self, state: ContractEntryState) -> dict:
        """用户取消录入后的提示"""
        return {
            "current_node": "summarize_cancel_node",
            "messages": [AIMessage(content="已取消合同录入。如需重新录入，请再次上传文件。")],
            "should_end": True,
        }

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 节点 9：异常兜底
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    async def fallback_node(self, state: ContractEntryState) -> dict:
        """异常兜底节点。按 fallback_strategy 分支返回不同提示，避免笼统错误。"""
        errors = state.get("errors", [])
        fallback = state.get("fallback_strategy", "unknown")

        # 各 fallback_strategy 专属消息；通用兜底保留 unknown 分支
        strategy_messages = {
            "duplicate": "该文件之前已用于创建合同（数据库已有 file_hash 记录），无需重复录入。\n"
                         "如需查看已有合同，请使用 search_contracts 工具。",
            "no_contract_data": "未能从文件中识别出客户姓名和合同编号，无法直接录入。\n"
                                "如需录入合同，请补充以下信息后重试：\n"
                                "- 客户姓名 + 联系电话\n"
                                "- 合同编号 + 签订日期 + 金额 + 币种",
            "unknown": "合同录入过程遇到未知问题，请稍后重试或联系管理员。",
        }
        fallback_msg = strategy_messages.get(fallback, f"合同录入过程遇到问题（{fallback}）")
        if errors and fallback not in ("duplicate", "no_contract_data"):
            # 已知策略的友好提示已含根因，不重复错误详情
            fallback_msg += "\n错误详情：" + "; ".join(errors)

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

        # 添加节点（9 个，auto_create_payments_node 已合并到 create_contract_node
        # 内 tools._auto_create_payments_from_terms，避免空 pass-through 节点）
        graph.add_node("analyze_file_node", self.analyze_file_node)
        graph.add_node("show_preview_node", self.show_preview_node)
        graph.add_node("wait_user_confirm_node", self.wait_user_confirm_node)
        graph.add_node("search_customer_node", self.search_customer_node)
        graph.add_node("create_customer_node", self.create_customer_node)
        graph.add_node("create_contract_node", self.create_contract_node)
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
        graph.add_edge("create_contract_node", "summarize_node")
        graph.add_edge("summarize_node", END)
        graph.add_edge("summarize_cancel_node", END)
        graph.add_edge("fallback_node", END)

        return graph.compile(checkpointer=checkpointer)
