import api from './api'
import type { Contract, ContractWithPayments, PaginatedResponse } from '@/types'

export interface ContractListParams {
  page?: number
  per_page?: number
  status?: string
  customer_id?: number
  customer_ids?: string
  customer_name?: string
  keyword?: string
  date_from?: string
  date_to?: string
  /** "payments" → 同时返回每个合同的付款流水（台账视图） */
  include?: 'payments'
}

export const contractApi = {
  getList: (params?: ContractListParams, signal?: AbortSignal): Promise<PaginatedResponse<Contract>> =>
    api.get('/contracts', { params, signal }),

  /** 台账视图专用：返回含 payments 明细的列表 */
  getListWithPayments: (
    params?: Omit<ContractListParams, 'include'>,
    signal?: AbortSignal,
  ): Promise<PaginatedResponse<ContractWithPayments>> =>
    api.get('/contracts', { params: { ...params, include: 'payments' }, signal }),

  getById: (id: number, signal?: AbortSignal): Promise<Contract> =>
    api.get(`/contracts/${id}`, { signal }),

  update: (id: number, data: Partial<Contract>): Promise<Contract> =>
    api.put(`/contracts/${id}`, data),

  delete: (id: number): Promise<void> =>
    api.delete(`/contracts/${id}`),

  complete: (id: number): Promise<Contract> =>
    api.post(`/contracts/${id}/complete`),
}
