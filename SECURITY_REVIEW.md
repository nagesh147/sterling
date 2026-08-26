# Sterling — Security & Correctness Review

**Date:** 2026-08-25
**Reviewer:** Claude Code (authorized self-review of `nageshmadaram/sterling`)
**Scope:** full repo clone — FastAPI backend (~969 Python files), React 19/TS frontend, execution/safety pipeline, credential handling, injection surface, dependencies.
**Method:** every Critical/High finding was read in-source and verified, not inferred from names. (`CLAUDE.md` directs code-review-graph/TrueCourse/graphify first; those MCP servers/CLIs were not connected in the review environment, so the documented Grep/Glob/Read fallback was used.)

> **Through-line:** `SECURITY.md` / `EXECUTION.md` describe a fail-closed, paper-by-default, idempotent, secrets-encrypted system. The *primitives* for that mostly exist and several are genuinely well-built — but on the **live auto-trading path they are bypassed, default the wrong way, or fail open.** The gap between the documented safety story and the wired-up behavior is itself the biggest risk.

---

## Severity summary

| ID | Severity | Finding |
|----|----------|---------|
| C1 | Critical | No real authentication on a live-order API bound to `0.0.0.0` |
| C2 | Critical | Auto-trader defaults to LIVE and ignores the advertised paper default |
| C3 | Critical | Broker secrets stored plaintext at rest; encryption keyed by a hardcoded, source-visible constant |
| C4 | Critical | Idempotency cannot stop duplicate LIVE orders on the failure it exists for |
| H1 | High | Greeks "hard gate" fails OPEN |
| H2 | High | Retried orders are re-placed WITHOUT their stop-loss/take-profit bracket |
| H3 | High | Unauthenticated SSRF via user-controlled webhook URL |
| H4 | High | SHADOW mode sends REAL orders on the auto path |
| M1 | Medium | Leverage/margin failures swallowed → order at stale leverage |
| M2 | Medium | Fractional size truncated by `int()`; claimed floor doesn't exist |
| M3 | Medium | Greeks budget uses a hardcoded $100k NAV, not real equity |
| M4 | Medium | Kite/INR live orders run with the daily-loss breaker disabled |
| M5 | Medium | Arbitrary directory enumeration via `/datalake/browse` + `/datalake/root` |
| M6 | Medium | CORS `allow_credentials=True` |
| L1 | Low | `CircuitBreaker` not wired into the live-order path |
| L2 | Low | Background monitors/retry build `is_paper=False` adapters |
| L3 | Low | Supply chain: `your-org` placeholder clones, unpinned deps, committed binary |
| L4 | Low | Kite postback signature check is optional — forged order-status updates |

---

## CRITICAL

### C1 — No real authentication on a live-order API bound to `0.0.0.0`
`get_current_user` (`backend/app/core/auth.py:28-31`) trusts the client-supplied `X-User-Id` header — no token/session/signature — defaulting to `"default"`. The docstring admits "Sterling has no first-party identity provider yet." `create_app()` (`backend/main.py:1750-1852`) mounts ~30 routers behind only CORS + security-headers; `__main__` runs `uvicorn.run(..., host="0.0.0.0", ..., reload=True)` (`backend/main.py:1861`).

**Impact:** anyone who can reach the port can place/cancel **live** orders, flip the kill-switch, switch the router to LIVE, and CRUD broker credentials — and by setting `X-User-Id: <victim>` impersonate any tenant (textbook IDOR on a real-money surface).

**Fix:** real authN (JWT/session) at the `get_current_user` seam; derive `user_id` from verified identity, never a header; bind to `127.0.0.1` by default; never run `reload=True` in production.

### C2 — Auto-trader defaults to LIVE and ignores the advertised paper default
`settings.paper_trading=True` (`backend/app/core/config.py:8`) is read only for *display* — never in a send path. The auto path builds `DeltaIndiaAdapter(is_paper=False)` (`backend/main.py:823-826`), defaults `algo_router_mode` to `"live"`, and **fails open to `RouterMode.LIVE`** on any parse error (`backend/main.py:828-834`, `:1176-1178`, `:1372-1375`). Unlike the manual endpoint (which checks `not active.is_paper`), `_auto_place_algo_order` never consults the account's `is_paper`.

**Impact:** a user who leaves the documented `paper_trading=True` and enables algo mode gets **real orders on real funds** on the first strong signal — and even setting the Delta account to paper does not stop it.

**Fix:** make `paper_trading=True` force `RouterMode.PAPER` everywhere; default the mode to `"paper"` and **fail closed to PAPER** on bad input; set the auto adapter's `is_paper` from the account/mode and refuse live when `active.is_paper`.

