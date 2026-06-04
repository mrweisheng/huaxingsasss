"""
付款相关Pydantic模型
"""
from typing import Optional, List
from pydantic import BaseModel, Field, model_validator, ConfigDict
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


# ─── 凭证录入 API Schema ───


class ReceiptAnalysisData(BaseModel):
    """凭证 AI 分析结果的结构化数据，也用于 CreateFromReceiptRequest.receipt_data"""
    amount: Optional[Decimal] = None
    currency: Optional[str] = None
    transaction_date: Optional[str] = None
    payer_name: Optional[str] = None
    payee_name: Optional[str] = None
    payment_method: Optional[str] = None
    confidence: Optional[float] = None
    warnings: list[str] = Field(default_factory=list)

    model_config = ConfigDict(populate_by_name=True)


class PendingMatchItem(BaseModel):
    """待匹配的已有付款记录（仅 income 类型）"""
    payment_id: int
    installment_number: int
    installment_name: Optional[str] = None
    amount: Decimal
    currency: str
    status: str
    score: int
    match_reason: str


class ReceiptAnalyzeResponse(BaseModel):
    """凭证分析 + 匹配结果的响应"""
    analysis: ReceiptAnalysisData
    temp_file_path: str
    pending_matches: list[PendingMatchItem] = []
    existing_payment_count: int
    next_installment_number: int


class CreateFromReceiptRequest(BaseModel):
    """从凭证创建/匹配付款记录的请求"""
    contract_id: int
    payment_type: str  # "income" | "expense"
    temp_file_path: str
    receipt_data: Optional[ReceiptAnalysisData] = None
    match_payment_id: Optional[int] = None
    installment_number: Optional[int] = None
    installment_name: Optional[str] = None
    currency: str
    amount: Decimal
    paid_date: date
    payment_method: Optional[str] = None
    payee_name: Optional[str] = None
    notes: Optional[str] = None

    @model_validator(mode="after")
    def _validate_exclusive_fields(self) -> "CreateFromReceiptRequest":
        """match_payment_id 和 installment_number 互斥，且必须二选一"""
        has_match = self.match_payment_id is not None
        has_inst = self.installment_number is not None
        if has_match and has_inst:
            raise ValueError("match_payment_id 和 installment_number 不能同时提供")
        if not has_match and not has_inst:
            raise ValueError("必须提供 match_payment_id 或 installment_number 之一")
        return self

    @model_validator(mode="after")
    def _validate_expense_payee(self) -> "CreateFromReceiptRequest":
        """expense 类型时 payee_name 必填"""
        if self.payment_type == "expense" and not self.payee_name:
            raise ValueError("支出类型必须填写收款方（payee_name）")
        return self
