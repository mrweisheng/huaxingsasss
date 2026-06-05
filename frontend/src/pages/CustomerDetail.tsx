import { useState, useEffect, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Button, Spin, Table, Tag, Empty, Tooltip } from 'antd'
import { ArrowLeftOutlined, EyeOutlined, UserOutlined, FileTextOutlined } from '@ant-design/icons'
import { customerApi } from '@/services/customer'
import { contractApi } from '@/services/contract'
import type { Customer, Contract } from '@/types'
import './CustomerDetail.css'

const STATUS_MAP: Record<string, { label: string; color: string }> = {
  draft: { label: '草稿', color: 'default' },
  active: { label: '执行中', color: 'blue' },
  completed: { label: '已完成', color: 'green' },
}

const BUSINESS_TYPE_MAP: Record<string, string> = {
  '买港车': '买港车',
  '办两地牌': '办两地牌',
}

const currencySymbol: Record<string, string> = { CNY: '¥', HKD: 'HK$', USD: '$' }

function fmt(amount: number | undefined | null, currency: string): string {
  if (amount === undefined || amount === null) return '-'
  const symbol = currencySymbol[currency] || '¥'
  return `${symbol}${amount.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

function fmtCny(amount: number | undefined | null): string {
  if (amount === undefined || amount === null || amount === 0) return ''
  return `≈ ¥${Math.round(amount).toLocaleString('zh-CN')}`
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

  if (loading) return <div className="app-loading-page"><Spin tip="加载中..." /></div>
  if (!customer) return <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-tertiary)' }}>客户不存在</div>

  // 合同汇总统计 — 检测是否单币种
  const currencies = [...new Set(contracts.map(c => c.currency))]
  const singleCurrency = currencies.length === 1 ? currencies[0] : null

  // 单币种时：用原币汇总；多币种时：用 CNY 汇总
  const totalAmount = singleCurrency
    ? contracts.reduce((sum, c) => sum + (c.total_amount || 0), 0)
    : contracts.reduce((sum, c) => sum + (c.total_amount_in_cny || c.total_amount), 0)
  const totalPaid = singleCurrency
    ? contracts.reduce((sum, c) => sum + (c.paid_amount || 0), 0)
    : contracts.reduce((sum, c) => sum + (c.paid_amount_in_cny || c.paid_amount), 0)
  const totalAmountCny = contracts.reduce((sum, c) => sum + (c.total_amount_in_cny || c.total_amount), 0)
  const totalPaidCny = contracts.reduce((sum, c) => sum + (c.paid_amount_in_cny || c.paid_amount), 0)
  const summaryCur = singleCurrency || 'CNY'

  const columns = [
    {
      title: '合同编号',
      dataIndex: 'contract_number',
      width: 140,
      render: (text: string, record: Contract) => (
        <a onClick={() => navigate(`/contracts/${record.id}`)} style={{ fontFamily: 'var(--font-mono)', fontWeight: 600 }}>
          {text}
        </a>
      ),
    },
    {
      title: '业务类型',
      dataIndex: 'business_type',
      width: 100,
      render: (val: string) => BUSINESS_TYPE_MAP[val] || val || '-',
    },
    {
      title: '合同金额',
      dataIndex: 'total_amount',
      width: 130,
      align: 'right' as const,
      render: (val: number, record: Contract) => (
        <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 600 }}>
          {fmt(val, record.currency)}
        </span>
      ),
    },
    {
      title: '已付',
      dataIndex: 'paid_amount',
      width: 120,
      align: 'right' as const,
      render: (val: number, record: Contract) => (
        <div>
          <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--color-success)' }}>
            {fmt(val, record.currency)}
          </span>
          {record.currency !== 'CNY' && record.paid_amount_in_cny != null && (
            <div style={{ fontSize: 11, color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)' }}>
              {fmtCny(record.paid_amount_in_cny)}
            </div>
          )}
        </div>
      ),
    },
    {
      title: '剩余',
      dataIndex: 'remaining_amount',
      width: 120,
      align: 'right' as const,
      render: (val: number, record: Contract) => {
        if (val <= 0) return <span style={{ color: 'var(--text-tertiary)' }}>已结清</span>
        return (
          <div>
            <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--color-danger)' }}>
              {fmt(val, record.currency)}
            </span>
            {record.currency !== 'CNY' && record.remaining_amount_in_cny != null && (
              <div style={{ fontSize: 11, color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)' }}>
                {fmtCny(record.remaining_amount_in_cny)}
              </div>
            )}
          </div>
        )
      },
    },
    {
      title: '付款进度',
      key: 'progress',
      width: 100,
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
      width: 80,
      render: (status: string) => {
        const s = STATUS_MAP[status] || { label: status, color: 'default' }
        return <Tag color={s.color}>{s.label}</Tag>
      },
    },
    {
      title: '签订日期',
      dataIndex: 'signed_date',
      width: 100,
      render: (val: string) => val || '-',
    },
    {
      title: '',
      key: 'action',
      width: 60,
      render: (_: unknown, record: Contract) => (
        <Tooltip title="查看合同详情">
          <Button
            type="text"
            size="small"
            icon={<EyeOutlined />}
            onClick={() => navigate(`/contracts/${record.id}`)}
          />
        </Tooltip>
      ),
    },
  ]

  return (
    <div className="cd-customer-container">
      {/* 顶部操作栏 */}
      <div className="detail-header">
        <div className="back-btn" onClick={() => navigate('/customers')}>
          <ArrowLeftOutlined /> 返回列表
        </div>
      </div>

      {/* ① 客户名称顶栏 */}
      <div className="cd-topbar">
        <div className="cd-topbar-left">
          <UserOutlined style={{ color: 'var(--brand-primary)', fontSize: 15 }} />
          <span className="cd-customer-name">{customer.name}</span>
          {customer.contact_person && (
            <>
              <span className="cd-topbar-sep">·</span>
              <span className="cd-contact-info">联系人：{customer.contact_person}</span>
            </>
          )}
          {customer.phone && (
            <>
              <span className="cd-topbar-sep">·</span>
              <span className="cd-contact-info">{customer.phone}</span>
            </>
          )}
        </div>
        <div className="cd-topbar-right">
          {customer.email && (
            <span>{customer.email}</span>
          )}
        </div>
      </div>

      {/* ② 客户详细信息网格 */}
      <div className="cd-info-strip">
        <div className="cd-info-grid">
          <div className="cd-info-item">
            <div className="cd-info-label">联系人</div>
            <div className="cd-info-value">{customer.contact_person || '-'}</div>
          </div>
          <div className="cd-info-item">
            <div className="cd-info-label">电话</div>
            <div className="cd-info-value">{customer.phone || '-'}</div>
          </div>
          <div className="cd-info-item">
            <div className="cd-info-label">邮箱</div>
            <div className="cd-info-value">{customer.email || '-'}</div>
          </div>
          <div className="cd-info-item">
            <div className="cd-info-label">证件号码</div>
            <div className="cd-info-value">{customer.id_card_number || '-'}</div>
          </div>
          <div className="cd-info-item">
            <div className="cd-info-label">营业执照号</div>
            <div className="cd-info-value">{customer.business_license || '-'}</div>
          </div>
          <div className="cd-info-item span2">
            <div className="cd-info-label">地址</div>
            <div className="cd-info-value multiline">{customer.address || '-'}</div>
          </div>
          <div className="cd-info-item">
            <div className="cd-info-label">微信群</div>
            <div className="cd-info-value">{customer.wechat_group_name || '-'}</div>
          </div>
          <div className="cd-info-item">
            <div className="cd-info-label">备注</div>
            <div className="cd-info-value multiline">{customer.remarks || '-'}</div>
          </div>
        </div>
      </div>

      {/* ③ KPI 指标卡：合同统计 */}
      {contracts.length > 0 && (
        <div className="cd-kpi-row">
          <div className="cd-kpi-card primary">
            <div className="cd-kpi-label">合同总数</div>
            <div className="cd-kpi-value small">
              {contracts.length}
              <span style={{ fontSize: 14, fontWeight: 500, color: 'var(--text-secondary)', letterSpacing: 0 }}> 份</span>
            </div>
            <div className="cd-kpi-sub">
              {contracts.filter(c => c.status === 'active').length} 份执行中
              · {contracts.filter(c => c.status === 'completed').length} 份已完成
            </div>
          </div>
          <div className="cd-kpi-card income">
            <div className="cd-kpi-label">
              合同总额{!singleCurrency ? '（CNY）' : ''}
            </div>
            <div className="cd-kpi-value success">
              {fmt(totalAmount, summaryCur)}
            </div>
            <div className="cd-kpi-sub">
              全量合同金额汇总
              {singleCurrency && singleCurrency !== 'CNY' && (
                <span style={{ marginLeft: 6, opacity: 0.65 }}>{fmtCny(totalAmountCny)}</span>
              )}
            </div>
          </div>
          <div className="cd-kpi-card expense">
            <div className="cd-kpi-label">
              已付总额{!singleCurrency ? '（CNY）' : ''}
            </div>
            <div className="cd-kpi-value" style={{ color: totalPaid >= totalAmount ? 'var(--color-success)' : 'var(--brand-primary)' }}>
              {fmt(totalPaid, summaryCur)}
            </div>
            <div className="cd-kpi-sub">
              {totalAmount > 0 ? `${Math.round((totalPaid / totalAmount) * 100)}% 已支付` : '-'}
              {singleCurrency && singleCurrency !== 'CNY' && (
                <span style={{ marginLeft: 6, opacity: 0.65 }}>{fmtCny(totalPaidCny)}</span>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ④ 关联合同 */}
      <div className="cd-payment-section">
        <div className="cd-payment-header">
          <span className="cd-payment-title">
            <FileTextOutlined style={{ marginRight: 6 }} />
            关联合同
          </span>
          <span className="cd-payment-count">{contracts.length} 份</span>
        </div>
        {contracts.length > 0 ? (
          <Table
            dataSource={contracts}
            columns={columns}
            rowKey="id"
            loading={contractsLoading}
            pagination={false}
            size="middle"
            locale={{ emptyText: <Empty description="暂无关联合同" /> }}
            style={{ padding: '0 4px' }}
          />
        ) : (
          <div style={{ textAlign: 'center', padding: '40px 24px', color: 'var(--text-tertiary)' }}>
            <FileTextOutlined style={{ fontSize: 28, marginBottom: 10, display: 'block', opacity: 0.3 }} />
            暂无关联合同
          </div>
        )}
      </div>
    </div>
  )
}
