"""
Agent 工具执行器
调用现有 Service 层实现业务操作
"""
import base64
import json
import os
import shutil
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Optional

from datetime import timedelta

import logging
import redis as redis_lib

logger = logging.getLogger(__name__)
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.config import settings
from app.core.chinese import search_variants
from app.core.permissions import Role, is_admin as _perm_is_admin, can_view_income as _perm_can_view_income, can_view_expense as _perm_can_view_expense, can_create_contract as _perm_can_create_contract
from app.models.customer import Customer
from app.models.contract import Contract
from app.models.payment import Payment
from app.models.user import User
from app.core.business_types import BusinessType
from app.services.contract_service import ContractService
from app.services.customer_service import CustomerService, _escape_ilike
from app.services.payment_service import PaymentService
from app.utils.file_analysis import guess_extension, normalize_payment_terms
from app.utils.file_utils import calculate_file_hash, resolve_file_path, validate_file_id_in_dir


# 模块级 Redis 连接池，所有 ToolExecutor 实例共享，避免每次请求新建连接
_redis_pool: Optional[redis_lib.ConnectionPool] = None


def _get_redis_pool() -> Optional[redis_lib.ConnectionPool]:
    """获取或创建模块级 Redis 连接池。返回 None 表示 Redis 不可用。"""
    global _redis_pool
    if _redis_pool is not None:
        return _redis_pool
    try:
        _redis_pool = redis_lib.ConnectionPool.from_url(
            settings.REDIS_URL,
            socket_connect_timeout=1,
            socket_timeout=1,
            decode_responses=True,
        )
        # 验证连接可用
        redis_lib.Redis(connection_pool=_redis_pool).ping()
        logger.debug("Redis 连接池创建成功")
        return _redis_pool
    except Exception:
        _redis_pool = None
        logger.debug("Redis 连接池创建失败，将使用内存缓存降级")
        return None


