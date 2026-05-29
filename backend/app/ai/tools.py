"""
Agent 工具执行器
调用现有 Service 层实现业务操作
"""
import base64
import json
import logging
import os
import shutil
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
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
from app.ai.prompts import RECEIPT_ANALYSIS_PROMPT, CONTRACT_ANALYSIS_PROMPT, GENERAL_ANALYSIS_PROMPT
from app.services.contract_service import ContractService
from app.services.customer_service import CustomerService
from app.services.payment_service import PaymentService
from app.utils.file_utils import calculate_file_hash

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
            "business_type": c.business_type,
            "business_description": c.business_description,
            "customer_name": c.customer.name if c.customer else None,
            "currency": c.currency,
            "total_amount": float(c.total_amount) if c.total_amount else 0,
            "paid_amount": float(c.paid_amount) if c.paid_amount else 0,
            "remaining_amount": float(c.remaining_amount) if c.remaining_amount else 0,
            "total_amount_in_cny": float(c.total_amount_in_cny) if c.total_amount_in_cny else None,
            "paid_amount_in_cny": float(c.paid_amount_in_cny) if c.paid_amount_in_cny else 0,
            "status": c.status,
            "wechat_group": c.wechat_group,
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
            result["payments"] = payment_data["payments"]
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

    def create_customer(self, **kwargs) -> str:
        """创建客户。如果同名+同电话/邮箱的客户已存在，返回已有客户。"""
        if self.user.role not in ("admin", "finance", "sales"):
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
                "message": "客户创建成功" if created else f"客户已存在（ID: {customer.id}）",
            }, ensure_ascii=False)
        except Exception as e:
            logger.exception("create_customer failed")
            return json.dumps({"error": f"创建客户失败: {str(e)}"}, ensure_ascii=False)

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
        return ".bin"

    def create_contract(self, **kwargs) -> str:
        """为客户创建合同记录。合同编号自动生成。"""
        if self.user.role not in ("admin", "finance", "sales"):
            return json.dumps({"error": "当前角色无权创建合同"}, ensure_ascii=False)

        customer_id = kwargs.get("customer_id")
        file_id = kwargs.get("file_id")
        contract_data_raw = kwargs.get("contract_data", {})

        if not customer_id:
            return json.dumps({"error": "缺少 customer_id，请先创建或查找客户"}, ensure_ascii=False)
        if not file_id:
            return json.dumps({"error": "缺少 file_id，无法关联原始文件"}, ensure_ascii=False)

        # 验证客户存在
        customer = self.db.query(Customer).filter(
            Customer.id == customer_id, Customer.is_deleted == False
        ).first()
        if not customer:
            return json.dumps({"error": f"客户不存在: {customer_id}"}, ensure_ascii=False)

        # 处理文件
        temp_file_path = os.path.join(settings.TEMP_UPLOAD_DIR, file_id)
        file_hash = None
        original_file_path = f"agent_upload/{file_id}"

        if os.path.exists(temp_file_path):
            with open(temp_file_path, "rb") as f:
                content = f.read()
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

        # 解析日期
        signed_date = None
        if kwargs.get("signed_date"):
            try:
                signed_date = date.fromisoformat(kwargs["signed_date"])
            except ValueError:
                pass

        # 构建 schema 并创建
        try:
            from app.schemas.contract import ContractCreate

            contract_create = ContractCreate(
                contract_number=contract_number,
                title=kwargs.get("title"),
                business_type=kwargs.get("business_type"),
                business_description=kwargs.get("business_description"),
                customer_id=customer_id,
                currency=kwargs.get("currency", "CNY"),
                total_amount=Decimal(str(kwargs.get("total_amount", 0))),
                original_file_path=original_file_path,
                file_hash=file_hash,
                signed_date=signed_date,
                wechat_group=kwargs.get("wechat_group"),
                status="active",
            )

            contract = ContractService.create_contract(
                db=self.db,
                contract_data=contract_create,
                sales_person_id=self.user.id,
            )

            # 写入 contract_data JSON
            contract.contract_data = {
                "source": "agent",
                "file_id": file_id,
                "business_type": kwargs.get("business_type"),
                "business_description": kwargs.get("business_description"),
                **(contract_data_raw if isinstance(contract_data_raw, dict) else {}),
            }
            self.db.commit()
            self.db.refresh(contract)

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
                    "wechat_group": contract.wechat_group,
                    "signed_date": str(contract.signed_date) if contract.signed_date else None,
                },
            }, ensure_ascii=False)
        except Exception as e:
            logger.exception("create_contract failed")
            return json.dumps({"error": f"创建合同失败: {str(e)}"}, ensure_ascii=False)

    def update_contract(self, **kwargs) -> str:
        """更新合同信息（如微信群、备注等）"""
        if self.user.role not in ("admin", "finance", "sales"):
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
            return json.dumps({"error": "没有需要更新的字段"}, ensure_ascii=False)

        try:
            from app.schemas.contract import ContractUpdate
            contract_update = ContractUpdate(**updates)
            updated = ContractService.update_contract(self.db, contract_id, contract_update)
            if not updated:
                return json.dumps({"error": "更新失败"}, ensure_ascii=False)

            return json.dumps({
                "success": True,
                "contract": self._contract_to_dict(updated),
            }, ensure_ascii=False)
        except Exception as e:
            logger.exception("update_contract failed")
            return json.dumps({"error": f"更新合同失败: {str(e)}"}, ensure_ascii=False)

    def create_payment(self, **kwargs) -> str:
        if self.user.role not in ("admin", "finance", "sales"):
            return json.dumps({"error": "当前角色无权创建付款记录"}, ensure_ascii=False)

        if self.user.role == "sales":
            contract = self.db.query(Contract).filter(Contract.id == kwargs["contract_id"]).first()
            if not contract or contract.sales_person_id != self.user.id:
                return json.dumps({"error": "无权操作该合同的付款"}, ensure_ascii=False)

        has_receipt = kwargs.get("has_receipt", False)

        try:
            payment = PaymentService.create_payment_with_exchange_rate(
                db=self.db,
                contract_id=kwargs["contract_id"],
                installment_number=kwargs["installment_number"],
                currency=kwargs["currency"],
                amount=Decimal(str(kwargs["amount"])),
                paid_date=date.fromisoformat(kwargs["paid_date"]),
                payment_method=kwargs.get("payment_method", "unknown"),
                receipt_image_path=kwargs.get("receipt_image_path"),
                notes=kwargs.get("notes"),
                created_by=self.user.id,
                auto_confirm=has_receipt,
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

    # ── 文件分析工具 ──

    @staticmethod
    def _detect_image_mime(header: bytes) -> str:
        """读取文件头判断图片 MIME 类型"""
        if header[:4] == b"\x89PNG":
            return "image/png"
        if header[:3] == b"\xff\xd8\xff":
            return "image/jpeg"
        if header[:4] == b"GIF8":
            return "image/gif"
        if header[:4] == b"RIFF" and header[8:12] == b"WEBP":
            return "image/webp"
        if header[:2] == b"BM":
            return "image/bmp"
        return ""  # 不是已知图片格式

    def _extract_text_sync(self, file_path: str) -> str:
        """同步提取 Word/文本文件内容"""
        # 先尝试 Word
        try:
            from docx import Document
            doc = Document(file_path)
            paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
            if paragraphs:
                return "Word 文档内容:\n" + "\n".join(paragraphs)[:10000]
        except ImportError:
            pass
        except Exception:
            pass

        # 再尝试纯文本（多种编码）
        for encoding in ("utf-8", "gbk", "gb2312", "utf-16"):
            try:
                with open(file_path, "r", encoding=encoding) as f:
                    text = f.read(20000)
                return "文件内容:\n" + text[:10000]
            except (UnicodeDecodeError, UnicodeError):
                continue
        return ""

    def _extract_excel_sync(self, file_path: str) -> str:
        """同步提取 Excel 表格数据"""
        try:
            import openpyxl
            wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
            rows = []
            for sheet_name in wb.sheetnames:
                ws = wb[sheet_name]
                rows.append(f"[工作表: {sheet_name}]")
                count = 0
                for row in ws.iter_rows():
                    vals = [str(c.value) if c.value is not None else "" for c in row]
                    line = "\t".join(vals)
                    if line.strip():
                        rows.append(line)
                        count += 1
                    if count >= 200:
                        rows.append(f"... (仅前 200 行)")
                        break
            wb.close()
            return "Excel 表格数据:\n" + "\n".join(rows)[:10000]
        except ImportError:
            return ""
        except Exception:
            return ".xls 旧格式不受支持，请转换为 .xlsx"

    def analyze_image(self, file_id: str, analysis_type: str = "receipt") -> str:
        """分析上传的文件（图片/PDF/Word/Excel/文本），同步调用"""
        file_path = os.path.join(settings.TEMP_UPLOAD_DIR, file_id)
        if not os.path.exists(file_path):
            return json.dumps({"error": f"文件不存在: {file_id}"}, ensure_ascii=False)

        # 1) 读取文件头判断是否为图片
        with open(file_path, "rb") as f:
            header = f.read(12)
            f.seek(0)
            file_bytes = f.read()

        mime = self._detect_image_mime(header)

        if mime:
            # 是图片 → VL 模型分析
            prompt = {
                "receipt": RECEIPT_ANALYSIS_PROMPT,
                "contract": CONTRACT_ANALYSIS_PROMPT,
                "general": GENERAL_ANALYSIS_PROMPT,
            }.get(analysis_type, GENERAL_ANALYSIS_PROMPT)

            image_base64 = base64.b64encode(file_bytes).decode()
            payload = {
                "model": settings.SILICONFLOW_VISION_MODEL,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:{mime};base64,{image_base64}"},
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

            try:
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
                    "file_type": "image",
                    "analysis_type": analysis_type,
                }, ensure_ascii=False)
            except Exception as e:
                logger.exception("analyze_image VL call failed")
                return json.dumps({"error": f"图片分析失败: {str(e)}"}, ensure_ascii=False)

        # 2) 不是图片 → 尝试 PDF 解析
        if header[:4] == b"%PDF":
            try:
                import fitz
                doc = fitz.open(file_path)
                pages_text = []
                for page_num in range(len(doc)):
                    page = doc[page_num]
                    text = page.get_text()
                    if text.strip():
                        pages_text.append(f"第{page_num + 1}页:\n{text.strip()}")
                    else:
                        # 扫描页 → 渲染为图片并用 VL 分析
                        pix = page.get_pixmap(dpi=200)
                        img_bytes = pix.tobytes("png")
                        img_b64 = base64.b64encode(img_bytes).decode()
                        prompt = {
                            "receipt": RECEIPT_ANALYSIS_PROMPT,
                            "contract": CONTRACT_ANALYSIS_PROMPT,
                            "general": GENERAL_ANALYSIS_PROMPT,
                        }.get(analysis_type, GENERAL_ANALYSIS_PROMPT)

                        payload = {
                            "model": settings.SILICONFLOW_VISION_MODEL,
                            "messages": [
                                {
                                    "role": "user",
                                    "content": [
                                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}},
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
                            resp = client.post(f"{settings.SILICONFLOW_BASE_URL}/chat/completions", json=payload, headers=headers)
                        if resp.status_code == 200:
                            content = resp.json()["choices"][0]["message"]["content"]
                            pages_text.append(f"第{page_num + 1}页(扫描): {content[:500]}")
                        else:
                            pages_text.append(f"第{page_num + 1}页分析失败")
                doc.close()
                result = "\n".join(pages_text)
                return json.dumps({"success": True, "data": {"content": result[:5000]}, "file_type": "pdf"}, ensure_ascii=False)
            except ImportError:
                return json.dumps({"error": "PDF 分析不可用（缺少 PyMuPDF）"}, ensure_ascii=False)
            except Exception as e:
                return json.dumps({"error": f"PDF 分析失败: {str(e)}"}, ensure_ascii=False)

        # 3) 尝试 Word / 文本
        text_result = self._extract_text_sync(file_path)
        if text_result:
            return json.dumps({"success": True, "data": {"content": text_result}, "file_type": "document"}, ensure_ascii=False)

        # 4) 尝试 Excel
        excel_result = self._extract_excel_sync(file_path)
        if excel_result:
            return json.dumps({"success": True, "data": {"content": excel_result}, "file_type": "excel"}, ensure_ascii=False)

        return json.dumps({"error": "无法识别的文件类型，支持：图片、PDF、Word、Excel、文本"}, ensure_ascii=False)

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
                    "id_card_number": {"type": "string", "description": "身份证号或证件号"},
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
                    "overdue_only": {"type": "boolean", "description": "只返回逾期付款", "default": False},
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
            "description": "为客户创建合同记录。需要先通过 create_customer 或 search_customers 获取 customer_id。合同编号自动生成。如果同一文件已创建过合同会返回已有记录。",
            "parameters": {
                "type": "object",
                "required": ["customer_id", "file_id", "contract_data"],
                "properties": {
                    "customer_id": {"type": "integer", "description": "客户ID（通过 create_customer 或 search_customers 获取）"},
                    "file_id": {"type": "string", "description": "上传文件的ID（聊天上传时返回的 file_id）"},
                    "contract_data": {"type": "object", "description": "从合同文件提取的全部信息（JSON对象，包含甲方乙方、金额、服务内容等）"},
                    "title": {"type": "string", "description": "合同标题（如：购车合同、两地牌办理合同）"},
                    "total_amount": {"type": "number", "description": "合同总金额"},
                    "currency": {"type": "string", "enum": ["CNY", "HKD", "USD"], "description": "币种，默认CNY"},
                    "signed_date": {"type": "string", "description": "签订日期（YYYY-MM-DD）"},
                    "business_type": {"type": "string", "enum": ["车辆业务", "中港牌业务"], "description": "业务大类：车辆业务（买车卖车）或中港牌业务（办理中港车牌）"},
                    "business_description": {"type": "string", "description": "业务具体描述，如：购买丰田阿尔法30系、办理深圳湾口岸中港车牌"},
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
            "description": "为合同创建付款记录。如果从合同中提取到已付定金/首付款但没有上传凭证，应设置 has_receipt=false，付款将标记为待凭证状态（不计入已付金额）。有凭证时 has_receipt=true 会立即确认付款并计入合同已付金额。调用前必须与用户确认所有信息。会自动按付款日期查找汇率并折算为人民币。",
            "parameters": {
                "type": "object",
                "required": ["contract_id", "installment_number", "amount", "currency", "paid_date"],
                "properties": {
                    "contract_id": {"type": "integer", "description": "合同ID"},
                    "installment_number": {"type": "integer", "description": "第几期（1, 2, 3...）"},
                    "amount": {"type": "number", "description": "付款金额"},
                    "currency": {"type": "string", "enum": ["CNY", "HKD", "USD"], "default": "CNY"},
                    "paid_date": {"type": "string", "description": "实际付款日期（YYYY-MM-DD）"},
                    "payment_method": {
                        "type": "string",
                        "enum": ["bank_transfer", "wechat", "alipay", "cash", "check", "unknown"],
                        "description": "付款方式",
                    },
                    "has_receipt": {
                        "type": "boolean",
                        "description": "是否已上传付款凭证。从合同提取的定金/首付款通常无凭证，设为 false",
                        "default": False,
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
            "description": "分析上传的文件（支持图片、PDF、Word、Excel、文本文件）。图片/扫描件通过视觉模型提取信息，文档类提取文字内容。文件需先通过聊天上传接口上传。",
            "parameters": {
                "type": "object",
                "required": ["file_id", "analysis_type"],
                "properties": {
                    "file_id": {"type": "string", "description": "上传接口返回的文件ID"},
                    "analysis_type": {
                        "type": "string",
                        "enum": ["receipt", "contract", "general"],
                        "description": "分析类型（图片/扫描件适用）",
                    },
                },
            },
        },
    },
]
