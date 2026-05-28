import { useState, useEffect, useCallback, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { Table, Button, Input, Space, Popconfirm, message } from 'antd'
import { PlusOutlined, DeleteOutlined } from '@ant-design/icons'
import { customerApi } from '@/services/customer'
import type { Customer } from '@/types'

export default function CustomerList() {
  const navigate = useNavigate()
  const [customers, setCustomers] = useState<Customer[]>([])
  const [loading, setLoading] = useState(false)
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [keyword, setKeyword] = useState('')
  const abortControllerRef = useRef<AbortController | null>(null)

  const loadCustomers = useCallback(async () => {
    // Cancel previous request
    abortControllerRef.current?.abort()
    const controller = new AbortController()
    abortControllerRef.current = controller

    setLoading(true)
    try {
      const response = await customerApi.getList({ page, per_page: 20, keyword }, controller.signal)
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

  const handleDelete = async (id: number) => {
    try {
      await customerApi.delete(id)
      message.success('删除成功')
      loadCustomers()
    } catch (error: any) {
      message.error(error.response?.data?.detail || '删除失败')
    }
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
      width: 130,
      render: (_: any, record: Customer) => (
        <Space size="small">
          <Button type="link" size="small" onClick={() => navigate(`/customers/${record.id}`)}>
            详情
          </Button>
          <Popconfirm
            title="确认删除"
            description={`确定要删除客户「${record.name}」吗？`}
            onConfirm={() => handleDelete(record.id)}
            okText="删除"
            cancelText="取消"
            okButtonProps={{ danger: true }}
          >
            <Button type="link" danger size="small" icon={<DeleteOutlined />}>
              删除
            </Button>
          </Popconfirm>
        </Space>
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