class ToolExecutor:
    """Agent 工具执行器，每个方法返回 JSON 字符串"""

    # VL 分析缓存 TTL（秒），跨请求保持可用
    _ANALYSIS_CACHE_TTL = 1800  # 30 分钟

    def __init__(self, db: Session, user: User, session_id: Optional[str] = None):
        self.db = db
        self.user = user
        self.session_id = session_id
        self.mode: str = "chat"  # 会话模式：chat | receipt_income | receipt_expense
        self.session_context: Optional[dict] = None  # 模式上下文
        self._document_context: Optional[str] = None  # "receipt"|"contract"|"general"|None
        self._pending_receipt_path: Optional[str] = None  # 同请求内快速路径
        self._last_receipt_file_hash: Optional[str] = None  # 凭证去重：最近一次 _ensure_file_in_receipt_dir 计算的 SHA-256
        self._file_hash_cache: dict = {}  # file_path → sha256 hash，避免 _try_pre_analyze 和 create_contract 重复计算

        # Redis 缓存：使用模块级连接池，跨请求复用连接
        self._redis: Optional[redis_lib.Redis] = None
        # 内存兜底：Redis 不可用时降级
        self._memory_contract: dict = {}
        self._memory_receipt: dict = {}
        pool = _get_redis_pool()
        if pool is not None:
            self._redis = redis_lib.Redis(connection_pool=pool)

    def _cache_key(self, analysis_type: str, file_id: str) -> str:
        """Redis 缓存 key。

        contract: vl:contract:{file_id}（PR-B-3 新格式，与 contract_analyzer 共享，file_id 为 UUID 不加 sid）
        receipt:   vl:receipt:{session_id}:{file_id}（保持旧格式，receipt 路径未重构）
        """
        if analysis_type == "contract":
            return f"vl:contract:{file_id}"
        sid = self.session_id or "nosession"
        return f"vl:{analysis_type}:{sid}:{file_id}"

    def _summarize_analysis_for_context(self, structured: dict) -> dict:
        """压缩 VL 分析结果再返回给 LLM context，剥离大字段（完整数据已缓存供后续工具取用）"""
        if not isinstance(structured, dict):
            return structured
        summary = dict(structured)
        # full_text 可能 2000+ tokens，已缓存在 Redis，create_contract 直接从缓存读取
        summary.pop("full_text", None)
        return summary

    def _cache_analysis(self, file_id: str, analysis_type: str, data: dict) -> None:
        """将 文件预分析 的 VL 完整输出缓存到 Redis（含内存降级）"""
        if not isinstance(data, dict):
            return
        if self._redis:
            try:
                key = self._cache_key(analysis_type, file_id)
                self._redis.setex(key, self._ANALYSIS_CACHE_TTL, json.dumps(data, ensure_ascii=False))
                logger.debug("vl_cache写入Redis: key=%s", key)
                return
            except Exception:
                logger.warning("vl_cache Redis写入失败，降级内存: file_id=%s", file_id)
        # 内存降级
        if analysis_type == "contract":
            self._memory_contract[file_id] = data
        elif analysis_type == "receipt":
            self._memory_receipt[file_id] = data

    def get_cached_analysis(self, file_id: str, analysis_type: str) -> Optional[dict]:
        """公共接口：从缓存获取 VL/文本分析结果（优先 Redis，降级内存）。

        供 orchestrator 子图等外部模块调用，避免直接访问私有方法。
        参数和返回值与 _get_cached_analysis 完全一致。
        """
        return self._get_cached_analysis(file_id, analysis_type)

    def _get_cached_analysis(self, file_id: str, analysis_type: str) -> Optional[dict]:
        """从缓存获取 VL 分析结果，优先 Redis，降级内存，都无则返回 None"""
        if self._redis:
            try:
                key = self._cache_key(analysis_type, file_id)
                raw = self._redis.get(key)
                if raw:
                    data = json.loads(raw)
                    if isinstance(data, dict):
                        logger.debug("vl_cache命中Redis: key=%s", key)
                        return data
            except Exception:
                logger.warning("vl_cache Redis读取失败: file_id=%s", file_id)
        # 内存降级
        store = self._memory_contract if analysis_type == "contract" else self._memory_receipt
        data = store.get(file_id)
        if isinstance(data, dict):
            logger.debug("vl_cache命中内存: type=%s file_id=%s", analysis_type, file_id)
            return data
        return None

    def _can_access_contract(self, contract: Contract) -> bool:
        # 合同对所有角色全部可见（admin/income/expense），仅按 payment.type 隔离收支
        return True

    def _is_admin(self) -> bool:
        return _perm_is_admin(self.user)

    def _can_view_income(self) -> bool:
        return _perm_can_view_income(self.user)

    def _can_view_expense(self) -> bool:
        return _perm_can_view_expense(self.user)

    def _can_create_contract(self) -> bool:
        return _perm_can_create_contract(self.user)

    def _contract_to_dict(self, c: Contract) -> dict:
        return {
            "id": c.id,
            "contract_number": c.contract_number,
            "title": c.title,
            "business_type": c.business_type,
            "business_description": c.business_description,
            "customer_name": c.customer.name if c.customer else None,
            "currency": c.currency,
            "total_amount": float(c.total_amount) if c.total_amount else 0,
            "paid_amount": float(c.paid_amount) if c.paid_amount else 0,
            "total_expense": float(c.total_expense) if c.total_expense else 0,
            # 改造后：按币种字典（如 {"HKD": 150000, "CNY": 20000}）
            "paid_by_currency": getattr(c, "paid_by_currency", {}) or {},
            "expense_by_currency": getattr(c, "expense_by_currency", {}) or {},
            "outstanding_amount": float(c.outstanding_amount) if getattr(c, "outstanding_amount", None) else None,
            "outstanding_currency": getattr(c, "outstanding_currency", None),
            "status": c.status,
            "wechat_group": c.wechat_group,
            "signed_date": str(c.signed_date) if c.signed_date else None,
            "end_date": str(c.end_date) if c.end_date else None,
            "payment_stats": {
                "total": getattr(c, 'payment_total_count', 0),
                "paid": getattr(c, 'paid_count', 0),
                "expense_count": getattr(c, 'expense_count', 0),
            },
        }

    def _payment_to_dict(self, p: Payment) -> dict:
        return {
            "id": p.id,
            "contract_id": p.contract_id,
            "installment_number": p.installment_number,
            "installment_name": p.installment_name,
            "type": p.type,
            "payee_name": p.payee_name,
            "currency": p.currency,
            "amount": float(p.amount) if p.amount else 0,
            "paid_amount": float(p.paid_amount) if p.paid_amount else 0,
            "outstanding_amount": float(p.outstanding_amount) if p.outstanding_amount else None,
            "outstanding_currency": p.outstanding_currency,
            "due_date": str(p.due_date) if p.due_date else None,
            "paid_date": str(p.paid_date) if p.paid_date else None,
            "payment_method": p.payment_method,
            "status": p.status,
            "notes": p.notes,
            "description": p.description,
            "receipt_image_path": p.receipt_image_path,
            "receipt_data": p.receipt_data,
        }

    def _contract_to_dict_lite(self, c: Contract) -> dict:
        """精简合同信息，用于列表/搜索场景（减少 context token 消耗）"""
        return {
            "id": c.id,
            "contract_number": c.contract_number,
            "title": c.title,
            "business_description": c.business_description,
            "customer_name": c.customer.name if c.customer else None,
            "business_type": c.business_type,
            "total_amount": float(c.total_amount) if c.total_amount else 0,
            "currency": c.currency,
            "status": c.status,
            "signed_date": str(c.signed_date) if c.signed_date else None,
        }

    def _payment_to_dict_lite(self, p: Payment) -> dict:
        """精简付款信息，用于列表/查询场景（不含 receipt_data 等大字段）"""
        return {
            "id": p.id,
            "installment_name": p.installment_name,
            "type": p.type,
            "payee_name": p.payee_name,
            "currency": p.currency,
            "amount": float(p.amount) if p.amount else 0,
            "paid_amount": float(p.paid_amount) if p.paid_amount else 0,
            "outstanding_amount": float(p.outstanding_amount) if p.outstanding_amount else None,
            "outstanding_currency": p.outstanding_currency,
            "status": p.status,
            "due_date": str(p.due_date) if p.due_date else None,
            "paid_date": str(p.paid_date) if p.paid_date else None,
        }

    # ── 查询工具 ──

    def search_customers(
        self,
        name: Optional[str] = None,
        phone: Optional[str] = None,
        wechat_group: Optional[str] = None,
        limit: int = 10,
    ) -> str:
        query = self.db.query(Customer).filter(Customer.is_deleted == False)

        # 客户对所有角色全部可见（admin/income/expense）

        has_filter = bool(name or phone or wechat_group)

        if name:
            variants = search_variants(name)
            escaped = [_escape_ilike(v) for v in variants]
            query = query.filter(or_(*[Customer.name.ilike(f"%{v}%") for v in escaped]))
        if phone:
            query = query.filter(Customer.phone.ilike(f"%{_escape_ilike(phone)}%"))
        if wechat_group:
            variants = search_variants(wechat_group)
            escaped = [_escape_ilike(v) for v in variants]
            query = query.filter(or_(*[Customer.wechat_group_name.ilike(f"%{v}%") for v in escaped]))

        total_count = query.count()
        customers = query.order_by(Customer.created_at.desc()).limit(limit).all()

        # 单条 group_by 查询统计每个客户的合同数，避免 N+1
        contract_count_map: dict[int, int] = {}
        if customers:
            rows = (
                self.db.query(Contract.customer_id, func.count(Contract.id))
                .filter(
                    Contract.customer_id.in_([c.id for c in customers]),
                    Contract.is_deleted == False,
                )
                .group_by(Contract.customer_id)
                .all()
            )
            contract_count_map = {cid: cnt for cid, cnt in rows}

        results = []
        for c in customers:
            results.append({
                "id": c.id,
                "name": c.name,
                "contact_person": c.contact_person,
                "phone": c.phone,
                "wechat_group_name": c.wechat_group_name,
                "contract_count": contract_count_map.get(c.id, 0),
            })

        # 无筛选条件时：返回统计 + 少量样例，引导用户精确查找
        if not has_filter:
            return json.dumps({
                "summary": {"total_customers": total_count, "returned": len(results)},
                "customers": results,
            }, ensure_ascii=False)

        return json.dumps({"customers": results, "total": len(results)}, ensure_ascii=False)

    def search_contracts(self, **kwargs) -> str:
        # 合同对所有角色全部可见
        sales_person_id = None

        # 判断是否无筛选条件
        has_filter = any(kwargs.get(k) for k in (
            "status", "customer_id", "customer_name", "keyword",
            "date_from", "date_to", "contract_number",
        ))

        try:
            items, total = ContractService.get_contracts(
                self.db,
                page=kwargs.get("page", 1),
                per_page=kwargs.get("per_page", 10),
                status=kwargs.get("status"),
                customer_id=kwargs.get("customer_id"),
                customer_name=kwargs.get("customer_name"),
                keyword=kwargs.get("keyword"),
                date_from=kwargs.get("date_from"),
                date_to=kwargs.get("date_to"),
                sales_person_id=sales_person_id,
                contract_number=kwargs.get("contract_number"),
            )
        except Exception as e:
            return json.dumps({"error": str(e)}, ensure_ascii=False)

        contracts = [self._contract_to_dict_lite(c) for c in items]

        # 无筛选条件时：返回统计 + 少量样例，引导用户精确查找
        if not has_filter:
            # 统计各状态数量
            from sqlalchemy import func
            status_counts = (
                self.db.query(Contract.status, func.count(Contract.id))
                .filter(Contract.is_deleted == False)
                .group_by(Contract.status)
                .all()
            )
            by_status = {s: c for s, c in status_counts}

            return json.dumps({
                "summary": {
                    "total_contracts": total,
                    "by_status": by_status,
                    "returned": len(contracts),
                },
                "contracts": contracts,
            }, ensure_ascii=False)

        return json.dumps({"contracts": contracts, "total": total}, ensure_ascii=False)

    def get_contract_detail(self, contract_id: int) -> str:
        contract = ContractService.get_contract(self.db, contract_id)
        if not contract:
            return json.dumps({"error": f"合同不存在：{contract_id}"}, ensure_ascii=False)
        if not self._can_access_contract(contract):
            return json.dumps({"error": "无权查看该合同"}, ensure_ascii=False)

        result = self._contract_to_dict(contract)
        result["customer_id"] = contract.customer_id
        result["sales_person_id"] = contract.sales_person_id
        result["remarks"] = contract.remarks

        try:
            # 按角色过滤：income 只看收入，expense 只看支出，admin 看全部
            if self.user.role == Role.INCOME:
                type_filter = "income"
            elif self.user.role == Role.EXPENSE:
                type_filter = "expense"
            else:
                type_filter = None

            # Agent 场景：直接查询并用精简序列化，避免 PaymentResponse 22 字段全量输出
            pay_query = self.db.query(Payment).filter(Payment.contract_id == contract_id)
            if type_filter:
                pay_query = pay_query.filter(Payment.type == type_filter)
            all_payments = pay_query.order_by(Payment.installment_number).all()
            income_pays = [p for p in all_payments if p.type == "income"]
            expense_pays = [p for p in all_payments if p.type == "expense"]

            # 按币种分桶（改造后：不再做汇率折算）
            def _bucket(pays):
                buckets: dict = {}
                for p in pays:
                    if p.status == "paid" and p.currency:
                        buckets[p.currency] = float(buckets.get(p.currency, 0) + (p.paid_amount or 0))
                return buckets

            paid_by_currency = _bucket(income_pays)
            expense_by_currency = _bucket(expense_pays)

            if type_filter != "expense":
                result["income"] = {
                    "payments": [self._payment_to_dict_lite(p) for p in income_pays],
                    "total_amount": float(contract.total_amount),
                    "paid_amount": float(contract.paid_amount),
                    "paid_by_currency": paid_by_currency,
                }
            if type_filter != "income":
                result["expense"] = {
                    "payments": [self._payment_to_dict_lite(p) for p in expense_pays],
                    "total_expense": float(contract.total_expense or 0),
                    "expense_by_currency": expense_by_currency,
                }
        except Exception:
            result["income"] = {"payments": []}
            result["expense"] = {"payments": []}

        return json.dumps(result, ensure_ascii=False)

    def query_payments(self, **kwargs) -> str:
        query = self.db.query(Payment).filter(Payment.is_deleted == False)

        if kwargs.get("contract_id"):
            query = query.filter(Payment.contract_id == kwargs["contract_id"])

        if kwargs.get("status"):
            query = query.filter(Payment.status == kwargs["status"])

        if kwargs.get("type"):
            query = query.filter(Payment.type == kwargs["type"])

        # 角色权限：仅按 payment.type 隔离收支，合同对所有角色可见
        if self.user.role == Role.INCOME:
            query = query.filter(Payment.type == "income")
        elif self.user.role == Role.EXPENSE:
            query = query.filter(Payment.type == "expense")

        page = kwargs.get("page", 1)
        per_page = kwargs.get("per_page", 20)
        total = query.count()
        payments = query.order_by(Payment.created_at.desc()) \
            .offset((page - 1) * per_page).limit(per_page).all()

        results = [self._payment_to_dict_lite(p) for p in payments]

        for r, p in zip(results, payments):
            if p.contract:
                r["contract_number"] = p.contract.contract_number
                if p.contract.customer:
                    r["customer_name"] = p.contract.customer.name

        return json.dumps({"payments": results, "total": total}, ensure_ascii=False)

    # ── 动作工具 ──

    def create_customer(self, **kwargs) -> str:
        """创建客户。如果同名+同电话/邮箱的客户已存在，返回已有客户。"""
        if not self._can_create_contract():
            return json.dumps({"error": "当前角色无权创建客户"}, ensure_ascii=False)

        name = kwargs.get("name", "").strip()
        if not name:
            return json.dumps({"error": "客户姓名不能为空"}, ensure_ascii=False)

        phone = kwargs.get("phone", "").strip() or None
        email = kwargs.get("email", "").strip() or None

        if not phone and not email:
            return json.dumps({"error": "电话和邮箱至少填写一项"}, ensure_ascii=False)

        try:
            customer, created = CustomerService.create_or_get(
                db=self.db,
                name=name,
                phone=phone,
                email=email,
                contact_person=kwargs.get("contact_person"),
                id_card_number=kwargs.get("id_card_number"),
                business_license=kwargs.get("business_license"),
                address=kwargs.get("address"),
                wechat_group_name=kwargs.get("wechat_group_name"),
                remarks=kwargs.get("remarks"),
                created_by=self.user.id,
            )
            logger.info("create_customer: name=%s, id=%d, created=%s", name, customer.id, created)
            return json.dumps({
                "success": True,
                "customer": {
                    "id": customer.id,
                    "name": customer.name,
                    "phone": customer.phone,
                    "email": customer.email,
                    "wechat_group_name": customer.wechat_group_name,
                },
                "created": created,
            }, ensure_ascii=False)
        except Exception as e:
            logger.exception("create_customer failed")
            return json.dumps({"error": f"创建客户失败: {str(e)}"}, ensure_ascii=False)

    def update_customer(self, **kwargs) -> str:
        """更新已有客户信息（电话、证件号等）"""
        if not self._can_create_contract():
            return json.dumps({"error": "当前角色无权修改客户"}, ensure_ascii=False)

        customer_id = kwargs.get("customer_id")
        if not customer_id:
            return json.dumps({"error": "缺少 customer_id"}, ensure_ascii=False)

        customer = self.db.query(Customer).filter(
            Customer.id == customer_id, Customer.is_deleted == False
        ).first()
        if not customer:
            return json.dumps({"error": f"客户不存在: {customer_id}"}, ensure_ascii=False)

        # 记录旧值用于审计
        old_values = {
            "phone": customer.phone,
            "email": customer.email,
            "wechat_group_name": customer.wechat_group_name,
            "address": customer.address,
            "remarks": customer.remarks,
        }

        # 客户对所有角色可改（admin/income）；expense 不可改客户由 mode_guard / 工具白名单控制

        updatable = ["phone", "email", "id_card_number", "wechat_group_name", "address", "remarks"]
        updated = {}
        for field in updatable:
            val = kwargs.get(field)
            if val is not None:
                target_field = "id_card_number_encrypted" if field == "id_card_number" else field
                if field == "id_card_number" and val:
                    val = base64.b64encode(val.encode()).decode()
                setattr(customer, target_field, val)
                updated[field] = kwargs.get(field)

        if not updated:
            return json.dumps({"error": "没有需要更新的字段"}, ensure_ascii=False)

        try:
            self.db.commit()
            self.db.refresh(customer)

            # 审计日志
            try:
                from app.services.audit_service import AuditService
                AuditService.log(
                    self.db,
                    user_id=self.user.id,
                    action="update",
                    entity_type="customer",
                    entity_id=customer_id,
                    old_values=old_values,
                    new_values=updated,
                )
            except Exception as e:
                logger.warning("审计日志写入失败: entity=customer, action=update, error=%s", e)

            return json.dumps({
                "success": True,
                "customer": {
                    "id": customer.id,
                    "name": customer.name,
                    "phone": customer.phone,
                    "email": customer.email,
                    "wechat_group_name": customer.wechat_group_name,
                },
                "updated_fields": list(updated.keys()),
            }, ensure_ascii=False)
        except Exception as e:
            logger.exception("update_customer failed")
            return json.dumps({"error": f"更新客户失败: {str(e)}"}, ensure_ascii=False)

    def _get_receipt_image_path(self, explicit_path: Optional[str] = None) -> Optional[str]:
        """获取凭证图片路径，三级策略：
        1. LLM 主动传的路径（最佳路径，直接用）
        2. 同请求内 _pending_receipt_path 缓存（文件预分析 刚设置的）
        3. DB 查询兜底：当前会话最近一次 文件预分析 的 file_path
        """
        # 1. LLM 主动传了
        if explicit_path:
            self._pending_receipt_path = None
            return explicit_path
        # 2. 同请求内缓存
        if self._pending_receipt_path:
            path = self._pending_receipt_path
            self._pending_receipt_path = None
            return path
        # 3. DB 查询兜底
        if not self.session_id:
            return None
        from app.models.chat_history import ChatHistory
        record = (
            self.db.query(ChatHistory)
            .filter(
                ChatHistory.session_id == self.session_id,
                ChatHistory.user_id == self.user.id,
                ChatHistory.role == "tool",
                ChatHistory.intent_type == "文件预分析",
            )
            .order_by(ChatHistory.created_at.desc())
            .first()
        )
        if not record or not record.answer:
            return None
        try:
            result = json.loads(record.answer)
            if result.get("success") and result.get("file_path"):
                logger.info("DB兜底：从会话历史找到 文件预分析 file_path=%s", result["file_path"])
                return result["file_path"]
        except (json.JSONDecodeError, TypeError):
            pass
        return None

    def _ensure_file_in_receipt_dir(self, file_path: str) -> Optional[str]:
        """如果 file_path 是 agent_upload/{file_id} 格式，
        把文件从上传目录复制到凭证目录，返回新路径。
        否则原样返回。

        文件定位委托 file_utils.resolve_file_path —— 它是项目里
        唯一知道文件可能在哪些目录的函数（AGENT_FILE_DIR 持久化目录、
        TEMP_UPLOAD_DIR/{user_id} 用户隔离、TEMP_UPLOAD_DIR 旧全局），
        以后新增/调整存储目录只改它，不必同步本函数。
        """
        self._last_receipt_file_hash = None
        if not file_path:
            return None
        # 兼容 LLM 传裸 file_id（UUID）的情况：自动补全为 agent_upload/ 格式
        if not file_path.startswith("agent_upload/"):
            if "/" not in file_path and "." not in file_path and len(file_path) >= 20:
                logger.info("检测到裸file_id，自动补全为agent_upload/格式: %s", file_path)
                file_path = f"agent_upload/{file_path}"
            else:
                return file_path
        file_id = file_path[len("agent_upload/"):]
        temp_path = resolve_file_path(file_id, self.user.id)
        if not temp_path:
            logger.warning("凭证文件复制跳过: 文件不存在 file_id=%s, user=%s", file_id, self.user.id)
            return None
        try:
            with open(temp_path, "rb") as f:
                content = f.read()
            self._last_receipt_file_hash = calculate_file_hash(content)
            ext = guess_extension(content)
            year_month = datetime.now().strftime("%Y/%m")
            target_dir = Path(settings.RECEIPT_UPLOAD_DIR) / year_month
            target_dir.mkdir(parents=True, exist_ok=True)
            target_filename = f"{file_id}{ext}"
            target_path = target_dir / target_filename
            shutil.copy2(temp_path, str(target_path))
            new_path = str(Path(year_month) / target_filename)
            logger.info("凭证文件已复制到凭证目录: %s → %s", file_path, new_path)
            return new_path
        except Exception:
            logger.exception("凭证文件复制失败 file_path=%s", file_path)
            return None

    def create_contract(self, **kwargs) -> str:
        """为客户创建合同记录。合同编号自动生成。"""
        if not self._can_create_contract():
            return json.dumps({"error": "当前角色无权创建合同"}, ensure_ascii=False)

        customer_id = kwargs.get("customer_id")
        file_id = kwargs.get("file_id")
        contract_data_raw = kwargs.get("contract_data", {})

        if not customer_id:
            return json.dumps({"error": "缺少 customer_id"}, ensure_ascii=False)
        if not file_id:
            return json.dumps({"error": "缺少 file_id，无法关联原始文件"}, ensure_ascii=False)

        # 业务微信群名称：每笔业务必须关联一个业务群，是必填字段。
        # 合同文件原文里没有群名，AI 应在创建前向用户询问；
        # 此处为兜底，防止 AI 漏问/漏传导致空群名合同入库。
        wechat_group = kwargs.get("wechat_group")
        if not wechat_group or not str(wechat_group).strip():
            return json.dumps(
                {"error": "缺少 wechat_group（业务微信群名称）。每笔业务都必须关联业务群，请先向用户询问群名再创建合同"},
                ensure_ascii=False,
            )

        # ━━━ 数据来源策略：VL 缓存优先，预提取缓存次之，Agent 兜底 ━━━
        cache_data = self._get_cached_analysis(file_id, "contract")
        data_source = "unknown"

        if cache_data and isinstance(cache_data, dict):
            if cache_data.get("raw_text"):
                # 预提取缓存（快速文本提取路径）：原文作为 full_text，结构化字段由 Agent 传入
                merged = dict(contract_data_raw) if isinstance(contract_data_raw, dict) else {}
                merged["full_text"] = cache_data["raw_text"]
                data_source = "pre_extracted"
            else:
                # VL 结构化缓存：以缓存为基础，仅白名单字段可从 Agent 覆盖
                merged = dict(cache_data)
                AGENT_OVERRIDABLE = {"title", "business_type", "business_description"}
                for key in AGENT_OVERRIDABLE:
                    agent_val = kwargs.get(key) or (contract_data_raw.get(key) if isinstance(contract_data_raw, dict) else None)
                    if agent_val:
                        merged[key] = agent_val
                # payment_terms 始终用 VL 原始输出，不容 Agent 改写
                merged["payment_terms"] = cache_data.get("payment_terms", [])
                merged["full_text"] = cache_data.get("full_text", "")
                if isinstance(contract_data_raw, dict) and contract_data_raw.get("payment_terms"):
                    logger.warning(
                        "create_contract: Agent传了payment_terms已忽略，使用VL缓存 file_id=%s", file_id
                    )
                data_source = "cache"
        elif isinstance(contract_data_raw, dict) and contract_data_raw:
            # 缓存 miss，降级使用 Agent 传来的 contract_data（兼容旧行为）
            merged = dict(contract_data_raw)
            data_source = "agent_passed"
        else:
            # 全都没有，空数据
            merged = {}
            data_source = "empty"

        logger.info(
            "create_contract数据来源: file_id=%s source=%s keys=%s",
            file_id, data_source,
            list(merged.keys()) if isinstance(merged, dict) else "N/A",
        )

        # ━━━ 归一化 payment_terms（VL 也可能写出 installment_name / 缺 name）━━━
        normalize_payment_terms(merged)

        # 验证客户存在
        customer = self.db.query(Customer).filter(
            Customer.id == customer_id, Customer.is_deleted == False
        ).first()
        if not customer:
            return json.dumps({"error": f"客户不存在: {customer_id}"}, ensure_ascii=False)

        # 处理文件：路径解析委托 resolve_file_path（统一支持 AGENT_FILE_DIR / TEMP_UPLOAD_DIR）
        temp_file_path = resolve_file_path(file_id, self.user.id)
        file_hash = None
        original_file_path = f"agent_upload/{file_id}"

        if temp_file_path and os.path.exists(temp_file_path):
            with open(temp_file_path, "rb") as f:
                content = f.read()
            # 复用 _try_pre_analyze 计算的 hash，避免重复读取大文件
            file_hash = self._file_hash_cache.get(temp_file_path)
            if not file_hash:
                file_hash = calculate_file_hash(content)

            # 基于文件 hash 检测重复
            existing = self.db.query(Contract).filter(
                Contract.file_hash == file_hash,
                Contract.is_deleted == False,
            ).first()
            if existing:
                return json.dumps({
                    "success": False,
                    "error": f"该文件已创建过合同（编号: {existing.contract_number}, ID: {existing.id}）",
                    "existing_contract_id": existing.id,
                }, ensure_ascii=False)

            # 复制到正式合同目录
            contract_number = ContractService.generate_contract_number()
            year_month = datetime.now().strftime("%Y/%m")
            target_dir = Path(settings.CONTRACT_UPLOAD_DIR) / year_month
            target_dir.mkdir(parents=True, exist_ok=True)

            ext = guess_extension(content)
            target_filename = f"{contract_number}{ext}"
            target_path = target_dir / target_filename
            shutil.copy2(temp_file_path, str(target_path))

            original_file_path = str(Path(year_month) / target_filename)
        else:
            contract_number = ContractService.generate_contract_number()

        # ━━━ 构建合同字段：声明式映射，Agent 显式传入 > VL 缓存回退 ━━━
        # 原则：VL 已提取的数据不应因 Agent 漏传参数而丢失。
        # 新增 VL 字段时只需在 FIELD_MAP 加一行，契约工具会自动生效。
        from app.schemas.contract import ContractCreate

        def _parse_date(val):
            """安全解析日期，兼容 date 对象 / YYYY-MM-DD 字符串 / datetime 对象"""
            if val is None:
                return None
            if isinstance(val, date):
                return val
            if isinstance(val, str) and val.strip():
                try:
                    return date.fromisoformat(val.strip())
                except ValueError:
                    pass
            return None

        def _resolve(kwargs_key: str, merged_path: str, *, parser=None, default=None):
            """统一取值：kwargs[key] 优先，否则 merged 路径回退。parser 用于类型转换，对 default 也生效。"""
            val = kwargs.get(kwargs_key)
            if val is not None and val != "":
                return parser(val) if parser else val
            # 递归解析 merged 嵌套路径，如 "validity_period.start_date"
            parts = merged_path.split(".")
            node = merged
            for p in parts:
                if isinstance(node, dict):
                    node = node.get(p)
                else:
                    node = None
                    break
            if node is not None and node != "":
                return parser(node) if parser else node
            # default 也走 parser 保证类型一致（如 default=0 配 parser=_parse_date 会返回 None）
            return parser(default) if (parser and default is not None) else default

        # 嵌套路径需要在 merged 里先定位
        validity = merged.get("validity_period") if isinstance(merged.get("validity_period"), dict) else {}

        contract_fields = {
            "contract_number": contract_number,
            "customer_id": customer_id,
            "original_file_path": original_file_path,
            "file_hash": file_hash,
            "status": "active",
            # ── 以下字段：kwargs 优先，VL 缓存兜底 ──
            "title":               _resolve("title", "title"),
            "business_type":       BusinessType.normalize(_resolve("business_type", "business_type")),
            "business_description": _resolve("business_description", "business_description"),
            "currency":            _resolve("currency", "currency", default="CNY"),
            "total_amount":        Decimal(str(_resolve("total_amount", "total_amount", default=0))),
            "signed_date":         _resolve("signed_date", "signed_date", parser=_parse_date),
            "start_date":          _resolve("start_date", "start_date", parser=_parse_date)
                                   or _parse_date(validity.get("start_date")),
            "end_date":            _resolve("end_date", "end_date", parser=_parse_date)
                                   or _parse_date(validity.get("end_date")),
            "wechat_group":        _resolve("wechat_group", "wechat_group"),
        }
        # 过滤掉 None 的可选字段（让 schema 默认值生效）
        contract_fields = {k: v for k, v in contract_fields.items() if v is not None}

        try:
            contract_create = ContractCreate(**contract_fields)

            contract = ContractService.create_contract(
                db=self.db,
                contract_data=contract_create,
                sales_person_id=self.user.id,
            )

            # 写入 contract_data JSON（使用合并后的完整数据）
            contract.contract_data = {
                "source": "agent",
                "file_id": file_id,
                "data_source": data_source,
                **merged,
            }
            # 存储合同全文（用于知识库问答）
            if merged.get("full_text"):
                contract.contract_text = merged["full_text"]
            # 写入 VL 解析元数据
            if merged.get("confidence") is not None:
                try:
                    conf = float(merged["confidence"])
                    contract.confidence = round(conf, 4)
                    contract.needs_review = conf < 0.85
                except (TypeError, ValueError):
                    pass
            self.db.commit()
            self.db.refresh(contract)

            # 合同录入只生成付款计划（payment_terms），不再自动创建任何 payment 记录。
            # 付款记录只能通过合同卡片上的表单录入。
            # auto_payments 字段保留为空数组，仅为兼容已上线响应格式。
            logger.info("create_contract完成: contract_id=%d", contract.id)

            return json.dumps({
                "success": True,
                "contract": {
                    "id": contract.id,
                    "contract_number": contract.contract_number,
                    "customer_name": customer.name,
                    "customer_id": customer_id,
                    "title": contract.title,
                    "currency": contract.currency,
                    "total_amount": float(contract.total_amount),
                    "status": contract.status,
                    "confidence": float(contract.confidence) if contract.confidence else None,
                    "needs_review": contract.needs_review,
                    "wechat_group": contract.wechat_group,
                    "signed_date": str(contract.signed_date) if contract.signed_date else None,
                },
                "auto_payments": [],
                **({"zero_amount": True} if contract.total_amount == 0 else {}),
            }, ensure_ascii=False)
        except Exception as e:
            logger.exception("create_contract failed")
            return json.dumps({"error": f"创建合同失败: {str(e)}"}, ensure_ascii=False)

    def update_contract(self, **kwargs) -> str:
        """更新合同信息（如微信群、备注等）"""
        if not self._can_create_contract():
            return json.dumps({"error": "当前角色无权修改合同"}, ensure_ascii=False)

        contract_id = kwargs.get("contract_id")
        if not contract_id:
            return json.dumps({"error": "缺少 contract_id"}, ensure_ascii=False)

        contract = ContractService.get_contract(self.db, contract_id)
        if not contract:
            return json.dumps({"error": f"合同不存在：{contract_id}"}, ensure_ascii=False)
        if not self._can_access_contract(contract):
            return json.dumps({"error": "无权修改该合同"}, ensure_ascii=False)

        updatable_fields = ["wechat_group", "remarks", "title", "business_description"]
        updates = {}
        for field in updatable_fields:
            if field in kwargs and kwargs[field] is not None:
                updates[field] = kwargs[field]

        if not updates:
            self._document_context = None  # 消费上下文
            return json.dumps({"error": "没有需要更新的字段"}, ensure_ascii=False)

        try:
            from app.schemas.contract import ContractUpdate
            contract_update = ContractUpdate(**updates)
            old_values = {
                "wechat_group": contract.wechat_group,
                "remarks": contract.remarks,
                "title": contract.title,
                "business_description": contract.business_description,
            }
            updated = ContractService.update_contract(self.db, contract_id, contract_update, updated_by=self.user.id)
            if not updated:
                self._document_context = None  # 更新失败也消费上下文
                return json.dumps({"error": "更新失败"}, ensure_ascii=False)

            # 群名关联审计：标记来源，便于后续统计推断准确率
            # - 群聊识别上下文（document_context="general" 或 "group_chat"）→ business_type_infer
            # - 用户在对话中明确说"把这个群名关联到合同" → user_manual
            # - 其他情况下手动更新 → user_manual（保守兜底）
            audit_source = "user_manual"
            if "wechat_group" in updates and self._document_context in ("general", "group_chat"):
                audit_source = "business_type_infer"
            if "wechat_group" in updates:
                try:
                    from app.services.audit_service import AuditService
                    AuditService.log(
                        self.db,
                        user_id=self.user.id,
                        action="link_wechat_group",
                        entity_type="contract",
                        entity_id=contract_id,
                        old_values={"wechat_group": old_values.get("wechat_group")},
                        new_values={
                            "wechat_group": updates["wechat_group"],
                            "source": audit_source,
                        },
                    )
                except Exception:
                    logger.exception("update_contract: 群名关联审计写入失败")
            # 写操作完成（成功或失败）：显式消费 document_context，避免污染同会话后续轮次
            self._document_context = None

            return json.dumps({
                "success": True,
                "contract": self._contract_to_dict(updated),
                "audit_source": audit_source,
            }, ensure_ascii=False)
        except Exception as e:
            logger.exception("update_contract failed")
            self._document_context = None  # 异常路径也要消费上下文
            return json.dumps({"error": f"更新合同失败: {str(e)}"}, ensure_ascii=False)

    def update_payment(self, **kwargs) -> str:
        """更新付款记录的备注、凭证、付款方式等信息"""
        payment_id = kwargs.get("payment_id")
        if not payment_id:
            return json.dumps({"error": "缺少 payment_id"}, ensure_ascii=False)

        payment = self.db.query(Payment).filter(Payment.id == payment_id).first()
        if not payment:
            return json.dumps({"error": f"付款记录不存在：{payment_id}"}, ensure_ascii=False)

        # 按 type 权限检查
        if payment.type == "expense":
            if not self._can_view_expense():
                return json.dumps({"error": "当前角色无权更新支出记录"}, ensure_ascii=False)
        else:
            if not self._can_view_income():
                return json.dumps({"error": "当前角色无权更新收入记录"}, ensure_ascii=False)

        # 合同对所有角色可见，income 可更新任意合同的收入流水（类型隔离由 _can_view_income/_expense 守卫）

        # 可更新字段白名单
        updatable_fields = [
            "notes", "payment_method", "receipt_image_path", "receipt_data",
            "installment_name", "paid_date",
            "outstanding_amount", "outstanding_currency",  # 仅 income 编辑时支持
        ]
        updates = {f: kwargs[f] for f in updatable_fields if kwargs.get(f) is not None}

        # 凭证路径双保险：LLM 主动传 > 同请求缓存 > DB 查询兜底
        if "receipt_image_path" not in updates:
            fallback = self._get_receipt_image_path()
            if fallback:
                updates["receipt_image_path"] = fallback

        # paid_date 合理性校验：拒绝晚于今天的日期，避免 LLM 误传未来日期
        if "paid_date" in updates:
            try:
                paid_date_val = date.fromisoformat(updates["paid_date"])
                if paid_date_val > date.today():
                    return json.dumps({"error": f"付款日期不能晚于今天: {updates['paid_date']}"}, ensure_ascii=False)
            except (ValueError, TypeError):
                return json.dumps({"error": f"paid_date 格式错误，应为 YYYY-MM-DD: {updates['paid_date']}"}, ensure_ascii=False)

        # 凭证路径：从 TEMP 复制到凭证目录
        if "receipt_image_path" in updates:
            resolved = self._ensure_file_in_receipt_dir(updates["receipt_image_path"])
            if resolved is not None:
                updates["receipt_image_path"] = resolved
            else:
                # 文件不存在，移除这个 key，避免用 None 覆盖已有路径
                del updates["receipt_image_path"]
                logger.warning("update_payment: 凭证文件不存在，跳过 receipt_image_path 更新")

        if not updates:
            return json.dumps({"error": "没有需要更新的字段"}, ensure_ascii=False)

        try:
            from app.schemas.payment import PaymentUpdate
            payment_update = PaymentUpdate(**updates)
            updated = PaymentService.update_payment(self.db, payment_id, payment_update, updated_by=self.user.id)
            if not updated:
                return json.dumps({"error": "更新失败"}, ensure_ascii=False)

            result = self._payment_to_dict(updated)
            return json.dumps({"success": True, "payment": result}, ensure_ascii=False)
        except Exception as e:
            logger.exception("update_payment failed")
            return json.dumps({"error": f"更新付款失败: {str(e)}"}, ensure_ascii=False)

    def search_contract_text(self, **kwargs) -> str:
        """按关键词搜索所有合同的全文内容，返回匹配片段"""
        keyword = kwargs.get("keyword", "").strip()
        if not keyword:
            return json.dumps({"error": "缺少 keyword 参数"}, ensure_ascii=False)

        contract_id = kwargs.get("contract_id")

        query = self.db.query(Contract).filter(
            Contract.is_deleted == False,
            Contract.contract_text.isnot(None),
            Contract.contract_text != "",
        )

        if contract_id:
            query = query.filter(Contract.id == contract_id)

        # 合同对所有角色可见，不再按 sales_person_id 过滤全文搜索范围

        # ILIKE 模糊搜索
        query = query.filter(Contract.contract_text.ilike(f"%{_escape_ilike(keyword)}%"))
        contracts = query.limit(10).all()

        if not contracts:
            return json.dumps({
                "matches": [],
                "keyword": keyword,
            }, ensure_ascii=False)

        results = []
        for c in contracts:
            # 提取匹配片段（关键词前后各 80 字）
            text = c.contract_text or ""
            idx = text.lower().find(keyword.lower())
            if idx == -1:
                # fallback：可能是数据库 ILIKE 匹配了但 Python find 大小写不一致
                idx = 0
            start = max(0, idx - 80)
            end = min(len(text), idx + len(keyword) + 80)
            snippet = text[start:end]
            if start > 0:
                snippet = "…" + snippet
            if end < len(text):
                snippet = snippet + "…"

            results.append({
                "contract_id": c.id,
                "contract_number": c.contract_number,
                "customer_name": c.customer.name if c.customer else "未知",
                "business_type": c.business_type,
                "business_description": c.business_description,
                "snippet": snippet,
            })

        return json.dumps({
            "matches": results,
            "keyword": keyword,
        }, ensure_ascii=False)

    # ── 统计概览工具 ──

    def get_overview(self) -> str:
        """全局统计概览，用于回答'现在什么情况''有哪些数据'等开放式问题。
        数据范围：客户/合同对所有角色全部可见，仅按 payment.type 隔离收支视角：
        - admin：客户 + 合同 + 收入 + 支出
        - income：客户 + 合同 + 收入（不看支出）
        - expense：客户 + 合同 + 支出（不看收入）
        """
        from sqlalchemy import func

        # ── 客户范围：对所有角色可见 ──
        customer_query = self.db.query(Customer).filter(Customer.is_deleted == False)

        # ── 合同范围：对所有角色可见 ──
        contract_query = self.db.query(Contract).filter(Contract.is_deleted == False)

        customers_total = customer_query.count()
        contracts_total = contract_query.count()

        status_counts = (
            contract_query.with_entities(Contract.status, func.count(Contract.id))
            .group_by(Contract.status)
            .all()
        )
        by_status = {s: c for s, c in status_counts}

        # ── 最近客户 ──
        latest_customers = (
            customer_query.order_by(Customer.created_at.desc()).limit(5).all()
        )
        recent_customers = []
        for c in latest_customers:
            cc_query = self.db.query(Contract).filter(
                Contract.customer_id == c.id, Contract.is_deleted == False
            )
            recent_customers.append({
                "id": c.id,
                "name": c.name,
                "contract_count": cc_query.count(),
            })

        # ── 最近合同 ──
        latest_contracts = (
            contract_query.order_by(Contract.created_at.desc()).limit(5).all()
        )
        recent_contracts = [
            {
                "id": c.id,
                "contract_number": c.contract_number,
                "customer_name": c.customer.name if c.customer else None,
                "status": c.status,
                "total_amount": float(c.total_amount) if c.total_amount else None,
                "currency": c.currency,  # 关键：让 LLM 知道币种，避免默认按 ¥ 展示
            }
            for c in latest_contracts
        ]

        # ── 30天内到期合同 ──
        from datetime import timedelta
        target_date = date.today() + timedelta(days=30)
        expiring_count = contract_query.filter(
            Contract.status == "active",
            Contract.end_date <= target_date,
            Contract.end_date >= date.today(),
        ).count()

        # ── 收入/支出汇总（按币种分组，不折算合并） ──
        result = {
            "customers_total": customers_total,
            "contracts_total": contracts_total,
            "contracts_by_status": by_status,
            "expiring_contracts_30days": expiring_count,
            "recent_contracts": recent_contracts,
            "recent_customers": recent_customers,
            "scope": self.user.role,  # 让 LLM 知道当前数据范围
        }

        # 收入：admin/income 看全部收入，expense 不看收入
        if self.user.role != Role.EXPENSE:
            income_rows = self.db.query(
                Payment.currency,
                func.coalesce(func.sum(Payment.paid_amount), 0).label("total"),
            ).filter(
                Payment.is_deleted == False,
                Payment.type == "income",
                Payment.status == "paid",
            ).group_by(Payment.currency).all()

            income_by_currency = {"CNY": 0.0, "HKD": 0.0}
            for r in income_rows:
                if r.currency in income_by_currency:
                    income_by_currency[r.currency] = float(r.total)
            result["income_by_currency"] = income_by_currency

        # 支出：admin/expense 看全部支出，income 不看支出
        if self.user.role != Role.INCOME:
            expense_rows = self.db.query(
                Payment.currency,
                func.coalesce(func.sum(Payment.paid_amount), 0).label("total"),
            ).filter(
                Payment.is_deleted == False,
                Payment.type == "expense",
                Payment.status == "paid",
            ).group_by(Payment.currency).all()

            expense_by_currency = {"CNY": 0.0, "HKD": 0.0}
            for r in expense_rows:
                if r.currency in expense_by_currency:
                    expense_by_currency[r.currency] = float(r.total)
            result["expense_by_currency"] = expense_by_currency

        return json.dumps(result, ensure_ascii=False)

    # ── 文件分析工具 ──

    def execute(self, tool_name: str, arguments: dict) -> str:
        """统一执行入口（v1 版本，已被 ToolExecutorV2 重写）
        
        注意：此方法在 v2 主链路中不被调用，保留仅为向后兼容。
        v2 的 execute() 在 tools_v2.py 中，无模式守卫，仅角色权限控制。
        """
        handler = getattr(self, tool_name, None)
        if not handler:
            logger.warning("未知工具调用: %s", tool_name)
            return json.dumps({"error": f"未知工具: {tool_name}"}, ensure_ascii=False)

        args_preview = json.dumps(arguments, ensure_ascii=False, default=str)[:300]
        logger.info("工具调用: %s | mode=%s | 参数: %s", tool_name, self.mode, args_preview)

        try:
            result = handler(**arguments)
            logger.info("工具结果: %s → %s", tool_name, result[:200] if result else "empty")
            return result
        except Exception as e:
            logger.exception("工具执行失败: %s", tool_name)
            return json.dumps({"error": f"工具执行失败: {str(e)}"}, ensure_ascii=False)


# v1 TOOL_DEFINITIONS 已删除（被 tools_v2.py 的 TOOL_DEFINITIONS 替代）
# 工具执行器基类，被 ToolExecutorV2 继承复用
