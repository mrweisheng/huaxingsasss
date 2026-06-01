import { useState, useEffect, useCallback, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { Input, Button, Popconfirm, message, Empty } from 'antd'
import {
  PlusOutlined,
  SearchOutlined,
  TeamOutlined,
  UserOutlined,
  PhoneOutlined,
  MailOutlined,
  WechatOutlined,
  EnvironmentOutlined,
  DeleteOutlined,
  EyeOutlined,
} from '@ant-design/icons'
import { customerApi } from '@/services/customer'
import type { Customer } from '@/types'
import dayjs from 'dayjs'
import './CustomerList.css'

function formatDate(date: string | undefined): string {
  if (!date) return '--'
  return dayjs(date).format('YYYY-MM-DD')
}

function getAvatarLetter(name: string): string {
  return name.charAt(0).toUpperCase()
}

export default function CustomerList() {
  const navigate = useNavigate()
  const [customers, setCustomers] = useState<Customer[]>([])
  const [loading, setLoading] = useState(false)
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
    try {
      const response = await customerApi.getList({ page, per_page: 20, keyword: keyword || undefined }, controller.signal)
      setCustomers(response.items)
      setTotal(response.pagination.total)
    } catch (error: any) {
      if (error?.name === 'AbortError' || error?.code === 'ERR_CANCELED') return
      console.error(error)
    } finally {
      if (!controller.signal.aborted) {
        setLoading(false)
      }
    }
  }, [page, keyword])

  useEffect(() => {
    loadCustomers()
    return () => {
      abortControllerRef.current?.abort()
    }
  }, [loadCustomers])

  const handleSearch = (value: string) => {
    setKeyword(value)
    setPage(1)
  }

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
          <Input.Search
            placeholder="搜索客户名称/联系人/电话..."
            allowClear
            onSearch={handleSearch}
            style={{ width: 220 }}
            prefix={<SearchOutlined />}
          />
          <Button type="primary" icon={<PlusOutlined />} onClick={() => navigate('/customers/new')}>
            新增客户
          </Button>
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
                    <div className="card-name-row">
                      <div className="customer-name">{customer.name}</div>
                      <div className="card-avatar">{getAvatarLetter(customer.name)}</div>
                    </div>

                    {(customer.contact_person || customer.phone) && (
                      <div className="contact-section">
                        {customer.contact_person && (
                          <div className="contact-row">
                            <UserOutlined className="contact-icon" />
                            <span className="contact-label">联系人</span>
                            <span className="contact-value">{customer.contact_person}</span>
                          </div>
                        )}
                        {customer.phone && (
                          <div className="contact-row">
                            <PhoneOutlined className="contact-icon" />
                            <span className="contact-label">电话</span>
                            <span className="contact-value">{customer.phone}</span>
                          </div>
                        )}
                      </div>
                    )}

                    <div className="info-grid">
                      {customer.email && (
                        <div className="info-item">
                          <MailOutlined className="info-icon" />
                          <span className="info-text">{customer.email}</span>
                        </div>
                      )}
                      {customer.wechat_group_name && (
                        <div className="info-item">
                          <WechatOutlined className="info-icon" />
                          <span className="info-text">{customer.wechat_group_name}</span>
                        </div>
                      )}
                      {customer.address && (
                        <div className="info-item" style={{ gridColumn: '1 / -1' }}>
                          <EnvironmentOutlined className="info-icon" />
                          <span className="info-text">{customer.address}</span>
                        </div>
                      )}
                    </div>

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