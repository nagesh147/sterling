"""Choosing *what* to download, and telling the truth about what it will cost.

The cost model is the important part of this module. Kite caps the historical endpoint at
3 requests/second, which makes every download rate-limited rather than bandwidth- or
disk-limited. That single constant decides whether a job takes four minutes or a day and
a half, so :func:`estimate_cost` exists to put that number in front of the user *before*
they start:

    minute bars, 6 months, per instrument = ceil(182 / 60) = 4 requests
    indices           (233)    ->    932 requests ->  ~6 minutes
    nse-all        (10,026)    -> 40,104 requests ->  ~4.5 hours
    everything    (114,401)    -> 457,604 requests -> ~2.1 days

Preset counts below were measured against the live instrument master on 2026-08-12.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Iterable, Sequence

import pyarrow as pa
import pyarrow.compute as pc

from .config import DEFAULT_RATE, INTERVAL_DAY_CAP, MEASURED_BYTES_PER_BAR, VALID_INTERVALS

__all__ = [
    "Instrument",
    "PRESETS",
    "TIERS",
    "OUT_OF_SCOPE",
    "resolve_universe",
    "estimate_cost",
    "preset_counts",
    "tier_plan",
]


@dataclass(frozen=True)
class Instrument:
    """One tradeable thing, as Kite describes it."""

    token: int
    tradingsymbol: str
    name: str = ""
    exchange: str = ""
    segment: str = ""
    instrument_type: str = ""
    expiry: date | None = None
    strike: float = 0.0
    tick_size: float = 0.0
    lot_size: int = 0

    @property
    def is_derivative(self) -> bool:
        """True for futures and options — the instruments that carry open interest."""
        return self.instrument_type in {"FUT", "CE", "PE"}

    @property
    def key(self) -> str:
        return f"{self.exchange}:{self.tradingsymbol}"


#: The three universes this lake is scoped to download, **in tier order**.
#:
#: They are nested — verified against the live master on 2026-08-13, their union is exactly
#: ``equity-all`` (22,810 instruments). That is why they are tiers rather than three
#: separate jobs: because the ledger tracks work per *chunk*, running them in order costs
#: 91,240 requests total, not the 132,276 a naive sum implies. The 41,036-request overlap
#: (~4.5 h) is skipped automatically.
#:
#: The payoff is early usable data: indices in ~6 min, all of NSE by ~4.5 h, everything by
#: ~10 h — for the same total price as going straight to equity-all.
TIERS: tuple[str, ...] = ("indices", "nse-all", "equity-all")

PRESETS: dict[str, str] = {
    # ── the three supported tiers ────────────────────────────────────────────
    "indices": "TIER 1 — every index across all exchanges (~233). ~6 min, ~0.2 GiB",
    "nse-all": "TIER 2 — NSE cash + NSE indices (~10,026). ~4.5 h, ~7.5 GiB",
    "equity-all": "TIER 3 — nse-all + BSE equities + all indices (~22,810). ~10 h, ~17 GiB",
    # ── components of the tiers, useful on their own ─────────────────────────
    "nse-eq": "NSE cash-market instruments only (~9,890) — stocks, ETFs, SME",
    "bse-eq": "BSE equities only (~12,760); overlaps NSE heavily and much is illiquid",
    # ── small curated subsets, for a quick smoke test before a long run ──────
    "nifty50": "The NIFTY 50 constituents (curated, as of 2026-08). ~80 s",
    "nifty-next50": "The NIFTY Next 50 constituents (curated, as of 2026-08)",
    "banknifty": "BANKNIFTY constituents (curated, as of 2026-08)",
}

#: Presets deliberately **not** supported, with the reason. Asking for one produces this
#: explanation rather than a bare "unknown preset" — the knowledge of *why* is the useful
#: part, and re-enabling any of them is a one-line change here plus a mask in _mask_preset.
OUT_OF_SCOPE: dict[str, str] = {
    "fno-fut": "futures (~652). Excluded from the current scope; needs --continuous to be "
               "useful, since the master lists live contracts only.",
    "fno-opt": "options (~39,220). Excluded: expired contracts cannot be enumerated, so "
               "historical option-chain coverage is unobtainable anyway.",
    "derivatives-live": "all live derivatives (~91,563). Excluded: ~1.7 days of downloading "
                        "and ~119 GiB, which does not fit the current drive.",
    "everything": "the entire master (~114,401). Excluded: ~2.1 days and ~136 GiB, larger "
                  "than the 107 GiB drive.",
}

#: Curated constituent lists. Static on purpose: index membership changes on a schedule
#: and silently re-deriving it would make a backtest's universe drift between runs.
NIFTY50 = (
    "ADANIENT", "ADANIPORTS", "APOLLOHOSP", "ASIANPAINT", "AXISBANK", "BAJAJ-AUTO",
    "BAJFINANCE", "BAJAJFINSV", "BEL", "BHARTIARTL", "CIPLA", "COALINDIA", "DRREDDY",
    "EICHERMOT", "ETERNAL", "GRASIM", "HCLTECH", "HDFCBANK", "HDFCLIFE", "HEROMOTOCO",
    "HINDALCO", "HINDUNILVR", "ICICIBANK", "INDUSINDBK", "INFY", "ITC", "JIOFIN",
    "JSWSTEEL", "KOTAKBANK", "LT", "M&M", "MARUTI", "MAXHEALTH", "NESTLEIND", "NTPC",
    "ONGC", "POWERGRID", "RELIANCE", "SBILIFE", "SBIN", "SHRIRAMFIN", "SUNPHARMA",
    "TATACONSUM", "TATAMOTORS", "TATASTEEL", "TCS", "TECHM", "TITAN", "TRENT",
    "ULTRACEMCO", "WIPRO",
)

NIFTY_NEXT50 = (
    "ABB", "ADANIENSOL", "ADANIGREEN", "ADANIPOWER", "AMBUJACEM", "BAJAJHLDNG",
    "BANKBARODA", "BPCL", "BRITANNIA", "CANBK", "CGPOWER", "CHOLAFIN", "DABUR",
    "DIVISLAB", "DLF", "DMART", "GAIL", "GODREJCP", "HAVELLS", "HYUNDAI", "ICICIGI",
    "ICICIPRULI", "INDHOTEL", "INDIGO", "IOC", "IRFC", "JINDALSTEL", "LICI", "LODHA",
    "LTIM", "MOTHERSON", "NAUKRI", "PFC", "PIDILITIND", "PNB", "RECLTD", "SHREECEM",
    "SIEMENS", "SWIGGY", "TATAPOWER", "TORNTPHARM", "TVSMOTOR", "UNITDSPR", "VBL",
    "VEDL", "ZYDUSLIFE",
)

BANKNIFTY = (
    "AXISBANK", "AUBANK", "BANKBARODA", "CANBK", "FEDERALBNK", "HDFCBANK", "ICICIBANK",
    "IDFCFIRSTB", "INDUSINDBK", "KOTAKBANK", "PNB", "SBIN",
)

_CURATED: dict[str, tuple[str, ...]] = {
    "nifty50": NIFTY50,
    "nifty-next50": NIFTY_NEXT50,
    "banknifty": BANKNIFTY,
}

_DERIV_EXCHANGES = ("NFO", "BFO", "MCX", "CDS", "BCD", "NCO")


# ─── Filtering ───────────────────────────────────────────────────────────────
def _mask_preset(table: pa.Table, preset: str) -> pa.Array:
    exch = table.column("exchange")
    seg = table.column("segment")
    itype = table.column("instrument_type")

    def eq(col: pa.ChunkedArray, value: str) -> pa.Array:
        return pc.equal(col, value)

    def isin(col: pa.ChunkedArray, values: Sequence[str]) -> pa.Array:
        return pc.is_in(col, value_set=pa.array(list(values)))

    indices = eq(seg, "INDICES")
    nse_eq = pc.and_(eq(exch, "NSE"), eq(seg, "NSE"))
    nse_idx = pc.and_(eq(exch, "NSE"), indices)
    bse_eq = pc.and_(eq(exch, "BSE"), eq(itype, "EQ"))

    if preset == "indices":
        return indices
    if preset == "nse-eq":
        return nse_eq
    if preset == "nse-all":
        return pc.or_(nse_eq, nse_idx)
    if preset == "bse-eq":
        return bse_eq
    if preset == "equity-all":
        return pc.or_(pc.or_(nse_eq, bse_eq), indices)
    raise KeyError(preset)


def _rows_to_instruments(table: pa.Table) -> list[Instrument]:
    out: list[Instrument] = []
    for row in table.to_pylist():
        token = row.get("instrument_token")
        if token is None:
            continue
        out.append(
            Instrument(
                token=int(token),
                tradingsymbol=str(row.get("tradingsymbol") or ""),
                name=str(row.get("name") or ""),
                exchange=str(row.get("exchange") or ""),
                segment=str(row.get("segment") or ""),
                instrument_type=str(row.get("instrument_type") or ""),
                expiry=row.get("expiry"),
                strike=float(row.get("strike") or 0.0),
                tick_size=float(row.get("tick_size") or 0.0),
                lot_size=int(row.get("lot_size") or 0),
            )
        )
    return out


def _by_symbols(table: pa.Table, symbols: Iterable[str], exchange: str = "") -> pa.Table:
    wanted = pa.array([s.upper() for s in symbols])
    mask = pc.is_in(pc.utf8_upper(table.column("tradingsymbol")), value_set=wanted)
    if exchange:
        mask = pc.and_(mask, pc.equal(table.column("exchange"), exchange))
    return table.filter(mask)


def resolve_universe(spec: str, master: pa.Table | None = None, *, root: Any = None) -> list[Instrument]:
    """Turn a universe spec into a concrete, de-duplicated instrument list.

    Accepted, comma-separated and freely mixed:

    - preset names: ``nse-all``, ``indices``, ``nifty50`` …
    - exchange-qualified symbols: ``NSE:RELIANCE``, ``NFO:NIFTY26AUGFUT``
    - bare symbols: ``RELIANCE`` (any exchange)
    - ``@/path/to/file.txt`` — one entry per line, ``#`` comments allowed
    """
    from .instruments import load_instrument_master

    if master is None:
        master = load_instrument_master(root=root)

    tokens: dict[int, Instrument] = {}
    unknown: list[str] = []

    def add(table: pa.Table) -> None:
        for inst in _rows_to_instruments(table):
            tokens.setdefault(inst.token, inst)

    parts: list[str] = []
    for chunk in (spec or "").split(","):
        item = chunk.strip()
        if not item:
            continue
        if item.startswith("@"):
            path = Path(item[1:]).expanduser()
            try:
                for line in path.read_text().splitlines():
                    line = line.split("#", 1)[0].strip()
                    if line:
                        parts.append(line)
            except OSError as exc:
                raise ValueError(f"cannot read universe file {path}: {exc}") from exc
        else:
            parts.append(item)

    for item in parts:
        low = item.lower()
        if low in OUT_OF_SCOPE:
            raise ValueError(
                f"'{low}' is not in scope for this lake: {OUT_OF_SCOPE[low]}\n"
                f"Supported tiers: {', '.join(TIERS)}.\n"
                f"See OUT_OF_SCOPE in kitelake/universe.py to re-enable it."
            )
        if low in _CURATED:
            add(_by_symbols(master, _CURATED[low], exchange="NSE"))
            continue
        if low in PRESETS:
            add(master.filter(_mask_preset(master, low)))
            continue
        if ":" in item:
            exch, _, sym = item.partition(":")
            sub = _by_symbols(master, [sym], exchange=exch.upper())
            if sub.num_rows:
                add(sub)
            else:
                unknown.append(item)
            continue
        sub = _by_symbols(master, [item])
        if sub.num_rows:
            add(sub)
        else:
            unknown.append(item)

    if not tokens:
        hint = ", ".join(sorted(PRESETS))
        detail = f" Unrecognised: {', '.join(unknown[:8])}." if unknown else ""
        raise ValueError(
            f"universe spec {spec!r} matched no instruments.{detail}\nAvailable presets: {hint}"
        )
    return sorted(tokens.values(), key=lambda i: (i.exchange, i.tradingsymbol, i.token))


def preset_counts(master: pa.Table | None = None, *, root: Any = None) -> dict[str, int]:
    """How many instruments each preset resolves to right now."""
    from .instruments import load_instrument_master

    if master is None:
        master = load_instrument_master(root=root)
    out: dict[str, int] = {}
    for name in PRESETS:
        try:
            if name in _CURATED:
                out[name] = _by_symbols(master, _CURATED[name], exchange="NSE").num_rows
            else:
                out[name] = int(pc.sum(_mask_preset(master, name)).as_py() or 0)
        except KeyError:
            out[name] = 0
    return out


# ─── Cost model ──────────────────────────────────────────────────────────────
def _human_duration(seconds: float) -> str:
    seconds = max(0.0, float(seconds))
    if seconds < 90:
        return f"{seconds:.0f}s"
    minutes = seconds / 60
    if minutes < 90:
        return f"{minutes:.0f}m"
    hours = minutes / 60
    if hours < 36:
        return f"{hours:.1f}h"
    return f"{hours / 24:.1f}d"


def tier_plan(
    interval: str = "minute",
    frm: date | None = None,
    to: date | None = None,
    *,
    rate: float = DEFAULT_RATE,
    master: pa.Table | None = None,
    root: Any = None,
) -> dict[str, Any]:
    """Cost the three tiers both naively and as they actually run.

    The ``incremental_*`` figures are the honest ones: because the ledger settles work per
    chunk, a tier only pays for instruments no earlier tier already covered. Summing the
    per-tier costs double-counts the overlap by ~41,000 requests (~4.5 h).
    """
    from .instruments import load_instrument_master

    if master is None:
        master = load_instrument_master(root=root)
    if frm is None or to is None:
        raise ValueError("both 'frm' and 'to' are required")

    seen: set[int] = set()
    tiers: list[dict[str, Any]] = []
    naive_requests = 0
    cumulative_requests = 0
    cumulative_bytes = 0

    for name in TIERS:
        instruments = resolve_universe(name, master, root=root)
        full = estimate_cost(instruments, interval, frm, to, rate=rate)
        naive_requests += full["requests"]

        fresh = [i for i in instruments if i.token not in seen]
        seen.update(i.token for i in instruments)
        incremental = estimate_cost(fresh, interval, frm, to, rate=rate)
        cumulative_requests += incremental["requests"]
        cumulative_bytes += incremental["est_bytes"]

        tiers.append(
            {
                "tier": len(tiers) + 1,
                "universe": name,
                "instruments": full["instruments"],
                "new_instruments": incremental["instruments"],
                "requests_standalone": full["requests"],
                "requests_incremental": incremental["requests"],
                "eta_incremental": incremental["eta_human"],
                "est_gib_incremental": incremental["est_gib"],
                "cumulative_requests": cumulative_requests,
                "cumulative_eta": _human_duration(cumulative_requests / max(rate, 0.01)),
                "cumulative_gib": round(cumulative_bytes / 2**30, 2),
                "description": PRESETS[name],
            }
        )

    return {
        "interval": interval,
        "frm": frm.isoformat(),
        "to": to.isoformat(),
        "rate": rate,
        "tiers": tiers,
        "total_instruments": len(seen),
        "total_requests": cumulative_requests,
        "total_eta": _human_duration(cumulative_requests / max(rate, 0.01)),
        "total_gib": round(cumulative_bytes / 2**30, 2),
        "naive_requests": naive_requests,
        "requests_saved_by_dedup": naive_requests - cumulative_requests,
    }


def estimate_cost(
    instruments: Sequence[Instrument],
    interval: str,
    frm: date,
    to: date,
    *,
    rate: float = DEFAULT_RATE,
    concurrency: int = 1,
) -> dict[str, Any]:
    """Predict requests, wall-clock and bytes for a download.

    ``concurrency`` deliberately does **not** reduce the time estimate: the shared rate
    limiter is the bottleneck, so more workers hide latency but cannot beat 3 rq/s.
    """
    if interval not in VALID_INTERVALS:
        raise ValueError(f"invalid interval {interval!r}; expected one of {', '.join(VALID_INTERVALS)}")
    if to < frm:
        raise ValueError(f"'to' ({to}) is before 'from' ({frm})")

    from .calendar_ import expected_bars

    span_days = (to - frm).days + 1
    cap = INTERVAL_DAY_CAP[interval]
    per_instrument = max(1, math.ceil(span_days / cap))
    requests = per_instrument * len(instruments)
    seconds = requests / max(rate, 0.01)

    # Bar expectation depends on the exchange's session length, so group by exchange.
    est_rows = 0
    for inst in instruments:
        est_rows += expected_bars(frm, to, interval, inst.exchange or "NSE")
    est_bytes = int(est_rows * MEASURED_BYTES_PER_BAR)

    return {
        "instruments": len(instruments),
        "interval": interval,
        "frm": frm.isoformat(),
        "to": to.isoformat(),
        "span_days": span_days,
        "chunk_days": cap,
        "requests_per_instrument": per_instrument,
        "requests": requests,
        "rate": rate,
        "seconds": seconds,
        "eta_human": _human_duration(seconds),
        "est_rows": est_rows,
        "est_bytes": est_bytes,
        "est_gib": round(est_bytes / 2**30, 3),
    }
