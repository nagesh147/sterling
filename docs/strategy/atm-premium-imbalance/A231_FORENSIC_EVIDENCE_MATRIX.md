# A231 — Forensic Evidence Matrix

Reverse-engineered from four screen recordings of a third-party bot
(`SENSEX_MEETING_POINT_BOT` / "SENSEX LIVE BOT"). This file is the **evidence
record**: every rule in [A230_STRATEGY_CONTRACT.md](A230_STRATEGY_CONTRACT.md)
must trace to a row here.

Confidence vocabulary: `CONFIRMED` (read directly off a sharp frame **and**
arithmetically self-consistent) · `VERIFIED` (read directly, no independent
cross-check) · `STRONGLY_SUPPORTED` (consistent across ≥2 recordings) ·
`INFERRED` (derived, not printed) · `UNRESOLVED` · `REJECTED`.

## Source recordings

| Tag | File | Res / fps | Host | Working dir | Session date | Role |
|-----|------|-----------|------|-------------|--------------|------|
| **V1** | `strategy.mp4` | 478×850 @60 | iPhone SSH client (camera-of-phone) | server `13.207.46.230` | **2026-08-20** | **LATEST — authoritative** |
| V17 | `video_..._05-21-17.mp4` | 720×1280 @60 | macOS Terminal → `ubuntu@ip-172-31-3-254` | `~/update` | 2026-07-30 | prior version |
| V21 | `video_..._05-21-21.mp4` | 720×1280 @60 | iPhone SSH client | `~/backup_20260730_1254` | ≥2026-07-30 | prior version (30-Jul backup) |
| V04 | `video_..._05-21-04.mp4` | 720×1280 @30 | VS Code terminal, `Raguls-MacBook-Air` | `SENSEX_MEETING_POINT_BOT` | earlier | local dev build |

**Version discipline.** V1 is the latest build and wins every conflict. The
older recordings are used to establish *log vocabulary and output templates*,
which is what makes V1's ~5px-tall text decodable at all. Where a rule is only
evidenced in an older build, the row says so and the contract marks it
non-authoritative.

## Platform

| # | Rule | Evidence | Confidence |
|---|------|----------|------------|
| P1 | Broker is **UPSTOX**, not Zerodha Kite | V21 login payload `{'data': {'broker': 'UPSTOX', ...}}`; V1/V17 tail shows browser tab **"Upstox Pro"** on the Positions page | CONFIRMED |
| P2 | Instrument keys are Upstox-format `BSE_FO|<token>` | V17 `Instrument : BSE_FO|1141595` (entry **and** exit blocks agree) | CONFIRMED |
| P3 | Underlying feed key is `BSE_INDEX|SENSEX` | V04 `BSE_INDEX|SENSEX LTP UPDATE : 77370.77` | VERIFIED |
| P4 | Order types available: MARKET, LIMIT, SL, SL-M | V21/V17 login payload `'order_types'` | CONFIRMED |
| P5 | Runs as a single-file `python3 main.py`, quantity typed at an interactive prompt | V21/V1 `Enter Quantity : 100`; V17 `python3 main.py` | CONFIRMED |
| P6 | Broker profile JSON is dumped to stdout in V17/V21 but **not** in V1 (`Logged in as: N/A`) — logging was changed | V1 startup block vs V17/V21 | CONFIRMED |

> PII note: the recordings expose a broker email, `user_id` and account name.
> They are deliberately **not** reproduced here. Only the `broker` field matters
> to the contract.

## Market / instrument selection

