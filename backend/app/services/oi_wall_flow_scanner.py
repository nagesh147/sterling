"""The OI Wall Flow scan: universe, then one expiry chain, then classify.

There is no historical funnel. The engine reads one expiry's option chain, so
the cost is one batched /quote of every contract on the chosen expiry plus the
underlying spots. Reordering this into per-strike historical requests is a
performance regression that will not look like one in review.

Open-interest *change* is the thing Kite will not give us. A quote has ``oi``
but not previous-close OI, so the session's first quote of each contract is the
baseline. A restart with no stored baseline reports 0% change — conservative:
the engine will not arm on a fabricated buildup.
"""
from __future__ import annotations

import json
import time
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from app.core.logging import get_logger
from app.engines.oi_wall_flow import (ChainRow, ChainSnapshot, FlowSignal,
                                      OIWallFlowConfig,
                                      OIWallFlowStrategy)
from app.services.oi_wall_flow import (ist_today, nfo_dump,
                                       scan_underlyings, spot_quote_key,
                                       to_instrument_ref)

log = get_logger(__name__)
_IST = timezone(timedelta(hours=5, minutes=30))

_QUOTE_RATE = 0.8
_QUOTE_BATCH = 400

_INDEX_NAMES = frozenset({
    "NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "NIFTYNXT50",
})


class Pacer:
    def __init__(self, rate: float):
        self._gap = 1.0 / max(rate, 0.01)
        self._next = 0.0
        import asyncio
        self._lock = asyncio.Lock()

    async def wait(self) -> None:
        import asyncio
        async with self._lock:
            now = time.monotonic()
            if now < self._next:
                await asyncio.sleep(self._next - now)
                now = time.monotonic()
            self._next = now + self._gap


_scan_stats: dict[str, dict] = {}
_oi_baseline: dict[str, dict[str, int]] = {}
#: Last scan's underlying spots and their NSE tokens, so the tick loop can
#: subscribe the cash/index print that wall-invalidation needs.
_spot_tokens: dict[str, dict[str, int]] = {}
_last_spots: dict[str, dict[str, float]] = {}


def scan_stats(uid: str) -> dict:
    return _scan_stats.get(uid) or {}


def last_spot_tokens(uid: str) -> dict[str, int]:
    return dict(_spot_tokens.get(uid) or {})


def last_spots(uid: str) -> dict[str, float]:
    return dict(_last_spots.get(uid) or {})


def reset_baselines(uid: str = "") -> None:
    if uid:
        _oi_baseline.pop(uid, None)
        _spot_tokens.pop(uid, None)
        _last_spots.pop(uid, None)
    else:
        _oi_baseline.clear()
        _spot_tokens.clear()
        _last_spots.clear()


def _baseline_key(uid: str, day: str) -> str:
    return f"oi_wall_flow_oi_baseline_{uid}_{day}"


def _load_baselines(uid: str, day: str) -> dict[str, int]:
    cached = _oi_baseline.get(uid)
    if cached is not None:
        return cached
    out: dict[str, int] = {}
    try:
        from app.services import db
        raw = db.get_config(_baseline_key(uid, day))
        if raw:
            loaded = json.loads(raw) if isinstance(raw, str) else raw
            out = {str(k): int(v) for k, v in dict(loaded).items()}
    except Exception as exc:                                       # noqa: BLE001
        log.debug("oi_wall_flow: OI baseline unreadable for %s: %s", uid, exc)
    _oi_baseline[uid] = out
    return out


def _persist_baselines(uid: str, day: str) -> None:
    try:
        from app.services import db
        db.set_config(_baseline_key(uid, day),
                      json.dumps(_oi_baseline.get(uid) or {}, separators=(",", ":")))
    except Exception as exc:                                       # noqa: BLE001
        log.debug("oi_wall_flow: OI baseline persist failed for %s: %s", uid, exc)


def oi_chg_pct(uid: str, day: str, symbol: str, oi: int) -> float:
    """Session change against the first quote of the day.

    First sighting seeds the baseline and returns 0%. A restart without a
    stored baseline does the same — conservative, not fabricated.
    """
    base = _load_baselines(uid, day)
    if symbol not in base:
        base[symbol] = int(oi)
        _oi_baseline[uid] = base
        _persist_baselines(uid, day)
        return 0.0
    prev = base[symbol]
    if prev <= 0:
        return 0.0
    return (int(oi) - prev) / prev * 100.0


def seed_oi_baseline(uid: str, day: str, symbol: str, oi: int) -> None:
    """Test helper: pretends ``oi`` was the first quote of the day."""
    base = _load_baselines(uid, day)
    base[symbol] = int(oi)
    _oi_baseline[uid] = base


