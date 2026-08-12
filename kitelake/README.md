# kitelake — offline market-data lake from Zerodha Kite

Code lives here, inside the Sterling project. **Data lives wherever you point it** —
typically a removable drive — and is found by identity rather than by path, so unplugging
or remounting the drive is a normal, recoverable state instead of a crash.

---

## Read this first: what Kite can and cannot give you

These are hard limits of the vendor, verified against the live API on 2026-08-12. No amount
of code works around them.

| You want | Reality |
|---|---|
| **Second- or tick-level history** | **Does not exist.** The historical API's finest interval is `minute`. There is no sub-minute endpoint and no tick archive. Sub-minute data only exists if something was recording at the time — see [Tick recording](#tick-recording-the-only-route-to-sub-minute-data). |
| Historical candles at all | Requires the **paid historical-data add-on** on your Kite Connect app. Valid credentials without it return `403 PermissionException`. |
| 6 months of the full option chain | **Not obtainable.** The instrument master lists **live contracts only** — expired option tokens cannot be enumerated, so their history is unreachable. You can only get contracts trading today, back to each one's own listing date. |
| 6 months of futures | Mostly yes, via `--continuous`, which stitches history across expiries using a live contract's token. |
| Fast bulk downloads | The historical endpoint is capped at **3 requests/second**. Everything is rate-limited, not bandwidth-limited. That single number sets every ETA below. |

If you need second-level data for a period already past, Kite cannot supply it at any
price. A vendor with a tick archive can — this repo already has a TrueData adapter
(`backend/app/services/market_data/truedata.py`) whose `/getticks` endpoint serves real
tick history at 10 bars/sec, far above Kite's 3. The lake's schema carries a `source` field
precisely so such a feed can land alongside Kite data.

---

## Quickstart

```bash
# 0. one-time: create the venv (kept out of git)
python3 -m venv .venv-kitelake
./.venv-kitelake/bin/pip install -r kitelake/requirements.txt
alias kitelake='./.venv-kitelake/bin/python -m kitelake'

kitelake root --pick                    # choose where data lives (graphical chooser)
kitelake instruments                    # sync the instrument master — no login needed
kitelake plan nse-all --interval minute --from 2026-02-13 --to 2026-08-13
kitelake auth                           # log in to Kite (token expires every morning)
kitelake download nse-all --interval minute --from 2026-02-13 --to 2026-08-13
kitelake verify                         # structural integrity sweep
kitelake catalog --hot nifty50          # DuckDB views + hot native table
kitelake read RELIANCE --tail 5
```

Everything before `auth` works without credentials, so you can size the job before paying
for anything.

---

## Choosing where data lives

Storage is fully relocatable. Three ways to set it:

```bash
kitelake root --pick                    # native folder chooser (zenity/kdialog/tkinter)
kitelake root --set /run/media/you/UUID/SterlingLake --label "Pendrive"
kitelake root --list                    # known folders + every mounted volume
```

…or graphically inside Sterling: the **Offline Market Data** panel
(`frontend/src/components/datalake/DataLakePanel.tsx`) shows status and opens a folder
picker listing drives with free space, flagging any that already hold data.

### How it survives being unplugged

Each lake carries a `LAKE_ID.json` stamp with a stable UUID. The registry
(`~/.config/kitelake/roots.json`) lives **outside** the lake, so it survives the drive
going away. Resolution order:

1. `KITELAKE_ROOT` env var — an explicit override always wins.
2. The active lake's last known path.
3. The drive's filesystem UUID → wherever it is mounted now (**self-heals a remount to a
   different path**).
4. Siblings of the last known path (handles a rename).
5. A sweep of every mounted volume for a matching stamp — two levels deep on removable
   media, one on the system disk.

When none of that finds it, nothing throws a stack trace. `lake_status()` returns
`available: false` with plain-English guidance, the API answers **HTTP 200** (not an error —
a missing drive is information, not a fault), and the UI shows amber guidance with one-click
buttons for any drive currently attached. Plug the drive back in and the panel recovers on
its own; a download resumes exactly where it stopped.

---

## Scope: three nested tiers

This lake downloads exactly three universes, and they are **nested** — verified against the
live master, their union is exactly `equity-all` (22,810 instruments). So they are not three
jobs; they are one job with useful checkpoints.

```bash
kitelake tiers --interval minute --from 2026-02-13 --to 2026-08-13   # cost them
kitelake download --tiers --interval minute --from 2026-02-13 --to 2026-08-13
kitelake download --tiers --stop-after nse-all                      # skip tier 3
```

