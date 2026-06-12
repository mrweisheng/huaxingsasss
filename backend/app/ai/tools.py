"""
Agent 工具执行器
调用现有 Service 层实现业务操作
"""
import base64
import json
import os
import shutil
from uuid import uuid4
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Optional

from datetime import timedelta

import httpx
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
from app.services.customer_service import CustomerService
from app.services.payment_service import PaymentService
from app.utils.file_utils import calculate_file_hash, resolve_file_path, validate_file_id_in_dir


def _escape_ilike(keyword: str) -> str:
    """转义 ILIKE 通配符，防止 SQL 注入"""
    return keyword.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


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

    def _normalize_payment_terms(self, merged_data: dict) -> None:
        """归一化 payment_terms：installment_name→name, due_date→condition兜底, 缺name补序号。
        在最终合并数据上执行，覆盖 VL 输出和 Agent 传入两条路径。"""
        if not isinstance(merged_data, dict):
            return
        terms = merged_data.get("payment_terms")
        if not isinstance(terms, list):
            return
        normalized = []
        for idx, t in enumerate(terms, 1):
            if not isinstance(t, dict):
                normalized.append(t)
                continue
            nt = dict(t)
            if "name" not in nt and "installment_name" in nt:
                nt["name"] = nt.pop("installment_name")
            if not nt.get("name"):
                nt["name"] = f"第 {idx} 期"
            if not nt.get("condition") and nt.get("due_date"):
                nt["condition"] = str(nt["due_date"])
            normalized.append(nt)
        merged_data["payment_terms"] = normalized

    def _can_access_contract(self, contract: Contract) -> bool:
        if self.user.role == Role.ADMIN:
            return True
        if self.user.role == Role.EXPENSE:
            return True  # expense 可查看所有合同（用于关联支出）
        return contract.sales_person_id == self.user.id

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
            "remaining_amount": float(c.remaining_amount) if c.remaining_amount else 0,
            "total_amount_in_cny": float(c.total_amount_in_cny) if c.total_amount_in_cny else None,
            "paid_amount_in_cny": float(c.paid_amount_in_cny) if c.paid_amount_in_cny else 0,
            "total_expense": float(c.total_expense) if c.total_expense else 0,
            "total_expense_in_cny": float(c.total_expense_in_cny) if c.total_expense_in_cny else 0,
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
            "exchange_rate": float(p.exchange_rate) if p.exchange_rate else None,
            "amount_in_cny": float(p.amount_in_cny) if p.amount_in_cny else None,
            "paid_amount_in_cny": float(p.paid_amount_in_cny) if p.paid_amount_in_cny else None,
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
            "paid_amount_in_cny": float(p.paid_amount_in_cny) if p.paid_amount_in_cny else 0,
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

        # 权限过滤：参照 REST API customers.py 的逻辑
        if self.user.role == Role.EXPENSE:
            return json.dumps({"error": "当前角色无权查看客户"}, ensure_ascii=False)
        if self.user.role == Role.INCOME:
            query = query.filter(Customer.created_by == self.user.id)

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
        sales_person_id = None
        if self.user.role == Role.INCOME:
            sales_person_id = self.user.id

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

            total_paid_cny = sum(p.paid_amount_in_cny or 0 for p in income_pays if p.status == 'paid')
            total_expense_cny = sum(p.paid_amount_in_cny or 0 for p in expense_pays if p.status == 'paid')

            if type_filter != "expense":
                result["income"] = {
                    "payments": [self._payment_to_dict_lite(p) for p in income_pays],
                    "total_amount": float(contract.total_amount),
                    "paid_amount": float(contract.paid_amount),
                    "remaining_amount": float(contract.remaining_amount or 0),
                    "total_paid_in_cny": float(total_paid_cny),
                }
            if type_filter != "income":
                result["expense"] = {
                    "payments": [self._payment_to_dict_lite(p) for p in expense_pays],
                    "total_expense": float(contract.total_expense or 0),
                    "total_expense_in_cny": float(contract.total_expense_in_cny or 0),
                }
            if self._is_admin():
                result["profit_in_cny"] = float(total_paid_cny - total_expense_cny)
        except Exception:
            result["income"] = {"payments": []}
            result["expense"] = {"payments": []}

        return json.dumps(result, ensure_ascii=False)

    def get_customer_contracts(
        self,
        customer_id: int,
        business_type: Optional[str] = None,
    ) -> str:
        """获取某客户的合同列表。

        Args:
            customer_id: 客户 ID。
            business_type: 业务类型过滤（车辆买卖/两地牌过户/年检保险/其他）。
                传入时仅返回该类型合同。
        """
        sales_person_id = None
        if self.user.role == Role.INCOME:
            sales_person_id = self.user.id

        normalized = BusinessType.normalize(business_type) if business_type else None

        items, total = ContractService.get_contracts(
            self.db,
            customer_id=customer_id,
            sales_person_id=sales_person_id,
            business_type=normalized,
            per_page=50,
        )

        contracts = [self._contract_to_dict_lite(c) for c in items]
        return json.dumps({
            "contracts": contracts,
            "total": total,
            "filter": {"business_type": normalized},
        }, ensure_ascii=False)

    def query_payments(self, **kwargs) -> str:
        query = self.db.query(Payment).filter(Payment.is_deleted == False)

        if kwargs.get("contract_id"):
            query = query.filter(Payment.contract_id == kwargs["contract_id"])

        if kwargs.get("status"):
            query = query.filter(Payment.status == kwargs["status"])

        if kwargs.get("type"):
            query = query.filter(Payment.type == kwargs["type"])

        # 角色权限：income 只看收入+自己合同，expense 只看支出+自己创建的
        if self.user.role == Role.INCOME:
            query = query.filter(Payment.type == "income")
            query = query.join(Contract).filter(Contract.sales_person_id == self.user.id)
        elif self.user.role == Role.EXPENSE:
            query = query.filter(Payment.type == "expense")
            query = query.filter(Payment.created_by == self.user.id)

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

        # income 角色只能修改自己创建的客户
        if self.user.role == Role.INCOME and customer.created_by != self.user.id:
            return json.dumps({"error": "无权修改其他用户创建的客户"}, ensure_ascii=False)

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

    @staticmethod
    def _guess_extension(content: bytes) -> str:
        """通过文件头判断扩展名"""
        if content[:4] == b"%PDF":
            return ".pdf"
        if content[:3] == b"\xff\xd8\xff":
            return ".jpg"
        if content[:4] == b"\x89PNG":
            return ".png"
        if content[:4] == b"GIF8":
            return ".gif"
        if content[:4] == b"RIFF" and len(content) > 11 and content[8:12] == b"WEBP":
            return ".webp"
        # Office Open XML (ZIP-based): .docx / .xlsx / .pptx 都以 PK\x03\x04 开头
        if content[:4] == b"PK\x03\x04":
            try:
                text = content[:2000].decode("utf-8", errors="ignore")
                if "word/" in text:
                    return ".docx"
                if "xl/" in text:
                    return ".xlsx"
            except Exception:
                pass
            return ".docx"
        return ".bin"

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
            ext = self._guess_extension(content)
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
        self._normalize_payment_terms(merged)

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

            ext = self._guess_extension(content)
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
            # 付款记录的唯一来源是凭证（match_and_confirm_payment）或手动录入（create_payment_record）。
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
            updated = ContractService.update_contract(self.db, contract_id, contract_update)
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

    def create_payment(self, **kwargs) -> str:
        """创建付款记录（收入类型）。"""
        if not self._can_view_income():
            return json.dumps({"error": "当前角色无权创建收入记录"}, ensure_ascii=False)

        required = ["contract_id", "amount", "currency", "paid_date"]
        missing = [r for r in required if not kwargs.get(r)]
        if missing:
            return json.dumps({"error": f"缺少必填参数: {', '.join(missing)}"}, ensure_ascii=False)

        if self.user.role == Role.INCOME:
            contract = self.db.query(Contract).filter(Contract.id == kwargs["contract_id"]).first()
            if not contract or contract.sales_person_id != self.user.id:
                return json.dumps({"error": "无权操作该合同的付款"}, ensure_ascii=False)

        # 期数处理：LLM 指定 → 检查碰撞；未指定 → 自动计算
        installment_number = kwargs.get("installment_number")
        if installment_number:
            existing = self.db.query(Payment).filter(
                Payment.contract_id == kwargs["contract_id"],
                Payment.installment_number == installment_number,
                Payment.type == "income",
                Payment.is_deleted == False,
            ).first()
            if existing:
                return json.dumps({
                    "duplicate": True,
                    "existing_payment": self._payment_to_dict_lite(existing),
                }, ensure_ascii=False)
        else:
            installment_number = PaymentService.get_next_installment_number(
                self.db, kwargs["contract_id"], "income"
            )

        try:
            receipt_path = self._ensure_file_in_receipt_dir(
                self._get_receipt_image_path(kwargs.get("receipt_image_path"))
            )
            # 凭证去重：同合同下相同文件哈希的凭证不允许重复录入
            file_hash = self._last_receipt_file_hash
            if receipt_path and file_hash:
                existing = self.db.query(Payment).filter(
                    Payment.contract_id == kwargs["contract_id"],
                    Payment.receipt_file_hash == file_hash,
                ).first()
                if existing:
                    info = self._payment_to_dict_lite(existing)
                    return json.dumps({
                        "duplicate": True,
                        "existing_payment": info,
                    }, ensure_ascii=False)
            logger.info(
                "Agent创建付款: contract_id=%s, installment=%s, amount=%s %s, receipt=%s, notes=%s",
                kwargs["contract_id"], installment_number,
                kwargs["amount"], kwargs.get("currency"),
                receipt_path or "无",
                kwargs.get("notes", "无"),
            )
            payment = PaymentService.create_payment_with_exchange_rate(
                db=self.db,
                contract_id=kwargs["contract_id"],
                installment_number=installment_number,
                currency=kwargs["currency"],
                amount=Decimal(str(kwargs["amount"])),
                paid_date=date.fromisoformat(kwargs["paid_date"]),
                payment_method=kwargs.get("payment_method", "unknown"),
                receipt_image_path=receipt_path,
                notes=kwargs.get("notes"),
                created_by=self.user.id,
                type="income",
                installment_name=kwargs.get("installment_name"),
                receipt_data=kwargs.get("receipt_data"),
                receipt_file_hash=file_hash,
                description=kwargs.get("description"),
            )
            if payment.contract and payment.contract.customer:
                payment.contract.customer  # ensure loaded
            result = self._payment_to_dict(payment)
            result["contract_number"] = payment.contract.contract_number if payment.contract else None
            result["customer_name"] = payment.contract.customer.name if payment.contract and payment.contract.customer else None
            return json.dumps({"success": True, "payment": result}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"error": str(e)}, ensure_ascii=False)

    def create_expense(self, **kwargs) -> str:
        """为合同创建支出记录（向第三方付款）。"""
        if not self._can_view_expense():
            return json.dumps({"error": "当前角色无权创建支出记录"}, ensure_ascii=False)

        required = ["contract_id", "amount", "currency", "paid_date", "payee_name"]
        missing = [r for r in required if not kwargs.get(r)]
        if missing:
            return json.dumps({"error": f"缺少必填参数: {', '.join(missing)}"}, ensure_ascii=False)

        try:
            # 自动计算 installment_number
            installment_number = PaymentService.get_next_installment_number(
                self.db, kwargs["contract_id"], "expense"
            )
            expense_receipt_path = self._ensure_file_in_receipt_dir(
                self._get_receipt_image_path(kwargs.get("receipt_image_path"))
            )

            # 凭证去重：同合同下相同文件哈希的凭证不允许重复录入
            file_hash = self._last_receipt_file_hash
            if expense_receipt_path and file_hash:
                existing = self.db.query(Payment).filter(
                    Payment.contract_id == kwargs["contract_id"],
                    Payment.receipt_file_hash == file_hash,
                ).first()
                if existing:
                    info = self._payment_to_dict_lite(existing)
                    return json.dumps({
                        "duplicate": True,
                        "existing_payment": info,
                    }, ensure_ascii=False)

            payment = PaymentService.create_payment_with_exchange_rate(
                db=self.db,
                contract_id=kwargs["contract_id"],
                installment_number=installment_number,
                currency=kwargs["currency"],
                amount=Decimal(str(kwargs["amount"])),
                paid_date=date.fromisoformat(kwargs["paid_date"]),
                payment_method=kwargs.get("payment_method", "unknown"),
                receipt_image_path=expense_receipt_path,
                notes=kwargs.get("notes"),
                created_by=self.user.id,
                type="expense",
                payee_name=kwargs["payee_name"],
                installment_name=kwargs.get("installment_name"),
                receipt_data=kwargs.get("receipt_data"),
                receipt_file_hash=file_hash,
                description=kwargs.get("description"),
            )
            result = self._payment_to_dict(payment)
            result["contract_number"] = payment.contract.contract_number if payment.contract else None
            return json.dumps({"success": True, "payment": result}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"error": str(e)}, ensure_ascii=False)

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

        # income 角色校验合同所有权
        if self.user.role == Role.INCOME and payment.contract and payment.contract.sales_person_id != self.user.id:
            return json.dumps({"error": "无权操作该合同的付款"}, ensure_ascii=False)

        # 可更新字段白名单
        updatable_fields = ["notes", "payment_method", "receipt_image_path", "receipt_data", "installment_name", "paid_date"]
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
            updated = PaymentService.update_payment(self.db, payment_id, payment_update)
            if not updated:
                return json.dumps({"error": "更新失败"}, ensure_ascii=False)

            result = self._payment_to_dict(updated)
            return json.dumps({"success": True, "payment": result}, ensure_ascii=False)
        except Exception as e:
            logger.exception("update_payment failed")
            return json.dumps({"error": f"更新付款失败: {str(e)}"}, ensure_ascii=False)

    def match_receipt(self, **kwargs) -> str:
        receipt_data = kwargs.get("receipt_data")
        file_id = kwargs.get("file_id")

        # 优先从缓存获取凭证分析结果
        if not receipt_data or not isinstance(receipt_data, dict) or not receipt_data:
            if file_id:
                cached = self._get_cached_analysis(file_id, "receipt")
                if cached:
                    receipt_data = cached
                    logger.info("match_receipt 使用缓存凭证数据: file_id=%s", file_id)

        if not receipt_data or not isinstance(receipt_data, dict):
            return json.dumps({"error": "缺少凭证数据"}, ensure_ascii=False)

        payer_name = receipt_data.get("payer_name", "")
        receipt_amount = None
        try:
            receipt_amount = float(receipt_data.get("amount", 0))
        except (TypeError, ValueError):
            pass
        receipt_currency = receipt_data.get("currency", "")

        customer_name_hint = kwargs.get("customer_name", "").strip()

        candidates = []

        if payer_name or customer_name_hint:
            search_name = customer_name_hint or payer_name
            variants = search_variants(search_name)
            escaped = [_escape_ilike(v) for v in variants]
            customers = self.db.query(Customer).filter(
                Customer.is_deleted == False,
                or_(*[Customer.name.ilike(f"%{v}%") for v in escaped]),
            ).limit(5).all()

            for customer in customers:
                contracts = self.db.query(Contract).filter(
                    Contract.customer_id == customer.id,
                    Contract.is_deleted == False,
                ).all()
                for contract in contracts:
                    if not self._can_access_contract(contract):
                        continue
                    pending_payments = self.db.query(Payment).filter(
                        Payment.contract_id == contract.id,
                        Payment.type == "income",
                        Payment.status == "pending",
                        Payment.is_deleted == False,
                    ).order_by(Payment.installment_number).all()

                    for p in pending_payments:
                        score = 0
                        match_reasons = []
                        if customer_name_hint:
                            score += 30
                            match_reasons.append("客户名指定")
                        else:
                            score += 20
                            match_reasons.append("客户名匹配")
                        if receipt_amount and p.amount:
                            diff = abs(float(p.amount) - receipt_amount)
                            if diff < 1:
                                score += 50
                                match_reasons.append("金额完全匹配")
                            elif diff / max(float(p.amount), receipt_amount) < 0.05:
                                score += 30
                                match_reasons.append("金额近似匹配")
                        if receipt_currency and p.currency == receipt_currency:
                            score += 10
                            match_reasons.append("币种匹配")

                        candidates.append({
                            "payment_id": p.id,
                            "contract_id": contract.id,
                            "contract_number": contract.contract_number,
                            "customer_name": customer.name,
                            "business_type": contract.business_type,
                            "business_description": contract.business_description,
                            "installment_number": p.installment_number,
                            "installment_name": p.installment_name,
                            "amount": float(p.amount) if p.amount else 0,
                            "currency": p.currency,
                            "status": p.status,
                            "paid_date": str(p.paid_date) if p.paid_date else None,
                            "score": score,
                            "match_reason": "、".join(match_reasons),
                        })

        if not candidates and receipt_amount:
            pending_query = self.db.query(Payment).filter(
                Payment.status == "pending",
                Payment.type == "income",
                Payment.is_deleted == False,
            )
            if self.user.role == Role.INCOME:
                pending_query = pending_query.join(Contract).filter(
                    Contract.sales_person_id == self.user.id
                )
            pending_payments = pending_query.all()

            for p in pending_payments:
                if not p.amount:
                    continue
                diff = abs(float(p.amount) - receipt_amount)
                if diff < 1 or diff / max(float(p.amount), receipt_amount) < 0.05:
                    contract = p.contract
                    if not contract:
                        continue
                    if not self._can_access_contract(contract):
                        continue
                    customer = contract.customer
                    score = 40
                    match_reasons = ["金额匹配"]
                    if receipt_currency and p.currency == receipt_currency:
                        score += 10
                        match_reasons.append("币种匹配")

                    candidates.append({
                        "payment_id": p.id,
                        "contract_id": contract.id,
                        "contract_number": contract.contract_number,
                        "customer_name": customer.name if customer else "未知",
                        "business_type": contract.business_type,
                        "business_description": contract.business_description,
                        "installment_number": p.installment_number,
                        "installment_name": p.installment_name,
                        "amount": float(p.amount) if p.amount else 0,
                        "currency": p.currency,
                        "status": p.status,
                        "paid_date": str(p.paid_date) if p.paid_date else None,
                        "score": score,
                        "match_reason": "、".join(match_reasons),
                    })

        candidates.sort(key=lambda x: x["score"], reverse=True)
        candidates = candidates[:5]

        if not candidates:
            return json.dumps({
                "matches": [],
            }, ensure_ascii=False)

        return json.dumps({
            "matches": candidates,
        }, ensure_ascii=False)

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

        # 角色权限：income 只看自己合同的全文
        if self.user.role == Role.INCOME:
            query = query.filter(Contract.sales_person_id == self.user.id)

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

    def ask_contract(self, **kwargs) -> str:
        """检索合同全文内容，返回给 AI 用于回答用户关于合同条款的问题"""
        contract_id = kwargs.get("contract_id")
        question = kwargs.get("question", "").strip()

        if not contract_id:
            return json.dumps({"error": "缺少 contract_id 参数"}, ensure_ascii=False)
        if not question:
            return json.dumps({"error": "缺少 question 参数"}, ensure_ascii=False)

        contract = self.db.query(Contract).filter(
            Contract.id == contract_id,
            Contract.is_deleted == False,
        ).first()

        if not contract:
            return json.dumps({"error": f"合同不存在：{contract_id}"}, ensure_ascii=False)

        if not self._can_access_contract(contract):
            return json.dumps({"error": "无权访问该合同"}, ensure_ascii=False)

        if not contract.contract_text:
            return json.dumps({
                "error": "该合同尚未提取全文内容",
                "contract_number": contract.contract_number,
                "customer_name": contract.customer.name if contract.customer else "未知",
            }, ensure_ascii=False)

        text = contract.contract_text
        if len(text) > 20000:
            text = text[:20000] + "\n…[合同文本过长，已截断]"

        return json.dumps({
            "success": True,
            "contract_id": contract.id,
            "contract_number": contract.contract_number,
            "customer_name": contract.customer.name if contract.customer else "未知",
            "business_type": contract.business_type,
            "signed_date": str(contract.signed_date) if contract.signed_date else None,
            "contract_text": text,
            "user_question": question,
        }, ensure_ascii=False)

    def get_expense_summary(self, **kwargs) -> str:
        """查看支出汇总，按合同或收款方维度聚合（按币种分组，不跨币种合并）"""
        if not self._can_view_expense():
            return json.dumps({"error": "当前角色无权查看支出汇总"}, ensure_ascii=False)

        query = self.db.query(Payment).filter(
            Payment.is_deleted == False,
            Payment.type == "expense",
        )

        if self.user.role == Role.EXPENSE:
            query = query.filter(Payment.created_by == self.user.id)

        if kwargs.get("contract_id"):
            query = query.filter(Payment.contract_id == kwargs["contract_id"])

        if kwargs.get("payee_name"):
            query = query.filter(Payment.payee_name.ilike(f"%{_escape_ilike(kwargs['payee_name'])}%"))

        payments = query.all()

        # 按原始币种分组：每一笔支出报给 LLM 时都是它原本的币种和金额
        total_by_currency = {"CNY": 0.0, "HKD": 0.0}
        for p in payments:
            cur = p.currency if p.currency in ("CNY", "HKD") else "CNY"
            total_by_currency[cur] += float(p.paid_amount or 0)

        group_by = kwargs.get("group_by", "contract")
        groups = {}
        for p in payments:
            if group_by == "payee":
                key = p.payee_name or "未知"
            else:
                key = str(p.contract_id)

            cur = p.currency if p.currency in ("CNY", "HKD") else "CNY"

            if key not in groups:
                groups[key] = {
                    "by_currency": {"CNY": 0.0, "HKD": 0.0},
                    "count": 0,
                }
                if group_by == "payee":
                    groups[key]["payee_name"] = p.payee_name or "未知"
                else:
                    groups[key]["contract_id"] = p.contract_id
                    groups[key]["contract_number"] = p.contract.contract_number if p.contract else None
                    groups[key]["contract_currency"] = p.contract.currency if p.contract else None

            groups[key]["by_currency"][cur] += float(p.paid_amount or 0)
            groups[key]["count"] += 1

        return json.dumps({
            "total_by_currency": total_by_currency,
            "expense_count": len(payments),
            "groups": list(groups.values()),
        }, ensure_ascii=False)

    # ── 分析工具 ──

    def get_payment_summary(self, **kwargs) -> str:
        query = self.db.query(Payment).filter(Payment.is_deleted == False)

        # 角色权限：income 只看收入，expense 只看支出
        if self.user.role == Role.INCOME:
            query = query.filter(Payment.type == "income")
        elif self.user.role == Role.EXPENSE:
            query = query.filter(Payment.type == "expense")
        elif kwargs.get("type"):
            query = query.filter(Payment.type == kwargs["type"])

        need_contract_join = self.user.role == Role.INCOME or kwargs.get("customer_name")
        if need_contract_join:
            query = query.join(Contract)
            if self.user.role == Role.INCOME:
                query = query.filter(Contract.sales_person_id == self.user.id)
            if kwargs.get("customer_name"):
                query = query.join(Customer).filter(
                    Customer.name.ilike(f"%{_escape_ilike(kwargs['customer_name'])}%")
                )

        if kwargs.get("date_from"):
            try:
                query = query.filter(Payment.paid_date >= date.fromisoformat(kwargs["date_from"]))
            except ValueError:
                pass
        if kwargs.get("date_to"):
            try:
                query = query.filter(Payment.paid_date <= date.fromisoformat(kwargs["date_to"]))
            except ValueError:
                pass

        payments = query.all()

        # 按原始币种分组：每笔付款的币种和金额都是它原本的，不折算后混合
        total_paid_by_currency = {"CNY": 0.0, "HKD": 0.0}
        total_pending_by_currency = {"CNY": 0.0, "HKD": 0.0}

        for p in payments:
            cur = p.currency if p.currency in ("CNY", "HKD") else "CNY"
            if p.status == "paid":
                total_paid_by_currency[cur] += float(p.paid_amount or 0)
            elif p.status == "pending":
                total_pending_by_currency[cur] += float(p.amount or 0)

        summary = {
            "total_paid_by_currency": total_paid_by_currency,
            "total_pending_by_currency": total_pending_by_currency,
            "payment_count": len(payments),
        }

        group_by = kwargs.get("group_by")
        if group_by == "contract":
            groups = {}
            for p in payments:
                cid = p.contract_id
                cur = p.currency if p.currency in ("CNY", "HKD") else "CNY"
                if cid not in groups:
                    groups[cid] = {
                        "contract_id": cid,
                        "contract_number": p.contract.contract_number if p.contract else None,
                        "contract_currency": p.contract.currency if p.contract else None,  # 合同主币种
                        "by_currency": {  # 按付款原始币种分组
                            "CNY": {"paid": 0.0, "pending": 0.0},
                            "HKD": {"paid": 0.0, "pending": 0.0},
                        },
                    }
                if p.status == "paid":
                    groups[cid]["by_currency"][cur]["paid"] += float(p.paid_amount or 0)
                elif p.status == "pending":
                    groups[cid]["by_currency"][cur]["pending"] += float(p.amount or 0)
            summary["groups"] = list(groups.values())
        elif group_by == "customer":
            groups = {}
            for p in payments:
                customer_name = p.contract.customer.name if p.contract and p.contract.customer else "未知"
                cur = p.currency if p.currency in ("CNY", "HKD") else "CNY"
                if customer_name not in groups:
                    groups[customer_name] = {
                        "customer_name": customer_name,
                        "by_currency": {
                            "CNY": {"paid": 0.0, "pending": 0.0},
                            "HKD": {"paid": 0.0, "pending": 0.0},
                        },
                        "contract_count": 0,
                    }
                if p.status == "paid":
                    groups[customer_name]["by_currency"][cur]["paid"] += float(p.paid_amount or 0)
                elif p.status == "pending":
                    groups[customer_name]["by_currency"][cur]["pending"] += float(p.amount or 0)
            for p in payments:
                customer_name = p.contract.customer.name if p.contract and p.contract.customer else "未知"
                if customer_name in groups:
                    groups[customer_name]["contract_count"] = len(set(
                        pp.contract_id for pp in payments
                        if pp.contract and pp.contract.customer and pp.contract.customer.name == customer_name
                    ))
            summary["groups"] = list(groups.values())

        return json.dumps(summary, ensure_ascii=False)

    def get_expiring_contracts(self, **kwargs) -> str:
        within_days = kwargs.get("within_days", 30)
        target_date = date.today() + timedelta(days=within_days)
        status = kwargs.get("status", "active")

        query = self.db.query(Contract).filter(
            Contract.is_deleted == False,
            Contract.end_date <= target_date,
            Contract.end_date >= date.today(),
        )

        if status:
            query = query.filter(Contract.status == status)

        if self.user.role == Role.INCOME:
            query = query.filter(Contract.sales_person_id == self.user.id)

        contracts = query.order_by(Contract.end_date).all()
        results = []
        for c in contracts:
            results.append({
                **self._contract_to_dict_lite(c),
                "days_until_expiry": (c.end_date - date.today()).days if c.end_date else None,
            })

        return json.dumps({"contracts": results, "total": len(results)}, ensure_ascii=False)

    # ── 统计概览工具 ──

    def get_overview(self) -> str:
        """全局统计概览，用于回答'现在什么情况''有哪些数据'等开放式问题。
        按角色隔离数据范围：
        - admin：全部数据
        - income：仅自己创建的客户 + 自己名下的合同 + 这些合同的收入
        - expense：所有合同（用于关联支出）+ 自己创建的支出；无客户视角
        """
        from sqlalchemy import func

        # ── 客户范围 ──
        customer_query = self.db.query(Customer).filter(Customer.is_deleted == False)
        if self.user.role == Role.INCOME:
            customer_query = customer_query.filter(Customer.created_by == self.user.id)
        # expense 不展示客户列表（参照 search_customers 的硬隔离）
        show_customers = self.user.role != Role.EXPENSE

        # ── 合同范围 ──
        contract_query = self.db.query(Contract).filter(Contract.is_deleted == False)
        if self.user.role == Role.INCOME:
            contract_query = contract_query.filter(Contract.sales_person_id == self.user.id)
        # admin/expense 看全部合同

        customers_total = customer_query.count() if show_customers else 0
        contracts_total = contract_query.count()

        status_counts = (
            contract_query.with_entities(Contract.status, func.count(Contract.id))
            .group_by(Contract.status)
            .all()
        )
        by_status = {s: c for s, c in status_counts}

        # ── 最近客户 ──
        recent_customers = []
        if show_customers:
            latest_customers = (
                customer_query.order_by(Customer.created_at.desc()).limit(5).all()
            )
            # 客户的合同数也要按角色过滤
            for c in latest_customers:
                cc_query = self.db.query(Contract).filter(
                    Contract.customer_id == c.id, Contract.is_deleted == False
                )
                if self.user.role == Role.INCOME:
                    cc_query = cc_query.filter(Contract.sales_person_id == self.user.id)
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
            "scope": self.user.role,  # 让 LLM 知道当前数据范围
        }
        if show_customers:
            result["recent_customers"] = recent_customers

        # 收入：admin 看全部，income 只看自己合同的，expense 不看
        if self.user.role != Role.EXPENSE:
            income_rows = self.db.query(
                Payment.currency,
                func.coalesce(func.sum(Payment.paid_amount), 0).label("total"),
            ).filter(
                Payment.is_deleted == False,
                Payment.type == "income",
                Payment.status == "paid",
            )
            if self.user.role == Role.INCOME:
                income_rows = income_rows.join(Contract).filter(
                    Contract.sales_person_id == self.user.id
                )
            income_rows = income_rows.group_by(Payment.currency).all()

            income_by_currency = {"CNY": 0.0, "HKD": 0.0}
            for r in income_rows:
                if r.currency in income_by_currency:
                    income_by_currency[r.currency] = float(r.total)
            result["income_by_currency"] = income_by_currency

        # 支出：admin 看全部，expense 只看自己创建的，income 不看
        if self.user.role != Role.INCOME:
            expense_rows = self.db.query(
                Payment.currency,
                func.coalesce(func.sum(Payment.paid_amount), 0).label("total"),
            ).filter(
                Payment.is_deleted == False,
                Payment.type == "expense",
                Payment.status == "paid",
            )
            if self.user.role == Role.EXPENSE:
                expense_rows = expense_rows.filter(Payment.created_by == self.user.id)
            expense_rows = expense_rows.group_by(Payment.currency).all()

            expense_by_currency = {"CNY": 0.0, "HKD": 0.0}
            for r in expense_rows:
                if r.currency in expense_by_currency:
                    expense_by_currency[r.currency] = float(r.total)
            result["expense_by_currency"] = expense_by_currency

        return json.dumps(result, ensure_ascii=False)

    # ── 文件分析工具 ──

    _MODE_ALLOWED_TOOLS = {
        "receipt_income": {
            "create_payment", "update_payment",
            "get_contract_detail", "query_payments",
        },
        "receipt_expense": {
            "create_expense", "update_payment",
            "get_contract_detail", "query_payments",
        },
    }

    def _check_mode_guard(self, tool_name: str) -> Optional[str]:
        """模式级工具白名单。非 chat 模式只能用白名单内的工具。
        返回 None 放行，返回 JSON 字符串拦截。"""
        if self.mode == "chat" or self.mode is None:
            return None
        allowed = self._MODE_ALLOWED_TOOLS.get(self.mode, set())
        if tool_name in allowed:
            return None
        return json.dumps({
            "error": f"当前模式下不可使用 {tool_name}，请联系管理员或切换到聊天助手模式",
        })

    # 文档类型 → 禁止的工具集合
    # receipt：上传凭证时，禁止创建合同/客户（凭证不能触发合同录入）
    #         凭证录入已迁移到合同卡片，禁止所有凭证写入操作
    # general：上传非合同图片时，禁止创建新合同（应通过 update_contract 关联已有合同）
    _DOCUMENT_BLOCKED_TOOLS = {
        "receipt": {
            "create_contract", "create_customer", "create_expense", "update_contract",
            "create_payment", "update_payment", "match_receipt",  # 凭证写入已迁移到卡片
        },
        "general": {"create_contract", "create_customer", "create_payment", "create_expense", "update_payment"},
        "group_chat": {"create_contract", "create_customer", "create_payment", "create_expense", "update_payment"},
    }

    def _check_document_guard(self, tool_name: str) -> Optional[str]:
        """文档上下文守卫。返回 None 放行，返回 JSON 字符串拦截。
        仅在「命中拦截」时一次性清空上下文。未命中的工具（如 general→get_customer_contracts
        或 general→update_contract）放行并保留上下文，让后续 update_contract 能识别
        「群聊识别推断」来源。execute 入口负责在写操作完成后消费上下文。
        receipt_income / receipt_expense 模式跳过文档守卫（由模式白名单控制）。"""
        if self.mode in ("receipt_income", "receipt_expense"):
            return None
        if self._document_context is None:
            return None
        context = self._document_context
        blocked = self._DOCUMENT_BLOCKED_TOOLS.get(context)
        if not blocked or tool_name not in blocked:
            return None
        self._document_context = None  # 命中拦截时一次性消费
        label = {"receipt": "付款凭证", "general": "非合同类文件", "group_chat": "群聊截图"}.get(
            context, context
        )
        hint = {
            "receipt": "凭证录入已迁移到合同列表卡片的「收」「支」按钮。请引导用户在合同列表找到对应合同，点击卡片上的按钮进行凭证录入。如需查询付款信息，仍可使用 query_payments / get_contract_detail。",
            "general": "此类文件应通过 update_contract 关联已有合同（仅修改微信群/备注等元信息），不能用于付款操作。如需创建新合同或记录付款，请让用户上传合同/凭证文件。",
            "group_chat": "群聊截图应通过 update_contract 关联已有合同（仅修改微信群/备注等元信息），不能用于付款操作。如需创建新合同或记录付款，请让用户上传合同/凭证文件。",
        }.get(context, "")
        return json.dumps({
            "error": f"当前文件为「{label}」，不允许执行「{tool_name}」。{hint}",
            "blocked_tool": tool_name,
            "document_context": context,
        }, ensure_ascii=False)

    def execute(self, tool_name: str, arguments: dict) -> str:
        """统一执行入口

        注意：set_pending_plan 不在此入口处理（见各子图 execute_tool_node 内联分支），
        原因：它是纯 state 写入工具，不调 Service，且需要绕过 _check_mode_guard
        （凭证模式下 set_pending_plan 不在 _MODE_ALLOWED_TOOLS 白名单中）。
        """
        handler = getattr(self, tool_name, None)
        if not handler:
            logger.warning("未知工具调用: %s", tool_name)
            return json.dumps({"error": f"未知工具: {tool_name}"}, ensure_ascii=False)

        args_preview = json.dumps(arguments, ensure_ascii=False, default=str)[:300]
        logger.info("工具调用: %s | mode=%s | 参数: %s", tool_name, self.mode, args_preview)

        # 模式级白名单检查（优先于文档守卫）
        mode_blocked = self._check_mode_guard(tool_name)
        if mode_blocked:
            logger.warning("模式守卫拦截: tool=%s, mode=%s", tool_name, self.mode)
            return mode_blocked

        # 文档上下文守卫：文件预分析 设置的 document_context 按以下规则处理：
        # - 工具命中封锁列表 → 拦截并一次性消费上下文
        # - 工具放行 → 保留上下文，由后续写操作工具（如 update_contract）结束后显式清空
        blocked = self._check_document_guard(tool_name)
        if blocked:
            logger.warning("文档上下文守卫拦截: tool=%s", tool_name)
            return blocked

        try:
            result = handler(**arguments)
            logger.info("工具结果: %s → %s", tool_name, result[:200] if result else "empty")
            # 写操作成功后由各工具自行决定是否清空 document_context（保持显式可控）
            return result
        except Exception as e:
            logger.exception("❌ 工具执行失败: %s", tool_name)
            return json.dumps({"error": f"工具执行失败: {str(e)}"}, ensure_ascii=False)


