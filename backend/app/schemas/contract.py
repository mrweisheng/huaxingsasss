"""
合同相关Pydantic模型
"""
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from datetime import date, datetime
from decimal import Decimal

from app.core.business_types import BusinessType, LEGACY_VALUES
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


class ContractFormCreate(BaseModel):
    """表单通道创建合同的入参（与 Agent 通道的 ContractCreate 区分）。

    设计要点（详见 .mimocode/plans/1782377932485-sunny-knight.md）：
    - 不收 contract_number：后端自动 generate_contract_number()，前端无需感知
    - file_id 替代 original_file_path：后端复用 resolve_file_path 定位源文件并复制，
      前端不接触任何文件路径（也避免路径穿越风险）
    - total_amount 可空：为空时由 contract_data['total_amount'] 兜底
    - contract_data 必填：端点1 analyze 返回的 AI 结构化结果，落库到 contract.contract_data
    - customer_id 可空：用户在预览步骤主动选，不自动绑（party_b 名字与系统客户名常对不上）
    """

    title: Optional[str] = Field(None, max_length=500, description="合同标题")
    business_type: Optional[str] = Field(None, max_length=50, description="业务类型")
    business_description: Optional[str] = Field(None, max_length=200, description="业务描述")
    currency: str = Field(default="CNY", description="合同币种")
    total_amount: Optional[Decimal] = Field(None, ge=0, description="合同总金额；为空时从 contract_data 兜底")
    signed_date: Optional[date] = Field(None, description="签订日期")
    start_date: Optional[date] = Field(None, description="生效日期")
    end_date: Optional[date] = Field(None, description="到期日期")
    remarks: Optional[str] = Field(None, description="备注")
    wechat_group: Optional[str] = Field(None, max_length=200, description="业务微信群名称")

    customer_id: Optional[int] = Field(None, description="客户ID（可选，用户主动关联）")
    file_id: str = Field(..., description="上传接口返回的文件ID，后端据此定位并复制源文件")
    contract_data: Dict[str, Any] = Field(..., description="端点1 analyze 返回的 AI 分析结果（结构化 JSON）")
    contract_text: Optional[str] = Field(None, description="合同全文（通常取 contract_data['full_text']）")
    confidence: Optional[float] = Field(None, description="AI 解析置信度")


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
    total_expense: Decimal = Decimal("0")

    # 改造后：按币种分桶（混币种合同的完整真相），由 Service 在序列化时计算
    # 例如 {"HKD": 150000, "CNY": 20000}
    paid_by_currency: Dict[str, float] = Field(default_factory=dict, description="按币种分组的已收金额")
    expense_by_currency: Dict[str, float] = Field(default_factory=dict, description="按币种分组的已付支出")

    # 改造后：剩余尾款不再 total-paid 算，取该合同最新一笔 income payment 的 outstanding 快照
    outstanding_amount: Optional[Decimal] = Field(None, description="当前剩余尾款（来自最新一笔收入的录入快照）")
    outstanding_currency: Optional[str] = Field(None, description="尾款币种")

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
    """合同详情响应（与 ContractResponse 同字段）。

    保留独立子类便于未来扩展（如增加详情专属字段）；当前不追加任何字段。
    """

    pass

