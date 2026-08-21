"""Runtime plumbing for the ATM Premium Imbalance strategy.

Config persistence and instrument resolution only. All strategy mathematics
lives in ``app.engines.atm_premium_imbalance`` and is deliberately reachable
from here without any broker object, so replay exercises the same code.

Instrument resolution reuses the existing Kite BFO path -- including the
``SENSEX -> BSX`` name alias that Kite's instrument dump uses -- rather than
building option symbols by string formatting. A fabricated key is an order that
either rejects or hits a contract nobody chose.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional

from app.core.logging import get_logger
from app.engines.atm_premium_imbalance import (
    ATMPremiumImbalanceConfig,
    q2,
    InstrumentRef,
    OptionPairRef,
    STRATEGY_ID,
    STRATEGY_NAME,
    CONTRACT_VERSION,
    resolve_pair as _resolve_pair,
    select_expiry,
)

log = get_logger(__name__)

_IST = timezone(timedelta(hours=5, minutes=30))
_CONFIG_KEY = "atm_premium_imbalance_config"

#: The BFO instrument dump is ~100k rows and changes once a day. Refetching it
#: per tick would be the classic hot-path mistake this codebase has hit before.
_DUMP_TTL_S = 900.0
_dump_cache: dict[str, tuple[float, list[dict]]] = {}


def ist_today() -> date:
    return datetime.now(_IST).date()


# ------------------------------------------------------------------ config

def get_config() -> ATMPremiumImbalanceConfig:
    """Load the persisted config, falling back to safe disabled defaults.

    A stored row that no longer validates must never become a trading config:
    the failure would otherwise surface deep inside the engine mid-session.
    Disabled is the safe state, so that is the fallback.
    """
    default = ATMPremiumImbalanceConfig(enabled=False)
    try:
        from app.services import db
        raw = db.get_config(_CONFIG_KEY)
    except Exception:
        return default
    if not raw:
        return default
    try:
        stored = json.loads(raw) if isinstance(raw, str) else raw
        known = ATMPremiumImbalanceConfig.field_names()
        merged = {**default.as_dict(), **{k: v for k, v in dict(stored).items() if k in known}}
        return ATMPremiumImbalanceConfig(**merged).validate()
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        log.error(
            "Stored %s config is invalid (%s); falling back to disabled defaults",
            STRATEGY_ID, exc,
        )
        return default


def set_config(values: dict[str, Any]) -> ATMPremiumImbalanceConfig:
    """Persist a config change. Validation is the engine's, not a second copy."""
    current = get_config().as_dict()
    unknown = sorted(set(values) - set(current))
    if unknown:
        raise ValueError(f"Unknown {STRATEGY_ID} config fields: {', '.join(unknown)}")
    current.update(values)
    cfg = ATMPremiumImbalanceConfig(**current).validate()
    from app.services import db
    db.set_config(_CONFIG_KEY, json.dumps(cfg.as_dict(), separators=(",", ":")))
    return cfg


# -------------------------------------------------- instrument resolution

async def _bfo_dump(uid: str) -> list[dict]:
    from app.services.exchanges.kite import accounts
    cached = _dump_cache.get(uid)
    now = datetime.now(timezone.utc).timestamp()
    if cached and now - cached[0] < _DUMP_TTL_S:
        return cached[1]
    acct = accounts.get_active(uid)
    if not acct:
        raise RuntimeError("No active Kite account")
    client = await accounts.acquire_client(acct)
    rows = await client.search_instruments("", "BFO", limit=1_000_000)
    _dump_cache[uid] = (now, rows)
    return rows


def _to_instrument_ref(row: dict, exchange: str = "BFO") -> InstrumentRef:
    """Map a Kite chain row onto the engine's instrument model.

    ``instrument_id`` is the Kite instrument token, stringified. It is opaque to
    the strategy -- the point is that it came from the dump, not from a template.
    """
    option_type = "CE" if str(row.get("option_type", "")).lower() == "call" else "PE"
    return InstrumentRef(
        instrument_id=str(row.get("token") or ""),
        tradingsymbol=str(row.get("instrument_name") or ""),
        option_type=option_type,
        strike=float(row.get("strike") or 0.0),
        expiry=str(row.get("expiry_date") or "")[:10],
        lot_size=int(row.get("lot_size") or 1) or 1,
        tick_size=float(row.get("tick_size") or 0.05) or 0.05,
        upper_circuit=None,
        exchange=exchange,
    )


async def resolve_option_pair(
    uid: str,
    cfg: Optional[ATMPremiumImbalanceConfig] = None,
    *,
    underlying_ltp: Optional[float] = None,
    today: Optional[date] = None,
) -> OptionPairRef:
    """Resolve the ATM CE/PE pair for the configured underlying and expiry."""
    cfg = cfg or get_config()
    day = today or ist_today()

    from app.services.kite_engine.strikes import chain_rows_for
    rows = chain_rows_for(await _bfo_dump(uid), cfg.underlying, day)
    if not rows:
        raise RuntimeError(f"no listed {cfg.underlying} options found in the BFO dump")

    expiry = select_expiry(
        [r["expiry_date"] for r in rows],
        policy=cfg.expiry_policy,
        today=day,
        explicit=cfg.explicit_expiry,
    )

    if underlying_ltp is None:
        underlying_ltp = await _underlying_ltp(uid, cfg.underlying)

    contracts = [_to_instrument_ref(r) for r in rows if r["expiry_date"] == expiry]
    contracts = [c for c in contracts if c.instrument_id and c.tradingsymbol]
    return _resolve_pair(
        underlying=cfg.underlying,
        underlying_ltp=float(underlying_ltp),
        contracts=contracts,
        expiry=expiry,
    )


