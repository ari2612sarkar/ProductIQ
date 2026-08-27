# Implementation Plan

## Overview

This document outlines the phased implementation plan for the Autonomous Product Intelligence & Decision Engine. The plan follows 15 phases as specified in the README, with each phase building upon the previous one. Each phase includes deliverables, acceptance criteria, and estimated effort.

---

## Phase 1: Repository + Configuration + Database (Week 1)

### Objectives
- Initialize repository structure
- Set up configuration management
- Configure PostgreSQL with schema
- Set up development tooling

### Deliverables

#### 1.1 Repository Structure
- Create directory structure per ARCHITECTURE.md
- Initialize git repository with .gitignore
- Create pyproject.toml with dependencies
- Create Makefile for common commands

#### 1.2 Configuration Management
- Implement config/settings.py with Pydantic Settings
- Create .env.example with all required variables
- Set up logging configuration
- Configure pytest, ruff, mypy

#### 1.3 Database Setup
- Implement db/connection.py with connection pooling
- Create SQLAlchemy models in db/schema/models.py
- Write initial migration (Alembic)
- Create raw DDL reference in db/schema/ddl.sql

#### 1.4 Development Tooling
- Dockerfile.api for API service
- docker-compose.yml with postgres, redis, qdrant
- GitHub Actions workflow for CI (lint, typecheck, test)
- Pre-commit hooks configuration

### Acceptance Criteria
- [ ] make install installs all dependencies
- [ ] make lint passes (ruff, mypy)
- [ ] make test runs (even if no tests yet)
- [ ] docker compose up -d starts postgres, redis, qdrant
- [ ] Database migrations run successfully
- [ ] Health check endpoint returns 200

### Dependencies
- Python 3.11+
- PostgreSQL 15+
- Redis 7+
- Qdrant (or pgvector)

### Estimated Effort: 5 days

---

## Phase 2: Synthetic Product Data (Week 1-2)

### Objectives
- Generate realistic synthetic dataset
- Plant known anomaly scenarios for evaluation
- Create data generation scripts

### Deliverables

#### 2.1 Data Generation Framework
- Implement db/seeds/generate.py with Faker and custom logic
- Create configurable data generation parameters
- Support deterministic seeding for reproducibility

#### 2.2 Core Entities Generation
- Users: 50,000+ with segments, plans, acquisition channels
- Sessions: 500,000+ with realistic duration, device, geography
- Events: 2,000,000+ with event names, properties, timestamps
- Subscriptions: 30,000+ with lifecycle states
- Payments: 100,000+ with amounts, currencies, statuses

#### 2.3 Experiment & Feedback Data
- Experiments: 10+ with control/treatment variants
- Experiment assignments: 20,000+ with proper randomization
- Support tickets: 5,000+ with categories, priorities, resolutions
- Product feedback: 10,000+ with NPS, reviews, feature requests

#### 2.4 Planted Scenarios (Documented in db/seeds/scenarios.py)
- **Scenario A**: Onboarding V3 experiment causes activation decline (free users, -15% activation)
- **Scenario B**: Enterprise segment experiences increased churn (+8% churn rate, payment failures)
- **Scenario C**: Feature X has high adoption (60%) but low retention correlation (users who adopt churn faster)
- **Scenario D**: Mobile app crash spike affects DAU (-12% DAU on Android)
- **Scenario E**: Pricing page experiment reduces conversion (-5% conversion, treatment group)

#### 2.5 Ground Truth Documentation
- Create evaluation/datasets/planted_scenarios.json with:
  - Scenario ID, description, affected metrics
  - Root cause, confidence, evidence types
  - Expected investigation steps

### Acceptance Criteria
- [ ] make generate-data produces complete dataset in < 5 minutes
- [ ] Data passes foreign key constraints
- [ ] Planted scenarios are verifiable via SQL queries
- [ ] Dataset size supports meaningful analytics (query latency < 2s)
- [ ] Ground truth documented for all 5 scenarios

### Dependencies
- Phase 1 complete
- Faker, numpy, pandas for data generation

### Estimated Effort: 5 days

---

## Phase 3: Analytics and Metrics (Week 2)

### Objectives
- Implement metric definitions and calculations
- Create metric registry
- Build cohort and funnel analyzers
- Document all metrics

### Deliverables

