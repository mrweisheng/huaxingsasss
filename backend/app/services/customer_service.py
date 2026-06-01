"""
客户服务层 — 封装客户创建与去重逻辑
"""
import base64
import logging
from typing import Optional, Tuple

from sqlalchemy.orm import Session

from app.models.customer import Customer
from app.models.contract import Contract
from app.services.audit_service import AuditService

logger = logging.getLogger(__name__)


class CustomerService:

    @staticmethod
    def delete_customer(db: Session, customer_id: int, user_id: int = None) -> bool:
        """硬删除客户（仅允许无活跃合同时）"""
        customer = db.query(Customer).filter(
            Customer.id == customer_id,
            Customer.is_deleted == False,
        ).first()

        if not customer:
            return False

        # 检查是否有活跃（未删除）合同
        active_contracts = db.query(Contract).filter(
            Contract.customer_id == customer_id,
            Contract.is_deleted == False,
        ).count()

        if active_contracts > 0:
            raise ValueError(f"客户有 {active_contracts} 个活跃合同，无法删除")

        db.delete(customer)
        db.commit()

        if user_id:
            AuditService.log(
                db,
                user_id=user_id,
                action="delete",
                entity_type="customer",
                entity_id=customer_id,
                old_values={"name": customer.name, "phone": customer.phone},
            )

        logger.info("客户已删除: id=%d, name=%s", customer_id, customer.name)
        return True

    @staticmethod
    def create_or_get(
        db: Session,
        name: str,
        phone: Optional[str] = None,
        email: Optional[str] = None,
        contact_person: Optional[str] = None,
        id_card_number: Optional[str] = None,
        business_license: Optional[str] = None,
        address: Optional[str] = None,
        wechat_group_name: Optional[str] = None,
        remarks: Optional[str] = None,
        created_by: Optional[int] = None,
    ) -> Tuple[Customer, bool]:
        """
        创建客户或返回已有客户。

        去重规则（与 REST API 一致）：同名+同电话 或 同名+同邮箱 → 返回已有客户。

        Returns: (customer, was_created)
        """
        # 去重检查
        existing = None
        if phone:
            existing = (
                db.query(Customer)
                .filter(
                    Customer.name == name,
                    Customer.phone == phone,
                    Customer.is_deleted == False,
                )
                .first()
            )
        if not existing and email:
            existing = (
                db.query(Customer)
                .filter(
                    Customer.name == name,
                    Customer.email == email,
                    Customer.is_deleted == False,
                )
                .first()
            )

        if existing:
            # 合并新传入的非空信息到已有客户（仅补写空字段，不覆盖已有值）
            updated = False
            if id_card_number and not existing.id_card_number_encrypted:
                existing.id_card_number_encrypted = base64.b64encode(id_card_number.encode()).decode()
                updated = True
            if email and not existing.email:
                existing.email = email
                updated = True
            if address and not existing.address:
                existing.address = address
                updated = True
            if wechat_group_name and not existing.wechat_group_name:
                existing.wechat_group_name = wechat_group_name
                updated = True
            if business_license and not existing.business_license:
                existing.business_license = business_license
                updated = True
            if contact_person and not existing.contact_person:
                existing.contact_person = contact_person
                updated = True
            if updated:
                db.commit()
                db.refresh(existing)
                logger.info("客户已存在，补充了新信息: id=%d, fields updated", existing.id)
            else:
                logger.info("客户已存在，复用: id=%d, name=%s", existing.id, existing.name)
            return existing, False

        customer = Customer(
            name=name,
            contact_person=contact_person,
            phone=phone,
            email=email,
            # TODO(security): 当前仅 base64 编码（可逆），合规上不等同加密。
            # 计划升级为 cryptography 库 AES-GCM + KMS 密钥管理。
            id_card_number_encrypted=(
                base64.b64encode(id_card_number.encode()).decode()
                if id_card_number
                else None
            ),
            business_license=business_license,
            address=address,
            wechat_group_name=wechat_group_name,
            remarks=remarks,
            created_by=created_by,
        )
        db.add(customer)
        db.commit()
        db.refresh(customer)

        logger.info("创建客户: id=%d, name=%s", customer.id, customer.name)
        return customer, True
