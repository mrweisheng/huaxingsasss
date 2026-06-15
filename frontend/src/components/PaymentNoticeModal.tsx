import { useState, useRef } from 'react'
import { Modal, Button, message } from 'antd'
import { DownloadOutlined } from '@ant-design/icons'
import { toPng } from 'html-to-image'
import type { Contract, Payment } from '@/types'
import { fmt, fmtFull, amountToChinese, methodMap } from '@/utils/moneyFormat'
import './PaymentNoticeModal.css'

interface Props {
  open: boolean
  contract: Contract
  /** 已收（income）付款明细，由详情页透传，避免重复请求 */
  incomePayments: Payment[]
  onClose: () => void
}

/**
 * 付款通知单 —— 纸质单据风格的对账弹窗。
 *
 * 数据全部来自详情页已有的 contract / incomePayments，无后端改动。
 * 支持下载为 PNG（html-to-image），方便微信发给客户核对。
 *
 * 应收口径与详情页一致：
 *   receivable = total_amount + additional_total_in_contract_currency
 *   unpaid     = max(0, receivable - paid_amount)
 */
export default function PaymentNoticeModal({ open, contract, incomePayments, onClose }: Props) {
  const sheetRef = useRef<HTMLDivElement>(null)
  const [downloading, setDownloading] = useState(false)

  /* ── 口径计算（与 ContractDetail 完全一致） ── */
  const cur = contract.currency
  const total = Number(contract.total_amount || 0)
  const paid = Number(contract.paid_amount || 0)
  const addlNum = contract.additional_total_in_contract_currency != null
    ? Number(contract.additional_total_in_contract_currency) : 0
  const addlItems = contract.additional_items || []
  const hasAddlItems = addlItems.length > 0
  const addlUnconverted = hasAddlItems && addlNum === 0   // 有附加项但缺汇率未折算
  const receivable = total + addlNum
  const unpaid = Math.max(0, receivable - paid)
  const overpaid = Math.max(0, paid - receivable)
  // 金额比较归一到「分」,避免浮点精度导致已结清的合同显示成 ¥0.00 未付
  const EPSILON = 0.005
  const isCleared = unpaid < EPSILON

  const today = new Date()
  const dateStr = `${today.getFullYear()}年${today.getMonth() + 1}月${today.getDate()}日`

  /* ── 下载为 PNG ── */
  const handleDownload = async () => {
    if (!sheetRef.current) return
    setDownloading(true)
    try {
      const dataUrl = await toPng(sheetRef.current, {
        pixelRatio: 2,
        backgroundColor: '#ffffff',
        // ⚡ 性能优化：通知单只用系统字体（PingFang/YaHei/SimSun），无 @font-face，
        //    跳过字体下载+base64 嵌入（这一步常占 html-to-image 总耗时的 70%+）
        skipFonts: true,
        // 过滤掉工具栏（虽然已用 CSS 隐藏，双保险）
        filter: (node) => {
          if (node instanceof HTMLElement) {
            return !node.classList?.contains('pn-toolbar')
          }
          return true
        },
      })
      const link = document.createElement('a')
      const safeNo = contract.contract_number?.replace(/[\\/:*?"<>|]/g, '_') || '通知单'
      link.download = `付款通知单-${safeNo}-${today.toISOString().slice(0, 10)}.png`
      link.href = dataUrl
      link.click()
      message.success('已保存为图片')
    } catch (e) {
      console.error(e)
      message.error('保存图片失败，请重试')
    } finally {
      setDownloading(false)
    }
  }

  return (
    <Modal
      open={open}
      onCancel={onClose}
      footer={null}
      width={800}
      className="pn-modal"
      destroyOnClose
      title={null}
    >
      {/* 工具栏：截图时会被过滤 */}
      <div className="pn-toolbar">
        <Button
          type="primary"
          icon={<DownloadOutlined />}
          loading={downloading}
          onClick={handleDownload}
        >
          保存为图片
        </Button>
      </div>

      {/* ── 单据主体（截图范围） ── */}
      <div ref={sheetRef} className={`pn-sheet ${downloading ? 'pn-screenshotting' : ''}`}>

        {/* 抬头 */}
        <div className="pn-header">
          <h2 className="pn-title">付款通知单</h2>
          <div className="pn-subtitle">PAYMENT NOTICE</div>
        </div>

        {/* 客户信息 */}
        <div className="pn-party">
          <div>
            <span className="pn-party-label">致（客户）：</span>
            <span className="pn-party-value">{contract.customer_name || '—'}</span>
          </div>
          <div>
            <span className="pn-party-label">合同编号：</span>
            <span className="pn-party-value">{contract.contract_number || '—'}</span>
          </div>
        </div>
        <div className="pn-party" style={{ marginTop: -10 }}>
          <div>
            <span className="pn-party-label">业务事项：</span>
            <span className="pn-party-value">{contract.business_description || contract.title || '—'}</span>
          </div>
          <div>
            <span className="pn-party-label">签订日期：</span>
            <span className="pn-party-value">{contract.signed_date || '—'}</span>
          </div>
        </div>

        {/* ① 应收清单 */}
        <div className="pn-section-title">应收款项明细</div>
        <table className="pn-table">
          <thead>
            <tr>
              <th style={{ width: 40 }}>#</th>
              <th>项目</th>
              <th className="pn-num" style={{ width: 160 }}>金额</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>1</td>
              <td>合同金额</td>
              <td className="pn-num">{fmtFull(total, cur)}</td>
            </tr>
            {addlItems.map((it, idx) => (
              <tr key={it.id}>
                <td>{idx + 2}</td>
                <td>
                  {it.name}
                  {it.currency !== cur && (
                    <span className="pn-unconverted-hint">（{it.currency}）</span>
                  )}
                </td>
                <td className="pn-num">{fmtFull(it.amount, it.currency)}</td>
              </tr>
            ))}
            <tr className="pn-row-total">
              <td colSpan={2}>
                应收合计
                {addlUnconverted && (
                  <span className="pn-unconverted-hint">
                    （{addlItems.length} 项附加项因缺汇率未折算，未计入）
                  </span>
                )}
              </td>
              <td className="pn-num">{fmtFull(receivable, cur)}</td>
            </tr>
          </tbody>
        </table>

        {/* ② 已支付明细 */}
        <div className="pn-section-title">已支付记录</div>
        {incomePayments.length > 0 ? (
          <table className="pn-table">
            <thead>
              <tr>
                <th style={{ width: 40 }}>#</th>
                <th style={{ width: 110 }}>收款日期</th>
                <th>款项说明</th>
                <th style={{ width: 90 }}>收款方式</th>
                <th className="pn-num" style={{ width: 130 }}>金额</th>
              </tr>
            </thead>
            <tbody>
              {incomePayments.map((p, idx) => (
                <tr key={p.id}>
                  <td>{idx + 1}</td>
                  <td>{p.paid_date || '—'}</td>
                  <td>{p.installment_name || p.description || '—'}</td>
                  <td>{p.payment_method ? (methodMap[p.payment_method] || p.payment_method) : '—'}</td>
                  <td className="pn-num">{fmtFull(p.paid_amount, p.currency)}</td>
                </tr>
              ))}
              <tr className="pn-row-total">
                <td colSpan={4}>已付合计（共 {incomePayments.length} 笔）</td>
                <td className="pn-num">{fmtFull(paid, cur)}</td>
              </tr>
            </tbody>
          </table>
        ) : (
          <div className="pn-empty">暂无收款记录</div>
        )}

        {/* ③ 未付余额（醒目块） */}
        <div className={`pn-balance ${isCleared ? 'cleared' : ''}`}>
          <div>
            <div className="pn-balance-label">
              {isCleared ? '本次已结清' : '尚欠余额（大写）'}
            </div>
            <span className="pn-balance-cny">{amountToChinese(isCleared ? 0 : unpaid, cur)}</span>
          </div>
          <div style={{ textAlign: 'right' }}>
            <div className="pn-balance-amount">{fmt(isCleared ? 0 : unpaid, cur)}</div>
            {overpaid > 0 && (
              <span className="pn-balance-cny">（含超收 {fmt(overpaid, cur)}）</span>
            )}
          </div>
        </div>

        {/* 落款 */}
        <div className="pn-footer">
          <div>
            <div className="pn-footer-brand">华星 · 财务部</div>
            <div style={{ marginTop: 4 }}>如有疑问请联系您的业务经办人</div>
          </div>
          <div style={{ textAlign: 'right' }}>
            <div>制单日期：{dateStr}</div>
            <div style={{ marginTop: 4 }}>本通知单仅供参考，最终以合同约定为准</div>
          </div>
        </div>

      </div>
    </Modal>
  )
}
