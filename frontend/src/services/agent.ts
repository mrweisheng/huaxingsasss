import api from './api'

export const agentApi = {
  chat: (question: string, sessionId?: string, signal?: AbortSignal): Promise<any> =>
    api.post('/agent/chat', {
      question,
      session_id: sessionId,
    }, { signal }),

  getHistory: (sessionId?: string, signal?: AbortSignal): Promise<any> =>
    api.get('/agent/history', {
      params: { session_id: sessionId },
      signal,
    }),
}
