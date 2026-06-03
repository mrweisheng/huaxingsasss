import { useState, useEffect, useCallback, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { Input, Select, DatePicker, Button, Popconfirm, message, Empty } from 'antd'
import { PlusOutlined, SearchOutlined, FilterOutlined, DeleteOutlined, FileTextOutlined } from '@ant-design/icons'
import { contractApi } from '@/services/contract'
import { useAuthStore } from '@/store/useAuthStore'
import ContractUploadWizard from '@/components/ContractUploadWizard'
import type { Contract } from '@/types'
import dayjs from 'dayjs'
import './ContractList.css'

const { RangePicker } = DatePicker

const statusConfig: Record<string, { color: string; bg: string; text: string }> = {
  active: { color: '#1890ff', bg: '#e6f7ff', text: '执行中' },
  completed: { color: '#52c41a', bg: '#f6ffed', text: '已完成' },
}

const businessTypeConfig: Record<string, { bg: string; border: string }> = {
  '车辆业务': { bg: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)', border: '#667eea' },
  '中港牌业务': { bg: 'linear-gradient(135deg, #11998e 0%, #38ef7d 100%)', border: '#11998e' },
}

const currencySymbol: Record<string, string> = {
  CNY: '¥',
  HKD: 'HK$',
  USD: '$',
}

function formatAmount(amount: number | null | undefined, currency: string): string {
  const symbol = currencySymbol[currency] || '¥'
  if (amount == null) return `${symbol}--`
  return `${symbol}${amount.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
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
  const [contracts, setContracts] = useState<Contract[]>([])
  const [loading, setLoading] = useState(false)
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [keyword, setKeyword] = useState('')
  const [statusFilter, setStatusFilter] = useState<string | undefined>(undefined)
  const [dateRange, setDateRange] = useState<[dayjs.Dayjs | null, dayjs.Dayjs | null] | null>(null)
  const [hoveredCard, setHoveredCard] = useState<number | null>(null)
  const [uploadModalOpen, setUploadModalOpen] = useState(false)
  const abortControllerRef = useRef<AbortController | null>(null)
  const searchTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

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
      const response = await contractApi.getList(params, controller.signal)
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
  }, [page, keyword, statusFilter, dateRange])

  useEffect(() => {
    loadContracts()
    return () => {
      abortControllerRef.current?.abort()
      if (searchTimerRef.current) clearTimeout(searchTimerRef.current)
    }
  }, [loadContracts])

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

  const handleDelete = async (id: number) => {
    try {
      await contractApi.delete(id)
      message.success('删除成功')
      loadContracts()
    } catch (error: any) {
      message.error(error.response?.data?.detail || '删除失败')
    }
  }

  const totalPages = Math.ceil(total / 20)

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
            placeholder="搜索客户名称..."
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
          <RangePicker
            onChange={handleDateChange}
            value={dateRange}
          />
          {(role === 'admin' || role === 'income') && (
            <Button type="primary" icon={<PlusOutlined />} onClick={() => setUploadModalOpen(true)}>
              上传
            </Button>
          )}
        </div>
      </div>

      {contracts.length === 0 && !loading ? (
        <Empty description="暂无合同数据" className="empty-state" />
      ) : (
        <>
          <div className="contract-grid">
            {contracts.map((contract, index) => {
              const status = statusConfig[contract.status] || statusConfig.active
              const businessType = businessTypeConfig[contract.business_type || '']
              const progress = calculateProgress(contract.paid_amount, contract.total_amount)
              const isHovered = hoveredCard === contract.id

              return (
                <div
                  key={contract.id}
                  className={`contract-card ${isHovered ? 'hovered' : ''}`}
                  onClick={() => navigate(`/contracts/${contract.id}`)}
                  onMouseEnter={() => setHoveredCard(contract.id)}
                  onMouseLeave={() => setHoveredCard(null)}
                  style={{ animationDelay: `${index * 50}ms` }}
                >
                  {contract.business_type && (
                    <div
                      className="business-type-badge"
                      style={{ background: businessType?.bg || '#667eea', borderColor: businessType?.border || '#667eea' }}
                    >
                      {contract.business_type}
                    </div>
                  )}

                  {/* 客户名称行 — 第二视觉权重，仅次于金额 */}
                  <div className="customer-name-hero">
                    <span className="customer-name-text">{contract.customer_name || '未关联客户'}</span>
                    <div className="status-badge" style={{ color: status.color, backgroundColor: status.bg }}>
                      {status.text}
                    </div>
                  </div>

                  {/* 合同元信息：编号 + 标题 紧凑一行 */}
                  <div className="contract-meta-row">
                    <span className="contract-meta-number">{contract.contract_number}</span>
                    {(contract.title || contract.customer_name) && (
                      <span className="contract-meta-sep">·</span>
                    )}
                    <span className="contract-meta-title">{contract.title || (contract.customer_name ? '合同详情' : '无标题')}</span>
                  </div>

                  {/* 业务描述 — 固定高度占位，统一卡片节奏 */}
                  <div className="business-desc">{contract.business_description || ''}</div>

                  {/* 金色语义分割线 — 身份层 / 金额层 */}
                  <div className="divider-gold card-divider" />

                  <div className="amount-section">
                    {/* 总金额 — 视觉锚点 */}
                    <div className="amount-hero">
                      <span className="amount-hero-label">合同总额</span>
                      <span className="amount-hero-value">
                        {formatAmount(contract.total_amount, contract.currency)}
                      </span>
                    </div>

                    {/* 已付 / 未付 — 并排对比 */}
                    <div className="amount-split">
                      <div className="amount-split-item is-paid">
                        <div className="split-item-header">
                          <span className="split-dot paid" />
                          <span className="split-label">已付</span>
                        </div>
                        <div className="split-value paid">
                          {formatAmount(contract.paid_amount, contract.currency)}
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
                          <span className="split-dot unpaid" />
                          <span className="split-label">未付</span>
                        </div>
                        <div className={`split-value ${contract.remaining_amount > 0 ? 'unpaid' : 'paid'}`}>
                          {formatAmount(contract.remaining_amount, contract.currency)}
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

                  <div className="card-footer">
                    <div className="footer-item">
                      <span className="footer-label">签订日期</span>
                      <span className="footer-value">{formatDate(contract.signed_date)}</span>
                    </div>
                    <div className="footer-actions" onClick={(e) => e.stopPropagation()}>
                      <Popconfirm
                        title="确认删除"
                        description={`确定要删除合同 ${contract.contract_number} 吗？`}
                        onConfirm={() => handleDelete(contract.id)}
                        okText="删除"
                        cancelText="取消"
                        okButtonProps={{ danger: true }}
                      >
                        <DeleteOutlined className="action-icon delete" />
                      </Popconfirm>
                    </div>
                  </div>

                  <div className="card-decoration" />
                </div>
              )
            })}
          </div>

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

      <ContractUploadWizard
        open={uploadModalOpen}
        onClose={(created) => { setUploadModalOpen(false); if (created) loadContracts() }}
      />
    </div>
  )
}