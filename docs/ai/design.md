# Sterling — Design Documentation

This document records *why* Sterling is built the way it is, split into two
independent concerns: the technical architecture of a system that moves real
(or paper-simulated) money, and the visual/interaction design of the surfaces
traders use to watch and control it. Read this alongside `CONTEXT.md` and
`WORKFLOWS.md` for session discipline; this file is the durable "why," not a
task log.

---

## 1. Technical Design Rationale

### 1.1 Why walk-forward validation over naive backtesting

Sterling requires walk-forward optimization with a strict no-lookahead rule
(the test window is never used for threshold selection), weekly-cached
sensitivity sweeps, and CPCV/Monte Carlo tooling as first-class `analytics`
engine modules — not one-off scripts. This is not academic caution; it
codifies a hard-won, repeated lesson from the project's own history.

The original Triple-ST momentum rule (`close>SMA50 & close>EMA7 & RSI(2)>ADX(2)`)
looked plausible on paper. A 144-config sweep across 25 coins with a 50/50
in-sample/out-of-sample split showed an IS↔OOS profit-factor correlation of
**−0.73**, with 0 of 58 in-sample-profitable configs staying profitable
out-of-sample — a textbook overfitting signature. By contrast, Connors-style
RSI(2) mean-reversion showed PF ~2.7–3.0 and was profitable in both
time-halves with graceful degradation across threshold choices. The same
pattern recurred independently in the scalping optimizer (IS↔OOS PF corr
≈ −0.65/−0.49, rejected in favor of a pooled per-timeframe study) and in the
DSR-deflation work on the regime book.

**The design conclusion:** a strategy is not trusted until it clears a
cross-symbol, OOS-split harness — naive single-window backtests reliably
produce false positives, and only walk-forward validation with genuine
held-out data exposes them before capital is at risk. A second, related
finding — that any timeframe under roughly an hour dies to transaction costs
(only 10/270 configs net-profitable in the edge-discovery matrix, virtually
all at 4h) — is treated as close to settled fact precisely because it
survived this same validation discipline across multiple independent
studies, not because it "looked right" once.

Even where validation succeeds, the bar for promotion stays high: the
regime-book's best deflated Sharpe ratio (DSR) reached 0.394 but never
cleared the 0.5 threshold the project treats as "statistically provable."
The design choice here is to separate *forward-green and HODL-beating* from
*provably not overfit*, and to keep anything short of the DSR bar paper-only
and isolated from the live `SterlingEngine` rather than promote it on faith.

### 1.2 Why singleton services for risk, calibration, and correlation

`DrawdownCircuitBreaker`, `CircuitBreaker`, `CorrelationTracker`, and
`CalibrationService` are all enforced as singletons (`dd_circuit_breaker`,
`circuit_breaker`, `correlation_tracker`, `calibration_service`) with fixed
call-order invariants inside `evaluate()`:

- `CircuitBreaker.update()` runs **first**, before any other evaluation logic.
- `CorrelationTracker.update()` runs on **every** `evaluate()` call with 1H closes.
- `CalibrationService.record_trade()` fires on **every** paper-store position close.
- `CalibrationService` is always injected via `Depends`, never imported directly.

The rationale is that these three concerns — capital erosion, correlated
exposure, and realized-edge tracking — are *portfolio-wide, continuously
accruing state*. If each strategy or code path held its own local instance,
two signals could evaluate risk against different views of the same
portfolio in the same tick, which is exactly the kind of silent
inconsistency a live-trading system cannot afford. A singleton with a fixed
update-order guarantees every evaluation path sees the same drawdown state,
the same correlation matrix, and the same calibrated win-rate — and
`Depends`-injection (rather than direct import) keeps the dependency
substitutable for tests without weakening that guarantee in production.

**Why two circuit breakers instead of one.** `DrawdownCircuitBreaker`
(portfolio-level, percentage-drawdown-from-peak, three-state
warn/halt/reset with a `size_multiplier()` for partial de-risking) and
`CircuitBreaker` (execution-level: daily P&L%, free-margin%, and
open-position-count against mode-specific concurrency limits) address
genuinely different risk dimensions — capital erosion vs. operational/margin
health. They are deliberately kept as separate singletons with separate
`app.state` attributes so a breach of one is never conflated with, or
silently masked by, the state of the other. The explicit documentation
callout that they are "not aliases of each other" is a defensive choice
against a real, anticipated confusion — this is treated as a load-bearing
platform invariant, not an implementation detail.

### 1.3 Why the strangler-fig / additive-only modular architecture

