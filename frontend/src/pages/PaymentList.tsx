import { useState, useEffect, useCallback, useRef } from 'react'
import { Table, Button, Select, Empty, Popconfirm, message } from 'antd'
import { PlusOutlined, FilterOutlined, DollarOutlined, DeleteOutlined } from '@ant-design/icons'
import { paymentApi, type PaymentListParams } from '@/services/payment'
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
  partial: { color: '#fa8c16', text: '部分支付' },
  paid: { color: '#52c41a', text: '已支付' },
  pending_voucher: { color: '#1890ff', text: '待凭证' },
  overdue: { color: '#ff4d4f', text: '逾期' },
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
  const abortControllerRef = useRef<AbortController | null>(null)

  const loadPayments = useCallback(async () => {
    abortControllerRef.current?.abort()
    const controller = new AbortController()
    abortControllerRef.current = controller

    setLoading(true)
    try {
      const params: PaymentListParams = { page, per_page: 20 }
      if (statusFilter) params.status = statusFilter
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
  }, [page, statusFilter])

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
      title: '应付金额',
      dataIndex: 'amount',
      key: 'amount',
      width: 100,
      minWidth: 80,
      align: 'right' as const,
      render: (v: number, r: Payment) => fmt(v, r.currency),
    },
    {
      title: '实付金额',
      dataIndex: 'paid_amount',
      key: 'paid_amount',
      width: 100,
      minWidth: 80,
      align: 'right' as const,
      render: (v: number, r: Payment) => fmt(v, r.currency),
    },
    {
      title: '折算CNY',
      dataIndex: 'paid_amount_in_cny',
      key: 'paid_amount_in_cny',
      width: 100,
      minWidth: 80,
      align: 'right' as const,
      render: (v: number) => fmt(v, 'CNY'),
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
        return <span style={{ color, padding: '2px 8px', borderRadius: 4, fontSize: 11, fontWeight: 600 }}>{text}</span>
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
      width: 70,
      minWidth: 60,
      align: 'center' as const,
      render: (_: unknown, record: Payment) => (
        <Popconfirm
          title="确定删除此付款记录？"
          description="删除后将无法恢复，合同已付金额将同步扣减"
          onConfirm={() => handleDelete(record.id)}
          okText="删除"
          cancelText="取消"
          okButtonProps={{ danger: true }}
        >
          <Button type="text" danger size="small" icon={<DeleteOutlined />} />
        </Popconfirm>
      ),
    },
  ]

  return (
    <div className="payment-list-container">
      <div className="top-bar">
        <div className="top-bar-left">
          <h2 className="page-title">
            <DollarOutlined className="title-icon" />
            <span className="title-text">付款管理</span>
            <span className="payment-count">{total} 条记录</span>
          </h2>
        </div>
        <div className="top-bar-right">
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
              { label: '待凭证', value: 'pending_voucher' },
              { label: '逾期', value: 'overdue' },
            ]}
          />
          <Button type="primary" icon={<PlusOutlined />}>
            新增
          </Button>
        </div>
      </div>

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
    </div>
  )
}