#### 3.1 Metric Definitions (analytics/metrics/definitions.py)
Each metric includes:
- Name, description, formula
- Required tables, time window
- Edge cases, SQL implementation
- Unit tests with known outputs

**Metrics to Implement:**
1. **DAU** - Daily Active Users (distinct users with events in 24h)
2. **WAU** - Weekly Active Users (distinct users with events in 7d)
3. **MAU** - Monthly Active Users (distinct users with events in 30d)
3. **Activation Rate** - Users completing onboarding / Signups
4. **Conversion Rate** - Trial to paid / Free to trial
5. **Retention** - N-day retention (D1, D7, D30) by cohort
6. **Churn Rate** - Cancelled subscriptions / Active subscriptions
7. **ARPU** - Total revenue / Active users
8. **Revenue** - MRR, ARR, total revenue
9. **Feature Adoption** - Users using feature / Eligible users

#### 3.2 Metric Calculator (analytics/metrics/calculator.py)
- Time-windowed metric computation
- Materialized view generation for dashboards
- Incremental computation support
- Caching with Redis

#### 3.3 Metric Registry (analytics/metrics/registry.py)
- Central metric catalog
- Version tracking for metric definitions
- API for listing/describing metrics

#### 3.4 Cohort Analyzer (analytics/cohorts/analyzer.py)
- Cohort definition (signup date, plan, channel)
- Retention curves by cohort
- Cohort comparison utilities

#### 3.5 Funnel Analyzer (analytics/funnels/analyzer.py)
- Multi-step funnel definition
- Conversion rates per step
- Drop-off analysis
- Segment comparison

#### 3.6 Documentation
- Create docs/METRICS.md with all metric definitions

### Acceptance Criteria
- [ ] All 9 metrics calculate correctly against synthetic data
- [ ] Metric values match manual SQL verification
- [ ] Cohort analysis produces valid retention curves
- [ ] Funnel analysis shows expected drop-offs
- [ ] docs/METRICS.md complete and accurate
- [ ] Unit tests cover all metrics with known outputs

### Dependencies
- Phase 2 complete (data available)
- SQLAlchemy, pandas for computation

### Estimated Effort: 5 days

---

## Phase 4: Anomaly Detection (Week 2-3)

### Objectives
- Implement deterministic anomaly detection
- Support multiple detection methods
- Create anomaly models and API endpoints

### Deliverables

#### 4.1 Anomaly Models (analytics/anomaly/models.py)
- Anomaly data class with:
  - metric_name, baseline, current_value
  - absolute_change, relative_change
  - detection_method, severity, confidence
  - timestamp, metadata

#### 4.2 Detection Algorithms (analytics/anomaly/detector.py)
- **Rolling Statistics**: Mean/std over trailing window, flag > 2σ
- **Z-Score**: Current vs. historical mean/std, threshold 2.5
- **Percentage Change**: Week-over-week, month-over-month, threshold configurable
- **Baseline Comparison**: Compare to same period previous year
- **Threshold-Based**: Absolute thresholds per metric

