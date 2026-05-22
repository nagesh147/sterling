# Sterling v4 — Canonical Strategy Spec

**Single source of truth.** Resolves contradictions C1–C4 from prior README revisions. Every
number here is enforced in code by `engines/directional/scoring.py`,
`engines/directional/sizing_engine.py`, `engines/directional/structure_selector.py`,
`engines/risk/cooldown.py`, `engines/risk/regime_adaptive_sizer.py`, and
`services/execution/order_router.py`. Conflicts between this doc and code are bugs to file.

---

## Contradiction Resolutions

### C1 — Score gates × leverage tiers (RESOLVED)

**Problem.** README listed two ladders that overlapped:

- "Hard score gate: ≥75 normal, ≥85 high-leverage (≥10×) or naked short"
- "Futures leverage scale: ≥75→3×, ≥80→5×, ≥85→10×, ≥90→25×, ≥95→50×"

Score-band 75–84 with leverage 3–5× is "normal", but 5× borders the high-leverage threshold —
unclear whether it falls under the 75 or 85 gate.

**Resolution.** Two **independent** ladders. The score gate is a *minimum* admission test;
leverage is a *post-admission* sizing parameter.

| Score band | Admitted? | Max futures leverage | Max options structure |
|------------|-----------|---------------------|----------------------|
| < 75       | NO  | 0× (excluded) | excluded |
| 75–79.9    | YES | **3×**  | debit spread / naked long only |
| 80–84.9    | YES | **5×**  | debit spread / naked long |
| 85–89.9    | YES | **10×** | + naked short / credit spread |
| 90–94.9    | YES | **25×** | + naked short |
| ≥ 95       | YES | **50×** (scalp) | + naked short |

Concrete invariants enforced by `passes_score_threshold`:

- `score < 75` → all structures excluded.
- `score < 85` AND `leverage ≥ 10` → excluded (caller cannot request 10× on a 75-score signal).
- `score < 85` AND `structure_type ∈ {naked_short, naked_short_call, naked_short_put}` → excluded.
- `signal_strength != "STRONG"` AND requested leverage ≥ 10× → leverage downgraded to 5×.

Code: `backend/app/engines/directional/scoring.py:passes_score_threshold`
and `structure_selector.py:select_leverage`.

### C2 — IVR fallback band (RESOLVED)

**Problem.** README's IVR table only listed bands `<40 / 40–60 / 60–70 / >70`. When the
data source returns `ivr=None` (Delta India HV fallback failure, dead chain, etc.), no row
applied. Routing was ambiguous.

**Resolution.** Five named bands with explicit `None` handling:

| Band      | IVR range  | Allowed structures                        | Risk posture |
|-----------|-----------|-------------------------------------------|--------------|
| LOW       | < 40      | naked long, debit spreads                 | Buy premium |
| NORMAL    | 40–60     | all structures (debit preferred)          | Mixed |
| ELEVATED  | 60–70     | debit + credit spreads (no naked long)    | Defined-risk |
| HIGH      | > 70      | naked short, credit spreads, futures      | Sell premium |
| **UNKNOWN** | `None`  | **debit spreads + futures only**          | Fail-closed |

Fail-closed rule: when `ivr is None` we treat the regime as **ELEVATED** for routing
purposes — naked premium (long or short) is excluded; defined-risk debit spreads and
futures are allowed. Documented in `engines/directional/policy_engine.py:resolve_band`.

### C3 — Sizing caps and stacking (RESOLVED)

**Problem.** Multiple cap sources collided:

- Per-trade cap by structure: 1.5% long, 1.0% short, 2.0% futures.
- Portfolio cap: 4.5% long, 3.0% short, futures unspecified.
- Scalp leverage (≥50×) cap: 0.5%.
- 25% fractional Kelly may produce a number above any of the above.

Unclear which dominates and whether caps stack or replace.

**Resolution.** Single deterministic chain. The smallest of these wins:

```
target_risk_pct = min(
    fractional_kelly_25(win_rate, rr),     # adaptive baseline
    base_cap_for_structure(structure),     # per-trade cap (1.0/1.5/2.0%)
    risk_params.max_position_pct,           # global config cap (default 5%)
    0.005 if leverage >= 50 else +∞,       # scalp ceiling
    portfolio_correlation_penalty(...),    # 1.0 / 0.7 / 0.4 multiplier
    regime_adaptive_multiplier(...),       # 0.5 / 1.0 / 1.5 by ATR pct
)
```

