"""
合同附加项服务层

附加项 = 合同应收清单上的一行。本服务负责 CRUD、维护 contracts.additional_total_by_currency
冗余汇总（保证列表/台账零 N+1）、写审计日志。

注意：付款打标/取消打标不在本服务处理；仅在软删附加项时顺带把引用它的付款标签置 null
（软删不会触发 FK 的 ON DELETE SET NULL，必须手动处理）。
"""
import logging
from decimal import Decimal
from typing import Optional, List, Dict

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.contract import Contract
from app.models.contract_additional_item import ContractAdditionalItem
from app.models.payment import Payment
from app.schemas.contract_additional_item import AdditionalItemCreate, AdditionalItemUpdate
from app.services.audit_service import AuditService

logger = logging.getLogger(__name__)


class AdditionalItemService:
    """合同附加项服务"""

    @staticmethod
    def get(db: Session, item_id: int) -> Optional[ContractAdditionalItem]:
        """取单条附加项（排除已软删）"""
        return db.query(ContractAdditionalItem).filter(
            ContractAdditionalItem.id == item_id,
            ContractAdditionalItem.is_deleted == False,
        ).first()

    @staticmethod
    def list_by_contract(db: Session, contract_id: int) -> List[ContractAdditionalItem]:
        """列出合同所有未删除附加项（按创建顺序）"""
        return (
            db.query(ContractAdditionalItem)
            .filter(
                ContractAdditionalItem.contract_id == contract_id,
                ContractAdditionalItem.is_deleted == False,
            )
            .order_by(ContractAdditionalItem.id.asc())
            .all()
        )

    @staticmethod
    def get_summary_by_currency(db: Session, contract_id: int) -> Dict[str, float]:
        """读取合同附加项按币种汇总（只读，不写回）。供 Agent 工具 / 详情口径使用。"""
        return AdditionalItemService._recalculate_contract_summary(db, contract_id, write_back=False)

    @staticmethod
    def create(
        db: Session,
        item_data: AdditionalItemCreate,
        user_id: int,
    ) -> ContractAdditionalItem:
        """创建附加项 + 重算合同汇总"""
        contract = (
            db.query(Contract)
            .filter(Contract.id == item_data.contract_id, Contract.is_deleted == False)
            .first()
        )
        if not contract:
            raise ValueError("合同不存在")

        item = ContractAdditionalItem(
            contract_id=item_data.contract_id,
            name=item_data.name,
            amount=item_data.amount,
            currency=item_data.currency,
            paid_to=item_data.paid_to,
            description=item_data.description,
            occurred_date=item_data.occurred_date,
            remarks=item_data.remarks,
            created_by=user_id,
        )
        db.add(item)
        db.flush()  # 拿到 item.id，供后续汇总计算

        AdditionalItemService._recalculate_contract_summary(db, item_data.contract_id)

        db.commit()
        db.refresh(item)

        try:
            AuditService.log(
                db,
                user_id=user_id,
                action="create",
                entity_type="contract_additional_item",
                entity_id=item.id,
                new_values={
                    "contract_id": item.contract_id,
                    "name": item.name,
                    "amount": float(item.amount) if item.amount is not None else None,
                    "currency": item.currency,
                    "paid_to": item.paid_to,
                },
            )
        except Exception as e:
            logger.warning("审计日志写入失败: entity=contract_additional_item, action=create, error=%s", e)

        return item

    @staticmethod
    def update(
        db: Session,
        item_id: int,
        item_data: AdditionalItemUpdate,
        user_id: int,
    ) -> Optional[ContractAdditionalItem]:
        """更新附加项 + 重算合同汇总"""
        item = AdditionalItemService.get(db, item_id)
        if not item:
            return None

        old_values = {
            "name": item.name,
            "amount": float(item.amount) if item.amount is not None else None,
            "currency": item.currency,
            "paid_to": item.paid_to,
            "description": item.description,
        }

        update_data = item_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(item, field, value)

        AdditionalItemService._recalculate_contract_summary(db, item.contract_id)

        db.commit()
        db.refresh(item)

        try:
            new_values = {
                k: (float(v) if isinstance(v, Decimal) else v)
                for k, v in update_data.items()
            }
            AuditService.log(
                db,
                user_id=user_id,
                action="update",
                entity_type="contract_additional_item",
                entity_id=item.id,
                old_values=old_values,
                new_values=new_values,
            )
        except Exception as e:
            logger.warning("审计日志写入失败: entity=contract_additional_item, action=update, error=%s", e)

        return item

    @staticmethod
    def delete(db: Session, item_id: int, user_id: int) -> bool:
        """软删附加项 + 引用付款标签置 null + 重算合同汇总"""
        item = AdditionalItemService.get(db, item_id)
        if not item:
            return False

        contract_id = item.contract_id
        old_values = {
            "name": item.name,
            "amount": float(item.amount) if item.amount is not None else None,
            "currency": item.currency,
            "paid_to": item.paid_to,
        }

        item.soft_delete()

        # 软删不会触发 FK 的 ON DELETE SET NULL，需手动把引用此附加项的付款标签置空
        db.query(Payment).filter(Payment.additional_item_id == item_id).update(
            {Payment.additional_item_id: None}, synchronize_session=False
        )

        AdditionalItemService._recalculate_contract_summary(db, contract_id)

        db.commit()

        try:
            AuditService.log(
                db,
                user_id=user_id,
                action="delete",
                entity_type="contract_additional_item",
                entity_id=item_id,
                old_values=old_values,
            )
        except Exception as e:
            logger.warning("审计日志写入失败: entity=contract_additional_item, action=delete, error=%s", e)

        return True

    @staticmethod
    def _recalculate_contract_summary(
        db: Session, contract_id: int, write_back: bool = True
    ) -> Dict[str, float]:
        """重算合同附加项按币种汇总。

        write_back=True（默认，用于增删改）：写回 contracts.additional_total_by_currency，
        保证 JSONB 冗余字段与明细表一致（列表/台账零 N+1 的数据底座）。
        write_back=False（只读口径）：仅返回汇总，不写库。
        """
        rows = (
            db.query(
                ContractAdditionalItem.currency,
                func.sum(ContractAdditionalItem.amount),
            )
            .filter(
                ContractAdditionalItem.contract_id == contract_id,
                ContractAdditionalItem.is_deleted == False,
            )
            .group_by(ContractAdditionalItem.currency)
            .all()
        )
        summary: Dict[str, float] = {}
        for currency, total in rows:
            summary[currency] = float(total) if total is not None else 0.0

        if write_back:
            contract = db.query(Contract).filter(Contract.id == contract_id).first()
            if contract:
                contract.additional_total_by_currency = summary
        return summary
