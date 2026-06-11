# Derivatives Structuring Revamp (Sterling + Grok) — Design

**Date:** 2026-06-11
**Branch:** `feat/dsr-deflation-gate`
**Scope:** the **derivatives translation layer only** — how an engine's signal becomes
a futures position or an options structure. **The alpha (signals/strategies) is NOT
touched.** No new strategies; no claims of new edge.

## Problem

Both engines (Sterling, Grok) feed armed signals into the NATIVE derivatives engine
(`app/engines/derivatives_native/engine.py::decide_both`), which is explicitly
"Phase 2a" and under-built:

- **Futures over-DEFERs.** `decide_both` builds the futures leg via
  `selector._futures_candidate`, which DEFERs ("sl_tp_reject") whenever
  `sl_tp_solver.solve_futures` rejects. For directional snapshots whose
  `stop_price`/`target_price` are missing, the collector sets `stop = entry`
  (zero risk distance) → the solver rejects → **the futures table is empty even
  when a real signal is armed.** Verified live: every futures leg = `DEFER`.
- **Options are incomplete.** "Phase 2a: directional_futures + long-only options."
  The directional debit-vertical path exists but isn't the reliable default;
  several branches DEFER on `no_structure`.
- **Per-engine structuring is under-developed.** Both engines run the same
  `decide_both`; the per-engine character is meant to come from each strategy's
  `StrategyDerivativesProfile` (Sterling: scalping short-DTE/near-ATM/high-lev +
  edge slightly-ITM; Grok: `directional` longer-DTE/slightly-ITM/lower-lev), but
  the structuring code doesn't fully honor it.

This is an **instrument-layer** problem, not an alpha problem. The fix is honest:
make a *real armed signal* reliably produce a *correctly-structured* futures
position and options structure per its engine's profile, deferring only on **real
quality gates** (funding cost, spread, liquidity, premium budget) — never
spuriously.

## Goal

For both engines, equally: an armed directional signal yields
- a **futures candidate** with a valid stop, per-profile leverage (funding-gated)
  and risk-based size — DEFER only when funding cost > the profile's R cap or no
  valid stop is derivable; and
- an **options candidate** — a delta-targeted defined-risk structure per the
  profile — DEFER only on real liquidity/spread/premium gates.

## The two engines (differentiation is entirely profile-driven)

No per-engine branching code. The same `decide_both` produces engine-appropriate
trades because `get_profile(signal.strategy)` returns:
- **Sterling** — `scalping/*` (dte 0–3, near-ATM Δ0.50, futures-bias, lev≤25, hold
  ~75m), `scalping/breakout`+`delta_gamma` (OTM Δ0.40, asymmetry), `edge/*`
  (dte 7–30, slightly-ITM Δ0.55, lev≤10).
- **Grok** — `directional` (dte 14–45, Δ0.60, AUTO bias, lev≤8, ~10-day hold).

## Architecture — two slices

### Slice 1 — Futures structuring (`selector._futures_candidate`)
The reliable-futures fix:
1. **Robust SL/TP derivation.** When the signal's `stop_loss` is missing/equal to
   entry/on the wrong side, derive an ATR-based stop **in the signal's direction**
   (`entry ∓ stop_atr_mult·atr`) and a TP at `rr_target`, so a valid plan is
   almost always producible. `solve_futures` is given a guaranteed-sane stop.
2. **Per-profile leverage** (already: provisional = `leverage_cap`, funding gate
   cuts it, `leverage_engine.decide` finalizes) — unchanged, validated.
3. **Risk-based sizing** (2% of NAV per R) — unchanged.
4. **DEFER discipline:** only when (a) no valid stop can be derived even from ATR
   (e.g. `atr ≤ 0` AND no structure stop), or (b) `funding_cost_gate` says funding
   > `funding_cost_max_pct_of_R`. Both are real gates. Spurious `sl_tp_reject`
   from a zero-distance stop is eliminated.

### Slice 2 — Options structuring (native engine options leg + `_defined_risk_candidate`)
Make the directional **delta-targeted debit vertical** the reliable default:
1. **Directional view → debit vertical** (`build_debit_vertical`): long leg nearest
   `target_delta`, short leg further OTM (one `strike_step`/profile width past),
   call-spread for long / put-spread for short. Strikes from the live chain.
2. **`prefer_asymmetry` profiles** (breakout/delta_gamma) → OTM single-leg long
   (Δ0.40) for convex payoff instead of a spread.
3. **DTE/expiry** per profile (`dte_preferred` within `[dte_min, dte_max]`).
4. **Greeks** (Δ/Γ/Θ/V) + expected-R populated on the candidate.
5. **DEFER discipline:** only on real gates — `spread% > max_spread_pct`,
   `OI < min_oi` / `vol < min_volume`, `premium > max_premium_pct_of_account`, or
   no strike within `target_delta_tolerance`. Vol-regime postures (naked/iron
   condor/GEX) are **retained unchanged** (they're separate, opt-in, regime-gated).

## Honesty guardrails (non-negotiable)

- **No alpha changes.** Signals/regime/arming untouched. This layer only structures
  what the engine already decided.
- **Real gates stay.** Funding, spread, OI/volume, premium-budget gates are
  retained — a genuinely un-tradeable structure still DEFERs. We remove only the
  *spurious* rejects (zero-distance stop), not the real ones.
- **No forced rows.** A candidate appears only for a real armed signal with a
  tradeable structure.
- **Auto-exec stays default-OFF.** This changes what's *shown*, not what's traded.

## Data flow (unchanged shape)

engine signal (armed) → `_both_rows` → `decide_both(signal, market, chain, profile)`
→ futures leg (`_futures_candidate`, Slice 1) + options leg (Slice 2) →
`DualDerivativesDecision` → candidate rows → scanner cache → FE tables.

## Testing

- **TDD per component.** Slice 1: `_futures_candidate` returns a candidate (not
  None) for a directional signal with a missing/zero stop (ATR fallback); returns
  None only when funding-gate trips or atr ≤ 0 with no stop. Slice 2:
  `_defined_risk_candidate` builds a delta-targeted debit vertical from a fixture
  chain; asymmetry profile → single-leg; DEFER on spread/OI/premium breach.
- **Regression:** the existing derivatives suites (`test_phase7_dual_tables`,
  `test_candidates_from_cache`, `test_phase0/1`, `test_derivatives_native`, …,
  ~300 tests) stay green.
- **In-process end-to-end:** an armed BTC short → `decide_both` → `futures=OK`
  (chosen) **and** `options=OK` (chosen, valid debit put spread), on real data.

## Decomposition / order

1. **Slice 1 (futures)** first — it's the most broken (empty futures table) and
   smallest. Ship + verify futures rows appear for armed signals.
2. **Slice 2 (options)** second — complete the delta-targeted structuring.

Each slice is independently shippable and testable.

## Non-goals

- No new strategies / alpha / signal changes.
- No removal of the real quality gates (funding/spread/liquidity/premium).
- No default-on auto-execution.
- No from-scratch engine rewrite (revamp in place; keep the validated
  leverage/funding/sizing sub-engines).
