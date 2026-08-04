# Sterling — Project Memory

This document is the narrative counterpart to `docs/ai/phases.md`. Where phases.md is a dated timeline of what shipped, this file is the **why**: the decisions and reasoning behind them, the approaches that were tried and cut, the surprising findings, and the lessons that now shape how work gets done on this project. It also documents how Sterling's own runtime state and memory mechanisms work — the pieces of the system that persist, cache, or recall information across requests and restarts.

Where a topic overlaps a shipped feature covered in phases.md, it's referenced here only loosely by name — the point of this file is the reasoning, not the changelog entry.

---

## Part 1 — Decisions, Dead Ends, and Lessons

### The recurring meta-lesson: never trust a single-window backtest

The single most repeated lesson across this project's history is: never trust an in-sample or single-window backtest, and always check IS→OOS correlation before shipping a strategy idea.

This was learned hard in the original Triple-ST slot. The first spec was a momentum rule (`close>SMA50 & close>EMA7 & RSI(2)>ADX(2)`) that looked plausible on its face. A 144-config sweep across 25 coins with a 50/50 IS/OOS split showed IS↔OOS profit-factor correlation of **−0.73**, with 0 of 58 in-sample-profitable configs staying profitable out-of-sample — a textbook overfitting signature. By contrast, Connors-style RSI(2) mean-reversion (buy RSI(2)<10 in an uptrend, exit RSI(2)>70) was robust: PF ~2.7–3.0, profitable in both time-halves, with graceful degradation across threshold choices.

This became the standing methodological bar — "validate with the cross-symbol + OOS-split harness before trusting it" — and was explicitly invoked again for:
- the scalping optimizer, where a fragmented grid search showed IS↔OOS PF correlation of ≈ **−0.65 / −0.49**, and was rejected in favor of a pooled per-timeframe study;
- the DSR-deflation work on the regime book, which repeatedly used IS→OOS rank correlation as its central honesty check.

### Why 4h is the load-bearing timeframe

Multiple independent efforts converged on the same finding: any timeframe under roughly an hour dies to transaction costs.

- The edge-discovery matrix (270 configs: 3 symbols × 6 timeframes × 5 strategies × 3 profiles) found only **10/270 net-profitable**, almost all clustered at 4h.
- The SterlingV2 fee-cliff analysis found mean $500-account outcomes by timeframe of $0 (5m), $14 (15m), $66 (30m), $141 (1h), and **$402 (4h)** — only 4h was tradeable.

This is now treated as close to settled fact rather than a preference, and the same underlying logic ("costs dominate below an hour") reappears in the Kite strategy audit, even though the Kite exit-mode sweep itself was run on 1H signals.

### Rejected and dead-end approaches

A consistent pattern in this codebase: plausible-sounding fixes get tested against real data and killed when they don't hold up. This is treated as a badge of rigor, not a failure.

- **Regime-adaptive ATR stops** — tested via A/B, hurt performance (MA Crossover Sharpe 1.83 → 1.36) despite sounding sensible. Fixed ATR stops were kept.
- **Breakout strategy** — rejected twice. First as a chase-entry design (44/44 stop-outs). Rebuilt as a retest-entry (commit `519dc49`) and still lost — 4–7% win rate, −85% to −96% — over 13.5 months of data. Conclusion: the intraday near-4H-level breakout framework doesn't work at all; the only surviving breakout edge is a distinct 4h channel variant.
- **Re-entry cooldown** — added to stop a perceived churn problem in mean-reversion scalping. Backtesting showed any cooldown collapsed the book's PnL (mean_reversion +123R → +13R). Lesson: rapid re-entry *is* the mean-reversion edge, not a bug; a losing cluster around May 30 was variance, not a structural flaw. Reverted to opt-in / default-0.
- **Trailing exits on the regime book** — rejected. On the strong base, a fixed wide bracket (TP 4.5×ATR) beat every trailing variant, because trailing chopped the fat winners the mean-reversion sleeve depends on.
- **Breadth via 24-coin pooling** — tested and found negative. Sharpe fell versus the 3-coin book (1.15 → 0.69) because the added coins were ~0.8-correlated with the core three — "more n, not more info," a correlation wall. Cross-sectional momentum and reversal sleeves also both lost badly OOS.
- **Funding-rate contrarian sleeve** — built and measured with the same DSR-deflation harness, then killed: 0/8 OOS-positive cells, IS→OOS correlation −0.33 (overfit signature), and combining it dragged the main book's DSR from 0.327 down to 0.065. Reasoning: funding extremes mark capitulation/squeeze points where a fresh contrarian trade gets run over, and the existing regime gate was already shorting downtrends — so funding added correlated risk rather than independent information.
- **Cross-market expansion to Indian indices (NIFTY/BANKNIFTY)** — tested and found negative; the regime-book engine is not market-agnostic (NIFTY OOS −13.5%, IS→OOS corr −0.87). The edge was concluded to be crypto-specific; equities would need a re-fit, not a config change. Notably, this was pushed through despite explicit user pressure to find validation ("million users... you have to get convinced") — the assistant held the line and reported the negative result rather than manufacturing conviction.
- **Naive leverage scaling** — Sharpe is leverage-invariant up to ~2x on the regime book, but past that, compounding return falls while drawdown explodes (vol drag). Rejected as a "free lever."
- **Multi-book expansion (SterlingV2 Stack B, adding breakout + smc)** — rejected because breakout was a consistent OOS loser (Sharpe −1.47 to −0.92) that dragged portfolio Sharpe negative and failed the OOS-Sharpe / p-loss / DSR gates — even though it hit the 100-trade sample-size target that the single-strategy Stack A missed. The chosen remedy was to keep accruing real paper trades rather than pad the book with a weak strategy just to satisfy a trade-count gate.

