"""
财务统计相关 Pydantic 模型
"""
from typing import Optional, List
from pydantic import BaseModel, Field
from decimal import Decimal


class CurrencyAmount(BaseModel):
    """分币种金额"""
    CNY: Decimal = Decimal("0")
    HKD: Decimal = Decimal("0")


class KpiData(BaseModel):
    """核心 KPI 指标"""
    total_contracts: int = Field(0, description="合同总数")
    active_contracts: int = Field(0, description="进行中合同")
    total_customers: int = Field(0, description="客户总数")
    total_income: CurrencyAmount = Field(default_factory=CurrencyAmount, description="已收总额")
    total_expense: CurrencyAmount = Field(default_factory=CurrencyAmount, description="支出总额")
    total_profit: CurrencyAmount = Field(default_factory=CurrencyAmount, description="利润")
    total_remaining: CurrencyAmount = Field(default_factory=CurrencyAmount, description="待收金额")


class MonthlyItem(BaseModel):
    """月度趋势条目"""
    month: str = Field(..., description="月份, YYYY-MM")
    income: Decimal = Field(Decimal("0"), description="收入（CNY）")
    expense: Decimal = Field(Decimal("0"), description="支出（CNY）")
    profit: Decimal = Field(Decimal("0"), description="利润（CNY）")


class BusinessTypeItem(BaseModel):
    """业务类型分布条目"""
    business_type: str = Field(..., description="业务类型")
    contract_count: int = Field(0, description="合同数")
    total_amount: Decimal = Field(Decimal("0"), description="合同总额（CNY）")
    income: Decimal = Field(Decimal("0"), description="已收（CNY）")
    expense: Decimal = Field(Decimal("0"), description="支出（CNY）")
    profit: Decimal = Field(Decimal("0"), description="利润（CNY）")


class TopCustomerItem(BaseModel):
    """TOP 客户条目"""
    customer_id: int
    customer_name: str
    contract_count: int = Field(0, description="合同数")
    total_income: Decimal = Field(Decimal("0"), description="已收总额（CNY）")
    total_expense: Decimal = Field(Decimal("0"), description="支出总额（CNY）")
    profit: Decimal = Field(Decimal("0"), description="利润（CNY）")


class ContractStatusItem(BaseModel):
    """合同状态分布条目"""
    status: str
    count: int


class FinancialOverview(BaseModel):
    """财务总览响应"""
    kpi: KpiData
    monthly_trend: List[MonthlyItem] = Field(default_factory=list)
    business_type_distribution: List[BusinessTypeItem] = Field(default_factory=list)
    top_customers: List[TopCustomerItem] = Field(default_factory=list)
    contract_status: List[ContractStatusItem] = Field(default_factory=list)
