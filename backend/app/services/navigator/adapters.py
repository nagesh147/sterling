"""Adapters that convert an existing Sterling engine's raw signal row into the
broker-neutral `BaseSignalEvidence` contract Navigator's fusion engine
consumes.

Kite-only build: `KiteTripleSupertrendAdapter` is the only adapter here, and
none is planned for the crypto/directional path in this build.
"""
from __future__ import annotations

from app.engines.navigator.schemas import BaseSignalEvidence, canonical_json_hash
from app.engines.sterling_kite_engine.schemas import EngineSignalRow

# Matches `client.get_candles(inst, "1H", _LOOKBACK_BARS)` in
# backend/app/services/kite_engine/scanner.py — the only base timeframe the
# Kite triple-SuperTrend engine evaluates today (spec's `price_timeframe`
# default of "60minute" must match this exactly, not be assumed).
BASE_TIMEFRAME = "60minute"
BASE_TIMEFRAME_MS = 60 * 60 * 1000

STRATEGY_LABEL = "kite_triple_supertrend"


class AdapterError(ValueError):
    """Raised when a raw engine row cannot be honestly adapted.

    Callers must treat this as "no evidence available" and propagate the
    failure — never catch it to synthesize a default/neutral direction.
    """


def kite_config_revision(config_payload: dict) -> str:
    """Stable surrogate revision id for `EngineConfigModel`.

    The Kite engine config has no built-in revision counter, so Navigator
    derives one from a canonical hash of the config payload (e.g.
    `cfg.model_dump(mode="json")`). Any config field change produces a new
    revision, letting fusion detect a stale base-engine config the same way
    it detects a stale Navigator config.
    """
    return canonical_json_hash(config_payload)[:16]


class KiteTripleSupertrendAdapter:
    """Maps one `EngineSignalRow` into a `BaseSignalEvidence`.

    Pure function of its inputs — never mutates the row, never falls back to
    a default direction when the row is ambiguous or stale.
    """

    engine_id = "kite_triple_supertrend"

    @staticmethod
    def adapt(
        row: EngineSignalRow,
        *,
        user_id: str,
        observed_at_ms: int,
        config_revision: str,
    ) -> BaseSignalEvidence:
        if not row.is_fresh and not row.is_active:
            raise AdapterError(
                "EngineSignalRow is neither fresh nor active — no actionable "
                f"base-signal evidence to adapt (underlying={row.underlying!r}, "
                f"token={row.token})"
            )
        if row.timestamp_ms <= 0:
            raise AdapterError(f"invalid timestamp_ms on row: {row.timestamp_ms!r}")

        bar_close_ms = row.timestamp_ms
        bar_open_ms = bar_close_ms - BASE_TIMEFRAME_MS
        if bar_close_ms > observed_at_ms:
            raise AdapterError(
                f"bar_close_ms {bar_close_ms} is after observed_at_ms "
                f"{observed_at_ms} — refusing to adapt a signal from the future"
            )

        state: str = "fresh" if row.is_fresh else "active"
        raw_payload = row.model_dump(mode="json")
        signal_id = (
            f"kite:{row.underlying}:{row.token}:{row.direction}:{row.source}:{bar_close_ms}"
        )

        try:
            return BaseSignalEvidence(
                signal_id=signal_id,
                engine_id=KiteTripleSupertrendAdapter.engine_id,
                user_id=user_id,
                underlying=row.underlying,
                exchange=row.exchange,
                instrument_token=row.token,
                timeframe=BASE_TIMEFRAME,
                bar_open_ms=bar_open_ms,
                bar_close_ms=bar_close_ms,
                observed_at_ms=observed_at_ms,
                direction=row.direction,
                state=state,
                score_100=row.score,
                source=row.source,
                strategy=STRATEGY_LABEL,
                config_revision=config_revision,
                raw_payload_hash=canonical_json_hash(raw_payload),
            )
        except ValueError as exc:
            raise AdapterError(str(exc)) from exc
