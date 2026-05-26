import api from './api'
import type { Customer, PaginatedResponse } from '@/types'

export const customerApi = {
  getList: (params?: {
    page?: number
    per_page?: number
    keyword?: string
  }, signal?: AbortSignal): Promise<PaginatedResponse<Customer>> =>
    api.get('/customers', { params, signal }),

  getById: (id: number, signal?: AbortSignal): Promise<Customer> =>
    api.get(`/customers/${id}`, { signal }),

  create: (data: Partial<Customer>): Promise<Customer> =>
    api.post('/customers', data),

  update: (id: number, data: Partial<Customer>): Promise<Customer> =>
    api.put(`/customers/${id}`, data),

  delete: (id: number): Promise<void> =>
    api.delete(`/customers/${id}`),
}
