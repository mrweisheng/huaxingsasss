import api, { API_BASE_URL } from './api'
import type { ChatSession, ChatMessage, UploadResult } from '../types/agent'

const API_BASE = '/agent'

// api.ts 响应拦截器已解包 response.data，返回的即 body 对象 { code, data }
type ApiBody<T> = { code: number; data: T }

/** 后端 snake_case → 前端 camelCase */
function mapSession(raw: any): ChatSession {
  return {
    sessionId: raw.session_id,
    createdAt: raw.created_at ?? null,
    messageCount: raw.message_count ?? 0,
    title: raw.title ?? null,
    mode: raw.mode ?? 'chat',
    context: raw.context ?? null,
  }
}

function mapMessage(raw: any): ChatMessage {
  return {
    id: raw.id,
    sessionId: raw.session_id ?? '',
    role: raw.role,
    content: raw.content ?? '',
    toolCalls: raw.tool_calls ?? undefined,
    intentType: raw.intent_type ?? undefined,
    createdAt: raw.created_at ?? '',
  }
}

function mapUploadResult(raw: any): UploadResult {
  return {
    fileId: raw.file_id,
    fileName: raw.file_name ?? '',
    fileSize: raw.file_size ?? 0,
  }
}

export const agentApi = {
  createSession: async (options?: {
    title?: string
    mode?: string
    context?: Record<string, any>
  }): Promise<ApiBody<ChatSession>> => {
    const body: any = await api.post(`${API_BASE}/sessions`, options || {})
    return { code: body.code, data: mapSession(body.data) }
  },

  listSessions: async (): Promise<ApiBody<ChatSession[]>> => {
    const body: any = await api.get(`${API_BASE}/sessions`)
    return { code: body.code, data: (body.data || []).map(mapSession) }
  },

  deleteSession: (sessionId: string): Promise<any> =>
    api.delete(`${API_BASE}/sessions/${sessionId}`),

  getHistory: async (sessionId: string): Promise<ApiBody<ChatMessage[]>> => {
    const body: any = await api.get(`${API_BASE}/history/${sessionId}`)
    return { code: body.code, data: (body.data || []).map(mapMessage) }
  },

  uploadFile: async (file: File): Promise<ApiBody<UploadResult>> => {
    const formData = new FormData()
    formData.append('file', file)
    const body: any = await api.post(`${API_BASE}/upload`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return { code: body.code, data: mapUploadResult(body.data) }
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
    return _chatRequest({
      question,
      session_id: sessionId || null,
      attachments: attachments || null,
    })
  },

  /**
}

function _chatRequest(body: Record<string, any>): Promise<Response> {
  const token = localStorage.getItem('access_token')
  return fetch(`${API_BASE_URL}${API_BASE}/chat`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(body),
  })
}
