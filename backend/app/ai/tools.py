"""
Agent 工具执行器
调用现有 Service 层实现业务操作
"""
import base64
import json
import logging
import os
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from datetime import timedelta

import httpx
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.config import settings
from app.models.customer import Customer
from app.models.contract import Contract
from app.models.payment import Payment
from app.models.user import User
from app.ai.prompts import RECEIPT_ANALYSIS_PROMPT, CONTRACT_ANALYSIS_PROMPT
from app.services.contract_service import ContractService
from app.services.payment_service import PaymentService

logger = logging.getLogger(__name__)


class ToolExecutor:
    """Agent 工具执行器，每个方法返回 JSON 字符串"""

    def __init__(self, db: Session, user: User):
        self.db = db
        self.user = user

    def _can_access_contract(self, contract: Contract) -> bool:
        if self.user.role in ("admin", "finance"):
            return True
        return contract.sales_person_id == self.user.id

    def _contract_to_dict(self, c: Contract) -> dict:
        return {
            "id": c.id,
            "contract_number": c.contract_number,
            "title": c.title,
            "customer_name": c.customer.name if c.customer else None,
            "currency": c.currency,
            "total_amount": float(c.total_amount) if c.total_amount else 0,
            "paid_amount": float(c.paid_amount) if c.paid_amount else 0,
            "remaining_amount": float(c.remaining_amount) if c.remaining_amount else 0,
            "total_amount_in_cny": float(c.total_amount_in_cny) if c.total_amount_in_cny else None,
            "paid_amount_in_cny": float(c.paid_amount_in_cny) if c.paid_amount_in_cny else 0,
            "status": c.status,
            "signed_date": str(c.signed_date) if c.signed_date else None,
            "end_date": str(c.end_date) if c.end_date else None,
        }

    def _payment_to_dict(self, p: Payment) -> dict:
        return {
            "id": p.id,
            "contract_id": p.contract_id,
            "installment_number": p.installment_number,
            "installment_name": p.installment_name,
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

        if name:
            query = query.filter(Customer.name.ilike(f"%{name}%"))
        if phone:
            query = query.filter(Customer.phone.ilike(f"%{phone}%"))
        if wechat_group:
            query = query.filter(Customer.wechat_group_name.ilike(f"%{wechat_group}%"))

        if not (name or phone or wechat_group):
            return json.dumps({"error": "请至少提供一个搜索条件（name/phone/wechat_group）"}, ensure_ascii=False)

        customers = query.limit(limit).all()
        results = []
        for c in customers:
            contract_count = self.db.query(Contract).filter(
                Contract.customer_id == c.id,
                Contract.is_deleted == False,
            ).count()
            results.append({
                "id": c.id,
                "name": c.name,
                "contact_person": c.contact_person,
                "phone": c.phone,
                "wechat_group_name": c.wechat_group_name,
                "contract_count": contract_count,
            })

        return json.dumps({"customers": results, "total": len(results)}, ensure_ascii=False)

    def search_contracts(self, **kwargs) -> str:
        sales_person_id = None
        if self.user.role == "sales":
            sales_person_id = self.user.id

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
            )
        except Exception as e:
            return json.dumps({"error": str(e)}, ensure_ascii=False)

        contracts = [self._contract_to_dict(c) for c in items]
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
            payment_data = PaymentService.get_contract_payments(self.db, contract_id)
            result["payments"] = [self._payment_to_dict(p) for p in payment_data["payments"]]
        except Exception:
            result["payments"] = []

        return json.dumps(result, ensure_ascii=False)

    def get_customer_contracts(self, customer_id: int) -> str:
        sales_person_id = None
        if self.user.role == "sales":
            sales_person_id = self.user.id

        items, total = ContractService.get_contracts(
            self.db,
            customer_id=customer_id,
            sales_person_id=sales_person_id,
            per_page=50,
        )
        contracts = [self._contract_to_dict(c) for c in items]
        return json.dumps({"contracts": contracts, "total": total}, ensure_ascii=False)

    def query_payments(self, **kwargs) -> str:
        query = self.db.query(Payment).filter(Payment.is_deleted == False)

        if kwargs.get("contract_id"):
            query = query.filter(Payment.contract_id == kwargs["contract_id"])

        if kwargs.get("status"):
            query = query.filter(Payment.status == kwargs["status"])

        if kwargs.get("overdue_only"):
            query = query.filter(
                Payment.due_date < date.today(),
                Payment.status.in_(["pending", "partial"]),
            )

        if self.user.role == "sales":
            query = query.join(Contract).filter(Contract.sales_person_id == self.user.id)

        page = kwargs.get("page", 1)
        per_page = kwargs.get("per_page", 20)
        total = query.count()
        payments = query.order_by(Payment.created_at.desc()) \
            .offset((page - 1) * per_page).limit(per_page).all()

        results = [self._payment_to_dict(p) for p in payments]

        for r, p in zip(results, payments):
            if p.contract:
                r["contract_number"] = p.contract.contract_number
                if p.contract.customer:
                    r["customer_name"] = p.contract.customer.name

        return json.dumps({"payments": results, "total": total}, ensure_ascii=False)

    # ── 动作工具 ──

    def create_payment(self, **kwargs) -> str:
        if self.user.role not in ("admin", "finance", "sales"):
            return json.dumps({"error": "当前角色无权创建付款记录"}, ensure_ascii=False)

        if self.user.role == "sales":
            contract = self.db.query(Contract).filter(Contract.id == kwargs["contract_id"]).first()
            if not contract or contract.sales_person_id != self.user.id:
                return json.dumps({"error": "无权操作该合同的付款"}, ensure_ascii=False)

        try:
            payment = PaymentService.create_payment_with_exchange_rate(
                db=self.db,
                contract_id=kwargs["contract_id"],
                installment_number=kwargs["installment_number"],
                currency=kwargs["currency"],
                amount=Decimal(str(kwargs["amount"])),
                paid_date=date.fromisoformat(kwargs["paid_date"]),
                payment_method=kwargs["payment_method"],
                receipt_image_path=kwargs.get("receipt_image_path"),
                notes=kwargs.get("notes"),
                created_by=self.user.id,
            )
            self.db.refresh(payment)
            if payment.contract and payment.contract.customer:
                payment.contract.customer  # ensure loaded
            result = self._payment_to_dict(payment)
            result["contract_number"] = payment.contract.contract_number if payment.contract else None
            result["customer_name"] = payment.contract.customer.name if payment.contract and payment.contract.customer else None
            return json.dumps({"success": True, "payment": result}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"error": str(e)}, ensure_ascii=False)

    # ── 分析工具 ──

    def get_payment_summary(self, **kwargs) -> str:
        query = self.db.query(Payment).filter(Payment.is_deleted == False)

        if self.user.role == "sales":
            query = query.join(Contract).filter(Contract.sales_person_id == self.user.id)

        if kwargs.get("customer_name"):
            query = query.join(Contract).join(Customer).filter(
                Customer.name.ilike(f"%{kwargs['customer_name']}%")
            )

        payments = query.all()

        total_paid = sum(float(p.paid_amount or 0) for p in payments if p.status == "paid")
        total_pending = sum(float(p.amount or 0) - float(p.paid_amount or 0) for p in payments if p.status in ("pending", "partial"))
        total_overdue = sum(
            float(p.amount or 0) - float(p.paid_amount or 0)
            for p in payments
            if p.status in ("pending", "partial") and p.due_date and p.due_date < date.today()
        )

        summary = {
            "total_paid": total_paid,
            "total_pending": total_pending,
            "total_overdue": total_overdue,
            "payment_count": len(payments),
        }

        group_by = kwargs.get("group_by")
        if group_by == "contract":
            groups = {}
            for p in payments:
                cid = p.contract_id
                if cid not in groups:
                    groups[cid] = {"contract_id": cid, "paid": 0, "pending": 0}
                if p.status == "paid":
                    groups[cid]["paid"] += float(p.paid_amount or 0)
                elif p.status in ("pending", "partial"):
                    groups[cid]["pending"] += float(p.amount or 0) - float(p.paid_amount or 0)
            summary["groups"] = list(groups.values())

        return json.dumps(summary, ensure_ascii=False)

    def get_overdue_payments(self, **kwargs) -> str:
        query = self.db.query(Payment).filter(
            Payment.is_deleted == False,
            Payment.due_date < date.today(),
            Payment.status.in_(["pending", "partial"]),
        )

        if self.user.role == "sales":
            query = query.join(Contract).filter(Contract.sales_person_id == self.user.id)

        if kwargs.get("customer_name"):
            query = query.join(Contract).join(Customer).filter(
                Customer.name.ilike(f"%{kwargs['customer_name']}%")
            )

        min_days = kwargs.get("min_days_overdue", 1)
        payments = query.all()

        results = []
        for p in payments:
            days_overdue = (date.today() - p.due_date).days if p.due_date else 0
            if days_overdue >= min_days:
                results.append({
                    **self._payment_to_dict(p),
                    "days_overdue": days_overdue,
                    "contract_number": p.contract.contract_number if p.contract else None,
                    "customer_name": p.contract.customer.name if p.contract and p.contract.customer else None,
                })

        results.sort(key=lambda x: x["days_overdue"], reverse=True)
        return json.dumps({"overdue_payments": results, "total": len(results)}, ensure_ascii=False)

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

        if self.user.role == "sales":
            query = query.filter(Contract.sales_person_id == self.user.id)

        contracts = query.order_by(Contract.end_date).all()
        results = []
        for c in contracts:
            results.append({
                **self._contract_to_dict(c),
                "days_until_expiry": (c.end_date - date.today()).days if c.end_date else None,
            })

        return json.dumps({"contracts": results, "total": len(results)}, ensure_ascii=False)

    # ── 图片分析工具 ──

    def analyze_image(self, file_id: str, analysis_type: str = "receipt") -> str:
        """使用 SiliconFlow VL 模型分析图片，同步调用"""
        file_path = os.path.join(settings.TEMP_UPLOAD_DIR, file_id)
        if not os.path.exists(file_path):
            return json.dumps({"error": f"文件不存在: {file_id}"}, ensure_ascii=False)

        if analysis_type == "receipt":
            prompt = RECEIPT_ANALYSIS_PROMPT
        elif analysis_type == "contract":
            prompt = CONTRACT_ANALYSIS_PROMPT
        else:
            prompt = RECEIPT_ANALYSIS_PROMPT

        try:
            with open(file_path, "rb") as f:
                image_base64 = base64.b64encode(f.read()).decode()

            payload = {
                "model": settings.SILICONFLOW_VISION_MODEL,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"},
                            },
                            {"type": "text", "text": prompt},
                        ],
                    }
                ],
                "temperature": 0.1,
                "max_tokens": 4096,
            }

            headers = {
                "Authorization": f"Bearer {settings.SILICONFLOW_API_KEY}",
                "Content-Type": "application/json",
            }

            with httpx.Client(timeout=60.0) as client:
                response = client.post(
                    f"{settings.SILICONFLOW_BASE_URL}/chat/completions",
                    json=payload,
                    headers=headers,
                )

            if response.status_code != 200:
                return json.dumps({"error": f"VL API 错误: {response.text}"}, ensure_ascii=False)

            result = response.json()
            content = result["choices"][0]["message"]["content"]

            try:
                structured = json.loads(content)
            except json.JSONDecodeError:
                structured = {"raw": content}

            return json.dumps({
                "success": True,
                "data": structured,
                "analysis_type": analysis_type,
            }, ensure_ascii=False)

        except Exception as e:
            logger.exception("analyze_image failed")
            return json.dumps({"error": f"图片分析失败: {str(e)}"}, ensure_ascii=False)

    def execute(self, tool_name: str, arguments: dict) -> str:
        """统一执行入口"""
        handler = getattr(self, tool_name, None)
        if not handler:
            return json.dumps({"error": f"未知工具: {tool_name}"}, ensure_ascii=False)

        try:
            return handler(**arguments)
        except Exception as e:
            logger.exception(f"Tool execution failed: {tool_name}")
            return json.dumps({"error": f"工具执行失败: {str(e)}"}, ensure_ascii=False)


