import { useState, useEffect, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Button, Spin, Alert, Popconfirm, message, Tabs, Tooltip } from 'antd'
import {
  ArrowLeftOutlined,
  FileOutlined,
  CheckCircleOutlined,
  CheckCircleFilled,
  DollarOutlined,
  UserOutlined,
  CalendarOutlined,
  FileTextOutlined,
  EyeOutlined,
  IdcardOutlined,
  PhoneOutlined,
  EnvironmentOutlined,
  ClockCircleFilled,
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

function amountToChinese(amount: number, currency: string): string {
  if (amount === 0) {
    const cn = currency === 'CNY' ? '人民幣' : currency === 'HKD' ? '港幣' : currency
    return `${cn}零元整`
  }
  const digitMap = ['零', '壹', '貳', '叁', '肆', '伍', '陸', '柒', '捌', '玖']
  const unitMap = ['', '拾', '佰', '仟']
  const bigUnitMap = ['', '萬', '億']
  const currencyName = currency === 'CNY' ? '人民幣' : currency === 'HKD' ? '港幣' : currency === 'USD' ? '美元' : currency
  const intPart = Math.floor(amount)
  const fracPart = Math.round((amount - intPart) * 100)
  let result = ''
  let intStr = intPart.toString()
  let unitIdx = 0
  let bigUnitIdx = 0
  let hasNonZero = false
  for (let i = intStr.length - 1; i >= 0; i--) {
    const digit = parseInt(intStr[i])
    if (digit !== 0) {
      result = digitMap[digit] + unitMap[unitIdx] + result
      hasNonZero = true
    } else if (hasNonZero) {
      result = digitMap[0] + result
      hasNonZero = false
    }
    unitIdx++
    if (unitIdx === 4) {
      unitIdx = 0
      bigUnitIdx++
      if (bigUnitIdx < bigUnitMap.length) {
        result = bigUnitMap[bigUnitIdx] + result
      }
    }
  }
  result = result.replace(/零+$/, '')
  if (!result) result = '零'
  if (fracPart > 0) {
    const jiao = Math.floor(fracPart / 10)
    const fen = fracPart % 10
    if (jiao > 0) result += digitMap[jiao] + '角'
    if (fen > 0) result += digitMap[fen] + '分'
  } else {
    result += '元整'
  }
  return `${currencyName}${result}`
}

const paymentStatusMap: Record<string, { text: string }> = {
  pending:   { text: '待确认' },
  partial:   { text: '部分支付' },
  paid:      { text: '已确认' },
  cancelled: { text: '已取消' },
}

const methodMap: Record<string, string> = {
  bank_transfer: '银行转账',
  wechat: '微信',
  alipay: '支付宝',
  cash: '现金',
  check: '支票',
}

/** 从 receipt_data 中提取摘要信息 */
function receiptSummary(data: Record<string, any> | undefined): string | null {
  if (!data || typeof data !== 'object') return null
  const parts: string[] = []
  if (data.payer_name) parts.push(`付款人: ${data.payer_name}`)
  if (data.amount) {
    const sym = currencySymbol[data.currency] || ''
    parts.push(`金额: ${sym}${data.amount}`)
  }
  if (data.transaction_date) parts.push(`日期: ${data.transaction_date}`)
  if (data.payee_name) parts.push(`收款人: ${data.payee_name}`)
  return parts.length > 0 ? parts.join(' | ') : null
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

  // 利润计算 — 以合同主要币种为基准
  const profitMain = (contract.paid_amount || 0) - (contract.total_expense || 0)
  const totalIncomeCny  = summary?.income?.total_paid_in_cny   || contract.paid_amount_in_cny   || 0
  const totalExpenseCny = summary?.expense?.total_expense_in_cny || contract.total_expense_in_cny || 0
  const profitCny = summary?.profit_in_cny ?? (totalIncomeCny - totalExpenseCny)

  // CNY 折算副文字（仅非 CNY 合同显示）
  const showCnyHint = cur !== 'CNY'

  // ── 付款记录横向卡片 ──
  const renderPaymentTimeline = (payments: Payment[], isExpense: boolean) => {
    if (payments.length === 0) {
      return (
        <div className="cd-no-payments">
          <DollarOutlined style={{ fontSize: 28, marginBottom: 10, display: 'block', opacity: 0.3 }} />
          暂无{isExpense ? '支出' : '收入'}记录
        </div>
      )
    }
    return (
      <div className="cd-payment-row">
        {payments.map((payment) => {
          const isPaid = payment.status === 'paid'
          return (
            <div key={payment.id} className={`cd-pay-card ${payment.status}`}>
              <div className="cd-pay-card-top">
                <span className="cd-pay-card-period">
                  {isPaid
                    ? <CheckCircleFilled style={{ color: '#0d9488', marginRight: 4, fontSize: 13 }} />
                    : <ClockCircleFilled style={{ color: '#94a3b8', marginRight: 4, fontSize: 13 }} />
                  }
                  第{payment.installment_number}期
                </span>
                {isExpense && payment.payee_name && (
                  <span className="cd-pay-card-payee">{payment.payee_name}</span>
                )}
                <span className={`cd-pay-card-status ${payment.status}`}>
                  {paymentStatusMap[payment.status]?.text || payment.status}
                </span>
              </div>
              <div className={`cd-pay-card-amount ${isPaid ? 'settled' : isExpense ? 'expense' : 'pending'}`}>
                {fmt(payment.paid_amount, payment.currency)}
                {payment.paid_amount_in_cny != null && payment.currency !== 'CNY' && (
                  <span className="cd-pay-card-cny">≈ ¥{Math.round(payment.paid_amount_in_cny).toLocaleString('zh-CN')}</span>
                )}
              </div>
              <div className="cd-pay-card-meta">
                {payment.paid_date && <span>{payment.paid_date}</span>}
                {payment.payment_method && (
                  <span className="cd-pay-card-method">
                    {methodMap[payment.payment_method] || payment.payment_method}
                  </span>
                )}
                {payment.receipt_image_path ? (
                  <span className="cd-pay-card-receipt" onClick={async (e) => {
                    e.stopPropagation()
                    try { const url = await paymentApi.getReceiptUrl(payment.id); window.open(url, '_blank') }
                    catch { message.error('加载凭证失败') }
                  }}>
                    <EyeOutlined style={{ marginRight: 2 }} />凭证
                  </span>
                ) : payment.receipt_data ? (
                  <Tooltip title={receiptSummary(payment.receipt_data)}>
                    <span className="cd-pay-card-receipt">
                      <FileTextOutlined style={{ marginRight: 2 }} />凭证
                    </span>
                  </Tooltip>
                ) : null}
              </div>
              {payment.description && (
                <div className="cd-pay-card-desc">{payment.description}</div>
              )}
            </div>
          )
        })}
      </div>
    )
  }

  const paymentTabItems = []
  if (role !== 'expense') {
    paymentTabItems.push({
      key: 'income',
      label: `收入记录 (${incomePayments.length})`,
      children: renderPaymentTimeline(incomePayments, false),
    })
  }
  if (role !== 'income') {
    paymentTabItems.push({
      key: 'expense',
      label: `支出记录 (${expensePayments.length})`,
      children: renderPaymentTimeline(expensePayments, true),
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
                <div className="cd-info-label">
                  <FileTextOutlined className="cd-info-label-icon" />
                  业务描述
                </div>
                <div className="cd-info-value" style={{ whiteSpace: 'normal' }}>{contract.business_description}</div>
              </div>
            )}
            {cd?.party_b?.id_number && (
              <div className="cd-info-item">
                <div className="cd-info-label">
                  <IdcardOutlined className="cd-info-label-icon" />
                  证件号码
                </div>
                <div className="cd-info-value">{cd.party_b.id_number}</div>
              </div>
            )}
            {cd?.party_b?.phone && (
              <div className="cd-info-item">
                <div className="cd-info-label">
                  <PhoneOutlined className="cd-info-label-icon" />
                  客户电话
                </div>
                <div className="cd-info-value">{cd.party_b.phone}</div>
              </div>
            )}
            {contract.wechat_group && (
              <div className="cd-info-item">
                <div className="cd-info-label">
                  <svg className="cd-info-label-icon" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"/></svg>
                  微信群
                </div>
                <div className="cd-info-value">{contract.wechat_group}</div>
              </div>
            )}
            {contract.remarks && (
              <div className="cd-info-item span2">
                <div className="cd-info-label">
                  <FileTextOutlined className="cd-info-label-icon" />
                  备注
                </div>
                <div className="cd-info-value" style={{ whiteSpace: 'normal' }}>{contract.remarks}</div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ③ 财务概览 — 统一面板 */}
      <div className="cd-finance-panel">

        {/* ── 行1：合同总额（主角）+ 进度条 ── */}
        <div className="cd-fn-hero">
          <div className="cd-fn-hero-main">
            <span className="cd-fn-hero-label">合同总额</span>
            <span className="cd-fn-hero-value">
              {fmt(contract.total_amount, cur)}
            </span>
            <span className="cd-fn-hero-chinese">{amountToChinese(contract.total_amount, cur)}</span>
            {showCnyHint && (
              <span className="cd-fn-hero-sub">{fmtCny(contract.total_amount_in_cny || summary?.total_amount_in_cny)}</span>
            )}
          </div>
          <div className="cd-fn-hero-progress">
            <span className="cd-fn-progress-label">收款进度</span>
            <div className="cd-fn-progress-track">
              <div
                className={`cd-fn-progress-fill ${progress === 100 ? 'done' : ''}`}
                style={{ width: `${progress}%` }}
              />
            </div>
            <span className={`cd-fn-progress-pct ${progress === 100 ? 'done' : ''}`}>{progress}%</span>
          </div>
        </div>

        {/* ── 行2：已收 / 剩余 / 总支出 三栏 ── */}
        <div className="cd-fn-cards">
          {/* 已收 */}
          <div className="cd-fn-card fn-income">
            <div className="fn-card-header">
              <span className="fn-card-dot income" />
              <span className="fn-card-label">已收金额</span>
            </div>
            <div className="fn-card-value income">{fmt(contract.paid_amount, cur)}</div>
            <div className="fn-card-chinese">{amountToChinese(contract.paid_amount, cur)}</div>
            <div className="fn-card-meta">
              <span className="fn-card-tag">{contract.paid_count}笔</span>
              {showCnyHint && (
                <span className="fn-card-cny">{fmtCny(contract.paid_amount_in_cny || summary?.income?.total_paid_in_cny)}</span>
              )}
            </div>
          </div>

          {/* 剩余尾款 — 视觉重点 */}
          <div className={`cd-fn-card ${isRemaining ? 'fn-remaining' : 'fn-cleared'}`}>
            <div className="fn-card-header">
              <span className={`fn-card-dot ${isRemaining ? 'remaining' : 'cleared'}`} />
              <span className="fn-card-label">剩余尾款</span>
            </div>
            <div className={`fn-card-value ${isRemaining ? 'remaining' : 'cleared'}`}>
              {fmt(contract.remaining_amount, cur)}
            </div>
            <div className="fn-card-chinese">{amountToChinese(contract.remaining_amount, cur)}</div>
            <div className="fn-card-meta">
              <span className={`fn-card-status ${isRemaining ? 'remaining' : 'cleared'}`}>
                {isRemaining ? '待收中' : '已结清 ✓'}
              </span>
              {showCnyHint && (
                <span className="fn-card-cny">{fmtCny(contract.remaining_amount_in_cny)}</span>
              )}
            </div>
          </div>

          {/* 总支出 */}
          <div className="cd-fn-card fn-expense">
            <div className="fn-card-header">
              <span className="fn-card-dot expense" />
              <span className="fn-card-label">总支出</span>
            </div>
            <div className="fn-card-value expense">{fmt(contract.total_expense || 0, cur)}</div>
            <div className="fn-card-chinese">{amountToChinese(contract.total_expense || 0, cur)}</div>
            <div className="fn-card-meta">
              {(contract as any).expense_count > 0 && (
                <span className="fn-card-tag expense">{(contract as any).expense_count}笔</span>
              )}
              {showCnyHint && (
                <span className="fn-card-cny">{fmtCny(contract.total_expense_in_cny || summary?.expense?.total_expense_in_cny)}</span>
              )}
            </div>
          </div>

          {/* 净利润 — 以合同币种为主，CNY 折算小字 */}
          <div className={`cd-fn-card fn-profit`}>
            <div className="fn-card-header">
              <span className={`fn-card-dot ${profitMain >= 0 ? 'income' : 'expense'}`} />
              <span className="fn-card-label">净利润</span>
            </div>
            <div className={`fn-card-value ${profitMain >= 0 ? 'income' : 'expense'}`}>
              {fmt(profitMain, cur)}
            </div>
            <div className="fn-card-chinese">{amountToChinese(Math.abs(profitMain), cur)}</div>
            <div className="fn-card-meta">
              {showCnyHint && profitCny !== 0 && (
                <span className="fn-card-cny">{fmtCny(profitCny)}</span>
              )}
            </div>
          </div>
        </div>

      </div>

      {/* ⑤ 车辆信息（紧凑条） */}
      {cd?.vehicle_info?.plate_number || cd?.vehicle_info?.vehicle_model || cd?.port ? (
        <div className="cd-info-strip">
          <div className="cd-info-grid">
            {cd?.vehicle_info?.plate_number && (
              <div className="cd-info-item">
                <div className="cd-info-label">
                  <svg className="cd-info-label-icon" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><rect x="2" y="6" width="20" height="11" rx="3"/><circle cx="7" cy="18" r="2"/><circle cx="17" cy="18" r="2"/><line x1="6" y1="12" x2="10" y2="12"/><line x1="14" y1="12" x2="18" y2="12"/></svg>
                  车牌号
                </div>
                <div className="cd-info-value">{cd.vehicle_info.plate_number}</div>
              </div>
            )}
            {cd?.vehicle_info?.vehicle_model && (
              <div className="cd-info-item">
                <div className="cd-info-label">
                  <svg className="cd-info-label-icon" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><rect x="2" y="3" width="20" height="12" rx="2"/><path d="M22 17H2v3a1 1 0 0 0 1 1h18a1 1 0 0 0 1-1v-3z"/><line x1="4" y1="7" x2="8" y2="7"/><line x1="12" y1="7" x2="16" y2="7"/><line x1="6" y1="10" x2="12" y2="10"/></svg>
                  车型
                </div>
                <div className="cd-info-value">{cd.vehicle_info.vehicle_model}</div>
              </div>
            )}
            {cd?.port && (
              <div className="cd-info-item">
                <div className="cd-info-label">
                  <EnvironmentOutlined className="cd-info-label-icon" />
                  通行口岸
                </div>
                <div className="cd-info-value">{cd.port}</div>
              </div>
            )}
          </div>
        </div>
      ) : null}

      {/* ⑦ 付款条款 — 步骤图标化 */}
      {cd?.payment_terms && cd.payment_terms.length > 0 && (
        <div className="cd-section">
          <div className="cd-section-title">
            <DollarOutlined /> 付款条款
          </div>
          <div className="cd-payment-terms-steps">
            {cd.payment_terms.map((term: any, i: number) => {
              // 兼容历史数据：旧合同存的是 installment_name 而非 name，且无 condition
              const termName = term.name || term.installment_name || `第 ${i + 1} 期`
              const dueDateStr = term.due_date ? String(term.due_date).trim() : ''
              const isIsoDate = /^\d{4}-\d{2}-\d{2}$/.test(dueDateStr)
              const condText = term.condition
                ? term.condition
                : term.due_date
                  ? (isIsoDate ? `约定付款：${term.due_date}` : `约定：${term.due_date}`)
                  : null
              return (
                <div key={i} className="cd-term-step">
                  <div className="cd-term-step-num">{i + 1}</div>
                  <div className="cd-term-step-body">
                    <div className="cd-term-step-left">
                      <span className="cd-term-step-name">{termName}</span>
                      {condText && (
                        <span className="cd-term-step-cond">{condText}</span>
                      )}
                    </div>
                    <span className="cd-term-step-amount">
                      {fmt(term.amount, contract.currency)}
                    </span>
                  </div>
                </div>
              )
            })}
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
