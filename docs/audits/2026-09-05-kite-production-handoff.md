# Sterling Kite Engine: production audit and AI implementation handoff

Date: 2026-09-05. Scope: Sterling Kite Engine, including spot, derivatives and confluence signals, option/futures execution, protection, replay and operator UI. Navigator remains an optional integration, not a replacement strategy.

## 1. Decision and evidence boundary

**NO-GO for live promotion.** This audit implemented safety changes; it did not establish positive net expectancy or complete production certification. No live order, account-mode change, deployment or parameter optimization was performed. Do not interpret this document, passing unit tests, historical comments saying “validated”, or the existing auto-exec toggle as permission/evidence to activate capital.

Concrete release blockers: failing broader regression suite; incomplete transactional fill/PnL accounting; ambiguous order recovery; unverified current executable contract data; incomplete quote freshness/mandatory risk gates. The connected lake's registered removable-drive path was unavailable during inspection. The available index cache ends **2026-07-16**, before CAS commenced.

Labels used below:

- **EXCHANGE-VERIFIED:** facts checked against exchange/regulator publications.
- **IMPLEMENTED:** code changes present in this checkout; verification limits still apply.
- **STERLING-DESIGNED:** engineering policy, not an exchange mandate or measured alpha.
- **CALIBRATION-REQUIRED:** profitability, liquidity or execution assumptions not demonstrated by available data.
- **REMAINING:** work required before promotion; never represent it as completed.

Original review base: `7ff055e1e30d6d26b33aafb07788e7ad982231aa`. Another workspace process committed most audit edits as `ba1996dc78b0e30bac1639617ef54f9f403cd2f4` during work. Review the entire delta from the original base plus later uncommitted changes. Graph results were stale relative to HEAD; their coverage numbers are navigation hints, not test evidence.

## 2. Verified exchange and broker rules

All times IST; intervals end exclusively for strategy eligibility. Effective dates must remain part of every replay, session decision and expiry calculation.

| Rule | Verified behavior | Engine policy |
|---|---|---|
| Pre-open from 2026-09-07 | 09:00–09:05 market/limit; 09:05 onward limit only; market modification/cancellation unavailable; entry closes randomly during 09:08–09:10; matching starts when entry ends; buffer 09:12–09:15 | No strategy orders in any pre-open phase. Do not infer order acceptance from clock during randomized closure. Futures pre-open eligibility must not be applied to options. |
| CAS from 2026-08-03 | Eligible cash stocks stop continuous trading at 15:15. Transition/reference calculation until 15:20; market/limit entry 15:20–15:25; limit-only phase then random closure during 15:28–15:30; matching finishes by 15:35 | Auctions excluded from continuous signal candles. No auction execution implementation. |
| Other NSE cash | Continuous trading ends 15:30 | Explicit eligibility flag required to distinguish the cash schedules. |
| NSE equity derivatives | Continuous session 09:15–15:40 from 2026-08-03 | NFO monitoring can continue after cash continuous trading ends. Cash-derived origination stops at 15:15. |
| Zerodha MIS | Current published square-off: CAS cash 15:12; other cash 15:25; equity/index derivatives 15:26 | Broker product cutoff overrides exchange close. A 15:40 exchange close does not authorize MIS holding until then. Existing engine futures margin request is NRML. Verify the actual order product end to end. |
| Holidays | 2026 annual NSE list plus January 15 election closure | New-entry calendar covers 2026; unknown years close entry eligibility. Special sessions are not assumed regular sessions. |

Primary references, checked 2026-09-05:

