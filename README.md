# Product Intelligence Engineering Project

A backend + frontend analytics project that simulates a product data stack: ingestion, metric computation, anomaly visibility, SQL investigation utilities, feedback search, and experiment analysis.

This project is intentionally presented as an engineering portfolio project (not a production SaaS). It focuses on clear architecture, reproducible runs, and explicit tradeoffs.

## Architecture Overview

```
Product Data → Metric Engine → Anomaly Detection → Investigation Agent
                                                    ↓
                    SQL Agent ←→ Feedback Agent ←→ Experiment Agent
                                                    ↓
                                           Root Cause Agent
                                                    ↓
                                           Decision Agent
                                                    ↓
                                         Product Recommendation
```

## What This Project Demonstrates

- **Metrics pipeline**: DAU/MAU, retention, revenue snapshots from event/payment data
- **SQL safety layer**: query validation + read-only execution path
- **Feedback and experiment modules**: data ingestion and analysis endpoints
- **Deterministic experiment statistics**: proportion/mean/ratio tests using SciPy/StatsModels
- **Operational tooling**: health endpoints, Docker services, CI workflow, and scripts

## Quick Start

### Prerequisites
- Python 3.11+
- PostgreSQL 15+
- Redis 7+
- Qdrant (or pgvector)
- OpenAI API key

### Local Development

```bash
# Clone and setup
git clone <repo>
cd product-intelligence
cp .env.example .env
# Edit .env with your API keys

# Install dependencies
make install

# Start infrastructure
make docker-up

# Initialize database
make db-init

# Ingest real data (e-commerce events + Upworthy experiments)
make ingest-data

# Run API server
make dev
```

### Windows (PowerShell) Notes

If `make` is not available, run direct commands:

```powershell
pip install -e ".[dev]"
docker compose -f docker/docker-compose.yml up -d postgres redis qdrant
python scripts/init_db.py
python scripts/ingest_ecommerce_data.py --sample 100000
python scripts/derive_subscriptions.py
python scripts/derive_feedback.py
python scripts/compute_metrics.py
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000
```

### Docker Compose (Production-like)

```bash
docker compose -f docker/docker-compose.yml up -d
```

This starts:
- PostgreSQL (port 5432)
- Redis (port 6379)
- Qdrant (port 6333)
- API (port 8000)
- Prometheus (port 9090)
- Grafana (port 3000)
- OpenTelemetry Collector (port 4317)

## Data Sources

The system uses real-world datasets:

1. **E-commerce Behavior Data** (HuggingFace): 110M+ events from a multi-category store (Oct-Nov 2019)
   - Events: page_view, add_to_cart, remove_from_cart, purchase
   - Users, sessions, products, categories, brands, prices

2. **Upworthy Research Archive** (OSF): 32,487 A/B tests with 538M participant assignments
   - Headline/image package tests with impressions and clicks

Derived data:
- Subscriptions from purchase patterns
- Support tickets from user behavior signals
- Product feedback (NPS, reviews, feature requests) from engagement patterns

## Data Realism Note

- Source events and experiments come from real public datasets.
- Some entities are derived for demo usability (for example generated user identities, transformed timestamps, and synthetic joins between datasets).
- This is suitable for portfolio evaluation and systems design discussion, not for business-grade inference.

## Known Limitations

- Some workflows are still scaffolded and not fully automated end-to-end.
- Experiment quality depends on assignment sample sizes in the ingested subset.
- If no new events are ingested beyond the latest date, future daily metrics will flatten or drop.
- This repository prioritizes clarity and reproducibility over production hardening.

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/investigations` | Create new investigation |
| GET | `/investigations/{id}` | Get investigation details |
| GET | `/investigations` | List investigations |
| GET | `/metrics` | Current metric values |
| GET | `/metrics/{name}/history` | Metric time series |
| GET | `/anomalies` | List detected anomalies |
| POST | `/feedback/search` | Semantic search feedback |
| POST | `/sql/query` | Execute read-only SQL (auth) |
| GET | `/experiments` | List experiments |
| POST | `/experiments/analyze` | Analyze A/B experiment |
| GET | `/health` | Health check |

## Project Structure

```
product-intelligence/
├── agents/                 # Agent implementations
│   ├── orchestrator/       # LangGraph workflow coordinator
│   ├── sql_agent/          # SQL investigation agent
│   ├── feedback_agent/     # RAG + feedback analysis
│   ├── experiment_agent/   # Statistical experiment analysis
│   ├── root_cause_agent/   # Evidence synthesis
│   └── decision_agent/     # RICE prioritization
├── analytics/              # Metrics, cohorts, funnels, retention, anomaly
├── db/                     # Database schema, migrations, seeds
├── api/                    # FastAPI routes and models
├── evaluation/             # SQL, RAG, Agent, E2E evaluation
├── observability/          # Logging, metrics, tracing
├── tests/                  # Unit, integration, agent workflow tests
├── docker/                 # Dockerfiles and compose
├── scripts/                # Data ingestion and utilities
├── config/                 # Settings and prompts
└── docs/                   # Architecture, metrics, experimentation docs
```

## Configuration

All configuration via environment variables (see `.env.example`):

- `DATABASE_URL` - PostgreSQL connection
- `REDIS_URL` - Redis connection
- `QDRANT_URL` - Vector database
- `OPENAI_API_KEY` - LLM API key
- `VECTOR_DB_TYPE` - pgvector or qdrant

## Testing

```bash
# Run all tests
make test

# Unit tests only
make test-unit

# Integration tests
make test-integration

# Agent workflow tests
make test-agent

# With coverage
make test-coverage
```

## Evaluation

```bash
# Run all evaluations
make eval-all

# SQL evaluation
make eval-sql

# RAG evaluation
make eval-rag

# Agent evaluation
make eval-agent

# End-to-end evaluation
make eval-e2e
```

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Implementation Plan](docs/IMPLEMENTATION_PLAN.md)
- [Metrics Definitions](docs/METRICS.md)
- [Experimentation Guide](docs/EXPERIMENTATION.md)
- [Observability](docs/OBSERVABILITY.md)
- [Security](docs/SECURITY.md)
- [Evaluation](docs/EVALUATION.md)
- [API Reference](docs/API.md)
- [GitHub Go-Live Checklist](docs/GITHUB_LIVE_CHECKLIST.md)
- [Project Decisions](docs/PROJECT_DECISIONS.md)

## Security

- Read-only database role for SQL agent
- SQL validation with sqlglot (blocks DDL/DML)
- Query timeout (30s) and row limits (10k)
- API key authentication for sensitive endpoints
- PII redaction in logs
- No secrets in code or config

## License

MIT
