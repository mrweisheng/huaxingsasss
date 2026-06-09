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
  event: 'text' | 'tool_call' | 'tool_result' | 'thinking' | 'done' | 'error'
  data: Record<string, any>
}

export interface UploadResult {
  fileId: string
  fileName: string
  fileSize: number
}
