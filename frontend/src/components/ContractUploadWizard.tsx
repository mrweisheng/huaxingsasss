import { useState, useCallback, useEffect, useRef } from 'react'
import {
  Modal, Steps, Button, Upload, Input, Alert, Tag, message, Card,
} from 'antd'
import {
  InboxOutlined, ArrowLeftOutlined, ArrowRightOutlined, CheckOutlined,
  WarningOutlined, FileTextOutlined, UserOutlined, CheckCircleOutlined,
  LoadingOutlined, SearchOutlined,
} from '@ant-design/icons'
import { agentApi } from '@/services/agent'
import { contractApi } from '@/services/contract'
import { customerApi } from '@/services/customer'
import './ContractUploadWizard.css'

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

  // 分析阶段动态提示语
  const [analyzeHint, setAnalyzeHint] = useState('')
  const analyzeTimerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const analyzeHints = [
    '正在读取文件内容...',
    'AI 正在提取合同关键字段...',
    '正在识别金额与付款条款...',
    '正在匹配客户信息...',
    '分析即将完成...',
  ]

  useEffect(() => {
    if (loading && current === STEP_ANALYSIS) {
      let idx = 0
      setAnalyzeHint(analyzeHints[0])
      analyzeTimerRef.current = setInterval(() => {
        idx += 1
        if (idx < analyzeHints.length) {
          setAnalyzeHint(analyzeHints[idx])
        }
      }, 1200)
    } else {
      setAnalyzeHint('')
      if (analyzeTimerRef.current) {
        clearInterval(analyzeTimerRef.current)
        analyzeTimerRef.current = null
      }
    }
    return () => {
      if (analyzeTimerRef.current) {
        clearInterval(analyzeTimerRef.current)
      }
    }
  }, [loading, current])

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
      width={680}
      centered
      footer={null}
      destroyOnClose
      maskClosable={false}
      className="wizard-modal"
    >
      <Steps
        current={current}
        className="wizard-steps"
        size="small"
        items={[
          { title: '上传文件' },
          { title: 'AI 分析' },
          { title: '关联客户' },
          { title: '确认创建' },
        ]}
      />

      <div className="wizard-content">
        {/* ─── Step 1: 上传文件 ─── */}
        {current === STEP_UPLOAD && (
          <div className="wizard-upload-zone">
            <Dragger
              accept="image/jpeg,image/png,image/jpg,.pdf,.docx,.xlsx"
              showUploadList={false}
              beforeUpload={handleUpload}
              disabled={loading}
            >
              <p className="ant-upload-drag-icon">
                {loading ? (
                  <LoadingOutlined style={{ fontSize: 48, color: 'var(--brand-primary)' }} />
                ) : (
                  <InboxOutlined style={{ fontSize: 48, color: 'var(--brand-primary)' }} />
                )}
              </p>
              <p className="ant-upload-text" style={{ fontSize: 15, fontWeight: 500, marginTop: 8 }}>
                {loading ? '正在上传...' : '点击或拖拽文件到此处上传'}
              </p>
              <p className="ant-upload-hint">
                支持 JPG / PNG / PDF / Word / Excel 格式
              </p>
            </Dragger>
          </div>
        )}

        {/* ─── Step 2: AI 分析 ─── */}
        {current === STEP_ANALYSIS && (
          <div className="wizard-analyze-zone">
            {loading ? (
              <div className="wizard-progress">
                <FileTextOutlined className="wizard-progress-icon" spin />
                <p className="wizard-progress-text">
                  {analyzeHint || 'AI 正在分析合同内容...'}
                </p>
                <p className="wizard-progress-hint">
                  系统将自动提取金额、客户、付款条款等关键信息，请稍候
                </p>
              </div>
            ) : duplicateInfo ? (
              <>
                <div className="wizard-duplicate-warning">
                  <div className="wizard-duplicate-title">
                    <WarningOutlined />
                    检测到重复合同
                  </div>
                  <div className="wizard-duplicate-detail">
                    <div>编号：<strong>{duplicateInfo.contract_number}</strong></div>
                    <div>标题：{duplicateInfo.title || '无'}</div>
                    <div>金额：{duplicateInfo.currency} {Number(duplicateInfo.total_amount || 0).toLocaleString()}</div>
                    <div>状态：<Tag color={duplicateInfo.status === 'active' ? 'blue' : 'green'}>{duplicateInfo.status === 'active' ? '执行中' : '已完成'}</Tag></div>
                    {duplicateInfo.customer_name && <div>客户：{duplicateInfo.customer_name}</div>}
                  </div>
                </div>
                <div style={{ display: 'flex', justifyContent: 'center', gap: 12 }}>
                  <Button onClick={handleClose}>取消</Button>
                  <Button type="primary" danger onClick={() => { setDuplicateInfo(null); runAnalysis(true) }}>
                    仍然创建
                  </Button>
                </div>
              </>
            ) : analysisResult ? (
              <>
                <div className="wizard-result-card">
                  <div className="wizard-result-card-header">
                    <CheckCircleOutlined />
                    AI 分析完成
                  </div>
                  <div className="wizard-result-fields">
                    {d.title && (
                      <div className="wizard-result-field">
                        <span className="wizard-result-field-label">标题</span>
                        <span className="wizard-result-field-value">{d.title}</span>
                      </div>
                    )}
                    {d.business_type && (
                      <div className="wizard-result-field">
                        <span className="wizard-result-field-label">业务类型</span>
                        <span className="wizard-result-field-value">{d.business_type}</span>
                      </div>
                    )}
                    {d.total_amount != null && (
                      <div className="wizard-result-field">
                        <span className="wizard-result-field-label">总金额</span>
                        <span className="wizard-result-field-value">
                          {d.currency || 'CNY'} {Number(d.total_amount).toLocaleString('zh-CN', { minimumFractionDigits: 2 })}
                        </span>
                      </div>
                    )}
                    {d.party_b?.name && (
                      <div className="wizard-result-field">
                        <span className="wizard-result-field-label">乙方</span>
                        <span className="wizard-result-field-value">{d.party_b.name}</span>
                      </div>
                    )}
                    {d.party_a?.name && (
                      <div className="wizard-result-field">
                        <span className="wizard-result-field-label">甲方</span>
                        <span className="wizard-result-field-value">{d.party_a.name}</span>
                      </div>
                    )}
                    {terms.length > 0 && (
                      <div className="wizard-result-field">
                        <span className="wizard-result-field-label">付款条款</span>
                        <span className="wizard-result-field-value">{terms.length} 条</span>
                      </div>
                    )}
                  </div>
                </div>
                <div style={{ display: 'flex', justifyContent: 'center' }}>
                  <Button type="primary" onClick={goFromAnalysisToCustomer} icon={<ArrowRightOutlined />} size="large">
                    下一步：关联客户
                  </Button>
                </div>
              </>
            ) : (
              <div className="wizard-start-btn">
                <Button type="primary" size="large" onClick={() => runAnalysis(false)} icon={<SearchOutlined />}>
                  开始 AI 分析
                </Button>
              </div>
            )}
          </div>
        )}

        {/* ─── Step 3: 客户自动关联 ─── */}
        {current === STEP_CUSTOMER && (
          <div className="wizard-customer-zone">
            {loading && !resolvedCustomer ? (
              <div className="wizard-progress">
                <UserOutlined className="wizard-progress-icon" spin />
                <p className="wizard-progress-text">正在匹配客户...</p>
                <p className="wizard-progress-hint">
                  系统将根据合同中的姓名和联系方式自动匹配或创建客户
                </p>
              </div>
            ) : resolvedCustomer ? (
              <>
                <div className="wizard-customer-card">
                  <div className="wizard-customer-card-header">
                    <CheckCircleOutlined />
                    <span style={{ fontSize: 14, fontWeight: 600, color: '#1890ff' }}>
                      客户关联成功
                    </span>
                    <Tag color={resolvedCustomer.created ? 'green' : 'blue'}>
                      {resolvedCustomer.created ? '新建客户' : '已有客户'}
                    </Tag>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                    <span className="wizard-customer-name">{resolvedCustomer.name}</span>
                    {resolvedCustomer.phone && (
                      <span className="wizard-customer-phone">电话：{resolvedCustomer.phone}</span>
                    )}
                  </div>
                </div>
                <div style={{ display: 'flex', justifyContent: 'center' }}>
                  <Button type="primary" size="large" onClick={goNext} icon={<ArrowRightOutlined />}>
                    下一步：确认创建
                  </Button>
                </div>
              </>
            ) : resolveError ? (
              <>
                <Alert
                  type="warning"
                  message={resolveError}
                  showIcon
                  style={{ marginBottom: 16 }}
                />
                <div className="wizard-fallback-card">
                  <div className="wizard-fallback-title">手动输入客户信息</div>
                  <div style={{ display: 'flex', gap: 12, marginBottom: 14 }}>
                    <Input
                      placeholder="客户姓名 *"
                      value={fallbackName}
                      onChange={e => setFallbackName(e.target.value)}
                      size="large"
                      style={{ flex: 1 }}
                      prefix={<UserOutlined />}
                    />
                    <Input
                      placeholder="电话（选填）"
                      value={fallbackPhone}
                      onChange={e => setFallbackPhone(e.target.value)}
                      size="large"
                      style={{ flex: 1 }}
                    />
                  </div>
                  <Button type="primary" onClick={handleFallbackCreate} loading={loading} block>
                    创建客户并继续
                  </Button>
                </div>
              </>
            ) : null}
          </div>
        )}

        {/* ─── Step 4: 确认创建 ─── */}
        {current === STEP_CONFIRM && (
          <div className="wizard-confirm-zone">
            <Card size="small" title="合同信息" className="wizard-summary-card">
              <div className="wizard-summary-grid">
                <div className="wizard-summary-grid-item">
                  <span className="wizard-summary-grid-label">标题：</span>
                  <span className="wizard-summary-grid-value">{d.title || uploadedFile?.name || '无'}</span>
                </div>
                <div className="wizard-summary-grid-item">
                  <span className="wizard-summary-grid-label">业务类型：</span>
                  <span className="wizard-summary-grid-value">{d.business_type || '未识别'}</span>
                </div>
                <div className="wizard-summary-grid-item">
                  <span className="wizard-summary-grid-label">币种：</span>
                  <span className="wizard-summary-grid-value">{d.currency || 'CNY'}</span>
                </div>
                <div className="wizard-summary-grid-item">
                  <span className="wizard-summary-grid-label">总金额：</span>
                  <span className="wizard-summary-grid-value">
                    {d.currency || 'CNY'} {Number(d.total_amount || 0).toLocaleString('zh-CN', { minimumFractionDigits: 2 })}
                  </span>
                </div>
                <div className="wizard-summary-grid-item">
                  <span className="wizard-summary-grid-label">签订日期：</span>
                  <span className="wizard-summary-grid-value">{d.signed_date || '未识别'}</span>
                </div>
                <div className="wizard-summary-grid-item">
                  <span className="wizard-summary-grid-label">有效期：</span>
                  <span className="wizard-summary-grid-value">
                    {validity.start_date && validity.end_date
                      ? `${validity.start_date} ~ ${validity.end_date}`
                      : '未识别'}
                  </span>
                </div>
              </div>
              {d.business_description && (
                <div style={{ marginTop: 10, fontSize: 13 }}>
                  <span className="wizard-summary-grid-label">业务描述：</span>
                  <span className="wizard-summary-grid-value">{d.business_description}</span>
                </div>
              )}
              {d.wechat_group && (
                <div style={{ marginTop: 4, fontSize: 13 }}>
                  <span className="wizard-summary-grid-label">微信群：</span>
                  <span className="wizard-summary-grid-value">{d.wechat_group}</span>
                </div>
              )}
            </Card>

            <Card size="small" title="客户信息" className="wizard-summary-card">
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <UserOutlined style={{ fontSize: 16, color: 'var(--brand-primary)' }} />
                <span style={{ fontSize: 14, fontWeight: 600 }}>{resolvedCustomer?.name}</span>
                {resolvedCustomer?.phone && (
                  <span style={{ fontSize: 13, color: 'var(--text-tertiary)' }}>
                    电话：{resolvedCustomer.phone}
                  </span>
                )}
                <Tag color={resolvedCustomer?.created ? 'green' : 'blue'}>
                  {resolvedCustomer?.created ? '新建' : '已有'}
                </Tag>
              </div>
            </Card>

            {terms.length > 0 && (
              <Card size="small" title={`付款条款（${terms.length} 条）`} className="wizard-summary-card">
                <table className="wizard-summary-table">
                  <thead>
                    <tr>
                      <th>款项名称</th>
                      <th style={{ textAlign: 'right' }}>金额</th>
                      <th style={{ textAlign: 'center' }}>应付日期</th>
                      <th style={{ textAlign: 'center' }}>已付</th>
                    </tr>
                  </thead>
                  <tbody>
                    {terms.map((t: any, i: number) => (
                      <tr key={i}>
                        <td>{t.name || '-'}</td>
                        <td className="right">
                          {Number(t.amount || 0).toLocaleString('zh-CN', { minimumFractionDigits: 2 })}
                        </td>
                        <td className="center">{t.due_date || '-'}</td>
                        <td className="center">{t.is_paid ? '✓' : '✗'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </Card>
            )}
          </div>
        )}
      </div>

      {/* ─── 底部按钮 ─── */}
      <div className="wizard-footer">
        <Button
          onClick={current === STEP_UPLOAD ? handleClose : goPrev}
          icon={current > STEP_UPLOAD ? <ArrowLeftOutlined /> : undefined}
        >
          {current === STEP_UPLOAD ? '取消' : '上一步'}
        </Button>

        <div className="wizard-footer-right">
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
