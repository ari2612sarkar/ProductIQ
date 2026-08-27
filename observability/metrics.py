"""
Prometheus metrics definitions
"""
from prometheus_client import Counter, Gauge, Histogram

# HTTP Metrics
http_requests_total = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"]
)

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "endpoint"],
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
)

# Agent Metrics
agent_execution_duration_seconds = Histogram(
    "agent_execution_duration_seconds",
    "Agent execution duration in seconds",
    ["agent_name", "status"],
    buckets=[1, 5, 10, 30, 60, 120, 300]
)

agent_steps_total = Counter(
    "agent_steps_total",
    "Total agent steps executed",
    ["agent_name", "step_name", "status"]
)

# LLM Metrics
llm_latency_seconds = Histogram(
    "llm_latency_seconds",
    "LLM API latency in seconds",
    ["model", "provider"],
    buckets=[0.5, 1, 2, 5, 10, 20, 30, 60]
)

llm_tokens_total = Counter(
    "llm_tokens_total",
    "Total LLM tokens used",
    ["model", "type"],  # type values: prompt, completion, total
)

llm_cost_usd_total = Counter(
    "llm_cost_usd_total",
    "Total LLM cost in USD",
    ["model"]
)

llm_errors_total = Counter(
    "llm_errors_total",
    "Total LLM errors",
    ["model", "error_type"]
)

# SQL Metrics
sql_execution_duration_seconds = Histogram(
    "sql_execution_duration_seconds",
    "SQL query execution duration in seconds",
    ["query_type"],  # select, insert, etc.
    buckets=[0.01, 0.05, 0.1, 0.5, 1, 5, 10, 30]
)

sql_rows_returned = Histogram(
    "sql_rows_returned",
    "Number of rows returned by SQL query",
    buckets=[1, 10, 100, 1000, 10000, 100000]
)

sql_errors_total = Counter(
    "sql_errors_total",
    "Total SQL errors",
    ["error_type"]
)

# Investigation Metrics
investigation_total = Counter(
    "investigation_total",
    "Total investigations",
    ["trigger", "status"]
)

investigation_duration_seconds = Histogram(
    "investigation_duration_seconds",
    "Investigation duration in seconds",
    ["trigger"],
    buckets=[10, 30, 60, 120, 300, 600, 1800]
)

# Anomaly Metrics
anomaly_detected_total = Counter(
    "anomaly_detected_total",
    "Total anomalies detected",
    ["metric_name", "severity"]
)

anomaly_resolution_duration_seconds = Histogram(
    "anomaly_resolution_duration_seconds",
    "Time to resolve anomaly in seconds",
    ["metric_name", "severity"],
    buckets=[60, 300, 900, 3600, 86400, 604800]
)

# RAG Metrics
rag_retrieval_duration_seconds = Histogram(
    "rag_retrieval_duration_seconds",
    "RAG retrieval duration in seconds",
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1, 2, 5]
)

rag_results_count = Histogram(
    "rag_results_count",
    "Number of results returned by RAG retrieval",
    buckets=[1, 5, 10, 20, 50, 100]
)

rag_rerank_duration_seconds = Histogram(
    "rag_rerank_duration_seconds",
    "RAG reranking duration in seconds",
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1, 2]
)

# System Metrics
active_investigations = Gauge(
    "active_investigations",
    "Number of currently active investigations"
)

database_connections_active = Gauge(
    "database_connections_active",
    "Active database connections"
)

redis_connections_active = Gauge(
    "redis_connections_active",
    "Active Redis connections"
)


def setup_metrics() -> None:
    """Initialize metrics (called on startup)."""
    # Metrics are automatically registered when imported
