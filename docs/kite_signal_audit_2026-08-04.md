# Kite signal board — deep audit (2026-08-04)

Scope: entry, legs, SL, TSL, exit and target for **SuperTrend** and **Navigator** signals
individually, plus the ✝ best-risk/reward and ▲ highest-delta strike selection, end to end.

## How to read the status column

Six independent finders swept six slices of the lifecycle. An adversarial refuter was
supposed to try to kill every finding; **it only completed for one slice** (the session hit
its usage limit), and on that slice it refuted 4 of the 6 claims.

Both halves of that are worth knowing. Unrefuted finder claims are unreliable — assume a
large fraction will not survive contact with the code. But the refuter was itself wrong
about at least two of the four it dismissed: I checked the ✝ score's algebra and the
ungated delta ranking by hand, both held, and both are fixed below. So neither the finder
nor the refuter is authority here. The only claims stated as defects are the ones I read,
reproduced and pinned with a test myself.

* **FIXED** — I verified it in the code myself, fixed it, and pinned it with a test.
* **CONFIRMED, NOT FIXED** — I verified it; the fix is a decision for you, not a bug fix.
* **UNVERIFIED CLAIM** — a finder's claim, not independently verified and not refuted.
  **No row carries this status any more** — see the close-out below; every one was
  re-read against the code and resolved into one of:
* **CLOSED** — was real, is handled by code shipped since the sweep.
* **NEEDS DECISION** — real, but the remedy is a product choice rather than a bug fix.
* **REFUTED** — never true as stated; the note says what was misread.

Raw finder output (full evidence, quoted code, scenarios) is in the workflow journal:
`~/.claude/projects/-home-nageshmadaram-Sterling/*/subagents/workflows/wf_16196edd-b06/journal.jsonl`

## Close-out (2026-08-14)

Every lead above was re-read against the code as it stands today, ten days after the
sweep. The line numbers in the claims are stale; the verdicts are not.

| Verdict | Count | What it means |
|---|---|---|
| CLOSED | 14 | Was real, is handled by code shipped since — usually with a test pinning it |
| FIXED | 6 | Still real when re-read. Fixed in this pass, with a test |
| NEEDS DECISION | 9 | Real, but the remedy is a product choice, not a bug fix |
| REFUTED | 2 | Never true as stated |

The six fixed here: the mid-exit fill that booked realized PnL twice (10); markers keyed
by a shared instrument token so re-entry rows fought over them (13, 18); confluence rows
sitting in "Active now" while their own legs read ended (14); expiry-day greeks collapsing
on the frontend while the detail pane still showed them (15); a React row key that let a
SuperTrend and a Navigator row for one bar collide (24); and badge copy that still
described the formula it no longer uses (31).

The nine NEEDS DECISION entries are the honest residue. Three of them (7, 12, and the
"which spot" half of 19) are the same underlying question: for a signal that is still
running days later, is the board showing HISTORY — the strike and premium as of the
trigger — or a TRADEABLE-NOW roll priced at today's LTP? Each half was decided
separately and they now point opposite ways. Whichever is chosen, both halves have to
move together.

## Summary

| Sev | Impact | Where | Finding | Status |
|---|---|---|---|---|
| critical | live money | `backend/app/services/kite_engine/monitor.py:95` | A rejected entry or an externally-filled exit closes the position but never cancels the broker GTT — an armed SELL is orphaned at Zerodha | CLOSED |
| critical | live money | `backend/app/services/kite_engine/service.py:548` | stop_mode="both" (default) arms the broker GTT and the tick monitor at the IDENTICAL trigger — a stop-out fires both and sells 2x qty, leaving a naked short option | CLOSED |
| critical | wrong number on screen | `backend/app/services/kite_engine/detail.py:113` | On expiry day (0 DTE) every leg's greeks are fabricated intrinsic values, so ✝/▲ crown the deepest-ITM leg and the ATM/OTM strikes show δ 0.00 and +₹0 projected gain | FIXED |
| critical | live money | `backend/app/services/kite_engine/monitor.py:115` | Protective GTT is placed on a PENDING (unfilled) entry and is never cancelled when the entry is REJECTED/CANCELLED → resting naked-short SELL at Zerodha | CLOSED |
| critical | live money | `backend/app/services/kite_engine/service.py:548` | When the entry premium quote returns 0 the auto-exec still BUYs, gets NO GTT and NO monitor stop, and the activity log claims "[both stop+monitor]" | CLOSED |
| critical | live money | `backend/app/services/kite_engine/service.py:748` | Live red-count is read from the ENTRY-BAR alignment chip, so every PE (bear) auto-exec position is market-sold on the first tick after the first post-entry scan | CLOSED |
| critical | wrong number on screen | `frontend/src/components/kite/SterlingKiteEnginePane.tsx:344` | A brand-new Navigator signal renders as "ended" — the board reads is_active only, but origination emits is_fresh=true / is_active=false | FIXED |
| high | live money | `backend/app/services/kite_engine/service.py:84` | Manual orders from the signal board get zero protection — positions.register has exactly one call site and it is the auto-exec path only | CONFIRMED, NOT FIXED |
| high | live money | `backend/app/services/kite_engine/sizing.py:374` | The 1-lot floor makes risk_pct advisory, not a cap: a 1% setting routinely takes ~15% of capital on one index option trade | NEEDS DECISION |
| high | wrong number on screen | `frontend/src/components/kite/SignalImpactCalculator.tsx:132` | The ▲ "highest delta" badge crowns legs whose greeks are degenerate (iv=0 → delta exactly ±1.00) on all three detail-page sites; the iv>0 gate exists at only one of four badge sites | FIXED |
| high | wrong number on screen | `frontend/src/components/kite/impactMath.ts:29` | The ✝ "best reward-to-risk" score reduces to 1 + γ·m/(2\|δ\|), a monotone function of strike — so the badge is deterministically the cheapest strike in the bucket (always the farthest OTM), not a reward:risk comparison, and it ignores the leg's real premium stop and target | FIXED |
| high | wrong number on screen | `backend/app/engines/sterling_kite_engine/exits.py:39` | An ENDED row's stop is frozen at the exit bar, not at the level that was breached — it can fall all the way back to the ENTRY bar's line, so the board prints "TSL 163.97" next to a "TSL exit ≤ 581.44" chip | FIXED |
| high | live money | `backend/app/services/kite_engine/detail.py:78` | Clicking a Navigator row opens a SuperTrend row's detail: build_detail falls back to any row with the same token before it ever consults Navigator, and Navigator rows reuse the underlying's instrument token | FIXED |
| high | wrong number on screen | `backend/app/services/kite_engine/expiry_series_runtime.py:234` | Retained (non-fresh) spot rows resolve their strike ladder at TODAY's spot but stamp the entry premium from the signal bar — fake Entry, fake P&L, wrong moneyness label | NEEDS DECISION |
| high | live money | `backend/app/services/kite_engine/greeks.py:98` | premium_stop_from_move clamps to 0 at realistic trail distances, and stop_px==0 silently means NO broker GTT, NO monitor stop and NO risk sizing — a naked long option | CLOSED |
| high | wrong number on screen | `backend/app/services/kite_engine/held_contract_scan.py:215` | _compile_rows is not idempotent over already-grouped rows; held_contract_scan re-runs it and silently drops every derivative leg except the first | CLOSED |
| high | live money | `backend/app/services/kite_engine/monitor.py:92` | `on_order_update` guards double-booking on status only, not on the `_exiting` claim — the monitor's own exit fill can be booked twice while `_exit_position` is still awaiting the GTT cancel | FIXED |
| high | live money | `backend/app/services/kite_engine/monitor.py:112` | Partial fills are never read: `filled_quantity` is ignored, so both the GTT and the monitor exit the intended quantity, and a CANCELLED-after-partial entry abandons a live position | CLOSED |
| high | live money | `backend/app/services/kite_engine/service.py:84` | Manual BUY from the signal board creates a position with no stop, no monitor and no expiry square-off, while the same pane displays SL / TSL / Target for the leg | CONFIRMED, NOT FIXED |
| high | wrong number on screen | `backend/app/services/navigator/service.py:454` | A still-running Navigator-originated row re-stamps its trigger time, entry premium, stop, target and even its strike to the LATEST bar on every scan — its Entry can never show open P&L | NEEDS DECISION |
| high | wrong number on screen | `frontend/src/components/kite/SignalDetailPane.tsx:640` | ▲ 'highest delta' is ranked on ungated \|delta\| in the detail pane, impact calculator and premium breakdown, so a leg whose IV could not be solved (delta hardcoded ±1.00) always wins the badge | FIXED |
| high | wrong number on screen | `frontend/src/components/kite/SterlingKiteEnginePane.tsx:493` | The ✝ badge is scoped per ITM/ATM/OTM bucket in the card but globally in the detail pane, and with the shipped 3-strike default ladder every leg wins both badges — the watchlist/ticker then shows three contradictory 'best' contracts for one signal | FIXED |
| high | wrong number on screen | `frontend/src/components/kite/SterlingKiteEnginePane.tsx:532` | Signal markers are keyed by row.token, which is NOT unique per row — the watchlist/ticker ✝▲ ends up on the last-rendered row's strike, including a dead signal's | FIXED |
| high | wrong number on screen | `frontend/src/components/kite/SterlingKiteEnginePane.tsx:908` | Option-leg "Chg. %" renders Kite's absolute rupee net_change with a % sign (the exact bug just fixed 400 lines above for the underlying) | FIXED |
| high | wrong number on screen | `frontend/src/components/kite/SterlingKiteEnginePane.tsx:347` | Confluence rows: "Active now" bucket and the footer live-count ignore the live-LTP stop reconciliation the card itself applies, so a row says "running" while its own body says every leg ended | FIXED |
| high | wrong number on screen | `frontend/src/components/kite/impactMath.ts:29` | The ✝ 'reward:risk' number is algebraically 1 + γ·m/(2δ) — a convexity ratio that can never fall below 1:1 and is monotone in strike, so the badge deterministically crowns the cheapest/furthest-OTM strike regardless of price | FIXED |
| high | wrong number on screen | `frontend/src/utils/computeGreeks.ts:129` | On expiry day the card's client-side greeks get dte = 0, so EVERY leg is 'unsolved' and the board loses all ✝/▲ badges and all Δ readouts — while the detail pane still shows them | FIXED |
| medium | latent or dead | `backend/app/services/kite_engine/service.py:380` | Futures vehicle sends an UNDERLYING-domain price as the futures contract's entry, stop and GTT trigger, and stores no expiry so it is never squared off | REFUTED |
| medium | wrong number on screen | `frontend/src/components/kite/SignalMarker.tsx:17` | Badge scoping contradicts itself across panes: the board computes ✝/▲ PER moneyness bucket (up to 3 of each per signal) but the watchlist/ticker marker, the detail leg list and the calculator all present a single winner "among this signal's strikes" | CLOSED |
| medium | wrong number on screen | `frontend/src/components/kite/SterlingKiteEnginePane.tsx:525` | Watchlist/ticker markers are published under `String(row.token)`, which collides for the re-entry rows the board is explicitly designed to show — last card wins, and one card unmounting clears the markers of the others | FIXED |
| medium | live money | `backend/app/services/kite_engine/scanner.py:925` | Derivatives-source is_fresh is measured against the CONTRACT's own last candle, so an illiquid strike with a stale last bar fires auto-exec as a live trigger | NEEDS DECISION |
| medium | gap missing feature | `backend/app/services/kite_engine/scanner.py:177` | No code path anywhere exits at a target — Navigator's row.target / leg.premium_target are display-only | CONFIRMED, NOT FIXED |
| medium | wrong number on screen | `backend/app/services/kite_engine/service.py:734` | A failed GTT trail move is silent: the board and registry show the tightened stop while the broker stop stays at the entry level | CLOSED |
| medium | wrong number on screen | `backend/app/services/kite_engine/service.py:153` | The GTT actually placed uses a flat 18% IV while the board's SL/TSL backs IV out of the entry premium — the broker stop is not the stop on screen | NEEDS DECISION |
| medium | wrong number on screen | `backend/app/services/kite_engine/signal_board_runtime.py:427` | Confluence entry premium is overwritten with the STILL-FORMING 1H bar's close, so the Entry column repaints every 5 minutes and diverges from the entry actually recorded for the order | CLOSED |
| medium | wrong number on screen | `frontend/src/components/kite/SignalImpactCalculator.tsx:120` | SignalImpactCalculator crowns legs with NO price data: `recommended` and `bestDeltaSym` skip the premium > 0 filter that its three sibling badge sites apply | FIXED |
| medium | wrong number on screen | `frontend/src/components/kite/SignalImpactCalculator.tsx:93` | For 'derivatives' rows the ✝ ranking and the Impact Calculator's "Risk to stop" are built on a fabricated 1R, because row.stop_loss is a PREMIUM level fed into an UNDERLYING stop-distance — the leg's real premium stop is ignored | CLOSED |
| medium | gap missing feature | `frontend/src/components/kite/SterlingKiteEnginePane.tsx:549` | The 'Best ✝▲' quick-toggle hides nothing under the default 3-strike ladder — it claims to drop the middle of the ladder while keeping every leg | ADDRESSED |
| medium | wrong number on screen | `frontend/src/components/kite/SterlingKiteEnginePane.tsx:1915` | Board row key omits `source`, so a SuperTrend row and a Navigator row for the same underlying/bar collide — one silently disappears mid-scan | FIXED |
| medium | wrong number on screen | `frontend/src/components/kite/SterlingKiteEnginePane.tsx:892` | Chg % column renders Kite's absolute `net_change` (rupees) with a % sign, and blanks the Chg column, whenever the contract has no previous close | FIXED |
| medium | wrong number on screen | `frontend/src/components/kite/SterlingKiteEnginePane.tsx:1027` | Navigator rows print the same number in SL and TSL, under a tooltip describing a SuperTrend ratchet the row does not have | NEEDS DECISION |
| medium | wrong number on screen | `frontend/src/components/kite/SterlingKiteEnginePane.tsx:1992` | The "re-entry" badge is computed after lens filtering, so switching lenses can hide the original entry and make a re-arm look like an independent new setup | NEEDS DECISION |
| low | latent or dead | `backend/app/services/kite_engine/service.py:513` | The `stop_loss` handed to place_order_option is silently discarded by the client — the entry order carries no broker stop at all | REFUTED |
| low | wrong number on screen | `frontend/src/components/kite/SterlingKiteEnginePane.tsx:553` | The "Best ✝▲" quick-toggle silently becomes a no-op whenever no leg has a solvable IV (market closed, quotes not yet loaded), while the chip stays lit as if it were filtering | ADDRESSED |
| low | latent or dead | `backend/app/engines/sterling_kite_engine/regime.py:74` | exit_aligned_trail rides trail_value_for_threshold, which ignores whether that line is still aligned — once the line flips, the 'trail' sits on the wrong side of price | NEEDS DECISION |
| low | wrong number on screen | `backend/app/services/kite_engine/scanner.py:176` | premium_stop_from_move mixes price domains: row.spot is a RAW close while row.stop_loss is a Heikin-Ashi SuperTrend level | CLOSED |
| low | wrong number on screen | `frontend/src/components/kite/SterlingKiteEnginePane.tsx:513` | The card ranks only the legs it is currently showing, so turning "Ended" off moves the ✝/▲ to a different strike than the detail pane crowns for the same signal | CLOSED |
| low | latent or dead | `frontend/src/components/kite/SterlingKiteEnginePane.tsx:504` | Badge tooltips and the card's own comments describe a per-bucket "reward-to-risk" that the shared selector explicitly is not | FIXED |

