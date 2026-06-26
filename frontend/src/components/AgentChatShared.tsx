import { useState, useEffect, memo, useRef } from 'react'
import { Spin, Button } from 'antd'
import {
  CheckCircleOutlined,
  LoadingOutlined,
  DownOutlined,
  RightOutlined,
  ToolOutlined,
  FileTextOutlined,
  FileSearchOutlined,
  UserAddOutlined,
  CreditCardOutlined,
  CalendarOutlined,
  BarChartOutlined,
  PictureOutlined,
  FunctionOutlined,
} from '@ant-design/icons'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { ThoughtStep, ToolCall, QuickReplyAction } from '@/types/agent'

/* ═══════════════════════════════════════════════════════════
   工具 → 业务图标 映射（让 ToolCallBlock 更可读）
   ═══════════════════════════════════════════════════════════ */
const TOOL_ICONS: Record<string, JSX.Element> = {
  search_customers: <UserAddOutlined style={{ color: '#1e3a5f' }} />,
  search_contracts: <FileSearchOutlined style={{ color: '#1e3a5f' }} />,
  get_contract_detail: <FileTextOutlined style={{ color: '#1e3a5f' }} />,
  get_customer_contracts: <FileTextOutlined style={{ color: '#1e3a5f' }} />,
  query_payments: <CreditCardOutlined style={{ color: '#1e3a5f' }} />,
  get_payment_summary: <BarChartOutlined style={{ color: '#1e3a5f' }} />,
  get_expiring_contracts: <CalendarOutlined style={{ color: '#d97706' }} />,
  analyze_image: <PictureOutlined style={{ color: '#1e3a5f' }} />,
  create_customer: <UserAddOutlined style={{ color: '#0d9488' }} />,
  create_contract: <FileTextOutlined style={{ color: '#0d9488' }} />,
}
const DEFAULT_TOOL_ICON = <FunctionOutlined style={{ color: '#1e3a5f' }} />

/* ═══════════════════════════════════════════════════════════
   俏皮文案库（场景感知 + 随机抽取）
   设计思路：thought.message 是后端给的中性描述（如"正在识别合同..."），
   我们根据关键词匹配场景，给出更有人情味的副标题。
   ═══════════════════════════════════════════════════════════ */

const WITTY_PHRASES = {
  contract_entry: {
    // 关键词：识别、合同、读取、OCR、解析
    keywords: ['合同', '识别', 'OCR', '读取', '解析', '提取', '字段'],
    phrases: [
      '正在细读这份合同，条款有点多，给我点时间 📄',
      '这份合同金额有点大，我得慎重一点 💰',
      'OCR 启动中，合同里的每一个字都别想跑 ✍️',
      '翻合同中...遇到手写体我得瞪大眼睛看 🔍',
      '合同有点厚，让我一页一页仔细看 📖',
      '正在提取关键信息，客户名、金额、日期一个不能少 🎯',
      '扫描中...这份合同的每个角落我都要扫到 🔎',
      '识别进行中，繁体字也难不倒我 💪',
    ],
  },
  contract_confirm: {
    // 关键词：确认、字段、待
    keywords: ['确认', '待您', '字段已'],
    phrases: [
      '一切就绪，要不要确认一下我提取的信息？✨',
      '我整理好了，您过目一下，心里更有底 👀',
      '材料已备齐，等您点头就入库 📦',
      '信息已核对完毕，就等您拍板了 🤝',
    ],
  },
  receipt_entry: {
    // 关键词：凭证、发票、票据、收据
    keywords: ['凭证', '发票', '票据', '收据', '看图'],
    phrases: [
      '看图识账中，这笔是收是支？🤔',
      '正在核对发票真伪，税务上可不能马虎 🧾',
      '在数钱了在数钱了 💵',
      '凭证上的数字有点小，让我放大看看 🔍',
      '正在识别收款方和金额，财务的事儿得仔细 💼',
    ],
  },
  search_query: {
    // 关键词：搜索、查询、查找、检索
    keywords: ['搜索', '查询', '查找', '检索', '翻', '查'],
    phrases: [
      '翻一翻数据库，给您找出来 🗂️',
      '在查了在查了，马上就好 ⏳',
      '这事儿我有印象，让我去翻翻档案 📚',
      '数据库有点大，稍等我翻一下 🔍',
      '正在检索相关记录，马上就有了 📋',
    ],
  },
  payment_summary: {
    // 关键词：汇总、统计、合计
    keywords: ['汇总', '统计', '合计', '总数'],
    phrases: [
      '数字在跳，让我加一下 ➕',
      '财务小算盘已经拨起来 🧮',
      '正在汇总收支数据，账本马上就好 📊',
    ],
  },
  file_processing: {
    // 关键词：文件、上传、PDF、图片
    keywords: ['文件', '上传', 'PDF', '图片', '渲染'],
    phrases: [
      '文件有点大，正在处理中 📁',
      'PDF 正在渲染，页数有点多 📄',
      '图片压缩中，马上就好 🖼️',
      '文件读取中，稍等一下 📎',
    ],
  },
  default: {
    keywords: [],
    phrases: [
      '思考中，让我捋一捋 🤔',
      '在想了在想了，别催我嘛 🧠',
      '脑子转啊转，灵感快来了 💡',
      '正在组织语言，马上回复您 ✍️',
      '让我想想怎么回答比较好 🤔',
    ],
  },
} as const

