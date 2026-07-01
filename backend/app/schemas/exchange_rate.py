"""
汇率相关Pydantic模型
"""
from typing import Optional
from pydantic import BaseModel, Field
from datetime import date, datetime
from decimal import Decimal


class ExchangeRateBase(BaseModel):
    """汇率基础模型"""
    
    from_currency: str = Field(..., max_length=3, description="源币种")
    to_currency: str = Field(default="CNY", max_length=3, description="目标币种")
    rate: Decimal = Field(..., gt=0, description="汇率值")
    rate_date: date = Field(..., description="汇率日期")
    source: str = Field(default="manual", description="来源")
    remarks: Optional[str] = Field(None, max_length=500, description="备注")


class ExchangeRateCreate(ExchangeRateBase):
    """创建汇率"""
    pass


class ExchangeRateResponse(ExchangeRateBase):
    """汇率响应"""
    
    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True
