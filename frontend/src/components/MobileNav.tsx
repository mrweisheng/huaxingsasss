import { useNavigate, useLocation } from 'react-router-dom'
import {
  TeamOutlined,
  FileTextOutlined,
  DollarOutlined,
  RobotOutlined,
} from '@ant-design/icons'
import './MobileNav.css'

interface MobileNavProps {
  role: string
}

interface NavTab {
  key: string
  icon: React.ReactNode
  label: string
  roles: string[]
}

const tabs: NavTab[] = [
  {
    key: '/customers',
    icon: <TeamOutlined />,
    label: '客户',
    roles: ['admin', 'income', 'expense'],
  },
  {
    key: '/contracts',
    icon: <FileTextOutlined />,
    label: '合同',
    roles: ['admin', 'income', 'expense'],
  },
  {
    key: '/payments',
    icon: <DollarOutlined />,
    label: '收付',
    roles: ['admin', 'income', 'expense'],
  },
  {
    key: '/agent',
    icon: <RobotOutlined />,
    label: '问答',
    roles: ['admin', 'income', 'expense'],
  },
]

/** 根据角色返回对应支付 Tab 的显示名称 */
function getPaymentLabel(role: string): string {
  if (role === 'expense') return '支出'
  if (role === 'income') return '收入'
  return '收付'
}

export default function MobileNav({ role }: MobileNavProps) {
  const navigate = useNavigate()
  const location = useLocation()

  const visibleTabs = tabs.filter((t) => t.roles.includes(role))

  if (visibleTabs.length === 0) return null

  return (
    <nav className="mobile-bottom-nav" role="tablist" aria-label="主导航">
      {visibleTabs.map((tab) => {
        const isActive =
          location.pathname === tab.key ||
          location.pathname.startsWith(tab.key + '/')
        return (
          <button
            key={tab.key}
            className={`mobile-nav-item${isActive ? ' active' : ''}`}
            onClick={() => navigate(tab.key)}
            role="tab"
            aria-selected={isActive}
            aria-label={tab.label}
          >
            <span className="mobile-nav-icon">{tab.icon}</span>
            <span className="mobile-nav-label">
              {tab.key === '/payments' ? getPaymentLabel(role) : tab.label}
            </span>
            {isActive && <span className="mobile-nav-indicator" />}
          </button>
        )
      })}
    </nav>
  )
}
