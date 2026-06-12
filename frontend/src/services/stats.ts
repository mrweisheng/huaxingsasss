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

export interface MonthlyReceiptTrendItem {
  date: string             // YYYY-MM-DD
  cny: number
  hkd: number
}

export interface FinancialOverview {
  kpi: KpiData
  daily_trend: DailyTrendItem[]
  monthly_receipt_trend: MonthlyReceiptTrendItem[]
}

export const statsApi = {
  getOverview: () => api.get<any, { data: FinancialOverview }>('/stats/overview'),
}
