/**
 * 付款审计标记前端 helper
 *
 * 与后端 backend/app/core/payment_audit.py 同步。后端 create_payment_record 在
 * no_receipt=true 时把此前缀写入 payment.notes 开头作为审计标记，前端识别后
 * 在付款列表展示「无凭证」chip。
 */

export const NO_RECEIPT_NOTE_PREFIX = '[无凭证支出]'

export function isNoReceipt(payment: {
  notes?: string | null
  receipt_image_path?: string | null
}): boolean {
  return (
    !payment.receipt_image_path &&
    (payment.notes ?? '').startsWith(NO_RECEIPT_NOTE_PREFIX)
  )
}
