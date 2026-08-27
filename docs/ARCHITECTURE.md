# Architecture Document

## System Overview

The Autonomous Product Intelligence & Decision Engine is an agentic AI system that autonomously investigates product performance anomalies, identifies root causes, analyzes customer feedback and experiments, and produces evidence-backed product decisions. It simulates an internal AI Product Analyst / Product Intelligence team.

The system follows a deterministic pipeline architecture with explicit state management via LangGraph, ensuring reproducibility, observability, and controlled agent behavior.
## Component Architecture

\\\
+---------------------------------------------------------------------------+
|                        PRODUCT INTELLIGENCE ENGINE                          |
+---------------------------------------------------------------------------+
|                                                                             |
|  +------------+    +------------+    +------------+    +----------+       |
|  |   Events   |    |  Customer  |    |  Feedback  |    |Experiments|       |
|  | Ingestion  |    |   Data     |    | Ingestion  |    | Ingestion |       |
|  +-----+------+    +-----+------+    +-----+------+    +----+----+       |
|        |                  |                  |                 |          |
|        +------------------+------------------+-----------------+          |
|                           v                  v                           |
|                  +---------------------------+                          |
|                  |       METRIC ENGINE       |                          |
|                  |  * DAU/WAU/MAU            |                          |
|                  |  * Activation/Conversion  |                          |
|                  |  * Retention/Churn        |                          |
|                  |  * Revenue/ARPU           |                          |
|                  |  * Feature Adoption       |                          |
|                  +-------------+-------------+                          |
|                                |                                        |
|                                v                                        |
|                  +---------------------------+                          |
|                  |      ANOMALY DETECTION    |                          |
|                  |  * Rolling statistics     |                          |
|                  |  * Z-score thresholding   |                          |
|                  |  * Percentage change      |                          |
|                  |  * Baseline comparison    |                          |
|                  +-------------+-------------+                          |
|                                |                                        |
|                                v                                        |
|  +------------------------------------------------------------------------+  |
|  |                   ORCHESTRATOR AGENT (LangGraph)                   |  |
|  |  * Receives investigation requests                                   |  |
|  |  * Creates investigation state                                       |  |
|  |  * Determines required investigation steps                           |  |
|  |  * Coordinates specialized agents                                    |  |
|  |  * Maintains state                                                   |  |
|  |  * Detects incomplete investigations                                 |  |
|  |  * Produces final investigation package                              |  |
|  +---------------------------+------------------------------------------+  |
|                              |                                          |
|           +------------------+------------------+                      |
|           v                 v                 v                       |
|  +---------------+   +---------------+   +---------------+            |
|  |   SQL AGENT   |   | FEEDBACK AGENT|   | EXPERIMENT AGT|            |
|  |               |   |               |   |               |            |
|  | * Schema intr |   | * RAG retrie  |   | * Control/Trea|            |
|  | * SQL gen/val |   | * Clustering  |   | * Stat tests  |            |
|  | * Read-only   |   | * Theme ident |   | * Effect size |            |
|  | * Multi-step  |   | * Evidence    |   | * Significance|            |
|  +-------+-------+   +-------+-------+   +-------+-------+            |
|          |                 |                 |                        |
|          +-----------------+-----------------+                        |
|                        v                                              |
|               +--------------------------+                           |
|               |   EVIDENCE AGGREGATOR    |                           |
|               |   (Internal Component)   |                           |
|               +-----------+--------------+                           |
|                           |                                          |
|                           v                                          |
|                +----------------------+                             |
|                |  ROOT CAUSE AGENT    |                             |
|                |                      |                             |
|                | * Combine evidence   |                             |
|                | * Rank hypotheses    |                             |
|                | * FACT/INFERENCE/    |                             |
|                |   HYPOTHESIS         |                             |
|                | * Confidence score   |                             |
|                +----------+-----------+                             |
|                           |                                          |
|                           v                                          |
|                +----------------------+                             |
|                |   DECISION AGENT     |                             |
|                |                      |                             |
|                | * RICE scoring       |                             |
|                | * Impact estimation  |                             |
|                | * Prioritization     |                             |
|                | * Recommendations    |                             |
|                +----------------------+                             |
|                                                                             |
+---------------------------------------------------------------------------+
\\\

---

## Agent Architecture

### 1. Orchestrator Agent
- **Responsibility**: Central coordinator for the entire investigation workflow
- **Inputs**: Investigation request (question, trigger, context)
- **Outputs**: Complete investigation package with root causes and recommendations
- **Tools**: State management, agent delegation, step planning
- **State**: \InvestigationState\ (defined in Section 6)
- **Termination**: All required investigation steps completed or max iterations reached

### 2. SQL Investigation Agent
- **Responsibility**: Perform multi-step SQL investigations to answer analytical questions
- **Inputs**: Analytical question, current investigation state, database schema
- **Outputs**: SQL queries, execution results, analytical conclusions
- **Tools**: 
  - \get_schema\: Retrieve relevant table schemas
  - \generate_sql\: Generate SQL from natural language
  - \alidate_sql\: Parse and validate SQL (read-only, no dangerous operations)
  - \xecute_sql\: Execute read-only SQL with timeout and row limits
  - \interpret_results\: Analyze query results
