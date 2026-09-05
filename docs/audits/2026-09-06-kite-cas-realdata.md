# CAS validation from recovered real lake data

Validated **136,980 broker minute bars**, including **9,855 observations after August 3, 2026**, from NIFTY 50, LT and SBIN. All three file hashes match the existing acquisition manifest. All **366 instrument-session checks pass**, with no invalid OHLC rows, duplicate/nonincreasing timestamps, missing minute intervals, or observed continuous-session boundary mismatches.

| Instrument | Bars checked | July 31 last minute / count | August 3 last minute / count | Latest observed bar (IST) |
|---|---:|---|---|---|
| NIFTY 50 index | 45,750 | 15:29 / 375 | 15:29 / 375 | August 13, 15:29 |
| LT cash | 45,615 | 15:29 / 375 | 15:14 / 360 | August 13, 15:14 |
| SBIN cash | 45,615 | 15:29 / 375 | 15:14 / 360 | August 13, 15:14 |

Minute timestamps label the start of each bar. The observed stock change therefore matches the August 3 cash continuous close moving from 15:30 to 15:15 for these CAS-eligible stocks. The index retains observations through 15:29. Sterling's cash-signal entry policy rejects the **135 index observations at or after 15:15** across the nine post-CAS sessions. These observations support the implemented cash timing boundaries described by [NSE's CAS specification](https://www.nseindia.com/static/products-services/closing-auction-session).

The previously unavailable lake is attached as USB filesystem UUID `3f36ac07-fdbe-48c1-9514-ecf65c6619b0`. It was mounted read-only with `ro,noload` at its configured path; no source data were modified. Its manifest reports 231,143,717 minute rows across 12,246 symbols, ending August 14. Those inventory totals are metadata, not a full audit of every file. The selected files cover February 13 through August 13.

Reproduce from the repository root:

```sh
PYTHONPATH=backend backend/.venv/bin/python backend/study/kite_cas_realdata_audit.py
```

Use `--lake /path/to/SterlingLake` for relocation and `--output /path/to/report.json` for another report destination. The script reads only the existing manifest and three parquet files, records SHA-256 hashes of source inputs and audit/policy code, checks every selected timestamp and OHLC row, and exits nonzero on validation failure. Detailed dates and checks are in [the JSON report](2026-09-06-kite-cas-realdata.json).

This closes the earlier absence of post-CAS **cash-session** evidence. It does not establish profitability or live execution readiness: the lake manifest contains no derivative bar symbols, its ticks directory is empty, and the selected data contain no executable option quotes, fills, auction matching records or September 4 recorded signals. September 7 pre-open behavior also lies beyond these observations. Acquisition hashes establish consistency with the local manifest, not independent exchange certification.