### What did work, and why it was kept

For the regime book, three additive layers compounded into the best validated result on the project:

- **Symbol pooling (3-coin)** — the "cleanest win, zero knobs": max drawdown improved −50% → −26%.
- **Regime gate** — ADX(14) + SMA(50)-slope, running momentum in trend / mean-reversion in range / shorts in downtrends — flipped a losing book to +17.4% / Sharpe 0.60, beating HODL on both return and drawdown.
- **Vol-target sizing + CONVICTION concentration** (deep-RSI mean-reversion selected in-sample, read out-of-sample) — pushed this further to +43.2% / Sharpe 1.15, with a genuinely predictive IS→OOS rank correlation of **+0.38** — explicitly contrasted with the −0.65/−0.73 correlations seen in the overfit strategies above, used as the argument that this combination was not overfit.

The **full-cycle stress test** extended data back to 2020 (to include the 2020–21 bull) specifically to counter the objection "this book has never seen a bull market." It survived: +150.7% OOS vs. basket HODL +92.8%, DSR improved from 0.327 to 0.394 purely from more data/regimes (not new tuning), and IS→OOS correlation rose to +0.82.

Despite all of this, the project holds a hard, repeatedly-restated line: **DSR (deflated Sharpe ratio) never cleared 0.5 anywhere.** The edge was treated as "forward-green and HODL-beating" but never declared "statistically provable," and was kept paper-only and isolated from the live SterlingEngine rather than promoted — described explicitly as avoiding a "faith-deploy."

### The brutal-audit findings

A 2026-06-06 adversarial self-audit found that the Grok/directional engine was mostly theater:

- 15 of 17 modules under `engines/directional/` were literal stub files (`# STRATEGY STUB`).
- `compute_signal` always returned a constant score=85/STRONG from a trivial `close>EMA20` check.
- `regime_engine` computed a fake ADX as `10.0 + int(close)%30` — i.e., derived from the last two digits of the price.

These fabrications were wired live into the Grok signal feed and position monitoring. `STERLING-V4-SPEC.md` was found to be aspirational fiction — it described a `scoring.py` module and portfolio-cap logic that did not exist in the codebase.

Fixing the two core stubs (signal_engine, regime_engine) with a real ADX/RSI/SMA-slope implementation immediately **exposed a second, previously-hidden bug**: the candidate tables went empty, because the honest signal engine no longer fabricated a constant fake trend, and a downstream `evaluate_setup` gate had been silently relying on that fabrication to arm trades. Lesson: a stub can mask a real structural gap, and de-stubbing can make things look *worse* before a fix is complete. Restoring candidate flow took multiple layered patches (profile defaults, market-context fallback, instrument-key normalization) over two days.

Separately, this same audit built a fresh real-data HODL benchmark and used it to correct its own earlier draft claims — an initial belief that BTC "tripled" over the period was wrong (real figure +72%, not +150%), and an initial assumption that the validated strategy "almost certainly underperforms HODL" was also refuted (the BTC 4h MA-crossover intraday variant did beat HODL on both return and drawdown). Logged as a case of the audit process correcting itself against real data rather than defending a fixed prior.

