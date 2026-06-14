"""Agent 工具执行器 v2 — 精简版

变更（相对 tools.py）：
  - 继承原 ToolExecutor，复用所有业务逻辑
  - 删除 mode guard / document guard / set_pending_plan
  - 新增 analyze_files / match_and_confirm_payment
  - 合并 create_payment + create_expense → create_payment_record
  - 工具集 20→14

设计原则：
  - 轻量确认：写入工具执行前检查 LLM 上文是否展示确认请求
  - 无模式锁定：所有工具在所有场景下可用（权限由角色控制）
"""
import json
import logging
from datetime import date
from decimal import Decimal
from typing import Optional

from app.ai.tool_executor_base import ToolExecutor, _get_redis_pool
from app.schemas.contract_additional_item import AdditionalItemCreate, AdditionalItemUpdate
from app.services.contract_additional_item_service import AdditionalItemService
from app.services.file_analyzer import FileAnalyzer
from app.services.payment_service import PaymentService
from app.services.exchange_rate_service import ExchangeRateService
from app.utils.file_utils import resolve_file_path
from app.models.payment import Payment
from app.models.contract import Contract

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
        # 凭证文件追踪：analyze_files 分析到 receipt 类型文件时记录 file_id，
        # 供后续 create_payment_record / match_and_confirm_payment 解析文件路径。
        # 不再依赖 LLM 在 receipt_data 中传递 _source_file_id。
        self._pending_receipt_file_ids: list[str] = []

    # 增强 _payment_to_dict_lite：加上 description 字段（供 LLM 查看上下文）
    def _payment_to_dict_lite(self, p) -> dict:
        d = super()._payment_to_dict_lite(p)
        d["description"] = p.description
        return d

    # ═══════════════════════════════════════════════════════════
    # 辅助方法
    # ═══════════════════════════════════════════════════════════

    def _resolve_receipt_paths(
        self, receipt_data: dict, explicit_path: str = None, receipt_file_ids: list[str] = None,
    ) -> tuple[Optional[str], str, list[dict]]:
        """解析凭证文件路径，支持多张凭证合并录入。

        Args:
            receipt_data: analyze_files 返回的凭证分析结果（主凭证）
            explicit_path: 显式指定的文件路径
            receipt_file_ids: LLM 传入的凭证文件 ID 列表（合并录入多张时使用）

        Returns:
            (主凭证路径, 主凭证文件哈希, [补充凭证列表])
            补充凭证每项: {file_path, file_hash}
        """
        # 1. 收集所有需要解析的 file_id
        all_file_ids = list(receipt_file_ids) if receipt_file_ids else []

        # 2. 从 receipt_data 提取主凭证 file_id（不与 receipt_file_ids 重复）
        primary_from_data = None
        if isinstance(receipt_data, dict):
            primary_from_data = receipt_data.get("_source_file_id") or receipt_data.get("file_id")

        # 3. 构建 file_id 队列：主凭证优先，其余追加（去重）
        file_id_queue = []
        seen = set()
        if primary_from_data:
            file_id_queue.append(primary_from_data)
            seen.add(primary_from_data)
        for fid in all_file_ids:
            if fid not in seen:
                file_id_queue.append(fid)
                seen.add(fid)

        # 4. 补充 _pending_receipt_file_ids 中未消费的（兜底）
        for fid in self._pending_receipt_file_ids:
            if fid not in seen:
                file_id_queue.append(fid)
                seen.add(fid)
        # 清空队列（全部消费）
        self._pending_receipt_file_ids.clear()

        # 5. 逐个解析
        primary_path = None
        primary_hash = ""
        additional: list[dict] = []

        # 如果有显式路径，直接作为主凭证
        if explicit_path:
            primary_path = self._ensure_file_in_receipt_dir(explicit_path)
            primary_hash = self._last_receipt_file_hash or ""

        for fid in file_id_queue:
            path = self._ensure_file_in_receipt_dir(f"agent_upload/{fid}")
            if not path:
                continue
            fhash = self._last_receipt_file_hash or ""
            if primary_path is None:
                primary_path = path
                primary_hash = fhash
            else:
                additional.append({"file_path": path, "file_hash": fhash})

        return primary_path, primary_hash, additional

    def _resolve_receipt_path(self, receipt_data: dict, explicit_path: str = None) -> Optional[str]:
        """向后兼容的单文件解析。内部调 _resolve_receipt_paths 取主凭证。
        调用后 self._last_receipt_file_hash 为空字符串（主凭证哈希通过 _resolve_receipt_paths 返回值获取）。
        """
        path, fhash, _ = self._resolve_receipt_paths(receipt_data, explicit_path)
        self._last_receipt_file_hash = fhash or None
        return path

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

    # ═══════════════════════════════════════════════════════════
    # 统一执行入口（简化版，无 mode guard / document guard）
    # ═══════════════════════════════════════════════════════════

    def execute(self, tool_name: str, arguments: dict) -> str:
        """统一执行入口 — 无模式守卫，仅角色权限控制"""
        # 白名单校验：阻止 LLM 误传/恶意传非 TOOL_DEFINITIONS 中的方法名
        # 防止 getattr(self, tool_name) 命中父类继承的 dunder 或私有方法
        if tool_name not in _ALLOWED_TOOLS:
            logger.warning("非白名单工具调用拒绝: %s", tool_name)
            return json.dumps({
                "error": f"未知工具: {tool_name}",
                "hint": "仅允许调用 TOOL_DEFINITIONS 中声明的工具。",
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

                # 调 FileAnalyzer
                file_name = file_id  # file_id 作为文件名 fallback
                analysis = FileAnalyzer.analyze(
                    file_path, file_name,
                    purpose=purpose,
                    db=self.db,
                    user_id=self.user.id,
                )

                if analysis.get("duplicate_detected"):
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
                    # 追踪凭证文件 file_id（不依赖 LLM 回传 _source_file_id）
                    if analysis.get("type") == "receipt":
                        self._pending_receipt_file_ids.append(file_id)
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
    # 🆕 match_and_confirm_payment — 凭证自动匹配 + 确认
    # ═══════════════════════════════════════════════════════════

    def match_and_confirm_payment(
        self,
        contract_id: int,
        receipt_data: dict,
        payment_type: str = "income",
        receipt_file_ids: list[str] = None,
        additional_item_id: Optional[int] = None,
    ) -> str:
        """根据凭证分析结果，自动匹配合同中待确认(pending)的付款记录。

        匹配成功 → 更新为 paid
        无匹配   → 创建新付款记录（paid 状态）

        Args:
            contract_id: 关联合同ID
            receipt_data: analyze_files 返回的凭证分析结果
            payment_type: income（收入）或 expense（支出）
            receipt_file_ids: 要关联的凭证文件ID列表（多张凭证合并录入时传入）

        Returns:
            JSON: {"success": True, "matched": bool, "payment": {...}}
        """
        # 角色权限校验：income 只能录入收入，expense 只能录入支出
        if payment_type == "income" and not self._can_view_income():
            return json.dumps({"error": "当前角色无权录入收入记录"}, ensure_ascii=False)
        if payment_type == "expense" and not self._can_view_expense():
            return json.dumps({"error": "当前角色无权录入支出记录"}, ensure_ascii=False)

        # 验证合同
        contract = self.db.query(Contract).filter(
            Contract.id == contract_id, Contract.is_deleted == False
        ).first()
        if not contract:
            return json.dumps({"error": f"合同不存在: {contract_id}"}, ensure_ascii=False)

        if not isinstance(receipt_data, dict):
            return json.dumps({"error": "receipt_data 格式错误，请从 analyze_files 结果中获取"}, ensure_ascii=False)

        # 观测：检测 LLM 是否漏传 _source_file_id（不阻塞，仅打 warning）
        if isinstance(receipt_data, dict) and not receipt_data.get("_source_file_id") and not receipt_file_ids:
            logger.warning(
                "match_and_confirm_payment: receipt_data 缺少 _source_file_id 且无 receipt_file_ids，"
                "凭证图片可能丢失。contract_id=%s, session=%s",
                contract_id, self.session_id,
            )

        # 提取凭证关键字段
        amount = None
        try:
            amount = float(receipt_data.get("amount", 0))
        except (TypeError, ValueError):
            pass
        currency = receipt_data.get("currency", contract.currency or "CNY")
        payer_name = receipt_data.get("payer_name", "")
        payee_name = receipt_data.get("payee_name", "")
        transaction_date = receipt_data.get("transaction_date", "")
        business_hint = receipt_data.get("business_hint", "")
        payment_purpose = receipt_data.get("payment_purpose", "") or ""
        description = payment_purpose or receipt_data.get("description", "") or business_hint or ""
        # 自动生成更可读的描述
        # 凭证本身的 OCR 结果几乎不会带"定金/尾款"这类标签，但合同 payment_terms 里有——
        # 用金额+币种从付款计划里反查最匹配的一期，把名字带进 description。
        # 仅用于描述参考，不写入 installment_number 等结构化字段。
        term_label_hint = (
            receipt_data.get("installment_name")
            or self._match_payment_term_label(contract, amount or 0, currency, payment_type)
        )
        auto_desc = self._build_payment_description(
            amount=amount, currency=currency,
            installment_name=term_label_hint or "",
            business_hint=business_hint,
            payee_name=payee_name if payment_type == "expense" else None,
            contract=contract,
        )
        description = description or auto_desc
        document_type = receipt_data.get("document_type", "")

        # 查该合同所有 pending 状态同类型付款记录
        pending_payments = (
            self.db.query(Payment)
            .filter(
                Payment.contract_id == contract_id,
                Payment.type == payment_type,
                Payment.status == "pending",
                Payment.is_deleted == False,
            )
            .order_by(Payment.installment_number.asc())
            .all()
        )

        matched = None
        match_error = None  # 匹配分支异常标记，阻断后续创建新记录的 fallback
        if pending_payments and amount and amount > 0:
            # 匹配策略：金额最接近 + 币种相同优先
            best_match = None
            best_score = float("inf")
            for p in pending_payments:
                score = abs(float(p.amount) - amount)
                if p.currency == currency:
                    score *= 0.5  # 同币种优先
                if score < best_score:
                    best_score = score
                    best_match = p

            # 阈值：金额差异 < 1% 或 < 100 元
            if best_match and (
                (best_match.amount > 0 and abs(float(best_match.amount) - amount) / float(best_match.amount) < 0.01)
                or abs(float(best_match.amount) - amount) < 100
            ):
                # 匹配成功 → 更新为 paid
                payment = best_match
                try:
                    # 凭证路径解析：支持多张凭证合并录入
                    receipt_path, file_hash, additional_receipts = self._resolve_receipt_paths(
                        receipt_data, None, receipt_file_ids,
                    )

                    # 凭证去重：同合同下相同文件哈希不允许重复（排除自身）
                    if receipt_path and file_hash:
                        dup = self.db.query(Payment).filter(
                            Payment.contract_id == contract_id,
                            Payment.receipt_file_hash == file_hash,
                            Payment.id != payment.id,
                            Payment.is_deleted == False,
                        ).first()
                        if dup:
                            self.db.rollback()
                            info = self._payment_to_dict_lite(dup)
                            return json.dumps({
                                "duplicate": True,
                                "existing_payment": info,
                                "message": "该凭证已在此合同下录入过",
                            }, ensure_ascii=False)

                    payment.status = "paid"
                    payment.paid_amount = Decimal(str(amount))
                    payment.currency = currency
                    payment.paid_date = date.today()
                    if transaction_date:
                        try:
                            payment.paid_date = date.fromisoformat(transaction_date)
                        except (ValueError, TypeError):
                            pass
                    payment.payment_method = document_type or "unknown"
                    payment.notes = f"凭证自动匹配确认: {description}" if description else "凭证自动匹配确认"
                    payment.description = description[:100] if description else None
                    payment.receipt_data = receipt_data
                    if additional_item_id:
                        payment.additional_item_id = additional_item_id
                    if receipt_path:
                        payment.receipt_image_path = receipt_path
                    if file_hash:
                        payment.receipt_file_hash = file_hash
                    if additional_receipts:
                        payment.additional_receipt_files = additional_receipts

                    # 计算汇率
                    if currency and currency != "CNY":
                        try:
                            _, amount_in_cny = ExchangeRateService.convert_to_cny(
                                self.db, Decimal(str(amount)), currency, payment.paid_date
                            )
                            if amount_in_cny:
                                payment.amount_in_cny = amount_in_cny
                                payment.paid_amount_in_cny = amount_in_cny
                        except Exception:
                            pass

                    # 更新合同汇总金额（pending→paid 必须累加，否则合同已收为 0）
                    contract = self.db.query(Contract).filter(Contract.id == contract_id).first()
                    if contract:
                        amt_cny = payment.paid_amount_in_cny or payment.paid_amount
                        if payment_type == "expense":
                            PaymentService._add_to_contract_expense(
                                self.db, contract, payment.paid_amount, payment.currency,
                                amt_cny, payment.paid_date,
                            )
                        else:
                            PaymentService._add_to_contract_paid(
                                self.db, contract, payment.paid_amount, payment.currency,
                                amt_cny, payment.paid_date,
                            )

                    self.db.commit()
                    self.db.refresh(payment)

                    # 审计日志
                    try:
                        from app.services.audit_service import AuditService
                        AuditService.log(
                            self.db,
                            user_id=self.user.id,
                            action="confirm_payment",
                            entity_type="payment",
                            entity_id=payment.id,
                            old_values={"status": "pending"},
                            new_values={
                                "status": "paid",
                                "amount": float(payment.amount),
                                "currency": payment.currency,
                                "paid_date": str(payment.paid_date) if payment.paid_date else None,
                                "contract_id": contract_id,
                            },
                        )
                    except Exception as e:
                        logger.warning("审计日志写入失败: entity=payment, action=confirm_payment, error=%s", e)

                    matched = {
                        "id": payment.id,
                        "installment_name": payment.installment_name,
                        "amount": float(payment.amount),
                        "currency": payment.currency,
                        "status": payment.status,
                        "paid_date": str(payment.paid_date) if payment.paid_date else None,
                    }
                except Exception as e:
                    self.db.rollback()
                    logger.exception("match_and_confirm 匹配更新失败")
                    match_error = "匹配更新失败，请重试或转人工"

        # 匹配阶段异常 → 阻断创建新记录，向上抛错让 LLM 看到失败并重试或询问用户
        if match_error:
            return json.dumps({
                "error": match_error,
                "matched": False,
                "hint": "匹配过程出错，请勿静默创建新记录。请向用户说明情况并重试或转人工。",
            }, ensure_ascii=False)

        # 无匹配 → 创建新记录
        if not matched:
            try:
                installment_number = PaymentService.get_next_installment_number(
                    self.db, contract_id, payment_type
                )

                # 凭证路径解析：支持多张凭证合并录入
                receipt_path, file_hash, additional_receipts = self._resolve_receipt_paths(
                    receipt_data, None, receipt_file_ids,
                )

                # 凭证去重：同合同下相同文件哈希不允许重复录入
                if receipt_path and file_hash:
                    dup = self.db.query(Payment).filter(
                        Payment.contract_id == contract_id,
                        Payment.receipt_file_hash == file_hash,
                        Payment.is_deleted == False,
                    ).first()
                    if dup:
                        info = self._payment_to_dict_lite(dup)
                        return json.dumps({
                            "duplicate": True,
                            "existing_payment": info,
                            "message": "该凭证已在此合同下录入过",
                        }, ensure_ascii=False)

                paid_date = date.today()
                if transaction_date:
                    try:
                        paid_date = date.fromisoformat(transaction_date)
                    except (ValueError, TypeError):
                        pass

                payment = PaymentService.create_payment_with_exchange_rate(
                    db=self.db,
                    contract_id=contract_id,
                    installment_number=installment_number,
                    currency=currency or contract.currency or "CNY",
                    amount=Decimal(str(amount)) if amount else Decimal("0"),
                    paid_date=paid_date,
                    payment_method=document_type or "unknown",
                    receipt_image_path=receipt_path,
                    notes=description or "凭证录入",
                    created_by=self.user.id,
                    type=payment_type,
                    installment_name=receipt_data.get("installment_name"),
                    receipt_file_hash=file_hash,
                )

                # 补充 receipt_data + additional_receipt_files
                # 防御：即使 receipt_image_path 解析失败（file_id 丢失等），
                # 只要有 receipt_data（说明 analyze_files 确实分析过凭证），
                # 就应视为有效凭证，强制 paid + 补结算合同金额。
                if receipt_data:
                    payment.receipt_data = receipt_data
                    if additional_item_id:
                        payment.additional_item_id = additional_item_id
                    payment.description = description[:100] if description else None
                    if payee_name and payment_type == "expense":
                        payment.payee_name = payee_name
                    if payment.status == "pending":
                        logger.info(
                            "match_and_confirm: receipt_image_path 为空但有 receipt_data，"
                            "强制 paid + 补结算合同金额: payment_id=%s, contract_id=%s",
                            payment.id, contract_id,
                        )
                        payment.status = "paid"
                        payment.notes = (payment.notes or "") + "（附凭证分析数据）"
                        amt_cny = payment.paid_amount_in_cny or payment.paid_amount
                        if payment_type == "expense":
                            PaymentService._add_to_contract_expense(
                                self.db, contract, payment.paid_amount, payment.currency,
                                amt_cny, payment.paid_date,
                            )
                        else:
                            PaymentService._add_to_contract_paid(
                                self.db, contract, payment.paid_amount, payment.currency,
                                amt_cny, payment.paid_date,
                            )
                if additional_receipts:
                    payment.additional_receipt_files = additional_receipts
                self.db.commit()
                self.db.refresh(payment)

                matched = {
                    "id": payment.id,
                    "installment_name": payment.installment_name,
                    "amount": float(payment.amount),
                    "currency": payment.currency,
                    "status": payment.status,
                    "paid_date": str(payment.paid_date) if payment.paid_date else None,
                }
            except Exception as e:
                self.db.rollback()
                logger.exception("match_and_confirm 创建新记录失败")
                return json.dumps({
                    "error": "创建付款记录失败，请重试或转人工",
                    "matched": False,
                }, ensure_ascii=False)

        return json.dumps({
            "success": True,
            "matched": True if pending_payments and matched else False,
            "payment": matched,
            "message": "凭证已匹配并确认" if pending_payments and matched else "已创建新付款记录",
        }, ensure_ascii=False, default=str)

    # ═══════════════════════════════════════════════════════════
    # 🔄 create_payment_record — 合并 create_payment + create_expense
    # ═══════════════════════════════════════════════════════════

    def create_payment_record(
        self,
        contract_id: int,
        amount: float,
        currency: str,
        paid_date: str,
        type: str = "income",  # noqa: A002
        payee_name: Optional[str] = None,
        installment_name: Optional[str] = None,
        installment_number: Optional[int] = None,
        payment_method: str = "unknown",
        receipt_image_path: Optional[str] = None,
        notes: Optional[str] = None,
        description: Optional[str] = None,
        receipt_data: Optional[dict] = None,
        receipt_file_ids: list[str] = None,
        additional_item_id: Optional[int] = None,
        no_receipt: bool = False,
    ) -> str:
        """统一的付款记录创建（收入/支出）。

        Args:
            contract_id: 合同ID
            amount: 金额
            currency: 币种（CNY/HKD）
            paid_date: 付款日期（YYYY-MM-DD）
            type: income（收入）或 expense（支出）
            payee_name: 收款方名称（仅支出，必填）
            installment_name: 期数名称（如"定金"、"尾款"）
            installment_number: 期数编号（可选，系统自动计算）
            payment_method: 付款方式
            receipt_image_path: 凭证图片路径
            notes: 备注
            description: 简短业务说明（不超过30字）
            receipt_data: 凭证分析结构化数据
            receipt_file_ids: 要关联的凭证文件ID列表（多张凭证合并录入时传入）
            no_receipt: 声明这是用户口头确认的无凭证小额支出（仅 type=expense 可用）
        """
        # 角色权限校验：income 只能创建收入，expense 只能创建支出
        if type == "income" and not self._can_view_income():
            return json.dumps({"error": "当前角色无权创建收入记录"}, ensure_ascii=False)
        if type == "expense" and not self._can_view_expense():
            return json.dumps({"error": "当前角色无权创建支出记录"}, ensure_ascii=False)

        # 合同校验
        contract = self.db.query(Contract).filter(
            Contract.id == contract_id, Contract.is_deleted == False
        ).first()
        if not contract:
            return json.dumps({"error": f"合同不存在: {contract_id}"}, ensure_ascii=False)

        # 支出必须有收款方
        if type == "expense" and not payee_name:
            return json.dumps({"error": "创建支出记录必须指定收款方名称"}, ensure_ascii=False)

        # ─────────────────────────────────────────────────────────
        # 无凭证支出栅栏：数据完整性边界，三道硬约束
        # 仅返回结构化错误，不嵌入"请先..."等行为指令（CLAUDE.md 工具铁律）
        # ─────────────────────────────────────────────────────────
        if no_receipt:
            if type != "expense":
                return json.dumps({
                    "error": "no_receipt 仅支持 type=expense",
                    "code": "NO_RECEIPT_INCOME_FORBIDDEN",
                }, ensure_ascii=False)
            missing_fields = []
            if not payee_name:
                missing_fields.append("payee_name")
            if not description:
                missing_fields.append("description")
            if not paid_date:
                missing_fields.append("paid_date")
            if missing_fields:
                return json.dumps({
                    "error": "no_receipt 支出缺少必填字段",
                    "code": "NO_RECEIPT_MISSING_FIELDS",
                    "missing_fields": missing_fields,
                }, ensure_ascii=False)
            if receipt_image_path or receipt_data or receipt_file_ids:
                return json.dumps({
                    "error": "no_receipt=true 与凭证字段互斥",
                    "code": "NO_RECEIPT_WITH_RECEIPT_DATA",
                }, ensure_ascii=False)

        # 凭证路径处理：支持多张凭证合并录入
        resolved_path, file_hash, additional_receipts = self._resolve_receipt_paths(
            receipt_data or {}, receipt_image_path, receipt_file_ids,
        )
        if resolved_path:
            receipt_image_path = resolved_path

        # 观测：检测 LLM 是否漏传 _source_file_id（不阻塞，仅打 warning）
        if isinstance(receipt_data, dict) and not receipt_data.get("_source_file_id") and not receipt_file_ids:
            logger.warning(
                "create_payment_record: receipt_data 缺少 _source_file_id 且无 receipt_file_ids，"
                "凭证图片可能丢失。contract_id=%s, session=%s",
                contract_id, self.session_id,
            )

        # 凭证去重：同合同下相同文件哈希的凭证不允许重复录入
        if resolved_path and file_hash:
            existing = self.db.query(Payment).filter(
                Payment.contract_id == contract_id,
                Payment.receipt_file_hash == file_hash,
                Payment.is_deleted == False,
            ).first()
            if existing:
                info = self._payment_to_dict_lite(existing)
                return json.dumps({
                    "duplicate": True,
                    "existing_payment": info,
                    "message": "该凭证已在此合同下录入过",
                }, ensure_ascii=False)

        # 自动生成 description（如果 Agent 未提供）
        # 与 match_and_confirm_payment 对齐：
        #   1. 优先用 receipt_data.business_hint 原文（VL 已抽取的简短业务说明，最干净）
        #   2. 否则回退 _build_payment_description 拼接（金额+期数+收款方+合同业务）
        # 不能直接走 _build 拼接，否则 description 会变成
        # "HK$4,330 →MINKFAIR... 购买港车 底盘号..." 这种堆字段串。
        # 无凭证支出场景跳过：栅栏 2 已强制 description 必填，LLM 必须显式给出。
        if not description and not no_receipt:
            hint = ""
            if isinstance(receipt_data, dict):
                hint = receipt_data.get("payment_purpose", "") or receipt_data.get("business_hint", "") or ""
            if hint:
                description = hint
            else:
                term_label_hint = installment_name or self._match_payment_term_label(
                    contract, amount or 0, currency, type,
                )
                description = self._build_payment_description(
                    amount=amount, currency=currency,
                    installment_name=term_label_hint or "",
                    business_hint="",
                    payee_name=payee_name if type == "expense" else None,
                    contract=contract,
                )

        # 期数
        if not installment_number:
            installment_number = PaymentService.get_next_installment_number(
                self.db, contract_id, type
            )

        # 解析日期
        try:
            paid_dt = date.fromisoformat(paid_date)
        except (ValueError, TypeError):
            paid_dt = date.today()

        try:
            payment = PaymentService.create_payment_with_exchange_rate(
                db=self.db,
                contract_id=contract_id,
                installment_number=installment_number,
                currency=currency,
                amount=Decimal(str(amount)),
                paid_date=paid_dt,
                payment_method=payment_method,
                receipt_image_path=receipt_image_path,
                notes=notes or "",
                created_by=self.user.id,
                type=type,
                installment_name=installment_name,
                receipt_file_hash=file_hash,
            )

            # 补充字段 + 凭证状态
            if payee_name and type == "expense":
                payment.payee_name = payee_name
            if additional_item_id:
                payment.additional_item_id = additional_item_id
            if description:
                payment.description = description[:100]
            has_receipt = bool(receipt_data or receipt_image_path)
            if has_receipt:
                payment.receipt_data = receipt_data
                if additional_receipts:
                    payment.additional_receipt_files = additional_receipts
                # 如果 service 层因无 receipt_image_path 创建了 pending 记录，
                # 需要手动更新合同金额（有 receipt_image_path 时 service 已处理）
                needs_contract_update = payment.status == "pending"
                payment.status = "paid"  # 有凭证 → 直接确认
                payment.notes = (notes or "") + "（附凭证）" if notes else "凭证录入"
                if needs_contract_update:
                    amt_cny = payment.paid_amount_in_cny or payment.paid_amount
                    if type == "expense":
                        PaymentService._add_to_contract_expense(
                            self.db, contract, payment.paid_amount, payment.currency,
                            amt_cny, payment.paid_date,
                        )
                    else:
                        PaymentService._add_to_contract_paid(
                            self.db, contract, payment.paid_amount, payment.currency,
                            amt_cny, payment.paid_date,
                        )
            elif no_receipt:
                # 无凭证支出：用户口头确认，强制 paid + 累加合同累计支出
                # service 因无 receipt_image_path 创建了 pending 记录，需要手动转 paid
                from app.core.payment_audit import NO_RECEIPT_NOTE_PREFIX
                needs_contract_update = payment.status == "pending"
                payment.status = "paid"
                base_note = notes or description or ""
                payment.notes = f"{NO_RECEIPT_NOTE_PREFIX} {base_note}".strip()
                if needs_contract_update:
                    amt_cny = payment.paid_amount_in_cny or payment.paid_amount
                    PaymentService._add_to_contract_expense(
                        self.db, contract, payment.paid_amount, payment.currency,
                        amt_cny, payment.paid_date,
                    )

            self.db.commit()
            self.db.refresh(payment)

            return json.dumps({
                "success": True,
                "payment": {
                    "id": payment.id,
                    "installment_name": payment.installment_name,
                    "type": payment.type,
                    "amount": float(payment.amount),
                    "currency": payment.currency,
                    "status": payment.status,
                    "paid_date": str(payment.paid_date) if payment.paid_date else None,
                },
                "message": f"{'收入' if type == 'income' else '支出'}记录已创建",
            }, ensure_ascii=False, default=str)

        except Exception as e:
            self.db.rollback()
            logger.exception("create_payment_record 失败")
            return json.dumps({"error": "创建付款记录失败，请重试或转人工"}, ensure_ascii=False)

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

        # 如果传入凭证数据但 description 未设置 → 自动生成
        if isinstance(receipt_data, dict) and not kwargs.get("description"):
            payment = self.db.query(Payment).filter(Payment.id == payment_id).first()
            if payment:
                contract = payment.contract
                hint = receipt_data.get("business_hint", "")
                desc = self._build_payment_description(
                    amount=float(payment.amount) if payment.amount else 0,
                    currency=payment.currency or "CNY",
                    installment_name=payment.installment_name or "",
                    business_hint=hint,
                    contract=contract,
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


# ═══════════════════════════════════════════════════════════════
# TOOL_DEFINITIONS v2 — 18 个工具
# ═══════════════════════════════════════════════════════════════

TOOL_DEFINITIONS = [
    # ── 文件分析 ──
    {
        "type": "function",
        "function": {
            "name": "analyze_files",
            "description": "分析上传的文件。自动识别文件类型（合同/付款凭证/群聊截图），并提取结构化信息。仅支持这三种类型，车辆照片、证件等会被拒绝并提示原因。用户上传文件后应首先调用此工具。支持批量分析多个文件。纯分析工具，不写数据库。",
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
                        "enum": ["auto", "contract", "receipt", "group_chat"],
                        "description": "分析目的。auto=自动判断（默认），其余为强制指定类型",
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
            "description": "为客户创建合同记录。需要先通过 create_customer 或 search_customers 获取 customer_id。合同编号自动生成。如果同一文件已创建过合同会返回已有记录。**只生成合同与付款计划（payment_terms），不创建任何 payment 记录**——付款记录的唯一来源是凭证录入（match_and_confirm_payment）或手动录入（create_payment_record）。",
            "parameters": {
                "type": "object",
                "required": ["customer_id", "file_id"],
                "properties": {
                    "customer_id": {"type": "integer", "description": "客户ID"},
                    "file_id": {"type": "string", "description": "上传文件的ID。系统会自动使用 analyze_files 对该文件的分析结果。"},
                    "title": {"type": "string", "description": "合同标题"},
                    "total_amount": {"type": "number", "description": "合同总金额"},
                    "currency": {"type": "string", "enum": ["CNY", "HKD"], "description": "币种。HK$/港币=HKD，¥/人民币=CNY"},
                    "signed_date": {"type": "string", "description": "签订日期（YYYY-MM-DD）"},
                    "business_type": {"type": "string", "enum": ["车辆买卖", "两地牌过户", "年检保险", "其他"], "description": "业务类型"},
                    "business_description": {"type": "string", "description": "极简业务描述（如：购买现牌 粤Z7N80港 深圳湾口岸）"},
                    "wechat_group": {"type": "string", "description": "业务微信群名称"},
                    "contract_data": {"type": "object", "description": "合同分析数据（通常无需传递，系统自动从缓存获取）"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_contract",
            "description": "更新合同信息。用于补充微信群名称、备注等元信息。当用户发送业务群截图时，提取群名后关联到合同。",
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
    # ── 付款管理（4 个） ──
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
            "name": "create_payment_record",
            "description": "创建付款记录（统一收入/支出）。type=income 为客户收入，type=expense 为公司支出（必须指定 payee_name）。有凭证时自动设为 paid 状态并参与结算。无凭证小额支出（如返点、现金杂费）通过 no_receipt=true 显式声明，仅 type=expense 可用。重要：receipt_data 必须原样回传 analyze_files 返回的完整对象，不要只挑业务字段——其中的 _source_file_id 是关联凭证文件的关键，缺少会导致凭证图片丢失。",
            "parameters": {
                "type": "object",
                "required": ["contract_id", "amount", "currency", "paid_date", "type"],
                "properties": {
                    "contract_id": {"type": "integer", "description": "合同ID"},
                    "amount": {"type": "number", "description": "金额"},
                    "currency": {"type": "string", "enum": ["CNY", "HKD"], "description": "币种"},
                    "paid_date": {"type": "string", "description": "付款日期（YYYY-MM-DD）"},
                    "type": {"type": "string", "enum": ["income", "expense"], "description": "income=收入，expense=支出"},
                    "payee_name": {"type": "string", "description": "收款方名称（仅支出必填）"},
                    "installment_name": {"type": "string", "description": "期数名称（如'定金'、'尾款'）"},
                    "payment_method": {"type": "string", "enum": ["bank_transfer", "wechat", "alipay", "cash", "check", "unknown"], "description": "付款方式"},
                    "receipt_image_path": {"type": "string", "description": "凭证图片路径"},
                    "notes": {"type": "string", "description": "备注"},
                    "description": {"type": "string", "description": "简短业务说明（不超过30字）。no_receipt=true 时必填。"},
                    "receipt_data": {"type": "object", "description": "凭证分析数据完整 JSON 对象（含 _source_file_id）。禁止只挑部分字段回传。"},
                    "receipt_file_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "要关联的凭证文件ID列表（从 analyze_files 结果获取）。传多个时表示多张凭证合并录入同一笔付款。不传时按系统追踪自动分配。",
                    },
                    "no_receipt": {
                        "type": "boolean",
                        "description": "声明这是用户口头确认的无凭证小额支出（如返点、现金杂费）。仅 type=expense 可用。设为 true 时不得再传 receipt_image_path/receipt_data/receipt_file_ids，且 description/payee_name/paid_date 必填。设为 true 后记录直接落 paid 并累加合同累计支出，notes 自动加「[无凭证支出]」前缀。",
                    },
                    "additional_item_id": {
                        "type": "integer",
                        "description": "可选：把这笔付款标到某项附加项（仅展示标签，不影响金额聚合）。仅当用户明确说\"这笔是付XX\"时填，附加项 id 从 list_additional_items / get_contract_detail 的 additional_items.id 获取；识别不到就不填。",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "match_and_confirm_payment",
            "description": "根据凭证分析结果，自动匹配合同中待确认(pending)的付款记录。匹配成功则更新为paid；无匹配则创建新付款记录。需要先调 analyze_files 获取凭证数据，再传入 receipt_data。重要：receipt_data 必须原样回传 analyze_files 返回的完整对象，不要只挑业务字段——其中的 _source_file_id 是关联凭证文件的关键，缺少会导致凭证图片丢失。",
            "parameters": {
                "type": "object",
                "required": ["contract_id", "receipt_data"],
                "properties": {
                    "contract_id": {"type": "integer", "description": "关联合同ID"},
                    "receipt_data": {"type": "object", "description": "analyze_files 返回的凭证分析结果完整 JSON 对象（含 _source_file_id）。禁止只挑部分字段回传。"},
                    "payment_type": {"type": "string", "enum": ["income", "expense"], "description": "收入或支出，默认 income"},
                    "receipt_file_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "要关联的凭证文件ID列表（从 analyze_files 结果获取）。传多个时表示多张凭证合并录入同一笔付款（如转账截图+收据）。不传时按系统追踪自动分配。",
                    },
                    "additional_item_id": {
                        "type": "integer",
                        "description": "可选：把这笔付款标到某项附加项（仅展示标签，不影响金额聚合）。仅当用户备注明确说\"这笔是付XX\"时填，附加项 id 从 list_additional_items / get_contract_detail 的 additional_items.id 获取；识别不到就不填，绝不追问归属。",
                    },
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
]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 模块加载完成后填充工具白名单（供 ToolExecutorV2.execute 校验）
# 防御性检查：TOOL_DEFINITIONS 为空时 _ALLOWED_TOOLS 必须是空集，execute 拒绝一切
# 防止误删 TOOL_DEFINITIONS 后白名单被错误地填充
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
_ALLOWED_TOOLS = frozenset(
    t["function"]["name"] for t in TOOL_DEFINITIONS if "function" in t and "name" in t["function"]
)
