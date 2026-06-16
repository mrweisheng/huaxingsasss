"""
收款账户模型
"""
from sqlalchemy import Column, String, Text, Integer, Boolean, Index
from app.models.base import BaseModel


class PaymentAccount(BaseModel):
    """收款账户表"""
    
    __tablename__ = "payment_accounts"
    
    name = Column(String(200), nullable=False, comment="账户名称（展示用，如：高山贸易有限公司-华侨银行）")
    account_type = Column(String(20), nullable=False, index=True, comment="账户类型: bank/alipay/wechat/other")
    bank_name = Column(String(100), comment="银行/平台名称")
    account_name = Column(String(200), nullable=False, comment="户名")
    account_number = Column(String(100), comment="账号")
    branch = Column(String(200), comment="网点")
    address = Column(String(500), comment="地址")
    phone = Column(String(50), comment="电话")
    swift_code = Column(String(50), comment="SWIFT Code")
    fps_id = Column(String(50), comment="转数快FPS ID")
    qr_code_url = Column(String(500), comment="收款二维码URL")
    is_default = Column(Boolean, default=False, comment="是否默认收款账户")
    sort_order = Column(Integer, default=0, comment="排序序号")
    remarks = Column(Text, comment="备注")
    
    created_by = Column(Integer, comment="创建者ID")
    
    __allow_unmapped__ = True
    
    __table_args__ = (
        Index("idx_payment_accounts_type", "account_type", postgresql_where="is_deleted = FALSE"),
        Index("idx_payment_accounts_default", "is_default", postgresql_where="is_default = TRUE AND is_deleted = FALSE"),
    )