Portfolio caps are enforced **as exposure budgets**, not per-trade caps:

| Bucket            | Max simultaneous capital-at-risk |
|-------------------|----------------------------------|
| Options long      | 4.5%                              |
| Options short     | 3.0%                              |
| Futures total     | 6.0%                              |
| **Mixed (any)**   | **8.0% global ceiling**           |

The OrderRouter rejects new orders that would breach any bucket cap. Code:
`engines/directional/sizing_engine.py:size_trade` plus
`engines/risk/regime_adaptive_sizer.py:adapt`.

### C4 — Veto priority order (RESOLVED)

**Problem.** Three veto layers existed without explicit precedence:

- IDLE veto (ATR percentile + slope on 4H regime).
- ADX gating (<15 ranging, 15–20 partial, ≥20 full).
- Hard vetoes (spread, OI, dead zone, funding).

Conflicts: a 4H IDLE bar with ADX=18 — partial signal allowed or full veto?
Dead-zone (02:00–06:00 UTC): does it block monitoring or just new entries?

**Resolution.** Precedence pipeline, top wins:

1. **Hard vetoes** (`scoring._check_hard_vetoes`) — spread > 10%, OI < 50, dead zone,
   funding |rate| > 2.5%. Drops `score=0`. Applies to **new entries only**;
   existing positions continue to monitor and trail.
2. **IDLE veto** (`regime_engine`) — ATR pct < 30 on 2 bars OR slope < 0 + pct < 35.
   Marks regime `IDLE`; orchestrator returns state `FILTERED` for new entries.
3. **ADX gate** — `<15` → RANGING (no signals), `15–20` → STRONG required, `≥20` → all
   signal strengths admitted.
4. **Cooldown** (per `(underlying, mode, direction)`) — runs after vetoes; blocks
   re-entries within mode-specific window.
5. **Score threshold** (75/85) — final admission test.
6. **Microstructure veto** (NEW v4) — last-ditch: bid/ask imbalance, last trade
   pressure on the venue's order book.

Order matters because cheaper checks short-circuit later expensive ones. Live OrderRouter
runs the same pipeline in the same order so backtest and live agree.

---

## v4 New Modules

### OrderRouter (`services/execution/order_router.py`)

Single class wrapping every primitive needed to emit a real order:

```python
router = OrderRouter(mode="shadow", adapter=delta, store=paper_store)
resp = await router.submit(OrderRouterRequest(
    underlying="BTC", direction="long", instrument_type="futures",
    size=1, leverage=5, client_order_id="user_42_xyz",
))
```

**Modes**:

| Mode     | Live API call | Paper position recorded | Use case |
|----------|---------------|------------------------|----------|
| `paper`  | NO            | YES                    | Default — pure simulation |
| `shadow` | YES           | YES                    | Audit trail — write paper position alongside live order, compare fills |
| `live`   | YES           | NO (live position only)| Production trading |

**Pre-flight pipeline** (every mode):

1. `live_safety.assert_safe_to_trade` — kill switch / daily loss / idempotency
2. `cooldown.is_blocked` — per-mode/direction cooldown
3. `correlation.portfolio_correlation_penalty` — sizing scale
4. Portfolio bucket caps (C3 ceilings)

On failure: structured response with `code`, `reason`, and (for retryable network errors)
auto-enqueue into `live_safety.RetryItem` queue.

### Vol-of-Vol Gate (`engines/risk/vol_of_vol_gate.py`)

IVR alone is a snapshot. **IVR-of-IVR** — the standard deviation of IVR over a rolling
window — flags volatility regime changes that snapshot IVR misses.

Rule: if `std(IVR_30d) > 12 percentile points` AND latest |Δ IVR_24h| > 8 points →
`vol_regime_unstable=True`. Naked premium (both long and short) is excluded; only
defined-risk spreads and futures allowed.

Catches: post-FOMC IV crush (high IVR snapshot, but vol-of-vol high → coming compression),
Friday-of-expiry vol expansions (low IVR snapshot, vol-of-vol high → coming expansion).

### Microstructure Veto (`engines/risk/microstructure_veto.py`)

Late-stage gate run only at the **moment of order submission**. Inputs: top-of-book
bid/ask sizes, last 50 trade prints (size + side).

Vetoes when any of:

- Book imbalance |bid_qty − ask_qty| / (bid_qty + ask_qty) > 0.7 against the trade direction.
- Last 50 prints show > 80% sell-pressure when going long (or vice versa).
- Mid-spread > 1.5× the contract's 1-hour spread mean (regime change in liquidity).

