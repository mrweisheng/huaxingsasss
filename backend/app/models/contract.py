"""
合同模型
"""
from sqlalchemy import Column, String, Text, Integer, Boolean, ForeignKey, DECIMAL, Date, JSON, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class Contract(BaseModel):
    """合同表"""
    
    __tablename__ = "contracts"
    
    # 合同基本信息
    contract_number = Column(String(50), unique=True, nullable=False, index=True, comment="合同编号")
    title = Column(String(500), comment="合同标题")
    
    # 关联关系
    customer_id = Column(Integer, ForeignKey("customers.id", ondelete="RESTRICT"), index=True, comment="客户ID（可为空，解析后关联）")
    sales_person_id = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True, comment="业务员ID")
    
    # 金额相关（支持多币种）
    currency = Column(String(3), nullable=False, default="CNY", comment="合同币种: CNY/HKD/USD")
    total_amount = Column(DECIMAL(15, 2), nullable=False, default=0, comment="合同总金额")
    paid_amount = Column(DECIMAL(15, 2), nullable=False, default=0, comment="已付金额")
    remaining_amount = Column(DECIMAL(15, 2), server_default="total_amount - paid_amount", comment="剩余金额")
    
    # 折算CNY金额
    total_amount_in_cny = Column(DECIMAL(15, 2), comment="合同总额折算CNY")
    paid_amount_in_cny = Column(DECIMAL(15, 2), default=0, comment="已付金额折算CNY")
    remaining_amount_in_cny = Column(DECIMAL(15, 2), server_default="COALESCE(total_amount_in_cny, 0) - paid_amount_in_cny", comment="剩余尾款折算CNY")
    
    # 合同文件
    original_file_path = Column(String(500), nullable=False, comment="原始合同文件路径")
    file_hash = Column(String(64), index=True, comment="文件SHA256哈希")
    
    # AI解析的结构化数据
    contract_data = Column(JSONB, nullable=False, server_default="'{}'", comment="AI解析的结构化数据")
    
    # AI解析元数据
    confidence = Column(DECIMAL(5, 4), comment="AI解析置信度")
    needs_review = Column(Boolean, default=False, comment="是否需要人工审核")

    # 合同状态
    status = Column(String(20), nullable=False, default="draft", index=True, comment="状态: draft/pending_review/active/completed/cancelled/disputed")
    
    # 时间字段
    signed_date = Column(Date, index=True, comment="签订日期")
    start_date = Column(Date, comment="生效日期")
    end_date = Column(Date, comment="到期日期")
    
    # 备注
    remarks = Column(Text, comment="备注")
    
    # 审计
    created_by = Column(Integer, ForeignKey("users.id"), comment="创建者ID")
    
    # 关系
    customer = relationship("Customer", back_populates="contracts")
    payments = relationship("Payment", back_populates="contract", cascade="all, delete-orphan")
    
    # 索引
    __table_args__ = (
        Index("idx_contracts_customer", "customer_id"),
        Index("idx_contracts_sales", "sales_person_id"),
        Index("idx_contracts_status", "status"),
        Index("idx_contracts_signed_date", "signed_date"),
        Index("idx_contracts_contract_number", "contract_number"),
        Index("idx_contracts_file_hash", "file_hash"),
        Index("idx_contracts_data_gin", "contract_data", postgresql_using="gin"),
    )