async def _quote_batched(client, pacer: Pacer, keys: list) -> dict:
    out: dict = {}
    for i in range(0, len(keys), _QUOTE_BATCH):
        await pacer.wait()
        try:
            out.update(await client.get_quote(keys[i:i + _QUOTE_BATCH]) or {})
        except Exception as exc:                                   # noqa: BLE001
            log.warning("oi_wall_flow quote batch at %s failed: %s", i, exc)
    return out


def _quote_of(quotes: dict, key: str) -> dict:
    if key in quotes:
        return quotes[key] or {}
    # Kite sometimes keys without the exchange prefix.
    bare = key.split(":", 1)[-1]
    for k, v in quotes.items():
        if str(k).endswith(bare):
            return v or {}
    return {}


def _token_of_quote(quote: dict) -> int:
    try:
        tok = int(quote.get("instrument_token") or 0)
    except (TypeError, ValueError):
        return 0
    return tok if tok > 0 else 0


def _ltp_chg_pct(quote: dict) -> float:
    try:
        ltp = float(quote.get("last_price") or 0.0)
        close = float((quote.get("ohlc") or {}).get("close") or 0.0)
    except (TypeError, ValueError):
        return 0.0
    if close <= 0 or ltp <= 0:
        return 0.0
    return (ltp - close) / close * 100.0


def days_to_expiry(expiry: str, today: date) -> Optional[int]:
    try:
        return (datetime.strptime(expiry[:10], "%Y-%m-%d").date() - today).days
    except (ValueError, TypeError):
        return None


def pick_expiry(option_rows: list[dict], name: str, cfg: OIWallFlowConfig,
                today: date) -> Optional[str]:
    """Soonest eligible listed expiry for this underlying, honouring series ranks."""
    from app.services.kite_engine.expiry_calendar import listed_expiry_series
    series = listed_expiry_series(option_rows, name, today=today)
    is_index = name in _INDEX_NAMES
    wanted: list[str] = []
    if is_index:
        if "weekly" in cfg.scan_expiries_indices:
            weekly = series.get("weekly") or []
            for rank in cfg.scan_weekly_series_indices:
                if 0 <= rank < len(weekly):
                    wanted.append(weekly[rank])
        if "monthly" in cfg.scan_expiries_indices:
            monthly = series.get("monthly") or []
            for rank in cfg.scan_monthly_series_indices:
                if 0 <= rank < len(monthly):
                    wanted.append(monthly[rank])
    else:
        if "monthly" in cfg.scan_expiries_stocks:
            monthly = series.get("monthly") or []
            for rank in cfg.scan_monthly_series_stocks:
                if 0 <= rank < len(monthly):
                    wanted.append(monthly[rank])
    eligible = []
    for expiry in wanted:
        dte = days_to_expiry(expiry, today)
        if dte is None:
            continue
        if cfg.avoid_expiry_day and dte == 0:
            continue
        if cfg.expiry_dte_min <= dte <= cfg.expiry_dte_max:
            eligible.append(expiry)
    if not eligible:
        return None
    if cfg.expiry_selection == "nearest":
        return sorted(eligible)[0]
    return sorted(eligible)[0]


def chain_rows_from_quotes(
    contracts: list[dict], quotes: dict, uid: str, day: str,
) -> list[ChainRow]:
    """Group CE/PE quotes of one expiry into ``ChainRow``s."""
    by_strike: dict[float, dict] = {}
    for row in contracts:
        try:
            strike = float(row.get("strike") or 0.0)
        except (TypeError, ValueError):
            continue
        if strike <= 0:
            continue
        side = "CE" if str(row.get("instrument_type")) == "CE" else "PE"
        symbol = str(row.get("tradingsymbol") or "")
        exchange = str(row.get("exchange") or "NFO")
        q = _quote_of(quotes, f"{exchange}:{symbol}")
        oi = int(q.get("oi") or 0)
        try:
            ltp = float(q.get("last_price") or 0.0)
        except (TypeError, ValueError):
            ltp = 0.0
        chg_oi = oi_chg_pct(uid, day, symbol, oi)
        chg_ltp = _ltp_chg_pct(q)
        slot = by_strike.setdefault(strike, {})
        if side == "CE":
            slot.update(call_oi=oi, call_oi_chg_pct=chg_oi,
                        call_ltp=ltp, call_ltp_chg_pct=chg_ltp)
        else:
            slot.update(put_oi=oi, put_oi_chg_pct=chg_oi,
                        put_ltp=ltp, put_ltp_chg_pct=chg_ltp)
    return [ChainRow(strike=s, **kw) for s, kw in sorted(by_strike.items())]


