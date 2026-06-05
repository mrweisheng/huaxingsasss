import { useEffect, useState } from 'react'
import { Spin, Empty } from 'antd'
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


export default function FinancialOverview() {
  const [loading, setLoading] = useState(true)
  const [data, setData] = useState<FinancialOverviewType | null>(null)

  useEffect(() => {
    statsApi.getOverview()
      .then((res) => setData(res.data))
      .finally(() => setLoading(false))
  }, [])

  if (loading) {
    return (
      <div className="fo-loading">
        <Spin size="large" />
      </div>
    )
  }

  if (!data) {
    return (
      <div className="fo-loading">
        <Empty description="暂无数据" />
      </div>
    )
  }

  const { kpi, monthly_trend, business_type_distribution, top_customers, contract_status } = data

  const fmt = (v: number) => v.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })

  return (
    <div className="fo-container">
      {/* ── KPI 卡片行 ── */}
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
              <span className="fo-kpi-card__symbol">$</span>{fmt(kpi.total_income.HKD)}
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
              <span className="fo-kpi-card__symbol">$</span>{fmt(kpi.total_expense.HKD)}
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
              <span className="fo-kpi-card__symbol">$</span>{fmt(kpi.total_profit.HKD)}
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
              <span className="fo-kpi-card__symbol">$</span>{fmt(kpi.total_remaining.HKD)}
            </div>
            <div className="fo-kpi-card__label">待收金额</div>
          </div>
        </div>
      </div>

      {/* ── 图表行 ── */}
      <div className="fo-chart-row">
        <div className="fo-chart-card fo-chart-card--wide">
          <div className="fo-chart-card__title">月度收支趋势</div>
          <ReactECharts
            option={monthlyTrendOption(monthly_trend)}
            style={{ height: 320 }}
            notMerge
          />
        </div>
        <div className="fo-chart-card">
          <div className="fo-chart-card__title">业务类型分布</div>
          <ReactECharts
            option={businessTypeOption(business_type_distribution)}
            style={{ height: 320 }}
            notMerge
          />
        </div>
      </div>

      {/* ── 底部行 ── */}
      <div className="fo-bottom-row">
        <div className="fo-chart-card fo-chart-card--wide">
          <div className="fo-chart-card__title">客户利润排名 TOP 10</div>
          <ReactECharts
            option={topCustomerOption(top_customers)}
            style={{ height: 320 }}
            notMerge
          />
        </div>
        <div className="fo-chart-card">
          <div className="fo-chart-card__title">合同状态分布</div>
          <ReactECharts
            option={contractStatusOption(contract_status)}
            style={{ height: 320 }}
            notMerge
          />
        </div>
      </div>
    </div>
  )
}


/* ── ECharts 配置工厂 ── */

function monthlyTrendOption(data: FinancialOverviewType['monthly_trend']) {
  const months = data.map(d => d.month)
  return {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter: (params: any[]) => {
        let s = `<b>${params[0].axisValue}</b><br/>`
        params.forEach(p => {
          s += `${p.marker} ${p.seriesName}：${Number(p.value).toLocaleString('zh-CN', { minimumFractionDigits: 2 })}<br/>`
        })
        return s
      },
    },
    legend: { data: ['收入', '支出', '利润'], top: 0, right: 0 },
    grid: { top: 40, bottom: 24, left: 60, right: 20 },
    xAxis: { type: 'category', data: months, axisLabel: { fontSize: 12 } },
    yAxis: {
      type: 'value',
      axisLabel: {
        fontSize: 12,
        formatter: (v: number) => v >= 10000 ? `${(v / 10000).toFixed(0)}万` : v.toString(),
      },
    },
    series: [
      {
        name: '收入',
        type: 'bar',
        data: data.map(d => d.income),
        itemStyle: { color: '#0d9488', borderRadius: [4, 4, 0, 0] },
        barMaxWidth: 28,
      },
      {
        name: '支出',
        type: 'bar',
        data: data.map(d => d.expense),
        itemStyle: { color: '#dc2626', borderRadius: [4, 4, 0, 0] },
        barMaxWidth: 28,
      },
      {
        name: '利润',
        type: 'line',
        data: data.map(d => d.profit),
        smooth: true,
        lineStyle: { color: '#c9952b', width: 2 },
        itemStyle: { color: '#c9952b' },
        areaStyle: {
          color: {
            type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(201,149,43,0.2)' },
              { offset: 1, color: 'rgba(201,149,43,0.01)' },
            ],
          },
        },
      },
    ],
  }
}