Sterling is deliberately **not** being rewritten. The stated principle —
"additive first... existing files are not moved or rewritten without
test-proven parity" — is backed by a hard zero-regression gate at every
step. The reasoning is risk management for a live-trading system: a rewrite
risks silently changing an exchange's real behavior (hence the
permanently-pinned golden smoke test for Delta Exchange India) or
introducing regressions into a codebase already handling real or
paper-simulated money movement.

The migration is split into six self-contained phases — safety net →
domain/broker contracts → observability → event bus/agents → separated
`RiskEngine` → SQLAlchemy persistence → canonical docs — specifically so
**any phase can be `git revert`ed independently** without unwinding the
others. Phases 2 and 4 are gated off/shadow by default, making rollback as
cheap as leaving a flag off. Reversibility was designed in up front, not
bolted on after the fact.

**Shadow-before-authoritative for behavior-changing components.** Both the
`RiskEngine` (Phase 4) and the SQLAlchemy persistence layer (Phase 5) ship
running in parallel/log-only mode alongside the existing authoritative path,
collecting disagreement data (`shadow_compare()` for risk;
`reconcile_positions()` / `reconcile_store()` for persistence) before being
promoted. The reasoning: pulling "should this be allowed?" logic into a
separate, registry-driven, independently-testable evaluator is valuable in
principle, but a risk-decision component is exactly the kind of thing that
cannot be cut over on faith — a silent behavioral difference could mean
money-losing orders that should have been rejected going through instead.
The same logic applies to the SQLAlchemy dual-write: a new source of truth
for trading state is not trusted until byte-for-byte parity is proven against
the old one over real traffic.

The Phase 5 dual-write deliberately **excludes** high-volume reproducible
market-data caches (`candles`, `ohlcv`, `iv_history`, `option_iv_ticks`,
`iv_surface_params`, `arrows`, `hmm_regimes`) and append-only stats
(`calibration_trades`, `wf_results`, `parameter_sensitivity`). These are
either trivially re-derivable from an external source or pure append-only
logs where a missed mirror write carries low durability risk. The dual-write
effort is concentrated where it matters: positions, equity snapshots, P&L
history, alerts, webhooks, exchange configs, calibration state, derivatives
audit — state that would be expensive or impossible to reconstruct if lost.

**Why `OrderRouter` is the sole integration point for orders.** Safety logic
(kill-switch, daily-loss, idempotency, cooldown, portfolio caps,
microstructure veto, correlation penalty, Greeks budget) must be enforced
identically regardless of which strategy or UI surface produced the order.
Auto-generated Sterling/Grok/derivatives signals and manually-placed Kite
orders funnel through the same pipeline — there is no code path where a
human clicking "buy" in the terminal bypasses the guards an automated signal
would hit. Making the router pure orchestration with injected `RouterDeps`
(rather than importing concrete implementations) is what makes the entire
safety pipeline unit-testable with zero real exchange calls, which in turn
is what makes the zero-regression discipline enforceable when risk logic
changes.

**Why fail-closed everywhere.** A guard that errors rejects the order —
never fails open. In a trading system the asymmetry is stark: a
false-positive rejection costs a missed trade; a false-negative pass-through
on a broken guard could place an unintended live order with real capital at
risk. This principle has propagated beyond the original `OrderRouter` into
newer, currently-undocumented code — the Navigator engine's flow/gamma
evidence explicitly reports `quality="unavailable"` with a
`CHAIN_UNAVAILABLE` code when option-chain history isn't available, and "the
order gate fails closed whenever those components are required." That it
shows up unprompted in new code is a signal it's treated as a platform-wide
convention, not a one-off rule.

**Why strategies never import adapters.** A strategy that only ever consumes
`Candle` / `OptionSummary` / `InstrumentMeta` and only ever emits `Signal`
can run unchanged against Delta India crypto, Zerodha equities, or any
future broker/market, because all exchange-specific translation (auth
signing, symbol formats, lot sizes, contract values) is isolated inside the
adapter — the anti-corruption layer. This is the concrete payoff of the
domain/application/infrastructure layering in `app/domain`: it is not an
aesthetic layering choice, it is what lets one MA-crossover / mean-reversion
/ VCP strategy implementation serve two structurally different markets
(crypto perpetuals vs. Indian equity/derivative contracts) without forking
the strategy code. `registry.json` is the mechanism that lets brokers and
strategies be discovered and composed without either side hard-coding
knowledge of the other.

**Why the Kite integration splits "raw client" from "trading logic."**
`app/services/exchanges/kite/` stays a thin, contract-conforming translator,
while all Zerodha-specific scanning, sizing, strike-selection, and
protective-stop logic lives in `app/services/kite_engine/`. This mirrors the
same anti-corruption-layer rationale used for the broker adapter/strategy
split generally: it keeps the raw Kite Connect API surface (auth, instrument
master, ticker) reusable and stable even as the trading logic built on top
of it — which has grown substantially (`scanner.py` and `service.py` are
each ~56KB) — continues to evolve rapidly.

