# NIFTY ORB — product contract (keep it simple)

One strategy. One signal. Two ways to trade it.

## Modes

| Mode | What the user sees | What happens |
|------|--------------------|--------------|
| **Manual** | Signals board shows the trade ticket (CE/PE, strike, qty, SL, target) | User presses **Buy** on that ticket |
| **Auto** | Same board, same ticket | System places **that same ticket** via `execute_scan` |

There is no second brain for Auto. If Auto would refuse (liquidity, window, daily limit, stale signal), Manual shows the same refusal reason.

## Rules users need to know

- Long options only: LONG → buy CE, SHORT → buy PE. Never sells options as the strategy.
- Paper / Live is the account switch (where orders go).
- Manual / Auto is who places the order (you vs the engine).
- Engine power (`enabled`) is whether ORB scans at all. Fresh installs stay **off**.

## Non-goals

- Adaptive Edge / Navigator signal merge
- Option selling
- Strategy-local paper-only flags
- Extra Auto-only filters
