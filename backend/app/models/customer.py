"""
客户模型
"""
from sqlalchemy import Column, String, Text, Integer, ForeignKey, CheckConstraint
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class Customer(BaseModel):
    """客户表"""
    
    __tablename__ = "customers"
    
    name = Column(String(200), nullable=False, index=True, comment="客户名称")
    contact_person = Column(String(100), comment="联系人")
    phone = Column(String(20), index=True, comment="联系电话")
    email = Column(String(100), comment="联系邮箱")
    id_card_number_encrypted = Column(Text, comment="身份证号（加密存储）")
    business_license = Column(String(50), comment="营业执照号")
    address = Column(Text, comment="地址")
    wechat_group_name = Column(String(200), index=True, comment="微信群名称")
    remarks = Column(Text, comment="备注")
    
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), comment="创建者ID")
    
    # 关系
    contracts = relationship("Contract", back_populates="customer")
    
    # 约束
    __table_args__ = (
        CheckConstraint("phone IS NOT NULL OR email IS NOT NULL", name="chk_phone_or_email"),
    )
