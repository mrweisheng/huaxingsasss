import { useState, useEffect, useCallback, useMemo, useRef, type Key } from 'react'
import { useNavigate } from 'react-router-dom'
import { Table, Button, Select, Input, DatePicker, Empty, message, Image, Tabs, Tooltip, Tag } from 'antd'
import { FilterOutlined, DollarOutlined, DeleteOutlined, EyeOutlined, FileTextOutlined, SearchOutlined, EditOutlined, WarningOutlined, CheckOutlined } from '@ant-design/icons'
import { paymentApi, type PaymentListParams } from '@/services/payment'
import { useDebounce } from '@/hooks/useDebounce'
import { useAuthStore } from '@/store/useAuthStore'
import { formatMoney } from '@/utils/money'
import { isNoReceipt } from '@/utils/payment'
import { methodMap, currencySymbol, fmtFull as fmt, amountToChinese as amountToChineseCompact } from '@/utils/moneyFormat'
import DangerConfirmModal from '@/components/DangerConfirmModal'
import PaymentFormModal from '@/components/PaymentFormModal'
import type { Payment } from '@/types'
import './PaymentList.css'

/** 从 receipt_data 中提取摘要信息用于展示 */
function receiptDataSummary(data: Record<string, any> | undefined): string | null {
  if (!data || typeof data !== 'object') return null
  const parts: string[] = []
  if (data.payer_name) parts.push(`付款人: ${data.payer_name}`)
  if (data.amount) {
    const sym = currencySymbol[data.currency] || ''
    parts.push(`金额: ${sym}${data.amount}`)
  }
  if (data.transaction_date) parts.push(`日期: ${data.transaction_date}`)
  return parts.length > 0 ? parts.join(' | ') : null
}

const statusMap: Record<string, { color: string; text: string }> = {
  pending: { color: '#8c8c8c', text: '待确认' },
  partial: { color: '#d97706', text: '部分支付' },
  paid: { color: '#0d9488', text: '已确认' },
  cancelled: { color: '#8c8c8c', text: '已取消' },
}


