import { useState, useEffect, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Button, Spin, Table, Tag, Alert, Popconfirm, message, Tabs } from 'antd'
import {
  ArrowLeftOutlined,
  FileOutlined,
  CheckCircleOutlined,
  DollarOutlined,
  UserOutlined,
  ExclamationCircleOutlined,
  CalendarOutlined,
} from '@ant-design/icons'
import { contractApi } from '@/services/contract'
import { paymentApi } from '@/services/payment'
import { useAuthStore } from '@/store/useAuthStore'
import { API_BASE_URL } from '@/services/api'
import type { Contract, Payment } from '@/types'
import './ContractDetail.css'

const statusMap: Record<string, { text: string; cls: string }> = {
  active:    { text: '执行中', cls: 'status-active' },
  completed: { text: '已完成', cls: 'status-completed' },
}

const businessTypeCls: Record<string, string> = {
  '车辆业务':   'type-vehicle',
  '中港牌业务': 'type-zhonggang',
}

const currencySymbol: Record<string, string> = { CNY: '¥', HKD: 'HK$', USD: '$' }

function fmt(amount: number | undefined | null, currency: string): string {
  if (amount === undefined || amount === null) return '-'
  const symbol = currencySymbol[currency] || '¥'
  return `${symbol}${amount.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

function fmtCny(amount: number | undefined | null): string {
  if (amount === undefined || amount === null || amount === 0) return ''
  return `≈ ¥${Math.round(amount).toLocaleString('zh-CN')}`
}

function calcProgress(paid: number, total: number): number {
  if (total === 0) return 0
  return Math.round((paid / total) * 100)
}

const paymentStatusMap: Record<string, { text: string }> = {
  pending:   { text: '待支付' },
  partial:   { text: '部分支付' },
  paid:      { text: '已支付' },
  overdue:   { text: '逾期' },
  cancelled: { text: '已取消' },
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
        setIncomePayments(data.income?.payments || [])
        setExpensePayments(data.expense?.payments || [])
      })
      .catch((e) => {
        if (e?.name === 'AbortError' || e?.code === 'ERR_CANCELED') return
        setError(e.response?.data?.detail || '加载失败')
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false)
      })
    return () => { controller.abort() }
  }, [id])

  if (loading) return <div style={{ textAlign: 'center', padding: 80 }}><Spin tip="加载中..." /></div>
  if (error)    return <Alert type="error" message={error} showIcon />
  if (!contract) return <Alert type="warning" message="合同不存在" showIcon />

  const cur = contract.currency
  const progress = calcProgress(contract.paid_amount, contract.total_amount)
  const authToken = localStorage.getItem('access_token')
  const contractFileUrl = contract.original_file_path
    ? `${API_BASE_URL}/contracts/${contract.id}/file?token=${authToken}`
    : null
  const statusInfo = statusMap[contract.status] || { text: contract.status, cls: '' }
  const isRemaining = contract.remaining_amount > 0

  // 利润计算
  const totalIncomeCny  = summary?.income?.total_paid_in_cny   || contract.paid_amount_in_cny   || 0
  const totalExpenseCny = summary?.expense?.total_expense_in_cny || contract.total_expense_in_cny || 0
  const profitCny = summary?.profit_in_cny ?? (totalIncomeCny - totalExpenseCny)

  // CNY 折算副文字（仅非 CNY 合同显示）
  const showCnyHint = cur !== 'CNY'

  const paymentColumns = [
    { title: '期数', dataIndex: 'installment_number', key: 'installment_number', width: 60 },
    { title: '期数名称', dataIndex: 'installment_name', key: 'installment_name', render: (v: string) => v || '-' },
    { title: '币种', dataIndex: 'currency', key: 'currency', width: 60 },
    { title: '金额', dataIndex: 'paid_amount', key: 'paid_amount', render: (v: number, r: Payment) => fmt(v, r.currency) },
    { title: '折CNY', dataIndex: 'paid_amount_in_cny', key: 'paid_amount_in_cny', width: 100, render: (v: number | null) => v != null ? fmt(v, 'CNY') : '-' },
    { title: '付款日期', dataIndex: 'paid_date', key: 'paid_date', width: 110, render: (v: string) => v || '-' },
    { title: '方式', dataIndex: 'payment_method', key: 'payment_method', width: 80, render: (v: string) => v || '-' },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 80,
      render: (s: string) => (
        <span className={`payment-status ${s}`}>{paymentStatusMap[s]?.text || s}</span>
      ),
    },
  ]

  const expenseColumns = [
    { title: '期数', dataIndex: 'installment_number', key: 'installment_number', width: 60 },
    { title: '收款方', dataIndex: 'payee_name', key: 'payee_name', render: (v: string) => v || '-' },
    { title: '币种', dataIndex: 'currency', key: 'currency', width: 60 },
    { title: '金额', dataIndex: 'paid_amount', key: 'paid_amount', render: (v: number, r: Payment) => fmt(v, r.currency) },
    { title: '折CNY', dataIndex: 'paid_amount_in_cny', key: 'paid_amount_in_cny', width: 100, render: (v: number | null) => v != null ? fmt(v, 'CNY') : '-' },
    { title: '付款日期', dataIndex: 'paid_date', key: 'paid_date', width: 110, render: (v: string) => v || '-' },
    { title: '方式', dataIndex: 'payment_method', key: 'payment_method', width: 80, render: (v: string) => v || '-' },
  ]

  const paymentTabItems = []
  if (role !== 'expense') {
    paymentTabItems.push({
      key: 'income',
      label: `收入记录 (${incomePayments.length})`,
      children: incomePayments.length > 0 ? (
        <Table columns={paymentColumns} dataSource={incomePayments} rowKey="id" size="small" pagination={false} scroll={{ x: 800 }} />
      ) : (
        <div className="cd-no-payments">
          <DollarOutlined style={{ fontSize: 28, marginBottom: 10, display: 'block', opacity: 0.3 }} />
          暂无收入记录
        </div>
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
        <div className="cd-no-payments">
          <DollarOutlined style={{ fontSize: 28, marginBottom: 10, display: 'block', opacity: 0.3 }} />
          暂无支出记录
        </div>
      ),
    })
  }

  const cd = contract.contract_data
  const hasVehicleInfo = cd?.vehicle_info?.plate_number || cd?.vehicle_info?.vehicle_model || cd?.port || cd?.party_b?.id_number || cd?.party_b?.phone

  return (
    <div className="contract-detail-container">

      {/* 顶部按钮栏 */}
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

      {/* ① Topbar：身份信息 */}
      <div className="cd-topbar">
        <div className="cd-topbar-left">
          {contract.status && (
            <span className={`cd-badge ${statusInfo.cls}`}>{statusInfo.text}</span>
          )}
          {contract.business_type && (
            <span className={`cd-badge ${businessTypeCls[contract.business_type] || 'type-default'}`}>
              {contract.business_type}
            </span>
          )}
          <UserOutlined style={{ color: '#8c8c8c', fontSize: 13 }} />
          <span className="cd-customer-name">{contract.customer_name || '无客户名称'}</span>
          {contract.title && (
            <span style={{ fontSize: 13, color: '#8c8c8c' }}>— {contract.title}</span>
          )}
        </div>
        <div className="cd-topbar-right">
          <span className="cd-contract-num">{contract.contract_number}</span>
          {contract.signed_date && (
            <>
              <span className="cd-topbar-sep">·</span>
              <CalendarOutlined style={{ fontSize: 12 }} />
              <span>{contract.signed_date}</span>
            </>
          )}
          <span className="cd-topbar-sep">·</span>
          <span>{cur}</span>
        </div>
      </div>

      {/* ② 合同基本信息 + 证件号码/客户电话（紧凑条） */}
      {(contract.business_description || contract.remarks || contract.wechat_group || hasVehicleInfo) && (
        <div className="cd-info-strip">
          <div className="cd-info-grid cols3">
            {contract.business_description && (
              <div className="cd-info-item">
                <div className="cd-info-label">业务描述</div>
                <div className="cd-info-value" style={{ whiteSpace: 'normal' }}>{contract.business_description}</div>
              </div>
            )}
            {cd?.party_b?.id_number && (
              <div className="cd-info-item">
                <div className="cd-info-label">证件号码</div>
                <div className="cd-info-value">{cd.party_b.id_number}</div>
              </div>
            )}
            {cd?.party_b?.phone && (
              <div className="cd-info-item">
                <div className="cd-info-label">客户电话</div>
                <div className="cd-info-value">{cd.party_b.phone}</div>
              </div>
            )}
            {contract.wechat_group && (
              <div className="cd-info-item">
                <div className="cd-info-label">微信群</div>
                <div className="cd-info-value">{contract.wechat_group}</div>
              </div>
            )}
            {contract.remarks && (
              <div className="cd-info-item span2">
                <div className="cd-info-label">备注</div>
                <div className="cd-info-value" style={{ whiteSpace: 'normal' }}>{contract.remarks}</div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ③ KPI 行：4 个指标卡 */}
      <div className="cd-kpi-row">
        {/* 合同总额 — 主角卡，2倍字号 */}
        <div className="cd-kpi-card primary">
          <div className="cd-kpi-label">合同总额</div>
          <div className="cd-kpi-value">{fmt(contract.total_amount, cur)}</div>
          {showCnyHint && (
            <div className="cd-kpi-sub">{fmtCny(contract.total_amount_in_cny || summary?.total_amount_in_cny)}</div>
          )}
        </div>

        {/* 已收金额 */}
        <div className="cd-kpi-card income">
          <div className="cd-kpi-label">已收金额</div>
          <div className="cd-kpi-value success">{fmt(contract.paid_amount, cur)}</div>
          {showCnyHint && (
            <div className="cd-kpi-sub">{fmtCny(contract.paid_amount_in_cny || summary?.income?.total_paid_in_cny)}</div>
          )}
        </div>

        {/* 总支出 */}
        <div className="cd-kpi-card expense">
          <div className="cd-kpi-label">总支出</div>
          <div className="cd-kpi-value danger">{fmt(contract.total_expense || 0, cur)}</div>
          {showCnyHint && (
            <div className="cd-kpi-sub">{fmtCny(contract.total_expense_in_cny || summary?.expense?.total_expense_in_cny)}</div>
          )}
        </div>

        {/* 剩余尾款 */}
        <div className={`cd-kpi-card ${isRemaining ? 'remaining-unpaid' : 'remaining-paid'}`}>
          <div className="cd-kpi-label">剩余尾款</div>
          <div className={`cd-kpi-value ${isRemaining ? 'danger' : ''}`}>
            {isRemaining
              ? <><ExclamationCircleOutlined style={{ marginRight: 4, fontSize: 14 }} />{fmt(contract.remaining_amount, cur)}</>
              : <><CheckCircleOutlined style={{ marginRight: 4, fontSize: 14, color: '#52c41a' }} />{fmt(contract.remaining_amount, cur)}</>
            }
          </div>
          {showCnyHint && (
            <div className="cd-kpi-sub">{fmtCny(contract.remaining_amount_in_cny)}</div>
          )}
        </div>
      </div>

      {/* ③ 进度条 */}
      <div className="cd-progress-row">
        <span className="cd-progress-label">收款进度</span>
        <div className="cd-progress-track">
          <div className={`cd-progress-fill ${progress === 100 ? 'complete' : ''}`} style={{ width: `${progress}%` }} />
        </div>
        <span className={`cd-progress-pct ${progress === 100 ? 'complete' : ''}`}>{progress}%</span>
      </div>

      {/* ④ P&L 单行条（收支利润 CNY 折算，仅 admin / 有权限时展示） */}
      {role !== 'income' && role !== 'expense' && (
        <div className="cd-pnl-row">
          <div className="cd-pnl-section-label">
            收支利润
            {showCnyHint && <><br /><span style={{ fontSize: 10 }}>（折 CNY）</span></>}
          </div>
          <div className="cd-pnl-sep" />
          <div className="cd-pnl-item">
            <div className="cd-pnl-item-label">已收</div>
            <div className="cd-pnl-item-value income">{fmt(totalIncomeCny, 'CNY')}</div>
          </div>
          <div className="cd-pnl-sep" />
          <div className="cd-pnl-item">
            <div className="cd-pnl-item-label">总支出</div>
            <div className="cd-pnl-item-value expense">{fmt(totalExpenseCny, 'CNY')}</div>
          </div>
          <div className="cd-pnl-sep" />
          <div className="cd-pnl-item">
            <div className="cd-pnl-item-label">净利润</div>
            <div className={`cd-pnl-item-value ${profitCny >= 0 ? 'profit-pos' : 'profit-neg'}`}>
              {fmt(profitCny, 'CNY')}
            </div>
          </div>
        </div>
      )}

      {/* ⑤ 车辆信息（紧凑条） */}
      {cd?.vehicle_info?.plate_number || cd?.vehicle_info?.vehicle_model || cd?.port ? (
        <div className="cd-info-strip">
          <div className="cd-info-grid">
            {cd?.vehicle_info?.plate_number && (
              <div className="cd-info-item">
                <div className="cd-info-label">车牌号</div>
                <div className="cd-info-value">{cd.vehicle_info.plate_number}</div>
              </div>
            )}
            {cd?.vehicle_info?.vehicle_model && (
              <div className="cd-info-item">
                <div className="cd-info-label">车型</div>
                <div className="cd-info-value">{cd.vehicle_info.vehicle_model}</div>
              </div>
            )}
            {cd?.port && (
              <div className="cd-info-item">
                <div className="cd-info-label">通行口岸</div>
                <div className="cd-info-value">{cd.port}</div>
              </div>
            )}
          </div>
        </div>
      ) : null}

      {/* ⑦ 付款条款 */}
      {cd?.payment_terms && cd.payment_terms.length > 0 && (
        <div className="cd-section">
          <div className="cd-section-title">
            <span>💰</span> 付款条款
          </div>
          <div className="cd-payment-terms">
            {cd.payment_terms.map((term: any, i: number) => (
              <div key={i} className="cd-payment-term-item">
                <Tag color="blue" style={{ margin: 0 }}>{term.name}</Tag>
                <span className="cd-term-amount">{fmt(term.amount, contract.currency)}</span>
                {term.condition && <span className="cd-term-condition">（{term.condition}）</span>}
              </div>
            ))}
          </div>
        </div>
      )}


      {/* ⑧ 合同文件 */}
      <div className="cd-section">
        <div className="cd-section-title">
          <FileOutlined /> 合同文件
        </div>
        {contractFileUrl ? (
          <a href={contractFileUrl} target="_blank" rel="noopener noreferrer" className="cd-file-link">
            <FileOutlined /> 查看原文件
          </a>
        ) : (
          <span className="cd-no-file">暂无文件</span>
        )}
      </div>

      {/* ⑩ 收付记录 */}
      <div className="cd-payment-section">
        <div className="cd-payment-header">
          <span className="cd-payment-title">收付记录</span>
          <span className="cd-payment-count">{incomePayments.length + expensePayments.length} 笔</span>
        </div>
        {paymentTabItems.length > 0 ? (
          <Tabs
            items={paymentTabItems}
            defaultActiveKey={role === 'expense' ? 'expense' : 'income'}
            style={{ padding: '0 4px' }}
          />
        ) : (
          <div className="cd-no-payments">
            <DollarOutlined style={{ fontSize: 28, marginBottom: 10, display: 'block', opacity: 0.3 }} />
            暂无记录
          </div>
        )}
      </div>

    </div>
  )
}
