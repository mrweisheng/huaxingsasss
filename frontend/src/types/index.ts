export interface User {
  id: number
  username: string
  email?: string
  full_name?: string
  role: string
  department?: string
  is_active: boolean
  created_at?: string
  last_login_at?: string
}

export interface Customer {
  id: number
  name: string
  contact_person?: string
  phone?: string
  email?: string
  id_card_number?: string
  business_license?: string
  address?: string
  wechat_group_name?: string
  remarks?: string
  created_at: string
  updated_at: string
}

export interface Contract {
  id: number
  contract_number: string
  title?: string
  business_type?: string
  business_description?: string
  customer_id: number
  customer_name?: string
  sales_person_id: number
  currency: string
  total_amount: number
  paid_amount: number
  remaining_amount: number
  total_amount_in_cny?: number
  paid_amount_in_cny?: number
  remaining_amount_in_cny?: number
  total_expense?: number
  total_expense_in_cny?: number
  confidence?: number
  needs_review?: boolean
  status: string
  original_file_path?: string
  signed_date?: string
  start_date?: string
  end_date?: string
  remarks?: string
  wechat_group?: string
  contract_data?: Record<string, any>
  paid_count: number
  expense_count: number
  payment_total_count: number
  created_at: string
  updated_at: string
}

/**
 * 合同 + 付款明细（台账视图专用）
 * 由 GET /contracts?include=payments 返回。卡片视图不应使用此类型，
 * 以免误传 include 把卡片接口也带成 N+1。
 */
export interface ContractWithPayments extends Contract {
  payments: Payment[]
}

export interface Payment {
  id: number
  contract_id: number
  contract_number?: string
  customer_name?: string
  contract_business_description?: string
  contract_wechat_group?: string
  contract_currency?: string  // 合同主币种（仅合同详情页回填，全局列表为空）
  installment_number: number
  installment_name?: string
  type: string
  payee_name?: string
  currency: string
  amount: number
  paid_amount: number
  exchange_rate?: number
  amount_in_cny?: number
  paid_amount_in_cny?: number
  due_date?: string
  paid_date?: string
  receipt_image_path?: string
  receipt_data?: Record<string, any>
  payment_method?: string
  status: string
  source: string
  notes?: string
  description?: string
  // 表单录入新增字段
  payment_account_id?: number
  payment_account_title?: string
  counterparty_account?: { account_name?: string; account_number?: string; bank_name?: string; branch?: string }
  verification_status?: 'pending' | 'passed' | 'failed' | null
  verification_result?: {
    expected?: { amount?: number; currency?: string; payer?: string }
    extracted?: { amount?: number; currency?: string; payer_name?: string }
    match?: { amount?: boolean; currency?: boolean; payer?: boolean }
    confidence?: number
    reason?: string
  }
  verified_at?: string
  created_at: string
  updated_at: string
}

export interface ExchangeRate {
  id: number
  from_currency: string
  to_currency: string
  rate: number
  rate_date: string
  source: string
  is_active: boolean
  remarks?: string
  created_at: string
  updated_at: string
}

export interface ApiResponse<T = any> {
  code: number
  message: string
  data?: T
  timestamp: string
}

export interface PaginatedResponse<T> {
  items: T[]
  pagination: {
    page: number
    per_page: number
    total: number
    total_pages: number
  }
}