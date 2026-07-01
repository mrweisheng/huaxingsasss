import { useEffect, useState } from 'react'
import { Empty, Tooltip } from 'antd'
import {
  ArrowUpOutlined,
  ArrowDownOutlined,
  TeamOutlined,
  FileTextOutlined,
  DollarOutlined,
  WalletOutlined,
} from '@ant-design/icons'
import ReactECharts from 'echarts-for-react'
import { statsApi, FinancialOverview as FinancialOverviewType } from '@/services/stats'
import { formatMoney, formatMoneyShort } from '@/utils/money'
import { currencySymbol } from '@/utils/moneyFormat'
import './FinancialOverview.css'

type Currency = 'CNY' | 'HKD'

export default function FinancialOverview() {
  const [loading, setLoading] = useState(true)
  const [data, setData] = useState<FinancialOverviewType | null>(null)

  useEffect(() => {
    statsApi.getOverview()
      .then((res) => setData(res.data))
      .finally(() => setLoading(false))
  }, [])

  if (loading) {
    // 骨架屏：6 张 KPI 卡 + 2 张图表占位，匹配真实布局，避免白屏
    return (
      <div className="fo-container">
        <div className="fo-kpi-row">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="fo-kpi-card" style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div className="app-skel-block app-skel-line w-50" />
                <div className="app-skel-block" style={{ width: 24, height: 24, borderRadius: 6 }} />
              </div>
              <div className="app-skel-block" style={{ height: 32, width: '70%' }} />
              <div className="app-skel-block app-skel-line w-60" />
            </div>
          ))}
        </div>
        <div className="fo-chart-card fo-chart-card--full">
          <div className="app-skel-block" style={{ width: 220, height: 18, marginBottom: 12 }} />
          <div className="app-skel-block" style={{ height: 320, borderRadius: 8 }} />
        </div>
        <div className="fo-chart-card fo-chart-card--full">
          <div className="app-skel-block" style={{ width: 220, height: 18, marginBottom: 12 }} />
          <div className="app-skel-block" style={{ height: 340, borderRadius: 8 }} />
        </div>
      </div>
    )
  }

  if (!data) {
    return (
      <div className="app-loading-section">
        <Empty description="暂无数据" />
      </div>
    )
  }

  const { kpi, daily_trend, monthly_receipt_trend } = data

  // 回款率 = 已收 / (已收 + 应收)，分币种算。0 分母时返回 null。
  const collectionRate = (c: Currency): number | null => {
    const paid = Number(kpi.total_income[c]) || 0
    const due = Number(kpi.total_remaining[c]) || 0
    const total = paid + due
    if (total <= 0) return null
    return (paid / total) * 100
  }

  const rateCNY = collectionRate('CNY')
  const rateHKD = collectionRate('HKD')

  /** 双币种金额卡通用渲染：CNY/HKD 同字号同字重，账本式对齐
   *  金额智能缩写为 万/亿，鼠标悬停看完整精确值。
   */
  const renderDualCurrency = (cny: number, hkd: number) => {
    const cnyM = formatMoney(cny)
    const hkdM = formatMoney(hkd)
    return (
      <>
        <Tooltip title={`CNY ${currencySymbol.CNY}${cnyM.full}`} placement="top" mouseEnterDelay={0.3}>
          <div className="fo-kpi-ledger__row">
            <span className="fo-kpi-ledger__code">
              CNY{cnyM.unit && <em className="fo-kpi-ledger__unit">{cnyM.unit}</em>}
            </span>
            <span className="fo-kpi-ledger__sym">{currencySymbol.CNY}</span>
            <span className="fo-kpi-ledger__num">{cnyM.display}</span>
          </div>
        </Tooltip>
        <Tooltip title={`HKD ${currencySymbol.HKD}${hkdM.full}`} placement="top" mouseEnterDelay={0.3}>
          <div className="fo-kpi-ledger__row">
            <span className="fo-kpi-ledger__code">
              HKD{hkdM.unit && <em className="fo-kpi-ledger__unit">{hkdM.unit}</em>}
            </span>
            <span className="fo-kpi-ledger__sym">{currencySymbol.HKD}</span>
            <span className="fo-kpi-ledger__num">{hkdM.display}</span>
          </div>
        </Tooltip>
      </>
    )
  }

  /** 底部 context 行：FT 财务版面风，dotted leader 引导 */
  const renderContext = (label: string, valueCNY: string, valueHKD: string) => (
    <div className="fo-kpi-card__context">
      <span className="fo-kpi-card__context-label">{label}</span>
      <span className="fo-kpi-card__context-leader" />
      <span className="fo-kpi-card__context-val">
        <span className="fo-kpi-card__context-tag">CNY</span> {valueCNY}
        <span className="fo-kpi-card__context-sep">·</span>
        <span className="fo-kpi-card__context-tag">HKD</span> {valueHKD}
      </span>
    </div>
  )

  return (
    <div className="fo-container">
      {/* ── KPI 卡片行 ── */}
      <div className="fo-kpi-row">
        {/* 计数：合同 */}
        <div className="fo-kpi-card fo-kpi-card--count fo-kpi-card--contracts">
          <header className="fo-kpi-card__header">
            <span className="fo-kpi-card__tick" />
            <h3 className="fo-kpi-card__title">合同总数</h3>
            <span className="fo-kpi-card__icon"><FileTextOutlined /></span>
          </header>
          <div className="fo-kpi-card__count">{kpi.total_contracts}</div>
          <div className="fo-kpi-card__footnote">进行中 <b>{kpi.active_contracts}</b></div>
        </div>

        {/* 计数：客户 */}
        <div className="fo-kpi-card fo-kpi-card--count fo-kpi-card--customers">
          <header className="fo-kpi-card__header">
            <span className="fo-kpi-card__tick" />
            <h3 className="fo-kpi-card__title">客户总数</h3>
            <span className="fo-kpi-card__icon"><TeamOutlined /></span>
          </header>
          <div className="fo-kpi-card__count">{kpi.total_customers}</div>
          <div className="fo-kpi-card__footnote">服务中客户</div>
        </div>

        {/* 已收 */}
        <div className="fo-kpi-card fo-kpi-card--money fo-kpi-card--income">
          <header className="fo-kpi-card__header">
            <span className="fo-kpi-card__tick" />
            <h3 className="fo-kpi-card__title">已收总额</h3>
            <span className="fo-kpi-card__icon"><ArrowUpOutlined /></span>
          </header>
          <div className="fo-kpi-ledger">
            {renderDualCurrency(Number(kpi.total_income.CNY), Number(kpi.total_income.HKD))}
          </div>
        </div>

        {/* 支出 */}
        <div className="fo-kpi-card fo-kpi-card--money fo-kpi-card--expense">
          <header className="fo-kpi-card__header">
            <span className="fo-kpi-card__tick" />
            <h3 className="fo-kpi-card__title">支出总额</h3>
            <span className="fo-kpi-card__icon"><ArrowDownOutlined /></span>
          </header>
          <div className="fo-kpi-ledger">
            {renderDualCurrency(Number(kpi.total_expense.CNY), Number(kpi.total_expense.HKD))}
          </div>
        </div>

        {/* 利润 */}
        <div className="fo-kpi-card fo-kpi-card--money fo-kpi-card--profit">
          <header className="fo-kpi-card__header">
            <span className="fo-kpi-card__tick" />
            <h3 className="fo-kpi-card__title">利润</h3>
            <span className="fo-kpi-card__icon"><DollarOutlined /></span>
          </header>
          <div className="fo-kpi-ledger">
            {renderDualCurrency(Number(kpi.total_profit.CNY), Number(kpi.total_profit.HKD))}
          </div>
        </div>

        {/* 应收账款（带回款进度上下文） */}
        <div className="fo-kpi-card fo-kpi-card--money fo-kpi-card--remaining">
          <header className="fo-kpi-card__header">
            <span className="fo-kpi-card__tick" />
            <h3 className="fo-kpi-card__title">应收账款</h3>
            <span className="fo-kpi-card__icon"><WalletOutlined /></span>
          </header>
          <div className="fo-kpi-ledger">
            {renderDualCurrency(Number(kpi.total_remaining.CNY), Number(kpi.total_remaining.HKD))}
          </div>
          {(rateCNY !== null || rateHKD !== null) && renderContext(
            '回款进度',
            rateCNY !== null ? `${rateCNY.toFixed(1)}%` : '—',
            rateHKD !== null ? `${rateHKD.toFixed(1)}%` : '—',
          )}
        </div>
      </div>

      {/* ── 月度业务趋势（全宽） ── */}
      <div className="fo-chart-card fo-chart-card--full">
        <div className="fo-chart-card__title">
          <span>月度业务趋势</span>
          <span className="fo-chart-card__subtitle">近 30 天 · 每日成交合同数 与 成交客户数</span>
        </div>
        <ReactECharts
          option={dailyBusinessTrendOption(daily_trend)}
          style={{ height: 340 }}
          notMerge
        />
      </div>

      {/* ── 月度收款趋势（全宽，双币种曲线） ── */}
      <div className="fo-chart-card fo-chart-card--full">
        <div className="fo-chart-card__title">
          <span>月度收款趋势</span>
          <span className="fo-chart-card__subtitle">近 30 天 · 按凭证付款日期 · CNY 与 HKD 分线</span>
        </div>
        <ReactECharts
          option={monthlyReceiptTrendOption(monthly_receipt_trend)}
          style={{ height: 360 }}
          notMerge
        />
      </div>
    </div>
  )
}


