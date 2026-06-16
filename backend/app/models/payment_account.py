"""
收款账户模型
"""
from sqlalchemy import Column, String, Text, Integer, Boolean, JSON
from app.models.base import BaseModel


class PaymentAccount(BaseModel):
    """收款账户表（支持银行/支付宝/微信等多种类型）"""
    
    __tablename__ = "payment_accounts"
    
    account_type = Column(String(20), nullable=False, index=True, comment="账户类型: bank/alipay/wechat/cash/other")
    title = Column(String(200), nullable=False, comment="展示标题")
    account_name = Column(String(200), nullable=False, comment="户名")
    account_number = Column(String(100), comment="账号")
    qr_code_url = Column(String(500), comment="收款码图片URL")
    fps_id = Column(String(50), comment="转数快 FPS ID")
    bank_name = Column(String(100), comment="银行名称")
    branch = Column(String(200), comment="网点")
    address = Column(String(500), comment="地址")
    phone = Column(String(50), comment="电话")
    swift_code = Column(String(50), comment="SWIFT Code")
    extra_info = Column(JSON, default={}, comment="扩展信息")
    is_default = Column(Boolean, default=False, comment="是否默认")
    sort_order = Column(Integer, default=0, comment="排序")
    created_by = Column(Integer, comment="创建者ID")
    
    __allow_unmapped__ = True