## Fixed in this pass

### On expiry day (0 DTE) every leg's greeks are fabricated intrinsic values, so ✝/▲ crown the deepest-ITM leg and the ATM/OTM strikes show δ 0.00 and +₹0 projected gain

**critical** · `backend/app/services/kite_engine/detail.py:113` · FIXED — fractional DTE to the 15:30 close (`detail.intraday_dte_days`) + `Greeks.solved`

Expiry Tuesday, NIFTY spot 24,000, row.stop_loss 23,880 → stopDist 120. Legs: ITM1 23900
(LTP 105), ATM 24000 (LTP 45), OTM1 24100 (LTP 12), lot 75. Verified with the repo's own
greeks: black_scholes_greeks(dte_days=0) returns delta 1.0 for 23900 and delta 0.0 for 24000
and 24100; implied_vol(price=200, dte_days=0) returns 0.0. Result on screen: ITM1 gets rr =
(1.0×120)/min(105, 120) = 1.14 and |delta| = 1.00 → it wins BOTH ✝ and ▲; ATM and OTM1 print
'δ 0.00', 'ITM 0%', 'If +120pts +₹0', 'Risk −₹0', 'R:R —', 'B/E —'. A real 0-DTE ATM has
delta ≈ 0.5, so a 120-pt move roughly doubles the ₹45 premium (≈ +₹4,000/lot) — the board
says zero. Simultaneously the row card shows NO badges at all (its gate `hasUsableGreeks` =
iv > 0 fails for every leg because the frontend dte is also 0), so the card and the detail
pane for the same signal disagree completely, and 'Best ✝▲' silently falls back to the whole
ladder.

### A brand-new Navigator signal renders as "ended" — the board reads is_active only, but origination emits is_fresh=true / is_active=false

**critical** · `frontend/src/components/kite/SterlingKiteEnginePane.tsx:344` · FIXED — origination is is_active=True; board reads `is_active || is_fresh`