Cheap (no extra REST calls — uses the order book snapshot the adapter already fetched).
Saves a measurable fraction of trades that would have entered into a bad print.

### Regime-Adaptive Sizer (`engines/risk/regime_adaptive_sizer.py`)

Final multiplier on top of Kelly + caps. Reads the `RegimeResult.atr_percentile`:

| ATR pct | Multiplier | Reasoning |
|---------|-----------|-----------|
| < 25    | 0.5       | Compression — moves slow, risk:reward worse, half-size |
| 25–60   | 1.0       | Normal regime |
| 60–85   | 1.25      | Healthy expansion — favorable for trend-followers |
| > 85    | 0.75      | Hyper-expansion — gap risk and stop-runs, partial-size |

This produces the "fat barbell" position-sizing curve that beats flat sizing in Monte
Carlo across the 2018–2024 BTC regime.

---

## Live Infra Architecture

```
┌──────────────────────┐
│ FastAPI: /trading/*  │  thin endpoint (parses body, calls router)
└──────────┬───────────┘
           ▼
┌──────────────────────────────────────────────────────────────┐
│                    OrderRouter.submit()                      │
│  ┌───────────────┐ ┌────────────┐ ┌─────────┐ ┌───────────┐ │
│  │ live_safety   │ │ cooldown   │ │ corr    │ │ portfolio │ │
│  │ assert_safe   │→│ is_blocked │→│ penalty │→│ caps      │ │
│  │ (3 guards)    │ │            │ │         │ │           │ │
│  └───────────────┘ └────────────┘ └─────────┘ └───────────┘ │
│         │                                                    │
│         ▼  (mode dispatch)                                   │
│  paper → paper_store.create()                                │
│  shadow → adapter.place_order() + paper_store.create()       │
│  live   → adapter.place_order()  ← idempotency-keyed          │
│         │                                                    │
│         ▼                                                    │
│  on success: record_idempotency, emit telegram alert         │
│  on failure: enqueue_retry, return structured 502            │
└──────────────────────────────────────────────────────────────┘
```

---

## Backtest Robustness

`engines/backtest/sweep.py` ships:

- `walk_forward_split(n, n_splits=3, train_pct=0.7)` — non-overlapping, non-leaking.
- `walk_forward_run(...)` — backtest each train/test window separately.
- `param_sweep(grid)` — full Cartesian over parameter grid.
- `top_by(results, key="sharpe", n=5)` — rank by stat.

`engines/analytics/performance.py` computes all four standard ratios:

| Ratio | Formula | Interpretation |
|-------|---------|---------------|
| Sharpe  | μ / σ * √252 | Reward per unit total volatility |
| Sortino | μ / σ_downside * √252 | Reward per unit downside volatility |
| Calmar  | annualised return / |max drawdown| | Reward per unit MDD |
| MAR     | annualised return / |max drawdown| (synonym) | |

Per-trade logs include entry/exit timestamps, mode, structure type, leverage, contracts,
realised PnL, fees, slippage estimate, and the ATR percentile / IVR / score at entry.

---

## UI/UX v4

| Component | File | Purpose |
|-----------|------|---------|
| `SignalsTable` | `components/SignalsTable.tsx` | Signal feed with track filter pills (ALL/VCP/TREND/REVERSION) |
| `LiveControlPanel` | `components/LiveControlPanel.tsx` | Kill switch, algo-mode, algo-router-mode selector |
| `PaperLiveToggle` | `components/PaperLiveToggle.tsx` | 3-way PAPER/SHADOW/LIVE toggle |
| `V4AnalyticsDashboard` | `components/V4AnalyticsDashboard.tsx` | Live P&L + realized PnL + mode badge |
| `ArrowAlert` | `components/ArrowAlert.tsx` | SSE overlay alert cards |

`LiveControlPanel` calls `POST /api/v1/trading/algo-router-mode` on mode change.  
`PaperLiveToggle` operates on exchange `is_paper` flag. Both sync via `sterling-router-mode-change` custom event.

---

## Testing Surface

