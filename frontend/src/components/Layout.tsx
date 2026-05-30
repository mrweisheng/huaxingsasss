import { Outlet, useNavigate, useLocation } from 'react-router-dom'
import { Layout as AntLayout, Menu } from 'antd'
import {
  UserOutlined,
  FileTextOutlined,
  DollarOutlined,
  RobotOutlined,
  LogoutOutlined,
} from '@ant-design/icons'
import { useAuthStore } from '@/store/useAuthStore'

const { Header, Sider, Content } = AntLayout

export default function Layout() {
  const navigate = useNavigate()
  const location = useLocation()
  const { user, logout } = useAuthStore()

  const role = user?.role || ''

  // 按角色显示菜单
  const menuItems = []

  // admin 和 income 显示客户管理和合同管理
  if (role === 'admin' || role === 'income') {
    menuItems.push({ key: '/customers', icon: <UserOutlined />, label: '客户管理' })
    menuItems.push({ key: '/contracts', icon: <FileTextOutlined />, label: '合同管理' })
  }

  // 付款管理：按角色显示不同标签
  const paymentLabel = role === 'expense' ? '支出管理' : role === 'income' ? '收入管理' : '收付管理'
  menuItems.push({ key: '/payments', icon: <DollarOutlined />, label: paymentLabel })

  // 所有角色都能用智能问答
  menuItems.push({ key: '/agent', icon: <RobotOutlined />, label: '智能问答' })

  const selectedKey = menuItems.find(item => location.pathname.startsWith(item.key + '/') || location.pathname === item.key)?.key || ''

  const handleMenuClick = ({ key }: { key: string }) => {
    navigate(key)
  }

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <AntLayout style={{ minHeight: '100vh' }}>
      <Sider width={200} theme="dark" style={{ height: '100vh', position: 'fixed', left: 0, top: 0 }}>
        <div style={{ padding: '16px', color: '#fff', fontSize: '18px', fontWeight: 'bold' }}>
          合同管理系统
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[selectedKey]}
          items={menuItems}
          onClick={handleMenuClick}
        />
      </Sider>
      <AntLayout style={{ marginLeft: 200, minHeight: '100vh' }}>
        <Header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: '#fff', padding: '0 24px', position: 'sticky', top: 0, zIndex: 1 }}>
          <span>欢迎，{user?.full_name || user?.username}</span>
          <a onClick={handleLogout} style={{ cursor: 'pointer' }}>
            <LogoutOutlined /> 退出登录
          </a>
        </Header>
        <Content style={{ margin: '24px 16px', padding: 24, background: '#fff', minHeight: 'calc(100vh - 64px - 48px)' }}>
          <Outlet />
        </Content>
      </AntLayout>
    </AntLayout>
  )
}
