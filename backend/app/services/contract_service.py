"""
合同服务层
"""
import logging
import os
import shutil
import uuid
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Optional, List, Dict, Any

from sqlalchemy import or_, func, String
from sqlalchemy.orm import Session, contains_eager, selectinload

from app.config import settings
from app.core.chinese import search_variants
from app.models.contract import Contract
from app.models.customer import Customer
from app.models.payment import Payment
from app.schemas.contract import ContractCreate, ContractUpdate
from app.services.audit_service import AuditService
from app.utils.file_analysis import guess_extension
from app.utils.file_utils import calculate_file_hash, resolve_file_path

logger = logging.getLogger(__name__)


class ContractService:

    @staticmethod
    def generate_contract_number() -> str:
        """自动生成唯一合同编号: HT + 时间戳 + 4位随机"""
        return f"HT{datetime.now().strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:4].upper()}"
    """合同服务类"""

    @staticmethod
    def _load_currency_aggregates(
        db: Session,
        contract_ids: List[int],
    ) -> Dict[int, Dict[str, Any]]:
        """按 contract_id 一次性查出：
        - paid_by_currency / expense_by_currency：按币种分桶累加 paid_amount（仅 status='paid'）
        - outstanding_amount / outstanding_currency：取该合同最新一笔 income payment 的 outstanding 快照

        Returns:
            {contract_id: {
                "paid_by_currency": {"HKD": 150000, "CNY": 20000},
                "expense_by_currency": {"HKD": 30000},
                "outstanding_amount": Decimal("60000") | None,
                "outstanding_currency": "HKD" | None,
            }}
        """
        result: Dict[int, Dict[str, Any]] = {
            cid: {
                "paid_by_currency": {},
                "expense_by_currency": {},
                "outstanding_amount": None,
                "outstanding_currency": None,
            }
            for cid in contract_ids
        }
        if not contract_ids:
            return result

        # 1. 按币种分桶累加 paid_amount
        rows = (
            db.query(
                Payment.contract_id,
                Payment.type,
                Payment.currency,
                func.sum(Payment.paid_amount).label("total"),
            )
            .filter(
                Payment.contract_id.in_(contract_ids),
                Payment.is_deleted == False,
                Payment.status == "paid",
            )
            .group_by(Payment.contract_id, Payment.type, Payment.currency)
            .all()
        )
        for r in rows:
            bucket_key = "paid_by_currency" if r.type == "income" else "expense_by_currency"
            if r.contract_id in result and r.currency:
                result[r.contract_id][bucket_key][r.currency] = float(r.total or 0)

        # 2. 最新一笔 income payment 的 outstanding 快照
        # 用 paid_date DESC, id DESC 排序，每个 contract_id 取第一条非空
        latest_outstandings = (
            db.query(
                Payment.contract_id,
                Payment.outstanding_amount,
                Payment.outstanding_currency,
                Payment.paid_date,
                Payment.id,
            )
            .filter(
                Payment.contract_id.in_(contract_ids),
                Payment.is_deleted == False,
                Payment.type == "income",
                Payment.outstanding_amount.isnot(None),
            )
            .order_by(
                Payment.contract_id,
                Payment.paid_date.desc().nullslast(),
                Payment.id.desc(),
            )
            .all()
        )
        # Python 端取每个 contract_id 的第一条（即最新）
        for row in latest_outstandings:
            entry = result.get(row.contract_id)
            if entry and entry["outstanding_amount"] is None:
                entry["outstanding_amount"] = row.outstanding_amount
                entry["outstanding_currency"] = row.outstanding_currency

        return result

    @staticmethod
    def _attach_aggregates(contract: Contract, agg: Dict[str, Any]) -> None:
        """把按币种字典 + outstanding 挂到合同对象上（pydantic from_attributes 序列化用）。"""
        contract.paid_by_currency = agg.get("paid_by_currency") or {}
        contract.expense_by_currency = agg.get("expense_by_currency") or {}
        contract.outstanding_amount = agg.get("outstanding_amount")
        contract.outstanding_currency = agg.get("outstanding_currency")

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
            # 按币种聚合 + 最新尾款（替代旧的 _in_cny 换算字段）
            aggregates_map = ContractService._load_currency_aggregates(db, contract_ids)
        else:
            stats_map = {}
            aggregates_map = {}

        for item in items:
            if item.customer:
                item.customer_name = item.customer.name
            else:
                item.customer_name = None
            stats = stats_map.get(item.id)
            item.paid_count = stats.paid_count if stats else 0
            item.expense_count = stats.expense_count if stats else 0
            item.payment_total_count = stats.total_count if stats else 0
            ContractService._attach_aggregates(item, aggregates_map.get(item.id, {}))
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

        return contract

    @staticmethod
    def _write_ai_meta(
        contract: Contract,
        contract_data: Dict[str, Any],
        contract_text: Optional[str],
        confidence: Optional[float],
    ) -> None:
        """把 AI 解析的 contract_data / contract_text / confidence 写到合同对象上（不 commit）。

        纯赋值辅助方法，被 persist_contract_file_and_meta（文件复制成功路径）与
        Agent 降级路径（文件不存在但仍建合同）共用，避免 meta 写入逻辑漂移。
        contract_data 应由调用方提前包装好 source/file_id 等追溯字段。
        """
        contract.contract_data = contract_data
        contract.contract_text = contract_text or (contract_data or {}).get("full_text")
        if confidence is not None:
            try:
                conf = float(confidence)
                contract.confidence = round(conf, 4)
                contract.needs_review = conf < 0.85
            except (TypeError, ValueError):
                pass

    @staticmethod
    def persist_contract_file_and_meta(
        db: Session,
        contract: Contract,
        file_id: str,
        user_id: int,
        contract_data: Dict[str, Any],
        contract_text: Optional[str],
        confidence: Optional[float],
        source: str = "form",
        file_hash_hint: Optional[str] = None,
    ) -> Contract:
        """复制源文件到合同正式目录 + 写入 AI 解析元数据。

        Agent 通道（tool_executor_base.create_contract）与表单通道（POST /contracts）
        共用本方法，避免文件复制/去重/meta 写入逻辑漂移。

        Args:
            contract: 已通过 create_contract 建好的合同主记录（contract_number 已生成）
            file_id: 上传接口返回的文件ID（用于 resolve_file_path 定位 agent 上传目录的源文件）
            user_id: 当前用户ID（resolve_file_path 需按用户隔离目录查找）
            contract_data: AI 结构化解析结果，落 contract.contract_data
            contract_text: 合同全文；为 None 时回退 contract_data['full_text']
            confidence: 置信度；<0.85 自动 needs_review=True
            source: 数据来源标记，'agent' / 'form'，写入 contract_data.source 便于审计追溯
            file_hash_hint: 调用方已算过的文件 hash（Agent 侧有 _file_hash_cache），避免重复读大文件；
                            None 则本方法自行计算

        Raises:
            FileNotFoundError: 源文件不存在 / 已过期（resolve_file_path 返回 None）
            ValueError: hash 命中已有合同（去重拦截）；此时调用方应回滚已建的 contract
        """
        # 1. 定位源文件（resolve_file_path 内含路径穿越防御）
        temp_file_path = resolve_file_path(file_id, user_id)
        if not temp_file_path or not os.path.exists(temp_file_path):
            raise FileNotFoundError(f"合同源文件不存在或已过期: file_id={file_id}")

        # 2. 计算 hash（优先用调用方传入的，避免重复读大文件）
        with open(temp_file_path, "rb") as f:
            content = f.read()
        file_hash = file_hash_hint or calculate_file_hash(content)

        # 3. hash 去重：排除自身（contract 已先建，避免把自己判重）
        existing = db.query(Contract).filter(
            Contract.file_hash == file_hash,
            Contract.is_deleted == False,
            Contract.id != contract.id,
        ).first()
        if existing:
            raise ValueError(
                f"该文件已创建过合同（编号: {existing.contract_number}, ID: {existing.id}）"
            )

        # 4. 复制到正式合同目录：CONTRACT_UPLOAD_DIR/{年月}/{合同编号}{扩展名}
        #    （与改造前 Agent 侧行为完全一致，路径形如 "2026/06/HT20260629123456ABCDEF.pdf"）
        year_month = datetime.now().strftime("%Y/%m")
        target_dir = Path(settings.CONTRACT_UPLOAD_DIR) / year_month
        target_dir.mkdir(parents=True, exist_ok=True)
        ext = guess_extension(content)
        target_filename = f"{contract.contract_number}{ext}"
        target_path = target_dir / target_filename
        shutil.copy2(temp_file_path, str(target_path))

        # 5. 写入文件路径 + hash + AI 元数据（meta 赋值委托 _write_ai_meta）
        contract.original_file_path = str(Path(year_month) / target_filename)
        contract.file_hash = file_hash
        ContractService._write_ai_meta(
            contract,
            {"source": source, "file_id": file_id, **(contract_data or {})},
            contract_text,
            confidence,
        )

        db.commit()
        db.refresh(contract)
        return contract

    @staticmethod
    def get_contract(db: Session, contract_id: int) -> Optional[Contract]:
        """获取合同详情（排除已软删除）"""
        contract = db.query(Contract).filter(
            Contract.id == contract_id,
            Contract.is_deleted == False
        ).first()
        if contract:
            aggregates = ContractService._load_currency_aggregates(db, [contract.id])
            ContractService._attach_aggregates(contract, aggregates.get(contract.id, {}))
        return contract

    @staticmethod
    def get_contract_detail(db: Session, contract_id: int) -> Optional[Contract]:
        """获取合同详情。

        附加项功能已下线后，详情接口与 get_contract 等价，保留独立入口便于未来按需扩展。
        """
        return ContractService.get_contract(db, contract_id)

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
        """硬删除合同及其所有关联付款记录，清理物理文件（原子操作）"""
        contract = db.query(Contract).filter(Contract.id == contract_id).first()

        if not contract:
            return False

        deleted_files = []

        # 1. 级联删除所有关联付款记录（含凭证文件）
        payments = db.query(Payment).filter(
            Payment.contract_id == contract_id,
            Payment.is_deleted == False,
        ).all()

        for payment in payments:
            if payment.receipt_image_path:
                receipt_path = Path(settings.RECEIPT_UPLOAD_DIR) / payment.receipt_image_path
                if receipt_path.exists():
                    receipt_path.unlink()
                    deleted_files.append(str(receipt_path))
            db.delete(payment)

        # 2. 删除合同物理文件
        if contract.original_file_path:
            contract_path = Path(settings.CONTRACT_UPLOAD_DIR) / contract.original_file_path
            if contract_path.exists():
                contract_path.unlink()
                deleted_files.append(str(contract_path))

        # 3. 硬删除合同
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
                    "cascade_deleted_payments": len(payments),
                    "deleted_files": deleted_files,
                },
            )

        logger.info("合同已删除: id=%d, number=%s, 级联删除付款=%d, 清理文件=%d",
                     contract_id, contract.contract_number, len(payments), len(deleted_files))
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
