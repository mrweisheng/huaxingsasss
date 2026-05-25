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

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/" element={<ProtectedRoute><Layout /></ProtectedRoute>}>
          <Route index element={<Navigate to="/customers" replace />} />
          <Route path="customers">
            <Route index element={<CustomerList />} />
            <Route path="new" element={<CustomerNew />} />
            <Route path=":id" element={<CustomerDetail />} />
          </Route>
          <Route path="contracts">
            <Route index element={<ContractList />} />
            <Route path=":id" element={<ContractDetail />} />
            <Route path="upload" element={<ContractUpload />} />
          </Route>
          <Route path="payments">
            <Route index element={<PaymentList />} />
          </Route>
          <Route path="agent" element={<AgentChat />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

export default App
