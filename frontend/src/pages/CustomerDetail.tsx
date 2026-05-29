import { useState, useEffect, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Descriptions, Card, Button, Spin, Table, Tag, Empty, Statistic, Row, Col } from 'antd'
import { ArrowLeftOutlined, EyeOutlined } from '@ant-design/icons'
import { customerApi } from '@/services/customer'
import { contractApi } from '@/services/contract'
import type { Customer, Contract } from '@/types'

const STATUS_MAP: Record<string, { label: string; color: string }> = {
  draft: { label: '草稿', color: 'default' },
  active: { label: '执行中', color: 'blue' },
  completed: { label: '已完成', color: 'green' },
}

const BUSINESS_TYPE_MAP: Record<string, string> = {
  '买港车': '买港车',
  '办两地牌': '办两地牌',
}

function formatAmount(amount: number, currency: string) {
  const formatted = amount.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
  return `${formatted} ${currency}`
}

export default function CustomerDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [customer, setCustomer] = useState<Customer | null>(null)
  const [contracts, setContracts] = useState<Contract[]>([])
  const [loading, setLoading] = useState(false)
  const [contractsLoading, setContractsLoading] = useState(false)
  const abortControllerRef = useRef<AbortController | null>(null)

  useEffect(() => {
    if (!id) return

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

    setContractsLoading(true)
    contractApi.getList({ customer_id: Number(id), per_page: 100 }, controller.signal)
      .then((res) => {
        if (!controller.signal.aborted) {
          setContracts(res.items || [])
        }
      })
      .catch((error) => {
        if (error?.name === 'AbortError' || error?.code === 'ERR_CANCELED') return
        console.error(error)
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setContractsLoading(false)
        }
      })

    return () => {
      controller.abort()
    }
  }, [id])

  if (loading) return <Spin />
  if (!customer) return <div>客户不存在</div>

  // 合同汇总统计
  const totalAmount = contracts.reduce((sum, c) => sum + (c.total_amount_in_cny || c.total_amount), 0)
  const totalPaid = contracts.reduce((sum, c) => sum + (c.paid_amount_in_cny || c.paid_amount), 0)

  const columns = [
    {
      title: '合同编号',
      dataIndex: 'contract_number',
      render: (text: string, record: Contract) => (
        <a onClick={() => navigate(`/contracts/${record.id}`)}>{text}</a>
      ),
    },
    {
      title: '业务类型',
      dataIndex: 'business_type',
      render: (val: string) => BUSINESS_TYPE_MAP[val] || val || '-',
    },
    {
      title: '合同金额',
      dataIndex: 'total_amount',
      align: 'right' as const,
      render: (val: number, record: Contract) => formatAmount(val, record.currency),
    },
    {
      title: '已付',
      dataIndex: 'paid_amount',
      align: 'right' as const,
      render: (val: number, record: Contract) => {
        const paid = record.paid_amount_in_cny || val
        return formatAmount(paid, 'CNY')
      },
    },
    {
      title: '剩余',
      dataIndex: 'remaining_amount',
      align: 'right' as const,
      render: (val: number, record: Contract) => {
        const remaining = record.remaining_amount_in_cny || val
        return formatAmount(remaining, 'CNY')
      },
    },
    {
      title: '付款进度',
      key: 'progress',
      align: 'center' as const,
      render: (_: unknown, record: Contract) => {
        const { paid_count, payment_total_count } = record
        if (!payment_total_count) return '-'
        const ratio = paid_count / payment_total_count
        const color = ratio >= 1 ? 'green' : ratio > 0 ? 'blue' : 'default'
        return <Tag color={color}>{paid_count}/{payment_total_count}</Tag>
      },
    },
    {
      title: '状态',
      dataIndex: 'status',
      render: (status: string) => {
        const s = STATUS_MAP[status] || { label: status, color: 'default' }
        return <Tag color={s.color}>{s.label}</Tag>
      },
    },
    {
      title: '签订日期',
      dataIndex: 'signed_date',
      render: (val: string) => val || '-',
    },
    {
      title: '操作',
      key: 'action',
      render: (_: unknown, record: Contract) => (
        <Button
          type="link"
          size="small"
          icon={<EyeOutlined />}
          onClick={() => navigate(`/contracts/${record.id}`)}
        >
          详情
        </Button>
      ),
    },
  ]

  return (
    <div>
      <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/customers')} style={{ marginBottom: 16 }}>
        返回列表
      </Button>

      <Card title="客户详情" style={{ marginBottom: 16 }}>
        <Descriptions column={2} bordered>
          <Descriptions.Item label="客户名称">{customer.name}</Descriptions.Item>
          <Descriptions.Item label="联系人">{customer.contact_person || '-'}</Descriptions.Item>
          <Descriptions.Item label="电话">{customer.phone || '-'}</Descriptions.Item>
          <Descriptions.Item label="邮箱">{customer.email || '-'}</Descriptions.Item>
          <Descriptions.Item label="证件号码">{customer.id_card_number || '-'}</Descriptions.Item>
          <Descriptions.Item label="营业执照号">{customer.business_license || '-'}</Descriptions.Item>
          <Descriptions.Item label="地址" span={2}>{customer.address || '-'}</Descriptions.Item>
          <Descriptions.Item label="微信群">{customer.wechat_group_name || '-'}</Descriptions.Item>
          <Descriptions.Item label="备注">{customer.remarks || '-'}</Descriptions.Item>
        </Descriptions>
      </Card>

      <Card title="关联合同">
        {contracts.length > 0 && (
          <Row gutter={16} style={{ marginBottom: 16 }}>
            <Col span={8}>
              <Statistic title="合同总数" value={contracts.length} suffix="份" />
            </Col>
            <Col span={8}>
              <Statistic
                title="合同总额（CNY）"
                value={totalAmount}
                precision={2}
                prefix="¥"
              />
            </Col>
            <Col span={8}>
              <Statistic
                title="已付总额（CNY）"
                value={totalPaid}
                precision={2}
                prefix="¥"
                valueStyle={{ color: totalPaid >= totalAmount ? '#52c41a' : undefined }}
              />
            </Col>
          </Row>
        )}
        <Table
          dataSource={contracts}
          columns={columns}
          rowKey="id"
          loading={contractsLoading}
          pagination={false}
          size="middle"
          locale={{ emptyText: <Empty description="暂无关联合同" /> }}
        />
      </Card>
    </div>
  )
}
