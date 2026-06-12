import { useState, useEffect } from 'react'
import { Outlet, useNavigate, useLocation } from 'react-router-dom'
import { Layout as AntLayout, Menu, Avatar, Dropdown, Typography, Space, Modal, Form, Input, Button, message, Drawer, Grid } from 'antd'
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
  DeleteOutlined,
  DownOutlined,
  UpOutlined,
  MessageOutlined,
  CommentOutlined,
} from '@ant-design/icons'
import { useAuthStore } from '@/store/useAuthStore'
import { useAgentStore } from '@/store/useAgentStore'
import { userApi } from '@/services/user'
import MobileNav from './MobileNav'

/* ── 会话时间格式化 ── */
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
  const [mobileDrawerOpen, setMobileDrawerOpen] = useState(false)
  const [sessionsExpanded, setSessionsExpanded] = useState(false)
  const [hoveredSession, setHoveredSession] = useState<string | null>(null)

  // 移动端断点检测 — 默认 desktop，避免首次渲染闪烁
  const screens = Grid.useBreakpoint()
  const isMobile = !(screens.md ?? true)

  // 会话管理（侧边栏下半部分常驻显示）
  const {
    sessions,
    currentSessionId,
    loadSessions,
    switchSession,
    deleteSession,
  } = useAgentStore()

  useEffect(() => {
    loadSessions()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const handleClickSession = (sessionId: string) => {
    switchSession(sessionId)
    if (!location.pathname.startsWith('/agent')) navigate('/agent')
  }

  const handleDeleteSession = (sessionId: string, e: React.MouseEvent) => {
    e.stopPropagation()
    Modal.confirm({
      title: '删除会话',
      content: '确定要删除此会话吗？删除后无法恢复。',
      okText: '删除',
      okType: 'danger',
      cancelText: '取消',
      centered: true,
      onOk: async () => {
        const wasCurrent = sessionId === currentSessionId
        await deleteSession(sessionId)
        if (wasCurrent) {
          const next = useAgentStore.getState().sessions[0]
          if (next) switchSession(next.sessionId)
        }
      },
    })
  }

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
    businessMenuItems.push({
      key: '/users',
      icon: <UserOutlined />,
      label: '用户管理',
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
        <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
        {/* ══════ LOGO 区（书脊形态：金色竖条 + 衬线字 + 等宽 META）══════ */}
        <div
          style={{
            padding: collapsed ? '22px 0 20px' : '22px 22px 20px',
            display: 'flex',
            alignItems: 'flex-start',
            justifyContent: collapsed ? 'center' : 'flex-start',
            gap: 14,
            borderBottom: '1px solid rgba(255,255,255,0.05)',
            overflow: 'hidden',
          }}
        >
          {!collapsed ? (
            <>
              {/* 金色书脊竖条 */}
              <div
                style={{
                  width: 3,
                  alignSelf: 'stretch',
                  background: 'linear-gradient(180deg, var(--brand-gold) 0%, rgba(201,149,43,0) 100%)',
                  borderRadius: 2,
                  marginTop: 4,
                  minHeight: 38,
                  flexShrink: 0,
                }}
              />
              <div style={{ flex: 1, minWidth: 0 }}>
                <Text
                  style={{
                    fontFamily: "'Noto Serif SC', serif",
                    fontSize: 19,
                    fontWeight: 600,
                    color: '#f1f5f9',
                    letterSpacing: 3,
                    lineHeight: 1.2,
                    display: 'block',
                  }}
                >
                  华星资源
                </Text>
                <div style={{ marginTop: 6, display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span
                    style={{
                      width: 4,
                      height: 4,
                      borderRadius: '50%',
                      background: 'var(--brand-gold)',
                      opacity: 0.7,
                    }}
                  />
                  <span
                    style={{
                      fontFamily: "'JetBrains Mono', monospace",
                      fontSize: 9.5,
                      color: 'rgba(241, 245, 249, 0.4)',
                      letterSpacing: 1.5,
                      textTransform: 'uppercase',
                    }}
                  >
                    CONTRACT · OS
                  </span>
                </div>
              </div>
            </>
          ) : (
            // 折叠态：保留一颗金色小圆作为品牌印记
            <div
              style={{
                width: 8,
                height: 8,
                borderRadius: '50%',
                background: 'var(--brand-gold)',
                boxShadow: '0 0 10px rgba(201,149,43,0.5)',
              }}
            />
          )}
        </div>

        {/* ══════ ① 小星助手独立入口（金色浮岛）══════ */}
        <div
          onClick={() => navigate('/agent')}
          style={{
            margin: collapsed ? '12px 10px 6px' : '18px 14px 6px',
            padding: collapsed ? '10px 0' : '14px 16px',
            borderRadius: 12,
            cursor: 'pointer',
            background: isOnAgent
              ? 'linear-gradient(135deg, #d4a23a 0%, #ecc05e 45%, #c2901c 100%)'
              : 'linear-gradient(135deg, #c9952b 0%, #e8b84b 45%, #b8831c 100%)',
            boxShadow: isOnAgent
              ? '0 10px 26px rgba(201, 149, 43, 0.5), 0 2px 6px rgba(201, 149, 43, 0.25), inset 0 1px 0 rgba(255,255,255,0.5), inset 0 -2px 4px rgba(0,0,0,0.12)'
              : '0 8px 20px rgba(201, 149, 43, 0.35), 0 2px 6px rgba(201, 149, 43, 0.2), inset 0 1px 0 rgba(255,255,255,0.4), inset 0 -2px 4px rgba(0,0,0,0.12)',
            color: '#0f1a2e',
            position: 'relative',
            overflow: 'hidden',
            transition: 'box-shadow 0.25s, transform 0.18s',
            display: 'flex',
            alignItems: 'center',
            justifyContent: collapsed ? 'center' : 'flex-start',
            gap: 12,
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.transform = 'translateY(-1px)'
            e.currentTarget.style.boxShadow =
              '0 12px 28px rgba(201, 149, 43, 0.5), 0 2px 6px rgba(201, 149, 43, 0.25), inset 0 1px 0 rgba(255,255,255,0.5), inset 0 -2px 4px rgba(0,0,0,0.12)'
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.transform = 'translateY(0)'
            e.currentTarget.style.boxShadow = isOnAgent
              ? '0 10px 26px rgba(201, 149, 43, 0.5), 0 2px 6px rgba(201, 149, 43, 0.25), inset 0 1px 0 rgba(255,255,255,0.5), inset 0 -2px 4px rgba(0,0,0,0.12)'
              : '0 8px 20px rgba(201, 149, 43, 0.35), 0 2px 6px rgba(201, 149, 43, 0.2), inset 0 1px 0 rgba(255,255,255,0.4), inset 0 -2px 4px rgba(0,0,0,0.12)'
          }}
        >
          {/* 浮岛高光层 */}
          <span
            aria-hidden
            style={{
              position: 'absolute',
              inset: -2,
              background: 'linear-gradient(135deg, transparent 0%, rgba(255,255,255,0.15) 50%, transparent 100%)',
              pointerEvents: 'none',
            }}
          />
          {/* 深色图标盒子 + 金色五角星 */}
          <div
            style={{
              width: 32,
              height: 32,
              borderRadius: 8,
              background: 'rgba(15, 26, 46, 0.88)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#e8b84b',
              boxShadow: '0 2px 8px rgba(0,0,0,0.2)',
              flexShrink: 0,
              position: 'relative',
            }}
          >
            <StarFilled style={{ fontSize: 15 }} />
          </div>
          {!collapsed && (
            <>
              <div style={{ flex: 1, minWidth: 0, position: 'relative' }}>
                <div
                  style={{
                    fontSize: 15,
                    fontWeight: 700,
                    color: '#0f1a2e',
                    letterSpacing: 0.5,
                    lineHeight: 1.2,
                  }}
                >
                  小星助手
                </div>
                <div
                  style={{
                    fontSize: 11,
                    color: 'rgba(15, 26, 46, 0.65)',
                    marginTop: 3,
                    fontWeight: 500,
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                  }}
                >
                  智能录入 · 文件分析
                </div>
              </div>
              <span
                style={{
                  background: 'rgba(15, 26, 46, 0.15)',
                  color: '#0f1a2e',
                  fontSize: 10,
                  fontWeight: 700,
                  padding: '2px 7px',
                  borderRadius: 4,
                  letterSpacing: 1,
                  lineHeight: '14px',
                  position: 'relative',
                  flexShrink: 0,
                }}
              >
                AI
              </span>
            </>
          )}
        </div>

        {/* ══════ ② 业务菜单（小星助手下方）══════ */}
        <div style={{ flexShrink: 0, display: 'flex', flexDirection: 'column' }}>
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
        </div>

        {/* ══════ ③ 会话历史（侧边栏下半部分，仅展开时显示）══════ */}
        {!collapsed ? (
          <div style={{
            flex: 1, minHeight: 0,
            display: 'flex', flexDirection: 'column',
            marginTop: 8,
            borderTop: '1px solid rgba(255,255,255,0.06)',
            paddingTop: 8,
          }}>
            <div style={{
              padding: '8px 16px 10px',
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
                <CommentOutlined style={{
                  fontSize: 12,
                  color: 'rgba(201, 149, 43, 0.9)',
                }} />
                <span style={{
                  fontSize: 13, fontWeight: 600,
                  color: 'rgba(255, 255, 255, 0.88)',
                  letterSpacing: 0.3,
                }}>
                  对话历史
                </span>
                {sessions.length > 0 && (
                  <span style={{
                    fontSize: 10, fontWeight: 600,
                    color: 'rgba(255, 255, 255, 0.55)',
                    background: 'rgba(255, 255, 255, 0.08)',
                    padding: '1px 6px', borderRadius: 8,
                    lineHeight: '14px',
                    minWidth: 16, textAlign: 'center',
                  }}>
                    {sessions.length}
                  </span>
                )}
              </div>
            </div>

            <div style={{
              flex: 1, minHeight: 0,
              overflow: sessionsExpanded ? 'auto' : 'hidden',
              padding: '0 8px 8px',
            }}>
              {sessions.length === 0 ? (
                <div style={{
                  textAlign: 'center', padding: '16px 8px',
                  color: 'rgba(255,255,255,0.3)', fontSize: 11,
                }}>
                  暂无对话
                </div>
              ) : (
                <>
                  {(sessionsExpanded ? sessions : sessions.slice(0, 3)).map((session) => {
                    const isActive = session.sessionId === currentSessionId
                    const isHovered = hoveredSession === session.sessionId
                    const title = (session.title && session.title.trim()) || '新对话'
                    return (
                      <div
                        key={session.sessionId}
                        onClick={() => handleClickSession(session.sessionId)}
                        onMouseEnter={() => setHoveredSession(session.sessionId)}
                        onMouseLeave={() => setHoveredSession(null)}
                        style={{
                          position: 'relative',
                          padding: '9px 12px 9px 14px',
                          borderRadius: 8,
                          cursor: 'pointer',
                          marginBottom: 4,
                          background: isActive
                            ? 'linear-gradient(90deg, rgba(201, 149, 43, 0.18) 0%, rgba(201, 149, 43, 0.06) 100%)'
                            : isHovered ? 'rgba(255,255,255,0.06)' : 'transparent',
                          border: isActive
                            ? '1px solid rgba(201, 149, 43, 0.35)'
                            : isHovered ? '1px solid rgba(255,255,255,0.08)' : '1px solid transparent',
                          boxShadow: isActive ? '0 2px 8px rgba(201, 149, 43, 0.12)' : 'none',
                          transition: 'all 0.18s',
                        }}
                      >
                        {/* 左侧活跃指示条 */}
                        {isActive && (
                          <span style={{
                            position: 'absolute', left: 0, top: 8, bottom: 8, width: 3,
                            background: 'var(--brand-gold)', borderRadius: '0 2px 2px 0',
                            boxShadow: '0 0 6px rgba(201, 149, 43, 0.5)',
                          }} />
                        )}

                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 6 }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 6, flex: 1, minWidth: 0 }}>
                            <MessageOutlined style={{
                              fontSize: 11,
                              color: isActive ? 'var(--brand-gold)' : 'rgba(255,255,255,0.4)',
                              flexShrink: 0,
                              transition: 'color 0.18s',
                            }} />
                            <Text style={{
                              fontSize: 12.5,
                              fontWeight: isActive ? 600 : 500,
                              color: isActive ? '#f8fafc' : 'rgba(241, 245, 249, 0.82)',
                              display: 'block',
                              overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                              flex: 1, minWidth: 0,
                              letterSpacing: 0.1,
                            }}>
                              {title}
                            </Text>
                          </div>
                          <span
                            role="button"
                            aria-label="删除会话"
                            title="删除会话"
                            onClick={(e) => handleDeleteSession(session.sessionId, e)}
                            style={{
                              display: 'inline-flex',
                              alignItems: 'center',
                              justifyContent: 'center',
                              width: 22, height: 22,
                              fontSize: 12,
                              flexShrink: 0,
                              cursor: 'pointer',
                              borderRadius: 4,
                              transition: 'all 0.15s',
                              color: '#dc6b3d',
                              background: 'rgba(220, 107, 61, 0.14)',
                              border: '1px solid rgba(220, 107, 61, 0.35)',
                            }}
                            onMouseEnter={(ev) => {
                              ev.currentTarget.style.color = '#b85823'
                              ev.currentTarget.style.background = 'rgba(220, 107, 61, 0.28)'
                              ev.currentTarget.style.borderColor = 'rgba(220, 107, 61, 0.6)'
                            }}
                            onMouseLeave={(ev) => {
                              ev.currentTarget.style.color = '#dc6b3d'
                              ev.currentTarget.style.background = 'rgba(220, 107, 61, 0.14)'
                              ev.currentTarget.style.borderColor = 'rgba(220, 107, 61, 0.35)'
                            }}
                          >
                            <DeleteOutlined />
                          </span>
                        </div>
                        <div style={{
                          display: 'flex', alignItems: 'center', gap: 6, marginTop: 4,
                          paddingLeft: 17,
                        }}>
                          <span style={{ fontSize: 10, color: 'rgba(255,255,255,0.38)' }}>
                            {formatSessionTime(session.createdAt)}
                          </span>
                          <span style={{ width: 2, height: 2, borderRadius: '50%', background: 'rgba(255,255,255,0.25)' }} />
                          <span style={{ fontSize: 10, color: 'rgba(255,255,255,0.38)' }}>
                            {session.messageCount} 条
                          </span>
                        </div>
                      </div>
                    )
                  })}
                  {sessions.length > 3 && (
                    <div
                      onClick={() => setSessionsExpanded(!sessionsExpanded)}
                      style={{
                        margin: '6px 0 2px',
                        padding: '6px 10px',
                        borderRadius: 6,
                        cursor: 'pointer',
                        display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 4,
                        fontSize: 11, color: 'rgba(255,255,255,0.5)',
                        border: '1px dashed rgba(255,255,255,0.1)',
                        transition: 'all 0.15s',
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.background = 'rgba(255,255,255,0.05)'
                        e.currentTarget.style.color = '#e2e8f0'
                        e.currentTarget.style.borderColor = 'rgba(255,255,255,0.2)'
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.background = 'transparent'
                        e.currentTarget.style.color = 'rgba(255,255,255,0.5)'
                        e.currentTarget.style.borderColor = 'rgba(255,255,255,0.1)'
                      }}
                    >
                      {sessionsExpanded ? <UpOutlined style={{ fontSize: 9 }} /> : <DownOutlined style={{ fontSize: 9 }} />}
                      {sessionsExpanded ? '收起对话' : `展开 ${sessions.length - 3} 条历史`}
                    </div>
                  )}
                </>
              )}
            </div>
          </div>
        ) : (
          <div style={{ flex: 1 }} />
        )}

        {/* ══════ ④ 用户信息（贴底）══════ */}
        {!collapsed && (
          <div
            style={{
              flexShrink: 0,
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
        </div>
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
        centered
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
