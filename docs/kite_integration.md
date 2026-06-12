# Zerodha Kite Integration (Indian Markets)

A complete, multi-tenant Zerodha **Kite Connect v3** broker integration: full REST
surface, the live KiteTicker binary WebSocket, per-user encrypted credentials, and a
dedicated **KITE** UI tab. It is a **standalone manual trading + portfolio + market-data
console** — no Sterling/Grok/scalping strategy is wired to Indian markets.

## Architecture

```
backend/app/services/exchanges/kite/
  constants.py      # endpoints, order enums, ticker segment maths
  errors.py         # KiteError hierarchy + error_type → friendly message
  models.py         # account CRUD + session + write-request Pydantic models
  session.py        # login_url(), checksum()  (pure, unit-tested)
  client.py         # KiteClient(TradingExchangeAdapter) — full REST surface
  instruments.py    # multi-exchange instruments cache + search + token resolution
  ticker.py         # KiteTicker — binary WebSocket tick decode + connection mgr
  ticker_manager.py # per-user ticker lifecycle → broadcasts to StreamManager
  accounts.py       # KiteAccountStore — per-user encrypted credential/session store
backend/app/core/
  auth.py           # get_current_user (pluggable multi-tenant user context)
  security.py       # Fernet encryption for secrets at rest
backend/app/api/v1/endpoints/kite.py   # 42 routes under /api/v1/kite
frontend/src/components/kite/           # KiteTab + Connect/Watch/Portfolio/Orders/GTT panes
frontend/src/hooks/useKite.ts           # React Query hooks + mutations
```

The legacy `app.services.exchanges.adapters.zerodha:ZerodhaAdapter` is now a thin
backward-compat shim re-exporting `KiteClient` (registry + factory unchanged).

## Multi-tenancy

Every credential, session and tick stream is scoped to a `user_id`.
`app.core.auth.get_current_user` resolves it from the `X-User-Id` header, falling back
to `"default"` for single-user/local usage. **This is the single seam** where a real
identity provider (JWT/SSO/session) plugs in later — swap that one dependency and the
whole `/kite/*` surface becomes authenticated with no other changes.

Secrets (`api_secret`, `access_token`) are encrypted at rest with Fernet, keyed by the
`STERLING_SECRET_KEY` env var. **Set `STERLING_SECRET_KEY` in production** (a warning is
logged and an insecure dev key is used if it is absent).

## Setup (per user, from the UI)

1. Create a **Kite Connect app** at https://kite.trade → get an **API key + secret**.
   Set the app's **redirect URL** to wherever the frontend captures `request_token`.
2. In the app: **KITE tab → Connect & Keys → Add Kite Account** (API key + secret).
3. Click **Open Kite Login**, log in on Zerodha, then paste the `request_token` from the
   redirect URL and press **Connect**. The backend computes the checksum, exchanges it for
   an `access_token`, and stores it encrypted.
4. Toggle **Paper mode off** on the account to place live orders.

### Daily login
Kite `access_token`s expire daily (~6 AM IST) and there is **no refresh token** in Connect
v3 — the user must re-login each morning. The UI surfaces a "session expired — reconnect"
state when a `TokenException` is seen.

### Historical data
`/instruments/historical/*` requires Zerodha's paid **Historical Data** add-on; without it
those calls fail with a clear message.

## Endpoint reference (prefix `/api/v1/kite`, all `Depends(get_current_user)`)

| Group | Routes |
|---|---|
| Accounts | `GET/POST /accounts`, `PUT/DELETE /accounts/{id}`, `POST /accounts/{id}/activate`, `POST /accounts/{id}/test` |
| Session | `GET /login-url`, `POST /session`, `GET /status`, `POST /logout` |
| User | `GET /profile`, `GET /margins` |
| Market | `GET /instruments`, `GET /quote|ohlc|ltp`, `GET /historical` |
| Portfolio | `GET /holdings`, `GET /positions`, `PUT /positions/convert` |
| Orders | `GET/POST /orders`, `PUT/DELETE /orders/{id}`, `GET /orders/{id}/history|trades` |
| GTT | `GET/POST /gtt`, `GET/PUT/DELETE /gtt/{id}` |
| Margins | `POST /margins/orders|basket`, `POST /charges/orders` |
| Mutual funds | `GET /mf/holdings|orders|sips`, `POST /mf/orders`, `DELETE /mf/orders/{id}` |
| Ticker | `POST /ticker/subscribe|unsubscribe`, `GET /ticker/status` |

Order placement passes through `live_safety.assert_safe_to_trade` (kill-switch → 423,
daily-loss → 423, idempotency dedup). Paper-mode order/GTT writes return mock ids and
never hit the network.

## Live ticks (KiteTicker)

`ticker.py` decodes the big-endian binary tick frames (LTP / quote / full incl. 5-level
depth + OI). `ticker_manager` runs at most one ticker per user (from their active **live**
account) and broadcasts decoded ticks to the `kite_ticks:{user_id}` channel on the existing
`/api/v1/stream/ws` socket — no second public socket. Paper accounts don't open a ticker.

## Contract caveats

- **`get_product_id(symbol)`** returns the Kite `instrument_token` (int). For Kite this is
  *informational* — orders are placed by `tradingsymbol`+`exchange`, not a numeric id
  (unlike Delta). Returns `0` on miss rather than raising.
- **`cancel_order(order_id, product_id)`** ignores `product_id` (kept only to satisfy the
  `TradingExchangeAdapter` contract); cancellation uses `variety`+`order_id`.
- **`post_only`** is unsupported by Kite regular orders → raises `KiteOrderError`.
- Brackets: Kite has no per-order SL/TP bracket. Use **GTT** for protective exits; the
  generic `place_order` places the entry leg only (honors `stop_loss` only with an explicit
  `kite_order_type` of `SL`/`SL-M`).
- Kite orders/GTT are **form-encoded**; margin calculators are **JSON**. GTT `condition`/
  `orders` are JSON strings embedded in form fields.

## Rate limits

3 req/s (1 req/s for quotes). Quotes are batched via repeated `i=` params; UI polls at 5s.

## Tests

`backend/tests/test_kite_{session,instruments,orders,accounts,ticker,router}.py` — run with
`PYTHONWARNINGS=ignore python -m pytest tests/test_kite_*.py -q`.