type SceneKey = keyof typeof WITTY_PHRASES

function detectScene(message: string): SceneKey {
  for (const [scene, def] of Object.entries(WITTY_PHRASES) as [SceneKey, typeof WITTY_PHRASES[SceneKey]][]) {
    if (def.keywords.some((kw) => message.includes(kw))) return scene
  }
  return 'default'
}

function pickRandom<T>(arr: readonly T[]): T {
  return arr[Math.floor(Math.random() * arr.length)]
}

/* ── Markdown 组件通用样式（含完整表格支持） ── */
const MARKDOWN_COMPONENTS = {
  table: ({ children }: any) => (
    <div style={{ overflowX: 'auto', margin: '8px 0' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>{children}</table>
    </div>
  ),
  thead: ({ children }: any) => <thead style={{ background: 'var(--bg-subtle)' }}>{children}</thead>,
  th: ({ children }: any) => (
    <th style={{ border: '1px solid var(--border-light)', padding: '6px 10px', textAlign: 'left', fontWeight: 600, color: 'var(--text-primary)' }}>
      {children}
    </th>
  ),
  td: ({ children }: any) => (
    <td style={{ border: '1px solid var(--border-light)', padding: '6px 10px', color: 'var(--text-secondary)' }}>
      {children}
    </td>
  ),
  tr: ({ children }: any) => (
    <tr style={{ borderBottom: '1px solid var(--border-light)' }}>{children}</tr>
  ),
  strong: ({ children }: any) => <strong style={{ color: 'var(--brand-primary)' }}>{children}</strong>,
  p: ({ children }: any) => <p style={{ margin: '4px 0', lineHeight: 1.7 }}>{children}</p>,
  ol: ({ children }: any) => <ol style={{ margin: '4px 0', paddingLeft: 20 }}>{children}</ol>,
  ul: ({ children }: any) => <ul style={{ margin: '4px 0', paddingLeft: 20 }}>{children}</ul>,
  li: ({ children }: any) => <li style={{ margin: '2px 0' }}>{children}</li>,
  code: ({ inline, children, ...props }: any) =>
    inline ? (
      <code style={{ background: 'var(--bg-hover)', padding: '2px 6px', borderRadius: 4, fontSize: 12, color: '#d63384' }} {...props}>
        {children}
      </code>
    ) : (
      <pre style={{ background: '#1e293b', color: '#e2e8f0', padding: 14, borderRadius: 8, overflow: 'auto', fontSize: 12, margin: '8px 0', lineHeight: 1.5 }}>
        <code {...props}>{children}</code>
      </pre>
    ),
  blockquote: ({ children }: any) => (
    <blockquote style={{ borderLeft: '3px solid var(--brand-primary)', margin: '8px 0', padding: '4px 12px', color: 'var(--text-secondary)' }}>
      {children}
    </blockquote>
  ),
}

/* ── Markdown 渲染器（共享） ── */
export function MarkdownRenderer({ content, streaming, className }: {
  content: string
  streaming?: boolean
  className?: string
}) {
  if (streaming) {
    // 流式阶段用纯文本，避免每次 chunk 重解析 Markdown（尤其表格代价高）
    // 末尾加打字光标动画，给用户"还在写"的视觉反馈
    return (
      <div className={className} style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word', lineHeight: 1.7, fontSize: 14 }}>
        {content}
        <span
          className="typing-cursor"
          style={{
            display: 'inline-block',
            width: 2,
            height: '1em',
            background: 'var(--brand-primary)',
            marginLeft: 1,
            verticalAlign: 'text-bottom',
            animation: 'cursorBlink 0.8s steps(1) infinite',
          }}
        />
      </div>
    )
  }
  return (
    <div className={className}>
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={MARKDOWN_COMPONENTS}>
        {content}
      </ReactMarkdown>
    </div>
  )
}

/* ═══════════════════════════════════════════════════════════
   快捷回复按钮（present_quick_replies 工具触发）
   行为：点击后发送 send_text，按钮立即消失。
   ═══════════════════════════════════════════════════════════ */
export function QuickReplyButtons({ actions, disabled, onClick }: {
  actions: QuickReplyAction[]
  disabled?: boolean
  onClick: (action: QuickReplyAction) => void
}) {
  if (!actions?.length) return null

  const confirmAction = actions.find(action => action.style === 'primary')
  const cancelAction = actions.find(action => action.style === 'danger')
  const isConfirmation = actions.length === 2 && !!confirmAction && !!cancelAction

  if (isConfirmation) {
    return (
      <div className="quick-reply-panel">
        <div className="quick-reply-panel-head">
          <span className="quick-reply-panel-kicker">需要您确认</span>
          <span className="quick-reply-panel-title">请选择下一步</span>
          <span className="quick-reply-panel-hint">要修改或补充？直接在下方输入框说明后发送。</span>
        </div>
        <div className="quick-reply-panel-actions">
          <Button
            type="primary"
            disabled={disabled}
            onClick={() => onClick(confirmAction)}
            className="quick-reply-confirm-btn"
          >
            {confirmAction.label}
          </Button>
          <Button
            disabled={disabled}
            onClick={() => onClick(cancelAction)}
            className="quick-reply-cancel-btn"
          >
            {cancelAction.label}
          </Button>
        </div>
      </div>
    )
  }

  return (
    <div className="quick-reply-chip-row">
      {actions.map((action, i) => (
        <Button
          key={i}
          type={action.style === 'primary' ? 'primary' : 'default'}
          danger={action.style === 'danger'}
          disabled={disabled}
          onClick={() => onClick(action)}
          className="quick-reply-chip"
          style={{ animationDelay: `${i * 0.05}s` }}
        >
          {action.label}
        </Button>
      ))}
    </div>
  )
}

/* ═══════════════════════════════════════════════════════════
   俏皮 Loading 文字
   行为：传入中性 message，自动匹配场景、随机抽一句俏皮副标题，
   并用 shimmer + bounce 微动效呈现。
   ═══════════════════════════════════════════════════════════ */
export const WittyLoadingText = memo(function WittyLoadingText({ message }: { message: string }) {
  const scene = detectScene(message)
  const phrase = pickRandom(WITTY_PHRASES[scene].phrases)
  // 关键：用 message 作为 seed，相同 message 抽到同一句（避免一直跳）
  const [stablePhrase, setStablePhrase] = useState(phrase)
  useEffect(() => {
    setStablePhrase(phrase)
    // 仅在 message 变化时重新抽
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [message])

  return (
    <div className="witty-loading" style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
      <span
        className="witty-bounce-icon"
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          justifyContent: 'center',
          width: 24, height: 24, borderRadius: 8,
          background: 'linear-gradient(135deg, var(--brand-gold), #e8b84b)',
          color: '#0f1a2e',
          fontSize: 13, fontWeight: 700,
          boxShadow: '0 2px 8px rgba(201,149,43,0.25)',
        }}
      >
        ✨
      </span>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 2, minWidth: 0, flex: 1 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span
            className="shimmer-text"
            style={{
              fontSize: 13, fontWeight: 500, color: 'var(--text-primary)',
            }}
          >
            {message}
          </span>
          {/* ── 心跳：三个点循环跳动（"还在干活"）── */}
          <span className="typing-dots" style={{ display: 'inline-flex', gap: 2, marginLeft: 2, flexShrink: 0 }}>
            <span style={{
              width: 4, height: 4, borderRadius: '50%',
              background: 'var(--brand-primary)',
              animation: 'typingDot 1.2s ease-in-out infinite',
            }} />
            <span style={{
              width: 4, height: 4, borderRadius: '50%',
              background: 'var(--brand-primary)',
              animation: 'typingDot 1.2s ease-in-out infinite 0.2s',
            }} />
            <span style={{
              width: 4, height: 4, borderRadius: '50%',
              background: 'var(--brand-primary)',
              animation: 'typingDot 1.2s ease-in-out infinite 0.4s',
            }} />
          </span>
        </div>
        <span
          className="witty-phrase"
          style={{
            fontSize: 12, color: 'var(--text-tertiary)',
            fontStyle: 'italic',
          }}
        >
          {stablePhrase}
        </span>
      </div>
    </div>
  )
})

/* ── 思考步骤指示器 ── */
export const ThoughtStepIndicator = memo(function ThoughtStepIndicator({ thoughts }: { thoughts: ThoughtStep[] }) {
  if (!thoughts.length) return null

  // 分离已完成和运行中的步骤
  const doneSteps = thoughts.filter(t => t.status === 'done')
  const runningStep = thoughts.find(t => t.status === 'running')

  // 只显示：最近1个完成步骤 + 当前运行步骤；历史完成步骤折叠
  const recentDone = doneSteps.length > 1 ? doneSteps.slice(-1) : doneSteps
  const foldedCount = doneSteps.length - recentDone.length

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6, flexWrap: 'wrap' }}>
      {foldedCount > 0 && (
        <span style={{
          fontSize: 11, color: 'var(--text-tertiary)', opacity: 0.7,
          background: 'var(--bg-subtle)', padding: '1px 6px', borderRadius: 4,
        }}>
          ✓ {foldedCount}步已完成
        </span>
      )}
      {recentDone.map((t) => (
        <span key={t.id} style={{
          display: 'inline-flex', alignItems: 'center', gap: 4,
          fontSize: 12, color: 'var(--text-tertiary)', opacity: 0.6,
        }}>
          <CheckCircleOutlined style={{ fontSize: 11 }} />
          {t.message}
        </span>
      ))}
      {runningStep && (
        <span style={{
          display: 'inline-flex', alignItems: 'center', gap: 4,
          fontSize: 12, color: 'var(--brand-primary)',
        }}>
          <LoadingOutlined style={{ fontSize: 11 }} />
          {runningStep.message}
        </span>
      )}
      {runningStep && <Spin size="small" />}
    </div>
  )
})

