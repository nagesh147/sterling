# Security

## Secrets

- Exchange API keys/secrets are stored as `ExchangeConfig`
  (`app/schemas/exchange_config.py`) and surfaced only via `api_key_hint()`
  (`****` + last 4) in responses — never the full secret.
- App-level config comes from environment / `.env` (`app/core/config.py`).
  `.env` is git-ignored; commit `.env.example` only.
- Never log secrets. The JSON log formatter logs only explicit fields; keep
  credentials out of `extra=`.

## HTTP hardening

The FastAPI app applies security headers on every response (`main.py`
middleware): `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`,
`Referrer-Policy: strict-origin-when-cross-origin`, and a locked-down CSP
(`default-src 'none'; frame-ancestors 'none'` — API-only server). CORS origins
are an explicit allow-list (`settings.cors_origins`).

## Request traceability

Each request carries an `X-Correlation-ID` (honored if inbound, else minted) and
echoes it back — see [OBSERVABILITY.md](OBSERVABILITY.md). Use it to trace a
request across logs.

## Audit

- `app/services/derivatives_audit.py` records execution decisions.
- Every order rejection carries a machine-readable `code` for alerting.
- Order placement is **fail-closed** and **idempotent** (minute-bucketed +
  optional `client_order_id`) — see [EXECUTION.md](EXECUTION.md) — so a retry or
  double-submit cannot place a duplicate live order.

## Input validation

All API inputs are Pydantic models (`app/schemas/`). The order contract and
domain models validate types at the boundary. Add new external inputs as
Pydantic schemas, not raw dicts.

## Live-trading safety

Going live requires explicit mode changes (`RouterMode.LIVE`) and passes the
full safety pipeline + Greeks budget gate ([RISK_MANAGEMENT.md](RISK_MANAGEMENT.md)).
Paper is the default (`settings.paper_trading = true`).
