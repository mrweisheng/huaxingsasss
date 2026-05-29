import { useState, useEffect, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Descriptions, Card, Button, Spin, Table, Tag, Alert, Progress, Image } from 'antd'
import { ArrowLeftOutlined, DownloadOutlined, EyeOutlined, FileOutlined } from '@ant-design/icons'
import { contractApi } from '@/services/contract'
import { paymentApi } from '@/services/payment'
import type { Contract, Payment } from '@/types'

const statusMap: Record<string, { color: string; text: string }> = {
  draft: { color: 'default', text: '草稿' },
  pending_review: { color: 'warning', text: '待审核' },
  active: { color: 'processing', text: '执行中' },
  completed: { color: 'success', text: '已完成' },
  cancelled: { color: 'error', text: '已取消' },
  disputed: { color: 'volcano', text: '争议' },
}

const businessTypeMap: Record<string, { color: string; text: string }> = {
  '车辆业务': { color: 'purple', text: '车辆业务' },
  '中港牌业务': { color: 'green', text: '中港牌业务' },
}

const currencySymbol: Record<string, string> = { CNY: '¥', HKD: 'HK$', USD: '$' }

function fmt(amount: number | undefined | null, currency: string): string {
  if (amount === undefined || amount === null) return '-'
  const symbol = currencySymbol[currency] || '¥'
  return `${symbol}${amount.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

function calcProgress(paid: number, total: number): number {
  if (total === 0) return 0
  return Math.round((paid / total) * 100)
}

const paymentStatusMap: Record<string, { color: string; text: string }> = {
  pending: { color: 'default', text: '待支付' },
  partial: { color: 'warning', text: '部分支付' },
  paid: { color: 'success', text: '已支付' },
  overdue: { color: 'error', text: '逾期' },
  cancelled: { color: 'default', text: '已取消' },
}

export default function ContractDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [contract, setContract] = useState<Contract | null>(null)
  const [payments, setPayments] = useState<Payment[]>([])
  const [summary, setSummary] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const abortControllerRef = useRef<AbortController | null>(null)

  useEffect(() => {
    if (!id) return

    abortControllerRef.current?.abort()
    const controller = new AbortController()
    abortControllerRef.current = controller

    setLoading(true)
    setError('')
    Promise.all([
      contractApi.getById(Number(id), controller.signal),
      paymentApi.getContractPayments(Number(id), controller.signal),
    ])
      .then(([c, p]) => {
        if (controller.signal.aborted) return
        setContract(c)
        const data = p.data || p
        setPayments(data.payments || [])
        setSummary(data)
      })
      .catch((e) => {
        if (e?.name === 'AbortError' || e?.code === 'ERR_CANCELED') return
        setError(e.response?.data?.detail || '加载失败')
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

  if (loading) return <div style={{ textAlign: 'center', padding: 80 }}><Spin tip="加载中..." /></div>
  if (error) return <Alert type="error" message={error} showIcon />
  if (!contract) return <Alert type="warning" message="合同不存在" showIcon />

  const cur = contract.currency
  const progress = calcProgress(contract.paid_amount, contract.total_amount)
  const authToken = localStorage.getItem('access_token')
  const contractFileUrl = contract.original_file_path
    ? `/api/v1/contracts/${contract.id}/file?token=${authToken}`
    : null

  const paymentColumns = [
    { title: '期数', dataIndex: 'installment_number', key: 'installment_number', width: 60 },
    { title: '期数名称', dataIndex: 'installment_name', key: 'installment_name', render: (v: string) => v || '-' },
    { title: '币种', dataIndex: 'currency', key: 'currency', width: 60 },
    { title: '应付金额', dataIndex: 'amount', key: 'amount', render: (v: number, r: Payment) => fmt(v, r.currency) },
    { title: '实付金额', dataIndex: 'paid_amount', key: 'paid_amount', render: (v: number, r: Payment) => fmt(v, r.currency) },
    { title: '汇率', dataIndex: 'exchange_rate', key: 'exchange_rate', width: 90, render: (v: number) => v ? Number(v).toFixed(4) : '-' },
    { title: '折算CNY', dataIndex: 'paid_amount_in_cny', key: 'paid_amount_in_cny', render: (v: number) => fmt(v, 'CNY') },
    { title: '付款日期', dataIndex: 'paid_date', key: 'paid_date', width: 110, render: (v: string) => v || '-' },
    { title: '方式', dataIndex: 'payment_method', key: 'payment_method', width: 80, render: (v: string) => v || '-' },
    { title: '状态', dataIndex: 'status', key: 'status', width: 80, render: (s: string) => {
      const { color, text } = paymentStatusMap[s] || { color: 'default', text: s }
      return <Tag color={color}>{text}</Tag>
    }},
    {
      title: '凭证',
      dataIndex: 'receipt_image_path',
      key: 'receipt',
      width: 70,
      render: (path: string, record: Payment) => {
        if (!path) return '-'
        const token = localStorage.getItem('access_token')
        const url = `/api/v1/payments/${record.id}/receipt?token=${token}`
        return (
          <Image
            src={url}
            width={32}
            height={32}
            style={{ objectFit: 'cover', borderRadius: 4, cursor: 'pointer' }}
            preview={{ mask: <EyeOutlined /> }}
          />
        )
      },
    },
    { title: '备注', dataIndex: 'notes', key: 'notes', ellipsis: true, render: (v: string) => v || '-' },
  ]

  return (
    <div>
      <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/contracts')} style={{ marginBottom: 16 }}>
        返回列表
      </Button>

      <Card title="合同详情">
        <Descriptions column={2} bordered size="small">
          <Descriptions.Item label="合同编号">{contract.contract_number}</Descriptions.Item>
          <Descriptions.Item label="客户名称">{contract.customer_name || '-'}</Descriptions.Item>

          <Descriptions.Item label="业务类型">
            {(() => {
              const bt = businessTypeMap[contract.business_type || '']
              return bt ? <Tag color={bt.color}>{bt.text}</Tag> : (contract.business_type || '-')
            })()}
          </Descriptions.Item>
          <Descriptions.Item label="状态">
            {(() => { const { color, text } = statusMap[contract.status] || { color: 'default', text: contract.status }; return <Tag color={color}>{text}</Tag> })()}
          </Descriptions.Item>

          {contract.business_description && (
            <Descriptions.Item label="业务描述" span={2}>{contract.business_description}</Descriptions.Item>
          )}

          {contract.title && (
            <Descriptions.Item label="合同标题" span={2}>{contract.title}</Descriptions.Item>
          )}

          <Descriptions.Item label="币种">{cur}</Descriptions.Item>
          <Descriptions.Item label="签订日期">{contract.signed_date || '-'}</Descriptions.Item>

          <Descriptions.Item label="生效日期">{contract.start_date || '-'}</Descriptions.Item>
          <Descriptions.Item label="到期日期">{contract.end_date || '-'}</Descriptions.Item>

          <Descriptions.Item label="总金额">{fmt(contract.total_amount, cur)}</Descriptions.Item>
          <Descriptions.Item label="已付金额">{fmt(contract.paid_amount, cur)}</Descriptions.Item>

          <Descriptions.Item label="剩余尾款">
            <span style={{ color: contract.remaining_amount > 0 ? '#ff4d4f' : '#52c41a' }}>
              {fmt(contract.remaining_amount, cur)}
            </span>
          </Descriptions.Item>
          <Descriptions.Item label="付款进度">
            <Progress
              percent={progress}
              size="small"
              strokeColor={progress === 100 ? '#52c41a' : '#1890ff'}
              style={{ maxWidth: 200 }}
            />
          </Descriptions.Item>

          {contract.wechat_group && (
            <Descriptions.Item label="微信群名称" span={2}>{contract.wechat_group}</Descriptions.Item>
          )}

          <Descriptions.Item label="备注" span={2}>{contract.remarks || '-'}</Descriptions.Item>

          <Descriptions.Item label="合同文件" span={2}>
            {contractFileUrl ? (
              <Button
                type="link"
                icon={<FileOutlined />}
                href={contractFileUrl}
                target="_blank"
                style={{ padding: 0 }}
              >
                查看原文件
              </Button>
            ) : '无'}
          </Descriptions.Item>
        </Descriptions>
      </Card>

      {summary && (summary.total_amount_in_cny || summary.paid_amount_in_cny) && (
        <Card title="CNY 汇总" style={{ marginTop: 16 }} size="small">
          <Descriptions column={3} size="small">
            <Descriptions.Item label="合同总额(CNY)">{fmt(summary.total_amount_in_cny, 'CNY')}</Descriptions.Item>
            <Descriptions.Item label="已付(CNY)">{fmt(summary.paid_amount_in_cny, 'CNY')}</Descriptions.Item>
            <Descriptions.Item label="剩余(CNY)">{fmt(summary.remaining_amount_in_cny, 'CNY')}</Descriptions.Item>
          </Descriptions>
        </Card>
      )}

      <Card title={`付款记录 (${payments.length} 笔)`} style={{ marginTop: 16 }}>
        {payments.length > 0 ? (
          <Table
            columns={paymentColumns}
            dataSource={payments}
            rowKey="id"
            size="small"
            pagination={false}
            scroll={{ x: 1100 }}
          />
        ) : (
          <div style={{ textAlign: 'center', color: '#999', padding: 24 }}>暂无付款记录</div>
        )}
      </Card>
    </div>
  )
}
