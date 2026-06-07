import { useState, useRef, useEffect } from 'react'
import {
  Modal, Steps, Upload, Button, Input, InputNumber, Select, DatePicker,
  Radio,
} from 'antd'
import { InboxOutlined, LoadingOutlined, CheckCircleFilled, CloseCircleFilled, ReloadOutlined } from '@ant-design/icons'
import { paymentApi } from '@/services/payment'
import type {
  Payment, ReceiptAnalyzeResponse, PendingMatchItem, CreateFromReceiptRequest,
} from '@/types'
import dayjs from 'dayjs'
import './ReceiptPaymentModal.css'

const { Dragger } = Upload
const { TextArea } = Input
const { Option } = Select

interface Props {
  open: boolean
  onClose: (success: boolean) => void
  contractId: number
  contractNumber: string
  customerName: string
  contractCurrency: string
  paymentType: 'income' | 'expense'
}

interface ReceiptFormData {
  match_payment_id?: number
  installment_number: number
  installment_name: string
  currency: string
  amount: number
  paid_date: string
  payment_method: string
  payee_name?: string
  notes: string
}

interface ReceiptFile {
  file: File
  thumbUrl?: string
  id: string
  status: 'pending' | 'analyzing' | 'analyzed' | 'confirmed' | 'submitting' | 'done' | 'error'
  analysis?: ReceiptAnalyzeResponse
  formData?: ReceiptFormData
  result?: Payment
  error?: string
}

const paymentMethodOptions = [
  { label: '银行转账', value: 'bank_transfer' },
  { label: '微信支付', value: 'wechat' },
  { label: '支付宝', value: 'alipay' },
  { label: '现金', value: 'cash' },
  { label: '支票', value: 'check' },
  { label: '其他', value: 'other' },
]

