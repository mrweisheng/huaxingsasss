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
  DollarOutlined,
  BarChartOutlined,
  FileSearchOutlined,
  PictureOutlined,
  CreditCardOutlined,
  PlusOutlined,
} from '@ant-design/icons'
import StarLogoWelcome from '@/components/StarLogoWelcome'
import { useAgentStore } from '@/store/useAgentStore'
import type { ChatMessage, AttachmentItem } from '@/types/agent'
import { MarkdownRenderer, ToolCallBlock, WittyLoadingText } from '@/components/AgentChatShared'
import { compressImage } from '@/utils/imageCompress'
import { useAgentFile } from '@/hooks/useAgentFile'
import { usePendingFiles, type PendingFile } from '@/hooks/usePendingFiles'
import { useDropZone } from '@/hooks/useDropZone'

const { Text } = Typography

/* ── 工具标签映射 ── */
const TOOL_LABELS: Record<string, string> = {
  search_customers: '搜索客户',
  search_contracts: '搜索合同',
  get_contract_detail: '合同详情',
  get_customer_contracts: '客户合同',
  query_payments: '查询付款',
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

/* ── 单张历史图片：当轮本地用 preview，历史会话从 useAgentFile 拉 Blob URL ── */
const AttachmentImage = memo(function AttachmentImage({
  att, single,
}: {
  att: AttachmentItem
  single: boolean
}) {
  // 当轮本地上传带 preview（base64 字符串），直接用
  // 历史回看没 preview → 按 fileId 拉远端
  const { url: fetched, loading, error } = useAgentFile(att.preview ? null : att.fileId)
  const src = att.preview || fetched

  const style: React.CSSProperties = {
    width: '100%',
    maxHeight: single ? 280 : 160,
    objectFit: 'cover',
    borderRadius: 10,
    display: 'block',
    cursor: 'pointer',
  }

  if (src) {
    return <img src={src} alt={att.fileName || '图片'} style={style} />
  }
  if (loading) {
    return (
      <div style={{ ...style, background: 'rgba(255,255,255,0.12)', display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: 100 }}>
        <Spin size="small" />
      </div>
    )
  }
  // error 或 fileId 缺失：占位提示
  return (
    <div style={{ ...style, background: 'rgba(255,255,255,0.12)', color: 'rgba(255,255,255,0.7)', fontSize: 12, display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: 100, padding: 12, textAlign: 'center' }}>
      {error === 'gone' ? '附件已被清理' : '附件已失效'}
    </div>
  )
})

/* ── 单个非图片附件卡片：点击下载（历史回看可用，当轮上传也可用）── */
const AttachmentFile = memo(function AttachmentFile({ att }: { att: AttachmentItem }) {
  const { url, loading, error } = useAgentFile(att.fileId)
  const cfg = FILE_TYPE_META[att.fileType] || FILE_TYPE_META.default

  const inner = (
    <div
      style={{
        display: 'flex', alignItems: 'center', gap: 10,
        background: 'rgba(255,255,255,0.12)',
        border: '1px solid rgba(255,255,255,0.15)',
        borderRadius: 10,
        padding: '8px 10px',
        minWidth: 200,
        cursor: url ? 'pointer' : 'default',
        opacity: error ? 0.6 : 1,
        transition: 'background 0.15s',
      }}
      title={error === 'gone' ? '附件已被清理' : error ? '附件已失效' : att.fileName}
    >
      <div style={{
        width: 40, height: 48, borderRadius: 6,
        background: cfg.bg,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        color: cfg.fg, fontSize: 20, flexShrink: 0,
        boxShadow: '0 1px 3px rgba(0,0,0,0.10)',
      }}>
        {loading ? <Spin size="small" /> : cfg.icon}
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
          {error === 'gone' ? '附件已被清理'
            : error ? '附件已失效'
            : (att.fileName || '').toLowerCase().split('.').pop()?.toUpperCase() || '文件'}
        </span>
      </div>
    </div>
  )

  if (url) {
    return (
      <a
        href={url}
        download={att.fileName || att.fileId}
        target="_blank"
        rel="noopener noreferrer"
        style={{ textDecoration: 'none' }}
      >
        {inner}
      </a>
    )
  }
  return inner
})

const MessageBubble = memo(function MessageBubble({ msg, streaming }: {
  msg: ChatMessage
  streaming?: boolean
}) {
  if (msg.role === 'user') {
    const attachments = msg.attachments || []
    const hasText = !!msg.content
    const hasAttachments = attachments.length > 0
    // 图片：当轮 preview 或历史 fileId 都算图片（不再硬性要求 preview）
    const imageAttachments = attachments.filter(a => a.fileType === 'image')
    const fileAttachments = attachments.filter(a => a.fileType !== 'image')

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
                    <AttachmentImage key={att.fileId || i} att={att} single={imageAttachments.length === 1} />
                  ))}
                </div>
              )}

              {fileAttachments.length > 0 && (
                <div style={{ padding: '8px 10px', display: 'flex', flexDirection: 'column', gap: 6 }}>
                  {fileAttachments.map((att, i) => (
                    <AttachmentFile key={att.fileId || i} att={att} />
                  ))}
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
    // 有 tool_call 但最后一个还没 result → 工具正在执行
    const hasRunningTool = hasToolCalls && msg.toolCalls!.some(tc => !tc.result)
    // 显示俏皮动效：思考中 或 工具执行中（且正在 streaming）
    const isThinking = !hasContent && hasThoughts && !!runningStep
    const isToolRunning = streaming && hasRunningTool

    // 俏皮动效用哪个 message：优先用 thinking 步骤文案，否则根据工具名生成
    const wittyMessage = runningStep?.message
      || (hasRunningTool
        ? `正在执行${TOOL_LABELS[msg.toolCalls!.find(tc => !tc.result)?.name || ''] || '操作'}...`
        : '思考中...')

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
          {(isThinking || isToolRunning) && (
            <div
              key={runningStep?.id || 'tool-running'}
              style={{ marginBottom: 8 }}
            >
              <WittyLoadingText message={wittyMessage} />
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
          ) : !isThinking && !isToolRunning && (
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

/* ── 能力卡片 ── */
const CAPABILITIES = [
  {
    key: 'contract_entry' as const,
    icon: <FileTextOutlined />,
    title: '合同录入',
    desc: '上传合同自动解析',
    bg: '#e8edf5', fg: '#1e3a5f',
  },
  {
    key: 'receipt_income' as const,
    icon: <CreditCardOutlined />,
    title: '收入登记',
    desc: '凭证上传智能匹配',
    bg: '#edfaf8', fg: '#0d9488',
  },
  {
    key: 'receipt_expense' as const,
    icon: <DollarOutlined />,
    title: '支出管理',
    desc: '支出记录凭证归档',
    bg: '#fef2f2', fg: '#dc2626',
  },
]

/* ── 三个工具（核心卖点）── */
const TOOLS = [
  { key: 'contract_entry' as const, icon: <FileTextOutlined />, label: '录合同', color: '#1e3a5f' },
  { key: 'receipt_income' as const, icon: <CreditCardOutlined />, label: '录收入', color: '#0d9488' },
  { key: 'receipt_expense' as const, icon: <DollarOutlined />, label: '录支出', color: '#dc2626' },
]

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
  value, onChange, onSend, onFileSelect, isStreaming, onStop, pendingFiles, onRemoveFile, hasUploading, toolTag,
}: {
  value: string
  onChange: (v: string) => void
  onSend: () => void
  onFileSelect: (f: File) => boolean
  isStreaming: boolean
  onStop: () => void
  pendingFiles: PendingFile[]
  onRemoveFile: (i: number) => void
  hasUploading: boolean
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
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 8, alignItems: 'center' }}>
          {pendingFiles.map((pf, i) => {
            const f = pf.file
            const name = f.name.toLowerCase()
            const isHeic = name.endsWith('.heic') || name.endsWith('.heif')
            if (isHeic) {
              const thumb = pf.status === 'uploading' ? (
                <span style={{ height: 40, width: 40, borderRadius: 8, background: 'var(--bg-subtle)', border: '1px solid var(--border-default)', display: 'inline-flex', alignItems: 'center', justifyContent: 'center' }}>
                  <Spin size="small" style={{ color: 'var(--brand-gold)' }} />
                </span>
              ) : pf.status === 'error' ? (
                <span style={{ height: 40, width: 40, borderRadius: 8, background: 'var(--bg-subtle)', border: '1px solid var(--border-default)', display: 'inline-flex', alignItems: 'center', justifyContent: 'center' }}>
                  <PictureOutlined style={{ fontSize: 18, color: 'var(--color-danger)' }} />
                </span>
              ) : pf.uploaded?.thumbnailUrl ? (
                <img src={pf.uploaded.thumbnailUrl} alt={f.name} style={{ height: 40, width: 40, borderRadius: 8, objectFit: 'cover', border: '1px solid var(--border-default)' }} />
              ) : (
                <span style={{ height: 40, width: 40, borderRadius: 8, background: 'var(--bg-subtle)', border: '1px solid var(--border-default)', display: 'inline-flex', alignItems: 'center', justifyContent: 'center' }}>
                  <PictureOutlined style={{ fontSize: 18, color: 'var(--brand-gold)' }} />
                </span>
              )
              return (
                <span key={pf.id} style={{ position: 'relative', display: 'inline-block', cursor: 'pointer' }} onClick={() => onRemoveFile(i)}>
                  {thumb}
                  <span style={{ position: 'absolute', top: -6, right: -6, background: 'var(--color-danger)', color: '#fff', borderRadius: '50%', width: 16, height: 16, fontSize: 10, lineHeight: '16px', textAlign: 'center', boxShadow: '0 2px 4px rgba(220,38,38,0.3)' }}>×</span>
                </span>
              )
            }
            if (f.type.startsWith('image/')) {
              return (
                <span key={pf.id} style={{ position: 'relative', display: 'inline-block', cursor: 'pointer' }} onClick={() => onRemoveFile(i)}>
                  <img src={URL.createObjectURL(f)} alt={f.name} style={{ height: 40, width: 40, borderRadius: 8, objectFit: 'cover', border: '1px solid var(--border-default)' }} />
                  <span style={{ position: 'absolute', top: -6, right: -6, background: 'var(--color-danger)', color: '#fff', borderRadius: '50%', width: 16, height: 16, fontSize: 10, lineHeight: '16px', textAlign: 'center', boxShadow: '0 2px 4px rgba(220,38,38,0.3)' }}>×</span>
                </span>
              )
            }
            const icon = name.endsWith('.pdf') ? <FilePdfOutlined style={{ color: '#dc2626' }} />
              : name.endsWith('.docx') || name.endsWith('.doc') ? <FileWordOutlined style={{ color: 'var(--brand-primary)' }} />
              : name.endsWith('.xlsx') || name.endsWith('.xls') ? <FileExcelOutlined style={{ color: 'var(--color-success)' }} />
              : <FileTextOutlined style={{ color: 'var(--color-warning)' }} />
            return (
              <Tag key={pf.id} closable onClose={() => onRemoveFile(i)} style={{ margin: 0, fontSize: 12, borderRadius: 6 }}>
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
        placeholder={pendingFiles.length > 0 ? '上传文件后可直接发送，也可补充说明...' : '问点什么？试试："查询最近付款" 或上传一份合同…'}
        autoSize={{ minRows: 2, maxRows: 6 }}
        disabled={isStreaming}
        variant="borderless"
        style={{ fontSize: 16, lineHeight: '26px', padding: '4px 0', resize: 'none', color: 'var(--text-primary)' }}
      />

      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: 8 }}>
        <Upload beforeUpload={onFileSelect} showUploadList={false} accept="image/*,.heic,.heif,.pdf,.doc,.docx,.xls,.xlsx,.txt,.csv">
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
            disabled={hasUploading || (!value.trim() && pendingFiles.length === 0)}
            style={{ borderRadius: 8, height: 36, padding: '0 18px', fontSize: 14 }}
          >
            发送
          </Button>
        )}
      </div>
    </div>
  )
})

