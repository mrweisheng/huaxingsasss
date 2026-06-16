"""
付款模型
"""
from sqlalchemy import Column, String, Text, Integer, ForeignKey, DECIMAL, Date, DateTime, Index, UniqueConstraint, text, JSON
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class Payment(BaseModel):
    """付款表"""
    
    __tablename__ = "payments"
    
    # 关联合同
    contract_id = Column(Integer, ForeignKey("contracts.id", ondelete="RESTRICT"), nullable=False, index=True, comment="合同ID")
    
    # 付款期数信息
    installment_number = Column(Integer, nullable=False, comment="第几期")
    installment_name = Column(String(100), comment="期数名称")

    # 收入/支出类型
    type = Column(String(20), nullable=False, default="income", index=True, comment="类型: income/expense")
    
    # 金额与币种（支持多币种）
    currency = Column(String(3), nullable=False, default="CNY", index=True, comment="付款币种: CNY/HKD")
    amount = Column(DECIMAL(15, 2), nullable=False, comment="本期应付金额")
    paid_amount = Column(DECIMAL(15, 2), default=0, comment="实际已付金额")
    
    # 汇率结算
    exchange_rate = Column(DECIMAL(10, 6), comment="使用的汇率")
    amount_in_cny = Column(DECIMAL(15, 2), comment="折算CNY金额")
    paid_amount_in_cny = Column(DECIMAL(15, 2), comment="已付折算CNY")
    
    # 时间
    due_date = Column(Date, index=True, comment="应付款日期")
    paid_date = Column(Date, index=True, comment="实际付款日期")
    
    # 付款凭证
    receipt_image_path = Column(String(500), comment="付款凭证图片路径")
    receipt_file_hash = Column(String(64), comment="凭证文件哈希")
    receipt_ocr_text = Column(Text, comment="OCR识别的文本内容")
    receipt_data = Column(JSON, comment="凭证分析结构化数据（银行转账/微信/支付宝/收据等）")
    additional_receipt_files = Column(JSON, comment="补充凭证文件列表 [{file_path, file_hash, receipt_data}]")

    # 付款方式
    payment_method = Column(String(20), comment="付款方式: bank_transfer/wechat/alipay/cash/check")

    # 收款方（仅支出使用）
    payee_name = Column(String(200), comment="收款方名称（仅expense使用）")

    # 收款账户（仅收入使用，关联己方预设账户 payment_accounts）
    payment_account_id = Column(Integer, ForeignKey("payment_accounts.id", ondelete="SET NULL"), comment="收款账户ID（仅income使用）")

    # 对方收款账户（仅支出使用，供应商不固定，存JSON不求建表）
    counterparty_account = Column(JSON, comment="对方收款账户（仅expense使用）{account_name, account_number, bank_name, branch}")

    # 状态
    status = Column(String(20), nullable=False, default="pending", index=True, comment="状态: pending(待确认)/paid(已确认)")

    # 凭证校验状态（独立于结算状态 status，避免二义性）
    # pending(校验中)/passed(通过)/failed(不符)/null(未触发校验，如支出无凭证)
    verification_status = Column(String(20), comment="凭证校验状态: pending/passed/failed")
    verification_result = Column(JSON, comment="校验明细 {expected, extracted, match:{amount,payer}, confidence, reason}")
    verified_at = Column(DateTime(timezone=True), comment="凭证校验完成时间")

    # 来源标记
    source = Column(String(20), default="manual", index=True, comment="来源: manual/screenshot/upload")
    
    # 备注
    notes = Column(Text, comment="备注")

    # 自动生成的可读描述
    description = Column(String(500), comment="自动生成的可读描述")

    # 附加项标签（可选，仅展示用，不参与任何金额聚合）
    additional_item_id = Column(Integer, ForeignKey("contract_additional_items.id", ondelete="SET NULL"), comment="附加项标签（可选）：记录这笔付款主要为某项附加项")

    # 审计
    created_by = Column(Integer, ForeignKey("users.id"), comment="创建者ID")
    
    # 关系
    contract = relationship("Contract", back_populates="payments")
    payment_account = relationship("PaymentAccount")  # 收款账户（仅income），不反向（避免账户删除影响）

    __allow_unmapped__ = True

    # 动态字段（不存储到数据库，仅用于 API 响应填充）
    customer_name: str = None  # type: ignore[assignment]
    contract_number: str = None  # type: ignore[assignment]
    contract_business_description: str = None  # type: ignore[assignment]
    contract_currency: str = None  # type: ignore[assignment]
    
    # 索引和约束
    __table_args__ = (
        Index("idx_payments_contract", "contract_id"),
        Index("idx_payments_due_date", "due_date"),
        Index("idx_payments_status", "status"),
        Index("idx_payments_verification_status", "verification_status"),
        Index("idx_payments_installment", "contract_id", "installment_number"),
        Index("idx_payments_source", "source"),
        Index("idx_payments_currency", "currency"),
        Index("idx_payments_type", "type"),
        Index("idx_payments_receipt_hash", "contract_id", "receipt_file_hash"),
        UniqueConstraint("contract_id", "installment_number", "type", name="uq_contract_installment_type"),
    )
