"""
客户服务层 — 封装客户创建与去重逻辑
"""
import base64
import logging
from typing import Optional, Tuple

from sqlalchemy.orm import Session

from app.models.customer import Customer

logger = logging.getLogger(__name__)


class CustomerService:
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
            logger.info("客户已存在，复用: id=%d, name=%s", existing.id, existing.name)
            return existing, False

        customer = Customer(
            name=name,
            contact_person=contact_person,
            phone=phone,
            email=email,
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
