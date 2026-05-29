import { useState, useCallback, useRef, useEffect } from 'react'
import {
  Input,
  Button,
  Drawer,
  List,
  Avatar,
  Tag,
  Upload,
  Tooltip,
  message,
  Empty,
  Spin,
  Popconfirm,
  Typography,
} from 'antd'
import {
  SendOutlined,
  RobotOutlined,
  UserOutlined,
  PaperClipOutlined,
  PlusOutlined,
  HistoryOutlined,
  StopOutlined,
  DeleteOutlined,
  ToolOutlined,
  CheckCircleOutlined,
  ExclamationCircleOutlined,
  FilePdfOutlined,
  FileWordOutlined,
  FileExcelOutlined,
  FileTextOutlined,
} from '@ant-design/icons'
import { useAgentStore } from '@/store/useAgentStore'
import type { ChatMessage, ToolCall } from '@/types/agent'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

const { Text } = Typography

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

function ToolCallView({ toolCall }: { toolCall: ToolCall }) {
  const label = TOOL_LABELS[toolCall.name] || toolCall.name
  const hasResult = !!toolCall.result

  return (
    <Tooltip title={!hasResult ? '历史记录中该工具结果未保存，返回查看时请重新对话获取最新信息' : undefined}>
      <Tag
        color={hasResult ? 'green' : 'orange'}
        icon={hasResult ? <CheckCircleOutlined /> : <ExclamationCircleOutlined />}
        style={{ marginBottom: 4, cursor: hasResult ? 'default' : 'help' }}
      >
        <ToolOutlined /> {label}
      </Tag>
    </Tooltip>
  )
}