export default function ReceiptPaymentModal({
  open, onClose, contractId, contractNumber, customerName, contractCurrency, paymentType,
}: Props) {
  const [receipts, setReceipts] = useState<ReceiptFile[]>([])
  const [currentStep, setCurrentStep] = useState<'upload' | 'processing' | 'summary'>('upload')
  const [activeIndex, setActiveIndex] = useState(0)
  const [processingPhase, setProcessingPhase] = useState<'analyze' | 'confirm' | 'submit'>('analyze')
  const [loading, setLoading] = useState(false)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const currentReceipt = receipts[activeIndex]
  const isIncome = paymentType === 'income'
  const typeLabel = isIncome ? '收入' : '支出'

  // 清理定时器
  useEffect(() => {
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current)
    }
  }, [])

  // 重置状态
  const reset = () => {
    receipts.forEach(r => { if (r.thumbUrl) URL.revokeObjectURL(r.thumbUrl) })
    setReceipts([])
    setCurrentStep('upload')
    setActiveIndex(0)
    setProcessingPhase('analyze')
    setLoading(false)
    if (timerRef.current) clearTimeout(timerRef.current)
  }

  const handleClose = (success: boolean) => {
    reset()
    onClose(success)
  }

  // 文件上传处理
  const handleBeforeUpload = (file: File) => {
    const id = `${Date.now()}_${Math.random().toString(36).slice(2, 8)}`
    const thumbUrl = file.type.startsWith('image/') ? URL.createObjectURL(file) : undefined
    setReceipts(prev => [...prev, {
      file,
      thumbUrl,
      id,
      status: 'pending',
    }])
    return false // 阻止自动上传
  }

  const handleRemoveFile = (index: number) => {
    setReceipts(prev => {
      const r = prev[index]
      if (r?.thumbUrl) URL.revokeObjectURL(r.thumbUrl)
      return prev.filter((_, i) => i !== index)
    })
  }

  // 更新单条 receipt 状态
  const updateReceipt = (index: number, updates: Partial<ReceiptFile>) => {
    setReceipts(prev => prev.map((r, i) => i === index ? { ...r, ...updates } : r))
  }

  // 开始处理
  const handleStartProcessing = async () => {
    if (receipts.length === 0) return
    setCurrentStep('processing')
    setActiveIndex(0)
    setProcessingPhase('analyze')
    processReceipt(0)
  }

  // 处理单张凭证
  const processReceipt = async (index: number) => {
    setActiveIndex(index)
    setProcessingPhase('analyze')
    updateReceipt(index, { status: 'analyzing', error: undefined })

    try {
      const analysis = await paymentApi.analyzeReceipt({
        contract_id: contractId,
        payment_type: paymentType,
        file: receipts[index].file,
      })

      // 预填表单
      const formData: ReceiptFormData = {
        installment_number: analysis.next_installment_number,
        installment_name: '',
        currency: analysis.analysis.currency || contractCurrency,
        amount: analysis.analysis.amount || 0,
        paid_date: analysis.analysis.transaction_date || dayjs().format('YYYY-MM-DD'),
        payment_method: analysis.analysis.payment_method || '',
        payee_name: analysis.analysis.payee_name || '',
        notes: '',
      }

      updateReceipt(index, { status: 'analyzed', analysis, formData })
      setProcessingPhase('confirm')
    } catch (err: any) {
      const errorMsg = err?.response?.data?.detail || err?.message || '分析失败'
      updateReceipt(index, { status: 'error', error: errorMsg })
      // 3 秒后自动跳到下一张
      timerRef.current = setTimeout(() => moveToNext(index), 3000)
    }
  }

  // 移到下一张或进入汇总
  const moveToNext = (currentIndex: number) => {
    if (currentIndex + 1 < receipts.length) {
      processReceipt(currentIndex + 1)
    } else {
      setCurrentStep('summary')
    }
  }

  // 确认并提交
  const handleSubmit = async () => {
    if (!currentReceipt?.analysis || !currentReceipt.formData) return
    setProcessingPhase('submit')
    updateReceipt(activeIndex, { status: 'submitting' })
    setLoading(true)

    try {
      const { analysis, formData } = currentReceipt
      const req: CreateFromReceiptRequest = {
        contract_id: contractId,
        payment_type: paymentType,
        temp_file_path: analysis.temp_file_path,
        receipt_data: analysis.analysis,
        currency: formData.currency,
        amount: formData.amount,
        paid_date: formData.paid_date,
        payment_method: formData.payment_method || undefined,
        installment_name: formData.installment_name || undefined,
        payee_name: formData.payee_name || undefined,
        notes: formData.notes || undefined,
      }

      if (formData.match_payment_id) {
        req.match_payment_id = formData.match_payment_id
      } else {
        req.installment_number = formData.installment_number
      }

      const payment = await paymentApi.createFromReceipt(req)
      updateReceipt(activeIndex, { status: 'done', result: payment })

      timerRef.current = setTimeout(() => moveToNext(activeIndex), 500)
    } catch (err: any) {
      const errorMsg = err?.response?.data?.detail || err?.message || '提交失败'
      updateReceipt(activeIndex, { status: 'error', error: errorMsg })
      timerRef.current = setTimeout(() => moveToNext(activeIndex), 3000)
    } finally {
      setLoading(false)
    }
  }

  // 重试
  const handleRetry = (index: number) => {
    processReceipt(index)
  }

  // 更新表单字段
  const updateFormField = (field: keyof ReceiptFormData, value: any) => {
    if (!currentReceipt?.formData) return
    updateReceipt(activeIndex, {
      formData: { ...currentReceipt.formData, [field]: value },
    })
  }

  // 选择匹配项
  const handleMatchSelect = (matchId: number | null) => {
    if (!currentReceipt?.formData) return
    updateFormField('match_payment_id', matchId || undefined)
  }

  // 渲染步骤内容
  const renderStepContent = () => {
    if (currentStep === 'upload') {
      return (
        <div className="receipt-modal-upload">
          <Dragger
            multiple
            showUploadList={false}
            beforeUpload={handleBeforeUpload}
            accept="image/*,.pdf,.docx,.xlsx"
          >
            <p className="ant-upload-drag-icon"><InboxOutlined /></p>
            <p className="ant-upload-text">点击或拖拽凭证文件到此区域</p>
            <p className="ant-upload-hint">支持图片、PDF、Word、Excel，可批量上传</p>
          </Dragger>
        </div>
      )
    }

    if (currentStep === 'processing' && currentReceipt) {
      return (
        <>
          {/* 凭证缩略图行 */}
          <div className="receipt-modal-thumbs">
            {receipts.map((r, i) => (
              <div
                key={r.id}
                className={`receipt-modal-thumb ${i === activeIndex ? 'active' : ''} ${r.status === 'done' ? 'done' : ''} ${r.status === 'error' ? 'error' : ''}`}
                onClick={() => {
                  if (r.status === 'analyzed' || r.status === 'confirmed') {
                    setActiveIndex(i)
                    setProcessingPhase('confirm')
                  }
                }}
              >
                {r.thumbUrl && (
                  <img src={r.thumbUrl} alt="" />
                )}
              </div>
            ))}
          </div>

          {/* 分析阶段 */}
          {processingPhase === 'analyze' && (
            <div className="receipt-modal-analyzing">
              <LoadingOutlined className="receipt-modal-analyzing-icon" />
              <div className="receipt-modal-analyzing-text">正在分析第 {activeIndex + 1} / {receipts.length} 张凭证...</div>
              <div className="receipt-modal-analyzing-hint">AI 正在识别凭证内容，请稍候</div>
            </div>
          )}

          {/* 确认阶段 */}
          {processingPhase === 'confirm' && currentReceipt.analysis && currentReceipt.formData && (
            <div className="receipt-modal-form">
              {/* 已有记录提示 */}
              <div className="receipt-modal-existing">
                该合同已有 {currentReceipt.analysis.existing_payment_count} 笔{typeLabel}记录
              </div>

              {/* Warnings */}
              {currentReceipt.analysis.analysis?.warnings?.length > 0 && (
                <div className="receipt-modal-warnings">
                  <CloseCircleFilled />
                  {currentReceipt.analysis.analysis?.warnings?.join('；')}
                </div>
              )}

              {/* 匹配选择（仅 income） */}
              {isIncome && currentReceipt.analysis.pending_matches?.length > 0 && (
                <div className="receipt-modal-match">
                  <div className="receipt-modal-match-title">匹配已有记录</div>
                  <Radio.Group
                    value={currentReceipt.formData.match_payment_id || 'new'}
                    onChange={(e) => handleMatchSelect(e.target.value === 'new' ? null : e.target.value)}
                  >
                    {currentReceipt.analysis.pending_matches.map((m: PendingMatchItem) => (
                      <div
                        key={m.payment_id}
                        className={`receipt-modal-match-option ${currentReceipt.formData?.match_payment_id === m.payment_id ? 'selected' : ''}`}
                        onClick={() => handleMatchSelect(m.payment_id)}
                      >
                        <Radio value={m.payment_id} />
                        <div className="receipt-modal-match-option-info">
                          <div className="receipt-modal-match-option-name">
                            {m.installment_name || `第${m.installment_number}期`}
                          </div>
                          <div className="receipt-modal-match-option-amount">
                            {m.currency} {m.amount.toLocaleString()}
                          </div>
                        </div>
                        <span className="receipt-modal-match-option-score">匹配度 {m.score}</span>
                      </div>
                    ))}
                    <div
                      className={`receipt-modal-match-option ${!currentReceipt.formData.match_payment_id ? 'selected' : ''}`}
                      onClick={() => handleMatchSelect(null)}
                    >
                      <Radio value="new" />
                      <div className="receipt-modal-match-option-info">
                        <div className="receipt-modal-match-option-name">创建新记录</div>
                      </div>
                    </div>
                  </Radio.Group>
                </div>
              )}

              {/* 表单字段 */}
              <div className="receipt-modal-form-row">
                <div className={currentReceipt.analysis.analysis?.currency === null ? 'receipt-modal-form-warning' : ''}>
                  <label>币种</label>
                  <Select
                    value={currentReceipt.formData.currency}
                    onChange={(v) => updateFormField('currency', v)}
                    style={{ width: '100%' }}
                  >
                    <Option value="CNY">CNY 人民币</Option>
                    <Option value="HKD">HKD 港币</Option>
                  </Select>
                </div>
                <div>
                  <label>金额</label>
                  <InputNumber
                    value={currentReceipt.formData.amount}
                    onChange={(v) => updateFormField('amount', v || 0)}
                    style={{ width: '100%' }}
                    min={0}
                    precision={2}
                  />
                </div>
              </div>

              <div className="receipt-modal-form-row">
                <div className={currentReceipt.analysis.analysis?.transaction_date === null ? 'receipt-modal-form-warning' : ''}>
                  <label>交易日期</label>
                  <DatePicker
                    value={dayjs(currentReceipt.formData.paid_date)}
                    onChange={(d) => updateFormField('paid_date', d?.format('YYYY-MM-DD') || '')}
                    style={{ width: '100%' }}
                  />
                </div>
                <div>
                  <label>付款方式</label>
                  <Select
                    value={currentReceipt.formData.payment_method || undefined}
                    onChange={(v) => updateFormField('payment_method', v)}
                    placeholder="请选择"
                    style={{ width: '100%' }}
                    allowClear
                    options={paymentMethodOptions}
                  />
                </div>
              </div>

              <div>
                <label>期数名称</label>
                <Input
                  value={currentReceipt.formData.installment_name}
                  onChange={(e) => updateFormField('installment_name', e.target.value)}
                  placeholder="如：定金、尾款"
                />
              </div>

              {!isIncome && (
                <div>
                  <label>收款方 <span style={{ color: '#ff4d4f' }}>*</span></label>
                  <Input
                    value={currentReceipt.formData.payee_name || ''}
                    onChange={(e) => updateFormField('payee_name', e.target.value)}
                    placeholder="请输入收款方名称"
                  />
                </div>
              )}

              <div>
                <label>备注</label>
                <TextArea
                  value={currentReceipt.formData.notes}
                  onChange={(e) => updateFormField('notes', e.target.value)}
                  rows={2}
                  placeholder="可选"
                />
              </div>
            </div>
          )}

          {/* 提交阶段 */}
          {processingPhase === 'submit' && (
            <div className="receipt-modal-analyzing">
              <LoadingOutlined className="receipt-modal-analyzing-icon" />
              <div className="receipt-modal-analyzing-text">正在提交...</div>
            </div>
          )}
        </>
      )
    }

    if (currentStep === 'summary') {
      const successCount = receipts.filter(r => r.status === 'done').length
      const errorCount = receipts.filter(r => r.status === 'error').length

      return (
        <div className="receipt-modal-summary">
          <div className="receipt-modal-summary-count">
            <span className="receipt-modal-summary-count-item success">
              <CheckCircleFilled /> 成功 {successCount} 笔
            </span>
            {errorCount > 0 && (
              <span className="receipt-modal-summary-count-item error">
                <CloseCircleFilled /> 失败 {errorCount} 笔
              </span>
            )}
          </div>

          <div className="receipt-modal-summary-list">
            {receipts.map((r, i) => (
              <div key={r.id} className="receipt-modal-summary-item">
                <div className={`receipt-modal-summary-item-status ${r.status === 'done' ? 'success' : 'error'}`}>
                  {r.status === 'done' ? <CheckCircleFilled /> : <CloseCircleFilled />}
                </div>
                <div className="receipt-modal-summary-item-info">
                  <div className="receipt-modal-summary-item-name">
                    {r.result?.installment_name || r.formData?.installment_name || `第${i + 1}张`}
                  </div>
                  <div className="receipt-modal-summary-item-detail">
                    {r.formData && `${r.formData.currency} ${r.formData.amount.toLocaleString()}`}
                  </div>
                  {r.error && (
                    <div className="receipt-modal-summary-item-error">{r.error}</div>
                  )}
                </div>
                {r.status === 'error' && (
                  <Button
                    size="small"
                    icon={<ReloadOutlined />}
                    onClick={() => handleRetry(i)}
                  >
                    重试
                  </Button>
                )}
              </div>
            ))}
          </div>
        </div>
      )
    }

    return null
  }

  // 步骤条配置
  const stepsItems = [
    { title: '上传凭证' },
    { title: currentStep === 'processing' ? `处理第 ${activeIndex + 1}/${receipts.length} 张` : '处理' },
    { title: '完成' },
  ]

  const currentStepIndex = currentStep === 'upload' ? 0 : currentStep === 'processing' ? 1 : 2

  // 底部按钮
  const renderFooter = () => {
    if (currentStep === 'upload') {
      return [
        <Button key="cancel" onClick={() => handleClose(false)}>取消</Button>,
        <Button
          key="start"
          type="primary"
          disabled={receipts.length === 0}
          onClick={handleStartProcessing}
        >
          开始处理
        </Button>,
      ]
    }

    if (currentStep === 'processing' && processingPhase === 'confirm') {
      return [
        <Button key="cancel" onClick={() => handleClose(false)}>取消</Button>,
        <Button
          key="submit"
          type="primary"
          loading={loading}
          onClick={handleSubmit}
        >
          确认并提交
        </Button>,
      ]
    }

    if (currentStep === 'summary') {
      const hasSuccess = receipts.some(r => r.status === 'done')
      return [
        <Button
          key="close"
          type="primary"
          onClick={() => handleClose(hasSuccess)}
        >
          关闭
        </Button>,
      ]
    }

    return []
  }

  return (
    <Modal
      open={open}
      onCancel={() => handleClose(false)}
      title={`录入${typeLabel}`}
      width={640}
      className="receipt-modal"
      footer={renderFooter()}
      maskClosable={false}
      destroyOnClose
    >
      {/* 合同上下文 */}
      <div className="receipt-modal-context">
        <span className="receipt-modal-context-item">
          <span className="label">合同</span>
          <span className="value">{contractNumber}</span>
        </span>
        <span>·</span>
        <span className="receipt-modal-context-item">
          <span className="label">客户</span>
          <span className="value">{customerName}</span>
        </span>
        <span>·</span>
        <span className="receipt-modal-context-item">
          <span className="label">币种</span>
          <span className="value">{contractCurrency}</span>
        </span>
      </div>

      {/* 步骤条 */}
      <Steps
        className="receipt-modal-steps"
        current={currentStepIndex}
        items={stepsItems}
        size="small"
      />

      {/* 已上传文件列表（upload 步骤） */}
      {currentStep === 'upload' && receipts.length > 0 && (
        <div style={{ marginBottom: 12 }}>
          {receipts.map((r, i) => (
            <div key={r.id} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '4px 0' }}>
              <span style={{ flex: 1, fontSize: 13 }}>{r.file.name}</span>
              <Button type="link" danger size="small" onClick={() => handleRemoveFile(i)}>删除</Button>
            </div>
          ))}
        </div>
      )}

      {/* 内容区 */}
      <div className="receipt-modal-content">
        {renderStepContent()}
      </div>
    </Modal>
  )
}
