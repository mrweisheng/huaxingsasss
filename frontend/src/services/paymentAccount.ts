/**
 * 收款账户 API 服务
 */
import api from './api'

export interface PaymentAccount {
  id: number
  account_type: 'bank' | 'alipay' | 'wechat' | 'cash' | 'other'
  title: string
  account_name: string
  account_number?: string
  qr_code_url?: string
  fps_id?: string
  bank_name?: string
  branch?: string
  address?: string
  phone?: string
  swift_code?: string
  extra_info?: Record<string, any>
  is_default: boolean
  sort_order: number
  created_at?: string
}

export interface PaymentAccountCreate {
  account_type: 'bank' | 'alipay' | 'wechat' | 'cash' | 'other'
  title: string
  account_name: string
  account_number?: string
  qr_code_url?: string
  fps_id?: string
  bank_name?: string
  branch?: string
  address?: string
  phone?: string
  swift_code?: string
  extra_info?: Record<string, any>
  is_default?: boolean
  sort_order?: number
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
