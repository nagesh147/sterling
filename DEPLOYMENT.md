# Deployment

## Local development

```bash
make setup        # python venv + pip install, npm install
make backend      # uvicorn main:app --reload --port 8000
make frontend     # vite dev server (port 5173)
```

Backend venv lives at `backend/.venv`; all make targets use it.

## Docker

```bash
make docker-up      # docker compose up --build -d
make docker-logs    # follow logs
make docker-down
```

`docker-compose.yml` (repo root) builds the backend from `backend/Dockerfile`.
Configure via environment (see [CONFIGURATION.md](CONFIGURATION.md)); mount or
inject `.env` rather than baking secrets into the image.

## Environments

- Set `ENVIRONMENT=production`, `PAPER_TRADING` as appropriate, and real
  `CORS_ORIGINS`.
- Enable `LOG_JSON=true` in production so logs are machine-parseable
  ([OBSERVABILITY.md](OBSERVABILITY.md)).
- Provide exchange credentials through the exchanges API / secret store, not the
  image.

## Persistence

Today persistence is SQLite (`backend/sterling_paper.db` and friends). The
SQLAlchemy layer (planned, [MIGRATION.md](MIGRATION.md) Phase 5) makes the engine
URL configurable for PostgreSQL — point it at a managed Postgres for production
durability and horizontal read scaling.

## Health & readiness

`GET /health` returns status + timestamp (`tests/test_api.py::TestHealth`). Wire
it to your orchestrator's liveness/readiness probes.

## Pre-deploy checklist

1. `make verify` green (see [TESTING.md](TESTING.md)).
2. Golden smoke (`tests/test_golden_smoke_delta.py`) green.
3. Secrets injected via env/secret store; `.env` not in the image.
4. `LOG_JSON=true`, correct `CORS_ORIGINS`, `PAPER_TRADING` set intentionally.