# OpenAI function calling 格式的工具定义
TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "get_overview",
            "description": "获取系统全局统计概览：客户总数、合同总数（按状态分布）、即将到期合同数、收支汇总，以及最近客户和合同样例。用于回答'现在什么情况''有哪些数据''系统里有什么'等开放式问题。不要传任何参数。",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_customers",
            "description": "搜索客户。不传任何参数时返回全局统计+最近10个客户样例（不是全量），引导用户精确查找；传 name/phone/wechat_group 则按条件模糊匹配（自动兼容繁简体）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "客户姓名（支持模糊匹配）"},
                    "phone": {"type": "string", "description": "电话号码"},
                    "wechat_group": {"type": "string", "description": "微信群名称"},
                    "limit": {"type": "integer", "description": "最大返回数量，默认10", "default": 10},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_customer",
            "description": "创建客户记录。如果同名+同电话/邮箱的客户已存在，会返回已有客户（不会重复创建）。从合同文件提取到客户信息后应调用此工具。返回包含 customer.id 用于后续创建合同。",
            "parameters": {
                "type": "object",
                "required": ["name"],
                "properties": {
                    "name": {"type": "string", "description": "客户姓名（必填）"},
                    "phone": {"type": "string", "description": "联系电话（phone和email至少填一个）"},
                    "email": {"type": "string", "description": "联系邮箱（phone和email至少填一个）"},
                    "contact_person": {"type": "string", "description": "联系人"},
                    "id_card_number": {"type": "string", "description": "证件信息（合同/证件原文里出现的整段字符串，原样照抄。可能含证件名称+号码，也可能只有号码。不要拆分类型和号码两个字段）"},
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
            "description": "更新已有客户信息。当从合同文件中提取到客户电话、证件号等新信息时，用此工具补充到已有客户记录中。",
            "parameters": {
                "type": "object",
                "required": ["customer_id"],
                "properties": {
                    "customer_id": {"type": "integer", "description": "客户ID"},
                    "phone": {"type": "string", "description": "联系电话"},
                    "email": {"type": "string", "description": "联系邮箱"},
                    "id_card_number": {"type": "string", "description": "证件信息（合同/证件原文里出现的整段字符串，原样照抄。例：港澳居民来往内地通行证 F420825(7)）"},
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
            "name": "search_contracts",
            "description": "搜索合同。不传任何参数时返回全局统计+最近10个合同样例（不是全量），引导用户精确查找；传 contract_number/customer_name/status/keyword 则按条件搜索。",
            "parameters": {
                "type": "object",
                "properties": {
                    "contract_number": {"type": "string", "description": "合同编号"},
                    "customer_name": {"type": "string", "description": "客户姓名（模糊匹配）"},
                    "status": {
                        "type": "string",
                        "enum": ["active", "completed"],
                        "description": "合同状态筛选",
                    },
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
            "description": "获取合同完整详情，包含所有付款记录和付款进度。用于用户询问某个具体合同时。",
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
            "name": "get_customer_contracts",
            "description": (
                "获取某客户的合同列表及付款状态汇总。"
                "支持按业务类型（business_type）过滤。"
                "业务类型取值：车辆买卖 / 两地牌过户 / 年检保险 / 其他。"
            ),
            "parameters": {
                "type": "object",
                "required": ["customer_id"],
                "properties": {
                    "customer_id": {"type": "integer", "description": "客户ID"},
                    "business_type": {
                        "type": "string",
                        "enum": [
                            "车辆买卖",
                            "两地牌过户",
                            "年检保险",
                            "其他",
                        ],
                        "description": (
                            "业务类型过滤。不传则返回全量。"
                        ),
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_payments",
            "description": "按合同ID、类型或状态查询付款记录。income角色只能查看收入，expense角色只能查看支出。",
            "parameters": {
                "type": "object",
                "properties": {
                    "contract_id": {"type": "integer", "description": "按合同ID筛选"},
                    "type": {
                        "type": "string",
                        "enum": ["income", "expense"],
                        "description": "付款类型筛选：income（收入）或 expense（支出）",
                    },
                    "status": {
                        "type": "string",
                        "enum": ["pending", "paid"],
                        "description": "付款状态筛选",
                    },
                    "page": {"type": "integer", "default": 1},
                    "per_page": {"type": "integer", "default": 20},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_contract",
            "description": "为客户创建合同记录。需要先通过 create_customer 或 search_customers 获取 customer_id。合同编号自动生成。如果同一文件已创建过合同会返回已有记录。系统会自动使用之前 文件预分析 的分析结果，并自动根据付款条款创建对应的付款记录。",
            "parameters": {
                "type": "object",
                "required": ["customer_id", "file_id"],
                "properties": {
                    "customer_id": {"type": "integer", "description": "客户ID（通过 create_customer 或 search_customers 获取）"},
                    "file_id": {"type": "string", "description": "上传文件的ID（聊天上传时返回的 file_id）。系统会自动使用之前 文件预分析 对该文件的分析结果。"},
                    "contract_data": {"type": "object", "description": "【通常无需传递】合同提取数据。系统自动使用分析结果。仅当需覆盖特定字段（如标题修正）时传入。"},
                    "title": {"type": "string", "description": "合同标题（如：购车合同、两地牌办理合同）"},
                    "total_amount": {"type": "number", "description": "合同总金额"},
                    "currency": {"type": "string", "enum": ["CNY", "HKD"], "description": "合同币种。从合同原文提取，如 HK$/港币=HKD，¥/人民币=CNY。不清楚时询问用户确认。"},
                    "signed_date": {"type": "string", "description": "签订日期（YYYY-MM-DD）"},
                    "business_type": {"type": "string", "enum": ["车辆买卖", "两地牌过户", "年检保险", "其他"], "description": "业务大类：车辆买卖（买车卖车）、两地牌过户（办理中港车牌过户）、年检保险、其他"},
                    "business_description": {"type": "string", "description": "极简业务描述，只说做了什么业务（买什么车/办什么牌/哪个口岸），不要包含金额和付款条件。如：购买现牌 粤Z7N80港（深圳湾口岸）"},
                    "wechat_group": {"type": "string", "description": "业务微信群名称（如有）"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_contract",
            "description": "更新合同信息。用于补充微信群名称、备注等信息。当用户发送业务群截图时，提取群名后用此工具关联到合同。",
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
    {
        "type": "function",
        "function": {
            "name": "create_payment",
            "description": "为合同创建收入付款记录（客户向公司付款）。无凭证时创建为 pending 状态，有凭证时创建为 paid 状态。同币种不折算，混币种按付款日实时汇率自动结算。合同录入时系统会自动创建已付款项的记录，不需要手动调用。",
            "parameters": {
                "type": "object",
                "required": ["contract_id", "amount", "currency", "paid_date"],
                "properties": {
                    "contract_id": {"type": "integer", "description": "合同ID"},
                    "installment_number": {"type": "integer", "description": "第几期（1, 2, 3...）。通常无需指定，系统自动计算。仅在你明确知道期数时传入"},
                    "installment_name": {"type": "string", "description": "期数名称（如「定金」、「首期」、「尾款」），从合同原文或用户描述提取"},
                    "amount": {"type": "number", "description": "付款金额"},
                    "currency": {
                        "type": "string", "enum": ["CNY", "HKD"],
                        "description": "付款币种。优先从凭证分析结果中提取。",
                    },
                    "paid_date": {"type": "string", "description": "实际付款日期（YYYY-MM-DD）"},
                    "payment_method": {
                        "type": "string",
                        "enum": ["bank_transfer", "wechat", "alipay", "cash", "check", "unknown"],
                        "description": "付款方式",
                    },
                    "receipt_image_path": {"type": "string", "description": "付款凭证图片路径 — 使用 文件预分析 返回的 file_path，系统会自动保存到凭证目录"},
                    "notes": {"type": "string", "description": "备注"},
                    "description": {"type": "string", "description": "本次付款的简短业务说明（如：30系埃尔法定金、港车保险、现牌定金），从凭证或对话中提取，不超过30字"},
                    "receipt_data": {"type": "object", "description": "凭证分析结构化数据（JSON对象，包含document_type/amount/payer_name/transaction_id等）"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_expense",
            "description": "为合同创建支出记录（公司向第三方付款，如渠道费、办证费等）。需要指定收款方名称。期数自动生成。无凭证时创建为 pending 状态（不参与结算），有凭证时创建为 paid 状态（自动参与结算）。自动按付款日期查找汇率并折算为人民币。仅admin和expense角色可用。",
            "parameters": {
                "type": "object",
                "required": ["contract_id", "amount", "currency", "paid_date", "payee_name"],
                "properties": {
                    "contract_id": {"type": "integer", "description": "合同ID"},
                    "amount": {"type": "number", "description": "支出金额"},
                    "currency": {
                        "type": "string", "enum": ["CNY", "HKD"],
                        "description": "支出币种。优先从凭证分析结果中提取。",
                    },
                    "paid_date": {"type": "string", "description": "实际付款日期（YYYY-MM-DD）"},
                    "payee_name": {"type": "string", "description": "收款方名称（如：某某代办公司）"},
                    "installment_name": {"type": "string", "description": "期数名称（如「渠道费」、「办证费」）"},
                    "payment_method": {
                        "type": "string",
                        "enum": ["bank_transfer", "wechat", "alipay", "cash", "check", "unknown"],
                        "description": "付款方式",
                    },
                    "receipt_image_path": {"type": "string", "description": "付款凭证图片路径 — 使用 文件预分析 返回的 file_path，系统会自动保存到凭证目录"},
                    "notes": {"type": "string", "description": "备注"},
                    "description": {"type": "string", "description": "本次支出的简短业务说明（如：港车保险费、代办车牌渠道费），从凭证或对话中提取，不超过30字"},
                    "receipt_data": {"type": "object", "description": "凭证分析结构化数据（JSON对象）"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_payment",
            "description": "更新已有付款记录的备注、凭证、付款方式等信息。当用户为已有付款补充凭证时使用此工具（而不是创建新记录）。补充凭证后系统自动将 pending 转为 paid 并参与结算。",
            "parameters": {
                "type": "object",
                "required": ["payment_id"],
                "properties": {
                    "payment_id": {"type": "integer", "description": "付款记录ID"},
                    "notes": {"type": "string", "description": "备注信息（根据凭证内容自动生成描述性备注）"},
                    "payment_method": {"type": "string", "description": "付款方式"},
                    "receipt_image_path": {"type": "string", "description": "凭证图片路径 — 使用 文件预分析 返回的 file_path，系统会自动保存到凭证目录"},
                    "receipt_data": {"type": "object", "description": "凭证分析结构化数据（JSON对象）"},
                    "installment_name": {"type": "string", "description": "期数名称"},
                    "paid_date": {"type": "string", "description": "实际付款日期（YYYY-MM-DD）"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "match_receipt",
            "description": "根据凭证分析结果智能匹配到合同付款记录。优先按客户名匹配，其次按金额匹配。返回候选列表供用户确认。系统会自动使用之前 文件预分析 的分析结果。",
            "parameters": {
                "type": "object",
                "required": [],
                "properties": {
                    "file_id": {"type": "string", "description": "凭证文件的ID。如已通过 文件预分析 分析过，系统会自动从缓存获取凭证数据。"},
                    "receipt_data": {"type": "object", "description": "【通常无需传递】凭证分析结果。系统自动使用缓存数据。仅当缓存不可用时手动传入。"},
                    "customer_name": {"type": "string", "description": "客户姓名（当凭证中无法识别客户时，由用户提供）"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_expense_summary",
            "description": "查看支出汇总，可按合同或收款方维度聚合。仅admin和expense角色可用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "contract_id": {"type": "integer", "description": "按合同ID筛选"},
                    "payee_name": {"type": "string", "description": "按收款方名称筛选（模糊匹配）"},
                    "group_by": {
                        "type": "string",
                        "enum": ["contract", "payee"],
                        "description": "分组方式：按合同或按收款方",
                        "default": "contract",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_payment_summary",
            "description": "获取付款汇总：已付总额、待付总额。可按客户或合同分组。",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_name": {"type": "string", "description": "按客户名筛选"},
                    "date_from": {"type": "string", "description": "日期范围起始（YYYY-MM-DD）"},
                    "date_to": {"type": "string", "description": "日期范围截止（YYYY-MM-DD）"},
                    "group_by": {
                        "type": "string",
                        "enum": ["customer", "contract"],
                        "description": "分组方式",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_expiring_contracts",
            "description": "查找即将到期的合同（end_date在指定天数内）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "within_days": {"type": "integer", "description": "从今天起的天数", "default": 30},
                    "status": {"type": "string", "default": "active"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_contract_text",
            "description": "按关键词搜索所有合同的全文内容，返回匹配的合同列表和文本片段。用于查找包含特定条款、约定的合同（如搜索'违约金'、'仲裁'、'交车日期'等）。",
            "parameters": {
                "type": "object",
                "required": ["keyword"],
                "properties": {
                    "keyword": {"type": "string", "description": "搜索关键词，如'违约金'、'仲裁'、'交车日期'等"},
                    "contract_id": {"type": "integer", "description": "限定在某份合同中搜索（可选）"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ask_contract",
            "description": "检索某份合同的全文内容，用于回答关于合同具体条款的问题（如违约责任、付款条件、交车时间、双方权利义务等）。调用后系统会基于合同原文回答用户问题。",
            "parameters": {
                "type": "object",
                "required": ["contract_id", "question"],
                "properties": {
                    "contract_id": {"type": "integer", "description": "合同ID"},
                    "question": {"type": "string", "description": "用户关于合同条款的具体问题，如'违约金怎么约定'、'交车截止日期是什么'、'甲方有什么义务'"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_pending_plan",
            "description": (
                "声明本次录入计划并请求用户确认。"
                "所有 create_customer / create_contract / create_payment / create_expense / update_payment "
                "工具调用前，必须先调此工具声明计划。"
                "工作流：\n"
                "1) 阶段 2（展示）：先调一次，user_confirmed=False，summary 给用户看的内容，actions 列出计划调用的 create_* 工具名\n"
                "2) 用户回复后（阶段 3）：你必须用语义理解（不要用词库）判断用户是否确认。\n"
                "   - 若同意：在同一轮先调此工具，user_confirmed=True，actions 不变；然后继续调 actions 里的 create_* 工具\n"
                "   - 若拒绝/犹豫/修改：调此工具，user_confirmed=False，可更新 actions/summary；不要调 create_*"
            ),
            "parameters": {
                "type": "object",
                "required": ["summary", "actions", "user_confirmed"],
                "properties": {
                    "summary": {
                        "type": "string",
                        "description": "向用户展示的计划摘要，1-2 句话概括客户/金额/业务类型等关键信息",
                    },
                    "actions": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": [
                                "create_customer", "create_contract",
                                "create_payment", "create_expense",
                                "update_payment",
                            ],
                        },
                        "description": "计划要执行的所有写入工具名。写入工具必须在此列表中才能被允许执行。",
                    },
                    "user_confirmed": {
                        "type": "boolean",
                        "description": (
                            "用户是否已确认此计划。"
                            "由你根据用户最新消息的语义自行判断（语气、上下文、否定词都考虑），"
                            "不要依赖词库或关键词匹配。"
                        ),
                    },
                },
            },
        },
    },
]
