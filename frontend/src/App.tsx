import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import Layout from './components/Layout'
import ProtectedRoute from './components/ProtectedRoute'
import Login from './pages/Login'
import CustomerList from './pages/CustomerList'
import CustomerNew from './pages/CustomerNew'
import CustomerDetail from './pages/CustomerDetail'
import ContractList from './pages/ContractList'
import ContractDetail from './pages/ContractDetail'
import ContractUpload from './pages/ContractUpload'
import PaymentList from './pages/PaymentList'
import AgentChat from './pages/AgentChat'
import UserList from './pages/UserList'
import { useAuthStore } from './store/useAuthStore'

function App() {
  const role = useAuthStore((s) => s.user?.role) || ''

  // 根据角色决定默认跳转页
  const defaultPath = (role === 'admin' || role === 'income') ? '/customers' : '/payments'

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/" element={<ProtectedRoute><Layout /></ProtectedRoute>}>
          <Route index element={<Navigate to={defaultPath} replace />} />
          <Route path="customers">
            <Route index element={<ProtectedRoute allowedRoles={['admin', 'income']}><CustomerList /></ProtectedRoute>} />
            <Route path="new" element={<ProtectedRoute allowedRoles={['admin', 'income']}><CustomerNew /></ProtectedRoute>} />
            <Route path=":id" element={<ProtectedRoute allowedRoles={['admin', 'income']}><CustomerDetail /></ProtectedRoute>} />
          </Route>
          <Route path="contracts">
            <Route index element={<ProtectedRoute allowedRoles={['admin', 'income']}><ContractList /></ProtectedRoute>} />
            <Route path=":id" element={<ContractDetail />} />
            <Route path="upload" element={<ProtectedRoute allowedRoles={['admin', 'income']}><ContractUpload /></ProtectedRoute>} />
          </Route>
          <Route path="payments">
            <Route index element={<PaymentList />} />
          </Route>
          <Route path="users">
            <Route index element={<ProtectedRoute allowedRoles={['admin']}><UserList /></ProtectedRoute>} />
          </Route>
          <Route path="agent" element={<AgentChat />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

export default App