# OpenAI function calling 格式的工具定义
TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "search_customers",
            "description": "按姓名、电话或微信群名搜索客户。返回匹配的客户列表及其关联合同数量。",
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
            "name": "search_contracts",
            "description": "按合同编号、客户名、状态或关键词搜索合同。返回合同列表含金额和付款进度。",
            "parameters": {
                "type": "object",
                "properties": {
                    "contract_number": {"type": "string", "description": "合同编号"},
                    "customer_name": {"type": "string", "description": "客户姓名（模糊匹配）"},
                    "status": {
                        "type": "string",
                        "enum": ["draft", "pending_review", "active", "completed", "cancelled", "disputed"],
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
            "description": "获取某客户的所有合同及付款状态汇总。",
            "parameters": {
                "type": "object",
                "required": ["customer_id"],
                "properties": {
                    "customer_id": {"type": "integer", "description": "客户ID"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_payments",
            "description": "按合同ID或状态查询付款记录。可查找逾期付款。",
            "parameters": {
                "type": "object",
                "properties": {
                    "contract_id": {"type": "integer", "description": "按合同ID筛选"},
                    "status": {
                        "type": "string",
                        "enum": ["pending", "partial", "paid", "overdue", "cancelled"],
                        "description": "付款状态筛选",
                    },
                    "overdue_only": {"type": "boolean", "description": "只返回逾期付款", "default": false},
                    "page": {"type": "integer", "default": 1},
                    "per_page": {"type": "integer", "default": 20},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_payment",
            "description": "为合同创建付款记录。调用前必须与用户确认所有信息。会自动按付款日期查找汇率并折算为人民币。",
            "parameters": {
                "type": "object",
                "required": ["contract_id", "installment_number", "amount", "currency", "paid_date", "payment_method"],
                "properties": {
                    "contract_id": {"type": "integer", "description": "合同ID"},
                    "installment_number": {"type": "integer", "description": "第几期（1, 2, 3...）"},
                    "amount": {"type": "number", "description": "付款金额"},
                    "currency": {"type": "string", "enum": ["CNY", "HKD", "USD"], "default": "CNY"},
                    "paid_date": {"type": "string", "description": "实际付款日期（YYYY-MM-DD）"},
                    "payment_method": {
                        "type": "string",
                        "enum": ["bank_transfer", "wechat", "alipay", "cash", "check"],
                        "description": "付款方式",
                    },
                    "notes": {"type": "string", "description": "备注"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_payment_summary",
            "description": "获取付款汇总：已付总额、待付总额、逾期总额。可按客户或合同分组。",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_name": {"type": "string", "description": "按客户名筛选"},
                    "date_from": {"type": "string", "description": "日期范围起始（YYYY-MM-DD）"},
                    "date_to": {"type": "string", "description": "日期范围截止（YYYY-MM-DD）"},
                    "group_by": {
                        "type": "string",
                        "enum": ["customer", "contract", "month"],
                        "description": "分组方式",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_overdue_payments",
            "description": "查找所有逾期未付的款项（已过应付款日期且状态为pending或partial）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_name": {"type": "string", "description": "按客户名筛选"},
                    "min_days_overdue": {"type": "integer", "description": "最小逾期天数", "default": 1},
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
            "name": "analyze_image",
            "description": "分析上传的图片（凭证、合同、截图）。图片需先通过聊天上传接口上传。返回提取的结构化信息。",
            "parameters": {
                "type": "object",
                "required": ["file_id", "analysis_type"],
                "properties": {
                    "file_id": {"type": "string", "description": "上传接口返回的文件ID"},
                    "analysis_type": {
                        "type": "string",
                        "enum": ["receipt", "contract", "general"],
                        "description": "分析类型",
                    },
                },
            },
        },
    },
]
