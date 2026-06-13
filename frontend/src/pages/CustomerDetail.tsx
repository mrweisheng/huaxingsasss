import { useState, useEffect, useCallback, useRef } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Button, message, Empty, Tooltip } from 'antd'
import {
  ArrowLeftOutlined,
  PhoneOutlined,
  MailOutlined,
  IdcardOutlined,
  EnvironmentOutlined,
  EditOutlined,
  DeleteOutlined,
  FileTextOutlined,
  UserOutlined,
  WechatOutlined,
  MessageOutlined,
} from '@ant-design/icons'
import { customerApi } from '@/services/customer'
import { contractApi } from '@/services/contract'
import DangerConfirmModal from '@/components/DangerConfirmModal'
import type { Customer, Contract } from '@/types'
import dayjs from 'dayjs'
import { formatMoney } from '@/utils/money'
import './ContractList.css' // 复用合同管理卡片样式（biz-badge / amount-section / contract-card 等）
import './CustomerDetail.css'

// 业务视觉映射（与 ContractList 完全一致）
// 业务色见 CLAUDE.md：车辆=钢蓝 #2d5b8a，两地牌=朱砂 #b8423b
type BizVisual = {
  className: string         // 卡片根类名（驱动业务色 CSS 变量）
  icon: React.ReactNode
  label: string
}

const vehicleVisual: BizVisual = {
  className: 'biz-vehicle',
  label: '车辆买卖',
  icon: (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="2" y="6" width="20" height="11" rx="3"/>
      <circle cx="7" cy="18" r="2"/><circle cx="17" cy="18" r="2"/>
      <line x1="6" y1="11" x2="10" y2="11"/><line x1="14" y1="11" x2="18" y2="11"/>
    </svg>
  ),
}

const crossVisual: BizVisual = {
  className: 'biz-cross',
  label: '两地牌过户',
  icon: (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 9h18v10H3z"/><path d="M9 19v-3h6v3"/><path d="M7 9V5h10v4"/>
      <line x1="8" y1="14" x2="10" y2="14"/><line x1="14" y1="14" x2="16" y2="14"/>
    </svg>
  ),
}

const bizVisual: Record<string, BizVisual> = {
  // 标准值
  '车辆买卖': vehicleVisual,
  '两地牌过户': crossVisual,
  // legacy 兼容
  '车辆业务': vehicleVisual,
  '中港牌业务': crossVisual,
}

const statusConfig: Record<string, { color: string; bg: string; text: string }> = {
  active: { color: '#1890ff', bg: '#e6f7ff', text: '执行中' },
  completed: { color: '#52c41a', bg: '#f6ffed', text: '已完成' },
}

const currencySymbol: Record<string, string> = {
  CNY: '¥',
  HKD: 'HK$',
}

// 缩写金额渲染：与 ContractList 同款（货币符号 + 数字 + 万/亿 chip + Tooltip 全值）
function renderAmount(amount: number | null | undefined, currency: string) {
  const symbol = currencySymbol[currency] || '¥'
  if (amount == null) return <>{symbol}--</>
  const m = formatMoney(amount)
  const node = (
    <>
      <span className="money-sym">{symbol}</span>
      <span className="money-num">{m.display}</span>
      {m.unit && <span className="money-unit">{m.unit}</span>}
    </>
  )
  if (!m.unit) return node
  return (
    <Tooltip title={`${symbol}${m.full}`} placement="top" mouseEnterDelay={0.3}>
      {node}
    </Tooltip>
  )
}

function calculateProgress(paid: number, total: number): number {
  if (total === 0) return 0
  return Math.round((paid / total) * 100)
}

