"""
付款相关Pydantic模型
"""
from typing import Optional, List
from pydantic import BaseModel, Field
from datetime import date, datetime
from decimal import Decimal


class PaymentBase(BaseModel):
    """付款基础模型"""

    installment_number: int = Field(..., ge=1, description="期数")
    installment_name: Optional[str] = Field(None, max_length=50, description="期数名称")
    type: str = Field(default="income", description="类型: income/expense")
    currency: str = Field(default="CNY", description="付款币种")
    amount: Decimal = Field(..., gt=0, description="金额")
    due_date: Optional[date] = Field(None, description="应付款日期")
    paid_date: Optional[date] = Field(None, description="实际付款日期")
    payment_method: Optional[str] = Field(None, description="付款方式")
    payee_name: Optional[str] = Field(None, max_length=200, description="收款方（仅expense）")
    notes: Optional[str] = Field(None, description="备注")


class PaymentCreate(PaymentBase):
    """创建付款"""
    
    contract_id: int = Field(..., description="合同ID")
    receipt_image_path: Optional[str] = Field(None, description="凭证图片路径")


class PaymentUpdate(BaseModel):
    """更新付款"""

    paid_amount: Optional[Decimal] = Field(None, ge=0)
    paid_date: Optional[date] = None
    status: Optional[str] = None
    notes: Optional[str] = None
    payment_method: Optional[str] = None
    receipt_image_path: Optional[str] = None
    receipt_data: Optional[dict] = None
    installment_name: Optional[str] = None


class PaymentResponse(PaymentBase):
    """付款响应"""

    id: int
    contract_id: int
    contract_number: Optional[str] = None
    customer_name: Optional[str] = None
    description: Optional[str] = None
    paid_amount: Decimal
    exchange_rate: Optional[Decimal]
    amount_in_cny: Optional[Decimal]
    paid_amount_in_cny: Optional[Decimal]
    receipt_image_path: Optional[str]
    receipt_data: Optional[dict] = None
    status: str
    source: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class PaymentPlanItem(BaseModel):
    """付款计划单期"""

    installment_number: int = Field(..., ge=1, description="期数序号")
    installment_name: str = Field(..., max_length=50, description="期数名称")
    amount: Decimal = Field(..., gt=0, description="应付金额")
    due_date: Optional[date] = Field(None, description="应付款日期")


class PaymentPlanCreate(BaseModel):
    """创建付款计划"""

    installments: list[PaymentPlanItem] = Field(..., min_length=1, description="付款期数列表")
