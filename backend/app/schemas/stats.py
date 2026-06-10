"""
财务统计相关 Pydantic 模型

币种规则：项目只支持 CNY 和 HKD 两种币种。所有金额按币种分组返回，不跨币种合并/折算。
"""
from typing import List
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


class DailyTrendItem(BaseModel):
    """每日业务趋势条目（滚动近 30 天）"""
    date: str = Field(..., description="日期 YYYY-MM-DD")
    contract_count: int = Field(0, description="当日成交合同数")
    customer_count: int = Field(0, description="当日成交不重复客户数")


class TopCustomerItem(BaseModel):
    """TOP 客户条目（按币种分组）"""
    customer_id: int
    customer_name: str
    contract_count: int = Field(0, description="合同数")
    total_income: CurrencyAmount = Field(default_factory=CurrencyAmount, description="已收总额（按币种）")
    total_expense: CurrencyAmount = Field(default_factory=CurrencyAmount, description="支出总额（按币种）")
    profit: CurrencyAmount = Field(default_factory=CurrencyAmount, description="利润（按币种）")


class FinancialOverview(BaseModel):
    """财务总览响应"""
    kpi: KpiData
    daily_trend: List[DailyTrendItem] = Field(default_factory=list)
    top_customers: List[TopCustomerItem] = Field(default_factory=list)
