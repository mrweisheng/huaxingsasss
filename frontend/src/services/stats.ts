import api from './api'

export interface CurrencyAmount {
  CNY: number
  HKD: number
}

export interface KpiData {
  total_contracts: number
  active_contracts: number
  total_customers: number
  total_income: CurrencyAmount
  total_expense: CurrencyAmount
  total_profit: CurrencyAmount
  total_remaining: CurrencyAmount
}

export interface MonthlyItem {
  month: string
  income: number
  expense: number
  profit: number
}

export interface BusinessTypeItem {
  business_type: string
  contract_count: number
  total_amount: number
  income: number
  expense: number
  profit: number
}

export interface TopCustomerItem {
  customer_id: number
  customer_name: string
  contract_count: number
  total_income: number
  total_expense: number
  profit: number
}

export interface ContractStatusItem {
  status: string
  count: number
}

export interface FinancialOverview {
  kpi: KpiData
  monthly_trend: MonthlyItem[]
  business_type_distribution: BusinessTypeItem[]
  top_customers: TopCustomerItem[]
  contract_status: ContractStatusItem[]
}

export const statsApi = {
  getOverview: () => api.get<any, { data: FinancialOverview }>('/stats/overview'),
}
