import { ArrowUpRight, ArrowDownRight } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { LucideIcon } from 'lucide-react'

interface MetricCardProps {
  title: string
  value: string | number
  icon: LucideIcon
  iconColor: string
  trend?: { value: number; positive: boolean }
  subtitle?: string
}

export function MetricCard({ title, value, icon: Icon, iconColor, trend, subtitle }: MetricCardProps) {
  return (
    <div className="card p-6">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm font-medium text-gray-500">{title}</p>
          <p className="text-3xl font-bold text-gray-900 mt-1">{value}</p>
          {subtitle && <p className="text-sm text-gray-500 mt-1">{subtitle}</p>}
        </div>
        <div className={cn('p-3 rounded-lg', iconColor)}>
          <Icon className="w-6 h-6" aria-hidden="true" />
        </div>
      </div>

      {trend && (
        <div className="flex items-center gap-1 mt-4">
          {trend.positive ? (
            <ArrowUpRight className="w-4 h-4 text-success-600" />
          ) : (
            <ArrowDownRight className="w-4 h-4 text-danger-600" />
          )}
          <span className={cn('text-sm font-medium', trend.positive ? 'text-success-600' : 'text-danger-600')}>
            {trend.value > 0 ? '+' : ''}{trend.value.toFixed(1)}%
          </span>
          <span className="text-sm text-gray-500">vs last period</span>
        </div>
      )}
    </div>
  )
}