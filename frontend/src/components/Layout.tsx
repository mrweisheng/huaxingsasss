import { useState } from 'react'
import { Outlet, useNavigate, useLocation } from 'react-router-dom'
import { Layout as AntLayout, Menu, Avatar, Dropdown, Typography, Space, Modal, Form, Input, Button, message } from 'antd'
import {
  FileTextOutlined,
  DollarOutlined,
  RobotOutlined,
  LogoutOutlined,
  TeamOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  UserOutlined,
  KeyOutlined,
  PieChartOutlined,
} from '@ant-design/icons'
import { useAuthStore } from '@/store/useAuthStore'
import { userApi } from '@/services/user'

const { Header, Sider, Content } = AntLayout
const { Text } = Typography

export default function Layout() {
  const navigate = useNavigate()
  const location = useLocation()
  const { user, logout } = useAuthStore()
  const [collapsed, setCollapsed] = useState(false)
  const [passwordModalOpen, setPasswordModalOpen] = useState(false)
  const [passwordLoading, setPasswordLoading] = useState(false)
  const [passwordForm] = Form.useForm()

  const role = user?.role || ''

  const menuItems = []

  if (role === 'admin' || role === 'income') {
    menuItems.push({
      key: '/customers',
      icon: <TeamOutlined />,
      label: '客户管理',
    })
    menuItems.push({
      key: '/contracts',
      icon: <FileTextOutlined />,
      label: '合同管理',
    })
  }

  if (role === 'admin') {
    menuItems.push({
      key: '/users',
      icon: <UserOutlined />,
      label: '用户管理',
    })
  }

  const paymentLabel =
    role === 'expense' ? '支出管理' : role === 'income' ? '收入管理' : '收付管理'
  menuItems.push({
    key: '/payments',
    icon: <DollarOutlined />,
    label: paymentLabel,
  })

  if (role === 'admin') {
    menuItems.push({
      key: '/financial-overview',
      icon: <PieChartOutlined />,
      label: '财务总览',
    })
  }
  menuItems.push({
    key: '/agent',
    icon: <RobotOutlined />,
    label: '智能问答',
  })

  const selectedKey =
    menuItems.find(
      (item) =>
        location.pathname.startsWith(item.key + '/') || location.pathname === item.key,
    )?.key || ''

  const handleMenuClick = ({ key }: { key: string }) => {
    navigate(key)
  }

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  const handleChangePassword = async (values: { old_password: string; new_password: string; confirm_password: string }) => {
    if (values.new_password !== values.confirm_password) {
      message.error('两次输入的新密码不一致')
      return
    }
    setPasswordLoading(true)
    try {
      await userApi.changePassword({
        old_password: values.old_password,
        new_password: values.new_password,
      })
      message.success('密码修改成功')
      setPasswordModalOpen(false)
      passwordForm.resetFields()
    } catch (error: any) {
      message.error(error.response?.data?.detail || '密码修改失败')
    } finally {
      setPasswordLoading(false)
    }
  }

  const userName = user?.full_name || user?.username || '用户'
  const userInitial = userName.charAt(0).toUpperCase()

  const dropdownItems = {
    items: [
      { key: 'info', label: `${userName} · ${role === 'admin' ? '管理员' : role === 'income' ? '收入专员' : '支出专员'}`, disabled: true },
      { type: 'divider' as const },
      { key: 'changePassword', icon: <KeyOutlined />, label: '修改密码' },
      { key: 'logout', icon: <LogoutOutlined />, label: '退出登录', danger: true },
    ],
    onClick: ({ key }: { key: string }) => {
      if (key === 'logout') handleLogout()
      else if (key === 'changePassword') setPasswordModalOpen(true)
    },
  }

  return (
    <AntLayout style={{ minHeight: '100vh' }}>
      <Sider
        width={240}
        collapsedWidth={68}
        collapsible
        collapsed={collapsed}
        onCollapse={setCollapsed}
        trigger={null}
        style={{
          height: '100vh',
          position: 'fixed',
          left: 0,
          top: 0,
          zIndex: 10,
          background: 'linear-gradient(180deg, #0f1a2e 0%, #162240 100%)',
        }}
      >
        <div
          style={{
            height: 64,
            display: 'flex',
            alignItems: 'center',
            justifyContent: collapsed ? 'center' : 'flex-start',
            padding: collapsed ? 0 : '0 16px 0 20px',
            borderBottom: '1px solid rgba(255,255,255,0.06)',
            gap: 10,
            overflow: 'hidden',
          }}
        >
          <div
            style={{
              width: 32,
              height: 32,
              borderRadius: 8,
              background: 'linear-gradient(135deg, #c9952b 0%, #e8b84b 100%)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#0f1a2e',
              fontWeight: 700,
              fontSize: 14,
              fontFamily: "'Noto Serif SC', serif",
              flexShrink: 0,
            }}
          >
            华
          </div>
          {!collapsed && (
            <div style={{ lineHeight: 1.2 }}>
              <Text
                style={{
                  color: '#f1f5f9',
                  fontSize: 16,
                  fontWeight: 700,
                  fontFamily: "'Noto Serif SC', serif",
                  letterSpacing: 1,
                  display: 'block',
                }}
              >
                华星资源
              </Text>
              <Text
                style={{
                  color: 'rgba(255,255,255,0.4)',
                  fontSize: 10,
                  letterSpacing: 0.5,
                  display: 'block',
                  marginTop: 1,
                }}
              >
                HUA XING CONTRACT
              </Text>
            </div>
          )}
        </div>

        {!collapsed && <div className="divider-gold" style={{ margin: '0 16px' }} />}

        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[selectedKey]}
          items={menuItems}
          onClick={handleMenuClick}
          className="sider-menu"
          style={{ marginTop: 4, borderInlineEnd: 'none' }}
        />

        {!collapsed && (
          <div
            style={{
              position: 'absolute',
              bottom: 0,
              left: 0,
              right: 0,
              padding: '12px 16px',
              borderTop: '1px solid rgba(255,255,255,0.06)',
              display: 'flex',
              alignItems: 'center',
              gap: 10,
            }}
          >
            <Dropdown menu={dropdownItems} placement="topRight">
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 10,
                  cursor: 'pointer',
                  padding: '4px 0',
                  width: '100%',
                }}
              >
                <Avatar
                  style={{
                    background: 'linear-gradient(135deg, #1e3a5f, #c9952b)',
                    flexShrink: 0,
                    fontSize: 12,
                  }}
                  size={28}
                >
                  {userInitial}
                </Avatar>
                <div style={{ lineHeight: 1.2, flex: 1, minWidth: 0 }}>
                  <Text
                    style={{
                      color: '#f1f5f9',
                      fontSize: 12,
                      fontWeight: 500,
                      display: 'block',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {userName}
                  </Text>
                  <Text
                    style={{
                      color: 'rgba(255,255,255,0.35)',
                      fontSize: 10,
                      display: 'block',
                    }}
                  >
                    {role === 'admin' ? '管理员' : role === 'income' ? '收入专员' : role === 'expense' ? '支出专员' : role}
                  </Text>
                </div>
              </div>
            </Dropdown>
          </div>
        )}
      </Sider>

      <AntLayout style={{ marginLeft: collapsed ? 68 : 240, transition: 'margin-left 0.2s' }}>
        <Header
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            background: 'rgba(255,255,255,0.85)',
            backdropFilter: 'blur(12px)',
            WebkitBackdropFilter: 'blur(12px)',
            padding: '0 24px',
            position: 'sticky',
            top: 0,
            zIndex: 9,
            height: 56,
            borderBottom: '1px solid var(--border-light)',
            boxShadow: '0 1px 3px rgba(15,23,42,0.04)',
          }}
        >
          <Space>
            <div
              onClick={() => setCollapsed(!collapsed)}
              style={{
                cursor: 'pointer',
                fontSize: 16,
                color: 'var(--text-secondary)',
                padding: '4px 8px',
                borderRadius: 6,
                transition: 'all 0.2s',
                display: 'flex',
                alignItems: 'center',
              }}
              onMouseEnter={(e) => { e.currentTarget.style.background = 'var(--bg-hover)' }}
              onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent' }}
            >
              {collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
            </div>
            <span style={{ fontSize: 13, color: 'var(--text-tertiary)', marginLeft: 4 }}>
              {selectedKey
                ? menuItems.find((m) => m.key === selectedKey)?.label as string
                : ''}
            </span>
          </Space>

          <Dropdown menu={dropdownItems} placement="bottomRight">
            <Space
              style={{ cursor: 'pointer', padding: '4px 8px', borderRadius: 6 }}
              onMouseEnter={(e) => { e.currentTarget.style.background = 'var(--bg-hover)' }}
              onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent' }}
            >
              <Avatar
                style={{
                  background: 'linear-gradient(135deg, #1e3a5f, #c9952b)',
                  fontSize: 11,
                }}
                size={26}
              >
                {userInitial}
              </Avatar>
              <span style={{ fontSize: 13, color: 'var(--text-secondary)', fontWeight: 500 }}>
                {userName}
              </span>
            </Space>
          </Dropdown>
        </Header>

        <Content style={{ padding: 0, minHeight: 'calc(100vh - 56px)' }}>
          <Outlet />
        </Content>
      </AntLayout>

      {/* 修改密码 Modal */}
      <Modal
        title="修改密码"
        open={passwordModalOpen}
        onCancel={() => {
          setPasswordModalOpen(false)
          passwordForm.resetFields()
        }}
        footer={null}
        destroyOnClose
      >
        <Form
          form={passwordForm}
          layout="vertical"
          onFinish={handleChangePassword}
          style={{ marginTop: 16 }}
        >
          <Form.Item
            name="old_password"
            label="旧密码"
            rules={[{ required: true, message: '请输入旧密码' }]}
          >
            <Input.Password placeholder="请输入旧密码" />
          </Form.Item>
          <Form.Item
            name="new_password"
            label="新密码"
            rules={[
              { required: true, message: '请输入新密码' },
              { min: 6, message: '密码至少 6 个字符' },
            ]}
          >
            <Input.Password placeholder="请输入新密码（至少6位）" />
          </Form.Item>
          <Form.Item
            name="confirm_password"
            label="确认新密码"
            dependencies={['new_password']}
            rules={[
              { required: true, message: '请确认新密码' },
              ({ getFieldValue }) => ({
                validator(_, value) {
                  if (!value || getFieldValue('new_password') === value) {
                    return Promise.resolve()
                  }
                  return Promise.reject(new Error('两次输入的密码不一致'))
                },
              }),
            ]}
          >
            <Input.Password placeholder="请再次输入新密码" />
          </Form.Item>
          <Form.Item style={{ marginBottom: 0, textAlign: 'right' }}>
            <Space>
              <Button onClick={() => {
                setPasswordModalOpen(false)
                passwordForm.resetFields()
              }}>
                取消
              </Button>
              <Button type="primary" htmlType="submit" loading={passwordLoading}>
                确认修改
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>
    </AntLayout>
  )
}
