import { useState, useEffect } from 'react'
import { Outlet, useNavigate, useLocation } from 'react-router-dom'
import { Layout as AntLayout, Menu, Avatar, Dropdown, Typography, Space, Modal, Form, Input, Button, message, Drawer, Grid, Tag } from 'antd'
import {
  FileTextOutlined,
  DollarOutlined,
  LogoutOutlined,
  TeamOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  MenuOutlined,
  UserOutlined,
  KeyOutlined,
  PieChartOutlined,
  CloseOutlined,
  StarFilled,
  PlusOutlined,
  DeleteOutlined,
  MessageOutlined,
} from '@ant-design/icons'
import { useAuthStore } from '@/store/useAuthStore'
import { useAgentStore } from '@/store/useAgentStore'
import { userApi } from '@/services/user'
import MobileNav from './MobileNav'

const { Header, Sider, Content } = AntLayout
const { Text } = Typography

/* ── 聊天记录时间格式化（Layout 侧栏专用）── */
function formatSessionTime(iso: string | null | undefined): string {
  if (!iso) return ''
  const d = new Date(iso)
  const now = new Date()
  const diffMin = Math.floor((now.getTime() - d.getTime()) / 60000)
  if (diffMin < 1) return '刚刚'
  if (diffMin < 60) return `${diffMin}分钟前`
  const diffHour = Math.floor(diffMin / 60)
  if (diffHour < 24) return `${diffHour}小时前`
  const diffDay = Math.floor(diffHour / 24)
  if (diffDay < 7) return `${diffDay}天前`
  return `${d.getMonth() + 1}/${d.getDate()}`
}

