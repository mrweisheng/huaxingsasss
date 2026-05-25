import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { Table, Button, Input, Space, Tag, Select, DatePicker } from 'antd'
import { PlusOutlined } from '@ant-design/icons'
import { contractApi } from '@/services/contract'
import type { Contract } from '@/types'
import dayjs from 'dayjs'

const { RangePicker } = DatePicker

const statusMap: Record<string, { color: string; text: string }> = {
  draft: { color: 'default', text: '草稿' },
  pending_review: { color: 'warning', text: '待审核' },
  active: { color: 'processing', text: '执行中' },
  completed: { color: 'success', text: '已完成' },
  cancelled: { color: 'error', text: '已取消' },
  disputed: { color: 'volcano', text: '争议' },
}

const currencySymbol: Record<string, string> = {
  CNY: '¥',
  HKD: 'HK$',
  USD: '$',
}

function formatAmount(amount: number, currency: string): string {
  const symbol = currencySymbol[currency] || '¥'
  return `${symbol}${amount.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

export default function ContractList() {
  const navigate = useNavigate()
  const [contracts, setContracts] = useState<Contract[]>([])
  const [loading, setLoading] = useState(false)
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [keyword, setKeyword] = useState('')
  const [statusFilter, setStatusFilter] = useState<string | undefined>(undefined)
  const [dateRange, setDateRange] = useState<[dayjs.Dayjs | null, dayjs.Dayjs | null] | null>(null)

  const loadContracts = useCallback(async () => {
    setLoading(true)
    try {
      const params: any = { page, per_page: 20, keyword: keyword || undefined }
      if (statusFilter) params.status = statusFilter
      if (dateRange && dateRange[0] && dateRange[1]) {
        params.date_from = dateRange[0].format('YYYY-MM-DD')
        params.date_to = dateRange[1].format('YYYY-MM-DD')
      }
      const response = await contractApi.getList(params)
      setContracts(response.items)
      setTotal(response.pagination.total)
    } catch (error) {
      console.error(error)
    } finally {
      setLoading(false)
    }
  }, [page, keyword, statusFilter, dateRange])

  useEffect(() => {
    loadContracts()
  }, [loadContracts])

  const handleSearch = (value: string) => {
    setKeyword(value)
    setPage(1)
  }

  const handleStatusChange = (value: string | undefined) => {
    setStatusFilter(value)
    setPage(1)
  }

  const handleDateChange = (dates: [dayjs.Dayjs | null, dayjs.Dayjs | null] | null) => {
    setDateRange(dates)
    setPage(1)
  }

  const columns = [
    { title: '合同编号', dataIndex: 'contract_number', key: 'contract_number', width: 180 },
    { title: '客户名称', dataIndex: 'customer_name', key: 'customer_name', render: (v: string) => v || '-' },
    { title: '合同标题', dataIndex: 'title', key: 'title', ellipsis: true },
    { title: '币种', dataIndex: 'currency', key: 'currency', width: 70 },
    {
      title: '总金额',
      dataIndex: 'total_amount',
      key: 'total_amount',
      width: 130,
      render: (v: number, record: Contract) => formatAmount(v, record.currency),
    },
    {
      title: '已付金额',
      dataIndex: 'paid_amount',
      key: 'paid_amount',
      width: 130,
      render: (v: number, record: Contract) => formatAmount(v, record.currency),
    },
    {
      title: '剩余尾款',
      dataIndex: 'remaining_amount',
      key: 'remaining_amount',
      width: 130,
      render: (v: number, record: Contract) => (
        <span style={{ color: v > 0 ? '#ff4d4f' : '#52c41a' }}>
          {formatAmount(v, record.currency)}
        </span>
      ),
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 90,
      render: (status: string) => {
        const { color, text } = statusMap[status] || { color: 'default', text: status }
        return <Tag color={color}>{text}</Tag>
      },
    },
    {
      title: '签订日期',
      dataIndex: 'signed_date',
      key: 'signed_date',
      width: 110,
      render: (v: string) => v || '-',
    },
    {
      title: '操作',
      key: 'action',
      width: 90,
      render: (_: any, record: Contract) => (
        <Button type="link" size="small" onClick={() => navigate(`/contracts/${record.id}`)}>
          详情
        </Button>
      ),
    },
  ]

  return (
    <div>
      <Space wrap style={{ marginBottom: 16 }}>
        <Input.Search
          placeholder="搜索合同编号/标题..."
          allowClear
          onSearch={handleSearch}
          style={{ width: 260 }}
        />
        <Select
          placeholder="合同状态"
          allowClear
          style={{ width: 130 }}
          value={statusFilter}
          onChange={handleStatusChange}
          options={[
            { label: '草稿', value: 'draft' },
            { label: '待审核', value: 'pending_review' },
            { label: '执行中', value: 'active' },
            { label: '已完成', value: 'completed' },
            { label: '已取消', value: 'cancelled' },
          ]}
        />
        <RangePicker
          placeholder={['签订开始', '签订结束']}
          onChange={handleDateChange}
          value={dateRange as any}
        />
        <Button type="primary" icon={<PlusOutlined />} onClick={() => navigate('/contracts/upload')}>
          上传合同
        </Button>
      </Space>
      <Table
        columns={columns}
        dataSource={contracts}
        loading={loading}
        rowKey="id"
        scroll={{ x: 1200 }}
        pagination={{ current: page, pageSize: 20, total, onChange: setPage, showTotal: (t) => `共 ${t} 条` }}
      />
    </div>
  )
}
