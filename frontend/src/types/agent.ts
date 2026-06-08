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

export interface InterruptOption {
  label: string
  value: Record<string, any>
}

export interface ToolCallSummary {
  tool: string
  description: string
  args: Record<string, any>
}

export interface ReceiptConfirmData {
  payee_name: string
  amount: number
  currency: string
  paid_date: string
  payment_method: string
  description: string
  installment_name: string
  notes: string
}

export interface ContractInfo {
  contract_number: string
  customer_name: string
  business_type: string
}

export interface InterruptInfo {
  type: string
  message: string
  tool_calls?: ToolCallSummary[]
  preview?: Record<string, any>  // 向后兼容旧 interrupt 格式
  // 凭证确认专用字段
  receipt_data?: ReceiptConfirmData
  contract_info?: ContractInfo
  payment_type?: string
  match_warning?: string
  options: InterruptOption[]
  interrupt_id: string
}

export interface SSEEvent {
  event: 'text' | 'tool_call' | 'tool_result' | 'thinking' | 'done' | 'error' | 'interrupt'
  data: Record<string, any>
}

export interface UploadResult {
  fileId: string
  fileName: string
  fileSize: number
}
