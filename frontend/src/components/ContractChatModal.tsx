import { useState, useRef, useEffect, useCallback, memo } from 'react'
import {
  Modal, Input, Button, Avatar, Upload, Tag, Spin, message,
} from 'antd'
import {
  SendOutlined, RobotOutlined, UserOutlined, PaperClipOutlined,
  StopOutlined, InboxOutlined, PictureOutlined,
  FilePdfOutlined, FileWordOutlined, FileExcelOutlined, FileTextOutlined,
  WechatOutlined, CloudUploadOutlined,
} from '@ant-design/icons'
import { agentApi } from '@/services/agent'
import { compressImage } from '@/utils/imageCompress'
import type { ChatMessage, FileType, UploadResult } from '@/types/agent'
import { MarkdownRenderer, WittyLoadingText, ToolCallBlock, QuickReplyButtons } from '@/components/AgentChatShared'
import { usePendingFiles } from '@/hooks/usePendingFiles'
import { useDropZone } from '@/hooks/useDropZone'
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

const MessageBubble = memo(function MessageBubble({ msg, streaming, onSendMessage, onClearQuickReplies }: {
  msg: ChatMessage; streaming?: boolean;
  onSendMessage?: (text: string) => void;
  onClearQuickReplies?: (msgId: number) => void;
}) {
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
                const pageHint = att.fileType === 'pdf' && att.pageCount && att.pageCount > 0
                  ? ` · ${att.pageCount} 页`
                  : ''
                return <Tag key={i} color="blue">{fileIcon} {att.fileName || '文件'}{pageHint}</Tag>
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
    // 欢迎引导卡片：带图标、分步排版，替代纯文字气泡
    if (msg.isWelcome) {
      return (
        <div className="contract-chat-msg contract-chat-msg-assistant">
          <Avatar icon={<RobotOutlined />} className="contract-chat-avatar-bot" size={32} />
          <div className="contract-chat-msg-content contract-chat-msg-bot-content">
            <div className="welcome-card">
              <div className="welcome-title">
                <RobotOutlined className="welcome-title-icon" />
                <span>我来帮你录入合同</span>
              </div>
              <div className="welcome-steps">
                <div className="welcome-step">
                  <div className="welcome-step-icon"><CloudUploadOutlined /></div>
                  <div className="welcome-step-text">
                    <div className="welcome-step-label">第一步</div>
                    <div className="welcome-step-desc">在下方输入框点 📎 上传合同文件（图片 / PDF / Word）</div>
                  </div>
                </div>
                <div className="welcome-step">
                  <div className="welcome-step-icon welcome-step-icon-wechat"><WechatOutlined /></div>
                  <div className="welcome-step-text">
                    <div className="welcome-step-label">第二步 · 必填</div>
                    <div className="welcome-step-desc">在同一输入框里打上<b>微信群名称</b>，和文件一起发送即可</div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      )
    }
    const hasThoughts = msg.thoughts && msg.thoughts.length > 0
    const hasToolCalls = msg.toolCalls && msg.toolCalls.length > 0
    const hasContent = !!msg.content
    const isThinking = !hasContent && hasThoughts && msg.thoughts!.some(t => t.status === 'running')

    return (
      <div className="contract-chat-msg contract-chat-msg-assistant">
        <Avatar icon={<RobotOutlined />} className="contract-chat-avatar-bot" size={32} />
        <div className="contract-chat-msg-content contract-chat-msg-bot-content">
          {isThinking && (
            <div style={{ marginBottom: 8 }}>
              <WittyLoadingText message={msg.thoughts![msg.thoughts!.length - 1].message} />
            </div>
          )}
          {hasToolCalls && <ToolCallBlock toolCalls={msg.toolCalls!} toolLabels={TOOL_LABELS} />}
          {hasContent ? (
            <div className="contract-chat-bubble contract-chat-bubble-bot">
              <MarkdownRenderer content={msg.content} streaming={streaming} className="contract-chat-markdown" />
            </div>
          ) : !isThinking && (
            <Spin size="small" style={{ marginTop: 8 }} />
          )}

          {msg.quickReplies && msg.quickReplies.length > 0 && !streaming && (
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

export default function ContractChatModal({
  open, onClose,
}: ContractChatModalProps) {
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [inputText, setInputText] = useState('')
  const { pendingFiles, addFiles, removeFile, clear: clearPending, hasUploading, toSendPayload } = usePendingFiles()
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
    clearPending()
    setSessionId(null)
    sessionCreatingRef.current = false

    setMessages([{
      id: Date.now(),
      sessionId: '',
      role: 'assistant',
      content: '',
      isWelcome: true,
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
  const doSend = useCallback(async (text: string, files?: Array<{ file: File; uploaded?: UploadResult }>) => {
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
    const uploaded: { file_id: string; file_type: string; fileName?: string; preview?: string }[] = []
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

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        if (abortRef.current?.signal.aborted) break

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
              const chunk = eventData.content || ''
              setMessages(prev => prev.map(m =>
                m.id === assistantId ? { ...m, content: m.content + chunk } : m
              ))
            } else if (event.event === 'tool_call') {
              setMessages(prev => prev.map(m =>
                m.id === assistantId ? {
                  ...m,
                  toolCalls: [...(m.toolCalls || []), { id: eventData.id || `tc_${Date.now()}`, name: eventData.name, arguments: eventData.arguments }],
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
            } else if (event.event === 'done') {
              setMessages(prev => prev.map(m => {
                if (m.id !== assistantId || !m.thoughts?.length) return m
                const thoughts = [...m.thoughts]
                const last = thoughts[thoughts.length - 1]
                if (last && last.status === 'running') {
                  thoughts[thoughts.length - 1] = { ...last, status: 'done' as const }
                }
                return { ...m, thoughts }
              }))
            } else if (event.event === 'error') {
              message.error(eventData.message || '对话出错')
            } else if (event.event === 'thinking') {
              const msgText = eventData.message || '思考中...'
              const stepId = `thought_${thoughtStepId++}`
              setMessages(prev => prev.map(m => {
                if (m.id !== assistantId) return m
                const thoughts = [...(m.thoughts || [])]
                if (thoughts.length > 0 && thoughts[thoughts.length - 1].status === 'running') {
                  thoughts[thoughts.length - 1] = { ...thoughts[thoughts.length - 1], status: 'done' as const }
                }
                thoughts.push({ id: stepId, message: msgText, status: 'running' })
                return { ...m, thoughts }
              }))
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
    if (hasUploading) {
      message.warning('文件上传中，请稍候…')
      return
    }
    const trimmedText = inputText.trim()
    if (!trimmedText && pendingFiles.length === 0) return
    const payload = pendingFiles.length > 0 ? toSendPayload() : undefined
    setInputText('')
    clearPending()
    await doSend(trimmedText, payload)
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
    const wasCreated = contractCreatedRef.current
    setSessionId(null)
    setMessages([])
    contractCreatedRef.current = false
    onClose(wasCreated)
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
      width={760}
      centered
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
        className={`contract-chat-messages${isOver ? ' chat-drop-active' : ''}`}
        {...dropHandlers}
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
      </div>

      {/* 输入区 */}
      <div className="contract-chat-input-area">
        {pendingFiles.length > 0 && (
          <div className="contract-chat-pending-files">
            <span style={{ fontSize: 11, color: 'var(--text-tertiary)', marginRight: 4 }}>待发送</span>
            {pendingFiles.map((pf, i) => {
              const f = pf.file
              const isHeic = f.name.toLowerCase().endsWith('.heic') || f.name.toLowerCase().endsWith('.heif')
              if (isHeic) {
                const inner = pf.status === 'uploading' ? (
                  <Spin size="small" style={{ color: 'var(--brand-gold)' }} />
                ) : pf.status === 'error' ? (
                  <PictureOutlined style={{ fontSize: 18, color: 'var(--color-danger)' }} />
                ) : pf.uploaded?.thumbnailUrl ? (
                  <img src={pf.uploaded.thumbnailUrl} alt={f.name} className="contract-chat-pending-thumb" />
                ) : (
                  <PictureOutlined style={{ fontSize: 18, color: 'var(--brand-gold)' }} />
                )
                return (
                  <span key={i} className="contract-chat-pending-preview" onClick={() => removePendingFile(i)}>
                    <span style={{
                      height: 40, width: 40, borderRadius: 8,
                      background: 'var(--bg-subtle)',
                      border: '1px solid var(--border-default)',
                      display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                    }}>
                      {inner}
                    </span>
                    <span className="contract-chat-pending-remove">×</span>
                  </span>
                )
              }
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
            beforeUpload={(file: File) => {
              const isImage = file.type.startsWith('image/')
              const nonImageCount = pendingFiles.filter(pf => !pf.file.type.startsWith('image/')).length
              if (isImage) {
                compressImage(file).then((compressed) => addFiles([compressed]))
              } else {
                if (nonImageCount >= 1) { message.warning('合同/文档类一次只能携带一份'); return false }
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
              disabled={hasUploading || (!inputText.trim() && pendingFiles.length === 0)}
              className="contract-chat-send-btn"
            >
              {hasUploading ? '上传中…' : '发送'}
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