def attach_instrument(sig: FlowSignal, contracts: list[dict]) -> FlowSignal:
    """Stamp the real NFO contract onto an armed plan. Engine leaves it None."""
    if sig.plan is None:
        return sig
    plan = sig.plan
    want_type = plan.option_type
    want_strike = float(plan.strike)
    match = None
    for row in contracts:
        if str(row.get("instrument_type")) != want_type:
            continue
        try:
            if abs(float(row.get("strike") or 0.0) - want_strike) > 1e-6:
                continue
        except (TypeError, ValueError):
            continue
        match = row
        break
    if match is None:
        return sig
    ref = to_instrument_ref(match)
    return replace(sig, plan=replace(plan, instrument=ref))


def _spot_of(quotes: dict, name: str) -> float:
    q = _quote_of(quotes, spot_quote_key(name))
    try:
        return float(q.get("last_price") or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _record_spots(uid: str, names: list[str], quotes: dict) -> None:
    """Cache this scan's underlying spots + tokens for the tick subscriber."""
    tokens: dict[str, int] = {}
    spots: dict[str, float] = {}
    for name in names:
        q = _quote_of(quotes, spot_quote_key(name))
        tok = _token_of_quote(q)
        if tok:
            tokens[name] = tok
        try:
            px = float(q.get("last_price") or 0.0)
        except (TypeError, ValueError):
            px = 0.0
        if px > 0:
            spots[name] = px
    _spot_tokens[uid] = tokens
    _last_spots[uid] = spots


async def scan_once(uid: str, cfg: OIWallFlowConfig,
                    strategy: OIWallFlowStrategy) -> list[FlowSignal]:
    """One universe pass. Returns a FlowSignal per underlying that produced a chain."""
    started = time.monotonic()
    today = ist_today()
    day = today.isoformat()
    now_ms = int(datetime.now(_IST).timestamp() * 1000)

    from app.services.exchanges.kite import accounts
    acct = accounts.get_active(uid)
    if not acct:
        _scan_stats[uid] = {"last_run_ms": now_ms, "error": "no active Kite account"}
        return []
    client = await accounts.acquire_client(acct)

    rows = await nfo_dump(uid)
    names = scan_underlyings(rows, cfg)
    by_name: dict[str, list[dict]] = {}
    for r in rows:
        if r.get("segment") != "NFO-OPT":
            continue
        if str(r.get("exchange") or "NFO").upper() != "NFO":
            continue
        n = str(r.get("name") or "").upper()
        if n in names:
            by_name.setdefault(n, []).append(r)

    chosen: list[tuple[str, str, list[dict]]] = []
    quote_keys: list[str] = []
    for name in names:
        contracts = by_name.get(name) or []
        expiry = pick_expiry(contracts, name, cfg, today)
        if not expiry:
            continue
        chain = [c for c in contracts if str(c.get("expiry") or "")[:10] == expiry]
        if not chain:
            continue
        chosen.append((name, expiry, chain))
        quote_keys.append(spot_quote_key(name))
        for c in chain:
            ex = str(c.get("exchange") or "NFO")
            sym = str(c.get("tradingsymbol") or "")
            if sym:
                quote_keys.append(f"{ex}:{sym}")

    pacer = Pacer(_QUOTE_RATE)
    # De-dupe while preserving order so a name that shares a spot key with
    # nothing else still gets quoted once.
    seen: set[str] = set()
    unique_keys = []
    for k in quote_keys:
        if k not in seen:
            seen.add(k)
            unique_keys.append(k)
    quotes = await _quote_batched(client, pacer, unique_keys) if unique_keys else {}
    _record_spots(uid, [name for name, _, _ in chosen], quotes)

    signals: list[FlowSignal] = []
    armed = 0
    for name, expiry, chain in chosen:
        spot = _spot_of(quotes, name)
        if spot <= 0:
            continue
        rows_out = chain_rows_from_quotes(chain, quotes, uid, day)
        if not rows_out:
            continue
        dte = days_to_expiry(expiry, today)
        lot = int(chain[0].get("lot_size") or 1) or 1
        tick = float(chain[0].get("tick_size") or 0.05) or 0.05
        snap = ChainSnapshot(
            underlying=name, spot=spot, expiry=expiry, rows=rows_out,
            at_ms=now_ms, days_to_expiry=dte, lot_size=lot, tick_size=tick,
            exchange="NFO",
        )
        sig = attach_instrument(strategy.evaluate(snap, now_ms=now_ms), chain)
        signals.append(sig)
        if sig.state == "armed":
            armed += 1

    _scan_stats[uid] = {
        "last_run_ms": now_ms,
        "underlyings": len(names),
        "chains": len(chosen),
        "quoted": len(unique_keys),
        "scanned": len(signals),
        "armed": armed,
        "total_seconds": round(time.monotonic() - started, 1),
    }
    return signals
