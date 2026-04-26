from app.schemas.risk import ExitSignal
from app.schemas.execution import SizedTrade
from app.schemas.directional import SignalResult


def check_exits(
    sized_trade: SizedTrade,
    signal: SignalResult,
    current_pnl_usd: float,
    dte_remaining: int,
    force_exit_dte: int = 3,
    financial_stop_pct: float = 0.50,
    partial_profit_r1: float = 1.5,
    partial_profit_r2: float = 2.0,
) -> ExitSignal:
    structure = sized_trade.structure
    max_risk = sized_trade.max_risk_usd
    direction = structure.direction.value

    # Expiry stop
    if dte_remaining <= force_exit_dte:
        return ExitSignal(
            should_exit=True,
            reason=f"DTE {dte_remaining} at/below force-exit threshold {force_exit_dte}",
            exit_type="expiry",
        )

    # Financial stop
    if current_pnl_usd <= -max_risk * financial_stop_pct:
        return ExitSignal(
            should_exit=True,
            reason=f"Financial stop: P&L {current_pnl_usd:.2f} exceeds {financial_stop_pct:.0%} of max risk {max_risk:.2f}",
            exit_type="financial",
        )

    # Thesis stop: 1H close crossed beyond ST(7,3) line
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

    # Full profit exit at 2R
    if max_risk > 0 and current_pnl_usd >= max_risk * partial_profit_r2:
        return ExitSignal(
            should_exit=True,
            reason=f"Full profit exit at {partial_profit_r2}R ({current_pnl_usd:.2f})",
            exit_type="full_profit",
        )

    # Partial profit at 1.5R (reduce position 50%)
    if max_risk > 0 and current_pnl_usd >= max_risk * partial_profit_r1:
        return ExitSignal(
            should_exit=False,
            reason=f"Partial profit at {partial_profit_r1}R ({current_pnl_usd:.2f})",
            exit_type="partial",
            partial=True,
            partial_ratio=0.50,
        )

    return ExitSignal(should_exit=False, reason="Hold — no exit condition triggered")
