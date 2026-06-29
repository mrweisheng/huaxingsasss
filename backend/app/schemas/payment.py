"""
付款相关Pydantic模型
"""
from typing import Optional
from pydantic import BaseModel, Field, model_validator
from datetime import date, datetime
from decimal import Decimal

from app.config import settings


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


class CounterpartyAccount(BaseModel):
    """对方收款账户（仅expense使用，供应商不固定，存JSON不求建表）"""

    account_name: Optional[str] = Field(None, max_length=200, description="户名")
    account_number: Optional[str] = Field(None, max_length=100, description="卡号/账号")
    bank_name: Optional[str] = Field(None, max_length=100, description="开户行")
    branch: Optional[str] = Field(None, max_length=200, description="网点")
    swift_code: Optional[str] = Field(None, max_length=50, description="SWIFT Code")


class VerificationResult(BaseModel):
    """凭证校验明细"""

    expected: Optional[dict] = Field(None, description="表单填写值 {amount, currency, payer}")
    extracted: Optional[dict] = Field(None, description="凭证提取值 {amount, currency, payer_name}")
    match: Optional[dict] = Field(None, description="比对结果 {amount: bool, payer: bool}")
    confidence: Optional[float] = Field(None, description="VL 置信度 0-1")
    reason: Optional[str] = Field(None, description="判定原因")


class PaymentCreate(BaseModel):
    """表单创建付款（收入/支出统一入口）

    - 收入（income）：
      - INCOME_RECEIPT_REQUIRED=True（将来）：凭证必传，落库 pending 由 Celery 异步校验
      - INCOME_RECEIPT_REQUIRED=False（现阶段，默认）：凭证可选，无凭证直接 paid 结算并打
        [无凭证收入] 标记；有凭证仍走异步校验
    - 支出（expense）：凭证可选；有凭证走 paid 结算并弱校验提醒，无凭证走 no_receipt 直接 paid。
    """

    type: str = Field(..., description="income/expense")
    currency: str = Field(default="CNY", description="币种")
    amount: Decimal = Field(..., gt=0, description="金额")
    paid_date: date = Field(..., description="实际付款日期")
    payment_method: Optional[str] = Field(None, description="付款方式")
    installment_name: Optional[str] = Field(None, max_length=100, description="期数名称/业务说明，如'尾款'")
    description: Optional[str] = Field(None, max_length=500, description="业务说明（对应模板第1项）")
    notes: Optional[str] = Field(None, description="备注（对应模板第6项结算状态说明等）")
    # 收入专属
    payment_account_id: Optional[int] = Field(None, description="收款账户ID（income 关联己方预设账户）")
    # 收入专属：剩余尾款快照（从用户消息「结算状态：剩 X 万」提取，仅 income 写入）
    outstanding_amount: Optional[Decimal] = Field(None, ge=0, description="本次结算后剩余尾款（仅income）")
    outstanding_currency: Optional[str] = Field(None, description="尾款币种 CNY/HKD（仅income，默认随本笔币种）")
    # 支出专属
    payee_name: Optional[str] = Field(None, max_length=200, description="收款方名称（expense）")
    counterparty_account: Optional[CounterpartyAccount] = Field(None, description="对方账户详情（expense）")
    # 凭证
    receipt_file_id: Optional[str] = Field(None, description="已上传凭证的文件ID（开关开启时收入必传；否则可选）")
    no_receipt: bool = Field(False, description="无凭证声明（与 receipt_file_id 互斥；现阶段 income 也允许）")

    @model_validator(mode="after")
    def _validate_receipt_rules(self):
        """凭证规则校验"""
        # 凭证与无凭证声明互斥（收入支出统一）
        if self.receipt_file_id and self.no_receipt:
            raise ValueError("不能同时上传凭证和声明无凭证")
        if self.type == "income":
            # 收入凭证强制：仅在 INCOME_RECEIPT_REQUIRED=True 时启用（现阶段关闭）
            if settings.INCOME_RECEIPT_REQUIRED and not self.receipt_file_id:
                raise ValueError("收入必须上传凭证")
        return self


class PaymentUpdate(BaseModel):
    """更新付款（编辑表单字段 / 换凭证）"""

    amount: Optional[Decimal] = Field(None, gt=0)
    currency: Optional[str] = None
    paid_date: Optional[date] = None
    payment_method: Optional[str] = None
    installment_name: Optional[str] = None
    description: Optional[str] = None
    notes: Optional[str] = None
    payee_name: Optional[str] = None
    counterparty_account: Optional[CounterpartyAccount] = None
    payment_account_id: Optional[int] = None
    outstanding_amount: Optional[Decimal] = Field(None, ge=0, description="剩余尾款（仅income编辑时支持）")
    outstanding_currency: Optional[str] = None
    # 换凭证：传新 file_id 触发重新校验；传空字符串表示删除凭证
    receipt_file_id: Optional[str] = None
    no_receipt: Optional[bool] = None


class PaymentManualConfirm(BaseModel):
    """人工确认凭证不符付款"""

    reason: str = Field(default="操作人确认以表单录入信息为准", max_length=200)


class PaymentResponse(PaymentBase):
    """付款响应"""

    id: int
    contract_id: int
    contract_number: Optional[str] = None
    customer_name: Optional[str] = None
    contract_business_description: Optional[str] = None
    contract_wechat_group: Optional[str] = None
    contract_currency: Optional[str] = None  # 合同主币种（仍保留供前端参考，不再用于换算）
    description: Optional[str] = None
    paid_amount: Decimal
    # 改造后：剩余尾款快照（仅 income 写入，expense 永远为 None）
    outstanding_amount: Optional[Decimal] = None
    outstanding_currency: Optional[str] = None
    receipt_image_path: Optional[str]
    receipt_data: Optional[dict] = None
    additional_receipt_files: Optional[list[dict]] = None
    # 表单录入新增字段
    payment_account_id: Optional[int] = None
    payment_account_title: Optional[str] = None  # 账户展示标题（join 填充）
    counterparty_account: Optional[dict] = None
    verification_status: Optional[str] = None
    verification_result: Optional[dict] = None
    verified_at: Optional[datetime] = None
    status: str
    source: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