/* ── ECharts 配置工厂 ── */

/**
 * 月度业务趋势：双柱并列（合同数 + 客户数）
 *
 * 颜色：
 *   - 合同数柱子：钢蓝 #2d5b8a 渐变（系统色家族，非业务色）
 *   - 客户数柱子：华星金 #c9952b 渐变（品牌强调色）
 * 共用单一 Y 轴：两者同量纲（计数），同轴对比能直接呈现"一客户多单"的密度。
 */
function dailyBusinessTrendOption(data: FinancialOverviewType['daily_trend']) {
  // X 轴日期标签：MM-DD，节省宽度
  const dates = data.map(d => d.date.slice(5))   // "2026-06-10" → "06-10"
  const fullDates = data.map(d => d.date)
  const contractData = data.map(d => d.contract_count)
  const customerData = data.map(d => d.customer_count)

  const maxValue = Math.max(...contractData, ...customerData, 1)

  return {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter: (params: any[]) => {
        const idx = params[0].dataIndex
        const date = fullDates[idx]
        let s = `<b>${date}</b><br/>`
        params.forEach(p => {
          const unit = p.seriesName === '成交客户数' ? '人' : '单'
          s += `${p.marker} ${p.seriesName}：<b>${p.value}</b> ${unit}<br/>`
        })
        return s
      },
    },
    legend: {
      data: ['成交合同数', '成交客户数'],
      top: 0,
      right: 8,
      itemWidth: 14,
      itemHeight: 10,
      textStyle: { fontSize: 12 },
    },
    grid: { top: 50, bottom: 50, left: 50, right: 30 },
    xAxis: {
      type: 'category',
      data: dates,
      axisLabel: {
        fontSize: 11,
        color: '#64748b',
        interval: dates.length > 20 ? 2 : 1,   // 30 天时跳着显示，避免拥挤
      },
      axisLine: { lineStyle: { color: '#e2e8f0' } },
      axisTick: { show: false },
    },
    yAxis: {
      type: 'value',
      name: '数量',
      nameTextStyle: { fontSize: 11, color: '#64748b', padding: [0, 30, 0, 0] },
      min: 0,
      max: Math.ceil(maxValue * 1.2),
      minInterval: 1,
      axisLabel: { fontSize: 11, color: '#64748b' },
      splitLine: { lineStyle: { color: '#f1f5f9', type: 'dashed' } },
    },
    series: [
      {
        name: '成交合同数',
        type: 'bar',
        data: contractData,
        barMaxWidth: 14,
        barGap: '20%',          // 同日两根柱子之间的间隙
        itemStyle: {
          color: {
            type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: '#2d5b8a' },
              { offset: 1, color: '#5680b0' },
            ],
          },
          borderRadius: [3, 3, 0, 0],
        },
        emphasis: { itemStyle: { color: '#1e3f63' } },
      },
      {
        name: '成交客户数',
        type: 'bar',
        data: customerData,
        barMaxWidth: 14,
        itemStyle: {
          color: {
            type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: '#c9952b' },
              { offset: 1, color: '#dbb466' },
            ],
          },
          borderRadius: [3, 3, 0, 0],
        },
        emphasis: { itemStyle: { color: '#a87a18' } },
      },
    ],
  }
}

