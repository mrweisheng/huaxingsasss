import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { Table, Button, Input, Space } from 'antd'
import { PlusOutlined } from '@ant-design/icons'
import { customerApi } from '@/services/customer'
import type { Customer } from '@/types'

export default function CustomerList() {
  const navigate = useNavigate()
  const [customers, setCustomers] = useState<Customer[]>([])
  const [loading, setLoading] = useState(false)
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [keyword, setKeyword] = useState('')

  const loadCustomers = useCallback(async () => {
    setLoading(true)
    try {
      const response = await customerApi.getList({ page, per_page: 20, keyword })
      setCustomers(response.items)
      setTotal(response.pagination.total)
    } catch (error) {
      console.error(error)
    } finally {
      setLoading(false)
    }
  }, [page, keyword])

  useEffect(() => {
    loadCustomers()
  }, [loadCustomers])

  const handleSearch = (value: string) => {
    setKeyword(value)
    setPage(1)
  }

  const columns = [
    { title: '客户名称', dataIndex: 'name', key: 'name' },
    { title: '联系人', dataIndex: 'contact_person', key: 'contact_person' },
    { title: '电话', dataIndex: 'phone', key: 'phone' },
    { title: '邮箱', dataIndex: 'email', key: 'email' },
    { title: '微信群', dataIndex: 'wechat_group_name', key: 'wechat_group_name' },
    {
      title: '操作',
      key: 'action',
      width: 90,
      render: (_: any, record: Customer) => (
        <Button type="link" size="small" onClick={() => navigate(`/customers/${record.id}`)}>
          详情
        </Button>
      ),
    },
  ]

  return (
    <div>
      <Space style={{ marginBottom: 16 }}>
        <Input.Search
          placeholder="搜索客户..."
          allowClear
          onSearch={handleSearch}
          style={{ width: 300 }}
        />
        <Button type="primary" icon={<PlusOutlined />} onClick={() => navigate('/customers/new')}>
          新增客户
        </Button>
      </Space>
      <Table
        columns={columns}
        dataSource={customers}
        loading={loading}
        rowKey="id"
        pagination={{
          current: page,
          pageSize: 20,
          total,
          onChange: setPage,
          showTotal: (t) => `共 ${t} 条`,
        }}
      />
    </div>
  )
}
