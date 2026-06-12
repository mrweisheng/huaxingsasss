/**
 * 合同台账导出为 .xlsx（WPS/Excel 可编辑）
 *
 * 方案 A：纵向平铺 —— 每笔收入/支出一行，合同信息纵向合并。
 * 结构：标题 → 汇总条 → 两级合并表头 → 数据行 → 嵌入凭证缩略图
 */
import ExcelJS from 'exceljs'
import { contractApi } from '@/services/contract'
import api from '@/services/api'
import dayjs from 'dayjs'

const CURRENCY_SYMBOL: Record<string, string> = { CNY: '¥', HKD: 'HK$' }

// ── 品牌色（ARGB）──
const CLR = {
  brand:   'FF1E3A5F',  // 深蓝
  gold:    'FFC9952B',  // 金
  orange:  'FFDC6B3D',  // 暖橙
  teal:    'FF0D9488',  // 结清
  headerBg:'FFE5EDF6',  // 浅钢蓝
  white:   'FFFFFFFF',
  border:  'FFD9D9D9',
  profitPos: 'FF0D9488',
  profitNeg: 'FFDC6B3D',
  incomeText: 'FF5B8C63',   // 鼠尾草绿
  expenseText: 'FFDC6B3D',  // 暖橙
}

export interface ExportOptions {
  dateFrom: string  // YYYY-MM-DD
  dateTo: string    // YYYY-MM-DD
}

// ── helpers ──

function blobToBase64(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onloadend = () => {
      const result = reader.result as string
      resolve(result.split(',')[1])  // 去掉 "data:...;base64," 前缀
    }
    reader.onerror = reject
    reader.readAsDataURL(blob)
  })
}

function detectImageExt(blob: Blob): 'jpeg' | 'png' {
  if (blob.type === 'image/png') return 'png'
  return 'jpeg'
}

function fmtMoney(value: number, currency: string): string {
  const sym = CURRENCY_SYMBOL[currency] || '¥'
  return `${sym}${value.toLocaleString('zh-CN', { maximumFractionDigits: 2 })}`
}

function bizLabel(businessType?: string): string {
  if (businessType === '车辆业务' || businessType === '车辆买卖') return '车辆买卖'
  if (businessType === '中港牌业务' || businessType === '两地牌过户') return '两地牌过户'
  return businessType || ''
}

function thinBorder(color = CLR.border): Partial<ExcelJS.Borders> {
  const style: Partial<ExcelJS.Border> = { style: 'thin', color: { argb: color } }
  return { top: style, left: style, bottom: style, right: style }
}

// ── 主函数 ──

