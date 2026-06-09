import { useState, useCallback, useRef, useEffect, memo } from 'react'
import {
  Input,
  Button,
  Avatar,
  Tag,
  Upload,
  message,
  Spin,
  Typography,
  Grid,
  Modal,
} from 'antd'
import {
  SendOutlined,
  RobotOutlined,
  UserOutlined,
  PaperClipOutlined,
  StopOutlined,
  FilePdfOutlined,
  FileWordOutlined,
  FileExcelOutlined,
  FileTextOutlined,
  StarFilled,
  DollarOutlined,
  BarChartOutlined,
  FileSearchOutlined,
  PictureOutlined,
  CreditCardOutlined,
  PlusOutlined,
  DeleteOutlined,
  MessageOutlined,
  RightOutlined,
  LeftOutlined,
} from '@ant-design/icons'
import { useAgentStore } from '@/store/useAgentStore'
import type { ChatMessage } from '@/types/agent'
import { MarkdownRenderer, ToolCallBlock, WittyLoadingText } from '@/components/AgentChatShared'

const { Text } = Typography

/* ── 工具标签映射 ── */
const TOOL_LABELS: Record<string, string> = {
  search_customers: '搜索客户',
  search_contracts: '搜索合同',
  get_contract_detail: '合同详情',
  get_customer_contracts: '客户合同',
  query_payments: '查询付款',
  create_payment: '创建付款',
  get_payment_summary: '付款汇总',
  get_expiring_contracts: '到期合同',
  analyze_image: '文件分析',
}

/* ── 会话时间格式化 ── */
function formatSessionTime(iso: string | null | undefined): string {
  if (!iso) return ''
  const d = new Date(iso)
  const now = new Date()
  const diffMin = Math.floor((now.getTime() - d.getTime()) / 60000)
  if (diffMin < 1) return '刚刚'
  if (diffMin < 60) return `${diffMin}分钟前`
  const diffHour = Math.floor(diffMin / 60)
  if (diffHour < 24) return `${diffHour}小时前`
  const diffDay = Math.floor(diffHour / 24)
  if (diffDay < 7) return `${diffDay}天前`
  return `${d.getMonth() + 1}/${d.getDate()}`
}

/* ── 消息气泡（memo 防止已完成消息重复渲染） ── */

/* ── 文件类型元信息（用于文件卡片的大色块图标）── */
const FILE_TYPE_META: Record<string, { icon: JSX.Element; bg: string; fg: string; label: string }> = {
  pdf:  { icon: <FilePdfOutlined />,  bg: 'linear-gradient(135deg, #fee2e2, #fecaca)', fg: '#b91c1c', label: 'PDF 文档' },
  word: { icon: <FileWordOutlined />, bg: 'linear-gradient(135deg, #dbeafe, #bfdbfe)', fg: '#1d4ed8', label: 'Word 文档' },
  excel:{ icon: <FileExcelOutlined />,bg: 'linear-gradient(135deg, #d1fae5, #a7f3d0)', fg: '#047857', label: 'Excel 表格' },
  text: { icon: <FileTextOutlined />, bg: 'linear-gradient(135deg, #fef3c7, #fde68a)', fg: '#b45309', label: '文本文件' },
  image:{ icon: <PictureOutlined />,  bg: 'linear-gradient(135deg, #ede9fe, #ddd6fe)', fg: '#6d28d9', label: '图片' },
  default: { icon: <PaperClipOutlined />, bg: 'linear-gradient(135deg, #e5e7eb, #d1d5db)', fg: '#374151', label: '文件' },
}

