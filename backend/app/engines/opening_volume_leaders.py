"""Causal opening-volume leader detection for Indian cash equities.

The engine implements the observable, documented core of ORION Scan without
copying its UI or pretending to know its private scoring weights:

* compare today's completed 09:15 one-minute volume with the same stock's
  09:15 volume over the preceding ten sessions;
* classify the resulting relative volume at 2x/3x/5x/10x;
* take direction from the 09:15 candle colour;
* track the first later breach of that candle's high or low; and
* expose, rather than silently discard, liquidity and candle-quality failures.

This module is pure and advisory-only.  It performs no broker I/O, option
selection, position sizing, or order submission.  The proprietary site's exact
numeric strength-score and late-entry formula are not publicly observable, so
they are deliberately not fabricated here.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import date, datetime, time, timedelta
from enum import Enum
from itertools import pairwise
from math import isfinite
from statistics import mean
from zoneinfo import ZoneInfo

from app.engines.nifty_orb_options import Bar

IST = ZoneInfo("Asia/Kolkata")
SESSION_OPEN = time(9, 15)
SESSION_CLOSE = time(15, 30)


class LeaderDirection(str, Enum):
    UP = "UP"
    DOWN = "DOWN"
    NEUTRAL = "NEUTRAL"


class LeaderTier(str, Enum):
    WEAK = "weak"
    WATCH = "watch"
    SPURT = "spurt"
    STRONG = "strong"
    EXPLOSIVE = "explosive"


class CandleQuality(str, Enum):
    WEAK = "weak"
    MODERATE = "moderate"
    STRONG = "strong"


class LiquidityState(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    UNKNOWN = "unknown"


class EntryPhase(str, Enum):
    OPENING = "opening"
    PLANNING = "planning"
    PRIME = "prime"
    MANAGE = "manage"
    DECAY = "decay"
    NO_NEW_ENTRY = "no_new_entry"
    EXIT = "exit"
    FLAT = "flat"
    CLOSED = "closed"


@dataclass(frozen=True)
class OpeningVolumeConfig:
    """Versioned thresholds for the opening-volume signal contract.

    RVOL tier boundaries, the ten-session same-minute baseline, and the Layer-1
    liquidity floors are directly observable in the source material.  Candle
    body/close-location boundaries are a transparent local implementation of
    the documented "fat body, close near the extreme" condition; they are not
    asserted to equal the source site's private formula.
    """

    baseline_sessions: int = 10
    turnover_sessions: int = 20
    min_turnover_bars_per_session: int = 300
    watch_rvol: float = 2.0
    spurt_rvol: float = 3.0
    strong_rvol: float = 5.0
    explosive_rvol: float = 10.0
    min_price_inr: float = 100.0
    min_average_turnover_inr: float = 20_000_000.0
    moderate_body_fraction: float = 0.35
    strong_body_fraction: float = 0.60
    moderate_close_location: float = 0.60
    strong_close_location: float = 0.75

    def validate(self) -> OpeningVolumeConfig:
        if self.baseline_sessions < 1:
            raise ValueError("baseline_sessions must be >= 1")
        if self.turnover_sessions < 1:
            raise ValueError("turnover_sessions must be >= 1")
        if self.min_turnover_bars_per_session < 1:
            raise ValueError("min_turnover_bars_per_session must be >= 1")
        thresholds = (
            self.watch_rvol,
            self.spurt_rvol,
            self.strong_rvol,
            self.explosive_rvol,
        )
        if not all(isfinite(v) and v > 0 for v in thresholds):
            raise ValueError("RVOL thresholds must be finite and greater than zero")
        if not all(a < b for a, b in pairwise(thresholds)):
            raise ValueError(
                "RVOL thresholds must satisfy watch < spurt < strong < explosive"
            )
        if not (isfinite(self.min_price_inr) and self.min_price_inr >= 0):
            raise ValueError("min_price_inr must be finite and non-negative")
        if not (
            isfinite(self.min_average_turnover_inr)
            and self.min_average_turnover_inr >= 0
        ):
            raise ValueError("min_average_turnover_inr must be finite and non-negative")
        fractions = (
            self.moderate_body_fraction,
            self.strong_body_fraction,
            self.moderate_close_location,
            self.strong_close_location,
        )
        if not all(isfinite(v) and 0 <= v <= 1 for v in fractions):
            raise ValueError("candle-quality fractions must be between zero and one")
        if self.moderate_body_fraction > self.strong_body_fraction:
            raise ValueError(
                "moderate_body_fraction cannot exceed strong_body_fraction"
            )
        if self.moderate_close_location > self.strong_close_location:
            raise ValueError(
                "moderate_close_location cannot exceed strong_close_location"
            )
        return self


@dataclass(frozen=True)
class LeaderSignal:
    symbol: str
    session_date: date
    signal_time: datetime
    observed_at: datetime
    direction: LeaderDirection
    tier: LeaderTier
    rvol: float
    opening_volume: float
    average_opening_volume: float
    baseline_session_count: int
    opening_open: float
    opening_high: float
    opening_low: float
    opening_close: float
    current_price: float
    previous_close: float | None
    day_change_pct: float | None
    gap_pct: float | None
    body_pct: float
    range_pct: float
    body_fraction: float
    close_location: float
    candle_quality: CandleQuality
    average_turnover_inr: float | None
    turnover_session_count: int
    liquidity_state: LiquidityState
    liquidity_reasons: tuple[str, ...]
    orb_break_side: LeaderDirection | None
    orb_break_time: datetime | None
    orb_cumulative_volume: float | None
    orb_aligned: bool
    orb_immediate: bool
    combo: bool
    rise_from_low_pct: float
    fall_from_high_pct: float
    is_leader: bool
    passes_quality_filters: bool
    entry_phase: EntryPhase

    @property
    def signal_key(self) -> str:
        return f"opening-volume:{self.session_date.isoformat()}:{self.symbol}:{self.direction.value}"

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload.update(
            {
                "session_date": self.session_date.isoformat(),
                "signal_time": self.signal_time.isoformat(),
                "observed_at": self.observed_at.isoformat(),
                "direction": self.direction.value,
                "tier": self.tier.value,
                "candle_quality": self.candle_quality.value,
                "liquidity_state": self.liquidity_state.value,
                "liquidity_reasons": list(self.liquidity_reasons),
                "orb_break_side": self.orb_break_side.value
                if self.orb_break_side
                else None,
                "orb_break_time": self.orb_break_time.isoformat()
                if self.orb_break_time
                else None,
                "entry_phase": self.entry_phase.value,
                "signal_key": self.signal_key,
            }
        )
        return payload


def _as_ist(timestamp: datetime) -> datetime:
    if timestamp.tzinfo is None:
        return timestamp.replace(tzinfo=IST)
    return timestamp.astimezone(IST)


def _validate_bar(bar: Bar) -> None:
    values = (bar.open, bar.high, bar.low, bar.close, bar.volume)
    if not all(isfinite(float(value)) for value in values):
        raise ValueError("bars must contain finite OHLCV values")
    if min(bar.open, bar.high, bar.low, bar.close) <= 0:
        raise ValueError("bar prices must be greater than zero")
    if bar.volume < 0:
        raise ValueError("bar volume cannot be negative")
    if bar.high < max(bar.open, bar.close) or bar.low > min(bar.open, bar.close):
        raise ValueError("bar high/low do not contain open and close")


def _session_rows(
    bars: Iterable[Bar],
    *,
    as_of: datetime | None = None,
) -> dict[date, list[Bar]]:
    rows: dict[date, dict[datetime, Bar]] = {}
    observed_at = _as_ist(as_of) if as_of is not None else None
    for bar in bars:
        timestamp = _as_ist(bar.timestamp).replace(microsecond=0)
        if not (SESSION_OPEN <= timestamp.time() < SESSION_CLOSE):
            continue
        if (
            observed_at is not None
            and timestamp.replace(second=0, microsecond=0) + timedelta(minutes=1)
            > observed_at
        ):
            continue
        _validate_bar(bar)
        # Provider retries can return the same candle twice.  The latest copy is
        # authoritative and prevents duplicate volume from contaminating RVOL.
        rows.setdefault(timestamp.date(), {})[timestamp] = bar
    return {
        session: sorted(values.values(), key=lambda bar: _as_ist(bar.timestamp))
        for session, values in rows.items()
    }


def _completed_rows(
    bars: Sequence[Bar], as_of: datetime, interval_minutes: int = 1
) -> list[Bar]:
    now = _as_ist(as_of)
    return [
        bar
        for bar in bars
        if _as_ist(bar.timestamp).replace(second=0, microsecond=0)
        + timedelta(minutes=interval_minutes)
        <= now
    ]


def _opening_bar(rows: Sequence[Bar]) -> Bar | None:
    return next(
        (
            bar
            for bar in rows
            if _as_ist(bar.timestamp).hour == SESSION_OPEN.hour
            and _as_ist(bar.timestamp).minute == SESSION_OPEN.minute
        ),
        None,
    )


def classify_tier(
    rvol: float,
    config: OpeningVolumeConfig | None = None,
) -> LeaderTier:
    config = config or OpeningVolumeConfig()
    config.validate()
    if not isfinite(rvol) or rvol < 0:
        raise ValueError("rvol must be finite and non-negative")
    if rvol >= config.explosive_rvol:
        return LeaderTier.EXPLOSIVE
    if rvol >= config.strong_rvol:
        return LeaderTier.STRONG
    if rvol >= config.spurt_rvol:
        return LeaderTier.SPURT
    if rvol >= config.watch_rvol:
        return LeaderTier.WATCH
    return LeaderTier.WEAK


def _direction(bar: Bar) -> LeaderDirection:
    if bar.close > bar.open:
        return LeaderDirection.UP
    if bar.close < bar.open:
        return LeaderDirection.DOWN
    return LeaderDirection.NEUTRAL


def _candle_quality(
    bar: Bar,
    direction: LeaderDirection,
    config: OpeningVolumeConfig,
) -> tuple[CandleQuality, float, float]:
    candle_range = max(bar.high - bar.low, 0.0)
    if candle_range <= 0 or direction is LeaderDirection.NEUTRAL:
        return CandleQuality.WEAK, 0.0, 0.5
    body_fraction = abs(bar.close - bar.open) / candle_range
    close_location = (
        (bar.close - bar.low) / candle_range
        if direction is LeaderDirection.UP
        else (bar.high - bar.close) / candle_range
    )
    if (
        body_fraction >= config.strong_body_fraction
        and close_location >= config.strong_close_location
    ):
        quality = CandleQuality.STRONG
    elif (
        body_fraction >= config.moderate_body_fraction
        and close_location >= config.moderate_close_location
    ):
        quality = CandleQuality.MODERATE
    else:
        quality = CandleQuality.WEAK
    return quality, body_fraction, close_location


def _entry_phase(at: datetime) -> EntryPhase:
    value = _as_ist(at)
    if value.weekday() >= 5:
        return EntryPhase.CLOSED
    current = value.time()
    if current < time(9, 15) or current >= time(15, 30):
        return EntryPhase.CLOSED
    if current < time(9, 16):
        return EntryPhase.OPENING
    if current < time(9, 25):
        return EntryPhase.PLANNING
    if current < time(9, 40):
        return EntryPhase.PRIME
    if current < time(10, 30):
        return EntryPhase.MANAGE
    if current < time(11, 30):
        return EntryPhase.DECAY
    if current < time(13, 45):
        return EntryPhase.NO_NEW_ENTRY
    if current < time(15, 15):
        return EntryPhase.EXIT
    return EntryPhase.FLAT


def _average_turnover(
    sessions: Mapping[date, Sequence[Bar]],
    before: date,
    config: OpeningVolumeConfig,
) -> tuple[float | None, int]:
    totals: list[float] = []
    for session in sorted((d for d in sessions if d < before), reverse=True):
        rows = sessions[session]
        if len(rows) < config.min_turnover_bars_per_session:
            continue
        total = sum(
            ((bar.high + bar.low + bar.close) / 3.0) * max(bar.volume, 0.0)
            for bar in rows
        )
        if total > 0:
            totals.append(total)
        if len(totals) >= config.turnover_sessions:
            break
    if len(totals) < config.turnover_sessions:
        return None, len(totals)
    return mean(totals), len(totals)


def _liquidity(
    current_price: float,
    average_turnover_inr: float | None,
    turnover_session_count: int,
    config: OpeningVolumeConfig,
) -> tuple[LiquidityState, tuple[str, ...]]:
    reasons: list[str] = []
    if current_price < config.min_price_inr:
        reasons.append(f"price below INR {config.min_price_inr:g}")
    if average_turnover_inr is None:
        reasons.append(
            f"fewer than {config.turnover_sessions} complete prior turnover sessions "
            f"({turnover_session_count} available)"
        )
    elif average_turnover_inr < config.min_average_turnover_inr:
        reasons.append(
            f"average turnover below INR {config.min_average_turnover_inr:g}"
        )
    if current_price < config.min_price_inr or (
        average_turnover_inr is not None
        and average_turnover_inr < config.min_average_turnover_inr
    ):
        return LiquidityState.FAIL, tuple(reasons)
    if average_turnover_inr is None:
        return LiquidityState.UNKNOWN, tuple(reasons)
    return LiquidityState.PASS, ()


def _first_orb_break(
    rows: Sequence[Bar],
    opening: Bar,
    direction: LeaderDirection,
) -> tuple[LeaderDirection | None, datetime | None, float | None, bool]:
    cumulative = max(opening.volume, 0.0)
    opening_ts = _as_ist(opening.timestamp)
    for bar in rows:
        timestamp = _as_ist(bar.timestamp)
        if timestamp <= opening_ts:
            continue
        cumulative += max(bar.volume, 0.0)
        breaks_up = bar.high > opening.high
        breaks_down = bar.low < opening.low
        if not (breaks_up or breaks_down):
            continue
        if breaks_up and breaks_down:
            # Minute OHLC cannot tell which boundary traded first.  Inferring a
            # side from candle colour would fabricate ordering and can create a
            # false aligned COMBO, so keep the event explicitly ambiguous.
            side = None
        elif breaks_up:
            side = LeaderDirection.UP
        else:
            side = LeaderDirection.DOWN
        aligned = side is not None and side is direction
        return side, timestamp, cumulative, aligned
    return None, None, None, False


def evaluate_leader(
    symbol: str,
    bars: Sequence[Bar],
    *,
    as_of: datetime,
    config: OpeningVolumeConfig | None = None,
    average_turnover_inr: float | None = None,
) -> LeaderSignal:
    """Evaluate one symbol from causally available one-minute bars.

    ``bars`` must include today's 09:15 candle and prior sessions.  Only bars
    closed by ``as_of`` participate.  Baseline sessions are strictly earlier
    than today's session, preventing the evaluated candle from leaking into its
    own normal.  ``average_turnover_inr`` may be supplied by an authoritative
    daily-data source; otherwise it is reconstructed from complete minute days.
    """

    config = (config or OpeningVolumeConfig()).validate()
    normalized_symbol = symbol.strip().upper()
    if not normalized_symbol:
        raise ValueError("symbol is required")
    now = _as_ist(as_of)
    sessions = _session_rows(bars, as_of=now)
    current_date = now.date()
    current_rows = _completed_rows(sessions.get(current_date, []), now)
    opening = _opening_bar(current_rows)
    if opening is None:
        if now.time() < time(9, 16):
            raise ValueError("the 09:15 one-minute candle is not complete")
        raise ValueError("completed 09:15 one-minute candle is missing")

    prior_openings: list[Bar] = []
    for session in sorted((d for d in sessions if d < current_date), reverse=True):
        candidate = _opening_bar(sessions[session])
        if candidate is not None and candidate.volume > 0:
            prior_openings.append(candidate)
        if len(prior_openings) >= config.baseline_sessions:
            break
    if len(prior_openings) < config.baseline_sessions:
        raise ValueError(
            f"fewer than {config.baseline_sessions} valid prior 09:15 volume sessions "
            f"({len(prior_openings)} available)"
        )

    baseline = mean(bar.volume for bar in prior_openings)
    if baseline <= 0:
        raise ValueError("prior 09:15 volume baseline is zero")
    rvol = max(opening.volume, 0.0) / baseline
    tier = classify_tier(rvol, config)
    direction = _direction(opening)
    quality, body_fraction, close_location = _candle_quality(opening, direction, config)

    prior_sessions = sorted(d for d in sessions if d < current_date)
    previous_close = sessions[prior_sessions[-1]][-1].close if prior_sessions else None
    latest = current_rows[-1]
    day_change_pct = (
        (latest.close / previous_close - 1.0) * 100.0
        if previous_close and previous_close > 0
        else None
    )
    gap_pct = (
        (opening.open / previous_close - 1.0) * 100.0
        if previous_close and previous_close > 0
        else None
    )
    candle_range = max(opening.high - opening.low, 0.0)
    body_pct = abs(opening.close - opening.open) / opening.open * 100.0
    range_pct = candle_range / opening.open * 100.0

    computed_turnover, turnover_count = _average_turnover(
        sessions, current_date, config
    )
    if average_turnover_inr is not None:
        if not isfinite(average_turnover_inr) or average_turnover_inr < 0:
            raise ValueError("average_turnover_inr must be finite and non-negative")
        computed_turnover = average_turnover_inr
        turnover_count = config.turnover_sessions
    liquidity_state, liquidity_reasons = _liquidity(
        latest.close,
        computed_turnover,
        turnover_count,
        config,
    )

    orb_side, orb_time, orb_volume, orb_aligned = _first_orb_break(
        current_rows,
        opening,
        direction,
    )
    is_leader = tier in {
        LeaderTier.SPURT,
        LeaderTier.STRONG,
        LeaderTier.EXPLOSIVE,
    }
    passes_quality = (
        is_leader
        and direction is not LeaderDirection.NEUTRAL
        and liquidity_state is LiquidityState.PASS
        and quality is not CandleQuality.WEAK
    )
    # Observed source cards associate COMBO with an immediately aligned 09:16
    # ORB event, but the site's private predicate is not exposed.  This is the
    # conservative, explicit local approximation; a later ORB break remains
    # useful context without being retroactively labelled as the same event.
    orb_immediate = orb_time is not None and orb_time.replace(
        second=0, microsecond=0
    ) == _as_ist(opening.timestamp).replace(second=0, microsecond=0) + timedelta(
        minutes=1
    )
    combo = (
        is_leader
        and liquidity_state is LiquidityState.PASS
        and direction is not LeaderDirection.NEUTRAL
        and orb_aligned
        and orb_immediate
    )
    session_low = min(bar.low for bar in current_rows)
    session_high = max(bar.high for bar in current_rows)
    rise_from_low_pct = (latest.close / session_low - 1.0) * 100.0
    fall_from_high_pct = (session_high - latest.close) / session_high * 100.0

    return LeaderSignal(
        symbol=normalized_symbol,
        session_date=current_date,
        signal_time=_as_ist(opening.timestamp),
        observed_at=now,
        direction=direction,
        tier=tier,
        rvol=rvol,
        opening_volume=opening.volume,
        average_opening_volume=baseline,
        baseline_session_count=len(prior_openings),
        opening_open=opening.open,
        opening_high=opening.high,
        opening_low=opening.low,
        opening_close=opening.close,
        current_price=latest.close,
        previous_close=previous_close,
        day_change_pct=day_change_pct,
        gap_pct=gap_pct,
        body_pct=body_pct,
        range_pct=range_pct,
        body_fraction=body_fraction,
        close_location=close_location,
        candle_quality=quality,
        average_turnover_inr=computed_turnover,
        turnover_session_count=turnover_count,
        liquidity_state=liquidity_state,
        liquidity_reasons=liquidity_reasons,
        orb_break_side=orb_side,
        orb_break_time=orb_time,
        orb_cumulative_volume=orb_volume,
        orb_aligned=orb_aligned,
        orb_immediate=orb_immediate,
        combo=combo,
        rise_from_low_pct=rise_from_low_pct,
        fall_from_high_pct=fall_from_high_pct,
        is_leader=is_leader,
        passes_quality_filters=passes_quality,
        entry_phase=_entry_phase(now),
    )


_TIER_RANK = {
    LeaderTier.WEAK: 0,
    LeaderTier.WATCH: 1,
    LeaderTier.SPURT: 2,
    LeaderTier.STRONG: 3,
    LeaderTier.EXPLOSIVE: 4,
}
_QUALITY_RANK = {
    CandleQuality.WEAK: 0,
    CandleQuality.MODERATE: 1,
    CandleQuality.STRONG: 2,
}


def rank_leaders(signals: Iterable[LeaderSignal]) -> list[LeaderSignal]:
    """Rank deterministically without inventing the source site's private score."""

    return sorted(
        signals,
        key=lambda signal: (
            -_TIER_RANK[signal.tier],
            -int(signal.combo),
            -int(signal.passes_quality_filters),
            -_QUALITY_RANK[signal.candle_quality],
            -signal.rvol,
            signal.symbol,
        ),
    )


