import { create } from 'zustand'
import { agentApi } from '../services/agent'
import type { ChatSession, ChatMessage, SSEEvent, FileType } from '../types/agent'

interface AgentState {
  sessions: ChatSession[]
  currentSessionId: string | null
  messages: ChatMessage[]
  isLoading: boolean
  isStreaming: boolean
  error: string | null

  loadSessions: () => Promise<void>
  createSession: () => Promise<string>
  switchSession: (sessionId: string) => Promise<void>
  deleteSession: (sessionId: string) => Promise<void>
  sendMessage: (content: string, attachments?: File[]) => Promise<void>
  stopGeneration: () => void
  clearError: () => void
}

let abortController: AbortController | null = null

export const useAgentStore = create<AgentState>((set, get) => ({
  sessions: [],
  currentSessionId: null,
  messages: [],
  isLoading: false,
  isStreaming: false,
  error: null,

  loadSessions: async () => {
    try {
      const res = await agentApi.listSessions()
      set({ sessions: res.data || [] })
    } catch {
      // ignore
    }
  },

  createSession: async () => {
    const res = await agentApi.createSession()
    const session = res.data
    set((state) => ({
      sessions: [session, ...state.sessions],
      currentSessionId: session.sessionId,
      messages: [],
    }))
    return session.sessionId
  },

  switchSession: async (sessionId: string) => {
    set({ isLoading: true, currentSessionId: sessionId })
    try {
      const res = await agentApi.getHistory(sessionId)
      set({ messages: res.data || [] })
    } catch {
      set({ messages: [] })
    } finally {
      set({ isLoading: false })
    }
  },

  deleteSession: async (sessionId: string) => {
    await agentApi.deleteSession(sessionId)
    const { currentSessionId } = get()
    set((state) => ({
      sessions: state.sessions.filter((s) => s.sessionId !== sessionId),
      currentSessionId: currentSessionId === sessionId ? null : currentSessionId,
      messages: currentSessionId === sessionId ? [] : state.messages,
    }))
  },

  sendMessage: async (content: string, attachments?: File[]) => {
    const { currentSessionId } = get()
    let sessionId = currentSessionId

    // 如果没有会话，自动创建
    if (!sessionId) {
      sessionId = await get().createSession()
    }

    // 上传附件并生成预览
    const uploadedAttachments: { file_id: string; file_type: FileType; fileName?: string; preview?: string }[] = []
    if (attachments && attachments.length > 0) {
      for (const file of attachments) {
        try {
          const res = await agentApi.uploadFile(file)
          // 根据文件名后缀判断类型（比 MIME 更可靠）
          const name = file.name.toLowerCase()
          let fileType: FileType
          if (file.type.startsWith('image/')) {
            fileType = 'image'
          } else if (name.endsWith('.pdf')) {
            fileType = 'pdf'
          } else if (name.endsWith('.docx') || name.endsWith('.doc')) {
            fileType = 'word'
          } else if (name.endsWith('.xlsx') || name.endsWith('.xls')) {
            fileType = 'excel'
          } else if (name.endsWith('.txt') || name.endsWith('.csv') || name.endsWith('.text')) {
            fileType = 'text'
          } else {
            fileType = 'image' // 未知类型默认尝试图片分析
          }
          const item: typeof uploadedAttachments[number] = {
            file_id: res.data.fileId,
            file_type: fileType,
            fileName: file.name,
          }
          // 生成图片预览
          if (file.type.startsWith('image/')) {
            item.preview = await new Promise<string>((resolve) => {
              const reader = new FileReader()
              reader.onloadend = () => resolve(reader.result as string)
              reader.readAsDataURL(file)
            })
          }
          uploadedAttachments.push(item)
        } catch {
          set({ error: `文件上传失败: ${file.name}` })
          return
        }
      }
    }

    // 添加用户消息到列表（含附件预览）
    const userMessage: ChatMessage = {
      id: Date.now(),
      sessionId: sessionId,
      role: 'user',
      content: content,
      attachments: uploadedAttachments.map(a => ({
        fileId: a.file_id,
        fileType: a.file_type,
        fileName: a.fileName,
        preview: a.preview,
      })),
      createdAt: new Date().toISOString(),
    }
    set((state) => ({
      messages: [...state.messages, userMessage],
      isStreaming: true,
      error: null,
    }))

    // 创建助手消息占位
    const assistantId = Date.now() + 1
    const assistantMessage: ChatMessage = {
      id: assistantId,
      sessionId: sessionId,
      role: 'assistant',
      content: '',
      toolCalls: [],
      createdAt: new Date().toISOString(),
    }
    set((state) => ({
      messages: [...state.messages, assistantMessage],
    }))

    // SSE 流式读取
    abortController = new AbortController()
    let fullContent = ''

    try {
      const response = await agentApi.chatStream(content, sessionId, uploadedAttachments)

      if (!response.ok || !response.body) {
        throw new Error(`请求失败: ${response.status}`)
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          const raw = line.slice(6).trim()
          if (!raw) continue

          try {
            const event: SSEEvent = JSON.parse(raw)
            const eventData = event.data

            if (event.event === 'text') {
              fullContent += eventData.content || ''
              set((state) => ({
                messages: state.messages.map((m) =>
                  m.id === assistantId ? { ...m, content: fullContent } : m,
                ),
              }))
            } else if (event.event === 'tool_call') {
              set((state) => ({
                messages: state.messages.map((m) =>
                  m.id === assistantId
                    ? {
                        ...m,
                        toolCalls: [
                          ...(m.toolCalls || []),
                          {
                            id: '',
                            name: eventData.name,
                            arguments: eventData.arguments,
                          },
                        ],
                      }
                    : m,
                ),
              }))
            } else if (event.event === 'tool_result') {
              // 更新最后一个工具调用的结果
              set((state) => ({
                messages: state.messages.map((m) => {
                  if (m.id !== assistantId || !m.toolCalls?.length) return m
                  const calls = [...m.toolCalls]
                  calls[calls.length - 1] = {
                    ...calls[calls.length - 1],
                    result: eventData.result,
                  }
                  return { ...m, toolCalls: calls }
                }),
              }))
            } else if (event.event === 'done') {
              // 如果有 session_id 更新
              if (eventData.session_id && !get().currentSessionId) {
                set({ currentSessionId: eventData.session_id })
              }
            } else if (event.event === 'error') {
              set({ error: eventData.message })
            }
          } catch {
            // JSON parse error, skip
          }
        }
      }
    } catch (e: any) {
      if (e.name !== 'AbortError') {
        set({ error: e.message || '对话出错' })
      }
    } finally {
      set({ isStreaming: false })
      abortController = null
    }
  },

  stopGeneration: () => {
    if (abortController) {
      abortController.abort()
      abortController = null
    }
    set({ isStreaming: false })
  },

  clearError: () => set({ error: null }),
}))
