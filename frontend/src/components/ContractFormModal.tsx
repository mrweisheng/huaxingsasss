import { useEffect, useState, useRef } from 'react'
import {
  Button, Modal, Form, Input, InputNumber, Select, Space, Upload, DatePicker,
  Spin, Alert, Tag, message,
} from 'antd'
import {
  InboxOutlined, FilePdfOutlined, FileWordOutlined, FileOutlined,
  DeleteOutlined, WechatOutlined, RobotOutlined, WarningOutlined,
} from '@ant-design/icons'
import dayjs from 'dayjs'
import { contractApi, type ContractAnalyzeResult, type ContractAnalyzeData, type ContractFormPayload } from '@/services/contract'
import { customerApi } from '@/services/customer'
import { agentApi } from '@/services/agent'
import { compressImage } from '@/utils/imageCompress'
import type { Customer } from '@/types'

interface Props {
  open: boolean
  onClose: (created: boolean) => void
}

type Step = 'upload' | 'preview'

interface UploadedFile {
  fileId: string
  fileName: string
  fileType: string   // image / pdf / word / excel / text
  previewUrl?: string
}

// 业务类型选项：与后端 BusinessType 标准值对齐
const BUSINESS_TYPE_OPTIONS = [
  { label: '车辆买卖', value: '车辆买卖' },
  { label: '两地牌过户', value: '两地牌过户' },
  { label: '年检保险', value: '年检保险' },
  { label: '其他', value: '其他' },
]

const CURRENCY_OPTIONS = [
  { label: '人民币 CNY', value: 'CNY' },
  { label: '港币 HKD', value: 'HKD' },
]

const ACCEPT = 'image/*,.heic,.heif,.pdf,.doc,.docx,.xls,.xlsx'

/**
 * 合同表单录入 Modal（与 Agent 对话通道并存，互不干扰）。
 * 两步式：上传文件 → AI 分析 → 预览确认（字段可改）→ 一键录入。
 * 对应 .mimocode/plans/1782377932485-sunny-knight.md。
 */
