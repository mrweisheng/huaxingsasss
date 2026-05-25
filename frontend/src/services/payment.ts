import api from './api'
import type { Payment, PaginatedResponse } from '@/types'

export const paymentApi = {
  getList: (params?: {
    page?: number
    per_page?: number
    contract_id?: number
    status?: string
  }): Promise<PaginatedResponse<Payment>> =>
    api.get('/payments', { params }),

  uploadReceipt: (data: {
    contract_id: number
    installment_number: number
    currency: string
    paid_amount: number
    paid_date: string
    payment_method: string
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
    if (data.notes) formData.append('notes', data.notes)
    if (data.file) formData.append('file', data.file)
    
    return api.post('/payments/upload-receipt', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },

  getContractPayments: (contractId: number): Promise<any> =>
    api.get(`/payments/contract/${contractId}`),
}
