import { useState, useEffect, useCallback, useRef, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { Input, Select, Empty, message } from 'antd'
import {
  SearchOutlined,
  TeamOutlined,
  DeleteOutlined,
  FileTextOutlined,
  ExclamationCircleOutlined,
  CarOutlined,
  SwapOutlined,
  SafetyCertificateOutlined,
} from '@ant-design/icons'
import { useDebounce } from '@/hooks/useDebounce'
import { customerApi } from '@/services/customer'
import { contractApi } from '@/services/contract'
import { useAuthStore } from '@/store/useAuthStore'
import DangerConfirmModal from '@/components/DangerConfirmModal'
import { formatMoney } from '@/utils/money'
import { currencySymbol } from '@/utils/moneyFormat'
import type { Customer, Contract } from '@/types'
import './CustomerList.css'

interface CustomerWithContracts {
  customer: Customer
  contracts: Contract[]
}

// 扁平化后的表格行：每份合同一行；rowSpan = 该客户在客户列合并的行数（首行写 N，后续行 0）
interface TableRow {
  customer: Customer
  contract: Contract | null
  isFirstOfCustomer: boolean
  rowSpan: number
  isLastOfCustomer: boolean
  contractCount: number
}

// 业务徽章视觉映射（标准值 + legacy 兼容）
type BizTone = 'vehicle' | 'cross' | 'insurance' | 'other'
const BIZ_VISUAL: Record<string, { tone: BizTone; label: string; icon: React.ReactNode }> = {
  '车辆买卖': { tone: 'vehicle', label: '车辆', icon: <CarOutlined /> },
  '车辆业务': { tone: 'vehicle', label: '车辆', icon: <CarOutlined /> },
  '两地牌过户': { tone: 'cross', label: '两地牌', icon: <SwapOutlined /> },
  '中港牌业务': { tone: 'cross', label: '两地牌', icon: <SwapOutlined /> },
  '年检保险': { tone: 'insurance', label: '年检保险', icon: <SafetyCertificateOutlined /> },
}

function getBizVisual(type?: string) {
  if (!type) return { tone: 'other' as BizTone, label: '其他', icon: <FileTextOutlined /> }
  return BIZ_VISUAL[type] || { tone: 'other' as BizTone, label: type, icon: <FileTextOutlined /> }
}

function calcProgress(paid: number, total: number): number {
  if (!total || total <= 0) return 0
  return Math.min(100, Math.round((Number(paid) / Number(total)) * 100))
}

// 合同摘要：优先 business_description，其次 title，再次合同号
function getContractDesc(ct: Contract): string {
  return (ct.business_description || '').trim()
    || (ct.title || '').trim()
    || ct.contract_number
    || '未命名合同'
}

// 期数 / 签订日的副信息
function getContractSubMeta(ct: Contract): string {
  const parts: string[] = []
  if (ct.signed_date) {
    const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(ct.signed_date)
    parts.push(m ? `签订 ${m[1]}-${m[2]}-${m[3]}` : `签订 ${ct.signed_date}`)
  }
  const total = Number(ct.payment_total_count || 0)
  if (total > 0) parts.push(`${ct.paid_count || 0}/${total} 期`)
  return parts.join(' · ')
}

// 扁平化数据
function flattenRows(items: CustomerWithContracts[]): TableRow[] {
  const rows: TableRow[] = []
  for (const { customer, contracts } of items) {
    if (contracts.length === 0) {
      rows.push({
        customer, contract: null,
        isFirstOfCustomer: true, isLastOfCustomer: true,
        rowSpan: 1, contractCount: 0,
      })
    } else {
      contracts.forEach((contract, idx) => {
        rows.push({
          customer, contract,
          isFirstOfCustomer: idx === 0,
          isLastOfCustomer: idx === contracts.length - 1,
          rowSpan: idx === 0 ? contracts.length : 0,
          contractCount: contracts.length,
        })
      })
    }
  }
  return rows
}

// 金额渲染：拆 display + unit，单位字号略小
function AmountCell({ value, currency, kind }: { value: number; currency: string; kind: 'total' | 'paid' | 'done' | 'zero' }) {
  const m = formatMoney(value)
  const sym = currencySymbol[currency] || '¥'
  return (
    <span className={`cl-amount cl-amount--${kind}`}>
      <span className="cl-amount-cur">{sym}</span>
      {m.display}
      {m.unit ? <span className="cl-amount-unit">{m.unit}</span> : null}
    </span>
  )
}

export default function CustomerList() {
  const navigate = useNavigate()
  const role = useAuthStore(s => s.user?.role || '')
  const isAdmin = role === 'admin'
  const [items, setItems] = useState<CustomerWithContracts[]>([])
  const [loading, setLoading] = useState(false)
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(10)
  const [totalPages, setTotalPages] = useState(1)
  const [keyword, setKeyword] = useState('')
  const abortControllerRef = useRef<AbortController | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<{ id: number; name: string; contractCount: number } | null>(null)
  const [deleting, setDeleting] = useState(false)

  const loadData = useCallback(async () => {
    abortControllerRef.current?.abort()
    const controller = new AbortController()
    abortControllerRef.current = controller

    setLoading(true)
    try {
      const response = await customerApi.getList(
        { page, per_page: pageSize, keyword: keyword || undefined },
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
  }, [page, pageSize, keyword])

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

  const rows = useMemo(() => flattenRows(items), [items])
  const totalContracts = useMemo(
    () => items.reduce((sum, it) => sum + it.contracts.length, 0),
    [items],
  )

  // 顶部封条期号 / 时间戳
  const now = new Date()
  const period = `CLIENT REGISTER · ${now.getFullYear()} / Q${Math.floor(now.getMonth() / 3) + 1}`
  const stamp = `${now.getFullYear()} · ${String(now.getMonth() + 1).padStart(2, '0')} · ${String(now.getDate()).padStart(2, '0')} · ${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`

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
            <span className="cl-head-stats">
              <span><b>{total}</b> 位客户</span>
              <span className="cl-stat-divider" />
              <span><b>{totalContracts}</b> 份合同</span>
            </span>
          </div>
        </div>
        <div className="page-topbar-right">
          <Input
            placeholder="搜索客户名称 / 电话 / 证件号"
            allowClear
            onChange={e => handleSearch(e.target.value)}
            style={{ width: 280 }}
            prefix={<SearchOutlined />}
          />
        </div>
      </div>

      {/* 账册式表格 */}
      <div className="cl-ledger-wrap">
        <div className="cl-ledger-head">
          <div>
            <span className="cl-seal">华星 · 客户档册</span>
            <span className="cl-period">{period}</span>
          </div>
          <div className="cl-head-right">
            本页 <b>{items.length}</b> 位客户 · 共 <b>{totalContracts}</b> 份合同
          </div>
        </div>

        {loading && rows.length === 0 ? (
          <div className="cl-skeleton-wrap">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="cl-skel-row">
                <div className="cl-skel-block cl-skel-customer" />
                <div className="cl-skel-block cl-skel-line" />
              </div>
            ))}
          </div>
        ) : rows.length === 0 && !loading ? (
          <div className="cl-empty-state">
            <Empty description="暂无客户" />
          </div>
        ) : (
          <table className="cl-table">
            <thead>
              <tr>
                <th>客户档案<span className="th-sub">CLIENT</span></th>
                <th>业务<span className="th-sub">TYPE</span></th>
                <th>合同编号<span className="th-sub">NO.</span></th>
                <th>合同描述<span className="th-sub">DESCRIPTION</span></th>
                <th className="th-right">合同金额<span className="th-sub">AMOUNT</span></th>
                <th className="th-right">已收<span className="th-sub">RECEIVED</span></th>
                <th>付款进度<span className="th-sub">PROGRESS</span></th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => {
                const { customer: c, contract: ct } = row
                const rowKey = `${c.id}-${ct?.id ?? 'empty'}`

                return (
                  <tr
                    key={rowKey}
                    className={`cl-row ${row.isFirstOfCustomer ? 'is-first-of-customer' : ''} ${row.isLastOfCustomer ? 'is-last-of-customer' : ''}`}
                  >
                    {/* 客户列：只在该客户的第一行渲染，rowSpan 撑满 */}
                    {row.isFirstOfCustomer && (
                      <td className="cell-customer" rowSpan={row.rowSpan}>
                        <div className="cl-customer-name-row">
                          <span className="cl-customer-name" title={c.name}>{c.name}</span>
                          <span className={`cl-customer-count${row.contractCount === 0 ? ' is-empty' : ''}`}>
                            · {row.contractCount} 份
                          </span>
                          {isAdmin && (
                            <button
                              className="cl-btn-del-icon"
                              title="删除客户"
                              onClick={() => setDeleteTarget({
                                id: c.id,
                                name: c.name,
                                contractCount: row.contractCount,
                              })}
                            >
                              <DeleteOutlined />
                            </button>
                          )}
                        </div>
                        {(c.phone || c.id_card_number) && (
                          <div className="cl-customer-lines">
                            {c.phone && (
                              <div className="cl-customer-line">
                                <span className="cl-line-label">TEL</span>
                                <span className="cl-line-val" title={c.phone}>{c.phone}</span>
                              </div>
                            )}
                            {c.id_card_number && (
                              <div className="cl-customer-line">
                                <span className="cl-line-label">ID</span>
                                <span className="cl-line-val" title={c.id_card_number}>{c.id_card_number}</span>
                              </div>
                            )}
                          </div>
                        )}
                      </td>
                    )}

                    {/* 合同区：空档案 colSpan=6 占满 */}
                    {ct === null ? (
                      <td className="cell-empty-contracts" colSpan={6}>
                        <span className="cl-empty-msg">
                          <ExclamationCircleOutlined />
                          该客户档案下暂无关联合同
                        </span>
                      </td>
                    ) : (() => {
                      const biz = getBizVisual(ct.business_type)
                      const receivable = Number(ct.total_amount || 0)
                      const paidNum = Number((ct.paid_by_currency || {})[ct.currency] ?? ct.paid_amount ?? 0)
                      const pct = calcProgress(paidNum, receivable)
                      const isDone = pct >= 100
                      const isZeroPaid = paidNum < 0.005
                      const progressState = isDone ? 'full' : pct > 0 ? 'partial' : 'empty'
                      const desc = getContractDesc(ct)
                      const subMeta = getContractSubMeta(ct)
                      const paidKind: 'done' | 'zero' | 'paid' = isDone ? 'done' : isZeroPaid ? 'zero' : 'paid'

                      return (
                        <>
                          <td className="cell-contract">
                            <span className={`cl-biz-tag cl-biz-tag--${biz.tone}`}>
                              <span className="cl-biz-tag-icon">{biz.icon}</span>
                              {biz.label}
                            </span>
                          </td>
                          <td className="cell-contract">
                            <a
                              className="cl-contract-no"
                              title={ct.contract_number}
                              onClick={() => navigate(`/contracts/${ct.id}`)}
                            >
                              {ct.contract_number}
                            </a>
                          </td>
                          <td className="cell-contract cell-desc">
                            <div className="cl-contract-desc" title={desc}>{desc}</div>
                            {subMeta && <span className="cl-contract-sub">{subMeta}</span>}
                          </td>
                          <td className="cell-contract cell-right">
                            <AmountCell value={receivable} currency={ct.currency} kind="total" />
                          </td>
                          <td className="cell-contract cell-right">
                            <AmountCell value={paidNum} currency={ct.currency} kind={paidKind} />
                          </td>
                          <td className="cell-contract">
                            <div className="cl-progress-cell">
                              <div className="cl-progress-track">
                                <div
                                  className={`cl-progress-fill cl-progress-fill--${progressState}`}
                                  style={{ width: `${pct}%` }}
                                />
                              </div>
                              <span className={`cl-progress-pct cl-progress-pct--${progressState}`}>
                                {pct}%
                              </span>
                            </div>
                          </td>
                        </>
                      )
                    })()}
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}

        {/* 底部脚标 + 分页 */}
        <div className="cl-ledger-foot">
          <span className="cl-stamp">截至 {stamp}</span>
          <div className="cl-pager">
            <div className="cl-page-size">
              <span>每页</span>
              <Select
                value={pageSize}
                onChange={(val) => { setPageSize(val); setPage(1); window.scrollTo(0, 0) }}
                options={[
                  { value: 10, label: '10' },
                  { value: 20, label: '20' },
                  { value: 50, label: '50' },
                ]}
                size="small"
                popupMatchSelectWidth={false}
              />
              <span>条</span>
            </div>
            <span className="cl-pager-total-info">共 {total} 条</span>
            {totalPages > 1 && (
              <>
                <button disabled={page <= 1} onClick={() => { setPage(1); window.scrollTo(0, 0) }}>首页</button>
                <button disabled={page <= 1} onClick={() => { setPage(p => p - 1); window.scrollTo(0, 0) }}>上一页</button>
                <span className="cl-pager-current">{page}</span>
                <span className="cl-pager-sep">/</span>
                <span className="cl-pager-total">{totalPages}</span>
                <button disabled={page >= totalPages} onClick={() => { setPage(p => p + 1); window.scrollTo(0, 0) }}>下一页</button>
                <button disabled={page >= totalPages} onClick={() => { setPage(totalPages); window.scrollTo(0, 0) }}>末页</button>
              </>
            )}
          </div>
        </div>
      </div>

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
