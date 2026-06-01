import { useState, useEffect, useCallback, useRef } from 'react'
import { Table, Button, Select, Empty, Popconfirm, message, Image, Tabs, Tag } from 'antd'
import { FilterOutlined, DollarOutlined, DeleteOutlined, EyeOutlined } from '@ant-design/icons'
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

const statusMap: Record<string, { color: string; text: string }> = {
  pending: { color: '#8c8c8c', text: '待支付' },
  partial: { color: '#d97706', text: '部分支付' },
  paid: { color: '#0d9488', text: '已支付' },
  overdue: { color: '#dc2626', text: '逾期' },
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
  const [statusFilter, setStatusFilter] = useState<string | undefined>(undefined)
  const [typeFilter, setTypeFilter] = useState<string | undefined>(undefined)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const [previewLoading, setPreviewLoading] = useState(false)
  const abortControllerRef = useRef<AbortController | null>(null)
  const user = useAuthStore((s) => s.user)
  const role = user?.role || ''

  const defaultTab = role === 'expense' ? 'expense' : role === 'income' ? 'income' : 'all'
  const [activeTab, setActiveTab] = useState(defaultTab)

  const loadPayments = useCallback(async () => {
    abortControllerRef.current?.abort()
    const controller = new AbortController()
    abortControllerRef.current = controller

    setLoading(true)
    try {
      const params: PaymentListParams = { page, per_page: 20 }
      if (statusFilter) params.status = statusFilter
      if (typeFilter) params.type = typeFilter
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
  }, [page, statusFilter, typeFilter])

  useEffect(() => {
    loadPayments()
    return () => {
      abortControllerRef.current?.abort()
    }
  }, [loadPayments])

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

  const columns = [
    {
      title: '类型',
      dataIndex: 'type',
      key: 'type',
      width: 70,
      align: 'center' as const,
      render: (v: string) => (
        <Tag color={v === 'income' ? 'green' : 'red'}>
          {v === 'income' ? '收入' : '支出'}
        </Tag>
      ),
    },
    {
      title: '合同编号',
      dataIndex: 'contract_number',
      key: 'contract_number',
      width: 140,
      minWidth: 100,
      ellipsis: true,
      render: (v: string) => v || '-',
    },
    {
      title: '客户名称',
      dataIndex: 'customer_name',
      key: 'customer_name',
      minWidth: 80,
      ellipsis: true,
      render: (v: string) => v || '-',
    },
    {
      title: '收款方',
      dataIndex: 'payee_name',
      key: 'payee_name',
      width: 120,
      ellipsis: true,
      render: (v: string) => v || '-',
    },
    {
      title: '期数',
      dataIndex: 'installment_number',
      key: 'installment_number',
      width: 60,
      minWidth: 50,
      align: 'center' as const,
    },
    {
      title: '币种',
      dataIndex: 'currency',
      key: 'currency',
      width: 60,
      minWidth: 50,
      align: 'center' as const,
    },
    {
      title: '金额',
      dataIndex: 'paid_amount',
      key: 'paid_amount',
      width: 100,
      minWidth: 80,
      align: 'right' as const,
      render: (v: number, r: Payment) => <span className="num-mono">{fmt(v, r.currency)}</span>,
    },
    {
      title: '折算CNY',
      dataIndex: 'paid_amount_in_cny',
      key: 'paid_amount_in_cny',
      width: 100,
      minWidth: 80,
      align: 'right' as const,
      render: (v: number) => <span className="num-mono">{fmt(v, 'CNY')}</span>,
    },
    {
      title: '付款日期',
      dataIndex: 'paid_date',
      key: 'paid_date',
      width: 100,
      minWidth: 80,
      ellipsis: true,
      render: (v: string) => v || '-',
    },
    {
      title: '方式',
      dataIndex: 'payment_method',
      key: 'payment_method',
      width: 80,
      minWidth: 60,
      render: (v: string) => methodMap[v] || v || '-',
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 80,
      minWidth: 70,
      render: (s: string) => {
        const { color, text } = statusMap[s] || { color: '#8c8c8c', text: s }
        return (
          <span
            style={{
              color,
              padding: '2px 8px',
              borderRadius: 4,
              fontSize: 11,
              fontWeight: 600,
              background: s === 'paid' ? 'var(--color-success-bg)' : s === 'overdue' ? 'var(--color-danger-bg)' : 'var(--bg-subtle)',
            }}
          >
            {text}
          </span>
        )
      },
    },
    {
      title: '备注',
      dataIndex: 'notes',
      key: 'notes',
      minWidth: 100,
      ellipsis: true,
      render: (v: string) => v || '-',
    },
    {
      title: '操作',
      key: 'action',
      width: 100,
      minWidth: 80,
      align: 'center' as const,
      render: (_: unknown, record: Payment) => (
        <>
          {record.receipt_image_path ? (
            <Button
              type="link"
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
            >
              凭证
            </Button>
          ) : (
            <span style={{ color: '#bbb', fontSize: 12 }}>无凭证</span>
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
              <Button type="text" danger size="small" icon={<DeleteOutlined />} />
            </Popconfirm>
          )}
        </>
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
          <Select
            placeholder="状态"
            allowClear
            style={{ width: 110 }}
            value={statusFilter}
            onChange={handleStatusChange}
            suffixIcon={<FilterOutlined />}
            options={[
              { label: '待支付', value: 'pending' },
              { label: '部分支付', value: 'partial' },
              { label: '已支付', value: 'paid' },
              { label: '逾期', value: 'overdue' },
            ]}
          />
        </div>
      </div>

      {visibleTabs.length > 1 && (
        <Tabs activeKey={activeTab} onChange={handleTabChange} items={visibleTabs} style={{ marginBottom: 16 }} />
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
