# GitHub Go-Live Checklist

Use this checklist to publish the project to GitHub with automated data refresh and predictable deploys.

## 1) Prepare Repository

1. Confirm `.env` is not committed (already ignored).
2. Keep large datasets out of Git (`data/` is ignored).
3. Keep commit history clean and portfolio-focused:
   - avoid committing generated files under `frontend/dist/`
   - remove one-off local debug scripts if not part of the product narrative
   - ensure README and decisions docs reflect current behavior
4. Run local checks:
   - `npm run build` in `frontend/`
   - backend health: `GET /health`
   - metrics: `GET /metrics`

## 2) Push to GitHub

1. Create a new GitHub repository.
2. Add remote and push your default branch.
3. Open GitHub Actions and confirm `CI` workflow passes.

## 3) Add Required GitHub Secrets

For existing workflows in `.github/workflows/ci.yml`:

- `DOCKERHUB_USERNAME`
- `DOCKERHUB_TOKEN`

For automated data jobs (if you add one):

- `DATABASE_URL`
- `REDIS_URL`
- `QDRANT_URL`
- `OPENAI_API_KEY`

## 4) Automated Data Refresh Strategy

For production-like behavior, run automation against hosted infrastructure (not local containers).

Recommended schedule:

- Daily: ingestion delta + derived tables + metric recompute
- Hourly: anomaly detection

Typical command order:

1. `python scripts/ingest_ecommerce_data.py --sample <size>` or your delta loader
2. `python scripts/ingest_upworthy_data.py --csv-path <path> --sample <size>`
3. `python scripts/derive_subscriptions.py`
4. `python scripts/derive_feedback.py`
5. `python scripts/compute_metrics.py`

## 5) Deployment Split

- Frontend: Vercel (connect GitHub repo, root `frontend/`)
- API + DB + Redis + Qdrant: Railway

This split keeps frontend deploys fast while backend and data jobs stay close to the database.

## 6) Go-Live Smoke Test

After deployment:

1. API health endpoint returns healthy.
2. Frontend dashboard cards show non-empty values.
3. Frontend request to `/api/metrics` returns the same payload as backend `/metrics`.
4. Run one manual investigation and confirm it completes.
