# NIFTY ORB — supervised go-live runbook

Not unattended until walk-forward on real option history is green. This is the supervised path.

## Checklist before Auto

1. ORB unit + execution e2e tests green (`pytest -k orb`)
2. Engine `enabled=false` until you intentionally turn it on
3. Underlyings configured; Kite connected
4. Risk caps set (`max_risk_inr`, `max_trades_per_day`, entry window)
5. Restart recovery exercised once in Paper (restart backend mid-session; open ORB positions still guarded)

## Sequence

1. **Paper + Manual** — confirm the board ticket matches what you would buy.
2. **Paper + Auto** — soak at least several sessions; compare fills to the board tickets.
3. **Live + Manual** — place one ticket by hand from the board.
4. **Live + Auto** — only after paper soak; keep tight `max_risk_inr` / `max_trades_per_day`.

## Same-ticket rule

Manual Buy and Auto must use the same plan fields from the scan row. If they ever diverge, treat it as a bug — fix before Live+Auto.
