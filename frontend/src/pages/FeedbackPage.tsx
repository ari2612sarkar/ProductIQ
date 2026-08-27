import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Search, MessageSquare, AlertTriangle } from 'lucide-react'
import { api } from '@/api/client'
import { FeedbackItem, SupportTicketResponse } from '@/types'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/Card'
import { FeedbackResultsList } from '@/components/feedback/FeedbackResultsList'
import { formatDate, getSeverityColor, getStatusColor, cn } from '@/lib/utils'

export function FeedbackPage() {
  const [activeTab, setActiveTab] = useState<'search' | 'tickets'>('search')
  const [searchQuery, setSearchQuery] = useState('')
  const [filters, setFilters] = useState({ source: '', sentiment: '', product_area: '' })

  const { data: searchResults } = useQuery({
    queryKey: ['feedbackSearch', searchQuery, filters],
    queryFn: () => api.feedback.search({ query: searchQuery, ...filters, page: 1, page_size: 20 }),
    enabled: !!searchQuery,
  })

  const { data: tickets } = useQuery({
    queryKey: ['tickets'],
    queryFn: () => api.feedback.tickets({ limit: 50 }),
  })

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Feedback</h1>
          <p className="text-gray-500 mt-1">Analyze customer feedback and support tickets</p>
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200">
        <nav className="flex gap-1" aria-label="Tabs">
          <button
            onClick={() => setActiveTab('search')}
            className={cn(
              'px-4 py-3 text-sm font-medium border-b-2 transition-colors',
              activeTab === 'search'
                ? 'border-primary-600 text-primary-600'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            )}
          >
            <MessageSquare className="w-4 h-4 inline mr-2" />
            Search Feedback
          </button>
          <button
            onClick={() => setActiveTab('tickets')}
            className={cn(
              'px-4 py-3 text-sm font-medium border-b-2 transition-colors',
              activeTab === 'tickets'
                ? 'border-primary-600 text-primary-600'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            )}
          >
            <AlertTriangle className="w-4 h-4 inline mr-2" />
            Support Tickets
          </button>
        </nav>
      </div>

      {activeTab === 'search' && (
        <div className="space-y-6">
          {/* Search Filters */}
          <Card>
            <CardContent className="p-4">
              <div className="flex flex-col sm:flex-row gap-4">
                <div className="flex-1">
                  <label className="label block mb-1">Search Feedback</label>
                  <div className="relative">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                    <input
                      type="text"
                      placeholder="Search feedback, reviews, NPS..."
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      className="input pl-10"
                    />
                  </div>
                </div>
                <div>
                  <label className="label block mb-1">Source</label>
                  <select
                    value={filters.source}
                    onChange={(e) => setFilters({ ...filters, source: e.target.value })}
                    className="input"
                  >
                    <option value="">All Sources</option>
                    <option value="nps">NPS</option>
                    <option value="review">Reviews</option>
                    <option value="feature_request">Feature Requests</option>
                    <option value="survey">Surveys</option>
                  </select>
                </div>
                <div>
                  <label className="label block mb-1">Sentiment</label>
                  <select
                    value={filters.sentiment}
                    onChange={(e) => setFilters({ ...filters, sentiment: e.target.value })}
                    className="input"
                  >
                    <option value="">All Sentiments</option>
                    <option value="positive">Positive</option>
                    <option value="negative">Negative</option>
                    <option value="neutral">Neutral</option>
                  </select>
                </div>
                <div>
                  <label className="label block mb-1">Product Area</label>
                  <select
                    value={filters.product_area}
                    onChange={(e) => setFilters({ ...filters, product_area: e.target.value })}
                    className="input"
                  >
                    <option value="">All Areas</option>
                    <option value="onboarding">Onboarding</option>
                    <option value="billing">Billing</option>
                    <option value="performance">Performance</option>
                    <option value="ui">UI/UX</option>
                  </select>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Search Results */}
          <Card>
            <CardHeader>
              <CardTitle>Search Results</CardTitle>
              <CardDescription>
                {searchResults ? `${searchResults.total} results found` : 'Enter a search query to find feedback'}
              </CardDescription>
            </CardHeader>
            {searchQuery && !searchResults && (
              <CardContent>
                <div className="text-center py-8 text-gray-500">Searching...</div>
              </CardContent>
            )}
            {searchResults?.items.length === 0 && !searchQuery && (
              <CardContent>
                <div className="text-center py-8 text-gray-500">
                  No feedback found matching your criteria
                </div>
              </CardContent>
            )}
            {!searchResults && !searchQuery && (
              <CardContent>
                <div className="text-center py-8 text-gray-500">
                  Enter a search query to find feedback
                </div>
              </CardContent>
)}
            {searchResults && (
              <CardContent>
                <FeedbackResultsList items={searchResults.items} total={searchResults.total} />
              </CardContent>
            )}
          </Card>
        </div>
      )}

      {activeTab === 'tickets' && (
        <div className="space-y-6">
          <Card>
            <CardContent className="p-4">
              <div className="flex flex-col sm:flex-row gap-4">
                <div>
                  <label className="label block mb-1">Status</label>
                  <select className="input">
                    <option value="">All Status</option>
                    <option value="open">Open</option>
                    <option value="in_progress">In Progress</option>
                    <option value="resolved">Resolved</option>
                  </select>
                </div>
                <div>
                  <label className="label block mb-1">Priority</label>
                  <select className="input">
                    <option value="">All Priorities</option>
                    <option value="critical">Critical</option>
                    <option value="high">High</option>
                    <option value="medium">Medium</option>
                    <option value="low">Low</option>
                  </select>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <div className="overflow-hidden">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-gray-200 bg-gray-50">
                    <th className="text-left p-4 font-medium text-gray-500">Subject</th>
                    <th className="text-left p-4 font-medium text-gray-500">Category</th>
                    <th className="text-left p-4 font-medium text-gray-500">Priority</th>
                    <th className="text-left p-4 font-medium text-gray-500">Status</th>
                    <th className="text-left p-4 font-medium text-gray-500">Created</th>
                    <th className="text-right p-4 font-medium text-gray-500">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {tickets?.map((ticket) => (
                    <tr key={ticket.id} className="hover:bg-gray-50">
                      <td className="p-4">
                        <p className="font-medium text-gray-900">{ticket.subject}</p>
                        <p className="text-sm text-gray-500 truncate max-w-xs mt-1">{ticket.body.slice(0, 100)}...</p>
                      </td>
                      <td className="p-4 text-gray-500">{ticket.category || '—'}</td>
                      <td className="p-4">
                        <span className={cn('badge', getSeverityColor(ticket.priority))}>
                          {ticket.priority.charAt(0).toUpperCase() + ticket.priority.slice(1)}
                        </span>
                      </td>
                      <td className="p-4">
                        <span className={cn('badge', getStatusColor(ticket.status))}>
                          {ticket.status.replace('_', ' ').charAt(0).toUpperCase() + ticket.status.replace('_', ' ').slice(1)}
                        </span>
                      </td>
                      <td className="p-4 text-gray-500">{formatDate(ticket.created_at)}</td>
                      <td className="p-4 text-right">
                        <button className="p-2 text-gray-500 hover:bg-gray-100 rounded-lg">View</button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </div>
      )}
    </div>
  )
}