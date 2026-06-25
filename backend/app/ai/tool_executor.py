"""Agent 工具执行器 v2 — 精简版

变更（相对 tools.py）：
  - 继承原 ToolExecutor，复用所有业务逻辑
  - 删除 mode guard / document guard / set_pending_plan
  - 新增 analyze_files
  - 凭证录入对话流（v3）：analyze_receipt / create_income_payment / create_expense_payment / override_receipt_mismatch
  - 工具集 20→16→20

设计原则：
  - 轻量确认：写入工具执行前检查 LLM 上文是否展示确认请求
  - 凭证录入对话流：analyze_receipt 同步前置 + 三态判定，写库直接 paid（不走异步 verify_receipt）
  - 写入工具按 session_mode 在 unified_agent 层做工具集过滤
"""
import json
import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from app.ai.tool_executor_base import ToolExecutor
from app.schemas.contract_additional_item import AdditionalItemCreate, AdditionalItemUpdate
from app.services.contract_additional_item_service import AdditionalItemService
from app.services.file_analyzer import FileAnalyzer
from app.services.payment_service import PaymentService
from app.services.payment_account_service import PaymentAccountService
from app.services.receipt_matcher import match_receipt, pick_payment_term
from app.utils.file_utils import resolve_file_path
from app.models.payment import Payment
from app.models.contract import Contract
from app.models.customer import Customer
from app.models.payment_account import PaymentAccount

logger = logging.getLogger(__name__)

# 工具白名单：与文件末尾 TOOL_DEFINITIONS 同步。模块加载时由下方 _ALLOWED_TOOLS
# 重新赋值（Python 同一模块内语句按顺序执行；这里先用占位避免导入期未定义）。
_ALLOWED_TOOLS: frozenset = frozenset()  # type: ignore[assignment]


