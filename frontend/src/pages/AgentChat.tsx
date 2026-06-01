import { useState, useCallback, useRef, useEffect } from 'react'
import {
  Input,
  Button,
  Avatar,
  Tag,
  Upload,
  Tooltip,
  message,
  Spin,
  Modal,
  Typography,
} from 'antd'
import {
  SendOutlined,
  RobotOutlined,
  UserOutlined,
  PaperClipOutlined,
  PlusOutlined,
  StopOutlined,
  DeleteOutlined,
  ToolOutlined,
  CheckCircleOutlined,
  ExclamationCircleOutlined,
  FilePdfOutlined,
  FileWordOutlined,
  FileExcelOutlined,
  FileTextOutlined,
  HistoryOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
} from '@ant-design/icons'
import { useAgentStore } from '@/store/useAgentStore'
import type { ChatMessage, ToolCall } from '@/types/agent'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

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
  get_overdue_payments: '逾期查询',
  get_expiring_contracts: '到期合同',
  analyze_image: '文件分析',
}

/* ── 格式化时间 ── */
function formatTime(iso: string | null | undefined): string {
  if (!iso) return ''
  const d = new Date(iso)
  const now = new Date()
  const diffMs = now.getTime() - d.getTime()
  const diffMin = Math.floor(diffMs / 60000)
  if (diffMin < 1) return '刚刚'
  if (diffMin < 60) return `${diffMin}分钟前`
  const diffHour = Math.floor(diffMin / 60)
  if (diffHour < 24) return `${diffHour}小时前`
  const diffDay = Math.floor(diffHour / 24)
  if (diffDay < 7) return `${diffDay}天前`
  return `${d.getMonth() + 1}/${d.getDate()}`
}

/* ── 工具调用标签 ── */
function ToolCallView({ toolCall }: { toolCall: ToolCall }) {
  const label = TOOL_LABELS[toolCall.name] || toolCall.name
  const hasResult = !!toolCall.result

  return (
    <Tooltip title={!hasResult ? '历史记录中该工具结果未保存，返回查看时请重新对话获取最新信息' : undefined}>
      <Tag
        color={hasResult ? 'green' : 'orange'}
        icon={hasResult ? <CheckCircleOutlined /> : <ExclamationCircleOutlined />}
        style={{ marginBottom: 4, cursor: hasResult ? 'default' : 'help', borderRadius: 4 }}
      >
        <ToolOutlined /> {label}
      </Tag>
    </Tooltip>
  )
}