const MessageBubble = memo(function MessageBubble({ msg, streaming }: {
  msg: ChatMessage
  streaming?: boolean
}) {
  if (msg.role === 'user') {
    const attachments = msg.attachments || []
    const hasText = !!msg.content
    const hasAttachments = attachments.length > 0
    const imageAttachments = attachments.filter(a => a.fileType === 'image' && a.preview)
    const fileAttachments = attachments.filter(a => !(a.fileType === 'image' && a.preview))

    return (
      <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 20 }}>
        <div style={{
          maxWidth: '85%',
          display: 'flex', flexDirection: 'column', alignItems: 'flex-end',
        }}>
          {(hasText || hasAttachments) && (
            <div
              className="user-bubble"
              style={{
                background: 'linear-gradient(135deg, var(--brand-primary) 0%, var(--brand-primary-light) 100%)',
                color: '#fff',
                borderRadius: '16px 16px 4px 16px',
                boxShadow: '0 4px 16px rgba(30,58,95,0.20)',
                overflow: 'hidden',
                minWidth: 60,
              }}
            >
              {imageAttachments.length > 0 && (
                <div
                  className="user-bubble-images"
                  style={{
                    display: 'grid',
                    gap: 2,
                    padding: imageAttachments.length === 1 ? 6 : 4,
                    background: 'rgba(255,255,255,0.06)',
                    gridTemplateColumns:
                      imageAttachments.length === 1 ? '1fr' :
                      imageAttachments.length === 2 ? '1fr 1fr' :
                      '1fr 1fr 1fr',
                  }}
                >
                  {imageAttachments.map((att, i) => (
                    <img
                      key={i}
                      src={att.preview}
                      alt={att.fileName || '图片'}
                      style={{
                        width: '100%',
                        maxHeight: imageAttachments.length === 1 ? 280 : 160,
                        objectFit: 'cover',
                        borderRadius: 10,
                        display: 'block',
                        cursor: 'pointer',
                      }}
                    />
                  ))}
                </div>
              )}

              {fileAttachments.length > 0 && (
                <div style={{ padding: '8px 10px', display: 'flex', flexDirection: 'column', gap: 6 }}>
                  {fileAttachments.map((att, i) => {
                    const cfg = FILE_TYPE_META[att.fileType] || FILE_TYPE_META.default
                    return (
                      <div
                        key={i}
                        style={{
                          display: 'flex', alignItems: 'center', gap: 10,
                          background: 'rgba(255,255,255,0.12)',
                          border: '1px solid rgba(255,255,255,0.15)',
                          borderRadius: 10,
                          padding: '8px 10px',
                          minWidth: 200,
                        }}
                      >
                        <div style={{
                          width: 40, height: 48, borderRadius: 6,
                          background: cfg.bg,
                          display: 'flex', alignItems: 'center', justifyContent: 'center',
                          color: cfg.fg, fontSize: 20, flexShrink: 0,
                          boxShadow: '0 1px 3px rgba(0,0,0,0.10)',
                        }}>
                          {cfg.icon}
                        </div>
                        <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column' }}>
                          <span style={{
                            fontSize: 13, color: '#fff', fontWeight: 500,
                            overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                          }}>
                            {att.fileName || '文件'}
                          </span>
                          <span style={{
                            fontSize: 11, color: 'rgba(255,255,255,0.7)',
                            marginTop: 2,
                          }}>
                            {(att.fileName || '').toLowerCase().split('.').pop()?.toUpperCase() || ''} 文件
                          </span>
                        </div>
                      </div>
                    )
                  })}
                </div>
              )}

              {hasText && (
                <div style={{
                  padding: hasAttachments ? '8px 14px 12px' : '10px 16px',
                  whiteSpace: 'pre-wrap',
                  wordBreak: 'break-word',
                  lineHeight: 1.6,
                  fontSize: 14,
                }}>
                  {msg.content}
                </div>
              )}
            </div>
          )}
        </div>
        <Avatar
          icon={<UserOutlined />}
          style={{
            background: 'linear-gradient(135deg, var(--brand-primary-light), var(--brand-primary))',
            marginLeft: 10, flexShrink: 0,
            boxShadow: '0 2px 6px rgba(30,58,95,0.2)',
          }}
          size={36}
        />
      </div>
    )
  }

  if (msg.role === 'assistant') {
    const hasThoughts = msg.thoughts && msg.thoughts.length > 0
    const hasToolCalls = msg.toolCalls && msg.toolCalls.length > 0
    const hasContent = !!msg.content
    const runningStep = msg.thoughts?.find(t => t.status === 'running')
    const isThinking = !hasContent && hasThoughts && !!runningStep

    return (
      <div style={{ display: 'flex', marginBottom: 20 }}>
        <Avatar
          icon={<RobotOutlined />}
          style={{
            background: 'linear-gradient(135deg, var(--brand-gold), #e8b84b)',
            marginRight: 10, flexShrink: 0,
            boxShadow: '0 2px 6px rgba(201,149,43,0.2)',
            color: '#0f1a2e',
          }}
          size={36}
        />
        <div style={{ maxWidth: '85%', minWidth: 0, flex: 1 }}>
          {isThinking && runningStep && (
            <div
              key={runningStep.id}
              style={{ marginBottom: 8 }}
            >
              <WittyLoadingText message={runningStep.message} />
            </div>
          )}

          {hasToolCalls && <ToolCallBlock toolCalls={msg.toolCalls!} toolLabels={TOOL_LABELS} />}

          {hasContent ? (
            <div
              style={{
                background: 'var(--bg-surface)',
                padding: '14px 18px',
                borderRadius: '14px 14px 14px 4px',
                wordBreak: 'break-word',
                border: '1px solid var(--border-light)',
                boxShadow: '0 1px 4px rgba(0,0,0,0.03)',
              }}
            >
              <MarkdownRenderer content={msg.content} streaming={streaming} />
            </div>
          ) : !isThinking && (
            <Spin size="small" style={{ marginTop: 8 }} />
          )}
        </div>
      </div>
    )
  }
  return null
})

/* ── 快捷建议（带图标）── */
const suggestions = [
  { icon: <BarChartOutlined />, text: '查看当前系统有哪些数据' },
  { icon: <CreditCardOutlined />, text: '查询最近付款记录' },
  { icon: <FileSearchOutlined />, text: '上传合同文件进行录入' },
]

/* ── 三个工具（核心卖点）── */
const TOOLS = [
  { key: 'contract_entry' as const, icon: <FileTextOutlined />, label: '录合同', color: '#1e3a5f' },
  { key: 'receipt_income' as const, icon: <CreditCardOutlined />, label: '录收入', color: '#0d9488' },
  { key: 'receipt_expense' as const, icon: <DollarOutlined />, label: '录支出', color: '#dc2626' },
]

const ToolSelector = memo(function ToolSelector({ value, onChange }: {
  value: typeof TOOLS[number]['key'] | null
  onChange: (k: typeof TOOLS[number]['key'] | null) => void
}) {
  return (
    <div style={{
      display: 'flex', flexWrap: 'wrap', gap: 10, justifyContent: 'center',
    }}>
      {TOOLS.map((t) => {
        const isActive = value === t.key
        return (
          <div
            key={t.key}
            onClick={() => onChange(isActive ? null : t.key)}
            className="tool-capsule"
            style={{
              display: 'inline-flex', alignItems: 'center', gap: 8,
              padding: '10px 20px',
              background: isActive ? t.color : 'var(--bg-surface)',
              border: `1.5px solid ${isActive ? t.color : 'var(--border-light)'}`,
              borderRadius: 22,
              cursor: 'pointer',
              fontSize: 14, fontWeight: isActive ? 600 : 500,
              color: isActive ? '#fff' : 'var(--text-secondary)',
              boxShadow: isActive
                ? `0 6px 20px ${t.color}33`
                : '0 1px 3px rgba(0,0,0,0.03)',
              transition: 'all 0.2s cubic-bezier(0.4, 0, 0.2, 1)',
            }}
            onMouseEnter={(e) => {
              if (!isActive) {
                e.currentTarget.style.borderColor = t.color
                e.currentTarget.style.color = t.color
              }
            }}
            onMouseLeave={(e) => {
              if (!isActive) {
                e.currentTarget.style.borderColor = 'var(--border-light)'
                e.currentTarget.style.color = 'var(--text-secondary)'
              }
            }}
          >
            <span style={{
              display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
              width: 24, height: 24, borderRadius: 7,
              background: isActive ? 'rgba(255,255,255,0.18)' : `${t.color}14`,
              color: isActive ? '#fff' : t.color,
              fontSize: 13, transition: 'all 0.2s',
            }}>
              {t.icon}
            </span>
            {t.label}
          </div>
        )
      })}
    </div>
  )
})