export default function Layout() {
  const navigate = useNavigate()
  const location = useLocation()
  const { user, logout } = useAuthStore()
  const [collapsed, setCollapsed] = useState(false)
  const [passwordModalOpen, setPasswordModalOpen] = useState(false)
  const [passwordLoading, setPasswordLoading] = useState(false)
  const [passwordForm] = Form.useForm()
  const [mobileDrawerOpen, setMobileDrawerOpen] = useState(false)
  const [hoveredSession, setHoveredSession] = useState<string | null>(null)

  // 聊天记录 store（Layout 直接消费）
  const {
    sessions,
    currentSessionId,
    loadSessions,
    createSession,
    switchSession,
    deleteSession,
  } = useAgentStore()

  // Layout 挂载时拉一次 sessions（AgentChat 也会拉，但 Layout 是全局，优先拉）
  useEffect(() => { loadSessions() }, [])

  // 移动端断点检测 — 默认 desktop，避免首次渲染闪烁
  const screens = Grid.useBreakpoint()
  const isMobile = !(screens.md ?? true)

  const role = user?.role || ''

  /* ── 业务菜单（不含小星助手）── */
  const businessMenuItems: { key: string; icon: JSX.Element; label: string }[] = []

  if (role === 'admin' || role === 'income') {
    businessMenuItems.push({
      key: '/customers',
      icon: <TeamOutlined />,
      label: '客户管理',
    })
    businessMenuItems.push({
      key: '/contracts',
      icon: <FileTextOutlined />,
      label: '合同管理',
    })
  }

  if (role === 'admin') {
    businessMenuItems.push({
      key: '/users',
      icon: <UserOutlined />,
      label: '用户管理',
    })
  }

  const paymentLabel =
    role === 'expense' ? '支出管理' : role === 'income' ? '收入管理' : '收付管理'
  businessMenuItems.push({
    key: '/payments',
    icon: <DollarOutlined />,
    label: paymentLabel,
  })

  if (role === 'admin') {
    businessMenuItems.push({
      key: '/financial-overview',
      icon: <PieChartOutlined />,
      label: '财务总览',
    })
  }

  // 不再把小星助手塞进业务菜单；它是独立入口

  const selectedKey =
    businessMenuItems.find(
      (item) =>
        location.pathname.startsWith(item.key + '/') || location.pathname === item.key,
    )?.key || ''

  // 小星助手入口高亮判断：在 /agent 路由下
  const isOnAgent = location.pathname.startsWith('/agent')

  const handleBusinessMenuClick = ({ key }: { key: string }) => {
    navigate(key)
  }

  const handleNewChat = async () => {
    // 创建新会话，然后跳到 /agent
    await createSession()
    navigate('/agent')
  }

  const handleClickSession = (sessionId: string) => {
    switchSession(sessionId)
    navigate('/agent')
  }

  const handleDeleteSession = (sessionId: string, e: React.MouseEvent) => {
    e.stopPropagation()
    Modal.confirm({
      title: '删除会话',
      content: '确定要删除此会话吗？删除后无法恢复。',
      okText: '删除',
      okType: 'danger',
      cancelText: '取消',
      onOk: () => deleteSession(sessionId),
    })
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
      {!isMobile && (
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

        {/* ══════ ① 小星助手独立入口（最顶部）══════ */}
        <div
          onClick={() => navigate('/agent')}
          style={{
            margin: '8px 8px 4px',
            padding: '10px 12px',
            borderRadius: 10,
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: 10,
            background: isOnAgent
              ? 'linear-gradient(90deg, rgba(201, 149, 43, 0.18) 0%, rgba(201, 149, 43, 0.06) 100%)'
              : 'rgba(201, 149, 43, 0.06)',
            border: isOnAgent
              ? '1px solid rgba(201, 149, 43, 0.3)'
              : '1px solid rgba(201, 149, 43, 0.12)',
            transition: 'all 0.2s',
            position: 'relative',
          }}
          onMouseEnter={(e) => {
            if (!isOnAgent) e.currentTarget.style.background = 'rgba(201, 149, 43, 0.12)'
          }}
          onMouseLeave={(e) => {
            if (!isOnAgent) e.currentTarget.style.background = 'rgba(201, 149, 43, 0.06)'
          }}
        >
          {isOnAgent && (
            <span style={{
              position: 'absolute', left: 0, top: 8, bottom: 8, width: 3,
              background: 'var(--brand-gold)', borderRadius: '0 2px 2px 0',
              boxShadow: '0 0 8px rgba(201, 149, 43, 0.4)',
            }} />
          )}
          <div style={{
            width: 28, height: 28, borderRadius: 8,
            background: 'linear-gradient(135deg, var(--brand-gold), #e8b84b)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            color: '#0f1a2e', flexShrink: 0,
            boxShadow: '0 2px 8px rgba(201, 149, 43, 0.25)',
          }}>
            <StarFilled style={{ fontSize: 14 }} />
          </div>
          {!collapsed && (
            <div style={{ flex: 1, minWidth: 0, display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 6 }}>
              <Text style={{
                color: isOnAgent ? '#f1f5f9' : 'rgba(255,255,255,0.85)',
                fontSize: 14, fontWeight: isOnAgent ? 600 : 500,
                overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
              }}>
                小星助手
              </Text>
              <Tag color="gold" style={{ margin: 0, fontSize: 9, lineHeight: '14px', padding: '0 4px', borderRadius: 3 }}>
                AI
              </Tag>
            </div>
          )}
        </div>

        {/* ══════ ② 业务菜单（小星助手下方）══════ */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
          {!collapsed && (
            <div style={{
              padding: '12px 16px 4px',
              fontSize: 10, fontWeight: 600,
              color: 'rgba(255,255,255,0.35)',
              letterSpacing: 1, textTransform: 'uppercase',
            }}>
              业务
            </div>
          )}
          <Menu
            theme="dark"
            mode="inline"
            selectedKeys={[selectedKey]}
            items={businessMenuItems}
            onClick={handleBusinessMenuClick}
            className="sider-menu"
            style={{ borderInlineEnd: 'none' }}
          />

          {/* ══════ ③ 聊天记录（侧边栏下半部分）══════ */}
          {!collapsed && (
            <div style={{
              marginTop: 16, paddingTop: 12,
              borderTop: '1px solid rgba(255,255,255,0.06)',
              display: 'flex', flexDirection: 'column',
              minHeight: 0, flex: 1,
            }}>
              <div style={{
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                padding: '0 16px 8px', flexShrink: 0,
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <MessageOutlined style={{ fontSize: 13, color: 'rgba(201,149,43,0.85)' }} />
                  <Text style={{
                    fontSize: 12, fontWeight: 600,
                    color: 'rgba(255,255,255,0.7)',
                    letterSpacing: 0.5,
                  }}>
                    聊天记录
                  </Text>
                  <span style={{
                    fontSize: 10, color: 'rgba(255,255,255,0.4)',
                    background: 'rgba(255,255,255,0.06)', padding: '0 5px',
                    borderRadius: 3,
                  }}>
                    {sessions.length}
                  </span>
                </div>
                <Button
                  type="text" size="small"
                  icon={<PlusOutlined style={{ fontSize: 12 }} />}
                  onClick={handleNewChat}
                  style={{ color: 'var(--brand-gold)', fontSize: 11, padding: '0 6px', height: 22 }}
                >
                  新建
                </Button>
              </div>
              <div style={{ flex: 1, overflow: 'auto', padding: '0 8px 8px' }}>
                {sessions.length === 0 ? (
                  <div style={{ textAlign: 'center', padding: '24px 8px', color: 'rgba(255,255,255,0.35)', fontSize: 12 }}>
                    暂无对话
                  </div>
                ) : (
                  sessions.map((session) => {
                    const isActive = session.sessionId === currentSessionId
                    const isHovered = hoveredSession === session.sessionId
                    return (
                      <div
                        key={session.sessionId}
                        onClick={() => handleClickSession(session.sessionId)}
                        onMouseEnter={() => setHoveredSession(session.sessionId)}
                        onMouseLeave={() => setHoveredSession(null)}
                        style={{
                          padding: '8px 10px',
                          borderRadius: 8,
                          cursor: 'pointer',
                          marginBottom: 2,
                          background: isActive
                            ? 'rgba(201, 149, 43, 0.15)'
                            : isHovered
                              ? 'rgba(255,255,255,0.06)'
                              : 'transparent',
                          border: isActive ? '1px solid rgba(201,149,43,0.3)' : '1px solid transparent',
                          transition: 'all 0.15s',
                          position: 'relative',
                        }}
                      >
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 4 }}>
                          <Text style={{
                            fontSize: 12,
                            fontWeight: isActive ? 600 : 400,
                            color: isActive ? '#f1f5f9' : 'rgba(255,255,255,0.75)',
                            display: 'block',
                            overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                            flex: 1, minWidth: 0,
                          }}>
                            {session.title || '新对话'}
                          </Text>
                          <DeleteOutlined
                            onClick={(e) => handleDeleteSession(session.sessionId, e)}
                            style={{
                              fontSize: 11,
                              color: isHovered ? 'rgba(255,255,255,0.5)' : 'transparent',
                              padding: 2, flexShrink: 0,
                              cursor: 'pointer', transition: 'color 0.15s',
                            }}
                            onMouseEnter={(e) => { e.currentTarget.style.color = '#ef4444' }}
                            onMouseLeave={(e) => { e.currentTarget.style.color = isHovered ? 'rgba(255,255,255,0.5)' : 'transparent' }}
                          />
                        </div>
                        <div style={{ display: 'flex', gap: 8, marginTop: 2 }}>
                          <span style={{ fontSize: 10, color: 'rgba(255,255,255,0.35)' }}>
                            {formatSessionTime(session.createdAt)}
                          </span>
                          <span style={{ fontSize: 10, color: 'rgba(255,255,255,0.35)' }}>
                            {session.messageCount} 条
                          </span>
                        </div>
                      </div>
                    )
                  })
                )}
              </div>
            </div>
          )}
        </div>

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
      )}

      <AntLayout style={{ marginLeft: isMobile ? 0 : (collapsed ? 68 : 240), transition: 'margin-left 0.2s' }}>
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
            {isMobile ? (
              <div
                onClick={() => setMobileDrawerOpen(true)}
                style={{
                  cursor: 'pointer',
                  fontSize: 20,
                  color: 'var(--text-secondary)',
                  padding: '4px 8px',
                  borderRadius: 6,
                  display: 'flex',
                  alignItems: 'center',
                }}
              >
                <MenuOutlined />
              </div>
            ) : (
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
            )}
            <span style={{ fontSize: 13, color: 'var(--text-tertiary)', marginLeft: 4 }}>
              {isOnAgent
                ? '小星助手'
                : selectedKey
                  ? businessMenuItems.find((m) => m.key === selectedKey)?.label as string
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
              {!isMobile && <span style={{ fontSize: 13, color: 'var(--text-secondary)', fontWeight: 500 }}>
                {userName}
              </span>}
            </Space>
          </Dropdown>
        </Header>

        <Content style={{ padding: 0, minHeight: 'calc(100vh - 56px)', paddingBottom: isMobile ? 'calc(56px + env(safe-area-inset-bottom, 0px))' : 0 }}>
          <Outlet />
        </Content>
      </AntLayout>

      {/* 移动端：底部导航栏 */}
      {isMobile && <MobileNav role={role} />}

      {/* 移动端：侧边抽屉导航（完整菜单） */}
      <Drawer
        title={
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div
              style={{
                width: 28,
                height: 28,
                borderRadius: 6,
                background: 'linear-gradient(135deg, #c9952b 0%, #e8b84b 100%)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#0f1a2e',
                fontWeight: 700,
                fontSize: 12,
                fontFamily: "'Noto Serif SC', serif",
                flexShrink: 0,
              }}
            >
              华
            </div>
            <span style={{ fontWeight: 700, fontSize: 16, color: '#0f172a', fontFamily: "'Noto Serif SC', serif" }}>
              华星资源
            </span>
          </div>
        }
        placement="left"
        onClose={() => setMobileDrawerOpen(false)}
        open={isMobile && mobileDrawerOpen}
        width={280}
        styles={{ body: { padding: 0, display: 'flex', flexDirection: 'column' } }}
        closeIcon={<CloseOutlined style={{ fontSize: 14, color: 'var(--text-tertiary)' }} />}
      >
        {/* 用户信息 */}
        <div
          style={{
            padding: '16px 20px',
            borderBottom: '1px solid var(--border-light)',
            display: 'flex',
            alignItems: 'center',
            gap: 12,
          }}
        >
          <Avatar
            style={{
              background: 'linear-gradient(135deg, #1e3a5f, #c9952b)',
              fontSize: 14,
            }}
            size={36}
          >
            {userInitial}
          </Avatar>
          <div style={{ lineHeight: 1.3 }}>
            <div style={{ fontSize: 15, fontWeight: 600, color: 'var(--text-primary)' }}>{userName}</div>
            <div style={{ fontSize: 12, color: 'var(--text-tertiary)', marginTop: 2 }}>
              {role === 'admin' ? '管理员' : role === 'income' ? '收入专员' : role === 'expense' ? '支出专员' : role}
            </div>
          </div>
        </div>

        {/* 导航菜单 */}
        <Menu
          mode="inline"
          selectedKeys={[isOnAgent ? '/agent' : selectedKey]}
          items={businessMenuItems}
          onClick={({ key }) => {
            navigate(key)
            setMobileDrawerOpen(false)
          }}
          style={{ border: 'none', flex: 1 }}
        />

        {/* 底部操作 */}
        <div
          style={{
            borderTop: '1px solid var(--border-light)',
            padding: '12px 8px',
          }}
        >
          <Button
            type="text"
            icon={<KeyOutlined />}
            block
            style={{
              justifyContent: 'flex-start',
              textAlign: 'left',
              height: 44,
              paddingLeft: 16,
              color: 'var(--text-secondary)',
            }}
            onClick={() => {
              setPasswordModalOpen(true)
              setMobileDrawerOpen(false)
            }}
          >
            修改密码
          </Button>
          <Button
            type="text"
            icon={<LogoutOutlined />}
            danger
            block
            style={{
              justifyContent: 'flex-start',
              textAlign: 'left',
              height: 44,
              paddingLeft: 16,
            }}
            onClick={() => {
              handleLogout()
              setMobileDrawerOpen(false)
            }}
          >
            退出登录
          </Button>
        </div>
      </Drawer>

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