/* ═══════════════════════════════════════════════════════════
   工具调用可折叠区块（升级版）
   - 业务图标替换 ToolOutlined
   - 进度提示 n/total
   - 折叠态显示最近一个工具的结果摘要
   ═══════════════════════════════════════════════════════════ */
export function ToolCallBlock({ toolCalls, toolLabels }: {
  toolCalls: ToolCall[]
  toolLabels: Record<string, string>
}) {
  const [expanded, setExpanded] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  if (!toolCalls.length) return null

  const completedCount = toolCalls.filter(tc => tc.result).length
  const totalCount = toolCalls.length
  const allDone = completedCount === totalCount

  // 最近一个已完成工具的"摘要"：
  // 1. 优先用后端发来的结构化 summary（DataReferenceSummary）
  // 2. 没有结构化 summary → 显示友好占位，绝不直接展示 raw JSON
  const lastDone = [...toolCalls].reverse().find(tc => tc.result)
  const structuredSummary = lastDone?.summary
  const summaryText = structuredSummary?.items?.length
    ? structuredSummary.items
        .map(it => `${it.label} ${it.value}`)
        .join(' · ')
        .slice(0, 60)
    : lastDone?.result
      ? '已获取数据'
      : null

  return (
    <div
      ref={ref}
      className="tool-call-block"
      style={{
        marginBottom: 8, border: '1px solid var(--border-light)', borderRadius: 8,
        overflow: 'hidden', background: 'var(--bg-subtle)',
        transition: 'box-shadow 0.3s',
      }}
    >
      <div
        onClick={() => setExpanded(!expanded)}
        style={{
          padding: '6px 10px', cursor: 'pointer', display: 'flex', alignItems: 'center',
          gap: 8, fontSize: 12, color: 'var(--text-secondary)', userSelect: 'none',
        }}
      >
        {expanded ? <DownOutlined /> : <RightOutlined />}
        <ToolOutlined />
        <span>
          {allDone
            ? `已完成 ${totalCount} 个操作`
            : `执行中 ${completedCount}/${totalCount}`}
        </span>
        {allDone && <CheckCircleOutlined style={{ color: 'var(--color-success)', marginLeft: 4 }} />}
        {!allDone && <Spin size="small" style={{ marginLeft: 4 }} />}
        {!expanded && summaryText && (
          <span style={{
            marginLeft: 'auto', color: 'var(--text-tertiary)', fontSize: 11,
            maxWidth: 280, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
          }}>
            {summaryText}
          </span>
        )}
      </div>
      {expanded && (
        <div style={{ padding: '0 10px 8px', borderTop: '1px solid var(--border-light)' }}>
          {toolCalls.map((tc, i) => {
            const label = toolLabels[tc.name] || tc.name
            const icon = TOOL_ICONS[tc.name] || DEFAULT_TOOL_ICON
            const hasResult = !!tc.result
            return (
              <div key={i} style={{
                display: 'flex', alignItems: 'center', gap: 8, padding: '5px 0',
                fontSize: 12, color: hasResult ? 'var(--text-secondary)' : 'var(--text-tertiary)',
                borderBottom: i < toolCalls.length - 1 ? '1px solid var(--border-light)' : 'none',
              }}>
                {hasResult
                  ? <CheckCircleOutlined style={{ color: 'var(--color-success)' }} />
                  : <Spin size="small" />}
                <span style={{ fontSize: 14, display: 'inline-flex' }}>{icon}</span>
                <span>{label}</span>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
