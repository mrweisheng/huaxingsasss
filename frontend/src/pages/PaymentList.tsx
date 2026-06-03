import { useState, useEffect, useCallback, useMemo, useRef, type Key } from 'react'
import { useNavigate } from 'react-router-dom'
import { Table, Button, Select, Input, DatePicker, Empty, Popconfirm, message, Image, Tabs, Tooltip } from 'antd'
import { FilterOutlined, DollarOutlined, DeleteOutlined, EyeOutlined, FileTextOutlined, SearchOutlined } from '@ant-design/icons'
import { paymentApi, type PaymentListParams } from '@/services/payment'
import { useAuthStore } from '@/store/useAuthStore'
import type { Payment } from '@/types'
import './PaymentList.css'

const currencySymbol: Record<string, string> = { CNY: '¥', HKD: 'HK$', USD: '$' }

function fmt(amount: number | undefined | null, currency: string): string {
  if (amount === undefined || amount === null) return '-'
  const symbol = currencySymbol[currency] || '¥'
  return `${symbol}${amount.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
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

function amountToChineseCompact(amount: number, currency: string): string {
  return amountToChinese(amount, currency)
}

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
  pending: { color: '#8c8c8c', text: '待支付' },
  partial: { color: '#d97706', text: '部分支付' },
  paid: { color: '#0d9488', text: '已确认' },
  cancelled: { color: '#8c8c8c', text: '已取消' },
}

const methodMap: Record<string, string> = {
  bank_transfer: '银行转账',
  wechat: '微信',
  alipay: '支付宝',
  cash: '现金',
  check: '支票',
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
  const [expandedRowKeys, setExpandedRowKeys] = useState<Key[]>([])
  const abortControllerRef = useRef<AbortController | null>(null)
  const user = useAuthStore((s) => s.user)
  const role = user?.role || ''
  const navigate = useNavigate()

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

  const handleSearch = (value: string) => {
    setKeyword(value || undefined)
    setPage(1)
  }

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
    try {
      await paymentApi.delete(id)
      message.success('删除成功')
      loadPayments()
    } catch (error: any) {
      message.error(error.response?.data?.detail || '删除失败')
    }
  }

  // ── KPI 统计（useMemo 避免重算） ──
  const kpiGroups = useMemo(() => payments.reduce((acc, p) => {
    if (role === 'income' && p.type !== 'income') return acc
    if (role === 'expense' && p.type !== 'expense') return acc
    const key = `${p.type}_${p.currency}`
    if (!acc[key]) {
      acc[key] = { total: 0, count: 0, currency: p.currency, type: p.type }
    }
    acc[key].total += p.paid_amount || 0
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
        <div className="pl-cell-compound">
          <span className="pl-cell-customer-main">{record.customer_name || '-'}</span>
          {record.type === 'expense' && record.payee_name && (
            <span className="pl-cell-payee">收款：{record.payee_name}</span>
          )}
        </div>
      ),
    },
    // 关联合同
    {
      title: '关联合同',
      key: 'contract',
      width: 150,
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
          <span className="pl-cell-installment">
            第{record.installment_number}期{record.type === 'income' ? '收款' : '支出'}
          </span>
        </div>
      ),
    },
    // 业务说明 — 自动换行，不限行数
    {
      title: '业务说明',
      key: 'description',
      width: 260,
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
            {record.paid_amount_in_cny != null && record.currency !== 'CNY' && (
              <div style={{ fontSize: 11, color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)' }}>
                ≈ ¥{Math.round(record.paid_amount_in_cny).toLocaleString('zh-CN')}
              </div>
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
      render: (v: string) => v || '-',
    },
    // 方式 — 改用小标签
    {
      title: '方式',
      dataIndex: 'payment_method',
      key: 'payment_method',
      width: 80,
      render: (v: string) => {
        const label = methodMap[v] || v || '-'
        return <span className="pl-method-tag">{label}</span>
      },
    },
    // 状态
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 80,
      minWidth: 70,
      render: (s: string) => {
        const info = statusMap[s]
        if (!info) return <span className="payment-status">{s}</span>
        return <span className={`payment-status ${s}`}>{info.text}</span>
      },
    },
    // 操作
    {
      title: '操作',
      key: 'action',
      width: 90,
      minWidth: 80,
      align: 'center' as const,
      render: (_: unknown, record: Payment) => (
        <div className="pl-action-btns">
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
          {role === 'admin' && (
            <Popconfirm
              title="确定删除此付款记录？"
              description="删除后将无法恢复，合同金额将同步扣减"
              onConfirm={() => handleDelete(record.id)}
              okText="删除"
              cancelText="取消"
              okButtonProps={{ danger: true }}
            >
              <Tooltip title="删除">
                <Button type="text" danger size="small" icon={<DeleteOutlined />} />
              </Tooltip>
            </Popconfirm>
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
              {role === 'expense' ? '支出管理' : role === 'income' ? '收入管理' : '收付管理'}
            </span>
            <span className="page-title-count">{total} 条记录</span>
          </div>
        </div>
        <div className="page-topbar-right">
          <div className="pl-filter-bar">
            <Input.Search
              placeholder="搜索合同编号/客户"
              allowClear
              onSearch={handleSearch}
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
                  return (
                    <div key={curr} className="pl-big-card pl-big-card--income">
                      <div className="pl-big-card__currency">{currencySymbol[curr] || curr} {curr}</div>
                      <div className="pl-big-card__amount">
                        {group ? (
                          <>
                            <span className="pl-big-card__symbol">{currencySymbol[curr] || ''}</span>
                            <span className="pl-big-card__number">
                              {group.total.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                            </span>
                          </>
                        ) : (
                          <span className="pl-big-card__number pl-big-card__number--empty">--</span>
                        )}
                      </div>
                      <div className="pl-big-card__chinese">
                        {group ? amountToChineseCompact(group.total, curr) : '暂无数据'}
                      </div>
                      <div className="pl-big-card__count">{group ? `${group.count} 笔` : '0 笔'}</div>
                    </div>
                  )
                })}
              </div>
            </div>

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
                  return (
                    <div key={curr} className="pl-big-card pl-big-card--expense">
                      <div className="pl-big-card__currency">{currencySymbol[curr] || curr} {curr}</div>
                      <div className="pl-big-card__amount">
                        {group ? (
                          <>
                            <span className="pl-big-card__symbol">{currencySymbol[curr] || ''}</span>
                            <span className="pl-big-card__number">
                              {group.total.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                            </span>
                          </>
                        ) : (
                          <span className="pl-big-card__number pl-big-card__number--empty">--</span>
                        )}
                      </div>
                      <div className="pl-big-card__chinese">
                        {group ? amountToChineseCompact(group.total, curr) : '暂无数据'}
                      </div>
                      <div className="pl-big-card__count">{group ? `${group.count} 笔` : '0 笔'}</div>
                    </div>
                  )
                })}
              </div>
            </div>
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
        <Empty description="暂无付款记录" className="empty-state" />
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
                {record.notes ? (
                  <><strong>备注：</strong>{record.notes}</>
                ) : (
                  <span style={{ color: 'var(--text-tertiary)' }}>暂无备注</span>
                )}
                {record.paid_amount_in_cny != null && record.currency !== 'CNY' && (
                  <div style={{ marginTop: 8 }}>
                    <strong>折算 CNY：</strong>
                    {fmt(record.paid_amount_in_cny, 'CNY')}
                    {record.exchange_rate && (
                      <span style={{ color: 'var(--text-tertiary)', marginLeft: 8 }}>
                        （汇率：{record.exchange_rate}）
                      </span>
                    )}
                  </div>
                )}
                {record.receipt_data && (
                  <div style={{ marginTop: 8 }}>
                    <strong>凭证数据：</strong>{receiptDataSummary(record.receipt_data)}
                  </div>
                )}
              </div>
            ),
            rowExpandable: (record) => !!(record.notes || (record.paid_amount_in_cny != null && record.currency !== 'CNY') || record.receipt_data),
            expandedRowKeys,
            onExpandedRowsChange: (keys: readonly Key[]) => setExpandedRowKeys([...keys]),
          }}
          rowClassName={(record) => {
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
    </div>
  )
}
