"""
收款账户 Schema
"""
from typing import Optional
from pydantic import BaseModel, Field
from datetime import datetime


class PaymentAccountCreate(BaseModel):
    """创建收款账户请求"""
    name: str = Field(..., max_length=200, description="账户名称")
    account_type: str = Field(..., pattern="^(bank|alipay|wechat|other)$", description="账户类型")
    bank_name: Optional[str] = Field(None, max_length=100, description="银行/平台名称")
    account_name: str = Field(..., max_length=200, description="户名")
    account_number: Optional[str] = Field(None, max_length=100, description="账号")
    branch: Optional[str] = Field(None, max_length=200, description="网点")
    address: Optional[str] = Field(None, max_length=500, description="地址")
    phone: Optional[str] = Field(None, max_length=50, description="电话")
    swift_code: Optional[str] = Field(None, max_length=50, description="SWIFT Code")
    fps_id: Optional[str] = Field(None, max_length=50, description="转数快FPS ID")
    qr_code_url: Optional[str] = Field(None, max_length=500, description="收款二维码URL")
    is_default: bool = Field(False, description="是否默认收款账户")
    sort_order: int = Field(0, description="排序序号")
    remarks: Optional[str] = Field(None, description="备注")


class PaymentAccountUpdate(BaseModel):
    """更新收款账户请求"""
    name: Optional[str] = Field(None, max_length=200, description="账户名称")
    account_type: Optional[str] = Field(None, pattern="^(bank|alipay|wechat|other)$", description="账户类型")
    bank_name: Optional[str] = Field(None, max_length=100, description="银行/平台名称")
    account_name: Optional[str] = Field(None, max_length=200, description="户名")
    account_number: Optional[str] = Field(None, max_length=100, description="账号")
    branch: Optional[str] = Field(None, max_length=200, description="网点")
    address: Optional[str] = Field(None, max_length=500, description="地址")
    phone: Optional[str] = Field(None, max_length=50, description="电话")
    swift_code: Optional[str] = Field(None, max_length=50, description="SWIFT Code")
    fps_id: Optional[str] = Field(None, max_length=50, description="转数快FPS ID")
    qr_code_url: Optional[str] = Field(None, max_length=500, description="收款二维码URL")
    is_default: Optional[bool] = Field(None, description="是否默认收款账户")
    sort_order: Optional[int] = Field(None, description="排序序号")
    remarks: Optional[str] = Field(None, description="备注")


class PaymentAccountResponse(BaseModel):
    """收款账户响应"""
    id: int
    name: str
    account_type: str
    bank_name: Optional[str] = None
    account_name: str
    account_number: Optional[str] = None
    branch: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    swift_code: Optional[str] = None
    fps_id: Optional[str] = None
    qr_code_url: Optional[str] = None
    is_default: bool = False
    sort_order: int = 0
    remarks: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