**Why Navigator treats its own state as a disposable cache.** Per its own
docstring, Navigator's runtime service is designed so "it is always safe to
drop and rebuild [on restart]... restart never marks old evidence as
current." This is a deliberate choice to avoid a stale-state bug class where
a server restart could cause previously-fresh trading evidence to be misread
as still-current after a gap — directly motivated by a just-fixed defect
class in exactly this area. New engines that cache decision state should
follow this as a first-class design principle, not treat it as a
Navigator-only quirk.

### 1.4 Why Kelly sizing

Position sizing in the v2 engine ties size to the *magnitude of measured
edge* — win probability and payoff ratio — rather than a fixed fraction of
capital per trade. The reasoning follows directly from the calibration
discipline elsewhere in the platform: `CalibrationService.record_trade()`
runs on every paper-store position close specifically so that the win-rate
and payoff inputs Kelly sizing depends on are continuously re-estimated from
*realized* outcomes, not fixed assumptions made at strategy-design time.
This closes the loop between "assumed edge" (what a strategy's backtest
claims) and "measured edge" (what it's actually delivering in current
market conditions) — the same meta-lesson that drove the DSR/OOS validation
discipline in §1.1 applies to sizing: an edge estimate that isn't
continuously checked against real trade outcomes is a liability, not a
convenience. In practice this pushes the platform toward fractional/capped
Kelly rather than full Kelly, since probability estimates carry real
estimation error and full Kelly is punishing to size on a noisy edge
estimate — the same caution that keeps unproven strategies paper-only (§1.1)
motivates sizing conservatively against an edge that is still being
recalibrated in production.

### 1.5 Other notable design choices

- **Fail-closed as a platform-wide convention, not a router-only rule** — see
  §1.3; it now governs Navigator's evidence-quality reporting as well as
  order execution.
- **DSR as a governance gate, not just a metric** — the platform treats
  "beats HODL, forward-green" and "provably not overfit (DSR ≥ 0.5)" as two
  distinct claims, and refuses to conflate them even under user pressure to
  find validation (a cross-market NIFTY/BANKNIFTY expansion was killed on
  negative OOS results, IS↔OOS corr −0.87, despite explicit pressure to be
  "convinced"). Holding this line is treated as a feature of the design
  process, not friction.
- **Display bugs are diagnosed as display bugs, not resized as risk bugs** —
  several investigations that looked like severe sizing problems (a "0.00%"
  risk column, an alarming "$2.7M notional" alert) turned out to be pure
  reporting artifacts (a hardcoded $100k NAV divisor; a legitimately large
  position against a tight stop). The design lesson is to verify whether a
  scary number is a measurement bug or a real exposure problem before
  changing risk logic — conflating the two would either mask a real bug or
  introduce risk-logic churn to fix a cosmetic one. The one *real* bug found
  in that investigation (poll-time-spot stop fills instead of stop-price
  fills, `realistic_stop_fill`) was fixed at the fill layer, not the risk
  layer.
- **Contract-value lot sizing** — `SizedTrade.contracts` represents exchange
  *lots*; all value/risk/PnL math must use `SizedTrade.qty` (lots ×
  contract-value, e.g. Delta ETH=0.01/BTC=0.001/SOL=1). This distinction
  exists because conflating lots with underlying-coin quantity is a latent
  100x valuation risk, not a cosmetic one — it previously caused
  sub-1-coin positions to floor to zero and silently reject as
  `size_too_small`.

---

## 2. UI/UX Design

### 2.1 Design principles

- **The UI must not lie about state.** A recurring class of fix across the
  Navigator/Kite surfaces — mislabeled board rows, lying strike badges,
  blank signal prices, a trailing stop that wasn't enforced as a real exit —
  is treated as a correctness bug, not a polish issue. A badge, price, or
  exit-state label is a claim about what actually happened to a position;
  the design bar is that the displayed state and the true broker/engine
  state can never diverge, even transiently.
- **Action over open-ended questions.** The interface (and the assistant
  building it) favors a sensible, stated default over a formal
  multiple-choice fork when a default is defensible — e.g. tuning a
  light/dark theme choice "to the app" rather than presenting an abstract
  option set. Explicit forks are reserved for decisions that materially
  change the deliverable with no sensible default, and honest caveats
  (unvalidated edge, fallback rates, DSR below threshold) are still
  surfaced unprompted even when a default is chosen.
- **A UI "rework" changes structure, not just skin.** Restyling an existing
  layout (same bands, new colors) reads to users as "no diff." A genuine
  rework collapses, merges, reorders, or promotes/demotes content — and the
  design process favors presenting two structurally distinct mockups to
  react to over iterating on a single restyle.

