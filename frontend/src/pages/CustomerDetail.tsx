import { useState, useEffect, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Descriptions, Card, Button, Spin } from 'antd'
import { ArrowLeftOutlined } from '@ant-design/icons'
import { customerApi } from '@/services/customer'
import type { Customer } from '@/types'

export default function CustomerDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [customer, setCustomer] = useState<Customer | null>(null)
  const [loading, setLoading] = useState(false)
  const abortControllerRef = useRef<AbortController | null>(null)

  useEffect(() => {
    if (!id) return

    // Cancel previous request
    abortControllerRef.current?.abort()
    const controller = new AbortController()
    abortControllerRef.current = controller

    setLoading(true)
    customerApi.getById(Number(id), controller.signal)
      .then((data) => {
        if (!controller.signal.aborted) {
          setCustomer(data)
        }
      })
      .catch((error) => {
        if (error?.name === 'AbortError' || error?.code === 'ERR_CANCELED') return
        console.error(error)
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setLoading(false)
        }
      })

    return () => {
      controller.abort()
    }
  }, [id])

  if (loading) return <Spin />
  if (!customer) return <div>客户不存在</div>

  return (
    <div>
      <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/customers')} style={{ marginBottom: 16 }}>
        返回列表
      </Button>
      <Card title="客户详情">
        <Descriptions column={2} bordered>
          <Descriptions.Item label="客户名称">{customer.name}</Descriptions.Item>
          <Descriptions.Item label="联系人">{customer.contact_person || '-'}</Descriptions.Item>
          <Descriptions.Item label="电话">{customer.phone || '-'}</Descriptions.Item>
          <Descriptions.Item label="邮箱">{customer.email || '-'}</Descriptions.Item>
          <Descriptions.Item label="地址" span={2}>{customer.address || '-'}</Descriptions.Item>
          <Descriptions.Item label="微信群">{customer.wechat_group_name || '-'}</Descriptions.Item>
          <Descriptions.Item label="备注" span={2}>{customer.remarks || '-'}</Descriptions.Item>
        </Descriptions>
      </Card>
    </div>
  )
}
