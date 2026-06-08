/**
 * 凭证确认面板 — interrupt 富 UI 组件
 * 在 Agent 发起 receipt_confirmation interrupt 时渲染可编辑的确认表单
 * 复用于 AgentChat 页面和 ReceiptChatModal
 */
import { useState } from 'react'
import { Input, InputNumber, Select, DatePicker, Button } from 'antd'
import { WarningOutlined } from '@ant-design/icons'
import type { ReceiptConfirmData, ContractInfo } from '@/types/agent'
import dayjs from 'dayjs'

const { Option } = Select
const { TextArea } = Input

interface Props {
  receiptData: ReceiptConfirmData
  contractInfo?: ContractInfo
  paymentType?: string
  matchWarning?: string
  onConfirm: (modifiedData: Partial<ReceiptConfirmData>) => void
  onCancel: () => void
  loading?: boolean
}

const paymentMethodOptions = [
  { label: '银行转账', value: 'bank_transfer' },
  { label: '微信支付', value: 'wechat' },
  { label: '支付宝', value: 'alipay' },
  { label: '现金', value: 'cash' },
  { label: '支票', value: 'check' },
  { label: '其他', value: 'other' },
]

export default function ReceiptConfirmPanel({
  receiptData, contractInfo, paymentType, matchWarning,
  onConfirm, onCancel, loading,
}: Props) {
  const [formData, setFormData] = useState<ReceiptConfirmData>({ ...receiptData })

  const isExpense = paymentType === 'expense'

  const updateField = <K extends keyof ReceiptConfirmData>(
    field: K, value: ReceiptConfirmData[K]
  ) => {
    setFormData(prev => ({ ...prev, [field]: value }))
  }

  // 检查是否有需要用户补充的字段
  const hasMissingCurrency = !receiptData.currency
  const hasMissingAmount = !receiptData.amount || receiptData.amount === 0
  const hasMissingDate = !receiptData.paid_date

  return (
    <div className="receipt-confirm-panel">
      {/* 标题 */}
      <div className="receipt-confirm-header">
        <span className="receipt-confirm-icon">📄</span>
        <span className="receipt-confirm-title">凭证识别结果</span>
      </div>

      {/* 匹配警告 */}
      {matchWarning && (
        <div className="receipt-confirm-warning">
          <WarningOutlined />
          <span>{matchWarning}</span>
        </div>
      )}

      {/* 合同上下文 */}
      {contractInfo && (
        <div className="receipt-confirm-context">
          <span>合同 <strong>{contractInfo.contract_number}</strong></span>
          <span className="receipt-confirm-sep">·</span>
          <span>{contractInfo.customer_name}</span>
          <span className="receipt-confirm-sep">·</span>
          <span>{contractInfo.business_type}</span>
        </div>
      )}

      {/* 表单 */}
      <div className="receipt-confirm-form">
        <div className="receipt-confirm-row">
          <div className={`receipt-confirm-field ${hasMissingCurrency ? 'field-warning' : ''}`}>
            <label>币种</label>
            <Select
              value={formData.currency || undefined}
              onChange={(v) => updateField('currency', v)}
              style={{ width: '100%' }}
              placeholder="请选择"
            >
              <Option value="CNY">CNY 人民币</Option>
              <Option value="HKD">HKD 港币</Option>
            </Select>
          </div>
          <div className={`receipt-confirm-field ${hasMissingAmount ? 'field-warning' : ''}`}>
            <label>金额</label>
            <InputNumber
              value={formData.amount || undefined}
              onChange={(v) => updateField('amount', v || 0)}
              style={{ width: '100%' }}
              min={0}
              precision={2}
              placeholder="请输入金额"
            />
          </div>
        </div>

        <div className="receipt-confirm-row">
          <div className={`receipt-confirm-field ${hasMissingDate ? 'field-warning' : ''}`}>
            <label>付款日期</label>
            <DatePicker
              value={formData.paid_date ? dayjs(formData.paid_date) : null}
              onChange={(d) => updateField('paid_date', d?.format('YYYY-MM-DD') || '')}
              style={{ width: '100%' }}
            />
          </div>
          <div className="receipt-confirm-field">
            <label>付款方式</label>
            <Select
              value={formData.payment_method || undefined}
              onChange={(v) => updateField('payment_method', v)}
              style={{ width: '100%' }}
              placeholder="请选择"
              allowClear
              options={paymentMethodOptions}
            />
          </div>
        </div>

        {isExpense && (
          <div className="receipt-confirm-field">
            <label>收款方 <span className="required-mark">*</span></label>
            <Input
              value={formData.payee_name}
              onChange={(e) => updateField('payee_name', e.target.value)}
              placeholder="请输入收款方名称"
            />
          </div>
        )}

        <div className="receipt-confirm-field">
          <label>业务说明</label>
          <Input
            value={formData.description}
            onChange={(e) => updateField('description', e.target.value)}
            placeholder="如：港车保险费、定金、尾款"
            maxLength={30}
          />
        </div>

        <div className="receipt-confirm-field">
          <label>备注</label>
          <TextArea
            value={formData.notes}
            onChange={(e) => updateField('notes', e.target.value)}
            rows={2}
            placeholder="可选"
          />
        </div>
      </div>

      {/* 操作按钮 */}
      <div className="receipt-confirm-actions">
        <Button
          type="primary"
          onClick={() => onConfirm(formData)}
          loading={loading}
        >
          确认录入
        </Button>
        <Button onClick={onCancel} disabled={loading}>
          取消
        </Button>
      </div>
    </div>
  )
}
