from app.schemas.risk import ExitSignal
from app.schemas.execution import SizedTrade
from app.schemas.directional import SignalResult


def check_exits(
    sized_trade: SizedTrade,
    signal: SignalResult,
    current_pnl_usd: float,
    dte_remaining: int,
    force_exit_dte: int = 3,
) -> ExitSignal:
    structure = sized_trade.structure
    max_risk = sized_trade.max_risk_usd

    # Expiry stop
    if dte_remaining <= force_exit_dte:
        return ExitSignal(
            should_exit=True,
            reason=f"DTE {dte_remaining} at/below force-exit threshold {force_exit_dte}",
            exit_type="expiry",
        )

    # Financial stop: lost >= 50% of max risk
    if current_pnl_usd <= -max_risk * 0.50:
        return ExitSignal(
            should_exit=True,
            reason=f"Financial stop: P&L {current_pnl_usd:.2f} exceeds 50% of max risk {max_risk:.2f}",
            exit_type="financial",
        )

    # Thesis stop: underlying trend flipped
    direction = structure.direction.value
    if direction == "long" and signal.all_red:
        return ExitSignal(
            should_exit=True,
            reason="Thesis stop: underlying flipped bearish (all ST red)",
            exit_type="thesis",
        )
    if direction == "short" and signal.all_green:
        return ExitSignal(
            should_exit=True,
            reason="Thesis stop: underlying flipped bullish (all ST green)",
            exit_type="thesis",
        )

    # Partial profit at 1.5R
    if max_risk > 0 and current_pnl_usd >= max_risk * 1.5:
        return ExitSignal(
            should_exit=False,
            reason=f"Partial profit at 1.5R ({current_pnl_usd:.2f})",
            exit_type="partial",
            partial=True,
            partial_ratio=0.50,
        )

    return ExitSignal(should_exit=False, reason="Hold — no exit condition triggered")
