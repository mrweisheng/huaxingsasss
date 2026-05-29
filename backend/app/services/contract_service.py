"""
合同服务层
"""
import logging
import uuid
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Optional, List, Dict, Any

from sqlalchemy import or_, func, String
from sqlalchemy.orm import Session, contains_eager

from app.config import settings
from app.models.contract import Contract
from app.models.customer import Customer
from app.models.payment import Payment
from app.schemas.contract import ContractCreate, ContractUpdate
from app.services.audit_service import AuditService

logger = logging.getLogger(__name__)


class ContractService:

    @staticmethod
    def generate_contract_number() -> str:
        """自动生成唯一合同编号: HT + 时间戳 + 4位随机"""
        return f"HT{datetime.now().strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:4].upper()}"
    """合同服务类"""
    
    @staticmethod
    def get_contracts(
        db: Session,
        page: int = 1,
        per_page: int = 20,
        status: Optional[str] = None,
        customer_id: Optional[int] = None,
        customer_name: Optional[str] = None,
        keyword: Optional[str] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        sales_person_id: Optional[int] = None
    ) -> tuple[List[Contract], int]:
        """
        获取合同列表
        
        Returns:
            (合同列表, 总数)
        """
        query = (
            db.query(Contract)
            .outerjoin(Customer, Contract.customer_id == Customer.id)
            .options(contains_eager(Contract.customer))
            .filter(Contract.is_deleted == False)
        )

        # 状态过滤
        if status:
            query = query.filter(Contract.status == status)

        # 客户ID过滤
        if customer_id:
            query = query.filter(Contract.customer_id == customer_id)

        # 业务员过滤
        if sales_person_id:
            query = query.filter(Contract.sales_person_id == sales_person_id)

        # 客户名称模糊搜索
        if customer_name:
            query = query.filter(Customer.name.ilike(f"%{customer_name}%"))

        # 关键词全文搜索
        if keyword:
            query = query.filter(
                or_(
                    Contract.contract_number.ilike(f"%{keyword}%"),
                    Contract.title.ilike(f"%{keyword}%"),
                    Contract.contract_data.cast(String).ilike(f"%{keyword}%")
                )
            )

        # 日期范围过滤
        if date_from:
            query = query.filter(Contract.signed_date >= date_from)
        if date_to:
            query = query.filter(Contract.signed_date <= date_to)

        # 总数
        total = query.count()

        # 分页（使用 contains_eager 后 Customer 已 join 加载，无需 N+1 回查）
        items = query.order_by(Contract.created_at.desc())\
            .offset((page - 1) * per_page)\
            .limit(per_page)\
            .all()

        # 填充 customer_name（从已加载的 customer 关系获取，无额外查询）
        for item in items:
            if item.customer:
                item.customer_name = item.customer.name
            else:
                item.customer_name = None

        return items, total
    
    @staticmethod
    def create_contract(
        db: Session,
        contract_data: ContractCreate,
        sales_person_id: int
    ) -> Contract:
        """创建合同"""
        # 检查合同编号是否已存在
        existing = db.query(Contract).filter(
            Contract.contract_number == contract_data.contract_number
        ).first()
        
        if existing:
            raise ValueError(f"合同编号 {contract_data.contract_number} 已存在")
        
        # 检查客户是否存在（customer_id 为 None 时跳过，解析后可关联）
        if contract_data.customer_id is not None:
            customer = db.query(Customer).filter(Customer.id == contract_data.customer_id).first()
            if not customer:
                raise ValueError("客户不存在")
        
        # 创建合同
        contract = Contract(
            contract_number=contract_data.contract_number,
            title=contract_data.title,
            business_type=contract_data.business_type,
            business_description=contract_data.business_description,
            customer_id=contract_data.customer_id,
            sales_person_id=sales_person_id,
            currency=contract_data.currency,
            total_amount=contract_data.total_amount,
            paid_amount=Decimal('0'),
            remaining_amount=contract_data.total_amount,
            original_file_path=contract_data.original_file_path,
            file_hash=contract_data.file_hash,
            signed_date=contract_data.signed_date,
            start_date=contract_data.start_date,
            end_date=contract_data.end_date,
            remarks=contract_data.remarks,
            status='draft',
            created_by=sales_person_id
        )
        
        db.add(contract)
        db.commit()
        db.refresh(contract)
        
        return contract
    
    @staticmethod
    def get_contract(db: Session, contract_id: int) -> Optional[Contract]:
        """获取合同详情（排除已软删除）"""
        return db.query(Contract).filter(
            Contract.id == contract_id,
            Contract.is_deleted == False
        ).first()

    @staticmethod
    def update_contract(
        db: Session,
        contract_id: int,
        contract_data: ContractUpdate
    ) -> Optional[Contract]:
        """更新合同"""
        contract = ContractService.get_contract(db, contract_id)

        if not contract:
            return None

        # 更新字段
        update_data = contract_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(contract, field, value)

        db.commit()
        db.refresh(contract)

        return contract

    @staticmethod
    def delete_contract(db: Session, contract_id: int, user_id: int = None) -> bool:
        """软删除合同，级联软删除付款记录，清理物理文件"""
        contract = db.query(Contract).filter(Contract.id == contract_id).first()

        if not contract:
            return False

        deleted_files = []

        # 1. 软删除关联付款记录，清理凭证文件
        payments = db.query(Payment).filter(Payment.contract_id == contract_id).all()
        for payment in payments:
            if payment.receipt_image_path:
                receipt_path = Path(settings.RECEIPT_UPLOAD_DIR) / payment.receipt_image_path
                if receipt_path.exists():
                    receipt_path.unlink()
                    deleted_files.append(str(receipt_path))
            payment.soft_delete()

        # 2. 删除合同物理文件
        if contract.original_file_path:
            contract_path = Path(settings.CONTRACT_UPLOAD_DIR) / contract.original_file_path
            if contract_path.exists():
                contract_path.unlink()
                deleted_files.append(str(contract_path))

        # 3. 软删除合同
        contract.soft_delete()
        db.commit()

        # 4. 审计日志
        if user_id:
            AuditService.log(
                db,
                user_id=user_id,
                action="delete",
                entity_type="contract",
                entity_id=contract_id,
                old_values={
                    "contract_number": contract.contract_number,
                    "status": contract.status,
                    "payments_count": len(payments),
                    "deleted_files": deleted_files,
                },
            )

        logger.info("合同已删除: id=%d, number=%s, 清理文件=%d", contract_id, contract.contract_number, len(deleted_files))
        return True
    
    @staticmethod
    def update_contract_data(
        db: Session,
        contract_id: int,
        contract_data: Dict[str, Any],
        confidence: float
    ) -> Optional[Contract]:
        """更新AI解析的合同数据"""
        contract = ContractService.get_contract(db, contract_id)
        
        if not contract:
            return None
        
        # 更新结构化数据
        contract.contract_data = contract_data
        
        # 从解析数据中提取关键字段
        if 'total_amount' in contract_data:
            contract.total_amount = Decimal(str(contract_data['total_amount']))
            contract.remaining_amount = contract.total_amount - contract.paid_amount
        
        if 'signed_date' in contract_data:
            try:
                contract.signed_date = date.fromisoformat(contract_data['signed_date'])
            except (ValueError, TypeError):
                pass

        if 'business_type' in contract_data:
            contract.business_type = contract_data['business_type']

        if 'business_description' in contract_data:
            contract.business_description = contract_data['business_description']

        validity = contract_data.get('validity_period')
        if isinstance(validity, dict):
            if validity.get('start_date'):
                try:
                    contract.start_date = date.fromisoformat(validity['start_date'])
                except (ValueError, TypeError):
                    pass
            if validity.get('end_date'):
                try:
                    contract.end_date = date.fromisoformat(validity['end_date'])
                except (ValueError, TypeError):
                    pass
        
        # 根据置信度设置状态
        if confidence >= 0.85:
            contract.status = 'active'
        else:
            contract.status = 'pending_review'
        
        db.commit()
        db.refresh(contract)
        
        return contract
