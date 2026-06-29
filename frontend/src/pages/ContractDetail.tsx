import { useState, useEffect, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Button, Alert, Popconfirm, message, Tabs, Tooltip, Image, Collapse } from 'antd'
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
  WarningOutlined,
} from '@ant-design/icons'
import { contractApi } from '@/services/contract'
import { paymentApi } from '@/services/payment'
import PaymentNoticeModal from '@/components/PaymentNoticeModal'
import { useAuthStore } from '@/store/useAuthStore'
import { API_BASE_URL } from '@/services/api'
import {
  fmt, fmtFull, amountToChinese, currencySymbol, methodMap,
} from '@/utils/moneyFormat'
import { isNoReceipt } from '@/utils/payment'
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

const paymentStatusMap: Record<string, { text: string }> = {
  pending:   { text: '待确认' },
  partial:   { text: '部分支付' },
  paid:      { text: '已确认' },
  cancelled: { text: '已取消' },
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
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const [noticeOpen, setNoticeOpen] = useState(false)
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
  const authToken = localStorage.getItem('access_token')
  const contractFileUrl = contract.original_file_path
    ? `${API_BASE_URL}/contracts/${contract.id}/file?token=${authToken}`
    : null
  const statusInfo = statusMap[contract.status] || { text: contract.status, cls: '' }
  // 应收口径：直接以合同 total_amount 为准（系统不再维护附加项）
  const paid = Number((contract.paid_by_currency || {})[contract.currency] ?? contract.paid_amount ?? 0)
  const total = Number(contract.total_amount || 0)
  const receivable = total
  const overpaid = Math.max(0, paid - receivable)

  // 改造后：剩余尾款不再 total-paid 算，直接取后端派生的最新一笔 income 的 outstanding 快照
  const outstandingAmount = contract.outstanding_amount != null ? Number(contract.outstanding_amount) : null
  const outstandingCurrency = contract.outstanding_currency || cur
  // 收款状态：has-outstanding（有尾款）/ cleared（已结清）/ unknown（未录入任何收款，无尾款数据）
  const paymentState: 'pending' | 'cleared' | 'overpaid' | 'unknown' =
    outstandingAmount == null
      ? 'unknown'
      : outstandingAmount > 0
        ? 'pending'
        : overpaid > 0 ? 'overpaid' : 'cleared'

  // 按币种分桶（混币种合同的完整真相）
  const paidByCurrency: Record<string, number> = contract.paid_by_currency && Object.keys(contract.paid_by_currency).length > 0
    ? contract.paid_by_currency
    : (summary?.income?.paid_by_currency as Record<string, number> | undefined) || {}
  const expenseByCurrency: Record<string, number> = contract.expense_by_currency && Object.keys(contract.expense_by_currency).length > 0
    ? contract.expense_by_currency
    : (summary?.expense?.expense_by_currency as Record<string, number> | undefined) || {}

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
                {/* 改造后：统一展示本币金额，不再做币种换算副位 */}
                <Tooltip title={fmtFull(payment.paid_amount, payment.currency)}>
                  <span>{fmt(payment.paid_amount, payment.currency)}</span>
                </Tooltip>
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
                        setPreviewUrl(url)
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
            <Tooltip title={`${fmtFull(total, cur)}\n${amountToChinese(total, cur)}`}>
              <span className="cd-fn-hero-value">{fmt(receivable, cur)}</span>
            </Tooltip>
          </div>
          <div className="cd-fn-hero-right">
            <Button
              size="small"
              icon={<FileTextOutlined />}
              onClick={() => setNoticeOpen(true)}
              className="cd-fn-notice-btn"
            >
              付款通知单
            </Button>
          </div>
        </div>

        {/* ── 行2：三栏指标（按币种分别展示；混币种合同需双值并列） ── */}
        <div className="cd-fn-metrics">
          {/* 已收 */}
          <div className="cd-fn-metric">
            <div className="cd-fn-metric-header">
              <span className="cd-fn-metric-dot income" />
              <span className="cd-fn-metric-label">已收金额</span>
            </div>
            <div className="cd-fn-metric-row">
              {Object.keys(paidByCurrency).length === 0 ? (
                <span className="cd-fn-metric-value income">{fmt(0, cur)}</span>
              ) : (
                <span className="cd-fn-metric-multi">
                  {Object.entries(paidByCurrency).map(([c, v]) => (
                    <span key={c} className="cd-fn-metric-value income">{fmt(Number(v), c)}</span>
                  ))}
                </span>
              )}
              <span className="cd-fn-metric-tag">{contract.paid_count}笔</span>
            </div>
          </div>

          {/* 剩余尾款 */}
          <div className="cd-fn-metric">
            <div className="cd-fn-metric-header">
              <span className={`cd-fn-metric-dot ${paymentState === 'pending' ? 'remaining' : 'cleared'}`} />
              <span className="cd-fn-metric-label">剩余尾款</span>
            </div>
            <div className="cd-fn-metric-row">
              {paymentState === 'unknown' ? (
                <span className="cd-fn-metric-value remaining" style={{ color: 'var(--text-tertiary)' }}>待录入收入</span>
              ) : paymentState === 'pending' ? (
                <>
                  <Tooltip title={`${fmtFull(outstandingAmount || 0, outstandingCurrency)}\n${amountToChinese(outstandingAmount || 0, outstandingCurrency)}`}>
                    <span className="cd-fn-metric-value remaining">
                      {fmt(Number(outstandingAmount || 0), outstandingCurrency)}
                    </span>
                  </Tooltip>
                  <span className="cd-fn-metric-status remaining">未结清</span>
                </>
              ) : (
                <>
                  <span className="cd-fn-metric-value cleared">{fmt(0, outstandingCurrency)}</span>
                  <span className="cd-fn-metric-status cleared">已结清 ✓</span>
                  {paymentState === 'overpaid' && (
                    <Tooltip title={`实付超出合同金额 ${fmtFull(overpaid, cur)}。\n可能原因：手续费、多付等`}>
                      <span className="cd-fn-metric-extra">
                        超收 +{fmt(overpaid, cur)}
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
              {Object.keys(expenseByCurrency).length === 0 ? (
                <span className="cd-fn-metric-value expense">{fmt(0, cur)}</span>
              ) : (
                <span className="cd-fn-metric-multi">
                  {Object.entries(expenseByCurrency).map(([c, v]) => (
                    <span key={c} className="cd-fn-metric-value expense">{fmt(Number(v), c)}</span>
                  ))}
                </span>
              )}
              {(contract as any).expense_count > 0 && (
                <span className="cd-fn-metric-tag expense">{(contract as any).expense_count}笔</span>
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

      {/* ⑪ 放行历史（仅当存在凭证不符手动放行时展示；默认折叠） */}
      {(() => {
        const overrides = [...incomePayments, ...expensePayments].filter(
          (p: any) => p?.verification_result?.manual_override === true,
        )
        if (overrides.length === 0) return null
        return (
          <div className="cd-section" style={{ marginTop: 18 }}>
            <Collapse
              items={[{
                key: 'override',
                label: (
                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8, fontWeight: 600 }}>
                    <WarningOutlined style={{ color: '#dc6b3d' }} />
                    放行历史
                    <span style={{
                      background: '#fbe9e7', color: '#8f2d28',
                      padding: '0 8px', borderRadius: 10, fontSize: 12, fontWeight: 500,
                    }}>
                      {overrides.length} 条
                    </span>
                  </span>
                ),
                children: (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                    {overrides.map((p: any) => {
                      const vr = p.verification_result || {}
                      const diffs: any[] = Array.isArray(vr.diff_fields) ? vr.diff_fields : []
                      const isIncome = p.type === 'income'
                      return (
                        <div
                          key={p.id}
                          style={{
                            border: '1px solid #f0d2cd',
                            background: '#fdf4f3',
                            borderRadius: 10,
                            padding: '12px 14px',
                          }}
                        >
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                            <span style={{ fontSize: 13, color: '#666' }}>
                              <span style={{
                                color: '#fff',
                                background: isIncome ? '#c9952b' : '#5b8c63',
                                padding: '1px 8px', borderRadius: 8, fontSize: 12, marginRight: 8,
                              }}>{isIncome ? '收' : '支'}</span>
                              第 {p.installment_number} 期 · {p.installment_name || p.description || '-'}
                            </span>
                            <span style={{ color: '#999', fontSize: 12 }}>
                              {vr.manual_override_at ? new Date(vr.manual_override_at).toLocaleString('zh-CN') : '-'}
                            </span>
                          </div>
                          <div style={{ fontSize: 13, color: '#333', marginBottom: 6 }}>
                            <strong>{fmt(p.paid_amount || p.amount, p.currency)}</strong>
                            <span style={{ marginLeft: 12, color: '#666' }}>
                              操作人：{vr.manual_override_by_name || `#${vr.manual_override_by || '-'}`}
                            </span>
                            <span style={{ marginLeft: 12, color: '#666' }}>
                              匹配状态：<code style={{ background: '#fff', padding: '0 4px', borderRadius: 3 }}>{vr.match_status || '-'}</code>
                            </span>
                          </div>
                          <div style={{ fontSize: 13, color: '#444', marginBottom: 6 }}>
                            <span style={{ color: '#8f2d28', fontWeight: 500 }}>放行理由：</span>
                            {vr.manual_override_reason || vr.manual_reason || '-'}
                          </div>
                          {diffs.length > 0 && (
                            <div style={{ fontSize: 12, color: '#666', background: '#fff', padding: '6px 10px', borderRadius: 6 }}>
                              <span style={{ color: '#999', marginRight: 6 }}>差异字段：</span>
                              {diffs.map((d: any, i: number) => (
                                <span key={i} style={{ marginRight: 10 }}>
                                  <strong>{d.field}</strong>: 期望 <code>{String(d.expected)}</code> → 实际 <code>{String(d.got)}</code>
                                </span>
                              ))}
                            </div>
                          )}
                        </div>
                      )
                    })}
                  </div>
                ),
              }]}
              defaultActiveKey={[]}
              ghost
            />
          </div>
        )
      })()}

      {/* 付款通知单（对账弹窗，可下载为图片发给客户） */}
      <PaymentNoticeModal
        open={noticeOpen}
        contract={contract}
        incomePayments={incomePayments}
        onClose={() => setNoticeOpen(false)}
      />

      {/* 凭证图片预览（弹窗模式） */}
      <Image
        style={{ display: 'none' }}
        preview={{
          visible: !!previewUrl,
          src: previewUrl || undefined,
          onVisibleChange: (vis) => {
            if (!vis) {
              if (previewUrl) URL.revokeObjectURL(previewUrl)
              setPreviewUrl(null)
            }
          },
        }}
      />

    </div>
  )
}
