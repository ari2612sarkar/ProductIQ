import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Search, Plus, ChevronRight, ChevronLeft } from 'lucide-react'
import { api } from '@/api/client'
import { InvestigationSummary, InvestigationDetailResponse } from '@/types'
import { Card, CardContent } from '@/components/ui/Card'
import { formatDate, getStatusColor, cn } from '@/lib/utils'

export function InvestigationsPage() {
  const queryClient = useQueryClient()
  const [page, setPage] = useState(1)
  const [filters, setFilters] = useState({ status: '', trigger: '' })
  const [searchQuery, setSearchQuery] = useState('')

  const { data: investigations } = useQuery({
    queryKey: ['investigations', page, filters, searchQuery],
    queryFn: () => api.investigations.list({ page, page_size: 20, status: filters.status, trigger: filters.trigger }),
  })

  const createMutation = useMutation({
    mutationFn: (data: { question: string; trigger?: string; anomaly_id?: string }) => api.investigations.create(data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['investigations'] }),
  })

  const [showCreateModal, setShowCreateModal] = useState(false)
  const [newQuestion, setNewQuestion] = useState('')
  const [newTrigger, setNewTrigger] = useState('manual')

  const handleCreate = (e: React.FormEvent) => {
    e.preventDefault()
    createMutation.mutate({ question: newQuestion, trigger: newTrigger })
    setShowCreateModal(false)
    setNewQuestion('')
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Investigations</h1>
          <p className="text-gray-500 mt-1">Manage and track product investigations</p>
        </div>
        <button
          onClick={() => setShowCreateModal(true)}
          className="btn-primary flex items-center gap-2"
        >
          <Plus className="w-4 h-4" />
          New Investigation
        </button>
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
                  placeholder="Search investigations..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="input pl-10"
                />
              </div>
            </div>
            <div className="sm:flex sm:gap-4">
              <div>
                <label className="label block mb-1">Status</label>
                <select
                  value={filters.status}
                  onChange={(e) => setFilters({ ...filters, status: e.target.value })}
                  className="input"
                >
                  <option value="">All Status</option>
                  <option value="pending">Pending</option>
                  <option value="in_progress">In Progress</option>
                  <option value="completed">Completed</option>
                  <option value="failed">Failed</option>
                </select>
              </div>
              <div>
                <label className="label block mb-1">Trigger</label>
                <select
                  value={filters.trigger}
                  onChange={(e) => setFilters({ ...filters, trigger: e.target.value })}
                  className="input"
                >
                  <option value="">All Triggers</option>
                  <option value="manual">Manual</option>
                  <option value="anomaly">Anomaly</option>
                  <option value="scheduled">Scheduled</option>
                </select>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Investigations Table */}
      <Card>
        <div className="overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="border-b border-gray-200 bg-gray-50">
                <th className="text-left p-4 font-medium text-gray-500">Question</th>
                <th className="text-left p-4 font-medium text-gray-500">Trigger</th>
                <th className="text-left p-4 font-medium text-gray-500">Status</th>
                <th className="text-left p-4 font-medium text-gray-500">Confidence</th>
                <th className="text-left p-4 font-medium text-gray-500">Created</th>
                <th className="text-left p-4 font-medium text-gray-500">Completed</th>
                <th className="text-right p-4 font-medium text-gray-500">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {investigations?.items.map((inv) => (
                <tr key={inv.id} className="hover:bg-gray-50">
                  <td className="p-4">
                    <p className="font-medium text-gray-900 truncate max-w-xs">{inv.question}</p>
                    {inv.root_cause_summary && (
                      <p className="text-sm text-gray-500 truncate max-w-xs mt-1">{inv.root_cause_summary}</p>
                    )}
                  </td>
                  <td className="p-4">
                    <span className={cn('badge', inv.trigger === 'anomaly' ? 'bg-warning-100 text-warning-800' : inv.trigger === 'scheduled' ? 'bg-blue-100 text-blue-800' : 'bg-gray-100 text-gray-800')}>
                      {(inv.trigger ?? '—').charAt(0).toUpperCase() + (inv.trigger ?? '—').slice(1)}
                    </span>
                  </td>
                  <td className="p-4">
                    <span className={cn('badge', getStatusColor(inv.status))}>
                      {inv.status.replace('_', ' ').charAt(0).toUpperCase() + inv.status.replace('_', ' ').slice(1)}
                    </span>
                  </td>
                  <td className="p-4">
                    {inv.confidence ? (
                      <div className="flex items-center gap-2">
                        <div className="flex-1 h-2 bg-gray-200 rounded-full overflow-hidden">
                          <div
                            className="h-full bg-primary-600 rounded-full transition-all"
                            style={{ width: `${inv.confidence * 100}%` }}
                          />
                        </div>
                        <span className="text-sm font-medium text-gray-700 w-10">
                          {(inv.confidence * 100).toFixed(0)}%
                        </span>
                      </div>
                    ) : (
                      <span className="text-gray-500">—</span>
                    )}
                  </td>
                  <td className="p-4 text-gray-500">{formatDate(inv.created_at)}</td>
                  <td className="p-4 text-gray-500">{inv.completed_at ? formatDate(inv.completed_at) : '—'}</td>
                  <td className="p-4 text-right">
                    <button className="p-2 text-gray-500 hover:bg-gray-100 rounded-lg transition-colors" title="View details">
                      <ChevronRight className="w-5 h-5" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {investigations && (
          <div className="px-6 py-4 border-t border-gray-200 flex items-center justify-between">
            <p className="text-sm text-gray-500">
              Showing {(page - 1) * 20 + 1} to {Math.min(page * 20, investigations.total)} of {investigations.total}
            </p>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setPage(page - 1)}
                disabled={page === 1}
                className="p-2 text-gray-500 hover:bg-gray-100 rounded-lg disabled:opacity-50"
              >
                <ChevronLeft className="w-5 h-5" />
              </button>
              <button
                onClick={() => setPage(page + 1)}
                disabled={page === investigations.total_pages}
                className="p-2 text-gray-500 hover:bg-gray-100 rounded-lg disabled:opacity-50"
              >
                <ChevronRight className="w-5 h-5" />
              </button>
            </div>
          </div>
        )}
      </Card>

      {/* Create Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-gray-900/50">
          <div className="bg-white rounded-xl p-6 w-full max-w-md mx-4">
            <h2 className="text-xl font-bold text-gray-900 mb-4">New Investigation</h2>
            <form onSubmit={handleCreate} className="space-y-4">
              <div>
                <label className="label block mb-1">Question</label>
                <textarea
                  value={newQuestion}
                  onChange={(e) => setNewQuestion(e.target.value)}
                  rows={4}
                  className="input"
                  placeholder="What would you like to investigate?"
                  required
                />
              </div>
              <div>
                <label className="label block mb-1">Trigger</label>
                <select value={newTrigger} onChange={(e) => setNewTrigger(e.target.value)} className="input">
                  <option value="manual">Manual</option>
                  <option value="anomaly">Anomaly</option>
                  <option value="scheduled">Scheduled</option>
                </select>
              </div>
              <div className="flex justify-end gap-3 pt-4">
                <button type="button" onClick={() => setShowCreateModal(false)} className="btn-secondary">
                  Cancel
                </button>
                <button type="submit" disabled={createMutation.isPending} className="btn-primary">
                  {createMutation.isPending ? 'Creating...' : 'Create Investigation'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}