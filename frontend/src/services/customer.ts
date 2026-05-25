import api from './api'
import type { Customer, PaginatedResponse } from '@/types'

export const customerApi = {
  getList: (params?: {
    page?: number
    per_page?: number
    keyword?: string
  }): Promise<PaginatedResponse<Customer>> =>
    api.get('/customers', { params }),

  getById: (id: number): Promise<Customer> =>
    api.get(`/customers/${id}`),

  create: (data: Partial<Customer>): Promise<Customer> =>
    api.post('/customers', data),

  update: (id: number, data: Partial<Customer>): Promise<Customer> =>
    api.put(`/customers/${id}`, data),

  delete: (id: number): Promise<void> =>
    api.delete(`/customers/${id}`),
}
