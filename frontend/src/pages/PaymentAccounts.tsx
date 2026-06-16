import { useState, useEffect } from 'react'
import { Button, Modal, Form, Input, Select, Switch, InputNumber, message, Popconfirm, Empty, Spin } from 'antd'
import {
  BankOutlined,
  PlusOutlined,
  DeleteOutlined,
  CopyOutlined,
  CheckOutlined,
} from '@ant-design/icons'
import { useAuthStore } from '@/store/useAuthStore'
import { paymentAccountApi, PaymentAccount } from '@/services/paymentAccount'

const TYPE_OPTIONS = [
  { value: 'bank', label: '银行' },
  { value: 'alipay', label: '支付宝' },
  { value: 'wechat', label: '微信' },
  { value: 'other', label: '其他' },
]

export default function PaymentAccounts() {
  const user = useAuthStore((s) => s.user)
  const role = user?.role || ''
  const isAdmin = role === 'admin'

  const [accounts, setAccounts] = useState<PaymentAccount[]>([])
  const [loading, setLoading] = useState(true)
  const [addModalOpen, setAddModalOpen] = useState(false)
  const [form] = Form.useForm()
  const [copiedField, setCopiedField] = useState<string | null>(null)
  const [accountType, setAccountType] = useState<string>('bank')

  const fetchAccounts = async () => {
    try {
      setLoading(true)
      const data = await paymentAccountApi.list()
      setAccounts(data)
    } catch {
      message.error('加载失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchAccounts() }, [])

  const handleCopy = async (text: string, field: string) => {
    try {
      await navigator.clipboard.writeText(text)
      setCopiedField(field)
      message.success('已复制')
      setTimeout(() => setCopiedField(null), 2000)
    } catch {
      message.error('复制失败')
    }
  }

  const handleDelete = async (id: number) => {
    try {
      await paymentAccountApi.delete(id)
      message.success('已删除')
      fetchAccounts()
    } catch (e: any) {
      message.error(e.response?.data?.detail || '删除失败')
    }
  }

  const handleAdd = () => {
    form.validateFields().then(async (values) => {
      try {
        await paymentAccountApi.create({
          account_type: values.account_type,
          title: values.title,
          account_name: values.account_name,
          account_number: values.account_number || undefined,
          qr_code_url: values.qr_code_url || undefined,
          fps_id: values.fps_id || undefined,
          bank_name: values.bank_name || undefined,
          branch: values.branch || undefined,
          address: values.address || undefined,
          phone: values.phone || undefined,
          swift_code: values.swift_code || undefined,
          is_default: values.is_default || false,
          sort_order: values.sort_order || 0,
        })
        setAddModalOpen(false)
        form.resetFields()
        message.success('已添加')
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
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <div>
          <h2 style={{ margin: 0, fontSize: 20, fontWeight: 600 }}>
            <BankOutlined style={{ marginRight: 8, color: 'var(--brand-gold)' }} />
            收款账户
          </h2>
          <p style={{ margin: '4px 0 0', fontSize: 13, color: 'var(--text-tertiary)' }}>
            支持银行、支付宝、微信等多种收款方式
          </p>
        </div>
        {isAdmin && (
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setAddModalOpen(true)}>
            添加账户
          </Button>
        )}
      </div>

      {accounts.length === 0 ? (
        <Empty description="暂无收款账户" />
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {accounts.map((account) => (
            <div
              key={account.id}
              style={{
                background: '#fff',
                borderRadius: 12,
                border: '1px solid var(--border-light)',
                overflow: 'hidden',
              }}
            >
              {/* 头部 */}
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
                      background: account.account_type === 'alipay' ? '#1677ff' : account.account_type === 'wechat' ? '#07c160' : 'linear-gradient(135deg, #1e3a5f 0%, #2d5b8a 100%)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      color: '#fff',
                      fontSize: 18,
                    }}
                  >
                    <BankOutlined />
                  </div>
                  <div>
                    <div style={{ fontSize: 16, fontWeight: 600 }}>{account.title}</div>
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
                    <Button type="text" danger icon={<DeleteOutlined />} size="small" />
                  </Popconfirm>
                )}
              </div>

              {/* 详情 */}
              <div style={{ padding: '16px 20px' }}>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 12 }}>
                  {account.account_number && (
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <span style={{ fontSize: 13, color: 'var(--text-tertiary)', minWidth: 50 }}>账号</span>
                      <span style={{ fontSize: 15, fontWeight: 600, fontFamily: 'monospace' }}>
                        {account.account_number}
                      </span>
                      <Button
                        type="text" size="small"
                        icon={copiedField === `acc-${account.id}` ? <CheckOutlined /> : <CopyOutlined />}
                        onClick={() => handleCopy(account.account_number!, `acc-${account.id}`)}
                        style={{ color: copiedField === `acc-${account.id}` ? '#52c41a' : 'var(--text-tertiary)' }}
                      />
                    </div>
                  )}
                  {account.fps_id && (
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <span style={{ fontSize: 13, color: 'var(--text-tertiary)', minWidth: 50 }}>转数快</span>
                      <span style={{ fontSize: 15, fontWeight: 600, fontFamily: 'monospace' }}>{account.fps_id}</span>
                      <Button
                        type="text" size="small"
                        icon={copiedField === `fps-${account.id}` ? <CheckOutlined /> : <CopyOutlined />}
                        onClick={() => handleCopy(account.fps_id!, `fps-${account.id}`)}
                        style={{ color: copiedField === `fps-${account.id}` ? '#52c41a' : 'var(--text-tertiary)' }}
                      />
                    </div>
                  )}
                  {account.branch && (
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <span style={{ fontSize: 13, color: 'var(--text-tertiary)', minWidth: 50 }}>网点</span>
                      <span style={{ fontSize: 14 }}>{account.branch}</span>
                    </div>
                  )}
                  {account.address && (
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <span style={{ fontSize: 13, color: 'var(--text-tertiary)', minWidth: 50 }}>地址</span>
                      <span style={{ fontSize: 14 }}>{account.address}</span>
                    </div>
                  )}
                  {account.phone && (
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <span style={{ fontSize: 13, color: 'var(--text-tertiary)', minWidth: 50 }}>电话</span>
                      <span style={{ fontSize: 14 }}>{account.phone}</span>
                    </div>
                  )}
                  {account.swift_code && (
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <span style={{ fontSize: 13, color: 'var(--text-tertiary)', minWidth: 50 }}>SWIFT</span>
                      <span style={{ fontSize: 14, fontWeight: 600, fontFamily: 'monospace' }}>{account.swift_code}</span>
                    </div>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* 添加弹窗 */}
      <Modal
        title="添加收款账户"
        open={addModalOpen}
        onOk={handleAdd}
        onCancel={() => { setAddModalOpen(false); form.resetFields(); setAccountType('bank') }}
        okText="添加"
        cancelText="取消"
        destroyOnClose
        width={520}
      >
        <Form form={form} layout="vertical" style={{ marginTop: 16 }} initialValues={{ account_type: 'bank' }}>
          <Form.Item name="account_type" label="账户类型" rules={[{ required: true }]}>
            <Select options={TYPE_OPTIONS} onChange={(v) => setAccountType(v)} />
          </Form.Item>
          <Form.Item name="title" label="标题" rules={[{ required: true, message: '请输入标题' }]}
            tooltip="展示用，如：华侨银行-高山贸易">
            <Input placeholder="如：华侨银行-高山贸易" />
          </Form.Item>
          <Form.Item name="account_name" label="户名" rules={[{ required: true, message: '请输入户名' }]}>
            <Input placeholder="如：高山貿易有限公司" />
          </Form.Item>
          <Form.Item name="account_number" label="账号">
            <Input placeholder="银行账号或支付宝账号" />
          </Form.Item>
          {accountType === 'bank' && (
            <>
              <Form.Item name="bank_name" label="银行名称">
                <Input placeholder="如：华侨银行" />
              </Form.Item>
              <Form.Item name="fps_id" label="转数快 FPS ID">
                <Input placeholder="可选" />
              </Form.Item>
              <Form.Item name="branch" label="网点">
                <Input placeholder="可选" />
              </Form.Item>
            </>
          )}
          {accountType === 'alipay' && (
            <Form.Item name="qr_code_url" label="收款码图片URL">
              <Input placeholder="支付宝收款码图片链接" />
            </Form.Item>
          )}
          {accountType === 'wechat' && (
            <Form.Item name="qr_code_url" label="收款码图片URL">
              <Input placeholder="微信收款码图片链接" />
            </Form.Item>
          )}
          <Form.Item name="address" label="地址">
            <Input placeholder="可选" />
          </Form.Item>
          <Form.Item name="phone" label="电话">
            <Input placeholder="可选" />
          </Form.Item>
          <div style={{ display: 'flex', gap: 16 }}>
            <Form.Item name="is_default" label="默认账户" valuePropName="checked">
              <Switch />
            </Form.Item>
            <Form.Item name="sort_order" label="排序" initialValue={0}>
              <InputNumber min={0} max={999} />
            </Form.Item>
          </div>
        </Form>
      </Modal>
    </div>
  )
}
