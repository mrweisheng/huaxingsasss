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
import { DeleteOutlined, EyeOutlined, FileImageOutlined, WechatOutlined } from '@ant-design/icons'
import type { ContractWithPayments, Payment } from '@/types'
import { paymentApi } from '@/services/payment'
import { formatMoney } from '@/utils/money'
import { methodMap } from '@/utils/moneyFormat'
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

/** 多币种总额：按币种逐行展示（HKD / CNY 分别显示），空字典时显示 ¥0 */
function MultiCurrencyTotal({ data }: { data: Record<string, number> }) {
  const entries = Object.entries(data).filter(([, v]) => Number(v) > 0)
  if (entries.length === 0) {
    return <>¥0</>
  }
  return (
    <span className="multi-currency-total">
      {entries.map(([cur, val]) => (
        <span key={cur} className="multi-currency-item">
          {currencySymbol[cur] || cur}
          {Number(val).toLocaleString('zh-CN', { maximumFractionDigits: 0 })}
        </span>
      ))}
    </span>
  )
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

        // 按币种分桶（改造后：不再做汇率换算，按本币分别展示）
        // 优先用后端返回的 paid_by_currency；fallback 到前端 payment 流水累加
        const paidByCurrency: Record<string, number> = c.paid_by_currency && Object.keys(c.paid_by_currency).length > 0
          ? c.paid_by_currency
          : incomes.reduce<Record<string, number>>((acc, p) => {
              if (p.status === 'paid' && p.currency) {
                acc[p.currency] = (acc[p.currency] || 0) + Number(p.paid_amount || 0)
              }
              return acc
            }, {})
        const expenseByCurrency: Record<string, number> = c.expense_by_currency && Object.keys(c.expense_by_currency).length > 0
          ? c.expense_by_currency
          : expenses.reduce<Record<string, number>>((acc, p) => {
              if (p.status === 'paid' && p.currency) {
                acc[p.currency] = (acc[p.currency] || 0) + Number(p.paid_amount || 0)
              }
              return acc
            }, {})

        const bizClass = bizClassOf(c.business_type)
        const statusClass = c.status === 'completed' ? 'completed' : 'active'
        const statusText = c.status === 'completed' ? '已完成' : '执行中'

        return (
          <div key={c.id} className={`ledger-row ${bizClass}`}>
            <div className="accent-bar" />
            <div className="ledger-row-inner">

              {/* ── 客户信息列 ── */}
              <div className="ledger-cell-info">
                {c.wechat_group ? (
                  <div className="info-group-block">
                    <div className="info-group-hero">
                      <WechatOutlined className="info-group-icon" />
                      <Tooltip title={c.wechat_group} placement="topLeft">
                        <span className="info-group-text">{c.wechat_group}</span>
                      </Tooltip>
                    </div>
                    <div className="info-group-sub">
                      <span className="info-customer-name">{c.customer_name || '未关联客户'}</span>
                      {c.signed_date && <span className="info-customer-date">{dayjs(c.signed_date).format('YYYY-MM-DD')}</span>}
                    </div>
                  </div>
                ) : (
                  <>
                    <div className="info-customer">
                      <span className="name">{c.customer_name || '未关联客户'}</span>
                    </div>
                    <div className="info-meta-row">
                      <span className="contract-no">{c.contract_number}</span>
                      {c.signed_date && <span className="signed-date">{dayjs(c.signed_date).format('YYYY-MM-DD')}</span>}
                    </div>
                  </>
                )}
                {c.wechat_group && (
                  <div className="info-meta-row">
                    <span className="contract-no">{c.contract_number}</span>
                  </div>
                )}
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
                    <CompactMoney value={Number(c.total_amount)} currency={c.currency} />
                  </span>
                </div>
                {c.outstanding_amount != null && c.outstanding_currency && (
                  <div className="info-amount-line">
                    <span className="info-amount-label">尾款</span>
                    <span className="info-amount-value">
                      <CompactMoney value={Number(c.outstanding_amount)} currency={c.outstanding_currency} />
                    </span>
                  </div>
                )}
              </div>

              {/* ── 收入列 ── */}
              <div className="ledger-cell-flow">
                <div className="flow-header">
                  <span className="dot income" />
                  <span className="title">收入</span>
                  <span className="badge">{incomes.length}笔</span>
                  <span className="total income">
                    <MultiCurrencyTotal data={paidByCurrency} />
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
                    <MultiCurrencyTotal data={expenseByCurrency} />
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
                    <span className="v">
                      {receiptPreview.payment.payment_method
                        ? (methodMap[receiptPreview.payment.payment_method] || receiptPreview.payment.payment_method)
                        : '--'}
                    </span>
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
