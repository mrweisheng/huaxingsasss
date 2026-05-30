"""
付款模型
"""
from sqlalchemy import Column, String, Text, Integer, ForeignKey, DECIMAL, Date, Index, UniqueConstraint, text
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class Payment(BaseModel):
    """付款表"""
    
    __tablename__ = "payments"
    
    # 关联合同
    contract_id = Column(Integer, ForeignKey("contracts.id", ondelete="RESTRICT"), nullable=False, index=True, comment="合同ID")
    
    # 付款期数信息
    installment_number = Column(Integer, nullable=False, comment="第几期")
    installment_name = Column(String(50), comment="期数名称")

    # 收入/支出类型
    type = Column(String(20), nullable=False, default="income", index=True, comment="类型: income/expense")
    
    # 金额与币种（支持多币种）
    currency = Column(String(3), nullable=False, default="CNY", index=True, comment="付款币种: CNY/HKD/USD")
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
    
    # 付款方式
    payment_method = Column(String(20), comment="付款方式: bank_transfer/wechat/alipay/cash/check")

    # 收款方（仅支出使用）
    payee_name = Column(String(200), comment="收款方名称（仅expense使用）")
    
    # 状态
    status = Column(String(20), nullable=False, default="pending", index=True, comment="状态: pending/partial/paid/overdue/cancelled")
    
    # 来源标记
    source = Column(String(20), default="manual", index=True, comment="来源: manual/screenshot/upload")
    
    # 备注
    notes = Column(Text, comment="备注")
    
    # 审计
    created_by = Column(Integer, ForeignKey("users.id"), comment="创建者ID")
    
    # 关系
    contract = relationship("Contract", back_populates="payments")
    
    # 索引和约束
    __table_args__ = (
        Index("idx_payments_contract", "contract_id"),
        Index("idx_payments_due_date", "due_date"),
        Index("idx_payments_status", "status"),
        Index("idx_payments_installment", "contract_id", "installment_number"),
        Index("idx_payments_source", "source"),
        Index("idx_payments_currency", "currency"),
        Index("idx_payments_type", "type"),
        UniqueConstraint("contract_id", "installment_number", "type", name="uq_contract_installment_type"),
    )
