import { useState, useEffect, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Button, Alert, Popconfirm, message, Tabs, Tooltip } from 'antd'
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
  EnvironmentOutlined,
  ClockCircleFilled,
  LoadingOutlined,
  PlusOutlined,
  EditOutlined,
  DeleteOutlined,
} from '@ant-design/icons'
import { contractApi } from '@/services/contract'
import { additionalItemApi } from '@/services/contractAdditionalItem'
import { paymentApi } from '@/services/payment'
import AdditionalItemFormModal from '@/components/AdditionalItemFormModal'
import { useAuthStore } from '@/store/useAuthStore'
import { API_BASE_URL } from '@/services/api'
import { formatMoney, formatMoneyShort } from '@/utils/money'
import { isNoReceipt } from '@/utils/payment'
import type { Contract, Payment, ContractAdditionalItem } from '@/types'
import './ContractDetail.css'

const statusMap: Record<string, { text: string; cls: string }> = {
  active:    { text: '执行中', cls: 'status-active' },
  completed: { text: '已完成', cls: 'status-completed' },
}

const businessTypeCls: Record<string, string> = {
  '车辆业务':   'type-vehicle',
  '中港牌业务': 'type-zhonggang',
}

const currencySymbol: Record<string, string> = { CNY: '¥', HKD: 'HK$' }

/** 缩写金额 + 货币符号（主显示用） */
function fmt(amount: number | undefined | null, currency: string): string {
  if (amount === undefined || amount === null) return '-'
  const symbol = currencySymbol[currency] || '¥'
  return `${symbol}${formatMoneyShort(amount)}`
}

/** 完整精确金额 + 货币符号（Tooltip 用） */
function fmtFull(amount: number | undefined | null, currency: string): string {
  if (amount === undefined || amount === null) return '-'
  const symbol = currencySymbol[currency] || '¥'
  return `${symbol}${formatMoney(amount).full}`
}