/* ── 欢迎内容（空状态共享）── */
const WelcomeContent = memo(function WelcomeContent({
  inputText, onChange, onSend, onFileSelect, isStreaming, onStop,
  pendingFiles, onRemoveFile, hasUploading, selectedTool, setSelectedTool,
}: {
  inputText: string
  onChange: (v: string) => void
  onSend: () => void
  onFileSelect: (f: File) => boolean
  isStreaming: boolean
  onStop: () => void
  pendingFiles: PendingFile[]
  onRemoveFile: (i: number) => void
  hasUploading: boolean
  selectedTool: 'contract_entry' | 'receipt_income' | 'receipt_expense' | null
  setSelectedTool: (v: 'contract_entry' | 'receipt_income' | 'receipt_expense' | null) => void
}) {
  return (
    <div className="chat-grid-bg" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', padding: '24px' }}>
      <div className="welcome-stagger" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', width: '100%', maxWidth: 760 }}>
        {/* 小星助手主 logo — Welcome 专享版（动效版） */}
        <div
          className="star-logo-halo"
          style={{
            width: 180, height: 180,
            marginBottom: 14,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}
        >
          <StarLogoWelcome size={180} />
        </div>
        <Text style={{ fontSize: 26, fontWeight: 700, color: 'var(--text-primary)', fontFamily: 'var(--font-display)', marginBottom: 4, letterSpacing: 0.3 }}>
          你好，我是小星
        </Text>
        <Text style={{ fontSize: 14, color: 'var(--text-tertiary)', marginBottom: 20, textAlign: 'center' }}>
          选择一种能力，或直接输入你的问题
        </Text>

        {/* ── 能力卡片 ── */}
        <div style={{
          display: 'flex', gap: 10, marginBottom: 20,
          flexWrap: 'wrap', justifyContent: 'center',
          maxWidth: 520,
        }}>
          {CAPABILITIES.map((cap) => {
            const isActive = cap.key !== null && selectedTool === cap.key
            return (
              <div
                key={cap.title}
                onClick={() => {
                  if (cap.key !== null) setSelectedTool(isActive ? null : cap.key)
                }}
                style={{
                  display: 'flex', alignItems: 'center', gap: 10,
                  padding: '10px 16px',
                  background: isActive ? cap.bg : 'var(--bg-surface)',
                  border: isActive ? `1.5px solid ${cap.fg}` : '1px solid var(--border-light)',
                  borderRadius: 12,
                  cursor: 'pointer',
                  transition: 'all 0.2s cubic-bezier(0.4, 0, 0.2, 1)',
                  boxShadow: isActive ? `0 4px 12px ${cap.fg}18` : '0 1px 3px rgba(0,0,0,0.03)',
                }}
                onMouseEnter={(e) => {
                  if (!isActive) {
                    e.currentTarget.style.borderColor = cap.fg
                    e.currentTarget.style.boxShadow = `0 2px 8px ${cap.fg}10`
                  }
                }}
                onMouseLeave={(e) => {
                  if (!isActive) {
                    e.currentTarget.style.borderColor = 'var(--border-light)'
                    e.currentTarget.style.boxShadow = '0 1px 3px rgba(0,0,0,0.03)'
                  }
                }}
              >
                <div style={{
                  width: 32, height: 32, borderRadius: 8,
                  background: isActive ? 'rgba(255,255,255,0.7)' : cap.bg,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  color: cap.fg, fontSize: 15, flexShrink: 0,
                  transition: 'all 0.2s',
                }}>
                  {cap.icon}
                </div>
                <div>
                  <div style={{ fontSize: 13, fontWeight: 600, color: isActive ? cap.fg : 'var(--text-primary)', transition: 'color 0.2s' }}>
                    {cap.title}
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--text-tertiary)', marginTop: 1 }}>
                    {cap.desc}
                  </div>
                </div>
              </div>
            )
          })}
        </div>

        {/* ── 居中输入框 ── */}
        <CenterInputBox
          value={inputText}
          onChange={onChange}
          onSend={onSend}
          onFileSelect={onFileSelect}
          isStreaming={isStreaming}
          onStop={onStop}
          pendingFiles={pendingFiles}
          onRemoveFile={onRemoveFile}
          hasUploading={hasUploading}
          toolTag={selectedTool ? (
            <ToolTag value={selectedTool} onRemove={() => setSelectedTool(null)} />
          ) : null}
        />

        {/* ── 快捷建议 ── */}
        <div style={{
          display: 'flex', flexWrap: 'wrap', gap: 10, justifyContent: 'center',
          marginTop: 20, maxWidth: 580,
        }}>
          {suggestions.map((s, i) => (
            <div
              key={i}
              className="quick-pill"
              onClick={() => onChange(s.text)}
              style={{
                display: 'inline-flex', alignItems: 'center', gap: 8,
                padding: '8px 16px',
                background: 'var(--bg-surface)',
                border: '1px solid var(--border-light)',
                borderRadius: 20,
                cursor: 'pointer', fontSize: 13, color: 'var(--text-secondary)',
                boxShadow: '0 1px 3px rgba(0,0,0,0.03)',
              }}
            >
              <span
                className="quick-pill-icon"
                style={{
                  display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                  width: 22, height: 22, borderRadius: 6,
                  background: 'var(--brand-gold-bg)', color: 'var(--brand-gold)',
                  fontSize: 12, transition: 'all 0.2s',
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
  )
})

/* ── 主组件 ── */
export default function AgentChat() {
  const [inputText, setInputText] = useState('')
  const { pendingFiles, addFiles, removeFile, clear: clearPending, hasUploading, toSendPayload } = usePendingFiles()
  const messageListRef = useRef<HTMLDivElement>(null)

  const screens = Grid.useBreakpoint()
  const isMobile = !(screens.md ?? true)

  const {
    currentSessionId,
    sessions,
    messages,
    isStreaming,
    error,
    sendMessage,
    stopGeneration,
    clearError,
    selectedTool,
    setSelectedTool,
    resetChat,
  } = useAgentStore()

  // 拖拽上传（通用 hook，支持悬停高亮 + 跨子元素稳定计数）
  const { isOver: isDropOver, dropHandlers } = useDropZone({
    onDrop: (files) => addFiles(files),
    accept: ['image/*', '.heic', '.heif', '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.txt', '.csv'],
    disabled: isStreaming,
  })

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

  const TOOL_DEFAULT_TEXT: Record<string, string> = {
    contract_entry: '录入合同',
    receipt_income: '录入收入',
    receipt_expense: '录入支出',
  }

  const handleSend = useCallback(async () => {
    if (hasUploading) {
      message.warning('文件上传中，请稍候…')
      return
    }
    const text = inputText.trim()
    if (!text && pendingFiles.length === 0) {
      message.warning('请输入内容或上传文件')
      return
    }
    // 有文件无文字时：优先用工具标签的默认文案，否则用"录入了文件"
    const finalText = text || TOOL_DEFAULT_TEXT[selectedTool || ''] || '录入了文件'
    const payload = pendingFiles.length > 0 ? toSendPayload() : undefined
    setInputText('')
    clearPending()
    await sendMessage(finalText, payload)
  }, [inputText, pendingFiles, sendMessage, selectedTool, hasUploading, toSendPayload, clearPending])

  // 新建会话：只重置本地状态，不创建后端 session（延迟到发第一条消息时）
  const handleNewChat = useCallback(() => {
    if (isStreaming) {
      message.warning('正在生成中，请先停止当前对话')
      return
    }
    resetChat()
  }, [resetChat, isStreaming])

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend() }
    },
    [handleSend],
  )

  const handleFileSelect = useCallback((file: File) => {
    const isImage = file.type.startsWith('image/')

    // 文件数量约束：图片最多 2 张，非图片（合同/文档）最多 1 份
    const imageCount = pendingFiles.filter(pf => pf.file.type.startsWith('image/')).length
    const nonImageCount = pendingFiles.length - imageCount

    if (isImage) {
      if (imageCount >= 2) {
        message.warning('图片最多携带 2 张')
        return false
      }
    } else {
      if (nonImageCount >= 1) {
        message.warning('合同/文档类一次只能携带一份')
        return false
      }
    }

    // 通过约束，异步压缩后加入待发列表（压缩 promise 让 antd Upload 不立刻上传）
    compressImage(file).then((compressed) => {
      addFiles([compressed])
    })
    return false // 阻止 antd Upload 默认上传
  }, [pendingFiles, addFiles])

  const removePendingFile = useCallback((index: number) => {
    removeFile(index)
  }, [removeFile])

  const hasMessages = messages.some((m) => m.role === 'user' || m.role === 'assistant')

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - 56px)', position: 'relative' }}>
      {/* ══════ 悬浮"新对话"主按钮（钉在视口左上角，不被消息滚动带走）══════ */}
      <div
        onClick={handleNewChat}
        title={sessions.length > 0 ? '开启新对话（不会删除历史）' : '开始新对话'}
        style={{
          position: 'absolute',
          top: isMobile ? 12 : 16,
          left: isMobile ? 12 : 20,
          zIndex: 10,
          display: 'inline-flex',
          alignItems: 'center',
          gap: 6,
          height: isMobile ? 32 : 36,
          padding: isMobile ? '0 12px' : '0 16px',
          background: 'linear-gradient(135deg, var(--brand-primary) 0%, var(--brand-primary-light) 100%)',
          color: '#fff',
          border: 'none',
          borderRadius: 20,
          fontSize: 13,
          fontWeight: 600,
          cursor: isStreaming ? 'not-allowed' : 'pointer',
          opacity: isStreaming ? 0.55 : 1,
          boxShadow: '0 2px 8px rgba(30, 58, 95, 0.22), 0 0 0 1px rgba(255,255,255,0.08) inset',
          transition: 'transform 0.18s, box-shadow 0.18s, opacity 0.18s',
          userSelect: 'none',
        }}
        onMouseEnter={(e) => {
          if (isStreaming) return
          e.currentTarget.style.transform = 'translateY(-1px)'
          e.currentTarget.style.boxShadow = '0 6px 16px rgba(30, 58, 95, 0.28), 0 0 0 1px rgba(255,255,255,0.12) inset'
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.transform = 'translateY(0)'
          e.currentTarget.style.boxShadow = '0 2px 8px rgba(30, 58, 95, 0.22), 0 0 0 1px rgba(255,255,255,0.08) inset'
        }}
        onMouseDown={(e) => {
          if (!isStreaming) e.currentTarget.style.transform = 'translateY(0) scale(0.97)'
        }}
        onMouseUp={(e) => {
          if (!isStreaming) e.currentTarget.style.transform = 'translateY(-1px)'
        }}
      >
        <PlusOutlined style={{ fontSize: 13, fontWeight: 700 }} />
        <span>新对话</span>
      </div>

      <div
        ref={messageListRef}
        className={hasMessages ? 'chat-grid-bg' : ''}
        style={{
          flex: 1,
          overflow: 'auto',
          padding: isMobile ? '56px 14px 12px' : '64px 24px 20px',
          background: hasMessages ? undefined : 'linear-gradient(180deg, var(--bg-page) 0%, #f0f2f5 100%)',
          transition: 'outline 0.15s, background 0.15s',
          outline: isDropOver ? '2px dashed var(--type-color)' : 'none',
          outlineOffset: isDropOver ? -8 : 0,
          backgroundBlendMode: isDropOver ? 'soft-light' : undefined,
        }}
        {...dropHandlers}
      >
        {(!currentSessionId || !hasMessages) ? (
          <WelcomeContent
            inputText={inputText}
            onChange={setInputText}
            onSend={handleSend}
            onFileSelect={handleFileSelect}
            isStreaming={isStreaming}
            onStop={stopGeneration}
            pendingFiles={pendingFiles}
            onRemoveFile={removePendingFile}
            selectedTool={selectedTool}
            setSelectedTool={setSelectedTool}
            hasUploading={hasUploading}
          />
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
                {pendingFiles.map((pf, i) => {
                  const f = pf.file
                  const name = f.name.toLowerCase()
                  const isHeic = name.endsWith('.heic') || name.endsWith('.heif')
                  // HEIC 文件在 Chrome 中无法渲染：根据上传状态显示不同占位
                  if (isHeic) {
                    const inner = pf.status === 'uploading' ? (
                      <Spin size="small" style={{ color: 'var(--brand-gold)' }} />
                    ) : pf.status === 'error' ? (
                      <PictureOutlined style={{ fontSize: 18, color: 'var(--color-danger)' }} />
                    ) : pf.uploaded?.thumbnailUrl ? (
                      // 上传完成：用后端返回的 JPEG 缩略图（浏览器可渲染）
                      <img src={pf.uploaded.thumbnailUrl} alt={f.name}
                        style={{ height: 40, width: 40, borderRadius: 8, objectFit: 'cover', border: '1px solid var(--border-default)' }}
                      />
                    ) : (
                      <PictureOutlined style={{ fontSize: 18, color: 'var(--brand-gold)' }} />
                    )
                    return (
                      <span
                        key={pf.id} style={{ position: 'relative', display: 'inline-block', cursor: 'pointer' }}
                        onClick={() => removePendingFile(i)}
                      >
                        <span style={{
                          height: 40, width: 40, borderRadius: 8,
                          background: 'var(--bg-subtle)',
                          border: '1px solid var(--border-default)',
                          display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                          verticalAlign: 'top',
                        }}>
                          {inner}
                        </span>
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
                  if (f.type.startsWith('image/')) {
                    return (
                      <span
                        key={pf.id} style={{ position: 'relative', display: 'inline-block', cursor: 'pointer' }}
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
                    <Tag key={pf.id} closable onClose={() => removePendingFile(i)} color="default" style={{ margin: 0, fontSize: 12, borderRadius: 4 }}>
                      {icon} {f.name.length > 20 ? f.name.slice(0, 18) + '…' : f.name}
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
                        beforeUpload={handleFileSelect}
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
                accept="image/*,.heic,.heif,.pdf,.doc,.docx,.xls,.xlsx,.txt,.csv"
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
                placeholder={pendingFiles.length > 0 ? '上传文件后可直接发送，也可补充说明...' : '输入你的问题...'}
                autoSize={{ minRows: 1, maxRows: 5 }}
                disabled={isStreaming}
                variant="borderless"
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
                  disabled={hasUploading || (!inputText.trim() && pendingFiles.length === 0)}
                  style={{ borderRadius: 8, height: 40, padding: '0 20px', flexShrink: 0, fontSize: 14 }}
                >
                  {hasUploading ? '上传中…' : '发送'}
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
  )
}
