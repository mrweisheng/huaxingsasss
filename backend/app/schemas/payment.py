"""
付款相关Pydantic模型
"""
from typing import Optional
from pydantic import BaseModel, Field
from datetime import date, datetime
from decimal import Decimal


class PaymentBase(BaseModel):
    """付款基础模型"""

    installment_number: int = Field(..., ge=1, description="期数")
    installment_name: Optional[str] = Field(None, max_length=100, description="期数名称")
    type: str = Field(default="income", description="类型: income/expense")
    currency: str = Field(default="CNY", description="付款币种")
    amount: Decimal = Field(..., gt=0, description="金额")
    due_date: Optional[date] = Field(None, description="应付款日期")
    paid_date: Optional[date] = Field(None, description="实际付款日期")
    payment_method: Optional[str] = Field(None, description="付款方式")
    payee_name: Optional[str] = Field(None, max_length=200, description="收款方（仅expense）")
    notes: Optional[str] = Field(None, description="备注")


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
    contract_business_description: Optional[str] = None
    contract_currency: Optional[str] = None  # 合同主币种（前端据此判断是否异币种展示）
    description: Optional[str] = None
    paid_amount: Decimal
    exchange_rate: Optional[Decimal]
    amount_in_cny: Optional[Decimal]
    paid_amount_in_cny: Optional[Decimal]
    receipt_image_path: Optional[str]
    receipt_data: Optional[dict] = None
    additional_receipt_files: Optional[list[dict]] = None
    additional_item_id: Optional[int] = None
    status: str
    source: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
