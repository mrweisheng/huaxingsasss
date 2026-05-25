export interface User {
  id: number
  username: string
  email?: string
  full_name?: string
  role: string
  department?: string
  is_active: boolean
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
  confidence?: number
  needs_review?: boolean
  status: string
  signed_date?: string
  start_date?: string
  end_date?: string
  remarks?: string
  created_at: string
  updated_at: string
}

export interface Payment {
  id: number
  contract_id: number
  contract_number?: string
  customer_name?: string
  installment_number: number
  installment_name?: string
  currency: string
  amount: number
  paid_amount: number
  exchange_rate?: number
  amount_in_cny?: number
  paid_amount_in_cny?: number
  due_date?: string
  paid_date?: string
  receipt_image_path?: string
  payment_method?: string
  status: string
  source: string
  notes?: string
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
