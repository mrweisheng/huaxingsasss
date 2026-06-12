import { create } from 'zustand'
import { agentApi } from '../services/agent'
import type { ChatSession, ChatMessage, FileType } from '../types/agent'
import {
  readSSEStream,
  computeEventUpdates,
  applyMessageUpdates,
  mergeTextAppends,
} from '@/lib/sseStream'

interface AgentState {
  sessions: ChatSession[]
  currentSessionId: string | null
  messages: ChatMessage[]
  isLoading: boolean
  isStreaming: boolean
  error: string | null
  /**
   * 当前会话选中的工具标签（贴在输入框前的标签）。
   * contract_entry: 录合同；receipt_income: 录收入；receipt_expense: 录支出；null: 通用
   * 选中工具后，sendMessage 会把 mode 透传给后端（防御：后端 mode guard 拦截越权工具）。
   */
  selectedTool: 'contract_entry' | 'receipt_income' | 'receipt_expense' | null

  loadSessions: () => Promise<void>
  createSession: (mode?: 'chat' | 'contract_entry' | 'receipt_income' | 'receipt_expense', title?: string) => Promise<string>
  switchSession: (sessionId: string) => Promise<void>
  deleteSession: (sessionId: string) => Promise<void>
  sendMessage: (
    content: string,
    pendingAttachments?: Array<{ file: File; uploaded?: { fileId: string; fileName?: string; fileSize?: number; thumbnailUrl?: string | null } }>,
  ) => Promise<void>
  stopGeneration: () => void
  clearError: () => void
  setSelectedTool: (tool: AgentState['selectedTool']) => void
  resetChat: () => void
}

let abortController: AbortController | null = null

/**
 * 把单个 SSE 事件应用到 store：消息列表更新 + 外层状态（error / sessionId）。
 * text 事件除外：textAppend 由调用方通过 rAF 合并机制刷入，此处跳过。
 * 返回 [action, nextThoughtId, textAppend]，调用方根据 action 决定是否提前退出循环。
 */
function applyEventToStore(
  event: Parameters<typeof computeEventUpdates>[0],
  assistantId: number,
  thoughtStepId: number,
  set: (partial: Partial<AgentState> | ((state: AgentState) => Partial<AgentState>)) => void,
  get: () => AgentState,
): [import('@/lib/sseStream').DispatchAction, number, string | undefined] {
  const result = computeEventUpdates(event, {
    assistantId,
    thoughtStepId,
    hasCurrentSessionId: !!get().currentSessionId,
  })

  // text 事件：不在此处 set()，返回 textAppend 让调用方通过 rAF 合并刷入
  if (result.textAppend) {
    // 仍需处理其他附带状态（如 sessionIdSync）
    if (result.sessionIdSync) {
      set({ currentSessionId: result.sessionIdSync })
    }
    return [result.action, result.nextThoughtId, result.textAppend]
  }

  if (result.toolCallAppend || result.toolResultLast ||
      result.thoughtAppend || result.thoughtFinalizeLast) {
    set((state) => ({
      messages: applyMessageUpdates(state.messages, result, assistantId),
    }))
  }

  if (result.sessionIdSync) {
    set({ currentSessionId: result.sessionIdSync })
  }

  if (result.errorMessage) {
    set({ error: result.errorMessage })
  }

  return [result.action, result.nextThoughtId, undefined]
}

/** 把客户端 File 列表转换为上传后的服务端附件元数据。
 *  - 如果传入了 uploaded（HEIC 已在选文件时上传），直接复用，跳过上传
 *  - 否则调后端 /agent/upload
 */
