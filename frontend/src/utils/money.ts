/**
 * 金额格式化工具
 *
 * 中文财务习惯按「万 / 亿」分档，不用 K/M/B（那是英文圈）。
 *
 * 缩写阈值（金额数字本身的绝对值）：
 *   < 1 万      → 完整显示       8500   → "8,500.00"
 *   1 万 ~ 1 亿 → "万" 单位      125000 → "12.50 万"
 *   ≥ 1 亿      → "亿" 单位   125000000 → "1.25 亿"
 *
 * 设计取舍：
 *   - 缩写后保留 2 位小数，可读性 vs 精度的折中
 *   - 负数原样处理（profit 可能为负）
 *   - 返回 { display, unit, full } 三元组，让调用方决定如何渲染
 *     （例：display 在主位、unit 做 chip、full 给 tooltip）
 */

const TEN_THOUSAND = 10_000
const ONE_HUNDRED_MILLION = 100_000_000

export type MoneyUnit = '' | '万' | '亿'

export interface FormattedMoney {
  /** 缩写后的数字字符串（已带千分位、2位小数） */
  display: string
  /** 单位后缀：'' | '万' | '亿' */
  unit: MoneyUnit
  /** 完整精确值（带千分位 + 2 位小数），用于 tooltip */
  full: string
}

/**
 * 智能金额格式化：按中文「万/亿」自动选单位
 */
export function formatMoney(value: number | string | null | undefined): FormattedMoney {
  const num = Number(value ?? 0)
  const safeNum = Number.isFinite(num) ? num : 0

  const full = safeNum.toLocaleString('zh-CN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })

  const abs = Math.abs(safeNum)

  if (abs >= ONE_HUNDRED_MILLION) {
    return {
      display: (safeNum / ONE_HUNDRED_MILLION).toLocaleString('zh-CN', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      }),
      unit: '亿',
      full,
    }
  }

  if (abs >= TEN_THOUSAND) {
    return {
      display: (safeNum / TEN_THOUSAND).toLocaleString('zh-CN', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      }),
      unit: '万',
      full,
    }
  }

  return { display: full, unit: '', full }
}

/**
 * 仅返回带单位的简写字符串（"125.00 万" / "1.25 亿" / "8,500.00"）。
 * 用于图表 axisLabel / tooltip 等只需文本的场景。
 */
export function formatMoneyShort(value: number | string | null | undefined): string {
  const { display, unit } = formatMoney(value)
  return unit ? `${display} ${unit}` : display
}