| # | Universe | Instruments | New | Requests | ETA | Size | Done by |
|---|---|---|---|---|---|---|---|
| 1 | `indices` | 233 | +233 | 932 | ~6 min | 0.20 GiB | ~6 min |
| 2 | `nse-all` | 10,026 | +9,890 | 39,560 | ~4.4 h | 7.42 GiB | ~4.5 h |
| 3 | `equity-all` | 22,810 | +12,687 | 50,748 | ~5.6 h | 9.51 GiB | **~10.1 h** |

**Total: 22,810 instruments, 91,240 requests, ~10.1 h, ~17.1 GiB.**

Because the ledger settles work per *chunk*, a later tier only pays for instruments no
earlier tier covered. Summing the tiers naively suggests 132,276 requests; the real cost is
91,240, and the 41,036-request overlap (~4.5 h) is skipped automatically. Verified at the
execution level, not just in the estimate: a tiered run and a direct `equity-all` run issue
an identical number of HTTP requests and produce identical bars.

The payoff is early usable data — queryable indices in ~6 minutes, all of NSE by ~4.5 h —
for the same total price as going straight to the widest tier.

Also available as components/subsets: `nse-eq`, `bse-eq`, and the curated `nifty50`,
`nifty-next50`, `banknifty` (handy for a ~80-second smoke test before committing to a long
run). At `--interval day`, `nse-all` is 10,026 requests ≈ 67 min and 0.02 GiB.

### Deliberately out of scope

`fno-fut`, `fno-opt`, `derivatives-live` and `everything` were removed. Asking for one
prints the reason rather than "unknown preset":

| Preset | Why not |
|---|---|
| `everything` (114,401) | ~2.1 days, ~136 GiB — larger than the 107 GiB drive |
| `derivatives-live` (91,563) | ~1.7 days, ~119 GiB — does not fit either |
| `fno-opt` (39,220) | expired contracts cannot be enumerated, so option-chain history is unobtainable anyway |
| `fno-fut` (652) | needs `--continuous` to be useful; out of current scope |

Re-enabling any of them is a one-line change in `OUT_OF_SCOPE` plus a mask in
`_mask_preset` (both in `universe.py`).

### About the sizes

They are **upper bounds**: they assume every minute has a bar. Kite omits candles for
minutes with no trade, so illiquid instruments store far less — often under 10% of the
theoretical maximum, which matters most for `bse-eq`. Storage measured at **17.6 bytes/row**
for zstd-9 int64 OHLCV parquet (vs 30.1 for float32+zstd3 — the fixed-point choice pays for
itself). `equity-all` at ~17 GiB fits the 107 GiB drive with room to spare.

---

## Storage layout

```
<lake root>/
  LAKE_ID.json                       stable identity — how the lake is found
  bars/interval=minute/exchange=NSE/segment=NSE/738561__RELIANCE.parquet
  instruments/date=2026-08-13/instruments.parquet   (+ latest.parquet)
  manifest/coverage.sqlite           chunk-level ledger; drives --resume
  catalog/lake.duckdb                SQL views over the parquet
  ticks/date=2026-08-13/NSE.parquet  recorded ticks (if you run the recorder)
  logs/download-<run_id>.jsonl       per-run event log
  _staging/                          atomic-write scratch
```

**One file per (instrument, interval).** The dominant query is "give me this symbol's
history", which becomes a single file open — no glob, no metadata merge. Measured: 6 ms for
a 19,875-bar read by token.

**Files are named by `instrument_token` first** because tokens are always filesystem-safe
integers. Real symbols are not: `M&M`, `NIFTY 50`, `NIFTY50 PR 2X LEV` all need
sanitising, and two different symbols can sanitise to the same string. The token prefix
makes collisions impossible; the symbol suffix is for humans.

**Conventions**

- **Prices are `int64` = `round(rupees * 10_000)`.** Four decimals, not two, because CDS
  currency pairs quote to 4dp (`83.4525`). Readers decode to float rupees by default;
  `--raw` gives the stored integers.
- **Timestamps are UTC instants** in the file (Kite sends `+0530`); readers convert to IST
  by default. `2026-02-03T09:15:00+0530` is stored as `2026-02-03T03:45:00Z`.
- **`oi` is nullable** — equities and indices have no open interest, and writing `0` would
  be a lie, since `0` is a meaningful OI for a real contract.

---

## Resume, and why it is trustworthy

Work is tracked as **chunks** (a 6-month minute pull is 4 requests per instrument), each
with a status:

