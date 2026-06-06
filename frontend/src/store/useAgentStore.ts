import { create } from 'zustand'
import { agentApi } from '../services/agent'
import type { ChatSession, ChatMessage, SSEEvent, FileType, InterruptInfo } from '../types/agent'

interface AgentState {
  sessions: ChatSession[]
  currentSessionId: string | null
  messages: ChatMessage[]
  isLoading: boolean
  isStreaming: boolean
  error: string | null
  interruptInfo: InterruptInfo | null

  loadSessions: () => Promise<void>
  createSession: () => Promise<string>
  switchSession: (sessionId: string) => Promise<void>
  deleteSession: (sessionId: string) => Promise<void>
  sendMessage: (content: string, attachments?: File[]) => Promise<void>
  resumeInterrupt: (confirmed: boolean) => Promise<void>
  dismissInterrupt: () => void
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
  interruptInfo: null,

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

    // 立即标记流式状态，防止前端重复提交（发送按钮变为停止按钮）
    set({ isStreaming: true, error: null })

    // 如果没有会话，自动创建
    if (!sessionId) {
      sessionId = await get().createSession()
    }

    // 立即生成附件本地预览（不等上传，让用户消息秒出）
    const localAttachments: { file: File; fileType: FileType; preview?: string }[] = []
    if (attachments && attachments.length > 0) {
      for (const file of attachments) {
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
          fileType = 'image'
        }
        let preview: string | undefined
        if (file.type.startsWith('image/')) {
          preview = await new Promise<string>((resolve) => {
            const reader = new FileReader()
            reader.onloadend = () => resolve(reader.result as string)
            reader.readAsDataURL(file)
          })
        }
        localAttachments.push({ file, fileType, preview })
      }
    }

    // 一次性添加用户消息 + 助手占位消息（避免两次 set 之间出现双头像）
    const userMsgId = Date.now()
    const userMessage: ChatMessage = {
      id: userMsgId,
      sessionId: sessionId,
      role: 'user',
      content: content,
      attachments: localAttachments.map(a => ({
        fileId: `pending_${Date.now()}`,
        fileType: a.fileType,
        fileName: a.file.name,
        preview: a.preview,
      })),
      createdAt: new Date().toISOString(),
    }
    const assistantId = userMsgId + 1
    const assistantMessage: ChatMessage = {
      id: assistantId,
      sessionId: sessionId,
      role: 'assistant',
      content: '',
      toolCalls: [],
      thoughts: [],
      createdAt: new Date().toISOString(),
    }
    set((state) => ({
      messages: [...state.messages, userMessage, assistantMessage],
    }))

    // 后台上传附件，获取服务端 file_id（用户已看到消息，不会感知等待）
    const uploadedAttachments: { file_id: string; file_type: FileType; fileName?: string; preview?: string }[] = []
    if (localAttachments.length > 0) {
      for (const local of localAttachments) {
        try {
          const res = await agentApi.uploadFile(local.file)
          uploadedAttachments.push({
            file_id: res.data.fileId,
            file_type: local.fileType,
            fileName: local.file.name,
            preview: local.preview,
          })
        } catch {
          set({ error: `文件上传失败: ${local.file.name}` })
          return
        }
      }
    }

    // SSE 流式读取
    abortController = new AbortController()
    let thoughtStepId = 0

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
        if (abortController.signal.aborted) break

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
              // 逐字流式追加（typewriter effect）
              const chunk = eventData.content || ''
              set((state) => ({
                messages: state.messages.map((m) =>
                  m.id === assistantId ? { ...m, content: m.content + chunk } : m,
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
                            id: eventData.id || `tc_${Date.now()}`,
                            name: eventData.name,
                            arguments: eventData.arguments,
                          },
                        ],
                      }
                    : m,
                ),
              }))
            } else if (event.event === 'tool_result') {
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
            } else if (event.event === 'interrupt') {
              // LangGraph interrupt → 显示确认面板
              const info: InterruptInfo = {
                type: eventData.type || 'contract_confirmation',
                message: eventData.message || '',
                preview: eventData.preview,
                options: eventData.options || [],
                interrupt_id: eventData.interrupt_id || '',
              }
              set({ interruptInfo: info, isStreaming: false })
            } else if (event.event === 'done') {
              // 被中断的 done 已在 interrupt 事件中处理，跳过重复 set
              if (eventData.interrupted) {
                if (eventData.session_id && !get().currentSessionId) {
                  set({ currentSessionId: eventData.session_id })
                }
                // isStreaming 已在 interrupt 事件中设置 false
                return
              }
              // 标记最后一个 thought 为 done
              set((state) => ({
                messages: state.messages.map((m) => {
                  if (m.id !== assistantId || !m.thoughts?.length) return m
                  const thoughts = [...m.thoughts]
                  const last = thoughts[thoughts.length - 1]
                  if (last && last.status === 'running') {
                    thoughts[thoughts.length - 1] = { ...last, status: 'done' as const }
                  }
                  return { ...m, thoughts }
                }),
              }))
              if (eventData.session_id && !get().currentSessionId) {
                set({ currentSessionId: eventData.session_id })
              }
            } else if (event.event === 'error') {
              set({ error: eventData.message })
            } else if (event.event === 'thinking') {
              // 累积式思考步骤，不替换
              const msg = eventData.message || '思考中...'
              const stepId = `thought_${thoughtStepId++}`
              set((state) => ({
                messages: state.messages.map((m) => {
                  if (m.id !== assistantId) return m
                  const thoughts = [...(m.thoughts || [])]
                  // 如果上一步是 running，标记为 done
                  if (thoughts.length > 0 && thoughts[thoughts.length - 1].status === 'running') {
                    thoughts[thoughts.length - 1] = { ...thoughts[thoughts.length - 1], status: 'done' as const }
                  }
                  thoughts.push({ id: stepId, message: msg, status: 'running' })
                  return { ...m, thoughts }
                }),
              }))
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

  resumeInterrupt: async (confirmed: boolean) => {
    const { currentSessionId, interruptInfo } = get()
    if (!currentSessionId || !interruptInfo) return

    set({ isStreaming: true, interruptInfo: null, error: null })

    const assistantId = Date.now() + 1
    const assistantMessage: ChatMessage = {
      id: assistantId,
      sessionId: currentSessionId,
      role: 'assistant',
      content: '',
      toolCalls: [],
      thoughts: [{ id: 'resume_0', message: '正在处理...', status: 'running' }],
      createdAt: new Date().toISOString(),
    }
    set((state) => ({ messages: [...state.messages, assistantMessage] }))

    abortController = new AbortController()
    let thoughtStepId = 1

    try {
      const response = await agentApi.resumeInterrupt(
        currentSessionId,
        { confirmed },
        interruptInfo.interrupt_id,
      )

      if (!response.ok || !response.body) {
        throw new Error(`请求失败: ${response.status}`)
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        if (abortController?.signal.aborted) break

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
              set((state) => ({
                messages: state.messages.map((m) =>
                  m.id === assistantId ? { ...m, content: m.content + (eventData.content || '') } : m,
                ),
              }))
            } else if (event.event === 'thinking') {
              const msg = eventData.message || '思考中...'
              const stepId = `thought_${thoughtStepId++}`
              set((state) => ({
                messages: state.messages.map((m) => {
                  if (m.id !== assistantId) return m
                  const thoughts = [...(m.thoughts || [])]
                  if (thoughts.length > 0 && thoughts[thoughts.length - 1].status === 'running') {
                    thoughts[thoughts.length - 1] = { ...thoughts[thoughts.length - 1], status: 'done' as const }
                  }
                  thoughts.push({ id: stepId, message: msg, status: 'running' })
                  return { ...m, thoughts }
                }),
              }))
            } else if (event.event === 'done') {
              if (eventData.interrupted) {
                set({ isStreaming: false })
                return
              }
              set((state) => ({
                messages: state.messages.map((m) => {
                  if (m.id !== assistantId || !m.thoughts?.length) return m
                  const thoughts = [...m.thoughts]
                  const last = thoughts[thoughts.length - 1]
                  if (last && last.status === 'running') {
                    thoughts[thoughts.length - 1] = { ...last, status: 'done' as const }
                  }
                  return { ...m, thoughts }
                }),
              }))
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

  dismissInterrupt: () => set({ interruptInfo: null }),

  stopGeneration: () => {
    if (abortController) {
      abortController.abort()
      abortController = null
    }
    set({ isStreaming: false })
  },

  clearError: () => set({ error: null }),
}))