```
backend/tests/
├── test_live_safety.py            ← kill switch, daily-loss, idem, retry queue
├── test_p1_cooldown_delta.py      ← per-mode/direction cooldown
├── test_p1_wiring_and_modes.py    ← orchestrator routes to correct timeframe
├── test_trailing_stop.py          ← ATR/ST/Pct trail, breakeven, lock-in
├── test_backtest_robustness.py    ← walk_forward + param_sweep
├── test_order_router.py           ← v4: paper/shadow/live dispatch + safety
├── test_advanced_risk.py          ← v4: vol-of-vol, microstructure, regime-adaptive
├── test_sse_keepalive.py          ← v4: SSE stream emits :keepalive every 30s
└── ... (all existing 30+ test files)
```

All tests are pure-Python with mocked exchanges; no live network calls. Run with
`cd backend && pytest -q`.

---

## Out of scope (deferred)

- Multi-account routing across exchanges (single Delta India account v4).
- Cross-exchange arbitrage signals.
- WebSocket fill streaming (REST polling is sufficient).
- Live order routing outside of paper/shadow modes.

---

## Track Routing System (v4 Shipped)

### config/tracks.yaml

Per `(instrument, profile)` → ordered list of track names. Orchestrator evaluates all tracks and picks the highest-scoring winner:

```yaml
routes:
  BTC:
    btc_scalping_5m:   [vcp, trend_following]
    btc_scalping_15m: [vcp, trend_following]
    btc_scalping_30m: [vcp, mean_reversion]
    btc_intraday_1h:   [vcp, trend_following]
    btc_intraday_4h:  [vcp, trend_following]
  ETH:
    eth_scalping_5m:   [vcp, trend_following]
    eth_scalping_15m:  [vcp, trend_following]
    eth_scalping_30m:  [vcp, trend_following]
    eth_intraday_1h:   [vcp, trend_following]
```

### Tracks

| Track | Engine | Logic |
|-------|--------|-------|
| `vcp` | `VCPTrack` | Volume concentration profiles, structure breaks, range-break confirmations |
| `trend_following` | `TrendFollowingTrack` | ST flip + RSI + squeeze + volume + HA alignment |
| `mean_reversion` | `FadeExtremesTrack` | Fades extremes in ranging/trending regimes |

### Signal Table Track Filter (Frontend)

The signal table (`SignalsTable.tsx`) shows a track pill row:
`ALL | VCP (amber) | TREND (green) | REVERSION (purple)`.

Each pill shows the live count of fresh signals for that track. The backend exposes `track` field in `/api/v1/directional/signals` — the winning track name from `DirectionalOrchestrator.run_once()`.

Filter is independent of mode/status filters. Counts refresh every 5s via REST polling.

### Track → SnapshotEntry

`best_track.name` is stored in `SnapshotEntry.track` and returned in both cached and live signal responses.

---

## Two-Axis Trading Control (v4 Shipped)

### algo_mode — Master On/Off

Boolean. Enables/disables ALL auto-trading (directional engine + VCP feeds).

- `algo_mode = true` → `_auto_place_algo_order` fires on `signal_strength == "STRONG"`
- `algo_mode = false` → no auto-trading, manual orders only

### algo_router_mode — Execution Dispatcher

```python
# Backend: app.state.algo_router_mode  (persisted in SQLite via db.set_config)
# Default on startup: get_config("algo_router_mode") or "live"
```

| Mode | Exchange call | Paper position | Use |
|------|--------------|----------------|-----|
| `paper` | NO | YES | Simulation |
| `shadow` | YES | YES | Live audit |
| `live` | YES | NO | Production |

### UI Components

- **LiveControlPanel**: 3-way mode selector. Calls `POST /api/v1/trading/algo-router-mode` on change. Dispatches `sterling-router-mode-change` custom event for same-tab sync.
- **PaperLiveToggle**: 3-way PAPER/SHADOW/LIVE toggle. Operates on exchange `is_paper` flag + credentials. SHADOW = `is_paper=true` + keys stored.

Both components must be in sync — `LiveControlPanel` is the authoritative source for the backend mode.

---

## VCP Live Feeds (v4 Shipped)

9 active feeds: BTC × 5m/15m/30m/1h/4h + ETH × 5m/15m/30m/1h. All routed via `tracks.yaml` to `[vcp, trend_following]`.

VCP feeds connect to Delta India WebSocket and auto-trade via `VCPExecutor.on_bar()` → `OrderRouter.submit()`. Require `vcp_mode = true` in addition to `algo_mode = true`.

---

## Versioning

- v1: paper-only single asset.
- v2: multi-instrument + alerts + webhooks.
- v3: unified options/futures engine, hard score gates, IVR-driven routing.
- **v4 (this doc)**: live OrderRouter, track routing, VCP hybrid, paper/shadow/live dispatch.
