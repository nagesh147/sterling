# DerivativesSelector — Architecture Reference

## What it is

`DerivativesSelector` is the central service every strategy calls to
decide **WHICH instrument** (futures vs options), **WHICH strike**,
**WHAT leverage**, and the SL/TP envelope for one signal — given the
signal context, the live market context, and the per-strategy profile.
The selector returns a `DerivativesDecision` with a chosen candidate, up
to 3 alternatives, and a `freeze_token` the execute endpoint validates.

```
Signal (any strategy)
        │
        ▼
┌────────────────────────────────────────────────────────┐
│  DerivativesSelector.decide(signal, market, chain,     │
│                              profile_overrides)        │
│                                                          │
│  1. profile gate                                         │
│  2. expiry_picker  (DTE ≥ 2× hold within profile band)  │
│  3. strike_picker  (Greeks-aware ranking)               │
│     ├─ option_pricing.enrich_with_greeks                │
│     ├─ liquidity_score  (hard floors)                   │
│     ├─ time_shifted_revaluation (BSM @ exit-T)          │
│     └─ pinning_gate     (DTE ≤ 2)                       │
│  4. instrument_chooser                                   │
│  5. funding_cost_gate                                    │
│  6. leverage_engine     (Kelly × CB × regime × caps)    │
│  7. sl_tp_solver        (futures or options)            │
│  8. greeks budget soft gate (Phase 0 wired hard at      │
│      OrderRouter._submit_live too)                       │
│  9. freeze + return                                      │
└──────────────────────┬──────────────────────────────────┘
                       │
                  freeze_token (UUID, 30s TTL)
                       │
            ┌──────────┴───────────┐
            ▼                      ▼
      /derivatives/preview    /derivatives/execute
      (table row, no order)    (validates token)
                                    │
                                    ▼
                       OrderRouter.submit(req)
                       ├─ Greeks budget HARD gate (refreshed)
                       ├─ Kill-switch / daily-loss / idempotency
                       ├─ Cooldown / correlation / microstructure
                       └─ set_margin_mode(isolated) → set_leverage
                                                    → place_order(_option)
```

## File layer-cake

```
app/engines/derivatives/
  schemas.py              — Pydantic models (SignalContext, MarketContext,
                             DerivativesDecision, DerivativesCandidate,
                             StrategyDerivativesProfile, LiquidityScore)
  profiles.py             — DEFAULT_PROFILES + get_profile()
  freeze_token.py         — FreezeTokenStore singleton, 30s TTL
  liquidity_score.py      — composite + hard floors
  expiry_picker.py        — 2× hold rule
  pinning_gate.py         — DTE ≤ 2 + OI concentration
  time_shifted_revaluation.py — BSM at exit-T (THE theta gate)
  strike_picker.py        — Greeks-aware ranking
  funding_cost_gate.py    — funding_cost / R hard cap
  instrument_chooser.py   — options vs futures heuristic + hard overrides
  leverage_engine.py      — Kelly × CB × regime × caps
  sl_tp_solver.py         — futures (resolve_trade_risk) / options (BSM)
  selector.py             — top-level orchestrator
  preview.py              — preview_one / preview_many shims

app/services/
  derivatives_audit.py    — record / mark_executed / record_exit / list_recent

app/api/v1/endpoints/
  derivatives.py          — /candidates /preview /execute /config
                            /greeks-budget /funding /book

app/engines/risk/         (Phase 0 + 1)
  greeks_budget.py        — bsm_greeks_full + GreeksBudgetChecker (gamma cap)
  option_pricing.py       — enrich_with_greeks + spot-bucket cache
  options_monitor.py      — OptionChainCache + force-close + microstructure veto
  portfolio_greeks_aggregator.py — runtime refresh + budget check
```

## Profiles

Each strategy carries a `StrategyDerivativesProfile`. Defaults ship in
`profiles.DEFAULT_PROFILES`; the operator overrides per-strategy via
`POST /derivatives/config`. `enabled` is `False` on first install for
every strategy — the legacy futures path runs until the operator flips
the flag after live observation.

### Per-strategy defaults

| Strategy slug | bias | target Δ | DTE band | leverage cap | IVR cap | premium cap |
|---|---|---|---|---|---|---|
| `scalping/price_action`   | AUTO    | 0.50 | 0–1–3   | 25× | 85 | 1.5% |
| `scalping/smc`            | AUTO    | 0.50 | 0–1–3   | 25× | 85 | 1.5% |
| `scalping/mean_reversion` | AUTO    | 0.50 | 0–1–3   | 25× | 85 | 1.5% |
| `scalping/ma_crossover`   | AUTO    | 0.50 | 0–1–3   | 25× | 85 | 1.5% |
| `scalping/breakout`       | OPTIONS | 0.40 | 0–1–3   | 15× | 85 | 1.5% |
| `scalping/delta_gamma`    | OPTIONS | 0.40 | 0–1–3   | 15× | 85 | 1.5% |
| `triple_st`               | AUTO    | 0.575 | 10–14–21 | 10× | 40 | 1.5% |
| `statarb`                 | FUTURES | —     | n/a     | 5× per leg, 2× net basis | — | 2% |
| `directional`             | AUTO    | 0.60 | 14–21–45 | 8× | 50 | 2% |