- **Safety**: Read-only database credentials, query timeout (30s), row limit (10,000), SQL parsing validation

### 3. Feedback Intelligence Agent
- **Responsibility**: Retrieve and analyze customer feedback related to product problems
- **Inputs**: Investigation context, identified problem areas, search queries
- **Outputs**: Clustered feedback themes, relevant evidence with citations
- **Tools**:
  - \search_feedback\: Vector similarity search over feedback corpus
  - \cluster_feedback\: Group related feedback by semantic similarity
  - \xtract_themes\: Identify recurring themes with evidence
- **RAG Pipeline**: Documents -> Cleaning -> Chunking -> Embedding -> Vector Store -> Retriever

### 4. Experiment Agent
- **Responsibility**: Analyze A/B experiments with deterministic statistical methods
- **Inputs**: Experiment identifiers, metrics to analyze, investigation context
- **Outputs**: Statistical analysis results (effect size, confidence intervals, p-values, significance)
- **Tools**:
  - \get_experiment_data\: Retrieve experiment assignments and outcomes
  - \calculate_statistics\: Deterministic statistical tests (t-test, chi-square, proportion tests)
  - \interpret_results\: Generate statistical interpretation
- **Statistical Libraries**: SciPy, statsmodels (not LLM-based calculations)

### 5. Root Cause Agent
- **Responsibility**: Synthesize evidence from all sources to identify probable root causes
- **Inputs**: Aggregated evidence (SQL results, feedback clusters, experiment results)
- **Outputs**: Ranked root cause hypotheses with confidence scores and evidence citations
- **Tools**:
  - \compare_hypotheses\: Evaluate competing explanations
  - \ssign_confidence\: Bayesian-style confidence scoring
  - \classify_evidence\: Tag evidence as FACT/INFERENCE/HYPOTHESIS
- **Key Distinction**: Must explicitly classify each finding as FACT, INFERENCE, or HYPOTHESIS

### 6. Decision Agent
- **Responsibility**: Convert evidence into prioritized product recommendations
- **Inputs**: Root cause analysis, business context, effort estimates
- **Outputs**: Prioritized recommendations with RICE scores
- **Tools**:
  - \calculate_rice\: Reach, Impact, Confidence, Effort scoring
  - \stimate_impact\: Business impact quantification
  - \prioritize_actions\: Rank recommendations
- **Framework**: RICE (Reach * Impact * Confidence / Effort) with extensions for revenue impact, strategic alignment, risk
---

## Data Flow

### Primary Investigation Flow

\\\
1. TRIGGER
   +- Manual: POST /investigations with question
   +- Automated: Anomaly detection webhook
   +- Scheduled: Periodic health check

2. ORCHESTRATOR INITIALIZATION
   +- Create InvestigationState
   +- Parse question -> identify required investigation types
   +- Plan investigation steps (SQL, Feedback, Experiment)

3. PARALLEL INVESTIGATION (LangGraph fan-out)
   +- SQL Agent: Multi-step cohort/funnel/segmentation analysis
   +- Feedback Agent: RAG retrieval + clustering for relevant feedback
   +- Experiment Agent: Identify relevant experiments + statistical analysis

4. EVIDENCE AGGREGATION
   +- Collect all agent outputs
   +- Normalize evidence format
   +- Attach metadata (source, confidence, timestamp)

5. ROOT CAUSE ANALYSIS
   +- Compare hypotheses across evidence types
   +- Score each hypothesis
   +- Classify evidence (FACT/INFERENCE/HYPOTHESIS)
   +- Produce ranked root causes with confidence

6. DECISION ENGINE
   +- Generate potential actions from root causes
   +- Score each action using RICE+
   +- Rank by priority score
   +- Produce final recommendations

7. FINALIZATION
   +- Assemble investigation report
   +- Store in database
   +- Emit observability events
   +- Return investigation ID + summary
\\\

### Metric Calculation Flow

\\\
Events/Sessions -> Metric Engine -> Materialized Views -> Anomaly Detection
                                    |
                                    v
                              PostgreSQL (analytics schema)
                                    |
                                    v
                              API: GET /metrics, GET /anomalies
\\\

### Feedback Ingestion Flow

\\\
Support Tickets / Reviews / NPS -> Cleaning -> Chunking -> Embedding -> Vector DB
                                                                     |
                                                                     v
                                                            Feedback Agent Retrieval
\\\

---

## Database Architecture

### PostgreSQL Schema (Analytics Database)

