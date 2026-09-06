# Sterling Kite Engine — implementation and AI release handoff

Updated September 6, 2026. Scope: the existing three-SuperTrend NSE options/futures strategy. This document supersedes implementation status in the [original audit](2026-09-05-kite-production-handoff.md); its exchange references and historical signal study remain applicable.

## Release decision

**NO-GO for production promotion.** Substantial execution safeguards are implemented and tested. Positive net expectancy on actual executable contracts, transactional realized-PnL accounting and complete operational recovery are still unproven. No live order, account-mode change, deployment or parameter optimization was performed by this audit. Existing runtime toggles are not certification: the registry preflight is narrower than the release requirements below.

Verification counts, commands, outcomes and code hashes are in [validation JSON](2026-09-06-kite-validation.json). Tests use protocol fixtures to prove mechanics; fixtures are never market-performance evidence. Concurrent workspace commits also extracted the Indian-only product. Those unrelated changes are preserved, and whole-repository findings must be attributed to the tested revision rather than this strategy alone.

## Real market evidence

The registered lake drive was attached but unmounted. It was mounted read-only (`ro,norecovery`) and the complete selected-file audit was rerun during final verification; input files were not changed. [CAS report](2026-09-06-kite-cas-realdata.json) and `backend/study/kite_cas_realdata_audit.py` reproduce that audit when the drive is mounted:

| Evidence | Observed result |
|---|---|
| Three actual minute series | NIFTY 50, LT, SBIN; 136,980 bars |
| Post-CAS coverage | 9,855 bars from August 3 onward; selected series end August 13 |
| Integrity/session checks | 366 instrument-session checks; zero invalid OHLC, timestamp-order or session-boundary failures |
| Eligible cash transition | LT/SBIN: July 31 had 375 minutes ending 15:29; August 3 had 360 ending 15:14 |
| Index observations | NIFTY still has 375 minutes through 15:29; 135 post-15:15 observations correctly fail cash-origin entry eligibility |
| Provenance check | All three complete Parquet hashes match the existing lake manifest |
| Broader inventory | Manifest reports 231,143,717 rows across 12,246 symbols, ending August 14; inventory is not full-file verification |
| Missing evidence | No derivative-bar symbols in manifest; no executable option/future replay or post-September-7 observations |

The original four-index study remains separate: 52,063 hourly bars ending July 16, 404 sampled prefix checks with zero violations, and 14 changed exit indices across 2,275 comparisons when raw extrema replace HA extrema. These studies prove observed data/implementation behavior. They do not establish an investable option edge, queue fills, future returns or independent vendor certification. No modeled option premiums were substituted for missing observations.

## Final strategy and session contract

Preserve existing SuperTrend settings `(21,1)`, `(14,2)`, `(7,3)` until real chronological evidence supports a change. Build indicators from configured raw/HA candles; execute stops against raw traded extrema, using the prior finalized stop. Signals require completed bars and fresh alignment. Cash bull/bear signals buy CE/PE respectively; both positions are long premium. Futures may be long or short. Replay decisions execute at the next available raw open; gap and dated cost rules remain explicit.

The policy remains `nse-2026-09-07-v1`. From August 3, eligible NSE cash continuous trading stops at 15:15, CAS ends 15:35, and NFO continuous trading ends 15:40. Cash-origin entries stop at 15:15 even if index observations continue. From September 7, pre-open entry allows market/limit until 09:05, then limit only, with randomized closure during 09:08–09:10. The strategy excludes every auction phase. NSE holidays and effective dates govern eligibility; unknown years fail closed. BSE/BFO policy is not certified by this NSE audit.

Live engine orders use NRML. Live entries now use bounded LIMIT orders, including a market-style manual request; they may remain unfilled. Automatic limits are rounded inward to the actual instrument tick within a 30-basis-point envelope around the observed traded price. This is an engineering price bound, not an exchange mandate or calibrated alpha parameter. Exits retain the broker's market-protection behavior. Manual LIMIT requests preserve their explicitly supplied price and must align with the instrument tick.

## Artifact-by-artifact implementation

Paths below are repository-relative.

