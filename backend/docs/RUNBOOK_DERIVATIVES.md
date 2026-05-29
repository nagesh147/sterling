# DerivativesSelector — Operator Runbook

Counterpart to `DERIVATIVES_SELECTOR.md` (architecture). This document
is the playbook for live operations: how to roll the selector out per
strategy, how to kill it, where the manual intervention knobs live, and
what each decision-path log line means.

---

## Quick-reference kill switches

Listed from least to most disruptive:

| Action | Path | Effect | Recovery |
|---|---|---|---|
| Disable a single strategy | `POST /derivatives/config` with `profile.enabled=false` | Strategy reverts to legacy futures path immediately. | Re-POST with `enabled=true`. |
| Pause new selector orders for one underlying | `POST /derivatives/config` with `instrument_bias=futures` on the strategy | Selector returns futures candidate only; options chain untouched. | Re-POST with `instrument_bias=auto`. |
| Global Greeks budget freeze | Set `max_net_delta=0` on `app.state.greeks_budget_checker.budget` (via /risk-dashboard config or restart with env). | OrderRouter rejects every new order with `code=greeks_budget_breach:delta`. | Restore original caps. |
| Force-close all positions for one underlying | Use existing `/positions/close-all?underlying=BTC` endpoint | All open BTC positions closed at market; selector-stamped audit IDs get exit PnL recorded. | n/a |
| Universal kill switch (BLOCKS ALL ORDERS) | `POST /trading/kill-switch {enabled: true}` | OrderRouter rejects every order, paper or live. | `POST /trading/kill-switch {enabled: false}` |

---

## Per-strategy rollout sequence (recommended)

Default state on fresh install: **every strategy has `profile.enabled=False`**.
The legacy futures path runs unchanged. The selector engine is
operational but no orders route through it.

### Step 1 — observe
1. Visit `/api/v1/derivatives/candidates` (or the FE Derivatives table).
   Confirm rows appear when strategies emit signals.
2. Inspect `/api/v1/derivatives/preview` for representative signals.
   Confirm the chosen candidates match what you'd expect (delta near
   target, DTE in band, leverage capped reasonably).
3. Watch the audit log (`SELECT * FROM derivatives_audit ORDER BY ts_ms
   DESC LIMIT 50`). Verify the selector's reasoning per signal.
4. Run this for at least 7 days during your strategy's typical trading
   window before flipping anything live.

### Step 2 — enable one strategy
1. `POST /api/v1/derivatives/config` with the profile JSON, `enabled=true`.
2. Verify by GETting `/config` — the patched profile should show in the
   response.
3. The next signal from that strategy will route through the selector.
4. Watch the audit log for `executed=1` entries with realistic exit PnL.

### Step 3 — escalate per strategy
- 7-day spacing per strategy enable, in this order: `scalping/price_action`
  → `scalping/smc` → `triple_st` → other scalping strategies → statarb
  (when execute endpoint added) → directional (when engines return).
- Watch `/api/v1/derivatives/greeks-budget` for capacity headroom as
  you stack strategies.

### Step 4 — rollback when needed
- Single-strategy issue: `POST /derivatives/config` with `enabled=false`.
- Multi-strategy / unsure scope: set kill-switch (universal).
- Suspect Greeks budget drift: inspect `/derivatives/greeks-budget`
  and `usage_pct_of_nav`. Tighten caps if needed.

---

## Decision-path log lines

Search the uvicorn log (or `backend/server.log`) for these prefixes:

| Prefix | When | Action |
|---|---|---|
| `scalp-exec selector path failed` | Selector raised inside the scalping execute path; legacy futures path used. | Inspect the exception in the message. If recurring, file a bug. |
| `triple_st selector path failed` | Same as above for triple_st. | Same. |
| `monitor[X]: chain stale` | Background monitor skipped Greek-dependent updates (chain > 30s old). | Watch for sustained staleness — implies exchange-side flakiness. |
| `Auto-monitor: amend deferred` | Microstructure veto fired (spread > 8%). Stop amend deferred one poll. | No action; selector retries next poll. |
| `Auto-monitor: force-closed` | DTE force-close fired. Includes `settlement=True/False`. | Verify the position closed cleanly; fill_type should be "settlement" if expiry was crossed. |
| `ALGO router rejected` | OrderRouter rejected with a `code=...`. | Look up the code: kill_switch / daily_loss_halt / duplicate_order / cooldown_active / portfolio_cap_breach / microstructure_veto / correlation_size_zero / **greeks_budget_breach** / **exchange_error**. |
| `compute_new_order_greeks: option chain fetch failed` | Greeks gate falls open for the new order. | Order proceeds (fail-open). If repeating, indicates chain endpoint trouble. |
| `OptionChainCache: fetch failed` | Monitor's chain cache couldn't fetch for an underlying. | Verify adapter health for that underlying. |

