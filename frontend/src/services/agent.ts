import api from './api'
import type { ChatSession, ChatMessage, UploadResult } from '../types/agent'

const API_BASE = '/agent'

export const agentApi = {
  createSession: (): Promise<{ code: number; data: ChatSession }> =>
    api.post(`${API_BASE}/sessions`),

  listSessions: (): Promise<{ code: number; data: ChatSession[] }> =>
    api.get(`${API_BASE}/sessions`),

  deleteSession: (sessionId: string): Promise<{ code: number; data: null }> =>
    api.delete(`${API_BASE}/sessions/${sessionId}`),

  getHistory: (sessionId: string): Promise<{ code: number; data: ChatMessage[] }> =>
    api.get(`${API_BASE}/history/${sessionId}`),

  uploadFile: async (file: File): Promise<{ code: number; data: UploadResult }> => {
    const formData = new FormData()
    formData.append('file', file)
    return api.post(`${API_BASE}/upload`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },

  /**
   * SSE 流式对话。使用原生 fetch 以便设置 Authorization 头。
   * 返回 ReadableStream，调用者自行解析 SSE 事件。
   */
  chatStream: async (
    question: string,
    sessionId?: string | null,
    attachments?: { file_id: string; file_type: string }[],
  ): Promise<Response> => {
    const token = localStorage.getItem('access_token')
    const baseUrl = import.meta.env.VITE_API_BASE_URL || '/api/v1'

    return fetch(`${baseUrl}${API_BASE}/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({
        question,
        session_id: sessionId || null,
        attachments: attachments || null,
      }),
    })
  },
}