| # | Rule | Evidence | Confidence |
|---|------|----------|------------|
| M1 | Underlying = SENSEX | every recording; banner "SENSEX LIVE BOT" | CONFIRMED |
| M2 | Instrument master loaded at startup, then SENSEX options filtered | V1 `Loaded 26305 instruments` → `SENSEX Options Loaded : 2445`; V21 `Loaded 26329 instruments` → `SENSEX Options Loaded : 2415` | CONFIRMED |
| M3 | Both ATM legs resolved to separate keys before entry | V17 `CE KEY : BSE_FO|1141595` / `PE KEY : BSE_FO|1145203` | VERIFIED |
| M4 | Strike used in V17 = **77600**, option **CE** | V17 `Strike : 77600` / `Option : CE` in both the `LIVE BUY` and `LIVE SELL` summary blocks | CONFIRMED |
| M5 | 77600 is the nearest 100-point strike to the open SENSEX LTP 77638.86 (distance 38.86 vs 61.14 for 77700) — consistent with nearest-available-strike ATM | V17 `SENSEX LTP : 77638.86` + M4 | STRONGLY_SUPPORTED |
| M6 | Put-call parity does **not** hold on the first post-open tick, so parity cannot be used to verify the strike | V17: `C−P = 167.50−214.85 = −47.35` implies K≈77686, contradicting the printed 77600. Cause: CE/PE last-traded prices at 09:15:00.9 are independently stale | CONFIRMED (as a caveat) |
| M7 | V04 premiums (CE 482.05 / PE 620.00 at SENSEX 77370.77) imply K≈77508.7 by parity — **not** the nearest 100-strike (77400) | V04 frame | UNRESOLVED — V04 is a dev build; may be a fixed strike or a non-same-day expiry |
| M8 | Same-day expiry is **not** directly printed in any recording | — | UNRESOLVED — inferred only from premium magnitudes in V1/V17 |

## Quote model — the core observation

| # | Rule | Evidence | Confidence |
|---|------|----------|------------|
| Q1 | Two lines print per tick: `LIVE WS PRICE: <ce> <pe>` (raw Python floats, trailing zeros dropped) then `CE : <ce> | PE : <pe> | Difference : <d>` (`%.2f`) | V17 frames 0032/0056/0084 — strictly alternating over dozens of consecutive lines | CONFIRMED |
| Q2 | **`Difference = PE − CE`** (signed PE-minus-CE, not `abs`) | verified on **every** legible line in V17/V04/V1. e.g. `245.15−106.80=138.35`, `199.30−138.10=61.20`, `192.60−149.10=43.50`, `620.00−482.05=137.95` | CONFIRMED |
| Q3 | CE and PE are cached **independently**; a tick may move one leg or both, and the difference is recomputed from the current cached pair | V17 sequence `106.80/245.15 → 103.80/246.40` (both) → `103.70/246.40` (CE only) → `103.70/249.15` (PE only) | CONFIRMED |
| Q4 | Underlying ticks are logged separately from option ticks | V04 `RAW TICK RECEIVED` / `TICK RECEIVED : dict_keys(['BSE_INDEX|SENSEX'])` / `BSE_INDEX|SENSEX LTP UPDATE : 77370.77` | VERIFIED (V04 dev build only) |
| Q5 | Live L1 depth is read separately from LTP: `Best Ask (live depth)` before entry, `Best Bid (live depth)` before exit | V17 entry + exit blocks | CONFIRMED |

## Signal

| # | Rule | Evidence | Confidence |
|---|------|----------|------------|
| S1 | Cheaper leg is bought. In V17 `CE LTP 167.50 < PE LTP 214.85` → bought **CE** | V17 `Premium Difference : 47.35` then `Option : CE` | CONFIRMED |
| S2 | The gate is named `Premium Validated` and fires 0–1 ms after the first tick — no indicator, no bar, no lookback | V17 `[TIMING] First Tick Received 09:15:00.946` → `[TIMING] Premium Validated 09:15:00.946` | CONFIRMED |
| S3 | No minimum difference threshold is enforced | V17 entered on a 47.35 difference with no threshold line printed | INFERRED (absence of evidence) |
| S4 | A PE-side entry (`PE < CE`) was **never observed** | all four recordings bought CE | UNRESOLVED — symmetry assumed, not observed |

## Entry — where the supplied spec is wrong