const ToolTag = ({ value, onRemove }: { value: string; onRemove: () => void }) => {
  const t = TOOLS.find(x => x.key === value)
  if (!t) return null
  return (
    <span
      className="tool-tag"
      style={{
        display: 'inline-flex', alignItems: 'center', gap: 6,
        padding: '5px 10px 5px 12px',
        background: `${t.color}14`,
        border: `1px solid ${t.color}40`,
        borderRadius: 14,
        fontSize: 12, fontWeight: 600, color: t.color,
        flexShrink: 0,
        animation: 'wittyPhraseIn 0.25s ease-out',
      }}
    >
      <span style={{ display: 'inline-flex', alignItems: 'center', fontSize: 12 }}>{t.icon}</span>
      {t.label}
      <span
        onClick={onRemove}
        style={{
          display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
          width: 16, height: 16, borderRadius: '50%',
          background: 'rgba(0,0,0,0.06)', color: t.color,
          fontSize: 11, cursor: 'pointer', lineHeight: 1,
          marginLeft: 2, transition: 'background 0.15s',
        }}
        onMouseEnter={(e) => { e.currentTarget.style.background = 'rgba(0,0,0,0.12)' }}
        onMouseLeave={(e) => { e.currentTarget.style.background = 'rgba(0,0,0,0.06)' }}
      >×</span>
    </span>
  )
}

const CenterInputBox = memo(function CenterInputBox({
  value, onChange, onSend, onFileSelect, isStreaming, onStop, pendingFiles, onRemoveFile, toolTag,
}: {
  value: string
  onChange: (v: string) => void
  onSend: () => void
  onFileSelect: (f: File) => boolean
  isStreaming: boolean
  onStop: () => void
  pendingFiles: File[]
  onRemoveFile: (i: number) => void
  toolTag?: React.ReactNode
}) {
  return (
    <div
      style={{
        width: '100%', maxWidth: 700,
        background: 'var(--bg-surface)',
        border: '1px solid var(--border-default)',
        borderRadius: 18,
        padding: '14px 16px',
        boxShadow: '0 4px 20px rgba(15, 23, 42, 0.06)',
        transition: 'all 0.2s',
      }}
      onFocus={(e) => {
        e.currentTarget.style.borderColor = 'var(--brand-primary)'
        e.currentTarget.style.boxShadow = '0 6px 24px rgba(30, 58, 95, 0.10)'
      }}
      onBlur={(e) => {
        e.currentTarget.style.borderColor = 'var(--border-default)'
        e.currentTarget.style.boxShadow = '0 4px 20px rgba(15, 23, 42, 0.06)'
      }}
    >
      {toolTag && (
        <div style={{ marginBottom: 8 }}>{toolTag}</div>
      )}

      {pendingFiles.length > 0 && (
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 8 }}>
          {pendingFiles.map((f, i) => {
            const name = f.name.toLowerCase()
            const icon = name.endsWith('.pdf') ? <FilePdfOutlined style={{ color: '#dc2626' }} />
              : name.endsWith('.docx') || name.endsWith('.doc') ? <FileWordOutlined style={{ color: 'var(--brand-primary)' }} />
              : name.endsWith('.xlsx') || name.endsWith('.xls') ? <FileExcelOutlined style={{ color: 'var(--color-success)' }} />
              : <FileTextOutlined style={{ color: 'var(--color-warning)' }} />
            return (
              <Tag key={i} closable onClose={() => onRemoveFile(i)} style={{ margin: 0, fontSize: 12, borderRadius: 6 }}>
                {icon} {f.name.length > 16 ? f.name.slice(0, 14) + '…' : f.name}
              </Tag>
            )
          })}
        </div>
      )}

      <Input.TextArea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); onSend() }
        }}
        placeholder={pendingFiles.length > 0 ? '请描述文件内容（必填）...' : '问点什么？试试："查询最近付款" 或上传一份合同…'}
        autoSize={{ minRows: 2, maxRows: 6 }}
        disabled={isStreaming}
        bordered={false}
        style={{ fontSize: 16, lineHeight: '26px', padding: '4px 0', resize: 'none', color: 'var(--text-primary)' }}
      />

      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: 8 }}>
        <Upload beforeUpload={onFileSelect} showUploadList={false} accept="image/*,.pdf,.doc,.docx,.xls,.xlsx,.txt,.csv">
          <Button
            type="text"
            icon={<PaperClipOutlined style={{ fontSize: 17 }} />}
            disabled={isStreaming}
            style={{ color: 'var(--text-tertiary)', padding: '4px 8px' }}
          />
        </Upload>
        {isStreaming ? (
          <Button danger icon={<StopOutlined />} onClick={onStop} style={{ borderRadius: 8, height: 36 }}>
            停止
          </Button>
        ) : (
          <Button
            type="primary"
            icon={<SendOutlined />}
            onClick={onSend}
            disabled={!value.trim()}
            style={{ borderRadius: 8, height: 36, padding: '0 18px', fontSize: 14 }}
          >
            发送
          </Button>
        )}
      </div>
    </div>
  )
})