/**
 * 月度收款趋势：双曲线（CNY + HKD），按凭证付款日期聚合
 *
 * 颜色：
 *   - CNY 线：华星金 #c9952b （已收/落袋 状态色家族，金钱语义）
 *   - HKD 线：teal #0d9488  （结清/到账 状态色家族，与金色高对比、易区分）
 * 平滑曲线 + 区域渐变填充，区别上方"业务趋势"的柱状图。
 */
function monthlyReceiptTrendOption(data: FinancialOverviewType['monthly_receipt_trend']) {
  const dates = data.map(d => d.date.slice(5))
  const fullDates = data.map(d => d.date)
  const cnyData = data.map(d => Number(d.cny) || 0)
  const hkdData = data.map(d => Number(d.hkd) || 0)

  return {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'line', lineStyle: { color: '#cbd5e1', type: 'dashed' } },
      formatter: (params: any[]) => {
        const idx = params[0].dataIndex
        const date = fullDates[idx]
        let s = `<b>${date}</b><br/>`
        params.forEach(p => {
          const sym = p.seriesName === 'CNY' ? currencySymbol.CNY : currencySymbol.HKD
          s += `${p.marker} ${p.seriesName}：<b>${sym}${formatMoney(Number(p.value)).full}</b><br/>`
        })
        return s
      },
    },
    legend: {
      data: ['CNY', 'HKD'],
      top: 0,
      right: 8,
      itemWidth: 14,
      itemHeight: 10,
      textStyle: { fontSize: 12 },
    },
    grid: { top: 50, bottom: 50, left: 60, right: 30 },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: dates,
      axisLabel: {
        fontSize: 11,
        color: '#64748b',
        interval: dates.length > 20 ? 2 : 1,
      },
      axisLine: { lineStyle: { color: '#e2e8f0' } },
      axisTick: { show: false },
    },
    yAxis: {
      type: 'value',
      name: '金额',
      nameTextStyle: { fontSize: 11, color: '#64748b', padding: [0, 30, 0, 0] },
      min: 0,
      axisLabel: {
        fontSize: 11,
        color: '#64748b',
        formatter: (v: number) => formatMoneyShort(v),
      },
      splitLine: { lineStyle: { color: '#f1f5f9', type: 'dashed' } },
    },
    series: [
      {
        name: 'CNY',
        type: 'line',
        smooth: true,
        symbol: 'circle',
        symbolSize: 6,
        showSymbol: false,
        data: cnyData,
        lineStyle: { width: 2.5, color: '#c9952b' },
        itemStyle: { color: '#c9952b', borderColor: '#fff', borderWidth: 2 },
        emphasis: { focus: 'series', scale: 1.2 },
        areaStyle: {
          color: {
            type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(201, 149, 43, 0.28)' },
              { offset: 1, color: 'rgba(201, 149, 43, 0.02)' },
            ],
          },
        },
      },
      {
        name: 'HKD',
        type: 'line',
        smooth: true,
        symbol: 'circle',
        symbolSize: 6,
        showSymbol: false,
        data: hkdData,
        lineStyle: { width: 2.5, color: '#0d9488' },
        itemStyle: { color: '#0d9488', borderColor: '#fff', borderWidth: 2 },
        emphasis: { focus: 'series', scale: 1.2 },
        areaStyle: {
          color: {
            type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(13, 148, 136, 0.24)' },
              { offset: 1, color: 'rgba(13, 148, 136, 0.02)' },
            ],
          },
        },
      },
    ],
  }
}
