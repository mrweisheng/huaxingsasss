import { useState, useEffect, useCallback, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { Input, Button, Popconfirm, message, Empty } from 'antd'
import {
  SearchOutlined,
  TeamOutlined,
  UserOutlined,
  PhoneOutlined,
  DeleteOutlined,
  EyeOutlined,
  FileTextOutlined,
} from '@ant-design/icons'
import { useDebounce } from '@/hooks/useDebounce'
import { customerApi } from '@/services/customer'
import { contractApi } from '@/services/contract'
import type { Customer, Contract } from '@/types'
import dayjs from 'dayjs'
import './CustomerList.css'

const STATUS_CONFIG: Record<string, { label: string; dotClass: string }> = {
  active: { label: '执行中', dotClass: 'status-dot-active' },
  completed: { label: '已完成', dotClass: 'status-dot-completed' },
  draft: { label: '草稿', dotClass: 'status-dot-draft' },
}

const BUSINESS_TYPE_MAP: Record<string, string> = {
  '买港车': '买港车',
  '办两地牌': '办两地牌',
}

function formatDate(date: string | undefined): string {
  if (!date) return '--'
  return dayjs(date).format('YYYY-MM-DD')
}

function getAvatarLetter(name: string): string {
  return name.charAt(0).toUpperCase()
}

function formatAmount(amount: number, currency: string): string {
  if (currency === 'CNY') return `¥${amount.toLocaleString('zh-CN', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`
  return `${currency} ${amount.toLocaleString('zh-CN', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`
}

function getProgressPercent(paid: number, total: number): number {
  if (total <= 0) return 0
  return Math.min(Math.round((paid / total) * 100), 100)
}

export default function CustomerList() {
  const navigate = useNavigate()
  const [customers, setCustomers] = useState<Customer[]>([])
  const [contractsByCustomer, setContractsByCustomer] = useState<Record<number, Contract[]>>({})
  const [loading, setLoading] = useState(false)
  const [contractsLoading, setContractsLoading] = useState(false)
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [keyword, setKeyword] = useState('')
  const [hoveredCard, setHoveredCard] = useState<number | null>(null)
  const abortControllerRef = useRef<AbortController | null>(null)

  const loadCustomers = useCallback(async () => {
    abortControllerRef.current?.abort()
    const controller = new AbortController()
    abortControllerRef.current = controller

    setLoading(true)
    setContractsByCustomer({})
    try {
      const response = await customerApi.getList({ page, per_page: 20, keyword: keyword || undefined }, controller.signal)
      if (controller.signal.aborted) return
      setCustomers(response.items)
      setTotal(response.pagination.total)

      // 批量加载这批客户的所有合同
      const customerIds = response.items.map(c => c.id)
      if (customerIds.length > 0) {
        setContractsLoading(true)
        try {
          const contractsRes = await contractApi.getList({
            customer_ids: customerIds.join(','),
            per_page: 500,
          }, controller.signal)
          if (!controller.signal.aborted) {
            const grouped: Record<number, Contract[]> = {}
            for (const c of contractsRes.items) {
              if (!grouped[c.customer_id]) grouped[c.customer_id] = []
              grouped[c.customer_id].push(c)
            }
            setContractsByCustomer(grouped)
          }
        } catch (err: any) {
          if (err?.name === 'AbortError' || err?.code === 'ERR_CANCELED') return
          console.error('加载合同失败:', err)
        } finally {
          if (!controller.signal.aborted) setContractsLoading(false)
        }
      }
    } catch (error: any) {
      if (error?.name === 'AbortError' || error?.code === 'ERR_CANCELED') return
      console.error(error)
    } finally {
      if (!controller.signal.aborted) setLoading(false)
    }
  }, [page, keyword])

  useEffect(() => {
    loadCustomers()
    return () => {
      abortControllerRef.current?.abort()
    }
  }, [loadCustomers])

  const handleSearch = useDebounce((value: string) => {
    setKeyword(value)
    setPage(1)
  }, 400)

  const handleDelete = async (id: number, _name: string) => {
    try {
      await customerApi.delete(id)
      message.success('删除成功')
      loadCustomers()
    } catch (error: any) {
      message.error(error.response?.data?.detail || '删除失败')
    }
  }

  const totalPages = Math.ceil(total / 20)

  return (
    <div className="customer-list-container">
      <div className="page-topbar">
        <div className="page-topbar-left">
          <div className="page-title-wrap">
            <div className="page-title-icon">
              <TeamOutlined />
            </div>
            <span className="page-title-text">客户管理</span>
            <span className="page-title-count">{total} 个客户</span>
          </div>
        </div>
        <div className="page-topbar-right">
          <Input
            placeholder="搜索客户名称/联系人/电话..."
            allowClear
            onChange={e => handleSearch(e.target.value)}
            style={{ width: 220 }}
            prefix={<SearchOutlined />}
          />
        </div>
      </div>

      {loading && customers.length === 0 ? (
        <div style={{ padding: '60px 0', textAlign: 'center' }}>
          <div style={{ fontSize: 14, color: '#94a3b8' }}>加载中...</div>
        </div>
      ) : customers.length === 0 ? (
        <Empty description="暂无客户数据" className="empty-state" />
      ) : (
        <>
          <div className="customer-grid">
            {customers.map((customer, index) => {
              const isHovered = hoveredCard === customer.id
              const customerContracts = contractsByCustomer[customer.id] || []
              const displayContracts = customerContracts.slice(0, 2)
              const moreCount = customerContracts.length - 2
              const showContractSection = customerContracts.length > 0

              return (
                <div
                  key={customer.id}
                  className={`customer-card ${isHovered ? 'hovered' : ''}`}
                  onClick={() => navigate(`/customers/${customer.id}`)}
                  onMouseEnter={() => setHoveredCard(customer.id)}
                  onMouseLeave={() => setHoveredCard(null)}
                  style={{ animationDelay: `${index * 50}ms` }}
                >
                  <div className="card-accent" />

                  <div className="card-body">
                    {/* 客户名称行 */}
                    <div className="card-name-row">
                      <div className="customer-name" title={customer.name}>{customer.name}</div>
                      <div className="card-avatar">{getAvatarLetter(customer.name)}</div>
                    </div>

                    {/* 联系人信息：紧凑一行 */}
                    <div className="contact-inline">
                      {customer.contact_person && (
                        <span className="contact-inline-item">
                          <UserOutlined />
                          <span>{customer.contact_person}</span>
                        </span>
                      )}
                      {customer.phone && (
                        <span className="contact-inline-item">
                          <PhoneOutlined />
                          <span>{customer.phone}</span>
                        </span>
                      )}
                      {!customer.contact_person && !customer.phone && (
                        <span className="contact-inline-empty">暂无联系方式</span>
                      )}
                    </div>

                    {/* 关联合同区域 */}
                    {contractsLoading && !showContractSection ? (
                      <div className="contracts-skeleton">
                        <div className="skeleton-line" />
                        <div className="skeleton-line short" />
                      </div>
                    ) : showContractSection ? (
                      <div className="contracts-section">
                        <div className="contracts-header">
                          <FileTextOutlined className="contracts-header-icon" />
                          <span className="contracts-header-label">关联合同</span>
                          <span className="contracts-header-count">{customerContracts.length} 份</span>
                        </div>
                        <div className="contracts-list">
                          {displayContracts.map(contract => {
                            const statusCfg = STATUS_CONFIG[contract.status] || STATUS_CONFIG.active
                            const progressPercent = getProgressPercent(contract.paid_amount, contract.total_amount)
                            const isCompleted = progressPercent >= 100 || contract.status === 'completed'

                            return (
                              <div
                                key={contract.id}
                                className="contract-row"
                                onClick={(e) => {
                                  e.stopPropagation()
                                  navigate(`/contracts/${contract.id}`)
                                }}
                                title="点击查看合同详情"
                              >
                                <div className="contract-row-top">
                                  <span className="contract-number">{contract.contract_number}</span>
                                  <div className="contract-row-tags">
                                    {contract.business_type && (
                                      <span className="business-type-tag">{BUSINESS_TYPE_MAP[contract.business_type] || contract.business_type}</span>
                                    )}
                                    <span className={`status-dot ${statusCfg.dotClass}`} />
                                  </div>
                                </div>
                                <div className="contract-row-bottom">
                                  <span className="contract-amount">{formatAmount(contract.total_amount, contract.currency)}</span>
                                  <div className="contract-progress">
                                    <div className="progress-track">
                                      <div
                                        className={`progress-fill ${isCompleted ? 'fill-completed' : 'fill-active'}`}
                                        style={{ width: `${progressPercent}%` }}
                                      />
                                    </div>
                                    <span className="progress-text">
                                      {isCompleted ? '已结清' : `已付${progressPercent}%`}
                                    </span>
                                  </div>
                                </div>
                              </div>
                            )
                          })}
                          {moreCount > 0 && (
                            <div className="contracts-more">
                              还有 {moreCount} 份合同
                            </div>
                          )}
                        </div>
                      </div>
                    ) : (
                      <div className="contracts-empty">
                        <FileTextOutlined style={{ fontSize: 18, opacity: 0.25 }} />
                        <span>暂无关联合同</span>
                      </div>
                    )}

                    {/* 底部 */}
                    <div className="card-footer">
                      <div className="footer-date">
                        <span className="footer-label">创建日期</span>
                        <span className="footer-value">{formatDate(customer.created_at)}</span>
                      </div>
                      <div className="footer-actions" onClick={(e) => e.stopPropagation()}>
                        <EyeOutlined
                          className="action-icon detail"
                          onClick={(e) => {
                            e.stopPropagation()
                            navigate(`/customers/${customer.id}`)
                          }}
                        />
                        <Popconfirm
                          title="确认删除"
                          description={`确定要删除客户「${customer.name}」吗？`}
                          onConfirm={() => handleDelete(customer.id, customer.name)}
                          okText="删除"
                          cancelText="取消"
                          okButtonProps={{ danger: true }}
                        >
                          <DeleteOutlined className="action-icon delete" />
                        </Popconfirm>
                      </div>
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
    </div>
  )
}