### Sizing and PnL bugs — pattern of "display bug, not real bug"

Several investigations that looked like severe risk-sizing problems turned out to be display/reporting bugs rather than real exposure problems:

- The Risk% column showing "0.00%" was traced to dividing by a hardcoded $100k account size instead of the real ~$500 NAV. Fixed via a pure helper + backfill script — with the caveat that a running live process holds positions in memory and will silently revert a backfill on OPEN positions unless the backend is stopped first.
- An apparently alarming "$2.7M notional / 54% capital-at-risk" scalping alert was diagnosed as a display artifact of a legitimately large position size against a tight stop, not real overexposure.

The one **real** bug in that investigation was a trailing-stop-loss overshoot: the background monitor polled on an interval and closed positions at poll-time spot rather than at the stop price, silently booking the entire polling interval's drift as slippage — a breakeven-protected stop that should have closed near $0 instead lost $896.

A separate, more dangerous latent bug — **contract-value lot sizing** — was a genuine 100× valuation risk: sizing math had conflated exchange "lots" with underlying coin quantity, causing sub-1-coin positions to floor to zero (silent `size_too_small` rejections) and creating a latent notional-miscalculation risk everywhere `.contracts` was used instead of `.qty`.

### Kite-side reversals and evolving beliefs

Worth flagging as genuine changes of design or belief, not simple bugfixes:

- **Chart-state persistence design was explicitly reversed mid-project.** The original (2026-07-17) design persisted chart config per-symbol. The very next day the user said "chart config including zoom should be same throughout," and the whole model was rebuilt around one shared global KV blob with only drawings staying per-symbol — a deliberate reversal, not a bugfix.
- **The Kite Triple-SuperTrend `scan_source` default flip-flopped across sessions**: originally spot, found to have silently drifted to `derivatives` by 2026-06-15, then deliberately flipped back to `spot` on 2026-07-16 after an audit concluded spot was "the only validated signal source" (delta-1 OOS positive on 4/4 indices) while derivatives mode was "structurally unvalidatable" (expired option premiums can't be refetched for backtesting).
- **The real-money hardening pass (2026-06-20) corrected an earlier, wrongly-reassuring belief.** A prior memory had described the Kite engine's trailing stop as "advisory." The hardening review found the auto-executed BUY orders had genuinely no broker-side stop attached at all (the stop-loss parameter was silently dropped for market orders) — a materially worse finding than "advisory" implied.
- **The strategy audit found a further contradiction between intent and code**: even where a stop nominally existed, a monotonic ratchet rule rejected the intended "step out to a wider trail line" behavior, so the effective live exit behaved like the tightest exit mode regardless of configured setting. This was later empirically resolved by actually running the shelved exit-mode sweep scripts, which showed the tightest mode ("one_red") was in fact best on real data — changing the default to match reality rather than forcing the originally-intended looser behavior.

### Process and collaboration lessons

Two standing behavioral lessons were recorded independent of any specific code change:

1. **Action over formal option-forming.** The user rejected a light/dark-theme `AskUserQuestion` fork and said "tune to our app." The recurring feedback is to pick a defensible default, state it in one line, and proceed — reserving explicit multi-choice questions for forks that materially change the deliverable with no sensible default — while still surfacing honest caveats (DSR<0.5, no live backtest, fallback rates) unprompted.
2. **A UI "rework" must change structure, not just restyle.** When asked to rework or upgrade a UI, a restyle of the existing layout reads to the user as "no diff." A genuine rework must collapse, merge, or reorganize bands and promote/demote content — and it's more effective to present two sharply different mockups to react to than to iterate on a single one.

### Architecture-hardening philosophy

The modular-architecture-hardening effort explicitly discovered that 60–70% of the "plug-and-play broker/strategy" architecture it set out to build already existed (broker ABCs, 5 adapters, an adapter factory, a fully safety-gated OrderRouter, 153 tests). The actual work was reframed from "rewrite" to "formalize, document, and additively infill," proceeding in small phases each proven zero-regression via diff-vs-baseline rather than raw pass counts — because the suite has known order-dependent flaky tests, so absolute pass counts are not a trustworthy regression signal.

---

## Part 2 — Runtime State & Memory Mechanisms

This section documents how Sterling's own running system remembers things — the persistence, caching, and reconciliation mechanisms that make it behave correctly across requests, restarts, and remounts.

### CalibrationService (adaptive win-rate / IVR)

Introduced in the Sterling v3 upgrade as `app/services/calibration.py`, persisting adaptive win-rate and IVR-percentile state to SQLite via the `calibration_state` and `calibration_trades` tables.

**Standing invariant** (in CLAUDE.md, honored across later work): `CalibrationService.record_trade()` must be called on **every** paper_store position close, and call sites must inject `CalibrationService` via `Depends(...)` rather than importing it directly.

The Sterling-only consolidation (2026-06-03) explicitly kept this service and its endpoint/panel wired into the terminal even while deleting the CALIBRATION browsing tab — the tab UI was removed, but the recording mechanism was preserved because other surfaces (the pro Terminal's BottomPanel/StatusBar) still depend on it.

### Singletons on `app.state`

The project maintains a fixed set of named singletons, with an explicit distinction between two circuit breakers that must not be confused:

- `app.state.circuit_breaker` — the **execution-level** breaker.
- `app.state.dd_circuit_breaker` (`DrawdownCircuitBreaker`) — the **drawdown-level** breaker introduced in v3. Standing invariant: `DrawdownCircuitBreaker.update()` (alias `CircuitBreaker`) must run **first** inside `evaluate()`.
- `app.state.correlation_tracker` (`CorrelationTracker`) — `.update()` must be called with 1H closes on every `evaluate()`, another standing invariant.
- `app.state.calibration_service` — see above.

Later derivatives/edge work added its own `app.state` caches following the same pattern:

- `app.state.derivatives_scan_cache` — populated solely by the background scanner, read-only for endpoints. Introduced specifically to fix an event-loop-starvation bug where synchronous full-universe scans were blocking all endpoints.
- `app.state.edge_registry` — loaded from `backtest_edge_results.csv`, invalidated on `POST /derivatives/edge-gate`.
- `app.state.edge_gate` — the operator-tunable EdgeGate thresholds.

### Kite chart-state KV persistence (the most-iterated runtime-state mechanism in this codebase)

Backend storage is a raw key-value blob (`app_db.set_config`/get), originally keyed `kite_chart_state_{user_id}_{symbol}`, now a single `__global__` key per user, exposed via `POST/GET /api/v1/kite/chart-state/{symbol}` in `backend/app/api/v1/endpoints/kite.py`.

The save endpoint does a **full replace with no merge** — any field sent as `null` overwrites the stored value. This is a durable trap: any time a new field is added to the persisted shape (e.g., the `drawingsBySymbol` map added for per-symbol drawings), it must be added to **both** the POST whitelist **and** the GET `setdefault`s, or the new field is silently dropped on the next round-trip.

As of 2026-07-18, the blob's shape is: global chart config (timeframe, active indicators, params, Heikin-Ashi flag, log-scale flag, volume-profile flag, and zoom) shared across every symbol, plus a `drawingsBySymbol: {[symbol]: Drawing[]}` map that remains per-symbol.

A frontend module-level cache, `globalChartStateCache` (with a `__resetGlobalChartStateCache()` test-only hook), is loaded once by the first GET and updated synchronously inside `saveChartState`. Lazy `useState` initializers read this cache so that a component remount (specifically the Mac-motion-mode `MacSectionFade` remount that fires on every symbol switch) reseeds instantly from memory instead of racing a fresh GET against a just-flushed POST to the same `__global__` key. This in-memory cache is the fix for a same-key race that the move to a single global key introduced.

A related guard, the last fix in that lineage: if the mount-time GET for `__global__` throws, the code must `return` from the catch block (not swallow-and-continue) so `chartStateLoaded` stays `false` and the save-on-change effects never fire with default values. Without this guard, a transient load error would trigger a full-replace POST that clobbers whatever real state was actually stored.

Saves are debounced 700ms behind a single shared timer ref, with a `flushSave()` / `pendingSaveRef` mechanism that fires the pending save immediately on unmount, and a page-unload path that hooks `pagehide` + `visibilitychange`→hidden to force a `keepalive` POST so state isn't lost on tab close. `signalData`-triggered chart opens are treated as transient and explicitly skip the save path, so that opening a signal's 1H/Heikin-Ashi view doesn't get persisted as if it were the user's chosen global config.

### Kite OI (open-interest) baseline caching

Kite's quote API has no change-in-OI field and no intraday OI-history endpoint, so delta-OI is computed entirely on the frontend against a rolling day-baseline cached in `localStorage` under the key `kiteOiBaseline:{underlying}:{expiry}:{IST-date}`. The first OI snapshot seen each day becomes the reference point, diffed against each subsequent poll (~15s). This is explicitly a client-only, non-durable cache (resets at midnight IST by construction of the key) and is labeled honestly in the UI as "since first snapshot today" rather than "since previous close."

### Paper-trade position/PnL tracking

The core store is `paper_store`, backed by the live `backend/sterling_paper.db` (~3GB).

- `close_position` was found to multiply futures PnL by leverage (a real overstatement bug, fixed in Derivatives Selector Phase 0), and is the canonical call site that must invoke `CalibrationService.record_trade()`.
- Position sizing correctness depends on the `SizedTrade.contracts` (exchange lot count) vs. `SizedTrade.qty` (`contracts × contract_value`, actual coin quantity) distinction — any code path computing value/risk/PnL/notional/Greeks-notional must use `.qty`, never raw `.contracts`. `contract_value` is sourced from `DeltaIndiaAdapter.get_contract_value`, which must be fetched via the raw unwrapped adapter (`_adm.get_raw_adapter()`) because the Caching/RetryingAdapter wrappers don't proxy that method.
- `capital_at_risk_pct` is computed per-position at add-time from real account equity (not recomputed later) — a backend restart is required after any correction to that formula for it to reflect on already-open positions.

On the Kite side, a parallel but separate registry exists:

- `kite_engine/positions.py` is a DB-persisted open-position registry (key `kite_engine_positions_{uid}`) that is the source of truth for stop management, order-update reconciliation, and sizing. Its `should_exit` is a pure function, and stops are enforced to only ratchet upward (`update_stop`, never loosens).
- Auto-open state is guarded by a separate DB-persisted key (`kite_engine_auto_open_{uid}`), reconciled against the broker's live `GET /positions` on startup (before the auto-scan loop starts), so a server restart can't cause double-entry.
- Kite's daily realized PnL (feeding the crypto-only daily-loss breaker logic — deliberately not applied to Kite/INR) is persisted under `kite_engine_daily_pnl_{uid}`, mirroring the auto-open-guard pattern, specifically because an earlier in-memory-only version zeroed out on a mid-day restart.

### Operational safety / kill-switch (research paper trader)

A separate, isolated `study/paper_trader.py` mechanism (not wired to the live SterlingEngine) persists its own state atomically to `data/paper/state.json` (write to tmp file, fsync, then `os.replace`), plus an append-only `trades.csv`.

`study/paper_safety.py` layers a drawdown kill-switch with hysteresis on top:

- `update_kill_switch` / `apply_kill_switch` trip the book flat and drop open positions when forward equity falls a configured threshold below its high-water mark, then only re-arm once equity recovers within a smaller band.
- An exclusive `flock`-based `run_lock` prevents concurrent state mutation.
- A `should_run` check enforces exactly-once-per-bar execution by recording the last-processed bar timestamp in state.

This breaker acts only on the paper trader's own recomputed book, not on any real broker equity feed.

### Client/connection-level caches (performance, not trading state, but load-bearing)

Kite's `kite_accounts.acquire_client()` / `release_client()` pattern maintains one warm `KiteClient` per account id, rebuilt only when encrypted credentials change, specifically to preserve its `InstrumentCache` (an in-memory parse of Kite's ~80k-row instrument dump) and its httpx connection pool across requests.

**Standing invariant:** never call `build_client()` on a hot/per-request path — doing so was the root cause of a 2-minute instrument-search regression. `InstrumentCache.load()` uses a per-key `asyncio.Lock` to deduplicate concurrent cold fetches.

### Other durable DB-backed state

- `wf_results`, `parameter_sensitivity`, `calibration_state`, `calibration_trades`, and `equity_snapshots` tables (introduced in v3).
- A background sensitivity sweep that runs at startup and weekly, cached for 7 days (a standing CLAUDE.md invariant).
- From the modular-architecture-hardening effort: an additive SQLAlchemy persistence layer (`app/persistence/`) with dual-write mirroring (`sync.py`, generic `MirroredRecord`) into ORM tables for positions, equity-snapshots, pnl-history, alerts, webhooks, exchange-accounts, calibration, and derivatives-audit — gated behind a `use_sqlalchemy` flag that was still OFF in production as of the last recorded update. This dual-write path was built as a safety net for a future cutover, not yet the live source of truth.