import { useQuery } from '@tanstack/react-query'
import { useEffect, useMemo, useState } from 'react'
import { Download } from 'lucide-react'
import { api } from '@/api/client'
import { MetricResponse, MetricHistoryResponse } from '@/types'
import { Card, CardContent } from '@/components/ui/Card'
import { LineChart } from '@/components/charts/LineChart'
import { formatNumber, formatPercent, formatDate } from '@/lib/utils'

export function MetricsPage() {
  const [selectedMetric, setSelectedMetric] = useState('dau')
  const [timeRange, setTimeRange] = useState('30d')

  const { data: metrics } = useQuery({
    queryKey: ['metrics'],
    queryFn: () => api.metrics.list(),
  })

  const { data: history } = useQuery({
    queryKey: ['metricHistory', selectedMetric, timeRange],
    queryFn: () => {
      const currentMetric = metrics?.find((metric) => metric.metric_name === selectedMetric)
      const endDate = currentMetric?.period_end ? new Date(currentMetric.period_end) : new Date()
      const startDate = new Date(endDate)

      if (timeRange === '7d') {
        startDate.setDate(endDate.getDate() - 7)
      } else if (timeRange === '30d') {
        startDate.setDate(endDate.getDate() - 30)
      } else {
        startDate.setDate(endDate.getDate() - 90)
      }

      return api.metrics.history(selectedMetric, {
        start_date: startDate.toISOString(),
        end_date: endDate.toISOString(),
        interval: timeRange === '90d' ? '1 week' : '1 day',
      })
    },
    enabled: !!selectedMetric && !!metrics?.length,
  })

  const metricLabelMap: Record<string, string> = {
    dau: 'Daily Active Users',
    mau: 'Monthly Active Users',
    retention: 'Retention Rate',
    revenue: 'Revenue',
  }

  const metricOptions = useMemo(
    () => (metrics ?? []).map((metric) => ({
      value: metric.metric_name,
      label: metricLabelMap[metric.metric_name] ?? metric.metric_name.toUpperCase(),
    })),
    [metrics]
  )

  useEffect(() => {
    if (!metricOptions.length) {
      return
    }

    const selectedExists = metricOptions.some((option) => option.value === selectedMetric)
    if (!selectedExists) {
      setSelectedMetric(metricOptions[0].value)
    }
  }, [metricOptions, selectedMetric])

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Metrics</h1>
          <p className="text-gray-500 mt-1">Track and analyze key product metrics</p>
        </div>
        <div className="flex items-center gap-2">
          <button className="btn-secondary flex items-center gap-2">
            <Download className="w-4 h-4" />
            Export
          </button>
        </div>
      </div>

      {/* Metric Selector */}
      <Card>
        <CardContent className="p-4">
          <div className="flex flex-col sm:flex-row gap-4 items-end">
            <div className="flex-1">
              <label className="label block mb-1">Select Metric</label>
              <select
                value={selectedMetric}
                onChange={(e) => setSelectedMetric(e.target.value)}
                className="input"
              >
                {metricOptions.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="label block mb-1">Time Range</label>
              <select
                value={timeRange}
                onChange={(e) => setTimeRange(e.target.value)}
                className="input"
              >
                <option value="7d">Last 7 Days</option>
                <option value="30d">Last 30 Days</option>
                <option value="90d">Last 90 Days</option>
              </select>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Current Metric Value */}
      <Card>
        <CardContent className="p-6">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
            <div>
              <h3 className="text-lg font-semibold text-gray-900">
                {metricOptions.find((o) => o.value === selectedMetric)?.label}
              </h3>
              <p className="text-gray-500 text-sm mt-1">Current value and trend</p>
            </div>
            <div className="flex items-center gap-4">
              <div className="text-right">
                <p className="text-3xl font-bold text-gray-900">
                   {metrics?.find((m) => m.metric_name === selectedMetric)?.value.toLocaleString() ?? '—'}
                </p>
                <p className="text-sm text-gray-500">Last updated: {formatDate(new Date().toISOString())}</p>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Time Series Chart */}
      <Card title={`${metricOptions.find((o) => o.value === selectedMetric)?.label} Trend`} subtitle={`Last ${timeRange === '7d' ? '7 days' : timeRange === '30d' ? '30 days' : '90 days'}`}>
        <LineChart
          data={history?.data ?? []}
          xKey="timestamp"
          yKey="value"
          color="primary"
          height={400}
        />
      </Card>

      {/* All Metrics Table */}
      <Card title="All Metrics" subtitle="Current values for all tracked metrics">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-gray-200">
                <th className="text-left p-4 font-medium text-gray-500">Metric</th>
                <th className="text-right p-4 font-medium text-gray-500">Current Value</th>
                <th className="text-right p-4 font-medium text-gray-500">Period</th>
                <th className="text-left p-4 font-medium text-gray-500">Sample Size</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {metrics?.map((metric) => (
                <tr key={metric.metric_name} className="hover:bg-gray-50">
                  <td className="p-4 font-medium text-gray-900">{metric.metric_name}</td>
                  <td className="text-right p-4 font-mono text-gray-900">
                    {typeof metric.value === 'number' && metric.value < 1 ? formatPercent(metric.value) : formatNumber(metric.value)}
                  </td>
                  <td className="text-right p-4 text-gray-500 text-sm">
                    {formatDate(metric.period_start)} - {formatDate(metric.period_end)}
                  </td>
                  <td className="p-4 text-gray-500">
                    {metric.sample_size ? formatNumber(metric.sample_size) : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  )
}
