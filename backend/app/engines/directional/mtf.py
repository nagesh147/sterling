"""
B5: Multi-timeframe score decomposition.

Pure helper that condenses the regime/signal/exec results into a single
dict consumable by the frontend. The numeric components mirror the same
0-20 / 0-15 caps used in the structure scoring so the UI can render
identical magnitudes.
"""
from __future__ import annotations
from typing import Dict, Any
from app.schemas.directional import (
    RegimeResult, SignalResult, ExecTimingResult, ExecMode,
)


def compute_mtf_breakdown(
    regime: RegimeResult,
    signal: SignalResult,
    exec_timing: ExecTimingResult,
) -> Dict[str, Any]:
    macro = float(min(20.0, max(0.0, regime.score)))
    sig   = float(min(20.0, max(0.0, signal.signal_score)))
    exec_ = float(min(15.0, max(0.0, exec_timing.exec_score)))

    # Alignment categorization for UI chips
    macro_ok  = macro >= 12.0
    signal_ok = sig >= 14.0    # 70% of the 20-pt scale → strong signal
    exec_ok   = exec_timing.mode != ExecMode.WAIT and exec_ >= 10.0

    if macro_ok and signal_ok and exec_ok:
        alignment = "all_aligned"
        alignment_label = "All timeframes aligned"
    elif macro_ok and signal_ok and not exec_ok:
        alignment = "exec_pending"
        alignment_label = "Macro + signal aligned; waiting for execution trigger"
    elif macro_ok and not signal_ok:
        alignment = "signal_weak"
        alignment_label = "Macro trend present but 1H confluence weak"
    elif not macro_ok and signal_ok:
        alignment = "macro_unaligned"
        alignment_label = "Strong 1H signal but macro regime undecided"
    else:
        alignment = "no_alignment"
        alignment_label = "Insufficient confluence"

    return {
        "macro_4h": round(macro, 2),
        "signal_1h": round(sig, 2),
        "execution_15m": round(exec_, 2),
        "macro_ok": macro_ok,
        "signal_ok": signal_ok,
        "exec_ok": exec_ok,
        "alignment": alignment,
        "alignment_label": alignment_label,
        "exec_mode": exec_timing.mode.value,
    }
