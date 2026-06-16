import { useState, useEffect } from 'react'
import { Button, Modal, Form, Input, Select, message, Popconfirm, Empty, Spin } from 'antd'
import {
  BankOutlined,
  PlusOutlined,
  DeleteOutlined,
  CopyOutlined,
  CheckOutlined,
  AlipayOutlined,
  WechatOutlined,
} from '@ant-design/icons'
import { useAuthStore } from '@/store/useAuthStore'
import { paymentAccountApi, PaymentAccount } from '@/services/paymentAccount'

const accountTypeMap: Record<string, { label: string; icon: React.ReactNode }> = {
  bank: { label: '银行', icon: <BankOutlined /> },
  alipay: { label: '支付宝', icon: <AlipayOutlined /> },
  wechat: { label: '微信', icon: <WechatOutlined /> },
  other: { label: '其他', icon: <BankOutlined /> },
}

export default function PaymentAccounts() {
  const user = useAuthStore((s) => s.user)
  const role = user?.role || ''
  const isAdmin = role === 'admin'

  const [accounts, setAccounts] = useState<PaymentAccount[]>([])
  const [loading, setLoading] = useState(true)
  const [addModalOpen, setAddModalOpen] = useState(false)
  const [form] = Form.useForm()
  const [copiedField, setCopiedField] = useState<string | null>(null)

  const fetchAccounts = async () => {
    try {
      setLoading(true)
      const data = await paymentAccountApi.list()
      setAccounts(data)
    } catch (e: any) {
      message.error('加载收款账户失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchAccounts()
  }, [])

  const handleCopy = async (text: string, field: string) => {
    try {
      await navigator.clipboard.writeText(text)
      setCopiedField(field)
      message.success('已复制到剪贴板')
      setTimeout(() => setCopiedField(null), 2000)
    } catch {
      message.error('复制失败')
    }
  }

  const handleDelete = async (id: number) => {
    try {
      await paymentAccountApi.delete(id)
      message.success('账户已删除')
      fetchAccounts()
    } catch (e: any) {
      message.error(e.response?.data?.detail || '删除失败')
    }
  }

  const handleAdd = () => {
    form.validateFields().then(async (values) => {
      try {
        await paymentAccountApi.create({
          name: values.name,
          account_type: values.account_type,
          bank_name: values.bank_name,
          account_name: values.account_name,
          account_number: values.account_number,
          branch: values.branch,
          address: values.address,
          phone: values.phone,
          swift_code: values.swift_code,
          fps_id: values.fps_id,
        })
        setAddModalOpen(false)
        form.resetFields()
        message.success('账户已添加')
        fetchAccounts()
      } catch (e: any) {
        message.error(e.response?.data?.detail || '添加失败')
      }
    })
  }

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: 400 }}>
        <Spin size="large" />
      </div>
    )
  }

  return (
    <div style={{ padding: '24px', maxWidth: 960, margin: '0 auto' }}>
      {/* 页面标题 */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <div>
          <h2 style={{ margin: 0, fontSize: 20, fontWeight: 600, color: 'var(--text-primary)' }}>
            <BankOutlined style={{ marginRight: 8, color: 'var(--brand-gold)' }} />
            收款账户
          </h2>
          <p style={{ margin: '4px 0 0', fontSize: 13, color: 'var(--text-tertiary)' }}>
            公司收款银行账户信息，供客户付款时参考
          </p>
        </div>
        {isAdmin && (
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => setAddModalOpen(true)}
          >
            添加账户
          </Button>
        )}
      </div>

      {/* 账户列表 */}
      {accounts.length === 0 ? (
        <Empty description="暂无收款账户" />
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {accounts.map((account) => {
            const typeInfo = accountTypeMap[account.account_type] || accountTypeMap.other
            return (
              <div
                key={account.id}
                style={{
                  background: '#fff',
                  borderRadius: 12,
                  border: '1px solid var(--border-light)',
                  overflow: 'hidden',
                }}
              >
                {/* 银行头部 */}
                <div
                  style={{
                    padding: '16px 20px',
                    background: 'linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%)',
                    borderBottom: '1px solid var(--border-light)',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                    <div
                      style={{
                        width: 40,
                        height: 40,
                        borderRadius: 10,
                        background: 'linear-gradient(135deg, #1e3a5f 0%, #2d5b8a 100%)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        color: '#fff',
                        fontSize: 18,
                      }}
                    >
                      {typeInfo.icon}
                    </div>
                    <div>
                      <div style={{ fontSize: 16, fontWeight: 600, color: 'var(--text-primary)' }}>
                        {account.bank_name || typeInfo.label}
                      </div>
                      <div style={{ fontSize: 13, color: 'var(--text-secondary)', marginTop: 2 }}>
                        {account.account_name}
                      </div>
                    </div>
                    {account.is_default && (
                      <span style={{
                        fontSize: 11,
                        fontWeight: 600,
                        color: 'var(--brand-gold)',
                        background: 'rgba(201, 149, 43, 0.1)',
                        border: '1px solid rgba(201, 149, 43, 0.3)',
                        padding: '2px 8px',
                        borderRadius: 4,
                      }}>
                        默认
                      </span>
                    )}
                  </div>
                  {isAdmin && (
                    <Popconfirm
                      title="确定删除此账户？"
                      onConfirm={() => handleDelete(account.id)}
                      okText="删除"
                      cancelText="取消"
                      okButtonProps={{ danger: true }}
                    >
                      <Button
                        type="text"
                        danger
                        icon={<DeleteOutlined />}
                        size="small"
                      />
                    </Popconfirm>
                  )}
                </div>

                {/* 账户详情 */}
                <div style={{ padding: '16px 20px' }}>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 16 }}>
                    {/* 账号 */}
                    {account.account_number && (
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <span style={{ fontSize: 13, color: 'var(--text-tertiary)', minWidth: 60 }}>账号</span>
                        <span style={{ fontSize: 15, fontWeight: 600, color: 'var(--text-primary)', fontFamily: 'monospace', letterSpacing: 1 }}>
                          {account.account_number}
                        </span>
                        <Button
                          type="text"
                          size="small"
                          icon={copiedField === `account-${account.id}` ? <CheckOutlined /> : <CopyOutlined />}
                          onClick={() => handleCopy(account.account_number!, `account-${account.id}`)}
                          style={{ color: copiedField === `account-${account.id}` ? '#52c41a' : 'var(--text-tertiary)' }}
                        />
                      </div>
                    )}

                    {/* 转数快 FPS */}
                    {account.fps_id && (
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <span style={{ fontSize: 13, color: 'var(--text-tertiary)', minWidth: 60 }}>转数快</span>
                        <span style={{ fontSize: 15, fontWeight: 600, color: 'var(--text-primary)', fontFamily: 'monospace', letterSpacing: 1 }}>
                          {account.fps_id}
                        </span>
                        <Button
                          type="text"
                          size="small"
                          icon={copiedField === `fps-${account.id}` ? <CheckOutlined /> : <CopyOutlined />}
                          onClick={() => handleCopy(account.fps_id!, `fps-${account.id}`)}
                          style={{ color: copiedField === `fps-${account.id}` ? '#52c41a' : 'var(--text-tertiary)' }}
                        />
                      </div>
                    )}

                    {/* 网点 */}
                    {account.branch && (
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <span style={{ fontSize: 13, color: 'var(--text-tertiary)', minWidth: 60 }}>网点</span>
                        <span style={{ fontSize: 14, color: 'var(--text-primary)' }}>
                          {account.branch}
                        </span>
                      </div>
                    )}

                    {/* 地址 */}
                    {account.address && (
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <span style={{ fontSize: 13, color: 'var(--text-tertiary)', minWidth: 60 }}>地址</span>
                        <span style={{ fontSize: 14, color: 'var(--text-primary)' }}>
                          {account.address}
                        </span>
                      </div>
                    )}

                    {/* 电话 */}
                    {account.phone && (
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <span style={{ fontSize: 13, color: 'var(--text-tertiary)', minWidth: 60 }}>电话</span>
                        <span style={{ fontSize: 14, color: 'var(--text-primary)' }}>
                          {account.phone}
                        </span>
                      </div>
                    )}

                    {/* SWIFT */}
                    {account.swift_code && (
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <span style={{ fontSize: 13, color: 'var(--text-tertiary)', minWidth: 60 }}>SWIFT</span>
                        <span style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)', fontFamily: 'monospace' }}>
                          {account.swift_code}
                        </span>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* 添加账户弹窗 */}
      <Modal
        title="添加收款账户"
        open={addModalOpen}
        onOk={handleAdd}
        onCancel={() => {
          setAddModalOpen(false)
          form.resetFields()
        }}
        okText="添加"
        cancelText="取消"
        destroyOnClose
      >
        <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item
            name="account_type"
            label="账户类型"
            rules={[{ required: true, message: '请选择账户类型' }]}
            initialValue="bank"
          >
            <Select
              options={[
                { value: 'bank', label: '银行' },
                { value: 'alipay', label: '支付宝' },
                { value: 'wechat', label: '微信' },
                { value: 'other', label: '其他' },
              ]}
            />
          </Form.Item>
          <Form.Item
            name="name"
            label="账户名称"
            rules={[{ required: true, message: '请输入账户名称' }]}
            tooltip="展示用名称，如：高山贸易有限公司-华侨银行"
          >
            <Input placeholder="如：高山贸易有限公司-华侨银行" />
          </Form.Item>
          <Form.Item
            name="account_name"
            label="户名"
            rules={[{ required: true, message: '请输入户名' }]}
          >
            <Input placeholder="如：高山貿易有限公司" />
          </Form.Item>
          <Form.Item
            name="bank_name"
            label="银行/平台名称"
          >
            <Input placeholder="如：华侨银行、支付宝" />
          </Form.Item>
          <Form.Item name="account_number" label="银行账号">
            <Input placeholder="如：035-803-185706051" />
          </Form.Item>
          <Form.Item name="fps_id" label="转数快 FPS ID">
            <Input placeholder="可选" />
          </Form.Item>
          <Form.Item name="branch" label="网点">
            <Input placeholder="可选" />
          </Form.Item>
          <Form.Item name="address" label="网点地址">
            <Input placeholder="可选" />
          </Form.Item>
          <Form.Item name="phone" label="联系电话">
            <Input placeholder="可选" />
          </Form.Item>
          <Form.Item name="swift_code" label="SWIFT Code">
            <Input placeholder="可选（国际汇款需要）" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
