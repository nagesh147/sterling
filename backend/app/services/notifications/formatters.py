def fmt_signal_alert(snapshot, structure, score) -> str:
    direction = getattr(snapshot, "direction", "neutral").upper()
    tag = "[BULLISH]" if direction == "LONG" else "[BEARISH]" if direction == "SHORT" else "[NEUTRAL]"
    ivr = getattr(snapshot, "ivr", None)
    ivr_str = f"{ivr:.1f}" if ivr is not None else "N/A"
    state = getattr(snapshot, "current_state", getattr(snapshot, "state", ""))
    struct_name = getattr(structure, "structure_type", str(structure)) if structure else "N/A"
    return (
        f"<b>{tag} SIGNAL — {getattr(snapshot, 'underlying', '')}</b>\n"
        f"Score: <b>{score:.1f}</b> | IV Rank: {ivr_str}\n"
        f"State: {state}\n"
        f"Structure: {struct_name}\n"
        f"<i>/enter_{getattr(snapshot, 'underlying', '')} to trade</i>"
    )


def fmt_trail_update(position, new_stop: float, gain_pct: float) -> str:
    pid = getattr(position, "id", "?")
    sym = getattr(position, "underlying", "?")
    return (
        f"<b>TRAIL UPDATE — {sym}</b> [#{pid}]\n"
        f"New stop: <b>${new_stop:,.2f}</b> | Gain: {gain_pct:.2%}"
    )


def fmt_partial_exit(position, partial) -> str:
    pid = getattr(position, "id", "?")
    sym = getattr(position, "underlying", "?")
    close_pct = getattr(partial, "close_pct", 0)
    reason = getattr(partial, "reason", "")
    return (
        f"<b>PARTIAL EXIT — {sym}</b> [#{pid}]\n"
        f"Closed: {close_pct}% | {reason}"
    )


def fmt_position_entered(position) -> str:
    pid = getattr(position, "id", "?")
    sym = getattr(position, "underlying", "?")
    return f"<b>ENTERED — {sym}</b> [#{pid}]\nTrade confirmed."


def fmt_position_closed(position, pnl: float, reason: str) -> str:
    pid = getattr(position, "id", "?")
    sym = getattr(position, "underlying", "?")
    sign = "+" if pnl >= 0 else ""
    return (
        f"<b>CLOSED — {sym}</b> [#{pid}]\n"
        f"P&L: {sign}${pnl:,.2f} | Reason: {reason}"
    )


def fmt_daily_summary(positions, total_pnl: float) -> str:
    lines = ["<b>DAILY SUMMARY</b>"]
    for p in positions:
        pnl = getattr(p, "realized_pnl_usd", None)
        sym = getattr(p, "underlying", "?")
        if pnl is not None:
            sign = "+" if pnl >= 0 else ""
            lines.append(f"  {sym}: {sign}${pnl:,.2f}")
    sign = "+" if total_pnl >= 0 else ""
    lines.append(f"Total: <b>{sign}${total_pnl:,.2f}</b>")
    return "\n".join(lines)


def fmt_circuit_breaker(reason: str) -> str:
    return f"<b>CIRCUIT BREAKER TRIGGERED</b>\nReason: {reason}"
