import { useEffect, useState, useRef } from 'react'
import {
  Button, Modal, Form, Input, InputNumber, Select, Space, Upload, DatePicker,
  Spin, Alert, Tag, Radio, message,
} from 'antd'
import type { InputRef } from 'antd'
import {
  InboxOutlined, FilePdfOutlined, FileWordOutlined, FileOutlined,
  DeleteOutlined, WechatOutlined, RobotOutlined, WarningOutlined,
  UserAddOutlined, SearchOutlined,
} from '@ant-design/icons'
import dayjs from 'dayjs'
import { contractApi, type ContractAnalyzeResult, type ContractAnalyzeData, type PaymentTerm, type ContractFormPayload } from '@/services/contract'
import { customerApi } from '@/services/customer'
import { agentApi } from '@/services/agent'
import { compressImage } from '@/utils/imageCompress'
import { fmtFull } from '@/utils/moneyFormat'
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

/** 去重命中信息（用于预览页明确提示，替代一闪而过的 message） */
interface DuplicateInfo {
  contractId: number
  contractNumber: string
  title?: string
  status?: string
  totalAmount?: number
  currency?: string
  customerName?: string
}

/** 客户关联模式：三态 */
type CustomerMode = 'existing' | 'new' | 'none'

const fmtDate = (d?: string) => {
  if (!d) return '-'
  const day = dayjs(d)
  return day.isValid() ? day.format('YYYY-MM-DD') : d
}

