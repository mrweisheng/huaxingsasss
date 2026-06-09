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
  UserAddOutlined,
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
    // 分离图片 / 文件
    const imageAttachments = attachments.filter(a => a.fileType === 'image' && a.preview)
    const fileAttachments = attachments.filter(a => !(a.fileType === 'image' && a.preview))

    return (
      <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 20 }}>
        <div style={{
          maxWidth: '85%',
          display: 'flex', flexDirection: 'column', alignItems: 'flex-end',
        }}>
          {/* ════════ 统一气泡：附件 + 文字 共一个容器 ════════ */}
          {(hasText || hasAttachments) && (
            <div
              className="user-bubble"
              style={{
                background: 'linear-gradient(135deg, var(--brand-primary) 0%, var(--brand-primary-light) 100%)',
                color: '#fff',
                borderRadius: '16px 16px 4px 16px',
                boxShadow: '0 4px 16px rgba(30,58,95,0.20)',
                overflow: 'hidden',  // 内部子元素圆角融入
                minWidth: 60,
              }}
            >
              {/* 图片附件：单张大图 / 多张网格 */}
              {imageAttachments.length > 0 && (
                <div
                  className="user-bubble-images"
                  style={{
                    display: 'grid',
                    gap: 2,  // 图片间细缝
                    padding: imageAttachments.length === 1 ? 6 : 4,
                    background: 'rgba(255,255,255,0.06)',  // 微妙对比，让图片边界清晰
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

              {/* 文件附件：每个文件一张卡片 */}
              {fileAttachments.length > 0 && (
                <div style={{ padding: '8px 10px', display: 'flex', flexDirection: 'column', gap: 6 }}>
                  {fileAttachments.map((att, i) => {
                    const ext = (att.fileName || '').toLowerCase().split('.').pop() || ''
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
                        {/* 大色块图标 */}
                        <div style={{
                          width: 40, height: 48, borderRadius: 6,
                          background: cfg.bg,
                          display: 'flex', alignItems: 'center', justifyContent: 'center',
                          color: cfg.fg, fontSize: 20, flexShrink: 0,
                          boxShadow: '0 1px 3px rgba(0,0,0,0.10)',
                        }}>
                          {cfg.icon}
                        </div>
                        {/* 文件信息 */}
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
                            {ext.toUpperCase()} 文件
                          </span>
                        </div>
                      </div>
                    )
                  })}
                </div>
              )}

              {/* 文字内容：紧贴附件下方 */}
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
    // 找到当前正在运行的 thought（决定 Witty 场景）
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
          {/* ── Witty 俏皮文案（持续显示在 Assistant 头部）──
              位置：头像正下方，最终内容上方
              key 绑定 runningStep.id：每次 thought 切换时强制重渲染，触发新场景文案 */}
          {isThinking && runningStep && (
            <div
              key={runningStep.id}  // 关键：每次新 thought 触发组件重建，刷新文案
              style={{ marginBottom: 8 }}
            >
              <WittyLoadingText message={runningStep.message} />
            </div>
          )}

          {/* 工具调用可折叠区块（显示在 Witty 下方）*/}
          {hasToolCalls && <ToolCallBlock toolCalls={msg.toolCalls!} toolLabels={TOOL_LABELS} />}

          {/* 最终回答内容 */}
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

/* ── 三个工具（核心卖点）──
   - 选完后给当前对话打标签，sendMessage 时把 mode 透传给后端
   - 后端 mode guard 拦截越权工具（防御性）
   - 点不同工具 = 切换；点 ×  = 退回通用模式 */
const TOOLS = [
  { key: 'contract_entry' as const, icon: <FileTextOutlined />, label: '录合同', color: '#1e3a5f' },
  { key: 'receipt_income' as const, icon: <CreditCardOutlined />, label: '录收入', color: '#0d9488' },
  { key: 'receipt_expense' as const, icon: <DollarOutlined />, label: '录支出', color: '#dc2626' },
]

/* ── 工具选择器组件（空状态居中版 + 底部版通用）── */
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

/* ── 工具标签（贴在输入框前面，× 删除）── */
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

/* ── 居中输入框（与底部输入框视觉一致，单独抽出便于复用）── */
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
      {/* 工具标签（如有）—— 贴在 textarea 上方 */}
      {toolTag && (
        <div style={{ marginBottom: 8 }}>{toolTag}</div>
      )}

      {/* 待发附件 */}
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

  // 移动端断点检测
  const screens = Grid.useBreakpoint()
  const isMobile = !(screens.md ?? true)

  const {
    currentSessionId,
    messages,
    isStreaming,
    error,
    loadSessions,
    createSession,
    sendMessage,
    stopGeneration,
    clearError,
    selectedTool,
    setSelectedTool,
  } = useAgentStore()

  useEffect(() => { loadSessions() }, [])

  // 默认进入 /agent 时若没有会话，自动建一个（不显示"未选会话"中间态）
  useEffect(() => {
    if (!currentSessionId) {
      createSession()
    }
    // 仅在 mount 时检查一次
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
    // Phase 2.5：有附件时文本必填（凭证录入需要辅助文字供 VL 分析）
    if (pendingFiles.length > 0 && !text) {
      message.warning('上传文件时必须添加文字说明')
      return
    }
    // 立即清空输入框和待发文件，防止重复提交
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

  const hasMessages = messages.some((m) => m.role === 'user' || m.role === 'assistant')
  // currentSession 字段已不再使用（顶部 header 已删除，会话标题在侧边栏展示）

  return (
    <div style={{ display: 'flex', height: 'calc(100vh - 56px)' }}>
      {/* 会话列表已迁移到 Layout 侧边栏下半部分；本页面单栏全宽 */}

      {/* ════════ 聊天主区域（单栏全宽，无 header 沉浸式）══════ */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
        {/* 消息区域 */}
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
            /* 默认新会话空状态（首次进入会自动建一个 session，这里兜底）*/
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

                {/* ── 三个工具（核心卖点）── */}
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
            /* 空会话 — 居中欢迎页 + 居中输入框 */
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

                {/* 居中输入框（带工具标签） */}
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

                {/* 三个工具（核心卖点） */}
                <div style={{ marginTop: 32 }}>
                  <div style={{
                    textAlign: 'center', fontSize: 13, color: 'var(--text-tertiary)',
                    marginBottom: 14, fontWeight: 500, letterSpacing: 0.3,
                  }}>
                    ✦ 先选一个工具，让小星为你做更精准的事
                  </div>
                  <ToolSelector value={selectedTool} onChange={setSelectedTool} />
                </div>

                {/* 快捷建议 */}
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

        {/* 输入区域：仅在有消息时显示底部输入框（空状态时用居中输入框，互斥）*/}
        {currentSessionId && hasMessages && (
          <div
            style={{
              padding: isMobile ? '8px 12px 12px' : '14px 24px 18px',
              background: 'transparent',  // 让网格底纹透过来，跟聊天区统一
              borderTop: '1px solid var(--border-light)',
              flexShrink: 0,
            }}
          >
            <div style={{ maxWidth: 768, margin: '0 auto' }}>
              {/* ── 工具条（始终可见，切换工具不消失）── */}
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

              {/* 输入框 —— 透明背景，让网格底纹透过来；只保留边框做视觉边界 */}
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
    </div>
  )
}