---

## Manual intervention paths

### Force-disable a strategy
```
curl -X POST http://localhost:8000/api/v1/derivatives/config \
  -H 'Content-Type: application/json' \
  -d '{
    "profile": {
      "strategy": "scalping/price_action",
      "enabled": false,
      "instrument_bias": "auto",
      "target_delta": 0.5,
      "target_delta_tolerance": 0.05,
      "prefer_asymmetry": false,
      "dte_min": 0, "dte_preferred": 1, "dte_max": 3,
      "expected_hold_minutes": 75,
      "expiry_close_minutes_before": 120,
      "front_back_iv_diff_max": 0.05,
      "leverage_cap": 25,
      "max_premium_pct_of_account": 0.015,
      "funding_cost_max_pct_of_R": 0.25,
      "min_oi": 50, "min_volume_24h_x_contract": 5,
      "max_spread_pct": 0.05, "ivr_pct_naked_max": 85
    }
  }'
```

### Override Greeks budget at runtime
The `GreeksBudgetChecker` instance lives on `app.state.greeks_budget_checker`.
To raise the delta cap to 50% of NAV at runtime (no restart):

1. Open the FastAPI `/docs` UI.
2. Or directly mutate via Python REPL (`pdb` attached to the running uvicorn):
   ```python
   app.state.greeks_budget_checker.budget.max_net_delta = 0.50
   ```

Bedside-table caps (used by tests + fresh installs):
- `max_net_delta = 0.30`
- `max_net_gamma = 0.05`
- `max_net_vega = 0.15`
- `max_net_theta = -0.02`

### Manually amend a live stop
Use the existing `/positions/{id}/monitor` endpoint, which calls
`TrailingStopEngine.update` and then `cancel_replace_stop` on the live
exchange. Microstructure veto runs automatically (defers if spread > 8%).

### Emergency close-all
Two flavours:
- **Per-underlying** (preferred): hit each open position's close
  endpoint sequentially.
- **Universal**: set the kill switch first, then call `market_reduce_close`
  for each open position via the live order endpoint.

---

## Settlement vs market-close PnL accounting

`paper_store.close_position` writes two flags on close:
- `fill_type` — exchange-fill categorisation. Mirrors `fees.py FILL_TYPES`:
  `normal` / `settlement` / `liquidation` / `adl` / `otc`.
- `settlement_recorded` — True ONLY when the position crossed actual
  option expiry. This distinguishes a pre-expiry market exit from a
  cash-settle event.

The Phase 1 monitor force-closes positions 120 min before expiry by
default (30 min for notional < $1k) — those close with
`fill_type=normal, exit_reason=force_close_dte`. A position that runs
ALL the way through expiry (e.g., monitor missed a poll) closes with
`fill_type=settlement, settlement_recorded=True`.

For tax reporting: filter realized PnL by `fill_type`. Settlement-fill
PnL is typically taxed differently from market-close PnL in some
jurisdictions; this taxonomy lets you split the report.

## Indian TDS notes

`paper_store.close_position` writes `tds_withheld_usd` = 1% of gross
sell value for live (non-paper) closes. Skipped when `fill_type ==
"settlement"` — DEI handles TDS at settlement.

The TDS field is **for display only**. It is NOT used in trade
decisions. The /derivatives/greeks-budget endpoint surfaces gross PnL;
the FE can render post-tax PnL by subtracting `tds_withheld_usd` from
the position's `realized_pnl_usd`.

---

## Operational guards still in place

After Phase 5 ships:
- **Live-from-day-1 with no paper runway.** Mitigation: per-strategy
  `profile.enabled=False` defaults; recommended 7-day audit-log
  observation before flipping each profile on.
- **Kelly cold-start.** When `CalibrationService.win_rate()` returns
  None (< 10 closed trades), `leverage_engine.decide` caps at 2× and
  surfaces `cold_start_kelly` in the decision's warnings — the FE
  shows a "Cold start" banner.
- **Option chain freshness.** Phase 1 staleness gate skips Greek-
  dependent updates when chain age > 30s. Logs at debug.
- **OrderRouter correlation_penalty rounding.** Phase 0 fix preserves
  fractional contracts; rejects only when scaled size < 0.01.

## Things NOT yet implemented (deferred)

Documented in the plan file:
- PCR / max-pain primitives (selector v2 follow-up).
- WebSocket option chain (REST-only with staleness gate today).
- Multi-leg strategy construction (spreads, straddles, condors).
- Greeks gating on theta/vega for short-vol strategies (selector v1 is
  long-only; matches existing `place_order_option(side="buy")`).
- Cross-exchange arbitrage (DEI single-exchange scope).

If any of these become priorities, file a follow-up plan and re-enter
plan mode.