| Artifact | Responsibility and implemented behavior | Integration/verification boundary |
|---|---|---|
| `backend/app/services/kite_engine/market_hours.py` | Date-effective continuous, auction, holiday and origination policy | All strategy time gates consume this policy; special sessions/BSE certification remain separate |
| `backend/app/services/kite_engine/scanner.py` | Finalized candles; invalid/nonfinite/nonincreasing OHLC rejection; short final-bar/session clipping | Actual cash transition verified by CAS audit; full revision/gap contract remains incomplete |
| `backend/app/engines/sterling_kite_engine/regime.py`, `exits.py` | Raw extrema separate from HA indicators; stop-hit semantics and monotonic trailing | Original audit identifies the other engine/replay artifacts; keep live, detail and replay decisions consistent |
| `backend/app/services/kite_engine/execution_evidence.py` | Exact contract match, nonexpired derivative, real lot/tick validation, fresh quote and last-trade timestamps, finite positive traded price, bounded tick prices | Missing/ambiguous/stale evidence rejects live entry. Quote age bound is 60 seconds. Freeze limits, mandatory depth capacity and slippage calibration remain open |
| `backend/app/services/kite_engine/order_journal.py` | Stable identity across config changes; immutable payload/qty conflict detection; legacy-key duplicate detection; unique 20-character tag; atomic send claim; pending capital reservation; scoped order/tag lookup | `claim_submission` alone grants send ownership. SQLite transactions use `synchronous=FULL`; one intent claim wins across competing workers |
| `backend/app/services/db.py` | Intent columns/migration, cumulative order-observation table, execution-event table | Existing DBs gain columns without deleting intents. The execution-event table is not yet a production signed financial ledger |
| `backend/app/services/kite_engine/execution_lifecycle.py` | Unknown-ACK recovery from authenticated order book/history; reconstruct missing registry; versioned projection; confirmed-quantity protection; no blind GTT retry | Recovery never resubmits an entry. Terminal journal evidence remains recoverable until its exact projection version is durably saved |
| `backend/app/services/kite_engine/positions.py` | Account/product attribution, requested-versus-confirmed entry quantity, pending remainder, uncertain protection, strict live persistence | New live ACK registers zero quantity. `persist_strict` raises on storage failure; legacy JSON writes elsewhere still need migration |
| `backend/app/services/kite_engine/protection.py` | Live ACK only registers journal-backed pending position; no independent GTT against intended quantity | Live scale-ins are blocked. Legacy paper simulations retain their prior behavior |
| `backend/app/services/kite_engine/monitor.py` | Journal entry handling before registry lookup; partial-fill projection; cancel/reconcile entry remainder before exit; fresh signed holdings before/after GTT cancellation | Unknown account, holdings, pending GTT outcome or cancellation blocks a rival exit. Complete GTT child attribution and distributed exit fencing remain open |
| `backend/app/services/kite_engine/service.py` | Common live manual/auto evidence and durable submission; reserve before network; final session/account checks; exact futures LIMIT margin request; position/recovery preflight | Unmatched live manual SELL and live scale-in are blocked. Manual partial exits are rejected; exact tracked quantity required. Reconciliation also scopes live net rows by account/exchange/product |
| `backend/app/services/exchanges/kite/accounts.py` | Cache identity includes mode, account owner, broker identity and credential generation; retained clients revalidated before entry | Switching paper/live or rotating credentials replaces cached client; no account credentials are emitted into reports |
| `backend/app/api/v1/endpoints/kite.py` | Generic live derivatives order endpoint routes supported options through engine safeguards | Unsupported product/variety/type and direct live futures bypass are rejected; validated auto futures remain supported |
| `backend/app/api/v1/endpoints/kite.py`, `backend/app/services/exchanges/kite/ticker_manager.py` | Mandatory constant-time webhook checksum verification; HTTP and WebSocket order callbacks bind their source account client | Unsigned/invalid postbacks cannot mutate positions; an active-account switch cannot reattribute an old socket's order |
| `backend/app/services/simulation.py` | Removes synthetic session and warmup generation; missing history stops replay with an explicit message | Insufficient actual warmup remains insufficient. Replay-clock regression reads the actual NIFTY hourly cache; September 4 snapshot-specific integration cases skip explicitly when their evidence is absent |
| `backend/tests/engines/sterling_kite_engine/conftest.py` | Per-test actual SQLite and cache isolation, wrapping shared cleanup | Prevents persisted positions leaking between tests or writing caller DB during fixture cleanup |
| `.../test_order_journal.py` | Concurrent reservation/claim, immutable identity, atomic capital, account/tag recovery, out-of-order/corrected fills, projection version, ACK/postback races | Thread concurrency uses independent SQLite connections. It is not proof of whole-engine multi-process execution safety |
| `.../test_execution_lifecycle.py` | Lost ACK without registry, crash after fill commit, partial/cancel quantity, duplicate event after exit, unknown GTT and wrong venue | Explicit crash-injection protocol fixtures; no live broker mutation |
| `.../test_execution_identity.py` | Mode/credential cache invalidation, account/venue/product holdings, pending-entry cancellation and exit safety | Explicit live-client protocol fixtures |
| `.../test_execution_evidence.py`, `.../test_live_manual_execution.py` | Quote/contract rejection, ticks, manual journal/funding, timeout deduplication, unmatched short rejection | Engineering validations only |
| `backend/study/kite_production_audit.py`, `kite_cas_realdata_audit.py` | Read-only, hash-recorded studies of actual cached/lake bars | JSON reports describe dataset dates and limits; no synthetic return claims |
| `docs/audits/2026-09-06-kite-validation.json` | Reproducible test and artifact manifest | Exact outcome record; do not replace failures with a headline count |

## End-to-end execution sequence