| # | Rule | Evidence | Confidence |
|---|------|----------|------------|
| E1 | Entry is a **marketable LIMIT BUY**, max **3** attempts | V17 `ENTRY ATTEMPT 1/3 — LIMIT BUY` | CONFIRMED |
| E2 | The limit price is read from an operator-maintained file, keyed by strike | V17 `Using manual strike price from strike_prices.txt : 288.75 (strike 77600CE)` | CONFIRMED |
| E3 | That price is then capped by the instrument's upper circuit | V17 `MPP (Upper Circuit) : 1745.45` → `Calculated Order Price (before cap) : 288.75` → `Order Price : 288.75` | CONFIRMED |
| E4 | The limit is deliberately far **through** the market (288.75 vs `Best Ask 167.50`, +72%) — it is a fill-guarantee device, not a price target | V17 entry block | CONFIRMED |
| E5 | **`entry_buffer_points = 10.25` is REJECTED as a strategy parameter.** In V17 `first_tick_CE=167.50`, `order=288.75`, `fill=133.40` — no fixed offset exists between first tick and either the order price or the fill. The 10.25 in the supplied spec equals V1's `fill 113.10 − first_tick 102.85`, i.e. **open-auction slippage**, not a configured buffer | V17 entry block + V1 arithmetic | REJECTED |
| E6 | Accounting entry price is the **broker average fill**, never the requested limit | V17 `Average Price : 133.4` = `ENTRY FILLED at 133.4` = `Entry : 133.4` in the summary, while the order price was 288.75 | CONFIRMED |
| E7 | Order-status lookup can transiently fail and is retried (`Order not found after retries.`) before `ORDER DETAILS` resolves to `Status : complete` | V17 entry block | CONFIRMED |
| E8 | Order IDs are date-stamped `YYMMDD…`: V17 `260730000006021` → 2026-07-30; V1 `260820000007450` → **2026-08-20** | both | CONFIRMED |

## Exit

| # | Rule | Evidence | Confidence |
|---|------|----------|------------|
| X1 | **`target = entry_fill + 15.0`** | V17 `Entry 133.4` → trigger fired on the first tick with `CE 149.10 ≥ 148.40`; summary prints the literal `Target Hit (+15)` | CONFIRMED |
| X2 | The `(+15)` constant is present in the **latest** build too | V1 shutdown tail `… (+15) — Trade Completed` | STRONGLY_SUPPORTED |
| X3 | Exit order is **`LIMIT SELL at best_bid − 0.50`** | V17 `Best Bid 149.2` → `Order Price 148.7`; V1 `Best Bid 127.1` → `Order Price 126.6`. Buffer = 0.50 in **both** builds | CONFIRMED |
| X4 | Exit trigger, exit order price and exit fill are three distinct values | V17 trigger `149.10`, order `148.7`, fill `156.85` | CONFIRMED |
| X5 | Realized points use fills only: `Points = exit_fill − entry_fill` | V17 `156.85 − 133.4 = 23.45` = printed `Points : 23.45` | CONFIRMED |
| X6 | `PnL = Points × quantity` (quantity is total contracts, not lots) | V17 `23.45 × 20 = 469.0` = printed `PnL : 469.0` | CONFIRMED |
| X7 | No stop-loss and no time-stop exist | no such line, and no such field, in any recording | INFERRED (absence of evidence) |

## Session lifecycle

| # | Rule | Evidence | Confidence |
|---|------|----------|------------|
| L1 | Bot idles until 09:15 IST | V1/V21 `Waiting for Market Open (09:15 IST)...` | CONFIRMED |
| L2 | WebSocket is (re)subscribed to the option pair immediately at open, before entry | V17 `Preparing WebSocket before Entry...` → `UPSTOX WEBSOCKET STARTING` → `Option Subscription Updated` → `[TIMING] WebSocket Subscribed 09:15:00.940` | CONFIRMED |
| L3 | One trade, then the process shuts down | V17/V1 `Trade Completed` → `Monitoring Ended (Exit Triggered)` → `Stopping WebSocket...` → `WebSocket Stopped` → `Bot Stopped` | CONFIRMED |
| L4 | Every milestone is timed as `[TIMING] <label> | HH:MM:SS.mmm | +<elapsed> ms`, elapsed measured from bot start | V17: start `09:12:27.642`, exit `09:15:49.144` = `+201502.36 ms` → 201.502 s ✓ | CONFIRMED |
| L5 | The latest build crashes on its own post-trade report: `Daily Report Error: could not convert string to float`, then `Error during runtime cleanup: [Errno 9] Bad file descriptor` | V1 shutdown tail | VERIFIED — a real defect in the source system, not to be reproduced |

