import { useState, useCallback } from 'react'
import {
  Modal, Steps, Button, Upload, Input, Select, InputNumber,
  DatePicker, Form, Spin, Alert, Tag, Divider, Space, message, Card,
} from 'antd'
import {
  InboxOutlined, ArrowLeftOutlined,
  ArrowRightOutlined, CheckOutlined, WarningOutlined,
  UserOutlined, PlusOutlined, FileTextOutlined,
} from '@ant-design/icons'
import dayjs from 'dayjs'
import { agentApi } from '@/services/agent'
import { contractApi } from '@/services/contract'
import { customerApi } from '@/services/customer'
import type { Customer } from '@/types'

const { Dragger } = Upload
const { TextArea } = Input

interface Props {
  open: boolean
  onClose: () => void
}

/** 向导步骤索引 */
const STEP_UPLOAD = 0
const STEP_ANALYSIS = 1
const STEP_CUSTOMER = 2
const STEP_CONFIRM = 3

const BUSINESS_TYPES = [
  { label: '车辆买卖', value: '车辆买卖' },
  { label: '两地牌过户', value: '两地牌过户' },
  { label: '年检保险', value: '年检保险' },
  { label: '其他', value: '其他' },
]

const CURRENCIES = [
  { label: '人民币 (CNY)', value: 'CNY' },
  { label: '港币 (HKD)', value: 'HKD' },
  { label: '美元 (USD)', value: 'USD' },
]

