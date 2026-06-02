"""
合同相关Pydantic模型
"""
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from datetime import date, datetime
from decimal import Decimal

from app.core.business_types import BusinessType, LEGACY_VALUES


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


class ContractParseResult(BaseModel):
    """合同解析结果"""
    
    task_id: str = Field(..., description="任务ID")
    status: str = Field(..., description="解析状态")
    contract_id: Optional[int] = Field(None, description="合同ID")
    parsed_data: Optional[Dict[str, Any]] = Field(None, description="解析数据")
    confidence: Optional[float] = Field(None, description="置信度")
    needs_review: bool = Field(default=False, description="是否需要人工审核")
    message: Optional[str] = Field(None, description="消息")