async def _underlying_ltp(uid: str, underlying: str) -> float:
    """Spot for the index. SENSEX/BANKEX quote on BSE, everything else on NSE."""
    from app.services.exchanges.kite import accounts
    acct = accounts.get_active(uid)
    if not acct:
        raise RuntimeError("No active Kite account")
    client = await accounts.acquire_client(acct)
    prefix = "BSE:" if underlying.upper() in {"SENSEX", "BANKEX"} else "NSE:"
    quotes = await client.get_ltp([f"{prefix}{underlying.upper()}"])
    for value in (quotes or {}).values():
        ltp = float((value or {}).get("last_price") or 0.0)
        if ltp > 0:
            return ltp
    raise RuntimeError(f"no LTP available for {underlying}")


# ------------------------------------------------------------------ status

def descriptor() -> dict:
    """Static identity, mirroring the contract. No live state."""
    return {
        "id": STRATEGY_ID,
        "name": STRATEGY_NAME,
        "contract_version": CONTRACT_VERSION,
        "tagline": "Buys the cheaper ATM leg at the open and takes a fixed +15 points.",
        "how_it_works": (
            "At market open it compares the ATM call and put premiums and buys whichever "
            "is cheaper, then exits at the entry fill plus 15 points. One trade per session. "
            "No indicators are involved."
        ),
        "provenance": "Reverse-engineered from recordings; see docs/strategy/atm-premium-imbalance/",
        "live_ready": False,
    }


async def snapshot(uid: str) -> dict:
    """Operator view: config, resolved pair, and why it is or is not armed."""
    cfg = get_config()
    from app.services.atm_premium_imbalance_runner import session_status
    from app.services.atm_premium_imbalance_sim import state as _sim_state
    out: dict[str, Any] = {
        "strategy": {**descriptor(), "enabled": cfg.enabled},
        "config": cfg.as_dict(),
        "resolved": None,
        "session": session_status(uid),
        # Present only while a simulation is running or has just finished. The
        # board must never render replayed numbers as live ones.
        "simulation": _sim_state(uid),
        "blockers": [],
    }
    if not cfg.enabled:
        out["blockers"].append("strategy disabled")
    if not cfg.size_is_set:
        out["blockers"].append("lots not set" if cfg.sizing_mode == "LOTS"
                               else "quantity not set")
    try:
        pair = await resolve_option_pair(uid, cfg)
        out["resolved"] = {
            "underlying": pair.underlying,
            "expiry": pair.expiry,
            "strike": pair.strike,
            "ce": {"instrument_id": pair.ce.instrument_id, "tradingsymbol": pair.ce.tradingsymbol,
                   "lot_size": pair.ce.lot_size},
            "pe": {"instrument_id": pair.pe.instrument_id, "tradingsymbol": pair.pe.tradingsymbol,
                   "lot_size": pair.pe.lot_size},
        }
        # A size the broker will refuse would be refused at the open -- the one
        # moment this strategy trades, with a three-attempt budget and one trade
        # per session. Report it here so the board shows it before arming, not
        # after the entry fails. Same function arm() uses, so they cannot differ.
        lot = int(pair.ce.lot_size or 0)
        qty = cfg.effective_quantity(lot) if cfg.size_is_set else 0
        out["sizing"] = {
            "mode": cfg.sizing_mode,
            "lot_size": lot,
            "quantity": qty,
            "max_premium_at_risk_inr": cfg.max_premium_at_risk_inr,
            # The premium ceiling divided by the size: the dearest option this
            # configuration can actually buy. Shown because the alternative is
            # discovering it as a halt at the open, and the entry happens
            # milliseconds after the bell -- too late to change anything.
            "max_affordable_premium": (
                q2(cfg.max_premium_at_risk_inr / qty)
                if qty > 0 and cfg.max_premium_at_risk_inr > 0 else None
            ),
        }
        blocker = cfg.sizing_blocker(lot) if cfg.size_is_set else None
        if blocker:
            out["blockers"].append(blocker)
    except Exception as exc:
        out["blockers"].append(f"instrument resolution failed: {exc}")

    # A position nothing accounts for is the most dangerous state this strategy
    # can be in: arming would double the exposure. It belongs in the blockers,
    # not only in a log line.
    try:
        from app.services.atm_premium_imbalance_runner import orphan_positions
        orphans = await orphan_positions(uid, cfg)
    except Exception as exc:  # noqa: BLE001
        orphans = []
        log.debug("ATM PI orphan check failed for %s: %s", uid, exc)
    out["orphan_positions"] = orphans
    for o in orphans:
        out["blockers"].append(
            f"open position {o['symbol']} ({o['quantity']} @ {o['entry_price']}) "
            f"is not accounted for — adopt or close it")
    return out
