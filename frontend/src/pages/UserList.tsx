import { useState, useEffect, useCallback, useRef } from 'react'
import {
  Table,
  Button,
  Input,
  Modal,
  Form,
  Select,
  Tag,
  Badge,
  Popconfirm,
  message,
  Space,
  Alert,
  Typography,
  Grid,
} from 'antd'
import {
  PlusOutlined,
  EditOutlined,
  LockOutlined,
  SearchOutlined,
} from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import dayjs from 'dayjs'
import { userApi } from '@/services/user'
import type { CreateUserData, UpdateUserData } from '@/services/user'
import { useAuthStore } from '@/store/useAuthStore'
import type { User } from '@/types'

const { Text } = Typography

const ROLE_OPTIONS = [
  { value: 'admin', label: '管理员' },
  { value: 'income', label: '收入专员' },
  { value: 'expense', label: '支出专员' },
]

const ROLE_TAG_COLOR: Record<string, string> = {
  admin: 'red',
  income: 'blue',
  expense: 'green',
}

const ROLE_LABEL: Record<string, string> = {
  admin: '管理员',
  income: '收入专员',
  expense: '支出专员',
}

export default function UserList() {
  const currentUser = useAuthStore((s) => s.user)
  const isMobile = !(Grid.useBreakpoint().md ?? true)
  const [users, setUsers] = useState<User[]>([])
  const [loading, setLoading] = useState(false)
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [keyword, setKeyword] = useState('')
  const abortControllerRef = useRef<AbortController | null>(null)

  // Modal state
  const [createModalOpen, setCreateModalOpen] = useState(false)
  const [editModalOpen, setEditModalOpen] = useState(false)
  const [editingUser, setEditingUser] = useState<User | null>(null)
  const [submitLoading, setSubmitLoading] = useState(false)

  const [createForm] = Form.useForm()
  const [editForm] = Form.useForm()

  const loadUsers = useCallback(async () => {
    abortControllerRef.current?.abort()
    const controller = new AbortController()
    abortControllerRef.current = controller

    setLoading(true)
    try {
      const res = await userApi.getList(
        { page, per_page: 20, keyword: keyword || undefined },
        controller.signal,
      )
      setUsers(res.items)
      setTotal(res.pagination.total)
    } catch (error: any) {
      if (error.name !== 'AbortError' && error.code !== 'ERR_CANCELED') {
        message.error(error.response?.data?.detail || '加载用户列表失败')
      }
    } finally {
      setLoading(false)
    }
  }, [page, keyword])

  useEffect(() => {
    loadUsers()
    return () => {
      abortControllerRef.current?.abort()
    }
  }, [loadUsers])

  const handleSearch = (value: string) => {
    setKeyword(value)
    setPage(1)
  }

  // Create user
  const handleCreate = async () => {
    try {
      const values = await createForm.validateFields()
      setSubmitLoading(true)
      const data: CreateUserData = {
        username: values.username,
        full_name: values.full_name,
        role: values.role || 'income',
        department: values.department,
        email: values.email,
      }
      await userApi.create(data)
      message.success('用户创建成功，默认密码为 123456')
      setCreateModalOpen(false)
      createForm.resetFields()
      loadUsers()
    } catch (error: any) {
      if (error.response?.data?.detail) {
        message.error(error.response.data.detail)
      } else if (error.errorFields) {
        // Form validation error, do nothing
      } else {
        message.error('创建用户失败')
      }
    } finally {
      setSubmitLoading(false)
    }
  }

  // Edit user
  const openEdit = (user: User) => {
    setEditingUser(user)
    editForm.setFieldsValue({
      full_name: user.full_name,
      email: user.email,
      department: user.department,
      role: user.role,
    })
    setEditModalOpen(true)
  }

  const handleEdit = async () => {
    if (!editingUser) return
    try {
      const values = await editForm.validateFields()
      setSubmitLoading(true)
      const data: UpdateUserData = {
        full_name: values.full_name,
        email: values.email,
        department: values.department,
        role: values.role,
      }
      await userApi.update(editingUser.id, data)
      message.success('用户信息已更新')
      setEditModalOpen(false)
      setEditingUser(null)
      loadUsers()
    } catch (error: any) {
      if (error.response?.data?.detail) {
        message.error(error.response.data.detail)
      } else if (error.errorFields) {
        // Form validation error
      } else {
        message.error('更新用户失败')
      }
    } finally {
      setSubmitLoading(false)
    }
  }

  // Toggle active
  const handleToggleActive = async (user: User) => {
    try {
      await userApi.toggleActive(user.id)
      message.success(user.is_active ? '已禁用用户' : '已启用用户')
      loadUsers()
    } catch (error: any) {
      message.error(error.response?.data?.detail || '操作失败')
    }
  }

  // Reset password
  const handleResetPassword = async (user: User) => {
    try {
      await userApi.resetPassword(user.id)
      message.success('密码已重置为 123456')
    } catch (error: any) {
      message.error(error.response?.data?.detail || '重置密码失败')
    }
  }

  const columns: ColumnsType<User> = [
    {
      title: '用户名',
      dataIndex: 'username',
      width: 120,
    },
    {
      title: '姓名',
      dataIndex: 'full_name',
      width: 120,
      render: (val: string) => val || '-',
    },
    {
      title: '角色',
      dataIndex: 'role',
      width: 100,
      responsive: ['md'],
      render: (role: string) => (
        <Tag color={ROLE_TAG_COLOR[role] || 'default'}>
          {ROLE_LABEL[role] || role}
        </Tag>
      ),
    },
    {
      title: '部门',
      dataIndex: 'department',
      width: 100,
      responsive: ['lg'],
      render: (val: string) => val || '-',
    },
    {
      title: '邮箱',
      dataIndex: 'email',
      width: 180,
      responsive: ['lg'],
      render: (val: string) => val || '-',
    },
    {
      title: '状态',
      dataIndex: 'is_active',
      width: 80,
      render: (active: boolean) => (
        <Badge
          status={active ? 'success' : 'error'}
          text={active ? '启用' : '禁用'}
        />
      ),
    },
    {
      title: '最后登录',
      dataIndex: 'last_login_at',
      width: 160,
      responsive: ['md'],
      render: (val: string) => val ? dayjs(val).format('YYYY-MM-DD HH:mm') : '从未登录',
    },
    {
      title: '操作',
      width: isMobile ? 100 : 220,
      render: (_: unknown, record: User) => {
        const isSelf = record.id === currentUser?.id
        return (
          <Space size="small">
            <Button
              type="link"
              size="small"
              icon={<EditOutlined />}
              onClick={() => openEdit(record)}
            >
              {isMobile ? null : '编辑'}
            </Button>
            {!isSelf && (
              <Popconfirm
                title={record.is_active ? '确认禁用该用户？' : '确认启用该用户？'}
                onConfirm={() => handleToggleActive(record)}
                okText="确认"
                cancelText="取消"
              >
                <Button type="link" size="small" danger={record.is_active}>
                  {record.is_active ? '禁用' : '启用'}
                </Button>
              </Popconfirm>
            )}
            <Popconfirm
              title="确认重置密码？"
              description="密码将被重置为默认密码 123456"
              onConfirm={() => handleResetPassword(record)}
              okText="确认"
              cancelText="取消"
            >
              <Button type="link" size="small" icon={<LockOutlined />}>
                {isMobile ? null : '重置密码'}
              </Button>
            </Popconfirm>
          </Space>
        )
      },
    },
  ]

  return (
    <div className="page-container" style={isMobile ? { padding: 12 } : undefined}>
      {/* Top bar */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: 20,
          flexDirection: isMobile ? 'column' : 'row',
          gap: isMobile ? 12 : 0,
        }}
      >
        <Space>
          <Text strong style={{ fontSize: 18 }}>
            用户管理
          </Text>
          <Tag>{total} 人</Tag>
        </Space>
        <Space style={isMobile ? { width: '100%' } : undefined}>
          <Input.Search
            placeholder="搜索用户名、姓名、邮箱、部门"
            allowClear
            onSearch={handleSearch}
            style={isMobile ? { width: '100%' } : { width: 280 }}
            prefix={<SearchOutlined />}
          />
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => {
              createForm.resetFields()
              setCreateModalOpen(true)
            }}
          >
            新建用户
          </Button>
        </Space>
      </div>

      {/* Table */}
      <Table<User>
        columns={columns}
        dataSource={users}
        rowKey="id"
        loading={loading}
        pagination={{
          current: page,
          pageSize: 20,
          total,
          onChange: (p) => setPage(p),
          showTotal: (t) => `共 ${t} 条`,
          showSizeChanger: false,
        }}
        scroll={{ x: 1100 }}
      />

      {/* Create Modal */}
      <Modal
        title="新建用户"
        open={createModalOpen}
        onOk={handleCreate}
        onCancel={() => setCreateModalOpen(false)}
        confirmLoading={submitLoading}
        destroyOnClose
        okText="创建"
        cancelText="取消"
      >
        <Alert
          message="默认密码为 123456，用户登录后可自行修改"
          type="info"
          showIcon
          style={{ marginBottom: 16 }}
        />
        <Form
          form={createForm}
          layout="vertical"
          initialValues={{ role: 'income' }}
        >
          <Form.Item
            name="username"
            label="用户名"
            rules={[
              { required: true, message: '请输入用户名' },
              { min: 3, message: '用户名至少 3 个字符' },
            ]}
          >
            <Input placeholder="请输入用户名" />
          </Form.Item>
          <Form.Item
            name="full_name"
            label="姓名"
            rules={[{ required: true, message: '请输入姓名' }]}
          >
            <Input placeholder="请输入姓名" />
          </Form.Item>
          <Form.Item name="role" label="角色">
            <Select options={ROLE_OPTIONS} />
          </Form.Item>
          <Form.Item name="department" label="部门">
            <Input placeholder="请输入部门（可选）" />
          </Form.Item>
          <Form.Item
            name="email"
            label="邮箱"
            rules={[{ type: 'email', message: '邮箱格式不正确' }]}
          >
            <Input placeholder="请输入邮箱（可选）" />
          </Form.Item>
        </Form>
      </Modal>

      {/* Edit Modal */}
      <Modal
        title={`编辑用户 — ${editingUser?.username || ''}`}
        open={editModalOpen}
        onOk={handleEdit}
        onCancel={() => {
          setEditModalOpen(false)
          setEditingUser(null)
        }}
        confirmLoading={submitLoading}
        destroyOnClose
        okText="保存"
        cancelText="取消"
      >
        <Form form={editForm} layout="vertical">
          <Form.Item
            name="full_name"
            label="姓名"
          >
            <Input placeholder="请输入姓名" />
          </Form.Item>
          <Form.Item name="role" label="角色">
            <Select options={ROLE_OPTIONS} />
          </Form.Item>
          <Form.Item name="department" label="部门">
            <Input placeholder="请输入部门" />
          </Form.Item>
          <Form.Item
            name="email"
            label="邮箱"
            rules={[{ type: 'email', message: '邮箱格式不正确' }]}
          >
            <Input placeholder="请输入邮箱" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
