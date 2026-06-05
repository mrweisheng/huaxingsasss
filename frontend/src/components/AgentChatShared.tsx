import { useState, memo } from 'react'
import { Spin } from 'antd'
import {
  CheckCircleOutlined,
  LoadingOutlined,
  DownOutlined,
  RightOutlined,
  ToolOutlined,
} from '@ant-design/icons'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { ThoughtStep, ToolCall } from '@/types/agent'

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
    return (
      <div className={className} style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word', lineHeight: 1.7, fontSize: 14 }}>
        {content}
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

/* ── 思考步骤指示器 ── */
export const ThoughtStepIndicator = memo(function ThoughtStepIndicator({ thoughts }: { thoughts: ThoughtStep[] }) {
  if (!thoughts.length) return null
  const last = thoughts[thoughts.length - 1]
  const isRunning = last.status === 'running'

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6, flexWrap: 'wrap' }}>
      {thoughts.map((t, i) => (
        <span
          key={t.id}
          style={{
            display: 'inline-flex', alignItems: 'center', gap: 4,
            fontSize: 12,
            color: t.status === 'done' ? 'var(--text-tertiary)' : 'var(--brand-primary)',
            opacity: t.status === 'done' ? 0.6 : 1,
          }}
        >
          {t.status === 'done' ? (
            <CheckCircleOutlined style={{ fontSize: 11 }} />
          ) : (
            <LoadingOutlined style={{ fontSize: 11 }} />
          )}
          {t.message}
          {i < thoughts.length - 1 && (
            <span style={{ color: 'var(--border-light)', margin: '0 2px' }}>→</span>
          )}
        </span>
      ))}
      {isRunning && <Spin size="small" />}
    </div>
  )
})

/* ── 工具调用可折叠区块 ── */
export function ToolCallBlock({ toolCalls, toolLabels }: {
  toolCalls: ToolCall[]
  toolLabels: Record<string, string>
}) {
  const [expanded, setExpanded] = useState(false)
  if (!toolCalls.length) return null

  const completedCount = toolCalls.filter(tc => tc.result).length
  const totalCount = toolCalls.length
  const allDone = completedCount === totalCount

  return (
    <div style={{
      marginBottom: 8, border: '1px solid var(--border-light)', borderRadius: 8,
      overflow: 'hidden', background: 'var(--bg-subtle)',
    }}>
      <div
        onClick={() => setExpanded(!expanded)}
        style={{
          padding: '6px 10px', cursor: 'pointer', display: 'flex', alignItems: 'center',
          gap: 8, fontSize: 12, color: 'var(--text-secondary)', userSelect: 'none',
        }}
      >
        {expanded ? <DownOutlined /> : <RightOutlined />}
        <ToolOutlined />
        <span>执行了 {totalCount} 个操作</span>
        {allDone && <CheckCircleOutlined style={{ color: 'var(--color-success)', marginLeft: 4 }} />}
        {!allDone && <Spin size="small" style={{ marginLeft: 4 }} />}
      </div>
      {expanded && (
        <div style={{ padding: '0 10px 8px', borderTop: '1px solid var(--border-light)' }}>
          {toolCalls.map((tc, i) => {
            const label = toolLabels[tc.name] || tc.name
            const hasResult = !!tc.result
            return (
              <div key={i} style={{
                display: 'flex', alignItems: 'center', gap: 8, padding: '4px 0',
                fontSize: 12, color: hasResult ? 'var(--text-secondary)' : 'var(--text-tertiary)',
                borderBottom: i < toolCalls.length - 1 ? '1px solid var(--border-light)' : 'none',
              }}>
                {hasResult ? <CheckCircleOutlined style={{ color: 'var(--color-success)' }} /> : <Spin size="small" />}
                <span>{label}</span>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
