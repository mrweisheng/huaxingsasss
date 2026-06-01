import { useState } from 'react'
import { Outlet, useNavigate, useLocation } from 'react-router-dom'
import { Layout as AntLayout, Menu, Avatar, Dropdown, Typography, Space } from 'antd'
import {
  FileTextOutlined,
  DollarOutlined,
  RobotOutlined,
  LogoutOutlined,
  TeamOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
} from '@ant-design/icons'
import { useAuthStore } from '@/store/useAuthStore'

const { Header, Sider, Content } = AntLayout
const { Text } = Typography

export default function Layout() {
  const navigate = useNavigate()
  const location = useLocation()
  const { user, logout } = useAuthStore()
  const [collapsed, setCollapsed] = useState(false)

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

  const paymentLabel =
    role === 'expense' ? '支出管理' : role === 'income' ? '收入管理' : '收付管理'
  menuItems.push({
    key: '/payments',
    icon: <DollarOutlined />,
    label: paymentLabel,
  })
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

  const userName = user?.full_name || user?.username || '用户'
  const userInitial = userName.charAt(0).toUpperCase()

  const dropdownItems = {
    items: [
      { key: 'info', label: `${userName} · ${role === 'admin' ? '管理员' : role === 'income' ? '收入专员' : '支出专员'}`, disabled: true },
      { type: 'divider' as const },
      { key: 'logout', icon: <LogoutOutlined />, label: '退出登录', danger: true },
    ],
    onClick: ({ key }: { key: string }) => {
      if (key === 'logout') handleLogout()
    },
  }

  return (
    <AntLayout style={{ minHeight: '100vh' }}>
      <Sider
        width={220}
        collapsedWidth={64}
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
          style={{ marginTop: 8, borderInlineEnd: 'none' }}
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

      <AntLayout style={{ marginLeft: collapsed ? 64 : 220, transition: 'margin-left 0.2s' }}>
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
    </AntLayout>
  )
}
