.PHONY: help install lint typecheck test test-unit test-integration test-coverage run dev docker-up docker-down docker-logs db-init db-migrate db-seed ingest-data clean

# Default target
help:
	@echo "Product Intelligence - Available commands:"
	@echo ""
	@echo "Development:"
	@echo "  install       - Install dependencies"
	@echo "  lint          - Run ruff linter"
	@echo "  typecheck     - Run mypy type checker"
	@echo "  test          - Run all tests"
	@echo "  test-unit     - Run unit tests only"
	@echo "  test-integration - Run integration tests only"
	@echo "  test-coverage - Run tests with coverage"
	@echo "  run           - Run API server"
	@echo "  dev           - Run API server with auto-reload"
	@echo ""
	@echo "Database:"
	@echo "  db-init       - Initialize database schema"
	@echo "  db-migrate    - Run Alembic migrations"
	@echo "  db-seed       - Seed database with initial data"
	@echo "  ingest-data   - Ingest all real datasets (e-commerce + Upworthy)"
	@echo ""
	@echo "Docker:"
	@echo "  docker-up     - Start all services with docker-compose"
	@echo "  docker-down   - Stop all services"
	@echo "  docker-logs   - View docker-compose logs"
	@echo "  docker-build  - Build docker images"
	@echo ""
	@echo "Data Ingestion:"
	@echo "  ingest-ecommerce   - Ingest e-commerce events from HuggingFace"
	@echo "  ingest-upworthy    - Ingest Upworthy A/B test experiments"
	@echo "  derive-subscriptions - Derive subscriptions from purchases"
	@echo "  derive-feedback    - Derive feedback/support tickets"
	@echo ""
	@echo "Evaluation:"
	@echo "  eval-sql      - Run SQL evaluation"
	@echo "  eval-rag      - Run RAG evaluation"
	@echo "  eval-agent    - Run agent evaluation"
	@echo "  eval-e2e      - Run end-to-end evaluation"
	@echo ""
	@echo "Maintenance:"
	@echo "  clean         - Clean build artifacts"

# Install dependencies
install:
	pip install -e ".[dev]"
	pre-commit install

# Linting
lint:
	ruff check .
	ruff format --check .

lint-fix:
	ruff check --fix .
	ruff format .

# Type checking
typecheck:
	mypy .

# Testing
test:
	pytest

test-unit:
	pytest tests/unit -v

test-integration:
	pytest tests/integration -v

test-agent:
	pytest tests/agent_workflows -v

test-coverage:
	pytest --cov=agents --cov=analytics --cov=api --cov=db --cov=config --cov-report=term-missing --cov-report=html

# Run API server
run:
	uvicorn api.main:app --host 0.0.0.0 --port 8000 --workers 4

dev:
	uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

# Database
db-init:
	python scripts/init_db.py

db-migrate:
	alembic upgrade head

db-migrate-create:
	alembic revision --autogenerate -m "$(MSG)"

db-seed:
	python scripts/seed_data.py

# Data Ingestion
ingest-data:
	python scripts/ingest_all.py --sample 100000

ingest-ecommerce:
	python scripts/ingest_ecommerce_data.py --sample 100000

ingest-upworthy:
	python scripts/ingest_upworthy_data.py

derive-subscriptions:
	python scripts/derive_subscriptions.py

derive-feedback:
	python scripts/derive_feedback.py

refresh-mviews:
	python scripts/refresh_mviews.py

# Docker
docker-up:
	docker compose -f docker/docker-compose.yml up -d

docker-down:
	docker compose -f docker/docker-compose.yml down

docker-down-v:
	docker compose -f docker/docker-compose.yml down -v

docker-logs:
	docker compose -f docker/docker-compose.yml logs -f

docker-build:
	docker compose -f docker/docker-compose.yml build

docker-ps:
	docker compose -f docker/docker-compose.yml ps

# Evaluation
eval-sql:
	python -m evaluation.sql_eval.runner

eval-rag:
	python -m evaluation.rag_eval.runner

eval-agent:
	python -m evaluation.agent_eval.runner

eval-e2e:
	python -m evaluation.e2e_eval.runner

eval-all: eval-sql eval-rag eval-agent eval-e2e

# Cleanup
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	rm -rf htmlcov .coverage dist build *.egg-info 2>/dev/null || true