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
import './ContractChatModal.css'

interface ContractChatModalProps {
  open: boolean
  onClose: (created: boolean) => void
}

const TOOL_LABELS: Record<string, string> = {
  analyze_image: '文件分析',
  search_customers: '搜索客户',
  create_customer: '创建客户',
  create_contract: '创建合同',
  update_contract: '更新合同',
  get_contract_detail: '合同详情',
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
    <div className="contract-chat-markdown">
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
      <div className="contract-chat-msg contract-chat-msg-user">
        <div className="contract-chat-msg-content contract-chat-msg-user-content">
          {msg.attachments && msg.attachments.length > 0 && (
            <div className="contract-chat-attachments">
              {msg.attachments.map((att, i) => {
                if (att.fileType === 'image' && att.preview) {
                  return (
                    <img
                      key={i} src={att.preview} alt={att.fileName || '附件'}
                      className="contract-chat-attachment-img"
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
          <div className="contract-chat-bubble contract-chat-bubble-user">
            {msg.content || (msg.attachments?.length ? `已上传 ${msg.attachments.length} 个文件` : '')}
          </div>
        </div>
        <Avatar icon={<UserOutlined />} className="contract-chat-avatar-user" size={32} />
      </div>
    )
  }

  if (msg.role === 'assistant') {
    return (
      <div className="contract-chat-msg contract-chat-msg-assistant">
        <Avatar icon={<RobotOutlined />} className="contract-chat-avatar-bot" size={32} />
        <div className="contract-chat-msg-content contract-chat-msg-bot-content">
          {msg.toolCalls && msg.toolCalls.length > 0 && (
            <div className="contract-chat-tool-calls">
              {msg.toolCalls.map((tc, i) => <ToolCallView key={i} toolCall={tc} />)}
            </div>
          )}
          {msg.content ? (
            <div className="contract-chat-bubble contract-chat-bubble-bot">
              <MarkdownRenderer content={msg.content} />
            </div>
          ) : (msg as any)._thinking ? (
            <div className="contract-chat-thinking">
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

export default function ContractChatModal({
  open, onClose,
}: ContractChatModalProps) {
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [inputText, setInputText] = useState('')
  const [pendingFiles, setPendingFiles] = useState<File[]>([])
  const [isStreaming, setIsStreaming] = useState(false)
  const abortRef = useRef<AbortController | null>(null)
  const sessionCreatingRef = useRef(false)
  const scrollRef = useRef<HTMLDivElement>(null)
  const contractCreatedRef = useRef(false)

  // 打开时重置状态
  useEffect(() => {
    if (!open) return
    contractCreatedRef.current = false
    setMessages([])
    setInputText('')
    setPendingFiles([])
    setSessionId(null)
    sessionCreatingRef.current = false

    setMessages([{
      id: Date.now(),
      sessionId: '',
      role: 'assistant',
      content: '请上传合同文件（图片、PDF 或 Word），我来帮你分析并创建合同。',
      createdAt: new Date().toISOString(),
    }])
  }, [open])

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
    // 懒创建 session
    let activeSessionId = sessionId
    if (!activeSessionId) {
      if (sessionCreatingRef.current) {
        message.warning('会话创建中，请稍候...')
        return
      }
      sessionCreatingRef.current = true
      try {
        const res = await agentApi.createSession({
          title: '上传合同',
        })
        activeSessionId = res.data.sessionId
        setSessionId(activeSessionId)
      } catch (e: any) {
        message.error(e?.response?.data?.detail || '创建会话失败，请重试')
        return
      } finally {
        sessionCreatingRef.current = false
      }
    }
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
      sessionId: activeSessionId,
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
      sessionId: activeSessionId,
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
      const response = await agentApi.chatStream(text, activeSessionId, uploaded)
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
              // 检测合同创建成功
              if (eventData.name === 'create_contract') {
                try {
                  const resultObj = JSON.parse(eventData.result)
                  if (resultObj.success) {
                    contractCreatedRef.current = true
                  }
                } catch { /* ignore */ }
              }
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
    const wasCreated = contractCreatedRef.current
    setSessionId(null)
    setMessages([])
    contractCreatedRef.current = false
    onClose(wasCreated)
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
      width={760}
      destroyOnHidden
      className="contract-chat-modal"
      styles={{ body: { padding: 0, height: '70vh', display: 'flex', flexDirection: 'column' } }}
    >
      {/* 头部 */}
      <div className="contract-chat-header">
        <Avatar icon={<RobotOutlined />} className="contract-chat-header-avatar" size={28} />
        <div className="contract-chat-header-info">
          <div className="contract-chat-header-row">
            <span className="contract-chat-header-title">上传合同</span>
            <span className="contract-chat-header-type">AI 助手</span>
          </div>
        </div>
      </div>

      {/* 消息区 */}
      <div
        ref={scrollRef}
        className="contract-chat-messages"
        onDrop={handleDrop}
        onDragOver={handleDragOver}
      >
        {!hasMessages ? (
          <div className="contract-chat-empty contract-chat-drop-zone">
            <InboxOutlined className="contract-chat-drop-icon" />
            <div className="contract-chat-drop-text">拖拽合同文件到此处</div>
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
              <div className="contract-chat-msg contract-chat-msg-assistant">
                <Avatar icon={<RobotOutlined />} className="contract-chat-avatar-bot" size={32} />
                <Spin size="small" style={{ marginTop: 10 }} />
              </div>
            )}
          </>
        )}
      </div>

      {/* 输入区 */}
      <div className="contract-chat-input-area">
        {pendingFiles.length > 0 && (
          <div className="contract-chat-pending-files">
            <span style={{ fontSize: 11, color: 'var(--text-tertiary)', marginRight: 4 }}>待发送</span>
            {pendingFiles.map((f, i) => {
              if (f.type.startsWith('image/')) {
                return (
                  <span key={i} className="contract-chat-pending-preview" onClick={() => removePendingFile(i)}>
                    <img src={URL.createObjectURL(f)} alt={f.name} className="contract-chat-pending-thumb" />
                    <span className="contract-chat-pending-remove">×</span>
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
        <div className="contract-chat-input-row">
          <Upload
            beforeUpload={(file: File) => { setPendingFiles(prev => [...prev, file]); return false }}
            showUploadList={false}
            accept="image/*,.pdf,.doc,.docx,.xls,.xlsx"
          >
            <Button
              type="text"
              icon={<PaperClipOutlined style={{ fontSize: 16 }} />}
              disabled={isStreaming}
              className="contract-chat-attach-btn"
            />
          </Upload>
          <Input.TextArea
            value={inputText}
            onChange={e => setInputText(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={pendingFiles.length > 0 ? '添加说明（可选）...' : '输入消息或上传合同文件...'}
            autoSize={{ minRows: 1, maxRows: 4 }}
            disabled={isStreaming}
            variant="borderless"
            className="contract-chat-textarea"
          />
          {isStreaming ? (
            <Button danger icon={<StopOutlined />} onClick={stopGeneration} className="contract-chat-send-btn">
              停止
            </Button>
          ) : (
            <Button
              type="primary"
              icon={<SendOutlined />}
              onClick={handleSend}
              disabled={!inputText.trim() && pendingFiles.length === 0}
              className="contract-chat-send-btn"
            >
              发送
            </Button>
          )}
        </div>
        <div className="contract-chat-input-hint">
          拖拽文件到聊天区域 · Enter 发送，Shift+Enter 换行
        </div>
      </div>
    </Modal>
  )
}
