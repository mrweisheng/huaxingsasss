import { useState, useEffect, useCallback } from 'react'
import { Table, Card, Tag, Input, Space, Select } from 'antd'
import { paymentApi } from '@/services/payment'
import type { Payment } from '@/types'

const currencySymbol: Record<string, string> = { CNY: '¥', HKD: 'HK$', USD: '$' }

function fmt(amount: number | undefined | null, currency: string): string {
  if (amount === undefined || amount === null) return '-'
  const symbol = currencySymbol[currency] || '¥'
  return `${symbol}${amount.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

const statusMap: Record<string, { color: string; text: string }> = {
  pending: { color: 'default', text: '待支付' },
  partial: { color: 'warning', text: '部分支付' },
  paid: { color: 'success', text: '已支付' },
  overdue: { color: 'error', text: '逾期' },
  cancelled: { color: 'default', text: '已取消' },
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

  const loadPayments = useCallback(async () => {
    setLoading(true)
    try {
      const params: any = { page, per_page: 20 }
      if (statusFilter) params.status = statusFilter
      const response = await paymentApi.getList(params)
      setPayments(response.items)
      setTotal(response.pagination.total)
    } catch (error) {
      console.error(error)
    } finally {
      setLoading(false)
    }
  }, [page, statusFilter])

  useEffect(() => {
    loadPayments()
  }, [loadPayments])

  const handleStatusChange = (value: string | undefined) => {
    setStatusFilter(value)
    setPage(1)
  }

  const columns = [
    {
      title: '合同编号',
      dataIndex: 'contract_number',
      key: 'contract_number',
      width: 170,
      render: (v: string) => v || '-',
    },
    {
      title: '客户名称',
      dataIndex: 'customer_name',
      key: 'customer_name',
      render: (v: string) => v || '-',
    },
    {
      title: '期数',
      dataIndex: 'installment_number',
      key: 'installment_number',
      width: 60,
    },
    {
      title: '币种',
      dataIndex: 'currency',
      key: 'currency',
      width: 60,
    },
    {
      title: '应付金额',
      dataIndex: 'amount',
      key: 'amount',
      width: 120,
      render: (v: number, r: Payment) => fmt(v, r.currency),
    },
    {
      title: '实付金额',
      dataIndex: 'paid_amount',
      key: 'paid_amount',
      width: 120,
      render: (v: number, r: Payment) => fmt(v, r.currency),
    },
    {
      title: '折算CNY',
      dataIndex: 'paid_amount_in_cny',
      key: 'paid_amount_in_cny',
      width: 120,
      render: (v: number) => fmt(v, 'CNY'),
    },
    {
      title: '付款日期',
      dataIndex: 'paid_date',
      key: 'paid_date',
      width: 110,
      render: (v: string) => v || '-',
    },
    {
      title: '方式',
      dataIndex: 'payment_method',
      key: 'payment_method',
      width: 80,
      render: (v: string) => methodMap[v] || v || '-',
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 80,
      render: (s: string) => {
        const { color, text } = statusMap[s] || { color: 'default', text: s }
        return <Tag color={color}>{text}</Tag>
      },
    },
    {
      title: '备注',
      dataIndex: 'notes',
      key: 'notes',
      ellipsis: true,
      render: (v: string) => v || '-',
    },
  ]

  return (
    <Card title="付款管理">
      <Space style={{ marginBottom: 16 }}>
        <Select
          placeholder="付款状态"
          allowClear
          style={{ width: 130 }}
          value={statusFilter}
          onChange={handleStatusChange}
          options={[
            { label: '待支付', value: 'pending' },
            { label: '部分支付', value: 'partial' },
            { label: '已支付', value: 'paid' },
            { label: '逾期', value: 'overdue' },
          ]}
        />
      </Space>
      <Table
        columns={columns}
        dataSource={payments}
        loading={loading}
        rowKey="id"
        scroll={{ x: 1100 }}
        pagination={{
          current: page,
          pageSize: 20,
          total,
          onChange: setPage,
          showTotal: (t) => `共 ${t} 条`,
        }}
      />
    </Card>
  )
}
