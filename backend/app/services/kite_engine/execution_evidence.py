"""Mandatory live contract and quote evidence; no guessed tick sizes or prices."""
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, ROUND_FLOOR, ROUND_CEILING
from math import isfinite
from zoneinfo import ZoneInfo

_IST = ZoneInfo("Asia/Kolkata")


@dataclass(frozen=True)
class EntryEvidence:
    last_price: float
    buy_limit: float
    sell_limit: float
    lot_size: int
    tick_size: float


def _timestamp(value):
    stamp = value if isinstance(value, datetime) else datetime.fromisoformat(str(value))
    return stamp.replace(tzinfo=_IST) if stamp.tzinfo is None else stamp


async def entry_evidence(client, symbol: str, exchange: str, quantity: int,
                         *, now: datetime | None = None, max_age_seconds: int = 60) -> EntryEvidence:
    supplied_now = now
    now = now or datetime.now(_IST)
    if now.tzinfo is None:
        raise ValueError("aware_evidence_clock_required")
    instruments = await client.search_instruments(symbol, exchange=exchange, limit=50)
    rows = [r for r in instruments if r.get("tradingsymbol") == symbol and r.get("exchange") == exchange]
    if len(rows) != 1:
        raise ValueError("unambiguous_contract_metadata_required")
    row = rows[0]
    lot, tick = int(row.get("lot_size") or 0), float(row.get("tick_size") or 0)
    expiry = _timestamp(row["expiry"]).astimezone(_IST).date()
    if (lot <= 0 or quantity <= 0 or quantity % lot or not isfinite(tick) or tick <= 0
            or row.get("instrument_type") not in {"CE", "PE", "FUT"}
            or expiry < now.astimezone(_IST).date()):
        raise ValueError("invalid_or_expired_contract_metadata")
    key = f"{exchange}:{symbol}"
    quote = (await client.get_quote([key])).get(key) or {}
    now = supplied_now or datetime.now(_IST)
    for field in ("timestamp", "last_trade_time"):
        age = (now - _timestamp(quote.get(field))).total_seconds()
        if not 0 <= age <= max_age_seconds:
            raise ValueError("stale_or_future_live_quote")
    last = float(quote.get("last_price") or 0)
    if not isfinite(last) or last <= 0:
        raise ValueError("invalid_live_quote_price")
    step = Decimal(str(tick))
    # Limits stay INSIDE the funded 30bp envelope; the instrument master defines ticks.
    buy = (Decimal(str(last)) * Decimal("1.003") / step).to_integral_value(rounding=ROUND_FLOOR) * step
    sell = (Decimal(str(last)) * Decimal("0.997") / step).to_integral_value(rounding=ROUND_CEILING) * step
    if buy <= 0 or sell <= 0:
        raise ValueError("invalid_tick_rounded_price")
    return EntryEvidence(last, float(buy), float(sell), lot, tick)
