import { useState, useRef, useEffect, useCallback, memo, type ReactNode } from 'react'
import {
  Modal, Input, Button, Avatar, Upload, Tag, Spin, message,
} from 'antd'
import {
  SendOutlined, RobotOutlined, UserOutlined, PaperClipOutlined,
  StopOutlined, InboxOutlined, PlusOutlined, PictureOutlined,
  FilePdfOutlined, FileWordOutlined, FileExcelOutlined, FileTextOutlined,
  CloseOutlined,
} from '@ant-design/icons'
import { agentApi } from '@/services/agent'
import { compressImage } from '@/utils/imageCompress'
import type { ChatMessage, FileType, UploadResult } from '@/types/agent'
import { MarkdownRenderer, WittyLoadingText, ToolCallBlock, QuickReplyButtons } from '@/components/AgentChatShared'
import { usePendingFiles } from '@/hooks/usePendingFiles'
import { useDropZone } from '@/hooks/useDropZone'
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
  wechatGroup?: string
  businessType?: string   // 车辆买卖 / 两地牌过户 / 年检保险 / 其他
  contractTitle?: string
  totalAmount?: number
  currency?: string
  status?: string
  paymentType: 'income' | 'expense'
  onClose: () => void
}

const TYPE_LABELS = { income: '收入', expense: '支出' }
const TOOL_LABELS: Record<string, string> = {
  analyze_files: '文件识别',
  analyze_image: '图片识别',
  analyze_receipt: '凭证识别+对比',
  update_payment: '更新记录',
  get_contract_detail: '合同详情',
  query_payments: '查询付款',
  search_contracts: '搜索合同',
  search_customers: '搜索客户',
  create_income_payment: '录入收入',
  create_expense_payment: '录入支出',
  override_receipt_mismatch: '放行入账',
}

// 业务色徽章映射：与设计系统业务色保持一致
const BIZ_BADGE_STYLE: Record<string, { className: string; label: string }> = {
  '两地牌过户': { className: 'biz-license-chip', label: '两地牌' },
  '车辆买卖': { className: 'biz-vehicle-chip', label: '车辆' },
  '年检保险': { className: 'biz-insurance-chip', label: '年检保险' },
  '其他': { className: 'biz-other-chip', label: '其他业务' },
}

const MessageBubble = memo(function MessageBubble({ msg, streaming, onSendMessage, onClearQuickReplies }: {
  msg: ChatMessage; streaming?: boolean;
  onSendMessage?: (text: string) => void;
  onClearQuickReplies?: (msgId: number) => void;
}) {
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
                const pageHint = att.fileType === 'pdf' && att.pageCount && att.pageCount > 0
                  ? ` · ${att.pageCount} 页`
                  : ''
                return <Tag key={i} color="blue">{fileIcon} {att.fileName || '文件'}{pageHint}</Tag>
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
          {isThinking && (
            <div style={{ marginBottom: 8 }}>
              <WittyLoadingText message={msg.thoughts![msg.thoughts!.length - 1].message} />
            </div>
          )}
          {hasToolCalls && <ToolCallBlock toolCalls={msg.toolCalls!} toolLabels={TOOL_LABELS} />}
          {hasContent ? (
            <div className="receipt-chat-bubble receipt-chat-bubble-bot">
              <MarkdownRenderer content={msg.content} streaming={streaming} className="receipt-chat-markdown" />
            </div>
          ) : !isThinking && (
            <Spin size="small" style={{ marginTop: 8 }} />
          )}

          {msg.quickReplies && msg.quickReplies.length > 0 && (
            <QuickReplyButtons
              actions={msg.quickReplies}
              disabled={streaming}
              onClick={(action) => {
                onClearQuickReplies?.(msg.id)
                onSendMessage?.(action.send_text)
              }}
            />
          )}
        </div>
      </div>
    )
  }
  return null
})

const currencySymbol: Record<string, string> = { CNY: '¥', HKD: 'HK$' }

