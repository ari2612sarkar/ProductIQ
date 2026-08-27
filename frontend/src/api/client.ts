import type {
  Investigation,
  InvestigationListResponse,
  InvestigationDetailResponse,
  SQLQueryResponse,
  RecommendationResponse,
  MetricResponse,
  MetricHistoryResponse,
  AnomalyResponse,
  AnomalyDetailResponse,
  SupportTicketResponse,
  ExperimentResponse,
  ExperimentAnalysisResponse,
  FeedbackSearchRequest,
  FeedbackSearchResponse,
} from '@/types'

const API_BASE = '/api'

async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_BASE}${endpoint}`, {
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
    ...options,
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({ message: 'Unknown error' }))
    throw new Error(error.message || `HTTP ${response.status}`)
  }

  if (response.status === 204) {
    return undefined as T
  }

  return response.json()
}

export const api = {
  investigations: {
    list: (params?: { page?: number; page_size?: number; status?: string; trigger?: string }) => {
      const searchParams = new URLSearchParams()
      if (params?.page) searchParams.set('page', params.page.toString())
      if (params?.page_size) searchParams.set('page_size', params.page_size.toString())
      if (params?.status) searchParams.set('status', params.status)
      if (params?.trigger) searchParams.set('trigger', params.trigger)
      return request<InvestigationListResponse>(`/investigations?${searchParams}`)
    },

    get: (id: string) => request<InvestigationDetailResponse>(`/investigations/${id}`),

    create: (data: { question: string; trigger?: string; anomaly_id?: string }) =>
      request<Investigation>('/investigations', {
        method: 'POST',
        body: JSON.stringify(data),
      }),

    getSqlQueries: (id: string) => request<SQLQueryResponse[]>(`/investigations/${id}/sql-queries`),

    getRecommendations: (id: string) => request<RecommendationResponse[]>(`/investigations/${id}/recommendations`),
  },

  metrics: {
    list: (metricNames?: string[]) => {
      const params = metricNames ? `?metric_names=${metricNames.join(',')}` : ''
      return request<MetricResponse[]>(`/metrics${params}`)
    },

    history: (metricName: string, params?: { start_date?: string; end_date?: string; interval?: string; limit?: number }) => {
      const searchParams = new URLSearchParams()
      if (params?.start_date) searchParams.set('start_date', params.start_date)
      if (params?.end_date) searchParams.set('end_date', params.end_date)
      if (params?.interval) searchParams.set('interval', params.interval)
      if (params?.limit) searchParams.set('limit', params.limit.toString())
      return request<MetricHistoryResponse>(`/metrics/${metricName}/history?${searchParams}`)
    },

    anomalies: (params?: { metric_name?: string; severity?: string; start_date?: string; end_date?: string; acknowledged?: boolean; limit?: number }) => {
      const searchParams = new URLSearchParams()
      if (params?.metric_name) searchParams.set('metric_name', params.metric_name)
      if (params?.severity) searchParams.set('severity', params.severity)
      if (params?.start_date) searchParams.set('start_date', params.start_date)
      if (params?.end_date) searchParams.set('end_date', params.end_date)
      if (params?.acknowledged !== undefined) searchParams.set('acknowledged', params.acknowledged.toString())
      if (params?.limit) searchParams.set('limit', params.limit.toString())
      return request<AnomalyResponse[]>(`/anomalies?${searchParams}`)
    },

    anomalyDetail: (id: string) => request<AnomalyDetailResponse>(`/anomalies/${id}`),

    acknowledgeAnomaly: (id: string) => request<{ status: string }>(`/anomalies/${id}/acknowledge`, { method: 'POST' }),

    resolveAnomaly: (id: string, notes?: string) => request<{ status: string }>(`/anomalies/${id}/resolve`, {
      method: 'POST',
      body: JSON.stringify({ resolution_notes: notes }),
    }),
  },

  feedback: {
    search: (data: FeedbackSearchRequest) =>
      request<FeedbackSearchResponse>('/feedback/search', {
        method: 'POST',
        body: JSON.stringify(data),
      }),

    tickets: (params?: { user_id?: string; status?: string; category?: string; priority?: string; limit?: number }) => {
      const searchParams = new URLSearchParams()
      if (params?.user_id) searchParams.set('user_id', params.user_id)
      if (params?.status) searchParams.set('status', params.status)
      if (params?.category) searchParams.set('category', params.category)
      if (params?.priority) searchParams.set('priority', params.priority)
      if (params?.limit) searchParams.set('limit', params.limit.toString())
      return request<SupportTicketResponse[]>(`/feedback/tickets?${searchParams}`)
    },

    ticketDetail: (id: string) => request<SupportTicketResponse>(`/feedback/tickets/${id}`),
  },

  experiments: {
    list: (params?: { status?: string; limit?: number }) => {
      const searchParams = new URLSearchParams()
      if (params?.status) searchParams.set('status', params.status)
      if (params?.limit) searchParams.set('limit', params.limit.toString())
      return request<ExperimentResponse[]>(`/experiments?${searchParams}`)
    },

    get: (id: string) => request<ExperimentResponse>(`/experiments/${id}`),

    assignments: (id: string, params?: { variant?: string; limit?: number }) => {
      const searchParams = new URLSearchParams()
      if (params?.variant) searchParams.set('variant', params.variant)
      if (params?.limit) searchParams.set('limit', params.limit.toString())
      return request<any[]>(`/experiments/${id}/assignments?${searchParams}`)
    },

    analyze: (data: { experiment_id: string; metric: string; metric_type: 'proportion' | 'mean' | 'ratio' }) =>
      request<ExperimentAnalysisResponse>('/experiments/analyze', {
        method: 'POST',
        body: JSON.stringify(data),
      }),
  },

  sql: {
    query: (sql: string, explanation?: string) =>
      request<{
        columns: string[]
        data: Record<string, any>[]
        row_count: number
        truncated: boolean
        execution_time_ms: number
      }>('/sql/query', {
        method: 'POST',
        body: JSON.stringify({ sql, explanation }),
      }),

    investigationQueries: (id: string) => request<SQLQueryResponse[]>(`/sql/investigations/${id}/queries`),
  },

  health: () => request<{ status: string; service: string; version: string }>('/health'),

  ready: () => request<{ status: string; database: string }>('/ready'),
}