"""Per-bar Navigator evidence, shaped for the chart overlay.

Two different kinds of number live in here, and the difference matters:

* **Recomputed** — the AVWAP band, the session VWAP, the confirmed pivot
  anchors, the per-bar setup families, the projected ranges and the volatility
  score all come from calling the SAME engine functions the live decision
  calls (`avwap.compute_structure`, `avwap.family_timeline`,
  `projected_ranges.evaluate_ranges`, `volatility.compute_features` /
  `compute_score_and_regime`) over the SAME 1H candles. Drawing them from a
  second implementation would risk an overlay that shows a setup the engine
  never saw, or hides one it acted on.
* **Recorded** — the option-flow oscillator, gamma activity and the decisions
  themselves cannot be recomputed from candles (they need the option-chain
  snapshots the sampler took at the time), so they are read back from what was
  actually stored. Bars with nothing stored are returned as gaps, never as
  zeroes: "Navigator was not watching" and "Navigator saw balanced flow" are
  different facts and must not render the same.

The series is always Navigator's own `60minute` timeframe. Recomputing the
structure on a 5-minute chart would be a different evaluation than the one the
engine makes, so the caller is told the timeframe and renders the caveat
rather than being handed same-looking numbers from a different basis.
"""
from __future__ import annotations

import json
import logging
import math
from typing import Any, Optional

from app.engines.navigator import avwap, projected_ranges, volatility
from app.engines.navigator.quality import CandleValidationError, validate_candles
from app.services.navigator import repository
from app.services.navigator.config_store import NavigatorConfigRecord

log = logging.getLogger(__name__)

TIMEFRAME = "60minute"

#: Bar timestamps at these chart timeframes always include the hourly stamps,
#: so the hourly series can be laid over them without inventing time slots.
HOURLY_COMPATIBLE_TIMEFRAMES = ("1m", "3m", "5m", "15m", "30m", "1H", "60minute")


def _f(value: Any) -> Optional[float]:
    """Finite float or None. NaN is the engine's "no value here" marker and must
    reach the chart as a gap — JSON has no NaN, and 0 would be a lie."""
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _projected(result: projected_ranges.ProjectedRange, context: str) -> dict:
    return {
        "available": bool(result.available),
        "period_open": _f(result.period_open),
        "upper": _f(result.upper),
        "lower": _f(result.lower),
        "sample_count": int(result.sample_count),
        "target_coverage": _f(result.target_coverage),
        "conditioned": bool(result.conditioned),
        "unavailable_reason": result.unavailable_reason,
        "context": context,
    }


def _evidence_of(raw: Optional[str]) -> Optional[dict]:
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        return None
    return parsed if isinstance(parsed, dict) else None


def _recorded_series(uid: str, underlying: str, *, since_ms: int, limit: int) -> tuple[list[dict], list[dict], int]:
    """`(flow, gamma, snapshot_count)` from the stored feature snapshots."""
    from app.services.navigator import service as nav_service

    rows = nav_service.get_feature_series(
        uid, underlying, timeframe=TIMEFRAME, since_bar_close_ms=since_ms, limit=limit,
    )
    flow: list[dict] = []
    gamma: list[dict] = []
    for row in rows:
        bar_ms = int(row.get("bar_close_ms") or 0)
        if bar_ms <= 0:
            continue
        flow_ev = _evidence_of(row.get("flow_json"))
        if flow_ev:
            diagnostics = flow_ev.get("diagnostics") or {}
            flow.append({
                "t": bar_ms // 1000,
                "oscillator": _f(diagnostics.get("oscillator")),
                "state": diagnostics.get("state"),
                "direction": int(flow_ev.get("direction") or 0),
                "confidence": _f(flow_ev.get("confidence_100")),
                "quality": flow_ev.get("quality"),
            })
        gamma_ev = _evidence_of(row.get("gamma_json"))
        if gamma_ev:
            direction = int(gamma_ev.get("direction") or 0)
            confidence = _f(gamma_ev.get("confidence_100")) or 0.0
            gamma.append({
                "t": bar_ms // 1000,
                # Gamma records a direction and a confidence, not a level. The
                # signed confidence is the only honest single number for it.
                "signed_confidence": direction * confidence,
                "direction": direction,
                "confidence": confidence,
                "quality": gamma_ev.get("quality"),
            })
    return flow, gamma, len(rows)


