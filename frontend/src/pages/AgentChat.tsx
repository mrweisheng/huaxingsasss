import { useState, useCallback, useRef } from 'react'
import { Card, Input, Button, Empty, message } from 'antd'
import { SendOutlined } from '@ant-design/icons'
import { agentApi } from '@/services/agent'

export default function AgentChat() {
  const [question, setQuestion] = useState('')
  const [loading, setLoading] = useState(false)
  const [answer, setAnswer] = useState<string | null>(null)
  const abortControllerRef = useRef<AbortController | null>(null)

  const handleSend = useCallback(async () => {
    if (!question.trim()) return

    // Cancel previous request
    abortControllerRef.current?.abort()
    const controller = new AbortController()
    abortControllerRef.current = controller

    setLoading(true)
    try {
      const result = await agentApi.chat(question, undefined, controller.signal)
      if (!controller.signal.aborted) {
        setAnswer(result.data?.answer || '暂无回答')
      }
    } catch (error: any) {
      if (error?.name === 'AbortError' || error?.code === 'ERR_CANCELED') return
      message.error('问答失败，请稍后重试')
    } finally {
      if (!controller.signal.aborted) {
        setLoading(false)
      }
    }
  }, [question])

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
        handleSend()
      }
    },
    [handleSend]
  )

  return (
    <Card title="智能问答">
      <div style={{ marginBottom: 16 }}>
        <Input.TextArea
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="请输入您的问题，例如：张三还欠多少钱？（Ctrl+Enter 发送）"
          rows={3}
          disabled={loading}
        />
        <Button
          type="primary"
          icon={<SendOutlined />}
          onClick={handleSend}
          loading={loading}
          style={{ marginTop: 8 }}
        >
          发送
        </Button>
      </div>
      {answer ? (
        <Card size="small" title="回答">
          {answer}
        </Card>
      ) : (
        <Empty description="输入问题开始智能问答" />
      )}
    </Card>
  )
}
