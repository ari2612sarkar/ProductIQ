import { formatDate, formatPercent, getSeverityColor, cn } from '@/lib/utils'
import { AnomalyResponse } from '@/types'

interface AnomalyListProps {
  anomalies: AnomalyResponse[]
  limit?: number
}

export function AnomalyList({ anomalies, limit = 10 }: AnomalyListProps) {
  const displayAnomalies = anomalies.slice(0, limit)

  if (displayAnomalies.length === 0) {
    return (
      <div className="text-center py-8">
        <p className="text-gray-500">No anomalies detected</p>
      </div>
    )
  }

  return (
    <div className="space-y-3">
      {displayAnomalies.map((anomaly) => (
        <div
          key={anomaly.id}
          className="flex items-center gap-4 p-4 bg-gray-50 rounded-lg border border-gray-200 hover:bg-gray-100 transition-colors"
        >
          <span className={cn('badge px-3 py-1', getSeverityColor(anomaly.severity))}>
            {anomaly.severity.charAt(0).toUpperCase() + anomaly.severity.slice(1)}
          </span>

          <div className="flex-1 min-w-0">
            <p className="font-medium text-gray-900 truncate">{anomaly.metric_name}</p>
            <div className="flex items-center gap-4 text-sm text-gray-500 mt-1">
              <span>
                {formatPercent(anomaly.relative_change)} change
              </span>
              <span>
                {formatPercent(anomaly.baseline_value)} → {formatPercent(anomaly.current_value)}
              </span>
              <span>{anomaly.detection_method}</span>
            </div>
          </div>

          <span className="text-sm text-gray-500 whitespace-nowrap">
            {formatDate(anomaly.detected_at)}
          </span>
        </div>
      ))}
      {anomalies.length > limit && (
        <div className="text-center pt-2">
          <span className="text-sm text-gray-500">
            +{anomalies.length - limit} more anomalies
          </span>
        </div>
      )}
    </div>
  )
}