export default function ContractFormModal({ open, onClose }: Props) {
  const [form] = Form.useForm()
  const [step, setStep] = useState<Step>('upload')
  const [wechatGroup, setWechatGroup] = useState('')
  const [uploadedFile, setUploadedFile] = useState<UploadedFile | null>(null)
  const [analyzing, setAnalyzing] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  // AI 原始解析结果（保留 full_text 等用于最终提交，不进表单）
  const analyzeResultRef = useRef<ContractAnalyzeResult | null>(null)
  const analyzeDataRef = useRef<ContractAnalyzeData | null>(null)
  // 客户下拉
  const [customers, setCustomers] = useState<Customer[]>([])
  const [customerSearching, setCustomerSearching] = useState(false)
  const isMountedRef = useRef(true)

  useEffect(() => {
    isMountedRef.current = true
    return () => { isMountedRef.current = false }
  }, [])

  // 打开/关闭重置
  useEffect(() => {
    if (!open) return
    setStep('upload')
    setWechatGroup('')
    setUploadedFile(null)
    setAnalyzing(false)
    setSubmitting(false)
    analyzeResultRef.current = null
    analyzeDataRef.current = null
    setCustomers([])
    form.resetFields()
  }, [open, form])

  // ── 文件选择 + 上传 + 分析 ──
  const handleFileSelect = async (file: File) => {
    if (!wechatGroup.trim()) {
      message.warning('请先填写业务群名称')
      return false
    }
    try {
      // 1. 压缩图片（非图片原样返回）
      const processed = await compressImage(file)
      // 2. 上传到 agent 目录（复用现有端点）
      const isImage = file.type.startsWith('image/')
      const previewUrl = isImage ? URL.createObjectURL(file) : undefined
      const res = await agentApi.uploadFile(processed)
      const fileId = res.data.fileId
      setUploadedFile({
        fileId,
        fileName: file.name,
        fileType: isImage ? 'image'
          : /\.pdf$/i.test(file.name) ? 'pdf'
          : /\.(docx?|)$/i.test(file.name) ? 'word'
          : 'text',
        previewUrl,
      })

      // 3. 调 analyze 触发 AI 分析（图片型慢，给 loading）
      setAnalyzing(true)
      const result = await contractApi.analyze(fileId)
      if (!isMountedRef.current) return

      // 去重命中：终止流程，提示已存在
      if (result.duplicate_detected && result.existing_contract) {
        const ex = result.existing_contract
        setAnalyzing(false)
        setUploadedFile(null)
        message.warning(`该文件已存在合同记录（编号 ${ex.contract_number}）`, 6)
        return false
      }
      if (!result.success || !result.data) {
        setAnalyzing(false)
        setUploadedFile(null)
        message.error((result as any).error || '文件分析失败，请重试或换用对话录入')
        return false
      }

      analyzeResultRef.current = result
      analyzeDataRef.current = result.data
      fillFormFromAnalyze(result.data)
      setAnalyzing(false)
      setStep('preview')
    } catch (e: any) {
      if (!isMountedRef.current) return
      setAnalyzing(false)
      setUploadedFile(null)
      message.error(e?.response?.data?.detail || e?.message || '上传/分析失败')
    }
    return false
  }

  // 把 AI 解析结果填入可编辑表单
  const fillFormFromAnalyze = (data: ContractAnalyzeData) => {
    const v: Record<string, any> = {}
    if (data.title) v.title = data.title
    if (data.currency) v.currency = data.currency
    else v.currency = 'CNY'
    if (data.total_amount != null) v.total_amount = data.total_amount
    if (data.signed_date) {
      const d = dayjs(data.signed_date)
      if (d.isValid()) v.signed_date = d
    }
    if (data.business_type) v.business_type = data.business_type
    if (data.business_description) v.business_description = data.business_description
    v.wechat_group = wechatGroup.trim()
    form.setFieldsValue(v)
  }

  // ── 客户搜索（下拉）──
  const searchCustomers = async (keyword: string) => {
    if (!keyword.trim()) { setCustomers([]); return }
    setCustomerSearching(true)
    try {
      const resp: any = await customerApi.getList({ keyword: keyword.trim(), per_page: 20 })
      const page = resp?.data ?? resp
      setCustomers(Array.isArray(page?.items) ? page.items : [])
    } catch {
      setCustomers([])
    } finally {
      setCustomerSearching(false)
    }
  }

  const handleRemoveFile = () => {
    if (uploadedFile?.previewUrl) URL.revokeObjectURL(uploadedFile.previewUrl)
    setUploadedFile(null)
    analyzeResultRef.current = null
    analyzeDataRef.current = null
    setStep('upload')
  }

  const handleOk = async () => {
    try {
      const values = await form.validateFields()
      if (!uploadedFile || !analyzeResultRef.current) {
        message.error('请先上传并分析合同文件')
        return
      }
      setSubmitting(true)

      const fullText = analyzeDataRef.current?.full_text || analyzeDataRef.current?.special_terms || undefined
      const payload: ContractFormPayload = {
        title: values.title?.trim() || undefined,
        business_type: values.business_type || undefined,
        business_description: values.business_description?.trim() || undefined,
        currency: values.currency || 'CNY',
        total_amount: values.total_amount != null ? Number(values.total_amount) : undefined,
        signed_date: values.signed_date ? values.signed_date.format('YYYY-MM-DD') : undefined,
        wechat_group: values.wechat_group?.trim() || undefined,
        customer_id: values.customer_id || undefined,
        file_id: uploadedFile.fileId,
        contract_data: analyzeDataRef.current || {},
        contract_text: fullText,
        confidence: analyzeResultRef.current.confidence,
      }
      await contractApi.createViaForm(payload)
      message.success('合同已录入')
      onClose(true)
    } catch (e: any) {
      if (e?.errorFields) return  // antd 校验失败
      const detail = e?.response?.data?.detail || e?.message || '录入失败'
      message.error(detail)
    } finally {
      setSubmitting(false)
    }
  }

  const handleBack = () => {
    handleRemoveFile()
  }

  return (
    <Modal
      title={
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
          <RobotOutlined style={{ color: 'var(--brand-gold, #d4a437)' }} />
          录入合同
          <Tag color="blue" style={{ marginLeft: 8, fontSize: 12 }}>表单模式</Tag>
        </span>
      }
      open={open}
      onCancel={() => onClose(false)}
      destroyOnClose
      maskClosable={false}
      width={720}
      footer={step === 'upload' ? (
        <Space>
          <Button onClick={() => onClose(false)}>取消</Button>
        </Space>
      ) : (
        <Space>
          <Button onClick={handleBack} disabled={submitting}>重新上传</Button>
          <Button type="primary" onClick={handleOk} loading={submitting}>确认录入</Button>
        </Space>
      )}
    >
      {step === 'upload' ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16, minHeight: 320 }}>
          <Alert
            type="info" showIcon
            message="表单模式：上传文件后 AI 自动分析，预览确认后一键录入"
            description="也可使用「AI 对话录入」进行多轮交互。"
          />
          <Form layout="vertical">
            <Form.Item
              label={<span><WechatOutlined style={{ marginRight: 6 }} />业务群名称</span>}
              required
            >
              <Input
                value={wechatGroup}
                onChange={e => setWechatGroup(e.target.value)}
                placeholder="每笔业务必须关联业务群，请填写微信群名称"
                maxLength={200}
              />
            </Form.Item>

            <Form.Item label="合同文件" required>
              {analyzing ? (
                <div style={{ textAlign: 'center', padding: '40px 0' }}>
                  <Spin tip="AI 正在分析合同内容，图片型文件较慢（约 10-30 秒）..." size="large">
                    <div style={{ padding: 24 }} />
                  </Spin>
                </div>
              ) : uploadedFile ? (
                <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: 12, border: '1px solid var(--border-default, #d9d9d9)', borderRadius: 8 }}>
                  {uploadedFile.previewUrl ? (
                    <img src={uploadedFile.previewUrl} alt={uploadedFile.fileName} style={{ width: 40, height: 40, objectFit: 'cover', borderRadius: 6 }} />
                  ) : uploadedFile.fileType === 'pdf' ? (
                    <FilePdfOutlined style={{ fontSize: 28, color: '#ff4d4f' }} />
                  ) : uploadedFile.fileType === 'word' ? (
                    <FileWordOutlined style={{ fontSize: 28, color: '#1677ff' }} />
                  ) : (
                    <FileOutlined style={{ fontSize: 28 }} />
                  )}
                  <span style={{ flex: 1, fontWeight: 500 }}>{uploadedFile.fileName}</span>
                  <Tag color="green">已上传</Tag>
                  <a onClick={handleRemoveFile}><DeleteOutlined /></a>
                </div>
              ) : (
                <Upload.Dragger
                  accept={ACCEPT}
                  maxCount={1}
                  showUploadList={false}
                  beforeUpload={handleFileSelect}
                  disabled={!wechatGroup.trim()}
                >
                  <p className="ant-upload-drag-icon"><InboxOutlined style={{ fontSize: 28 }} /></p>
                  <p className="ant-upload-text" style={{ fontSize: 13 }}>
                    {wechatGroup.trim() ? '点击或拖拽合同文件上传' : '请先填写业务群名称'}
                  </p>
                  <p className="ant-upload-hint" style={{ fontSize: 11 }}>支持 JPG / PNG / PDF / Word · 上传后自动分析</p>
                </Upload.Dragger>
              )}
            </Form.Item>
          </Form>
        </div>
      ) : (
        <Form form={form} layout="vertical" requiredMark="optional">
          <Alert
            type="success" showIcon
            style={{ marginBottom: 16 }}
            message="AI 已完成分析，请核对以下字段（可修改）后确认录入"
          />

          <div style={{ display: 'flex', gap: 12 }}>
            <Form.Item name="title" label="合同标题" style={{ flex: 1 }}>
              <Input placeholder="如：车辆买卖合同" maxLength={500} />
            </Form.Item>
            <Form.Item name="signed_date" label="签订日期" style={{ width: 200 }}>
              <DatePicker style={{ width: '100%' }} />
            </Form.Item>
          </div>

          <div style={{ display: 'flex', gap: 12 }}>
            <Form.Item
              name="total_amount" label="合同金额" rules={[{ required: true, message: '请输入合同金额' }]}
              style={{ flex: 1 }}
            >
              <InputNumber style={{ width: '100%' }} min={0} precision={2} placeholder="0.00" />
            </Form.Item>
            <Form.Item name="currency" label="币种" rules={[{ required: true }]} style={{ width: 160 }}>
              <Select options={CURRENCY_OPTIONS} />
            </Form.Item>
          </div>

          <div style={{ display: 'flex', gap: 12 }}>
            <Form.Item name="business_type" label="业务类型" style={{ flex: 1 }}>
              <Select options={BUSINESS_TYPE_OPTIONS} allowClear placeholder="选择业务类型" />
            </Form.Item>
            <Form.Item name="wechat_group" label="业务群" rules={[{ required: true, message: '请填写业务群名称' }]} style={{ flex: 1 }}>
              <Input maxLength={200} />
            </Form.Item>
          </div>

          <Form.Item name="business_description" label="业务描述">
            <Input maxLength={200} placeholder="如：深圳湾粤Z牌过户" />
          </Form.Item>

          <Form.Item label="关联客户（可选）">
            <Select
              showSearch
              allowClear
              placeholder="搜索客户名称（可留空，后续再关联）"
              filterOption={false}
              onSearch={searchCustomers}
              loading={customerSearching}
              notFoundContent={customerSearching ? '搜索中...' : '输入关键词搜索'}
              options={customers.map(c => ({ label: c.name, value: c.id }))}
            />
          </Form.Item>

          {analyzeDataRef.current?.payment_terms && analyzeDataRef.current.payment_terms.length > 0 && (
            <Alert
              type="info" showIcon
              style={{ marginBottom: 8 }}
              message={`AI 识别到 ${analyzeDataRef.current.payment_terms.length} 期付款计划（已保存，付款记录请到合同卡片录入）`}
            />
          )}

          {analyzeResultRef.current?.confidence != null && analyzeResultRef.current.confidence < 0.85 && (
            <Alert
              type="warning" showIcon
              icon={<WarningOutlined />}
              message={`AI 解析置信度较低（${Math.round((analyzeResultRef.current.confidence) * 100)}%），请重点核对金额与日期`}
            />
          )}
        </Form>
      )}
    </Modal>
  )
}
