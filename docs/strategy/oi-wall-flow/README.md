# OI Wall Flow

**Id:** `oi_wall_flow`  
**Contract:** A320.1  
**Engine:** `backend/app/engines/oi_wall_flow/`  
**Live path:** `backend/app/services/oi_wall_flow*.py` — scanner, runner, positions. Shared SignalBoard tab, Connect settings, Trading Mode re-scan, footer chip `OWF`.

Buy the first-resistance call (or first-support put) that the chain is actually
defending, when near-ATM flow agrees.

This is not a candle strategy. The input is one expiry's option chain.

## Why this exists

The BSE Ltd 29-Sep-2026 chain at spot 3392.50 (+1.94%) is the motivating
example. Near-ATM calls were being covered (OI down, premium up 20%+), puts
were being written at 3300–3400 (OI up, premium crushed), the put wall sat at
3300 and the call wall at 3500. The trade that matches that picture is **3500
CE**, not 3400 CE (ATM, expensive) and not a PE (fighting the flow).

That chain is a golden test. If it ever arms a PE, the engine is wrong.

## Decision, in order

1. Classify every strike: long buildup / short covering / short buildup /
   long unwinding. Deadband changes do not vote.
2. Put wall = max put OI (support). Call wall = max call OI (resistance).
3. Score near-ATM (±2 strikes) flow. Calls covering and puts being written
   are bullish for the underlying. The inverse is bearish.
4. Confirm with room-to-wall and max-pain pin. PCR is recorded, not voted —
   sub-1 PCR is a call-writing ceiling, not a short signal.
5. If `|score| >= min_bias_score`:
   - bullish → buy the call wall if it is first resistance above spot, else
     the nearest OTM CE. Never ATM when `skip_atm` is on.
   - bearish → the mirror, first-support PE.
6. Stops are on the **premium** (default −40%). A second kill is the
   opposing wall breaking on the underlying.
7. Targets are +50% / +100% of premium.

## What this package does not do

The engine itself has no broker, socket, or clock. It emits
`app.domain.models.Signal`. Scanning, arming, GTT protection and the tick
loop live in `app.services.oi_wall_flow*`, same split as Gamma Move.

Open-interest *change* is against a **session baseline** (first quote of the
day). Kite quotes have no previous-close OI; a restart with no stored
baseline reports 0% change — conservative, not fabricated. SENSEX / BFO is
skipped in v1.

Thresholds in `config.py` are judgement (`JUDGEMENT`), not a calibrated
sample. Do not describe them as measured.

## Files

| File | Owns |
|---|---|
| `classify.py` | flow labels, walls, PCR, max pain |
| `bias.py` | directional score |
| `selection.py` | CE/PE + strike |
| `exits.py` | premium stop, wall invalidation, targets |
| `strategy.py` | state machine + `generate()` |
| `tests/engines/oi_wall_flow/test_bse_snapshot.py` | the screenshot, as a test |
