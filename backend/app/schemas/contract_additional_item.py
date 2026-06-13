"""
合同附加项 Pydantic 模型
"""
from typing import Optional
from pydantic import BaseModel, Field
from datetime import date, datetime
from decimal import Decimal


class AdditionalItemBase(BaseModel):
    """附加项基础模型"""

    name: str = Field(..., max_length=200, description="项目名称（车险/保养改装/人工费）")
    amount: Decimal = Field(..., ge=0, description="金额")
    currency: str = Field(default="CNY", max_length=3, description="币种: CNY/HKD")
    paid_to: Optional[str] = Field(None, max_length=200, description="付给谁（保险公司/修理厂）")
    description: Optional[str] = Field(None, description="用途说明")
    occurred_date: Optional[date] = Field(None, description="发生日期，备查用")
    remarks: Optional[str] = Field(None, description="业务备注")


class AdditionalItemCreate(AdditionalItemBase):
    """创建附加项"""

    contract_id: int = Field(..., description="合同ID")


class AdditionalItemUpdate(BaseModel):
    """更新附加项（所有字段可选）"""

    name: Optional[str] = Field(None, max_length=200)
    amount: Optional[Decimal] = Field(None, ge=0)
    currency: Optional[str] = Field(None, max_length=3)
    paid_to: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = None
    occurred_date: Optional[date] = None
    remarks: Optional[str] = None


class AdditionalItemResponse(AdditionalItemBase):
    """附加项响应"""

    id: int
    contract_id: int
    created_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
