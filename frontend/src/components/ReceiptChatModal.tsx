import { useState, useRef, useEffect, useCallback } from 'react'
import {
  Modal, Input, Button, Avatar, Upload, Tag, Spin, message,
} from 'antd'
import {
  SendOutlined, RobotOutlined, UserOutlined, PaperClipOutlined,
  StopOutlined, InboxOutlined, CheckCircleOutlined, ExclamationCircleOutlined,
  ToolOutlined, FilePdfOutlined, FileWordOutlined, FileExcelOutlined, FileTextOutlined,
} from '@ant-design/icons'
import { agentApi } from '@/services/agent'
import type { ChatMessage, FileType, ToolCall } from '@/types/agent'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import './ReceiptChatModal.css'

interface ReceiptChatModalProps {
  open: boolean
  contractId: number
  contractNumber: string
  customerName: string
  paymentType: 'income' | 'expense'
  onClose: () => void
}

const TYPE_LABELS = { income: '收入', expense: '支出' }
const TOOL_LABELS: Record<string, string> = {
  analyze_image: '文件分析',
  create_payment: '创建收入',
  create_expense: '创建支出',
  update_payment: '更新记录',
  get_contract_detail: '合同详情',
  query_payments: '查询付款',
}

function ToolCallView({ toolCall }: { toolCall: ToolCall }) {
  const label = TOOL_LABELS[toolCall.name] || toolCall.name
  const hasResult = !!toolCall.result
  return (
    <Tag
      color={hasResult ? 'green' : 'orange'}
      icon={hasResult ? <CheckCircleOutlined /> : <ExclamationCircleOutlined />}
      style={{ marginBottom: 4, borderRadius: 4 }}
    >
      <ToolOutlined /> {label}
    </Tag>
  )
}

function MarkdownRenderer({ content }: { content: string }) {
  return (
    <div className="receipt-chat-markdown">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          p: ({ children }) => <p style={{ margin: '4px 0', lineHeight: 1.7 }}>{children}</p>,
          strong: ({ children }) => <strong style={{ color: 'var(--brand-primary)' }}>{children}</strong>,
          ul: ({ children }) => <ul style={{ margin: '4px 0', paddingLeft: 18 }}>{children}</ul>,
          ol: ({ children }) => <ol style={{ margin: '4px 0', paddingLeft: 18 }}>{children}</ol>,
          li: ({ children }) => <li style={{ margin: '2px 0' }}>{children}</li>,
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  )
}

function MessageBubble({ msg }: { msg: ChatMessage }) {
  if (msg.role === 'user') {
    return (
      <div className="receipt-chat-msg receipt-chat-msg-user">
        <div className="receipt-chat-msg-content receipt-chat-msg-user-content">
          {msg.attachments && msg.attachments.length > 0 && (
            <div className="receipt-chat-attachments">
              {msg.attachments.map((att, i) => {
                if (att.fileType === 'image' && att.preview) {
                  return (
                    <img
                      key={i} src={att.preview} alt={att.fileName || '附件'}
                      className="receipt-chat-attachment-img"
                    />
                  )
                }
                const fileIcon = att.fileType === 'pdf' ? <FilePdfOutlined />
                  : att.fileType === 'word' ? <FileWordOutlined />
                  : att.fileType === 'excel' ? <FileExcelOutlined />
                  : <FileTextOutlined />
                return <Tag key={i} color="blue">{fileIcon} {att.fileName || '文件'}</Tag>
              })}
            </div>
          )}
          <div className="receipt-chat-bubble receipt-chat-bubble-user">
            {msg.content || (msg.attachments?.length ? `已上传 ${msg.attachments.length} 个文件` : '')}
          </div>
        </div>
        <Avatar icon={<UserOutlined />} className="receipt-chat-avatar-user" size={32} />
      </div>
    )
  }

  if (msg.role === 'assistant') {
    return (
      <div className="receipt-chat-msg receipt-chat-msg-assistant">
        <Avatar icon={<RobotOutlined />} className="receipt-chat-avatar-bot" size={32} />
        <div className="receipt-chat-msg-content receipt-chat-msg-bot-content">
          {msg.toolCalls && msg.toolCalls.length > 0 && (
            <div className="receipt-chat-tool-calls">
              {msg.toolCalls.map((tc, i) => <ToolCallView key={i} toolCall={tc} />)}
            </div>
          )}
          {msg.content ? (
            <div className="receipt-chat-bubble receipt-chat-bubble-bot">
              <MarkdownRenderer content={msg.content} />
            </div>
          ) : (msg as any)._thinking ? (
            <div className="receipt-chat-thinking">
              <Spin size="small" />
              {(msg as any)._thinking}
            </div>
          ) : msg.toolCalls?.length ? (
            <Spin size="small" style={{ marginTop: 8 }} />
          ) : null}
        </div>
      </div>
    )
  }
  return null
}