/** 文件类型 → antd 图标组件（文档类凭证用，图片走缩略图） */
function pickFileIcon(fileType: FileType) {
  if (fileType === 'pdf') return FilePdfOutlined
  if (fileType === 'word') return FileWordOutlined
  if (fileType === 'excel') return FileExcelOutlined
  return FileTextOutlined
}

/** 文件大小人性化显示 */
function formatSize(bytes: number) {
  if (!bytes) return ''
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

export default function ReceiptChatModal({
  open, contractId, contractNumber, customerName,
  wechatGroup, businessType, contractTitle, totalAmount, currency = 'CNY', status,
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
      result.thoughtAppend || result.thoughtFinalizeLast || result.quickReplies
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
    setMessages(prev => prev.map(m =>
      m.quickReplies ? { ...m, quickReplies: undefined } : m,
    ))

    // 本地附件预览
    const localAttachments: { file: File; fileType: FileType; preview?: string; uploaded?: UploadResult; pageCount?: number }[] = []
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
        localAttachments.push({ file, fileType, preview, uploaded: item.uploaded, pageCount: item.uploaded?.pageCount ?? undefined })
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
        pageCount: a.pageCount,
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
    for (let i = 0; i < localAttachments.length; i++) {
      const local = localAttachments[i]
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
          // PDF 上传成功后页数才回来 —— 把"共 N 页"回写到用户消息气泡里展示
          const pageCount = res.data.pageCount
          if (pageCount && pageCount > 0) {
            setMessages(prev => prev.map(m => {
              if (m.id !== userMsgId || !m.attachments) return m
              const next = [...m.attachments]
              if (next[i]) next[i] = { ...next[i], pageCount }
              return { ...m, attachments: next }
            }))
          }
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

  const clearQuickReplies = useCallback((msgId: number) => {
    setMessages(prev => prev.map(m =>
      m.id === msgId ? { ...m, quickReplies: undefined } : m
    ))
  }, [])

  const sendMessage = useCallback(async (text: string) => {
    await doSend(text)
  }, [doSend])

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

  // 拖拽上传（用通用 hook，支持悬停高亮 + 跨子元素稳定计数）
  const { isOver, dropHandlers } = useDropZone({
    onDrop: (files) => addFiles(files),
    accept: ['image/*', '.heic', '.heif', '.pdf', '.doc', '.docx', '.xls', '.xlsx'],
    disabled: isStreaming,
  })

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
      {/* 头部 · 凭证小票风：业务行 → 客户合同次行 → 金额小票条（视觉锚点） */}
      <div className="receipt-chat-header">
        <div className="receipt-chat-header-top">
          <Avatar icon={<RobotOutlined />} className="receipt-chat-header-avatar" size={38} />
          <div className="receipt-chat-header-info">
            {/* 主行：业务色徽章 + 群名称（主标题）+ 状态 */}
            <div className="receipt-chat-header-main">
              {businessType && BIZ_BADGE_STYLE[businessType] && (
                <span className={`receipt-chat-header-biz-chip ${BIZ_BADGE_STYLE[businessType].className}`}>
                  {BIZ_BADGE_STYLE[businessType].label}
                </span>
              )}
              <span className="receipt-chat-header-groupname" title={wechatGroup}>
                {wechatGroup || '未设置业务群'}
              </span>
              {status && (
                <span className={`receipt-chat-header-status ${status}`}>
                  {status === 'active' ? '执行中' : status === 'completed' ? '已完成' : status}
                </span>
              )}
            </div>
            {/* 次行：客户名 · 合同描述 */}
            <div className="receipt-chat-header-sub">
              <span className="receipt-chat-header-customer">{customerName}</span>
              {contractTitle && (
                <>
                  <span className="receipt-chat-header-dot">·</span>
                  <span className="receipt-chat-header-contract-title" title={contractTitle}>
                    {contractTitle}
                  </span>
                </>
              )}
            </div>
          </div>
        </div>
        {/* 金额小票条：类型标签 | 金额（视觉锚点，类型色大字）| 合同号 */}
        <div className="receipt-chat-receipt-bar">
          <span className="receipt-chat-receipt-type">录入{typeLabel}</span>
          <span className="receipt-chat-receipt-sep" />
          {totalAmount != null && (
            <span className="receipt-chat-receipt-amount">
              <span className="receipt-chat-receipt-amount-cur">{currencySymbol[currency] || '¥'}</span>
              <span className="receipt-chat-receipt-amount-num">
                {totalAmount.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </span>
            </span>
          )}
          <span className="receipt-chat-receipt-number">{contractNumber}</span>
        </div>
      </div>

      {/* 消息区 */}
      <div
        ref={scrollRef}
        className={`receipt-chat-messages${isOver ? ' chat-drop-active' : ''}`}
        {...dropHandlers}
      >
        {!hasMessages ? (
          <div className="receipt-chat-empty receipt-chat-drop-zone">
            <InboxOutlined className="receipt-chat-drop-icon" />
            <div className="receipt-chat-drop-text">拖拽凭证文件到此</div>
            <div className="receipt-chat-drop-sub">或点击下方 📎 按钮选择文件</div>
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
                  onSendMessage={sendMessage}
                  onClearQuickReplies={clearQuickReplies}
                />
              ))}
          </>
        )}
        {/* 拖拽悬停浮层：玻璃态 + 类型色光晕，有消息时也能醒目提示 */}
        {isOver && (
          <div className="receipt-chat-drop-overlay">
            <InboxOutlined className="receipt-chat-drop-overlay-icon" />
            <div className="receipt-chat-drop-overlay-title">松开即可上传凭证</div>
            <div className="receipt-chat-drop-overlay-hint">支持 图片 / PDF / Word / Excel</div>
          </div>
        )}
      </div>

      {/* 输入区 */}
      {(
        <div className="receipt-chat-input-area">
          {pendingFiles.length > 0 && (
            <div className="receipt-chat-tray">
              <div className="receipt-chat-tray-label">
                <PaperClipOutlined />
                <span>待发送凭证</span>
                <span className="receipt-chat-tray-count">{pendingFiles.length}</span>
              </div>
              <div className="receipt-chat-tray-items">
              {pendingFiles.map((pf, i) => {
                const f = pf.file
                const isHeic = f.name.toLowerCase().endsWith('.heic') || f.name.toLowerCase().endsWith('.heif')
                const isImage = f.type.startsWith('image/')
                const Icon = pickFileIcon(getFileType(f))
                // 缩略图内容：图片走缩略图，HEIC 按上传状态切换，文档走类型图标
                let thumb: ReactNode
                if (isImage && !isHeic) {
                  thumb = <img src={URL.createObjectURL(f)} alt={f.name} className="receipt-chat-filecard-img" />
                } else if (isHeic) {
                  thumb = pf.status === 'uploading' ? (
                    <Spin size="small" />
                  ) : pf.status === 'error' ? (
                    <PictureOutlined style={{ fontSize: 18, color: 'var(--color-danger)' }} />
                  ) : pf.uploaded?.thumbnailUrl ? (
                    <img src={pf.uploaded.thumbnailUrl} alt={f.name} className="receipt-chat-filecard-img" />
                  ) : (
                    <PictureOutlined style={{ fontSize: 18, color: 'var(--brand-gold)' }} />
                  )
                } else {
                  thumb = <Icon style={{ fontSize: 18, color: 'var(--type-color)' }} />
                }
                return (
                  <div key={pf.id} className="receipt-chat-filecard" title={f.name}>
                    <span className="receipt-chat-filecard-thumb">{thumb}</span>
                    <span className="receipt-chat-filecard-meta">
                      <span className="receipt-chat-filecard-name">{f.name}</span>
                      <span className="receipt-chat-filecard-size">
                        {pf.status === 'uploading' ? '上传中…' : formatSize(f.size)}
                      </span>
                    </span>
                    <span className="receipt-chat-filecard-remove" onClick={() => removePendingFile(i)}>
                      <CloseOutlined />
                    </span>
                  </div>
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
                      <span className="receipt-chat-filecard-add" title="再加一张凭证">
                        <PlusOutlined />
                      </span>
                    </Upload>
                  )
                }
                return null
              })()}
              </div>
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
