import { useState, useEffect, useCallback, useRef } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { Input, Select, DatePicker, Button, message, Empty, Tooltip, Popover } from 'antd'
import { PlusOutlined, SearchOutlined, FilterOutlined, DeleteOutlined, FileTextOutlined, ArrowDownOutlined, ArrowUpOutlined, AppstoreOutlined, UnorderedListOutlined, DownloadOutlined, WechatOutlined } from '@ant-design/icons'
import { contractApi } from '@/services/contract'
import { useAuthStore } from '@/store/useAuthStore'
import ContractChatModal from '@/components/ContractChatModal'
import ReceiptChatModal from '@/components/ReceiptChatModal'
import ContractLedger from './ContractLedger'
import DangerConfirmModal from '@/components/DangerConfirmModal'
import type { Contract, ContractWithPayments } from '@/types'
import dayjs from 'dayjs'
import { formatMoney } from '@/utils/money'
import { exportLedger } from '@/utils/exportLedger'
import './ContractList.css'
import './ContractLedger.css'

const { RangePicker } = DatePicker

const statusConfig: Record<string, { color: string; bg: string; text: string }> = {
  active: { color: '#1890ff', bg: '#e6f7ff', text: '执行中' },
  completed: { color: '#52c41a', bg: '#f6ffed', text: '已完成' },
}

// 业务视觉映射 —— 与 CustomerList 完全一致的范式
// 业务色见 CLAUDE.md：车辆=钢蓝 #2d5b8a，两地牌=朱砂 #b8423b
// 后端枚举见 backend/app/core/business_types.py（标准值 + legacy 值都要覆盖）
type BizVisual = {
  className: string         // 卡片根类名（驱动业务色 CSS 变量）
  icon: React.ReactNode     // 业务图标
  label: string             // 显示文字
}

const vehicleVisual: BizVisual = {
  className: 'biz-vehicle',
  label: '车辆买卖',
  icon: (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="2" y="6" width="20" height="11" rx="3"/>
      <circle cx="7" cy="18" r="2"/><circle cx="17" cy="18" r="2"/>
      <line x1="6" y1="11" x2="10" y2="11"/><line x1="14" y1="11" x2="18" y2="11"/>
    </svg>
  ),
}

const crossVisual: BizVisual = {
  className: 'biz-cross',
  label: '两地牌过户',
  icon: (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 9h18v10H3z"/><path d="M9 19v-3h6v3"/><path d="M7 9V5h10v4"/>
      <line x1="8" y1="14" x2="10" y2="14"/><line x1="14" y1="14" x2="16" y2="14"/>
    </svg>
  ),
}

const bizVisual: Record<string, BizVisual> = {
  // 标准值
  '车辆买卖': vehicleVisual,
  '两地牌过户': crossVisual,
  // legacy 兼容
  '车辆业务': vehicleVisual,
  '中港牌业务': crossVisual,
}

const currencySymbol: Record<string, string> = {
  CNY: '¥',
  HKD: 'HK$',
}

// 缩写金额渲染：货币符号 + 数字（万/亿 自动缩写）+ 单位 chip
// 完整精确值通过 Tooltip 暴露，避免 26px 大字撑爆卡片
function renderAmount(amount: number | null | undefined, currency: string) {
  const symbol = currencySymbol[currency] || '¥'
  if (amount == null) return <>{symbol}--</>
  const m = formatMoney(amount)
  const node = (
    <>
      <span className="money-sym">{symbol}</span>
      <span className="money-num">{m.display}</span>
      {m.unit && <span className="money-unit">{m.unit}</span>}
    </>
  )
  if (!m.unit) return node  // 万以下不缩写，无需 tooltip
  return (
    <Tooltip title={`${symbol}${m.full}`} placement="top" mouseEnterDelay={0.3}>
      {node}
    </Tooltip>
  )
}

function formatDate(date: string | undefined): string {
  if (!date) return '--'
  return dayjs(date).format('YYYY-MM-DD')
}

