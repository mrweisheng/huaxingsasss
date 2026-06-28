/**
 * 付款审计标记前端 helper
 *
 * 与后端 backend/app/core/payment_audit.py 同步。后端在无凭证录入时把对应前缀写入
 * payment.notes 开头作为审计标记，前端识别后在付款列表展示「无凭证」chip。
 *
 * - [无凭证支出]：支出无凭证录入（no_receipt）
 * - [无凭证收入]：现阶段（INCOME_RECEIPT_REQUIRED=False）收入无凭证录入
 */

export const NO_RECEIPT_NOTE_PREFIX = '[无凭证支出]'
export const NO_RECEIPT_INCOME_PREFIX = '[无凭证收入]'

/** 无凭证前缀集合（支出 / 收入） */
const NO_RECEIPT_PREFIXES = [NO_RECEIPT_NOTE_PREFIX, NO_RECEIPT_INCOME_PREFIX]

export function isNoReceipt(payment: {
  notes?: string | null
  receipt_image_path?: string | null
}): boolean {
  if (payment.receipt_image_path) return false
  const notes = payment.notes ?? ''
  return NO_RECEIPT_PREFIXES.some((prefix) => notes.startsWith(prefix))
}