class ToolExecutorV2(ToolExecutor):
    """精简版工具执行器。

    继承原 ToolExecutor，复用所有查询/写入工具的业务逻辑。
    重写 execute() 入口，删除 mode guard / document guard。
    """

    def __init__(self, db, user, session_id: Optional[str] = None):
        super().__init__(db, user, session_id)
        # 删除 mode 相关成员（不再需要模式锁定）
        self.mode = None
        self.session_context = None
        self._document_context = None

    # ═══════════════════════════════════════════════════════════
    # 辅助方法
    # ═══════════════════════════════════════════════════════════

    def _build_payment_description(
        self, amount: float, currency: str, installment_name: str = "",
        business_hint: str = "", payee_name: str = None, contract=None,
    ) -> str:
        """自动生成付款记录的 description 字段。

        格式："{币种符号}{金额} {期数名} [{业务上下文}]"
        例如："港币5万 定金 30系埃尔法"、"人民币5万 定金 购买现牌粤Z7N80港"
        """
        symbol = "HK$" if currency == "HKD" else "¥"
        amt = f"{amount:,.0f}" if amount >= 1000 else str(int(amount))
        parts = [f"{symbol}{amt}"]
        if installment_name:
            parts.append(installment_name)
        if payee_name:
            parts.append(f"→{payee_name}")
        # 补充业务上下文
        ctx = business_hint or ""
        if contract and hasattr(contract, 'business_description') and contract.business_description:
            ctx = contract.business_description
        if ctx:
            parts.append(ctx[:20])
        return " ".join(parts)[:100]

    def _match_payment_term_label(
        self, contract: Contract, amount: float, currency: str, payment_type: str = "income",
    ) -> str:
        """从合同付款计划中找出最匹配的一期，返回其名字（如"定金"/"尾款"）作为描述参考。

        匹配规则（仅用于丰富 description，不写入 installment_number 等结构化字段）：
          1. 币种相同
          2. 金额差异 < 1% 或 < 100
          3. 该期未被同合同已有 payment 命中过（按 installment_name 去重）
          4. 多期同金额时按 payment_terms 数组顺序取第一个未命中的

        匹配不上返回空字符串——description 退化为"金额 + 业务"，不会出错。
        仅 income 类型走该逻辑；expense 通常无对应付款计划。
        """
        if payment_type != "income" or not contract:
            return ""
        contract_data = getattr(contract, "contract_data", None) or {}
        if not isinstance(contract_data, dict):
            return ""
        terms = contract_data.get("payment_terms") or []
        if not terms or not amount or amount <= 0:
            return ""

        # 已用过的 installment_name（同合同所有 income payment）
        used_names = {
            row[0] for row in self.db.query(Payment.installment_name)
            .filter(
                Payment.contract_id == contract.id,
                Payment.type == "income",
                Payment.is_deleted == False,
                Payment.installment_name.isnot(None),
            ).all()
        }

        for term in terms:
            term_name = (term.get("name") or "").strip()
            if not term_name or term_name in used_names:
                continue
            term_currency = (term.get("currency") or contract.currency or "CNY").upper()
            if term_currency != (currency or "").upper():
                continue
            try:
                term_amount = float(term.get("amount", 0))
            except (TypeError, ValueError):
                continue
            if term_amount <= 0:
                continue
            diff = abs(term_amount - amount)
            if diff < 100 or diff / term_amount < 0.01:
                return term_name
        return ""

    def _resolve_payment_description(
        self, receipt_data: dict, contract, amount: float,
        currency: str, payment_type: str = "income",
    ) -> str:
        """统一 description 生成逻辑，所有凭证→付款路径共用。

        优先级：
          1. 凭证原文 — payment_purpose（"该款项系付"等字段，最有价值）
          2. 业务推断 — business_hint（"两地牌相关费用"等，笼统但有）
          3. 兜底拼接 — 期数匹配 + _build_payment_description
        """
        # 1. 凭证提取的具体内容优先
        hint = (
            receipt_data.get("payment_purpose", "")
            or receipt_data.get("business_hint", "")
            or ""
        )
        if hint:
            return hint[:100]

        # 2. 兜底：期数匹配 + 格式化拼接
        term_label = self._match_payment_term_label(
            contract, amount or 0, currency, payment_type,
        )
        payee = (
            receipt_data.get("payee_name", "")
            if payment_type == "expense" else None
        )
        return self._build_payment_description(
            amount=amount, currency=currency,
            installment_name=term_label,
            business_hint="",
            payee_name=payee, contract=contract,
        )

    # ═══════════════════════════════════════════════════════════
    # 统一执行入口（简化版，无 mode guard / document guard）
    # ═══════════════════════════════════════════════════════════

    def execute(self, tool_name: str, arguments: dict) -> str:
        """统一执行入口 — 白名单 + 轻量 mode guard。

        - 白名单校验：阻止 LLM 误传/恶意传非 TOOL_DEFINITIONS 中的方法名
        - mode guard：当 self.mode 是 receipt_income/receipt_expense 时，
          只允许调用 MODE_TOOL_WHITELIST[mode] 内的工具
        """
        if tool_name not in _ALLOWED_TOOLS:
            logger.warning("非白名单工具调用拒绝: %s", tool_name)
            return json.dumps({
                "error": f"未知工具: {tool_name}",
                "hint": "仅允许调用 TOOL_DEFINITIONS 中声明的工具。",
            }, ensure_ascii=False)

        # ── mode guard：录收入会话只允许调收入工具集，录支出反之 ──
        if self.mode and not is_tool_allowed_in_mode(tool_name, self.mode):
            logger.warning("工具不在当前模式允许列表: tool=%s mode=%s", tool_name, self.mode)
            return json.dumps({
                "error": f"当前会话模式（{self.mode}）不允许调用工具：{tool_name}",
                "hint": "凭证录入会话仅暴露与当前收支类型相关的工具",
            }, ensure_ascii=False)

        handler = getattr(self, tool_name, None)
        if not handler:
            # 理论上白名单已过滤，这里是双保险
            logger.warning("未知工具调用: %s", tool_name)
            return json.dumps({"error": f"未知工具: {tool_name}"}, ensure_ascii=False)

        args_preview = json.dumps(arguments, ensure_ascii=False, default=str)[:300]
        logger.info("工具调用: %s | 参数: %s", tool_name, args_preview)

        try:
            result = handler(**arguments)
            return result
        except Exception as e:
            logger.exception("工具执行失败: %s", tool_name)
            return json.dumps({"error": f"工具执行失败: {str(e)}"}, ensure_ascii=False)

    # ═══════════════════════════════════════════════════════════
    # 🆕 analyze_files — LLM 可主动调度的文件分析工具
    # ═══════════════════════════════════════════════════════════

    def analyze_files(
        self,
        file_ids: list[str],
        purpose: str = "auto",
    ) -> str:
        """分析上传的文件。自动识别类型（合同/凭证/证件/车辆照片/群聊截图/其他），提取结构化信息。

        Args:
            file_ids: 文件ID列表（支持批量）
            purpose: 分析目的（auto=自动判断, contract/receipt/group_chat。其他类型会被拒绝）

        Returns:
            JSON: {
                "success": True,
                "files": [
                    {
                        "file_id": "...",
                        "type": "contract"|"receipt"|...,
                        "data": {...},       # 类型对应的结构化数据
                        "confidence": 0.0-1.0,
                        "file_type": "image"|"pdf"|"document",
                    },
                    ...
                ]
            }
        """
        if not file_ids:
            return json.dumps({"success": False, "error": "请提供至少一个 file_id"}, ensure_ascii=False)

        results = []
        for file_id in file_ids:
            try:
                # 解析文件路径
                file_path = resolve_file_path(file_id, self.user.id)
                if not file_path:
                    results.append({
                        "file_id": file_id, "success": False,
                        "error": f"文件不存在: {file_id}",
                    })
                    continue

                # 检查缓存
                cached = self._get_cached_analysis(file_id, "contract") \
                    or self._get_cached_analysis(file_id, "receipt")
                # 故意不缓存 auto 模式：auto 是探索性入口，每次重新分析以获取最新结果；
                # purpose=contract/receipt 时走缓存，避免重复消耗 token。
                if cached and purpose not in ("auto",):
                    # 注入 file_id 到缓存数据中
                    cached_with_fid = dict(cached) if isinstance(cached, dict) else cached
                    if isinstance(cached_with_fid, dict):
                        cached_with_fid.setdefault("_source_file_id", file_id)
                    results.append({
                        "file_id": file_id, "success": True,
                        "type": purpose, "data": cached_with_fid,
                        "source": "cache",
                    })
                    continue

                # 调 FileAnalyzer（传入 contract_id 用于凭证去重，receipt 模式下在 VL 分析前拦截）
                file_name = file_id  # file_id 作为文件名 fallback
                session_contract_id = (
                    self.session_context.get("contract_id")
                    if isinstance(self.session_context, dict) else None
                )
                analysis = FileAnalyzer.analyze(
                    file_path, file_name,
                    purpose=purpose,
                    db=self.db,
                    user_id=self.user.id,
                    contract_id=session_contract_id,
                )

                if analysis.get("duplicate_detected"):
                    # 合同去重 / 凭证去重 都走这个分支（VL 分析前已拦截）
                    dup_type = analysis.get("type", "contract")
                    if dup_type == "receipt":
                        results.append({
                            "file_id": file_id, "success": True,
                            "type": "receipt",
                            "duplicate_detected": True,
                            "existing_payment": analysis.get("existing_payment"),
                            "message": "该凭证已在此合同下录入过",
                        })
                    else:
                        results.append({
                            "file_id": file_id, "success": True,
                            "type": "contract",
                            "duplicate_detected": True,
                            "existing_contract": analysis.get("existing_contract"),
                            "message": "该文件已在系统中存在对应的合同记录",
                        })
                elif analysis.get("success"):
                    # 注入 _source_file_id 到 data 中（供后续工具解析凭证路径）
                    data_with_fid = dict(analysis["data"]) if isinstance(analysis["data"], dict) else analysis["data"]
                    if isinstance(data_with_fid, dict):
                        data_with_fid["_source_file_id"] = file_id
                    results.append({
                        "file_id": file_id, "success": True,
                        "type": analysis["type"],
                        "data": data_with_fid,
                        "confidence": analysis.get("confidence"),
                        "file_type": analysis.get("file_type"),
                    })
                    # 缓存结果
                    self._cache_analysis(file_id, analysis["type"], analysis["data"])
                else:
                    results.append({
                        "file_id": file_id, "success": False,
                        "error": analysis.get("error", "分析失败"),
                    })
            except Exception as e:
                logger.exception("analyze_files 失败: file_id=%s", file_id)
                results.append({
                    "file_id": file_id, "success": False,
                    "error": str(e),
                })

        return json.dumps({
            "success": True,
            "files": results,
            "total": len(results),
        }, ensure_ascii=False, default=str)

    # ═══════════════════════════════════════════════════════════
    # 🔄 update_payment — 增强：支持 description 自动生成
    # ═══════════════════════════════════════════════════════════

    def update_payment(self, **kwargs) -> str:
        """更新付款记录。增强：传入 receipt_data 时自动生成 description。"""
        payment_id = kwargs.get("payment_id")
        receipt_data = kwargs.get("receipt_data")

        # 前缀保护：原 notes 含「[无凭证支出]」审计标记 → 用户/LLM 改 notes 时自动补回
        # 防止审计标记被无意覆盖。仅在传入 notes 字段且不带前缀时介入。
        new_notes = kwargs.get("notes")
        if payment_id and new_notes is not None:
            from app.core.payment_audit import NO_RECEIPT_NOTE_PREFIX
            existing = self.db.query(Payment).filter(Payment.id == payment_id).first()
            if existing and (existing.notes or "").startswith(NO_RECEIPT_NOTE_PREFIX):
                if not new_notes.startswith(NO_RECEIPT_NOTE_PREFIX):
                    kwargs["notes"] = f"{NO_RECEIPT_NOTE_PREFIX} {new_notes}".strip()

        # 先调父类完成核心更新
        result_str = super().update_payment(**kwargs)
        try:
            result = json.loads(result_str)
        except json.JSONDecodeError:
            return result_str

        if not result.get("success") or not payment_id:
            return result_str

        # 如果传入凭证数据但 description 未设置 → 自动生成（统一路径）
        if isinstance(receipt_data, dict) and not kwargs.get("description"):
            payment = self.db.query(Payment).filter(Payment.id == payment_id).first()
            if payment:
                contract = payment.contract
                desc = self._resolve_payment_description(
                    receipt_data, contract,
                    float(payment.amount) if payment.amount else 0,
                    payment.currency or "CNY",
                )
                payment.description = desc
                self.db.commit()
                result["payment"]["description"] = desc

        return json.dumps(result, ensure_ascii=False, default=str)

    # ═══════════════════════════════════════════════════════════
    # create_contract — v2 不再增强：合同录入不创建 payment，无需补 description
    # （基类已只生成付款计划，auto_payments 永远为 []）
    # ═══════════════════════════════════════════════════════════

    # 注：曾经在此为基类返回的 auto_payments 批量补齐 description 字段。
    # 改造后合同录入零 payment 写入，子类不再需要覆写该方法。

    # ═══════════════════════════════════════════════════════════
    # 🔄 query_payments — 增强：支持分组聚合（替代 get_payment_summary / get_expense_summary）
    # ═══════════════════════════════════════════════════════════

    def query_payments(self, **kwargs) -> str:
        """付款记录查询，支持按合同/状态/类型/日期筛选，支持分组聚合。

        分组聚合：group_by=contract 时，按合同汇总（替代 get_payment_summary/get_expense_summary）
        """
        group_by = kwargs.pop("group_by", None)
        if group_by:
            return self._query_payments_grouped(group_by, **kwargs)
        return super().query_payments(**kwargs)

    def _query_payments_grouped(self, group_by: str, **kwargs) -> str:
        """按维度分组聚合付款数据"""
        from sqlalchemy import func

        query = self.db.query(
            Payment.contract_id,
            Payment.type,
            Payment.currency,
            func.count(Payment.id).label("count"),
            func.coalesce(func.sum(Payment.paid_amount), 0).label("total"),
        ).filter(
            Payment.is_deleted == False,
            Payment.status == "paid",
        )

        if kwargs.get("contract_id"):
            query = query.filter(Payment.contract_id == kwargs["contract_id"])

        # 角色权限：仅按 payment.type 隔离收支，合同对所有角色可见
        if self.user.role == "income":
            query = query.filter(Payment.type == "income")
        elif self.user.role == "expense":
            query = query.filter(Payment.type == "expense")

        groups = {"contract": Payment.contract_id}
        group_col = groups.get(group_by, Payment.contract_id)
        query = query.group_by(group_col, Payment.type, Payment.currency)

        rows = query.all()

        # 一次性查出所有相关合同 + 客户（避免 N+1）
        contract_ids = {row.contract_id for row in rows}
        contract_map = {}
        if contract_ids:
            from app.models.customer import Customer
            stmt = (
                self.db.query(Contract, Customer)
                .outerjoin(Customer, Contract.customer_id == Customer.id)
                .filter(Contract.id.in_(contract_ids))
            )
            for contract, customer in stmt.all():
                contract_map[contract.id] = (contract, customer)

        # 按 contract_id 汇总
        result = {}
        for row in rows:
            cid = row.contract_id
            if cid not in result:
                contract, customer = contract_map.get(cid, (None, None))
                result[cid] = {
                    "contract_id": cid,
                    "contract_number": contract.contract_number if contract else "",
                    "customer_name": customer.name if customer else "",
                    "income": {"CNY": 0.0, "HKD": 0.0},
                    "expense": {"CNY": 0.0, "HKD": 0.0},
                }
            if row.type in ("income", "expense"):
                result[cid][row.type][row.currency] = float(row.total)

        return json.dumps({
            "grouped_by": group_by,
            "payments": list(result.values()),
        }, ensure_ascii=False)

    # ═══════════════════════════════════════════════════════════
    # 🆕 合同附加项工具（list/add/update/delete）+ get_contract_detail 扩展
    # 附加项 = 合同应收清单上的一行；付款打标 additional_item_id 为可选展示标签，
    # 不参与任何金额聚合（聚合逻辑在 payment_service，完全不变）。
    # ═══════════════════════════════════════════════════════════

    def _additional_item_to_dict(self, it) -> dict:
        """附加项精简序列化（Agent 返回用）。"""
        return {
            "id": it.id,
            "contract_id": it.contract_id,
            "name": it.name,
            "amount": float(it.amount) if it.amount is not None else 0.0,
            "currency": it.currency,
            "paid_to": it.paid_to,
            "description": it.description,
            "occurred_date": str(it.occurred_date) if it.occurred_date else None,
            "remarks": it.remarks,
        }

    def get_contract_detail(self, contract_id: int) -> str:
        """合同详情（覆写父类，追加附加项明细 + 分币种汇总）。

        附加项是合同应收的细化补充，详情需让 LLM 感知，便于回答"这个合同有哪些附加项/共多少"。
        复用父类全部逻辑（客户/合同/收支/利润），仅追加附加项字段。
        """
        result_str = super().get_contract_detail(contract_id)
        try:
            result = json.loads(result_str)
        except json.JSONDecodeError:
            return result_str
        # 父类对不存在/无权合同返回 {"error": ...}，原样透传
        if not isinstance(result, dict) or result.get("error"):
            return result_str

        items = AdditionalItemService.list_by_contract(self.db, contract_id)
        result["additional_items"] = [self._additional_item_to_dict(it) for it in items]
        result["additional_total_by_currency"] = AdditionalItemService.get_summary_by_currency(
            self.db, contract_id
        )
        # 附加项折算到合同主币种（应收口径统一用）；缺汇率返回 None，LLM 据此降级
        result["additional_total_in_contract_currency"] = AdditionalItemService.get_additional_total_in_contract_currency(
            self.db, contract_id
        )
        return json.dumps(result, ensure_ascii=False, default=str)

    def list_additional_items(self, contract_id: int) -> str:
        """列出合同所有附加项 + 分币种汇总（只读，所有角色可见）。"""
        items = AdditionalItemService.list_by_contract(self.db, contract_id)
        summary = AdditionalItemService.get_summary_by_currency(self.db, contract_id)
        return json.dumps({
            "success": True,
            "contract_id": contract_id,
            "additional_items": [self._additional_item_to_dict(it) for it in items],
            "additional_total_by_currency": summary,
        }, ensure_ascii=False, default=str)

    def add_additional_item(
        self,
        contract_id: int,
        name: str,
        amount: float,
        currency: Optional[str] = None,
        paid_to: Optional[str] = None,
        description: Optional[str] = None,
        occurred_date: Optional[str] = None,
        remarks: Optional[str] = None,
    ) -> str:
        """新增合同附加项（写入工具，遵循确认规则）。"""
        if self.user.role == "expense":
            return json.dumps({"error": "当前角色无权操作合同附加项"}, ensure_ascii=False)
        try:
            occurred = date.fromisoformat(occurred_date) if occurred_date else None
            item_data = AdditionalItemCreate(
                contract_id=contract_id,
                name=name,
                amount=amount,
                currency=currency or "CNY",
                paid_to=paid_to,
                description=description,
                occurred_date=occurred,
                remarks=remarks,
            )
            item = AdditionalItemService.create(self.db, item_data, user_id=self.user.id)
            return json.dumps({
                "success": True,
                "additional_item": self._additional_item_to_dict(item),
                "message": f"附加项「{item.name}」已创建",
            }, ensure_ascii=False, default=str)
        except ValueError as e:
            return json.dumps({"error": str(e)}, ensure_ascii=False)
        except Exception as e:
            self.db.rollback()
            logger.exception("add_additional_item 失败")
            return json.dumps({"error": f"创建附加项失败: {e}"}, ensure_ascii=False)

    def update_additional_item(self, item_id: int, **kwargs) -> str:
        """更新合同附加项字段（写入工具，遵循确认规则）。"""
        if self.user.role == "expense":
            return json.dumps({"error": "当前角色无权操作合同附加项"}, ensure_ascii=False)
        payload = {k: v for k, v in kwargs.items() if v is not None}
        if payload.get("occurred_date"):
            try:
                payload["occurred_date"] = date.fromisoformat(payload["occurred_date"])
            except (ValueError, TypeError):
                pass
        try:
            item_data = AdditionalItemUpdate(**payload)
            item = AdditionalItemService.update(self.db, item_id, item_data, user_id=self.user.id)
            if not item:
                return json.dumps({"error": f"附加项不存在: {item_id}"}, ensure_ascii=False)
            return json.dumps({
                "success": True,
                "additional_item": self._additional_item_to_dict(item),
                "message": f"附加项「{item.name}」已更新",
            }, ensure_ascii=False, default=str)
        except Exception as e:
            self.db.rollback()
            logger.exception("update_additional_item 失败")
            return json.dumps({"error": f"更新附加项失败: {e}"}, ensure_ascii=False)

    def delete_additional_item(self, item_id: int) -> str:
        """软删合同附加项（引用此附加项的付款标签自动置空）。"""
        if self.user.role == "expense":
            return json.dumps({"error": "当前角色无权操作合同附加项"}, ensure_ascii=False)
        success = AdditionalItemService.delete(self.db, item_id, user_id=self.user.id)
        if not success:
            return json.dumps({"error": f"附加项不存在: {item_id}"}, ensure_ascii=False)
        return json.dumps({
            "success": True,
            "message": "附加项已删除（引用此附加项的付款标签已自动置空）",
        }, ensure_ascii=False)

    # ═══════════════════════════════════════════════════════════
    # 🆕 凭证录入对话流（v3）
    # analyze_receipt   — 同步 VL 提取 + 三态判定
    # create_income_payment / create_expense_payment — ok 状态直接落库
    # override_receipt_mismatch — soft_mismatch / 无凭证 手动放行
    # ═══════════════════════════════════════════════════════════

    def _load_contract_bundle(self, contract_id: int):
        """加载合同 + 客户 + 角色权限校验。返回 (contract, customer)。"""
        contract = self.db.query(Contract).filter(
            Contract.id == contract_id, Contract.is_deleted == False
        ).first()
        if not contract:
            return None, None
        customer = None
        if contract.customer_id:
            customer = self.db.query(Customer).filter(
                Customer.id == contract.customer_id
            ).first()
        return contract, customer

    def _check_payment_role(self, payment_type: str) -> Optional[str]:
        """收入/支出权限校验。返回错误 JSON 字符串或 None。"""
        if payment_type == "income" and self.user.role == "expense":
            return json.dumps({"error": "当前角色无权录入收入"}, ensure_ascii=False)
        if payment_type == "expense" and self.user.role == "income":
            return json.dumps({"error": "当前角色无权录入支出"}, ensure_ascii=False)
        return None

    def analyze_receipt(
        self,
        file_id: str,
        contract_id: int,
        payment_type: str = "income",
        payment_account_hint: Optional[str] = None,
    ) -> str:
        """凭证识别 + 三态对比：ok / soft_mismatch / hard_conflict。

        Args:
            file_id: 凭证文件 ID（用户已上传到 agent_upload）
            contract_id: 当前合同 ID
            payment_type: income / expense（影响匹配规则）
            payment_account_hint: 凭证 hint（如收款方简称），用于 aliases 匹配收款账户

        Returns:
            JSON: {
                "match_status": "ok"|"soft_mismatch"|"hard_conflict",
                "extracted": {...},
                "expected": {...},
                "diff_fields": [...],
                "confidence": float,
                "reason": str,
                "_receipt_path": "...",        # 内部传递给 create_* 工具
                "_receipt_file_hash": "...",   # 内部传递给 create_* 工具
                "_payment_account_id": int|None,
                "_payment_term": {...}|None,
                "duplicate_detected": bool,
            }
        """
        if not file_id:
            return json.dumps({"error": "缺少 file_id"}, ensure_ascii=False)
        if not contract_id:
            return json.dumps({"error": "缺少 contract_id"}, ensure_ascii=False)

        err = self._check_payment_role(payment_type)
        if err:
            return err

        contract, customer = self._load_contract_bundle(contract_id)
        if not contract:
            return json.dumps({"error": f"合同不存在: {contract_id}"}, ensure_ascii=False)

        # 解析文件
        file_path = resolve_file_path(file_id, self.user.id)
        if not file_path:
            return json.dumps({"error": f"凭证文件不存在: {file_id}"}, ensure_ascii=False)

        # VL 分析（凭证去重检测顺带做了）
        analysis = FileAnalyzer.analyze(
            file_path, file_id,
            purpose="receipt",
            db=self.db,
            user_id=self.user.id,
            contract_id=contract_id,
        )
        if analysis.get("duplicate_detected"):
            return json.dumps({
                "duplicate_detected": True,
                "existing_payment": analysis.get("existing_payment"),
                "message": "该凭证已在此合同下录入过，请勿重复录入",
            }, ensure_ascii=False, default=str)

        if not analysis.get("success") or analysis.get("type") != "receipt":
            return json.dumps({
                "error": analysis.get("error") or "凭证识别失败",
                "type": analysis.get("type"),
            }, ensure_ascii=False)

        extracted = analysis.get("data") or {}

        # 把文件搬到 receipt 目录（落库要存稳定路径）
        receipt_path = self._ensure_file_in_receipt_dir(f"agent_upload/{file_id}")
        receipt_hash = getattr(self, "_last_receipt_file_hash", None) or analysis.get("file_hash")

        # 收款账户匹配（aliases 优先），仅 income 走
        payment_account = None
        if payment_type == "income":
            hint = (
                payment_account_hint
                or extracted.get("payment_account_hint")
                or extracted.get("payee_name")
                or ""
            )
            if hint:
                payment_account = PaymentAccountService.find_by_hint(self.db, hint)

        # 选定付款计划项（按金额命中）
        from decimal import Decimal as _Dec
        amount_dec = None
        try:
            amount_dec = _Dec(str(extracted.get("amount"))) if extracted.get("amount") else None
        except Exception:
            amount_dec = None
        currency_str = (extracted.get("currency") or contract.currency or "CNY").upper()
        payment_term = pick_payment_term(contract, amount_dec, currency_str) if payment_type == "income" else None

        # 三态判定
        result = match_receipt(
            extracted=extracted,
            contract=contract,
            customer=customer,
            payment_account=payment_account,
            expected_payment_term=payment_term,
            payment_type=payment_type,
        )

        return json.dumps({
            "match_status": result["match_status"],
            "extracted": result["extracted_norm"],
            "expected": result["expected"],
            "diff_fields": result["diff_fields"],
            "confidence": result["confidence"],
            "reason": result["reason"],
            "_receipt_path": receipt_path,
            "_receipt_file_hash": receipt_hash,
            "_receipt_data": extracted,
            "_payment_account_id": payment_account.id if payment_account else None,
            "_payment_account_title": payment_account.title if payment_account else None,
            "_payment_term": payment_term,
            "_source_file_id": file_id,
        }, ensure_ascii=False, default=str)

    def _build_user_input_snapshot(self, **fields) -> dict:
        """统一序列化用户输入快照（金额/币种/日期/描述等）。"""
        snapshot = {}
        for k, v in fields.items():
            if v is None:
                continue
            if isinstance(v, Decimal):
                snapshot[k] = float(v)
            elif isinstance(v, date):
                snapshot[k] = v.isoformat()
            else:
                snapshot[k] = v
        return snapshot

    def _resolve_receipt_artifact(
        self,
        file_id: Optional[str],
        receipt_path_hint: Optional[str],
        receipt_hash_hint: Optional[str],
        receipt_data_hint: Optional[dict],
    ) -> tuple[Optional[str], Optional[str], Optional[dict]]:
        """凭证三件套解析：path / hash / data。

        优先级：
        1. LLM 直接传 _receipt_path / _receipt_file_hash / _receipt_data（从 analyze_receipt 透传）
        2. LLM 只传 file_id → 现场 resolve + 搬目录 + 算 hash
        3. 无 file_id → (None, None, None)（支出 no_receipt 场景）
        """
        if receipt_path_hint or receipt_hash_hint:
            return receipt_path_hint, receipt_hash_hint, receipt_data_hint
        if not file_id:
            return None, None, None
        receipt_path = self._ensure_file_in_receipt_dir(f"agent_upload/{file_id}")
        receipt_hash = getattr(self, "_last_receipt_file_hash", None)
        return receipt_path, receipt_hash, receipt_data_hint

    def _create_payment_dialog(
        self,
        *,
        payment_type: str,
        contract_id: int,
        amount: float,
        currency: str,
        paid_date: str,
        payment_method: Optional[str] = None,
        installment_name: Optional[str] = None,
        description: Optional[str] = None,
        notes: Optional[str] = None,
        payee_name: Optional[str] = None,
        payment_account_id: Optional[int] = None,
        counterparty_account: Optional[dict] = None,
        file_id: Optional[str] = None,
        _receipt_path: Optional[str] = None,
        _receipt_file_hash: Optional[str] = None,
        _receipt_data: Optional[dict] = None,
        verification: Optional[dict] = None,
    ) -> str:
        """内部公共实现：ok 状态对话流创建付款。"""
        err = self._check_payment_role(payment_type)
        if err:
            return err

        try:
            paid_date_obj = date.fromisoformat(paid_date)
        except (ValueError, TypeError):
            return json.dumps({"error": "paid_date 格式应为 YYYY-MM-DD"}, ensure_ascii=False)

        try:
            amount_dec = Decimal(str(amount))
        except Exception:
            return json.dumps({"error": "amount 必须为数字"}, ensure_ascii=False)
        if amount_dec <= 0:
            return json.dumps({"error": "amount 必须大于 0"}, ensure_ascii=False)

        receipt_path, receipt_hash, receipt_data = self._resolve_receipt_artifact(
            file_id, _receipt_path, _receipt_file_hash, _receipt_data,
        )

        # description 自动生成
        if not description and isinstance(receipt_data, dict):
            contract = self.db.query(Contract).filter(Contract.id == contract_id).first()
            description = self._resolve_payment_description(
                receipt_data, contract,
                float(amount_dec), currency, payment_type,
            )

        try:
            payment = PaymentService.create_payment_for_dialog(
                db=self.db,
                contract_id=contract_id,
                payment_type=payment_type,
                amount=amount_dec,
                currency=currency,
                paid_date=paid_date_obj,
                payment_method=payment_method,
                receipt_path=receipt_path,
                receipt_file_hash=receipt_hash,
                receipt_data=receipt_data,
                verification_snapshot=verification,
                description=description,
                installment_name=installment_name,
                notes=notes,
                payee_name=payee_name,
                payment_account_id=payment_account_id,
                counterparty_account=counterparty_account,
                created_by=self.user.id,
                no_receipt=False,
            )
        except ValueError as e:
            self.db.rollback()
            return json.dumps({"error": str(e)}, ensure_ascii=False)
        except Exception as e:
            self.db.rollback()
            logger.exception("create_payment_for_dialog 失败")
            return json.dumps({"error": f"创建付款失败: {e}"}, ensure_ascii=False)

        return json.dumps({
            "success": True,
            "payment": self._payment_to_dict(payment),
            "message": f"{('收入' if payment_type == 'income' else '支出')}已成功录入：{currency} {amount_dec}",
        }, ensure_ascii=False, default=str)

    def create_income_payment(self, **kwargs) -> str:
        """对话流创建收入付款（凭证已同步预校验通过=ok 时才能调用）。"""
        # 防御：要求凭证字段
        if not (kwargs.get("file_id") or kwargs.get("_receipt_path")):
            return json.dumps({"error": "收入必须先调 analyze_receipt 提取凭证"}, ensure_ascii=False)
        return self._create_payment_dialog(payment_type="income", **kwargs)

    def create_expense_payment(self, **kwargs) -> str:
        """对话流创建支出付款（可无凭证，支出允许 no_receipt）。"""
        no_receipt = bool(kwargs.pop("no_receipt", False))
        has_receipt = bool(kwargs.get("file_id") or kwargs.get("_receipt_path"))
        if not has_receipt and not no_receipt:
            return json.dumps({
                "error": "支出录入需明确：传 file_id（有凭证）或 no_receipt=true（无凭证）",
            }, ensure_ascii=False)
        if has_receipt and no_receipt:
            return json.dumps({"error": "不能同时传 file_id 和 no_receipt=true"}, ensure_ascii=False)
        if no_receipt:
            # 走放行通道（无凭证 = manual 模式审计）
            return self._override_payment(
                payment_type="expense",
                match_status="manual",
                no_receipt=True,
                **kwargs,
            )
        return self._create_payment_dialog(payment_type="expense", **kwargs)

    def _override_payment(
        self,
        *,
        payment_type: str,
        match_status: str,
        contract_id: int,
        amount: float,
        currency: str,
        paid_date: str,
        override_reason: str,
        payment_method: Optional[str] = None,
        installment_name: Optional[str] = None,
        description: Optional[str] = None,
        notes: Optional[str] = None,
        payee_name: Optional[str] = None,
        payment_account_id: Optional[int] = None,
        counterparty_account: Optional[dict] = None,
        file_id: Optional[str] = None,
        _receipt_path: Optional[str] = None,
        _receipt_file_hash: Optional[str] = None,
        _receipt_data: Optional[dict] = None,
        extracted_snapshot: Optional[dict] = None,
        expected_snapshot: Optional[dict] = None,
        diff_fields: Optional[list] = None,
        no_receipt: bool = False,
        source: str = "bank_receipt",
    ) -> str:
        """内部：放行创建（soft_mismatch / manual）。

        source 取值：bank_receipt / payment_info_screenshot / manual_no_receipt。
        no_receipt=True 时会自动覆盖 source 为 manual_no_receipt（防 LLM 传错）。
        """
        err = self._check_payment_role(payment_type)
        if err:
            return err
        if not override_reason or not override_reason.strip():
            return json.dumps({"error": "放行理由（override_reason）不能为空"}, ensure_ascii=False)

        try:
            paid_date_obj = date.fromisoformat(paid_date)
        except (ValueError, TypeError):
            return json.dumps({"error": "paid_date 格式应为 YYYY-MM-DD"}, ensure_ascii=False)
        try:
            amount_dec = Decimal(str(amount))
        except Exception:
            return json.dumps({"error": "amount 必须为数字"}, ensure_ascii=False)
        if amount_dec <= 0:
            return json.dumps({"error": "amount 必须大于 0"}, ensure_ascii=False)

        receipt_path, receipt_hash, receipt_data = self._resolve_receipt_artifact(
            file_id, _receipt_path, _receipt_file_hash, _receipt_data,
        )

        # source 兜底：no_receipt 必走 manual_no_receipt，防 LLM 传错
        if no_receipt:
            source = "manual_no_receipt"
        elif source not in ("bank_receipt", "payment_info_screenshot", "manual_no_receipt"):
            source = "bank_receipt"

        if not description and isinstance(receipt_data, dict):
            contract = self.db.query(Contract).filter(Contract.id == contract_id).first()
            description = self._resolve_payment_description(
                receipt_data, contract,
                float(amount_dec), currency, payment_type,
            )

        user_input_snapshot = self._build_user_input_snapshot(
            amount=amount_dec, currency=currency, paid_date=paid_date_obj,
            payment_method=payment_method, installment_name=installment_name,
            description=description, payee_name=payee_name,
            payment_account_id=payment_account_id,
        )

        try:
            payment = PaymentService.create_payment_with_override(
                db=self.db,
                contract_id=contract_id,
                payment_type=payment_type,
                amount=amount_dec,
                currency=currency,
                paid_date=paid_date_obj,
                payment_method=payment_method,
                receipt_path=receipt_path,
                receipt_file_hash=receipt_hash,
                receipt_data=receipt_data,
                description=description,
                installment_name=installment_name,
                notes=notes,
                payee_name=payee_name,
                payment_account_id=payment_account_id,
                counterparty_account=counterparty_account,
                created_by=self.user.id,
                operator_name=self.user.full_name or self.user.username,
                operator_role=self.user.role,
                session_id=self.session_id,
                override_reason=override_reason.strip(),
                match_status=match_status,
                extracted_snapshot=extracted_snapshot,
                user_input_snapshot=user_input_snapshot,
                expected_snapshot=expected_snapshot,
                diff_fields=diff_fields,
                no_receipt=no_receipt,
                source=source,
            )
        except ValueError as e:
            self.db.rollback()
            return json.dumps({"error": str(e)}, ensure_ascii=False)
        except Exception as e:
            self.db.rollback()
            logger.exception("create_payment_with_override 失败")
            return json.dumps({"error": f"放行创建失败: {e}"}, ensure_ascii=False)

        return json.dumps({
            "success": True,
            "payment": self._payment_to_dict(payment),
            "match_status": match_status,
            "message": "已凭借放行理由完成录入，本次操作已写入放行审计表。",
        }, ensure_ascii=False, default=str)

    def override_receipt_mismatch(self, **kwargs) -> str:
        """凭证轻微不符（soft_mismatch）/ 付款信息文字（manual + payment_info_screenshot）状态下手动放行创建付款。

        hard_conflict 状态下此工具会拒绝执行（match_status 校验放在 Service 层）。

        Args:
            source: 审计来源，默认 "bank_receipt"。可选值：
              - bank_receipt：银行凭证/转账截图等正式凭证
              - payment_info_screenshot：付款信息文字截图（聊天里手敲的转账描述）
              - manual_no_receipt：纯文字无凭证录入
        """
        match_status = kwargs.get("match_status", "soft_mismatch")
        if match_status == "hard_conflict":
            return json.dumps({
                "error": "硬冲突（凭证客户与合同客户完全不符）禁止放行。请重新核对凭证或合同。",
            }, ensure_ascii=False)
        payment_type = kwargs.pop("payment_type", "income")
        return self._override_payment(
            payment_type=payment_type,
            match_status=match_status,
            no_receipt=False,
            **kwargs,
        )