/* ── 主组件 ── */
export default function AgentChat() {
  const [inputText, setInputText] = useState('')
  const [pendingFiles, setPendingFiles] = useState<File[]>([])
  const messageListRef = useRef<HTMLDivElement>(null)
  const [rightPanelOpen, setRightPanelOpen] = useState(true)
  const [hoveredSession, setHoveredSession] = useState<string | null>(null)

  const screens = Grid.useBreakpoint()
  const isMobile = !(screens.md ?? true)

  const {
    sessions,
    currentSessionId,
    messages,
    isStreaming,
    error,
    loadSessions,
    createSession,
    switchSession,
    deleteSession,
    sendMessage,
    stopGeneration,
    clearError,
    selectedTool,
    setSelectedTool,
  } = useAgentStore()

  useEffect(() => { loadSessions() }, [])

  useEffect(() => {
    if (!currentSessionId) {
      createSession()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    if (messageListRef.current) {
      messageListRef.current.scrollTop = messageListRef.current.scrollHeight
    }
  }, [messages])

  useEffect(() => {
    if (error) { message.error(error); clearError() }
  }, [error])

  useEffect(() => {
    const handlePaste = (e: ClipboardEvent) => {
      const items = e.clipboardData?.items
      if (!items) return
      for (const item of items) {
        if (item.type.startsWith('image/')) {
          e.preventDefault()
          const file = item.getAsFile()
          if (file) setPendingFiles((prev) => [...prev, file])
          return
        }
      }
    }
    document.addEventListener('paste', handlePaste)
    return () => document.removeEventListener('paste', handlePaste)
  }, [])

  const handleSend = useCallback(async () => {
    const text = inputText.trim()
    if (!text && pendingFiles.length === 0) {
      message.warning('请输入内容或上传文件')
      return
    }
    if (pendingFiles.length > 0 && !text) {
      message.warning('上传文件时必须添加文字说明')
      return
    }
    const filesToSend = pendingFiles.length > 0 ? [...pendingFiles] : undefined
    setInputText('')
    setPendingFiles([])
    await sendMessage(text, filesToSend)
  }, [inputText, pendingFiles, sendMessage])

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend() }
    },
    [handleSend],
  )

  const handleFileSelect = useCallback((file: File) => {
    setPendingFiles((prev) => [...prev, file])
    return false
  }, [])

  const removePendingFile = useCallback((index: number) => {
    setPendingFiles((prev) => prev.filter((_, i) => i !== index))
  }, [])

  // ── 会话管理（左侧面板）──
  const handleNewChat = useCallback(async () => {
    await createSession()
  }, [createSession])

  const handleClickSession = useCallback((sessionId: string) => {
    switchSession(sessionId)
  }, [switchSession])

  const handleDeleteSession = useCallback((sessionId: string, e: React.MouseEvent) => {
    e.stopPropagation()
    Modal.confirm({
      title: '删除会话',
      content: '确定要删除此会话吗？删除后无法恢复。',
      okText: '删除',
      okType: 'danger',
      cancelText: '取消',
      onOk: () => deleteSession(sessionId),
    })
  }, [deleteSession])

  const hasMessages = messages.some((m) => m.role === 'user' || m.role === 'assistant')

  // ── 活跃助手消息：取最后一条助手的 toolCalls / thoughts 用于右侧面板 ──
  const lastAssistantMsg = [...messages].reverse().find(m => m.role === 'assistant')

  return (
    <div style={{ display: 'flex', height: 'calc(100vh - 56px)' }}>

      {/* ══════ 左侧面板 — 会话管理 ══════ */}
      {!isMobile && (
        <div style={{
          width: 200, minWidth: 200,
          background: 'linear-gradient(180deg, #0f1a2e 0%, #162240 100%)',
          display: 'flex', flexDirection: 'column',
          overflow: 'hidden',
          borderRight: '1px solid rgba(255,255,255,0.06)',
        }}>
          <div style={{
            padding: '12px 12px',
            display: 'flex', alignItems: 'center', gap: 8,
            borderBottom: '1px solid rgba(255,255,255,0.06)',
          }}>
            <div style={{
              width: 28, height: 28, borderRadius: 8,
              background: 'linear-gradient(135deg, var(--brand-gold), #e8b84b)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              color: '#0f1a2e', flexShrink: 0,
            }}>
              <StarFilled style={{ fontSize: 14 }} />
            </div>
            <Text style={{ fontSize: 13, fontWeight: 500, color: '#e2e8f0' }}>
              小星助手
            </Text>
            <Tag color="gold" style={{ margin: 0, fontSize: 9, lineHeight: '14px', padding: '0 4px', borderRadius: 3 }}>
              AI
            </Tag>
          </div>

          <div
            onClick={handleNewChat}
            style={{
              margin: '8px 10px 6px',
              padding: '7px 12px',
              borderRadius: 8,
              border: '1px solid rgba(255,255,255,0.10)',
              cursor: 'pointer',
              display: 'flex', alignItems: 'center', gap: 6,
              color: 'rgba(255,255,255,0.6)',
              fontSize: 12, fontWeight: 500,
              transition: 'all 0.15s',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = 'rgba(255,255,255,0.05)'
              e.currentTarget.style.color = '#e2e8f0'
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = 'transparent'
              e.currentTarget.style.color = 'rgba(255,255,255,0.6)'
            }}
          >
            <PlusOutlined style={{ fontSize: 11 }} />
            新对话
          </div>

          <div style={{
            margin: '0 10px 8px',
            padding: '6px 10px',
            borderRadius: 6,
            background: 'rgba(255,255,255,0.04)',
            border: '1px solid rgba(255,255,255,0.06)',
            fontSize: 11, color: 'rgba(255,255,255,0.3)',
          }}>
            <MessageOutlined style={{ marginRight: 6, fontSize: 11 }} />
            搜索会话...
          </div>

          <div style={{ flex: 1, overflow: 'auto', padding: '0 8px 8px', minHeight: 0 }}>
            {sessions.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '24px 8px', color: 'rgba(255,255,255,0.3)', fontSize: 11 }}>
                暂无对话
              </div>
            ) : (
              sessions.map((session) => {
                const isActive = session.sessionId === currentSessionId
                const isHovered = hoveredSession === session.sessionId
                return (
                  <div
                    key={session.sessionId}
                    onClick={() => handleClickSession(session.sessionId)}
                    onMouseEnter={() => setHoveredSession(session.sessionId)}
                    onMouseLeave={() => setHoveredSession(null)}
                    style={{
                      padding: '7px 10px',
                      borderRadius: 6,
                      cursor: 'pointer',
                      marginBottom: 2,
                      background: isActive
                        ? 'rgba(201, 149, 43, 0.15)'
                        : isHovered
                          ? 'rgba(255,255,255,0.05)'
                          : 'transparent',
                      border: isActive ? '1px solid rgba(201,149,43,0.25)' : '1px solid transparent',
                      transition: 'all 0.15s',
                      position: 'relative',
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 4 }}>
                      <Text style={{
                        fontSize: 11,
                        fontWeight: isActive ? 600 : 400,
                        color: isActive ? '#f1f5f9' : 'rgba(255,255,255,0.7)',
                        display: 'block',
                        overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                        flex: 1, minWidth: 0,
                      }}>
                        {session.title || '新对话'}
                      </Text>
                      <DeleteOutlined
                        onClick={(e) => handleDeleteSession(session.sessionId, e)}
                        style={{
                          fontSize: 10,
                          color: isHovered ? 'rgba(255,255,255,0.45)' : 'transparent',
                          padding: 2, flexShrink: 0,
                          cursor: 'pointer', transition: 'color 0.15s',
                        }}
                        onMouseEnter={(ev) => { ev.currentTarget.style.color = '#ef4444' }}
                        onMouseLeave={(ev) => { ev.currentTarget.style.color = isHovered ? 'rgba(255,255,255,0.45)' : 'transparent' }}
                      />
                    </div>
                    <div style={{ display: 'flex', gap: 6, marginTop: 2 }}>
                      <span style={{ fontSize: 9, color: 'rgba(255,255,255,0.3)' }}>
                        {formatSessionTime(session.createdAt)}
                      </span>
                      <span style={{ fontSize: 9, color: 'rgba(255,255,255,0.3)' }}>
                        {session.messageCount} 条
                      </span>
                    </div>
                  </div>
                )
              })
            )}
          </div>
        </div>
      )}

      {/* ══════ 中央主区域 — 对话 ══════ */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
        <div
          ref={messageListRef}
          className={hasMessages ? 'chat-grid-bg' : ''}
          style={{
            flex: 1,
            overflow: 'auto',
            padding: hasMessages ? (isMobile ? '12px 14px' : '20px 24px') : 0,
            background: hasMessages ? undefined : 'linear-gradient(180deg, var(--bg-page) 0%, #f0f2f5 100%)',
          }}
        >
          {!currentSessionId ? (
            <div className="chat-grid-bg" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', padding: '24px' }}>
              <div className="welcome-stagger" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', width: '100%', maxWidth: 640 }}>
                <div
                  className="star-logo-halo"
                  style={{
                    width: 64, height: 64, borderRadius: 20,
                    background: 'linear-gradient(135deg, var(--brand-gold) 0%, #e8b84b 100%)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    marginBottom: 18,
                  }}
                >
                  <StarFilled style={{ fontSize: 30, color: '#0f1a2e' }} />
                </div>
                <Text style={{ fontSize: 28, fontWeight: 700, color: 'var(--text-primary)', fontFamily: 'var(--font-display)', marginBottom: 8, letterSpacing: 0.5 }}>
                  你好，我是小星
                </Text>
                <Text style={{ fontSize: 15, color: 'var(--text-tertiary)', marginBottom: 28, textAlign: 'center' }}>
                  查询合同付款 · 上传凭证登记 · 查看收支统计 · 合同条款问答
                </Text>

                <CenterInputBox
                  value={inputText}
                  onChange={setInputText}
                  onSend={handleSend}
                  onFileSelect={handleFileSelect}
                  isStreaming={isStreaming}
                  onStop={stopGeneration}
                  pendingFiles={pendingFiles}
                  onRemoveFile={removePendingFile}
                  toolTag={selectedTool ? (
                    <ToolTag value={selectedTool} onRemove={() => setSelectedTool(null)} />
                  ) : null}
                />

                <div style={{ marginTop: 32 }}>
                  <div style={{
                    textAlign: 'center', fontSize: 13, color: 'var(--text-tertiary)',
                    marginBottom: 14, fontWeight: 500, letterSpacing: 0.3,
                  }}>
                    ✦ 先选一个工具，让小星为你做更精准的事
                  </div>
                  <ToolSelector value={selectedTool} onChange={setSelectedTool} />
                </div>

                <div style={{
                  display: 'flex', flexWrap: 'wrap', gap: 12, justifyContent: 'center',
                  marginTop: 28, maxWidth: 600,
                }}>
                  {suggestions.map((s, i) => (
                    <div
                      key={i}
                      className="quick-pill"
                      onClick={() => setInputText(s.text)}
                      style={{
                        display: 'inline-flex', alignItems: 'center', gap: 10,
                        padding: '10px 20px',
                        background: 'var(--bg-surface)',
                        border: '1px solid var(--border-light)',
                        borderRadius: 22,
                        cursor: 'pointer', fontSize: 14, color: 'var(--text-secondary)',
                        boxShadow: '0 1px 3px rgba(0,0,0,0.03)',
                      }}
                    >
                      <span
                        className="quick-pill-icon"
                        style={{
                          display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                          width: 26, height: 26, borderRadius: 7,
                          background: 'var(--brand-gold-bg)', color: 'var(--brand-gold)',
                          fontSize: 14, transition: 'all 0.2s',
                        }}
                      >
                        {s.icon}
                      </span>
                      {s.text}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          ) : !hasMessages ? (
            <div className="chat-grid-bg" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', padding: '24px' }}>
              <div className="welcome-stagger" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', width: '100%', maxWidth: 700 }}>
                <div
                  className="star-logo-halo"
                  style={{
                    width: 72, height: 72, borderRadius: 22,
                    background: 'linear-gradient(135deg, var(--brand-gold) 0%, #e8b84b 100%)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    marginBottom: 20,
                  }}
                >
                  <StarFilled style={{ fontSize: 34, color: '#0f1a2e' }} />
                </div>
                <Text style={{ fontSize: 28, fontWeight: 700, color: 'var(--text-primary)', fontFamily: 'var(--font-display)', marginBottom: 8, letterSpacing: 0.5 }}>
                  你好，我是小星
                </Text>
                <Text style={{ fontSize: 15, color: 'var(--text-tertiary)', marginBottom: 28, textAlign: 'center' }}>
                  查询合同付款 · 上传凭证登记 · 查看收支统计 · 合同条款问答
                </Text>

                <CenterInputBox
                  value={inputText}
                  onChange={setInputText}
                  onSend={handleSend}
                  onFileSelect={handleFileSelect}
                  isStreaming={isStreaming}
                  onStop={stopGeneration}
                  pendingFiles={pendingFiles}
                  onRemoveFile={removePendingFile}
                  toolTag={selectedTool ? (
                    <ToolTag value={selectedTool} onRemove={() => setSelectedTool(null)} />
                  ) : null}
                />

                <div style={{ marginTop: 32 }}>
                  <div style={{
                    textAlign: 'center', fontSize: 13, color: 'var(--text-tertiary)',
                    marginBottom: 14, fontWeight: 500, letterSpacing: 0.3,
                  }}>
                    ✦ 先选一个工具，让小星为你做更精准的事
                  </div>
                  <ToolSelector value={selectedTool} onChange={setSelectedTool} />
                </div>

                <div style={{
                  display: 'flex', flexWrap: 'wrap', gap: 12, justifyContent: 'center',
                  marginTop: 28, maxWidth: 640,
                }}>
                  {suggestions.map((s, i) => (
                    <div
                      key={i}
                      className="quick-pill"
                      onClick={() => setInputText(s.text)}
                      style={{
                        display: 'inline-flex', alignItems: 'center', gap: 10,
                        padding: '10px 20px',
                        background: 'var(--bg-surface)',
                        border: '1px solid var(--border-light)',
                        borderRadius: 22,
                        cursor: 'pointer', fontSize: 14, color: 'var(--text-secondary)',
                        boxShadow: '0 1px 3px rgba(0,0,0,0.03)',
                      }}
                    >
                      <span
                        className="quick-pill-icon"
                        style={{
                          display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                          width: 26, height: 26, borderRadius: 7,
                          background: 'var(--brand-gold-bg)', color: 'var(--brand-gold)',
                          fontSize: 14, transition: 'all 0.2s',
                        }}
                      >
                        {s.icon}
                      </span>
                      {s.text}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            <div style={{ maxWidth: 768, margin: '0 auto' }}>
              {messages
                .filter((m) => m.role === 'user' || m.role === 'assistant')
                .map((msg, idx, arr) => (
                  <MessageBubble
                    key={msg.id}
                    msg={msg}
                    streaming={isStreaming && msg.role === 'assistant' && idx === arr.length - 1}
                  />
                ))}
            </div>
          )}
        </div>

        {/* 输入区域 */}
        {currentSessionId && hasMessages && (
          <div
            style={{
              padding: isMobile ? '8px 12px 12px' : '14px 24px 18px',
              background: 'transparent',
              borderTop: '1px solid var(--border-light)',
              flexShrink: 0,
            }}
          >
            <div style={{ maxWidth: 768, margin: '0 auto' }}>
              <div style={{
                display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10,
                flexWrap: 'wrap',
              }}>
                <span style={{
                  fontSize: 12, color: 'var(--text-tertiary)', fontWeight: 500,
                  marginRight: 4, flexShrink: 0,
                }}>
                  工具：
                </span>
                {TOOLS.map((t) => {
                  const isActive = selectedTool === t.key
                  return (
                    <div
                      key={t.key}
                      onClick={() => setSelectedTool(isActive ? null : t.key)}
                      className="tool-pill"
                      style={{
                        display: 'inline-flex', alignItems: 'center', gap: 6,
                        padding: '5px 12px',
                        background: isActive ? t.color : 'transparent',
                        border: `1px solid ${isActive ? t.color : 'var(--border-light)'}`,
                        borderRadius: 14,
                        cursor: 'pointer',
                        fontSize: 12, fontWeight: isActive ? 600 : 400,
                        color: isActive ? '#fff' : 'var(--text-secondary)',
                        transition: 'all 0.18s',
                      }}
                      onMouseEnter={(e) => {
                        if (!isActive) {
                          e.currentTarget.style.borderColor = t.color
                          e.currentTarget.style.color = t.color
                        }
                      }}
                      onMouseLeave={(e) => {
                        if (!isActive) {
                          e.currentTarget.style.borderColor = 'var(--border-light)'
                          e.currentTarget.style.color = 'var(--text-secondary)'
                        }
                      }}
                    >
                      <span style={{ display: 'inline-flex', fontSize: 12 }}>{t.icon}</span>
                      {t.label}
                    </div>
                  )
                })}
                {selectedTool && (
                  <span
                    onClick={() => setSelectedTool(null)}
                    style={{
                      fontSize: 11, color: 'var(--text-tertiary)',
                      cursor: 'pointer', marginLeft: 4, textDecoration: 'underline',
                    }}
                    onMouseEnter={(e) => { e.currentTarget.style.color = 'var(--color-danger)' }}
                    onMouseLeave={(e) => { e.currentTarget.style.color = 'var(--text-tertiary)' }}
                  >
                    清除
                  </span>
                )}
              </div>

              {pendingFiles.length > 0 && (
                <div
                  style={{
                    background: 'var(--bg-subtle)', border: '1px solid var(--border-light)',
                    borderBottom: 'none', borderRadius: '12px 12px 0 0',
                    padding: '10px 14px', display: 'flex', gap: 8,
                    flexWrap: 'wrap', alignItems: 'center',
                  }}
                >
                  <span style={{ fontSize: 11, color: 'var(--text-tertiary)', marginRight: 4, whiteSpace: 'nowrap' }}>
                    待发送附件
                  </span>
                  {pendingFiles.map((f, i) => {
                    const name = f.name.toLowerCase()
                    if (f.type.startsWith('image/')) {
                      return (
                        <span
                          key={i} style={{ position: 'relative', display: 'inline-block', cursor: 'pointer' }}
                          onClick={() => removePendingFile(i)}
                        >
                          <img
                            src={URL.createObjectURL(f)} alt={f.name}
                            style={{ height: 40, width: 40, borderRadius: 8, objectFit: 'cover', border: '1px solid var(--border-default)' }}
                          />
                          <span style={{
                            position: 'absolute', top: -6, right: -6,
                            background: 'var(--color-danger)', color: '#fff',
                            borderRadius: '50%', width: 16, height: 16,
                            fontSize: 10, lineHeight: '16px', textAlign: 'center',
                            boxShadow: '0 2px 4px rgba(220,38,38,0.3)',
                          }}>×</span>
                        </span>
                      )
                    }
                    const icon = name.endsWith('.pdf') ? <FilePdfOutlined style={{ color: '#dc2626' }} />
                      : name.endsWith('.docx') || name.endsWith('.doc') ? <FileWordOutlined style={{ color: 'var(--brand-primary)' }} />
                      : name.endsWith('.xlsx') || name.endsWith('.xls') ? <FileExcelOutlined style={{ color: 'var(--color-success)' }} />
                      : <FileTextOutlined style={{ color: 'var(--color-warning)' }} />
                    return (
                      <Tag key={i} closable onClose={() => removePendingFile(i)} color="default" style={{ margin: 0, fontSize: 12, borderRadius: 4 }}>
                        {icon} {f.name.length > 20 ? f.name.slice(0, 18) + '…' : f.name}
                      </Tag>
                    )
                  })}
                </div>
              )}

              <div
                style={{
                  display: 'flex', gap: 10, alignItems: 'flex-end',
                  background: 'transparent', border: '1px solid var(--border-default)',
                  borderRadius: pendingFiles.length > 0 ? '0 0 14px 14px' : 14,
                  padding: '10px 10px 10px 16px',
                  boxShadow: '0 2px 12px rgba(15,23,42,0.05)',
                  transition: 'border-color 0.2s, box-shadow 0.2s',
                }}
                onMouseEnter={(e) => {
                  if (!e.currentTarget.querySelector(':focus-within')) e.currentTarget.style.borderColor = 'var(--border-hover)'
                }}
                onMouseLeave={(e) => {
                  if (!e.currentTarget.querySelector(':focus-within')) e.currentTarget.style.borderColor = 'var(--border-default)'
                }}
              >
                <Upload
                  beforeUpload={handleFileSelect}
                  showUploadList={false}
                  accept="image/*,.pdf,.doc,.docx,.xls,.xlsx,.txt,.csv"
                >
                  <Button
                    type="text"
                    icon={<PaperClipOutlined style={{ fontSize: 18 }} />}
                    disabled={isStreaming}
                    style={{
                      padding: '8px', borderRadius: 8,
                      color: pendingFiles.length > 0 ? 'var(--brand-primary)' : 'var(--text-tertiary)',
                      flexShrink: 0, fontSize: 16,
                    }}
                  />
                </Upload>
                <Input.TextArea
                  value={inputText}
                  onChange={(e) => setInputText(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder={pendingFiles.length > 0 ? '请描述文件内容（必填）...' : '输入你的问题...'}
                  autoSize={{ minRows: 1, maxRows: 5 }}
                  disabled={isStreaming}
                  bordered={false}
                  style={{ flex: 1, fontSize: 15, lineHeight: '24px', padding: '6px 0', resize: 'none', color: 'var(--text-primary)' }}
                />
                {isStreaming ? (
                  <Button
                    danger size="large" icon={<StopOutlined />}
                    onClick={stopGeneration}
                    style={{ borderRadius: 8, height: 40, padding: '0 16px', flexShrink: 0 }}
                  >
                    停止
                  </Button>
                ) : (
                  <Button
                    type="primary" size="large" icon={<SendOutlined />}
                    onClick={handleSend}
                    disabled={!inputText.trim()}
                    style={{ borderRadius: 8, height: 40, padding: '0 20px', flexShrink: 0, fontSize: 14 }}
                  >
                    发送
                  </Button>
                )}
              </div>
              <div style={{ textAlign: 'center', fontSize: 11, color: 'var(--text-tertiary)', marginTop: 8 }}>
                Ctrl/Cmd + V 粘贴图片 · AI 可能产生错误信息，请核实重要数据
              </div>
            </div>
          </div>
        )}
      </div>

      {/* ══════ 右侧面板 — 活动面板 ══════ */}
      {!isMobile && (
        <div style={{
          width: rightPanelOpen ? 240 : 0,
          minWidth: rightPanelOpen ? 240 : 0,
          background: 'var(--bg-surface)',
          display: 'flex', flexDirection: 'column',
          overflow: 'hidden',
          borderLeft: rightPanelOpen ? '1px solid var(--border-light)' : 'none',
          transition: 'width 0.25s cubic-bezier(0.4, 0, 0.2, 1), min-width 0.25s cubic-bezier(0.4, 0, 0.2, 1)',
        }}>
          <div style={{
            padding: '10px 14px',
            borderBottom: '1px solid var(--border-light)',
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            flexShrink: 0,
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <Text style={{ fontSize: 12, fontWeight: 500, color: 'var(--text-primary)' }}>
                活动面板
              </Text>
            </div>
            <Button
              type="text"
              size="small"
              icon={rightPanelOpen ? <RightOutlined /> : <LeftOutlined />}
              onClick={() => setRightPanelOpen(!rightPanelOpen)}
              style={{ color: 'var(--text-tertiary)', padding: '0 4px', height: 22, fontSize: 10 }}
            />
          </div>

          {rightPanelOpen && (
            <div style={{ flex: 1, overflow: 'auto', padding: '8px 10px', minHeight: 0 }}>
              {/* ── 思考链 ── */}
              {lastAssistantMsg?.thoughts && lastAssistantMsg.thoughts.length > 0 && (
                <div style={{
                  padding: '8px 10px', borderRadius: 6, marginBottom: 8,
                  border: '1px solid var(--border-light)',
                  background: 'var(--bg-subtle)',
                }}>
                  <div style={{
                    display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8,
                  }}>
                    <div style={{
                      width: 22, height: 22, borderRadius: 5,
                      background: 'var(--brand-primary-lighter)', color: 'var(--brand-primary)',
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      fontSize: 11, flexShrink: 0,
                    }}>
                      ⚡
                    </div>
                    <span style={{ fontSize: 11, fontWeight: 500, color: 'var(--text-primary)' }}>思考链</span>
                  </div>
                  {lastAssistantMsg.thoughts.map((step, i) => (
                    <div key={step.id} style={{
                      display: 'flex', alignItems: 'center', gap: 6,
                      padding: '3px 0', fontSize: 11, color: 'var(--text-secondary)',
                    }}>
                      <span style={{
                        width: 6, height: 6, borderRadius: '50%', flexShrink: 0,
                        background: step.status === 'done' ? 'var(--color-success)' : 'var(--brand-gold)',
                        opacity: step.status === 'running' ? 1 : 0.6,
                      }} />
                      {step.message}
                    </span>
                  ))}
                </div>
              )}

              {/* ── 工具调用 ── */}
              {lastAssistantMsg?.toolCalls && lastAssistantMsg.toolCalls.length > 0 && (
                <div style={{
                  padding: '8px 10px', borderRadius: 6, marginBottom: 8,
                  border: '1px solid var(--border-light)',
                  background: 'var(--bg-subtle)',
                }}>
                  <div style={{
                    display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8,
                  }}>
                    <div style={{
                      width: 22, height: 22, borderRadius: 5,
                      background: 'var(--brand-gold-bg)', color: 'var(--brand-gold)',
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      fontSize: 11, flexShrink: 0,
                    }}>
                      🔧
                    </div>
                    <span style={{ fontSize: 11, fontWeight: 500, color: 'var(--text-primary)' }}>工具调用</span>
                  </div>
                  {lastAssistantMsg.toolCalls.map((tc, i) => (
                    <div key={tc.id} style={{
                      display: 'flex', alignItems: 'center', gap: 4,
                      padding: '2px 0', fontSize: 11,
                    }}>
                      <span style={{ color: tc.result ? 'var(--color-success)' : 'var(--brand-gold)', fontSize: 10 }}>
                        {tc.result ? '✓' : '◌'}
                      </span>
                      <span style={{
                        color: 'var(--text-secondary)',
                        fontFamily: 'var(--font-mono)', fontSize: 10,
                      }}>
                        {tc.name}
                      </span>
                    </div>
                  ))}
                </div>
              )}

              {/* ── 数据引用 ── */}
              {lastAssistantMsg?.toolCalls?.some(tc => tc.summary?.items?.length) && (
                <div style={{
                  padding: '8px 10px', borderRadius: 6, marginBottom: 8,
                  border: '1px solid var(--border-light)',
                  background: 'var(--bg-subtle)',
                }}>
                  <div style={{
                    display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8,
                  }}>
                    <div style={{
                      width: 22, height: 22, borderRadius: 5,
                      background: 'var(--color-success-bg)', color: 'var(--color-success)',
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      fontSize: 11, flexShrink: 0,
                    }}>
                      📊
                    </div>
                    <span style={{ fontSize: 11, fontWeight: 500, color: 'var(--text-primary)' }}>数据引用</span>
                  </div>
                  {lastAssistantMsg.toolCalls.filter(tc => tc.summary?.items?.length).map((tc) => (
                    <div key={tc.id}>
                      {tc.summary!.items.map((item, j) => (
                        <div key={j} style={{
                          display: 'flex', justifyContent: 'space-between',
                          padding: '2px 0', fontSize: 11,
                        }}>
                          <span style={{ color: 'var(--text-secondary)' }}>{item.label}</span>
                          <span style={{
                            color: item.highlight === 'warning' ? 'var(--color-danger)' : 'var(--text-primary)',
                            fontWeight: 500,
                          }}>
                            {item.value}
                          </span>
                        </div>
                      ))}
                    </div>
                  ))}
                </div>
              )}

              {/* ── 空状态 ── */}
              {!(lastAssistantMsg?.thoughts?.length || lastAssistantMsg?.toolCalls?.length) && (
                <div style={{
                  textAlign: 'center', padding: '32px 8px',
                  color: 'var(--text-tertiary)', fontSize: 11,
                }}>
                  <div style={{ fontSize: 28, marginBottom: 8, opacity: 0.4 }}>⚡</div>
                  发送消息后，这里将显示<br />AI 的思考和工具调用过程
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