#### 4.3 Detection Pipeline
- Scheduled detection runs (cron or background worker)
- Metric-specific configuration (window, threshold, method)
- Anomaly deduplication (don't re-alert on same anomaly)
- Severity scoring (critical, high, medium, low)

#### 4.4 API Endpoints
- GET /anomalies - List with filters (metric, severity, date range)
- GET /anomalies/{id} - Anomaly details with context

### Acceptance Criteria
- [ ] All 5 detection methods implemented and tested
- [ ] Detects planted Scenario A (retention drop) automatically
- [ ] Detects planted Scenario B (churn increase) automatically
- [ ] Detects planted Scenario D (DAU drop) automatically
- [ ] No false positives on stable metrics
- [ ] API returns anomalies with full context

### Dependencies
- Phase 3 complete (metrics available)
- NumPy, SciPy for statistics

### Estimated Effort: 4 days

---

## Phase 5: SQL Investigation Agent (Week 3-4)

### Objectives
- Build SQL agent with schema introspection
- Implement SQL generation, validation, execution
- Support multi-step investigations

### Deliverables

#### 5.1 SQL Validator (agents/sql_agent/validator.py)
- SQL parsing with sqlglot or sqlparse
- Read-only enforcement (no INSERT/UPDATE/DELETE/DDL)
- Table/column allowlist validation
- Query complexity limits (max joins, subqueries, recursion depth)
- Query timeout enforcement (30s)
- Row limit enforcement (10,000)

#### 5.2 Schema Introspection
- get_schema tool: Retrieve relevant tables for question
- Table descriptions, column types, foreign keys
- Sample values for categorical columns

#### 5.3 SQL Generation (agents/sql_agent/tools.py)
- generate_sql tool: Natural language → SQL
- Few-shot prompting with schema context
- Support for CTEs, window functions, joins, aggregations

#### 5.4 SQL Execution
- execute_sql tool: Read-only connection pool
- Parameterized queries only
- Result validation (row count, column types)
- Error handling with retry logic

#### 5.5 SQL Agent (agents/sql_agent/agent.py)
- LangGraph node with state management
- Multi-step investigation loop
- Result interpretation → next question generation
- Termination conditions (max steps, confidence threshold)

#### 5.6 Prompts
- Centralized in config/prompts/sql_agent.yaml
- Version-controlled prompt templates

### Acceptance Criteria
- [ ] SQL validator blocks all write operations
- [ ] SQL validator blocks dangerous functions (pg_sleep, etc.)
- [ ] Agent answers "Why did retention fall?" with multi-step queries
- [ ] Agent segments by plan, channel, cohort correctly
- [ ] Execution time < 30s per query
- [ ] Results interpreted into natural language conclusions
- [ ] Unit tests for validator with malicious SQL attempts

### Dependencies
- Phase 1-2 complete (database, schema, data)
- LangGraph, sqlglot, OpenAI API

### Estimated Effort: 7 days

---

## Phase 6: RAG Feedback System (Week 4)

### Objectives
- Build feedback ingestion pipeline
- Implement vector search and retrieval
- Create feedback clustering and theme extraction

### Deliverables

#### 6.1 Document Processing (agents/feedback_agent/rag.py)
- Cleaning: PII removal, normalization
- Chunking: Semantic chunks (512 tokens, 50 overlap)
- Embedding: OpenAI text-embedding-3-small
- Storage: pgvector or Qdrant

#### 6.2 Retrieval
- Hybrid search: Vector + BM25 keyword
- Metadata filtering (source, area, date, sentiment)
- Cross-encoder reranking (optional)
- Citation extraction for agent responses

#### 6.3 Clustering (agents/feedback_agent/clustering.py)
- Semantic clustering of retrieved feedback
- Theme extraction with representative quotes
- Cluster labeling with LLM

#### 6.4 Feedback Agent (agents/feedback_agent/agent.py)
- search_feedback tool: Query → relevant chunks
- cluster_feedback tool: Chunks → themes
- extract_themes tool: Themes → structured evidence

#### 6.5 Ingestion Pipeline
- Batch ingestion script for initial load
- Incremental ingestion for new feedback
- Embedding cache to avoid recomputation

### Acceptance Criteria
- [ ] Ingests 10,000+ feedback items in < 10 minutes
- [ ] Retrieval finds relevant feedback for planted scenarios
- [ ] Clustering groups related complaints (Scenario A: onboarding issues)
- [ ] Agent cites specific feedback documents in responses
- [ ] Hybrid search outperforms vector-only on keyword queries
- [ ] RAG evaluation metrics: relevance > 0.7, faithfulness > 0.8

### Dependencies
- Phase 2 complete (feedback data)
- Phase 1 complete (vector DB)
- OpenAI embeddings, pgvector/Qdrant

### Estimated Effort: 5 days

---

## Phase 7: Experiment Analysis (Week 4-5)

### Objectives
- Implement deterministic experiment analysis
- Support multiple metric types and statistical tests
- Create experiment agent

### Deliverables

#### 7.1 Statistical Tests (agents/experiment_agent/statistics.py)
- **Proportion tests**: Conversion, activation, retention (chi-square, z-test)
- **Mean tests**: Revenue, session duration (t-test, Mann-Whitney)
- **Ratio metrics**: ARPU, revenue per user (delta method)
- **Effect size**: Cohen's d, relative risk, odds ratio
- **Confidence intervals**: Bootstrap, analytical
- **Multiple comparison correction**: Bonferroni, Benjamini-Hochberg

#### 7.2 Experiment Analyzer (agents/experiment_agent/analyzer.py)
- Load experiment assignments + outcomes
- Compute metrics per variant
- Run appropriate statistical tests
- Generate structured results with interpretations

#### 7.3 Experiment Agent (agents/experiment_agent/agent.py)
- get_experiment_data tool
- calculate_statistics tool
- interpret_results tool
- Identify relevant experiments for investigation question

#### 7.4 Documentation
- Create docs/EXPERIMENTATION.md with:
  - Test selection guide
  - Assumptions per test
  - Example analyses

### Acceptance Criteria
- [ ] Correctly analyzes planted Scenario A (Onboarding V3 experiment)
- [ ] Correctly analyzes planted Scenario E (Pricing experiment)
- [ ] Statistical results match manual calculation (R/Python)
- [ ] Handles edge cases: small samples, zero conversions, skewed data
- [ ] Agent provides clear interpretation with p-values, CIs, effect sizes
- [ ] No LLM-based statistical calculations

### Dependencies
- Phase 2 complete (experiment data)
- SciPy, statsmodels, numpy

### Estimated Effort: 5 days

---

## Phase 8: Root Cause Agent (Week 5)

### Objectives
- Synthesize evidence from all sources
- Implement FACT/INFERENCE/HYPOTHESIS classification
- Rank root causes with confidence

### Deliverables

#### 8.1 Evidence Synthesis (agents/root_cause_agent/synthesizer.py)
- Normalize evidence from SQL, feedback, experiments
- Cross-reference findings across sources
- Identify convergent/divergent evidence

#### 8.2 Evidence Classifier (agents/root_cause_agent/classifier.py)
- Rule-based + LLM classification
- FACT: Directly observed (SQL result, experiment p-value)
- INFERENCE: Logical deduction (retention drop → onboarding issue)
- HYPOTHESIS: Unverified explanation (competitor launched feature)

#### 8.3 Hypothesis Ranking
- Bayesian-style confidence scoring
- Evidence weighting by source reliability
- Competing hypothesis comparison

#### 8.4 Root Cause Agent (agents/root_cause_agent/agent.py)
- compare_hypotheses tool
- assign_confidence tool
- classify_evidence tool

### Acceptance Criteria
- [ ] Correctly identifies Scenario A root cause (Onboarding V3) with >0.85 confidence
- [ ] Correctly identifies Scenario B root cause (payment failures) with >0.8 confidence
- [ ] Correctly identifies Scenario D root cause (Android crashes) with >0.9 confidence
- [ ] Explicitly classifies evidence as FACT/INFERENCE/HYPOTHESIS
- [ ] Provides evidence citations for each root cause
- [ ] Handles conflicting evidence gracefully

### Dependencies
- Phase 5, 6, 7 complete (all evidence sources)
- LangGraph, OpenAI API

### Estimated Effort: 4 days

---

## Phase 9: Decision Engine (Week 5-6)

### Objectives
- Implement RICE prioritization framework
- Generate product recommendations
- Quantify business impact

### Deliverables

#### 9.1 RICE Scoring (agents/decision_agent/rice.py)
- Reach: Users affected (from SQL/data)
- Impact: Expected metric improvement (0.25-3 scale)
- Confidence: Evidence confidence (0-1)
- Effort: Engineering weeks (1-100)
- Formula: (Reach * Impact * Confidence) / Effort

#### 9.2 Extensions
- Revenue Impact: Estimated $ impact
- Strategic Alignment: 1-5 score
- Risk: Implementation risk (1-5)

#### 9.3 Recommendation Generation
- Map root causes → potential actions
- Estimate reach from data
- Estimate impact from historical analogs
- Effort estimation (engineering input or heuristics)

#### 9.4 Decision Agent (agents/decision_agent/agent.py)
- calculate_rice tool
- estimate_impact tool
- prioritize_actions tool

### Acceptance Criteria
- [ ] Generates recommendations for Scenario A (rollback onboarding V3)
- [ ] RICE scores are transparent and auditable
- [ ] Recommendations include evidence citations
- [ ] Priority ordering matches business intuition
- [ ] API returns structured recommendations with scores

### Dependencies
- Phase 8 complete (root causes)
- Phase 3 complete (metrics for reach/impact)

### Estimated Effort: 3 days

---

## Phase 10: FastAPI Backend (Week 6)

### Objectives
- Build complete REST API
- Implement all endpoints
- Add authentication, validation, error handling

### Deliverables

#### 10.1 API Routes
- investigations.py: POST/GET investigations
- metrics.py: GET metrics, history
- anomalies.py: GET anomalies
- feedback.py: POST search
- sql.py: POST query (authenticated)
- experiments.py: GET/POST experiments
- health.py: GET /health, /ready

#### 10.2 Request/Response Models (api/models/)
- Pydantic models for all endpoints
- Standardized error responses
- Pagination, filtering, sorting

#### 10.3 Middleware (api/middleware.py)
- Request ID generation/propagation
- Structured logging
- Rate limiting
- Error handling with proper HTTP codes

#### 10.4 Dependencies (api/dependencies.py)
- Database session
- Authentication (API key for /sql/query)
- Rate limiter
- Tracing context

#### 10.5 Integration
- Wire orchestrator to /investigations endpoint
- Background task support for long investigations
- WebSocket/SSE for progress updates (optional)

### Acceptance Criteria
- [ ] All 10 endpoints functional with correct responses
- [ ] Input validation rejects invalid requests (422)
- [ ] Authentication works for /sql/query
- [ ] Rate limiting enforced
- [ ] Request IDs in all logs and responses
- [ ] OpenAPI docs at /docs
- [ ] Integration test creates investigation end-to-end

### Dependencies
- Phase 1, 3, 4, 5, 6, 7, 8, 9 complete
- FastAPI, Pydantic, slowapi (rate limiting)

### Estimated Effort: 5 days

---

## Phase 11: Dashboard (Week 6-7)

### Objectives
- Build functional Product Intelligence dashboard
- Display metrics, anomalies, investigations
- Show investigation details with evidence

### Deliverables

#### 11.1 Technology Choice
- React + TypeScript + Vite
- TanStack Query for data fetching
- Recharts for visualizations
- Tailwind CSS for styling

#### 11.2 Pages/Components
- **Dashboard**: Health overview, key metrics, recent anomalies
- **Metrics**: Time-series charts, comparisons
- **Anomalies**: List with severity, drill-down
- **Investigations**: List, status, detail view
- **Investigation Detail**: Evidence tabs (SQL, Feedback, Experiment), Root Cause, Recommendations

#### 11.3 Dockerfile.frontend
- Multi-stage build
- Nginx for production serving
- API proxy configuration

### Acceptance Criteria
- [ ] Dashboard loads and displays real data
- [ ] Metric charts show time series correctly
- [ ] Anomaly list filters work
- [ ] Investigation detail shows all evidence types
- [ ] Root cause display shows FACT/INFERENCE/HYPOTHESIS
- [ ] Recommendations show RICE scores
- [ ] Responsive design works on desktop/tablet

### Dependencies
- Phase 10 complete (API)
- Node.js 20+, npm

### Estimated Effort: 5 days

---

## Phase 12: Evaluation (Week 7)

### Objectives
- Build evaluation framework
- Create evaluation datasets
- Run evaluations for all components

### Deliverables

#### 12.1 Evaluation Datasets (evaluation/datasets/)
- sql_queries.jsonl: 50+ question/SQL/result tuples
- rag_queries.jsonl: 50+ query/relevant_docs tuples
- agent_scenarios.jsonl: 20+ scenario/expected_output tuples
- planted_scenarios.json: 5 scenarios with ground truth

#### 12.2 SQL Evaluation (evaluation/sql_eval/)
- Execution success rate
- Correctness (result matches expected)
- Schema grounding (uses correct tables/columns)
- Safety (no forbidden operations)

#### 12.3 RAG Evaluation (evaluation/rag_eval/)
- Retrieval relevance (NDCG@10)
- Context precision/recall
- Faithfulness (answer supported by context)

#### 12.4 Agent Evaluation (evaluation/agent_eval/)
- Tool selection accuracy
- Task completion rate
- Root cause accuracy (vs. ground truth)
- Recommendation quality (human eval)
- Hallucination rate

#### 12.5 E2E Evaluation (evaluation/e2e_eval/)
- Full investigation on planted scenarios
- Compare output to ground truth
- Measure end-to-end latency, cost

#### 12.6 Runner Scripts
- make eval-sql, make eval-rag, make eval-agent, make eval-e2e
- CI integration for regression detection

### Acceptance Criteria
- [ ] All evaluation datasets created with ground truth
- [ ] SQL evaluation runs and reports metrics
- [ ] RAG evaluation runs and reports metrics
- [ ] Agent evaluation runs on all planted scenarios
- [ ] E2E evaluation detects all 5 planted scenarios
- [ ] Results documented in evaluation/results/

### Dependencies
- All previous phases complete
- pytest, custom evaluation scripts

### Estimated Effort: 5 days

---

## Phase 13: Observability (Week 7-8)

### Objectives
- Implement structured logging
- Add Prometheus metrics
- Set up OpenTelemetry tracing
- Create Grafana dashboards

### Deliverables

#### 13.1 Structured Logging (observability/logging.py)
- JSON formatter with standard fields
- Request/response logging
- Agent step logging
- Error logging with context
- PII redaction

#### 13.2 Prometheus Metrics (observability/metrics.py)
- HTTP metrics (requests, latency, errors)
- Agent metrics (execution time, steps, errors)
- LLM metrics (latency, tokens, cost)
- SQL metrics (execution time, rows, errors)
- Investigation metrics (total, duration, success rate)
- Anomaly metrics (detected, by severity)
- RAG metrics (retrieval time, results count)

#### 13.3 OpenTelemetry Tracing (observability/tracing.py)
- HTTP server instrumentation
- LangGraph workflow spans
- Tool call spans (SQL, RAG, Experiment)
- LLM call spans
- Export to OTLP endpoint

#### 13.4 Grafana Dashboards
- Product Health Overview
- Agent Performance
- Investigation Pipeline
- SQL Execution
- RAG Performance

#### 13.5 Alerting Rules
- Investigation failure rate > 5%
- SQL timeout > 30s
- Anomaly detection stalled
- LLM error rate > 10%

### Acceptance Criteria
- [ ] Structured logs in JSON format
- [ ] Prometheus scrapes metrics successfully
- [ ] Traces visible in Jaeger/Grafana Tempo
- [ ] All 5 dashboards render correctly
- [ ] Alerts fire on threshold breach
- [ ] No PII in logs or metrics

### Dependencies
- Phase 10 complete (API)
- Prometheus, Grafana, OpenTelemetry Collector

### Estimated Effort: 4 days

---

## Phase 14: Testing and Hardening (Week 8)

### Objectives
- Comprehensive test coverage
- Failure handling and recovery
- Security hardening

### Deliverables

#### 14.1 Unit Tests (tests/unit/)
- Metric calculations (all 9 metrics)
- Anomaly detection (all 5 methods)
- SQL validator (malicious queries, edge cases)
- RICE scoring (edge cases)
- Statistical tests (known inputs/outputs)
- Evidence classification

#### 14.2 Integration Tests (tests/integration/)
- Database operations (CRUD, migrations)
- API endpoints (all 10)
- RAG pipeline (ingest, retrieve)
- Agent workflows (mocked LLM)

#### 14.3 Agent Workflow Tests (tests/agent_workflows/)
- Orchestrator state transitions
- SQL agent multi-step investigation
- E2E investigation with planted scenarios
- Failure recovery (LLM timeout, SQL error, empty results)

#### 14.4 Security Tests
- SQL injection attempts blocked
- Read-only enforcement verified
- API input validation
- Secrets not in logs

#### 14.5 Load/Stress Tests (optional)
- Concurrent investigations
- Large query handling
- Rate limiting under load

### Acceptance Criteria
- [ ] Unit test coverage > 80% for core modules
- [ ] All integration tests pass
- [ ] Agent workflow tests pass for all 5 scenarios
- [ ] Security tests block all injection attempts
- [ ] Failure handling: graceful degradation, no crashes
- [ ] make test runs full suite in < 3 minutes

### Dependencies
- All previous phases complete
- pytest, pytest-asyncio, httpx, pytest-mock

### Estimated Effort: 5 days

---

## Phase 15: Docker + CI/CD (Week 8)

### Objectives
- Production-ready Docker configuration
- Complete CI/CD pipeline
- Documentation finalization

### Deliverables

#### 15.1 Docker Configuration
- docker-compose.yml with all services
- Dockerfile.api (multi-stage, non-root user)
- Dockerfile.worker (if separate worker)
- Dockerfile.frontend (multi-stage, nginx)
- .dockerignore
- Health checks for all services

#### 15.2 CI/CD (GitHub Actions)
- .github/workflows/ci.yml: lint, typecheck, test, build
- .github/workflows/docker.yml: build and push images
- Dependency scanning (dependabot or similar)
- Security scanning (trivy or similar)

#### 15.3 Documentation
- Update README.md with run instructions
- Verify all docs/ files match implementation
- Create API.md from OpenAPI spec
- Create SECURITY.md with security practices

#### 15.4 Final Verification
- Fresh clone → docker compose up → working app
- All acceptance criteria from phases 1-14 verified
- Evaluation runs in CI
- No secrets in repository

### Acceptance Criteria
- [ ] git clone && cp .env.example .env && docker compose up -d works
- [ ] API accessible at localhost:8000
- [ ] Frontend accessible at localhost:3000
- [ ] Grafana accessible at localhost:3000
- [ ] All CI checks pass
- [ ] No hardcoded secrets
- [ ] Documentation accurate

### Dependencies
- All previous phases complete
- Docker, GitHub Actions

### Estimated Effort: 3 days

---

## Summary Timeline

| Phase | Duration | Cumulative |
|-------|----------|------------|
| 1: Repo + Config + DB | 5 days | Week 1 |
| 2: Synthetic Data | 5 days | Week 1-2 |
| 3: Analytics & Metrics | 5 days | Week 2 |
| 4: Anomaly Detection | 4 days | Week 2-3 |
| 5: SQL Agent | 7 days | Week 3-4 |
| 6: RAG Feedback | 5 days | Week 4 |
| 7: Experiment Analysis | 5 days | Week 4-5 |
| 8: Root Cause Agent | 4 days | Week 5 |
| 9: Decision Engine | 3 days | Week 5-6 |
| 10: FastAPI Backend | 5 days | Week 6 |
| 11: Dashboard | 5 days | Week 6-7 |
| 12: Evaluation | 5 days | Week 7 |
| 13: Observability | 4 days | Week 7-8 |
| 14: Testing & Hardening | 5 days | Week 8 |
| 15: Docker + CI/CD | 3 days | Week 8 |
| **Total** | **~70 days** | **~14 weeks** |

---

## Parallelization Opportunities

Phases that can run in parallel (with different engineers):
- Phase 3 (Metrics) || Phase 4 (Anomaly) - after Phase 2
- Phase 5 (SQL Agent) || Phase 6 (RAG) - after Phase 2
- Phase 7 (Experiments) || Phase 5/6 - after Phase 2
- Phase 11 (Dashboard) || Phase 12 (Evaluation) - after Phase 10
- Phase 13 (Observability) || Phase 14 (Testing) - after Phase 10

With 2-3 engineers, timeline can be compressed to ~8-10 weeks.

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| LLM API costs/limits | Implement caching, fallback models, cost monitoring |
| SQL agent hallucination | Strict validation, few-shot prompts, schema grounding |
| RAG retrieval quality | Hybrid search, reranking, evaluation-driven tuning |
| Statistical test selection | Clear decision tree in docs, unit tests with known outputs |
| Data generation realism | Iterate with domain expert review, validate against real patterns |
| Agent loop infinite recursion | Max iteration limits, explicit termination conditions |
| Docker compose complexity | Start minimal, add services incrementally |

---

## Success Criteria (Final Acceptance)

Per README Section 31:
- [ ] Repository installs successfully
- [ ] Docker Compose starts successfully
- [ ] PostgreSQL schema works
- [ ] Synthetic data generation works
- [ ] Metrics calculate correctly
- [ ] Anomaly detection works
- [ ] SQL agent executes safely
- [ ] RAG retrieval works
- [ ] Experiment analysis works
- [ ] Root-cause workflow works
- [ ] Decision engine works
- [ ] FastAPI works
- [ ] UI works
- [ ] Tests pass
- [ ] Evaluation runs
- [ ] Observability works
- [ ] Configuration documented
- [ ] No secrets committed
- [ ] Documentation matches implementation
- [ ] At least one complete end-to-end investigation works
- [ ] At least one planted anomaly correctly discovered without hard-coded answers
