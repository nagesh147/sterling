import time
from app.schemas.market import OptionSummary
from app.schemas.execution import CandidateContract

_MAX_SPREAD_PCT = 0.15          # 15% bid-ask spread relative to mid
_MIN_OI = 10.0
_MIN_VOLUME = 1.0
_MAX_STALENESS_SEC = 60 * 5    # 5 minutes
_MAX_MARK_MID_DIFF_PCT = 0.20  # mark vs mid within 20%


def assess_contract_health(
    option: OptionSummary,
    min_dte: int = 5,
) -> CandidateContract:
    now_ms = int(time.time() * 1000)
    staleness_sec = (now_ms - option.last_updated_ms) / 1000.0

    veto_reason = None

    # Hard veto conditions
    if option.bid <= 0 or option.ask <= 0:
        veto_reason = "Invalid bid/ask (zero or negative)"
    elif option.bid >= option.ask:
        veto_reason = "Bid >= ask"
    elif option.dte < min_dte:
        veto_reason = f"DTE {option.dte} < minimum {min_dte}"

    spread = option.ask - option.bid
    mid = option.mid_price if option.mid_price > 0 else (option.bid + option.ask) / 2
    spread_pct = spread / mid if mid > 0 else 1.0

    if veto_reason is None:
        if spread_pct > _MAX_SPREAD_PCT:
            veto_reason = f"Spread {spread_pct:.1%} exceeds {_MAX_SPREAD_PCT:.0%}"
        elif option.open_interest < _MIN_OI:
            veto_reason = f"OI {option.open_interest:.0f} below minimum {_MIN_OI:.0f}"
        elif option.volume_24h < _MIN_VOLUME:
            veto_reason = f"Volume {option.volume_24h:.1f} below minimum {_MIN_VOLUME:.1f}"
        elif staleness_sec > _MAX_STALENESS_SEC:
            veto_reason = f"Quote stale {staleness_sec:.0f}s ago"
        elif mid > 0 and abs(option.mark_price - mid) / mid > _MAX_MARK_MID_DIFF_PCT:
            veto_reason = "Mark vs mid divergence exceeds threshold"

    healthy = veto_reason is None

    # Health score 0–100 (four additive components, each 0–25)
    # spread:    0  = perfect (25 pts),  15% = worst passing (0 pts)
    # liquidity: OI ≥ 100 = full (25 pts),   OI = 10 = min (2.5 pts)
    # volume:    vol ≥ 10  = full (25 pts),   vol = 1  = min (2.5 pts)
    # freshness: staleness = 0 = full (25 pts), at 5 min = 0 pts
    if not healthy:
        health_score = 0.0
    else:
        spread_pts  = max(0.0, 25.0 - spread_pct / _MAX_SPREAD_PCT * 25.0)
        oi_pts      = min(25.0, option.open_interest / 100.0 * 25.0)
        vol_pts     = min(25.0, option.volume_24h / 10.0 * 25.0)
        fresh_pts   = max(0.0, 25.0 * (1.0 - staleness_sec / _MAX_STALENESS_SEC))
        health_score = round(min(100.0, spread_pts + oi_pts + vol_pts + fresh_pts), 2)

    return CandidateContract(
        instrument_name=option.instrument_name,
        underlying=option.underlying,
        strike=option.strike,
        expiry_date=option.expiry_date,
        dte=option.dte,
        option_type=option.option_type,
        bid=option.bid,
        ask=option.ask,
        mark_price=option.mark_price,
        mid_price=mid,
        mark_iv=option.mark_iv,
        delta=option.delta,
        open_interest=option.open_interest,
        volume_24h=option.volume_24h,
        spread_pct=round(spread_pct, 4),
        health_score=health_score,
        healthy=healthy,
        health_veto_reason=veto_reason,
    )