### Knob reference

Defined in `app/engines/derivatives/schemas.py:StrategyDerivativesProfile`.
Surfaced for editing in the FE `DerivativesPanel`.

- `enabled` — master switch. Default OFF. When OFF the legacy futures
  path runs unchanged.
- `instrument_bias` — `auto` / `futures` / `options`. Hard override.
- `target_delta`, `target_delta_tolerance` — bull's-eye for the strike
  picker.
- `dte_min` / `dte_preferred` / `dte_max` — the DTE band; `dte_preferred`
  is what `expiry_picker` aims for.
- `expected_hold_minutes` — drives `time_shifted_revaluation` exit-T.
  The selector enforces DTE ≥ 2× hold automatically.
- `expiry_close_minutes_before` — overrides the per-mode default that
  `_background_position_monitor` uses for force-close.
- `front_back_iv_diff_max` — reject options when front-month IV
  exceeds back-month IV by more than this (decimal vol points).
- `leverage_cap` — profile-level ceiling fed into `leverage_engine`.
- `max_premium_pct_of_account` — single-trade premium debit cap as
  fraction of NAV.
- `funding_cost_max_pct_of_R` — `funding_cost_gate` hard rule.
- `min_oi`, `max_spread_pct`, `min_volume_24h_x_contract` — liquidity
  hard floors.
- `ivr_pct_naked_max` — reject buying options above this IV percentile.

## DecisionStatus

```
OK          — selector picked a candidate; freeze_token is set
DEFER       — no candidate fits right now; user can re-poll
FAIL_OPEN   — selector couldn't run (chain missing, etc); caller
              falls back to legacy path
PROFILE_OFF — profile.enabled is False; caller uses legacy path
```

The wiring at `scalping.py:execute` and `strategy.py:execute` treats
DEFER / FAIL_OPEN / PROFILE_OFF identically — fall through to the
legacy futures path.

## Freeze-token contract

`FreezeTokenStore` is a process-singleton dict
`{token: (decision, expires_at_ms)}`. The selector calls `freeze(decision)`
which returns `(uuid_hex, 30_000)`. `/execute` calls `consume(token)`
which validates AND removes — so a single token fires at most once.
`get(token)` validates non-consumptively (used by FE previews).

A 409 with `code=stale_candidate` from `/execute` means the freeze
token expired or was already consumed. FE refetches `/candidates` and
prompts re-confirm.

## Greeks budget integration

Two gates, distinct responsibilities:

1. **Selector-side soft gate** (Phase 2; planned for v2 polish) — when
   the top candidate would breach the portfolio Greeks budget, the
   selector picks the next-best candidate that fits. UI shows
   "deferred — picked alternative" in the row's warnings.

2. **OrderRouter-side hard gate** (Phase 0, plumbed) — universal
   backstop. Refreshes every open option position's Greeks via
   `portfolio_greeks_aggregator.refresh_position_greeks(spot, iv_override)`
   at submit-time using live chain IV (Phase 1 upgrade), then runs
   `GreeksBudgetChecker.check`. Rejects with `code=greeks_budget_breach`.

Caps default to: `max_net_delta=0.30`, `max_net_gamma=0.05`,
`max_net_vega=0.15`, `max_net_theta=-0.02` (fractions of NAV).

## Audit log

`app/services/derivatives_audit.py` is an in-memory ring (5000-entry
cap) + SQLite write-through. Three call sites:

- `record(decision, signal, market)` — every `selector.decide` result,
  whether executed or not. Returns `audit_id` (UUID hex).
- `mark_executed(audit_id)` — flag the entry as executed after the
  OrderRouter response is non-rejected.
- `record_exit(audit_id, exit_pnl)` — called from
  `paper_store.close_position` when the position's notes carry a
  `[DERIV-aid=XXXXXXXX]` tag (the first 8 chars of the audit_id).

Operator queries via `list_recent(strategy=?, underlying=?, limit=200)`
or directly against the `derivatives_audit` SQLite table.

## Critical invariants

- `profile.enabled=False` is the default for every strategy. The
  derivatives path is **opt-in per strategy** with explicit operator
  action.
- The selector NEVER bypasses `OrderRouter`. Every order, selector-
  routed or legacy, hits the same safety pipeline (kill-switch, daily
  loss, idempotency, cooldown, correlation, microstructure,
  Greeks-budget hard gate, isolated margin set before leverage).
- `freeze_token` consume is single-fire. A user clicking EXECUTE twice
  gets one 200 and one 409 stale_candidate.
- `time_shifted_revaluation` is the ONLY theta gate. Do not reintroduce
  a separate theta budget — theta is implicit in the time-shifted price.
- Selector falls open (legacy path) on any unhandled exception. A
  selector hiccup never blocks an order.

## See also

- `RUNBOOK_DERIVATIVES.md` — operator manual intervention paths.
- `.claude/plans/nifty-honking-pudding.md` — the full implementation
  plan (Phases 0–6).
