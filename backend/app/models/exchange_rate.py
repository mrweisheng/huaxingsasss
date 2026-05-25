"""
汇率模型
"""
from sqlalchemy import Column, String, Text, DECIMAL, Date, Boolean, Integer, ForeignKey, Index, UniqueConstraint
from app.models.base import BaseModel


class ExchangeRate(BaseModel):
    """汇率表"""
    
    __tablename__ = "exchange_rates"
    
    # 汇率信息
    from_currency = Column(String(3), nullable=False, index=True, comment="源币种")
    to_currency = Column(String(3), nullable=False, default="CNY", comment="目标币种")
    rate = Column(DECIMAL(10, 6), nullable=False, comment="汇率值")
    
    # 汇率日期
    rate_date = Column(Date, nullable=False, index=True, comment="汇率生效日期")
    
    # 数据来源
    source = Column(String(20), default="manual", comment="来源: manual/api/system")
    
    # 是否启用
    is_active = Column(Boolean, default=True, index=True, comment="是否启用")
    
    # 备注
    remarks = Column(Text, comment="备注")
    
    # 审计
    created_by = Column(Integer, ForeignKey("users.id"), comment="创建者ID")
    
    # 索引和约束
    __table_args__ = (
        Index("idx_exchange_rates_currencies", "from_currency", "to_currency"),
        Index("idx_exchange_rates_date", "rate_date"),
        Index("idx_exchange_rates_active", "is_active"),
        UniqueConstraint("from_currency", "to_currency", "rate_date", name="uq_currency_date"),
    )
