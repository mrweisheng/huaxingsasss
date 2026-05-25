import api from './api'

export const agentApi = {
  chat: (question: string, sessionId?: string): Promise<any> =>
    api.post('/agent/chat', {
      question,
      session_id: sessionId,
    }),

  getHistory: (sessionId?: string): Promise<any> =>
    api.get('/agent/history', {
      params: { session_id: sessionId },
    }),
}