def _recorded_decisions(uid: str, underlying: str, *, since_ms: int, limit: int) -> list[dict]:
    try:
        rows = repository.fetch_signal_events_page(uid, underlying=underlying, limit=limit)
    except Exception as exc:  # noqa: BLE001 — an overlay must never break on storage
        log.debug("navigator chart: decision read failed for %s/%s: %s", uid, underlying, exc)
        return []
    out: list[dict] = []
    for row in rows:
        bar_ms = int(row.get("bar_close_ms") or 0)
        if bar_ms < since_ms:
            continue
        payload = _evidence_of(row.get("payload_json")) or {}
        # A NavigatorDecision carries evidence and a verdict — it has no
        # entry/stop/target. Those belong to the origination ROW built from it,
        # so the overlay must not invent a plan the decision never held.
        out.append({
            "t": bar_ms // 1000,
            "decision_id": row.get("decision_id"),
            "direction": row.get("direction"),
            "status": row.get("status"),
            "trigger": payload.get("trigger"),
            "effective_score": _f(row.get("effective_score")),
            "base_score": _f(payload.get("base_score")),
            "execution_eligible": bool(row.get("execution_eligible")),
            "data_quality": payload.get("data_quality"),
            "reason_codes": [str(c) for c in (payload.get("reason_codes") or [])][:8],
        })
    out.sort(key=lambda d: d["t"])
    return out


