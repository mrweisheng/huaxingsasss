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

export interface DailyTrendItem {
  date: string             // YYYY-MM-DD
  contract_count: number
  customer_count: number
}

export interface TopCustomerItem {
  customer_id: number
  customer_name: string
  contract_count: number
  total_income: CurrencyAmount
  total_expense: CurrencyAmount
  profit: CurrencyAmount
}

export interface FinancialOverview {
  kpi: KpiData
  daily_trend: DailyTrendItem[]
  top_customers: TopCustomerItem[]
}

export const statsApi = {
  getOverview: () => api.get<any, { data: FinancialOverview }>('/stats/overview'),
}
