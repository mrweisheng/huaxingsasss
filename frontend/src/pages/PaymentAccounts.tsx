import { useState } from 'react'
import { Button, Modal, Form, Input, message, Popconfirm, Empty } from 'antd'
import {
  BankOutlined,
  PlusOutlined,
  DeleteOutlined,
  CopyOutlined,
  CheckOutlined,
} from '@ant-design/icons'
import { useAuthStore } from '@/store/useAuthStore'

interface PaymentAccount {
  id: string
  bankName: string
  accountName: string
  accountNumber: string
  branch?: string
  address?: string
  phone?: string
  swiftCode?: string
  fpsId?: string
}

const INITIAL_ACCOUNTS: PaymentAccount[] = [
  {
    id: '1',
    bankName: '华侨银行',
    accountName: '高山貿易有限公司',
    accountNumber: '035-803-185706051',
    fpsId: '122842800',
  },
  {
    id: '2',
    bankName: '工商银行',
    accountName: '陈振耀',
    accountNumber: '2009020501023937427',
    branch: '汕尾海丰东门头支行',
    address: '海丰县城人民中路7号',
    phone: '0660-6623712',
  },
]

export default function PaymentAccounts() {
  const user = useAuthStore((s) => s.user)
  const role = user?.role || ''
  const isAdmin = role === 'admin'

  const [accounts, setAccounts] = useState<PaymentAccount[]>(INITIAL_ACCOUNTS)
  const [addModalOpen, setAddModalOpen] = useState(false)
  const [form] = Form.useForm()
  const [copiedField, setCopiedField] = useState<string | null>(null)

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

  const handleDelete = (id: string) => {
    setAccounts((prev) => prev.filter((a) => a.id !== id))
    message.success('账户已删除')
  }

  const handleAdd = () => {
    form.validateFields().then((values) => {
      const newAccount: PaymentAccount = {
        id: Date.now().toString(),
        bankName: values.bankName,
        accountName: values.accountName,
        accountNumber: values.accountNumber,
        branch: values.branch || undefined,
        address: values.address || undefined,
        phone: values.phone || undefined,
        swiftCode: values.swiftCode || undefined,
        fpsId: values.fpsId || undefined,
      }
      setAccounts((prev) => [...prev, newAccount])
      setAddModalOpen(false)
      form.resetFields()
      message.success('账户已添加')
    })
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
                    <BankOutlined />
                  </div>
                  <div>
                    <div style={{ fontSize: 16, fontWeight: 600, color: 'var(--text-primary)' }}>
                      {account.bankName}
                    </div>
                    <div style={{ fontSize: 13, color: 'var(--text-secondary)', marginTop: 2 }}>
                      {account.accountName}
                    </div>
                  </div>
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
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span style={{ fontSize: 13, color: 'var(--text-tertiary)', minWidth: 60 }}>账号</span>
                    <span style={{ fontSize: 15, fontWeight: 600, color: 'var(--text-primary)', fontFamily: 'monospace', letterSpacing: 1 }}>
                      {account.accountNumber}
                    </span>
                    <Button
                      type="text"
                      size="small"
                      icon={copiedField === `account-${account.id}` ? <CheckOutlined /> : <CopyOutlined />}
                      onClick={() => handleCopy(account.accountNumber, `account-${account.id}`)}
                      style={{ color: copiedField === `account-${account.id}` ? '#52c41a' : 'var(--text-tertiary)' }}
                    />
                  </div>

                  {/* 转数快 FPS */}
                  {account.fpsId && (
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <span style={{ fontSize: 13, color: 'var(--text-tertiary)', minWidth: 60 }}>转数快</span>
                      <span style={{ fontSize: 15, fontWeight: 600, color: 'var(--text-primary)', fontFamily: 'monospace', letterSpacing: 1 }}>
                        {account.fpsId}
                      </span>
                      <Button
                        type="text"
                        size="small"
                        icon={copiedField === `fps-${account.id}` ? <CheckOutlined /> : <CopyOutlined />}
                        onClick={() => handleCopy(account.fpsId!, `fps-${account.id}`)}
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
                  {account.swiftCode && (
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <span style={{ fontSize: 13, color: 'var(--text-tertiary)', minWidth: 60 }}>SWIFT</span>
                      <span style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)', fontFamily: 'monospace' }}>
                        {account.swiftCode}
                      </span>
                    </div>
                  )}
                </div>
              </div>
            </div>
          ))}
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
            name="bankName"
            label="银行名称"
            rules={[{ required: true, message: '请输入银行名称' }]}
          >
            <Input placeholder="如：华侨银行" />
          </Form.Item>
          <Form.Item
            name="accountName"
            label="账户名称"
            rules={[{ required: true, message: '请输入账户名称' }]}
          >
            <Input placeholder="如：高山貿易有限公司" />
          </Form.Item>
          <Form.Item
            name="accountNumber"
            label="银行账号"
            rules={[{ required: true, message: '请输入银行账号' }]}
          >
            <Input placeholder="如：035-803-185706051" />
          </Form.Item>
          <Form.Item name="fpsId" label="转数快 FPS ID">
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
          <Form.Item name="swiftCode" label="SWIFT Code">
            <Input placeholder="可选（国际汇款需要）" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
