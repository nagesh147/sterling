# Phase 2 — Native Derivatives Strategy (toggle-able) — Design

_Date: 2026-06-02 · Branch context: `feat/realtime-iv-stream` · Status: approved design, ready for plan_
_Predecessor: `2026-06-02-derivatives-edge-study-design.md` (Phase 1, deferred to run later)_

## Context

Today the derivatives layer is a **routing + admission gate**: a long-only spot signal is routed to
futures or wrapped as a long call, or DEFER'd when a constraint trips. It never generates a
derivatives-native signal, and high-IV regimes (where the gate correctly blocks option *buying*)
have **no vol-selling alternative** — they just fall back to futures. Phase 2 adds a **native
derivatives strategy** that generates its own trades, coexisting with the existing gate behind a
**UI toggle**.

### Live-surface measurement that grounds this design (2026-06-02, real Delta India data)

| | BTC ($71.4k) | ETH ($1,994) | SOL |
|---|---|---|---|
| Realized vol 30d | 31% | 41% | — |
| ATM IV (0→87 DTE) | 28%→37% | 37%→50% | — |
| VRP (IV÷RV30) | 0.91→1.18 | 0.90→1.21 | — |
| Skew (25Δp−25Δc) | +3.9 pts | +2.7 pts | — |
| Liquidity (spread<5%) | 414/547, med 1.3% | 176/250, med 1.5% | — |

- **SOL has no options on Delta India → futures-only.**
- VRP is **thin** right now (short-dated < 1.0); rich VRP only appears in high-IV regimes that need
  an IV-rank history we **don't have yet** → vol-timing output is **provisional / forward-calibrating**.
- Skew is modestly positive (puts bid) → small structural put-side edge.
- Liquidity is good → the gate's spread vetoes rarely bind; the **IVR cap** is the real over-filter.

## Decisions (locked with user)

- **Risk posture:** `long_only` is the **default**; `defined_risk` (spreads/condors) and `naked`
  (short options) are **UI-selectable escalation tiers**, opt-in with guardrails.
- **Alpha sources:** support **all four**, each user-selectable; **directional-via-futures default-on**:
  `directional_futures`, `vrp_voltiming`, `skew_put`, `gex_pinning` (overlay).
- **Coexistence:** mode toggle `routing_gate` (existing, untouched) ↔ `native` (new); new active when
  selected.
- **Validation method (1/2/3) is a UI selector** that runs the chosen Phase 1 study method and renders
  its report (1=calibrate-to-live default, 2=real-only/forward, 3=snapshot).

## Architecture

New package **`app/engines/derivatives_native/`** exposing `decide(...)` and `decide_both(...)`-shaped
functions that **return the existing output contract** (`DerivativesDecision` /
`DualDerivativesDecision` / `DerivativesCandidate`). Nothing downstream changes — FE tables,
freeze-token store, and `/execute` consume the same schema.

**The toggle plugs in at the producer**, `app/services/derivatives_scanner.py` (verified: the sole
caller of `decide_both()` that writes `app.state.derivatives_scan_cache`):

```
scanner tick:
    mode = app.state.derivatives_engine_config.engine_mode   # "routing_gate" | "native"
    decide = selector.decide_both if mode == "routing_gate" else native_engine.decide_both
    dual = decide(signal=sig, market=market, chain=chain, ...)
```

Existing `selector.decide_both` is **not modified**. `engine_mode` defaulting to `routing_gate`
means zero behavior change until the operator flips the toggle.

### Global engine config

New `app.state.derivatives_engine_config` (and persisted via the existing `/derivatives/config`
global-patch path, `_ConfigPatchGlobalRequest`):

```
engine_mode:           "routing_gate" | "native"          # default "routing_gate"
active_alpha_sources:  set[str]   # subset of the 4; default {"directional_futures"}
risk_posture:          "long_only" | "defined_risk" | "naked"   # default "long_only"
validation_method:     1 | 2 | 3                          # default 1
```

This is **global** (engine-level), distinct from the existing **per-strategy** `profile_overrides`.

## Native engine pipeline (`native_engine.decide_both`)

Inputs: `SignalContext`, `MarketContext` (spot/IVR/funding/basis), live option `chain`, underlying
candles (for directional signal + realized vol), and the global engine config.

1. **Directional layer (futures, default-on):** build a futures candidate from the directional view
   (reuse `sl_tp_solver.solve_futures` + `leverage_engine`, as the existing `_futures_candidate`
   does). Fully real/validated. Present whenever `directional_futures` is active.
