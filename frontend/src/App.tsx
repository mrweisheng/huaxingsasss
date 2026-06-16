import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import Layout from './components/Layout'
import ProtectedRoute from './components/ProtectedRoute'
import Login from './pages/Login'
import CustomerList from './pages/CustomerList'
import CustomerDetail from './pages/CustomerDetail'
import ContractList from './pages/ContractList'
import ContractDetail from './pages/ContractDetail'
import PaymentList from './pages/PaymentList'
import FinancialOverview from './pages/FinancialOverview'
import AgentChat from './pages/AgentChat'
import UserList from './pages/UserList'
import PaymentAccounts from './pages/PaymentAccounts'
import { useAuthStore } from './store/useAuthStore'

// 登录后默认进入小星助手（核心 AI 入口）
const ROLE_DEFAULT_PATH: Record<string, string> = {
  admin: '/agent',
  income: '/agent',
  expense: '/agent',
}

function App() {
  const role = useAuthStore((s) => s.user?.role) || ''

  // 根据角色决定默认跳转页
  const defaultPath = ROLE_DEFAULT_PATH[role] || '/customers'

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/" element={<ProtectedRoute><Layout /></ProtectedRoute>}>
          <Route index element={<Navigate to={defaultPath} replace />} />
          <Route path="customers">
            <Route index element={<ProtectedRoute allowedRoles={['admin', 'income']}><CustomerList /></ProtectedRoute>} />
            <Route path=":id" element={<ProtectedRoute allowedRoles={['admin', 'income']}><CustomerDetail /></ProtectedRoute>} />
          </Route>
          <Route path="contracts">
            <Route index element={<ProtectedRoute allowedRoles={['admin', 'income']}><ContractList /></ProtectedRoute>} />
            <Route path=":id" element={<ContractDetail />} />
          </Route>
          <Route path="payments">
            <Route index element={<PaymentList />} />
          </Route>
          <Route path="financial-overview" element={<ProtectedRoute allowedRoles={['admin']}><FinancialOverview /></ProtectedRoute>} />
          <Route path="users">
            <Route index element={<ProtectedRoute allowedRoles={['admin']}><UserList /></ProtectedRoute>} />
          </Route>
          <Route path="payment-accounts" element={<ProtectedRoute allowedRoles={['admin']}><PaymentAccounts /></ProtectedRoute>} />
          <Route path="agent" element={<AgentChat />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

export default App