### C3 — Live broker secrets stored plaintext at rest; "encryption" keyed by a hardcoded, source-visible constant
`exchange_configs` declares `api_key TEXT` / `api_secret TEXT` (not `*_enc`) and `_persist()` writes them raw (`backend/app/services/exchange_account_store.py:39-40, 62-64`) — covering Delta/Binance/Deribit/OKX. Where encryption *is* used (Kite), `security._init()` falls back to the literal `"sterling-dev-insecure-key"` when `STERLING_SECRET_KEY` is unset (warn only), degrades to reversible base64 if `cryptography` is missing, and returns un-prefixed legacy values as plaintext (`backend/app/core/security.py:40-46, 51-65, 79-80`). `.gitignore:116-118` spells out the danger: *"sterling_paper.db carries exchange_configs.api_key and api_secret (plaintext — note the column is NOT *_enc)… Committing it publishes live credentials."*

**Impact:** anyone who obtains the SQLite file recovers **every live trading credential** — either as plaintext or under a key printed in public source. (No `.db` is currently committed — verified — so this is exposure-on-leak, not an active leak.)

**Fix:** encrypt `exchange_configs` secrets like the Kite path *intends* to; make `STERLING_SECRET_KEY` mandatory (refuse to start without it outside dev); make `cryptography` a hard dependency and drop the base64/plaintext fallbacks in production.

