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

  uploadAndParse: (file: File, customerId?: number): Promise<any> => {
    const formData = new FormData()
    formData.append('file', file)
    if (customerId) formData.append('customer_id', String(customerId))
    return api.post('/contracts/upload-and-parse', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },

  /** 分析已上传的合同文件（同步） */
  analyzeFile: (fileId: string, fileName?: string, skipDuplicate?: boolean): Promise<any> =>
    api.post('/contracts/analyze-file', {
      file_id: fileId,
      file_name: fileName,
      skip_duplicate_check: skipDuplicate || false,
    }),

  /** 从 AI 分析结果创建合同 */
  createFromAnalysis: (data: any): Promise<any> =>
    api.post('/contracts/create-from-analysis', data),

  /** 从 AI 分析结果自动关联/创建客户 */
  resolveCustomer: (analysisData: any, party = 'party_b') =>
    api.post('/contracts/resolve-customer', { analysis_data: analysisData, party }),

  update: (id: number, data: Partial<Contract>): Promise<Contract> =>
    api.put(`/contracts/${id}`, data),

  delete: (id: number): Promise<void> =>
    api.delete(`/contracts/${id}`),

  confirmParsedData: (id: number, parsedData: any): Promise<Contract> =>
    api.post(`/contracts/${id}/confirm-parsed-data`, parsedData),

  complete: (id: number): Promise<Contract> =>
    api.post(`/contracts/${id}/complete`),

  getParseStatus: (contractId: number, signal?: AbortSignal): Promise<any> =>
    api.get(`/contracts/parse-status/${contractId}`, { signal }),
}