## Golden trades

### V17 — 2026-07-30 (fully decoded, every field cross-checked)

| Field | Value | Confidence |
|-------|-------|------------|
| SENSEX LTP at first tick | 77638.86 | CONFIRMED |
| CE LTP / PE LTP / difference | 167.50 / 214.85 / 47.35 | CONFIRMED (47.35 = 214.85−167.50) |
| Strike / option | 77600 / CE | CONFIRMED |
| Instrument | `BSE_FO|1141595` | CONFIRMED |
| Quantity | 20 | CONFIRMED (from `PnL 469.0 = 23.45 × 20`) |
| Entry order price / best ask | 288.75 / 167.50 | CONFIRMED |
| Entry fill | **133.40** | CONFIRMED |
| Target | 148.40 | INFERRED (= 133.40 + 15; not printed) |
| Exit trigger tick | CE 149.10 | CONFIRMED |
| Best bid / exit order price | 149.2 / 148.7 | CONFIRMED |
| Exit fill | **156.85** | CONFIRMED |
| Points / PnL | 23.45 / 469.0 | CONFIRMED |
| Entry order id / exit order id | 260730000006021 / 260730000008605 | CONFIRMED |

### V1 — 2026-08-20 (the canonical case; entry block not directly legible)

| Field | Value | Confidence |
|-------|-------|------------|
| Quantity | 100 | CONFIRMED (`Enter Quantity : 100`) |
| Instruments loaded | 26305 → `SENSEX Options Loaded : 2445` | VERIFIED |
| Best bid / exit order price | 127.1 / 126.6 | CONFIRMED (buffer 0.50 ✓ X3) |
| Exit fill (`Average Price`) | **126.60** | CONFIRMED |
| Exit order id | 260820000007450 | CONFIRMED |
| Entry fill | **113.10** | INFERRED — `126.60 − 1350.00/100`. Triangulated three ways: log exit fill, Upstox `Day P&L 1,350.00` **and** `Overall P&L 1,350.00`, and `Points × qty` |
| Points / PnL | 13.50 / 1350.00 | CONFIRMED (broker UI) |
| Post-trade LTP | 107.70 | VERIFIED (Upstox positions row) |
| Strike / instrument / first tick / entry order price | — | **UNRESOLVED** — V1's entry block falls inside a burst where the terminal repaints at 30 Hz with ~5 px glyph height; no static frame stack exists to super-resolve. The supplied spec's `77500 CE` and `first tick 102.85` are **not** independently confirmed by me |

## Method

1. All 2146 V1 frames extracted at native resolution; the phone screen tracked
   frame-to-frame with SIFT + RANSAC homography (1810/1810 frames, no failures).
2. Per-frame sharpness and inter-frame content delta computed in the rectified
   screen plane to locate **static runs** — windows where the terminal did not
   repaint.
3. Each static run stacked (sub-pixel phase-correlation alignment, sharpness
   weighting) and deconvolved (Richardson–Lucy, Gaussian PSF) — this is what
   made V1's exit and startup blocks legible.
4. Every numeric read was accepted only if it satisfied an independent
   arithmetic identity (`Difference = PE − CE`, `Points = exit − entry`,
   `PnL = Points × qty`, `elapsed_ms = clock − bot_start`, `order price =
   best_bid − 0.50`). Readings that failed were discarded, not rounded — this is
   how `1141695` was corrected to `1141595` and `133.47` to `133.40`.
5. OCR (RapidOCR) was run over all frames as corroboration only; it was too
   noisy to be authoritative and no value in this document rests on it alone.
