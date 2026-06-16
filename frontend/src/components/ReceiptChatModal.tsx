import { useState, useRef, useEffect, useCallback, memo } from 'react'
import {
  Modal, Input, Button, Avatar, Upload, Tag, Spin, message,
} from 'antd'
import {
  SendOutlined, RobotOutlined, UserOutlined, PaperClipOutlined,
  StopOutlined, InboxOutlined, PlusOutlined, PictureOutlined,
  FilePdfOutlined, FileWordOutlined, FileExcelOutlined, FileTextOutlined,
} from '@ant-design/icons'
import { agentApi } from '@/services/agent'
import { compressImage } from '@/utils/imageCompress'
import type { ChatMessage, FileType, UploadResult } from '@/types/agent'
import { MarkdownRenderer, ThoughtStepIndicator, ToolCallBlock } from '@/components/AgentChatShared'
import { usePendingFiles } from '@/hooks/usePendingFiles'
import {
  readSSEStream,
  computeEventUpdates,
  applyMessageUpdates,
} from '@/lib/sseStream'
import './ReceiptChatModal.css'

interface ReceiptChatModalProps {
  open: boolean
  contractId: number
  contractNumber: string
  customerName: string
  contractTitle?: string
  totalAmount?: number
  currency?: string
  status?: string
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

const MessageBubble = memo(function MessageBubble({ msg, streaming }: { msg: ChatMessage; streaming?: boolean }) {
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
    const hasThoughts = msg.thoughts && msg.thoughts.length > 0
    const hasToolCalls = msg.toolCalls && msg.toolCalls.length > 0
    const hasContent = !!msg.content
    const isThinking = !hasContent && hasThoughts && msg.thoughts!.some(t => t.status === 'running')

    return (
      <div className="receipt-chat-msg receipt-chat-msg-assistant">
        <Avatar icon={<RobotOutlined />} className="receipt-chat-avatar-bot" size={32} />
        <div className="receipt-chat-msg-content receipt-chat-msg-bot-content">
          {hasThoughts && <ThoughtStepIndicator thoughts={msg.thoughts!} />}
          {hasToolCalls && <ToolCallBlock toolCalls={msg.toolCalls!} toolLabels={TOOL_LABELS} />}
          {hasContent ? (
            <div className="receipt-chat-bubble receipt-chat-bubble-bot">
              <MarkdownRenderer content={msg.content} streaming={streaming} className="receipt-chat-markdown" />
            </div>
          ) : isThinking ? (
            <div className="receipt-chat-thinking">
              <Spin size="small" />
              <span>{msg.thoughts![msg.thoughts!.length - 1].message}</span>
            </div>
          ) : (
            <Spin size="small" style={{ marginTop: 8 }} />
          )}
        </div>
      </div>
    )
  }
  return null
})

const currencySymbol: Record<string, string> = { CNY: '¥', HKD: 'HK$' }

