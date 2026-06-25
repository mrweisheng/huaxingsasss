import { useState, useEffect, useCallback, useRef } from 'react'
import { Input, Select, DatePicker, Button, message, Empty, Popover, Pagination } from 'antd'
import { PlusOutlined, SearchOutlined, FilterOutlined, FileTextOutlined, DownloadOutlined } from '@ant-design/icons'
import { contractApi } from '@/services/contract'
import { useAuthStore } from '@/store/useAuthStore'
import ContractChatModal from '@/components/ContractChatModal'
import ContractTable from '@/components/ContractTable'
import DangerConfirmModal from '@/components/DangerConfirmModal'
import type { ContractWithPayments } from '@/types'
import dayjs from 'dayjs'
import { formatMoney } from '@/utils/money'
import { exportLedger } from '@/utils/exportLedger'
import './ContractList.css'

const { RangePicker } = DatePicker

export default function ContractList() {
  const user = useAuthStore(s => s.user)
  const role = user?.role || ''
  const [contracts, setContracts] = useState<ContractWithPayments[]>([])
  const [loading, setLoading] = useState(false)
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [keyword, setKeyword] = useState('')
  const [statusFilter, setStatusFilter] = useState<string | undefined>(undefined)
  const [dateRange, setDateRange] = useState<[dayjs.Dayjs | null, dayjs.Dayjs | null] | null>(null)
  const [uploadModalOpen, setUploadModalOpen] = useState(false)
  const abortControllerRef = useRef<AbortController | null>(null)
  const searchTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  // 删除二次确认弹窗状态
  const [deleteTarget, setDeleteTarget] = useState<{ id: number; number: string; title: string } | null>(null)
  const [deleting, setDeleting] = useState(false)
  // 导出台账
  const [exportDateRange, setExportDateRange] = useState<[dayjs.Dayjs | null, dayjs.Dayjs | null]>([
    dayjs().subtract(30, 'day'),
    dayjs(),
  ])
  const [exporting, setExporting] = useState(false)

  // 始终走 ContractWithPayments（表格展开行需要收支明细）
  const loadContracts = useCallback(async () => {
    abortControllerRef.current?.abort()
    const controller = new AbortController()
    abortControllerRef.current = controller

    setLoading(true)
    try {
      const params: any = { page, per_page: 20, customer_name: keyword || undefined }
      if (statusFilter) params.status = statusFilter
      if (dateRange && dateRange[0] && dateRange[1]) {
        params.date_from = dateRange[0].format('YYYY-MM-DD')
        params.date_to = dateRange[1].format('YYYY-MM-DD')
      }
      const response = await contractApi.getListWithPayments(params, controller.signal)
      setContracts(response.items)
      setTotal(response.pagination.total)
    } catch (error: any) {
      if (error?.name === 'AbortError' || error?.code === 'ERR_CANCELED') return
      console.error(error)
    } finally {
      if (!controller.signal.aborted) {
        setLoading(false)
      }
    }
  }, [page, keyword, statusFilter, dateRange])

  useEffect(() => {
    loadContracts()
    return () => {
      abortControllerRef.current?.abort()
      if (searchTimerRef.current) clearTimeout(searchTimerRef.current)
    }
  }, [loadContracts])

  const handleSearch = (e: React.ChangeEvent<HTMLInputElement> | undefined) => {
    const value = e?.target?.value ?? ''
    if (searchTimerRef.current) clearTimeout(searchTimerRef.current)
    searchTimerRef.current = setTimeout(() => {
      setKeyword(value)
      setPage(1)
    }, 400)
  }

  const handleStatusChange = (value: string | undefined) => {
    setStatusFilter(value)
    setPage(1)
  }

  const handleDateChange = (dates: [dayjs.Dayjs | null, dayjs.Dayjs | null] | null) => {
    setDateRange(dates)
    setPage(1)
  }

  const handleDelete = (id: number) => {
    const ct = contracts.find(c => c.id === id)
    setDeleteTarget({
      id,
      number: ct?.contract_number || String(id),
      title: ct?.business_description || ct?.title || '',
    })
  }

  const handleDeleteConfirmed = async () => {
    if (!deleteTarget) return
    setDeleting(true)
    try {
      await contractApi.delete(deleteTarget.id)
      message.success('删除成功')
      setDeleteTarget(null)
      loadContracts()
    } catch (error: any) {
      message.error(error.response?.data?.detail || '删除失败')
    } finally {
      setDeleting(false)
    }
  }

  const handleExport = async () => {
    if (!exportDateRange || !exportDateRange[0] || !exportDateRange[1]) {
      message.warning('请选择导出日期范围')
      return
    }
    setExporting(true)
    try {
      await exportLedger({
        dateFrom: exportDateRange[0].format('YYYY-MM-DD'),
        dateTo: exportDateRange[1].format('YYYY-MM-DD'),
      })
      message.success('导出成功')
    } catch (e: any) {
      message.error(e.message || '导出失败')
    } finally {
      setExporting(false)
    }
  }

  // 汇总条：按当前页累加，按币种分组
  const summary = (() => {
    const agg: Record<string, { total: number; paid: number; expense: number }> = {}
    for (const c of contracts) {
      const cur = c.currency || 'CNY'
      if (!agg[cur]) agg[cur] = { total: 0, paid: 0, expense: 0 }
      // 合同总额含附加项折算
      const addl = c.additional_total_in_contract_currency != null
        ? Number(c.additional_total_in_contract_currency) : 0
      agg[cur].total += Number(c.total_amount || 0) + addl
      agg[cur].paid += Number(c.paid_amount || 0)
      agg[cur].expense += Number(c.total_expense || 0)
    }
    return agg
  })()
  const summaryCurrencies = Object.keys(summary)
  const formatSumVal = (n: number) => {
    const m = formatMoney(n)
    return m.unit ? `${m.display}${m.unit}` : m.display
  }
  const currencySymbol2: Record<string, string> = { CNY: '¥', HKD: 'HK$' }

  return (
    <div className="contract-list-container">
      <div className="page-topbar">
        <div className="page-topbar-left">
          <div className="page-title-wrap">
            <div className="page-title-icon">
              <FileTextOutlined />
            </div>
            <span className="page-title-text">合同管理</span>
            <span className="page-title-count">{total} 个合同</span>
          </div>
        </div>
        <div className="page-topbar-right">
          <Input
            placeholder="搜索客户名称 / 业务群..."
            allowClear
            onChange={handleSearch}
            style={{ width: 220 }}
            prefix={<SearchOutlined />}
          />
          <Select
            placeholder="状态"
            allowClear
            style={{ width: 110 }}
            value={statusFilter}
            onChange={handleStatusChange}
            suffixIcon={<FilterOutlined />}
            options={[
              { label: '执行中', value: 'active' },
              { label: '已完成', value: 'completed' },
            ]}
          />
          <div className="date-range-wrap">
            <span className="date-range-label">签订日期</span>
            <RangePicker
              onChange={handleDateChange}
              value={dateRange}
            />
          </div>
          {(role === 'admin' || role === 'income') && (
            <Button type="primary" icon={<PlusOutlined />} onClick={() => setUploadModalOpen(true)}>
              上传
            </Button>
          )}
          <Popover
            content={
              <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                <RangePicker
                  value={exportDateRange}
                  onChange={(dates) => setExportDateRange(dates as any)}
                  size="small"
                  style={{ width: 240 }}
                  placeholder={['开始日期', '结束日期']}
                />
                <Button
                  size="small"
                  type="primary"
                  loading={exporting}
                  onClick={handleExport}
                >
                  确认导出
                </Button>
              </div>
            }
            title="导出台账"
            trigger="click"
            placement="bottomRight"
          >
            <Button icon={<DownloadOutlined />}>导出台账</Button>
          </Popover>
        </div>
      </div>

      {/* 汇总条 */}
      {contracts.length > 0 && (
        <div className="ledger-summary-strip">
          <div className="summary-block">
            <div className="summary-block-title"><span className="dot primary" />合同总额</div>
            <div className="summary-currency-rows">
              {summaryCurrencies.map(cur => (
                <div key={cur} className="summary-currency-row">
                  <span className="summary-sym">{currencySymbol2[cur] || cur}</span>
                  <span className="summary-val primary">{formatSumVal(summary[cur].total)}</span>
                </div>
              ))}
            </div>
          </div>
          <div className="summary-block">
            <div className="summary-block-title"><span className="dot gold" />已收</div>
            <div className="summary-currency-rows">
              {summaryCurrencies.map(cur => (
                <div key={cur} className="summary-currency-row">
                  <span className="summary-sym">{currencySymbol2[cur] || cur}</span>
                  <span className="summary-val gold">{formatSumVal(summary[cur].paid)}</span>
                </div>
              ))}
            </div>
          </div>
          <div className="summary-block">
            <div className="summary-block-title"><span className="dot orange" />支出</div>
            <div className="summary-currency-rows">
              {summaryCurrencies.map(cur => (
                <div key={cur} className="summary-currency-row">
                  <span className="summary-sym">{currencySymbol2[cur] || cur}</span>
                  <span className="summary-val orange">{formatSumVal(summary[cur].expense)}</span>
                </div>
              ))}
            </div>
          </div>
          <div className="summary-block">
            <div className="summary-block-title"><span className="dot teal" />净利润<span style={{ marginLeft: 6, fontSize: 9, opacity: 0.6 }}>本页</span></div>
            <div className="summary-currency-rows">
              {summaryCurrencies.map(cur => {
                const p = summary[cur].paid - summary[cur].expense
                return (
                  <div key={cur} className="summary-currency-row">
                    <span className="summary-sym">{currencySymbol2[cur] || cur}</span>
                    <span className={`summary-val ${p >= 0 ? 'teal' : 'orange'}`}>
                      {p < 0 ? '-' : ''}{formatSumVal(Math.abs(p))}
                    </span>
                  </div>
                )
              })}
            </div>
          </div>
        </div>
      )}

      {loading && contracts.length === 0 ? (
        <div className="table-skeleton" style={{ minHeight: 400, padding: 16 }}>
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="ct-skel-block ct-skel-line ct-skel-w-100" style={{ marginBottom: 12 }} />
          ))}
        </div>
      ) : contracts.length === 0 && !loading ? (
        <Empty description="暂无合同数据" className="empty-state" />
      ) : (
        <>
          <ContractTable
            contracts={contracts}
            loading={loading}
            onDeleteContract={role === 'admin' ? handleDelete : undefined}
            onContractUpdated={loadContracts}
          />

          {total > 0 && (
            <div className="table-pagination-wrapper">
              <Pagination
                current={page}
                pageSize={20}
                total={total}
                onChange={setPage}
                showSizeChanger={false}
                showQuickJumper
                showTotal={(total, range) => `第 ${range[0]}-${range[1]} 条，共 ${total} 条`}
              />
            </div>
          )}
        </>
      )}

      <ContractChatModal
        open={uploadModalOpen}
        onClose={(created) => { setUploadModalOpen(false); if (created) loadContracts() }}
      />

      {/* 删除合同二次确认（5 秒读秒） */}
      <DangerConfirmModal
        open={!!deleteTarget}
        title="确认删除合同"
        description={deleteTarget && (
          <>
            即将删除合同 <strong>{deleteTarget.number}</strong>
            {deleteTarget.title ? <>（{deleteTarget.title}）</> : null}。
            该合同名下的<strong>付款计划与收付款记录将一并删除</strong>。
          </>
        )}
        warning="此操作不可撤销，金额统计、客户回款状态都会受影响。"
        onConfirm={handleDeleteConfirmed}
        onCancel={() => { if (!deleting) setDeleteTarget(null) }}
        confirming={deleting}
      />
    </div>
  )
}
