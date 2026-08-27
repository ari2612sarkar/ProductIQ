import { FeedbackItem } from '@/types'
import { Star } from 'lucide-react'
import { formatDate, getSeverityColor, cn } from '@/lib/utils'

interface FeedbackResultsListProps {
  items: FeedbackItem[]
  total: number
}

export function FeedbackResultsList({ items, total }: FeedbackResultsListProps) {
  const renderItems = () => {
    return (
      <div className="space-y-4">
        {items.map((item) => (
          <div
            key={item.id}
            className="border border-gray-200 rounded-lg p-4 hover:bg-gray-50 transition-colors"
          >
            <div className="flex items-start justify-between gap-4">
              <div className="flex-1">
                <div className="flex items-center gap-3 mb-2">
                  <span className={cn('badge px-3 py-1', getSeverityColor(item.sentiment || 'neutral'))}>
                    {(item.sentiment || 'neutral').charAt(0).toUpperCase() + (item.sentiment || 'neutral').slice(1)}
                  </span>
                  <span className="badge bg-gray-100 text-gray-800">{item.source}</span>
                  {item.rating && (
                    <span className="flex items-center gap-1 text-warning-600">
                      <Star className="w-4 h-4 fill-current" /> {item.rating}/10
                    </span>
                  )}
                </div>
                <p className="text-gray-700 mb-2">{item.text}</p>
                <div className="flex items-center gap-4 text-sm text-gray-500">
                  <span>{item.product_area}</span>
                  <span>{formatDate(item.created_at)}</span>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <button className="p-2 text-gray-500 hover:bg-gray-100 rounded-lg">View Context</button>
              </div>
            </div>
          </div>
        ))}
      </div>
    )
  }

  const renderLoadMore = () => {
    return (
      total > items.length ? (
        <div className="text-center pt-4">
          <button className="btn-secondary">Load More</button>
        </div>
      ) : null
    )
  }

  return (
    <div className="space-y-4">
      {renderItems()}
      {renderLoadMore()}
    </div>
  )
}