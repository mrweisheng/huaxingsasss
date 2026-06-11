import { useEffect, useState, useRef } from 'react'
import { Modal, Button } from 'antd'
import { ExclamationCircleFilled } from '@ant-design/icons'

/**
 * 危险操作二次确认弹窗 —— 5 秒强制读秒
 *
 * 设计意图：
 * - 删除客户/合同/收付记录是不可逆操作，必须"分量感"地确认
 * - 5 秒倒计时强迫用户停顿、看清描述
 * - 倒计时未结束时"确认删除"按钮禁用，按钮文字显示剩余秒数
 * - 0 后按钮才变红色可点
 *
 * 复用：客户管理/客户详情/合同管理/合同台账/付款管理 所有删除流程统一走此组件
 */

const COUNTDOWN_SECONDS = 5

export interface DangerConfirmModalProps {
  open: boolean
  /** 弹窗标题，例：「确认删除客户」 */
  title: string
  /** 主描述，例：「将删除客户「张三」，关联合同不会被删除。」 */
  description: React.ReactNode
  /** 风险提示副文案（可选） */
  warning?: React.ReactNode
  /** 确认按钮文字（默认「确认删除」） */
  okText?: string
  /** 取消按钮文字（默认「取消」） */
  cancelText?: string
  /** 用户确认（倒计时结束后点击）回调 */
  onConfirm: () => void | Promise<void>
  /** 取消 / 关闭 回调 */
  onCancel: () => void
  /** 业务侧是否处于提交中（外部 loading） */
  confirming?: boolean
}

export default function DangerConfirmModal({
  open,
  title,
  description,
  warning,
  okText = '确认删除',
  cancelText = '取消',
  onConfirm,
  onCancel,
  confirming = false,
}: DangerConfirmModalProps) {
  const [remaining, setRemaining] = useState(COUNTDOWN_SECONDS)
  const timerRef = useRef<number | null>(null)

  // 弹窗每次打开时重置倒计时
  useEffect(() => {
    if (!open) {
      if (timerRef.current) {
        window.clearInterval(timerRef.current)
        timerRef.current = null
      }
      setRemaining(COUNTDOWN_SECONDS)
      return
    }
    setRemaining(COUNTDOWN_SECONDS)
    timerRef.current = window.setInterval(() => {
      setRemaining(prev => {
        if (prev <= 1) {
          if (timerRef.current) {
            window.clearInterval(timerRef.current)
            timerRef.current = null
          }
          return 0
        }
        return prev - 1
      })
    }, 1000)
    return () => {
      if (timerRef.current) {
        window.clearInterval(timerRef.current)
        timerRef.current = null
      }
    }
  }, [open])

  const isReady = remaining === 0
  const confirmLabel = isReady ? okText : `请等待 ${remaining}s`

  return (
    <Modal
      open={open}
      title={
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
          <ExclamationCircleFilled style={{ color: '#dc6b3d', fontSize: 20 }} />
          {title}
        </span>
      }
      onCancel={() => {
        if (confirming) return
        onCancel()
      }}
      maskClosable={!confirming}
      closable={!confirming}
      keyboard={!confirming}
      centered
      destroyOnClose
      footer={[
        <Button key="cancel" onClick={onCancel} disabled={confirming}>
          {cancelText}
        </Button>,
        <Button
          key="ok"
          danger
          type="primary"
          loading={confirming}
          disabled={!isReady || confirming}
          onClick={() => onConfirm()}
        >
          {confirmLabel}
        </Button>,
      ]}
    >
      <div style={{ fontSize: 14, color: '#333', lineHeight: 1.7, marginTop: 4 }}>
        {description}
      </div>
      {warning && (
        <div
          style={{
            marginTop: 12,
            padding: '10px 12px',
            background: '#fdf4f3',
            border: '1px solid #f5c7c2',
            borderRadius: 6,
            color: '#8f2d28',
            fontSize: 13,
            lineHeight: 1.6,
          }}
        >
          {warning}
        </div>
      )}
      <div
        style={{
          marginTop: 14,
          fontSize: 12,
          color: isReady ? '#0d9488' : '#999',
        }}
      >
        {isReady ? '✓ 已可执行，请确认。此操作不可撤销。' : `安全等待中，${remaining} 秒后可执行 …`}
      </div>
    </Modal>
  )
}
