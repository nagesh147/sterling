"""Read-only expiry calendar built from Kite's exact listed instruments.

The calendar is presentation data for the expiry-series selector. It deliberately
does not calculate an expiry from a weekday: every returned date is copied from an
``expiry`` field in Kite's instrument dump. The latest listed date in each calendar
month is classified as monthly, matching the production strike resolver.
"""
from __future__ import annotations

from datetime import date
from typing import Iterable, Sequence

_ALIASES = {"SENSEX": "BSX", "BANKEX": "BKX"}


def _parse_expiry(raw: object) -> date | None:
    try:
        return date.fromisoformat(str(raw or "")[:10])
    except (TypeError, ValueError):
        return None


def _matches_underlying(row: dict, option_name: str) -> bool:
    wanted = option_name.strip().upper()
    name = str(row.get("name") or "").strip().upper()
    symbol = str(row.get("tradingsymbol") or "").strip().upper()
    prefix_match = (
        symbol.startswith(wanted)
        and len(symbol) > len(wanted)
        and symbol[len(wanted)].isdigit()
    )
    return name == wanted or name == _ALIASES.get(wanted) or prefix_match


def listed_expiry_series(
    option_rows: Sequence[dict],
    option_name: str,
    *,
    today: date,
) -> dict[str, list[str]]:
    """Return up to W1-W4/M1-M2 dates without exposing those rank codes."""
    future = sorted({
        expiry
        for row in option_rows
        if row.get("instrument_type") in ("CE", "PE")
        and _matches_underlying(row, option_name)
        and (expiry := _parse_expiry(row.get("expiry"))) is not None
        and expiry >= today
    })
    by_month: dict[tuple[int, int], list[date]] = {}
    for expiry in future:
        by_month.setdefault((expiry.year, expiry.month), []).append(expiry)

    weekly: list[str] = []
    monthly: list[str] = []
    for dates in by_month.values():
        month_end = max(dates)
        monthly.append(month_end.isoformat())
        weekly.extend(expiry.isoformat() for expiry in dates if expiry != month_end)
    return {
        "weekly": sorted(weekly)[:4],
        "monthly": sorted(monthly)[:2],
    }


def _calendar_entry(
    *,
    name: str,
    option_name: str,
    option_rows: Sequence[dict],
    today: date,
) -> dict:
    return {
        "name": option_name,
        "display_name": name,
        **listed_expiry_series(option_rows, option_name, today=today),
    }


def build_expiry_calendar(
    *,
    nfo_rows: Sequence[dict],
    bfo_rows: Sequence[dict],
    index_definitions: Sequence[dict],
    stock_names: Iterable[str],
    today: date,
) -> dict:
    """Build the exact-date calendar for selected index and stock families."""
    exchanges = {"NFO": nfo_rows, "BFO": bfo_rows}
    indices = [
        _calendar_entry(
            name=str(item.get("name") or item.get("option_name") or ""),
            option_name=str(item.get("option_name") or ""),
            option_rows=exchanges.get(str(item.get("option_exchange") or "NFO"), ()),
            today=today,
        )
        for item in index_definitions
        if item.get("option_name")
    ]

    wanted_stocks = [
        name for name in dict.fromkeys(str(name).strip().upper() for name in stock_names)
        if name
    ]
    wanted_set = set(wanted_stocks)
    rows_by_stock: dict[str, list[dict]] = {name: [] for name in wanted_stocks}
    for row in (*nfo_rows, *bfo_rows):
        name = str(row.get("name") or "").strip().upper()
        if name in wanted_set and row.get("instrument_type") in ("CE", "PE"):
            rows_by_stock[name].append(row)

    stocks = [
        _calendar_entry(
            name=name,
            option_name=name,
            option_rows=rows_by_stock[name],
            today=today,
        )
        for name in wanted_stocks
    ]
    return {
        "as_of": today.isoformat(),
        "source": "kite_instruments",
        "indices": indices,
        "stocks": stocks,
    }
