import api from './api'
import type { Contract, PaginatedResponse } from '@/types'

export const contractApi = {
  getList: (params?: {
    page?: number
    per_page?: number
    status?: string
    customer_id?: number
    keyword?: string
  }): Promise<PaginatedResponse<Contract>> =>
    api.get('/contracts', { params }),

  getById: (id: number): Promise<Contract> =>
    api.get(`/contracts/${id}`),

  uploadAndParse: (file: File, customerId?: number): Promise<any> => {
    const formData = new FormData()
    formData.append('file', file)
    if (customerId) formData.append('customer_id', String(customerId))
    return api.post('/contracts/upload-and-parse', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },

  update: (id: number, data: Partial<Contract>): Promise<Contract> =>
    api.put(`/contracts/${id}`, data),

  delete: (id: number): Promise<void> =>
    api.delete(`/contracts/${id}`),

  confirmParsedData: (id: number, parsedData: any): Promise<Contract> =>
    api.post(`/contracts/${id}/confirm-parsed-data`, parsedData),

  getParseStatus: (contractId: number): Promise<any> =>
    api.get(`/contracts/parse-status/${contractId}`),
}