export async function exportLedger(options: ExportOptions): Promise<void> {
  // 1) 拉数据
  const response = await contractApi.getListWithPayments({
    date_from: options.dateFrom,
    date_to: options.dateTo,
    per_page: 500,
  })
  const contracts = response.items

  if (!contracts.length) {
    throw new Error('选定日期范围内没有合同数据')
  }

  // 2) 并发拉凭证图
  const receiptMap = new Map<number, { base64: string; ext: 'jpeg' | 'png' }>()
  const fetches = contracts.flatMap(c =>
    (c.payments || [])
      .filter(p => p.receipt_image_path)
      .map(async p => {
        try {
          const blob = await api.get(`/payments/${p.id}/receipt`, { responseType: 'blob' }) as unknown as Blob
          const base64 = await blobToBase64(blob)
          receiptMap.set(p.id, { base64, ext: detectImageExt(blob) })
        } catch { /* 跳过拉取失败的凭证 */ }
      }),
  )
  await Promise.all(fetches)

  // 3) 建 workbook
  const wb = new ExcelJS.Workbook()
  wb.creator = '华星合同管理系统'
  wb.created = new Date()

  const ws = wb.addWorksheet('合同台账', {
    views: [{ state: 'frozen', ySplit: 5 }],  // 冻结标题+汇总+表头
  })

  // ── 列宽 ──
  //                A     B     C     D     E     F     G     H     I    J     K     L    M     N     O     P     Q
  const widths = [12,   16,   12,   10,   24,   16,   10,    8,    8,  14,   14,    8,   12,   10,   12,   14,   16]
  ws.columns = widths.map(w => ({ width: w }))

  // ── Row 1: 标题 ──
  ws.mergeCells('A1:Q1')
  const titleCell = ws.getCell('A1')
  titleCell.value = `华星合同台账 · ${options.dateFrom} ~ ${options.dateTo}`
  titleCell.font = { size: 14, bold: true, color: { argb: CLR.brand } }
  titleCell.alignment = { horizontal: 'center', vertical: 'middle' }
  titleCell.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FFF4F7FB' } }
  ws.getRow(1).height = 36

  // ── Row 2: 汇总条 ──
  const summary = contracts.reduce(
    (acc, c) => {
      const cur = c.currency || 'CNY'
      if (!acc[cur]) acc[cur] = { total: 0, paid: 0, expense: 0 }
      acc[cur].total += Number(c.total_amount || 0)
      acc[cur].paid += Number(c.paid_amount || 0)
      acc[cur].expense += Number(c.total_expense || 0)
      return acc
    },
    {} as Record<string, { total: number; paid: number; expense: number }>,
  )
  const sumCurrs = Object.keys(summary)

  const fmtSum = (cur: string, key: 'total' | 'paid' | 'expense') =>
    `${CURRENCY_SYMBOL[cur]}${summary[cur][key].toLocaleString('zh-CN', { maximumFractionDigits: 0 })}`

  // 合同总额
  ws.mergeCells('A2:C2')
  setSummaryBlock(ws, 'A2', '合同总额', sumCurrs.map(c => fmtSum(c, 'total')).join('  '), CLR.brand)
  // 已收
  ws.mergeCells('D2:F2')
  setSummaryBlock(ws, 'D2', '已收', sumCurrs.map(c => fmtSum(c, 'paid')).join('  '), CLR.gold)
  // 支出
  ws.mergeCells('G2:I2')
  setSummaryBlock(ws, 'G2', '支出', sumCurrs.map(c => fmtSum(c, 'expense')).join('  '), CLR.orange)
  // 净利润
  ws.mergeCells('J2:M2')
  const profitSumText = sumCurrs.map(c => {
    const p = summary[c].paid - summary[c].expense
    return `${p < 0 ? '-' : ''}${CURRENCY_SYMBOL[c]}${Math.abs(p).toLocaleString('zh-CN', { maximumFractionDigits: 0 })}`
  }).join('  ')
  setSummaryBlock(ws, 'J2', '净利润', profitSumText, CLR.teal)
  // 合同数
  ws.mergeCells('N2:Q2')
  const countCell = ws.getCell('N2')
  countCell.value = `共 ${contracts.length} 个合同`
  countCell.font = { size: 10, color: { argb: 'FF999999' } }
  countCell.alignment = { horizontal: 'right', vertical: 'middle' }

  ws.getRow(2).height = 28

  // ── Row 3: 分隔空行 ──
  ws.getRow(3).height = 6

  // ── Row 4: 表头一级（合并组名）──
  ws.mergeCells('A4:H4')
  fillRange(ws, 4, 1, 4, 8, {
    value: '合同信息',
    font: { bold: true, size: 11, color: { argb: CLR.white } },
    alignment: { horizontal: 'center', vertical: 'middle' },
    fill: { type: 'pattern', pattern: 'solid', fgColor: { argb: CLR.brand } },
  })

  ws.mergeCells('I4:P4')
  fillRange(ws, 4, 9, 4, 16, {
    value: '收支明细',
    font: { bold: true, size: 11, color: { argb: CLR.white } },
    alignment: { horizontal: 'center', vertical: 'middle' },
    fill: { type: 'pattern', pattern: 'solid', fgColor: { argb: CLR.brand } },
  })

  fillRange(ws, 4, 17, 4, 17, {
    value: '利润',
    font: { bold: true, size: 11, color: { argb: CLR.white } },
    alignment: { horizontal: 'center', vertical: 'middle' },
    fill: { type: 'pattern', pattern: 'solid', fgColor: { argb: CLR.brand } },
  })
  ws.getRow(4).height = 24

  // ── Row 5: 表头二级（列名）──
  const colNames = [
    '客户', '合同号', '签约日', '业务类型', '业务说明',
    '合同金额', '回款进度', '状态',
    '收/支', '款项名称', '金额', '币种', '付款日期', '付款方式', '收款方', '凭证',
    '净利润',
  ]
  const hr5 = ws.getRow(5)
  colNames.forEach((name, i) => {
    const cell = hr5.getCell(i + 1)
    cell.value = name
    cell.font = { bold: true, size: 10, color: { argb: CLR.brand } }
    cell.alignment = { horizontal: 'center', vertical: 'middle' }
    cell.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: CLR.headerBg } }
    cell.border = { bottom: { style: 'medium', color: { argb: CLR.brand } } }
  })
  ws.getRow(5).height = 22

  // ── Row 6+: 数据行 ──
  let curRow = 6
  const imageQueue: { base64: string; ext: 'jpeg' | 'png'; row0: number; col0: number }[] = []

  for (const c of contracts) {
    const incomes = (c.payments || []).filter(p => p.type === 'income')
    const expenses = (c.payments || []).filter(p => p.type === 'expense')
    const allFlows = [
      ...incomes.map(p => ({ ...p, flowLabel: '收入' })),
      ...expenses.map(p => ({ ...p, flowLabel: '支出' })),
    ]

    const rowCount = Math.max(allFlows.length, 1)
    const startRow = curRow
    const endRow = curRow + rowCount - 1

    // 计算合同级汇总
    const paid = Number(c.paid_amount || 0)
    const expense = Number(c.total_expense || 0)
    const profit = paid - expense
    const progress = c.total_amount > 0
      ? Math.min(Math.round((paid / Number(c.total_amount)) * 100), 999)
      : 0
    const statusText = c.status === 'completed' ? '已完成' : '执行中'

    // CNY 折算利润（HKD 合同才有）
    let profitCny: number | null = null
    if (c.currency === 'HKD' && c.paid_amount_in_cny != null && c.total_expense_in_cny != null) {
      profitCny = Number(c.paid_amount_in_cny) - Number(c.total_expense_in_cny)
    }

    // 填充每一行
    for (let i = 0; i < rowCount; i++) {
      const row = ws.getRow(curRow + i)

      // 收支明细（列 I~P）
      const p = allFlows[i]
      if (p) {
        row.getCell(9).value = p.flowLabel    // I: 收/支
        row.getCell(9).font = { bold: true, color: { argb: p.flowLabel === '收入' ? CLR.incomeText : CLR.expenseText } }
        row.getCell(10).value = p.installment_name || p.description || `第${p.installment_number}期`
        row.getCell(11).value = Number(p.paid_amount || p.amount)
        row.getCell(11).numFmt = '#,##0.00'
        row.getCell(12).value = p.currency || c.currency
        row.getCell(13).value = p.paid_date || ''
        row.getCell(14).value = p.payment_method || ''
        row.getCell(15).value = p.payee_name || ''

        // 凭证列
        if (p.receipt_image_path && receiptMap.has(p.id)) {
          row.getCell(16).value = '📷 有凭证'
          row.getCell(16).font = { size: 9, color: { argb: 'FF999999' } }
          const receipt = receiptMap.get(p.id)!
          imageQueue.push({ base64: receipt.base64, ext: receipt.ext, row0: curRow + i - 1, col0: 15 })
          row.height = 56
        }
      }

      // 所有单元格加边框
      for (let col = 1; col <= 17; col++) {
        const cell = row.getCell(col)
        cell.border = thinBorder()
        if (!cell.alignment?.vertical) {
          cell.alignment = { vertical: 'middle', wrapText: true }
        }
      }
      if (!row.height) row.height = 22
    }

    // 合同信息（只写第一行，多行时纵向合并）
    const r0 = ws.getRow(startRow)
    r0.getCell(1).value = c.customer_name || '未关联客户'
    r0.getCell(2).value = c.contract_number
    r0.getCell(3).value = c.signed_date ? dayjs(c.signed_date).format('YYYY-MM-DD') : ''
    r0.getCell(4).value = bizLabel(c.business_type)
    r0.getCell(5).value = c.business_description || ''
    r0.getCell(6).value = fmtMoney(Number(c.total_amount), c.currency)
    r0.getCell(6).alignment = { horizontal: 'right', vertical: 'middle' }
    r0.getCell(7).value = `${progress}%`
    r0.getCell(7).alignment = { horizontal: 'center', vertical: 'middle' }
    r0.getCell(8).value = statusText
    r0.getCell(8).alignment = { horizontal: 'center', vertical: 'middle' }

    // 净利润（Q 列）
    const profitText = `${profit < 0 ? '-' : ''}${fmtMoney(Math.abs(profit), c.currency)}`
    const fullProfit = profitCny !== null
      ? `${profitText}\n≈ ¥${Math.abs(profitCny).toLocaleString('zh-CN', { maximumFractionDigits: 0 })}`
      : profitText
    r0.getCell(17).value = fullProfit
    r0.getCell(17).font = { bold: true, color: { argb: profit >= 0 ? CLR.profitPos : CLR.profitNeg } }
    r0.getCell(17).alignment = { vertical: 'middle', horizontal: 'right', wrapText: true }

    // 纵向合并（合同信息列 + 净利润列）
    if (rowCount > 1) {
      const mergeCols = [1, 2, 3, 4, 5, 6, 7, 8, 17]
      for (const col of mergeCols) {
        ws.mergeCells(startRow, col, endRow, col)
      }
      // 合并区加浅色底，区分不同合同
      for (let r = startRow; r <= endRow; r++) {
        for (const col of mergeCols) {
          ws.getCell(r, col).fill = {
            type: 'pattern', pattern: 'solid',
            fgColor: { argb: 'FFFAFCFE' },
          }
        }
      }
    }

    curRow = endRow + 1
  }

  // ── 嵌入凭证缩略图 ──
  for (const img of imageQueue) {
    const imageId = wb.addImage({ base64: img.base64, extension: img.ext })
    ws.addImage(imageId, {
      tl: { col: img.col0 + 0.15, row: img.row0 + 0.15 },
      ext: { width: 48, height: 48 },
    })
  }

  // ── 下载 ──
  const buffer = await wb.xlsx.writeBuffer()
  const blob = new Blob([buffer], {
    type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `华星合同台账_${options.dateFrom}_${options.dateTo}.xlsx`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

// ── 辅助：汇总条单元格 ──
function setSummaryBlock(
  ws: ExcelJS.Worksheet,
  cellRef: string,
  label: string,
  valueText: string,
  color: string,
) {
  const cell = ws.getCell(cellRef)
  cell.value = `${label}：${valueText}`
  cell.font = { bold: true, size: 11, color: { argb: color } }
  cell.alignment = { vertical: 'middle' }
}

// ── 辅助：批量填充区域 ──
function fillRange(
  ws: ExcelJS.Worksheet,
  r1: number, c1: number,
  r2: number, c2: number,
  props: Partial<Pick<ExcelJS.Cell, 'value' | 'font' | 'alignment' | 'fill'>>,
) {
  for (let r = r1; r <= r2; r++) {
    for (let c = c1; c <= c2; c++) {
      const cell = ws.getCell(r, c)
      if (props.value !== undefined) cell.value = props.value
      if (props.font) cell.font = props.font
      if (props.alignment) cell.alignment = props.alignment
      if (props.fill) cell.fill = props.fill
    }
  }
}
