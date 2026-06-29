import api from './api'
import type { Contract, ContractWithPayments, PaginatedResponse } from '@/types'

/** 端点1 analyze 返回的 AI 结构化解析结果（与后端 FileAnalyzer.analyze contract 输出对齐） */
export interface ContractAnalyzeResult {
  success: boolean
  type?: string
  confidence?: number
  file_type?: string
  file_hash?: string
  duplicate_detected?: boolean
  existing_contract?: {
    id: number
    contract_number: string
    title?: string
    status?: string
    total_amount?: number
    currency?: string
    customer_name?: string
  } | null
  data?: ContractAnalyzeData
}

export interface ContractAnalyzeData {
  title?: string
  currency?: string
  total_amount?: number
  payment_terms?: any[]
  party_a?: { name?: string }
  party_b?: { name?: string }
  signed_date?: string
  business_type?: string
  business_description?: string
  special_terms?: string
  validity_period?: { start_date?: string; end_date?: string }
  full_text?: string
  [key: string]: any
}

/** 端点2 create 表单入参（与后端 ContractFormCreate 对齐） */
export interface ContractFormPayload {
  title?: string
  business_type?: string
  business_description?: string
  currency: string
  total_amount?: number
  signed_date?: string
  start_date?: string
  end_date?: string
  remarks?: string
  wechat_group?: string
  customer_id?: number
  file_id: string
  contract_data: Record<string, any>
  contract_text?: string
  confidence?: number
}

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

  /** 表单通道 · 步骤1：分析已上传的合同文件，返回 AI 结构化解析结果 */
  analyze: (file_id: string): Promise<ContractAnalyzeResult> =>
    api.post('/contracts/analyze', { file_id }),

  /** 表单通道 · 步骤2：根据预览确认的字段 + AI 解析结果创建合同 */
  createViaForm: (data: ContractFormPayload): Promise<Contract> =>
    api.post('/contracts', data),
}
