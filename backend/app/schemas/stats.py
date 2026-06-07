"""
财务统计相关 Pydantic 模型

币种规则：项目只支持 CNY 和 HKD 两种币种。所有金额按币种分组返回，不跨币种合并/折算。
"""
from typing import Optional, List
from pydantic import BaseModel, Field
from decimal import Decimal


class CurrencyAmount(BaseModel):
    """分币种金额"""
    CNY: Decimal = Decimal("0")
    HKD: Decimal = Decimal("0")


class KpiData(BaseModel):
    """核心 KPI 指标（已按币种分组）"""
    total_contracts: int = Field(0, description="合同总数")
    active_contracts: int = Field(0, description="进行中合同")
    total_customers: int = Field(0, description="客户总数")
    total_income: CurrencyAmount = Field(default_factory=CurrencyAmount, description="已收总额（按币种）")
    total_expense: CurrencyAmount = Field(default_factory=CurrencyAmount, description="支出总额（按币种）")
    total_profit: CurrencyAmount = Field(default_factory=CurrencyAmount, description="利润（按币种）")
    total_remaining: CurrencyAmount = Field(default_factory=CurrencyAmount, description="待收金额（按币种）")


class MonthlyItem(BaseModel):
    """月度趋势条目（按币种分组）"""
    month: str = Field(..., description="月份, YYYY-MM")
    income: CurrencyAmount = Field(default_factory=CurrencyAmount, description="收入（按币种）")
    expense: CurrencyAmount = Field(default_factory=CurrencyAmount, description="支出（按币种）")
    profit: CurrencyAmount = Field(default_factory=CurrencyAmount, description="利润（按币种）")


class BusinessTypeItem(BaseModel):
    """业务类型分布条目（按币种分组）"""
    business_type: str = Field(..., description="业务类型")
    contract_count: int = Field(0, description="合同数")
    total_amount: CurrencyAmount = Field(default_factory=CurrencyAmount, description="合同总额（按币种）")
    income: CurrencyAmount = Field(default_factory=CurrencyAmount, description="已收（按币种）")
    expense: CurrencyAmount = Field(default_factory=CurrencyAmount, description="支出（按币种）")
    profit: CurrencyAmount = Field(default_factory=CurrencyAmount, description="利润（按币种）")


class TopCustomerItem(BaseModel):
    """TOP 客户条目（按币种分组）"""
    customer_id: int
    customer_name: str
    contract_count: int = Field(0, description="合同数")
    total_income: CurrencyAmount = Field(default_factory=CurrencyAmount, description="已收总额（按币种）")
    total_expense: CurrencyAmount = Field(default_factory=CurrencyAmount, description="支出总额（按币种）")
    profit: CurrencyAmount = Field(default_factory=CurrencyAmount, description="利润（按币种）")


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
