/**
 * 收款账户 API 服务
 */
import api from './api'

export interface PaymentAccount {
  id: number
  name: string
  account_type: 'bank' | 'alipay' | 'wechat' | 'other'
  bank_name?: string
  account_name: string
  account_number?: string
  branch?: string
  address?: string
  phone?: string
  swift_code?: string
  fps_id?: string
  qr_code_url?: string
  is_default: boolean
  sort_order: number
  remarks?: string
  created_at?: string
}

export interface PaymentAccountCreate {
  name: string
  account_type: 'bank' | 'alipay' | 'wechat' | 'other'
  bank_name?: string
  account_name: string
  account_number?: string
  branch?: string
  address?: string
  phone?: string
  swift_code?: string
  fps_id?: string
  qr_code_url?: string
  is_default?: boolean
  sort_order?: number
  remarks?: string
}

export const paymentAccountApi = {
  /** 获取收款账户列表 */
  list(): Promise<PaymentAccount[]> {
    return api.get('/payment-accounts').then((res) => res.data)
  },

  /** 创建收款账户 */
  create(data: PaymentAccountCreate): Promise<PaymentAccount> {
    return api.post('/payment-accounts', data).then((res) => res.data)
  },

  /** 删除收款账户 */
  delete(id: number): Promise<void> {
    return api.delete(`/payment-accounts/${id}`).then((res) => res.data)
  },
}