/**
 * 合同表单录入 Modal。
 * 两步式：上传文件 → AI 分析 → 预览确认（付款计划/客户/关键字段全展示）→ 一键录入。
 * 底层存储逻辑（合同主记录 / 文件复制 / contract_data / contract_text）完全由后端处理，前端只管展示与提交。
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
  // 去重命中信息（null = 未命中 / 已处理）
  const [duplicateInfo, setDuplicateInfo] = useState<DuplicateInfo | null>(null)

  // 客户关联三态
  const [customerMode, setCustomerMode] = useState<CustomerMode>('none')
  const [customers, setCustomers] = useState<Customer[]>([])
  const [customerSearching, setCustomerSearching] = useState(false)
  const [selectedCustomerId, setSelectedCustomerId] = useState<number | undefined>()
  const [newCustomerName, setNewCustomerName] = useState('')
  const [newCustomerPhone, setNewCustomerPhone] = useState('')

  const isMountedRef = useRef(true)
  // 业务群输入框 ref：群为空时拖文件，自动聚焦引导用户先填群名
  const wechatGroupInputRef = useRef<InputRef>(null)
  // 业务群名同步到 ref，避免 drop 闭包读到旧值（setState 是异步的）
  const wechatGroupRef = useRef('')
  useEffect(() => { wechatGroupRef.current = wechatGroup }, [wechatGroup])

  useEffect(() => {
    isMountedRef.current = true
    return () => { isMountedRef.current = false }
  }, [])

  // 打开/关闭重置
  useEffect(() => {
    if (!open) return
    resetAll()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open])

  const resetAll = () => {
    setStep('upload')
    setWechatGroup('')
    setUploadedFile(null)
    setAnalyzing(false)
    setSubmitting(false)
    setDuplicateInfo(null)
    analyzeResultRef.current = null
    analyzeDataRef.current = null
    setCustomers([])
    setCustomerMode('none')
    setSelectedCustomerId(undefined)
    setNewCustomerName('')
    setNewCustomerPhone('')
    form.resetFields()
  }

  // ── 拖拽拦截：上传步骤整块区域始终阻止浏览器默认行为 ──
  // 根因：群为空时若不拦截 onDrop，浏览器会打开文件（新标签页），用户一脸懵。
  // 这里无论群是否填好，都先阻止默认；群为空则高亮+聚焦输入框引导。
  const handleDropOnStep = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    if (analyzing || uploadedFile) return  // 分析中 / 已上传：不再接受新文件
    if (!wechatGroupRef.current.trim()) {
      message.warning('请先填写业务群名称，再上传合同文件', 2.5)
      wechatGroupInputRef.current?.focus()
      // 输入框短暂红色高亮，吸引视线
      const el = wechatGroupInputRef.current?.nativeElement as HTMLElement | undefined
      if (el) {
        const input = el.querySelector('input') || el
        input.style.borderColor = 'var(--color-danger, #ff4d4f)'
        setTimeout(() => { input.style.borderColor = '' }, 1500)
      }
      return
    }
    const file = e.dataTransfer.files?.[0]
    if (file) handleFileSelect(file)
  }

  const handleDragOver = (e: React.DragEvent) => {
    // 必须 preventDefault 才能让后续 onDrop 触发（否则浏览器仍会打开文件）
    e.preventDefault()
    e.stopPropagation()
  }

  // ── 文件选择 + 上传 + 分析 ──
  const handleFileSelect = async (file: File) => {
    if (!wechatGroup.trim()) {
      message.warning('请先填写业务群名称')
      return false
    }
    try {
      const processed = await compressImage(file)
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

      setAnalyzing(true)
      const result = await contractApi.analyze(fileId)
      if (!isMountedRef.current) return

      // 去重命中：进入预览页，但顶部明确提示已有合同（不再一闪而过）
      if (result.duplicate_detected && result.existing_contract) {
        const ex = result.existing_contract
        setDuplicateInfo({
          contractId: ex.id,
          contractNumber: ex.contract_number,
          title: ex.title,
          status: ex.status,
          totalAmount: ex.total_amount,
          currency: ex.currency,
          customerName: ex.customer_name,
        })
        analyzeResultRef.current = result
        analyzeDataRef.current = result.data || null
        setAnalyzing(false)
        setStep('preview')
        message.warning('该文件已在系统中存在对应合同，请核对下方提示')
        return false
      }
      if (!result.success || !result.data) {
        setAnalyzing(false)
        setUploadedFile(null)
        message.error((result as any).error || '文件分析失败，请重试')
        return false
      }

      setDuplicateInfo(null)
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

  // 把 AI 解析结果填入可编辑表单 + 初始化客户三态
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

    // 客户三态默认值：AI 提取到乙方姓名 → 默认"新建"分支并预填姓名；否则"不关联"
    const partyBName = data.party_b?.name
    if (partyBName) {
      setCustomerMode('new')
      setNewCustomerName(partyBName)
      setNewCustomerPhone(data.party_b?.phone || '')
    } else {
      setCustomerMode('none')
    }
  }

  // ── 客户搜索（existing 模式下拉）──
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

  // ── 新建客户（new 模式）──
  const handleCreateCustomer = async (): Promise<number | undefined> => {
    if (!newCustomerName.trim()) {
      message.warning('请填写客户姓名')
      return undefined
    }
    try {
      const created = await customerApi.createOrGet({
        name: newCustomerName.trim(),
        phone: newCustomerPhone.trim() || undefined,
      })
      message.success('客户已创建/关联')
      return created.id
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '客户创建失败')
      return undefined
    }
  }

  const handleRemoveFile = () => {
    if (uploadedFile?.previewUrl) URL.revokeObjectURL(uploadedFile.previewUrl)
    setUploadedFile(null)
    analyzeResultRef.current = null
    analyzeDataRef.current = null
    setDuplicateInfo(null)
    setStep('upload')
  }

  const handleOk = async () => {
    // 去重命中：禁止重复录入
    if (duplicateInfo) {
      message.error('该文件已存在合同记录，无法重复录入。如需重新录入请先删除原合同')
      return
    }
    try {
      const values = await form.validateFields()
      if (!uploadedFile || !analyzeResultRef.current || !analyzeDataRef.current) {
        message.error('请先上传并分析合同文件')
        return
      }
      setSubmitting(true)

      // 客户关联：existing 直取 ID；new 调创建接口拿 ID；none 不传
      let customerId: number | undefined
      if (customerMode === 'existing') {
        if (!selectedCustomerId) {
          message.warning('请选择一个已有客户')
          setSubmitting(false)
          return
        }
        customerId = selectedCustomerId
      } else if (customerMode === 'new') {
        customerId = await handleCreateCustomer()
        if (!customerId) {
          setSubmitting(false)
          return
        }
      }

      const fullText = analyzeDataRef.current.full_text || undefined
      const payload: ContractFormPayload = {
        title: values.title?.trim() || undefined,
        business_type: values.business_type || undefined,
        business_description: values.business_description?.trim() || undefined,
        currency: values.currency || 'CNY',
        total_amount: values.total_amount != null ? Number(values.total_amount) : undefined,
        signed_date: values.signed_date ? values.signed_date.format('YYYY-MM-DD') : undefined,
        wechat_group: values.wechat_group?.trim() || undefined,
        customer_id: customerId,
        file_id: uploadedFile.fileId,
        contract_data: analyzeDataRef.current,
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

  const data = analyzeDataRef.current
  const paymentTerms: PaymentTerm[] = data?.payment_terms || []
  const partyA = data?.party_a
  const partyB = data?.party_b
  const validity = data?.validity_period
  const specialTerms = data?.special_terms || []

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
      centered
      maskClosable={false}
      width={760}
      footer={step === 'upload' ? (
        <Space>
          <Button onClick={() => onClose(false)}>取消</Button>
        </Space>
      ) : (
        <Space>
          <Button onClick={handleRemoveFile} disabled={submitting}>重新上传</Button>
          <Button
            type="primary"
            onClick={handleOk}
            loading={submitting}
            disabled={!!duplicateInfo}
            title={duplicateInfo ? '该文件已存在合同，无法重复录入' : undefined}
          >
            确认录入
          </Button>
        </Space>
      )}
    >
      {step === 'upload' ? (
        <div
          style={{ display: 'flex', flexDirection: 'column', gap: 16, minHeight: 320 }}
          onDrop={handleDropOnStep}
          onDragOver={handleDragOver}
        >
          <Alert
            type="info" showIcon
            message="上传合同文件，AI 自动分析关键字段，预览确认后一键录入"
          />
          <Form layout="vertical">
            <Form.Item
              label={<span><WechatOutlined style={{ marginRight: 6 }} />业务群名称</span>}
              required
              validateStatus={wechatGroup.trim() ? 'success' : ''}
            >
              <Input
                ref={wechatGroupInputRef}
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
                >
                  <p className="ant-upload-drag-icon"><InboxOutlined style={{ fontSize: 28 }} /></p>
                  <p className="ant-upload-text" style={{ fontSize: 13 }}>
                    点击或拖拽合同文件上传
                  </p>
                  <p className="ant-upload-hint" style={{ fontSize: 11 }}>
                    支持 JPG / PNG / PDF / Word · 上传后自动分析
                    {!wechatGroup.trim() && (
                      <span style={{ color: 'var(--color-danger, #ff4d4f)' }}>（请先填写上方业务群名称）</span>
                    )}
                  </p>
                </Upload.Dragger>
              )}
            </Form.Item>
          </Form>
        </div>
      ) : (
        <>
          {/* 去重命中明确提示卡片（替代一闪而过的 message） */}
          {duplicateInfo && (
            <Alert
              type="warning" showIcon
              icon={<WarningOutlined />}
              style={{ marginBottom: 16 }}
              message="该文件已在系统中存在对应合同"
              description={
                <div style={{ fontSize: 13 }}>
                  <div>合同编号：<b>{duplicateInfo.contractNumber}</b></div>
                  {duplicateInfo.title && <div>标题：{duplicateInfo.title}</div>}
                  <div>
                    金额：{fmtFull(duplicateInfo.totalAmount, duplicateInfo.currency || '')}
                    {duplicateInfo.customerName ? ` · 客户：${duplicateInfo.customerName}` : ''}
                    {duplicateInfo.status ? ` · 状态：${duplicateInfo.status}` : ''}
                  </div>
                  <div style={{ marginTop: 6, color: 'var(--color-danger, #ff4d4f)' }}>
                    无法重复录入。如需重新录入，请先到合同管理删除原合同。
                  </div>
                </div>
              }
            />
          )}

          {!duplicateInfo && (
            <Alert
              type="success" showIcon
              style={{ marginBottom: 16 }}
              message="AI 已完成分析，请核对以下字段（可修改）后确认录入"
            />
          )}

          <Form form={form} layout="vertical" requiredMark="optional">
            {/* 文件来源摘要 */}
            {uploadedFile && (
              <div style={{ marginBottom: 16, padding: '8px 12px', background: 'var(--bg-subtle, #fafafa)', borderRadius: 6, fontSize: 13, color: 'var(--text-secondary, #666)' }}>
                来源文件：{uploadedFile.fileName}
                {analyzeResultRef.current?.confidence != null && (
                  <span style={{ marginLeft: 12 }}>
                    AI 置信度：<b>{Math.round((analyzeResultRef.current.confidence) * 100)}%</b>
                    {analyzeResultRef.current.confidence < 0.85 && (
                      <Tag color="orange" style={{ marginLeft: 8 }}>较低，请重点核对</Tag>
                    )}
                  </span>
                )}
              </div>
            )}

            <div style={{ display: 'flex', gap: 12 }}>
              <Form.Item name="title" label="合同标题" style={{ flex: 1 }}>
                <Input placeholder="如：车辆买卖合同" maxLength={500} />
              </Form.Item>
              <Form.Item name="signed_date" label="签订日期" style={{ width: 200 }}>
                <DatePicker style={{ width: '100%' }} />
              </Form.Item>
            </div>

            {/* AI 提取的合同编号（只读展示，便于用户核对，不入库——后端自动生成新编号） */}
            {data?.contract_number && (
              <Form.Item label="原合同编号（仅供参考，系统将自动生成新编号）">
                <Input value={data.contract_number} disabled />
              </Form.Item>
            )}

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

            {/* ── 客户关联（三态选择器）── */}
            <Form.Item label="关联客户">
              <Radio.Group
                value={customerMode}
                onChange={e => setCustomerMode(e.target.value)}
                style={{ marginBottom: 8 }}
              >
                <Radio.Button value="existing"><SearchOutlined /> 搜索现有</Radio.Button>
                <Radio.Button value="new"><UserAddOutlined /> 新建客户</Radio.Button>
                <Radio.Button value="none">不关联</Radio.Button>
              </Radio.Group>

              {customerMode === 'existing' && (
                <Select
                  showSearch
                  allowClear
                  placeholder="输入客户姓名/电话搜索"
                  filterOption={false}
                  onSearch={searchCustomers}
                  loading={customerSearching}
                  value={selectedCustomerId}
                  onChange={setSelectedCustomerId}
                  style={{ width: '100%' }}
                  notFoundContent={customerSearching ? '搜索中...' : '输入关键词搜索'}
                  options={customers.map(c => ({
                    label: `${c.name}${c.phone ? ' · ' + c.phone : ''}`,
                    value: c.id,
                  }))}
                />
              )}
              {customerMode === 'new' && (
                <div style={{ display: 'flex', gap: 8 }}>
                  <Input
                    value={newCustomerName}
                    onChange={e => setNewCustomerName(e.target.value)}
                    placeholder="客户姓名（默认带入 AI 识别的乙方）"
                    maxLength={200}
                    style={{ flex: 2 }}
                  />
                  <Input
                    value={newCustomerPhone}
                    onChange={e => setNewCustomerPhone(e.target.value)}
                    placeholder="电话（选填）"
                    maxLength={20}
                    style={{ flex: 1 }}
                  />
                </div>
              )}
              {customerMode === 'none' && (
                <div style={{ fontSize: 12, color: 'var(--text-tertiary, #999)' }}>
                  暂不关联客户，可后续到客户管理补关联
                </div>
              )}
            </Form.Item>

            {/* ── AI 提取的只读参考信息（不入库主字段，仅展示供核对）── */}
            {(partyB || partyA) && (
              <div style={{ marginBottom: 16, padding: 12, border: '1px solid var(--border-default, #eee)', borderRadius: 6, background: 'var(--bg-subtle, #fafafa)' }}>
                <div style={{ fontWeight: 500, marginBottom: 8, fontSize: 13 }}>AI 提取的甲乙方信息（参考）</div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px 24px', fontSize: 13 }}>
                  {partyB?.name && <div>乙方（客户）：{partyB.name}</div>}
                  {partyB?.id_info && <div>证件：{partyB.id_info}</div>}
                  {partyB?.phone && <div>电话：{partyB.phone}</div>}
                  {partyA?.name && <div>甲方：{partyA.name}</div>}
                  {partyA?.contact && <div>甲方联系：{partyA.contact}</div>}
                </div>
              </div>
            )}

            {/* ── 付款计划明细（关键字段，完整展示）── */}
            {paymentTerms.length > 0 && (
              <div style={{ marginBottom: 16 }}>
                <div style={{ fontWeight: 500, marginBottom: 8, fontSize: 13 }}>
                  付款计划（共 {paymentTerms.length} 期，已随合同保存；实际收款请到合同卡片录入）
                </div>
                <div style={{ border: '1px solid var(--border-default, #eee)', borderRadius: 6, overflow: 'hidden' }}>
                  {paymentTerms.map((term, i) => (
                    <div
                      key={i}
                      style={{
                        display: 'grid',
                        gridTemplateColumns: '1fr auto auto',
                        gap: 12,
                        padding: '8px 12px',
                        fontSize: 13,
                        borderBottom: i < paymentTerms.length - 1 ? '1px solid var(--border-default, #f0f0f0)' : 'none',
                        alignItems: 'center',
                      }}
                    >
                      <div>
                        <div>{term.name || `第 ${i + 1} 期`}</div>
                        {term.condition && (
                          <div style={{ fontSize: 11, color: 'var(--text-tertiary, #999)' }}>{term.condition}</div>
                        )}
                      </div>
                      <div style={{ fontWeight: 500, color: 'var(--color-success, #52c41a)' }}>
                        {fmtFull(term.amount, term.currency || data?.currency || '')}
                      </div>
                      <div style={{ fontSize: 12, color: 'var(--text-secondary, #666)', minWidth: 96, textAlign: 'right' }}>
                        {fmtDate(term.due_date)}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* ── 有效期 + 特殊条款（只读参考）── */}
            {(validity?.start_date || validity?.end_date || specialTerms.length > 0) && (
              <div style={{ marginBottom: 16, padding: 12, border: '1px solid var(--border-default, #eee)', borderRadius: 6, background: 'var(--bg-subtle, #fafafa)' }}>
                <div style={{ fontWeight: 500, marginBottom: 8, fontSize: 13 }}>其他条款（参考）</div>
                <div style={{ fontSize: 13, lineHeight: 1.8 }}>
                  {(validity?.start_date || validity?.end_date) && (
                    <div>合同有效期：{fmtDate(validity?.start_date)} ~ {fmtDate(validity?.end_date)}</div>
                  )}
                  {specialTerms.map((t, i) => (
                    <div key={i}>· {t}</div>
                  ))}
                </div>
              </div>
            )}
          </Form>
        </>
      )}
    </Modal>
  )
}
