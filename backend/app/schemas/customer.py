"""
客户相关Pydantic模型
"""
from typing import Optional
from pydantic import BaseModel, EmailStr, Field
from datetime import datetime


class CustomerBase(BaseModel):
    """客户基础模型"""

    name: str = Field(..., max_length=200, description="客户名称")
    contact_person: Optional[str] = Field(None, max_length=100, description="联系人")
    phone: Optional[str] = Field(None, max_length=20, description="联系电话")
    email: Optional[EmailStr] = Field(None, description="联系邮箱")
    id_card_number: Optional[str] = Field(None, description="身份证号（加密存储）")
    business_license: Optional[str] = Field(None, max_length=50, description="营业执照号")
    address: Optional[str] = Field(None, description="地址")
    wechat_group_name: Optional[str] = Field(None, max_length=200, description="微信群名称")
    remarks: Optional[str] = Field(None, description="备注")


class CustomerUpdate(BaseModel):
    """更新客户"""

    name: Optional[str] = Field(None, max_length=200)
    contact_person: Optional[str] = Field(None, max_length=100)
    phone: Optional[str] = Field(None, max_length=20)
    email: Optional[EmailStr] = None
    id_card_number: Optional[str] = None
    business_license: Optional[str] = Field(None, max_length=50)
    address: Optional[str] = None
    wechat_group_name: Optional[str] = Field(None, max_length=200)
    remarks: Optional[str] = None


class CustomerResponse(CustomerBase):
    """客户响应"""
    
    id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True
