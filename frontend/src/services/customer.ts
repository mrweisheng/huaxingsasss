import api from './api'
import type { Customer, PaginatedResponse } from '@/types'

export interface CustomerCreatePayload {
  name: string
  contact_person?: string
  phone?: string
  email?: string
  id_card_number?: string
  business_license?: string
  address?: string
  wechat_group_name?: string
  remarks?: string
}

export const customerApi = {
  getList: (params?: {
    page?: number
    per_page?: number
    keyword?: string
  }, signal?: AbortSignal): Promise<PaginatedResponse<Customer>> =>
    api.get('/customers', { params, signal }),

  /** 创建客户或返回已有（按 同名+同电话/同名+同邮箱 去重复用） */
  createOrGet: (data: CustomerCreatePayload): Promise<Customer> =>
    api.post('/customers', data),

  getById: (id: number, signal?: AbortSignal): Promise<Customer> =>
    api.get(`/customers/${id}`, { signal }),

  update: (id: number, data: Partial<Customer>): Promise<Customer> =>
    api.put(`/customers/${id}`, data),

  delete: (id: number): Promise<void> =>
    api.delete(`/customers/${id}`),
}
