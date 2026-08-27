import { Search } from 'lucide-react'
import { useState } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { api } from '@/api/client'
import { ExperimentResponse, ExperimentAnalysisResponse } from '@/types'
import { Card, CardContent } from '@/components/ui/Card'
import { formatDate, cn, formatPercent, getStatusColor } from '@/lib/utils'

export function ExperimentsPage() {
  const [filters, setFilters] = useState({ status: '' })
  const [searchQuery, setSearchQuery] = useState('')
  const [analysisResult, setAnalysisResult] = useState<ExperimentAnalysisResponse | null>(null)
  const [analysisLoading, setAnalysisLoading] = useState(false)
  const [analysisError, setAnalysisError] = useState<string | null>(null)

  const { data: experiments } = useQuery({
    queryKey: ['experiments', filters.status],
    queryFn: () => api.experiments.list({ status: filters.status, limit: 50 }),
  })

  const analyzeMutation = useMutation({
    mutationFn: (data: { experiment_id: string; metric: string; metric_type: 'proportion' | 'mean' | 'ratio' }) =>
      api.experiments.analyze(data),
    onSuccess: (result) => {
      setAnalysisResult(result)
      setAnalysisError(null)
      setAnalysisLoading(false)
    },
    onError: (error: Error) => {
      setAnalysisError(error.message || 'Experiment analysis failed')
      setAnalysisLoading(false)
    },
  })

  const handleAnalyze = (experiment: ExperimentResponse, metric: string = 'conversion', metric_type: 'proportion' | 'mean' | 'ratio' = 'proportion') => {
    setAnalysisResult(null)
    setAnalysisError(null)
    setAnalysisLoading(true)
    analyzeMutation.mutate({ experiment_id: experiment.id, metric, metric_type })
  }

  const confidenceInterval = analysisResult
    ? (analysisResult.effect_size_ci ?? analysisResult.confidence_interval ?? []).map((v) => Number(v)).filter((v) => Number.isFinite(v))
    : []

  const toNumber = (value: unknown): number | null => {
    const num = Number(value)
    return Number.isFinite(num) ? num : null
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Experiments</h1>
          <p className="text-gray-500 mt-1">Analyze A/B test results</p>
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
                  placeholder="Search experiments..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="input pl-10"
                />
              </div>
            </div>
            <div>
              <label className="label block mb-1">Status</label>
              <select
                value={filters.status}
                onChange={(e) => setFilters({ ...filters, status: e.target.value })}
                className="input"
              >
                <option value="">All Status</option>
                <option value="running">Running</option>
                <option value="completed">Completed</option>
                <option value="stopped">Stopped</option>
              </select>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Experiments Table */}
      <Card>
        <div className="overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="border-b border-gray-200 bg-gray-50">
                <th className="text-left p-4 font-medium text-gray-500">Experiment</th>
                <th className="text-left p-4 font-medium text-gray-500">Status</th>
                <th className="text-left p-4 font-medium text-gray-500">Metric</th>
                <th className="text-left p-4 font-medium text-gray-500">Variants</th>
                <th className="text-left p-4 font-medium text-gray-500">Period</th>
                <th className="text-right p-4 font-medium text-gray-500">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {experiments?.filter((exp) =>
                !searchQuery ||
                exp.name.toLowerCase().includes(searchQuery.toLowerCase())
              ).map((experiment) => (
                <tr key={experiment.id} className="hover:bg-gray-50">
                  <td className="p-4">
                    <p className="font-medium text-gray-900">{experiment.name}</p>
                    {experiment.hypothesis && (
                      <p className="text-sm text-gray-500 truncate max-w-xs mt-1">{experiment.hypothesis}</p>
                    )}
                  </td>
                  <td className="p-4">
                    <span className={cn('badge', getStatusColor(experiment.status))}>
                      {experiment.status.charAt(0).toUpperCase() + experiment.status.slice(1)}
                    </span>
                  </td>
                  <td className="p-4 text-gray-500">{experiment.target_metric || '—'}</td>
                  <td className="p-4 text-gray-500">
                    {experiment.control_variant} vs {experiment.treatment_variant}
                  </td>
                  <td className="p-4 text-gray-500">
                    {formatDate(experiment.started_at)} - {experiment.ended_at ? formatDate(experiment.ended_at) : 'Ongoing'}
                  </td>
                  <td className="p-4 text-right">
                    <button
                      onClick={() => handleAnalyze(experiment)}
                      disabled={analysisLoading}
                      className="btn-primary flex items-center gap-2"
                    >
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4M6 16l-4-4 4-4" /></svg>
                      Analyze
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      {/* Analysis Results Modal */}
      {analysisResult && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-gray-900/50">
          <div className="bg-white rounded-xl p-6 w-full max-w-3xl mx-4 max-h-[80vh] overflow-y-auto">
            <div className="flex items-center justify-between mb-6">
              <div className="flex items-center gap-3">
                <h2 className="text-xl font-bold text-gray-900">Analysis Results</h2>
                <span className={cn('badge', analysisResult.analysis_source === 'real' ? 'bg-success-100 text-success-800' : 'bg-warning-100 text-warning-800')}>
                  {analysisResult.analysis_source === 'real' ? 'Real data analysis' : 'Mock analysis'}
                </span>
              </div>
              <button onClick={() => setAnalysisResult(null)} className="p-2 text-gray-500 hover:bg-gray-100 rounded-lg">
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
              </button>
            </div>

            <div className="space-y-4">
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="card p-4">
                  <p className="text-sm font-medium text-gray-500">Control</p>
                  <p className="text-2xl font-bold text-gray-900">
                    {analysisResult.control?.mean !== undefined && toNumber(analysisResult.control.mean) !== null
                      ? toNumber(analysisResult.control.mean)!.toFixed(4)
                      : analysisResult.control?.rate !== undefined && toNumber(analysisResult.control.rate) !== null
                        ? formatPercent(toNumber(analysisResult.control.rate)!)
                        : '—'}
                  </p>
                  <p className="text-sm text-gray-500">Sample: {analysisResult.control?.sample_size ?? '—'}</p>
                </div>
                <div className="card p-4">
                  <p className="text-sm font-medium text-gray-500">Treatment</p>
                  <p className="text-2xl font-bold text-gray-900">
                    {analysisResult.treatment?.mean !== undefined && toNumber(analysisResult.treatment.mean) !== null
                      ? toNumber(analysisResult.treatment.mean)!.toFixed(4)
                      : analysisResult.treatment?.rate !== undefined && toNumber(analysisResult.treatment.rate) !== null
                        ? formatPercent(toNumber(analysisResult.treatment.rate)!)
                        : '—'}
                  </p>
                  <p className="text-sm text-gray-500">Sample: {analysisResult.treatment?.sample_size ?? '—'}</p>
                </div>
              </div>

              <div className="card p-4 bg-gray-50">
                <h4 className="font-semibold text-gray-900 mb-3">Statistical Results</h4>
                <div className="grid gap-3 sm:grid-cols-3">
                  <div>
                    <p className="text-sm text-gray-500">Effect Size</p>
                    <p className="font-bold text-lg text-gray-900">
                      {toNumber(analysisResult.effect_size) !== null ? toNumber(analysisResult.effect_size)!.toFixed(3) : '—'}
                    </p>
                  </div>
                  <div>
                    <p className="text-sm text-gray-500">P-Value</p>
                    <p className="font-bold text-lg text-gray-900">
                      {toNumber(analysisResult.p_value) !== null ? toNumber(analysisResult.p_value)!.toFixed(4) : '—'}
                    </p>
                  </div>
                  <div>
                    <p className="text-sm text-gray-500">Confidence Interval</p>
                    <p className="font-bold text-lg text-gray-900">
                      {confidenceInterval.length >= 2
                        ? `[${confidenceInterval[0].toFixed(3)}, ${confidenceInterval[1].toFixed(3)}]`
                        : '—'}
                    </p>
                  </div>
                </div>
                <div className="mt-3 p-3 bg-gray-50 rounded-lg">
                  <p className="font-medium text-gray-900">{analysisResult.interpretation}</p>
                </div>
              </div>

              <div>
                <h4 className="font-semibold text-gray-900 mb-3">Significance</h4>
                <div className="flex items-center gap-3">
                  {analysisResult.statistically_significant ? (
                    <span className="badge bg-success-100 text-success-800 flex items-center gap-2">
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" /></svg>
                      Statistically Significant
                    </span>
                  ) : (
                    <span className="badge bg-gray-100 text-gray-800 flex items-center gap-2">
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 4c-.77 1.333.192 3 1.732 3z" /></svg>
                      Not Statistically Significant
                    </span>
                  )}
                  <span className="text-sm text-gray-500 ml-auto">
                    Power: {toNumber(analysisResult.achieved_power) !== null ? `${(toNumber(analysisResult.achieved_power)! * 100).toFixed(0)}%` : '—'}
                    {' '}• Test: {analysisResult.test_used ?? 'default'}
                  </span>
                </div>
              </div>

              {analysisResult.warnings && analysisResult.warnings.length > 0 && (
                <div className="p-3 bg-warning-50 border border-warning-200 rounded-lg">
                  <h4 className="font-medium text-warning-800 mb-2 flex items-center gap-2">
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 4c-.77 1.333.192 3 1.732 3z" /></svg>
                    Warnings
                  </h4>
                  <ul className="list-disc list-inside text-sm text-warning-700 space-y-1">
                    {analysisResult.warnings.map((w, i) => <li key={i}>{w}</li>)}
                  </ul>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {analysisError && (
        <Card>
          <CardContent className="p-4">
            <p className="text-danger-700 text-sm">Analysis failed: {analysisError}</p>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
