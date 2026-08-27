import { useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ChevronRight, Download, Clock, CheckCircle, AlertCircle, Info } from 'lucide-react'
import { api } from '@/api/client'
import { InvestigationDetailResponse, SQLQueryResponse, RecommendationResponse } from '@/types'
import { Card } from '@/components/ui/Card'
import { formatDate, getStatusColor, getPriorityColor, cn } from '@/lib/utils'
import { formatNumber, formatPercent, formatCurrency } from '@/lib/utils'

export function InvestigationDetailPage() {
  const { id } = useParams<{ id: string }>()

  const { data: investigation } = useQuery({
    queryKey: ['investigation', id],
    queryFn: () => api.investigations.get(id!),
    enabled: !!id,
  })

  const { data: sqlQueries } = useQuery({
    queryKey: ['investigationSql', id],
    queryFn: () => api.investigations.getSqlQueries(id!),
    enabled: !!id,
  })

  const { data: recommendations } = useQuery({
    queryKey: ['investigationRecommendations', id],
    queryFn: () => api.investigations.getRecommendations(id!),
    enabled: !!id,
  })

  if (!investigation) return null

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
        <div>
          <div className="flex items-center gap-3 mb-2">
            <h1 className="text-2xl font-bold text-gray-900">{investigation.question}</h1>
            <span className={cn('badge px-3 py-1', getStatusColor(investigation.status))}>
              {investigation.status.replace('_', ' ').charAt(0).toUpperCase() + investigation.status.replace('_', ' ').slice(1)}
            </span>
          </div>
          <p className="text-gray-500 text-sm">Trigger: {investigation.trigger_type} • Created {formatDate(investigation.created_at)}</p>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="card p-6">
          <p className="text-sm font-medium text-gray-500">Confidence</p>
          <p className="text-3xl font-bold text-primary-600 mt-1">
            {investigation.confidence ? `${(investigation.confidence * 100).toFixed(0)}%` : '—'}
          </p>
        </div>
        <div className="card p-6">
          <p className="text-sm font-medium text-gray-500">SQL Queries</p>
          <p className="text-3xl font-bold text-gray-900 mt-1">{sqlQueries?.length ?? 0}</p>
        </div>
        <div className="card p-6">
          <p className="text-sm font-medium text-gray-500">Recommendations</p>
          <p className="text-3xl font-bold text-gray-900 mt-1">{recommendations?.length ?? 0}</p>
        </div>
        <div className="card p-6">
          <p className="text-sm font-medium text-gray-500">Duration</p>
          <p className="text-3xl font-bold text-gray-900 mt-1">
            {investigation.execution_time_ms ? `${(investigation.execution_time_ms / 1000).toFixed(1)}s` : '—'}
          </p>
        </div>
      </div>

      {/* Root Cause Summary */}
      {investigation.root_cause_summary && (
        <Card title="Root Cause Summary">
          <div className="prose prose-sm max-w-none text-gray-700">
            {investigation.root_cause_summary}
          </div>
        </Card>
      )}

      {/* SQL Investigation Steps */}
      <Card title="SQL Investigation Steps">
        <div className="space-y-4">
          {sqlQueries?.map((step) => (
            <div key={step.id} className="border border-gray-200 rounded-lg overflow-hidden">
              <div className="bg-gray-50 px-4 py-3 border-b border-gray-200 flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <span className="badge bg-primary-100 text-primary-800">Step {step.step_number}</span>
                  <span className="font-medium text-gray-900">{step.question}</span>
                </div>
                <div className="flex items-center gap-2">
                  {step.execution_time_ms && (
                    <span className="text-sm text-gray-500">{step.execution_time_ms}ms</span>
                  )}
                  {step.rows_returned !== undefined && (
                    <span className="text-sm text-gray-500">{step.rows_returned} rows</span>
                  )}
                  {step.error && <span className="badge bg-danger-100 text-danger-800">Error</span>}
                </div>
              </div>
              <div className="p-4">
                <div className="bg-gray-900 rounded-lg p-4 overflow-x-auto font-mono text-sm text-gray-100">
                  <pre>{step.sql_query}</pre>
                </div>
                {step.explanation && (
                  <div className="mt-3 p-3 bg-blue-50 rounded-lg text-sm text-blue-800">
                    {step.explanation}
                  </div>
                )}
                {step.result_summary && (
                  <div className="mt-3 p-3 bg-gray-50 rounded-lg text-sm text-gray-700">
                    <strong>Result:</strong> {step.result_summary}
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      </Card>

      {/* Recommendations */}
      <Card title="Recommendations">
        <div className="space-y-4">
          {recommendations?.map((rec) => (
            <div key={rec.id} className="border border-gray-200 rounded-lg p-6">
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-3 mb-2">
                    <h4 className="font-semibold text-gray-900">{rec.title}</h4>
                    <span className={cn('badge', getPriorityColor(rec.priority))}>{rec.priority}</span>
                  </div>
                  <p className="text-gray-600 mb-3">{rec.description}</p>
                  <div className="flex flex-wrap gap-4 text-sm text-gray-600">
                    <span>RICE: <strong>{rec.rice_score?.toFixed(0) ?? '—'}</strong></span>
                    <span>Reach: <strong>{rec.reach ? formatNumber(rec.reach) : '—'}</strong></span>
                    <span>Impact: <strong>{rec.impact?.toFixed(1) ?? '—'}</strong></span>
                    <span>Confidence: <strong>{rec.confidence ? formatPercent(rec.confidence) : '—'}</strong></span>
                    <span>Effort: <strong>{rec.effort ?? '—'} weeks</strong></span>
                    {rec.revenue_impact && (
                      <span>Revenue: <strong>{formatCurrency(rec.revenue_impact)}/yr</strong></span>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {rec.evidence_summary && (
                    <span className="text-sm text-gray-500">{rec.evidence_summary}</span>
                  )}
                </div>
              </div>
            </div>
          ))}
          {(!recommendations || recommendations.length === 0) && (
            <div className="text-center py-8 text-gray-500">
              No recommendations generated yet
            </div>
          )}
        </div>
      </Card>
    </div>
  )
}