# ═══════════════════════════════════════════════════════════════
# TOOL_DEFINITIONS v3 — 20 个工具
#   16 个基础 + 4 个凭证录入对话流（analyze_receipt / create_income_payment /
#   create_expense_payment / override_receipt_mismatch）
# ═══════════════════════════════════════════════════════════════

TOOL_DEFINITIONS = [
    # ── 文件分析 ──
    {
        "type": "function",
        "function": {
            "name": "analyze_files",
            "description": "分析上传的文件。自动识别文件类型并提取结构化信息。支持四种类型：合同（contract）/银行凭证（receipt）/付款信息文字截图（payment_info，如聊天里手敲的'1、收款/转出...对应业务（群名称）'格式）/群聊截图（group_chat）。车辆照片、证件等会被拒绝。批量分析多个文件。纯分析工具，不写数据库。",
            "parameters": {
                "type": "object",
                "required": ["file_ids"],
                "properties": {
                    "file_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "要分析的文件ID列表，从附件信息中获取",
                    },
                    "purpose": {
                        "type": "string",
                        "enum": ["auto", "contract", "receipt", "payment_info", "group_chat"],
                        "description": "分析目的。auto=自动判断（默认），其余为强制指定类型。payment_info=付款信息文字截图。",
                    },
                },
            },
        },
    },
    # ── 全局概览 ──
    {
        "type": "function",
        "function": {
            "name": "get_overview",
            "description": "获取系统全局统计概览：客户总数、合同总数（按状态分布）、即将到期合同数、收支汇总。用于回答'现在什么情况''有哪些数据'等开放式问题。",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    # ── 客户管理（3 个） ──
    {
        "type": "function",
        "function": {
            "name": "search_customers",
            "description": "搜索客户。不传参数时返回全局统计+最近10个客户样例；传 name/phone/wechat_group 按条件模糊匹配（自动兼容繁简体）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "客户姓名"},
                    "phone": {"type": "string", "description": "电话号码"},
                    "wechat_group": {"type": "string", "description": "微信群名称"},
                    "limit": {"type": "integer", "description": "最大返回数量", "default": 10},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_customer",
            "description": "创建客户记录。同名+同电话/邮箱的客户已存在时会返回已有客户（不会重复创建）。从合同文件提取到客户信息后调用。",
            "parameters": {
                "type": "object",
                "required": ["name"],
                "properties": {
                    "name": {"type": "string", "description": "客户姓名"},
                    "phone": {"type": "string", "description": "联系电话"},
                    "email": {"type": "string", "description": "联系邮箱"},
                    "contact_person": {"type": "string", "description": "联系人"},
                    "id_card_number": {"type": "string", "description": "身份证号"},
                    "wechat_group_name": {"type": "string", "description": "微信群名称"},
                    "address": {"type": "string", "description": "地址"},
                    "remarks": {"type": "string", "description": "备注"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_customer",
            "description": "更新已有客户信息。从合同文件中提取到客户电话、证件号等新信息时，用于补充已有客户记录。",
            "parameters": {
                "type": "object",
                "required": ["customer_id"],
                "properties": {
                    "customer_id": {"type": "integer", "description": "客户ID"},
                    "phone": {"type": "string", "description": "联系电话"},
                    "email": {"type": "string", "description": "联系邮箱"},
                    "id_card_number": {"type": "string", "description": "身份证号"},
                    "wechat_group_name": {"type": "string", "description": "微信群名称"},
                    "address": {"type": "string", "description": "地址"},
                    "remarks": {"type": "string", "description": "备注"},
                },
            },
        },
    },
    # ── 合同管理（4 个） ──
    {
        "type": "function",
        "function": {
            "name": "search_contracts",
            "description": "搜索合同。不传参数时返回全局统计+最近10个合同样例；传 contract_number/customer_name/status/keyword 按条件搜索。",
            "parameters": {
                "type": "object",
                "properties": {
                    "contract_number": {"type": "string", "description": "合同编号"},
                    "customer_name": {"type": "string", "description": "客户姓名（模糊匹配）"},
                    "status": {"type": "string", "enum": ["active", "completed"], "description": "合同状态"},
                    "keyword": {"type": "string", "description": "全文搜索关键词"},
                    "date_from": {"type": "string", "description": "签订日期起始（YYYY-MM-DD）"},
                    "date_to": {"type": "string", "description": "签订日期截止（YYYY-MM-DD）"},
                    "page": {"type": "integer", "default": 1},
                    "per_page": {"type": "integer", "default": 10},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_contract_detail",
            "description": "获取合同完整详情，包含所有付款记录、付款进度和待确认收款列表。用于用户询问某个具体合同时。",
            "parameters": {
                "type": "object",
                "required": ["contract_id"],
                "properties": {
                    "contract_id": {"type": "integer", "description": "合同ID"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_contract",
            "description": "为客户创建合同记录。需要先通过 create_customer 或 search_customers 获取 customer_id。合同编号自动生成。如果同一文件已创建过合同会返回已有记录。**只生成合同与付款计划（payment_terms），不创建任何 payment 记录**——付款记录只能通过合同卡片上的表单录入。",
            "parameters": {
                "type": "object",
                "required": ["customer_id", "file_id", "wechat_group"],
                "properties": {
                    "customer_id": {"type": "integer", "description": "客户ID"},
                    "file_id": {"type": "string", "description": "上传文件的ID。系统会自动使用 analyze_files 对该文件的分析结果。"},
                    "title": {"type": "string", "description": "合同标题"},
                    "total_amount": {"type": "number", "description": "合同总金额"},
                    "currency": {"type": "string", "enum": ["CNY", "HKD"], "description": "币种。HK$/港币=HKD，¥/人民币=CNY"},
                    "signed_date": {"type": "string", "description": "签订日期（YYYY-MM-DD）"},
                    "business_type": {"type": "string", "enum": ["车辆买卖", "两地牌过户", "年检保险", "其他"], "description": "业务类型"},
                    "business_description": {"type": "string", "description": "极简业务描述（如：购买现牌 粤Z7N80港 深圳湾口岸）"},
                    "wechat_group": {"type": "string", "description": "业务微信群名称（必填）。每笔业务都必须关联一个业务群，群名由用户提供，不要从合同文件中提取"},
                    "contract_data": {"type": "object", "description": "合同分析数据（通常无需传递，系统自动从缓存获取）"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_contract",
            "description": "更新合同信息。用于补充或修改微信群名称、备注等元信息。群名由用户口述提供，不要从合同文件或群聊截图中提取。",
            "parameters": {
                "type": "object",
                "required": ["contract_id"],
                "properties": {
                    "contract_id": {"type": "integer", "description": "合同ID"},
                    "wechat_group": {"type": "string", "description": "业务微信群名称"},
                    "remarks": {"type": "string", "description": "备注"},
                    "title": {"type": "string", "description": "合同标题"},
                    "business_description": {"type": "string", "description": "业务描述"},
                },
            },
        },
    },
    # ── 付款管理（2 个） ──
    {
        "type": "function",
        "function": {
            "name": "query_payments",
            "description": "付款记录查询。可按合同ID、类型（income/expense）、状态（pending/paid）筛选。支持 group_by=contract 按合同分组聚合（替代旧的收支汇总工具）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "contract_id": {"type": "integer", "description": "按合同ID筛选"},
                    "type": {"type": "string", "enum": ["income", "expense"], "description": "付款类型"},
                    "status": {"type": "string", "enum": ["pending", "paid"], "description": "付款状态"},
                    "group_by": {"type": "string", "enum": ["contract"], "description": "分组聚合维度"},
                    "page": {"type": "integer", "default": 1},
                    "per_page": {"type": "integer", "default": 20},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_payment",
            "description": "更新已有付款记录的备注、凭证、付款方式等信息。为已有 pending 付款补充凭证时使用（系统自动转为 paid 并参与结算）。",
            "parameters": {
                "type": "object",
                "required": ["payment_id"],
                "properties": {
                    "payment_id": {"type": "integer", "description": "付款记录ID"},
                    "notes": {"type": "string", "description": "备注"},
                    "payment_method": {"type": "string", "description": "付款方式"},
                    "receipt_image_path": {"type": "string", "description": "凭证图片路径"},
                    "receipt_data": {"type": "object", "description": "凭证分析数据"},
                    "installment_name": {"type": "string", "description": "期数名称"},
                    "paid_date": {"type": "string", "description": "付款日期（YYYY-MM-DD）"},
                },
            },
        },
    },
    # ── 全文搜索 ──
    {
        "type": "function",
        "function": {
            "name": "search_contract_text",
            "description": "按关键词搜索所有合同的全文内容，返回匹配的合同列表和文本片段。用于查找包含特定条款、约定的合同（如搜索'违约金'、'仲裁'、'交车日期'）。传 contract_id 可限定在某份合同中搜索（替代 ask_contract）。",
            "parameters": {
                "type": "object",
                "required": ["keyword"],
                "properties": {
                    "keyword": {"type": "string", "description": "搜索关键词"},
                    "contract_id": {"type": "integer", "description": "限定在某份合同中搜索（可选）"},
                },
            },
        },
    },
    # ── 合同附加项（4 个） ──
    {
        "type": "function",
        "function": {
            "name": "list_additional_items",
            "description": "列出合同的所有附加项（车险/保养/人工费等应收清单项）+ 按币种汇总。只读，用于回答\"这个合同有哪些附加项/附加项共多少\"。",
            "parameters": {
                "type": "object",
                "required": ["contract_id"],
                "properties": {
                    "contract_id": {"type": "integer", "description": "合同ID"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_additional_item",
            "description": "为合同新增一项附加项（应收清单上的额外项目，如车险/保养改装/人工费）。附加项是合同应收的细化补充，不是独立财务实体，无已收/未收概念。写入工具，需先列计划等用户确认。币种可与合同不同（系统按所选币种独立记账，不自动折算）。",
            "parameters": {
                "type": "object",
                "required": ["contract_id", "name", "amount"],
                "properties": {
                    "contract_id": {"type": "integer", "description": "合同ID"},
                    "name": {"type": "string", "description": "项目名称（如：车险、保养改装、过户费、人工费）"},
                    "amount": {"type": "number", "description": "金额"},
                    "currency": {"type": "string", "enum": ["CNY", "HKD"], "description": "币种，默认 CNY"},
                    "paid_to": {"type": "string", "description": "付给谁（如：太平洋保险、XX修理厂）"},
                    "description": {"type": "string", "description": "用途说明（如：基础三责险+车损）"},
                    "occurred_date": {"type": "string", "description": "发生日期（YYYY-MM-DD），备查用"},
                    "remarks": {"type": "string", "description": "业务备注"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_additional_item",
            "description": "更新已有附加项的字段。写入工具，需先列计划等用户确认。",
            "parameters": {
                "type": "object",
                "required": ["item_id"],
                "properties": {
                    "item_id": {"type": "integer", "description": "附加项ID"},
                    "name": {"type": "string", "description": "项目名称"},
                    "amount": {"type": "number", "description": "金额"},
                    "currency": {"type": "string", "enum": ["CNY", "HKD"]},
                    "paid_to": {"type": "string"},
                    "description": {"type": "string"},
                    "occurred_date": {"type": "string", "description": "YYYY-MM-DD"},
                    "remarks": {"type": "string"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_additional_item",
            "description": "软删附加项。引用此附加项的付款标签会自动置空（付款本身保留）。删除自由，无硬保护。",
            "parameters": {
                "type": "object",
                "required": ["item_id"],
                "properties": {
                    "item_id": {"type": "integer", "description": "附加项ID"},
                },
            },
        },
    },
    # ── 凭证录入对话流（4 个） ──
    {
        "type": "function",
        "function": {
            "name": "analyze_receipt",
            "description": "识别凭证并对照合同/付款计划做三态判定（ok/soft_mismatch/hard_conflict）。这是凭证录入对话流的第一步：用户上传凭证图后立刻调它，根据返回的 match_status 决定下一步：ok→展示计划等用户确认→create_income_payment/create_expense_payment；soft_mismatch→把差异展示给用户，请用户给放行理由→override_receipt_mismatch；hard_conflict→明确拒绝录入并提醒用户核对。**必须在调 create_*_payment / override_receipt_mismatch 之前先调本工具**，把返回结果中的 _receipt_path / _receipt_file_hash / _receipt_data / _payment_account_id / extracted / expected / diff_fields 透传到后续写入工具。",
            "parameters": {
                "type": "object",
                "required": ["file_id", "contract_id"],
                "properties": {
                    "file_id": {"type": "string", "description": "凭证文件ID（从附件信息获取）"},
                    "contract_id": {"type": "integer", "description": "当前合同ID（从会话上下文获取）"},
                    "payment_type": {"type": "string", "enum": ["income", "expense"], "description": "付款类型，默认 income"},
                    "payment_account_hint": {"type": "string", "description": "收款账户提示词（如收款方简称），可选；用于命中收款账户别名"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_income_payment",
            "description": "对话流创建一笔收入。**必须先调 analyze_receipt 且 match_status=ok 时才能调本工具**。把 analyze_receipt 返回的 _receipt_path / _receipt_file_hash / _receipt_data / _payment_account_id / verification 透传进来。写入前必须先用自然语言列出关键信息（金额/币种/付款方/付款日期/期数名）并等用户确认。",
            "parameters": {
                "type": "object",
                "required": ["contract_id", "amount", "currency", "paid_date"],
                "properties": {
                    "contract_id": {"type": "integer", "description": "合同ID"},
                    "amount": {"type": "number", "description": "金额（凭证识别值）"},
                    "currency": {"type": "string", "enum": ["CNY", "HKD"], "description": "币种"},
                    "paid_date": {"type": "string", "description": "付款日期 YYYY-MM-DD"},
                    "payment_method": {"type": "string", "description": "付款方式 bank_transfer/wechat/alipay/cash/check"},
                    "installment_name": {"type": "string", "description": "期数名（如\"定金\"、\"尾款\"）"},
                    "description": {"type": "string", "description": "业务描述（不传则自动生成）"},
                    "notes": {"type": "string", "description": "备注"},
                    "payment_account_id": {"type": "integer", "description": "收款账户ID（从 analyze_receipt._payment_account_id 透传）"},
                    "file_id": {"type": "string", "description": "凭证文件ID"},
                    "_receipt_path": {"type": "string", "description": "凭证落库路径（从 analyze_receipt 透传）"},
                    "_receipt_file_hash": {"type": "string", "description": "凭证哈希（从 analyze_receipt 透传）"},
                    "_receipt_data": {"type": "object", "description": "凭证识别结构化数据（从 analyze_receipt 透传）"},
                    "verification": {"type": "object", "description": "ReceiptMatcher 返回的判定快照（含 expected/extracted/diff_fields），落到 verification_result"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_expense_payment",
            "description": "对话流创建一笔支出。支出允许无凭证：有凭证时必须先调 analyze_receipt（同收入路径）；无凭证时传 no_receipt=true + override_reason（视为 manual 模式审计放行）。写入前必须先列出关键信息（金额/币种/收款方/付款日期/用途）并等用户确认。",
            "parameters": {
                "type": "object",
                "required": ["contract_id", "amount", "currency", "paid_date"],
                "properties": {
                    "contract_id": {"type": "integer", "description": "合同ID"},
                    "amount": {"type": "number", "description": "金额"},
                    "currency": {"type": "string", "enum": ["CNY", "HKD"], "description": "币种"},
                    "paid_date": {"type": "string", "description": "付款日期 YYYY-MM-DD"},
                    "payment_method": {"type": "string", "description": "付款方式"},
                    "installment_name": {"type": "string", "description": "期数名"},
                    "description": {"type": "string", "description": "业务描述"},
                    "notes": {"type": "string", "description": "备注"},
                    "payee_name": {"type": "string", "description": "收款方名称（支出必填）"},
                    "counterparty_account": {"type": "object", "description": "对方账户详情 {account_name, account_number, bank_name, branch}"},
                    "file_id": {"type": "string", "description": "凭证文件ID（可选）"},
                    "_receipt_path": {"type": "string", "description": "凭证落库路径（从 analyze_receipt 透传）"},
                    "_receipt_file_hash": {"type": "string", "description": "凭证哈希（从 analyze_receipt 透传）"},
                    "_receipt_data": {"type": "object", "description": "凭证识别结构化数据"},
                    "verification": {"type": "object", "description": "判定快照"},
                    "no_receipt": {"type": "boolean", "description": "无凭证声明（与 file_id 互斥）。true 时必须同时传 override_reason"},
                    "override_reason": {"type": "string", "description": "no_receipt=true 时必填：说明为何无凭证（用户口述的业务理由）"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "override_receipt_mismatch",
            "description": "用于三种场景的放行创建付款：(1) 银行凭证 soft_mismatch 用户给放行理由 (2) 付款信息文字截图（manual + source=payment_info_screenshot）(3) 纯文字描述录入（manual + source=manual_no_receipt）。**禁止用于 hard_conflict**（工具入口硬挡）。写入前必须先在对话里清楚列出关键字段和理由，请用户明确同意后再调用。",
            "parameters": {
                "type": "object",
                "required": ["contract_id", "amount", "currency", "paid_date", "override_reason", "match_status"],
                "properties": {
                    "contract_id": {"type": "integer", "description": "合同ID"},
                    "payment_type": {"type": "string", "enum": ["income", "expense"], "description": "付款类型，默认 income"},
                    "match_status": {"type": "string", "enum": ["soft_mismatch", "manual"], "description": "soft_mismatch=银行凭证轻微不符放行；manual=付款信息截图或纯文字录入"},
                    "source": {"type": "string", "enum": ["bank_receipt", "payment_info_screenshot", "manual_no_receipt"], "description": "审计来源。bank_receipt=正式银行凭证（默认）；payment_info_screenshot=付款信息文字截图；manual_no_receipt=纯文字无凭证。**付款信息截图场景必须传 payment_info_screenshot**"},
                    "amount": {"type": "number", "description": "实际录入金额（一般取用户输入或凭证值）"},
                    "currency": {"type": "string", "enum": ["CNY", "HKD"]},
                    "paid_date": {"type": "string", "description": "YYYY-MM-DD"},
                    "payment_method": {"type": "string"},
                    "installment_name": {"type": "string"},
                    "description": {"type": "string"},
                    "notes": {"type": "string", "description": "付款备注。付款信息截图场景应保存结算状态原文（如「已结清:599800+7498-50000=557498」整段不解析）"},
                    "payee_name": {"type": "string", "description": "收款方（仅支出）"},
                    "counterparty_account": {"type": "object"},
                    "payment_account_id": {"type": "integer", "description": "收款账户ID（仅收入）"},
                    "override_reason": {"type": "string", "description": "放行理由（必填，要落审计）。付款信息截图：'基于付款信息截图录入；[款项摘要]'；纯文字：'用户口述录入，无凭证。[款项说明]'"},
                    "file_id": {"type": "string"},
                    "_receipt_path": {"type": "string"},
                    "_receipt_file_hash": {"type": "string"},
                    "_receipt_data": {"type": "object"},
                    "extracted_snapshot": {"type": "object", "description": "analyze_receipt/analyze_files 返回的 extracted 快照"},
                    "expected_snapshot": {"type": "object", "description": "合同期望字段快照"},
                    "diff_fields": {"type": "array", "description": "差异字段清单", "items": {"type": "object"}},
                },
            },
        },
    },
]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 模块加载完成后填充工具白名单（供 ToolExecutorV2.execute 校验）
# 防御性检查：TOOL_DEFINITIONS 为空时 _ALLOWED_TOOLS 必须是空集，execute 拒绝一切
# 防止误删 TOOL_DEFINITIONS 后白名单被错误地填充
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
_ALLOWED_TOOLS = frozenset(
    t["function"]["name"] for t in TOOL_DEFINITIONS if "function" in t and "name" in t["function"]
)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 会话模式工具集（mode guard）
# - chat 模式：全部工具
# - receipt_income / receipt_expense：限定在凭证录入对话流相关工具
#   避免 LLM 在录支出会话里误调 create_income_payment 等不相关写入工具
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# 凭证录入会话共用的工具（搜索/查询/分析 + 同步凭证识别 + 放行）
_RECEIPT_COMMON_TOOLS = frozenset({
    "analyze_files",
    "analyze_receipt",
    "get_overview",
    "search_contracts",
    "search_customers",
    "get_contract_detail",
    "query_payments",
    "search_contract_text",
    "list_additional_items",
    "override_receipt_mismatch",
})

# 模式 → 允许的工具集
MODE_TOOL_WHITELIST: dict[str, frozenset[str]] = {
    "chat": _ALLOWED_TOOLS,
    "receipt_income": _RECEIPT_COMMON_TOOLS | {"create_income_payment"},
    "receipt_expense": _RECEIPT_COMMON_TOOLS | {"create_expense_payment"},
}


def filter_tool_definitions(session_mode: str) -> list:
    """按 session_mode 过滤 TOOL_DEFINITIONS，给 LLM 暴露受限工具集。

    未知 mode 返回全集（兜底）。
    """
    allowed = MODE_TOOL_WHITELIST.get(session_mode)
    if not allowed:
        return TOOL_DEFINITIONS
    return [
        t for t in TOOL_DEFINITIONS
        if t.get("function", {}).get("name") in allowed
    ]


def is_tool_allowed_in_mode(tool_name: str, session_mode: str) -> bool:
    """工具执行入口兜底：防止 LLM 不听话调用 mode 外的工具。"""
    allowed = MODE_TOOL_WHITELIST.get(session_mode)
    if not allowed:
        return True   # 未知 mode 不拦截
    return tool_name in allowed