async def build_chart_series(
    client, uid: str, underlying: str, *, token: int, record: NavigatorConfigRecord, bars: int = 320,
) -> dict:
    """Everything the chart needs to draw Navigator over `underlying`'s candles."""
    from app.services.navigator.service import _fetch_candles_for_navigator

    config = record.config
    notes: list[str] = []
    configured = underlying in set(config.underlyings or [])
    if not config.enabled:
        notes.append("Navigator is off — this is its structure maths on live candles. "
                     "Nothing was recorded, so there are no flow, gamma or decision overlays.")
    if not configured:
        notes.append(f"Navigator does not scan {underlying}, so it never evaluated these bars. "
                     "The structure shown is its maths applied to this instrument's candles.")

    def _nothing_to_draw(reason: str) -> dict:
        return {
            "underlying": underlying, "token": token, "timeframe": TIMEFRAME,
            "enabled": bool(config.enabled), "configured": configured,
            "config_revision": record.revision, "bar_count": len(raw_candles),
            "structure": [], "anchors": [], "projected": None, "volatility": None,
            "flow": [], "gamma": [], "decisions": [], "snapshot_count": 0,
            "notes": notes + [reason],
        }

    raw_candles = await _fetch_candles_for_navigator(client, token, lookback_bars=bars)
    if len(raw_candles) < 60:
        return _nothing_to_draw(
            f"Only {len(raw_candles)} hourly bars available — Navigator needs 60 to evaluate.")
    try:
        candles = validate_candles(raw_candles)
    except CandleValidationError as exc:
        # The live pass skips an underlying whose candles fail validation, so the
        # overlay must show nothing for it too. Drawing a band over candles the
        # engine refused would claim an evaluation that never happened.
        return _nothing_to_draw(f"Navigator rejected these candles and did not evaluate them: {exc}")

    structure = avwap.compute_structure(candles, config.avwap)
    timeline = avwap.family_timeline(candles, structure, config.avwap)

    features = volatility.compute_features(candles, config.volatility)
    scored = volatility.compute_score_and_regime(features, config.volatility)

    bars_out: list[dict] = []
    for i in range(candles.n):
        family = timeline.family_at(i)
        bars_out.append({
            "t": int(candles.timestamp_ms[i]) // 1000,
            "upper": _f(structure.upper[i]),
            "mid": _f(structure.mid[i]),
            "lower": _f(structure.lower[i]),
            "session_vwap": _f(structure.session_vwap[i]),
            "atr": _f(structure.atr[i]),
            "relative_volume": _f(structure.relative_volume[i]),
            "mid_slope": _f(structure.mid_slope[i]),
            "warming_up": bool(structure.warming_up[i]),
            "vol_score": _f(scored.vol_score[i]),
            "regime": scored.regime[i],
            "adx": _f(features.adx[i]),
            # `setup` is the family that held on this bar; `fired` is whether the
            # cooldown let it count. A setup with fired=false is one Navigator
            # deliberately ignored, and the overlay draws it differently.
            "setup": family[0] if family else None,
            "fired": bool(timeline.fired[i]),
        })

    anchors: list[dict] = []
    for kind, pivots in (("high", structure.high_pivots), ("low", structure.low_pivots)):
        for pivot in pivots:
            if pivot.visible_from_index >= candles.n:
                continue  # not yet confirmed within this window — never anticipate it
            anchors.append({
                "kind": kind,
                "pivot_t": int(candles.timestamp_ms[pivot.bar_index]) // 1000,
                "confirmed_t": int(candles.timestamp_ms[pivot.visible_from_index]) // 1000,
                "price": _f(pivot.price),
            })

    last_atr = _f(structure.atr[-1])
    try:
        range_eval = projected_ranges.evaluate_ranges(candles, config.ranges, atr_value=last_atr)
        projected = {
            "daily": _projected(range_eval.daily, range_eval.daily_context),
            "weekly": _projected(range_eval.weekly, range_eval.weekly_context),
        }
    except Exception as exc:  # noqa: BLE001
        log.debug("navigator chart: range evaluation failed for %s: %s", underlying, exc)
        projected = None
        notes.append("Projected ranges unavailable for this window.")

    first_bar_ms = int(candles.timestamp_ms[0])
    flow, gamma, snapshot_count = ([], [], 0)
    decisions: list[dict] = []
    try:
        flow, gamma, snapshot_count = _recorded_series(uid, underlying, since_ms=first_bar_ms, limit=max(bars, 320))
        decisions = _recorded_decisions(uid, underlying, since_ms=first_bar_ms, limit=200)
    except Exception as exc:  # noqa: BLE001
        log.debug("navigator chart: recorded evidence read failed for %s: %s", underlying, exc)

    if not snapshot_count:
        notes.append("No option-chain evidence was recorded over these bars, so flow and gamma have nothing to draw.")
    if not decisions:
        notes.append("Navigator recorded no decision on these bars.")
    if bool(structure.warming_up[-1]):
        notes.append("AVWAP is still warming up at the latest bar — it needs a confirmed swing high AND low.")

    return {
        "underlying": underlying,
        "token": token,
        "timeframe": TIMEFRAME,
        "enabled": bool(config.enabled),
        "configured": configured,
        "config_revision": record.revision,
        "bar_count": candles.n,
        "structure": bars_out,
        "anchors": anchors,
        "projected": projected,
        "volatility": {
            "regime": scored.regime[-1],
            "vol_score": _f(scored.vol_score[-1]),
            "adx": _f(features.adx[-1]),
        },
        "flow": flow,
        "gamma": gamma,
        "decisions": decisions,
        "snapshot_count": snapshot_count,
        "notes": notes,
    }


def resolve_underlying_token(cfg_indices: list[dict], underlying: str) -> Optional[int]:
    """Spot token for an index underlying from the static engine config.

    Indices are matched on any of the three names they carry (`name`,
    `spot_symbol`, `option_name`) because the board, the option chain and the
    chart each use a different one — `NIFTY BANK` and `BANKNIFTY` are the same
    instrument.
    """
    want = (underlying or "").strip().upper()
    if not want:
        return None
    for index in cfg_indices:
        candidates = {
            str(index.get("name", "")).upper(),
            str(index.get("spot_symbol", "")).upper(),
            str(index.get("option_name", "")).upper(),
        }
        if want in candidates:
            token = int(index.get("spot_token", 0) or 0)
            return token or None
    return None


__all__ = ["build_chart_series", "resolve_underlying_token", "TIMEFRAME", "HOURLY_COMPATIBLE_TIMEFRAMES"]
