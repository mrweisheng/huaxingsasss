/**
 * Agent 智能助手相关类型定义
 */

export type FileType = 'image' | 'pdf' | 'word' | 'excel' | 'text'

export interface AttachmentItem {
  fileId: string
  fileType: FileType
  fileName?: string
  preview?: string // 图片 base64 预览
}

export interface ThoughtStep {
  id: string
  message: string
  status: 'running' | 'done'
}

export interface ToolCall {
  id: string
  name: string
  arguments: string
  result?: string
}

export interface ChatMessage {
  id: number
  sessionId: string
  role: 'user' | 'assistant' | 'tool' | 'system'
  content: string
  attachments?: AttachmentItem[]
  toolCalls?: ToolCall[]
  thoughts?: ThoughtStep[]
  intentType?: string
  createdAt: string
}

export interface ChatSession {
  sessionId: string
  createdAt: string | null
  messageCount: number
  title: string | null
  mode: string
  context?: Record<string, any> | null
}

export interface SSEEvent {
  event: 'text' | 'tool_call' | 'tool_result' | 'thinking' | 'done' | 'error'
  data: Record<string, any>
}

export interface UploadResult {
  fileId: string
  fileName: string
  fileSize: number
}
