/**
 * 合同台账视图（与卡片视图同源数据，靠 ?view=ledger 切换）。
 *
 * 与卡片视图的区别：
 * - 调 GET /contracts?include=payments，一次取回每行的全部收/支流水
 * - 横向行布局：客户信息 | 收入流水 | 支出流水 | 净利润 | 操作
 * - 顶部汇总条按当前页数据累加（不是全量；全量汇总待后续 /summary 接口）
 *
 * 不复用 ContractList 的卡片渲染——刻意分文件让两套视图各自演化。
 * 共用的：筛选条状态、删除、ReceiptChatModal、ContractChatModal、分页。
 * 因此把筛选条 + 模态控制留在外层 ContractList 里，本组件只接收数据 + 上报事件。
 */
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Tooltip, Empty } from 'antd'
import { DeleteOutlined, EyeOutlined, FileImageOutlined } from '@ant-design/icons'
import type { ContractWithPayments, Payment } from '@/types'
import { paymentApi } from '@/services/payment'
import { formatMoney } from '@/utils/money'
import dayjs from 'dayjs'
import './ContractLedger.css'

interface Props {
  contracts: ContractWithPayments[]
  role: string
  onDelete: (id: number) => void
}

const currencySymbol: Record<string, string> = { CNY: '¥', HKD: 'HK$' }

// 业务类型 → 行根类名（与 CLAUDE.md 业务色映射保持一致）
function bizClassOf(businessType?: string): string {
  if (!businessType) return ''
  if (businessType === '车辆买卖' || businessType === '车辆业务') return 'biz-vehicle'
  if (businessType === '两地牌过户' || businessType === '中港牌业务') return 'biz-cross'
  return 'biz-other'
}

function bizLabelOf(businessType?: string): string {
  if (!businessType) return '合同'
  if (businessType === '车辆业务') return '车辆买卖'
  if (businessType === '中港牌业务') return '两地牌过户'
  return businessType
}

function bizIconOf(businessType?: string): string {
  const c = bizClassOf(businessType)
  if (c === 'biz-vehicle') return '🚗'
  if (c === 'biz-cross') return '🛂'
  return '📄'
}

/** 紧凑金额：保持货币符号 + 万缩写，全值通过 tooltip 暴露 */
function CompactMoney({ value, currency }: { value: number; currency: string }) {
  const symbol = currencySymbol[currency] || '¥'
  const m = formatMoney(value)
  const node = (
    <span className="lm-money">
      <span className="sym">{symbol}</span>
      {m.display}
      {m.unit && <span className="unit">{m.unit}</span>}
    </span>
  )
  if (!m.unit) return node
  return <Tooltip title={`${symbol}${m.full}`} mouseEnterDelay={0.3}>{node}</Tooltip>
}

/** 流水行金额：纯数字，状态色由父级 className 控制 */
function FlowAmount({ value, currency }: { value: number; currency: string }) {
  const symbol = currencySymbol[currency] || '¥'
  return <>{symbol}{value.toLocaleString('zh-CN', { maximumFractionDigits: 0 })}</>
}

/** 一笔流水（收入/支出共用） */
function FlowItem({
  payment,
  currency,
  onPreview,
}: {
  payment: Payment
  currency: string
  onPreview: (p: Payment) => void
}) {
  const isPaid = payment.status === 'paid'
  const isExpense = payment.type === 'expense'
  const desc = payment.installment_name || payment.description || `第${payment.installment_number}期`
  const counterparty = isExpense
    ? (payment.payee_name || '')
    : ''
  const titleTip = counterparty ? `${desc} · ${counterparty}` : desc

  return (
    <div className="flow-item">
      <span className={`si ${isPaid ? 'paid' : 'pending'}`}>{isPaid ? '✓' : '◌'}</span>
      <Tooltip title={titleTip} mouseEnterDelay={0.4}>
        <span className="desc">{desc}</span>
      </Tooltip>
      <span className={`amount ${isPaid ? (isExpense ? 'expense-paid' : 'income-paid') : 'pending'}`}>
        <FlowAmount value={Number(payment.paid_amount || payment.amount)} currency={payment.currency || currency} />
      </span>
      {isPaid && payment.receipt_image_path ? (
        <button
          className="receipt-btn"
          title="查看凭证"
          onClick={() => onPreview(payment)}
        >
          <FileImageOutlined />
        </button>
      ) : (
        <span className="receipt-btn placeholder" />
      )}
    </div>
  )
}

