# A320 — OI Wall Flow contract

## Invariants

1. A `watching` or `error` signal always carries a `reason`. Constructing one
   without a reason raises.
2. The engine never imports an adapter and never places an order.
3. Gate order is: chain present → DTE window → bias → strike → premium/OI/risk.
   A contract outside the DTE window is refused without building a plan.
4. Buying a call is `Signal.direction = "long"` (underlying). Buying a put is
   `"short"`. The option itself is always a long premium position.
5. Stops and targets on `Signal` are **option premia**, not spot.
6. The BSE Ltd 29-Sep-2026 fixture (spot 3392.50, expiry 2026-09-29) arms
   3500 CE at 84.15 / stop 50.49 / target 126.23 and does not arm a PE.

## Flow vocabulary

| premium | OI | label | CE implication | PE implication |
|---|---|---|---|---|
| up | up | long buildup | bullish | bearish |
| up | down | short covering | bullish | bearish |
| down | up | short buildup | bearish | bullish (put writing) |
| down | down | long unwinding | bearish | bullish |

## Provenance

Motivated by a live BSE Ltd chain screenshot, 29-Sep-2026 expiry. Not
reverse-engineered from a third-party bot; there is no compatibility mode.