function businessTypeOption(data: FinancialOverviewType['business_type_distribution']) {
  const colors = ['#1e3a5f', '#c9952b', '#0d9488', '#94a3b8']
  return {
    tooltip: {
      trigger: 'item',
      formatter: (p: any) => `${p.name}<br/>合同数：${p.data.count}<br/>利润：¥${Number(p.value).toLocaleString('zh-CN', { minimumFractionDigits: 2 })}`,
    },
    legend: { orient: 'vertical', right: 10, top: 'center', textStyle: { fontSize: 12 } },
    series: [{
      type: 'pie',
      radius: ['42%', '70%'],
      center: ['40%', '50%'],
      avoidLabelOverlap: true,
      itemStyle: { borderRadius: 6, borderColor: '#fff', borderWidth: 2 },
      label: { show: false },
      emphasis: { label: { show: true, fontSize: 14, fontWeight: 'bold' } },
      data: data.map((d, i) => ({
        name: d.business_type,
        value: d.profit,
        count: d.contract_count,
        itemStyle: { color: colors[i % colors.length] },
      })),
    }],
  }
}

function topCustomerOption(data: FinancialOverviewType['top_customers']) {
  const sorted = [...data].sort((a, b) => a.profit - b.profit)
  const names = sorted.map(d => d.customer_name)
  return {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter: (params: any[]) => {
        const idx = params[0].dataIndex
        const item = sorted[idx]
        return `<b>${item.customer_name}</b><br/>合同数：${item.contract_count}<br/>` +
          params.map(p => `${p.marker} ${p.seriesName}：¥${Number(p.value).toLocaleString('zh-CN', { minimumFractionDigits: 2 })}`).join('<br/>')
      },
    },
    legend: { data: ['已收', '支出', '利润'], top: 0, right: 0 },
    grid: { top: 40, bottom: 24, left: 100, right: 30 },
    xAxis: {
      type: 'value',
      axisLabel: {
        fontSize: 12,
        formatter: (v: number) => v >= 10000 ? `${(v / 10000).toFixed(0)}万` : v.toString(),
      },
    },
    yAxis: { type: 'category', data: names, axisLabel: { fontSize: 12 } },
    series: [
      {
        name: '已收',
        type: 'bar',
        data: sorted.map(d => d.total_income),
        itemStyle: { color: '#0d9486', borderRadius: [0, 4, 4, 0] },
        barMaxWidth: 16,
      },
      {
        name: '支出',
        type: 'bar',
        data: sorted.map(d => d.total_expense),
        itemStyle: { color: '#dc2626', borderRadius: [0, 4, 4, 0] },
        barMaxWidth: 16,
      },
      {
        name: '利润',
        type: 'bar',
        data: sorted.map(d => d.profit),
        itemStyle: { color: '#c9952b', borderRadius: [0, 4, 4, 0] },
        barMaxWidth: 16,
      },
    ],
  }
}

function contractStatusOption(data: FinancialOverviewType['contract_status']) {
  const colorMap: Record<string, string> = {
    '草稿': '#94a3b8',
    '进行中': '#2563eb',
    '已完成': '#0d9488',
    '已取消': '#dc2626',
  }
  return {
    tooltip: {
      trigger: 'item',
      formatter: (p: any) => `${p.name}：${p.value} 个`,
    },
    series: [{
      type: 'pie',
      radius: ['0%', '65%'],
      center: ['50%', '55%'],
      roseType: 'area',
      itemStyle: { borderRadius: 6, borderColor: '#fff', borderWidth: 2 },
      label: { formatter: '{b}\n{c}个', fontSize: 12 },
      data: data.map(d => ({
        name: d.status,
        value: d.count,
        itemStyle: { color: colorMap[d.status] || '#94a3b8' },
      })),
    }],
  }
}