/** CNY 折算副文字（缩写） */
function fmtCny(amount: number | undefined | null): string {
  if (amount === undefined || amount === null || amount === 0) return ''
  return `≈ ¥${formatMoneyShort(amount)}`
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
  const currencyName = currency === 'CNY' ? '人民幣' : currency === 'HKD' ? '港幣' : currency
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
      if (bigUnitIdx < bigUnitMap.length && i > 0) {
        result = bigUnitMap[bigUnitIdx] + result
      }
    }
  }
  result = result.replace(/零+$/, '')
  if (!result) result = '零'
  if (fracPart > 0) {
    result += '元'
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
  const [receiptLoading, setReceiptLoading] = useState<number | null>(null)
  const [addlModal, setAddlModal] = useState<{ open: boolean; mode: 'add' | 'edit'; editing: ContractAdditionalItem | null }>({ open: false, mode: 'add', editing: null })
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

  // 附加项增删改后刷新详情（同步 additional_items + additional_total_by_currency 冗余字段）
  const reloadDetail = async () => {
    if (!contract) return
    try {
      const c = await contractApi.getById(contract.id)
      setContract(c)
    } catch {
      /* 静默：刷新失败不阻塞用户 */
    }
  }

  const openAddItem = () => setAddlModal({ open: true, mode: 'add', editing: null })
  const openEditItem = (it: ContractAdditionalItem) => setAddlModal({ open: true, mode: 'edit', editing: it })
  const handleDeleteItem = async (it: ContractAdditionalItem) => {
    try {
      await additionalItemApi.remove(it.id)
      message.success('附加项已删除')
      reloadDetail()
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '删除失败')
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

  if (loading) {
    // 骨架屏：与正常布局结构一致 —— 顶栏 / 身份卡 / 财务概览 / 付款时间线
    // 让用户首屏即看到页面骨架，避免空白页
    return (
      <div className="contract-detail-container">
        <div className="detail-header">
          <div className="app-skel-block" style={{ width: 92, height: 32, borderRadius: 6 }} />
        </div>
        <div className="cd-identity-card">
          <div className="cd-id-row">
            <div className="app-skel-block" style={{ width: 56, height: 22, borderRadius: 11 }} />
            <div className="app-skel-block" style={{ width: 80, height: 22, borderRadius: 11 }} />
            <div className="app-skel-block" style={{ width: 140, height: 18 }} />
            <div className="app-skel-block" style={{ width: 220, height: 14, marginLeft: 'auto' }} />
          </div>
          <div className="cd-id-row cd-id-row-sub" style={{ marginTop: 12 }}>
            <div className="app-skel-block app-skel-line w-50" />
            <div className="app-skel-block app-skel-line w-30" />
          </div>
        </div>
        <div className="cd-finance-panel" style={{ marginTop: 16 }}>
          <div className="cd-fn-hero" style={{ display: 'flex', gap: 24, alignItems: 'center' }}>
            <div className="app-skel-block" style={{ width: 220, height: 36 }} />
            <div className="app-skel-block" style={{ flex: 1, height: 12, borderRadius: 6 }} />
            <div className="app-skel-block" style={{ width: 60, height: 16 }} />
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16, marginTop: 16 }}>
            {[0, 1, 2].map(i => (
              <div key={i} style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                <div className="app-skel-block app-skel-line w-40" />
                <div className="app-skel-block" style={{ height: 28, width: '70%' }} />
                <div className="app-skel-block app-skel-line w-60" />
              </div>
            ))}
          </div>
        </div>
        <div style={{ marginTop: 16, display: 'flex', flexDirection: 'column', gap: 10 }}>
          <div className="app-skel-block" style={{ width: 160, height: 18 }} />
          <div style={{ display: 'flex', gap: 12, overflow: 'hidden' }}>
            {Array.from({ length: 4 }).map((_, i) => (
              <div
                key={i}
                className="app-skel-block"
                style={{ width: 220, height: 110, borderRadius: 8, flexShrink: 0 }}
              />
            ))}
          </div>
        </div>
      </div>
    )
  }
  if (error)    return <Alert type="error" message={error} showIcon />
  if (!contract) return <Alert type="warning" message="合同不存在" showIcon />

  const cur = contract.currency
  const progressRaw = calcProgress(contract.paid_amount, contract.total_amount)
  const progress = Math.min(progressRaw, 100)  // 视觉进度条 cap 在 100%
  const authToken = localStorage.getItem('access_token')
  const contractFileUrl = contract.original_file_path
    ? `${API_BASE_URL}/contracts/${contract.id}/file?token=${authToken}`
    : null
  const statusInfo = statusMap[contract.status] || { text: contract.status, cls: '' }
  // 收款三态：未付 / 已结清 / 加项收入（实付 > 合同价，业务上常见的装饰费/过户费/议价加价）
  const paid = Number(contract.paid_amount || 0)
  const total = Number(contract.total_amount || 0)
  const overpaid = Math.max(0, paid - total)
  const unpaid = Math.max(0, total - paid)
  const paymentState: 'pending' | 'cleared' | 'overpaid' =
    overpaid > 0 ? 'overpaid' : unpaid > 0 ? 'pending' : 'cleared'

  // 附加项：分币种汇总 + 业务色色条（卡片左侧色条用合同业务色：车辆钢蓝 / 两地牌朱砂）
  const addlItems = contract.additional_items || []
  const addlSummary = contract.additional_total_by_currency || {}
  const addlEntries = Object.entries(addlSummary).filter(([, v]) => Number(v) > 0)
  const bizColorMap: Record<string, string> = {
    '车辆业务': '#2d5b8a', '车辆买卖': '#2d5b8a',
    '中港牌业务': '#b8423b', '两地牌过户': '#b8423b',
  }
  const addlBarColor = bizColorMap[contract.business_type || ''] || 'var(--brand-primary)'

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
                <Tooltip title={fmtFull(payment.paid_amount, payment.currency)}>
                  <span>{fmt(payment.paid_amount, payment.currency)}</span>
                </Tooltip>
                {payment.paid_amount_in_cny != null && payment.currency !== 'CNY' && (
                  <span className="cd-pay-card-cny">≈ ¥{formatMoneyShort(payment.paid_amount_in_cny)}</span>
                )}
                {isNoReceipt(payment) && (
                  <Tooltip title="无凭证 · 用户口头确认">
                    <span className="cd-pay-card-no-receipt">无凭证</span>
                  </Tooltip>
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
                  <span
                    className="cd-pay-card-receipt"
                    onClick={async (e) => {
                      e.stopPropagation()
                      if (receiptLoading) return
                      setReceiptLoading(payment.id)
                      try {
                        const url = await paymentApi.getReceiptUrl(payment.id)
                        window.open(url, '_blank')
                      } catch {
                        message.error('加载凭证失败')
                      } finally {
                        setReceiptLoading(null)
                      }
                    }}
                  >
                    {receiptLoading === payment.id ? (
                      <LoadingOutlined style={{ marginRight: 2 }} spin />
                    ) : (
                      <EyeOutlined style={{ marginRight: 2 }} />
                    )}
                    凭证
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

      {/* ① 身份 + 基本信息（合并卡片） */}
      <div className="cd-identity-card">
        <div className="cd-id-row">
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
            <span className="cd-contract-title">— {contract.title}</span>
          )}
          <div className="cd-id-meta">
            <span className="cd-contract-num">{contract.contract_number}</span>
            {contract.signed_date && (
              <>
                <span className="cd-id-sep">·</span>
                <CalendarOutlined style={{ fontSize: 12 }} />
                <span>{contract.signed_date}</span>
              </>
            )}
            <span className="cd-id-sep">·</span>
            <span>{cur}</span>
          </div>
        </div>
        {(contract.business_description || contract.remarks || contract.wechat_group || cd?.party_b?.id_number || cd?.party_b?.phone) && (
          <div className="cd-id-row cd-id-row-sub">
            {contract.business_description && (
              <span className="cd-id-meta-item"><span className="cd-id-meta-label">业务描述</span>{contract.business_description}</span>
            )}
            {cd?.party_b?.id_number && (
              <span className="cd-id-meta-item"><span className="cd-id-meta-label">证件</span>{cd.party_b.id_number}</span>
            )}
            {cd?.party_b?.phone && (
              <span className="cd-id-meta-item"><span className="cd-id-meta-label">电话</span>{cd.party_b.phone}</span>
            )}
            {contract.wechat_group && (
              <span className="cd-id-meta-item"><span className="cd-id-meta-label">微信群</span>{contract.wechat_group}</span>
            )}
            {contract.remarks && (
              <span className="cd-id-meta-item"><span className="cd-id-meta-label">备注</span>{contract.remarks}</span>
            )}
          </div>
        )}
      </div>

      {/* ② 财务概览 — 压缩面板 */}
      <div className="cd-finance-panel">

        {/* ── 行1：合同总额 + 进度条（单行） ── */}
        <div className="cd-fn-hero">
          <div className="cd-fn-hero-left">
            <span className="cd-fn-hero-label">合同总额</span>
            <Tooltip title={`${fmtFull(contract.total_amount, cur)}\n${amountToChinese(contract.total_amount, cur)}`}>
              <span className="cd-fn-hero-value">{fmt(contract.total_amount, cur)}</span>
            </Tooltip>
            {showCnyHint && (
              <span className="cd-fn-hero-cny">{fmtCny(contract.total_amount_in_cny || summary?.total_amount_in_cny)}</span>
            )}
          </div>
          <div className="cd-fn-hero-right">
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

        {/* ── 行2：四栏指标（紧凑） ── */}
        <div className="cd-fn-metrics">
          {/* 已收 */}
          <div className="cd-fn-metric">
            <div className="cd-fn-metric-header">
              <span className="cd-fn-metric-dot income" />
              <span className="cd-fn-metric-label">已收金额</span>
            </div>
            <div className="cd-fn-metric-row">
              <Tooltip title={`${fmtFull(contract.paid_amount, cur)}\n${amountToChinese(contract.paid_amount, cur)}`}>
                <span className="cd-fn-metric-value income">{fmt(contract.paid_amount, cur)}</span>
              </Tooltip>
              <span className="cd-fn-metric-tag">{contract.paid_count}笔</span>
              {showCnyHint && (
                <span className="cd-fn-metric-cny">{fmtCny(contract.paid_amount_in_cny || summary?.income?.total_paid_in_cny)}</span>
              )}
            </div>
          </div>

          {/* 剩余尾款 */}
          <div className="cd-fn-metric">
            <div className="cd-fn-metric-header">
              <span className={`cd-fn-metric-dot ${paymentState === 'pending' ? 'remaining' : 'cleared'}`} />
              <span className="cd-fn-metric-label">剩余尾款</span>
            </div>
            <div className="cd-fn-metric-row">
              {paymentState === 'pending' ? (
                <>
                  <Tooltip title={`${fmtFull(contract.remaining_amount, cur)}\n${amountToChinese(contract.remaining_amount, cur)}`}>
                    <span className="cd-fn-metric-value remaining">
                      {fmt(contract.remaining_amount, cur)}
                    </span>
                  </Tooltip>
                  <span className="cd-fn-metric-status remaining">待收中</span>
                  {showCnyHint && (
                    <span className="cd-fn-metric-cny">{fmtCny(contract.remaining_amount_in_cny)}</span>
                  )}
                </>
              ) : (
                <>
                  <span className="cd-fn-metric-value cleared">{fmt(0, cur)}</span>
                  <span className="cd-fn-metric-status cleared">已结清 ✓</span>
                  {paymentState === 'overpaid' && (
                    <Tooltip title={`实付超出合同字面金额 ${fmtFull(overpaid, cur)}。\n常见原因：附加项应收、装饰费、过户费、议价加价、手续费等多付`}>
                      <span className="cd-fn-metric-extra">
                        加项收入 +{fmt(overpaid, cur)}
                      </span>
                    </Tooltip>
                  )}
                </>
              )}
            </div>
          </div>

          {/* 总支出 */}
          <div className="cd-fn-metric">
            <div className="cd-fn-metric-header">
              <span className="cd-fn-metric-dot expense" />
              <span className="cd-fn-metric-label">总支出</span>
            </div>
            <div className="cd-fn-metric-row">
              <Tooltip title={`${fmtFull(contract.total_expense || 0, cur)}\n${amountToChinese(contract.total_expense || 0, cur)}`}>
                <span className="cd-fn-metric-value expense">{fmt(contract.total_expense || 0, cur)}</span>
              </Tooltip>
              {(contract as any).expense_count > 0 && (
                <span className="cd-fn-metric-tag expense">{(contract as any).expense_count}笔</span>
              )}
              {showCnyHint && (
                <span className="cd-fn-metric-cny">{fmtCny(contract.total_expense_in_cny || summary?.expense?.total_expense_in_cny)}</span>
              )}
            </div>
          </div>

          {/* 净利润 */}
          <div className="cd-fn-metric">
            <div className="cd-fn-metric-header">
              <span className={`cd-fn-metric-dot ${profitMain >= 0 ? 'income' : 'expense'}`} />
              <span className="cd-fn-metric-label">净利润</span>
            </div>
            <div className="cd-fn-metric-row">
              <Tooltip title={`${fmtFull(profitMain, cur)}\n${amountToChinese(Math.abs(profitMain), cur)}`}>
                <span className={`cd-fn-metric-value ${profitMain >= 0 ? 'income' : 'expense'}`}>
                  {fmt(profitMain, cur)}
                </span>
              </Tooltip>
              {showCnyHint && profitCny !== 0 && (
                <span className="cd-fn-metric-cny">{fmtCny(profitCny)}</span>
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

      {/* ⑥ 附加项明细 — 应收清单的细化补充（车险/保养/人工费等），非独立财务实体 */}
      <div className="cd-addl-section">
        <div className="cd-section-title cd-addl-title">
          <span><DollarOutlined /> 附加项明细{addlItems.length > 0 && ` (${addlItems.length})`}</span>
          {role !== 'expense' && (
            <Button size="small" type="primary" icon={<PlusOutlined />} onClick={openAddItem} className="cd-addl-add-btn">
              添加附加项
            </Button>
          )}
        </div>

        {addlItems.length > 0 ? (
          <>
            <div className="cd-addl-grid">
              {addlItems.map((it) => (
                <div key={it.id} className="cd-addl-card" style={{ borderLeftColor: addlBarColor }}>
                  <div className="cd-addl-card-head">
                    <span className="cd-addl-card-name">{it.name}</span>
                    <Tooltip title={fmtFull(it.amount, it.currency)}>
                      <span className="cd-addl-card-amount">{fmt(it.amount, it.currency)}</span>
                    </Tooltip>
                  </div>
                  {it.paid_to && <div className="cd-addl-card-paidto">付：{it.paid_to}</div>}
                  {it.description && <div className="cd-addl-card-desc">{it.description}</div>}
                  {(it.occurred_date || it.remarks) && (
                    <div className="cd-addl-card-meta">
                      {it.occurred_date && <span>{it.occurred_date}</span>}
                      {it.remarks && <span className="cd-addl-card-remarks">{it.remarks}</span>}
                    </div>
                  )}
                  {role !== 'expense' && (
                    <div className="cd-addl-card-actions">
                      <Tooltip title="编辑">
                        <EditOutlined onClick={() => openEditItem(it)} />
                      </Tooltip>
                      <Popconfirm
                        title="删除附加项"
                        description="引用此附加项的付款标签会自动置空。"
                        onConfirm={() => handleDeleteItem(it)}
                        okText="删除"
                        cancelText="取消"
                      >
                        <DeleteOutlined className="cd-addl-act-del" />
                      </Popconfirm>
                    </div>
                  )}
                </div>
              ))}
            </div>
            {addlEntries.length > 0 && (
              <div className="cd-addl-summary">
                <span className="cd-addl-summary-label">附加项汇总</span>
                {addlEntries.map(([cur, amt]) => (
                  <span key={cur} className="cd-addl-summary-val">{fmt(Number(amt), cur)}</span>
                ))}
              </div>
            )}
          </>
        ) : (
          <div className="cd-addl-empty">
            {role !== 'expense' ? '暂无附加项。可添加车险、保养改装、人工费等应收项。' : '暂无附加项'}
          </div>
        )}
      </div>

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
                    <Tooltip title={fmtFull(term.amount, contract.currency)}>
                      <span className="cd-term-step-amount">
                        {fmt(term.amount, contract.currency)}
                      </span>
                    </Tooltip>
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

      {/* 附加项 新增/编辑 表单 Modal */}
      <AdditionalItemFormModal
        open={addlModal.open}
        mode={addlModal.mode}
        contractId={contract.id}
        contractCurrency={cur}
        editing={addlModal.editing}
        onClose={() => setAddlModal({ open: false, mode: 'add', editing: null })}
        onSuccess={reloadDetail}
      />

    </div>
  )
}