\\\
+---------------------------------------------------------------------------+
|                            PRODUCT ANALYTICS SCHEMA                         |
+---------------------------------------------------------------------------+
|                                                                             |
|  users                                                                       |
|  +- id (PK, UUID)                                                           |
|  +- created_at (TIMESTAMPTZ)                                                |
|  +- email (VARCHAR, unique)                                                 |
|  +- plan_id (FK -> plans.id)                                                |
|  +- acquisition_channel (VARCHAR)                                           |
|  +- segment (VARCHAR)                                                       |
|  +- status (VARCHAR: active, churned, trial)                                |
|  +- metadata (JSONB)                                                        |
|                                                                             |
|  plans                                                                       |
|  +- id (PK, UUID)                                                           |
|  +- name (VARCHAR)                                                          |
|  +- price_monthly (DECIMAL)                                                 |
|  +- price_yearly (DECIMAL)                                                  |
|  +- features (JSONB)                                                        |
|                                                                             |
|  sessions                                                                    |
|  +- id (PK, UUID)                                                           |
|  +- user_id (FK -> users.id)                                                |
|  +- started_at (TIMESTAMPTZ)                                                |
|  +- ended_at (TIMESTAMPTZ)                                                  |
|  +- duration_seconds (INTEGER)                                              |
|  +- device_type (VARCHAR)                                                   |
|  +- platform (VARCHAR)                                                      |
|  +- country (VARCHAR)                                                       |
|                                                                             |
|  events                                                                      |
|  +- id (PK, UUID)                                                           |
|  +- user_id (FK -> users.id)                                                |
|  +- session_id (FK -> sessions.id)                                          |
|  +- event_name (VARCHAR)                                                    |
|  +- event_properties (JSONB)                                                |
|  +- timestamp (TIMESTAMPTZ)                                                 |
|  +- experiment_id (FK -> experiments.id, nullable)                          |
|                                                                             |
|  subscriptions                                                               |
|  +- id (PK, UUID)                                                           |
|  +- user_id (FK -> users.id)                                                |
|  +- plan_id (FK -> plans.id)                                                |
|  +- status (VARCHAR: active, cancelled, past_due, trialing)                |
|  +- started_at (TIMESTAMPTZ)                                                |
|  +- cancelled_at (TIMESTAMPTZ, nullable)                                    |
|  +- current_period_start (TIMESTAMPTZ)                                      |
|  +- current_period_end (TIMESTAMPTZ)                                        |
|  +- billing_cycle (VARCHAR: monthly, yearly)                                |
|                                                                             |
|  payments                                                                    |
|  +- id (PK, UUID)                                                           |
|  +- subscription_id (FK -> subscriptions.id)                                |
|  +- amount (DECIMAL)                                                        |
|  +- currency (VARCHAR)                                                      |
|  +- status (VARCHAR: succeeded, failed, refunded)                           |
|  +- paid_at (TIMESTAMPTZ)                                                   |
|  +- invoice_number (VARCHAR)                                                |
|                                                                             |
|  features                                                                    |
|  +- id (PK, UUID)                                                           |
|  +- name (VARCHAR)                                                          |
|  +- description (TEXT)                                                      |
|  +- category (VARCHAR)                                                      |
|  +- launched_at (TIMESTAMPTZ)                                               |
|                                                                             |
|  experiments                                                                 |
|  +- id (PK, UUID)                                                           |
|  +- name (VARCHAR)                                                          |
|  +- hypothesis (TEXT)                                                       |
|  +- status (VARCHAR: running, completed, stopped)                           |
|  +- started_at (TIMESTAMPTZ)                                                |
|  +- ended_at (TIMESTAMPTZ, nullable)                                        |
|  +- control_variant (VARCHAR)                                               |
|  +- treatment_variant (VARCHAR)                                             |
|  +- traffic_allocation (DECIMAL)                                            |
|                                                                             |
|  experiment_assignments                                                      |
|  +- id (PK, UUID)                                                           |
|  +- experiment_id (FK -> experiments.id)                                    |
|  +- user_id (FK -> users.id)                                                |
|  +- variant (VARCHAR: control, treatment)                                   |
|  +- assigned_at (TIMESTAMPTZ)                                               |
|  +- UNIQUE(experiment_id, user_id)                                          |
|                                                                             |
|  support_tickets                                                             |
|  +- id (PK, UUID)                                                           |
|  +- user_id (FK -> users.id, nullable)                                      |
|  +- subject (VARCHAR)                                                       |
|  +- body (TEXT)                                                             |
|  +- category (VARCHAR)                                                      |
|  +- priority (VARCHAR)                                                      |
|  +- status (VARCHAR: open, in_progress, resolved, closed)                   |
|  +- created_at (TIMESTAMPTZ)                                                |
|  +- resolved_at (TIMESTAMPTZ, nullable)                                     |
|  +- tags (TEXT[])                                                           |
|                                                                             |
|  product_feedback                                                            |
|  +- id (PK, UUID)                                                           |
|  +- user_id (FK -> users.id, nullable)                                      |
|  +- source (VARCHAR: nps, review, feature_request, survey)                 |
|  +- rating (INTEGER, nullable)                                              |
|  +- text (TEXT)                                                             |
|  +- product_area (VARCHAR)                                                  |
|  +- sentiment (VARCHAR: positive, negative, neutral)                       |
|  +- created_at (TIMESTAMPTZ)                                                |
|  +- metadata (JSONB)                                                        |
|                                                                             |
+---------------------------------------------------------------------------+
\\\

