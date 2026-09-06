# NIFTY ORB — product contract (keep it simple)

One strategy. One signal. Two ways to trade it.

## One sentence

ORB scans the opening range and shows a long-options ticket; you Buy it in **Manual**, or the engine places **that same ticket** in **Auto**.

## Modes

| Mode | What the user sees | What happens |
|------|--------------------|--------------|
| **Manual** | Signals board shows the trade ticket (CE/PE, strike, qty, SL, target) | User presses **Buy** on that ticket |
| **Auto** | Same board, same ticket | System places **that same ticket** via `execute_scan` |

There is no second brain for Auto. If Auto would refuse (liquidity, window, daily limit, stale signal), Manual shows the same refusal reason.

Same-ticket fields (must match): `symbol`, `option_type`, `strike`, `expiry`, `quantity`, `underlying_entry`, `stop_premium`, `target_premium`, `lot_size`. Identity is `ticket_fingerprint`.

## Rules users need to know

- Long options only: LONG → buy CE, SHORT → buy PE. Never sells options as the strategy.
- Paper / Live is the account switch (where orders go).
- Manual / Auto is who places the order (you vs the engine).
- Engine power (`enabled`) is whether ORB scans at all. Fresh installs stay **off**.
- Auto-off returns `status: manual` and places nothing.

## Non-goals

- Adaptive Edge / Navigator signal merge
- Option selling
- Strategy-local paper-only or auto-execute flags
- Extra Auto-only filters
- Unattended live until walk-forward on real option history is green
