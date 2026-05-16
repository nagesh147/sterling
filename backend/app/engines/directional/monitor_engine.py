from typing import Optional
from app.schemas.risk import ExitSignal
from app.schemas.execution import SizedTrade
from app.schemas.directional import SignalResult


def check_exits(
    sized_trade: SizedTrade,
    signal: SignalResult,
    current_pnl_usd: float,
    dte_remaining: int,
    current_spot: float = 0.0,
    current_tp: Optional[float] = None,
    current_sl: Optional[float] = None,
    force_exit_dte: int = 3,
    financial_stop_pct: float = 0.50,
    partial_profit_r1: float = 1.5,
    partial_profit_r2: float = 2.0,
) -> ExitSignal:
    """
    Evaluate all exit conditions in priority order:
    1. DTE expiry force-exit
    2. Financial stop (% of max risk)
    3. Spot-price trailing stop (current_sl)
    4. Thesis stop (ST line cross)
    5. Spot-price TP hit (current_tp) — exact and reliable
    6. 2R P&L-based profit exit
    7. 1.5R partial profit
    """
    structure  = sized_trade.structure
    max_risk   = sized_trade.max_risk_usd
    direction  = structure.direction.value

    # 1. DTE expiry
    if dte_remaining <= force_exit_dte:
        return ExitSignal(
            should_exit=True,
            reason=f"DTE {dte_remaining} at/below force-exit threshold {force_exit_dte}",
            exit_type="expiry",
        )

    # 2. Financial stop
    if current_pnl_usd <= -max_risk * financial_stop_pct:
        return ExitSignal(
            should_exit=True,
            reason=(f"Financial stop: P&L {current_pnl_usd:.2f} exceeds "
                    f"{financial_stop_pct:.0%} of max risk {max_risk:.2f}"),
            exit_type="financial",
        )

    # 3. Trailing stop hit by spot price (more reliable than candle low/high check in engine)
    if current_sl is not None and current_sl > 0 and current_spot > 0:
        if direction == "long" and current_spot <= current_sl:
            return ExitSignal(
                should_exit=True,
                reason=f"Trail stop hit: spot {current_spot:.2f} ≤ SL {current_sl:.2f}",
                exit_type="trail_stop",
            )
        elif direction == "short" and current_spot >= current_sl:
            return ExitSignal(
                should_exit=True,
                reason=f"Trail stop hit: spot {current_spot:.2f} ≥ SL {current_sl:.2f}",
                exit_type="trail_stop",
            )

    # 4. Thesis stop: 1H close crossed beyond ST(7,3) line
    st_73 = signal.st_values[0] if signal.st_values and signal.st_values[0] > 0 else 0.0
    if direction == "long":
        if st_73 > 0 and signal.close_1h < st_73:
            return ExitSignal(
                should_exit=True,
                reason=f"Thesis stop: 1H close {signal.close_1h:.2f} below ST(7,3) {st_73:.2f}",
                exit_type="thesis",
            )
        elif st_73 == 0 and signal.all_red:
            return ExitSignal(
                should_exit=True,
                reason="Thesis stop: underlying flipped bearish (all ST red)",
                exit_type="thesis",
            )
    elif direction == "short":
        if st_73 > 0 and signal.close_1h > st_73:
            return ExitSignal(
                should_exit=True,
                reason=f"Thesis stop: 1H close {signal.close_1h:.2f} above ST(7,3) {st_73:.2f}",
                exit_type="thesis",
            )
        elif st_73 == 0 and signal.all_green:
            return ExitSignal(
                should_exit=True,
                reason="Thesis stop: underlying flipped bullish (all ST green)",
                exit_type="thesis",
            )

    # 5. Spot-price TP hit — checked before P&L estimate (P&L uses delta approx; spot is exact)
    if current_tp is not None and current_tp > 0 and current_spot > 0:
        if direction == "long" and current_spot >= current_tp:
            return ExitSignal(
                should_exit=True,
                reason=f"Take-profit hit: spot {current_spot:.2f} ≥ TP {current_tp:.2f}",
                exit_type="full_profit",
            )
        elif direction == "short" and current_spot <= current_tp:
            return ExitSignal(
                should_exit=True,
                reason=f"Take-profit hit: spot {current_spot:.2f} ≤ TP {current_tp:.2f}",
                exit_type="full_profit",
            )

    # 6. Full profit exit at configured R multiple (P&L based)
    if max_risk > 0 and current_pnl_usd >= max_risk * partial_profit_r2:
        return ExitSignal(
            should_exit=True,
            reason=f"Full profit exit at {partial_profit_r2}R ({current_pnl_usd:.2f})",
            exit_type="full_profit",
        )

    # 7. Partial profit at 1.5R
    if max_risk > 0 and current_pnl_usd >= max_risk * partial_profit_r1:
        return ExitSignal(
            should_exit=False,
            reason=f"Partial profit at {partial_profit_r1}R ({current_pnl_usd:.2f})",
            exit_type="partial",
            partial=True,
            partial_ratio=0.50,
        )

    return ExitSignal(should_exit=False, reason="Hold — no exit condition triggered")
