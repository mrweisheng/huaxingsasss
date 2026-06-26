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
from sqlalchemy.orm import Session, contains_eager, selectinload, with_loader_criteria

from app.config import settings
from app.core.chinese import search_variants
from app.models.contract import Contract
from app.models.contract_additional_item import ContractAdditionalItem
from app.models.customer import Customer
from app.models.payment import Payment
from app.schemas.contract import ContractCreate, ContractUpdate
from app.services.audit_service import AuditService
from app.services.exchange_rate_service import ExchangeRateService

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
        sales_person_id: Optional[int] = None,
        contract_number: Optional[str] = None,
        business_type: Optional[str] = None,
        customer_ids: Optional[List[int]] = None,
        include_payments: bool = False,
        payment_type_filter: Optional[str] = None,
    ) -> tuple[List[Contract], int]:
        """
        获取合同列表

        Args:
            business_type: 业务类型过滤。
                - 传入非空字符串 → WHERE business_type IN (传入值, NULL)，存量合同 NULL 兜底包含
                - None/空 → 不过滤
            customer_ids: 批量客户ID列表。
                - 传入非空列表 → WHERE customer_id IN (...)
            include_payments: 是否一并 eager load 付款明细。
                - True → selectinload(Contract.payments)，供台账视图一次拿全
                - False（默认） → 不加载，向后兼容现有调用方
            payment_type_filter: 仅 include_payments=True 时生效；
                'income' / 'expense' → 在 selectinload 时即按类型过滤，避免把另一类 IO 拉到内存。
                None → 不按类型过滤（admin 视角，两类都要看）。

        Returns:
            (合同列表, 总数)
        """
        query = (
            db.query(Contract)
            .outerjoin(Customer, Contract.customer_id == Customer.id)
            .options(contains_eager(Contract.customer))
            .filter(Contract.is_deleted == False)
        )

        if include_payments:
            # loader criterion：把软删过滤 + 角色类型过滤直接下推到 DB
            #   - 避免拉 expense 流水给 income 用户（数据暴露面 + IO 双省）
            #   - 避免软删数据走网络再被 Python 端裁掉
            payment_criteria = [Payment.is_deleted == False]
            if payment_type_filter in ("income", "expense"):
                payment_criteria.append(Payment.type == payment_type_filter)
            query = query.options(
                selectinload(Contract.payments.and_(*payment_criteria))
            )

        # 合同编号精确匹配
        if contract_number:
            query = query.filter(Contract.contract_number == contract_number)

        # 状态过滤
        if status:
            query = query.filter(Contract.status == status)

        # 客户ID过滤（单个）
        if customer_id:
            query = query.filter(Contract.customer_id == customer_id)

        # 客户ID批量过滤
        if customer_ids:
            query = query.filter(Contract.customer_id.in_(customer_ids))

        # 业务员过滤
        if sales_person_id:
            query = query.filter(Contract.sales_person_id == sales_person_id)

        # 业务类型过滤（含 NULL 兜底）
        if business_type:
            from app.core.business_types import BusinessType as _BT
            normalized = _BT.normalize(business_type) or business_type
            # IN (传入值, NULL) —— 存量合同 business_type 为 NULL 时兜底包含
            query = query.filter(
                or_(Contract.business_type == normalized, Contract.business_type.is_(None))
            )

        # 客户名称 / 业务群名称 模糊搜索（繁简兼容）
        # 群名是业务员查找合同的主要线索（"查这个群0605深圳湾"），与客户名同等重要，故一并匹配
        if customer_name:
            variants = search_variants(customer_name)
            escaped = [v.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") for v in variants]
            query = query.filter(or_(
                *[Customer.name.ilike(f"%{v}%") for v in escaped],
                *[Contract.wechat_group.ilike(f"%{v}%") for v in escaped],
            ))

        # 关键词全文搜索（含业务微信群名称——业务员常按群名查合同）
        if keyword:
            # 群名是用户自由输入的中文，繁简都可能，走 search_variants 兼容；
            # 编号/标题/contract_data 不做繁简转换（编号无中文，标题由 AI 规整）
            group_variants = search_variants(keyword)
            group_escaped = [v.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") for v in group_variants]
            query = query.filter(
                or_(
                    Contract.contract_number.ilike(f"%{keyword}%"),
                    Contract.title.ilike(f"%{keyword}%"),
                    *[Contract.wechat_group.ilike(f"%{v}%") for v in group_escaped],
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
        # 按签订日期降序排列（新到旧），NULL 值排在最后
        items = query.order_by(Contract.signed_date.desc().nullslast())\
            .offset((page - 1) * per_page)\
            .limit(per_page)\
            .all()

        # 填充 customer_name（从已加载的 customer 关系获取，无额外查询）
        # 同时统计每份合同的付款状态分布
        if items:
            contract_ids = [item.id for item in items]
            payment_stats = (
                db.query(
                    Payment.contract_id,
                    func.count().filter(Payment.status == 'paid', Payment.type == 'income').label('paid_count'),
                    func.count().filter(Payment.type == 'expense').label('expense_count'),
                    func.count().filter(Payment.is_deleted == False).label('total_count'),
                )
                .filter(Payment.contract_id.in_(contract_ids), Payment.is_deleted == False)
                .group_by(Payment.contract_id)
                .all()
            )
            stats_map = {s.contract_id: s for s in payment_stats}
        else:
            stats_map = {}

        for item in items:
            if item.customer:
                item.customer_name = item.customer.name
            else:
                item.customer_name = None
            stats = stats_map.get(item.id)
            item.paid_count = stats.paid_count if stats else 0
            item.expense_count = stats.expense_count if stats else 0
            item.payment_total_count = stats.total_count if stats else 0
            # include_payments：DB 层已过滤软删/类型，这里只按 (期数, id) 排序保证前端展示稳定
            if include_payments:
                item.payments = sorted(
                    list(item.payments),
                    key=lambda p: (p.installment_number or 0, p.id),
                )

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
            wechat_group=contract_data.wechat_group,
            status=contract_data.status or 'draft',
            created_by=sales_person_id
        )
        
        db.add(contract)
        db.commit()
        db.refresh(contract)

        # 审计日志
        try:
            AuditService.log(
                db,
                user_id=sales_person_id,
                action="create",
                entity_type="contract",
                entity_id=contract.id,
                new_values={
                    "contract_number": contract.contract_number,
                    "title": contract.title,
                    "business_type": contract.business_type,
                    "customer_id": contract.customer_id,
                    "currency": contract.currency,
                    "total_amount": float(contract.total_amount) if contract.total_amount else None,
                    "status": contract.status,
                },
            )
        except Exception as e:
            logger.warning("审计日志写入失败: entity=contract, action=create, error=%s", e)

        # 所有合同统一维护 _in_cny 字段（CNY 合同为原值，非 CNY 合同按汇率折算）
        if contract.total_amount > 0:
            if contract.currency == "CNY":
                contract.total_amount_in_cny = contract.total_amount
                contract.remaining_amount_in_cny = contract.total_amount
                logger.info("合同CNY等值: contract_id=%d, CNY 1:1, amount=%s", contract.id, contract.total_amount)
            else:
                rate_date = contract.signed_date or date.today()
                try:
                    exchange_rate, total_in_cny = ExchangeRateService.convert_to_cny(
                        db, contract.total_amount, contract.currency, rate_date
                    )
                    contract.total_amount_in_cny = total_in_cny
                    contract.remaining_amount_in_cny = total_in_cny  # paid_amount=0, 所以 remaining = total
                    logger.info(
                        "合同CNY等值计算: contract_id=%d, %s %s → %s CNY (汇率=%s, 日期=%s)",
                        contract.id, contract.total_amount, contract.currency,
                        total_in_cny, exchange_rate, rate_date,
                    )
                except Exception as e:
                    logger.warning("合同CNY等值计算失败: contract_id=%d, error=%s", contract.id, e)
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
    def get_contract_detail(db: Session, contract_id: int) -> Optional[Contract]:
        """获取合同详情（预加载附加项明细，供详情接口 ContractDetailResponse 序列化）。

        与 get_contract 的区别：selectinload(Contract.additional_items) 一次性把附加项
        拉进内存（单合同只 1 条附加查询，无 N+1）。详情页需要附加项明细，列表页不需要，
        因此只在此方法加载。
        """
        return db.query(Contract).options(
            selectinload(Contract.additional_items),
            # 软删过滤：BaseModel 无全局软删过滤，显式注入条件，
            # 让 selectinload 与潜在 lazy load 都排除已软删附加项（修审核 P1 泄漏）
            with_loader_criteria(
                ContractAdditionalItem,
                lambda c: c.is_deleted == False,
            ),
        ).filter(
            Contract.id == contract_id,
            Contract.is_deleted == False
        ).first()

    @staticmethod
    def update_contract(
        db: Session,
        contract_id: int,
        contract_data: ContractUpdate,
        updated_by: Optional[int] = None,
    ) -> Optional[Contract]:
        """更新合同"""
        contract = ContractService.get_contract(db, contract_id)

        if not contract:
            return None

        # 记录旧值用于审计
        old_values = {
            "status": contract.status,
            "wechat_group": contract.wechat_group,
            "remarks": contract.remarks,
            "title": contract.title,
            "business_type": contract.business_type,
        }

        # 更新字段
        update_data = contract_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(contract, field, value)

        db.commit()
        db.refresh(contract)

        # 审计日志
        if updated_by:
            try:
                new_values = {k: v for k, v in update_data.items() if v is not None}
                AuditService.log(
                    db,
                    user_id=updated_by,
                    action="update",
                    entity_type="contract",
                    entity_id=contract_id,
                    old_values=old_values,
                    new_values=new_values,
                )
            except Exception as e:
                logger.warning("审计日志写入失败: entity=contract, action=update, error=%s", e)

        return contract

    @staticmethod
    def delete_contract(db: Session, contract_id: int, user_id: int = None) -> bool:
        """硬删除合同（仅允许无付款记录时），清理物理文件"""
        contract = db.query(Contract).filter(Contract.id == contract_id).first()

        if not contract:
            return False

        # 检查是否有关联付款记录
        payment_count = db.query(Payment).filter(
            Payment.contract_id == contract_id,
            Payment.is_deleted == False,
        ).count()

        if payment_count > 0:
            raise ValueError(f"合同有 {payment_count} 条付款记录，请先删除付款记录")

        deleted_files = []

        # 删除合同物理文件
        if contract.original_file_path:
            contract_path = Path(settings.CONTRACT_UPLOAD_DIR) / contract.original_file_path
            if contract_path.exists():
                contract_path.unlink()
                deleted_files.append(str(contract_path))

        # 硬删除合同
        db.delete(contract)
        db.commit()

        # 审计日志
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
        confidence: float,
        updated_by: Optional[int] = None,
    ) -> Optional[Contract]:
        """更新AI解析的合同数据"""
        contract = ContractService.get_contract(db, contract_id)
        
        if not contract:
            return None
        
        # 记录旧值用于审计
        old_values = {
            "status": contract.status,
            "total_amount": float(contract.total_amount) if contract.total_amount else None,
            "currency": contract.currency,
            "business_type": contract.business_type,
            "business_description": contract.business_description,
        }

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

        # 提取币种（AI 可识别 CNY/HKD）
        if 'currency' in contract_data and contract_data['currency']:
            contract.currency = contract_data['currency']

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
        
        # 写入置信度元数据
        if confidence is not None:
            contract.confidence = round(confidence, 4)
            contract.needs_review = confidence < 0.85
        
        # 解析完成直接设为执行中（人工确认路径，不按置信度分级）
        contract.status = 'active'

        # 所有合同统一维护 _in_cny 字段（CNY 合同为原值，非 CNY 合同按汇率折算）
        if contract.total_amount > 0:
            if contract.currency == "CNY":
                contract.total_amount_in_cny = contract.total_amount
                contract.paid_amount_in_cny = contract.paid_amount_in_cny or 0
                contract.remaining_amount_in_cny = (contract.total_amount_in_cny or 0) - (contract.paid_amount_in_cny or 0)
                logger.info("AI解析后CNY等值: contract_id=%d, CNY 1:1, amount=%s", contract.id, contract.total_amount)
            else:
                rate_date = contract.signed_date or date.today()
                try:
                    exchange_rate, total_in_cny = ExchangeRateService.convert_to_cny(
                        db, contract.total_amount, contract.currency, rate_date
                    )
                    contract.total_amount_in_cny = total_in_cny
                    contract.paid_amount_in_cny = contract.paid_amount_in_cny or 0
                    contract.remaining_amount_in_cny = (contract.total_amount_in_cny or 0) - (contract.paid_amount_in_cny or 0)
                    logger.info(
                        "AI解析后重算CNY等值: contract_id=%d, %s %s → %s CNY (汇率=%s)",
                        contract.id, contract.total_amount, contract.currency,
                        total_in_cny, exchange_rate,
                    )
                except Exception as e:
                    logger.warning("AI解析后CNY等值计算失败: contract_id=%d, error=%s", contract.id, e)

        db.commit()
        db.refresh(contract)

        # 审计日志
        if updated_by:
            try:
                new_values = {
                    "status": contract.status,
                    "total_amount": float(contract.total_amount) if contract.total_amount else None,
                    "currency": contract.currency,
                    "business_type": contract.business_type,
                    "confidence": contract.confidence,
                }
                AuditService.log(
                    db,
                    user_id=updated_by,
                    action="update_data",
                    entity_type="contract",
                    entity_id=contract_id,
                    old_values=old_values,
                    new_values=new_values,
                )
            except Exception as e:
                logger.warning("审计日志写入失败: entity=contract, action=update_data, error=%s", e)
        
        return contract
