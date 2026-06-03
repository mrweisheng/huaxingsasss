import { useState, useCallback } from 'react'
import {
  Modal, Steps, Button, Upload, Input, Spin, Alert, Tag, Space, message, Card,
} from 'antd'
import {
  InboxOutlined, ArrowLeftOutlined, ArrowRightOutlined, CheckOutlined,
  WarningOutlined, FileTextOutlined, UserOutlined, CheckCircleOutlined,
} from '@ant-design/icons'
import { agentApi } from '@/services/agent'
import { contractApi } from '@/services/contract'
import { customerApi } from '@/services/customer'

const { Dragger } = Upload

interface Props {
  open: boolean
  onClose: (created: boolean) => void
}

const STEP_UPLOAD = 0
const STEP_ANALYSIS = 1
const STEP_CUSTOMER = 2
const STEP_CONFIRM = 3

export default function ContractUploadWizard({ open, onClose }: Props) {
  const [current, setCurrent] = useState(STEP_UPLOAD)
  const [loading, setLoading] = useState(false)

  // Step 1: 上传
  const [uploadedFile, setUploadedFile] = useState<File | null>(null)
  const [fileId, setFileId] = useState<string | null>(null)

  // Step 2: 分析结果
  const [analysisResult, setAnalysisResult] = useState<any>(null)
  const [duplicateInfo, setDuplicateInfo] = useState<any>(null)

  // Step 3: 客户自动关联
  const [resolvedCustomer, setResolvedCustomer] = useState<{
    id: number; name: string; phone?: string; created: boolean
  } | null>(null)
  const [resolveError, setResolveError] = useState<string | null>(null)
  const [fallbackName, setFallbackName] = useState('')
  const [fallbackPhone, setFallbackPhone] = useState('')

  // ─── 重置 ───
  const reset = useCallback(() => {
    setCurrent(STEP_UPLOAD)
    setLoading(false)
    setUploadedFile(null)
    setFileId(null)
    setAnalysisResult(null)
    setDuplicateInfo(null)
    setResolvedCustomer(null)
    setResolveError(null)
    setFallbackName('')
    setFallbackPhone('')
  }, [])

  const handleClose = () => { reset(); onClose(false) }
  const handleCreated = () => { reset(); onClose(true) }

  // ─── Step 1: 上传 ───
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
    return false
  }

  // ─── Step 2: AI 分析 ───
  const runAnalysis = useCallback(async (skipDuplicate = false) => {
    if (!fileId) return
    setLoading(true)
    setDuplicateInfo(null)
    try {
      const res = await contractApi.analyzeFile(fileId, uploadedFile?.name, skipDuplicate)
      const data = res.data
      if (data.duplicate_detected) {
        setDuplicateInfo(data.existing_contract)
        setLoading(false)
        return
      }
      setAnalysisResult(data)
    } catch (err: any) {
      message.error(err?.response?.data?.detail || 'AI 分析失败')
    } finally {
      setLoading(false)
    }
  }, [fileId, uploadedFile])

  /** Step 2 → Step 3：自动关联客户 */
  const goFromAnalysisToCustomer = async () => {
    setCurrent(STEP_CUSTOMER)
    setLoading(true)
    setResolveError(null)
    setResolvedCustomer(null)
    try {
      const res = await contractApi.resolveCustomer(analysisResult?.data)
      const data = res.data
      if (data.success) {
        setResolvedCustomer(data.customer)
      } else {
        setResolveError(data.error || '无法自动识别客户')
      }
    } catch (err: any) {
      setResolveError(err?.response?.data?.detail || '客户关联失败')
    } finally {
      setLoading(false)
    }
  }

  /** 兜底：手动创建客户 */
  const handleFallbackCreate = async () => {
    if (!fallbackName.trim()) {
      message.error('请输入客户姓名')
      return
    }
    setLoading(true)
    try {
      const customer = await customerApi.create({
        name: fallbackName,
        phone: fallbackPhone || undefined,
      })
      setResolvedCustomer({
        id: customer.id,
        name: customer.name,
        phone: customer.phone,
        created: true,
      })
      setResolveError(null)
    } catch (err: any) {
      message.error(err?.response?.data?.detail || '创建客户失败')
    } finally {
      setLoading(false)
    }
  }

  // ─── Step 4: 提交创建合同 ───
  const handleSubmit = async () => {
    if (!resolvedCustomer) {
      message.error('客户信息缺失')
      return
    }
    setLoading(true)
    try {
      const d = analysisResult?.data || {}
      const validity = d.validity_period || {}
      const payload = {
        file_id: fileId,
        file_name: uploadedFile?.name,
        customer_id: resolvedCustomer.id,
        title: d.title || uploadedFile?.name || '',
        business_type: d.business_type,
        business_description: d.business_description,
        currency: d.currency || 'CNY',
        total_amount: d.total_amount || 0,
        signed_date: d.signed_date || null,
        start_date: validity.start_date || null,
        end_date: validity.end_date || null,
        wechat_group: d.wechat_group,
        payment_terms: (d.payment_terms || []).map((t: any) => ({
          name: t.name,
          amount: t.amount,
          due_date: t.due_date,
          condition: t.condition,
          is_paid: t.is_paid,
        })),
        analysis_data: d,
        full_text: d.full_text || '',
        confidence: d.confidence || null,
      }
      await contractApi.createFromAnalysis(payload)
      message.success('合同创建成功')
      handleCreated()
    } catch (err: any) {
      message.error(err?.response?.data?.detail || '创建合同失败')
    } finally {
      setLoading(false)
    }
  }

  // ─── Step 导航 ───
  const goNext = () => {
    if (current === STEP_CUSTOMER && !resolvedCustomer) {
      message.warning('请先完成客户关联')
      return
    }
    setCurrent(STEP_CONFIRM)
  }

  const goPrev = () => {
    if (current > STEP_UPLOAD) setCurrent(current - 1)
  }

  const d = analysisResult?.data || {}
  const terms: any[] = d.payment_terms || []
  const validity = d.validity_period || {}

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
                  onClick={() => { setDuplicateInfo(null); runAnalysis(true) }}
                >
                  仍然创建
                </Button>
              </Space>
            </div>
          ) : analysisResult ? (
            <div style={{ textAlign: 'left' }}>
              <Card size="small" style={{ marginBottom: 16, background: '#f6ffed' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                  <FileTextOutlined />
                  <strong>AI 分析完成</strong>
                </div>
                <div style={{ fontSize: 13, color: '#555' }}>
                  {d.title && <p style={{ margin: '4px 0' }}>标题：{d.title}</p>}
                  {d.business_type && <p style={{ margin: '4px 0' }}>业务类型：{d.business_type}</p>}
                  {d.total_amount != null && (
                    <p style={{ margin: '4px 0' }}>
                      总金额：{d.currency || 'CNY'} {Number(d.total_amount).toLocaleString('zh-CN', { minimumFractionDigits: 2 })}
                    </p>
                  )}
                  {d.party_b?.name && <p style={{ margin: '4px 0' }}>乙方：{d.party_b.name}</p>}
                  {d.party_a?.name && <p style={{ margin: '4px 0' }}>甲方：{d.party_a.name}</p>}
                  {terms.length > 0 && <p style={{ margin: '4px 0' }}>付款条款：{terms.length} 条</p>}
                </div>
              </Card>
              <div style={{ textAlign: 'center' }}>
                <Button type="primary" onClick={goFromAnalysisToCustomer} icon={<ArrowRightOutlined />}>
                  下一步：关联客户
                </Button>
              </div>
            </div>
          ) : (
            <Button type="primary" onClick={() => runAnalysis(false)}>
              开始 AI 分析
            </Button>
          )}
        </div>
      )}

      {/* ─── Step 3: 客户自动关联 ─── */}
      {current === STEP_CUSTOMER && (
        <div style={{ padding: '16px 0' }}>
          {loading && !resolvedCustomer ? (
            <div style={{ textAlign: 'center', padding: '40px 0' }}>
              <Spin size="large" />
              <p style={{ marginTop: 16, color: '#666' }}>正在自动关联客户...</p>
            </div>
          ) : resolvedCustomer ? (
            <Card size="small" style={{ background: '#f6ffed' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                <CheckCircleOutlined style={{ color: '#52c41a', fontSize: 18 }} />
                <strong>客户关联成功</strong>
                <Tag color={resolvedCustomer.created ? 'green' : 'blue'}>
                  {resolvedCustomer.created ? '新建客户' : '已有客户'}
                </Tag>
              </div>
              <div style={{ fontSize: 13 }}>
                <strong>{resolvedCustomer.name}</strong>
                {resolvedCustomer.phone && (
                  <span style={{ marginLeft: 12, color: '#888' }}>电话: {resolvedCustomer.phone}</span>
                )}
              </div>
            </Card>
          ) : resolveError ? (
            <div>
              <Alert type="warning" message={resolveError} showIcon style={{ marginBottom: 12 }} />
              <Card size="small" title="手动输入客户信息">
                <div style={{ display: 'flex', gap: 12, marginBottom: 12 }}>
                  <Input
                    placeholder="客户姓名 *"
                    value={fallbackName}
                    onChange={e => setFallbackName(e.target.value)}
                    style={{ flex: 1 }}
                  />
                  <Input
                    placeholder="电话（选填）"
                    value={fallbackPhone}
                    onChange={e => setFallbackPhone(e.target.value)}
                    style={{ flex: 1 }}
                  />
                </div>
                <Button type="primary" size="small" onClick={handleFallbackCreate} loading={loading}>
                  创建客户
                </Button>
              </Card>
            </div>
          ) : null}
        </div>
      )}

      {/* ─── Step 4: 只读确认摘要 ─── */}
      {current === STEP_CONFIRM && (
        <div>
          <Card size="small" title="合同信息" style={{ marginBottom: 12 }}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px 24px', fontSize: 13 }}>
              <div><span style={{ color: '#888' }}>标题：</span>{d.title || uploadedFile?.name || '无'}</div>
              <div><span style={{ color: '#888' }}>业务类型：</span>{d.business_type || '未识别'}</div>
              <div><span style={{ color: '#888' }}>币种：</span>{d.currency || 'CNY'}</div>
              <div>
                <span style={{ color: '#888' }}>总金额：</span>
                {d.currency || 'CNY'} {Number(d.total_amount || 0).toLocaleString('zh-CN', { minimumFractionDigits: 2 })}
              </div>
              <div><span style={{ color: '#888' }}>签订日期：</span>{d.signed_date || '未识别'}</div>
              <div>
                <span style={{ color: '#888' }}>有效期：</span>
                {validity.start_date && validity.end_date
                  ? `${validity.start_date} ~ ${validity.end_date}`
                  : '未识别'}
              </div>
            </div>
            {d.business_description && (
              <div style={{ marginTop: 8, fontSize: 13 }}>
                <span style={{ color: '#888' }}>业务描述：</span>{d.business_description}
              </div>
            )}
            {d.wechat_group && (
              <div style={{ marginTop: 4, fontSize: 13 }}>
                <span style={{ color: '#888' }}>微信群：</span>{d.wechat_group}
              </div>
            )}
          </Card>

          <Card size="small" title="客户信息" style={{ marginBottom: 12 }}>
            <div style={{ fontSize: 13, display: 'flex', alignItems: 'center', gap: 8 }}>
              <UserOutlined />
              <strong>{resolvedCustomer?.name}</strong>
              {resolvedCustomer?.phone && (
                <span style={{ color: '#888' }}>电话: {resolvedCustomer.phone}</span>
              )}
              <Tag color={resolvedCustomer?.created ? 'green' : 'blue'}>
                {resolvedCustomer?.created ? '新建' : '已有'}
              </Tag>
            </div>
          </Card>

          {terms.length > 0 && (
            <Card size="small" title={`付款条款（${terms.length} 条）`}>
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
                  {terms.map((t: any, i: number) => (
                    <tr key={i} style={{ borderBottom: '1px solid #f5f5f5' }}>
                      <td style={{ padding: '6px 8px' }}>{t.name || '-'}</td>
                      <td style={{ padding: '6px 8px', textAlign: 'right' }}>
                        {Number(t.amount || 0).toLocaleString('zh-CN', { minimumFractionDigits: 2 })}
                      </td>
                      <td style={{ padding: '6px 8px', textAlign: 'center' }}>{t.due_date || '-'}</td>
                      <td style={{ padding: '6px 8px', textAlign: 'center' }}>{t.is_paid ? '✓' : '✗'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Card>
          )}
        </div>
      )}

      {/* ─── 底部按钮 ─── */}
      <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 24, borderTop: '1px solid #f0f0f0', paddingTop: 16 }}>
        <Button onClick={current === STEP_UPLOAD ? handleClose : goPrev} icon={current === STEP_UPLOAD ? undefined : <ArrowLeftOutlined />}>
          {current === STEP_UPLOAD ? '取消' : '上一步'}
        </Button>
        <div style={{ display: 'flex', gap: 8 }}>
          {current === STEP_CUSTOMER && (
            <Button type="primary" onClick={goNext} disabled={!resolvedCustomer} loading={loading} icon={<ArrowRightOutlined />}>
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