export default function ContractUploadWizard({ open, onClose }: Props) {
  const [current, setCurrent] = useState(STEP_UPLOAD)
  const [loading, setLoading] = useState(false)

  // Step 1: 上传
  const [uploadedFile, setUploadedFile] = useState<File | null>(null)
  const [fileId, setFileId] = useState<string | null>(null)

  // Step 2: 分析结果
  const [analysisResult, setAnalysisResult] = useState<any>(null)
  const [duplicateInfo, setDuplicateInfo] = useState<any>(null)

  // Step 3: 客户
  const [selectedCustomerId, setSelectedCustomerId] = useState<number | null>(null)
  const [customers, setCustomers] = useState<Customer[]>([])
  const [searchingCustomers, setSearchingCustomers] = useState(false)
  const [showNewCustomerForm, setShowNewCustomerForm] = useState(false)
  const [newCustomerForm] = Form.useForm()

  // Step 4: 确认数据
  const [confirmForm] = Form.useForm()

  // ─── 重置状态 ───
  const reset = useCallback(() => {
    setCurrent(STEP_UPLOAD)
    setLoading(false)
    setUploadedFile(null)
    setFileId(null)
    setAnalysisResult(null)
    setDuplicateInfo(null)
    setSelectedCustomerId(null)
    setCustomers([])
    setSearchingCustomers(false)
    setShowNewCustomerForm(false)
    newCustomerForm.resetFields()
    confirmForm.resetFields()
  }, [newCustomerForm, confirmForm])

  const handleClose = () => { reset(); onClose() }

  // ─── Step 1: 上传文件 ───
  const handleUpload = async (file: File) => {
    setLoading(true)
    try {
      const res = await agentApi.uploadFile(file)
      setFileId(res.data.fileId)
      setUploadedFile(file)
      setCurrent(STEP_ANALYSIS)
    } catch (err: any) {
      message.error(err?.response?.data?.detail || '文件上传失败')
    } finally {
      setLoading(false)
    }
    return false // 阻止 antd 自动上传
  }

  // ─── Step 2: AI 分析（进入时自动触发） ───
  const runAnalysis = useCallback(async () => {
    if (!fileId) return
    setLoading(true)
    setDuplicateInfo(null)
    try {
      const res = await contractApi.analyzeFile(fileId, uploadedFile?.name)
      const data = res.data
      if (data.duplicate_detected) {
        setDuplicateInfo(data.existing_contract)
        setLoading(false)
        return
      }
      setAnalysisResult(data)
      setLoading(false)
      // 自动搜索客户
      await searchCustomers(data.data)
      setCurrent(STEP_CUSTOMER)
    } catch (err: any) {
      message.error(err?.response?.data?.detail || 'AI 分析失败')
      setLoading(false)
    }
  }, [fileId, uploadedFile])

  // ─── Step 3: 搜索/创建客户 ───
  const searchCustomers = async (analysisData?: any) => {
    setSearchingCustomers(true)
    try {
      // 从分析结果中提取候选名字
      const names: string[] = []
      if (analysisData?.party_b?.name) names.push(analysisData.party_b.name)
      if (analysisData?.party_a?.name) names.push(analysisData.party_a.name)
      const keyword = names[0] || ''
      const res = await customerApi.getList({ keyword, per_page: 20 })
      setCustomers(res.items || [])
    } catch {
      setCustomers([])
    } finally {
      setSearchingCustomers(false)
    }
  }

  const handleCreateCustomer = async () => {
    try {
      const values = await newCustomerForm.validateFields()
      const customer = await customerApi.create(values)
      setSelectedCustomerId(customer.id)
      message.success('客户创建成功')
      setShowNewCustomerForm(false)
    } catch (err: any) {
      if (err?.response?.data?.detail) {
        message.error(err.response.data.detail)
      }
    }
  }

  // ─── Step 4: 填充表单 ───
  const fillConfirmForm = useCallback(() => {
    if (!analysisResult?.data) return
    const d = analysisResult.data
    const validity = d.validity_period || {}

    confirmForm.setFieldsValue({
      title: d.title || uploadedFile?.name || '',
      business_type: d.business_type || undefined,
      business_description: d.business_description || '',
      currency: d.currency || 'CNY',
      total_amount: d.total_amount || 0,
      signed_date: d.signed_date ? dayjs(d.signed_date) : undefined,
      start_date: validity.start_date ? dayjs(validity.start_date) : undefined,
      end_date: validity.end_date ? dayjs(validity.end_date) : undefined,
      wechat_group: d.wechat_group || '',
      payment_terms: (d.payment_terms || []).map((t: any) => ({
        name: t.name || '',
        amount: t.amount || 0,
        due_date: t.due_date || '',
        condition: t.condition || '',
        is_paid: t.is_paid || false,
      })),
    })
  }, [analysisResult, uploadedFile, confirmForm])

  // ─── 提交创建合同 ───
  const handleSubmit = async () => {
    try {
      const values = await confirmForm.validateFields()
      if (!selectedCustomerId) {
        message.error('请先选择或创建客户')
        return
      }

      setLoading(true)
      const paymentTerms = (values.payment_terms || []).map((t: any) => ({
        name: t.name,
        amount: t.amount,
        due_date: t.due_date,
        condition: t.condition,
        is_paid: t.is_paid,
      }))

      const payload = {
        file_id: fileId,
        file_name: uploadedFile?.name,
        customer_id: selectedCustomerId,
        title: values.title,
        business_type: values.business_type,
        business_description: values.business_description,
        currency: values.currency,
        total_amount: values.total_amount,
        signed_date: values.signed_date?.format('YYYY-MM-DD') || null,
        start_date: values.start_date?.format('YYYY-MM-DD') || null,
        end_date: values.end_date?.format('YYYY-MM-DD') || null,
        wechat_group: values.wechat_group,
        payment_terms: paymentTerms,
        analysis_data: analysisResult?.data || {},
        full_text: analysisResult?.data?.full_text || '',
        confidence: analysisResult?.data?.confidence || null,
        remarks: values.remarks,
      }

      await contractApi.createFromAnalysis(payload)
      message.success('合同创建成功')
      handleClose()
    } catch (err: any) {
      if (err?.errorFields) return // 表单验证错误
      message.error(err?.response?.data?.detail || '创建合同失败')
    } finally {
      setLoading(false)
    }
  }

  // ─── Step 导航逻辑 ───
  const goNext = () => {
    if (current === STEP_UPLOAD) {
      // 上传步骤由 handleUpload 处理跳转
    } else if (current === STEP_ANALYSIS) {
      runAnalysis()
    } else if (current === STEP_CUSTOMER) {
      if (!selectedCustomerId) {
        message.warning('请选择或创建客户')
        return
      }
      fillConfirmForm()
      setCurrent(STEP_CONFIRM)
    }
  }

  const goPrev = () => {
    if (current > STEP_UPLOAD) setCurrent(current - 1)
  }

  const canGoNext = () => {
    if (current === STEP_UPLOAD) return !!fileId
    if (current === STEP_ANALYSIS) return true
    if (current === STEP_CUSTOMER) return !!selectedCustomerId
    return false
  }

  const confidenceValue = analysisResult?.data?.confidence
  const confidenceColor = confidenceValue == null ? 'default'
    : confidenceValue >= 0.85 ? 'green'
    : confidenceValue >= 0.6 ? 'orange' : 'red'
  const confidenceLabel = confidenceValue == null ? '未知'
    : `${Math.round(confidenceValue * 100)}%`

  return (
    <Modal
      title="上传合同"
      open={open}
      onCancel={handleClose}
      width={720}
      footer={null}
      destroyOnClose
      maskClosable={false}
    >
      <Steps
        current={current}
        style={{ marginBottom: 24 }}
        items={[
          { title: '上传文件' },
          { title: 'AI 分析' },
          { title: '关联客户' },
          { title: '确认创建' },
        ]}
      />

      {/* ─── Step 1: 上传文件 ─── */}
      {current === STEP_UPLOAD && (
        <div style={{ textAlign: 'center', padding: '24px 0' }}>
          <Dragger
            accept="image/jpeg,image/png,image/jpg,.pdf,.docx,.xlsx"
            showUploadList={false}
            beforeUpload={handleUpload}
            disabled={loading}
            style={{ padding: '32px 16px' }}
          >
            <p className="ant-upload-drag-icon"><InboxOutlined style={{ fontSize: 48, color: '#1677ff' }} /></p>
            <p className="ant-upload-text">点击或拖拽文件到此处上传</p>
            <p className="ant-upload-hint">支持 JPG、PNG、PDF、Word、Excel 格式</p>
          </Dragger>
        </div>
      )}

      {/* ─── Step 2: AI 分析 ─── */}
      {current === STEP_ANALYSIS && (
        <div style={{ textAlign: 'center', padding: '40px 0' }}>
          {loading ? (
            <>
              <Spin size="large" />
              <p style={{ marginTop: 16, color: '#666' }}>AI 正在分析合同内容，请稍候...</p>
            </>
          ) : duplicateInfo ? (
            <div>
              <Alert
                type="warning"
                showIcon
                icon={<WarningOutlined />}
                message="检测到重复合同"
                description={
                  <div>
                    <p>该文件已在系统中存在对应的合同记录：</p>
                    <p>编号：<strong>{duplicateInfo.contract_number}</strong> | 标题：{duplicateInfo.title || '无'}</p>
                    <p>金额：{duplicateInfo.currency} {duplicateInfo.total_amount} | 状态：{duplicateInfo.status}</p>
                    {duplicateInfo.customer_name && <p>客户：{duplicateInfo.customer_name}</p>}
                  </div>
                }
                style={{ marginBottom: 16, textAlign: 'left' }}
              />
              <Space>
                <Button onClick={handleClose}>取消</Button>
                <Button
                  danger
                  onClick={() => {
                    setDuplicateInfo(null)
                    // 强制继续：重新分析（重复检测在 analyze_file 中已完成，
                    // 但这里让用户可以忽略重复警告继续）
                    runAnalysis()
                  }}
                >
                  仍然创建
                </Button>
              </Space>
            </div>
          ) : (
            <Button type="primary" onClick={runAnalysis}>
              开始 AI 分析
            </Button>
          )}
        </div>
      )}

      {/* ─── Step 3: 客户选择/创建 ─── */}
      {current === STEP_CUSTOMER && (
        <div>
          <div style={{ marginBottom: 16 }}>
            <h4 style={{ marginBottom: 8 }}>
              <UserOutlined style={{ marginRight: 4 }} />
              AI 识别到的客户信息
            </h4>
            <Card size="small" style={{ background: '#fafafa' }}>
              {analysisResult?.data?.party_b ? (
                <div>
                  <p><strong>乙方（客户）：</strong>{analysisResult.data.party_b.name || '未识别'}</p>
                  {analysisResult.data.party_b.phone && <p><strong>电话：</strong>{analysisResult.data.party_b.phone}</p>}
                  {analysisResult.data.party_b.id_number && <p><strong>证件号：</strong>{analysisResult.data.party_b.id_number}</p>}
                </div>
              ) : (
                <p style={{ color: '#999' }}>未识别到客户信息</p>
              )}
            </Card>
          </div>

          <Divider orientation="left" plain>选择已有客户</Divider>
          {searchingCustomers ? <Spin /> : (
            customers.length > 0 ? (
              <div style={{ maxHeight: 200, overflowY: 'auto', marginBottom: 16 }}>
                {customers.map(c => (
                  <Card
                    key={c.id}
                    size="small"
                    hoverable
                    style={{
                      marginBottom: 8,
                      border: selectedCustomerId === c.id ? '2px solid #1677ff' : undefined,
                      cursor: 'pointer',
                    }}
                    onClick={() => setSelectedCustomerId(c.id)}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                      <span><strong>{c.name}</strong></span>
                      {selectedCustomerId === c.id && <Tag color="blue">已选择</Tag>}
                    </div>
                    <div style={{ color: '#888', fontSize: 12 }}>
                      {c.phone && <span style={{ marginRight: 12 }}>电话: {c.phone}</span>}
                      {c.wechat_group_name && <span>微信: {c.wechat_group_name}</span>}
                    </div>
                  </Card>
                ))}
              </div>
            ) : (
              <p style={{ color: '#999', marginBottom: 16 }}>未找到匹配的客户</p>
            )
          )}

          <Divider orientation="left" plain>
            <Button
              type="link"
              size="small"
              icon={<PlusOutlined />}
              onClick={() => setShowNewCustomerForm(!showNewCustomerForm)}
            >
              {showNewCustomerForm ? '收起新建表单' : '创建新客户'}
            </Button>
          </Divider>

          {showNewCustomerForm && (
            <Card size="small" style={{ marginBottom: 16 }}>
              <Form
                form={newCustomerForm}
                layout="vertical"
                size="small"
                initialValues={{
                  name: analysisResult?.data?.party_b?.name || '',
                  phone: analysisResult?.data?.party_b?.phone || '',
                  id_card_number: analysisResult?.data?.party_b?.id_number || '',
                }}
              >
                <Form.Item name="name" label="客户名称" rules={[{ required: true, message: '请输入客户名称' }]}>
                  <Input placeholder="输入客户名称" />
                </Form.Item>
                <div style={{ display: 'flex', gap: 12 }}>
                  <Form.Item name="phone" label="电话" style={{ flex: 1 }}>
                    <Input placeholder="电话号码" />
                  </Form.Item>
                  <Form.Item name="id_card_number" label="证件号码" style={{ flex: 1 }}>
                    <Input placeholder="身份证/证件号" />
                  </Form.Item>
                </div>
                <Form.Item name="email" label="邮箱">
                  <Input placeholder="电子邮箱" />
                </Form.Item>
                <Form.Item name="contact_person" label="联系人">
                  <Input placeholder="联系人姓名" />
                </Form.Item>
                <Form.Item>
                  <Button type="primary" onClick={handleCreateCustomer}>创建客户</Button>
                </Form.Item>
              </Form>
            </Card>
          )}
        </div>
      )}

      {/* ─── Step 4: 确认创建 ─── */}
      {current === STEP_CONFIRM && (
        <div>
          <div style={{ marginBottom: 16, display: 'flex', alignItems: 'center', gap: 8 }}>
            <FileTextOutlined />
            <span>AI 分析结果确认</span>
            <Tag color={confidenceColor}>置信度: {confidenceLabel}</Tag>
            {confidenceValue != null && confidenceValue < 0.85 && (
              <Alert
                type="warning"
                message="AI 置信度较低，请仔细核对数据"
                showIcon
                style={{ flex: 1, padding: '4px 12px' }}
              />
            )}
          </div>

          <Form form={confirmForm} layout="vertical" size="small">
            <div style={{ display: 'flex', gap: 12 }}>
              <Form.Item name="title" label="合同标题" style={{ flex: 2 }}>
                <Input placeholder="合同标题" />
              </Form.Item>
              <Form.Item name="business_type" label="业务类型" style={{ flex: 1 }}>
                <Select options={BUSINESS_TYPES} placeholder="选择业务类型" />
              </Form.Item>
            </div>

            <Form.Item name="business_description" label="业务描述">
              <TextArea rows={2} placeholder="一句话业务描述" />
            </Form.Item>

            <div style={{ display: 'flex', gap: 12 }}>
              <Form.Item name="currency" label="币种" style={{ flex: 1 }}>
                <Select options={CURRENCIES} />
              </Form.Item>
              <Form.Item name="total_amount" label="总金额" style={{ flex: 1 }}>
                <InputNumber style={{ width: '100%' }} min={0} precision={2} />
              </Form.Item>
              <Form.Item name="signed_date" label="签订日期" style={{ flex: 1 }}>
                <DatePicker style={{ width: '100%' }} />
              </Form.Item>
            </div>

            <div style={{ display: 'flex', gap: 12 }}>
              <Form.Item name="start_date" label="生效日期" style={{ flex: 1 }}>
                <DatePicker style={{ width: '100%' }} />
              </Form.Item>
              <Form.Item name="end_date" label="到期日期" style={{ flex: 1 }}>
                <DatePicker style={{ width: '100%' }} />
              </Form.Item>
              <Form.Item name="wechat_group" label="微信群" style={{ flex: 1 }}>
                <Input placeholder="微信群名称" />
              </Form.Item>
            </div>

            <Form.Item name="remarks" label="备注">
              <TextArea rows={2} placeholder="备注信息（可选）" />
            </Form.Item>

            {/* 付款条款 */}
            <Divider orientation="left" plain>付款条款</Divider>
            <Form.List name="payment_terms">
              {(fields) => fields.length > 0 ? (
                <div style={{ maxHeight: 240, overflowY: 'auto' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                    <thead>
                      <tr style={{ background: '#fafafa', borderBottom: '1px solid #f0f0f0' }}>
                        <th style={{ padding: '6px 8px', textAlign: 'left' }}>款项名称</th>
                        <th style={{ padding: '6px 8px', textAlign: 'right' }}>金额</th>
                        <th style={{ padding: '6px 8px', textAlign: 'center' }}>应付日期</th>
                        <th style={{ padding: '6px 8px', textAlign: 'center' }}>已付</th>
                      </tr>
                    </thead>
                    <tbody>
                      {fields.map(({ key, name, ...restField }) => (
                        <tr key={key} style={{ borderBottom: '1px solid #f5f5f5' }}>
                          <td style={{ padding: '4px 8px' }}>
                            <Form.Item {...restField} name={[name, 'name']} noStyle>
                              <Input size="small" placeholder="款项名称" variant="borderless" />
                            </Form.Item>
                          </td>
                          <td style={{ padding: '4px 8px', textAlign: 'right' }}>
                            <Form.Item {...restField} name={[name, 'amount']} noStyle>
                              <InputNumber size="small" min={0} precision={2} variant="borderless" style={{ width: 100 }} />
                            </Form.Item>
                          </td>
                          <td style={{ padding: '4px 8px', textAlign: 'center' }}>
                            <Form.Item {...restField} name={[name, 'due_date']} noStyle>
                              <Input size="small" placeholder="日期" variant="borderless" style={{ width: 100 }} />
                            </Form.Item>
                          </td>
                          <td style={{ padding: '4px 8px', textAlign: 'center' }}>
                            <Form.Item {...restField} name={[name, 'is_paid']} noStyle valuePropName="checked">
                              <input type="checkbox" />
                            </Form.Item>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p style={{ color: '#999' }}>未提取到付款条款</p>
              )}
            </Form.List>
          </Form>
        </div>
      )}

      {/* ─── 底部按钮 ─── */}
      <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 24, borderTop: '1px solid #f0f0f0', paddingTop: 16 }}>
        <Button onClick={current === STEP_UPLOAD ? handleClose : goPrev} icon={current === STEP_UPLOAD ? undefined : <ArrowLeftOutlined />}>
          {current === STEP_UPLOAD ? '取消' : '上一步'}
        </Button>
        <div style={{ display: 'flex', gap: 8 }}>
          {current < STEP_CONFIRM && current !== STEP_ANALYSIS && (
            <Button type="primary" onClick={goNext} disabled={!canGoNext()} loading={loading} icon={<ArrowRightOutlined />}>
              下一步
            </Button>
          )}
          {current === STEP_CONFIRM && (
            <Button type="primary" onClick={handleSubmit} loading={loading} icon={<CheckOutlined />}>
              确认创建
            </Button>
          )}
        </div>
      </div>
    </Modal>
  )
}
