"""NIFTY ORB option-level historical replay endpoint."""
from fastapi import APIRouter, HTTPException
from app.engines.nifty_orb_option_replay import OptionBar, ReplayCostConfig, replay_trade, summarize_replay
from datetime import datetime

router = APIRouter(prefix="/nifty-orb-options", tags=["nifty-orb-options"])


def _option_bar(row: dict) -> OptionBar:
    ts = row.get("timestamp")
    if isinstance(ts, datetime):
        dt = ts
    else:
        dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    return OptionBar(
        timestamp=dt,
        symbol=str(row["symbol"]),
        option_type=str(row["option_type"]),
        strike=float(row["strike"]),
        expiry=str(row["expiry"]),
        open=float(row["open"]),
        high=float(row["high"]),
        low=float(row["low"]),
        close=float(row["close"]),
        bid=float(row.get("bid") or 0),
        ask=float(row.get("ask") or 0),
        volume=float(row.get("volume") or 0),
        open_interest=float(row.get("open_interest") or 0),
        lot_size=int(row.get("lot_size") or 1),
    )


@router.post("/replay")
async def replay(body: dict) -> dict:
    rows = body.get("bars")
    if not isinstance(rows, list) or not rows:
        raise HTTPException(422, "bars must be a non-empty option OHLC list")
    try:
        bars = [_option_bar(row) for row in rows]
        costs = ReplayCostConfig(
            slippage_points=float(body.get("slippage_points") or 0),
            brokerage_per_order=float(body.get("brokerage_per_order") or 0),
            charges_per_order=float(body.get("charges_per_order") or 0),
        )
        trades = []
        for item in body.get("trades", []):
            start = int(item["entry_index"])
            trade = replay_trade(bars, start, float(item["risk_points"]), float(item.get("target_r") or 2), costs)
            if trade:
                trades.append(trade)
        return {"trades": [trade.to_dict() for trade in trades], "metrics": summarize_replay(trades), "option_pnl": True}
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(422, str(exc)) from exc