14:15 bar closes. Navigator's independent scan originates NIFTY BANK long: `prior =
get_cached_decision(..., origin=True)` is None → `prior_is_live_origin=False` →
`state="fresh"` → the row is emitted with `is_active=False, is_fresh=True,
source="navigator"`, an accepted AVWAP stop 54,120 and target 54,900, legs hydrated with
Entry 312.40 / SL 268.10 / Target 402.75. The board then does: `rowIsRunning(row)` →
`row.source !== 'derivatives'` → `!!row.is_active` → FALSE. Result: (a) the row is NOT in
the "Active now" bucket — it lands under "Today (ended)"; (b) `legIsExited(leg)` →
`!row.is_active` → true, so Entry/SL/TSL/Target all render `line-through`, opacity 0.65,
with the tooltip "Past setup (fired at 312.40, stop 268.10) — the entry's SuperTrend has
since flipped, not a live order" — on a row that has no SuperTrend at all and fired 30
seconds ago; (c) `liveCount = rows.filter((r) => rowIsRunning(r, quotes)).length` excludes
it, so the Kite footer pill says "0 live"; (d) if the user has the Ended toggle OFF,
`groupedRows` keeps only `b.active` buckets and the signal is invisible — it never appears
on the board at all. Meanwhile opening that same row's detail dock prints "fresh this bar"
(SignalDetailPane.tsx:529 `data.is_fresh ? 'fresh this bar' : data.is_active ? 'running' :
'ended'`), so the two surfaces flatly contradict each other. It self-heals one scan cycle
(~5 min) later when the cached decision makes state="active" — i.e. it is wrong for exactly
the window in which the signal is actionable.

### The ▲ "highest delta" badge crowns legs whose greeks are degenerate (iv=0 → delta exactly ±1.00) on all three detail-page sites; the iv>0 gate exists at only one of four badge sites

**high** · `frontend/src/components/kite/SignalImpactCalculator.tsx:132` · FIXED — same fix; all four badge sites share `selectBestLegs`

BANKNIFTY 1H SuperTrend fires BULL; spot_now = 57,000, strikes ITM5…OTM5 resolved
(expiry_series_runtime._FULL_MONEYNESS is the live default). The 56,500 CE (ITM5) is
illiquid and last traded 25 minutes ago at ₹480, before the last 200 points of the move; its
intrinsic is now 500. detail.py: ltp=480 > 0, so it calls implied_vol(price=480, spot=57000,
strike=56500) → 480 < 500 - 1e-6 → returns 0.0 → black_scholes_greeks(iv=0) → delta = 1.0,
gamma = 0. On the detail page the user now sees, simultaneously: (a) Trade Impact Calculator
row ITM5 56500 with 'δ / ITM%' = '1.00  100%' and the ▲ badge titled 'Highest delta — most
responsive to the underlying'; (b) the same ▲ on ITM5 in Premium breakdown; (c) the same ▲
on ITM5 in the Option-legs list — while the genuinely-priced ATM 57000 CE (δ 0.52 from a
real IV) gets nothing. The board row that the user clicked through from shows the opposite:
it prints '(Δ—)' for ITM5 and puts ▲ on a leg with solvable IV. Worse, the row that wears
the badge is exactly the one whose displayed LTP (₹480) is below its no-arbitrage floor
(₹500) — clicking its B / BUY button (SignalImpactCalculator.tsx:302-307 →
SignalDetailPane.tsx:602-608) opens the order window seeded with `lastPrice: 480` for a
MARKET buy that cannot fill under 500. A second, cruder variant: if `client.get_quote`
throws (detail.py:99-100 logs and leaves `quotes = {}`), EVERY leg gets ltp=0 → iv=0 → every
ITM leg gets delta 1.00 and every OTM leg 0.00; the Option-legs list and Premium breakdown
then show no badge at all (their premium>0 filters skip everything) while the Impact
Calculator still marks the first ITM leg ▲ and, via the stable-sort tie at score 0, stamps ✝
on rows[0] and prints 'The ITM5 56500 gives the best reward-to-risk here — a 200-pt move up
turns ~₹0 of premium into +₹0, against −₹0.'

### The ✝ "best reward-to-risk" score reduces to 1 + γ·m/(2|δ|), a monotone function of strike — so the badge is deterministically the cheapest strike in the bucket (always the farthest OTM), not a reward:risk comparison, and it ignores the leg's real premium stop and target

**high** · `frontend/src/components/kite/impactMath.ts:29` · FIXED — same fix

BANKNIFTY spot 57,000, 5 DTE, IV 15%, signal stop 56,800 → stopDistance = 200. Evaluating
the live default ladder with the real BS greeks the code uses (verified by running backend
greeks.py directly): ITM5 56500 score 1.0475, ITM4 1.0530, ITM3 1.0583, ITM2 1.0640, ITM1
1.0700, ATM 1.0760, OTM1 1.0824, OTM2 1.0889, OTM3 1.0956, OTM4 1.1025, OTM5 1.1094. The
ordering is strictly monotone in strike, so the ✝ in the OTM bucket is OTM5 (the farthest
strike scanned) and the ✝ in the ITM bucket is ITM1 (the shallowest) — for every underlying,
every IV, every stop distance, every day. Nothing about the market can move the badge;
adding an OTM6 to the scan config would immediately move the badge to OTM6. Meanwhile the
R:R column prints '1' for ITM5…ITM1 (the `Math.abs(r.rr - 1) < 0.05` branch at line 292) and
'1.1:1' for the OTM legs, so the user sees eleven near-identical ratios and one strike
wearing a cross that says 'Best reward-to-risk'. What the badge is actually telling them,
every single time, is 'buy the cheapest lottery ticket in the ladder'. The leg's own plan
disagrees: the same ATM 57000 CE row on the same screen shows Entry 425 / TSL 380 / Target
620 (a genuine 4.3:1) while its R:R cell reads '1.1:1'.

### An ENDED row's stop is frozen at the exit bar, not at the level that was breached — it can fall all the way back to the ENTRY bar's line, so the board prints "TSL 163.97" next to a "TSL exit ≤ 581.44" chip

**high** · `backend/app/engines/sterling_kite_engine/exits.py:39` · FIXED — `exits.reported_trail_level` reports the level actually breached

Run `evaluate_item` on live-default config (one_red, exit_aligned_trail=False,
price_stop_exit=True, heikin_ashi, trail_target=fast) over an uptrend that then drops.
Measured: entry_i=65, exit_j=141, `exit_reason = "trail breach (≤ 581.44)"`, but
`row.stop_loss = 566.61` — at bar 141 the fast line flipped, `green_lines("long", 141) =
['slow','mid']`, so the row shows `l_mid[141]`. Worse, on a decisive one-bar crash (all
three flip at the exit bar) `green_lines` is empty, `best_trail_line_value` returns 0.0, and
`trail_level` falls back to `l_fast[entry_i]`: measured `row.stop_loss = 163.97` against a
true breached level of `578.33` — a 3.5x error, reporting a large winner as if it stopped
out at its original entry stop. This propagates into the premium domain via
`_stamp_leg_premium_stops`: for NIFTY entered at 24,000 with a ₹180 ATM CE that trailed to
24,800, `leg.premium_sl` should read ₹715.45 (₹53,658/lot) but reads ₹514.65 in the mid-line
case and ₹113.07 (₹8,480/lot) in the entry-fallback case. The board renders both numbers
side by side: `TSL {row.stop_loss.toFixed(1)}` and the `TSL exit` chip whose tooltip quotes
`exit_reason`.

### Clicking a Navigator row opens a SuperTrend row's detail: build_detail falls back to any row with the same token before it ever consults Navigator, and Navigator rows reuse the underlying's instrument token

**high** · `backend/app/services/kite_engine/detail.py:78` · FIXED — `source` threaded to `/detail`; exact-timestamp match wins

Combined lens. NIFTY 50 (token 256265) has two rows on the board: a spot SuperTrend entry
from 10:15 (entry_sl 24,400, target null, exit_state "1/3 red", 5 candidate strikes) and a
"Navigator idea" from 14:15 (AVWAP stop 24,510, target 24,900, one ATM leg, Nav
HIGH_CONVICTION). Both carry token=256265 because service.py:449 uses `token=fetch_token`
and scanner.py:244 uses `token=item.token`. User clicks the Navigator row →
`onSelectSignal({token: 256265, timestamp_ms: <14:15>})` → GET
detail?token=256265&timestamp_ms=<14:15>. In build_detail: `snapshot.row_for_token(256265,
14:15)` finds the 10:15 spot row in the index, `_matches` fails on the timestamp, the linear
rescan finds no scanner row at 14:15 → None. Line 78-79 then runs `row =
snapshot.row_for_token(token)` with NO timestamp → returns the 10:15 SPOT row.
`_navigator_row_for_token` on line 81 is never reached. The dock renders: "Triggered 10:15",
the orange "SuperTrend · underlying" badge with the blurb "Exit is the trailing stop plus
the red counter — there is no fixed target", "Stop at entry 24,400", "Target: none", "Exit
counter 1/3 red", NO NavigatorEvidencePanel, and the spot row's five candidate strikes with
live BUY/SELL buttons. Every number on screen belongs to a different signal, and the user
places a real MARKET order off the wrong strike and the wrong stop. The same hijack happens
with the SuperTrend engine disabled: `_signals_response` line 84 serves `rows = []` from the
scanner, but `scanner.snapshot(uid)` still holds DB-hydrated rows, so a board made entirely
of Navigator rows still resolves details to invisible SuperTrend rows.

### ▲ 'highest delta' is ranked on ungated |delta| in the detail pane, impact calculator and premium breakdown, so a leg whose IV could not be solved (delta hardcoded ±1.00) always wins the badge

**high** · `frontend/src/components/kite/SignalDetailPane.tsx:640` · FIXED — `greeks_solved` on the payload; unsolved legs cannot win either badge

NIFTY 24,000, 7 DTE. The ITM2 23800 CE has intrinsic 200 but its last trade printed at 180
(stale/illiquid deep-ITM strike — the ITM2/ITM3 rungs the resolver picks are thinly traded).
Verified with repo code: implied_vol(price=180, spot=24000, strike=23800, dte_days=7, 'CE')
= 0.0 → black_scholes_greeks(iv=0) = Greeks(delta=1.0, gamma=0.0, ...). In SignalDetailPane
the loop computes ad = 1.0, beating the genuinely-solved ITM1 (δ 0.631) and ATM (δ 0.533),
so ▲ 'Highest delta — most responsive to the underlying' is pinned on the one leg with NO
usable greeks; the same table prints 'δ 1.00 / ITM 100%' for it and θ/day ₹0. The row card
for the same signal, one click away, puts ▲ on ITM1. A user trading the ▲ buys the stale
deep-ITM strike on fabricated data.

### The ✝ badge is scoped per ITM/ATM/OTM bucket in the card but globally in the detail pane, and with the shipped 3-strike default ladder every leg wins both badges — the watchlist/ticker then shows three contradictory 'best' contracts for one signal

**high** · `frontend/src/components/kite/SterlingKiteEnginePane.tsx:493` · FIXED — one global winner per signal via `selectBestLegs`

Default config, one NIFTY spot signal, spot 24,000, 7 DTE, iv 12%, stop 23,880 (sd 120),
legs ITM1 23900 / ATM 24000 / OTM1 24100. Card (grid and list): all three legs render ✝ and
▲ — five badge glyphs telling the user three different strikes are each 'the best'. The ▲ on
OTM1 marks δ 0.434, the LOWEST delta on the card, while ITM1 on the same card has δ 0.631.
Watchlist/ticker: useSignalMarkers receives {NFO:...23900CE: rr+delta, ...24000CE: rr+delta,
...24100CE: rr+delta} and SignalMarker renders each with title 'Best reward-to-risk among
this signal's strikes' / 'Highest delta — most responsive to the underlying' — three
simultaneous, mutually exclusive claims. Click into the detail pane for the SAME signal and
the global computation (verified with repo BS: scores ITM1 1.0899 / ATM 1.1122 / OTM1
1.1365; deltas 0.631/0.533/0.434) puts ✝ on OTM1 only and ▲ on ITM1 only — so the card says
ITM1 is a best-R:R strike and the detail pane says it is not.

### Option-leg "Chg. %" renders Kite's absolute rupee net_change with a % sign (the exact bug just fixed 400 lines above for the underlying)

**high** · `frontend/src/components/kite/SterlingKiteEnginePane.tsx:908` · FIXED — same fix applied to the per-leg row

User setting `chgType` is 'open' (a supported toggle in Signal-table settings) and a leg is
a strike that has not traded yet today, so the quote comes back with `ohlc.open = 0` (falsy)
but `net_change = 46.75`. Leg NIFTY25AUG24500CE, LTP 210.00, previous close 163.25. The
board renders: Chg. = "—" (chgAbs stays null) and Chg. % = "46.75%". The true day change is
46.75/163.25 = 28.64%. The direction chevron also disappears (it keys off `chgAbs`) while
the row is coloured green from `chgPct`. Same code, same wrong string, in the detail dock at
SignalDetailPane.tsx:116.

### The ✝ 'reward:risk' number is algebraically 1 + γ·m/(2δ) — a convexity ratio that can never fall below 1:1 and is monotone in strike, so the badge deterministically crowns the cheapest/furthest-OTM strike regardless of price

**high** · `frontend/src/components/kite/impactMath.ts:29` · FIXED — carry-inclusive net R multiple, renamed; no longer claims reward:risk

NIFTY 24,000, 7 DTE, iv 12%, stop 23,880 → m = 120. Computed with the repo's own
black_scholes_greeks/bs_price: ITM2 23800 rr 1.0700 · ITM1 23900 rr 1.0899 · ATM 24000 rr
1.1122 · OTM1 24100 rr 1.1365 · OTM2 24200 rr 1.1625. Strictly increasing in strike; total
spread across the whole ladder is 8.6%, i.e. noise. The detail pane therefore always plants
✝ on the furthest-OTM leg it can price (OTM2 here — the lowest-probability, highest-theta
strike, ITM% 34), and the R:R column shows '1.1:1' amber for all five, which a user reads as
'this trade risks 1 to make 1.1' even though the engine has no fixed target (schemas.py:
target is `None` for every SuperTrend row; the exit is the ratcheting trail plus the red
counter). Change every premium on the board and the ✝ does not move.

### SignalImpactCalculator crowns legs with NO price data: `recommended` and `bestDeltaSym` skip the premium > 0 filter that its three sibling badge sites apply

**medium** · `frontend/src/components/kite/SignalImpactCalculator.tsx:120` · FIXED — `premium > 0` gate now lives in the shared selector

detail.py:96-100 swallows a get_quote failure (`log.warning(...)`; `quotes = {}`) — a rate-
limit or transient network error during the 15s auto-refresh. Every OptionDetail then has
last_price 0.0 and iv 0.0, so delta is the intrinsic ±1.0/0.0. The Trade Impact Calculator
still renders (`if (!data.options.length) return null;` passes because the legs exist): all
rows score 0, V8's stable sort makes scored[0] = data.options[0], so ✝ 'Best reward-to-risk
for this move' is planted on whichever leg happens to be first, and ▲ goes to the ITM leg on
its hardcoded delta 1.00 — over a table reading 'Cost ₹0 / If +120pts +₹0 / Risk −₹0 / R:R
—'. The 'Read' footer then prints 'The ITM1 23900 gives the best reward-to-risk here — a
120-pt move up turns ~₹0 of premium into +₹0, against −₹0 if it hits the stop instead.'
Meanwhile the Option-legs card and Premium-breakdown card directly above show no badges at
all.

### The 'Best ✝▲' quick-toggle hides nothing under the default 3-strike ladder — it claims to drop the middle of the ladder while keeping every leg

**medium** · `frontend/src/components/kite/SterlingKiteEnginePane.tsx:549` · ADDRESSED — selector returns no winner when <2 legs are rankable

Default config board, three NIFTY/BANKNIFTY signals each with ITM1/ATM/OTM1 legs. User flips
'Best ✝▲' (tooltip: 'Show only the best strikes per signal: ✝ best reward:risk and ▲ highest
delta'; the code comment promises 'hiding the middle-of-the-ladder strikes'). The pill turns
blue, aria-pressed flips — and not one leg disappears, because ITM1 is the best of its
bucket, ATM is the best of its bucket and OTM1 is the best of its bucket. The user concludes
the ladder they are looking at is already the shortlist. Configure the full
ATM/ITM1/ITM2/OTM1/OTM2 ladder and it still keeps all five (ITM1+ITM2 both win in the ITM
bucket: ITM1 on R:R 1.0899 > 1.0700, ITM2 on delta 0.721 > 0.631; likewise OTM1/OTM2), so
the toggle only ever bites from ITM3/OTM3 outward.

### Chg % column renders Kite's absolute `net_change` (rupees) with a % sign, and blanks the Chg column, whenever the contract has no previous close

**medium** · `frontend/src/components/kite/SterlingKiteEnginePane.tsx:892` · FIXED — `net_change` feeds Chg. (rupees); % left blank without a base

NIFTY 24500CE OTM3 did not trade yesterday, so Kite returns `ohlc.close = 0` and `net_change
= 84.50` (absolute) with `last_price = 84.50`. `base = s.chgType === 'close' ? q.ohlc?.close
: q.ohlc?.open` → 0 → falsy → the else-branch sets `chgPct = 84.50` and leaves `chgAbs =
null`. The row renders Chg `—` and Chg % `84.50%`, on a contract whose real day change is
unknown (and whose premium is ₹84.50, so an 84.5% reading is pure coincidence of units). The
same value also drives the direction chevron colour, and sorting: `getChg` at line 864
returns `q.net_change` for `sort.key==='chgPct'` (so illiquid strikes sort as if they were
the biggest movers on the board) and returns literal `0` for `sort.key==='chg'` (so they all
sort as flat). The identical branch is duplicated for the underlying at line 478-479 and for
the detail-pane legs at SignalDetailPane.tsx:112-114.

### The "Best ✝▲" quick-toggle silently becomes a no-op whenever no leg has a solvable IV (market closed, quotes not yet loaded), while the chip stays lit as if it were filtering

**low** · `frontend/src/components/kite/SterlingKiteEnginePane.tsx:553` · ADDRESSED — same

After market hours the user opens the board, flips 'Best ✝▲' on. `useKiteQuote` has no live
quotes, so for every leg `lq` is undefined → `extractIv` returns 0 → `hasUsableGreeks` false
→ `bestRRSyms`/`bestDeltaSyms` are empty → `keep.size === 0` → `filtered = []` → `base =
visibleLegs`. All eleven strikes of every signal stay on screen with the chip highlighted
blue and `aria-pressed="true"`, and not one of them carries a ✝ or ▲. The user reads the
full ladder as 'these are all best strikes'. Note this is display-only and self-corrects the
moment quotes arrive — labelling it low, not latent, because it fires every session outside
market hours.


## Confirmed, left as your decision

### Manual orders from the signal board get zero protection — positions.register has exactly one call site and it is the auto-exec path only

**high** · `backend/app/services/kite_engine/service.py:84`

`positions.register` has one call site (auto-exec). Needs your decision (see PR #38).

A leg row on the board shows Entry 120.00, SL 85.00, TSL 85.00 (leg.premium_sl, stamped by
scanner._stamp_leg_premium_stops). The user clicks BUY on that row and takes 1 lot (75) of a
weekly NIFTY 24000CE for Rs 9,000. What the numbers imply is a Rs 2,625 risk ((120-85) x
75). What actually exists: no GTT at Zerodha, no ticker subscription for that token, no
entry in the positions registry, so the 5-min scan's trail ratchet skips it, the T-1 expiry
square-off (_square_off_expiring iterates positions.open_positions) skips it, and the time
stop skips it. NIFTY reverses; nobody sells. The weekly expires worthless and the realized
loss is the full Rs 9,000 — 3.4x the risk the board displayed — and it is also never booked
into state.record_realized_pnl, so the INR daily-loss breaker (max_daily_loss_pct) does not
see it either and will not halt further entries.

### Manual BUY from the signal board creates a position with no stop, no monitor and no expiry square-off, while the same pane displays SL / TSL / Target for the leg

**high** · `backend/app/services/kite_engine/service.py:84`

same finding from a second angle.

A user opens a signal on the board. SignalDetailPane renders `PlanCell label="SL @ entry"` =
₹95 and `PlanCell label="TSL"` = ₹101 for the NIFTY24800CE leg
(SignalDetailPane.tsx:195-204), plus a red "TSL HIT" badge when breached — the pane visibly
promises a managed stop. They click BUY on that leg. `handleAction`
(SignalDetailPane.tsx:120-129) calls `openOrderWindow({symbol, exchange, initialSide,
lotSize, lastPrice})` — no stop is carried across. In OrderWindow, `slOn` initialises to
`false` and `slPct` to `0` (OrderWindow.tsx:86-87), so the protection block at
OrderWindow.tsx:244-251 is skipped and the body posted is a bare market BUY. Result: 1 lot
(75) at ₹120 = ₹9,000 outlay. The user believes their risk is (120−95)×75 = ₹1,875. Actual
enforced risk is ₹9,000 — a 4.8× overshoot — because nothing anywhere holds a ₹95 stop.
Because `positions.register` was never called, `monitor.on_tick` (which iterates
`pos.open_positions(uid)`) can never exit it, `_update_open_position_trails` never ratchets
it, and `_square_off_expiring` never squares it off, so the contract rides into expiry and
settles worthless. Even if the user manually ticks SL in the ticket, `buildProtectionGtt`
builds a static percentage GTT that never trails with the engine's SuperTrend.

### No code path anywhere exits at a target — Navigator's row.target / leg.premium_target are display-only

**medium** · `backend/app/services/kite_engine/scanner.py:177`

`row.target` / `leg.premium_target` are display-only. Design decision.

Navigator originates a CONFIRMED NIFTY long: AVWAP proposal accepted with stop 23,900 and
target 24,300 (target_r x risk). The board's Target column shows ₹259 (premium-translated)
with the tooltip "Navigator's AVWAP stop/target proposal". Spot reaches 24,300 intraday and
reverses. Nothing closes the position: `monitor.on_tick` only tests
`pos.should_exit(p.stop_premium, ltp, ...)` and the (broken) red count; the broker GTT is
single-leg SELL-on-downside only. The user sees a target the engine has no rule to take and
gives the whole move back to the trailing stop, while the R-multiple the proposal was gated
on is never realised.


## Unverified claims, worth checking (highest damage first)

> **Verification status as of 2026-08-13.** Nine of these were re-checked against the code
> as it stands. **All nine were already closed** — this section is largely historical, and
> the entries below should be read as leads to verify, not as a backlog to work through.
> Everything here predates four rounds of protection work; see
> `kite_protection_hardening_2026-08-06.md`.
>
> | Claim | Status | Closed by |
> |---|---|---|
> | `[critical]` orphaned GTT on reject / external exit (L383) | closed | live paths + `_reconcile_orphan_stops` |
> | `[critical]` `stop_mode="both"` double sell (L406) | closed | `_exit_position` cancels before selling |
> | `[critical]` GTT on a PENDING entry (L430) | closed | reject cancels, partial resizes |
> | `[critical]` zero premium → unprotected BUY (L459) | closed | auto-exec aborts; log reports what was armed |
> | `[critical]` red count from the entry-bar chip (L487) | closed | `current_reds` + `signal_direction` |
> | `[high]` 1-lot floor makes `risk_pct` advisory (L513) | closed | `blocked=True` + `_blocked()` at every call site |
> | `[high]` `_compile_rows` not idempotent (L586) | closed | copies rather than mutates |
> | `[medium]` GTT's flat 18% IV ≠ the on-screen stop (L867) | closed | `_effective_iv` solves from the quote |
> | `[medium]` futures sent an underlying-domain trigger (L754) | closed | `_futures_entry_and_stop` + `pos_expiry` |
>
> Each is now pinned by a test that fails when the fix is reverted. Two were fixed in the
> module but unpinned on the **caller** path, which is where the earlier rounds went wrong;
> those tests are the ones worth keeping.
>
> **Still unverified**, and the thread worth pulling next: auto-exec passes
> `spot=float(row.spot)` into the premium translation while the board uses
> `row.underlying_spot or row.spot`. For a derivatives-source row those differ — `spot`
> carries the option premium there, and `place_cb` runs on the raw row before grouping.
> Adjacent to `[medium]` L908.

### [critical] A rejected entry or an externally-filled exit closes the position but never cancels the broker GTT — an armed SELL is orphaned at Zerodha

`backend/app/services/kite_engine/monitor.py:95`

**Scenario claimed.** Rejection case: auto-exec places a BUY for 75 NIFTY 24000CE, Kite returns order_id ORD-1
(service.py:519). service.py:549 places GTT #555 = SELL 75 @ 85. Kite RMS then rejects ORD-1
asynchronously (margin shortfall / freeze-quantity / contract blocked); the postback arrives
with status REJECTED and order_id ORD-1. monitor.py:115-120 marks the position REJECTED and
releases the auto-open guard — and GTT #555 stays armed. Two hours later the premium drifts
to 84 and GTT #555 fires a market SELL of 75 NIFTY 24000CE the user never owned: a naked
short call, unlimited loss, and it is invisible to the engine because the registry says
REJECTED. The released guard also lets the next scan re-enter the same slot, so the user can
end up long 75 and short 75 on two different strikes. Manual-square-off case: the user
closes the position from the Kite mobile app. monitor.py:92-108 sees a COMPLETE SELL with a
foreign order_id, closes the registry, releases the guard, unsubscribes the token — and
leaves GTT #555 armed. Same naked short when the premium later touches 85.

**Suggested fix.** Give on_order_update a client handle (ticker_manager already has one via _warm_client) and
call `pstop.cancel_stop(client, p.gtt_id)` in both the broker-exit-fill branch and the
rejection branch, then zero p.gtt_id. Additionally add a startup/periodic GTT reconcile:
list get_gtts() and delete any trigger whose tradingsymbol has no OPEN registry position and
no non-zero broker net quantity.

### [critical] stop_mode="both" (default) arms the broker GTT and the tick monitor at the IDENTICAL trigger — a stop-out fires both and sells 2x qty, leaving a naked short option

`backend/app/services/kite_engine/service.py:548`

**Scenario claimed.** Defaults: stop_mode="both", auto_execute on. Auto-exec buys 1 lot NIFTY 24000CE, qty 75,
entry premium 120, stop_px 85. service.py:526-535 registers stop_premium=85;
service.py:549-552 places GTT #555 with trigger_values=[85]; service.py:538-541 subscribes
token 777 to the ticker. Premium prints 84.5. (a) Zerodha's GTT engine triggers and submits
a market SELL 75. (b) The same tick reaches our WS ~simultaneously ->
ticker_manager._broadcast -> monitor.on_ticks -> on_tick -> should_exit(85, 84.5,
"long")=True -> _exit_position places a second market SELL 75 (monitor.py:145) and only then
calls cancel_stop on an already-triggered GTT (monitor.py:152-153). Both fill. The user is
now short 75 NIFTY 24000CE with no long against it — unlimited upside loss and an
SPAN/exposure margin call on the next up-move. The registry books PnL exactly once (the
on_order_update double-book guard at monitor.py:92-93 works), so the board shows a clean
flat position while the broker account is short 1 lot.

**Suggested fix.** In "both" mode the two stops must not sit on the same price. Either (a) make _exit_position
cancel the GTT BEFORE placing the SELL and skip the SELL if the delete fails / returns
already-triggered, or (b) offset the monitor's trigger to be strictly tighter than the GTT
(monitor exits at stop*(1+eps) so it always wins and can cancel a still-resting GTT), or (c)
in "both" mode treat the GTT as the primary and have the monitor only act after a grace
window with no exit-fill postback.

### [critical] Protective GTT is placed on a PENDING (unfilled) entry and is never cancelled when the entry is REJECTED/CANCELLED → resting naked-short SELL at Zerodha

`backend/app/services/kite_engine/monitor.py:115`

**Scenario claimed.** stop_mode default is "both" (schemas.py:377), so every auto-exec entry gets a GTT. Auto-exec
fires on NIFTY, sizes 3 lots (qty 225) of NIFTY24800CE at entry_px ₹120, stop_px ₹95.
`client.place_order_option` returns order_id O1 (HTTP 200). register(status=PENDING) at
service.py:526. protective_stop.place_stop(qty=225, trigger_premium=95) at service.py:549
creates GTT #12345 = "SELL 225 NIFTY24800CE at market when premium ≤ 95". Two seconds later
Zerodha RMS rejects O1 (insufficient F&O margin / freeze-quantity / illiquid strike).
on_order_update hits monitor.py:115-120: status REJECTED → `pos.mark_rejected` → position
drops out of `open_positions`, guard cleared. GTT #12345 is still resting. Later that
session the premium prints ₹94 and the GTT fires: a market SELL of 225 NIFTY24800CE against
a ZERO long position = a naked short index call, unlimited upside risk, with SPAN+exposure
margin the user never budgeted. Our own side is blind to it: the SELL's COMPLETE postback
re-enters on_order_update, but the reconcile branch at monitor.py:92-93 requires `p.status
in (pos.PENDING, pos.OPEN)` and p.status is REJECTED, and the `is_entry` branches don't
match a different order_id — so the postback is silently dropped and nothing appears in the
engine terminal. The same hole exists for a partial fill that ends CANCELLED: 1 of 3 lots
filled → mark_rejected → GTT sells 225 against a 75 long = 150 naked short.

**Suggested fix.** In `monitor.on_order_update`, before/after `pos.mark_rejected`, cancel the broker stop: `if
p.gtt_id: await pstop.cancel_stop(client, p.gtt_id)` (the handler already accepts a `client`
kwarg — ticker_manager.py:63 must start passing it). Better still, defer
`protective_stop.place_stop` until the entry fill is confirmed (call it from the COMPLETE
branch of `on_order_update`, sizing the GTT to `order["filled_quantity"]`), and add a
startup pass that cancels any `trailexit`/protective GTT whose symbol has no OPEN position
at the broker.

### [critical] When the entry premium quote returns 0 the auto-exec still BUYs, gets NO GTT and NO monitor stop, and the activity log claims "[both stop+monitor]"

`backend/app/services/kite_engine/service.py:548`

**Scenario claimed.** 09:20 IST, spot-mode scan. NIFTY 1H SuperTrend fires; nearest-spot leg is NIFTY24800CE,
which has not traded yet today so Kite returns `last_price: 0` (or the quote call is rate-
limited and the bare `except` at service.py:167-168 swallows it). `_resolve_premium_stop` →
entry_premium = 0.0 → `premium_stop_from_move(entry_premium=0, ...)` returns 0.0 → entry_px
= stop_px = 0.0. Sizing is skipped (`cfg.risk_sizing and entry_px > 0 and stop_px > 0` is
False) so qty = 1 lot = 75. `place_order_option(..., stop_loss=None)` executes a real market
BUY at, say, ₹118 (₹8,850 outlay). service.py:548 `stop_px > 0` is False → no GTT is placed
and no warning fires (the `elif cfg.stop_mode == "broker"` warning only covers a place_stop
failure, and the default mode is "both" anyway). The token IS subscribed at
service.py:538-543, so the monitor looks armed, but `positions.should_exit(0, ltp, "long")`
returns False on every tick (positions.py:84). The terminal prints `BUY 75 (1 lot)
NIFTY24800CE @ market (#O1) [both stop+monitor]`. Next scan, `_new_trail_for_open` →
`_retranslated_stop` → `premium_stop_from_move(entry_premium=0, ...)` = 0.0, and `0 >
p.stop_premium (0)` is False → returns None, so the stop stays 0 permanently. The premium
collapses to ₹12: realized −₹7,950 on a position the board and log both said had a broker
stop plus a monitor backstop. Only `_square_off_expiring` (T-1) ever closes it.

**Suggested fix.** Treat an unresolved premium as a hard abort, not a degraded entry: if `not use_futures and
stop_px <= 0`, `state.log(uid, "order_blocked", ...)` and `return` before placing anything.
If the entry must be allowed, at minimum (a) log `order_blocked`-level warning "NO STOP" and
make the `order_placed` line report the stop actually installed rather than `cfg.stop_mode`,
and (b) let `_retranslated_stop` fall back to the confirmed `p.fill_price` when
`p.entry_premium <= 0` so the next scan can install a stop.

### [critical] Live red-count is read from the ENTRY-BAR alignment chip, so every PE (bear) auto-exec position is market-sold on the first tick after the first post-entry scan

`backend/app/services/kite_engine/service.py:748`

**Scenario claimed.** NIFTY fires a fresh BEAR signal (all three ST red at bar i). Auto-exec BUYs
NIFTY26AUG24000PE at ₹120, registers OpenPosition(direction="long", exit_mode="one_red",
stop_premium=90). The entry fills, status→OPEN. Five minutes later `scan_user` runs
`_update_open_position_trails`; the first scanner row matching underlying "NIFTY 50" is that
same bear row, whose `alignment` is the ENTRY bar's (-1,-1,-1). `want_red = -1` (because
p.direction=="long" for every option) → current_reds = 3. `positions.update_health` persists
3. On the very next WS tick, `monitor.on_tick` computes `reds=3 >=
get_exit_threshold("one_red")=1` → `_exit_position` places a market SELL of all 75 qty with
reason "red count exit 3/1 (one_red)". The trade is closed minutes after entry at whatever
the premium happens to be, even though the SuperTrend has not flipped against it at all — it
is still perfectly aligned WITH it. Verified by running the real
`service._update_open_position_trails` against a stubbed snapshot: current_red_count written
= 3, red_exit = True; the CE mirror wrote 0.

