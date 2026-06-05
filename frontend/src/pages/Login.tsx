import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Form, Input, Button, Typography, message } from 'antd'
import { UserOutlined, LockOutlined, SafetyCertificateOutlined } from '@ant-design/icons'
import { useAuthStore } from '@/store/useAuthStore'
import { authApi } from '@/services/auth'
import type { LoginData, PublicChangePasswordData } from '@/services/auth'

const { Text, Title } = Typography

export default function Login() {
  const navigate = useNavigate()
  const login = useAuthStore((state) => state.login)
  const [loading, setLoading] = useState(false)
  const [mounted, setMounted] = useState(false)
  const [shake, setShake] = useState(false)
  const [showChangePassword, setShowChangePassword] = useState(false)
  const [changePasswordLoading, setChangePasswordLoading] = useState(false)
  const [changePasswordForm] = Form.useForm()

  useEffect(() => {
    const raf = requestAnimationFrame(() => setMounted(true))
    return () => cancelAnimationFrame(raf)
  }, [])

  const onFinish = async (values: LoginData) => {
    setLoading(true)
    try {
      await login(values)
      message.success('登录成功')
      navigate('/')
    } catch (error: any) {
      setLoading(false)
      setShake(true)
      setTimeout(() => setShake(false), 500)
      message.error(error.response?.data?.detail || '登录失败，请检查用户名和密码')
    }
  }

  const onChangePassword = async (values: PublicChangePasswordData & { confirm_password: string }) => {
    if (values.new_password !== values.confirm_password) {
      message.error('两次输入的新密码不一致')
      return
    }
    setChangePasswordLoading(true)
    try {
      await authApi.changePasswordPublic({
        username: values.username,
        old_password: values.old_password,
        new_password: values.new_password,
      })
      message.success('密码修改成功，请使用新密码登录')
      setShowChangePassword(false)
      changePasswordForm.resetFields()
    } catch (error: any) {
      message.error(error.response?.data?.detail || '密码修改失败')
    } finally {
      setChangePasswordLoading(false)
    }
  }

  const anim = mounted
  const A = (name: string, dur = '0.5s', delay = 0) =>
    anim ? { animation: `${name} ${dur} ${delay}s cubic-bezier(0.22, 1, 0.36, 1) both` } : { opacity: 0 }

  return (
    <div
      style={{
        width: '100vw',
        height: '100vh',
        background: '#060b13',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        position: 'relative',
        overflow: 'hidden',
        fontFamily: "'Noto Sans SC', -apple-system, sans-serif",
      }}
    >
      {/* ═══ 背景层：4 个彩色光球（大气氛围，不抢戏） ═══ */}
      <div
        style={{
          position: 'absolute',
          width: '75vw', height: '75vw', maxWidth: 800, maxHeight: 800,
          borderRadius: '50%',
          background: 'radial-gradient(circle at 40% 40%, rgba(30,58,95,0.40) 0%, rgba(30,58,95,0.08) 40%, transparent 60%)',
          top: '-20%', left: '-15%',
          filter: 'blur(70px)',
          animation: anim ? 'l2Orb1 22s ease-in-out infinite' : 'none',
          pointerEvents: 'none',
        }}
      />
      <div
        style={{
          position: 'absolute',
          width: '65vw', height: '65vw', maxWidth: 650, maxHeight: 650,
          borderRadius: '50%',
          background: 'radial-gradient(circle at 55% 35%, rgba(201,149,43,0.25) 0%, rgba(201,149,43,0.05) 40%, transparent 60%)',
          top: '-12%', right: '-10%',
          filter: 'blur(60px)',
          animation: anim ? 'l2Orb2 20s ease-in-out infinite' : 'none',
          pointerEvents: 'none',
        }}
      />
      <div
        style={{
          position: 'absolute',
          width: '60vw', height: '60vw', maxWidth: 550, maxHeight: 550,
          borderRadius: '50%',
          background: 'radial-gradient(circle at 50% 50%, rgba(13,148,136,0.20) 0%, rgba(13,148,136,0.04) 40%, transparent 60%)',
          bottom: '-15%', left: '5%',
          filter: 'blur(55px)',
          animation: anim ? 'l2Orb3 24s ease-in-out infinite' : 'none',
          pointerEvents: 'none',
        }}
      />
      <div
        style={{
          position: 'absolute',
          width: '50vw', height: '50vw', maxWidth: 480, maxHeight: 480,
          borderRadius: '50%',
          background: 'radial-gradient(circle at 45% 55%, rgba(49,46,129,0.20) 0%, rgba(49,46,129,0.03) 40%, transparent 60%)',
          bottom: '-10%', right: '-5%',
          filter: 'blur(50px)',
          animation: anim ? 'l2Orb4 26s ease-in-out infinite' : 'none',
          pointerEvents: 'none',
        }}
      />

      {/* ═══ 卡片 ═══ */}
      <div
        style={{
          position: 'relative',
          zIndex: 2,
          ...A('l2CardAppear 0.9s 0.15s'),
          opacity: anim ? undefined : 0,
        }}
      >
        <div
          style={{
            width: 'min(420px, 90vw)',
            padding: '40px 32px 32px',
            borderRadius: 24,
            background: 'rgba(15,26,46,0.50)',
            backdropFilter: 'blur(32px)',
            WebkitBackdropFilter: 'blur(32px)',
            border: '1px solid rgba(255,255,255,0.06)',
            boxShadow: '0 25px 70px rgba(0,0,0,0.55), 0 0 0 1px rgba(201,149,43,0.08), 0 0 30px rgba(201,149,43,0.03)',
            ...(shake ? { animation: 'l2FormShake 0.45s ease-in-out' } : {}),
          }}
        >
          {/* ═══ Act 1：品牌认知 ═══ */}

          {/* Logo — 轻落定 */}
          <div
            style={{
              width: 56, height: 56, borderRadius: 14,
              background: 'linear-gradient(135deg, #c9952b 0%, #e8b84b 100%)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              margin: '0 auto 20px',
              boxShadow: '0 8px 36px rgba(201,149,43,0.35)',
              ...A('l2LogoLand', '0.55s', 0.25),
            }}
          >
            <span
              style={{
                color: '#0f1a2e', fontSize: 24, fontWeight: 700,
                fontFamily: "'Noto Serif SC', serif",
              }}
            >
              华
            </span>
          </div>

          {/* 公司名称 */}
          <Title
            level={2}
            style={{
              color: '#e2e8f0',
              fontFamily: "'Noto Serif SC', serif",
              fontSize: 26, fontWeight: 700, letterSpacing: 4,
              margin: 0, marginBottom: 8, textAlign: 'center',
              textShadow: '0 0 40px rgba(201,149,43,0.25)',
              ...A('l2StaggerUp', '0.5s', 0.35),
            }}
          >
            华星资源
          </Title>

          {/* 金色装饰线 — 中心展开 */}
          <div
            style={{
              height: 2, width: 44,
              background: 'linear-gradient(90deg, transparent, #c9952b 25%, #c9952b 75%, transparent)',
              margin: '0 auto 14px', borderRadius: 1,
              transformOrigin: 'center',
              ...A('l2AccentExpand', '0.45s', 0.4),
            }}
          />

          {/* 英文副标题 */}
          <Text
            style={{
              color: 'rgba(255,255,255,0.25)',
              fontSize: 12, letterSpacing: 3,
              display: 'block', textAlign: 'center', marginBottom: 22,
              ...A('l2StaggerUp', '0.4s', 0.45),
            }}
          >
            HUA XING CONTRACT MANAGEMENT
          </Text>

          {/* ═══ Act 2：业务说明 ═══ */}

          {/* 业务关键词 */}
          <Text
            style={{
              color: 'rgba(255,255,255,0.35)',
              fontSize: 13, lineHeight: 1.9,
              display: 'block', textAlign: 'center', marginBottom: 18,
              ...A('l2StaggerUp', '0.4s', 0.5),
            }}
          >
            两地车牌 · 车辆买卖 · 合同管理 · 智能服务
          </Text>

          {/* 特性圆点 */}
          <div
            style={{
              display: 'flex', justifyContent: 'center', gap: 36,
              marginBottom: 28,
            }}
          >
            {['合同管理', '付款跟踪', '智能问答'].map((item, i) => (
              <div
                key={item}
                style={{
                  textAlign: 'center',
                  ...A('l2StaggerUp', '0.35s', 0.52 + i * 0.06),
                }}
              >
                <div
                  style={{
                    width: 6, height: 6, borderRadius: '50%',
                    background: '#c9952b',
                    margin: '0 auto 8px',
                    animation: anim ? 'l2DotPulse 3s ease-in-out infinite' : 'none',
                    animationDelay: `${i * 0.4}s`,
                  }}
                />
                <Text
                  style={{ color: 'rgba(255,255,255,0.28)', fontSize: 11 }}
                >
                  {item}
                </Text>
              </div>
            ))}
          </div>

          {/* ═══ Act 3：开始操作 ═══ */}

          {/* 分割线 */}
          <div
            style={{
              height: 1, marginBottom: 24,
              background: 'linear-gradient(90deg, transparent, rgba(255,255,255,0.04), transparent)',
              ...A('l2AccentExpand', '0.4s', 0.7),
            }}
          />

          {/* 表单标题 */}
          <Text
            style={{
              color: 'rgba(255,255,255,0.35)',
              fontSize: 13, letterSpacing: 2,
              display: 'block', textAlign: 'center', marginBottom: 24,
              ...A('l2StaggerUp', '0.4s', 0.75),
            }}
          >
            {showChangePassword ? '修改密码' : '登录系统'}
          </Text>

          {/* 登录表单 */}
          {!showChangePassword && (
            <Form
              name="login"
              onFinish={onFinish}
              autoComplete="off"
              layout="vertical"
              size="large"
              requiredMark={false}
              className="l2-login-form"
            >
              {/* 用户名 */}
              <Form.Item
                name="username"
                rules={[{ required: true, message: '请输入用户名' }]}
                style={{
                  marginBottom: 18,
                  ...A('l2StaggerUp', '0.4s', 0.8),
                }}
              >
                <div className="l2-glass-input">
                  <Input
                    prefix={<UserOutlined />}
                    placeholder="用户名"
                    style={{ height: 48, paddingLeft: 12 }}
                  />
                </div>
              </Form.Item>

              {/* 密码 */}
              <Form.Item
                name="password"
                rules={[{ required: true, message: '请输入密码' }]}
                style={{
                  marginBottom: 24,
                  ...A('l2StaggerUp', '0.4s', 0.85),
                }}
              >
                <div className="l2-glass-input">
                  <Input.Password
                    prefix={<LockOutlined />}
                    placeholder="密码"
                    style={{ height: 48, paddingLeft: 12 }}
                  />
                </div>
              </Form.Item>

              {/* 登录按钮 */}
              <Form.Item
                style={{
                  marginBottom: 14,
                  ...A('l2StaggerUp', '0.4s', 0.9),
                }}
              >
                <Button
                  type="primary"
                  htmlType="submit"
                  loading={loading}
                  block
                  className="l2-btn-gold"
                  style={{
                    height: 48, borderRadius: 12,
                    fontSize: 16, fontWeight: 600, letterSpacing: 3,
                    background: 'linear-gradient(135deg, #c9952b 0%, #e8b84b 100%)',
                    border: 'none',
                    color: '#0f1a2e',
                  }}
                >
                  登 录
                </Button>
              </Form.Item>

              {/* 修改密码链接 */}
              <div style={{ textAlign: 'center', marginBottom: 14 }}>
                <Button
                  type="link"
                  size="small"
                  onClick={() => setShowChangePassword(true)}
                  style={{ color: 'rgba(201,149,43,0.7)', fontSize: 13, padding: 0 }}
                >
                  修改密码
                </Button>
              </div>

              {/* 安全提示 */}
              <div
                style={{
                  textAlign: 'center',
                  ...A('l2StaggerUp', '0.4s', 0.95),
                }}
              >
                <SafetyCertificateOutlined
                  style={{ color: 'rgba(255,255,255,0.12)', marginRight: 6, fontSize: 11 }}
                />
                <span style={{ color: 'rgba(255,255,255,0.12)', fontSize: 11 }}>
                  安全登录 · 数据加密传输
                </span>
              </div>
            </Form>
          )}

          {/* 修改密码表单 */}
          {showChangePassword && (
            <Form
              form={changePasswordForm}
              name="changePassword"
              onFinish={onChangePassword}
              autoComplete="off"
              layout="vertical"
              size="large"
              requiredMark={false}
              className="l2-login-form"
            >
              {/* 用户名 */}
              <Form.Item
                name="username"
                rules={[{ required: true, message: '请输入用户名' }]}
                style={{
                  marginBottom: 14,
                  ...A('l2StaggerUp', '0.4s', 0.8),
                }}
              >
                <div className="l2-glass-input">
                  <Input
                    prefix={<UserOutlined />}
                    placeholder="用户名"
                    style={{ height: 48, paddingLeft: 12 }}
                  />
                </div>
              </Form.Item>

              {/* 旧密码 */}
              <Form.Item
                name="old_password"
                rules={[{ required: true, message: '请输入旧密码' }]}
                style={{
                  marginBottom: 14,
                  ...A('l2StaggerUp', '0.4s', 0.85),
                }}
              >
                <div className="l2-glass-input">
                  <Input.Password
                    prefix={<LockOutlined />}
                    placeholder="旧密码"
                    style={{ height: 48, paddingLeft: 12 }}
                  />
                </div>
              </Form.Item>

              {/* 新密码 */}
              <Form.Item
                name="new_password"
                rules={[
                  { required: true, message: '请输入新密码' },
                  { min: 6, message: '密码至少 6 个字符' },
                ]}
                style={{
                  marginBottom: 14,
                  ...A('l2StaggerUp', '0.4s', 0.9),
                }}
              >
                <div className="l2-glass-input">
                  <Input.Password
                    prefix={<LockOutlined />}
                    placeholder="新密码（至少6位）"
                    style={{ height: 48, paddingLeft: 12 }}
                  />
                </div>
              </Form.Item>

              {/* 确认新密码 */}
              <Form.Item
                name="confirm_password"
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
                style={{
                  marginBottom: 20,
                  ...A('l2StaggerUp', '0.4s', 0.95),
                }}
              >
                <div className="l2-glass-input">
                  <Input.Password
                    prefix={<LockOutlined />}
                    placeholder="确认新密码"
                    style={{ height: 48, paddingLeft: 12 }}
                  />
                </div>
              </Form.Item>

              {/* 提交按钮 */}
              <Form.Item
                style={{
                  marginBottom: 14,
                  ...A('l2StaggerUp', '0.4s', 1.0),
                }}
              >
                <Button
                  type="primary"
                  htmlType="submit"
                  loading={changePasswordLoading}
                  block
                  className="l2-btn-gold"
                  style={{
                    height: 48, borderRadius: 12,
                    fontSize: 16, fontWeight: 600, letterSpacing: 3,
                    background: 'linear-gradient(135deg, #c9952b 0%, #e8b84b 100%)',
                    border: 'none',
                    color: '#0f1a2e',
                  }}
                >
                  确认修改
                </Button>
              </Form.Item>

              {/* 返回登录链接 */}
              <div style={{ textAlign: 'center', marginBottom: 14 }}>
                <Button
                  type="link"
                  size="small"
                  onClick={() => {
                    setShowChangePassword(false)
                    changePasswordForm.resetFields()
                  }}
                  style={{ color: 'rgba(201,149,43,0.7)', fontSize: 13, padding: 0 }}
                >
                  返回登录
                </Button>
              </div>

              {/* 安全提示 */}
              <div
                style={{
                  textAlign: 'center',
                  ...A('l2StaggerUp', '0.4s', 1.05),
                }}
              >
                <SafetyCertificateOutlined
                  style={{ color: 'rgba(255,255,255,0.12)', marginRight: 6, fontSize: 11 }}
                />
                <span style={{ color: 'rgba(255,255,255,0.12)', fontSize: 11 }}>
                  安全登录 · 数据加密传输
                </span>
              </div>
            </Form>
          )}
        </div>
      </div>

      {/* 底部版权 */}
      <Text
        style={{
          position: 'absolute', bottom: 36, zIndex: 2,
          color: 'rgba(255,255,255,0.06)', fontSize: 11,
          pointerEvents: 'none',
        }}
      >
        &copy; 2026 华星资源开发有限公司
      </Text>
    </div>
  )
}
