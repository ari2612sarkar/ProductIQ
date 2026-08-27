export interface Investigation {
  id: string
  question: string
  trigger_type: string
  status: string
  anomaly_id?: string
  root_cause_summary?: string
  confidence?: number
  created_at: string
  completed_at?: string
  execution_time_ms?: number
  llm_tokens_used?: number
  llm_cost_usd?: number
}

export interface InvestigationSummary {
  id: string
  question: string
  trigger_type: string
  trigger?: string
  status: string
  anomaly_id?: string
  root_cause_summary?: string
  confidence?: number
  created_at: string
  completed_at?: string
  execution_time_ms?: number
}

export interface InvestigationListResponse {
  items: InvestigationSummary[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export interface InvestigationDetailResponse extends Investigation {
  sql_queries: SQLQueryResponse[]
  recommendations: RecommendationResponse[]
}

export interface SQLQueryResponse {
  id: string
  investigation_id: string
  step_number: number
  question: string
  sql_query: string
  explanation?: string
  execution_time_ms?: number
  rows_returned?: number
  result_summary?: string
  error?: string
}

export interface RecommendationResponse {
  id: string
  investigation_id: string
  title: string
  description: string
  priority: string
  rice_score?: number
  reach?: number
  impact?: number
  confidence?: number
  effort?: number
  revenue_impact?: number
  strategic_alignment?: number
  risk?: number
  evidence_summary?: string
  status: string
}

export interface MetricResponse {
  metric_name: string
  period_start: string
  period_end: string
  value: number
  sample_size?: number
  dimensions: Record<string, any>
}

export interface MetricHistoryResponse {
  metric_name: string
  data: { timestamp: string; value: number }[]
  interval: string
}

export interface AnomalyResponse {
  id: string
  metric_name: string
  baseline_value: number
  current_value: number
  absolute_change: number
  relative_change: number
  detection_method: string
  severity: string
  confidence?: number
  detected_at: string
  acknowledged_at?: string
  resolved_at?: string
}

export interface AnomalyDetailResponse extends AnomalyResponse {
  metadata: Record<string, any>
}

export interface FeedbackItem {
  id: string
  user_id?: string
  source: string
  rating?: number
  text: string
  product_area?: string
  sentiment?: string
  created_at: string
}

export interface FeedbackSearchRequest {
  query?: string
  source?: string
  sentiment?: string
  product_area?: string
  start_date?: string
  end_date?: string
  page?: number
  page_size?: number
}

export interface FeedbackSearchResponse {
  items: FeedbackItem[]
  total: number
  page: number
  page_size: number
  query?: string
}

export interface SupportTicketResponse {
  id: string
  user_id?: string
  subject: string
  body: string
  category?: string
  priority: string
  status: string
  created_at: string
  resolved_at?: string
  tags: string[]
}

export interface ExperimentResponse {
  id: string
  name: string
  hypothesis?: string
  description?: string
  status: string
  started_at: string
  ended_at?: string
  control_variant: string
  treatment_variant: string
  traffic_allocation: number
  target_metric?: string
  minimum_detectable_effect?: number
}

export interface ExperimentAnalysisResponse {
  experiment_id: string
  metric: string
  control: Record<string, any>
  treatment: Record<string, any>
  effect_size: number
  confidence_interval: number[]
  effect_size_ci?: number[]
  p_value: number
  statistically_significant: boolean
  confidence_level?: number
  test_used?: string
  interpretation: string
  assumptions_met?: boolean
  warnings?: string[]
  achieved_power?: number
  analysis_source?: 'real' | 'mock'
  analyzed_at: string
}

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  page_size: number
  total_pages: number
}