function calculateProgress(paid: number, total: number): number {
  if (total === 0) return 0
  return Math.round((paid / total) * 100)
}

export default function ContractList() {
  const navigate = useNavigate()
  const user = useAuthStore(s => s.user)
  const role = user?.role || ''
  const [searchParams, setSearchParams] = useSearchParams()
  const initialView = searchParams.get('view') === 'ledger' ? 'ledger' : 'card'
  const [view, setView] = useState<'card' | 'ledger'>(initialView)
  const [contracts, setContracts] = useState<Contract[] | ContractWithPayments[]>([])
  const [loading, setLoading] = useState(false)
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [keyword, setKeyword] = useState('')
  const [statusFilter, setStatusFilter] = useState<string | undefined>(undefined)
  const [dateRange, setDateRange] = useState<[dayjs.Dayjs | null, dayjs.Dayjs | null] | null>(null)
  const [hoveredCard, setHoveredCard] = useState<number | null>(null)
  const [uploadModalOpen, setUploadModalOpen] = useState(false)
  const [receiptModal, setReceiptModal] = useState<{
    open: boolean
    contract: Contract | null
    type: 'income' | 'expense'
  }>({ open: false, contract: null, type: 'income' })
  const abortControllerRef = useRef<AbortController | null>(null)
  const searchTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  // 删除二次确认弹窗状态
  const [deleteTarget, setDeleteTarget] = useState<{ id: number; number: string; title: string } | null>(null)
  const [deleting, setDeleting] = useState(false)
  // 导出台账
  const [exportDateRange, setExportDateRange] = useState<[dayjs.Dayjs | null, dayjs.Dayjs | null]>([
    dayjs().subtract(30, 'day'),
    dayjs(),
  ])
  const [exporting, setExporting] = useState(false)

  // 视图切换：写入 URL 深链；并把分页重置回第 1 页，避免切到不存在的页码导致空白
  const changeView = useCallback((mode: 'card' | 'ledger') => {
    setView(mode)
    setPage(1)
    const next = new URLSearchParams(searchParams)
    if (mode === 'ledger') next.set('view', 'ledger')
    else next.delete('view')
    setSearchParams(next, { replace: true })
  }, [searchParams, setSearchParams])

  const loadContracts = useCallback(async () => {
    abortControllerRef.current?.abort()
    const controller = new AbortController()
    abortControllerRef.current = controller

    setLoading(true)
    try {
      const params: any = { page, per_page: 20, customer_name: keyword || undefined }
      if (statusFilter) params.status = statusFilter
      if (dateRange && dateRange[0] && dateRange[1]) {
        params.date_from = dateRange[0].format('YYYY-MM-DD')
        params.date_to = dateRange[1].format('YYYY-MM-DD')
      }
      // 台账视图带 include=payments；卡片视图走原接口，性能不变
      const response = view === 'ledger'
        ? await contractApi.getListWithPayments(params, controller.signal)
        : await contractApi.getList(params, controller.signal)
      setContracts(response.items)
      setTotal(response.pagination.total)
    } catch (error: any) {
      if (error?.name === 'AbortError' || error?.code === 'ERR_CANCELED') return
      console.error(error)
    } finally {
      if (!controller.signal.aborted) {
        setLoading(false)
      }
    }
  }, [page, keyword, statusFilter, dateRange, view])

  useEffect(() => {
    loadContracts()
    return () => {
      abortControllerRef.current?.abort()
      if (searchTimerRef.current) clearTimeout(searchTimerRef.current)
    }
  }, [loadContracts])

  // 键盘快捷键：1 卡片 / 2 台账（输入框聚焦时不触发；IME 合成态期间也不触发，避免中文输入选词误触）
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.isComposing) return
      const tag = (document.activeElement as HTMLElement | null)?.tagName
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return
      if (e.key === '1') changeView('card')
      else if (e.key === '2') changeView('ledger')
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [changeView])

  const handleSearch = (e: React.ChangeEvent<HTMLInputElement> | undefined) => {
    const value = e?.target?.value ?? ''
    if (searchTimerRef.current) clearTimeout(searchTimerRef.current)
    searchTimerRef.current = setTimeout(() => {
      setKeyword(value)
      setPage(1)
    }, 400)
  }

  const handleStatusChange = (value: string | undefined) => {
    setStatusFilter(value)
    setPage(1)
  }

  const handleDateChange = (dates: [dayjs.Dayjs | null, dayjs.Dayjs | null] | null) => {
    setDateRange(dates)
    setPage(1)
  }

  const handleDelete = (id: number) => {
    const ct = contracts.find(c => c.id === id)
    setDeleteTarget({
      id,
      number: ct?.contract_number || String(id),
      title: ct?.business_description || ct?.title || '',
    })
  }

  const handleDeleteConfirmed = async () => {
    if (!deleteTarget) return
    setDeleting(true)
    try {
      await contractApi.delete(deleteTarget.id)
      message.success('删除成功')
      setDeleteTarget(null)
      loadContracts()
    } catch (error: any) {
      message.error(error.response?.data?.detail || '删除失败')
    } finally {
      setDeleting(false)
    }
  }

  const handleExport = async () => {
    if (!exportDateRange || !exportDateRange[0] || !exportDateRange[1]) {
      message.warning('请选择导出日期范围')
      return
    }
    setExporting(true)
    try {
      await exportLedger({
        dateFrom: exportDateRange[0].format('YYYY-MM-DD'),
        dateTo: exportDateRange[1].format('YYYY-MM-DD'),
      })
      message.success('导出成功')
    } catch (e: any) {
      message.error(e.message || '导出失败')
    } finally {
      setExporting(false)
    }
  }

  const totalPages = Math.ceil(total / 20)

  // 汇总条：按当前页累加，按币种分组（仅台账模式显示）
  // 注意：这是"本页汇总"而非"全量筛选汇总"——后者需要单独的 /summary 接口
  const summary = (() => {
    const agg: Record<string, { total: number; paid: number; expense: number }> = {}
    for (const c of contracts) {
      const cur = c.currency || 'CNY'
      if (!agg[cur]) agg[cur] = { total: 0, paid: 0, expense: 0 }
      // 合同总额含附加项折算（与卡片/详情页同口径）
      const addl = c.additional_total_in_contract_currency != null
        ? Number(c.additional_total_in_contract_currency) : 0
      agg[cur].total += Number(c.total_amount || 0) + addl
      agg[cur].paid += Number(c.paid_amount || 0)
      agg[cur].expense += Number(c.total_expense || 0)
    }
    return agg
  })()
  const summaryCurrencies = Object.keys(summary)
  const formatSumVal = (n: number) => {
    const m = formatMoney(n)
    return m.unit ? `${m.display}${m.unit}` : m.display
  }
  const currencySymbol2: Record<string, string> = { CNY: '¥', HKD: 'HK$' }

  return (
    <div className="contract-list-container">
      <div className="page-topbar">
        <div className="page-topbar-left">
          <div className="page-title-wrap">
            <div className="page-title-icon">
              <FileTextOutlined />
            </div>
            <span className="page-title-text">合同管理</span>
            <span className="page-title-count">{total} 个合同</span>
          </div>
        </div>
        <div className="page-topbar-right">
          <Input
            placeholder="搜索客户名称 / 业务群..."
            allowClear
            onChange={handleSearch}
            style={{ width: 220 }}
            prefix={<SearchOutlined />}
          />
          <Select
            placeholder="状态"
            allowClear
            style={{ width: 110 }}
            value={statusFilter}
            onChange={handleStatusChange}
            suffixIcon={<FilterOutlined />}
            options={[
              { label: '执行中', value: 'active' },
              { label: '已完成', value: 'completed' },
            ]}
          />
          <div className="date-range-wrap">
            <span className="date-range-label">签订日期</span>
            <RangePicker
              onChange={handleDateChange}
              value={dateRange}
            />
          </div>
          {(role === 'admin' || role === 'income') && (
            <Button type="primary" icon={<PlusOutlined />} onClick={() => setUploadModalOpen(true)}>
              上传
            </Button>
          )}
          {view === 'ledger' && (
            <Popover
              content={
                <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                  <RangePicker
                    value={exportDateRange}
                    onChange={(dates) => setExportDateRange(dates as any)}
                    size="small"
                    style={{ width: 240 }}
                    placeholder={['开始日期', '结束日期']}
                  />
                  <Button
                    size="small"
                    type="primary"
                    loading={exporting}
                    onClick={handleExport}
                  >
                    确认导出
                  </Button>
                </div>
              }
              title="导出台账"
              trigger="click"
              placement="bottomRight"
            >
              <Button icon={<DownloadOutlined />}>导出台账</Button>
            </Popover>
          )}
          <div className="view-toggle" role="tablist" aria-label="视图切换">
            <button
              type="button"
              role="tab"
              aria-selected={view === 'card'}
              className={view === 'card' ? 'active' : ''}
              onClick={() => changeView('card')}
              title="卡片视图 (按 1)"
            >
              <AppstoreOutlined /> 卡片
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={view === 'ledger'}
              className={view === 'ledger' ? 'active' : ''}
              onClick={() => changeView('ledger')}
              title="台账视图 (按 2)"
            >
              <UnorderedListOutlined /> 台账
            </button>
          </div>
        </div>
      </div>

      {/* 汇总条：仅台账模式 + 有数据 */}
      {view === 'ledger' && contracts.length > 0 && (
        <div className="ledger-summary-strip">
          <div className="summary-block">
            <div className="summary-block-title"><span className="dot primary" />合同总额</div>
            <div className="summary-currency-rows">
              {summaryCurrencies.map(cur => (
                <div key={cur} className="summary-currency-row">
                  <span className="summary-sym">{currencySymbol2[cur] || cur}</span>
                  <span className="summary-val primary">{formatSumVal(summary[cur].total)}</span>
                </div>
              ))}
            </div>
          </div>
          <div className="summary-block">
            <div className="summary-block-title"><span className="dot gold" />已收</div>
            <div className="summary-currency-rows">
              {summaryCurrencies.map(cur => (
                <div key={cur} className="summary-currency-row">
                  <span className="summary-sym">{currencySymbol2[cur] || cur}</span>
                  <span className="summary-val gold">{formatSumVal(summary[cur].paid)}</span>
                </div>
              ))}
            </div>
          </div>
          <div className="summary-block">
            <div className="summary-block-title"><span className="dot orange" />支出</div>
            <div className="summary-currency-rows">
              {summaryCurrencies.map(cur => (
                <div key={cur} className="summary-currency-row">
                  <span className="summary-sym">{currencySymbol2[cur] || cur}</span>
                  <span className="summary-val orange">{formatSumVal(summary[cur].expense)}</span>
                </div>
              ))}
            </div>
          </div>
          <div className="summary-block">
            <div className="summary-block-title"><span className="dot teal" />净利润<span style={{ marginLeft: 6, fontSize: 9, opacity: 0.6 }}>本页</span></div>
            <div className="summary-currency-rows">
              {summaryCurrencies.map(cur => {
                const p = summary[cur].paid - summary[cur].expense
                return (
                  <div key={cur} className="summary-currency-row">
                    <span className="summary-sym">{currencySymbol2[cur] || cur}</span>
                    <span className={`summary-val ${p >= 0 ? 'teal' : 'orange'}`}>
                      {p < 0 ? '-' : ''}{formatSumVal(Math.abs(p))}
                    </span>
                  </div>
                )
              })}
            </div>
          </div>
        </div>
      )}

      {loading && contracts.length === 0 ? (
        view === 'ledger' ? (
          <div className="ct-skel-card" style={{ minHeight: 360 }}>
            <div className="ct-skel-row">
              <div className="ct-skel-block ct-skel-pill" />
              <div className="ct-skel-block ct-skel-pill" />
              <div className="ct-skel-block ct-skel-meta" />
            </div>
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="ct-skel-block ct-skel-line ct-skel-w-100" />
            ))}
          </div>
        ) : (
          <div className="contract-grid">
            {Array.from({ length: 8 }).map((_, i) => (
              <div key={i} className="ct-skel-card">
                <div className="ct-skel-row">
                  <div className="ct-skel-block ct-skel-pill" />
                  <div className="ct-skel-block ct-skel-meta" />
                </div>
                <div className="ct-skel-block ct-skel-title ct-skel-w-80" />
                <div className="ct-skel-block ct-skel-amount" />
                <div className="ct-skel-block ct-skel-line ct-skel-w-60" />
                <div className="ct-skel-block ct-skel-progress ct-skel-w-100" />
              </div>
            ))}
          </div>
        )
      ) : contracts.length === 0 && !loading ? (
        <Empty description="暂无合同数据" className="empty-state" />
      ) : (
        <>
          {view === 'ledger' ? (
            <ContractLedger
              contracts={contracts as ContractWithPayments[]}
              role={role}
              onDelete={handleDelete}
            />
          ) : (
          <div className="contract-grid">
            {contracts.map((contract, index) => {
              const status = statusConfig[contract.status] || statusConfig.active
              const biz = contract.business_type ? bizVisual[contract.business_type] : null
              const bizClass = biz?.className || (contract.business_type ? 'biz-other' : '')
              const bizMiniSuffix = bizClass.replace('biz-', '')
              // 应收口径与详情页统一：receivable = 合同金额 + 附加项折算到主币种
              // null/未维护或缺汇率时降级为合同金额，避免卡片"未含附加项"导致三态/进度失真
              const _paid = Number(contract.paid_amount || 0)
              const _total = Number(contract.total_amount || 0)
              const _addl = contract.additional_total_in_contract_currency != null
                ? Number(contract.additional_total_in_contract_currency) : 0
              const _receivable = _total + _addl
              const progressRaw = calculateProgress(_paid, _receivable)
              const progress = Math.min(progressRaw, 100)  // 视觉进度条 cap 100%
              // 三态：未付 / 已结清 / 加项收入（实付 > 应收）
              const _overpaid = Math.max(0, _paid - _receivable)
              const _unpaid = Math.max(0, _receivable - _paid)
              const _payState: 'pending' | 'cleared' | 'overpaid' =
                _overpaid > 0 ? 'overpaid' : _unpaid > 0 ? 'pending' : 'cleared'
              const isHovered = hoveredCard === contract.id

              return (
                <div
                  key={contract.id}
                  className={`contract-card ${bizClass} ${isHovered ? 'hovered' : ''}`}
                  onClick={() => navigate(`/contracts/${contract.id}`)}
                  onMouseEnter={() => setHoveredCard(contract.id)}
                  onMouseLeave={() => setHoveredCard(null)}
                  style={{ animationDelay: `${index * 50}ms` }}
                >
                  {/* ── 左侧色条（业务色 base）—— 由 .biz-vehicle/.biz-cross CSS 驱动 ── */}
                  {(biz || contract.business_type) && (
                    <div className="card-accent-bar" />
                  )}

                  {/* ── 顶栏：业务徽章（soft 底 + deep 字）+ 状态 ── */}
                  <div className="card-top-row">
                    {biz ? (
                      <span className={`biz-badge biz-badge--${bizMiniSuffix}`}>
                        <span className="biz-badge-icon">{biz.icon}</span>
                        <span className="biz-badge-label">{biz.label}</span>
                      </span>
                    ) : contract.business_type ? (
                      <span className="biz-badge biz-badge--other">
                        <FileTextOutlined className="biz-badge-icon" />
                        <span className="biz-badge-label">{contract.business_type}</span>
                      </span>
                    ) : (
                      <span className="biz-badge biz-badge--default">
                        <FileTextOutlined className="biz-badge-icon" />
                        <span className="biz-badge-label">合同</span>
                      </span>
                    )}
                    <span className="status-badge" style={{ color: status.color, backgroundColor: status.bg }}>
                      {status.text}
                    </span>
                  </div>

                  {/* 业务群名 + 客户名（群名为业务员查找合同的主要线索，故置于最醒目位置） */}
                  {contract.wechat_group ? (
                    <div className="group-name-block" style={{ paddingTop: '6px' }}>
                      <div className="group-name-hero">
                        <WechatOutlined className="group-name-icon" />
                        <Tooltip title={contract.wechat_group} placement="topLeft">
                          <span className="group-name-text">{contract.wechat_group}</span>
                        </Tooltip>
                      </div>
                      <div className="group-sub-row">
                        <span className="customer-name-text">{contract.customer_name || '未关联客户'}</span>
                        <span className="customer-date-text">{formatDate(contract.signed_date)}</span>
                      </div>
                    </div>
                  ) : (
                    /* 历史合同无群名：退回原展示，保证不崩 */
                    <div className="customer-name-hero" style={{ paddingTop: '6px' }}>
                      <span className="customer-name-text">{contract.customer_name || '未关联客户'}</span>
                      <span className="customer-date-text">{formatDate(contract.signed_date)}</span>
                    </div>
                  )}

                  {/* 合同元信息：编号 */}
                  <div className="contract-meta-row">
                    <span className="contract-meta-number">{contract.contract_number}</span>
                  </div>

                  {/* 业务描述 — 固定高度占位，统一卡片节奏 */}
                  <div className="business-desc">{contract.business_description || ''}</div>

                  {/* 金色语义分割线 — 身份层 / 金额层 */}
                  <div className="divider-gold card-divider" />

                  <div className="amount-section">
                    {/* 金额拆分展示：合同金额 + 附加项 */}
                    <div className="amount-hero">
                      <div className="amount-tags-row">
                        <div className="amount-tag">
                          <span className="amount-tag-label">合同金额</span>
                          <span className="amount-tag-value">{renderAmount(_total, contract.currency)}</span>
                        </div>
                        {_addl > 0 && (
                          <Tooltip
                            title={contract.additional_total_by_currency
                              ? Object.entries(contract.additional_total_by_currency)
                                  .filter(([, v]) => Number(v) > 0)
                                  .map(([cur, v]) => `${currencySymbol[cur] || cur}${formatMoney(Number(v)).full}`)
                                  .join(' + ')
                              : ''}
                          >
                            <div className="amount-tag amount-tag--addl">
                              <span className="amount-tag-label">附加项</span>
                              <span className="amount-tag-value">{renderAmount(_addl, contract.currency)}</span>
                            </div>
                          </Tooltip>
                        )}
                      </div>
                    </div>

                    {/* 已付 / 未付 — 并排对比 */}
                    <div className="amount-split">
                      <div className="amount-split-item is-paid">
                        <div className="split-item-header">
                          <span className="split-dot paid" />
                          <span className="split-label">已付</span>
                        </div>
                        <div className="split-value paid">
                          {renderAmount(contract.paid_amount, contract.currency)}
                        </div>
                        {contract.payment_total_count > 0 && (
                          <div className="split-meta">
                            <span className="split-count">{contract.paid_count}/{contract.payment_total_count}笔</span>
                            {(contract as any).expense_count > 0 && (
                              <span className="split-expense">{(contract as any).expense_count}笔支出</span>
                            )}
                          </div>
                        )}
                      </div>

                      <div className="amount-split-vert" />

                      <div className="amount-split-item is-unpaid">
                        <div className="split-item-header">
                          <span className={`split-dot ${_payState === 'pending' ? 'unpaid' : 'paid'}`} />
                          <span className="split-label">
                            {_payState === 'overpaid' ? '加项收入' : _payState === 'cleared' ? '已结清' : '未付'}
                          </span>
                        </div>
                        <div className={`split-value ${_payState === 'pending' ? 'unpaid' : _payState === 'overpaid' ? 'overpaid' : 'paid'}`}>
                          {_payState === 'overpaid'
                            ? <>+{renderAmount(_overpaid, contract.currency)}</>
                            : renderAmount(_payState === 'pending' ? _unpaid : 0, contract.currency)}
                        </div>
                        {contract.payment_total_count > 0 && (
                          <div className="split-meta">
                            <div className="split-progress">
                              <div className="split-progress-track">
                                <div className="split-progress-fill" style={{ width: `${progress}%` }} />
                              </div>
                              <span className="split-progress-text">{progress}%</span>
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                  </div>

                  {/* ── 快速录入栏：收入/支出（核心高频操作）── */}
                  <div className="card-quick-actions" onClick={(e) => e.stopPropagation()}>
                    {(role === 'admin' || role === 'income') && (
                      <div
                        className="qa-btn qa-btn-income"
                        onClick={() => setReceiptModal({ open: true, contract, type: 'income' })}
                      >
                        <ArrowDownOutlined className="qa-btn-icon" />
                        <span className="qa-btn-text">录入收入</span>
                      </div>
                    )}
                    {(role === 'admin' || role === 'expense') && (
                      <div
                        className="qa-btn qa-btn-expense"
                        onClick={() => setReceiptModal({ open: true, contract, type: 'expense' })}
                      >
                        <ArrowUpOutlined className="qa-btn-icon" />
                        <span className="qa-btn-text">录入支出</span>
                      </div>
                    )}
                    {/* 已录入笔数提示 */}
                    {contract.payment_total_count > 0 && (
                      <span className="qa-count-hint">
                        {contract.paid_count}/{contract.payment_total_count}笔
                      </span>
                    )}
                  </div>

                  {role === 'admin' && (
                  <div className="card-footer">
                    <div className="footer-actions" onClick={(e) => e.stopPropagation()}>
                      <Tooltip title="删除合同">
                        <DeleteOutlined
                          className="action-icon delete"
                          onClick={() => handleDelete(contract.id)}
                        />
                      </Tooltip>
                    </div>
                  </div>
                  )}

                  <div className="card-decoration" />
                </div>
              )
            })}
          </div>
          )}

          {totalPages > 1 && (
            <div className="pagination">
              <div className="pagination-info">
                第 {page} / {totalPages} 页，共 {total} 条
              </div>
              <div className="pagination-buttons">
                <Button disabled={page <= 1} onClick={() => setPage(1)}>首页</Button>
                <Button disabled={page <= 1} onClick={() => setPage(p => p - 1)}>上一页</Button>
                <Button disabled={page >= totalPages} onClick={() => setPage(p => p + 1)}>下一页</Button>
                <Button disabled={page >= totalPages} onClick={() => setPage(totalPages)}>末页</Button>
              </div>
            </div>
          )}
        </>
      )}

      <ContractChatModal
        open={uploadModalOpen}
        onClose={(created) => { setUploadModalOpen(false); if (created) loadContracts() }}
      />

      {receiptModal.contract && (
        <ReceiptChatModal
          open={receiptModal.open}
          onClose={() => {
            setReceiptModal(prev => ({ ...prev, open: false }))
            loadContracts()
          }}
          contractId={receiptModal.contract.id}
          contractNumber={receiptModal.contract.contract_number}
          customerName={receiptModal.contract.customer_name || ''}
          contractTitle={receiptModal.contract.business_description}
          totalAmount={receiptModal.contract.total_amount}
          currency={receiptModal.contract.currency}
          status={receiptModal.contract.status}
          paymentType={receiptModal.type}
        />
      )}

      {/* 删除合同二次确认（5 秒读秒） */}
      <DangerConfirmModal
        open={!!deleteTarget}
        title="确认删除合同"
        description={deleteTarget && (
          <>
            即将删除合同 <strong>{deleteTarget.number}</strong>
            {deleteTarget.title ? <>（{deleteTarget.title}）</> : null}。
            该合同名下的<strong>付款计划与收付款记录将一并删除</strong>。
          </>
        )}
        warning="此操作不可撤销，金额统计、客户回款状态都会受影响。"
        onConfirm={handleDeleteConfirmed}
        onCancel={() => { if (!deleting) setDeleteTarget(null) }}
        confirming={deleting}
      />
    </div>
  )
}