### 2.2 Key screens and tabs

**Terminal shell.** The app is Sterling-engine-only at the top level —
STERLING ENGINE / POSITIONS / BACKTEST — after the removal of legacy
stat-arb, RSI mean-reversion, and standalone signal/calibration tabs. Engine
attribution across shared tables (Sterling vs. Grok vs. derivatives-edge
candidates) is carried by a `SourceBadge` component and an `engine` prop
rather than duplicated tables, so multiple engines can post into a common
candidate/position view without visually blending their signals.

**Kite tab.** The largest and most actively developed surface:
- *Chart state* is global, not per-symbol: timeframe, indicators, params,
  and zoom are one shared `__global__` config blob, while drawings remain
  per-symbol (`drawingsBySymbol`). This was a deliberate reversal of the
  original per-symbol design after user feedback that chart configuration
  "should be the same throughout" — not a bug fix, a rebuilt data model.
- *OI Change / Open Interest* are Sensibull-style tabs beside Fundamentals,
  rendering CE/PE bars diverging by strike; since Kite has no intraday OI
  history, ΔOI is computed client-side against a localStorage
  first-snapshot-of-the-day baseline, with total OI sourced live from the
  option chain.
- *Scan-source quick-toggle* is a 4-way control (spot / derivatives /
  confluence / both), reflecting that confluence is a distinct fourth
  scan mode (underlying fires and the leg's own premium confirms), not a
  variant of the other three.
- *Position table* uses a 7-column convention — Entry / SL / TSL (not
  "Stop") / Exit / Target (the trailing level, since there is no fixed
  take-profit) / Chg / LTP — chosen so the column names describe what the
  value actually represents rather than reusing generic labels that would
  misdescribe a trailing-only exit model.
- *Order window* uses flex columns for its input rows; any such column
  needs `minWidth: 0` or fields silently clip/overflow (the concrete
  historical failure mode was a Trigger field that appeared to be
  "missing" but was actually just clipped to zero width).

**Charts.** Built on lightweight-charts. Multi-color line indicators (dual
SuperTrend lines, Navigator overlays) use a `supertrendRuns`-style
convention: split the series into contiguous same-color runs and render
**one short series per run**, each seeded to share its boundary vertex with
the next. This exists because lightweight-charts v5 connects `LineSeries`
straight through whitespace gaps — a naive "insert whitespace to break the
line" approach silently fails to produce a color break in v5. Any new
two-color line overlay on this chart stack should use the runs pattern, not
whitespace gaps.

**Navigator.** Drawn directly on the chart rather than as a side panel —
entry/SL/TSL/exit markers and strike badges are chart annotations, kept in
sync with the same "UI must not lie" principle from §2.1: strike badges must
reflect the actual selected strike, board rows must reflect the actual
Navigator row they annotate, and rupee-move figures must reflect the real
priced move, not a stale or misattributed one.

**Signal status taxonomy.** Sterling-native signals expose `entry_ok`
directly; Grok/directional signals have no such field and instead derive a
status from `state` (`ENTRY_ARMED_*` → ready, `*_SETUP_ACTIVE` → pending,
`IDLE`/`NONE` → watching) through a shared `getSignalStatus` helper, so the
tab-level counts and the per-row signal pane can never disagree about what
"ready" means for a given engine.

**Modals.** Header-hosted modals (e.g. the paper/live toggle) are portaled
to `document.body` with a z-index above 10000, because the terminal's root
stacking context (`.term-root > * { z-index: 1 }`) otherwise traps them
behind the page — a modal that silently renders behind the page reads to a
user as "the page went blank," which is why this is treated as a layout
invariant for any new header-hosted modal, not a one-off CSS fix.

### 2.3 The Mac-style motion layer (optional, gated)

`useMacKite()` gates an optional "Apple-grade" motion mode across tickers,
order-window transitions (morph), chart transitions (Magic Move), and
free-drag panel rearrangement (Stage Manager–style). When the mode is off,
the interface is stock Kite with no motion dependency loaded at all.

The design choice that matters here is **lazy loading, never a static
import** of `framer-motion`. If the motion library were imported at module
scope, every user would pay its bundle cost regardless of whether they ever
enable the mode, which defeats the point of making it optional. Gating the
feature at the hook level (`useMacKite()`) while lazy-loading the animation
library underneath it means:

- Default users get the plain, lightweight Kite experience with zero motion
  overhead.
- Users who opt in get a distinct, cohesive motion language (`macMotion`
  tokens) applied consistently across tickers, order transitions, and chart
  transitions, rather than a single animated widget bolted onto an
  otherwise-static page.
- The feature can evolve or be removed without touching the default render
  path, consistent with the additive-only philosophy in §1.3 applied to the
  frontend.