/* ── Markdown 渲染 ── */
function MarkdownRenderer({ content }: { content: string }) {
  return (
    <div className="markdown-content">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          table: ({ children }) => (
            <div style={{ overflowX: 'auto', margin: '8px 0' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>{children}</table>
            </div>
          ),
          thead: ({ children }) => <thead style={{ background: 'var(--bg-subtle)' }}>{children}</thead>,
          th: ({ children }) => (
            <th style={{ border: '1px solid var(--border-light)', padding: '6px 10px', textAlign: 'left', fontWeight: 600, color: 'var(--text-primary)' }}>
              {children}
            </th>
          ),
          td: ({ children }) => (
            <td style={{ border: '1px solid var(--border-light)', padding: '6px 10px', color: 'var(--text-secondary)' }}>
              {children}
            </td>
          ),
          strong: ({ children }) => <strong style={{ color: 'var(--brand-primary)' }}>{children}</strong>,
          p: ({ children }) => <p style={{ margin: '6px 0', lineHeight: 1.7 }}>{children}</p>,
          ol: ({ children }) => <ol style={{ margin: '6px 0', paddingLeft: 20 }}>{children}</ol>,
          ul: ({ children }) => <ul style={{ margin: '6px 0', paddingLeft: 20 }}>{children}</ul>,
          li: ({ children }) => <li style={{ margin: '4px 0' }}>{children}</li>,
          code: ({ inline, children }: any) =>
            inline ? (
              <code style={{ background: 'var(--bg-hover)', padding: '2px 6px', borderRadius: 4, fontSize: 12, color: '#d63384' }}>
                {children}
              </code>
            ) : (
              <pre style={{ background: '#1e293b', color: '#e2e8f0', padding: 14, borderRadius: 8, overflow: 'auto', fontSize: 12, margin: '8px 0', lineHeight: 1.5 }}>
                <code>{children}</code>
              </pre>
            ),
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  )
}

/* ── 消息气泡 ── */
function MessageBubble({ msg }: { msg: ChatMessage }) {
  if (msg.role === 'user') {
    return (
      <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 20 }}>
        <div style={{ maxWidth: '72%', display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 6 }}>
          {msg.attachments && msg.attachments.length > 0 && (
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', justifyContent: 'flex-end' }}>
              {msg.attachments.map((att, i) => {
                if (att.fileType === 'image' && att.preview) {
                  return (
                    <img
                      key={i} src={att.preview} alt={att.fileName || '附件'}
                      style={{ maxWidth: 180, maxHeight: 180, borderRadius: 10, objectFit: 'cover', border: '2px solid var(--brand-primary)', boxShadow: '0 2px 8px rgba(0,0,0,0.08)' }}
                    />
                  )
                }
                const fileIcon = att.fileType === 'pdf' ? <FilePdfOutlined />
                  : att.fileType === 'word' ? <FileWordOutlined />
                  : att.fileType === 'excel' ? <FileExcelOutlined />
                  : att.fileType === 'text' ? <FileTextOutlined />
                  : <PaperClipOutlined />
                return <Tag key={i} color="blue" style={{ margin: 0 }}>{fileIcon} {att.fileName || '文件'}</Tag>
              })}
            </div>
          )}
          <div
            style={{
              background: 'linear-gradient(135deg, var(--brand-primary) 0%, var(--brand-primary-light) 100%)',
              color: '#fff',
              padding: msg.content ? '10px 16px' : '6px 16px',
              borderRadius: '14px 14px 4px 14px',
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-word',
              lineHeight: msg.content ? 1.6 : '32px',
              boxShadow: '0 2px 8px rgba(30,58,95,0.15)',
            }}
          >
            {msg.content || (msg.attachments?.length ? `已上传 ${msg.attachments.length} 个文件` : '')}
          </div>
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
        <div style={{ maxWidth: '72%' }}>
          {msg.toolCalls && msg.toolCalls.length > 0 && (
            <div style={{ marginBottom: 6, display: 'flex', flexWrap: 'wrap', gap: 4 }}>
              {msg.toolCalls.map((tc, i) => (
                <ToolCallView key={i} toolCall={tc} />
              ))}
            </div>
          )}
          {msg.content ? (
            <div
              style={{
                background: 'var(--bg-surface)',
                padding: '12px 18px',
                borderRadius: '14px 14px 14px 4px',
                wordBreak: 'break-word',
                border: '1px solid var(--border-light)',
                boxShadow: '0 1px 4px rgba(0,0,0,0.03)',
              }}
            >
              <MarkdownRenderer content={msg.content} />
            </div>
          ) : (msg as any)._thinking ? (
            <div
              style={{
                background: 'var(--bg-surface)', padding: '8px 16px',
                borderRadius: '14px 14px 14px 4px',
                display: 'flex', alignItems: 'center', gap: 8,
                color: 'var(--text-tertiary)', fontSize: 13,
                border: '1px solid var(--border-light)',
              }}
            >
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

/* ── 快捷建议 ── */
const suggestions = [
  '查看当前系统有哪些数据',
  '查询逾期付款记录',
  '上传合同文件进行录入',
]

/* ── 主组件 ── */
export default function AgentChat() {
  const [inputText, setInputText] = useState('')
  const [pendingFiles, setPendingFiles] = useState<File[]>([])
  const [leftCollapsed, setLeftCollapsed] = useState(false)
  const messageListRef = useRef<HTMLDivElement>(null)
  const [hoveredSession, setHoveredSession] = useState<string | null>(null)

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
  } = useAgentStore()

  useEffect(() => { loadSessions() }, [])

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
    if (!text && pendingFiles.length === 0) return
    await sendMessage(text, pendingFiles.length > 0 ? pendingFiles : undefined)
    setInputText('')
    setPendingFiles([])
  }, [inputText, pendingFiles, sendMessage])

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend() }
    },
    [handleSend],
  )

  const handleNewSession = useCallback(async () => {
    await createSession()
    setLeftCollapsed(false)
  }, [createSession])

  const handleFileSelect = useCallback((file: File) => {
    setPendingFiles((prev) => [...prev, file])
    return false
  }, [])

  const removePendingFile = useCallback((index: number) => {
    setPendingFiles((prev) => prev.filter((_, i) => i !== index))
  }, [])

  const hasMessages = messages.some((m) => m.role === 'user' || m.role === 'assistant')
  const currentSession = sessions.find((s) => s.sessionId === currentSessionId)

  return (
    <div style={{ display: 'flex', height: 'calc(100vh - 56px)' }}>
      {/* ════════ 左侧：会话列表 ════════ */}
      <div
        style={{
          width: leftCollapsed ? 0 : 290,
          minWidth: leftCollapsed ? 0 : 290,
          overflow: 'hidden',
          borderRight: '1px solid var(--border-light)',
          background: 'var(--bg-surface)',
          display: 'flex',
          flexDirection: 'column',
          transition: 'width 0.2s, min-width 0.2s',
          flexShrink: 0,
        }}
      >
        {/* 左侧头部 */}
        <div
          style={{
            height: 56,
            borderBottom: '1px solid var(--border-light)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '0 14px',
            flexShrink: 0,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <HistoryOutlined style={{ fontSize: 16, color: 'var(--brand-primary)' }} />
            <Text strong style={{ fontSize: 14, color: 'var(--text-primary)' }}>
              会话列表
            </Text>
            <span
              style={{
                fontSize: 11,
                color: 'var(--text-tertiary)',
                background: 'var(--bg-subtle)',
                padding: '0 6px',
                borderRadius: 4,
                fontFamily: 'var(--font-mono)',
              }}
            >
              {sessions.length}
            </span>
          </div>
          <Button
            type="primary"
            size="small"
            icon={<PlusOutlined />}
            onClick={handleNewSession}
            style={{ borderRadius: 6, height: 30 }}
          >
            新会话
          </Button>
        </div>

        {/* 会话列表 */}
        <div style={{ flex: 1, overflow: 'auto', padding: '8px 10px' }}>
          {sessions.length === 0 ? (
            <div style={{ textAlign: 'center', paddingTop: 60 }}>
              <RobotOutlined style={{ fontSize: 28, color: 'var(--text-tertiary)', opacity: 0.3 }} />
              <div style={{ marginTop: 12, fontSize: 13, color: 'var(--text-tertiary)' }}>暂无会话</div>
            </div>
          ) : (
            sessions.map((session) => {
              const isActive = session.sessionId === currentSessionId
              const isHovered = hoveredSession === session.sessionId
              const handleDelete = (e: React.MouseEvent) => {
                e.stopPropagation()
                Modal.confirm({
                  title: '删除会话',
                  content: '确定要删除此会话吗？删除后无法恢复。',
                  okText: '删除',
                  okType: 'danger',
                  cancelText: '取消',
                  onOk: () => deleteSession(session.sessionId),
                })
              }
              return (
                <div
                  key={session.sessionId}
                  onClick={() => switchSession(session.sessionId)}
                  onMouseEnter={() => setHoveredSession(session.sessionId)}
                  onMouseLeave={() => setHoveredSession(null)}
                  style={{
                    padding: '10px 12px',
                    borderRadius: 8,
                    cursor: 'pointer',
                    marginBottom: 4,
                    background: isActive
                      ? 'var(--brand-primary-lighter)'
                      : isHovered
                        ? 'var(--bg-hover)'
                        : 'transparent',
                    border: isActive ? '1px solid rgba(30,58,95,0.15)' : '1px solid transparent',
                    transition: 'all 0.15s',
                    position: 'relative',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                    <Text
                      style={{
                        fontSize: 13,
                        fontWeight: isActive ? 600 : 500,
                        color: isActive ? 'var(--brand-primary)' : 'var(--text-primary)',
                        display: 'block',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                        flex: 1,
                        marginRight: 8,
                      }}
                    >
                      {session.title || '新会话'}
                    </Text>
                    <DeleteOutlined
                      onClick={handleDelete}
                      style={{
                        fontSize: 13,
                        color: isHovered ? 'var(--text-tertiary)' : 'transparent',
                        padding: 2,
                        flexShrink: 0,
                        cursor: 'pointer',
                        transition: 'color 0.15s',
                      }}
                      onMouseEnter={(e) => { e.currentTarget.style.color = 'var(--color-danger)' }}
                      onMouseLeave={(e) => { e.currentTarget.style.color = isHovered ? 'var(--text-tertiary)' : 'transparent' }}
                    />
                  </div>
                  <div style={{ display: 'flex', gap: 10, marginTop: 4 }}>
                    <span style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>
                      {formatTime(session.createdAt)}
                    </span>
                    <span style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>
                      {session.messageCount} 条消息
                    </span>
                  </div>
                </div>
              )
            })
          )}
        </div>

        {/* 折叠按钮 */}
        <div
          style={{
            borderTop: '1px solid var(--border-light)',
            padding: '6px 10px',
            display: 'flex',
            justifyContent: 'flex-end',
          }}
        >
          <Button
            type="text"
            size="small"
            icon={<MenuFoldOutlined />}
            onClick={() => setLeftCollapsed(true)}
            style={{ color: 'var(--text-tertiary)', fontSize: 13 }}
          >
            收起
          </Button>
        </div>
      </div>

      {/* ════════ 右侧：聊天主区域 ════════ */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
        {/* 聊天头部 */}
        <div
          style={{
            height: 56,
            borderBottom: '1px solid var(--border-light)',
            background: 'rgba(255,255,255,0.85)',
            backdropFilter: 'blur(12px)',
            WebkitBackdropFilter: 'blur(12px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '0 20px',
            flexShrink: 0,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            {/* 展开按钮（左侧收起时） */}
            {leftCollapsed && (
              <Button
                type="text"
                icon={<MenuUnfoldOutlined />}
                onClick={() => setLeftCollapsed(false)}
                style={{ color: 'var(--text-tertiary)', marginRight: 4 }}
              />
            )}
            <div
              style={{
                width: 30,
                height: 30,
                borderRadius: 8,
                background: 'linear-gradient(135deg, var(--brand-gold), #e8b84b)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#0f1a2e',
                flexShrink: 0,
              }}
            >
              <RobotOutlined style={{ fontSize: 15 }} />
            </div>
            <div>
              <Text strong style={{ fontSize: 14, color: 'var(--text-primary)', display: 'block', lineHeight: 1.2 }}>
                {currentSession ? (currentSession.title || '智能业务助手') : '智能业务助手'}
              </Text>
              <Text style={{ fontSize: 11, color: 'var(--text-tertiary)', display: 'block', lineHeight: 1.2 }}>
                {currentSession
                  ? `${currentSession.messageCount} 条消息`
                  : '选择左侧会话或开始新对话'}
              </Text>
            </div>
          </div>
        </div>

        {/* 消息区域 */}
        <div
          ref={messageListRef}
          style={{
            flex: 1,
            overflow: 'auto',
            padding: hasMessages ? '20px 24px' : 0,
            background: 'linear-gradient(180deg, var(--bg-page) 0%, #f0f2f5 100%)',
          }}
        >
          {!currentSessionId ? (
            /* 未选择会话的状态 */
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', padding: '0 24px' }}>
              <div
                style={{
                  width: 72, height: 72, borderRadius: 20,
                  background: 'linear-gradient(135deg, var(--brand-primary) 0%, var(--brand-primary-light) 100%)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  marginBottom: 24, boxShadow: '0 8px 24px rgba(30,58,95,0.2)',
                }}
              >
                <RobotOutlined style={{ fontSize: 32, color: '#fff' }} />
              </div>
              <Text style={{ fontSize: 18, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 8 }}>
                智能业务助手
              </Text>
              <Text style={{ fontSize: 13, color: 'var(--text-tertiary)', marginBottom: 24, textAlign: 'center', maxWidth: 380 }}>
                从左侧选择一个会话，或创建一个新的对话
              </Text>
              <Button
                type="primary"
                icon={<PlusOutlined />}
                onClick={handleNewSession}
                style={{ borderRadius: 8, height: 40, padding: '0 24px' }}
              >
                开始新会话
              </Button>
            </div>
          ) : !hasMessages ? (
            /* 空会话 */
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', padding: '0 24px' }}>
              <div
                style={{
                  width: 64, height: 64, borderRadius: 18,
                  background: 'linear-gradient(135deg, var(--brand-gold), #e8b84b)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  marginBottom: 20, boxShadow: '0 6px 20px rgba(201,149,43,0.2)',
                }}
              >
                <RobotOutlined style={{ fontSize: 28, color: '#0f1a2e' }} />
              </div>
              <Text style={{ fontSize: 16, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 6 }}>
                有什么可以帮你的？
              </Text>
              <Text style={{ fontSize: 13, color: 'var(--text-tertiary)', marginBottom: 28, textAlign: 'center', maxWidth: 400 }}>
                查询合同付款 · 上传凭证登记 · 分析逾期情况 · 合同条款问答
              </Text>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8, width: 320 }}>
                {suggestions.map((text, i) => (
                  <div
                    key={i}
                    onClick={() => setInputText(text)}
                    style={{
                      padding: '10px 16px', background: 'var(--bg-surface)',
                      border: '1px solid var(--border-light)', borderRadius: 10,
                      cursor: 'pointer', fontSize: 13, color: 'var(--text-secondary)',
                      transition: 'all 0.2s', textAlign: 'center',
                      boxShadow: '0 1px 2px rgba(0,0,0,0.02)',
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.borderColor = 'var(--brand-primary)'
                      e.currentTarget.style.color = 'var(--brand-primary)'
                      e.currentTarget.style.boxShadow = '0 2px 8px rgba(30,58,95,0.08)'
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.borderColor = 'var(--border-light)'
                      e.currentTarget.style.color = 'var(--text-secondary)'
                      e.currentTarget.style.boxShadow = '0 1px 2px rgba(0,0,0,0.02)'
                    }}
                  >
                    <RobotOutlined style={{ marginRight: 8, fontSize: 12, opacity: 0.5 }} />
                    {text}
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <>
              {messages
                .filter((m) => m.role === 'user' || m.role === 'assistant')
                .map((msg) => <MessageBubble key={msg.id} msg={msg} />)}
              {isStreaming && !messages.some((m) => m.role === 'assistant' && !m.content && !(m.toolCalls?.length)) && (
                <div style={{ display: 'flex', marginBottom: 16 }}>
                  <Avatar
                    icon={<RobotOutlined />}
                    style={{ background: 'linear-gradient(135deg, var(--brand-gold), #e8b84b)', marginRight: 10, color: '#0f1a2e' }}
                    size={36}
                  />
                  <Spin size="small" style={{ marginTop: 10 }} />
                </div>
              )}
            </>
          )}
        </div>

        {/* 输入区域（仅在有当前会话时显示） */}
        {currentSessionId && (
          <div
            style={{
              padding: '12px 24px 16px',
              background: 'var(--bg-surface)',
              borderTop: '1px solid var(--border-light)',
              flexShrink: 0,
            }}
          >
            {/* 文件预览 */}
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

            {/* 输入框 */}
            <div
              style={{
                display: 'flex', gap: 10, alignItems: 'flex-end',
                background: 'var(--bg-surface)', border: '1px solid var(--border-default)',
                borderRadius: pendingFiles.length > 0 ? '0 0 12px 12px' : 12,
                padding: '8px 8px 8px 14px',
                boxShadow: '0 1px 4px rgba(0,0,0,0.03)',
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
                placeholder={pendingFiles.length > 0 ? '添加说明（可选）...' : '输入你的问题...'}
                autoSize={{ minRows: 1, maxRows: 5 }}
                disabled={isStreaming}
                bordered={false}
                style={{ flex: 1, fontSize: 14, lineHeight: '22px', padding: '6px 0', resize: 'none', color: 'var(--text-primary)' }}
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
                  disabled={!inputText.trim() && pendingFiles.length === 0}
                  style={{ borderRadius: 8, height: 40, padding: '0 20px', flexShrink: 0 }}
                >
                  发送
                </Button>
              )}
            </div>
            <div style={{ textAlign: 'center', fontSize: 11, color: 'var(--text-tertiary)', marginTop: 8 }}>
              Ctrl/Cmd + V 粘贴图片 · AI 可能产生错误信息，请核实重要数据
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
