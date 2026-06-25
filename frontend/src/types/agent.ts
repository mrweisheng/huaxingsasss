/**
 * Agent 智能助手相关类型定义
 */

export type FileType = 'image' | 'pdf' | 'word' | 'excel' | 'text'

export interface AttachmentItem {
  fileId: string
  fileType: FileType
  fileName?: string
  preview?: string // 图片 base64 预览
  pageCount?: number // PDF 才有，其他类型 undefined
}

export interface ThoughtStep {
  id: string
  message: string
  status: 'running' | 'done'
}

export interface DataReferenceItem {
  label: string
  value: string
  highlight?: 'warning' | 'success'
}

export interface DataReferenceSummary {
  type: 'data_reference'
  items: DataReferenceItem[]
}

export interface ToolCall {
  id: string
  name: string
  arguments: string
  result?: string
  summary?: DataReferenceSummary | null
}

export interface QuickReplyAction {
  label: string
  send_text: string
  style?: 'primary' | 'default' | 'danger'
}

export interface ChatMessage {
  id: number
  sessionId: string
  role: 'user' | 'assistant' | 'tool' | 'system'
  content: string
  attachments?: AttachmentItem[]
  toolCalls?: ToolCall[]
  thoughts?: ThoughtStep[]
  quickReplies?: QuickReplyAction[]
  intentType?: string
  isWelcome?: boolean
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

export interface ToolCallSummary {
  tool: string
  description: string
  args: Record<string, any>
}

export interface ContractInfo {
  contract_number: string
  customer_name: string
  business_type: string
}

export interface SSEEvent {
  event: 'text' | 'tool_call' | 'tool_result' | 'thinking' | 'done' | 'error' | 'ui_actions'
  data: Record<string, any>
}

export interface UploadResult {
  fileId: string
  fileName: string
  fileSize: number
  thumbnailUrl?: string | null
  pageCount?: number | null // 仅 PDF 返回页数，其他类型为 null
}
