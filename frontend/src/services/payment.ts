import api from './api'
import type { Payment, PaginatedResponse } from '@/types'

export interface PaymentListParams {
  page?: number
  per_page?: number
  contract_id?: number
  keyword?: string
  status?: string
  type?: string
  date_from?: string
  date_to?: string
}

/** 对方收款账户（仅支出，供应商不固定） */
export interface CounterpartyAccount {
  account_name?: string
  account_number?: string
  bank_name?: string
  branch?: string
  swift_code?: string
}

/** 表单创建收支 payload */
export interface PaymentCreatePayload {
  type: 'income' | 'expense'
  currency: string
  amount: number
  paid_date: string  // YYYY-MM-DD
  payment_method?: string
  installment_name?: string
  description?: string
  notes?: string
  // 收入专属
  payment_account_id?: number
  // 支出专属
  payee_name?: string
  counterparty_account?: CounterpartyAccount
  // 凭证
  receipt_file_id?: string  // 已上传凭证的 file_id（收入必传；支出可选）
  no_receipt?: boolean      // 无凭证声明（仅支出）
}

export interface PaymentUpdatePayload {
  amount?: number
  currency?: string
  paid_date?: string
  payment_method?: string
  installment_name?: string
  description?: string
  notes?: string
  payee_name?: string
  counterparty_account?: CounterpartyAccount
  payment_account_id?: number
  receipt_file_id?: string  // 新凭证 file_id；空字符串表示清除凭证
  no_receipt?: boolean
}

export const paymentApi = {
  getList: (params?: PaymentListParams, signal?: AbortSignal): Promise<PaginatedResponse<Payment>> =>
    api.get('/payments', { params, signal }),

  getContractPayments: (contractId: number, signal?: AbortSignal): Promise<any> =>
    api.get(`/payments/contract/${contractId}`, { signal }),

  /** 表单创建收支（contract_id 由合同卡片入口带入） */
  create: (contractId: number, payload: PaymentCreatePayload): Promise<Payment> =>
    api.post(`/payments`, payload, { params: { contract_id: contractId } }),

  /** 表单编辑收支 */
  update: (id: number, payload: PaymentUpdatePayload): Promise<Payment> =>
    api.put(`/payments/${id}`, payload),

  /** 人工确认凭证不符记录，按表单录入信息入账 */
  manualConfirm: (id: number, reason = '操作人确认以表单录入信息为准'): Promise<Payment> =>
    api.post(`/payments/${id}/manual-confirm`, { reason }),

  delete: (id: number): Promise<void> =>
    api.delete(`/payments/${id}`),

  getReceiptUrl: async (id: number): Promise<string> => {
    const blob = await api.get(`/payments/${id}/receipt`, { responseType: 'blob' })
    return URL.createObjectURL(blob as unknown as Blob)
  },

  /** 表单凭证上传，返回 file_id 供创建/编辑引用 */
  uploadReceipt: async (file: File): Promise<{ file_id: string; original_name: string }> => {
    const form = new FormData()
    form.append('file', file)
    const res: any = await api.post('/payments/upload', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return res.data
  },

  /** 从模板截图提取结构化数据（用于自动填充表单） */
  extractReceipt: async (file: File): Promise<ExtractedReceiptData> => {
    const form = new FormData()
    form.append('file', file)
    const res: any = await api.post('/payments/extract-receipt', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return res.data
  },
}

/** 从模板截图提取的结构化数据 */
export interface ExtractedReceiptData {
  installment_name?: string
  paid_date?: string
  amount?: number
  currency?: string
  payee_name?: string
  counterparty_account?: {
    account_name?: string
    account_number?: string
    bank_name?: string
    branch?: string
    swift_code?: string
  }
  notes?: string
  payment_method?: string
  wechat_group?: string
  customer_name_hint?: string
  confidence?: number
}