**Suggested fix.** Stop deriving reds from the stale entry-bar chip. Either (a) have the scanner stamp a
separate live field (e.g. `row.current_reds` computed via `r.red_line_count(direction,
last_idx)` at the latest bar — `_exit_state_str` already does exactly this at `end_idx`) and
read that, or (b) map the row's own SIGNAL direction, not the position's premium side, into
`want_red` (`want_red = -1 if row.direction == "long" else 1`) and drop the `break` so a
counter-direction row cannot be picked. Also match rows by direction/leg, not just
underlying.

### [high] The 1-lot floor makes risk_pct advisory, not a cap: a 1% setting routinely takes ~15% of capital on one index option trade

`backend/app/services/kite_engine/sizing.py:374`

**Scenario claimed.** cfg defaults: risk_sizing=True, risk_pct=1.0, max_lots=10. Account available_fo_capital = Rs
50,000. Spot NIFTY 24,000, 1H ST trail at 23,700. Auto-exec resolves the near-ATM CE:
entry_px = 120 (LTP), delta 0.35, stop_px = premium_stop_from_move(120, 0.35, 24000, 23700)
= 120 - 105 = 15. sizing.py:358-359: risk_per_unit = 105, risk_per_lot = 105 x 75 = Rs
7,875. sizing.py:367: budget = 50,000 x 1% = Rs 500. sizing.py:368: by_risk = 500 // 7875 =
0. sizing.py:372: by_margin = 50,000 // (120 x 75 = 9,000) = 5. sizing.py:374-378: lots =
max(1,0) = 1, min(1,10) = 1, min(1,5) = 1. Order goes in with est_risk Rs 7,875 = 15.75% of
the account on a setting labelled 1%. Log line reads "risk/lot Rs 7875 > budget Rs 500 (1.0%
of Rs 50000) - floored to 1 lot", i.e. the system tells the truth in the activity feed and
does the opposite of the configured policy. Two such positions open concurrently (both-mode
/ two indices) put >30% of the account at risk with the drawdown breaker off by default
(wire_risk_infra=False) and the INR daily-loss breaker off by default
(max_daily_loss_pct=None).

