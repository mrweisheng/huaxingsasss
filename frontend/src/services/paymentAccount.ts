/**
 * 收款账户 API 服务
 */
import api from './api'

export interface PaymentAccount {
  id: number
  bank_name: string
  account_name: string
  account_number?: string
  fps_id?: string
  branch?: string
  address?: string
  phone?: string
  swift_code?: string
  is_default: boolean
  sort_order: number
  remarks?: string
  created_at?: string
}

export interface PaymentAccountCreate {
  bank_name: string
  account_name: string
  account_number?: string
  fps_id?: string
  branch?: string
  address?: string
  phone?: string
  swift_code?: string
  is_default?: boolean
  sort_order?: number
  remarks?: string
}

export const paymentAccountApi = {
  list(): Promise<PaymentAccount[]> {
    return api.get('/payment-accounts')
  },

  create(data: PaymentAccountCreate): Promise<PaymentAccount> {
    return api.post('/payment-accounts', data)
  },

  delete(id: number): Promise<void> {
    return api.delete(`/payment-accounts/${id}`)
  },
}
