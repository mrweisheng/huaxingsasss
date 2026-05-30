import api from './api'
import type { Payment, PaginatedResponse } from '@/types'

export interface PaymentListParams {
  page?: number
  per_page?: number
  contract_id?: number
  status?: string
  type?: string
}

export const paymentApi = {
  getList: (params?: PaymentListParams, signal?: AbortSignal): Promise<PaginatedResponse<Payment>> =>
    api.get('/payments', { params, signal }),

  uploadReceipt: (data: {
    contract_id: number
    installment_number: number
    currency: string
    paid_amount: number
    paid_date: string
    payment_method: string
    type?: string
    payee_name?: string
    notes?: string
    file?: File
  }): Promise<Payment> => {
    const formData = new FormData()
    formData.append('contract_id', String(data.contract_id))
    formData.append('installment_number', String(data.installment_number))
    formData.append('currency', data.currency)
    formData.append('paid_amount', String(data.paid_amount))
    formData.append('paid_date', data.paid_date)
    formData.append('payment_method', data.payment_method)
    if (data.type) formData.append('payment_type', data.type)
    if (data.payee_name) formData.append('payee_name', data.payee_name)
    if (data.notes) formData.append('notes', data.notes)
    if (data.file) formData.append('file', data.file)

    return api.post('/payments/upload-receipt', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },

  getContractPayments: (contractId: number, signal?: AbortSignal): Promise<any> =>
    api.get(`/payments/contract/${contractId}`, { signal }),

  delete: (id: number): Promise<void> =>
    api.delete(`/payments/${id}`),

  getReceiptUrl: async (id: number): Promise<string> => {
    const blob = await api.get(`/payments/${id}/receipt`, { responseType: 'blob' })
    return URL.createObjectURL(blob as unknown as Blob)
  },
}
