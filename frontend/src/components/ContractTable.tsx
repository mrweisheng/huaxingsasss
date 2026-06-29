import { useState, useCallback } from 'react'
import { Table, Button, Progress, Image, Badge, Empty, Popconfirm, Tooltip, Popover, Input, DatePicker, message } from 'antd'
import {
  PlusOutlined, DeleteOutlined, FileTextOutlined, PrinterOutlined,
  EyeOutlined, CheckCircleOutlined, ClockCircleOutlined, ExclamationCircleOutlined,
  CaretRightOutlined, CarOutlined, SwapOutlined, SafetyCertificateOutlined,
} from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import type { ContractWithPayments } from '@/types'
import { contractApi } from '@/services/contract'
import ReceiptChatModal from './ReceiptChatModal'
import PaymentNoticeModal from './PaymentNoticeModal'
import { formatMoney } from '@/utils/money'
import dayjs from 'dayjs'
import './ContractTable.css'

interface Props {
  contracts: ContractWithPayments[]
  loading?: boolean
  onDeleteContract?: (id: number) => void
  onContractUpdated?: () => void
}

// 业务色徽章 + 图标
const BIZ_VISUAL: Record<string, { className: string; label: string; icon: React.ReactNode }> = {
  '车辆买卖': { className: 'biz-vehicle-tag', label: '车辆', icon: <CarOutlined /> },
  '车辆业务': { className: 'biz-vehicle-tag', label: '车辆', icon: <CarOutlined /> },
  '两地牌过户': { className: 'biz-cross-tag', label: '两地牌', icon: <SwapOutlined /> },
  '中港牌业务': { className: 'biz-cross-tag', label: '两地牌', icon: <SwapOutlined /> },
  '年检保险': { className: 'biz-insurance-tag', label: '年检保险', icon: <SafetyCertificateOutlined /> },
}

function getBizToneClass(type?: string): 'vehicle' | 'cross' | 'insurance' | 'default' {
  if (type === '车辆买卖' || type === '车辆业务') return 'vehicle'
  if (type === '两地牌过户' || type === '中港牌业务') return 'cross'
  if (type === '年检保险') return 'insurance'
  return 'default'
}

// 货币符号
const SYMBOL: Record<string, string> = { CNY: '¥', HKD: 'HK$' }

function calcProgress(paid: number, total: number): number {
  if (total === 0) return 0
  return Math.round((paid / total) * 100)
}

function fmt(amount: number, currency: string): string {
  const m = formatMoney(amount)
  const sym = SYMBOL[currency] || '¥'
  return `${sym}${m.display}${m.unit ?? ''}`
}

function fmtDate(d: string | undefined): string {
  if (!d) return '—'
  return dayjs(d).format('YYYY-MM-DD')
}

const VERIFY_ICONS: Record<string, React.ReactNode> = {
  passed: <CheckCircleOutlined style={{ color: '#0d9488', fontSize: 14 }} />,
  pending: <ClockCircleOutlined style={{ color: '#faad14', fontSize: 14 }} />,
  failed: <ExclamationCircleOutlined style={{ color: '#ff4d4f', fontSize: 14 }} />,
}

const VERIFY_LABELS: Record<string, string> = {
  passed: '核验通过',
  pending: '核验中',
  failed: '核验失败',
}