| Status | Meaning |
|---|---|
| `pending` | planned, not attempted |
| `done` | fetched, rows written |
| `empty` | fetched fine, **zero candles** — normal for illiquid or pre-listing windows. Never retried. |
| `failed` | errored. Retried only with `--retry-failed`, so an outage cannot silently become a permanent hole. |

Verified end-to-end: a run interrupted at chunk 14 of 40, then resumed, issued only the 26
missing requests and produced **byte-identical totals** to an uninterrupted run
(15,900 bars, 20 instruments either way).

**The credential trap this design avoids.** Kite returns **HTTP 400 `InputException`** for
an invalid api_key — not the 403 the docs imply. Classified naively, a dead token would mark
all 40,000 chunks `failed`; resume would then skip them all and you would have an empty lake
that looks finished. Instead anything credential-shaped raises a fatal error that aborts the
run on first occurrence and leaves chunks `pending`. Measured: aborts in 0.16 s with
**0 chunks marked failed**.

Ctrl-C stops scheduling but lets in-flight writes finish, so the parquet on disk is always
valid and always agrees with the ledger.

---

## Rate limiting

The limiter enforces a **minimum spacing** of `1/rate` between requests rather than using a
token bucket. This is not fussiness: a bucket with capacity 1 banks a token while idle, so a
burst after a pause emits `rate + 1` requests inside one second — 3.5 at rate 2.5, over
Kite's ceiling of 3. Measured before the fix: an idle-then-burst window contained 4 grants.
After: never more than 3, idle or not.

On a 429 the rate halves (floor 0.5 rq/s) and creeps back after 40 consecutive successes
(AIMD), so a throttling episode costs seconds instead of repeatedly flagging your API key.

---

## Tick recording (the only route to sub-minute data)

```bash
kitelake ticks record nifty50            # streams FULL-mode ticks into the lake
kitelake ticks aggregate --date 2026-08-13   # ticks -> true second bars
```

This captures data **from the moment you start it, forward only**. It cannot backfill.
Ticks buffer in memory and flush in batches; per-second bars derive traded volume from the
*span* of the cumulative `volume_traded` field across each bucket, not a sum of it.

---

## Verifying what you have

```bash
kitelake status                 # ledger progress + recent runs
kitelake verify                 # structural sweep
kitelake coverage nse-all --interval minute --from … --to …
```

`verify` checks schema, timestamp ordering and uniqueness, nulls, `high >= low`,
`high >= max(open, close)`, `low <= min(open, close)`, non-negative volume, bars inside a
valid session window, and alignment to the interval grid. It also reports both directions of
ledger/disk disagreement — a file with no ledger row means a ledger reset; a ledger row with
no file means a lost write.

**Low completeness is not a defect.** An illiquid stock legitimately returns 8% of the
theoretical bar count, so `coverage` reports completeness as information while `verify` only
fails on things that are structurally impossible.

---

## Querying

```python
from kitelake.reader import read_bars, read_many, resample, sql

df = read_bars("RELIANCE", "minute", "2026-06-01", "2026-08-13")   # polars, IST, float ₹
five = resample(df, "5m")            # left-closed, left-labelled (matches exchange labels)
wide = read_many(["RELIANCE", "INFY", "TCS"])
top  = sql("SELECT tradingsymbol, COUNT(*) n FROM bars GROUP BY 1 ORDER BY n DESC LIMIT 10")
```

`read_bars` on one instrument bypasses DuckDB entirely — direct `scan_parquet` on one file.
`sql()` goes through the catalog, where partition keys and parquet row-group statistics do
the pruning. `catalog --hot <universe>` additionally materialises a native DuckDB table
(measured ~3.5x faster than re-scanning parquet for repeated aggregations).

---

## Notes

- DuckDB's `temp_directory` is pinned inside the lake. The default would spill large sorts
  onto the system drive, which on this machine has ~5 GiB free.
- All writes are staged then `os.replace`d, so a crash or a yanked cable can leave a stray
  staging file (cleaned by `kitelake clean`) but never a truncated parquet.
- Sessions are stored at `~/.config/kitelake/session.json`, created mode `0600` *before*
  the token is written. Credentials never enter logs, event files, or parquet metadata.
- NSE holidays are bundled for 2026 only (the year we verified). Other years fall back to
  weekdays-only; override with `instruments/holidays.txt` in the lake, one `YYYY-MM-DD` per
  line. This only affects *expected*-bar arithmetic, never what gets fetched.
