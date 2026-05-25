import { useNavigate } from 'react-router-dom'
import { Form, Input, Button, Card, message, Space } from 'antd'
import { ArrowLeftOutlined } from '@ant-design/icons'
import { customerApi } from '@/services/customer'

export default function CustomerNew() {
  const navigate = useNavigate()
  const [form] = Form.useForm()

  const onFinish = async (values: any) => {
    try {
      await customerApi.create(values)
      message.success('客户创建成功')
      navigate('/customers')
    } catch (error: any) {
      message.error(error.response?.data?.detail || '创建失败')
    }
  }

  return (
    <div>
      <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/customers')} style={{ marginBottom: 16 }}>
        返回列表
      </Button>
      <Card title="新增客户">
        <Form
          form={form}
          layout="vertical"
          onFinish={onFinish}
          style={{ maxWidth: 600 }}
        >
          <Form.Item
            name="name"
            label="客户名称"
            rules={[{ required: true, message: '请输入客户名称' }]}
          >
            <Input placeholder="公司名称或个人姓名" />
          </Form.Item>

          <Form.Item name="contact_person" label="联系人">
            <Input placeholder="联系人姓名" />
          </Form.Item>

          <Form.Item
            name="phone"
            label="联系电话"
            rules={[
              {
                pattern: /^(\+?852[2-9]\d{7}|\+?861[3-9]\d{9}|\+?[1-9]\d{6,14})$/,
                message: '请输入正确的电话号码（支持内地/香港/其他地区）'
              },
            ]}
          >
            <Input placeholder="手机号码或固定电话" />
          </Form.Item>

          <Form.Item
            name="email"
            label="联系邮箱"
            rules={[{ type: 'email', message: '请输入正确的邮箱地址' }]}
          >
            <Input placeholder="电子邮箱" />
          </Form.Item>

          <Form.Item name="id_card_number" label="身份证号">
            <Input placeholder="身份证号（将加密存储）" />
          </Form.Item>

          <Form.Item name="business_license" label="营业执照号">
            <Input placeholder="营业执照号" />
          </Form.Item>

          <Form.Item name="address" label="地址">
            <Input.TextArea rows={2} placeholder="详细地址" />
          </Form.Item>

          <Form.Item name="wechat_group_name" label="微信群名称">
            <Input placeholder="对应的微信群名称" />
          </Form.Item>

          <Form.Item name="remarks" label="备注">
            <Input.TextArea rows={3} placeholder="备注信息" />
          </Form.Item>

          <Form.Item>
            <Space>
              <Button type="primary" htmlType="submit">
                创建客户
              </Button>
              <Button onClick={() => navigate('/customers')}>
                取消
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Card>
    </div>
  )
}