def scan_leaders(
    bars_by_symbol: Mapping[str, Sequence[Bar]],
    *,
    as_of: datetime,
    config: OpeningVolumeConfig | None = None,
    include_watch: bool = False,
    average_turnover_by_symbol: Mapping[str, float] | None = None,
) -> tuple[list[LeaderSignal], dict[str, str]]:
    """Evaluate a universe, returning ranked candidates and explicit failures."""

    config = (config or OpeningVolumeConfig()).validate()
    signals: list[LeaderSignal] = []
    failures: dict[str, str] = {}
    turnover = average_turnover_by_symbol or {}
    for raw_symbol, bars in bars_by_symbol.items():
        symbol = raw_symbol.strip().upper()
        try:
            signal = evaluate_leader(
                symbol,
                bars,
                as_of=as_of,
                config=config,
                average_turnover_inr=turnover.get(symbol),
            )
        except (TypeError, ValueError) as exc:
            failures[symbol or raw_symbol] = str(exc)
            continue
        if signal.is_leader or (include_watch and signal.tier is LeaderTier.WATCH):
            signals.append(signal)
    return rank_leaders(signals), failures


STRATEGY_CONTRACT = {
    "id": "opening_volume_leaders",
    "version": "1.1.0",
    "execution": "advisory_only",
    "documented_rules": [
        "completed 09:15 one-minute candle",
        "same-symbol 09:15 volume mean over 10 prior sessions",
        "WATCH >=2x; SPURT >=3x; STRONG >=5x; EXPLOSIVE >=10x",
        "direction from the 09:15 candle colour",
        "ORB from the 09:15 high/low with first later breach time",
        "Layer-1 price >= INR 100 and 20-session average turnover >= INR 2 crore",
    ],
    "local_transparent_rules": [
        "candle quality uses configurable body-fraction and close-location thresholds",
        "COMBO approximates a leader with Layer-1 pass and an aligned first ORB break at 09:16",
        "ranking uses tier, combo, quality, RVOL, then symbol",
    ],
    "unknown_and_omitted": [
        "proprietary numeric strength-score weights",
        "proprietary late-entry numeric thresholds",
        "private COMBO predicate beyond observable card behaviour",
        "experimental Momentum Lab and five-minute-hold model",
        "seven-factor conviction score and sector-tailwind model",
        "option selection, premium, and lot-cost presentation",
    ],
}
