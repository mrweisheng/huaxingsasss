import api from './api'
import type { ContractAdditionalItem } from '@/types'

export interface AdditionalItemInput {
  name: string
  amount: number
  currency: string
  paid_to?: string
  description?: string
  occurred_date?: string
  remarks?: string
}

/** 合同附加项 API（与合同路由共享 /contracts 前缀） */
export const additionalItemApi = {
  list: (contractId: number, signal?: AbortSignal): Promise<ContractAdditionalItem[]> =>
    api.get(`/contracts/${contractId}/additional-items`, { signal }),

  create: (contractId: number, data: AdditionalItemInput): Promise<ContractAdditionalItem> =>
    api.post(`/contracts/${contractId}/additional-items`, { ...data, contract_id: contractId }),

  update: (itemId: number, data: Partial<AdditionalItemInput>): Promise<ContractAdditionalItem> =>
    api.put(`/contracts/additional-items/${itemId}`, data),

  remove: (itemId: number): Promise<void> =>
    api.delete(`/contracts/additional-items/${itemId}`),
}
