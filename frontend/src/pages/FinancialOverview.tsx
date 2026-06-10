import { useEffect, useState } from 'react'
import { Spin, Empty, Segmented } from 'antd'
import {
  ArrowUpOutlined,
  ArrowDownOutlined,
  TeamOutlined,
  FileTextOutlined,
  DollarOutlined,
} from '@ant-design/icons'
import ReactECharts from 'echarts-for-react'
import { statsApi, FinancialOverview as FinancialOverviewType } from '@/services/stats'
import './FinancialOverview.css'

type Currency = 'CNY' | 'HKD'

const CURRENCY_LABEL: Record<Currency, { unit: string; symbol: string }> = {
  CNY: { unit: 'CNY', symbol: '¥' },
  HKD: { unit: 'HKD', symbol: 'HK$' },
}

export default function FinancialOverview() {
  const [loading, setLoading] = useState(true)
  const [data, setData] = useState<FinancialOverviewType | null>(null)
  const [topCurrency, setTopCurrency] = useState<Currency>('CNY')

  useEffect(() => {
    statsApi.getOverview()
      .then((res) => setData(res.data))
      .finally(() => setLoading(false))
  }, [])

  if (loading) {
    return (
      <div className="app-loading-section">
        <Spin size="large" />
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

  const { kpi, daily_trend, top_customers } = data

  const fmt = (v: number) => v.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })

  return (
    <div className="fo-container">
      {/* ── KPI 卡片行：双币种并列 ── */}
      <div className="fo-kpi-row">
        <div className="fo-kpi-card fo-kpi-card--contracts">
          <div className="fo-kpi-card__icon">
            <FileTextOutlined />
          </div>
          <div className="fo-kpi-card__body">
            <div className="fo-kpi-card__value">{kpi.total_contracts}</div>
            <div className="fo-kpi-card__label">合同总数</div>
          </div>
          <div className="fo-kpi-card__sub">进行中 {kpi.active_contracts}</div>
        </div>

        <div className="fo-kpi-card fo-kpi-card--customers">
          <div className="fo-kpi-card__icon">
            <TeamOutlined />
          </div>
          <div className="fo-kpi-card__body">
            <div className="fo-kpi-card__value">{kpi.total_customers}</div>
            <div className="fo-kpi-card__label">客户总数</div>
          </div>
        </div>

        <div className="fo-kpi-card fo-kpi-card--income">
          <div className="fo-kpi-card__icon">
            <ArrowUpOutlined />
          </div>
          <div className="fo-kpi-card__body">
            <div className="fo-kpi-card__value">
              <span className="fo-kpi-card__currency">CNY</span>
              <span className="fo-kpi-card__symbol">¥</span>{fmt(kpi.total_income.CNY)}
            </div>
            <div className="fo-kpi-card__value fo-kpi-card__value--sub">
              <span className="fo-kpi-card__currency">HKD</span>
              <span className="fo-kpi-card__symbol">HK$</span>{fmt(kpi.total_income.HKD)}
            </div>
            <div className="fo-kpi-card__label">已收总额</div>
          </div>
        </div>

        <div className="fo-kpi-card fo-kpi-card--expense">
          <div className="fo-kpi-card__icon">
            <ArrowDownOutlined />
          </div>
          <div className="fo-kpi-card__body">
            <div className="fo-kpi-card__value">
              <span className="fo-kpi-card__currency">CNY</span>
              <span className="fo-kpi-card__symbol">¥</span>{fmt(kpi.total_expense.CNY)}
            </div>
            <div className="fo-kpi-card__value fo-kpi-card__value--sub">
              <span className="fo-kpi-card__currency">HKD</span>
              <span className="fo-kpi-card__symbol">HK$</span>{fmt(kpi.total_expense.HKD)}
            </div>
            <div className="fo-kpi-card__label">支出总额</div>
          </div>
        </div>

        <div className="fo-kpi-card fo-kpi-card--profit">
          <div className="fo-kpi-card__icon">
            <DollarOutlined />
          </div>
          <div className="fo-kpi-card__body">
            <div className="fo-kpi-card__value">
              <span className="fo-kpi-card__currency">CNY</span>
              <span className="fo-kpi-card__symbol">¥</span>{fmt(kpi.total_profit.CNY)}
            </div>
            <div className="fo-kpi-card__value fo-kpi-card__value--sub">
              <span className="fo-kpi-card__currency">HKD</span>
              <span className="fo-kpi-card__symbol">HK$</span>{fmt(kpi.total_profit.HKD)}
            </div>
            <div className="fo-kpi-card__label">利润</div>
          </div>
        </div>

        <div className="fo-kpi-card fo-kpi-card--remaining">
          <div className="fo-kpi-card__icon">
            <DollarOutlined />
          </div>
          <div className="fo-kpi-card__body">
            <div className="fo-kpi-card__value">
              <span className="fo-kpi-card__currency">CNY</span>
              <span className="fo-kpi-card__symbol">¥</span>{fmt(kpi.total_remaining.CNY)}
            </div>
            <div className="fo-kpi-card__value fo-kpi-card__value--sub">
              <span className="fo-kpi-card__currency">HKD</span>
              <span className="fo-kpi-card__symbol">HK$</span>{fmt(kpi.total_remaining.HKD)}
            </div>
            <div className="fo-kpi-card__label">待收金额</div>
          </div>
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

      {/* ── TOP 10 客户利润（全宽） ── */}
      <div className="fo-chart-card fo-chart-card--full">
        <div className="fo-chart-card__title">
          <span>客户利润排名 TOP 10</span>
          <Segmented
            size="small"
            value={topCurrency}
            onChange={(v) => setTopCurrency(v as Currency)}
            options={['CNY', 'HKD']}
          />
        </div>
        <ReactECharts
          option={topCustomerOption(top_customers, topCurrency)}
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

function topCustomerOption(data: FinancialOverviewType['top_customers'], currency: Currency) {
  // 按所选币种的利润排序，取前 10
  const sorted = [...data]
    .filter(d => (d.profit[currency] || 0) !== 0 || (d.total_income[currency] || 0) !== 0)
    .sort((a, b) => b.profit[currency] - a.profit[currency])
    .slice(0, 10)
  const names = sorted.map(d => d.customer_name)
  const sym = CURRENCY_LABEL[currency].symbol
  const yFormatter = (v: number) => v >= 10000 ? `${(v / 10000).toFixed(0)}万` : v.toString()
  return {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter: (params: any[]) => {
        const idx = params[0].dataIndex
        const item = sorted[idx]
        return `<b>${item.customer_name}</b><br/>合同数：${item.contract_count}<br/>` +
          params.map(p => `${p.marker} ${p.seriesName}：${sym}${Number(p.value).toLocaleString('zh-CN', { minimumFractionDigits: 2 })}`).join('<br/>')
      },
    },
    legend: { data: ['已收', '支出', '利润'], top: 0, right: 0 },
    grid: { top: 40, bottom: 24, left: 100, right: 30 },
    xAxis: {
      type: 'value',
      axisLabel: { fontSize: 12, formatter: yFormatter },
    },
    yAxis: { type: 'category', data: names, axisLabel: { fontSize: 12 } },
    series: [
      {
        name: '已收',
        type: 'bar',
        data: sorted.map(d => d.total_income[currency]),
        itemStyle: { color: '#0d9486', borderRadius: [0, 4, 4, 0] },
        barMaxWidth: 16,
      },
      {
        name: '支出',
        type: 'bar',
        data: sorted.map(d => d.total_expense[currency]),
        itemStyle: { color: '#dc2626', borderRadius: [0, 4, 4, 0] },
        barMaxWidth: 16,
      },
      {
        name: '利润',
        type: 'bar',
        data: sorted.map(d => d.profit[currency]),
        itemStyle: { color: '#c9952b', borderRadius: [0, 4, 4, 0] },
        barMaxWidth: 16,
      },
    ],
  }
}