2. **Options layers** (only if chain present → BTC/ETH; SOL skips):
   - **`vrp_voltiming`:** compute live VRP (IV÷RV) + IV-percentile from `get_iv_history` (forward-
     accruing; until ≥ 60 distinct daily IV observations, fall back to VRP-vs-realized proxy and
     **flag `provisional=True`**).
     IV rich → propose a vol-*selling* structure (subject to risk posture); IV cheap → long premium.
   - **`skew_put`:** when downside skew rich, propose a put-side structure (long-only: long put as
     hedge/directional; defined_risk: put debit/credit spread; naked: cash-secured short put).
   - **`gex_pinning`:** overlay only — reuse `gex_engine.calculate_gex_profile` to size/time and to
     veto strikes near max-pain pinning. Never a standalone trade source.
3. **Risk-posture gate** filters the candidate structures (next section).
4. **Greeks-budget + freeze:** run the existing portfolio Greeks soft-gate and freeze each leg's
   decision (reuse `get_freeze_store().freeze`) so `/execute` is unchanged.

## Risk-posture tiers

| Tier | Structures allowed | Schema | Notes |
|---|---|---|---|
| `long_only` (default) | long call / long put | existing single-leg `DerivativesCandidate` | max loss = premium; no new schema |
| `defined_risk` | + verticals, put/call debit & credit spreads, iron condors | **new `DerivativesStructure` (legs[])** | capped loss; multi-leg |
| `naked` | + short put/call/strangle | `DerivativesStructure` | **opt-in only**; explicit confirm + margin/Greeks-budget check + warnings; unreachable from default |

`DerivativesStructure` (new): `legs: list[StructureLeg]` where a leg carries
`option_symbol, side(buy|sell), ratio, strike, expiry, premium, greeks`, plus aggregate
`max_loss_usd`, `max_profit_usd`, `net_premium_usd`, `breakevens`. Single-leg long-only continues to
use `DerivativesCandidate` so 2a ships without the multi-leg schema.

## UI

`frontend/src/components/derivatives/DerivativesPanel.tsx` (+ `useDerivatives.ts`) gains:
- **Mode toggle** `routing_gate ↔ native`.
- **Alpha-source checkboxes** (futures default-on, others opt-in).
- **Risk-tier selector** (`long_only` default; selecting `naked` shows a confirm + risk warning).
- **Validation-method selector (1/2/3)** that triggers the chosen study run and renders its report
  inline (new backend endpoints under `/derivatives/study/*` that invoke the Phase 1 study methods).

## Forward IV collector

Activate the idle `app/services/delta_iv_recorder.py` (writes `iv_history` / `option_iv_ticks` via
`db.record_iv` / `db.record_option_ticks`) on startup so IV-percentile becomes **real** over time —
the prerequisite for non-provisional vol-timing and for a true (non-modeled) Phase 1 re-run later.

## Build order (→ implementation plan)

- **2a — Native core (MVP):** `derivatives_native/` with `directional_futures` + `long_only` long
  premium options; global engine config + `engine_mode` toggle wired in `derivatives_scanner.py`;
  GET/POST `/config` carries engine config; FE toggle + source checkboxes + risk-tier selector
  (long_only only active). Default `routing_gate` ⇒ zero behavior change until flipped. **Tests:**
  native produces valid `DualDerivativesDecision`; mode switch is honored; existing path untouched.
- **2b — Multi-leg structures:** `DerivativesStructure` schema + `defined_risk` tier (spreads/
  condors) + `/execute` support for multi-leg + FE rendering. **Tests:** max-loss capped; legs
  freeze/execute atomically.
- **2c — UI + validation reports + forward collector:** validation-method selector wired to
  `/derivatives/study/*`; report rendering; activate `delta_iv_recorder`. **Tests:** each method runs
  and returns a report; recorder writes rows.
- **2d — Regime engine + naked tier:** VRP/IV-percentile engine consuming accruing `iv_history`;
  `naked` tier behind opt-in + margin/Greeks guardrails. **Tests:** provisional flag clears once
  history sufficient; naked unreachable without explicit opt-in.

## Honesty / safety invariants

- `engine_mode` defaults to `routing_gate`; native is opt-in. Existing selector code is not modified.
- `long_only` is the only default-reachable posture; `naked` requires explicit opt-in + guardrails.
- Vol-timing output is **`provisional`-flagged** until `iv_history` has ≥ 60 distinct daily IV
  observations (tunable).
- SOL is **futures-only** (no options listed on Delta India).
- Native mode reuses the existing freeze-token + Greeks-budget + circuit-breaker safety; no new
  bypass of `app.state.dd_circuit_breaker`.

## Dependencies / open items

- Phase 1 study still pending — when run, its winners should **seed/replace** the directional layer's
  signal rules and the vol-timing regime thresholds (currently provisional hypotheses).
- Multi-leg execution on Delta India: confirm `place_order_option` supports the multi-leg/structure
  flow (or sequence single-leg fills) before 2b execution wiring.