### Indexes

\\\sql
-- Performance indexes for analytical queries
CREATE INDEX idx_events_user_timestamp ON events(user_id, timestamp DESC);
CREATE INDEX idx_events_name_timestamp ON events(event_name, timestamp DESC);
CREATE INDEX idx_sessions_user_started ON sessions(user_id, started_at DESC);
CREATE INDEX idx_subscriptions_user_status ON subscriptions(user_id, status);
CREATE INDEX idx_payments_subscription_paid ON payments(subscription_id, paid_at DESC);
CREATE INDEX idx_experiment_assignments_exp_user ON experiment_assignments(experiment_id, user_id);
CREATE INDEX idx_support_tickets_created ON support_tickets(created_at DESC);
CREATE INDEX idx_product_feedback_created ON product_feedback(created_at DESC);
CREATE INDEX idx_product_feedback_area_sentiment ON product_feedback(product_area, sentiment);

-- For cohort analysis
CREATE INDEX idx_users_created_plan ON users(created_at, plan_id);
\\\

### Vector Database (Feedback RAG)

\\\
Collection: product_feedback
+- Vector: embedding (1536-dim, text-embedding-3-small)
+- Metadata:
|   +- document_id (UUID)
|   +- source (support_ticket, nps, review, feature_request, survey)
|   +- user_id (UUID, nullable)
|   +- timestamp (TIMESTAMPTZ)
|   +- product_area (VARCHAR)
|   +- category (VARCHAR)
|   +- sentiment (VARCHAR)
|   +- tags (TEXT[])
\\\

---

## API Architecture

### REST Endpoints (FastAPI)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /investigations | Create new investigation |
| GET | /investigations/{id} | Get investigation by ID |
| GET | /investigations | List investigations (paginated, filterable) |
| GET | /metrics | Get current metric values |
| GET | /metrics/{metric_name}/history | Get metric time series |
| GET | /anomalies | List detected anomalies |
| GET | /anomalies/{id} | Get anomaly details |
| POST | /feedback/search | Semantic search over feedback |
| POST | /sql/query | Execute validated read-only SQL (authenticated) |
| GET | /experiments | List experiments |
| GET | /experiments/{id} | Get experiment details |
| POST | /experiments/analyze | Trigger experiment analysis |
| GET | /health | Health check |
| GET | /ready | Readiness check |

### Request/Response Models

All endpoints use Pydantic models for validation:
- \InvestigationRequest\, \InvestigationResponse\, \InvestigationSummary\
- \MetricResponse\, \MetricHistoryResponse\
- \AnomalyResponse\, \AnomalyDetailResponse\
- \FeedbackSearchRequest\, \FeedbackSearchResponse\
- \SQLQueryRequest\, \SQLQueryResponse\
- \ExperimentResponse\, \ExperimentAnalysisRequest\, \ExperimentAnalysisResponse\
- \ErrorResponse\ (standardized error format)

### Authentication & Authorization

- API key authentication for \/sql/query\ endpoint
- Read-only database role for SQL execution
- Rate limiting on all endpoints
- Request ID propagation for tracing
---

## RAG Pipeline

\\\
+------------+    +------------+    +------------+    +------------+
|   SOURCES  |--> |  CLEANING  |--> |  CHUNKING  |--> |  EMBEDDING |
+------------+    +------------+    +------------+    +-----+------+
                                                              |
                                               +--------------+
                                               v
+---------------------------------------------------------------------------+
|                          VECTOR DATABASE (pgvector / Qdrant)               |
|  * Collection: product_feedback                                            |
|  * Embedding model: text-embedding-3-small (1536 dim)                      |
|  * Chunk size: 512 tokens, overlap: 50 tokens                              |
|  * Metadata filtering support                                              |
+---------------------------------------------------------------------------+
                                               |
                                               v
+---------------------------------------------------------------------------+
|                           RETRIEVER (Feedback Agent)                        |
|  * Hybrid search: vector + keyword (BM25)                                  |
|  * Top-k: 10, rerank: cross-encoder                                        |
|  * Metadata filters: source, product_area, date_range, sentiment           |
|  * Citation extraction for agent responses                                 |
+---------------------------------------------------------------------------+
\\\

### Document Processing

1. **Cleaning**: Remove PII, normalize whitespace, handle encoding
2. **Chunking**: Semantic chunking with overlap (512 tokens, 50 overlap)
3. **Embedding**: OpenAI text-embedding-3-small (configurable)
4. **Storage**: pgvector in PostgreSQL or Qdrant (configurable)
5. **Retrieval**: Hybrid search with metadata filtering

---

## Evaluation Architecture

