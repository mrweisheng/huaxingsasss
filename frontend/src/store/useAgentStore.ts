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
  resumeInterrupt: (resumeValue: Record<string, any>) => Promise<void>
  dismissInterrupt: () => Promise<void>
  stopGeneration: () => void
  clearError: () => void
}

let abortController: AbortController | null = null

/**
 * 通用 SSE 流读取器 — 消除 sendMessage / resumeInterrupt 中的重复代码。
 * 从 Response body 逐行解析 SSE 事件，通过 AsyncGenerator 对外暴露。
 */
async function* readSSEStream(
  response: Response,
  signal: AbortSignal | null,
): AsyncGenerator<SSEEvent> {
  if (!response.body) return

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      if (signal?.aborted) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        const raw = line.slice(6).trim()
        if (!raw) continue

        try {
          const event: SSEEvent = JSON.parse(raw)
          yield event
        } catch {
          // JSON parse error, skip
        }
      }
    }
  } finally {
    reader.releaseLock()
  }
}

/**
 * SSE 事件分发器。sendMessage 和 resumeInterrupt 共用。
 *
 * 行为：
 *  - text           → 追加到指定 assistant 消息 content
 *  - tool_call      → 追加到 toolCalls
 *  - tool_result    → 回填到最后一个 toolCall
 *  - thinking       → 累积式思考步骤，thoughtStepId 自增
 *  - interrupt      → 写入 interruptInfo 并清 streaming
 *  - done (interrupted) → 维持中断面板，仅同步 session_id
 *  - done (正常)    → 收尾 thought 步骤 + 同步 session_id
 *  - error          → 写入 error
 *
 * 返回 [action, nextThoughtId]，action 让调用方决定是否提前退出循环。
 */
type DispatchAction = 'continue' | 'interrupt' | 'done-interrupted' | 'done-normal' | 'error'

function dispatchSSEEvent(
  event: SSEEvent,
  assistantId: number,
  thoughtStepId: number,
  set: (partial: Partial<AgentState> | ((state: AgentState) => Partial<AgentState>)) => void,
  get: () => AgentState,
): [DispatchAction, number] {
  const eventData = event.data

  if (event.event === 'text') {
    const chunk = eventData.content || ''
    set((state) => ({
      messages: state.messages.map((m) =>
        m.id === assistantId ? { ...m, content: m.content + chunk } : m,
      ),
    }))
    return ['continue', thoughtStepId]
  }

  if (event.event === 'tool_call') {
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
    return ['continue', thoughtStepId]
  }

  if (event.event === 'tool_result') {
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
    return ['continue', thoughtStepId]
  }

  if (event.event === 'thinking') {
    const msg = eventData.message || '思考中...'
    const stepId = `thought_${thoughtStepId}`
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
    return ['continue', thoughtStepId + 1]
  }

  if (event.event === 'interrupt') {
    const info: InterruptInfo = {
      type: eventData.type || 'contract_confirmation',
      message: eventData.message || '',
      tool_calls: eventData.tool_calls,
      preview: eventData.preview,
      options: eventData.options || [],
      interrupt_id: eventData.interrupt_id || '',
    }
    set({ interruptInfo: info, isStreaming: false })
    return ['interrupt', thoughtStepId]
  }

  if (event.event === 'done') {
    if (eventData.interrupted) {
      if (eventData.session_id && !get().currentSessionId) {
        set({ currentSessionId: eventData.session_id })
      }
      return ['done-interrupted', thoughtStepId]
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
    if (eventData.session_id && !get().currentSessionId) {
      set({ currentSessionId: eventData.session_id })
    }
    return ['done-normal', thoughtStepId]
  }

  if (event.event === 'error') {
    set({ error: eventData.message })
    return ['error', thoughtStepId]
  }

  return ['continue', thoughtStepId]
}

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

      for await (const event of readSSEStream(response, abortController.signal)) {
        const [action, nextThoughtId] = dispatchSSEEvent(event, assistantId, thoughtStepId, set, get)
        thoughtStepId = nextThoughtId
        if (action === 'interrupt' || action === 'done-interrupted' || action === 'error') {
          return
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

  resumeInterrupt: async (resumeValue: Record<string, any>) => {
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
    // 起始计数器为 1，因为初始 'resume_0' 思考步骤已占用 0
    let thoughtStepId = 1

    try {
      // 透传整段 opt.value：当前是 {confirmed: bool}，
      // Phase 2 扩展为 {customer_id, customer_name} / {business_type} / {currency} / {date} 等
      // 时不需要再改 store，只需 InterruptPanel 传不同 shape
      const response = await agentApi.resumeInterrupt(
        currentSessionId,
        resumeValue,
        interruptInfo.interrupt_id,
      )

      if (!response.ok || !response.body) {
        throw new Error(`请求失败: ${response.status}`)
      }

      for await (const event of readSSEStream(response, abortController.signal)) {
        const [action, nextThoughtId] = dispatchSSEEvent(event, assistantId, thoughtStepId, set, get)
        thoughtStepId = nextThoughtId
        // interrupt / done-interrupted / error 任一都退出循环
        // 注意：resume 过程中可能再次触发 interrupt（多步交互），dispatcher 会写入
        // 新 interruptInfo 并返回 'interrupt'，UI 自动展示新面板
        if (action === 'interrupt' || action === 'done-interrupted' || action === 'error') {
          return
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

  dismissInterrupt: async () => {
    // 通知后端 LangGraph 取消（发送 confirmed: false），让图正常走完
    // summarize_cancel_node → finalize_node → END，避免 checkpoint 残留。
    // 加 await：保证后端进入取消流程后才返回，避免后端响应失败时
    // 前端已清面板但 checkpoint 仍卡在 wait_user_confirm_node 的竞态。
    const { currentSessionId, interruptInfo } = get()
    if (currentSessionId && interruptInfo) {
      await get().resumeInterrupt({ confirmed: false })
    } else {
      set({ interruptInfo: null })
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
