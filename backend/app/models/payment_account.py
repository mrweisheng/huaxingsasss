"""
收款账户模型
"""
from sqlalchemy import Column, String, Text, Integer, Boolean
from app.models.base import BaseModel


class PaymentAccount(BaseModel):
    """收款账户表"""
    
    __tablename__ = "payment_accounts"
    
    bank_name = Column(String(100), nullable=False, comment="银行名称")
    account_name = Column(String(200), nullable=False, comment="户名")
    account_number = Column(String(100), comment="银行账号")
    fps_id = Column(String(50), comment="转数快 FPS ID")
    branch = Column(String(200), comment="网点")
    address = Column(String(500), comment="地址")
    phone = Column(String(50), comment="电话")
    swift_code = Column(String(50), comment="SWIFT Code")
    is_default = Column(Boolean, default=False, comment="是否默认收款账户")
    sort_order = Column(Integer, default=0, comment="排序")
    remarks = Column(Text, comment="备注")
    created_by = Column(Integer, comment="创建者ID")
    
    __allow_unmapped__ = True
