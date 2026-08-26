# A265 — Architecture

## Where it lives

```
backend/app/engines/atm_premium_imbalance/     strategy mathematics — no I/O
    models.py        LegQuote, PremiumPairView, TradeRecord, ExitEvent, q2, align_to_tick
    config.py        ATMPremiumImbalanceConfig + validate() (incl. live-mode guards)
    quote_cache.py   independent CE/PE caching -> the three views
    signal.py        the one signal implementation
    entry.py         entry price policies + the 3-attempt state machine
    exit.py          target, trigger, exit order pricing
    selection.py     expiry + nearest-listed-strike ATM resolution
    strategy.py      orchestrator: ticks in, Intents out

backend/app/services/atm_premium_imbalance.py  config persistence + Kite BFO resolution
backend/app/api/v1/endpoints/config.py         GET/PUT/snapshot endpoints
frontend/src/hooks/useAtmPremiumImbalance.ts   typed client
frontend/src/components/AtmPremiumImbalanceSettings.tsx   operator panel
```

Adaptive Edge is not imported, not read and not modified.

## Data flow

```
       Kite BFO instrument dump              index LTP
                 │                               │
                 ▼                               ▼
        selection.select_expiry ──────► selection.select_atm_strike
                 │                               │
                 └──────────► OptionPairRef ◄────┘
                                   │
              CE ticks ────────────┤────────── PE ticks
                    │              │              │
                    ▼              ▼              ▼
              PremiumQuoteCache  (independent per-leg cache)
                                   │
              ┌────────────────────┼────────────────────┐
              ▼                    ▼                    ▼
       COMPATIBILITY        SYNCHRONIZED           EXECUTABLE
        cached LTPs         ts-aligned pair          two asks
              └────────────────────┼────────────────────┘
                                   ▼
                          PremiumPairView          ONE shape
                                   │
                                   ▼
                            signal.evaluate        ONE implementation
                                   │
                                   ▼
                     strategy.ATMPremiumImbalanceStrategy
                                   │
                                   ▼
                                Intent             (caller does the I/O)
```

The narrowing at `PremiumPairView` is the point of the design. Three ways to
build a view, one way to read it — so a research mode can never diverge into a
second strategy.

## Why the orchestrator returns Intents

`ATMPremiumImbalanceStrategy` performs no side effects. It consumes ticks and
returns an `Intent` (`submit_entry`, `poll_entry`, `reconcile_entry`,
`submit_exit`, `poll_exit`, `complete`, `halt`); the caller executes it and
reports back.

That inversion is what makes the golden-trade tests meaningful. The V17 and V1
replays in `backend/tests/engines/atm_premium_imbalance/test_golden_trades.py`
drive the same object the live runner would, with a scripted broker in place of
a real one. There is no second backtest implementation that could agree with the
recordings while the live path quietly disagreed.

## Lifecycle

```
IDLE ──both legs quoted──▶ ARMED ──signal──▶ ENTERING ──fill──▶ IN_POSITION
                                                │                     │
                                    attempts exhausted        price >= target
                                                │                     │
                                                ▼                     ▼
                                              DONE  ◀────fill──── EXITING

any unresolved order state ─────────────────▶ HALTED
```

## Entry state machine

The only interesting part. Everything else is bookkeeping.

```
ATTEMPT n ──submit──▶ order id?
                        │
       ┌────────────────┴────────────────┐
       │ yes                             │ no
       ▼                                 ▼
   poll status                    error reported?
       │                            │          │
  ┌────┼──────────┐            yes  │          │ no
  │    │          │                 ▼          ▼
FILLED │      REJECTED         ATTEMPT n+1   RECONCILE
  │    │          │                            (may be live!)
  │  UNKNOWN      ▼
  │    │      ATTEMPT n+1
  │    ▼
  │  RECONCILE ──┬── found filled ──▶ use that fill
  │              ├── confirmed absent ──▶ ATTEMPT n+1
  │              └── UNKNOWN / DIVERGED ──▶ HALT
  ▼
use fill
```

The load-bearing edge is **submit returned neither an id nor an error**. The
order may be live at the exchange. Retrying there is how a duplicate position
gets opened, so that path goes to reconciliation, and `next_action()` keeps
returning `RECONCILE` no matter how many times it is asked.

## Failure flow

| Condition | Result |
|---|---|
| No view buildable (e.g. EXECUTABLE with no ask) | `NO_TRADE`, reason `no_quote_pair`. No fallback to another mode. |
| Quote older than `max_quote_age_ms` | `NO_TRADE`, reason `stale_quote` |
| Entry unpriceable this tick | no intent; retried on the next tick, never priced off a different reference |
| Broker says `complete` with no average price | treated as `UNKNOWN` → reconcile. A target is never computed from a missing fill. |
| Reconciliation `UNKNOWN`/`DIVERGED` | `HALT`, trade state `reconciliation_required` |
| Exit submit unacknowledged | `HALT` — we may be flat or may still be long |
| No bid and no fallback at exit | `HALT` rather than invent a price for a real exit |

## Integration notes

**No central strategy registry exists.** `app/engines/edge/catalog.py`
catalogues backtest-validated `(symbol, tf, profile)` combos for the edge feed,
which is a different concept. Standalone strategies (NIFTY ORB, and now this
one) are registered as: engine package + service config store + `config.py`
endpoints + a `config/registry.ts` section on the client. Inventing a second
registry would be exactly the parallel infrastructure the contract forbids, so
the strategy publishes its own identity on its `GET` instead.

**SENSEX options resolve through the existing Kite BFO path**, including the
`SENSEX -> BSX` name alias Kite's instrument dump uses
(`app/services/kite_engine/strikes.py`). The instrument dump is cached for 15
minutes — resolving it per tick would be the hot-path mistake this codebase has
made before.

**The observed bot used Upstox.** Sterling has no Upstox adapter. The strategy
is broker-agnostic by construction (it emits Intents), and Kite does serve BSE
F&O, so Kite is the execution path here. Order ids and instrument-key *formats*
in the evidence are Upstox's and are not reproduced.