\\\
+---------------------------------------------------------------------------+
|                           EVALUATION FRAMEWORK                              |
+---------------------------------------------------------------------------+
|                                                                             |
|  +--------------+  +--------------+  +--------------+                      |
|  |  SQL EVAL    |  |  RAG EVAL    |  |  AGENT EVAL  |                      |
|  |              |  |              |  |              |                      |
|  | * Execution  |  | * Retrieval  |  | * Tool select|                      |
|  |   success    |  |   relevance  |  | * Task compl.|                      |
|  | * Correctness|  | * Context    |  | * Root cause |                      |
|  | * Schema     |  |   precision  |  |   accuracy   |                      |
|  |   grounding  |  | * Context    |  | * Decision   |                      |
|  | * Read-only  |  |   recall     |  |   quality    |                      |
|  |   safety     |  | * Faithfulnes|  | * Hallucinatn|                      |
|  +--------------+  +--------------+  +--------------+                      |
|                                                                             |
|  +------------------------------------------------------------------------+ |
|  |                    END-TO-END INVESTIGATION EVAL                    | |
|  |  * Planted scenario detection (Scenario A, B, C)                   | |
|  |  * Ground truth comparison                                         | |
|  |  * Full pipeline accuracy                                          | |
|  +------------------------------------------------------------------------+ |
|                                                                             |
|  Dataset: evaluation/datasets/                                             |
|  +- sql_queries.jsonl          (question, expected_sql, expected_result)  |
|  +- rag_queries.jsonl          (query, relevant_docs, irrelevant_docs)   |
|  +- agent_scenarios.jsonl      (scenario, expected_root_cause, evidence)  |
|  +- planted_scenarios.json     (scenario_id, description, ground_truth)   |
|                                                                             |
+---------------------------------------------------------------------------+
\\\

---

## Observability Architecture

\\\
+---------------------------------------------------------------------------+
|                         OBSERVABILITY STACK                                 |
+---------------------------------------------------------------------------+
|                                                                             |
|  APPLICATION                                                                 |
|  +- Structured Logging (JSON)                                              |
|  |  +- request_id, trace_id, span_id                                       |
|  |  +- agent_name, step_name                                               |
|  |  +- latency_ms, token_usage                                             |
|  |  +- error_type, error_message                                           |
|  |                                                                         |
|  +- Metrics (Prometheus)                                                   |
|  |  +- http_requests_total, http_request_duration_seconds                 |
|  |  +- agent_execution_duration_seconds                                    |
|  |  +- llm_latency_seconds, llm_tokens_total                              |
|  |  +- sql_execution_duration_seconds, sql_rows_returned                  |
|  |  +- investigation_total, investigation_duration_seconds                |
|  |  +- anomaly_detected_total                                             |
|  |  +- rag_retrieval_duration_seconds, rag_results_count                 |
|  |                                                                         |
|  +- Traces (OpenTelemetry)                                                 |
|     +- HTTP request spans                                                  |
|     +- Agent workflow spans (orchestrator -> sub-agents)                   |
|     +- Tool call spans (SQL, RAG, Experiment)                             |
|     +- LLM call spans                                                     |
|                                                                             |
|  INFRASTRUCTURE                                                              |
|  +- PostgreSQL: pg_stat_statements, connection pool metrics               |
|  +- Redis: hit/miss ratio, memory, connected clients                      |
|  +- Vector DB: query latency, index size                                   |
|  +- Container: CPU, memory, network, disk                                 |
|                                                                             |
|  VISUALIZATION                                                               |
|  +- Grafana Dashboards:                                                    |
|  |  +- Product Health Overview                                             |
|  |  +- Agent Performance                                                   |
|  |  +- Investigation Pipeline                                              |
|  |  +- SQL Execution                                                       |
|  |  +- RAG Performance                                                     |
|  +- Alerting:                                                              |
|     +- Investigation failure rate > 5%                                     |
|     +- SQL execution timeout > 30s                                         |
|     +- Anomaly detection stalled                                           |
|     +- LLM error rate > 10%                                                |
|                                                                             |
+---------------------------------------------------------------------------+
\\\

---

## Security Boundaries

\\\
+---------------------------------------------------------------------------+
|                         SECURITY ARCHITECTURE                               |
+---------------------------------------------------------------------------+
|                                                                             |
|  NETWORK                                                                    |
|  +- API: Public (with API key auth)                                        |
|  +- PostgreSQL: Internal only (no public exposure)                         |
|  +- Redis: Internal only                                                   |
|  +- Vector DB: Internal only                                               |
|  +- Grafana/Prometheus: Internal or VPN                                    |
|                                                                             |
|  DATABASE ACCESS                                                            |
|  +- Application: Read-write (migrations, seeds, app data)                 |
|  +- SQL Agent: Read-only role (SELECT only, no DDL/DML)                   |
|  +- Row-level security for multi-tenancy (future)                          |
|  +- Query timeout: 30 seconds                                              |
|                                                                             |
|  SECRETS MANAGEMENT                                                         |
|  +- All secrets via environment variables                                  |
|  +- .env.example provided (no real secrets)                                |
|  +- Docker secrets for production                                          |
|  +- No secrets in code, logs, or config files                              |
|                                                                             |
|  INPUT VALIDATION                                                           |
|  +- Pydantic models for all API inputs                                     |
|  +- SQL validation: AST parsing, allowlist of tables/columns              |
|  +- Query complexity limits (joins, subqueries, recursion)                |
|  +- Output sanitization (no PII in logs)                                   |
|                                                                             |
|  AUDIT LOGGING                                                              |
|  +- All SQL executions logged (query, user, timestamp, rows)              |
|  +- Investigation access logged                                            |
|  +- Admin actions logged                                                   |
|                                                                             |
+---------------------------------------------------------------------------+
\\\

