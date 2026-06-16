"""
收款账户 Schema
"""
from typing import Optional, Any
from pydantic import BaseModel, Field
from datetime import datetime


class PaymentAccountCreate(BaseModel):
    """创建收款账户请求"""
    account_type: str = Field(..., pattern="^(bank|alipay|wechat|cash|other)$", description="账户类型")
    title: str = Field(..., max_length=200, description="展示标题")
    account_name: str = Field(..., max_length=200, description="户名")
    account_number: Optional[str] = Field(None, max_length=100, description="账号")
    qr_code_url: Optional[str] = Field(None, max_length=500, description="收款码URL")
    fps_id: Optional[str] = Field(None, max_length=50, description="转数快 FPS ID")
    bank_name: Optional[str] = Field(None, max_length=100, description="银行名称")
    branch: Optional[str] = Field(None, max_length=200, description="网点")
    address: Optional[str] = Field(None, max_length=500, description="地址")
    phone: Optional[str] = Field(None, max_length=50, description="电话")
    swift_code: Optional[str] = Field(None, max_length=50, description="SWIFT Code")
    extra_info: Optional[dict] = Field(None, description="扩展信息")
    is_default: bool = Field(False, description="是否默认")
    sort_order: int = Field(0, description="排序")


class PaymentAccountResponse(BaseModel):
    """收款账户响应"""
    id: int
    account_type: str
    title: str
    account_name: str
    account_number: Optional[str] = None
    qr_code_url: Optional[str] = None
    fps_id: Optional[str] = None
    bank_name: Optional[str] = None
    branch: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    swift_code: Optional[str] = None
    extra_info: Optional[dict] = None
    is_default: bool = False
    sort_order: int = 0
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
