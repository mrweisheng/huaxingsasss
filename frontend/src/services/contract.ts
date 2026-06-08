import api from './api'
import type { Contract, PaginatedResponse } from '@/types'

export const contractApi = {
  getList: (params?: {
    page?: number
    per_page?: number
    status?: string
    customer_id?: number
    customer_ids?: string
    customer_name?: string
    keyword?: string
    date_from?: string
    date_to?: string
  }, signal?: AbortSignal): Promise<PaginatedResponse<Contract>> =>
    api.get('/contracts', { params, signal }),

  getById: (id: number, signal?: AbortSignal): Promise<Contract> =>
    api.get(`/contracts/${id}`, { signal }),

  update: (id: number, data: Partial<Contract>): Promise<Contract> =>
    api.put(`/contracts/${id}`, data),

  delete: (id: number): Promise<void> =>
    api.delete(`/contracts/${id}`),

  confirmParsedData: (id: number, parsedData: any): Promise<Contract> =>
    api.post(`/contracts/${id}/confirm-parsed-data`, parsedData),

  complete: (id: number): Promise<Contract> =>
    api.post(`/contracts/${id}/complete`),
}