export default function ReceiptChatModal({
  open, contractId, contractNumber, customerName, paymentType, onClose,
}: ReceiptChatModalProps) {
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [inputText, setInputText] = useState('')
  const [pendingFiles, setPendingFiles] = useState<File[]>([])
  const [isStreaming, setIsStreaming] = useState(false)
  const [isInitializing, setIsInitializing] = useState(false)
  const abortRef = useRef<AbortController | null>(null)
  const scrollRef = useRef<HTMLDivElement>(null)

  const typeLabel = TYPE_LABELS[paymentType]
  const title = `录入${typeLabel} · ${contractNumber} ${customerName}`

  // 打开时创建 session
  useEffect(() => {
    if (!open) return
    let cancelled = false
    setIsInitializing(true)
    setMessages([])
    setInputText('')
    setPendingFiles([])

    agentApi.createSession({
      title,
      mode: paymentType === 'income' ? 'receipt_income' : 'receipt_expense',
      context: { contract_id: contractId, payment_type: paymentType },
    }).then((res) => {
      if (!cancelled) {
        setSessionId(res.data.sessionId)
        setIsInitializing(false)
        // 添加欢迎消息
        setMessages([{
          id: Date.now(),
          sessionId: res.data.sessionId,
          role: 'assistant',
          content: `请上传${typeLabel}凭证（图片或 PDF），我来帮你分析并录入。`,
          createdAt: new Date().toISOString(),
        }])
      }
    }).catch(() => {
      if (!cancelled) {
        setIsInitializing(false)
        message.error('创建会话失败')
      }
    })

    return () => { cancelled = true }
  }, [open, contractId, paymentType])

  // 自动滚到底部
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [messages])

  // 判断文件类型
  const getFileType = (file: File): FileType => {
    if (file.type.startsWith('image/')) return 'image'
    const name = file.name.toLowerCase()
    if (name.endsWith('.pdf')) return 'pdf'
    if (name.endsWith('.docx') || name.endsWith('.doc')) return 'word'
    if (name.endsWith('.xlsx') || name.endsWith('.xls')) return 'excel'
    return 'text'
  }

  // SSE 流式发送
  const doSend = useCallback(async (text: string, files?: File[]) => {
    if (!sessionId) return
    setIsStreaming(true)

    // 本地附件预览
    const localAttachments: { file: File; fileType: FileType; preview?: string }[] = []
    if (files && files.length > 0) {
      for (const file of files) {
        const fileType = getFileType(file)
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

    // 用户消息
    const userMsgId = Date.now()
    const userMsg: ChatMessage = {
      id: userMsgId,
      sessionId,
      role: 'user',
      content: text,
      attachments: localAttachments.map(a => ({
        fileId: `pending_${Date.now()}`,
        fileType: a.fileType,
        fileName: a.file.name,
        preview: a.preview,
      })),
      createdAt: new Date().toISOString(),
    }

    // 助手占位
    const assistantId = userMsgId + 1
    const assistantMsg: ChatMessage = {
      id: assistantId,
      sessionId,
      role: 'assistant',
      content: '',
      toolCalls: [],
      createdAt: new Date().toISOString(),
      _thinking: '准备中...',
    }

    setMessages(prev => [...prev, userMsg, assistantMsg])

    // 上传文件
    const uploaded: { file_id: string; file_type: string; fileName?: string; preview?: string }[] = []
    for (const local of localAttachments) {
      try {
        const res = await agentApi.uploadFile(local.file)
        uploaded.push({ file_id: res.data.fileId, file_type: local.fileType, fileName: local.file.name, preview: local.preview })
      } catch {
        setMessages(prev => prev.map(m =>
          m.id === assistantId ? { ...m, content: '', _thinking: undefined } : m
        ))
        setIsStreaming(false)
        return
      }
    }

    // SSE
    abortRef.current = new AbortController()
    let fullContent = ''

    try {
      const response = await agentApi.chatStream(text, sessionId, uploaded)
      if (!response.ok || !response.body) throw new Error(`请求失败: ${response.status}`)

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
            const event = JSON.parse(raw)
            const eventData = event.data

            if (event.event === 'text') {
              fullContent += eventData.content || ''
              setMessages(prev => prev.map(m =>
                m.id === assistantId ? { ...m, content: fullContent, _thinking: undefined } : m
              ))
            } else if (event.event === 'tool_call') {
              setMessages(prev => prev.map(m =>
                m.id === assistantId ? {
                  ...m,
                  _thinking: undefined,
                  toolCalls: [...(m.toolCalls || []), { id: '', name: eventData.name, arguments: eventData.arguments }],
                } : m
              ))
            } else if (event.event === 'tool_result') {
              setMessages(prev => prev.map(m => {
                if (m.id !== assistantId || !m.toolCalls?.length) return m
                const calls = [...m.toolCalls]
                calls[calls.length - 1] = { ...calls[calls.length - 1], result: eventData.result }
                return { ...m, toolCalls: calls }
              }))
            } else if (event.event === 'thinking') {
              setMessages(prev => prev.map(m =>
                m.id === assistantId ? { ...m, _thinking: eventData.message || '思考中...' } : m
              ))
            } else if (event.event === 'error') {
              message.error(eventData.message || '对话出错')
            }
          } catch { /* skip */ }
        }
      }
    } catch (e: any) {
      if (e.name !== 'AbortError') {
        message.error(e.message || '对话出错')
      }
    } finally {
      setIsStreaming(false)
      abortRef.current = null
    }
  }, [sessionId])

  const handleSend = useCallback(async () => {
    const text = inputText.trim()
    if (!text && pendingFiles.length === 0) return
    const files = pendingFiles.length > 0 ? [...pendingFiles] : undefined
    setInputText('')
    setPendingFiles([])
    await doSend(text, files)
  }, [inputText, pendingFiles, doSend])

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend() }
  }, [handleSend])

  const stopGeneration = useCallback(() => {
    abortRef.current?.abort()
    setIsStreaming(false)
  }, [])

  const handleClose = useCallback(() => {
    abortRef.current?.abort()
    setSessionId(null)
    setMessages([])
    onClose()
  }, [onClose])

  // 拖拽上传
  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    const files = Array.from(e.dataTransfer.files)
    if (files.length > 0) {
      setPendingFiles(prev => [...prev, ...files])
    }
  }, [])

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
  }, [])

  const removePendingFile = useCallback((index: number) => {
    setPendingFiles(prev => prev.filter((_, i) => i !== index))
  }, [])

  const hasMessages = messages.some(m => m.role === 'user' || m.role === 'assistant')

  return (
    <Modal
      title={null}
      open={open}
      onCancel={handleClose}
      footer={null}
      width={600}
      destroyOnHidden
      className="receipt-chat-modal"
      styles={{ body: { padding: 0, height: '70vh', display: 'flex', flexDirection: 'column' } }}
    >
      {/* 头部 */}
      <div className="receipt-chat-header">
        <Avatar icon={<RobotOutlined />} className="receipt-chat-header-avatar" size={28} />
        <div>
          <div className="receipt-chat-header-title">{title}</div>
          <div className="receipt-chat-header-sub">对话式智能录入</div>
        </div>
      </div>

      {/* 消息区 */}
      <div
        ref={scrollRef}
        className="receipt-chat-messages"
        onDrop={handleDrop}
        onDragOver={handleDragOver}
      >
        {isInitializing ? (
          <div className="receipt-chat-empty">
            <Spin size="large" />
            <div style={{ marginTop: 12, color: 'var(--text-tertiary)' }}>正在初始化...</div>
          </div>
        ) : !hasMessages ? (
          <div className="receipt-chat-empty receipt-chat-drop-zone">
            <InboxOutlined className="receipt-chat-drop-icon" />
            <div className="receipt-chat-drop-text">拖拽凭证文件到此处</div>
            <div style={{ color: 'var(--text-tertiary)', fontSize: 12, marginTop: 4 }}>
              或点击下方 📎 按钮选择文件
            </div>
          </div>
        ) : (
          <>
            {messages
              .filter(m => m.role === 'user' || m.role === 'assistant')
              .map(msg => <MessageBubble key={msg.id} msg={msg} />)}
            {isStreaming && !messages.some(m => m.role === 'assistant' && !m.content && !(m.toolCalls?.length)) && (
              <div className="receipt-chat-msg receipt-chat-msg-assistant">
                <Avatar icon={<RobotOutlined />} className="receipt-chat-avatar-bot" size={32} />
                <Spin size="small" style={{ marginTop: 10 }} />
              </div>
            )}
          </>
        )}
      </div>

      {/* 输入区 */}
      {!isInitializing && sessionId && (
        <div className="receipt-chat-input-area">
          {pendingFiles.length > 0 && (
            <div className="receipt-chat-pending-files">
              <span style={{ fontSize: 11, color: 'var(--text-tertiary)', marginRight: 4 }}>待发送</span>
              {pendingFiles.map((f, i) => {
                if (f.type.startsWith('image/')) {
                  return (
                    <span key={i} className="receipt-chat-pending-preview" onClick={() => removePendingFile(i)}>
                      <img src={URL.createObjectURL(f)} alt={f.name} className="receipt-chat-pending-thumb" />
                      <span className="receipt-chat-pending-remove">×</span>
                    </span>
                  )
                }
                return (
                  <Tag key={i} closable onClose={() => removePendingFile(i)} style={{ margin: 0, fontSize: 12 }}>
                    {f.name.length > 16 ? f.name.slice(0, 14) + '…' : f.name}
                  </Tag>
                )
              })}
            </div>
          )}
          <div className="receipt-chat-input-row">
            <Upload
              beforeUpload={(file: File) => { setPendingFiles(prev => [...prev, file]); return false }}
              showUploadList={false}
              accept="image/*,.pdf,.doc,.docx,.xls,.xlsx"
            >
              <Button
                type="text"
                icon={<PaperClipOutlined style={{ fontSize: 16 }} />}
                disabled={isStreaming}
                className="receipt-chat-attach-btn"
              />
            </Upload>
            <Input.TextArea
              value={inputText}
              onChange={e => setInputText(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={pendingFiles.length > 0 ? '添加说明（可选）...' : '输入消息或上传凭证...'}
              autoSize={{ minRows: 1, maxRows: 4 }}
              disabled={isStreaming}
              variant="borderless"
              className="receipt-chat-textarea"
            />
            {isStreaming ? (
              <Button danger icon={<StopOutlined />} onClick={stopGeneration} className="receipt-chat-send-btn">
                停止
              </Button>
            ) : (
              <Button
                type="primary"
                icon={<SendOutlined />}
                onClick={handleSend}
                disabled={!inputText.trim() && pendingFiles.length === 0}
                className="receipt-chat-send-btn"
              >
                发送
              </Button>
            )}
          </div>
          <div className="receipt-chat-input-hint">
            拖拽文件到聊天区域 · Enter 发送，Shift+Enter 换行
          </div>
        </div>
      )}
    </Modal>
  )
}
