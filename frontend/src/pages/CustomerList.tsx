import { useState, useEffect, useCallback, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { Input, Button, Empty, message } from 'antd'
import {
  SearchOutlined,
  PhoneOutlined,
  IdcardOutlined,
  FileTextOutlined,
  TeamOutlined,
  DeleteOutlined,
} from '@ant-design/icons'
import { useDebounce } from '@/hooks/useDebounce'
import { customerApi } from '@/services/customer'
import { contractApi } from '@/services/contract'
import { useAuthStore } from '@/store/useAuthStore'
import DangerConfirmModal from '@/components/DangerConfirmModal'
import type { Customer, Contract } from '@/types'
import './CustomerList.css'

interface CustomerWithContracts {
  customer: Customer
  contracts: Contract[]
}

// 业务视觉映射 —— 两个核心业务各对应一组视觉资产
// 后端枚举见 backend/app/core/business_types.py（标准值 + legacy 值都要覆盖）
type BizVisual = { className: string; icon: React.ReactNode; label: string }

const vehicleVisual: BizVisual = {
  className: 'biz-vehicle',
  label: '车辆买卖',
  icon: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
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
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
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

const currencySymbol: Record<string, string> = { CNY: '¥', HKD: 'HK$' }

// 纯数字千分位（不带货币符号），用于收据样式里货币符号单独 span
function formatNumber(amount: number | null | undefined): string {
  if (amount == null) return '--'
  return Number(amount).toLocaleString('zh-CN', { minimumFractionDigits: 0, maximumFractionDigits: 2 })
}

function calcProgress(paid: number, total: number): number {
  if (!total || total <= 0) return 0
  return Math.min(100, Math.round((Number(paid) / Number(total)) * 100))
}

// 取客户名首字（中文取首字，英文取首字母大写）
function getAvatarChar(name: string): string {
  if (!name) return '?'
  const trimmed = name.trim()
  return /^[A-Za-z]/.test(trimmed) ? trimmed[0].toUpperCase() : trimmed[0]
}

// 从 contract_data 里抽取一组「车牌 / 口岸」之类的轻量 tag，最多 2 个
function extractContractTags(data: any): string[] {
  if (!data || typeof data !== 'object') return []
  const tags: string[] = []
  const plate = data?.vehicle_info?.plate_number
  if (plate && typeof plate === 'string') tags.push(plate.trim())
  if (data.port && typeof data.port === 'string') tags.push(data.port.trim())
  return tags.filter(Boolean).slice(0, 2)
}

// 取一段合同摘要：优先 business_description，其次 title，再次合同号
function getContractSummary(ct: Contract): string {
  const desc = (ct.business_description || '').trim()
  if (desc) return desc
  const title = (ct.title || '').trim()
  if (title) return title
  return ct.contract_number || '未命名合同'
}

// 期数显示：paid_count / payment_total_count，未配置时返回空
function getStageText(ct: Contract): string {
  const paid = Number(ct.paid_count || 0)
  const total = Number(ct.payment_total_count || 0)
  if (total <= 0) return ''
  return `${paid}/${total} 期`
}

// 签约日格式化为 MM-DD
function formatSignedDate(date?: string): string {
  if (!date) return ''
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(date)
  return m ? `${m[2]}-${m[3]}` : date
}

export default function CustomerList() {
  const navigate = useNavigate()
  const role = useAuthStore(s => s.user?.role || '')
  const isAdmin = role === 'admin'
  const [items, setItems] = useState<CustomerWithContracts[]>([])
  const [loading, setLoading] = useState(false)
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [totalPages, setTotalPages] = useState(1)
  const [keyword, setKeyword] = useState('')
  const abortControllerRef = useRef<AbortController | null>(null)
  // 删除二次确认弹窗状态
  const [deleteTarget, setDeleteTarget] = useState<{ id: number; name: string; contractCount: number } | null>(null)
  const [deleting, setDeleting] = useState(false)

  const loadData = useCallback(async () => {
    abortControllerRef.current?.abort()
    const controller = new AbortController()
    abortControllerRef.current = controller

    setLoading(true)
    try {
      const response = await customerApi.getList(
        { page, per_page: 20, keyword: keyword || undefined },
        controller.signal,
      )
      if (controller.signal.aborted) return
      setTotal(response.pagination.total)
      setTotalPages(response.pagination.total_pages)

      const customers = response.items
      const customerIds = customers.map(c => c.id)
      const contractsByCustomer: Record<number, Contract[]> = {}

      if (customerIds.length > 0) {
        try {
          const contractsRes = await contractApi.getList(
            { customer_ids: customerIds.join(','), per_page: 500 },
            controller.signal,
          )
          if (!controller.signal.aborted) {
            for (const ct of contractsRes.items) {
              if (!contractsByCustomer[ct.customer_id]) contractsByCustomer[ct.customer_id] = []
              contractsByCustomer[ct.customer_id].push(ct)
            }
          }
        } catch (err: any) {
          if (err?.name === 'AbortError' || err?.code === 'ERR_CANCELED') return
          console.error('加载合同失败:', err)
        }
      }

      if (controller.signal.aborted) return

      const merged: CustomerWithContracts[] = customers.map(c => ({
        customer: c,
        contracts: contractsByCustomer[c.id] || [],
      }))

      setItems(merged)
    } catch (error: any) {
      if (error?.name === 'AbortError' || error?.code === 'ERR_CANCELED') return
      console.error(error)
    } finally {
      if (!controller.signal.aborted) setLoading(false)
    }
  }, [page, keyword])

  useEffect(() => {
    loadData()
    return () => { abortControllerRef.current?.abort() }
  }, [loadData])

  const handleSearch = useDebounce((value: string) => {
    setKeyword(value)
    setPage(1)
  }, 400)

  const handleDeleteConfirmed = async () => {
    if (!deleteTarget) return
    setDeleting(true)
    try {
      await customerApi.delete(deleteTarget.id)
      message.success(`已删除「${deleteTarget.name}」`)
      setDeleteTarget(null)
      loadData()
    } catch (err: any) {
      message.error(err?.response?.data?.detail || '删除失败')
    } finally {
      setDeleting(false)
    }
  }

  return (
    <div className="cl-wrap">
      {/* 顶栏 */}
      <div className="page-topbar">
        <div className="page-topbar-left">
          <div className="page-title-wrap">
            <div className="page-title-icon">
              <TeamOutlined />
            </div>
            <span className="page-title-text">客户管理</span>
            <span className="page-title-count">{total} 位客户</span>
          </div>
        </div>
        <div className="page-topbar-right">
          <Input
            placeholder="搜索客户名称/电话/证件号"
            allowClear
            onChange={e => handleSearch(e.target.value)}
            style={{ width: 260 }}
            prefix={<SearchOutlined />}
          />
        </div>
      </div>

      {/* 客户卡片网格 */}
      {items.length === 0 && !loading ? (
        <Empty description="暂无客户" className="empty-state" />
      ) : (
        <div className="cl-grid">
          {items.map((item, index) => {
            const { customer: c, contracts } = item
            return (
              <div
                key={c.id}
                className="cl-card"
                onClick={() => navigate(`/customers/${c.id}`)}
                style={{ animationDelay: `${index * 50}ms` }}
              >
                {/* 右上角删除按钮（仅管理员；hover 时显形） */}
                {isAdmin && (
                  <button
                    className="cl-card-del"
                    title="删除客户"
                    onClick={e => {
                      e.stopPropagation()
                      setDeleteTarget({ id: c.id, name: c.name, contractCount: contracts.length })
                    }}
                  >
                    <DeleteOutlined />
                  </button>
                )}
                {/* ── 身份区 ── */}
                <div className="cl-identity">
                  <div className="cl-identity-top">
                    <div className="cl-avatar">{getAvatarChar(c.name)}</div>
                    <div className="cl-name" title={c.name}>{c.name}</div>
                    {contracts.length > 0 && (
                      <span className="cl-contracts-pill">
                        <FileTextOutlined />
                        <span className="cl-contracts-pill-num">{contracts.length}</span>
                        <span>份</span>
                      </span>
                    )}
                  </div>
                  <div className="cl-meta">
                    {c.phone && (
                      <span className="cl-meta-item" title={c.phone}>
                        <PhoneOutlined />
                        <span>{c.phone}</span>
                      </span>
                    )}
                    {c.id_card_number && (
                      <span className="cl-meta-item cl-meta-item--mono" title={c.id_card_number}>
                        <IdcardOutlined />
                        <span>{c.id_card_number}</span>
                      </span>
                    )}
                    {!c.phone && !c.id_card_number && (
                      <span className="cl-meta-empty">暂无联系方式</span>
                    )}
                  </div>
                </div>

                {/* ── 合同区 ── */}
                {contracts.length === 0 ? (
                  <div className="cl-empty">
                    <svg className="cl-empty-icon" width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                      <polyline points="14 2 14 8 20 8"/>
                    </svg>
                    <span>暂无关联合同</span>
                  </div>
                ) : (
                  <div className="cl-contracts">
                    {contracts.map(ct => {
                      const biz = ct.business_type ? bizVisual[ct.business_type] : null
                      const bizClass = biz?.className || 'biz-other'
                      const bizMiniSuffix = bizClass.replace('biz-', '')
                      const pct = calcProgress(ct.paid_amount, ct.total_amount)
                      const progressState =
                        pct >= 100 ? 'full' : pct > 0 ? 'partial' : 'empty'
                      const isDone = pct >= 100
                      const paidNum = Number(ct.paid_amount || 0)
                      const totalNum = Number(ct.total_amount || 0)
                      const dueNum = Math.max(0, totalNum - paidNum)
                      const paidClass = isDone ? 'is-done' : paidNum > 0 ? '' : 'is-zero'
                      const cur = currencySymbol[ct.currency] || '¥'
                      const summary = getContractSummary(ct)
                      const tags = extractContractTags(ct.contract_data)
                      const stageText = getStageText(ct)
                      const signed = formatSignedDate(ct.signed_date)
                      const metaText = [signed && `${signed} 签约`, ct.contract_number]
                        .filter(Boolean)
                        .join(' · ')
                      return (
                        <div
                          key={ct.id}
                          className={`cl-ct ${bizClass}`}
                          onClick={e => {
                            e.stopPropagation()
                            navigate(`/contracts/${ct.id}`)
                          }}
                        >
                          {/* 合同头：业务徽章 + 签约日/合同号 */}
                          <div className="cl-ct-head">
                            <span className={`cl-biz-mini cl-biz-mini--${bizMiniSuffix}`}>
                              {biz ? (
                                <>
                                  <span className="cl-biz-mini-icon">{biz.icon}</span>
                                  {biz.label}
                                </>
                              ) : (
                                ct.business_type || '其他业务'
                              )}
                            </span>
                            {metaText && (
                              <span className="cl-ct-meta" title={metaText}>{metaText}</span>
                            )}
                          </div>

                          {/* 金额收据区：已收 / 总额 / 未收（或全额结清） */}
                          <div className={`cl-receipt${isDone ? ' is-done' : ''}`}>
                            <div className="cl-receipt-row">
                              <span className={`cl-receipt-label${isDone ? ' cl-receipt-label--done' : ''}`}>
                                已收
                              </span>
                              <span className={`cl-receipt-num cl-receipt-num--paid ${paidClass}`}>
                                <span className="cl-cur">{cur}</span>{formatNumber(paidNum)}
                              </span>
                            </div>
                            <div className="cl-receipt-row">
                              <span className={`cl-receipt-label${isDone ? ' cl-receipt-label--done' : ''}`}>
                                合同总额
                              </span>
                              <span className="cl-receipt-num cl-receipt-num--total">
                                <span className="cl-cur">{cur}</span>{formatNumber(totalNum)}
                              </span>
                            </div>
                            <div className="cl-receipt-row is-divider">
                              {isDone ? (
                                <>
                                  <span className="cl-receipt-label cl-receipt-label--done">✓ 全额结清</span>
                                  <span className="cl-receipt-num cl-receipt-num--done-text">100%</span>
                                </>
                              ) : (
                                <>
                                  <span className="cl-receipt-label cl-receipt-label--due">未收</span>
                                  <span className="cl-receipt-num cl-receipt-num--due">
                                    <span className="cl-cur">{cur}</span>{formatNumber(dueNum)}
                                  </span>
                                </>
                              )}
                            </div>
                          </div>

                          {/* 合同信息：业务摘要 + tag + 进度 */}
                          <div className="cl-ct-info">
                            <div className={`cl-info-desc${summary ? '' : ' is-empty'}`} title={summary}>
                              {summary || '—'}
                            </div>
                            {tags.length > 0 && (
                              <div className="cl-info-tags">
                                {tags.map(t => (
                                  <span key={t} className="cl-info-tag" title={t}>{t}</span>
                                ))}
                              </div>
                            )}
                            <div className="cl-info-progress">
                              <div className="cl-info-bar">
                                <div
                                  className={`cl-info-bar-fill cl-info-bar-fill--${progressState}`}
                                  style={{ width: `${pct}%` }}
                                />
                              </div>
                              <span className={`cl-info-pct cl-info-pct--${progressState}`}>
                                {pct}%
                              </span>
                              {stageText && (
                                <span className={`cl-info-stage${isDone ? ' is-done' : ''}`}>
                                  · <b>{ct.paid_count}</b>/{ct.payment_total_count} 期
                                </span>
                              )}
                            </div>
                          </div>
                        </div>
                      )
                    })}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}

      {/* 分页 */}
      {totalPages > 1 && (
        <div className="page-footer">
          <div className="page-footer-info">
            第 {page} / {totalPages} 页，共 {total} 位客户
          </div>
          <div className="page-footer-actions">
            <Button disabled={page <= 1} onClick={() => { setPage(1); window.scrollTo(0, 0) }}>首页</Button>
            <Button disabled={page <= 1} onClick={() => { setPage(p => p - 1); window.scrollTo(0, 0) }}>上一页</Button>
            <Button disabled={page >= totalPages} onClick={() => { setPage(p => p + 1); window.scrollTo(0, 0) }}>下一页</Button>
            <Button disabled={page >= totalPages} onClick={() => { setPage(totalPages); window.scrollTo(0, 0) }}>末页</Button>
          </div>
        </div>
      )}

      {/* 删除客户二次确认（5 秒读秒） */}
      <DangerConfirmModal
        open={!!deleteTarget}
        title="确认删除客户"
        description={deleteTarget && (
          <>
            即将删除客户 <strong>「{deleteTarget.name}」</strong>。
            {deleteTarget.contractCount > 0 && (
              <> 该客户名下有 <strong>{deleteTarget.contractCount}</strong> 份合同，<u>合同记录不会被一并删除</u>，仅断开客户关联。</>
            )}
          </>
        )}
        warning="删除后客户档案将无法恢复，请确认无误。"
        onConfirm={handleDeleteConfirmed}
        onCancel={() => { if (!deleting) setDeleteTarget(null) }}
        confirming={deleting}
      />
    </div>
  )
}