export default function ContractLedger({ contracts, role, onDelete }: Props) {
  const navigate = useNavigate()
  const [receiptPreview, setReceiptPreview] = useState<{
    open: boolean
    url: string
    payment: Payment | null
  }>({ open: false, url: '', payment: null })

  const openReceiptPreview = async (payment: Payment) => {
    try {
      const url = await paymentApi.getReceiptUrl(payment.id)
      setReceiptPreview({ open: true, url, payment })
    } catch (e) {
      console.error('加载凭证失败', e)
    }
  }
  const closeReceiptPreview = () => {
    if (receiptPreview.url) URL.revokeObjectURL(receiptPreview.url)
    setReceiptPreview({ open: false, url: '', payment: null })
  }

  if (!contracts.length) {
    return <Empty description="暂无合同数据" className="empty-state" />
  }

  return (
    <div className="ledger-list">
      {contracts.map((c) => {
        // 已收 = 已发生且 paid 的收入；未收 = 计划但未收（pending）
        const incomes = (c.payments || []).filter(p => p.type === 'income')
        const expenses = (c.payments || []).filter(p => p.type === 'expense')

        const paid = Number(c.paid_amount || 0)
        const expense = Number(c.total_expense || 0)
        const profit = paid - expense
        // 应收口径与详情页统一：合同金额 + 附加项折算（含附加项的进度才准确）
        const addl = c.additional_total_in_contract_currency != null
          ? Number(c.additional_total_in_contract_currency) : 0
        const receivable = Number(c.total_amount || 0) + addl
        const progress = receivable > 0
          ? Math.min(Math.round((paid / receivable) * 100), 999)
          : 0
        const progressClass = progress >= 100 ? (progress > 100 ? 'over' : 'done') : ''

        const bizClass = bizClassOf(c.business_type)
        const statusClass = c.status === 'completed' ? 'completed' : 'active'
        const statusText = c.status === 'completed' ? '已完成' : '执行中'

        // CNY 净利润折算（仅 HKD 合同）
        let profitCny: number | null = null
        if (c.currency === 'HKD' && c.paid_amount_in_cny != null && c.total_expense_in_cny != null) {
          profitCny = Number(c.paid_amount_in_cny) - Number(c.total_expense_in_cny)
        }

        return (
          <div key={c.id} className={`ledger-row ${bizClass}`}>
            <div className="accent-bar" />
            <div className="ledger-row-inner">

              {/* ── 客户信息列 ── */}
              <div className="ledger-cell-info">
                <div className="info-customer">
                  <span className="name">{c.customer_name || '未关联客户'}</span>
                </div>
                <div className="info-meta-row">
                  <span className="contract-no">{c.contract_number}</span>
                  {c.signed_date && <span className="signed-date">{dayjs(c.signed_date).format('YYYY-MM-DD')}</span>}
                </div>
                {c.business_description && (
                  <div className="info-desc" title={c.business_description}>{c.business_description}</div>
                )}
                <div className="info-meta">
                  <span className={`biz-chip ${bizClass}`}>
                    {bizIconOf(c.business_type)} {bizLabelOf(c.business_type)}
                  </span>
                  <span className={`status-chip ${statusClass}`}>
                    {c.status === 'completed' ? '✓' : '●'} {statusText}
                  </span>
                </div>
                <div className="info-amount-line">
                  <span className="info-amount-label">合同</span>
                  <span className="info-amount-value">
                    {addl > 0 ? (
                      <Tooltip
                        title={`应收 = 合同金额 ${formatMoney(Number(c.total_amount)).full} + 附加项折算 ${formatMoney(addl).full}\n含：${c.additional_total_by_currency
                          ? Object.entries(c.additional_total_by_currency)
                              .filter(([, v]) => Number(v) > 0)
                              .map(([cur, v]) => `${currencySymbol[cur] || cur}${formatMoney(Number(v)).full}`)
                              .join(' + ')
                          : ''}`}
                      >
                        <span><CompactMoney value={receivable} currency={c.currency} /></span>
                      </Tooltip>
                    ) : (
                      <CompactMoney value={Number(c.total_amount)} currency={c.currency} />
                    )}
                  </span>
                </div>
                <div className="mini-progress">
                  <div className="mini-progress-track">
                    <div
                      className={`mini-progress-fill ${progressClass}`}
                      style={{ width: `${Math.min(progress, 100)}%` }}
                    />
                  </div>
                  <span className={`mini-progress-text ${progressClass}`}>{progress}%</span>
                </div>
              </div>

              {/* ── 收入列 ── */}
              <div className="ledger-cell-flow">
                <div className="flow-header">
                  <span className="dot income" />
                  <span className="title">收入</span>
                  <span className="badge">{incomes.length}笔</span>
                  <span className="total income">
                    <FlowAmount value={paid} currency={c.currency} />
                  </span>
                </div>
                {incomes.length === 0 ? (
                  <div className="flow-empty">暂无收入计划</div>
                ) : (
                  incomes.map(p => (
                    <FlowItem key={p.id} payment={p} currency={c.currency} onPreview={openReceiptPreview} />
                  ))
                )}
              </div>

              {/* ── 支出列 ── */}
              <div className="ledger-cell-flow">
                <div className="flow-header">
                  <span className="dot expense" />
                  <span className="title">支出</span>
                  <span className="badge">{expenses.length}笔</span>
                  <span className={`total expense ${expenses.length === 0 ? 'muted' : ''}`}>
                    <FlowAmount value={expense} currency={c.currency} />
                  </span>
                </div>
                {expenses.length === 0 ? (
                  <div className="flow-empty">暂无支出记录</div>
                ) : (
                  expenses.map(p => (
                    <FlowItem key={p.id} payment={p} currency={c.currency} onPreview={openReceiptPreview} />
                  ))
                )}
              </div>

              {/* ── 净利润列 ── */}
              <div className="ledger-cell-profit">
                <span className="profit-label">净利润</span>
                <span className={`profit-value ${profit > 0 ? 'positive' : profit < 0 ? 'negative' : 'zero'}`}>
                  {profit < 0 ? '-' : ''}{currencySymbol[c.currency] || '¥'}
                  {Math.abs(profit).toLocaleString('zh-CN', { maximumFractionDigits: 0 })}
                </span>
                <div className={`profit-divider ${profit > 0 ? 'positive' : profit < 0 ? 'negative' : 'zero'}`} />
                {profitCny !== null && (
                  <span className="profit-cny">
                    ≈ ¥{Math.abs(profitCny).toLocaleString('zh-CN', { maximumFractionDigits: 0 })}
                  </span>
                )}
              </div>

              {/* ── 操作列 ── */}
              <div className="ledger-cell-actions">
                <button
                  className="action-btn detail"
                  title="查看合同详情"
                  onClick={() => navigate(`/contracts/${c.id}`)}
                >
                  <EyeOutlined />
                </button>
                {role === 'admin' && (
                  <Tooltip title="删除合同">
                    <button
                      className="action-btn del-btn"
                      title="删除合同"
                      onClick={() => onDelete(c.id)}
                    >
                      <DeleteOutlined />
                    </button>
                  </Tooltip>
                )}
              </div>
            </div>
          </div>
        )
      })}

      {/* 凭证预览 Lightbox */}
      {receiptPreview.open && (
        <div className="receipt-lightbox" onClick={closeReceiptPreview}>
          <div className="lightbox-card" onClick={(e) => e.stopPropagation()}>
            <div className="lightbox-header">
              <h4>
                凭证详情
                {receiptPreview.payment && (
                  <span className="lb-subtle">
                    · {receiptPreview.payment.installment_name || `第${receiptPreview.payment.installment_number}期`}
                  </span>
                )}
              </h4>
              <button className="lightbox-close" onClick={closeReceiptPreview}>✕</button>
            </div>
            <div className="lightbox-body">
              <img className="lightbox-img" src={receiptPreview.url} alt="凭证" />
              {receiptPreview.payment && (
                <div className="lightbox-meta">
                  <div className="lightbox-meta-item">
                    <span className="k">金额</span>
                    <span className="v">
                      {currencySymbol[receiptPreview.payment.currency] || '¥'}
                      {Number(receiptPreview.payment.paid_amount || receiptPreview.payment.amount)
                        .toLocaleString('zh-CN', { maximumFractionDigits: 2 })}
                    </span>
                  </div>
                  <div className="lightbox-meta-item">
                    <span className="k">付款日期</span>
                    <span className="v">{receiptPreview.payment.paid_date || '--'}</span>
                  </div>
                  <div className="lightbox-meta-item">
                    <span className="k">付款方式</span>
                    <span className="v">{receiptPreview.payment.payment_method || '--'}</span>
                  </div>
                  <div className="lightbox-meta-item">
                    <span className="k">{receiptPreview.payment.type === 'expense' ? '收款方' : '付款方'}</span>
                    <span className="v">
                      {receiptPreview.payment.type === 'expense'
                        ? (receiptPreview.payment.payee_name || '--')
                        : '--'}
                    </span>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