export default function PaymentList() {
  const [payments, setPayments] = useState<Payment[]>([])
  const [loading, setLoading] = useState(false)
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [keyword, setKeyword] = useState<string | undefined>(undefined)
  const [statusFilter, setStatusFilter] = useState<string | undefined>(undefined)
  const [typeFilter, setTypeFilter] = useState<string | undefined>(undefined)
  const [dateRange, setDateRange] = useState<[string, string] | null>(null)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const [previewLoading, setPreviewLoading] = useState(false)
  const [expandPreviewLoading, setExpandPreviewLoading] = useState<number | null>(null)
  const [expandedRowKeys, setExpandedRowKeys] = useState<Key[]>([])
  const abortControllerRef = useRef<AbortController | null>(null)
  const user = useAuthStore((s) => s.user)
  const role = user?.role || ''
  const navigate = useNavigate()
  // 删除二次确认弹窗状态
  const [deleteTarget, setDeleteTarget] = useState<Payment | null>(null)
  const [deleting, setDeleting] = useState(false)
  // 人工确认入账弹窗状态
  const [manualConfirmTarget, setManualConfirmTarget] = useState<Payment | null>(null)
  const [manualConfirming, setManualConfirming] = useState(false)
  // 编辑弹窗状态
  const [editTarget, setEditTarget] = useState<Payment | null>(null)

  const defaultTab = role === 'expense' ? 'expense' : role === 'income' ? 'income' : 'all'
  const [activeTab, setActiveTab] = useState(defaultTab)

  const loadPayments = useCallback(async () => {
    abortControllerRef.current?.abort()
    const controller = new AbortController()
    abortControllerRef.current = controller

    setLoading(true)
    try {
      const params: PaymentListParams = { page, per_page: 20 }
      if (keyword) params.keyword = keyword
      if (statusFilter) params.status = statusFilter
      if (typeFilter) params.type = typeFilter
      if (dateRange) {
        params.date_from = dateRange[0]
        params.date_to = dateRange[1]
      }
      const response = await paymentApi.getList(params, controller.signal)
      setPayments(response.items)
      setTotal(response.pagination.total)
    } catch (error: any) {
      if (error?.name === 'AbortError' || error?.code === 'ERR_CANCELED') return
      console.error(error)
    } finally {
      if (!controller.signal.aborted) {
        setLoading(false)
      }
    }
  }, [page, keyword, statusFilter, typeFilter, dateRange])

  useEffect(() => {
    loadPayments()
    return () => {
      abortControllerRef.current?.abort()
    }
  }, [loadPayments])

  const handleSearch = useDebounce((value: string) => {
    setKeyword(value || undefined)
    setPage(1)
  }, 400)

  const handleDateChange = (_: any, dateStrings: [string, string]) => {
    if (dateStrings[0] && dateStrings[1]) {
      setDateRange(dateStrings)
    } else {
      setDateRange(null)
    }
    setPage(1)
  }

  const handleStatusChange = (value: string | undefined) => {
    setStatusFilter(value)
    setPage(1)
  }

  const handleTabChange = (key: string) => {
    setActiveTab(key)
    setTypeFilter(key === 'all' ? undefined : key)
    setPage(1)
  }

  const handleDelete = async (id: number) => {
    setDeleting(true)
    try {
      await paymentApi.delete(id)
      message.success('删除成功')
      setDeleteTarget(null)
      loadPayments()
    } catch (error: any) {
      message.error(error.response?.data?.detail || '删除失败')
    } finally {
      setDeleting(false)
    }
  }

  const handleManualConfirm = async (id: number) => {
    setManualConfirming(true)
    try {
      await paymentApi.manualConfirm(id)
      message.success('人工确认成功，已按表单信息入账')
      setManualConfirmTarget(null)
      loadPayments()
    } catch (error: any) {
      message.error(error.response?.data?.detail || '人工确认失败')
    } finally {
      setManualConfirming(false)
    }
  }

  // ── KPI 统计（useMemo 避免重算） ──
  const kpiGroups = useMemo(() => payments.reduce((acc, p) => {
    if (p.status !== 'paid') return acc
    if (role === 'income' && p.type !== 'income') return acc
    if (role === 'expense' && p.type !== 'expense') return acc
    const key = `${p.type}_${p.currency}`
    if (!acc[key]) {
      acc[key] = { total: 0, count: 0, currency: p.currency, type: p.type }
    }
    // paid_amount 后端是 Decimal，序列化后为字符串；不显式 Number() 会触发字符串拼接，
    // 导致 group.total 变成 "01000.00500.00" 之类的脏字符串，下游 formatMoney/amountToChinese 全崩。
    acc[key].total += Number(p.paid_amount) || 0
    acc[key].count += 1
    return acc
  }, {} as Record<string, { total: number; count: number; currency: string; type: string }>), [payments, role])

  const incomeGroups = useMemo(() => Object.values(kpiGroups).filter(g => g.type === 'income'), [kpiGroups])
  const expenseGroups = useMemo(() => Object.values(kpiGroups).filter(g => g.type === 'expense'), [kpiGroups])

  const statusCounts = useMemo(() => payments.reduce((acc, p) => {
    acc[p.status] = (acc[p.status] || 0) + 1
    return acc
  }, {} as Record<string, number>), [payments])

  // ── 列定义 ──
  const columns = [
    // 类型 — 缩小为小色块
    {
      title: '',
      dataIndex: 'type',
      key: 'type',
      width: 40,
      align: 'center' as const,
      render: (v: string) => (
        <Tooltip title={v === 'income' ? '收入' : '支出'}>
          <span className={`pl-type-dot ${v}`}>
            {v === 'income' ? '收' : '支'}
          </span>
        </Tooltip>
      ),
    },
    // 客户
    {
      title: '客户',
      key: 'customer',
      width: 110,
      render: (_: unknown, record: Payment) => (
        <span className="pl-cell-customer-main">{record.customer_name || '-'}</span>
      ),
    },
    // 关联合同
    {
      title: '关联合同',
      key: 'contract',
      width: 200,
      render: (_: unknown, record: Payment) => (
        <div className="pl-cell-compound">
          {record.contract_number ? (
            <a
              className="pl-cell-contract-link"
              onClick={() => navigate(`/contracts/${record.contract_id}`)}
            >
              {record.contract_number}
            </a>
          ) : (
            <span className="pl-cell-contract-link">-</span>
          )}
          {record.contract_business_description && (
            <span className="pl-cell-business-brief">{record.contract_business_description}</span>
          )}
        </div>
      ),
    },
    // 业务说明 — 自动换行，不限行数
    {
      title: '业务说明',
      key: 'description',
      width: 260,
      responsive: ['md' as const],
      render: (_: unknown, record: Payment) => (
        <span className="pl-cell-desc">{record.description || '-'}</span>
      ),
    },
    // 币种
    {
      title: '币种',
      dataIndex: 'currency',
      key: 'currency',
      width: 55,
      align: 'center' as const,
      render: (v: string) => (
        <span className={`pl-currency-tag ${v?.toLowerCase()}`}>{v || '-'}</span>
      ),
    },
    // 金额（含 CNY 折算提示）
    {
      title: '金额',
      key: 'amount',
      width: 130,
      align: 'right' as const,
      render: (_: unknown, record: Payment) => {
        const isPaid = record.status === 'paid'
        return (
          <div>
            <span className={`pl-cell-amount ${isPaid ? 'success' : ''}`}>
              {fmt(record.paid_amount, record.currency)}
            </span>
            {isNoReceipt(record) && (
              <Tooltip title="无凭证 · 用户口头确认">
                <span className="pl-cell-no-receipt">无凭证</span>
              </Tooltip>
            )}
          </div>
        )
      },
    },
    // 付款日期
    {
      title: '付款日期',
      dataIndex: 'paid_date',
      key: 'paid_date',
      width: 100,
      minWidth: 80,
      responsive: ['md' as const],
      render: (v: string) => v || '-',
    },
    // 方式 — 改用小标签
    {
      title: '方式',
      dataIndex: 'payment_method',
      key: 'payment_method',
      width: 80,
      responsive: ['md' as const],
      render: (v: string) => {
        const label = methodMap[v] || v || '-'
        return <span className="pl-method-tag">{label}</span>
      },
    },
    // 收款/付款账户：收入显示己方收款账户名，支出显示对方收款方
    {
      title: '收款账户',
      key: 'payment_account',
      width: 160,
      responsive: ['lg' as const],
      render: (_: unknown, record: Payment) => {
        if (record.type === 'income') {
          // 己方预设收款账户（payment_account_title 由后端 join 填充）
          if (!record.payment_account_title) return <span className="pl-cell-account-empty">-</span>
          return (
            <Tooltip title={record.payment_account_title}>
              <span className="pl-cell-account">{record.payment_account_title}</span>
            </Tooltip>
          )
        }
        // 支出：对方收款方（payee_name）
        if (!record.payee_name) return <span className="pl-cell-account-empty">-</span>
        return (
          <Tooltip title={record.payee_name}>
            <span className="pl-cell-account">{record.payee_name}</span>
          </Tooltip>
        )
      },
    },
    // 状态（含凭证校验状态：failed 标红 / pending 校验中 / passed 已通过）
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      minWidth: 90,
      render: (s: string, record: Payment) => {
        const info = statusMap[s]
        const vs = record.verification_status
        return (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            {info
              ? <span className={`payment-status ${s}`}>{info.text}</span>
              : <span className="payment-status">{s}</span>}
            {vs === 'failed' && (
              <Tag color="error" style={{ margin: 0, fontSize: 11 }}>凭证不符</Tag>
            )}
            {vs === 'pending' && (
              <Tag color="processing" style={{ margin: 0, fontSize: 11 }}>校验中</Tag>
            )}
          </div>
        )
      },
    },
    // 操作
    {
      title: '操作',
      key: 'action',
      width: 120,
      minWidth: 110,
      align: 'center' as const,
      render: (_: unknown, record: Payment) => (
        <div className="pl-action-btns">
          {record.verification_status === 'failed' && (
            <Tooltip title={record.verification_result?.reason || '凭证不符，点击编辑核对'}>
              <Button
                type="text"
                size="small"
                icon={<WarningOutlined />}
                style={{ color: '#ff4d4f' }}
                onClick={() => setEditTarget(record)}
              />
            </Tooltip>
          )}
          {role === 'admin' && record.verification_status === 'failed' && record.status !== 'paid' && (
            <Tooltip title="人工确认入账">
              <Button
                type="text"
                size="small"
                icon={<CheckOutlined />}
                style={{ color: '#0d9488' }}
                onClick={() => setManualConfirmTarget(record)}
              />
            </Tooltip>
          )}
          {record.receipt_image_path ? (
            <Tooltip title="查看凭证">
              <Button
                type="text"
                size="small"
                icon={<EyeOutlined />}
                loading={previewLoading}
                onClick={async () => {
                  setPreviewLoading(true)
                  try {
                    const url = await paymentApi.getReceiptUrl(record.id)
                    setPreviewUrl(url)
                  } catch {
                    message.error('加载凭证失败')
                  } finally {
                    setPreviewLoading(false)
                  }
                }}
              />
            </Tooltip>
          ) : record.receipt_data ? (
            <Tooltip title={receiptDataSummary(record.receipt_data)}>
              <Button type="text" size="small" icon={<FileTextOutlined />} style={{ color: '#0d9488' }} />
            </Tooltip>
          ) : (
            <span style={{ color: '#ccc', fontSize: 11 }}>-</span>
          )}
          <Tooltip title="编辑">
            <Button
              type="text"
              size="small"
              icon={<EditOutlined />}
              onClick={() => setEditTarget(record)}
            />
          </Tooltip>
          {role === 'admin' && (
            <Tooltip title="删除">
              <Button
                type="text"
                danger
                size="small"
                icon={<DeleteOutlined />}
                onClick={() => setDeleteTarget(record)}
              />
            </Tooltip>
          )}
        </div>
      ),
    },
  ]

  const tabItems = [
    { key: 'all', label: '全部' },
    { key: 'income', label: '收入' },
    { key: 'expense', label: '支出' },
  ]

  const visibleTabs = role === 'income'
    ? tabItems.filter(t => t.key === 'income')
    : role === 'expense'
      ? tabItems.filter(t => t.key === 'expense')
      : tabItems

  return (
    <div className="payment-list-container">
      {/* 页面标题栏 */}
      <div className="page-topbar">
        <div className="page-topbar-left">
          <div className="page-title-wrap">
            <div className="page-title-icon">
              <DollarOutlined />
            </div>
            <span className="page-title-text">
              {role === 'expense' ? '支出管理' : role === 'income' ? '收入管理' : activeTab === 'income' ? '收入管理' : activeTab === 'expense' ? '支出管理' : '收付管理'}
            </span>
            <span className="page-title-count">{total} 条记录</span>
          </div>
        </div>
        <div className="page-topbar-right">
          <div className="pl-filter-bar">
            <Input
              placeholder="搜索合同编号/客户"
              allowClear
              onChange={e => handleSearch(e.target.value)}
              className="pl-search-box"
              prefix={<SearchOutlined style={{ color: 'var(--text-tertiary)' }} />}
            />
            <DatePicker.RangePicker
              onChange={handleDateChange}
              style={{ width: 210 }}
              size="middle"
              placeholder={['开始日期', '结束日期']}
            />
            <Select
              placeholder="状态筛选"
              allowClear
              style={{ width: 110 }}
              value={statusFilter}
              onChange={handleStatusChange}
              suffixIcon={<FilterOutlined />}
              options={[
                { label: '待确认', value: 'pending' },
                { label: '部分支付', value: 'partial' },
                { label: '已确认', value: 'paid' },
              ]}
            />
          </div>
        </div>
      </div>

      {visibleTabs.length > 1 && (
        <Tabs activeKey={activeTab} onChange={handleTabChange} items={visibleTabs} style={{ marginBottom: 16 }} />
      )}

      {payments.length > 0 && (
        <div className="pl-kpi-section">
          <div className="pl-kpi-grid">
            {(activeTab === 'all' || activeTab === 'income') && (
            <div className="pl-kpi-col pl-kpi-col--income">
              <div className="pl-kpi-col__header">
                <svg className="pl-kpi-col__arrow" viewBox="0 0 24 24" fill="none">
                  <path d="M12 19V5M12 5L6 11M12 5L18 11" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
                <span className="pl-kpi-col__title">收入</span>
              </div>
              <div className="pl-kpi-col__cards">
                {['CNY', 'HKD'].map(curr => {
                  const group = incomeGroups.find(g => g.currency === curr)
                  const m = group ? formatMoney(group.total) : null
                  return (
                    <div key={curr} className="pl-big-card pl-big-card--income">
                      <span className="pl-big-card__count">{group ? `${group.count} 笔` : '0 笔'}</span>
                      <div className="pl-big-card__amount">
                        {group && m ? (
                          <Tooltip title={`${currencySymbol[curr] || ''}${m.full}`} placement="top" mouseEnterDelay={0.3}>
                            <span className="pl-big-card__amount-inner">
                              <span className="pl-big-card__symbol">{currencySymbol[curr] || ''}</span>
                              <span className="pl-big-card__number">{m.display}</span>
                              {m.unit && <span className="pl-big-card__unit">{m.unit}</span>}
                            </span>
                          </Tooltip>
                        ) : (
                          <span className="pl-big-card__number pl-big-card__number--empty">--</span>
                        )}
                      </div>
                      <div className="pl-big-card__chinese">
                        {group ? amountToChineseCompact(group.total, curr) : '暂无数据'}
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
            )}

            {(activeTab === 'all' || activeTab === 'expense') && (
            <div className="pl-kpi-col pl-kpi-col--expense">
              <div className="pl-kpi-col__header">
                <svg className="pl-kpi-col__arrow" viewBox="0 0 24 24" fill="none">
                  <path d="M12 5V19M12 19L6 13M12 19L18 13" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
                <span className="pl-kpi-col__title">支出</span>
              </div>
              <div className="pl-kpi-col__cards">
                {['CNY', 'HKD'].map(curr => {
                  const group = expenseGroups.find(g => g.currency === curr)
                  const m = group ? formatMoney(group.total) : null
                  return (
                    <div key={curr} className="pl-big-card pl-big-card--expense">
                      <span className="pl-big-card__count">{group ? `${group.count} 笔` : '0 笔'}</span>
                      <div className="pl-big-card__amount">
                        {group && m ? (
                          <Tooltip title={`${currencySymbol[curr] || ''}${m.full}`} placement="top" mouseEnterDelay={0.3}>
                            <span className="pl-big-card__amount-inner">
                              <span className="pl-big-card__symbol">{currencySymbol[curr] || ''}</span>
                              <span className="pl-big-card__number">{m.display}</span>
                              {m.unit && <span className="pl-big-card__unit">{m.unit}</span>}
                            </span>
                          </Tooltip>
                        ) : (
                          <span className="pl-big-card__number pl-big-card__number--empty">--</span>
                        )}
                      </div>
                      <div className="pl-big-card__chinese">
                        {group ? amountToChineseCompact(group.total, curr) : '暂无数据'}
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
            )}
          </div>

          <div className="pl-kpi-status-bar">
            <span className="pl-kpi-status__label">状态分布</span>
            <div className="pl-kpi-status__chips">
              {Object.entries(statusCounts).map(([status, count]) => {
                const info = statusMap[status]
                return (
                  <div key={status} className={`pl-kpi-chip pl-kpi-chip--${status}`}>
                    <span className="pl-kpi-chip__dot" />
                    <span className="pl-kpi-chip__text">{info?.text || status}</span>
                    <span className="pl-kpi-chip__count">{count}</span>
                  </div>
                )
              })}
            </div>
          </div>
        </div>
      )}

      {payments.length === 0 && !loading ? (
        <Empty description={activeTab === 'income' ? '暂无收入记录' : activeTab === 'expense' ? '暂无支出记录' : '暂无付款记录'} className="empty-state" />
      ) : (
        <Table
          columns={columns}
          dataSource={payments}
          loading={loading}
          rowKey="id"
          scroll={{ x: 'max-content' }}
          expandable={{
            expandedRowRender: (record) => (
              <div className="pl-expand-notes">
                {/* 手机端完整信息行 */}
                <div className="pl-expand-mobile-only">
                  <div className="pl-expand-row">
                    <span className="pl-expand-label">业务说明</span>
                    <span className="pl-expand-value">{record.description || '-'}</span>
                  </div>
                  <div className="pl-expand-row">
                    <span className="pl-expand-label">付款日期</span>
                    <span className="pl-expand-value">{record.paid_date || '-'}</span>
                  </div>
                  <div className="pl-expand-row">
                    <span className="pl-expand-label">付款方式</span>
                    <span className="pl-expand-value">{methodMap[record.payment_method as string] || record.payment_method || '-'}</span>
                  </div>
                  <div className="pl-expand-row">
                    <span className="pl-expand-label">期数</span>
                    <span className="pl-expand-value">{record.installment_number ? `第${record.installment_number}期` : '-'}</span>
                  </div>
                  {record.type === 'income' && record.payment_account_title && (
                    <div className="pl-expand-row">
                      <span className="pl-expand-label">收款账户</span>
                      <span className="pl-expand-value">{record.payment_account_title}</span>
                    </div>
                  )}
                  {record.type === 'expense' && record.payee_name && (
                    <div className="pl-expand-row">
                      <span className="pl-expand-label">收款方</span>
                      <span className="pl-expand-value">{record.payee_name}</span>
                    </div>
                  )}
                </div>
                {/* 凭证图片预览 */}
                {record.receipt_image_path && (
                  <div className="pl-expand-row" style={{ marginBottom: 8 }}>
                    <span className="pl-expand-label">凭证</span>
                    <span className="pl-expand-value">
                      <Button
                        type="link"
                        size="small"
                        icon={<EyeOutlined />}
                        loading={expandPreviewLoading === record.id}
                        onClick={async () => {
                          setExpandPreviewLoading(record.id)
                          try {
                            const url = await paymentApi.getReceiptUrl(record.id)
                            setPreviewUrl(url)
                          } catch {
                            message.error('加载凭证失败')
                          } finally {
                            setExpandPreviewLoading(null)
                          }
                        }}
                      >查看凭证</Button>
                    </span>
                  </div>
                )}
                {/* 凭证校验结果（不符/存疑时醒目展示） */}
                {record.verification_result && record.verification_status !== 'passed' && (
                  <div style={{
                    padding: '8px 12px', marginBottom: 8, borderRadius: 6,
                    background: record.verification_status === 'failed' ? '#fff2f0' : '#fffbe6',
                    border: `1px solid ${record.verification_status === 'failed' ? '#ffccc7' : '#ffe58f'}`,
                  }}>
                    <div style={{ fontWeight: 600, color: record.verification_status === 'failed' ? '#cf1322' : '#d48806', marginBottom: 6, fontSize: 13 }}>
                      <WarningOutlined style={{ marginRight: 6 }} />
                      {record.verification_status === 'failed' ? '凭证校验不符' : '凭证校验存疑'}
                    </div>
                    {(() => {
                      const vr = record.verification_result!
                      const exp = vr.expected || {}
                      const ext = vr.extracted || {}
                      return (
                        <div style={{ fontSize: 12, lineHeight: 1.8, color: '#595959' }}>
                          {exp.amount != null && (
                            <div>表单金额：<strong>{exp.currency} {exp.amount}</strong>
                              {ext.amount != null && (
                                <>　凭证识别：<strong style={{ color: vr.match?.amount === false ? '#cf1322' : '#52c41a' }}>{ext.currency || exp.currency} {ext.amount}</strong></>
                              )}
                            </div>
                          )}
                          {exp.payer && (
                            <div>表单客户：{exp.payer}{ext.payer_name ? `　凭证付款方：${ext.payer_name}` : ''}</div>
                          )}
                          {vr.confidence != null && <div>识别置信度：{(vr.confidence * 100).toFixed(0)}%</div>}
                          {vr.reason && <div style={{ marginTop: 4, color: '#8c8c8c' }}>{vr.reason}</div>}
                        </div>
                      )
                    })()}
                    <div style={{ marginTop: 6 }}>
                      <Button type="link" size="small" icon={<EditOutlined />} onClick={() => setEditTarget(record)}>
                        去核对/修改
                      </Button>
                    </div>
                  </div>
                )}
                {record.notes ? (
                  <div style={{ padding: '8px 0' }}>
                    <span className="pl-expand-label" style={{ display: 'inline-block', marginBottom: 4 }}>备注</span>
                    <div style={{ color: 'var(--text-secondary)', fontSize: 13, lineHeight: 1.6, whiteSpace: 'pre-wrap' }}>{record.notes}</div>
                  </div>
                ) : null}
                {record.outstanding_amount != null && record.outstanding_currency && record.type === 'income' && (
                  <div style={{ paddingTop: 8, borderTop: '1px solid var(--border-light)' }}>
                    <span className="pl-expand-label" style={{ display: 'inline-block', marginBottom: 4 }}>本次结算后剩余尾款</span>
                    <div style={{ color: 'var(--text-primary)', fontSize: 14, fontWeight: 600 }}>
                      {fmt(record.outstanding_amount, record.outstanding_currency)}
                    </div>
                  </div>
                )}
                {record.receipt_data && !record.receipt_image_path && (
                  <div style={{ marginTop: 8 }}>
                    <span className="pl-expand-label" style={{ display: 'inline-block', marginBottom: 4 }}>凭证数据</span>
                    <div style={{ color: 'var(--text-secondary)', fontSize: 13 }}>{receiptDataSummary(record.receipt_data)}</div>
                  </div>
                )}
              </div>
            ),
            rowExpandable: (_record) => true,
            expandedRowKeys,
            onExpandedRowsChange: (keys: readonly Key[]) => setExpandedRowKeys([...keys]),
          }}
          rowClassName={(record) => {
            if (record.verification_status === 'failed') return 'tr-verification-failed'
            if (record.status === 'paid') return 'tr-paid'
            return ''
          }}
          pagination={{
            current: page,
            pageSize: 20,
            total,
            onChange: setPage,
            showTotal: (t) => `共 ${t} 条`,
          }}
          className="payment-table"
        />
      )}

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

      {/* 删除付款记录二次确认（5 秒读秒） */}
      <DangerConfirmModal
        open={!!deleteTarget}
        title={deleteTarget?.type === 'expense' ? '确认删除支出记录' : '确认删除收款记录'}
        description={deleteTarget && (
          <>
            即将删除一笔 <strong>{fmt(deleteTarget.paid_amount, deleteTarget.currency)}</strong> 的
            {deleteTarget.type === 'expense' ? '支出' : '收款'}记录
            {deleteTarget.contract_number ? <>（合同 <strong>{deleteTarget.contract_number}</strong>）</> : null}。
          </>
        )}
        warning="删除后将无法恢复，对应合同的已收/已付金额会同步扣减。"
        onConfirm={() => { if (deleteTarget) handleDelete(deleteTarget.id) }}
        onCancel={() => { if (!deleting) setDeleteTarget(null) }}
        confirming={deleting}
      />

      <DangerConfirmModal
        open={!!manualConfirmTarget}
        title="确认人工入账"
        description={manualConfirmTarget && (
          <>
            将以表单录入信息为准，人工确认这笔 <strong>{fmt(manualConfirmTarget.paid_amount, manualConfirmTarget.currency)}</strong> 收款并入账。
            <div style={{ marginTop: 8 }}>
              {manualConfirmTarget.contract_wechat_group && <div>微信群：<strong>{manualConfirmTarget.contract_wechat_group}</strong></div>}
              {manualConfirmTarget.customer_name && <div>客户：<strong>{manualConfirmTarget.customer_name}</strong></div>}
              {(manualConfirmTarget.description || manualConfirmTarget.contract_business_description) && (
                <div>业务：<strong>{manualConfirmTarget.description || manualConfirmTarget.contract_business_description}</strong></div>
              )}
            </div>
          </>
        )}
        warning="该操作会把付款状态改为已确认，并同步计入合同已收金额；系统会记录人工确认痕迹和操作审计。"
        okText="确认入账"
        onConfirm={() => { if (manualConfirmTarget) handleManualConfirm(manualConfirmTarget.id) }}
        onCancel={() => { if (!manualConfirming) setManualConfirmTarget(null) }}
        confirming={manualConfirming}
      />

      {/* 编辑收支记录（修复凭证不符 / 改字段） */}
      {editTarget && (
        <PaymentFormModal
          open={!!editTarget}
          mode="edit"
          editing={editTarget}
          contractId={editTarget.contract_id}
          contractNumber={editTarget.contract_number}
          customerName={editTarget.customer_name}
          contractTitle={editTarget.contract_business_description}
          wechatGroup={editTarget.contract_wechat_group}
          currency={editTarget.contract_currency || editTarget.currency}
          onClose={() => setEditTarget(null)}
          onSuccess={() => loadPayments()}
        />
      )}
    </div>
  )
}
