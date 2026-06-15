/**
 * 金额 / 币种 / 收款方式 的共享展示工具
 *
 * 从 ContractDetail.tsx 抽出，供合同详情页与「付款通知单」弹窗复用，
 * 保证两处金额、货币符号、大写金额、收款方式文案口径一致。
 */
import { formatMoney, formatMoneyShort } from './money'

/** 货币符号表（与 ContractDetail 保持一致） */
export const currencySymbol: Record<string, string> = { CNY: '¥', HKD: 'HK$' }

/** 收款方式 code → 中文文案 */
export const methodMap: Record<string, string> = {
  bank_transfer: '银行转账',
  wechat: '微信',
  alipay: '支付宝',
  cash: '现金',
  check: '支票',
}

/** 缩写金额 + 货币符号（主显示用） */
export function fmt(amount: number | undefined | null, currency: string): string {
  if (amount === undefined || amount === null) return '-'
  const symbol = currencySymbol[currency] || '¥'
  return `${symbol}${formatMoneyShort(amount)}`
}

/** 完整精确金额 + 货币符号（Tooltip / 单据正文用） */
export function fmtFull(amount: number | undefined | null, currency: string): string {
  if (amount === undefined || amount === null) return '-'
  const symbol = currencySymbol[currency] || '¥'
  return `${symbol}${formatMoney(amount).full}`
}

/**
 * 金额转中文大写（繁体，财务单据习惯）。
 * 如 150000.00 CNY → 「人民幣壹拾伍萬元整」
 */
export function amountToChinese(amount: number, currency: string): string {
  if (amount === 0) {
    const cn = currency === 'CNY' ? '人民幣' : currency === 'HKD' ? '港幣' : currency
    return `${cn}零元整`
  }
  const digitMap = ['零', '壹', '貳', '叁', '肆', '伍', '陸', '柒', '捌', '玖']
  const unitMap = ['', '拾', '佰', '仟']
  const bigUnitMap = ['', '萬', '億']
  const currencyName = currency === 'CNY' ? '人民幣' : currency === 'HKD' ? '港幣' : currency
  const intPart = Math.floor(amount)
  const fracPart = Math.round((amount - intPart) * 100)
  let result = ''
  let intStr = intPart.toString()
  let unitIdx = 0
  let bigUnitIdx = 0
  let hasNonZero = false
  for (let i = intStr.length - 1; i >= 0; i--) {
    const digit = parseInt(intStr[i])
    if (digit !== 0) {
      result = digitMap[digit] + unitMap[unitIdx] + result
      hasNonZero = true
    } else if (hasNonZero) {
      result = digitMap[0] + result
      hasNonZero = false
    }
    unitIdx++
    if (unitIdx === 4) {
      unitIdx = 0
      bigUnitIdx++
      if (bigUnitIdx < bigUnitMap.length && i > 0) {
        result = bigUnitMap[bigUnitIdx] + result
      }
    }
  }
  result = result.replace(/零+$/, '')
  if (!result) result = '零'
  if (fracPart > 0) {
    result += '元'
    const jiao = Math.floor(fracPart / 10)
    const fen = fracPart % 10
    if (jiao > 0) result += digitMap[jiao] + '角'
    if (fen > 0) result += digitMap[fen] + '分'
  } else {
    result += '元整'
  }
  return `${currencyName}${result}`
}
