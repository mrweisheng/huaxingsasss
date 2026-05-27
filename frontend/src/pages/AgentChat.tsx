import { useState, useCallback, useRef, useEffect } from 'react'
import {
  Card,
  Input,
  Button,
  Drawer,
  List,
  Avatar,
  Tag,
  Upload,
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
  LoadingOutlined,
} from '@ant-design/icons'
import type { UploadFile } from 'antd'
import { useAgentStore } from '@/store/useAgentStore'
import type { ChatMessage, ToolCall } from '@/types/agent'

const { Text, Paragraph } = Typography

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
  analyze_image: '图片分析',
}

function ToolCallView({ toolCall }: { toolCall: ToolCall }) {
  const label = TOOL_LABELS[toolCall.name] || toolCall.name
  const hasResult = !!toolCall.result

  return (
    <Tag
      color={hasResult ? 'green' : 'processing'}
      icon={hasResult ? <CheckCircleOutlined /> : <LoadingOutlined />}
      style={{ marginBottom: 4 }}
    >
      <ToolOutlined /> {label}
    </Tag>
  )
}

function MessageBubble({ msg }: { msg: ChatMessage }) {
  if (msg.role === 'user') {
    return (
      <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 16 }}>
        <div
          style={{
            maxWidth: '70%',
            background: '#1677ff',
            color: '#fff',
            padding: '10px 16px',
            borderRadius: '12px 12px 2px 12px',
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-word',
          }}
        >
          {msg.content}
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
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word',
              }}
            >
              {msg.content}
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

  const handleSend = useCallback(async () => {
    const text = inputText.trim()
    if (!text && pendingFiles.length === 0) return

    await sendMessage(text, pendingFiles.length > 0 ? pendingFiles : undefined)
    setInputText('')
    setPendingFiles([])
  }, [inputText, pendingFiles, sendMessage])

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
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
    <div style={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - 120px)' }}>
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

      {/* 待上传文件预览 */}
      {pendingFiles.length > 0 && (
        <div
          style={{
            padding: '8px 24px',
            background: '#fff',
            borderTop: '1px solid #f0f0f0',
            display: 'flex',
            gap: 8,
            flexWrap: 'wrap',
          }}
        >
          {pendingFiles.map((f, i) => (
            <Tag
              key={i}
              closable
              onClose={() => removePendingFile(i)}
              color="blue"
            >
              <PaperClipOutlined /> {f.name}
            </Tag>
          ))}
        </div>
      )}

      {/* 输入区域 */}
      <div
        style={{
          padding: '12px 24px',
          background: '#fff',
          borderTop: '1px solid #f0f0f0',
          display: 'flex',
          gap: 8,
          alignItems: 'flex-end',
        }}
      >
        <Upload
          beforeUpload={handleFileSelect}
          showUploadList={false}
          accept="image/*,.pdf"
        >
          <Button icon={<PaperClipOutlined />} disabled={isStreaming} />
        </Upload>
        <Input.TextArea
          value={inputText}
          onChange={(e) => setInputText(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="输入消息... (Ctrl+Enter 发送)"
          autoSize={{ minRows: 1, maxRows: 4 }}
          disabled={isStreaming}
          style={{ flex: 1 }}
        />
        {isStreaming ? (
          <Button
            danger
            icon={<StopOutlined />}
            onClick={stopGeneration}
          >
            停止
          </Button>
        ) : (
          <Button
            type="primary"
            icon={<SendOutlined />}
            onClick={handleSend}
            disabled={!inputText.trim() && pendingFiles.length === 0}
          >
            发送
          </Button>
        )}
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
                  onConfirm={(e) => {
                    e?.stopPropagation()
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