/** Markdown 渲染组件 */
function MarkdownRenderer({ content }: { content: string }) {
  return (
    <div className="markdown-content">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          // 表格样式
          table: ({ children }) => (
            <table style={{
              width: '100%',
              borderCollapse: 'collapse',
              margin: '8px 0',
              fontSize: 13,
            }}>
              {children}
            </table>
          ),
          thead: ({ children }) => (
            <thead style={{ background: '#f0f5ff' }}>
              {children}
            </thead>
          ),
          th: ({ children }) => (
            <th style={{
              border: '1px solid #d9d9d9',
              padding: '6px 10px',
              textAlign: 'left',
              fontWeight: 600,
              color: '#333',
            }}>
              {children}
            </th>
          ),
          td: ({ children }) => (
            <td style={{
              border: '1px solid #d9d9d9',
              padding: '6px 10px',
              color: '#555',
            }}>
              {children}
            </td>
          ),
          // 加粗文字
          strong: ({ children }) => (
            <strong style={{ color: '#1677ff' }}>
              {children}
            </strong>
          ),
          // 段落
          p: ({ children }) => (
            <p style={{ margin: '6px 0' }}>
              {children}
            </p>
          ),
          // 有序/无序列表
          ol: ({ children }) => (
            <ol style={{ margin: '6px 0', paddingLeft: 20 }}>
              {children}
            </ol>
          ),
          ul: ({ children }) => (
            <ul style={{ margin: '6px 0', paddingLeft: 20 }}>
              {children}
            </ul>
          ),
          li: ({ children }) => (
            <li style={{ margin: '4px 0' }}>
              {children}
            </li>
          ),
          // 代码块
          code: ({ inline, children }: any) =>
            inline ? (
              <code style={{
                background: '#f0f0f0',
                padding: '2px 6px',
                borderRadius: 4,
                fontSize: 12,
                color: '#eb2f96',
              }}>
                {children}
              </code>
            ) : (
              <pre style={{
                background: '#f5f5f5',
                padding: 12,
                borderRadius: 6,
                overflow: 'auto',
                fontSize: 12,
                margin: '8px 0',
              }}>
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

function MessageBubble({ msg }: { msg: ChatMessage }) {
  if (msg.role === 'user') {
    return (
      <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 16 }}>
        <div
          style={{
            maxWidth: '70%',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'flex-end',
            gap: 6,
          }}
        >
          {/* 附件预览 */}
          {msg.attachments && msg.attachments.length > 0 && (
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', justifyContent: 'flex-end' }}>
              {msg.attachments.map((att, i) => {
                if (att.fileType === 'image' && att.preview) {
                  return (
                    <img
                      key={i}
                      src={att.preview}
                      alt={att.fileName || '附件'}
                      style={{
                        maxWidth: 200, maxHeight: 200,
                        borderRadius: 10, objectFit: 'cover',
                        border: '2px solid #1677ff',
                      }}
                    />
                  )
                }
                const fileIcon = att.fileType === 'pdf' ? <FilePdfOutlined />
                  : att.fileType === 'word' ? <FileWordOutlined />
                  : att.fileType === 'excel' ? <FileExcelOutlined />
                  : att.fileType === 'text' ? <FileTextOutlined />
                  : <PaperClipOutlined />
                return (
                  <Tag key={i} color="blue" style={{ margin: 0 }}>
                    {fileIcon} {att.fileName || '文件'}
                  </Tag>
                )
              })}
            </div>
          )}
          {/* 文字内容 — 如果只有附件没有文字，显示占位提示 */}
          <div
            style={{
              background: '#1677ff',
              color: '#fff',
              padding: msg.content ? '10px 16px' : '6px 16px',
              borderRadius: msg.attachments?.length ? '12px 12px 2px 12px' : '12px 12px 2px 12px',
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-word',
              lineHeight: msg.content ? undefined : '32px',
            }}
          >
            {msg.content || (msg.attachments?.length ? `已上传 ${msg.attachments.length} 个文件` : '')}
          </div>
        </div>
        <Avatar
          icon={<UserOutlined />}
          style={{ background: '#1677ff', marginLeft: 8, flexShrink: 0 }}
          size={36}
        />
      </div>
    )
  }

  if (msg.role === 'assistant') {
    return (
      <div style={{ display: 'flex', marginBottom: 16 }}>
        <Avatar
          icon={<RobotOutlined />}
          style={{ background: '#52c41a', marginRight: 8, flexShrink: 0 }}
          size={36}
        />
        <div style={{ maxWidth: '70%' }}>
          {msg.toolCalls && msg.toolCalls.length > 0 && (
            <div style={{ marginBottom: 6 }}>
              {msg.toolCalls.map((tc, i) => (
                <ToolCallView key={i} toolCall={tc} />
              ))}
            </div>
          )}
          {msg.content ? (
            <div
              style={{
                background: '#f5f5f5',
                padding: '10px 16px',
                borderRadius: '12px 12px 12px 2px',
                wordBreak: 'break-word',
              }}
            >
              <MarkdownRenderer content={msg.content} />
            </div>
          ) : (msg as any)._thinking ? (
            <div
              style={{
                background: '#f5f5f5',
                padding: '8px 16px',
                borderRadius: '12px 12px 12px 2px',
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                color: '#999',
                fontSize: 13,
              }}
            >
              <Spin size="small" />
              {(msg as any)._thinking}
            </div>
          ) : msg.toolCalls?.length ? (
            <Spin size="small" />
          ) : null}
        </div>
      </div>
    )
  }

  return null
}

export default function AgentChat() {
  const [inputText, setInputText] = useState('')
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [pendingFiles, setPendingFiles] = useState<File[]>([])
  const messageListRef = useRef<HTMLDivElement>(null)

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

  // 初始化加载会话
  useEffect(() => {
    loadSessions()
  }, [])

  // 自动滚动到底部
  useEffect(() => {
    if (messageListRef.current) {
      messageListRef.current.scrollTop = messageListRef.current.scrollHeight
    }
  }, [messages])

  // 错误提示
  useEffect(() => {
    if (error) {
      message.error(error)
      clearError()
    }
  }, [error])

  // 监听粘贴事件，支持图片粘贴上传
  useEffect(() => {
    const handlePaste = (e: ClipboardEvent) => {
      const items = e.clipboardData?.items
      if (!items) return

      for (const item of items) {
        if (item.type.startsWith('image/')) {
          e.preventDefault()
          const file = item.getAsFile()
          if (file) {
            setPendingFiles((prev) => [...prev, file])
          }
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
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault()
        handleSend()
      }
    },
    [handleSend],
  )

  const handleNewSession = useCallback(async () => {
    await createSession()
  }, [createSession])

  const handleFileSelect = useCallback((file: File) => {
    setPendingFiles((prev) => [...prev, file])
    return false // prevent Upload from auto-uploading
  }, [])

  const removePendingFile = useCallback((index: number) => {
    setPendingFiles((prev) => prev.filter((_, i) => i !== index))
  }, [])

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - 160px)' }}>
      {/* 顶部工具栏 */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '8px 16px',
          borderBottom: '1px solid #f0f0f0',
          background: '#fff',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <RobotOutlined style={{ fontSize: 20, color: '#52c41a' }} />
          <Text strong style={{ fontSize: 16 }}>
            智能业务助手
          </Text>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <Button icon={<HistoryOutlined />} onClick={() => setDrawerOpen(true)}>
            会话记录
          </Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={handleNewSession}>
            新会话
          </Button>
        </div>
      </div>

      {/* 消息列表 */}
      <div
        ref={messageListRef}
        style={{
          flex: 1,
          overflow: 'auto',
          padding: '16px 24px',
          background: '#fafafa',
        }}
      >
        {messages.length === 0 ? (
          <div style={{ textAlign: 'center', paddingTop: 80 }}>
            <RobotOutlined style={{ fontSize: 48, color: '#d9d9d9' }} />
            <div style={{ marginTop: 16, color: '#999' }}>
              <p>你好！我是华星资源业务助手，可以帮你：</p>
              <div style={{ textAlign: 'left', maxWidth: 400, margin: '0 auto' }}>
                <p>- 查询合同和付款信息</p>
                <p>- 上传凭证并登记付款</p>
                <p>- 分析逾期和到期情况</p>
                <p>- 回答业务相关问题</p>
              </div>
              <p style={{ marginTop: 16, color: '#bbb' }}>请输入你的问题开始对话</p>
            </div>
          </div>
        ) : (
          messages
            .filter((m) => m.role === 'user' || m.role === 'assistant')
            .map((msg) => <MessageBubble key={msg.id} msg={msg} />)
        )}
        {isStreaming && !messages.some((m) => m.role === 'assistant' && !m.content && !(m.toolCalls?.length)) && (
          <div style={{ display: 'flex', marginBottom: 16 }}>
            <Avatar icon={<RobotOutlined />} style={{ background: '#52c41a', marginRight: 8 }} size={36} />
            <Spin size="small" style={{ marginTop: 10 }} />
          </div>
        )}
      </div>

      {/* 输入区域 */}
      <div
        style={{
          padding: '12px 24px 16px',
          background: '#fff',
          borderTop: '1px solid #f0f0f0',
        }}
      >
        {/* 待发送文件预览 — 在输入框内部上方 */}
        {pendingFiles.length > 0 && (
          <div
            style={{
              background: '#fafafa',
              border: '1px solid #e8e8e8',
              borderBottom: 'none',
              borderRadius: '12px 12px 0 0',
              padding: '8px 12px',
              display: 'flex',
              gap: 8,
              flexWrap: 'wrap',
              alignItems: 'center',
            }}
          >
            <span style={{ fontSize: 12, color: '#999', marginRight: 4, whiteSpace: 'nowrap' }}>
              附件
            </span>
            {pendingFiles.map((f, i) => {
              const name = f.name.toLowerCase()
              if (f.type.startsWith('image/')) {
                return (
                  <span
                    key={i}
                    style={{ position: 'relative', display: 'inline-block', cursor: 'pointer' }}
                    onClick={() => removePendingFile(i)}
                  >
                    <img
                      src={URL.createObjectURL(f)}
                      alt={f.name}
                      style={{
                        height: 40, width: 40, borderRadius: 6,
                        objectFit: 'cover', border: '1px solid #d9d9d9',
                      }}
                    />
                    <span style={{
                      position: 'absolute', top: -4, right: -4,
                      background: '#ff4d4f', color: '#fff',
                      borderRadius: '50%', width: 14, height: 14,
                      fontSize: 10, lineHeight: '14px', textAlign: 'center',
                    }}>×</span>
                  </span>
                )
              }
              const icon = name.endsWith('.pdf') ? <FilePdfOutlined style={{ color: '#f5222d' }} />
                : name.endsWith('.docx') || name.endsWith('.doc') ? <FileWordOutlined style={{ color: '#1677ff' }} />
                : name.endsWith('.xlsx') || name.endsWith('.xls') ? <FileExcelOutlined style={{ color: '#52c41a' }} />
                : <FileTextOutlined style={{ color: '#faad14' }} />
              return (
                <Tag
                  key={i}
                  closable
                  onClose={() => removePendingFile(i)}
                  color="default"
                  style={{ margin: 0, fontSize: 12 }}
                >
                  {icon} {f.name.length > 20 ? f.name.slice(0, 18) + '…' : f.name}
                </Tag>
              )
            })}
          </div>
        )}

        {/* 输入框 + 按钮 */}
        <div
          style={{
            display: 'flex',
            gap: 10,
            alignItems: 'flex-end',
            background: '#fff',
            border: '1px solid #e8e8e8',
            borderRadius: pendingFiles.length > 0 ? '0 0 12px 12px' : 12,
            padding: '8px 8px 8px 12px',
            boxShadow: '0 1px 4px rgba(0,0,0,0.03)',
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
                padding: '8px',
                borderRadius: 8,
                color: pendingFiles.length > 0 ? '#1677ff' : '#666',
                flexShrink: 0,
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
            style={{
              flex: 1,
              fontSize: 14,
              lineHeight: '22px',
              padding: '6px 0',
              resize: 'none',
            }}
          />
          {isStreaming ? (
            <Button
              danger
              size="large"
              icon={<StopOutlined />}
              onClick={stopGeneration}
              style={{
                borderRadius: 8,
                height: 40,
                padding: '0 16px',
                flexShrink: 0,
              }}
            >
              停止
            </Button>
          ) : (
            <Button
              type="primary"
              size="large"
              icon={<SendOutlined />}
              onClick={handleSend}
              disabled={!inputText.trim() && pendingFiles.length === 0}
              style={{
                borderRadius: 8,
                height: 40,
                padding: '0 20px',
                flexShrink: 0,
              }}
            >
              发送
            </Button>
          )}
        </div>
        {/* 底部提示 */}
        <div
          style={{
            textAlign: 'center',
            fontSize: 11,
            color: '#bbb',
            marginTop: 8,
          }}
        >
          Ctrl/Cmd + V 粘贴图片 · AI 可能产生错误信息，请核实重要数据
        </div>
      </div>

      {/* 会话历史抽屉 */}
      <Drawer
        title="会话记录"
        placement="right"
        onClose={() => setDrawerOpen(false)}
        open={drawerOpen}
        width={320}
      >
        <List
          dataSource={sessions}
          locale={{ emptyText: <Empty description="暂无会话记录" /> }}
          renderItem={(session) => (
            <List.Item
              style={{
                cursor: 'pointer',
                background: session.sessionId === currentSessionId ? '#e6f4ff' : undefined,
                padding: '8px 12px',
                borderRadius: 6,
              }}
              onClick={() => {
                switchSession(session.sessionId)
                setDrawerOpen(false)
              }}
              actions={[
                <Popconfirm
                  key="delete"
                  title="确定删除此会话？"
                  onConfirm={() => {
                    deleteSession(session.sessionId)
                  }}
                >
                  <Button
                    type="text"
                    danger
                    size="small"
                    icon={<DeleteOutlined />}
                    onClick={(e) => e.stopPropagation()}
                  />
                </Popconfirm>,
              ]}
            >
              <List.Item.Meta
                title={session.title || '新会话'}
                description={`${session.messageCount} 条消息`}
              />
            </List.Item>
          )}
        />
      </Drawer>
    </div>
  )
}