**Suggested fix.** Add a hard `skip_if_over_budget` policy (default on for real money): when `by_risk < 1`,
block the entry and log "skipped - 1 lot risks X% > risk_pct" instead of buying, or at
minimum expose the realised risk percentage on the board/order confirm so the operator sees
15.75% rather than the configured 1%.

### [high] Retained (non-fresh) spot rows resolve their strike ladder at TODAY's spot but stamp the entry premium from the signal bar — fake Entry, fake P&L, wrong moneyness label

`backend/app/services/kite_engine/expiry_series_runtime.py:234`

**Scenario claimed.** A NIFTY long fires 12 sessions ago at spot 24,000, trail still intact, so `_retain_signals`
keeps it (`is_active=True`, `is_fresh=False`). NIFTY is now 25,100. Each scan re-runs
`evaluate_item` → fresh row objects → `attach_strikes`. Because `is_fresh` is False,
`expiry_series_compat._resolve_with_fresh_trigger_spot` does NOT null `latest_spot`, so
`resolve_option_legs` picks strikes around 25,100: the leg is labelled "ATM" at strike
25,100. `_stamp_spot_leg_premiums` then fetches that contract's history and takes the last
bar `<= row.timestamp_ms`, i.e. the 25100CE's close 12 days ago when it was 1,100 points OTM
≈ ₹25, and writes `leg.premium_spot = 25`. `_stamp_leg_premium_stops` derives `premium_sl`
from `row.stop_loss` (today's ratcheted trail, ~24,800) against `spot = row.spot = 24,000`,
giving ~₹145. The board renders Entry ₹25, TSL ₹145, chip "ATM", and `entryDiff = lastPx -
entryPx` shows roughly +₹155 (~+620%) on a position nobody could have taken at that
strike/price pairing. The moneyness chip is also provably wrong relative to `row.spot`: at
24,000 the 25,100 strike was OTM, not ATM.

**Suggested fix.** Drop the `is_fresh` condition in `expiry_series_compat._resolve_with_fresh_trigger_spot` and
always resolve strikes at `row.spot` (the trigger-bar spot), so strike, moneyness label and
entry premium all come from the same bar. If a current-spot ladder is genuinely wanted for
old running setups, it must be a separate 'roll' row whose entry premium is today's LTP, not
the signal bar's close.

### [high] premium_stop_from_move clamps to 0 at realistic trail distances, and stop_px==0 silently means NO broker GTT, NO monitor stop and NO risk sizing — a naked long option

`backend/app/services/kite_engine/greeks.py:98`

**Scenario claimed.** NIFTY spot 24,000, fresh bull, fast ST trail at 23,850 (150 pts). Auto-exec resolves the
OTM2 leg NIFTY 24200 CE, 3 DTE, LTP ₹30 (solved IV ~0.11, delta 0.220).
`_resolve_premium_stop` → `premium_stop_from_move(30, 0.220, 24000, 23850) = max(0, 30 - 33)
= 0.00`. Then: (1) `place_order_option(..., stop_loss=None)` — no stop on the order; (2) `if
cfg.stop_mode in ("broker","both") and stop_px > 0` is False → no GTT is placed AND the
`elif cfg.stop_mode == "broker"` warning is nested inside that block so nothing is logged;
(3) `positions.register(... stop_premium=0.0, initial_stop_premium=0.0)` → `should_exit(0,
ltp)` returns False on every tick forever; (4) the `elif cfg.risk_sizing and entry_px > 0
and stop_px > 0` sizing branch is skipped, so qty stays `args["size"]`. The position rides
to ₹0. The correct stop is not 0: repricing the same contract with the same BS model at
spot=23,850 gives ₹8.65. Even where the clamp does not bite, the linear model systematically
under-prices a convex long option: NIFTY 24100 CE prem ₹60 → linear stop ₹5.62 vs true BS
₹21.31 at the trail, i.e. the stop sits 74% too low and gives back 3.8x the premium the
trail intends.

**Suggested fix.** Reprice the option at the trail level instead of extrapolating linearly:
`bs_price(spot=trail_level, strike, dte_days, iv, option_type)` is already in the same
module and is convexity-correct and never negative. At minimum, treat a clamped-to-zero
result as a hard error: refuse the entry (or force `stop_mode` to a monitor-side underlying-
level exit) and log `order_blocked`, rather than registering a position with
`stop_premium=0` that every guard silently skips.

### [high] _compile_rows is not idempotent over already-grouped rows; held_contract_scan re-runs it and silently drops every derivative leg except the first

`backend/app/services/kite_engine/held_contract_scan.py:215`

**Scenario claimed.** scan_source = "derivatives" (or "both"), strike ladder ITM1/ATM/OTM1 (or the full ITM5..OTM5
ladder that expiry_series_runtime defaults to). NIFTY fires BUY on three CE strikes →
`_flush()` builds one parent ("NIFTY 50","CE") with legs [ATM 24500, ITM1 24000, OTM1
25000]. The user also holds one broker NFO option that has drifted off the ladder, so
`pending` is non-empty. The held-contract wrapper (outermost, installed last at
__init__.py:20) then runs `us.rows = _compile_rows([*us.rows, *appended])`. Verified by
execution:   pass1 rows 1 legs ['N24500CE', 'N24000CE', 'N25000CE']   pass2 rows 1 legs
['N24500CE'] The board now shows one strike per underlying/type instead of three, and
`state.save_signal_cache` persists it. Knock-on live-money effect:
`service._update_open_position_trails` runs AFTER the wrapper, and `_new_trail_for_open`
looks for `leg.option_symbol == p.symbol` in `row.legs`. For an open otm_options position
whose leg was just dropped, no leg matches; it falls through to `_retranslated_stop`, which
needs `row.stop_loss > 0` — but the grouped derivatives parent has `parent.stop_loss = 0`
(scanner.py:303) — so it returns None and the trailing stop / broker GTT for that position
stops ratcheting entirely.

**Suggested fix.** Make `_compile_rows` fold ALL of `r.legs`, not just `r.legs[0]` (iterate legs and merge each
by `option_symbol`), so re-compiling a grouped parent is a no-op. Alternatively have
`held_contract_scan` append to `us.rows` without re-compiling (it only needs to merge new
single-leg rows), and add a regression test that asserts `_compile_rows(_compile_rows(x)) ==
_compile_rows(x)`.

### [high] `on_order_update` guards double-booking on status only, not on the `_exiting` claim — the monitor's own exit fill can be booked twice while `_exit_position` is still awaiting the GTT cancel

`backend/app/services/kite_engine/monitor.py:92`

**Scenario claimed.** stop_mode="both" (default), so `p.gtt_id > 0` and the cancel round-trip always runs. Trail
breach on NIFTY24800CE (entry ₹120, qty 225). `on_tick` → `_exit_position`: `_exiting`
claims the key, `place_order_option(sell, 225)` returns after ~120 ms, then `await
pstop.cancel_stop(client, 12345)` blocks for another ~150 ms. Zerodha's order postback for
the SELL (COMPLETE, average_price ₹94, order_id EXIT-1) arrives on the WS during that 150 ms
and `ticker_manager` (ticker_manager.py:63) awaits `monitor.on_order_update`. At
monitor.py:92 status==COMPLETE, txn==SELL==exit_side, `is_entry` False, and `p.status` is
still OPEN (pos.close has not run) → the reconcile branch fires: `pos.close(...)` +
`_record_realized(uid, p, 94.0)` books (94−120)×225 = −₹5,850. `_exit_position` then resumes
and books −₹5,850 again at monitor.py:158 → day total −₹11,700 for a real −₹5,850 loss. With
`max_daily_loss_pct = 2%` on ₹500,000 capital the breaker at service.py:323-330 halts all
new entries at half the intended limit. The mirror case is worse: a WINNING exit double-
books +PnL, so a real cumulative loss reads as break-even and the breaker fails to halt when
it should.

**Suggested fix.** Add `or (uid, symbol) in _exiting` to the skip condition at monitor.py:92, i.e. `and
p.status in (pos.PENDING, pos.OPEN) and (uid, symbol) not in _exiting`. Alternatively, tag
exit orders (`_exit_position` already sends `tag=f"trailexit:{p.symbol}"`) and have
`on_order_update` ignore any postback whose tag starts with `trailexit:`, since those are
always our own.

### [high] Partial fills are never read: `filled_quantity` is ignored, so both the GTT and the monitor exit the intended quantity, and a CANCELLED-after-partial entry abandons a live position

`backend/app/services/kite_engine/monitor.py:112`

**Scenario claimed.** Auto-exec buys 5 lots (qty 375) of a thinner weekly strike at market. The book absorbs 2
lots (150) and the remainder is cancelled by the exchange/RMS. Two outcomes, both bad: (a)
the postback arrives as COMPLETE with `filled_quantity: 150` — `mark_filled` sets status
OPEN with `p.qty` still 375; when the trail breaks, `_exit_position` places
`place_order_option(symbol, "sell", 375)` against a 150 long → 225 naked short index calls;
the GTT at #12345 would do the same. (b) the postback arrives as CANCELLED with
`filled_quantity: 150` — monitor.py:115 matches `_DEAD_STATUSES`, so `pos.mark_rejected`
drops the position out of `open_positions` and releases the guard, even though 150 contracts
are genuinely held: no trail, no monitor, no expiry square-off, and the engine is now free
to BUY the same slot again on the next bar, doubling the exposure it thinks is zero.

**Suggested fix.** Read `int(order.get("filled_quantity") or 0)` in `on_order_update`: on COMPLETE set `p.qty`
to the filled quantity (and re-issue `move_stop` with the corrected size); on a dead status
with `filled_quantity > 0`, do NOT `mark_rejected` — set `p.qty = filled_quantity`,
`mark_filled`, keep the guard, and resize the GTT. Only mark rejected when the filled
quantity is genuinely zero.

### [high] A still-running Navigator-originated row re-stamps its trigger time, entry premium, stop, target and even its strike to the LATEST bar on every scan — its Entry can never show open P&L

`backend/app/services/navigator/service.py:454`

**Scenario claimed.** Navigator confirms NIFTY 50 long Monday 10:15; at that moment NIFTY25AUG24500CE is ₹112 and
the accepted AVWAP stop is 24,780 (premium SL ≈ ₹86). The decision stays CONFIRMED, so
`prior_is_live_origin` is true and `state='active'` (is_active=True) on every subsequent
scan. By Wednesday 14:15 the contract is ₹268. The board shows ONE row under "Active now":
header time "14:00 Wed", Entry "265.40" (Wednesday's 14:00 option close), Entry(Δpts)
"(+2.60)", and SL/TSL re-translated from Wednesday's AVWAP stop off a ₹265 entry. The ₹156
the idea actually made is nowhere on the board, and the row reads as a setup that fired
minutes ago. If spot has moved a strike step, `attach_strikes` also swaps the leg to a
different contract while the row still presents as the same continuously-running idea.

**Suggested fix.** Persist the origination bar. When `prior_is_live_origin`, carry the prior row's
`timestamp_ms`, resolved legs and `premium_spot`/`entry_sl`/`premium_target` forward (only
`premium_sl` should re-derive, if there is a trail at all) instead of rebuilding from
`candles[-1]`. Navigator's decision cache already knows the row is the same lifecycle —
`_row_lifecycle_key` — so the prior row is available to copy from in
`_merge_with_lifecycle`.

### [high] Signal markers are keyed by row.token, which is NOT unique per row — the watchlist/ticker ✝▲ ends up on the last-rendered row's strike, including a dead signal's

`frontend/src/components/kite/SterlingKiteEnginePane.tsx:532`

**Scenario claimed.** NIFTY has two spot rows on the board: (A) a BULL/CE entry from 30 Jul that is still running,
legs ATM 24500CE / ITM1 24400CE / OTM1 24600CE, ✝ on 24500CE; and (B) a BEAR/PE entry from
28 Jul that has since exited, legs 24100PE/24000PE/24200PE, ✝ on 24100PE. Both have token
256265. Row A is in the 'Active now' bucket, row B is in the 'Yesterday (ended)' bucket,
which renders AFTER it (SterlingKiteEnginePane.tsx:2450-2480, buckets pushed active-first).
React commits passive effects in tree order, so B's `publishMarkers('256265',
{NFO:NIFTY...24100PE:{rr:true}, ...})` runs last and overwrites A's entry. The market
watchlist and the ticker then show the ✝ "best reward-to-risk" marker on 24100PE — a PUT
from a dead bearish signal — and show NO marker on 24500CE, the strike of the live bullish
signal. Same mechanism with the code's own documented case (comment at
SterlingKiteEnginePane.tsx:1972-1977: "NIFTY BANK long on 27, 29 and 30 Jul, all
'running'"): those three rows have different ATM strikes, and the marker that survives is
the OLDEST entry's, because 'Active now' is stably sorted descending by timestamp so the
oldest row renders last.

**Suggested fix.** Publish under the row's real identity: `const rowKey =
`${row.token}:${row.option_type}:${row.timestamp_ms}``, matching
SterlingKiteEnginePane.tsx:1925 and the React key at 2470. Since `flatten()` already OR-
merges across rows, that alone stops the clobbering — but then decide the semantics
deliberately: an ENDED row should probably not publish markers at all (skip publish when
`!rowRunning`), otherwise a dead signal's strike still wears ✝ in the watchlist alongside
the live one.

### [high] Confluence rows: "Active now" bucket and the footer live-count ignore the live-LTP stop reconciliation the card itself applies, so a row says "running" while its own body says every leg ended

`frontend/src/components/kite/SterlingKiteEnginePane.tsx:347`

**Scenario claimed.** scan_source='confluence'. Board has one NIFTY 50 CE confluence row, backend `is_active:
true`, single leg NIFTY25JUN24000CE with `premium_spot: 120.5`, `premium_sl: 100.0`. Live
LTP ticks to 96.00 (through the trail). Then: `rowIsRunning` -> `rowIsLive(row)` -> true, so
the row is placed under the green "Active now" header and is counted in the footer pill "1
live". Inside the card, `legIsExited(leg)` -> `legHasExited(leg, true, 96)` -> `liveExited =
96 <= 100` -> true, so the leg renders with Entry struck through, the "Past setup ... live
premium has fallen through the stop" tooltip, and no Entry(Δpts). With the Ended toggle off,
`visibleLegs` is empty and the card body under "Active now" prints "All resolved legs are
ended. Enable Ended to view them." One row, two contradictory verdicts, plus a live-count of
1 for a position with nothing live in it.

**Suggested fix.** Change the guard to match the card: `if (row.source !== 'derivatives' && row.source !==
'confluence') return rowIsLive(row);` — or better, derive both from one
`legIsExited`-equivalent that takes `hasPremium` so the bucketing and the card literally
call the same function.

### [high] On expiry day the card's client-side greeks get dte = 0, so EVERY leg is 'unsolved' and the board loses all ✝/▲ badges and all Δ readouts — while the detail pane still shows them

`frontend/src/utils/computeGreeks.ts:129`

**Scenario claimed.** Thursday 6 Aug 2026, 10:00 IST, NIFTY weekly expiry day (the highest-volume day of these
contracts). A live BULL row shows legs 24400CE/24500CE/24600CE. In the card, `new
Date('2026-08-06').getTime() - Date.now()` is negative → `dte = 0` (verified: node prints 0
for 10:00 IST on expiry day, and 0.8125 for 10:00 IST the day before, where the true value
to the 15:30 IST close is 1.23). Every leg gets `{iv:0, delta:±1|0, gamma:0, theta:0}` →
`solved:false` → `selectBestLegs` returns `{bestR:null, bestDelta:null, rankable:0}`. Result
on screen: no ✝, no ▲ on any strike, the per-leg `(Δ…)` readout at
SterlingKiteEnginePane.tsx:947 is blank for every leg, no markers reach the watchlist, and
the 'Best ✝▲' quick-toggle becomes a silent no-op for the entire board (keep.size === 0 →
the filter falls back to showing all legs). Click the same signal open and the detail pane
DOES show ✝ and ▲, because detail.py computes `dte_exact = intraday_dte_days(...) ≈ 0.23
days` and back-solves IV from the LTP — so the two panes give contradictory answers about
the same signal on the same screen. The day-before case is a quieter version of the same
bug: t is understated by ~34%, and since theta ∝ 1/√t the carry penalty is inflated, which
biases the ✝ ranking against ATM legs.

**Suggested fix.** Port `intraday_dte_days` to the frontend: parse `expiryStr` as a 15:30 IST instant (`new
Date(`${expiryStr}T15:30:00+05:30`)`) and use fractional days, in BOTH
`computeGreeksFromLeg` (computeGreeks.ts:126) and `parseExpiry`/`computeGreeksFromSymbol`
(computeGreeks.ts:34-51, 106). Better still, stop recomputing greeks client-side for the
board and reuse the backend's already-solved per-leg greeks (`greeks_solved`, `delta`,
`gamma`, `theta`) that detail.py:150-154 emits, so the card and the detail pane cannot
diverge by construction.

### [medium] Futures vehicle sends an UNDERLYING-domain price as the futures contract's entry, stop and GTT trigger, and stores no expiry so it is never squared off

`backend/app/services/kite_engine/service.py:380`

**Scenario claimed.** Set directional_mode=True, add "futures" to enabled_vehicles, vehicle="futures". NIFTY spot
24,000, near-month future trading 24,065 (basis +65). row.stop_loss = 23,700.
service.py:380-381 sets entry_px=24,000, stop_px=23,700. sizing.size_future_position
computes risk_per_lot = 300 x 75 = Rs 22,500, but the fill is at 24,065 so the real distance
to 23,700 is 365 pts = Rs 27,375 — 22% more risk than sized. protective_stop.place_stop then
puts the GTT on the FUTURES symbol at trigger 23,700 with last_price 24,000 (a stale, wrong
reference for that contract). Second failure: p.expiry == "", so on the last Thursday
_square_off_expiring skips the position (service.py:597 `_is_expiring(p.expiry, ...)`
returns False at service.py:575 for an empty string). The contract cash-settles at the
exchange; our registry keeps it status=OPEN forever, state.clear_auto_open is never called
so the underlying's guard slot is blocked against re-entry indefinitely, and the monitor
keeps evaluating a dead instrument token.

**Suggested fix.** Quote the resolved futures contract (get_ltp on fp.tradingsymbol) for entry_px, translate
row.stop_loss into the futures domain by the observed basis (or simply stop on the futures
price with the same point distance), and copy fp.expiry into OpenPosition.expiry so the
expiry square-off covers futures too (or implement the roll the docstring at schemas.py:359
promises).

### [medium] Badge scoping contradicts itself across panes: the board computes ✝/▲ PER moneyness bucket (up to 3 of each per signal) but the watchlist/ticker marker, the detail leg list and the calculator all present a single winner "among this signal's strikes"

`frontend/src/components/kite/SignalMarker.tsx:17`

**Scenario claimed.** A BANKNIFTY BULL signal resolves ITM5…OTM5. On the board the user sees ✝ on ITM1, ATM and
OTM5, and ▲ on ITM5, ATM and OTM1 — six badges, correctly labelled per bucket. They pin ITM1
and OTM5 to the ticker; both now show a grey ✝ whose tooltip reads 'Best reward-to-risk
among this signal's strikes', i.e. two contracts each claiming to be the single best strike
for the same signal. They then click the row to open the detail page: the Option-legs list,
the Trade Impact Calculator and the Premium breakdown all put a single ✝ on OTM5 and a
single ▲ on ITM5 (per finding #2 the ITM1 and ATM crosses simply vanish), so two of the
three strikes the board recommended silently lose their recommendation on click-through with
no explanation. Cross-pane, the ▲ can also differ outright because the board solves greeks
client-side from the live tick with `spot = uLastPx` (SterlingKiteEnginePane:491,499) while
the detail uses backend greeks solved from `spot_ref = spot_now or row.spot` at the last 15s
detail refresh (detail.py:92,121) — two different spots, two different IVs, potentially two
different winners for the same leg set at the same moment.

**Suggested fix.** Pick one scope and enforce it in impactMath: either export a single `pickBadges(legs, spot,
stop, {perBucket})` used by all four sites, or drop bucketing on the board. At minimum,
propagate the scope into the published marker so SignalMarker's tooltip can say 'best
reward-to-risk in its ITM/ATM/OTM group' when that is what it means, and make the detail
sites bucket the same way so a click-through never removes a badge the board just showed.

### [medium] Watchlist/ticker markers are published under `String(row.token)`, which collides for the re-entry rows the board is explicitly designed to show — last card wins, and one card unmounting clears the markers of the others

`frontend/src/components/kite/SterlingKiteEnginePane.tsx:525`

**Scenario claimed.** BANKNIFTY (token 260105) trends for a week: the board shows the Monday original plus two re-
entry rows, three SignalCards, all with `rowKey = '260105'`. Because
`bestRRSyms`/`bestDeltaSyms` are rebuilt from `quotes` on every tick (dep array line 517),
all three effects re-run every tick and publish into the same key; the last card committed
wins, so the ✝/▲ that appear in the market watchlist and the ticker are always the stale re-
entry row's picks, never the original trade's — and the three rows can resolve different
strikes because attach_strikes resolved each against a different spot. The user pins the
contract the original row marked ✝ and sees no marker on it, while a strike they were never
shown a cross for wears one. Then the board re-sorts or 'Ended' is toggled and one of the
three cards unmounts: its cleanup runs `clearMarkers('260105')` (line 536), deleting the
surviving cards' entries too, so every ✝/▲ for that instrument disappears from the watchlist
and ticker until the next publish. The same collision applies to a CE row and a PE row on
one underlying (both carry the underlying token for spot/confluence/navigator sources).

**Suggested fix.** Use the same identity as the React key: `const rowKey =
`${row.token}:${row.option_type}:${row.timestamp_ms}`;` at line 525. `flatten()` already OR-
merges across rows, so distinct keys give the correct union and an unmount only removes that
card's own contribution.

### [medium] Derivatives-source is_fresh is measured against the CONTRACT's own last candle, so an illiquid strike with a stale last bar fires auto-exec as a live trigger

`backend/app/services/kite_engine/scanner.py:925`

**Scenario claimed.** scan_source = "derivatives", auto_execute ON, a monthly stock OTM3 CE whose last trade was
Wednesday 14:15. On Friday the scan fetches its premium history; `drop_forming` does not
drop the Wednesday bar (its hour is long closed), so `oc[-1]` = Wednesday 14:15. If the
premium's triple-ST completed a fresh long transition on that bar,
`evaluate_derivative_contract` sets `is_fresh=True` (ts == latest_ts) and `_deriv_one` calls
`place_cb(drow, item)` — a real market BUY placed on Friday against a two-day-old, never-
since-traded premium signal, sized off `leg.premium_spot` = Wednesday's close and stopped at
Wednesday's ST trail. `live_safety.make_idempotency_key(..., row.timestamp_ms)` does not
help: this is the first time that (symbol, ts) combination is submitted. The board
simultaneously badges it as a just-fired signal. The same shape produces a false Monday-
morning re-trigger of Friday's last bar.

**Suggested fix.** In `_deriv_one`, carry the underlying's last closed bar timestamp (already available as
`under[-1].timestamp_ms`) and compute `is_fresh = (drow.timestamp_ms == latest_ts ==
under_latest_ts)`, mirroring the confluence guard — or at minimum refuse `place_cb` when
`oc[-1].timestamp_ms` is older than the underlying's last closed bar.

### [medium] A failed GTT trail move is silent: the board and registry show the tightened stop while the broker stop stays at the entry level

`backend/app/services/kite_engine/service.py:734`

**Scenario claimed.** stop_mode is set to "broker" (the GTT is then the only protection — service.py:538 only
subscribes the ticker for "monitor"/"both"). NIFTY24800CE bought at ₹120, GTT #12345 placed
at ₹95. The user separately deletes that GTT from the Kite web console, or Zerodha rate-
limits the modify. Over the session the SuperTrend trail ratchets and `_new_trail_for_open`
returns ₹180. `positions.update_stop(uid, p.symbol, 180)` commits, `state.log(... "Trail
updated ... ₹95.00 → ₹180.00")` is written, and EnginePositionsPane.tsx:143 renders
`180.00`. `move_stop` then 404s / errors; `moved` is False; the `if moved:` at
service.py:734 skips, so the only trace is a server-side `log.warning` the user never sees.
The premium reverses to ₹40. Real loss (120−40)×75 = −₹6,000 on a position whose board row
claimed a ₹180 stop, i.e. a locked +₹4,500. Total swing vs. the displayed protection:
₹10,500 per lot-block.

**Suggested fix.** Emit a user-visible `state.log(uid, "order_failed", f"⚠ Broker GTT #{p.gtt_id} did NOT trail
to ₹{new_sl:.2f} for {p.symbol} — broker stop still at ₹{old_sl:.2f}")` in an `else` branch,
and track the last broker-confirmed trigger separately from the registry stop (e.g.
`p.broker_stop_premium`) so the positions API can surface the divergence. On repeated
failures, re-place the GTT (`place_stop`) rather than leaving a stale one.

### [medium] The GTT actually placed uses a flat 18% IV while the board's SL/TSL backs IV out of the entry premium — the broker stop is not the stop on screen

`backend/app/services/kite_engine/service.py:153`

**Scenario claimed.** AXISBANK bear row (the repo's own test fixture: spot 1228.9, ST trail 1250.0, 1260 PE, ~30
DTE) with an entry premium of ₹80. The board computes solved IV 0.473 → delta -0.531 → shows
TSL ₹68.80. Auto-exec computes flat IV 0.18 → delta -0.639 → places the GTT at ₹66.52. The
user sizes and reasons off ₹68.80; the resting broker order is ₹66.52 — 2.8% of premium
lower. The gap widens with the IV error, which is exactly the stock-option case the
`_stamp_leg_premium_stops` comment says the flat assumption was wrong for ("badly wrong for
stock options (25-45%)").

**Suggested fix.** Have `_resolve_premium_stop` solve IV from the fetched LTP exactly as
`_stamp_leg_premium_stops` does (`implied_vol(price=entry_premium, ...)`, falling back to
`_IV_ASSUMPTION` only when it returns 0), or better, extract one shared
`premium_stop_for_leg()` used by both the board and auto-exec so the number shown is by
construction the number placed.

### [medium] Confluence entry premium is overwritten with the STILL-FORMING 1H bar's close, so the Entry column repaints every 5 minutes and diverges from the entry actually recorded for the order

`backend/app/services/kite_engine/signal_board_runtime.py:427`

**Scenario claimed.** Confluence mode, 10:20 IST. The last closed 1H underlying bar is 09:15; the 10:15 bar is
forming. `_confluence_one` sets `leg.premium_spot = float(oc[-1].close)` = the option's
09:15 close, say ₹120, and `leg.premium_sl` / `leg.entry_sl` = the premium ST trail off that
same closed bar, ₹105. `place_cb` runs at this point, so `option_order_args` hands sizing
`entry_premium=120, stop_premium=105` (risk ₹15/unit) and
`positions.register(entry_premium=120)`. Then the wrapper's `_apply_current_premiums`
overwrites `leg.premium_spot` with the 10:15 forming close, say ₹158. The board now shows
Entry ₹158 against SL ₹105 for a position the system recorded at ₹120, and at 10:25 the next
scan re-stamps it again (the row is still `is_fresh` — `latest_ts` does not change until
11:15), so the Entry cell moves on every poll. A user reading the board sees ~₹0 unrealised
P&L on a fill that is actually +₹38, and the SL/Entry pair implies a risk that matches
neither the sized order nor the displayed entry.

**Suggested fix.** Record the anchor close from the drop_forming'd series (or record `candles[-2]` when
`candles[-1]` is still forming) so `_apply_current_premiums` can never stamp a partial bar.
Better: leave `premium_spot` as the closed-bar entry the order path already used, and
surface the live premium through the existing quote stream instead of mutating the entry
field.

### [medium] For 'derivatives' rows the ✝ ranking and the Impact Calculator's "Risk to stop" are built on a fabricated 1R, because row.stop_loss is a PREMIUM level fed into an UNDERLYING stop-distance — the leg's real premium stop is ignored

`frontend/src/components/kite/SignalImpactCalculator.tsx:93`

**Scenario claimed.** NIFTY derivatives row, underlying 24000, contract 24000CE 3 DTE: entry premium ₹120,
premium_sl (real trail) ₹95, δ 0.52, γ 0.0009, θ −8.5/day, lot 75. `stopDistance(24000,
95)`: d = 23905, which is > 24000*0.5, so it returns `defaultMove(24000)` = 100. `hasStop` =
(95 > 0) && (100 <= 12000) = TRUE, so the UI asserts this is the signal's own stop.
`computeLegImpact` then reports risk = min(120, 0.52*100) = 52 → "Risk to stop" per lot = 52
× 75 = ₹3,900, described to the user as the loss if the underlying hits the signal stop. The
trade's actual risk to its actual stop is (120 − 95) × 75 = ₹1,875 — the screen overstates
it by 2.1×, and the ✝ ranking divides by that wrong denominator, so a cheap OTM leg whose
`min(premium, δ·m)` collapses to its premium can outrank the leg with the genuinely tighter
premium stop. The card (SterlingKiteEnginePane.tsx:512) makes the same substitution, so the
badge and the calculator are consistently wrong rather than disagreeing.

**Suggested fix.** Make the risk domain-aware. When the row is 'derivatives' (or any leg that carries
`premium_sl`/`trail_stop_premium` > 0), set risk = `premium - premium_sl` per share directly
instead of `min(premium, |δ|·m)`, and derive the reward horizon from the premium series
rather than a spot move. Separately, fix `hasStop` to test the RAW stop (`const d =
Math.abs(spot - data.stop_loss); const hasStop = data.stop_loss > 0 && d > 0 && d <= spot *
0.5;`) so the ½R/1R/2R/3R labels and the "risk to the signal stop" wording only appear when
a real underlying stop was accepted.

### [medium] Board row key omits `source`, so a SuperTrend row and a Navigator row for the same underlying/bar collide — one silently disappears mid-scan

`frontend/src/components/kite/SterlingKiteEnginePane.tsx:1915`

**Scenario claimed.** The 14:15 1H bar closes. The SuperTrend scan fires a fresh spot long on NIFTY 50 (token
256265, option_type 'CE', timestamp_ms = 14:15 bar close). Navigator's independent pass,
which fetches the same 1H series and applies the same `drop_forming` rule, originates NIFTY
50 long on the same bar (token 256265, option_type 'CE', timestamp_ms = the same bar close).
The API keeps both — `_signal_row_key` includes `row.source` and the leg symbol — and emits
them ordered base_rows-then-navigator-rows (the sort key `(is_fresh or is_active,
timestamp_ms)` is identical for both and `sorted` is stable). The board is scanning (a full
universe scan takes ~2 min per `fmtTime`, and the engine re-scans every ~5 min), so the
`rows` memo runs `for (const r of rawRows) merged.set(rowKey(r), r)` — both map to
`"256265:CE:1753..."`, the Navigator row is set last and OVERWRITES the SuperTrend row. The
live SuperTrend entry — the one the auto-exec path is acting on — vanishes from the board
for the duration of the scan, then reappears when scanning ends. When scanning ends both
render, and line 2477 emits two sibling `<div>`s with the identical `key`, so React
reconciles them as one slot: the per-card `expanded` leg state (line 446) and the quote-
detail expansion get attributed to the wrong row.

**Suggested fix.** Add `source` (and, for grouped rows, the first leg symbol) to `rowKey` and to the React list
key so the frontend key is a superset of the backend's `_signal_row_key`: `${r.source ??
'spot'}:${r.token}:${r.option_type}:${r.timestamp_ms}:${r.legs[0]?.option_symbol ?? ''}`.

### [medium] Navigator rows print the same number in SL and TSL, under a tooltip describing a SuperTrend ratchet the row does not have

`frontend/src/components/kite/SterlingKiteEnginePane.tsx:1027`

**Scenario claimed.** Navigator originates NIFTY 50 long, AVWAP stop 24,780, entry premium ₹265, delta 0.52, spot
24,930. `premium_stop_from_move(265, 0.52, 24930, 24780) = 187.0` is written to BOTH
`leg.entry_sl` and `leg.premium_sl`. The row renders SL "187.0" and TSL "187.0" side by
side, Exit "—", and the header badge "TSL 24780.0". A user reads two independent protection
levels and an active trailing mechanism where there is one static AVWAP stop and no trail at
all — and no ST-driven exit is running against this row, so nothing will move that 187.0
except the next scan re-deriving it from a new AVWAP and a new entry premium (see the
previous finding).

**Suggested fix.** Make the SL/TSL cells and the header badge source-aware: for `row.source === 'navigator'`
render the TSL cell as "—" (or collapse SL/TSL into a single "AVWAP stop" cell) and swap the
tooltips for the AVWAP wording the detail pane already uses (`ENGINE_BY_SOURCE.navigator`,
SignalDetailPane.tsx:66-69, and its `isNav ? 'AVWAP stop' : 'Stop at entry'` PlanCell
label).

### [medium] The "re-entry" badge is computed after lens filtering, so switching lenses can hide the original entry and make a re-arm look like an independent new setup

`frontend/src/components/kite/SterlingKiteEnginePane.tsx:1992`

**Scenario claimed.** exit_mode is 'two_red' (so the engine legitimately keeps concurrent still-running
transitions — the case the code comment at :1986-1991 documents: "NIFTY BANK long on 27, 29
and 30 Jul, all running"). NIFTY BANK long entries exist at 27 Jul (running, no Navigator
evidence attached) and 30 Jul (running, Navigator CONFIRMED). In Combined lens both rows
show and the 30 Jul row correctly wears "re-entry". Switch the VIEW dropdown to Navigator:
`filteredRows` drops the 27 Jul row (`r.navigator == null`), `originalEntryMs` for `NIFTY
BANK|long|spot` becomes 30 Jul, the badge disappears, and the 30 Jul row now reads as the
original entry — while auto-exec's one-position-per-instrument guard will never actually
open it, because the 27 Jul position is the one that is held. Separately, a Navigator-
originated row that is `is_fresh` but not yet `is_active` is skipped entirely by the
`!r.is_active` guard.

**Suggested fix.** Compute `originalEntryMs` from `rows` (pre-filter) and use `rowIsLive(r)` instead of
`r.is_active`, so the badge reflects what the engine is actually holding rather than what
the current lens happens to display.

### [low] The `stop_loss` handed to place_order_option is silently discarded by the client — the entry order carries no broker stop at all

`backend/app/services/kite_engine/service.py:513`

**Scenario claimed.** A maintainer reading service.py:509-515 concludes the entry order already carries the
premium stop and, while simplifying, switches cfg.stop_mode away from "both" or removes the
protective_stop.place_stop block at service.py:548-556. The position is then guarded by
nothing except the WS tick monitor, which dies with the process — the exact failure
protective_stop.py:208-212 was written to prevent ("the headline real-money bug was that a
market BUY carries no stop").

**Suggested fix.** Drop the `stop_loss=` argument from the auto-exec call (it does nothing) and reword the
comment to say the GTT at service.py:549 and the tick monitor are the only stops, so nobody
mistakes the entry order for a protected one.

### [low] exit_aligned_trail rides trail_value_for_threshold, which ignores whether that line is still aligned — once the line flips, the 'trail' sits on the wrong side of price

`backend/app/engines/sterling_kite_engine/regime.py:74`

**Scenario claimed.** cfg = SterlingKiteEngineConfig(exit_mode="two_red", exit_aligned_trail=True). A long is
running; at bar j-1 the mid ST flips red and `l_mid[j-1]` jumps from below price to above
it. `trail_level(..., j-1)` returns that above-price value (it is > 0, so no fallback), and
`trail_exit_index` immediately reports a breach at bar j with reason "trail breach (<= <a
level above the current price>)" — the stop reads as breached in the wrong direction.
LATENT: `exit_aligned_trail` defaults to False (config.py:68) and the config comment
explicitly says turning it on is 'NOT recommended', so this cannot fire on the live board
today; `test_exit_aligned_trail_moves_stop_to_mode_line` only exercises the still-aligned
case.

**Suggested fix.** Gate the threshold line on alignment too — return 0.0 when `self.trend(name)[i]` is against
the position so `trail_level` takes its (corrected) fallback — and make that fallback use
the exit-mode line rather than `cfg.trail_target` when `exit_aligned_trail` is on.

### [low] premium_stop_from_move mixes price domains: row.spot is a RAW close while row.stop_loss is a Heikin-Ashi SuperTrend level

`backend/app/services/kite_engine/scanner.py:176`

**Scenario claimed.** On a simulated NIFTY-like 1H series with the live config, at fresh long transitions the HA
close and the raw close differ by up to ~12 index points against a ~65-76 point trail
distance, so the translated premium stop is off by a few percent and the error flips sign
bar to bar (measured at three entry bars: raw-based premium stop 166.51 / 165.89 / 161.94 vs
HA-consistent 167.21 / 162.54 / 167.92 for entry 200, delta 0.5). The board's SL/TSL cells
and the GTT trigger are therefore a few percent away from the level whose breach the engine
actually acts on (`basis_low <= level`). The magnitude is small and two-sided, so this is a
consistency defect rather than a systematic mis-stop — but on a bar where the raw close gaps
below the HA close far enough that `l_fast > c[i]`, the formula yields a premium stop ABOVE
the entry premium, i.e. an already-breached protective stop shipped to
`protective_stop.place_stop`.

**Suggested fix.** Carry the basis close alongside the raw close on the row (or expose `r.basis_close`) and use
it as the `spot` argument in every `premium_stop_from_move` call, so the delta translation
measures a distance inside a single series. Independently, clamp the returned stop to `<
entry_premium` for a long-premium position before it reaches `protective_stop.place_stop`.

### [low] The card ranks only the legs it is currently showing, so turning "Ended" off moves the ✝/▲ to a different strike than the detail pane crowns for the same signal

`frontend/src/components/kite/SterlingKiteEnginePane.tsx:513`

**Scenario claimed.** A confluence row on RELIANCE with three legs (ITM1, ATM, OTM1). The ITM1 leg's live premium
has traded through its `premium_sl`, so `legHasExited` returns true for it. With 'Ended'
off, `visibleLegs` = {ATM, OTM1}, and if ATM's carry-adjusted R beats OTM1 the card puts ✝
on ATM. Open the same signal: `SignalDetailPane` ranks all three legs (`data.options`), ITM1
still has the best score (highest delta, lowest relative carry), so the drawer puts ✝ on
ITM1. Two different "best strike" recommendations for one signal, one click apart. The
degenerate version: a two-leg confluence row where one leg has exited drops to a single
visible leg, `ranked.length < 2` → no badge on the board at all, while the drawer still
shows one.

**Suggested fix.** Rank over `row.legs` (all resolved legs) and only use `visibleLegs` for display, or
conversely have the detail pane exclude exited legs too. Pick one rule and state it in the
tooltip; today the card silently changes its recommendation when a display filter is
toggled.

### [low] Badge tooltips and the card's own comments describe a per-bucket "reward-to-risk" that the shared selector explicitly is not

`frontend/src/components/kite/SterlingKiteEnginePane.tsx:504`

**Scenario claimed.** A user hovers ✝ in the watchlist and reads "Best reward-to-risk among this signal's
strikes", infers a target-based ratio > 1, and buys that strike. The underlying moves
exactly 1R in their favour over one day and the position is down: the leg's actual score was
netR 0.75 (impactMath's own worked example at impactMath.ts:12-19: "Include the carry that
leg actually pays over one day and the same leg scores 0.75 — holding it loses money even
when the underlying does exactly what the signal predicted"). Separately, a maintainer
reading SterlingKiteEnginePane.tsx:504-509 and :556-561 will size the Best-only view for up
to 6 legs and mis-diagnose the 2-leg output as a bug.

**Suggested fix.** Delete the per-bucket comments at SterlingKiteEnginePane.tsx:504-509 and 556-561 and restate
Best-only as "at most 2 legs per signal". Replace the three "Best reward-to-risk" tooltips
(SignalMarker.tsx:17, SignalDetailPane.tsx:148, SignalImpactCalculator.tsx:408 and :262)
with the card's wording, and consider surfacing the actual netR value in the tooltip so a
sub-1.0 winner is visible rather than implied.

