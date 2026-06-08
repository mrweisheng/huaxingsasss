import { create } from 'zustand'
import { agentApi } from '../services/agent'
import type { ChatSession, ChatMessage, FileType, InterruptInfo } from '../types/agent'
import {
  readSSEStream,
  computeEventUpdates,
  applyMessageUpdates,
} from '@/lib/sseStream'

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
 * 把单个 SSE 事件应用到 store：消息列表更新 + 外层状态（interruptInfo / error / sessionId）。
 * 返回 [action, nextThoughtId]，调用方根据 action 决定是否提前退出循环。
 */
function applyEventToStore(
  event: Parameters<typeof computeEventUpdates>[0],
  assistantId: number,
  thoughtStepId: number,
  set: (partial: Partial<AgentState> | ((state: AgentState) => Partial<AgentState>)) => void,
  get: () => AgentState,
): [import('@/lib/sseStream').DispatchAction, number] {
  const result = computeEventUpdates(event, {
    assistantId,
    thoughtStepId,
    hasCurrentSessionId: !!get().currentSessionId,
  })

  if (result.textAppend || result.toolCallAppend || result.toolResultLast ||
      result.thoughtAppend || result.thoughtFinalizeLast) {
    set((state) => ({
      messages: applyMessageUpdates(state.messages, result, assistantId),
    }))
  }

  if (result.interruptInfo) {
    set({ interruptInfo: result.interruptInfo, isStreaming: false })
  }

  if (result.sessionIdSync) {
    set({ currentSessionId: result.sessionIdSync })
  }

  if (result.errorMessage) {
    set({ error: result.errorMessage })
  }

  return [result.action, result.nextThoughtId]
}

/** 把客户端 File 列表转换为上传后的服务端附件元数据。*/
async function uploadPendingFiles(
  localAttachments: { file: File; fileType: FileType; preview?: string }[],
): Promise<{ file_id: string; file_type: FileType; fileName?: string; preview?: string }[]> {
  const uploaded: { file_id: string; file_type: FileType; fileName?: string; preview?: string }[] = []
  for (const local of localAttachments) {
    const res = await agentApi.uploadFile(local.file)
    uploaded.push({
      file_id: res.data.fileId,
      file_type: local.fileType,
      fileName: local.file.name,
      preview: local.preview,
    })
  }
  return uploaded
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

    set({ isStreaming: true, error: null })

    if (!sessionId) {
      sessionId = await get().createSession()
    }

    // 生成本地附件预览（图片 base64），不阻塞 UI
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

    // 一次性插入用户消息 + 助手占位
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

    // 上传附件 → 拿 file_id
    let uploadedAttachments: { file_id: string; file_type: FileType; fileName?: string; preview?: string }[] = []
    if (localAttachments.length > 0) {
      try {
        uploadedAttachments = await uploadPendingFiles(localAttachments)
      } catch (e: any) {
        set({ error: e?.response?.data?.detail || e.message || '文件上传失败' })
        set({ isStreaming: false })
        return
      }
    }

    abortController = new AbortController()
    let thoughtStepId = 0

    try {
      const response = await agentApi.chatStream(content, sessionId, uploadedAttachments)
      if (!response.ok || !response.body) {
        throw new Error(`请求失败: ${response.status}`)
      }

      for await (const event of readSSEStream(response, abortController.signal)) {
        const [action, nextThoughtId] = applyEventToStore(event, assistantId, thoughtStepId, set, get)
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
    let thoughtStepId = 1  // 0 已被 resume_0 占用

    try {
      const response = await agentApi.resumeInterrupt(
        currentSessionId,
        resumeValue,
        interruptInfo.interrupt_id,
      )
      if (!response.ok || !response.body) {
        throw new Error(`请求失败: ${response.status}`)
      }

      for await (const event of readSSEStream(response, abortController.signal)) {
        const [action, nextThoughtId] = applyEventToStore(event, assistantId, thoughtStepId, set, get)
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
