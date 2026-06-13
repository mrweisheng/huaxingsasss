"""
合同相关Pydantic模型
"""
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from datetime import date, datetime
from decimal import Decimal

from app.core.business_types import BusinessType, LEGACY_VALUES
from app.schemas.contract_additional_item import AdditionalItemResponse
from app.schemas.payment import PaymentResponse


class ContractBase(BaseModel):
    """合同基础模型"""

    contract_number: str = Field(..., max_length=50, description="合同编号")
    title: Optional[str] = Field(None, max_length=500, description="合同标题")
    business_type: Optional[str] = Field(None, max_length=50, description=(
        f"业务类型: {'/'.join(BusinessType.all_values())}；legacy: {'/'.join(LEGACY_VALUES)}"
    ))
    business_description: Optional[str] = Field(None, max_length=200, description="业务描述")
    currency: str = Field(default="CNY", description="合同币种")
    total_amount: Decimal = Field(..., ge=0, description="合同总金额")
    signed_date: Optional[date] = Field(None, description="签订日期")
    start_date: Optional[date] = Field(None, description="生效日期")
    end_date: Optional[date] = Field(None, description="到期日期")
    remarks: Optional[str] = Field(None, description="备注")
    wechat_group: Optional[str] = Field(None, max_length=200, description="业务微信群名称")
    contract_text: Optional[str] = Field(None, description="合同全文内容")


class ContractCreate(ContractBase):
    """创建合同"""

    customer_id: Optional[int] = Field(None, description="客户ID（可选，解析后可关联）")
    original_file_path: str = Field(..., description="合同文件路径")
    file_hash: Optional[str] = Field(None, description="文件哈希")
    status: Optional[str] = Field("draft", description="初始状态: draft/active")


class ContractUpdate(BaseModel):
    """更新合同"""

    title: Optional[str] = Field(None, max_length=500)
    business_type: Optional[str] = Field(None, max_length=50, description=(
        f"业务类型: {'/'.join(BusinessType.all_values())}；legacy: {'/'.join(LEGACY_VALUES)}"
    ))
    business_description: Optional[str] = Field(None, max_length=200, description="业务描述")
    status: Optional[str] = Field(None, description="状态")
    signed_date: Optional[date] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    remarks: Optional[str] = None
    wechat_group: Optional[str] = Field(None, max_length=200, description="业务微信群名称")
    contract_data: Optional[Dict[str, Any]] = Field(None, description="AI解析数据")
    contract_text: Optional[str] = Field(None, description="合同全文内容")


class ContractResponse(ContractBase):
    """合同响应"""

    id: int
    customer_id: Optional[int] = None
    customer_name: Optional[str] = None
    sales_person_id: int
    paid_amount: Decimal
    remaining_amount: Optional[Decimal] = None
    total_amount_in_cny: Optional[Decimal] = None
    paid_amount_in_cny: Optional[Decimal] = None
    remaining_amount_in_cny: Optional[Decimal] = None
    total_expense: Decimal = Decimal("0")
    total_expense_in_cny: Optional[Decimal] = Decimal("0")
    additional_total_by_currency: Optional[Dict[str, Any]] = None
    additional_total_in_contract_currency: Optional[Decimal] = None
    confidence: Optional[float] = None
    needs_review: Optional[bool] = False
    status: str
    original_file_path: Optional[str] = None
    contract_data: Optional[Dict[str, Any]] = None
    contract_text: Optional[str] = None
    paid_count: int = 0
    expense_count: int = 0
    payment_total_count: int = 0
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ContractWithPaymentsResponse(ContractResponse):
    """合同响应（含付款明细）。

    仅在 GET /contracts?include=payments 场景下使用。
    单独建子类是为了避免在 ContractResponse 上声明 payments 字段——
    那样 pydantic from_attributes 会在所有列表查询时 getattr(contract, "payments")
    触发 SQLAlchemy lazy load，反而把不需要明细的调用方拖入 N+1。
    """

    payments: List[PaymentResponse] = Field(
        default_factory=list,
        description="付款流水明细（已按未删除过滤）",
    )


class ContractDetailResponse(ContractResponse):
    """合同详情响应（含附加项明细）。

    仅在 GET /contracts/{id} 场景使用——单独建子类避免在列表 ContractResponse 上声明
    additional_items 列表字段，否则 pydantic from_attributes 会在列表查询时
    getattr 触发 SQLAlchemy lazy load N+1。detail 接口由 Service 层 selectinload 预加载。
    """

    additional_items: List[AdditionalItemResponse] = Field(
        default_factory=list,
        description="附加项明细（已按未删除过滤）",
    )