1. [SEBI January 16 circular: CAS and pre-open](https://www.sebi.gov.in/legal/circulars/jan-2026/introduction-of-closing-auction-session-cas-in-the-equity-cash-segment-and-certain-modifications-in-the-pre-open-auction-session_99122.html).
2. [NSE CAS operating page](https://www.nseindia.com/static/products-services/closing-auction-session), including circular references CMTR/74466 and FAOP/74467. Some direct archive fetches failed; indexed primary content and the operating page supported the rules.
3. [NSE derivatives pre-open](https://www.nseindia.com/static/products-services/equity-derivatives-pre-open-session), updated September 4.
4. [NSE current timings and holidays](https://www.nseindia.com/resources/exchange-communication-holidays). This page spans multiple segments; do not merge settlement/banking holidays into the equity trading list.
5. [NSE annual equity holidays CMTR/71775](https://nsearchives.nseindia.com/content/circulars/CMTR71775.pdf) and [January 15 addition CMTR/72260](https://nsearchives.nseindia.com/content/circulars/CMTR72260.pdf).
6. [Zerodha MIS cutoffs](https://zerodha.com/marketintel/bulletin/249809/latest-intraday-leverages-mis-bo-co).
7. [Zerodha April 2026 STT revision](https://zerodha.com/marketintel/bulletin/445377/revision-in-stt-securities-transaction-tax-from-1st-april-2026) and [STT calculation](https://support.zerodha.com/category/account-opening/resident-individual/ri-charges/articles/how-is-the-securities-transaction-tax-stt-calculated).

**BSE limitation:** the implemented timing module retains the old BSE/BFO 15:30 bound. Its separate notices, CAS eligibility and holiday coverage are not independently certified here. Do not promote BSE/BFO execution using this NSE audit. The calendar's shared holiday assumptions also need separation before BSE certification.

## 3. Actual data audit

Machine-readable results: [2026-09-05-kite-real-data-audit.json](2026-09-05-kite-real-data-audit.json). Reproducer: `backend/study/kite_production_audit.py`. Input arrays were read without modification; hashes record the exact bytes examined. No generated premiums or manufactured market series were used in this evidence run.

| Instrument | Raw bars | Invalid OHLC/volume bars | Signal prefix violations | Exit indices changed by raw versus HA extrema |
|---|---:|---:|---:|---:|
| NIFTY 50 | 13,029 | 0 | 0 | 3 |
| NIFTY FIN SERVICE | 13,029 | 0 | 0 | 4 |
| NIFTY BANK | 13,029 | 0 | 0 | 2 |
| SENSEX | 12,976 | 0 | 0 | 5 |

Total: **52,063 bars**, **404 sampled prefix checks**, **2,275 entry/exit comparisons**, **14 changed exit indices**. Exit comparison horizon: at most 240 following bars. It isolates the extrema change while keeping the current exit implementation otherwise constant; it is not a full comparison against the original commit. No prefix failures in a sample is not proof of every possible input.

All caches end July 16, 2026. Post-CAS bars: **0**. Index volume can legitimately be zero; it must not be treated as executed option volume. Files were produced by the existing Kite history-cache workflow, but lack original response receipts, acquisition manifests and independent vendor validation. They establish observed-cache behavior, not independently certified market provenance.

**No Sharpe, winning strategy selection, option profitability or go-live return claim is supported by this dataset.** An index is not an option or futures fill. Earlier Black–Scholes “options lens” sweeps are modeled research and cannot satisfy the user's real-data-only promotion requirement.

## 4. Final strategy contract

Preserve current three SuperTrend parameters `(21,1)`, `(14,2)`, `(7,3)` and configurable HA/raw indicator basis until a valid chronological study demonstrates an improvement. These parameters are existing choices, not proven optima. Entry requires a fresh full alignment transition after warmup. Options remain long premium: bull cash signal selects CE; bear cash signal selects PE. Futures alone carry short exposure directly. Contract-premium derivative signals have their own direction in premium space.

Decisions use finalized candles. HA may define indicators; raw traded prices establish order execution/stop touches. Check the previous completed bar's stop against the next bar's raw extrema; a same-bar revised stop is lookahead. Stops may tighten but must not widen after entry. Closed-bar counter exits and resting price stops are separate event types.

STERLING-DESIGNED operating policies implemented: no auctions; no unknown-year entries; no previous-day or unfinished signal entries; fresh signal age within ten minutes after a full one-hour bar closes; serialize account entry callbacks in one process; unknown capital or invalid stop sizes to zero; unresolved exits/PnL halt further origination. Ten minutes reflects scan/cache operations, not a measured trading advantage. Final shortened session bars are finalized for analytics but cannot authorize entries after the market has closed.

REMAINING: unify every consumer on the same session-aware bar-end resolver, including partial final bars, chart preparation, historical premium attribution, index close/CAS observations and expiry-day stops. The scanner applies its new session clipping from the CAS effective date; earlier historical records retain the old duration path. Date-effective symbol eligibility and separate CAS datasets remain necessary.

## 5. Artifact-by-artifact implementation inventory

Paths below are repository-relative. Treat this table as a precise work map; inspect the current diff before editing because other tasks share the checkout.

| Artifact | Implemented behavior | Remaining acceptance requirement |
|---|---|---|
| `backend/app/services/kite_engine/market_hours.py` | Versioned NSE policy, 2026 holidays, aware timestamps, exclusive close, pre-open/CAS phase labels, date-effective NFO close, cash-source entry cutoff | Primary-source refresh workflow; 2027 and special sessions; instrument eligibility snapshots; separate BSE policy; broker product cutoff resolver; operational observability |
| `backend/app/services/kite_engine/scanner.py` | Removed execution uses of `allow_forming=True`; common scan snapshot time; rejects nonfinite/nonincreasing/impossible OHLC; short final bars and new-session auction clipping | Full interval continuity/gap checks, stale data reasons in response, true candle revision/finality contract, cash-index CAS semantics, short-bar entry premium attribution |
| `backend/app/engines/sterling_kite_engine/regime.py` | Carries raw high/low separately from indicator-basis prices | Raw OHLC validation at every direct engine/replay entrypoint; freeze hashes of indicator implementation in evidence |
| `backend/app/engines/sterling_kite_engine/exits.py` | Raw extrema for stop touches; monotonic stop within exit search | Ratcheted stop level must also be used consistently in displayed/reported reason and all replay branches; special cash-to-premium translation remains approximate |
| `backend/app/engines/sterling_kite_engine/engine.py` | Tracks entry timestamp; management delegates to shared exit resolver | Incremental versus batch parity after skipped calls/lookback eviction; same-bar reprocessing; stock theta-stop scope parity |
| `backend/app/services/kite_engine/sizing.py` | Invalid/missing/nonfinite inputs block; no default lot on unknown capital or invalid stop; affordability cannot be bypassed by min-lot risk override | Remove futures 15% estimate entirely in favor of per-order broker margin input; exact decimals/tick/lot rules; fee and gap risk; portfolio capital reservation |
| `backend/app/services/kite_engine/service.py` | Entry data/session gate before work and before send; account callback lock; enabled liquidity failures block; exact final futures quantity checked through broker margin endpoint; pending exit history polling; unresolved PnL/exit entry block | Mandatory risk/quote freshness independent of optional filters; multi-process durable idempotency; account generation checks; unknown ACK recovery; no assumed IV for live premium stops; short-side reconciliation; complete manual-entry parity |
| `backend/app/services/kite_engine/positions.py` | Persists exit order ID, cumulative exit fills and PnL-reconciliation flag | Transactional durable journal; persistence failures currently swallowed; generation identity; per-order cumulative fill accounting and schema migration |
| `backend/app/services/kite_engine/monitor.py` | ACK no longer closes/bookmarks PnL; pending/unknown exit prevents resend; attributable confirmed fills consume quantity; duplicate quantities ignored; partial exit retains remainder; unknown orders defer reconciliation | Partial-fill financial accounting, accepted-but-timeout recovery, external/GTT child-order attribution, protection re-arm on rejection, fill quantity/value corrections, crash atomicity, price/timestamp freshness |
| `backend/app/services/kite_engine/detail.py` | Date/venue-dependent expiry close for fractional DTE | Scanner/service helpers still contain day floors/defaults; unify DTE everywhere; remove stale 15:30 comments; certify BFO expiry rules |
| `backend/app/services/kite_engine/backtest.py` | Raw next-open premium entry; next-open close-derived exit; gap-aware stop estimate; raw input checks; cash affordability; dated STT; GST includes SEBI fee; removed spurious daily annualization of trade returns | Effective dates for all fees; IPFT/exercise/physical settlement; expiry identity; unresolved end-of-series holdings; quote-based execution; bid/ask and fee stress; portfolio replay; invalidate older synthetic evidence |
| `backend/app/api/v1/endpoints/kite_engine.py` | Registry deletion requires broker-confirmed flatness; returns pending-exit/PnL flags | Complete API contract tests; no force bypass of readiness; return machine-readable readiness reasons, policy/config/data version |
| `backend/app/engines/sterling_kite_engine/schemas.py` | New `exit_pending` and `pnl_reconciliation_required` response fields | Explicit submitted/part-filled/unknown/reconciliation states; strict finite config validation; stop-mode and product constraints |
| `frontend/src/types/kiteEngine.ts` | Mirrors optional exit/PnL flags | Durable readiness response types and migration coverage |
| `frontend/src/components/kite/EnginePositionsPane.tsx` | Shows “Exit awaiting fill” and “P&L reconciliation required” | UI interaction test: pending remains visible; repeated exit disabled; no claim that ACK means flat |
| `frontend/src/components/kite/BacktestPane.tsx` | Renamed old “Sharpe” output to “Trade return ratio” | Daily mark-to-market equity and correctly defined Sharpe before restoring that label; visibly non-promotable synthetic runs |
| `backend/tests/engines/sterling_kite_engine/test_production_audit.py` | Session boundaries, malformed bars, no HA-only fills, next-open replay, sizing failures, exit ACK/partial/duplicate behavior, STT dates, liquidity evidence | Broader state-machine/crash/restart/time-boundary suites; actual broker sandbox/captured postback contracts |
| Existing execution/scanner test fixtures | Historic execution fixtures isolate new entry-data dependency; positive low fixture avoids impossible zero price | Migrate old tests that expect one lot on missing capital or immediate closure on ACK. Preserve meaningful protection/race assertions; do not weaken code to satisfy unsafe expectations. |
| `backend/study/kite_production_audit.py` | Read-only hash/integrity/prefix/stop-impact report from actual caches | Acquire immutable post-CAS contract datasets with manifests; independent data-source comparison; replay actual tradable vehicles |
| `docs/audits/2026-09-05-kite-real-data-audit.json` | Machine-readable source/code hashes and measured audit counts | Regenerate after relevant strategy code or input data changes; retain prior versions for provenance |
| `docs/audits/2026-09-05-kite-validation.json` | Exact verification snapshot, commands and failing test IDs | Release requires zero unexplained failures across core and affected integrations |

## 6. Required production lifecycle

Implement one durable state machine per account, instrument, strategy and position generation:

`INTENT_RESERVED → ENTRY_SUBMITTED/ENTRY_UNKNOWN → PARTIALLY_FILLED → OPEN_PROTECTED → EXIT_SUBMITTED/EXIT_UNKNOWN → PARTIALLY_EXITED → FLAT_RECONCILED`.

Rejection/cancellation changes order status; it does not prove position quantity is zero. Timeout means unknown outcome, not permission to retry. Broker net position is evidence of exposure, not attribution to one strategy or trade. Resolve order IDs using strategy/client intent tags and the broker order book before sending again.

In one database transaction, ingest `(account, order_id, exchange_trade_id)` once, update cumulative quantity/value, update position quantity/average cost, book exact realized PnL/fees, update risk reservations, and enqueue state/event delivery. Keep exchange and receive timestamps. Reject stale-generation fills. For order updates with cumulative averages, derive incremental value from cumulative value differences; never multiply the latest cumulative average by just the newly filled quantity.

Crash tests must cover every boundary between reservation, send, ACK, persistence, fill delivery, protection placement/cancellation and exit. A duplicated/out-of-order postback must not double-book PnL or create an opposite exposure. Broker-protection rejection requires confirmed replacement or explicit unprotected-exposure handling; never silently forget the position. One process lock does not solve multiple workers, duplicate service instances or a restart.

## 7. Real-data acquisition and research protocol

1. Restore the registered lake or select an accessible account-authorized storage destination. Fetch read-only broker history and current instrument masters. Store raw payloads, request parameters, server/exchange timestamps, retrieval time, hashes and source identifiers. Do not expose credentials in artifacts.
2. Capture NSE post-August-3 cash continuous bars, separate auction events, NFO options/futures OHLC and timestamped bid/ask depth. Capture September-7 pre-open under the new policy when those events exist; they do not exist as historical evidence on September 5. Preserve absence as absence.
3. Build date-effective universes with listed tokens, expiry, option type/strike, lot/tick size, corporate actions and CAS eligibility. Never select historical strikes from today's instrument master. Respect expired-contract data availability; no Black–Scholes replacement in a real-only run.
4. Split chronologically with a final untouched holdout. Purge/embargo overlapping trade horizons across folds. Freeze the hypothesis/parameter grid before seeing holdout results; log all tested candidates and reject retrospective “best” selection.
5. Replay the actual vehicle using closed-bar decision times and first available subsequent executable quote. Model order type, tick rounding, spread, queue uncertainty, partial fills, gaps, broker RMS rejection and dated costs. Report any OHLC approximation explicitly; OHLC cannot establish intrabar ordering or queue fills.
6. Build daily mark-to-market portfolio equity, including open positions, costs, funding/margin and cash reservations. Report net expectancy, confidence intervals using session blocks, drawdown, loss tails, concentration, turnover, fill/rejection statistics and cost sensitivity. Do not annualize trade returns as daily returns.
7. Compare the unchanged baseline against one justified change at a time. Declare acceptance thresholds and permitted risk budget before calibration. There is no pre-approved profit-factor/sample-size threshold in this audit; do not fabricate one.
8. Use shadow execution on real market events to validate decision and order-intent parity. Paper fills are operational simulations, not proof of live fill quality or profitability.

## 8. Release gates and rollback

All gates required: current primary-source session/calendar coverage; verified contract dataset and untouched holdout; positive robust net edge under predeclared acceptance rules; no unresolved core/affected test failures; transactional fill/risk accounting; startup reconciliation against broker; fresh quote/depth and margin evidence; validated protected partial-fill paths; broker/product/account permissions; operational alerting and tested kill switch.

No autoexec `force` flag can override missing data, unknown exposure, stale policy, unverified margin, failed protection or missing release evidence. On any such condition, block new exposure while maintaining monitoring and confirmed risk-reducing exits.

Deploy only after gates pass. Start with explicitly approved limited capital/position limits and continuously compare expected versus observed fills. On rollback: stop new entries, reconcile and protect existing exposure, preserve order/fill journal and idempotency records, then revert code. Never reset the registry or cancel protection merely to obtain a clean UI.

## 9. Instructions to the next AI

Read root AGENTS.md; use code-review-graph before source exploration. Read this handoff, validation JSON and real-data JSON. Inspect the delta from the original base and preserve concurrent user changes. Use isolated test databases: existing global fixtures clear stored account/config records.

Priority order: (1) classify and repair every regression in validation JSON, preserving new fail-closed semantics; (2) implement and prove transactional lifecycle/ambiguous ACK recovery; (3) unify mandatory execution inputs, premium/DTE/stop domains and policy metadata; (4) acquire the missing real contract/post-CAS data and complete chronological research; (5) wire readiness through API/UI; (6) operational shadow validation and only then controlled rollout.

Do not call this strategy “production ready” while any release gate is open. Report implemented artifacts, exact tests, real measurements and unresolved dependencies separately. Do not tune on generated prices, purchase data, place live orders, deploy, or send external messages merely because this handoff exists.