---

## Deployment Architecture

\\\
+---------------------------------------------------------------------------+
|                         DOCKER COMPOSE (LOCAL)                              |
+---------------------------------------------------------------------------+
|                                                                             |
|  services:                                                                  |
|  +- postgres:15                                                             |
|  |  +- Port: 5432                                                          |
|  |  +- Volumes: pgdata, init-scripts                                       |
|  |  +- Healthcheck: pg_isready                                             |
|  |                                                                         |
|  +- redis:7-alpine                                                          |
|  |  +- Port: 6379                                                          |
|  |  +- Healthcheck: redis-cli ping                                         |
|  |                                                                         |
|  +- qdrant:latest (or pgvector in postgres)                                |
|  |  +- Port: 6333                                                          |
|  |  +- Volumes: qdrant_data                                                |
|  |                                                                         |
|  +- api:                                                                    |
|  |  +- Build: Dockerfile.api                                               |
|  |  +- Port: 8000                                                          |
|  |  +- Depends: postgres, redis, qdrant                                    |
|  |  +- Env: DATABASE_URL, REDIS_URL, QDRANT_URL, OPENAI_API_KEY          |
|  |  +- Healthcheck: /health                                                |
|  |                                                                         |
|  +- worker (optional):                                                      |
|  |  +- Build: Dockerfile.worker                                           |
|  |  +- Depends: postgres, redis, qdrant                                    |
|  |  +- For background investigation processing                             |
|  |                                                                         |
|  +- prometheus:                                                             |
|  |  +- Port: 9090                                                          |
|  |  +- Config: prometheus.yml                                              |
|  |                                                                         |
|  +- grafana:                                                                |
|  |  +- Port: 3000                                                          |
|  |  +- Volumes: grafana_data, dashboards                                   |
|  |  +- Depends: prometheus                                                 |
|  |                                                                         |
|  +- frontend (optional):                                                    |
|     +- Build: Dockerfile.frontend                                          |
|     +- Port: 3000 (or 80 via nginx)                                        |
|     +- Depends: api                                                        |
|                                                                             |
+---------------------------------------------------------------------------+
\\\

---

## Major Design Decisions

| Decision | Rationale | Trade-off |
|----------|-----------|-----------|
| LangGraph for orchestration | Explicit state machines, built-in retry/checkpoint, visual debugging | Learning curve, less flexible than raw Python |
| PostgreSQL + pgvector | Single database for relational + vector, ACID, mature ecosystem | Vector performance < dedicated vector DB at scale |
| Read-only SQL role | Security by design, prevents accidental data modification | Requires separate connection pool |
| Deterministic statistics (SciPy) | Reproducible, auditable, no LLM hallucination on math | Less flexible than LLM reasoning for novel tests |
| RICE + extensions for prioritization | Industry standard, transparent, quantitative | May not capture all strategic nuances |
| Structured Pydantic state | Type safety, validation, serialization, IDE support | More boilerplate than dicts |
| OpenTelemetry + Prometheus | Vendor-neutral, industry standard, rich ecosystem | More setup than proprietary solutions |
| Phased implementation | Reduces risk, enables early validation, manageable scope | Longer time to full system |

---

## Trade-offs

### Chosen Approach vs. Alternatives

1. **Single PostgreSQL vs. Polyglot Persistence**
   - Chosen: PostgreSQL for both relational and vector (pgvector)
   - Alternative: PostgreSQL + Qdrant/Weaviate/Pinecone
   - Trade-off: Simplicity vs. vector search performance at scale

2. **LangGraph vs. Custom Orchestration**
   - Chosen: LangGraph (explicit state graph)
   - Alternative: Custom async state machine, Temporal, Airflow
   - Trade-off: Framework constraints vs. full control

3. **Sync vs. Async API**
   - Chosen: FastAPI (async) with sync database driver (psycopg2) in thread pool
   - Alternative: Fully async (asyncpg), fully sync
   - Trade-off: Simplicity of sync SQL drivers vs. full async throughput

4. **LLM Provider**
   - Chosen: OpenAI API (configurable via interface)
   - Alternative: Local models (Ollama, vLLM), Anthropic, Azure OpenAI
   - Trade-off: Cost/latency vs. data privacy vs. capability

5. **Evaluation: Automated vs. Human**
   - Chosen: Automated metrics + human review for final validation
   - Alternative: Pure automated, pure human
   - Trade-off: Scale vs. nuance in root cause quality assessment

---

## Repository Structure