async function uploadPendingFiles(
  localAttachments: { file: File; fileType: FileType; preview?: string; uploaded?: { fileId: string; fileName?: string; fileSize?: number; thumbnailUrl?: string | null } }[],
): Promise<{ file_id: string; file_type: FileType; fileName?: string; preview?: string; thumbnailUrl?: string }[]> {
  const uploaded: { file_id: string; file_type: FileType; fileName?: string; preview?: string; thumbnailUrl?: string }[] = []
  for (const local of localAttachments) {
    if (local.uploaded) {
      // HEIC 已在选文件时上传完成：直接复用 fileId/thumbnailUrl
      uploaded.push({
        file_id: local.uploaded.fileId,
        file_type: local.fileType,
        fileName: local.file.name,
        preview: local.uploaded.thumbnailUrl ?? local.preview,
        thumbnailUrl: local.uploaded.thumbnailUrl ?? undefined,
      })
    } else {
      const res = await agentApi.uploadFile(local.file)
      uploaded.push({
        file_id: res.data.fileId,
        file_type: local.fileType,
        fileName: local.file.name,
        preview: local.preview,
        thumbnailUrl: res.data.thumbnailUrl ?? undefined,
      })
    }
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
  selectedTool: null,

  loadSessions: async () => {
    try {
      const res = await agentApi.listSessions()
      set({ sessions: res.data || [] })
    } catch {
      // ignore
    }
  },

  createSession: async (mode?: 'chat' | 'contract_entry' | 'receipt_income' | 'receipt_expense', title?: string) => {
    const res = await agentApi.createSession({ mode: mode || 'chat', title })
    const session = res.data
    set((state) => ({
      sessions: [session, ...state.sessions],
      currentSessionId: session.sessionId,
      messages: [],
    }))
    return session.sessionId
  },

  switchSession: async (sessionId: string) => {
    set({ isLoading: true, currentSessionId: sessionId, selectedTool: null })
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

  setSelectedTool: (tool) => set({ selectedTool: tool }),

  sendMessage: async (
    content: string,
    pendingAttachments?: Array<{ file: File; uploaded?: { fileId: string; fileName?: string; fileSize?: number; thumbnailUrl?: string | null } }>,
  ) => {
    const { currentSessionId, selectedTool } = get()
    let sessionId = currentSessionId

    set({ isStreaming: true, error: null, selectedTool: null })

    if (!sessionId) {
      // 第一次发消息：用消息内容前 50 字作标题
      const title = content.slice(0, 50)
      sessionId = await get().createSession(selectedTool || 'chat', title)
    }

    // 生成本地附件预览（图片 base64），不阻塞 UI
    // 已上传的 HEIC 直接用 thumbnailUrl 作为 preview，不再 FileReader
    const localAttachments: { file: File; fileType: FileType; preview?: string; uploaded?: { fileId: string; fileName?: string; fileSize?: number; thumbnailUrl?: string | null } }[] = []
    if (pendingAttachments && pendingAttachments.length > 0) {
      for (const pa of pendingAttachments) {
        const file = pa.file
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
        if (pa.uploaded) {
          // HEIC 已在选文件时上传完成，直接用后端返回的 JPEG thumbnail_url 作为预览
          preview = pa.uploaded.thumbnailUrl ?? undefined
        } else {
          // HEIC 跳过 FileReader base64 预览：Chrome 无法渲染 data:image/heic
          // 此时意味着调用方没有提前上传（理论上不会发生——HEIC 必提前上传），防御性跳过
          const isHeic = name.endsWith('.heic') || name.endsWith('.heif')
          if (file.type.startsWith('image/') && !isHeic) {
            preview = await new Promise<string>((resolve) => {
              const reader = new FileReader()
              reader.onloadend = () => resolve(reader.result as string)
              reader.readAsDataURL(file)
            })
          }
        }
        localAttachments.push({ file, fileType, preview, uploaded: pa.uploaded })
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
    let uploadedAttachments: { file_id: string; file_type: FileType; fileName?: string; preview?: string; thumbnailUrl?: string }[] = []
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

    // rAF 合并渲染：同一帧内的多个 text chunk 合并为一次 state 更新
    let pendingTextChunks: string[] = []
    let rafHandle: number | null = null

    const flushText = () => {
      if (pendingTextChunks.length === 0) return
      const merged = mergeTextAppends(pendingTextChunks)
      pendingTextChunks = []
      rafHandle = null
      set((state) => ({
        messages: applyMessageUpdates(state.messages, {
          action: 'continue',
          nextThoughtId: thoughtStepId,
          textAppend: merged,
        }, assistantId),
      }))
    }

    const scheduleFlush = () => {
      if (rafHandle === null) {
        rafHandle = requestAnimationFrame(flushText)
      }
    }

    try {
      const response = await agentApi.chatStream(content, sessionId, uploadedAttachments, selectedTool || undefined)
      if (!response.ok || !response.body) {
        throw new Error(`请求失败: ${response.status}`)
      }

      for await (const event of readSSEStream(response, abortController.signal)) {
        const [action, nextThoughtId, textAppend] = applyEventToStore(event, assistantId, thoughtStepId, set, get)
        thoughtStepId = nextThoughtId

        // text 事件：缓冲后 rAF 合并渲染，避免逐 chunk set() 导致卡顿
        if (textAppend) {
          pendingTextChunks.push(textAppend)
          scheduleFlush()
        }

        if (action === 'done-normal' || action === 'error') {
          // 退出前刷出剩余 text
          if (rafHandle !== null) cancelAnimationFrame(rafHandle)
          flushText()
          return
        }
      }
      // 流结束，刷出剩余 text
      if (rafHandle !== null) cancelAnimationFrame(rafHandle)
      flushText()
    } catch (e: any) {
      if (e.name !== 'AbortError') {
        set({ error: e.message || '对话出错' })
      }
    } finally {
      // 阅后即焚：消息生命周期结束（流完成/中断/出错）→ 清掉工具高亮态。
      // 注意：session.mode 还在（跟着 session 走），后端会自动让后续消息继续走对应 subgraph；
      // 前端按钮只是"下一次发送是否注入 intent"的开关，发完就清，避免视觉上"一直按下"的违和感。
      set({ isStreaming: false, selectedTool: null })
      abortController = null
      if (rafHandle !== null) cancelAnimationFrame(rafHandle)
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

  resetChat: () => set({ currentSessionId: null, messages: [], selectedTool: null }),
}))