export default function ReceiptChatModal({
  open, contractId, contractNumber, customerName,
  contractTitle, totalAmount, currency = 'CNY', status,
  paymentType, onClose,
}: ReceiptChatModalProps) {
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [inputText, setInputText] = useState('')
  const { pendingFiles, addFiles, removeFile, clear: clearPending, hasUploading, toSendPayload } = usePendingFiles()
  const [isStreaming, setIsStreaming] = useState(false)
  const abortRef = useRef<AbortController | null>(null)
  const sessionCreatingRef = useRef(false)
  const scrollRef = useRef<HTMLDivElement>(null)

  const typeLabel = TYPE_LABELS[paymentType]

  // 打开时立即重置 UI（不再阻塞等待 createSession）
  // session 改为懒创建：用户首次发送时才创建
  useEffect(() => {
    if (!open) return
    setMessages([])
    setInputText('')
    clearPending()
    setSessionId(null)
    sessionCreatingRef.current = false

    setMessages([{
      id: Date.now(),
      sessionId: '',
      role: 'assistant',
      content: `请上传${typeLabel}凭证（图片或 PDF），我来帮您分析并录入。`,
      createdAt: new Date().toISOString(),
    }])
  }, [open, contractId, paymentType])

  // 关闭时 abort 在飞 SSE（修复 P1 遗漏：之前关闭不中断后台请求）
  useEffect(() => {
    if (open) return
    abortRef.current?.abort()
    abortRef.current = null
    setIsStreaming(false)
  }, [open])

  // 自动滚到底部
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [messages])

  // 剪贴板粘贴图片
  useEffect(() => {
    const handlePaste = (e: ClipboardEvent) => {
      const items = e.clipboardData?.items
      if (!items) return
      for (const item of items) {
        if (item.type.startsWith('image/')) {
          e.preventDefault()
          const file = item.getAsFile()
          if (file) {
            const imageCount = pendingFiles.filter(pf => pf.file.type.startsWith('image/')).length
            if (imageCount >= 2) {
              message.warning('图片最多携带 2 张')
              return
            }
            addFiles([file])
          }
          return
        }
      }
    }
    document.addEventListener('paste', handlePaste)
    return () => document.removeEventListener('paste', handlePaste)
  }, [pendingFiles, addFiles])

  // 判断文件类型
  const getFileType = (file: File): FileType => {
    if (file.type.startsWith('image/')) return 'image'
    const name = file.name.toLowerCase()
    if (name.endsWith('.pdf')) return 'pdf'
    if (name.endsWith('.docx') || name.endsWith('.doc')) return 'word'
    if (name.endsWith('.xlsx') || name.endsWith('.xls')) return 'excel'
    return 'image'
  }

  /**
   * 把 SSE 事件应用到本地 state（消息 + 中断面板）。
   * 行为与 useAgentStore.applyEventToStore 完全一致，通过共享模块统一。
   */
  const applyEvent = useCallback((
    event: Parameters<typeof computeEventUpdates>[0],
    assistantId: number,
    thoughtStepId: number,
  ): [import('@/lib/sseStream').DispatchAction, number] => {
    const result = computeEventUpdates(event, {
      assistantId,
      thoughtStepId,
      hasCurrentSessionId: !!sessionId,
    })

    if (
      result.textAppend || result.toolCallAppend || result.toolResultLast ||
      result.thoughtAppend || result.thoughtFinalizeLast
    ) {
      setMessages(prev => applyMessageUpdates(prev, result, assistantId))
    }

    if (result.sessionIdSync && !sessionId) {
      setSessionId(result.sessionIdSync)
    }

    return [result.action, result.nextThoughtId]
  }, [sessionId])

  // SSE 流式发送
  const doSend = useCallback(async (text: string, files?: Array<{ file: File; uploaded?: UploadResult }>) => {
    // 懒创建 session：没有 sessionId 时先建一个
    let activeSessionId = sessionId
    if (!activeSessionId) {
      if (sessionCreatingRef.current) {
        message.warning('会话创建中，请稍候...')
        return
      }
      sessionCreatingRef.current = true
      try {
        const res = await agentApi.createSession({
          title: `录入${typeLabel} · ${contractNumber} ${customerName}`,
          mode: paymentType === 'income' ? 'receipt_income' : 'receipt_expense',
          context: { contract_id: contractId, payment_type: paymentType },
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
    const localAttachments: { file: File; fileType: FileType; preview?: string; uploaded?: UploadResult }[] = []
    if (files && files.length > 0) {
      for (const item of files) {
        const file = item.file
        const fileType = getFileType(file)
        // 已上传的 HEIC 直接用 thumbnailUrl 做预览，否则走 FileReader
        let preview: string | undefined
        if (item.uploaded) {
          preview = item.uploaded.thumbnailUrl ?? undefined
        } else {
          const isHeic = file.name.toLowerCase().endsWith('.heic') || file.name.toLowerCase().endsWith('.heif')
          if (file.type.startsWith('image/') && !isHeic) {
            preview = await new Promise<string>((resolve) => {
              const reader = new FileReader()
              reader.onloadend = () => resolve(reader.result as string)
              reader.readAsDataURL(file)
            })
          }
        }
        localAttachments.push({ file, fileType, preview, uploaded: item.uploaded })
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
      thoughts: [],
      createdAt: new Date().toISOString(),
    }

    setMessages(prev => [...prev, userMsg, assistantMsg])

    // 上传文件（已上传的 HEIC 跳过）
    const uploaded: { file_id: string; file_type: FileType; fileName?: string; preview?: string }[] = []
    for (const local of localAttachments) {
      try {
        if (local.uploaded) {
          // HEIC 已在选文件时上传完成，直接复用 fileId
          uploaded.push({
            file_id: local.uploaded.fileId,
            file_type: local.fileType,
            fileName: local.file.name,
            preview: local.preview,
          })
        } else {
          const res = await agentApi.uploadFile(local.file)
          uploaded.push({
            file_id: res.data.fileId,
            file_type: local.fileType,
            fileName: local.file.name,
            preview: local.preview,
          })
        }
      } catch {
        setMessages(prev => prev.map(m =>
          m.id === assistantId ? { ...m, content: '' } : m
        ))
        setIsStreaming(false)
        return
      }
    }

    // SSE
    abortRef.current = new AbortController()
    let thoughtStepId = 0

    try {
      const response = await agentApi.chatStream(text, activeSessionId, uploaded)
      if (!response.ok || !response.body) throw new Error(`请求失败: ${response.status}`)

      for await (const event of readSSEStream(response, abortRef.current.signal)) {
        const [action, nextThoughtId] = applyEvent(event, assistantId, thoughtStepId)
        thoughtStepId = nextThoughtId
        if (action === 'done-normal' || action === 'error') {
          return
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
  }, [sessionId, typeLabel, contractNumber, customerName, paymentType, contractId, applyEvent])

  // 收支录入：有文字或凭证其一即可发送（两者都空才禁用）
  const missingText = !inputText.trim()
  const missingFile = pendingFiles.length === 0

  const handleSend = useCallback(async () => {
    const text = inputText.trim()
    if (!text && pendingFiles.length === 0) return
    const payload = pendingFiles.length > 0 ? toSendPayload() : undefined
    setInputText('')
    clearPending()
    await doSend(text, payload)
  }, [inputText, pendingFiles, doSend, hasUploading, toSendPayload, clearPending])

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
      addFiles(files)
    }
  }, [addFiles])

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
  }, [])

  const removePendingFile = useCallback((index: number) => {
    removeFile(index)
  }, [removeFile])

  const hasMessages = messages.some(m => m.role === 'user' || m.role === 'assistant')

  return (
    <Modal
      title={null}
      open={open}
      onCancel={handleClose}
      footer={null}
      width="70%"
      centered
      destroyOnHidden
      className={`receipt-chat-modal receipt-chat-modal--${paymentType}`}
      styles={{ body: { padding: 0, height: '70vh', display: 'flex', flexDirection: 'column' } }}
    >
      {/* 头部：合同信息 + 操作描述 */}
      <div className="receipt-chat-header">
        <Avatar icon={<RobotOutlined />} className="receipt-chat-header-avatar" size={28} />
        <div className="receipt-chat-header-info">
          <div className="receipt-chat-header-row">
            <span className="receipt-chat-header-title">{customerName}</span>
            <span className="receipt-chat-header-number">{contractNumber}</span>
            {status && (
              <span className={`receipt-chat-header-status ${status}`}>
                {status === 'active' ? '执行中' : status === 'completed' ? '已完成' : status}
              </span>
            )}
          </div>
          <div className="receipt-chat-header-meta">
            <span className="receipt-chat-header-type">录入{typeLabel}</span>
            {totalAmount != null && (
              <span className="receipt-chat-header-amount">
                {currencySymbol[currency] || '¥'}{totalAmount.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </span>
            )}
            {contractTitle && (
              <span className="receipt-chat-header-contract-title" title={contractTitle}>
                {contractTitle}
              </span>
            )}
          </div>
        </div>
      </div>

      {/* 消息区 */}
      <div
        ref={scrollRef}
        className="receipt-chat-messages"
        onDrop={handleDrop}
        onDragOver={handleDragOver}
      >
        {!hasMessages ? (
          <div className="receipt-chat-empty receipt-chat-drop-zone">
            <InboxOutlined className="receipt-chat-drop-icon" />
            <div className="receipt-chat-drop-text">拖拽凭证文件到此</div>
            <div style={{ color: 'var(--text-tertiary)', fontSize: 12, marginTop: 4 }}>
              或点击下方 📎 按钮选择文件
            </div>
          </div>
        ) : (
          <>
            {messages
              .filter(m => m.role === 'user' || m.role === 'assistant')
              .map((msg, idx, arr) => (
                <MessageBubble
                  key={msg.id}
                  msg={msg}
                  streaming={isStreaming && msg.role === 'assistant' && idx === arr.length - 1}
                />
              ))}
          </>
        )}
      </div>

      {/* 输入区 */}
      {(
        <div className="receipt-chat-input-area">
          {pendingFiles.length > 0 && (
            <div className="receipt-chat-pending-files">
              <span style={{ fontSize: 11, color: 'var(--text-tertiary)', marginRight: 4 }}>待发送</span>
              {pendingFiles.map((pf, i) => {
                const f = pf.file
                const isHeic = f.name.toLowerCase().endsWith('.heic') || f.name.toLowerCase().endsWith('.heif')
                // HEIC 文件：根据上传状态显示不同占位（uploading 转圈 / done 缩略图 / error 错误）
                if (isHeic) {
                  const inner = pf.status === 'uploading' ? (
                    <Spin size="small" style={{ color: 'var(--brand-gold)' }} />
                  ) : pf.status === 'error' ? (
                    <PictureOutlined style={{ fontSize: 18, color: 'var(--color-danger)' }} />
                  ) : pf.uploaded?.thumbnailUrl ? (
                    <img src={pf.uploaded.thumbnailUrl} alt={f.name} className="receipt-chat-pending-thumb" />
                  ) : (
                    <PictureOutlined style={{ fontSize: 18, color: 'var(--brand-gold)' }} />
                  )
                  return (
                    <span key={pf.id} className="receipt-chat-pending-preview" onClick={() => removePendingFile(i)}>
                      <span style={{
                        height: 40, width: 40, borderRadius: 8,
                        background: 'var(--bg-subtle)',
                        border: '1px solid var(--border-default)',
                        display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                      }}>
                        {inner}
                      </span>
                      <span className="receipt-chat-pending-remove">×</span>
                    </span>
                  )
                }
                if (f.type.startsWith('image/')) {
                  return (
                    <span key={pf.id} className="receipt-chat-pending-preview" onClick={() => removePendingFile(i)}>
                      <img src={URL.createObjectURL(f)} alt={f.name} className="receipt-chat-pending-thumb" />
                      <span className="receipt-chat-pending-remove">×</span>
                    </span>
                  )
                }
                return (
                  <Tag key={pf.id} closable onClose={() => removePendingFile(i)} style={{ margin: 0, fontSize: 12 }}>
                    {f.name.length > 16 ? f.name.slice(0, 14) + '…' : f.name}
                  </Tag>
                )
              })}
              {/* 图片未满 2 张时显示「+」按钮，点击再选一张 */}
              {(() => {
                const imageCount = pendingFiles.filter(pf => pf.file.type.startsWith('image/')).length
                const hasNonImage = pendingFiles.some(pf => !pf.file.type.startsWith('image/'))
                if (imageCount > 0 && imageCount < 2 && !hasNonImage) {
                  return (
                    <Upload
                      beforeUpload={(file: File) => {
                        if (imageCount >= 2) {
                          message.warning('图片最多携带 2 张')
                          return false
                        }
                        compressImage(file).then((compressed) => addFiles([compressed]))
                        return false
                      }}
                      showUploadList={false}
                      accept="image/*,.heic,.heif"
                    >
                      <span style={{
                        height: 40, width: 40, borderRadius: 8,
                        border: '1.5px dashed var(--border-default)',
                        display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                        cursor: 'pointer', color: 'var(--text-tertiary)',
                        transition: 'border-color 0.2s, color 0.2s',
                        flexShrink: 0,
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.borderColor = 'var(--brand-primary)'
                        e.currentTarget.style.color = 'var(--brand-primary)'
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.borderColor = 'var(--border-default)'
                        e.currentTarget.style.color = 'var(--text-tertiary)'
                      }}
                      >
                        <PlusOutlined style={{ fontSize: 16 }} />
                      </span>
                    </Upload>
                  )
                }
                return null
              })()}
            </div>
          )}
          <div className="receipt-chat-input-row">
            <Upload
              beforeUpload={(file: File) => {
                const isImage = file.type.startsWith('image/')
                const imageCount = pendingFiles.filter(pf => pf.file.type.startsWith('image/')).length
                const nonImageCount = pendingFiles.length - imageCount
                if (isImage) {
                  if (imageCount >= 2) { message.warning('图片最多携带 2 张'); return false }
                  compressImage(file).then((compressed) => addFiles([compressed]))
                } else {
                  if (nonImageCount >= 1) { message.warning('文档类一次只能携带一份'); return false }
                  addFiles([file])
                }
                return false
              }}
              showUploadList={false}
              accept="image/*,.heic,.heif,.pdf,.doc,.docx,.xls,.xlsx"
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
              placeholder={
                pendingFiles.length > 0 ? '添加说明（可选）...' : '输入消息或上传凭证...'
              }
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
                disabled={hasUploading || (missingText && missingFile)}
                className="receipt-chat-send-btn"
              >
                发送
              </Button>
            )}
          </div>
          <div className="receipt-chat-input-hint">
            {missingText && missingFile ? (
              <span className="receipt-chat-input-warn">请输入消息或上传凭证后再发送</span>
            ) : (
              '拖拽文件到聊天区 · Enter 发送，Shift+Enter 换行'
            )}
          </div>
        </div>
      )}
    </Modal>
  )
}