Broker payload fields were checked against [Kite postback documentation](https://kite.trade/docs/connect/v3/postbacks/) and [quote/instrument documentation](https://kite.trade/docs/connect/v3/market-quotes/) on September 6. The latter distinguishes daily instrument metadata from real-time quotes; metadata's `last_price` is never accepted as live price evidence.

1. Resolve active account, final signal, contract, product and current session. Reject stale/unclosed source bars or invalid stop/lot inputs.
2. Obtain actual instrument metadata and current quote/last-trade timestamps. Derive exchange-tick entry bounds. Check fresh capital, configured risk budget and exact broker futures margin. Revalidate retained account identity.
3. Atomically reserve immutable intent and pending account capital. A config change cannot create a second logical identity for the same signal/contract/side. Only the winning `RESERVED → SUBMITTING` compare-and-swap sends the broker request.
4. Send once with persisted tag. ACK binds order ID; timeout or missing ID remains unknown. A postback arriving before ACK is stronger evidence and cannot be regressed by the later HTTP response.
5. Match authenticated broker evidence on user/account, order/tag, symbol, exchange, side, product and requested quantity. Journal cumulative quantity/value first. Duplicate/older evidence cannot double-consume; contradictory corrections require reconciliation.
6. Project confirmed quantity/value into the registry, persist strictly, then acknowledge that exact journal projection version. A crash before projection acknowledgement leaves recoverable work, including terminal FILLED intents.
7. Subscribe monitoring and place/resize protection only for confirmed quantity. Persist uncertain protection before initial GTT request. An unknown result is not authorization to create a second independent trigger or submit a competing exit.
8. Before exit, cancel and prove terminal any pending entry remainder, verify fresh attributed holdings, then verify GTT cancellation. Recheck holdings before sending. An exit ACK remains pending; only attributable fill evidence consumes quantity/closes the position.
9. Recovery walks journal intents even when the position registry is absent. Exact unique order/tag evidence repairs state. Empty or ambiguous broker results never permit resubmission. Legacy flat-position reconciliation flags missing fill-level PnL instead of inventing it.

## Remaining release work and acceptance criteria

| Priority | Required implementation/evidence | Acceptance |
|---|---|---|
| P0 | Signed fill/lot/value/fees/realized-PnL ledger shared by entries, exits, GTT children and risk state | One transaction preserves account inventory, costs and realized values across partial cancel, multiple exits, corrections, duplicate/reordered events and crash. Current partial-exit PnL reconciliation flags remain mandatory |
| P0 | Process-level ownership/fencing across protection, registry projection and exits | Concurrent process/restart tests prove one broker side effect, no stale projection overwrite and no competing GTT/exit. Atomic entry claim alone does not certify multiple engine workers; use a single engine writer until completed |
| P0 | Independent recovery cadence, authenticated event capture, GTT child/order attribution and uncertain-GTT reconciliation | Missed WS events and disabled/slow scans cannot leave fills unprotected; restart reconstructs complete broker exposure before entries. Existing recovery is invoked by scan reconciliation and postbacks, not a separately certified watchdog |
| P0 | Canonical strict persistence and portfolio risk | Corrupt/unreadable registry cannot look empty; drawdown, aggregate open risk, fees and exposure limits share transactional account state; reserve/release is reconciled with fresh broker balances |
| P0 | Real executable-contract dataset and chronological validation | Actual option/futures prices, quotes/trades, instrument master and costs with provenance; untouched holdout and post-CAS coverage; predeclared robust net-edge criteria. Index/cash success is insufficient |
| P1 | Versioned calendar/instrument evidence and candle finality | BSE and special sessions verified separately; historical CAS membership, rollover/corporate actions and revisions recorded; September 7 observations acquired after occurrence |
| P1 | Unified readiness API/UI and operational runbook | Evidence/code/data/policy IDs checked at startup/enable/entry; no force bypass; actionable stale-feed/unknown-order/ledger alerts; tested rollback, reconnect and kill switch |
| P1 | Account/broker production validation | Actual static-IP/algo permissions, product rules, RMS, GTT and margin behavior verified. Sandbox lacks some production capabilities and cannot certify them alone |

Keep unknown orders/protection quarantined until exact broker evidence resolves them. Do not delete journal rows to unlock trading, infer a missing fill, silently turn a failed API response into zero exposure, or retry an ambiguous submission.

## AI continuation instructions

Read root `AGENTS.md`; use code-review-graph before source exploration. Inspect the current branch/diff because concurrent user work moves HEAD. Preserve unrelated extraction changes. Read this document, validation JSON, both real-data reports and the original audit's rule references. Use isolated test databases and never print credentials.

Complete the P0 rows in order; extend existing modules instead of creating another execution path. Record each remaining gate as evidence-backed pass/fail. Acquire missing actual contract data through existing authorized read-only sources; do not synthesize missing option prices or tune on the final holdout. Re-run changed-path checks, then the affected/full suite when warranted. Publish a new hash-bound validation manifest after the final source edit. Production promotion requires every release gate, not merely passing tests or a configuration toggle.
