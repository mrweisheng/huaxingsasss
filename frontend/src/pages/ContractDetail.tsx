import { useState, useEffect, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Button, Spin, Table, Tag, Alert, Popconfirm, message, Tabs } from 'antd'
import { ArrowLeftOutlined, FileOutlined, CheckCircleOutlined, DollarOutlined, UserOutlined, ExclamationCircleOutlined } from '@ant-design/icons'
import { contractApi } from '@/services/contract'
import { paymentApi } from '@/services/payment'
import { useAuthStore } from '@/store/useAuthStore'
import { API_BASE_URL } from '@/services/api'
import type { Contract, Payment } from '@/types'
import './ContractDetail.css'

const statusMap: Record<string, { color: string; text: string }> = {
  active: { color: 'processing', text: '执行中' },
  completed: { color: 'success', text: '已完成' },
}

const currencySymbol: Record<string, string> = { CNY: '¥', HKD: 'HK$', USD: '$' }

function fmt(amount: number | undefined | null, currency: string): string {
  if (amount === undefined || amount === null) return '-'
  const symbol = currencySymbol[currency] || '¥'
  return `${symbol}${amount.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

function calcProgress(paid: number, total: number): number {
  if (total === 0) return 0
  return Math.round((paid / total) * 100)
}

const paymentStatusMap: Record<string, { color: string; text: string }> = {
  pending: { color: 'default', text: '待支付' },
  partial: { color: 'warning', text: '部分支付' },
  paid: { color: 'success', text: '已支付' },
  overdue: { color: 'error', text: '逾期' },
  cancelled: { color: 'default', text: '已取消' },
}

export default function ContractDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const user = useAuthStore(s => s.user)
  const role = user?.role || ''
  const [contract, setContract] = useState<Contract | null>(null)
  const [incomePayments, setIncomePayments] = useState<Payment[]>([])
  const [expensePayments, setExpensePayments] = useState<Payment[]>([])
  const [summary, setSummary] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [completing, setCompleting] = useState(false)
  const abortControllerRef = useRef<AbortController | null>(null)

  const handleComplete = async () => {
    if (!contract) return
    setCompleting(true)
    try {
      const updated = await contractApi.complete(contract.id)
      setContract(updated)
      message.success('合同已标记为完成')
    } catch (e: any) {
      message.error(e.response?.data?.detail || '操作失败')
    } finally {
      setCompleting(false)
    }
  }

  useEffect(() => {
    if (!id) return

    abortControllerRef.current?.abort()
    const controller = new AbortController()
    abortControllerRef.current = controller

    setLoading(true)
    setError('')
    Promise.all([
      contractApi.getById(Number(id), controller.signal),
      paymentApi.getContractPayments(Number(id), controller.signal),
    ])
      .then(([c, p]) => {
        if (controller.signal.aborted) return
        setContract(c)
        const data = p.data || p
        setSummary(data)
        // 按收入/支出分组
        setIncomePayments(data.income?.payments || [])
        setExpensePayments(data.expense?.payments || [])
      })
      .catch((e) => {
        if (e?.name === 'AbortError' || e?.code === 'ERR_CANCELED') return
        setError(e.response?.data?.detail || '加载失败')
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setLoading(false)
        }
      })

    return () => {
      controller.abort()
    }
  }, [id])

  if (loading) return <div style={{ textAlign: 'center', padding: 80 }}><Spin tip="加载中..." /></div>
  if (error) return <Alert type="error" message={error} showIcon />
  if (!contract) return <Alert type="warning" message="合同不存在" showIcon />

  const cur = contract.currency
  const progress = calcProgress(contract.paid_amount, contract.total_amount)
  const authToken = localStorage.getItem('access_token')
  const contractFileUrl = contract.original_file_path
    ? `${API_BASE_URL}/contracts/${contract.id}/file?token=${authToken}`
    : null
  const status = statusMap[contract.status] || { color: 'default', text: contract.status }
  const isRemaining = contract.remaining_amount > 0

  // 利润计算
  const totalIncomeCny = summary?.income?.total_paid_in_cny || contract.paid_amount_in_cny || 0
  const totalExpenseCny = summary?.expense?.total_expense_in_cny || contract.total_expense_in_cny || 0
  const profitCny = summary?.profit_in_cny ?? (totalIncomeCny - totalExpenseCny)

  const paymentColumns = [
    { title: '期数', dataIndex: 'installment_number', key: 'installment_number', width: 60 },
    { title: '期数名称', dataIndex: 'installment_name', key: 'installment_name', render: (v: string) => v || '-' },
    { title: '币种', dataIndex: 'currency', key: 'currency', width: 60 },
    { title: '金额', dataIndex: 'paid_amount', key: 'paid_amount', render: (v: number, r: Payment) => fmt(v, r.currency) },
    { title: '折CNY', dataIndex: 'paid_amount_in_cny', key: 'paid_amount_in_cny', width: 100, render: (v: number) => fmt(v, 'CNY') },
    { title: '付款日期', dataIndex: 'paid_date', key: 'paid_date', width: 110, render: (v: string) => v || '-' },
    { title: '方式', dataIndex: 'payment_method', key: 'payment_method', width: 80, render: (v: string) => v || '-' },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 80,
      render: (s: string) => (
        <span className={`payment-status ${s}`}>
          {paymentStatusMap[s]?.text || s}
        </span>
      )
    },
  ]

  const expenseColumns = [
    { title: '期数', dataIndex: 'installment_number', key: 'installment_number', width: 60 },
    { title: '收款方', dataIndex: 'payee_name', key: 'payee_name', render: (v: string) => v || '-' },
    { title: '币种', dataIndex: 'currency', key: 'currency', width: 60 },
    { title: '金额', dataIndex: 'paid_amount', key: 'paid_amount', render: (v: number, r: Payment) => fmt(v, r.currency) },
    { title: '折CNY', dataIndex: 'paid_amount_in_cny', key: 'paid_amount_in_cny', width: 100, render: (v: number) => fmt(v, 'CNY') },
    { title: '付款日期', dataIndex: 'paid_date', key: 'paid_date', width: 110, render: (v: string) => v || '-' },
    { title: '方式', dataIndex: 'payment_method', key: 'payment_method', width: 80, render: (v: string) => v || '-' },
  ]

  // 根据 role 决定显示哪些 tab
  const paymentTabItems = []
  if (role !== 'expense') {
    paymentTabItems.push({
      key: 'income',
      label: `收入记录 (${incomePayments.length})`,
      children: incomePayments.length > 0 ? (
        <Table columns={paymentColumns} dataSource={incomePayments} rowKey="id" size="small" pagination={false} scroll={{ x: 800 }} />
      ) : (
        <div className="no-payments"><DollarOutlined style={{ fontSize: 32, marginBottom: 12, display: 'block', opacity: 0.4 }} />暂无收入记录</div>
      ),
    })
  }
  if (role !== 'income') {
    paymentTabItems.push({
      key: 'expense',
      label: `支出记录 (${expensePayments.length})`,
      children: expensePayments.length > 0 ? (
        <Table columns={expenseColumns} dataSource={expensePayments} rowKey="id" size="small" pagination={false} scroll={{ x: 800 }} />
      ) : (
        <div className="no-payments"><DollarOutlined style={{ fontSize: 32, marginBottom: 12, display: 'block', opacity: 0.4 }} />暂无支出记录</div>
      ),
    })
  }

  return (
    <div className="contract-detail-container">
      <div className="detail-header">
        <div className="back-btn" onClick={() => navigate('/contracts')}>
          <ArrowLeftOutlined /> 返回列表
        </div>
        {user?.role === 'admin' && contract?.status === 'active' && (
          <Popconfirm
            title="确认完成"
            description="确定要将此合同标记为已完成吗？"
            onConfirm={handleComplete}
            okText="确认"
            cancelText="取消"
          >
            <Button type="primary" icon={<CheckCircleOutlined />} loading={completing} className="complete-btn">
              标记完成
            </Button>
          </Popconfirm>
        )}
      </div>

      <div className="hero-plus-financial">
        <div className="hero-section">
          <div className="hero-badges">
            {contract.business_type && (
              <span className={`business-type-tag ${contract.business_type === '车辆业务' ? 'vehicle' : 'zhonggang'}`}>
                {contract.business_type}
              </span>
            )}
            <span className={`status-tag ${contract.status}`}>
              {status.text}
            </span>
          </div>
          <div className="contract-number-hero">{contract.contract_number}</div>
          <div className="hero-customer">
            <UserOutlined style={{ marginRight: 8, opacity: 0.7 }} />
            {contract.customer_name || '无客户名称'}
          </div>
          {contract.title && (
            <div className="hero-title">{contract.title}</div>
          )}
        </div>

        <div className="financial-hero">
          <div className="financial-card total">
            <div className="financial-label">合同总额</div>
            <div className="financial-value large">{fmt(contract.total_amount, cur)}</div>
          </div>
          <div className="financial-card">
            <div className="financial-label">已收金额</div>
            <div className="financial-value" style={{ color: '#52c41a' }}>{fmt(contract.paid_amount, cur)}</div>
          </div>
          <div className="financial-card">
            <div className="financial-label">总支出</div>
            <div className="financial-value" style={{ color: '#ff4d4f' }}>{fmt(contract.total_expense || 0, cur)}</div>
          </div>
          <div className={`financial-card remaining ${isRemaining ? 'unpaid' : 'paid'}`}>
            <div className="financial-label">剩余尾款</div>
            <div className={`financial-value ${isRemaining ? 'unpaid' : 'paid'}`}>
              {isRemaining ? (
                <>
                  <ExclamationCircleOutlined style={{ marginRight: 4, fontSize: 14 }} />
                  {fmt(contract.remaining_amount, cur)}
                </>
              ) : (
                <>
                  <CheckCircleOutlined style={{ marginRight: 4, fontSize: 14 }} />
                  {fmt(contract.remaining_amount, cur)}
                </>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* 利润汇总 */}
      <div className="progress-section">
        <div className="progress-header">
          <span className="progress-title">
            <DollarOutlined style={{ marginRight: 8 }} />
            收支汇总（CNY）
          </span>
        </div>
        <div className="progress-details">
          <div className="progress-detail-item">
            <span className="progress-detail-label">已收金额</span>
            <span className="progress-detail-value paid">{fmt(totalIncomeCny, 'CNY')}</span>
          </div>
          <div className="progress-detail-item">
            <span className="progress-detail-label">总支出</span>
            <span className="progress-detail-value" style={{ color: '#ff4d4f' }}>{fmt(totalExpenseCny, 'CNY')}</span>
          </div>
          <div className="progress-detail-item">
            <span className="progress-detail-label">利润</span>
            <span className="progress-detail-value" style={{ color: profitCny >= 0 ? '#52c41a' : '#ff4d4f', fontWeight: 700, fontSize: 16 }}>
              {fmt(profitCny, 'CNY')}
            </span>
          </div>
        </div>
      </div>

      <div className="progress-section" style={{ marginTop: 16 }}>
        <div className="progress-header">
          <span className="progress-title">
            <DollarOutlined style={{ marginRight: 8 }} />
            付款进度
          </span>
          <span className="progress-percent">{progress}%</span>
        </div>
        <div className="progress-bar-container">
          <div className={`progress-bar-fill ${progress === 100 ? 'complete' : ''}`} style={{ width: `${progress}%` }} />
        </div>
        <div className="progress-details">
          <div className="progress-detail-item">
            <span className="progress-detail-label">合同金额</span>
            <span className="progress-detail-value">{fmt(contract.total_amount, cur)}</span>
          </div>
          <div className="progress-detail-item">
            <span className="progress-detail-label">已付金额</span>
            <span className="progress-detail-value paid">{fmt(contract.paid_amount, cur)}</span>
          </div>
          <div className="progress-detail-item">
            <span className="progress-detail-label">剩余尾款</span>
            <span className={`progress-detail-value remaining ${isRemaining ? 'danger' : ''}`}>
              {fmt(contract.remaining_amount, cur)}
            </span>
          </div>
        </div>
      </div>

      {summary && (summary.total_amount_in_cny || summary.paid_amount_in_cny || summary.income?.total_paid_in_cny) && (
        <div className="cny-summary">
          <div className="cny-summary-title">
            <DollarOutlined />
            CNY 汇总
          </div>
          <div className="cny-grid">
            <div className="cny-item">
              <span className="cny-label">合同总额</span>
              <span className="cny-value">{fmt(summary.total_amount_in_cny || summary.income?.total_amount, 'CNY')}</span>
            </div>
            <div className="cny-item">
              <span className="cny-label">已收</span>
              <span className="cny-value">{fmt(summary.income?.total_paid_in_cny || summary.paid_amount_in_cny, 'CNY')}</span>
            </div>
            <div className="cny-item">
              <span className="cny-label">支出</span>
              <span className="cny-value" style={{ color: '#ff4d4f' }}>{fmt(summary.expense?.total_expense_in_cny, 'CNY')}</span>
            </div>
            <div className="cny-item">
              <span className="cny-label">利润</span>
              <span className="cny-value" style={{ color: profitCny >= 0 ? '#52c41a' : '#ff4d4f', fontWeight: 600 }}>{fmt(profitCny, 'CNY')}</span>
            </div>
          </div>
        </div>
      )}

      <div className="detail-section">
        <div className="detail-section-title">
          <span className="section-icon">📋</span>
          合同信息
        </div>
        <div className="info-grid">
          <div className="info-item">
            <span className="info-label">币种</span>
            <span className="info-value">{cur}</span>
          </div>
          {contract.business_description && (
            <div className="info-item full-width">
              <span className="info-label">业务描述</span>
              <span className="info-value">{contract.business_description}</span>
            </div>
          )}
          {contract.remarks && (
            <div className="info-item full-width">
              <span className="info-label">备注</span>
              <span className="info-value">{contract.remarks}</span>
            </div>
          )}
        </div>

        {contract.contract_data && (() => {
          const cd = contract.contract_data
          const hasVehicleInfo = cd.vehicle_info?.plate_number || cd.vehicle_info?.vehicle_model || cd.port
          const hasPartyB = cd.party_b?.id_number || cd.party_b?.phone

          if (hasVehicleInfo || hasPartyB) {
            return (
              <div className="vehicle-info">
                {cd.vehicle_info?.plate_number && (
                  <div className="vehicle-item">
                    <span className="vehicle-label">车牌号</span>
                    <span className="vehicle-value">{cd.vehicle_info.plate_number}</span>
                  </div>
                )}
                {cd.vehicle_info?.vehicle_model && (
                  <div className="vehicle-item">
                    <span className="vehicle-label">车型</span>
                    <span className="vehicle-value">{cd.vehicle_info.vehicle_model}</span>
                  </div>
                )}
                {cd.port && (
                  <div className="vehicle-item">
                    <span className="vehicle-label">通行口岸</span>
                    <span className="vehicle-value">{cd.port}</span>
                  </div>
                )}
                {cd.party_b?.id_number && (
                  <div className="vehicle-item">
                    <span className="vehicle-label">证件号码</span>
                    <span className="vehicle-value">{cd.party_b.id_number}</span>
                  </div>
                )}
                {cd.party_b?.phone && (
                  <div className="vehicle-item">
                    <span className="vehicle-label">客户电话</span>
                    <span className="vehicle-value">{cd.party_b.phone}</span>
                  </div>
                )}
              </div>
            )
          }
          return null
        })()}

        {contract.contract_data?.payment_terms && contract.contract_data.payment_terms.length > 0 && (
          <div style={{ marginTop: 20 }}>
            <div className="detail-section-title" style={{ fontSize: 14, marginBottom: 12 }}>
              <span className="section-icon">💰</span>
              付款条款
            </div>
            <div className="payment-terms">
              {contract.contract_data.payment_terms.map((term: any, i: number) => (
                <div key={i} className="payment-term-item">
                  <Tag color="blue">{term.name}</Tag>
                  <span className="term-amount">{fmt(term.amount, contract.currency)}</span>
                  {term.condition && <span className="term-condition">({term.condition})</span>}
                </div>
              ))}
            </div>
          </div>
        )}

        {contract.contract_data?.special_terms && contract.contract_data.special_terms.length > 0 && (
          <div style={{ marginTop: 20 }}>
            <div className="detail-section-title" style={{ fontSize: 14, marginBottom: 12 }}>
              <span className="section-icon">⚠️</span>
              特殊条款
            </div>
            <div className="special-terms">
              {contract.contract_data.special_terms.map((t: string, i: number) => (
                <div key={i} className="special-term-item">
                  <span className="term-icon">!</span>
                  <span className="term-text">{t}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        <div style={{ marginTop: 20 }}>
          <span className="info-label">合同文件</span>
          <div style={{ marginTop: 8 }}>
            {contractFileUrl ? (
              <a href={contractFileUrl} target="_blank" rel="noopener noreferrer" className="file-link">
                <FileOutlined /> 查看原文件
              </a>
            ) : (
              <span className="no-file">暂无文件</span>
            )}
          </div>
        </div>
      </div>

      <div className="payment-section">
        <div className="payment-header">
          <span className="payment-title">收付记录</span>
          <span className="payment-count">{incomePayments.length + expensePayments.length} 笔</span>
        </div>
        {paymentTabItems.length > 0 ? (
          <Tabs items={paymentTabItems} defaultActiveKey={role === 'expense' ? 'expense' : 'income'} />
        ) : (
          <div className="no-payments">
            <DollarOutlined style={{ fontSize: 32, marginBottom: 12, display: 'block', opacity: 0.4 }} />
            暂无记录
          </div>
        )}
      </div>
    </div>
  )
}