\\\
product-intelligence/
+- agents/
|   +- __init__.py
|   +- base.py                 # Base agent classes, state definitions
|   +- orchestrator/
|   |   +- __init__.py
|   |   +- agent.py            # Orchestrator agent implementation
|   |   +- graph.py            # LangGraph workflow definition
|   |   +- state.py            # InvestigationState Pydantic model
|   |   +- steps.py            # Investigation step definitions
|   +- sql_agent/
|   |   +- __init__.py
|   |   +- agent.py            # SQL agent implementation
|   |   +- tools.py            # SQL tools (schema, generate, validate, execute)
|   |   +- validator.py        # SQL parsing and safety validation
|   |   +- prompts.py          # SQL agent prompts
|   +- feedback_agent/
|   |   +- __init__.py
|   |   +- agent.py            # Feedback agent implementation
|   |   +- rag.py              # RAG pipeline (ingest, retrieve, rerank)
|   |   +- clustering.py       # Feedback clustering
|   |   +- prompts.py
|   +- experiment_agent/
|   |   +- __init__.py
|   |   +- agent.py            # Experiment agent implementation
|   |   +- statistics.py       # Deterministic statistical tests
|   |   +- analyzer.py         # Experiment analysis logic
|   |   +- prompts.py
|   +- root_cause_agent/
|   |   +- __init__.py
|   |   +- agent.py
|   |   +- synthesizer.py      # Evidence synthesis
|   |   +- classifier.py       # FACT/INFERENCE/HYPOTHESIS classification
|   |   +- prompts.py
|   +- decision_agent/
|       +- __init__.py
|       +- agent.py
|       +- rice.py             # RICE scoring implementation
|       +- prompts.py
+- analytics/
|   +- __init__.py
|   +- metrics/
|   |   +- __init__.py
|   |   +- definitions.py      # Metric definitions (formula, SQL, params)
|   |   +- calculator.py       # Metric computation engine
|   |   +- registry.py         # Metric registry
|   +- cohorts/
|   |   +- __init__.py
|   |   +- analyzer.py         # Cohort analysis
|   +- funnels/
|   |   +- __init__.py
|   |   +- analyzer.py         # Funnel analysis
|   +- retention/
|   |   +- __init__.py
|   |   +- calculator.py       # Retention calculations
|   +- anomaly/
|       +- __init__.py
|       +- detector.py         # Anomaly detection algorithms
|       +- models.py           # Anomaly data models
+- db/
|   +- __init__.py
|   +- connection.py           # Database connection management
|   +- schema/
|   |   +- __init__.py
|   |   +- models.py           # SQLAlchemy models
|   |   +- ddl.sql             # Raw DDL for reference
|   +- migrations/
|   |   +- __init__.py
|   |   +- env.py              # Alembic environment
|   |   +- versions/           # Migration files
|   +- seeds/
|       +- __init__.py
|       +- generate.py         # Synthetic data generation
|       +- scenarios.py        # Planted anomaly scenarios
|       +- fixtures/           # Static seed data
+- api/
|   +- __init__.py
|   +- main.py                 # FastAPI app factory
|   +- routes/
|   |   +- __init__.py
|   |   +- investigations.py
|   |   +- metrics.py
|   |   +- anomalies.py
|   |   +- feedback.py
|   |   +- sql.py
|   |   +- experiments.py
|   |   +- health.py
|   +- models/
|   |   +- __init__.py
|   |   +- requests.py
|   |   +- responses.py
|   |   +- errors.py
|   +- dependencies.py         # FastAPI dependencies (DB, auth, etc.)
|   +- middleware.py           # Request ID, logging, error handling
+- evaluation/
|   +- __init__.py
|   +- datasets/
|   |   +- sql_queries.jsonl
|   |   +- rag_queries.jsonl
|   |   +- agent_scenarios.jsonl
|   |   +- planted_scenarios.json
|   +- sql_eval/
|   |   +- __init__.py
|   |   +- runner.py
|   |   +- metrics.py
|   +- rag_eval/
|   |   +- __init__.py
|   |   +- runner.py
|   |   +- metrics.py
|   +- agent_eval/
|   |   +- __init__.py
|   |   +- runner.py
|   |   +- metrics.py
|   +- e2e_eval/
|       +- __init__.py
|       +- runner.py
|       +- scenarios.py
+- observability/
|   +- __init__.py
|   +- logging.py              # Structured logging setup
|   +- metrics.py              # Prometheus metrics definitions
|   +- tracing.py              # OpenTelemetry setup
|   +- middleware.py           # FastAPI observability middleware
+- tests/
|   +- __init__.py
|   +- conftest.py             # Pytest fixtures
|   +- unit/
|   |   +- test_metrics.py
|   |   +- test_anomaly.py
|   |   +- test_sql_validator.py
|   |   +- test_rice.py
|   |   +- test_statistics.py
|   +- integration/
|   |   +- test_db.py
|   |   +- test_api.py
|   |   +- test_rag.py
|   |   +- test_agents.py
|   +- agent_workflows/
|   |   +- test_orchestrator.py
|   |   +- test_sql_agent.py
|   |   +- test_e2e_investigation.py
|   +- fixtures/
|       +- sample_data.py
+- docker/
|   +- Dockerfile.api
|   +- Dockerfile.worker
|   +- Dockerfile.frontend
|   +- docker-compose.yml
+- docs/
|   +- ARCHITECTURE.md
|   +- IMPLEMENTATION_PLAN.md
|   +- METRICS.md
|   +- EXPERIMENTATION.md
|   +- OBSERVABILITY.md
|   +- SECURITY.md
|   +- EVALUATION.md
|   +- API.md
+- scripts/
|   +- init_db.py
|   +- generate_data.py
|   +- run_evaluation.py
|   +- seed_scenarios.py
+- config/
|   +- __init__.py
|   +- settings.py             # Pydantic Settings (env config)
|   +- prompts/                # Centralized prompt templates
|       +- sql_agent.yaml
|       +- feedback_agent.yaml
|       +- experiment_agent.yaml
|       +- root_cause_agent.yaml
|       +- decision_agent.yaml
+- .env.example
+- .gitignore
+- pyproject.toml
+- README.md
+- Makefile
\\\