export default function CustomerDetail() {
  const navigate = useNavigate()
  const { id } = useParams<{ id: string }>()
  const customerId = Number(id)

  const [customer, setCustomer] = useState<Customer | null>(null)
  const [contracts, setContracts] = useState<Contract[]>([])
  const [loading, setLoading] = useState(true)
  const [editing, setEditing] = useState(false)
  const [editForm, setEditForm] = useState<Partial<Customer>>({})
  const [saving, setSaving] = useState(false)
  const [deleteOpen, setDeleteOpen] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const abortControllerRef = useRef<AbortController | null>(null)

  const loadData = useCallback(async () => {
    if (!customerId || Number.isNaN(customerId)) {
      message.error('客户 ID 无效')
      navigate('/customers')
      return
    }

    abortControllerRef.current?.abort()
    const controller = new AbortController()
    abortControllerRef.current = controller

    setLoading(true)
    try {
      const [cust, ctRes] = await Promise.all([
        customerApi.getById(customerId, controller.signal),
        contractApi.getList({ customer_id: customerId, per_page: 200 }, controller.signal),
      ])
      if (controller.signal.aborted) return
      setCustomer(cust)
      setContracts(ctRes.items)
      setEditForm(cust)
    } catch (error: any) {
      if (error?.name === 'AbortError' || error?.code === 'ERR_CANCELED') return
      message.error(error?.response?.data?.detail || '加载客户详情失败')
    } finally {
      if (!controller.signal.aborted) setLoading(false)
    }
  }, [customerId, navigate])

  useEffect(() => {
    loadData()
    return () => { abortControllerRef.current?.abort() }
  }, [loadData])

  const handleDelete = async () => {
    if (!customer) return
    setDeleting(true)
    try {
      await customerApi.delete(customer.id)
      message.success(`已删除「${customer.name}」`)
      setDeleteOpen(false)
      navigate('/customers')
    } catch (error: any) {
      message.error(error?.response?.data?.detail || '删除失败')
    } finally {
      setDeleting(false)
    }
  }

  const handleSave = async () => {
    if (!customer) return
    if (!editForm.name?.trim()) {
      message.error('客户名称不能为空')
      return
    }
    setSaving(true)
    try {
      await customerApi.update(customer.id, editForm)
      message.success('已更新')
      setEditing(false)
      loadData()
    } catch (error: any) {
      message.error(error?.response?.data?.detail || '更新失败')
    } finally {
      setSaving(false)
    }
  }

  // 计算该客户的主业务类型（按合同数最多的）
  const dominantBiz = (() => {
    if (contracts.length === 0) return null
    const counts: Record<string, number> = {}
    contracts.forEach(ct => {
      if (ct.business_type) counts[ct.business_type] = (counts[ct.business_type] || 0) + 1
    })
    const sorted = Object.entries(counts).sort((a, b) => b[1] - a[1])
    return sorted[0]?.[0] || null
  })()
  const dominantVisual = dominantBiz ? bizVisual[dominantBiz] : null
  const dominantBizClass = dominantVisual?.className || ''
  const dominantBizSuffix = dominantBizClass.replace('biz-', '')

  if (loading) {
    // 骨架屏：与档案卡片 + 合同卡片网格结构一致，避免白屏
    return (
      <div className="cd-wrap">
        <div className="cd-back">
          <div className="app-skel-block" style={{ width: 120, height: 32, borderRadius: 6 }} />
        </div>
        <div className="cd-profile">
          <div className="cd-profile-top">
            <div className="cd-profile-id" style={{ display: 'flex', gap: 16, alignItems: 'center' }}>
              <div className="app-skel-block" style={{ width: 56, height: 56, borderRadius: '50%' }} />
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                <div className="app-skel-block" style={{ width: 160, height: 24 }} />
                <div style={{ display: 'flex', gap: 8 }}>
                  <div className="app-skel-block" style={{ width: 110, height: 22, borderRadius: 11 }} />
                  <div className="app-skel-block" style={{ width: 80, height: 22, borderRadius: 11 }} />
                </div>
              </div>
            </div>
            <div className="cd-profile-actions" style={{ display: 'flex', gap: 8 }}>
              <div className="app-skel-block" style={{ width: 72, height: 32, borderRadius: 6 }} />
              <div className="app-skel-block" style={{ width: 72, height: 32, borderRadius: 6 }} />
            </div>
          </div>
          <div className="divider-gold" style={{ margin: '16px 0 14px' }} />
          <div className="cd-info-grid">
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="cd-info-item" style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                <div className="app-skel-block app-skel-line w-40" />
                <div className="app-skel-block app-skel-line w-70" />
              </div>
            ))}
          </div>
        </div>
        <div style={{ marginTop: 20, display: 'flex', flexDirection: 'column', gap: 10 }}>
          <div className="app-skel-block" style={{ width: 140, height: 18 }} />
          <div className="contract-grid">
            {Array.from({ length: 3 }).map((_, i) => (
              <div
                key={i}
                className="app-skel-block"
                style={{ height: 220, borderRadius: 12 }}
              />
            ))}
          </div>
        </div>
      </div>
    )
  }

  if (!customer) {
    return (
      <div className="cd-wrap">
        <Empty description="未找到客户" />
      </div>
    )
  }

  return (
    <div className="cd-wrap">
      {/* 返回按钮 */}
      <div className="cd-back">
        <Button
          type="text"
          icon={<ArrowLeftOutlined />}
          onClick={() => navigate('/customers')}
        >
          返回客户列表
        </Button>
      </div>

      {/* 客户档案卡片 */}
      <div className={`cd-profile ${dominantBizClass}`}>
        {dominantVisual && (
          <div className="card-accent-bar" />
        )}

        <div className="cd-profile-top">
          <div className="cd-profile-id">
            <div className="cd-avatar">
              <UserOutlined />
            </div>
            <div>
              {editing ? (
                <input
                  className="cd-name-input"
                  value={editForm.name || ''}
                  onChange={e => setEditForm({ ...editForm, name: e.target.value })}
                  placeholder="客户名称"
                />
              ) : (
                <h1 className="cd-name">{customer.name}</h1>
              )}
              <div className="cd-tags">
                {dominantVisual && (
                  <span className={`biz-badge biz-badge--${dominantBizSuffix}`}>
                    <span className="biz-badge-icon">{dominantVisual.icon}</span>
                    <span className="biz-badge-label">主业务 · {dominantVisual.label}</span>
                  </span>
                )}
                {contracts.length > 0 && (
                  <span className="cd-tag-count">
                    <FileTextOutlined /> {contracts.length} 份合同
                  </span>
                )}
              </div>
            </div>
          </div>

          <div className="cd-profile-actions">
            {editing ? (
              <>
                <Button onClick={() => { setEditForm(customer); setEditing(false) }}>取消</Button>
                <Button type="primary" loading={saving} onClick={handleSave}>保存</Button>
              </>
            ) : (
              <>
                <Button icon={<EditOutlined />} onClick={() => setEditing(true)}>编辑</Button>
                <Button danger icon={<DeleteOutlined />} onClick={() => setDeleteOpen(true)}>
                  删除
                </Button>
              </>
            )}
          </div>
        </div>

        <div className="divider-gold" style={{ margin: '16px 0 14px' }} />

        <div className="cd-info-grid">
          <div className="cd-info-item">
            <span className="cd-info-label"><PhoneOutlined /> 联系电话</span>
            {editing ? (
              <input
                className="cd-info-input"
                value={editForm.phone || ''}
                onChange={e => setEditForm({ ...editForm, phone: e.target.value })}
                placeholder="--"
              />
            ) : (
              <span className="cd-info-value">{customer.phone || '--'}</span>
            )}
          </div>

          <div className="cd-info-item">
            <span className="cd-info-label"><MailOutlined /> 邮箱</span>
            {editing ? (
              <input
                className="cd-info-input"
                value={editForm.email || ''}
                onChange={e => setEditForm({ ...editForm, email: e.target.value })}
                placeholder="--"
              />
            ) : (
              <span className="cd-info-value">{customer.email || '--'}</span>
            )}
          </div>

          <div className="cd-info-item">
            <span className="cd-info-label"><IdcardOutlined /> 证件号码</span>
            {editing ? (
              <input
                className="cd-info-input"
                value={editForm.id_card_number || ''}
                onChange={e => setEditForm({ ...editForm, id_card_number: e.target.value })}
                placeholder="--"
              />
            ) : (
              <span className="cd-info-value cd-info-mono">{customer.id_card_number || '--'}</span>
            )}
          </div>

          <div className="cd-info-item">
            <span className="cd-info-label"><UserOutlined /> 联系人</span>
            {editing ? (
              <input
                className="cd-info-input"
                value={editForm.contact_person || ''}
                onChange={e => setEditForm({ ...editForm, contact_person: e.target.value })}
                placeholder="--"
              />
            ) : (
              <span className="cd-info-value">{customer.contact_person || '--'}</span>
            )}
          </div>

          <div className="cd-info-item cd-info-item-wide">
            <span className="cd-info-label"><EnvironmentOutlined /> 地址</span>
            {editing ? (
              <input
                className="cd-info-input"
                value={editForm.address || ''}
                onChange={e => setEditForm({ ...editForm, address: e.target.value })}
                placeholder="--"
              />
            ) : (
              <span className="cd-info-value">{customer.address || '--'}</span>
            )}
          </div>

          {customer.remarks && (
            <div className="cd-info-item cd-info-item-wide">
              <span className="cd-info-label"><MessageOutlined /> 备注</span>
              {editing ? (
                <textarea
                  className="cd-info-textarea"
                  value={editForm.remarks || ''}
                  onChange={e => setEditForm({ ...editForm, remarks: e.target.value })}
                  rows={2}
                  placeholder="--"
                />
              ) : (
                <span className="cd-info-value">{customer.remarks}</span>
              )}
            </div>
          )}
        </div>
      </div>

      {/* 合同一览 */}
      <div className="cd-contracts">
        <div className="cd-contracts-header">
          <h2 className="cd-section-title">
            <FileTextOutlined /> 合同一览
            <span className="cd-section-count">{contracts.length} 份</span>
          </h2>
        </div>

        {contracts.length === 0 ? (
          <Empty description="该客户暂无合同" className="empty-state" />
        ) : (
          <div className="contract-grid">
            {contracts.map((contract, index) => {
              const status = statusConfig[contract.status] || statusConfig.active
              const biz = contract.business_type ? bizVisual[contract.business_type] : null
              const bizClass = biz?.className || (contract.business_type ? 'biz-other' : '')
              const bizMiniSuffix = bizClass.replace('biz-', '')
              const progressRaw = calculateProgress(contract.paid_amount, contract.total_amount)
              const progress = Math.min(progressRaw, 100)
              const _paid = Number(contract.paid_amount || 0)
              const _total = Number(contract.total_amount || 0)
              const _overpaid = Math.max(0, _paid - _total)
              const _unpaid = Math.max(0, _total - _paid)
              const _payState: 'pending' | 'cleared' | 'overpaid' =
                _overpaid > 0 ? 'overpaid' : _unpaid > 0 ? 'pending' : 'cleared'

              return (
                <div
                  key={contract.id}
                  className={`contract-card ${bizClass}`}
                  onClick={() => navigate(`/contracts/${contract.id}`)}
                  style={{ animationDelay: `${index * 50}ms` }}
                >
                  {/* ── 左侧色条（业务色 base）── */}
                  {(biz || contract.business_type) && (
                    <div className="card-accent-bar" />
                  )}

                  {/* ── 顶栏：业务徽章 + 状态 ── */}
                  <div className="card-top-row">
                    {biz ? (
                      <span className={`biz-badge biz-badge--${bizMiniSuffix}`}>
                        <span className="biz-badge-icon">{biz.icon}</span>
                        <span className="biz-badge-label">{biz.label}</span>
                      </span>
                    ) : contract.business_type ? (
                      <span className="biz-badge biz-badge--other">
                        <FileTextOutlined className="biz-badge-icon" />
                        <span className="biz-badge-label">{contract.business_type}</span>
                      </span>
                    ) : (
                      <span className="biz-badge biz-badge--default">
                        <FileTextOutlined className="biz-badge-icon" />
                        <span className="biz-badge-label">合同</span>
                      </span>
                    )}
                    <span className="status-badge" style={{ color: status.color, backgroundColor: status.bg }}>
                      {status.text}
                    </span>
                  </div>

                  {/* 标题行 + 签订日期（客户详情页客户名重复，改显合同标题）*/}
                  <div className="customer-name-hero" style={{ paddingTop: '6px' }}>
                    <span className="customer-name-text">{contract.title || '合同详情'}</span>
                    <span className="customer-date-text">
                      {contract.signed_date ? dayjs(contract.signed_date).format('YYYY-MM-DD') : '--'}
                    </span>
                  </div>

                  {/* 合同元信息：编号 + 微信群 */}
                  <div className="contract-meta-row">
                    <span className="contract-meta-number">{contract.contract_number}</span>
                    {contract.wechat_group && (
                      <>
                        <span className="contract-meta-sep">·</span>
                        <span className="contract-meta-title">
                          <WechatOutlined style={{ color: '#07c160', marginRight: 4 }} />
                          {contract.wechat_group}
                        </span>
                      </>
                    )}
                  </div>

                  {/* 业务描述 */}
                  <div className="business-desc">{contract.business_description || ''}</div>

                  {/* 金色分割线 */}
                  <div className="divider-gold card-divider" />

                  <div className="amount-section">
                    {/* 总金额 */}
                    <div className="amount-hero">
                      <span className="amount-hero-label">合同总额</span>
                      <span className="amount-hero-value">
                        {renderAmount(contract.total_amount, contract.currency)}
                      </span>
                    </div>

                    {/* 已付 / 未付 */}
                    <div className="amount-split">
                      <div className="amount-split-item is-paid">
                        <div className="split-item-header">
                          <span className="split-dot paid" />
                          <span className="split-label">已付</span>
                        </div>
                        <div className="split-value paid">
                          {renderAmount(contract.paid_amount, contract.currency)}
                        </div>
                        {contract.payment_total_count > 0 && (
                          <div className="split-meta">
                            <span className="split-count">{contract.paid_count}/{contract.payment_total_count}笔</span>
                          </div>
                        )}
                      </div>

                      <div className="amount-split-vert" />

                      <div className="amount-split-item is-unpaid">
                        <div className="split-item-header">
                          <span className={`split-dot ${_payState === 'pending' ? 'unpaid' : 'paid'}`} />
                          <span className="split-label">
                            {_payState === 'overpaid' ? '加项收入' : _payState === 'cleared' ? '已结清' : '未付'}
                          </span>
                        </div>
                        <div className={`split-value ${_payState === 'pending' ? 'unpaid' : _payState === 'overpaid' ? 'overpaid' : 'paid'}`}>
                          {_payState === 'overpaid'
                            ? <>+{renderAmount(_overpaid, contract.currency)}</>
                            : renderAmount(_payState === 'pending' ? contract.remaining_amount : 0, contract.currency)}
                        </div>
                        {contract.payment_total_count > 0 && (
                          <div className="split-meta">
                            <div className="split-progress">
                              <div className="split-progress-track">
                                <div className="split-progress-fill" style={{ width: `${progress}%` }} />
                              </div>
                              <span className="split-progress-text">{progress}%</span>
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                  </div>

                  <div className="card-decoration" />
                </div>
              )
            })}
          </div>
        )}
      </div>

      {/* 删除客户二次确认（5 秒读秒） */}
      <DangerConfirmModal
        open={deleteOpen}
        title="确认删除客户"
        description={
          <>
            即将删除客户 <strong>「{customer.name}」</strong>。
            {contracts.length > 0 && (
              <> 该客户名下有 <strong>{contracts.length}</strong> 份合同，<u>合同记录不会被一并删除</u>，仅断开客户关联。</>
            )}
          </>
        }
        warning="删除后客户档案将无法恢复，请确认无误。"
        onConfirm={handleDelete}
        onCancel={() => { if (!deleting) setDeleteOpen(false) }}
        confirming={deleting}
      />
    </div>
  )
}