export default function ContractTable({ contracts, loading, onDeleteContract, onContractUpdated }: Props) {
  // 互斥展开：同一时间只展开一行
  const [expandedRowKey, setExpandedRowKey] = useState<number | null>(null)

  // 凭证录入弹窗（收入/支出）
  const [receiptModal, setReceiptModal] = useState<{ open: boolean; contract: ContractWithPayments | null; type: 'income' | 'expense' }>({ open: false, contract: null, type: 'income' })

  // 付款通知单弹窗
  const [noticeModal, setNoticeModal] = useState<{ open: boolean; contract: ContractWithPayments | null }>({ open: false, contract: null })

  // 内联编辑状态
  const [editingCell, setEditingCell] = useState<{ contractId: number; field: string } | null>(null)
  const [editValue, setEditValue] = useState<any>(null)
  const [saving, setSaving] = useState(false)

  // 凭证录入成功回调：刷新父级列表（已收金额/进度同步更新）
  const handleReceiptSuccess = useCallback(() => {
    setReceiptModal(prev => ({ ...prev, open: false }))
    onContractUpdated?.()
  }, [onContractUpdated])

  // 开始编辑
  const startEdit = useCallback((contractId: number, field: string, currentValue: any) => {
    setEditingCell({ contractId, field })
    setEditValue(currentValue)
  }, [])

  // 取消编辑
  const cancelEdit = useCallback(() => {
    setEditingCell(null)
    setEditValue(null)
  }, [])

  // 保存编辑
  const saveEdit = useCallback(async (contractId: number, field: string) => {
    if (saving) return
    setSaving(true)
    try {
      await contractApi.update(contractId, { [field]: editValue })
      message.success('修改成功')
      setEditingCell(null)
      setEditValue(null)
      onContractUpdated?.()
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '修改失败')
    } finally {
      setSaving(false)
    }
  }, [editValue, saving, onContractUpdated])

  const columns: ColumnsType<ContractWithPayments> = [
    {
      title: '签订日期',
      dataIndex: 'signed_date',
      key: 'signed_date',
      width: 100,
      render: (v, row) => {
        const isEditing = editingCell?.contractId === row.id && editingCell?.field === 'signed_date'
        if (isEditing) {
          return (
            <Popover
              open
              trigger="click"
              content={
                <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                  <DatePicker
                    size="small"
                    value={editValue ? dayjs(editValue) : null}
                    onChange={(d) => setEditValue(d ? d.format('YYYY-MM-DD') : null)}
                    style={{ width: 130 }}
                    allowClear
                  />
                  <Button size="small" type="primary" loading={saving} onClick={() => saveEdit(row.id, 'signed_date')}>保存</Button>
                  <Button size="small" onClick={cancelEdit}>取消</Button>
                </div>
              }
              onOpenChange={(open) => { if (!open) cancelEdit() }}
            >
              <span className="editable-cell">{fmtDate(v)}</span>
            </Popover>
          )
        }
        return (
          <span className="editable-cell" onDoubleClick={() => startEdit(row.id, 'signed_date', v)}>
            {fmtDate(v)}
          </span>
        )
      },
    },
    {
      title: '业务群',
      dataIndex: 'wechat_group',
      key: 'wechat_group',
      width: 170,
      render: (v, row) => {
        const biz = BIZ_VISUAL[row.business_type || '']
        const tone = getBizToneClass(row.business_type)
        const isEditing = editingCell?.contractId === row.id && editingCell?.field === 'wechat_group'

        if (isEditing) {
          return (
            <Popover
              open
              trigger="click"
              content={
                <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                  <Input
                    size="small"
                    value={editValue ?? ''}
                    onChange={(e) => setEditValue(e.target.value)}
                    placeholder="业务群名称"
                    style={{ width: 160 }}
                    onPressEnter={() => saveEdit(row.id, 'wechat_group')}
                    autoFocus
                  />
                  <Button size="small" type="primary" loading={saving} onClick={() => saveEdit(row.id, 'wechat_group')}>保存</Button>
                  <Button size="small" onClick={cancelEdit}>取消</Button>
                </div>
              }
              onOpenChange={(open) => { if (!open) cancelEdit() }}
            >
              <span className={`wechat-group-cell biz-tone-${tone} editable-cell`}>
                {biz && <span className="wechat-group-icon">{biz.icon}</span>}
                {v || <span className="text-muted">—</span>}
              </span>
            </Popover>
          )
        }

        if (!v && !biz) return <span className="text-muted">—</span>
        return (
          <span
            className={`wechat-group-cell biz-tone-${tone} editable-cell`}
            title={v || biz?.label}
            onDoubleClick={() => startEdit(row.id, 'wechat_group', v)}
          >
            {biz && <span className="wechat-group-icon">{biz.icon}</span>}
            {v || <span className="text-muted">—</span>}
          </span>
        )
      },
    },
    {
      title: '客户',
      dataIndex: 'customer_name',
      key: 'customer_name',
      width: 100,
      ellipsis: true,
      render: (v) => v || <span className="text-muted">未关联</span>,
    },
    {
      title: '合同描述',
      dataIndex: 'business_description',
      key: 'business_description',
      width: 180,
      render: (v, row) => (
        <span className="description-cell" title={v || row.title}>
          {v || row.title || <span className="text-muted">—</span>}
        </span>
      ),
    },
    {
      title: '源文件',
      key: 'original_file',
      width: 70,
      render: (_, row) => {
        if (!row.original_file_path) return <span className="text-muted">—</span>
        const ext = row.original_file_path.split('.').pop()?.toLowerCase()
        const isImg = ['png', 'jpg', 'jpeg', 'gif', 'webp', 'heic', 'heif'].includes(ext ?? '')
        if (isImg) {
          return (
            <Button size="small" type="text" icon={<EyeOutlined />} onClick={() => {
              const url = `${import.meta.env.VITE_API_BASE_URL || '/api/v1'}/contracts/${row.id}/file?token=${localStorage.getItem('access_token')}`
              window.open(url, '_blank')
            }}>
              预览
            </Button>
          )
        }
        return (
          <Button size="small" type="text" icon={<FileTextOutlined />} onClick={() => {
            const url = `${import.meta.env.VITE_API_BASE_URL || '/api/v1'}/contracts/${row.id}/file?token=${localStorage.getItem('access_token')}`
            window.open(url, '_blank')
          }}>
            下载
          </Button>
        )
      },
    },
    {
      title: '合同金额',
      dataIndex: 'total_amount',
      key: 'total_amount',
      width: 100,
      align: 'right',
      render: (v, row) => <span className="amount-text">{fmt(v, row.currency)}</span>,
    },
    {
      title: '已收',
      dataIndex: 'paid_amount',
      key: 'paid_amount',
      width: 90,
      align: 'right',
      render: (v, row) => <span className="amount-paid">{fmt(v, row.currency)}</span>,
    },
    {
      title: '剩余尾款',
      key: 'remaining',
      width: 90,
      align: 'right',
      render: (_, row) => {
        const receivable = Number(row.total_amount || 0)
        const paid = Number(row.paid_amount || 0)
        const unpaid = Math.max(0, receivable - paid)
        const overpaid = Math.max(0, paid - receivable)
        if (overpaid > 0) return <span className="amount-overpaid">+{fmt(overpaid, row.currency)}</span>
        return unpaid > 0 ? <span className="amount-unpaid">{fmt(unpaid, row.currency)}</span> : <Badge status="success" text="已结清" />
      },
    },
    {
      title: '成本',
      dataIndex: 'total_expense',
      key: 'total_expense',
      width: 90,
      align: 'right',
      render: (v, row) => <span className="amount-expense">{fmt(Number(v ?? 0), row.currency)}</span>,
    },
    {
      title: '利润',
      key: 'profit',
      width: 90,
      align: 'right',
      render: (_, row) => {
        const profit = Number(row.paid_amount ?? 0) - Number(row.total_expense ?? 0)
        return <span className={profit >= 0 ? 'amount-profit' : 'amount-loss'}>
          {profit < 0 ? '-' : ''}{fmt(Math.abs(profit), row.currency)}
        </span>
      },
    },
    {
      title: '付款进度',
      key: 'progress',
      width: 135,
      render: (_, row) => {
        const receivable = Number(row.total_amount || 0)
        const paid = Number(row.paid_amount || 0)
        const pct = calcProgress(paid, receivable)
        const capPct = Math.min(pct, 100)
        const color = capPct >= 100 ? '#0d9488' : capPct >= 70 ? '#faad14' : '#ff4d4f'
        return (
          <div className="progress-cell">
            <Progress
              percent={capPct}
              size={[65, 6]}
              strokeColor={color}
              showInfo={false}
              strokeLinecap="round"
            />
            <span className="progress-text" style={{ color }}>{capPct}%</span>
          </div>
        )
      },
    },
    {
      title: '操作',
      key: 'actions',
      width: 160,
      fixed: 'right',
      render: (_, row) => (
        <div className="table-actions">
          <Button
            size="small"
            type="text"
            icon={<PrinterOutlined />}
            onClick={(e) => { e.stopPropagation(); setNoticeModal({ open: true, contract: row }) }}
          >
            通知单
          </Button>
          {onDeleteContract && (
            <Popconfirm
              title="确认删除合同？"
              description="该合同名下的付款计划与收付款记录将一并删除。"
              okText="删除"
              cancelText="取消"
              okButtonProps={{ danger: true }}
              onConfirm={(e) => { e?.stopPropagation(); onDeleteContract(row.id) }}
              onCancel={(e) => e?.stopPropagation()}
            >
              <Button size="small" type="text" danger icon={<DeleteOutlined />}>
                删除
              </Button>
            </Popconfirm>
          )}
        </div>
      ),
    },
  ]

  // 展开行内容：付款条款 / 收入流水 / 支出流水
  const expandedRowRender = (row: ContractWithPayments) => {
    const incomePayments = (row.payments || []).filter(p => p.type === 'income')
    const expensePayments = (row.payments || []).filter(p => p.type === 'expense')

    return (
      <div className={`contract-expanded-content ${getBizToneClass(row.business_type)}`}>
        <div className="expanded-grid">

          {/* ─── 左侧：付款条款 ─── */}
          <div className="expanded-panel">
            <div className="expanded-panel-head">
              <span className="expanded-panel-title">付款条款</span>
              {(row.payments || []).length === 0 && <span className="expanded-panel-empty-hint">无付款计划</span>}
            </div>
            <div className="payment-terms-list">
              {row.contract_data?.payment_terms?.length > 0 ? (
                row.contract_data?.payment_terms.map((term: any, idx: number) => (
                  <div key={idx} className="term-item">
                    <div className="term-name">{term.name || `第${idx + 1}期`}</div>
                    <div className="term-amount">{fmt(term.amount, row.currency)}</div>
                    <div className="term-meta">
                      {term.due_date && <span className="term-date">{term.due_date}</span>}
                      {term.condition && <span className="term-condition">{term.condition}</span>}
                    </div>
                  </div>
                ))
              ) : (
                <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无付款计划" />
              )}
            </div>
          </div>

          {/* ─── 右侧：收入流水 ─── */}
          <div className="expanded-panel">
            <div className="expanded-panel-head">
              <span className="expanded-panel-title">收入流水</span>
              <Button
                size="small"
                type="text"
                icon={<PlusOutlined />}
                className="btn-income"
                onClick={() => setReceiptModal({ open: true, contract: row, type: 'income' })}
              >
                录入
              </Button>
            </div>
            {incomePayments.length === 0 ? (
              <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无收入记录" />
            ) : (
              <div className="payment-list">
                {incomePayments.map(p => (
                  <div key={p.id} className="payment-item income">
                    <div className="payment-main">
                      <div className="payment-name">{p.installment_name || p.description || '收入'}</div>
                      <div className="payment-amount">{fmt(p.paid_amount, p.currency)}</div>
                    </div>
                    <div className="payment-meta">
                      {p.paid_date && <span className="payment-date">{p.paid_date}</span>}
                      {p.payment_method && <span className="payment-method">{p.payment_method}</span>}
                      {p.verification_status && (
                        <Tooltip title={VERIFY_LABELS[p.verification_status] || p.verification_status}>
                          <span className="payment-verify">{VERIFY_ICONS[p.verification_status]}</span>
                        </Tooltip>
                      )}
                    </div>
                    {p.receipt_image_path && (
                      <div className="payment-proof">
                        <Image
                          width={32}
                          height={32}
                          src={`${import.meta.env.VITE_API_BASE_URL || '/api/v1'}/payments/${p.id}/receipt?token=${localStorage.getItem('access_token')}`}
                          preview={{ mask: <EyeOutlined />, maskClosable: true }}
                          className="receipt-thumb"
                        />
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* ─── 右侧：支出流水 ─── */}
          <div className="expanded-panel">
            <div className="expanded-panel-head">
              <span className="expanded-panel-title">支出流水</span>
              <Button
                size="small"
                type="text"
                icon={<PlusOutlined />}
                className="btn-expense"
                onClick={() => setReceiptModal({ open: true, contract: row, type: 'expense' })}
              >
                录入
              </Button>
            </div>
            {expensePayments.length === 0 ? (
              <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无支出记录" />
            ) : (
              <div className="payment-list expense">
                {expensePayments.map(p => (
                  <div key={p.id} className="payment-item expense">
                    <div className="payment-main">
                      <div className="payment-name">{p.installment_name || p.description || p.payee_name || '支出'}</div>
                      <div className="payment-amount">{fmt(p.paid_amount, p.currency)}</div>
                    </div>
                    <div className="payment-meta">
                      {p.paid_date && <span className="payment-date">{p.paid_date}</span>}
                      {p.payment_method && <span className="payment-method">{p.payment_method}</span>}
                      {p.payee_name && <span className="payment-payee">收款方：{p.payee_name}</span>}
                      {p.verification_status && (
                        <Tooltip title={VERIFY_LABELS[p.verification_status] || p.verification_status}>
                          <span className="payment-verify">{VERIFY_ICONS[p.verification_status]}</span>
                        </Tooltip>
                      )}
                    </div>
                    {p.receipt_image_path && (
                      <div className="payment-proof">
                        <Image
                          width={32}
                          height={32}
                          src={`${import.meta.env.VITE_API_BASE_URL || '/api/v1'}/payments/${p.id}/receipt?token=${localStorage.getItem('access_token')}`}
                          preview={{ mask: <EyeOutlined />, maskClosable: true }}
                          className="receipt-thumb"
                        />
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>

        </div>
      </div>
    )
  }

  return (
    <>
      <Table
        columns={columns}
        dataSource={contracts}
        rowKey="id"
        loading={loading}
        pagination={false}
        size="middle"
        className="contract-main-table"
        expandable={{
          expandedRowRender,
          expandedRowKeys: expandedRowKey != null ? [expandedRowKey] : [],
          onExpand: (expanded, record) => {
            setExpandedRowKey(expanded ? record.id : null)
          },
          expandIcon: ({ expanded, onExpand, record }) => (
            <span
              className={`contract-expand-icon${expanded ? ' expanded' : ''}`}
              onClick={(e) => { e.stopPropagation(); onExpand(record, e) }}
            >
              <CaretRightOutlined />
            </span>
          ),
          expandIconColumnIndex: 0,
          columnWidth: 36,
        }}
        rowClassName={(row) => {
          const classes: string[] = []
          const receivable = Number(row.total_amount || 0)
          const paid = Number(row.paid_amount || 0)
          if (paid >= receivable) classes.push('row-cleared')
          if (expandedRowKey === row.id) {
            classes.push('row-expanded-active', `row-biz-${getBizToneClass(row.business_type)}`)
          }
          return classes.join(' ')
        }}
        scroll={{ x: 1365 }}
      />

      {/* 凭证录入弹窗 */}
      {receiptModal.contract && (
        <ReceiptChatModal
          open={receiptModal.open}
          onClose={() => handleReceiptSuccess()}
          contractId={receiptModal.contract.id}
          contractNumber={receiptModal.contract.contract_number}
          customerName={receiptModal.contract.customer_name || ''}
          wechatGroup={receiptModal.contract.wechat_group || ''}
          businessType={receiptModal.contract.business_type}
          contractTitle={receiptModal.contract.business_description || receiptModal.contract.title}
          totalAmount={receiptModal.contract.total_amount}
          currency={receiptModal.contract.currency}
          status={receiptModal.contract.status}
          paymentType={receiptModal.type}
        />
      )}

      {/* 付款通知单弹窗 */}
      {noticeModal.contract && (
        <PaymentNoticeModal
          open={noticeModal.open}
          contract={noticeModal.contract}
          incomePayments={(noticeModal.contract.payments || []).filter(p => p.type === 'income')}
          onClose={() => setNoticeModal({ open: false, contract: null })}
        />
      )}
    </>
  )
}