---

## Configuration Management

All configuration via Pydantic Settings (\config/settings.py\):

\\\python
class Settings(BaseSettings):
    # Database
    database_url: str
    database_pool_size: int = 10
    database_max_overflow: int = 20
    
    # Redis
    redis_url: str
    
    # Vector DB
    vector_db_url: str
    vector_db_type: str = "pgvector"  # or "qdrant"
    
    # LLM
    llm_provider: str = "openai"
    llm_model: str = "gpt-4o"
    llm_temperature: float = 0.1
    llm_max_tokens: int = 4096
    
    # Embeddings
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536
    
    # SQL Safety
    sql_query_timeout: int = 30
    sql_max_rows: int = 10000
    sql_allowed_schemas: list[str] = ["public"]
    
    # RAG
    rag_chunk_size: int = 512
    rag_chunk_overlap: int = 50
    rag_top_k: int = 10
    rag_rerank: bool = True
    
    # Observability
    otel_endpoint: str = "http://otel-collector:4317"
    prometheus_port: int = 9090
    log_level: str = "INFO"
    
    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_workers: int = 4
    rate_limit_requests: int = 100
    rate_limit_window: int = 60
    
    class Config:
        env_file = ".env"
        case_sensitive = False
\\\

---

## Key Interfaces

### InvestigationState (Pydantic)

\\\python
class InvestigationState(BaseModel):
    investigation_id: UUID
    question: str
    trigger: Literal["manual", "anomaly", "scheduled"]
    status: Literal["pending", "in_progress", "completed", "failed"]
    created_at: datetime
    updated_at: datetime
    
    # Metrics & Anomaly
    metrics: dict[str, MetricValue] = {}
    anomaly: Anomaly | None = None
    
    # Hypotheses
    hypotheses: list[Hypothesis] = []
    
    # SQL Investigation
    sql_queries: list[SQLQuery] = []
    sql_results: list[SQLResult] = []
    
    # Feedback Evidence
    feedback_evidence: list[FeedbackEvidence] = []
    feedback_clusters: list[FeedbackCluster] = []
    
    # Experiment Results
    experiment_results: list[ExperimentResult] = []
    
    # Root Cause
    root_causes: list[RootCause] = []
    
    # Recommendations
    recommendations: list[Recommendation] = []
    
    # Meta
    confidence: float = 0.0
    evidence: list[Evidence] = []
    errors: list[InvestigationError] = []
    execution_trace: list[ExecutionStep] = []
\\\

### Evidence Classification

\\\python
class EvidenceType(str, Enum):
    FACT = "fact"           # Directly observed, verifiable
    INFERENCE = "inference" # Logical deduction from facts
    HYPOTHESIS = "hypothesis" # Unverified explanation

class Evidence(BaseModel):
    id: UUID
    type: EvidenceType
    source: Literal["sql", "feedback", "experiment", "metric"]
    content: str
    confidence: float
    citation: str | None = None  # SQL query ID, feedback doc ID, experiment ID
    metadata: dict = {}
\\\

---

## Technology Stack Summary

| Layer | Technology | Version |
|-------|------------|---------|
| Language | Python | 3.11+ |
| Web Framework | FastAPI | 0.110+ |
| Database | PostgreSQL | 15+ |
| ORM | SQLAlchemy | 2.0+ |
| Migrations | Alembic | 1.13+ |
| Vector DB | pgvector / Qdrant | Latest |
| Caching | Redis | 7+ |
| Agent Framework | LangGraph | 0.2+ |
| LLM | OpenAI API | GPT-4o |
| Embeddings | OpenAI | text-embedding-3-small |
| Statistics | SciPy, statsmodels | Latest |
| Testing | pytest | 8+ |
| Linting | ruff | 0.5+ |
| Type Checking | mypy | 1.10+ |
| Observability | OpenTelemetry, Prometheus, Grafana | Latest |
| Containerization | Docker, Docker Compose | Latest |
| CI/CD | GitHub Actions | Latest |
