import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Form, Input, Button, Typography, message } from 'antd'
import { UserOutlined, LockOutlined, SafetyCertificateOutlined } from '@ant-design/icons'
import { useAuthStore } from '@/store/useAuthStore'
import type { LoginData } from '@/services/auth'

const { Text, Title } = Typography

export default function Login() {
  const navigate = useNavigate()
  const login = useAuthStore((state) => state.login)
  const [loading, setLoading] = useState(false)

  const onFinish = async (values: LoginData) => {
    setLoading(true)
    try {
      await login(values)
      message.success('登录成功')
      navigate('/')
    } catch (error: any) {
      message.error(error.response?.data?.detail || '登录失败，请检查用户名和密码')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div
      style={{
        display: 'flex',
        minHeight: '100vh',
        background: '#f5f6f8',
      }}
    >
      {/* 左侧品牌展示区 */}
      <div
        style={{
          flex: 1,
          background: 'linear-gradient(135deg, #0f1a2e 0%, #1e3a5f 50%, #162240 100%)',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'center',
          alignItems: 'center',
          padding: '60px 40px',
          position: 'relative',
          overflow: 'hidden',
        }}
      >
        {/* 装饰光晕 */}
        <div
          style={{
            position: 'absolute',
            top: '-20%',
            right: '-10%',
            width: '60%',
            height: '60%',
            background: 'radial-gradient(circle, rgba(201,149,43,0.08) 0%, transparent 70%)',
            borderRadius: '50%',
            pointerEvents: 'none',
          }}
        />
        <div
          style={{
            position: 'absolute',
            bottom: '-10%',
            left: '-10%',
            width: '50%',
            height: '50%',
            background: 'radial-gradient(circle, rgba(255,255,255,0.03) 0%, transparent 70%)',
            borderRadius: '50%',
            pointerEvents: 'none',
          }}
        />

        {/* 品牌标识 */}
        <div
          style={{
            width: 72,
            height: 72,
            borderRadius: 18,
            background: 'linear-gradient(135deg, #c9952b 0%, #e8b84b 100%)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            marginBottom: 28,
            boxShadow: '0 8px 32px rgba(201,149,43,0.25)',
          }}
        >
          <span style={{ color: '#0f1a2e', fontSize: 32, fontWeight: 700, fontFamily: "'Noto Serif SC', serif" }}>华</span>
        </div>

        <Title level={2} style={{ color: '#f1f5f9', fontFamily: "'Noto Serif SC', serif", fontSize: 28, fontWeight: 700, letterSpacing: 2, margin: 0, marginBottom: 8, textAlign: 'center' }}>
          华星资源
        </Title>
        <Text style={{ color: 'rgba(255,255,255,0.5)', fontSize: 13, letterSpacing: 3, textTransform: 'uppercase', marginBottom: 40 }}>
          HUA XING CONTRACT MANAGEMENT
        </Text>

        <div style={{ maxWidth: 360, textAlign: 'center' }}>
          <Text style={{ color: 'rgba(255,255,255,0.6)', fontSize: 14, lineHeight: 1.8, display: 'block' }}>
            两地车牌 · 车辆买卖 · 合同管理 · 智能服务
          </Text>
          <div style={{ marginTop: 24, display: 'flex', justifyContent: 'center', gap: 32 }}>
            {['合同管理', '付款跟踪', '智能问答'].map((item) => (
              <div key={item} style={{ textAlign: 'center' }}>
                <div style={{ width: 6, height: 6, borderRadius: '50%', background: '#c9952b', margin: '0 auto 8px' }} />
                <Text style={{ color: 'rgba(255,255,255,0.45)', fontSize: 12 }}>{item}</Text>
              </div>
            ))}
          </div>
        </div>

        <Text style={{ position: 'absolute', bottom: 32, color: 'rgba(255,255,255,0.15)', fontSize: 11, letterSpacing: 0.5 }}>
          &copy; 2026 华星资源开发有限公司
        </Text>
      </div>

      {/* 右侧登录表单 */}
      <div style={{ width: 460, display: 'flex', flexDirection: 'column', justifyContent: 'center', padding: '60px 48px', background: '#ffffff' }}>
        <div style={{ maxWidth: 340, margin: '0 auto', width: '100%' }}>
          <Title level={3} style={{ fontSize: 22, fontWeight: 700, color: '#0f172a', marginBottom: 4, fontFamily: "'Noto Sans SC', sans-serif" }}>
            登录系统
          </Title>
          <Text style={{ color: '#94a3b8', fontSize: 14, display: 'block', marginBottom: 40 }}>
            请输入您的账号和密码登录
          </Text>

          <Form name="login" onFinish={onFinish} autoComplete="off" layout="vertical" size="large" requiredMark={false}>
            <Form.Item name="username" rules={[{ required: true, message: '请输入用户名' }]} style={{ marginBottom: 24 }}>
              <Input
                prefix={<UserOutlined style={{ color: '#94a3b8', fontSize: 15 }} />}
                placeholder="用户名"
                style={{ height: 48, borderRadius: 8, paddingLeft: 12, borderColor: '#e2e5ea' }}
              />
            </Form.Item>

            <Form.Item name="password" rules={[{ required: true, message: '请输入密码' }]} style={{ marginBottom: 32 }}>
              <Input.Password
                prefix={<LockOutlined style={{ color: '#94a3b8', fontSize: 15 }} />}
                placeholder="密码"
                style={{ height: 48, borderRadius: 8, paddingLeft: 12, borderColor: '#e2e5ea' }}
              />
            </Form.Item>

            <Form.Item style={{ marginBottom: 16 }}>
              <Button
                type="primary"
                htmlType="submit"
                loading={loading}
                block
                style={{ height: 48, borderRadius: 8, fontSize: 15, fontWeight: 600, background: '#1e3a5f', borderColor: '#1e3a5f', boxShadow: '0 4px 14px rgba(30,58,95,0.25)' }}
              >
                登 录
              </Button>
            </Form.Item>

            <div style={{ textAlign: 'center' }}>
              <SafetyCertificateOutlined style={{ color: '#c0c5ce', marginRight: 6, fontSize: 12 }} />
              <span style={{ color: '#94a3b8', fontSize: 12 }}>安全登录 · 数据加密传输</span>
            </div>
          </Form>
        </div>
      </div>
    </div>
  )
}
