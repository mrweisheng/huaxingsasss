"""
合同附加项模型

附加项 = 合同应收清单上的一行（车险 / 保养改装 / 人工费等），
不是独立的财务实体：没有「已收/未收」概念，付款不强制归属。
"""
from sqlalchemy import Column, String, Text, Integer, ForeignKey, DECIMAL, Date, Index
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class ContractAdditionalItem(BaseModel):
    """合同附加项表"""

    __tablename__ = "contract_additional_items"

    # 关联合同
    contract_id = Column(Integer, ForeignKey("contracts.id", ondelete="RESTRICT"), nullable=False, index=True, comment="合同ID")

    # 项目内容
    name = Column(String(200), nullable=False, comment="项目名称（车险/保养改装/人工费）")
    amount = Column(DECIMAL(15, 2), nullable=False, comment="金额")
    currency = Column(String(3), nullable=False, default="CNY", comment="币种: CNY/HKD")
    paid_to = Column(String(200), comment="付给谁（保险公司/修理厂）")
    description = Column(Text, comment="用途说明")
    occurred_date = Column(Date, comment="发生日期，备查用")
    remarks = Column(Text, comment="业务备注")

    # 审计
    created_by = Column(Integer, ForeignKey("users.id"), comment="创建者ID")

    # 关系
    contract = relationship("Contract", back_populates="additional_items")

    __table_args__ = (
        Index("idx_addl_items_contract", "contract_id"),
    )
