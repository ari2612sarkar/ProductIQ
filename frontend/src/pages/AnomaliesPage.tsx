import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Search, AlertTriangle, CheckCircle } from 'lucide-react'
import { api } from '@/api/client'
import { Card, CardContent } from '@/components/ui/Card'
import { formatDate, getSeverityColor, cn } from '@/lib/utils'

export function AnomaliesPage() {
  const queryClient = useQueryClient()
  const [filters, setFilters] = useState({
    metric_name: '',
    severity: '',
    acknowledged: false,
    start_date: '',
    end_date: '',
  })
  const [searchQuery, setSearchQuery] = useState('')

  const { data: anomalies } = useQuery({
    queryKey: ['anomalies', filters],
    queryFn: () => api.metrics.anomalies(filters),
  })

  const acknowledgeMutation = useMutation({
    mutationFn: (id: string) => api.metrics.acknowledgeAnomaly(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['anomalies'] }),
  })

  const resolveMutation = useMutation({
    mutationFn: (id: string) => api.metrics.resolveAnomaly(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['anomalies'] }),
  })

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Anomalies</h1>
          <p className="text-gray-500 mt-1">Monitor and manage detected anomalies</p>
        </div>
      </div>

      {/* Filters */}
      <Card>
        <CardContent className="p-4">
          <div className="flex flex-col sm:flex-row gap-4">
            <div className="flex-1">
              <label className="label block mb-1">Search</label>
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                <input
                  type="text"
                  placeholder="Search anomalies..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="input pl-10"
                />
              </div>
            </div>
            <div className="sm:flex sm:gap-4">
              <div>
                <label className="label block mb-1">Severity</label>
                <select
                  value={filters.severity}
                  onChange={(e) => setFilters({ ...filters, severity: e.target.value })}
                  className="input"
                >
                  <option value="">All Severities</option>
                  <option value="critical">Critical</option>
                  <option value="high">High</option>
                  <option value="medium">Medium</option>
                  <option value="low">Low</option>
                </select>
              </div>
              <div>
                <label className="label block mb-1">Status</label>
                <select
                  value={filters.acknowledged ? 'acknowledged' : 'unacknowledged'}
                  onChange={(e) => setFilters({ ...filters, acknowledged: e.target.value === 'acknowledged' })}
                  className="input"
                >
                  <option value="unacknowledged">Unacknowledged</option>
                  <option value="acknowledged">Acknowledged</option>
                  <option value="resolved">Resolved</option>
                </select>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Anomalies List */}
      <Card>
        <div className="overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="border-b border-gray-200 bg-gray-50">
                <th className="text-left p-4 font-medium text-gray-500">Metric</th>
                <th className="text-left p-4 font-medium text-gray-500">Severity</th>
                <th className="text-left p-4 font-medium text-gray-500">Change</th>
                <th className="text-left p-4 font-medium text-gray-500">Method</th>
                <th className="text-left p-4 font-medium text-gray-500">Detected</th>
                <th className="text-left p-4 font-medium text-gray-500">Status</th>
                <th className="text-right p-4 font-medium text-gray-500">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {anomalies?.filter((a) =>
                !searchQuery ||
                a.metric_name.toLowerCase().includes(searchQuery.toLowerCase())
              ).map((anomaly) => (
                <tr key={anomaly.id} className="hover:bg-gray-50">
                  <td className="p-4 font-medium text-gray-900">{anomaly.metric_name}</td>
                  <td className="p-4">
                    <span className={cn('badge px-3 py-1', getSeverityColor(anomaly.severity))}>
                      {anomaly.severity.charAt(0).toUpperCase() + anomaly.severity.slice(1)}
                    </span>
                  </td>
                  <td className="p-4 font-mono text-gray-900">
                    {anomaly.relative_change > 0 ? '+' : ''}{anomaly.relative_change.toFixed(1)}%
                  </td>
                  <td className="p-4 text-gray-500 text-sm">{anomaly.detection_method}</td>
                  <td className="p-4 text-gray-500">{formatDate(anomaly.detected_at)}</td>
                  <td className="p-4">
                    {anomaly.resolved_at ? (
                      <span className="badge bg-success-100 text-success-800">Resolved</span>
                    ) : anomaly.acknowledged_at ? (
                      <span className="badge bg-primary-100 text-primary-800">Acknowledged</span>
                    ) : (
                      <span className="badge bg-warning-100 text-warning-800">New</span>
                    )}
                  </td>
                  <td className="p-4 text-right">
                    <div className="flex items-center justify-end gap-2">
                      {!anomaly.acknowledged_at && (
                        <button
                          onClick={() => acknowledgeMutation.mutate(anomaly.id)}
                          disabled={acknowledgeMutation.isPending}
                          className="p-2 text-gray-500 hover:bg-gray-100 rounded-lg transition-colors"
                          title="Acknowledge"
                        >
                          <CheckCircle className="w-5 h-5" />
                        </button>
                      )}
                      {!anomaly.resolved_at && (
                        <button
                          onClick={() => resolveMutation.mutate(anomaly.id)}
                          disabled={resolveMutation.isPending}
                          className="p-2 text-gray-500 hover:bg-gray-100 rounded-lg transition-colors"
                          title="Resolve"
                        >
                          <AlertTriangle className="w-5 h-5" />
                        </button>
                      )}
                    </div>
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