### C4 — Idempotency cannot stop duplicate LIVE orders on the failure it exists for
The dedup key is recorded **only after a successful fill** (`backend/app/services/live_safety.py:86-87`), lives in an in-process dict with a **60 s TTL** (`:7`), is checked non-atomically before the `await place_order`, and is **never sent to the broker** (Delta's body has no `client_order_id`). On a post-submit timeout the order is live-but-unrecorded, so `enqueue_retry` fires and the retry worker re-sends it ≥60 s later with no idempotency key — and concurrent submits race the same window.

**Impact:** the exact scenario the mechanism advertises (timeout → retry) **doubles a real position**; multi-worker deployments don't share the cache at all.

**Fix:** generate a stable `client_order_id` and **send it to the broker** (Delta supports it) so the exchange rejects the duplicate; reserve the key *before* the network call; serialize check-then-act per key; on unknown-outcome exceptions, reconcile via order lookup before re-placing.

---

## HIGH

### H1 — The Greeks "hard gate" fails OPEN
`backend/app/services/execution/order_router.py:285-297`: `except Exception: gate_result = None  # fail-open`, with a comment confirming it. The module docstring claims it "never silently fails-open." If the chain/NAV fetch throws during volatility, a budget-breaching live order proceeds.
**Fix:** reject with `greeks_budget_unknown` on gate exception, mirroring `assert_safe_to_trade`.

### H2 — Retried orders are re-placed WITHOUT their stop-loss/take-profit bracket
The retry payload omits SL/TP/trail (`backend/app/services/execution/order_router.py:347-354`); the worker re-places a bare market order. Result: an **unprotected live position** with no exchange-side stop.
**Fix:** carry and re-attach the bracket; refuse to retry an entry that can't include its protection.

### H3 — Unauthenticated SSRF via user-controlled webhook URL
`POST /webhooks` and `/{id}/test` have **no auth** (`backend/app/api/v1/endpoints/webhooks.py:26,37`); `_send` POSTs to the raw `wh.url` (`backend/app/services/webhook_store.py:208`); `WebhookCreate.url` is a plain `str` (`HttpUrl` is imported but deliberately unused). An anonymous caller can hit `http://169.254.169.254/…`, localhost, or internal hosts and read reachability from the echoed error.
**Fix:** type as `HttpUrl`, https-only allowlist, resolve-and-reject private/link-local/loopback ranges, require auth.

### H4 — SHADOW mode sends REAL orders on the auto path
`_submit_shadow` calls `_submit_live` (`backend/app/services/execution/order_router.py:261`) — a real order plus a paper twin — while the manual endpoint's comment says shadow "never touches real funds." An operator picking "shadow" to observe safely gets live Delta orders.
**Fix:** pick one definition; if shadow must be safe, simulate the fill instead of calling `_submit_live`.

---

## MEDIUM

- **M1 — Leverage/margin failures swallowed** (`backend/app/services/execution/order_router.py:324-331`, both `except: pass`): order places at whatever leverage the product previously carried → oversized position. Treat leverage-set failure as fatal for live entries, or read-back and verify.
- **M2 — Fractional size truncated by `int()`** (`backend/app/services/exchanges/adapters/delta_india.py:631`); the integer-floor the router comment claims lives in `_submit_live` doesn't exist. `2.7→2` (26% undersize), `0.6→0` (invalid, yet passes the `<0.01` guard). Round/validate against real lot size; reject when rounded size is 0.
- **M3 — Greeks budget uses a hardcoded $100k NAV** (`backend/main.py:1476-1477`), not account equity: on a $5k account the "30% delta" cap permits ~6× the book. Source PV from the live snapshot; refuse live if NAV unknown.
- **M4 — Kite/INR live orders run with the daily-loss breaker disabled** (`check_daily_loss=False` in the Kite service; drawdown breaker gated behind opt-in `wire_risk_infra`). Wire the INR daily-loss halt into both Kite paths; default the drawdown breaker on.
- **M5 — Arbitrary directory enumeration** via `GET /datalake/browse?path=…` and `POST /datalake/root` (`backend/app/api/v1/endpoints/datalake.py:140-182`) — behind the *stub* auth only. Constrain to an allowlisted base dir; reject `..`/absolute escapes.
- **M6 — CORS `allow_credentials=True`** (`backend/main.py:1758-1761`). Safe today because origins default to localhost — but never set `CORS_ORIGINS=*` alongside credentials.

---

## LOW

- **L1 — `CircuitBreaker` (margin<20% no-new-entries, 5-loss size cut) isn't wired into the live-order path** — instantiated at `backend/main.py:1452`, enforced only in a paper-P&L positions endpoint. (The daily-loss *halt* is still enforced.) Fold its checks into `assert_safe_to_trade`.
- **L2 — Background monitors/retry build `is_paper=False` adapters** independent of `algo_router_mode`, gated only by an active keyed account. Mostly reduce-only, but they act on live positions.
- **L3 — Supply chain:** `claude-setup.sh:20-21` clones `github.com/your-org/…` placeholders and installs them as `"default":true` skills (register the org → dev-env code execution; `$PWD` is also unquoted in the `jq` arg); `requirements.txt` uses unpinned `>=` with no hashes; `frontend/package.json` dev-dep `agentation ^3.0.2` and `vite ^8` are worth verifying against the registry; a 216 KB `git-filter-repo` binary is committed at root.
- **L4 — Kite postback signature check is optional (auth bypass on the webhook)** (`backend/app/api/v1/endpoints/kite.py:1143-1151`). The checksum comparison is guarded by `if checksum:`, so a payload that simply **omits** the `checksum` field skips verification entirely and is broadcast on the victim's `kite_orders` stream via `broadcast_order_update` (`:1151`). The endpoint is unauthenticated by design (the checksum *is* the auth), so an attacker who knows a Kite `user_id` can inject **forged order-status updates** (spoofed fills/rejections) into that trader's live UI → bad manual decisions. Bounded to stream spoofing — it does **not** place/modify orders — hence Low, but the bypass is real. **Fix:** require the checksum unconditionally (`if not checksum or checksum != expected: reject`) and compare with `hmac.compare_digest` (constant-time).

---

## What actually holds up (verified genuine, not just claimed)

- **Composite gate is truly fail-closed** — `assert_safe_to_trade` wraps kill-switch + daily-loss + idempotency in `try/except → deny("safety_unknown")` (`backend/app/services/live_safety.py:108-118`), and the INR risk read deliberately propagates DB errors so "can't see a loss" never reads as "no loss" (`:33-69`) — a thoughtful fix.
- **Adapter second line of defense** — Delta writes raise, and Kite simulates, when `is_paper`/creds missing (genuine; just bypassed on the auto path).
- **`no_adapter` rejects**, and only Delta+Kite can send orders (Binance/Deribit/OKX/`zerodha.py` are data-only).
- **Accounts default to paper** at the store/schema layer.
- **Injection surface is clean** (verified): SQL is fully parameterized (f-strings only interpolate hardcoded or allowlist+regex-validated identifiers); no `shell=True`/`os.system`/`os.popen`; no unsafe deserialization (`.xgb` models load via XGBoost's native non-executing loader, not pickle); no `verify=False`.
- **Frontend is well-behaved** — no `dangerouslySetInnerHTML`/`eval` in prod, no secrets or auth tokens in `localStorage` (only UI state), credentials only ever surface as hints.
- **Strong security headers/CSP** (`backend/main.py:1766-1784`); `.env` git-ignored and `.env.example` clean.

---

## Suggested fix order

1. **C1 (auth)** + **H3 (webhook SSRF)** — together they let an unauthenticated attacker place live trades and pivot internally.
2. **C2 (live-by-default)** + **C4 (dup orders)** — the two ways real money moves when you believe it's safe.
3. **C3 (credential encryption)** — fail-closed before any deploy that touches a real key.
4. H1/H2/H4, then the Mediums.
