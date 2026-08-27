import { useQuery } from '@tanstack/react-query'
import {
  Users,
  TrendingUp,
  DollarSign,
  AlertTriangle,
  Search,
  FlaskConical,
  MessageSquare,
} from 'lucide-react'
import { api } from '@/api/client'
import { MetricResponse, AnomalyResponse } from '@/types'
import { Card } from '@/components/ui/Card'
import { MetricCard } from '@/components/charts/MetricCard'
import { AnomalyList } from '@/components/anomalies/AnomalyList'
import { LineChart } from '@/components/charts/LineChart'
import { formatNumber, formatPercent, formatCurrency } from '@/lib/utils'

export function DashboardPage() {
  const { data: metrics } = useQuery({
    queryKey: ['metrics'],
    queryFn: () => api.metrics.list(),
  })

  const { data: anomalies } = useQuery({
    queryKey: ['anomalies', { limit: 5 }],
    queryFn: () => api.metrics.anomalies({ limit: 5, acknowledged: false }),
  })

  const metricMap = new Map(metrics?.map((m) => [m.metric_name, m]) ?? [])

  const dau = metricMap.get('dau')?.value
  const mau = metricMap.get('mau')?.value
  const retention = metricMap.get('retention')?.value
  const revenue = metricMap.get('revenue')?.value

  const renderMetric = (value: number | undefined, formatter: (v: number) => string) => {
    if (value === undefined || value === null) {
      return '--'
    }
    return formatter(value)
  }

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
          <p className="text-gray-500 mt-1">Product health overview and key metrics</p>
        </div>
      </div>

      {/* Key Metrics Row */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard
          title="Daily Active Users"
          value={renderMetric(dau, formatNumber)}
          icon={Users}
          iconColor="text-primary-600 bg-primary-100"
          trend={{ value: 2.3, positive: true }}
          subtitle="vs last week"
        />
        <MetricCard
          title="Monthly Active Users"
          value={renderMetric(mau, formatNumber)}
          icon={Users}
          iconColor="text-blue-600 bg-blue-100"
          trend={{ value: 1.1, positive: true }}
          subtitle="vs last month"
        />
        <MetricCard
          title="30-Day Retention"
          value={renderMetric(retention, formatPercent)}
          icon={TrendingUp}
          iconColor="text-success-600 bg-success-100"
          trend={{ value: -0.8, positive: false }}
          subtitle="vs last month"
        />
        <MetricCard
          title="Revenue (MRR)"
          value={renderMetric(revenue, formatCurrency)}
          icon={DollarSign}
          iconColor="text-success-600 bg-success-100"
          trend={{ value: 3.2, positive: true }}
          subtitle="vs last month"
        />
      </div>

      {/* Charts Row */}
      <div className="grid gap-6 lg:grid-cols-2">
        <Card title="DAU Trend (30 Days)" subtitle="Daily active users over time">
          <LineChart
            data={Array.from({ length: 30 }, (_, i) => {
              const date = new Date(Date.now() - (29 - i) * 86400000).toISOString().split('T')[0];
              const value = Math.floor(10000 + Math.random() * 2000);
              return { date, value };
            })}
            xKey="date"
            yKey="value"
            color="primary"
          />
        </Card>

        <Card title="Retention by Cohort" subtitle="30-day retention by signup week">
          <div className="space-y-3">
            {['Week 1', 'Week 2', 'Week 3', 'Week 4'].map((week, i) => (
              <div key={week} className="flex items-center gap-4">
                <span className="w-24 text-sm text-gray-600">{week}</span>
                <div className="flex-1 h-4 bg-gray-100 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-primary-600 rounded-full transition-all"
                    style={{ width: `${65 + i * 5}%` }}
                  />
                </div>
                <span className="w-12 text-sm text-gray-600 text-right">
                  {65 + i * 5}%
                </span>
              </div>
            ))}
          </div>
        </Card>
      </div>

      {/* Recent Anomalies */}
      <Card title="Recent Anomalies" subtitle="Unacknowledged anomalies requiring attention">
        <AnomalyList anomalies={anomalies ?? []} limit={5} />
      </Card>

      {/* Validation Scenario */}
      <Card title="Validation Scenario" subtitle="Quick end-to-end test case for this dashboard">
        <div className="space-y-3 text-sm text-gray-700">
          <p>
            <span className="font-medium text-gray-900">Scenario:</span> A PM sees a retention dip and needs to confirm
            that metrics, anomalies, and investigation actions are connected.
          </p>
          <ol className="list-decimal pl-5 space-y-2">
            <li>Verify key cards show non-empty values for DAU, MAU, retention, and revenue.</li>
            <li>Open recent anomalies and confirm at least one retention-related alert is listed.</li>
            <li>Start a new investigation from Quick Actions and track it in the Investigations view.</li>
            <li>Pass condition: all API-backed sections load without zero-value fallbacks.</li>
          </ol>
        </div>
      </Card>

      {/* Quick Actions */}
      <Card title="Quick Actions">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <button className="p-4 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors text-left">
            <Search className="w-6 h-6 text-primary-600 mb-2" />
            <h3 className="font-medium text-gray-900">New Investigation</h3>
            <p className="text-sm text-gray-500 mt-1">Start a new product investigation</p>
          </button>
          <button className="p-4 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors text-left">
            <AlertTriangle className="w-6 h-6 text-warning-600 mb-2" />
            <h3 className="font-medium text-gray-900">Review Anomalies</h3>
            <p className="text-sm text-gray-500 mt-1">{anomalies?.length ?? 0} unacknowledged</p>
          </button>
          <button className="p-4 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors text-left">
            <FlaskConical className="w-6 h-6 text-blue-600 mb-2" />
            <h3 className="font-medium text-gray-900">Analyze Experiment</h3>
            <p className="text-sm text-gray-500 mt-1">Review A/B test results</p>
          </button>
          <button className="p-4 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors text-left">
            <MessageSquare className="w-6 h-6 text-green-600 mb-2" />
            <h3 className="font-medium text-gray-900">Search Feedback</h3>
            <p className="text-sm text-gray-500 mt-1">Analyze customer feedback</p>
          </button>
        </div>
      </Card>
    </div>
  )
}
