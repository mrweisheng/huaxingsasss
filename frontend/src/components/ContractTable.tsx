import { useState, useCallback, useEffect } from 'react'
import { Table, Button, Tag, Progress, Image, Badge, Empty, message, Popconfirm, Tooltip } from 'antd'
import {
  PlusOutlined, EditOutlined, DeleteOutlined, FileTextOutlined, PrinterOutlined,
  EyeOutlined, CheckCircleOutlined, ClockCircleOutlined, ExclamationCircleOutlined,
} from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import type { ContractWithPayments, ContractAdditionalItem } from '@/types'
import AdditionalItemFormModal from './AdditionalItemFormModal'
import ReceiptChatModal from './ReceiptChatModal'
import PaymentNoticeModal from './PaymentNoticeModal'
import { additionalItemApi } from '@/services/contractAdditionalItem'
import { formatMoney } from '@/utils/money'
import dayjs from 'dayjs'
import './ContractTable.css'

interface Props {
  contracts: ContractWithPayments[]
  loading?: boolean
  onDeleteContract?: (id: number) => void
  onContractUpdated?: () => void
}

// 业务色徽章
const BIZ_VISUAL: Record<string, { className: string; label: string }> = {
  '车辆买卖': { className: 'biz-vehicle-tag', label: '车辆' },
  '车辆业务': { className: 'biz-vehicle-tag', label: '车辆' },
  '两地牌过户': { className: 'biz-cross-tag', label: '两地牌' },
  '中港牌业务': { className: 'biz-cross-tag', label: '两地牌' },
  '年检保险': { className: 'biz-insurance-tag', label: '年检保险' },
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
  passed: <CheckCircleOutlined style={{ color: '#52c41a', fontSize: 14 }} />,
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

  // 附加项明细（按合同 ID 懒加载）
  const [additionalItems, setAdditionalItems] = useState<Record<number, ContractAdditionalItem[]>>({})
  const [additionalLoading, setAdditionalLoading] = useState<Record<number, boolean>>({})

  // 附加项弹窗
  const [addlModal, setAddlModal] = useState<{ open: boolean; contractId: number; contractCurrency: string; editing?: ContractAdditionalItem | null }>({ open: false, contractId: 0, contractCurrency: 'CNY' })

  // 凭证录入弹窗（收入/支出）
  const [receiptModal, setReceiptModal] = useState<{ open: boolean; contract: ContractWithPayments | null; type: 'income' | 'expense' }>({ open: false, contract: null, type: 'income' })

  // 付款通知单弹窗
  const [noticeModal, setNoticeModal] = useState<{ open: boolean; contract: ContractWithPayments | null }>({ open: false, contract: null })

  // 展开时懒加载附加项明细
  useEffect(() => {
    if (expandedRowKey == null) return
    if (additionalItems[expandedRowKey] != null) return  // 已加载过，跳过

    const load = async () => {
      setAdditionalLoading(prev => ({ ...prev, [expandedRowKey]: true }))
      try {
        const items = await additionalItemApi.list(expandedRowKey)
        setAdditionalItems(prev => ({ ...prev, [expandedRowKey]: items }))
      } catch (e) {
        console.error(e)
        message.error('加载附加项失败')
      } finally {
        setAdditionalLoading(prev => ({ ...prev, [expandedRowKey]: false }))
      }
    }

    load()
  }, [expandedRowKey])

  // 附加项操作成功回调：刷新当前合同的附加项列表，并通知父级刷新合同汇总（附加项总额）
  const handleAddlSuccess = useCallback(() => {
    if (expandedRowKey == null) return
    // 清除缓存，下次展开重新拉取（保证附加项总金额同步更新）
    setAdditionalItems(prev => {
      const next = { ...prev }
      delete next[expandedRowKey]
      return next
    })
    onContractUpdated?.()
  }, [expandedRowKey, onContractUpdated])

  const handleDeleteAddlItem = useCallback((itemId: number) => {
    additionalItemApi.remove(itemId)
      .then(() => {
        message.success('附加项已删除')
        handleAddlSuccess()
      })
      .catch((e: any) => message.error(e?.response?.data?.detail || '删除失败'))
  }, [handleAddlSuccess])

  // 凭证录入成功回调：刷新父级列表（已收金额/进度同步更新）
  const handleReceiptSuccess = useCallback(() => {
    setReceiptModal(prev => ({ ...prev, open: false }))
    onContractUpdated?.()
  }, [onContractUpdated])

  const columns: ColumnsType<ContractWithPayments> = [
    {
      title: '签订日期',
      dataIndex: 'signed_date',
      key: 'signed_date',
      width: 100,
      render: (v) => fmtDate(v),
    },
    {
      title: '业务',
      dataIndex: 'business_type',
      key: 'business_type',
      width: 90,
      render: (t) => {
        const v = BIZ_VISUAL[t]
        if (v) return <Tag className={v.className}>{v.label}</Tag>
        return t ? <Tag>{t}</Tag> : <span className="text-muted">—</span>
      },
    },
    {
      title: '业务群',
      dataIndex: 'wechat_group',
      key: 'wechat_group',
      width: 110,
      ellipsis: true,
      render: (v) => v ? <span title={v}>{v}</span> : <span className="text-muted">—</span>,
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
      ellipsis: true,
      render: (v, row) => v || row.title || <span className="text-muted">—</span>,
    },
    {
      title: '源文件',
      key: 'original_file',
      width: 90,
      render: (_, row) => {
        if (!row.original_file_path) return <span className="text-muted">—</span>
        const ext = row.original_file_path.split('.').pop()?.toLowerCase()
        const isImg = ['png', 'jpg', 'jpeg', 'gif', 'webp', 'heic', 'heif'].includes(ext ?? '')
        if (isImg) {
          return (
            <Button size="small" type="text" icon={<EyeOutlined />} onClick={() => {
              const url = `${import.meta.env.VITE_API_BASE_URL || '/api/v1'}/contracts/${row.id}/file?token=${localStorage.getItem('token')}`
              window.open(url, '_blank')
            }}>
              预览
            </Button>
          )
        }
        return (
          <Button size="small" type="text" icon={<FileTextOutlined />} onClick={() => {
            const url = `${import.meta.env.VITE_API_BASE_URL || '/api/v1'}/contracts/${row.id}/file?token=${localStorage.getItem('token')}`
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
      width: 115,
      align: 'right',
      render: (v, row) => <span className="amount-text">{fmt(v, row.currency)}</span>,
    },
    {
      title: '已收',
      dataIndex: 'paid_amount',
      key: 'paid_amount',
      width: 100,
      align: 'right',
      render: (v, row) => <span className="amount-paid">{fmt(v, row.currency)}</span>,
    },
    {
      title: '剩余尾款',
      key: 'remaining',
      width: 100,
      align: 'right',
      render: (_, row) => {
        const total = Number(row.total_amount || 0)
        const addl = Number(row.additional_total_in_contract_currency ?? 0)
        const receivable = total + addl
        const unpaid = Math.max(0, receivable - Number(row.paid_amount || 0))
        const overpaid = Math.max(0, Number(row.paid_amount || 0) - receivable)
        if (overpaid > 0) return <span className="amount-overpaid">+{fmt(overpaid, row.currency)}</span>
        return unpaid > 0 ? <span className="amount-unpaid">{fmt(unpaid, row.currency)}</span> : <Badge status="success" text="已结清" />
      },
    },
    {
      title: '成本',
      dataIndex: 'total_expense',
      key: 'total_expense',
      width: 100,
      align: 'right',
      render: (v, row) => <span className="amount-expense">{fmt(Number(v ?? 0), row.currency)}</span>,
    },
    {
      title: '利润',
      key: 'profit',
      width: 100,
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
        const total = Number(row.total_amount || 0)
        const addl = Number(row.additional_total_in_contract_currency ?? 0)
        const receivable = total + addl
        const paid = Number(row.paid_amount || 0)
        const pct = calcProgress(paid, receivable)
        const capPct = Math.min(pct, 100)
        const color = capPct >= 100 ? '#52c41a' : capPct >= 70 ? '#faad14' : '#ff4d4f'
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

  // 展开行内容：付款条款 / 附加项 / 收入流水 / 支出流水
  const expandedRowRender = (row: ContractWithPayments) => {
    const addlItems = additionalItems[row.id] || []
    const isLoading = additionalLoading[row.id]
    const incomePayments = (row.payments || []).filter(p => p.type === 'income')
    const expensePayments = (row.payments || []).filter(p => p.type === 'expense')

    return (
      <div className="contract-expanded-content">
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

          {/* ─── 中间：附加项 ─── */}
          <div className="expanded-panel">
            <div className="expanded-panel-head">
              <span className="expanded-panel-title">附加项</span>
              <Button
                size="small"
                type="text"
                icon={<PlusOutlined />}
                onClick={() => setAddlModal({ open: true, contractId: row.id, contractCurrency: row.currency })}
              >
                新增
              </Button>
            </div>
            {isLoading ? (
              <div className="expanded-loading">加载中...</div>
            ) : addlItems.length === 0 ? (
              <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无附加项" />
            ) : (
              <div className="additional-list">
                {addlItems.map(item => (
                  <div key={item.id} className="additional-item">
                    <div className="addl-main">
                      <div className="addl-name">{item.name}</div>
                      <div className="addl-amount">{fmt(item.amount, item.currency)}</div>
                    </div>
                    <div className="addl-meta">
                      {item.paid_to && <span className="addl-paid-to">付给：{item.paid_to}</span>}
                      {item.occurred_date && <span className="addl-date">{item.occurred_date}</span>}
                    </div>
                    <div className="addl-actions">
                      <Button size="small" type="text" icon={<EditOutlined />} onClick={() => {
                        setAddlModal({ open: true, contractId: row.id, contractCurrency: row.currency, editing: item })
                      }}>
                        编辑
                      </Button>
                      <Popconfirm
                        title="删除附加项？"
                        okText="删除"
                        cancelText="取消"
                        okButtonProps={{ danger: true }}
                        onConfirm={() => handleDeleteAddlItem(item.id)}
                      >
                        <Button size="small" type="text" danger icon={<DeleteOutlined />}>
                          删除
                        </Button>
                      </Popconfirm>
                    </div>
                  </div>
                ))}
              </div>
            )}
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
                          src={`${import.meta.env.VITE_API_BASE_URL || '/api/v1'}/payments/${p.id}/receipt`}
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

          {/* ─── 底部：支出流水（横跨全部宽度） ─── */}
          <div className="expanded-panel span-3">
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
                          src={`${import.meta.env.VITE_API_BASE_URL || '/api/v1'}/payments/${p.id}/receipt`}
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
          expandIconColumnIndex: 0,
          columnWidth: 36,
        }}
        rowClassName={(row) => {
          const total = Number(row.total_amount || 0)
          const addl = Number(row.additional_total_in_contract_currency ?? 0)
          const receivable = total + addl
          const paid = Number(row.paid_amount || 0)
          if (paid >= receivable) return 'row-cleared'
          return ''
        }}
        scroll={{ x: 1500 }}
      />

      {/* 附加项弹窗 */}
      {addlModal.open && (
        <AdditionalItemFormModal
          open={addlModal.open}
          mode={addlModal.editing ? 'edit' : 'add'}
          contractId={addlModal.contractId}
          contractCurrency={addlModal.contractCurrency}
          editing={addlModal.editing || null}
          onClose={() => setAddlModal(prev => ({ ...prev, open: false }))}
          onSuccess={handleAddlSuccess}
        />
      )}

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
