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

export const paymentApi = {
  getList: (params?: PaymentListParams, signal?: AbortSignal): Promise<PaginatedResponse<Payment>> =>
    api.get('/payments', { params, signal }),

  getContractPayments: (contractId: number, signal?: AbortSignal): Promise<any> =>
    api.get(`/payments/contract/${contractId}`, { signal }),

  delete: (id: number): Promise<void> =>
    api.delete(`/payments/${id}`),

  getReceiptUrl: async (id: number): Promise<string> => {
    const blob = await api.get(`/payments/${id}/receipt`, { responseType: 'blob' })
    return URL.createObjectURL(blob as unknown as Blob)
  },
}
