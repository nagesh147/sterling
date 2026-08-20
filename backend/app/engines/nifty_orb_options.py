"""ORB + VWAP directional options engine.

Signals are generated from completed underlying bars. Options are the execution
vehicle only: LONG -> BUY CE and SHORT -> BUY PE.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime, time, timedelta
from math import isfinite
from statistics import mean
from typing import Iterable, Literal, Sequence
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")
Direction = Literal["LONG", "SHORT", "NONE"]
Regime = Literal["EXPANSION", "TREND", "RANGE", "UNKNOWN"]

#: Canonical expiry-preference vocabulary shared by the engine and every provider.
EXPIRY_SELECTIONS = frozenset({"nearest", "weekly", "monthly", "any"})
MONEYNESS = frozenset({"ATM", "ITM", "OTM"})


@dataclass(frozen=True)
class Bar:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0


@dataclass(frozen=True)
class StrategyConfig:
    enabled: bool = False
    underlying: str = "NIFTY"
    scan_indices: tuple[str, ...] = ("NIFTY",)
    scan_stocks: tuple[str, ...] = ()
    scan_all_stocks: bool = False
    scan_stock_contracts: bool = True
    interval_minutes: int = 5
    opening_range_minutes: int = 15
    entry_start: str = "09:30"
    entry_end: str = "12:00"
    min_breakout_atr: float = 0.15
    volume_multiplier: float = 1.15
    vwap_slope_lookback: int = 3
    trend_lookback: int = 5
    atr_period: int = 14
    stop_buffer_atr: float = 0.10
    target_r: float = 2.0
    option_moneyness: str = "ATM"
    option_steps_itm: int = 1
    max_risk_inr: float = 3000.0
    max_trades_per_day: int = 2
    avoid_expiry_day: bool = False
    expiry_selection: str = "nearest"
    expiry_dte_min: int = 0
    expiry_dte_max: int = 7
    execution_broker: str = "kite"
    data_source: str = "kite"
    max_spread_pct: float = 1.5
    min_option_volume: float = 1000.0
    min_open_interest: float = 10000.0
    max_quote_staleness_s: int = 15
    risk_free_rate: float = 0.065
    truedata_use_ticks: bool = True
    truedata_use_oi: bool = True
    truedata_use_bid_ask: bool = True
    truedata_use_quote_freshness: bool = True

    def validate(self) -> "StrategyConfig":
        """Reject configuration that would silently bypass a strategy filter.

        An invalid value is a configuration error, never an implicit bypass: a
        zero ``volume_multiplier`` used to disable volume confirmation *and*
        divide by zero in the confidence term. Disabling a liquidity floor is
        expressed by setting that floor to zero, or by the explicit
        ``truedata_use_*`` switches -- not by an out-of-range value.
        """
        def positive(name: str, value: float) -> None:
            if not (isfinite(float(value)) and float(value) > 0):
                raise ValueError(f"{name} must be greater than zero")

        def non_negative(name: str, value: float) -> None:
            if not (isfinite(float(value)) and float(value) >= 0):
                raise ValueError(f"{name} must be zero or greater")

        positive("interval_minutes", self.interval_minutes)
        positive("opening_range_minutes", self.opening_range_minutes)
        positive("atr_period", self.atr_period)
        positive("vwap_slope_lookback", self.vwap_slope_lookback)
        positive("trend_lookback", self.trend_lookback)
        positive("volume_multiplier", self.volume_multiplier)
        positive("max_risk_inr", self.max_risk_inr)
        positive("max_trades_per_day", self.max_trades_per_day)
        positive("max_spread_pct", self.max_spread_pct)
        positive("option_steps_itm", self.option_steps_itm)
        non_negative("min_breakout_atr", self.min_breakout_atr)
        non_negative("stop_buffer_atr", self.stop_buffer_atr)
        non_negative("min_option_volume", self.min_option_volume)
        non_negative("min_open_interest", self.min_open_interest)
        non_negative("max_quote_staleness_s", self.max_quote_staleness_s)
        non_negative("risk_free_rate", self.risk_free_rate)
        positive("target_r", self.target_r)

        try:
            start, end = _parse_time(self.entry_start), _parse_time(self.entry_end)
        except (AttributeError, TypeError, ValueError) as exc:
            raise ValueError("entry_start and entry_end must be HH:MM") from exc
        if start >= end:
            raise ValueError("entry_start must be earlier than entry_end")

        if self.expiry_dte_min < 0:
            raise ValueError("expiry_dte_min must be zero or greater")
        if self.expiry_dte_max < self.expiry_dte_min:
            raise ValueError("expiry_dte_max must be greater than or equal to expiry_dte_min")
        if self.expiry_selection.strip().lower() not in EXPIRY_SELECTIONS:
            raise ValueError(f"expiry_selection must be one of {sorted(EXPIRY_SELECTIONS)}")
        if self.option_moneyness.strip().upper() not in MONEYNESS:
            raise ValueError(f"option_moneyness must be one of {sorted(MONEYNESS)}")
        if self.avoid_expiry_day and self.expiry_dte_min == 0 and self.expiry_dte_max == 0:
            raise ValueError("avoid_expiry_day leaves no eligible expiry when the DTE range is 0-0")
        if self.data_source == "truedata" and self.truedata_use_quote_freshness and not self.truedata_use_ticks:
            # TrueData freshness is measured from the tick stamp, so switching
            # ticks off silently disables the freshness gate rather than keeping
            # it. The provider is allowed to return early when ticks are off, and
            # this invariant is what makes that safe.
            raise ValueError("truedata_use_quote_freshness requires truedata_use_ticks")
        return self


@dataclass(frozen=True)
class Signal:
    direction: Direction
    regime: Regime
    timestamp: datetime | None
    or_high: float
    or_low: float
    vwap: float
    atr: float
    breakout_distance: float
    volume_ratio: float
    confidence: float
    reason: str

    def to_dict(self) -> dict:
        d = asdict(self)
        d["timestamp"] = self.timestamp.isoformat() if self.timestamp else None
        return d


@dataclass(frozen=True)
class OptionContract:
    symbol: str
    strike: float
    expiry: str
    option_type: Literal["CE", "PE"]
    ltp: float = 0.0
    bid: float = 0.0
    ask: float = 0.0
    lot_size: int = 1
    delta: float | None = None
    volume: float = 0.0
    open_interest: float = 0.0
    quote_timestamp: datetime | None = None

    @property
    def spread_pct(self) -> float:
        mid = (self.bid + self.ask) / 2.0
        if mid <= 0 or self.ask < self.bid:
            return float("inf")
        return (self.ask - self.bid) / mid * 100.0

    @property
    def quote_age_seconds(self) -> float | None:
        if self.quote_timestamp is None:
            return None
        ts = self.quote_timestamp
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=IST)
        return max(0.0, (datetime.now(IST) - ts.astimezone(IST)).total_seconds())

    @property
    def expiry_date(self) -> date | None:
        try:
            return datetime.strptime(self.expiry[:10], "%Y-%m-%d").date()
        except (ValueError, TypeError, AttributeError):
            return None

    def dte_on(self, today: date) -> int | None:
        """Days to expiry measured against an explicit reference date.

        Callers that must be reproducible (tests, replay, walk-forward) pass the
        session date instead of inheriting the wall clock.
        """
        expiry = self.expiry_date
        return None if expiry is None else max(0, (expiry - today).days)

    @property
    def dte(self) -> int | None:
        return self.dte_on(datetime.now(IST).date())


@dataclass(frozen=True)
class TradePlan:
    direction: Direction
    option_type: Literal["CE", "PE"]
    contract: OptionContract
    underlying_entry: float
    underlying_stop: float
    initial_risk_points: float
    target_points: float
    entry_premium: float
    stop_premium: float
    target_premium: float
    premium_risk_per_share: float
    quantity: int
    risk_inr: float
    reason: str
    max_loss_inr: float = 0.0
    """Full premium outlay: what this position loses if the option expires worthless."""
    delta_is_estimated: bool = False
    """True whenever the delta did not come from the broker."""
    delta_source: str = "assumed"
    """Where the delta came from: ``broker``, ``implied`` or ``assumed``.

    Kite publishes no Greeks, so ``broker`` is rare there. ``implied`` means the
    delta was solved from the traded premium via Black-Scholes -- derived from an
    observable, not guessed. ``assumed`` means 0.50 was used because the premium
    could not support a solution, and everything in the premium domain
    (``stop_premium``, ``target_premium``, ``risk_inr``) is only as good as that.
    ``stop_premium`` is the number armed at the broker, so the distinction matters.
    """
    delta: float | None = None
    """The delta actually used to derive every premium-domain number here."""
    implied_volatility: float | None = None
    gamma: float | None = None
    theta_per_day: float | None = None
    vega_per_point: float | None = None

    def to_dict(self) -> dict:
        d = asdict(self)
        d["contract"] = asdict(self.contract)
        d["quote_spread_pct"] = self.contract.spread_pct
        return d


def _as_ist(ts: datetime) -> datetime:
    if ts.tzinfo is None:
        return ts.replace(tzinfo=IST)
    return ts.astimezone(IST)


def _session_date(b: Bar) -> date:
    return _as_ist(b.timestamp).date()


def _typical_price(b: Bar) -> float:
    return (b.high + b.low + b.close) / 3.0


def vwap(bars: Sequence[Bar]) -> float:
    pv = sum(_typical_price(b) * max(b.volume, 0.0) for b in bars)
    vol = sum(max(b.volume, 0.0) for b in bars)
    return pv / vol if vol > 0 else (bars[-1].close if bars else 0.0)


def atr(bars: Sequence[Bar], period: int = 14) -> float:
    """Average true range, with the overnight gap excluded.

    True range normally spans the previous close. Across a session boundary that
    previous close is yesterday's, so an overnight gap was being measured as an
    intraday range: a 500-point gap turned a real ATR of 8 into 43.5 and lifted
    the 0.15-ATR breakout threshold from 1.2 to 6.5 points. The first bar of a
    session therefore contributes only its own high-low.

    The lookback still spans sessions, which is deliberate -- an intraday
    estimator seeded from three bars is worse than one seeded from yesterday's
    ranges. Only the gap artifact is removed.
    """
    if len(bars) < 2:
        return 0.0
    trs = []
    prev = bars[0].close
    prev_session = _session_date(bars[0])
    for b in bars[1:]:
        session = _session_date(b)
        if session != prev_session:
            trs.append(b.high - b.low)
        else:
            trs.append(max(b.high - b.low, abs(b.high - prev), abs(b.low - prev)))
        prev = b.close
        prev_session = session
    return mean(trs[-max(1, period):]) if trs else 0.0


def _parse_time(value: str) -> time:
    h, m = value.split(":", 1)
    return time(int(h), int(m))


def _volume_ratio(bars: Sequence[Bar], lookback: int = 20) -> float:
    """Current bar's volume against the baseline *of its own session*.

    The baseline used to be the previous ``lookback`` bars whatever session they
    belonged to, so before ~10:55 every day the current bar was measured against
    yesterday's tail. After a heavy prior session that put the ratio at 0.15
    against a 1.15 threshold -- the volume gate could not pass during most of the
    entry window. With no same-session baseline the ratio is a neutral 1.0, which
    fails the default threshold and produces no trade.
    """
    if not bars:
        return 0.0
    current = max(bars[-1].volume, 0.0)
    session = _session_date(bars[-1])
    prior = [max(b.volume, 0.0) for b in bars[:-1] if _session_date(b) == session][-lookback:]
    baseline = mean(prior) if prior else 0.0
    return current / baseline if baseline > 0 else 1.0


def _regime(bars: Sequence[Bar], cfg: StrategyConfig, current_vwap: float, current_atr: float) -> Regime:
    if len(bars) < max(cfg.trend_lookback + 1, 5) or current_atr <= 0:
        return "UNKNOWN"
    recent = bars[-cfg.trend_lookback:]
    net = recent[-1].close - recent[0].close
    efficiency = abs(net) / max(sum(abs(b.close - a.close) for a, b in zip(recent, recent[1:])), 1e-9)
    last_range = recent[-1].high - recent[-1].low
    if last_range >= 1.25 * current_atr and efficiency >= 0.45:
        return "EXPANSION"
    if efficiency >= 0.35 and abs(recent[-1].close - current_vwap) >= 0.25 * current_atr:
        return "TREND"
    return "RANGE"


def opening_range(bars: Sequence[Bar], minutes: int = 15) -> tuple[float, float]:
    """Build the OR from the 09:15 IST session, independent of source timezone."""
    if not bars:
        raise ValueError("No bars supplied")
    session = max(_as_ist(b.timestamp).date() for b in bars)
    start = datetime.combine(session, time(9, 15), tzinfo=IST)
    end = start + timedelta(minutes=minutes)
    opening = [b for b in bars if start <= _as_ist(b.timestamp) < end]
    if not opening:
        raise ValueError("Opening range bars are missing")
    return max(b.high for b in opening), min(b.low for b in opening)


def _vwap_slope(session_bars: Sequence[Bar], lookback: int) -> float:
    return vwap(session_bars) - vwap(session_bars[:-lookback]) if len(session_bars) > lookback else 0.0


def generate_signal(
    bars: Sequence[Bar],
    cfg: StrategyConfig = StrategyConfig(),
    *,
    as_of: datetime | None = None,
) -> Signal:
    """Generate a signal from completed bars only.

    ``as_of`` is supplied by realtime callers. Historical callers may omit it,
    because their input is already closed data. A realtime caller must pass the
    current clock so a still-forming candle cannot become a signal.
    """
    cfg.validate()
    if not bars:
        raise ValueError("No bars supplied")

    normalized = sorted(bars, key=lambda b: _as_ist(b.timestamp))
    if as_of is not None:
        now = _as_ist(as_of)
        interval = max(1, cfg.interval_minutes)
        completed = []
        for b in normalized:
            ts = _as_ist(b.timestamp).replace(second=0, microsecond=0)
            close_time = ts + timedelta(minutes=interval)
            if close_time <= now:
                completed.append(b)
        normalized = completed
    if not normalized:
        raise ValueError("No completed bars available")

    current = normalized[-1]
    or_high, or_low = opening_range(normalized, cfg.opening_range_minutes)
    session_bars = [
        b for b in normalized
        if _as_ist(b.timestamp).date() == _as_ist(current.timestamp).date()
        and _as_ist(b.timestamp).time() >= time(9, 15)
    ]
    current_vwap = vwap(session_bars)
    slope = _vwap_slope(session_bars, cfg.vwap_slope_lookback)
    current_atr = atr(normalized, cfg.atr_period)
    vol_ratio = _volume_ratio(session_bars)
    # Regime describes *today's* character. Measuring it across the session
    # boundary let yesterday's path decide whether today was trending.
    regime = _regime(session_bars, cfg, current_vwap, current_atr)
    t = _as_ist(current.timestamp).time()

    if not (_parse_time(cfg.entry_start) <= t <= _parse_time(cfg.entry_end)):
        return Signal("NONE", regime, current.timestamp, or_high, or_low, current_vwap, current_atr, 0.0, vol_ratio, 0.0, "outside entry window")
    if current_atr <= 0:
        return Signal("NONE", regime, current.timestamp, or_high, or_low, current_vwap, current_atr, 0.0, vol_ratio, 0.0, "ATR unavailable")

    long_break = current.close - or_high
    short_break = or_low - current.close
    threshold = cfg.min_breakout_atr * current_atr
    breakout_distance = max(long_break, short_break, 0.0)
    volume_ok = vol_ratio >= cfg.volume_multiplier

    def none(reason: str) -> Signal:
        return Signal("NONE", regime, current.timestamp, or_high, or_low, current_vwap, current_atr, breakout_distance, vol_ratio, 0.0, reason)

    # Gate order is the diagnostic order: the first unmet prerequisite is the
    # reported reason, so a rejected bar says which filter stopped it. It runs
    # from the strategy's defining condition outwards -- structure, magnitude,
    # location, direction, participation, context -- so the reason names the
    # most specific thing that was missing.
    if long_break <= 0 and short_break <= 0:
        return none("no opening-range breakout")
    side = "LONG" if long_break >= short_break else "SHORT"
    distance = long_break if side == "LONG" else short_break
    if distance < threshold:
        return none("breakout below ATR threshold")
    if side == "LONG" and current.close <= current_vwap:
        return none("close is not above VWAP")
    if side == "SHORT" and current.close >= current_vwap:
        return none("close is not below VWAP")
    if side == "LONG" and slope <= 0:
        return none("VWAP slope is not positive")
    if side == "SHORT" and slope >= 0:
        return none("VWAP slope is not negative")
    if not volume_ok:
        return none("volume below confirmation threshold")
    if regime not in ("EXPANSION", "TREND"):
        return none(f"regime is {regime}")

    confidence = _confidence(distance, current_atr, vol_ratio, cfg)
    if side == "LONG":
        return Signal("LONG", regime, current.timestamp, or_high, or_low, current_vwap, current_atr, long_break, vol_ratio, confidence, "ORB high break + VWAP + positive VWAP slope + momentum + volume")
    return Signal("SHORT", regime, current.timestamp, or_high, or_low, current_vwap, current_atr, short_break, vol_ratio, confidence, "ORB low break + VWAP + negative VWAP slope + momentum + volume")


def is_monthly_expiry(expiry: date, *, monthly_expiries: frozenset[date] | None = None) -> bool:
    """Classify an expiry as monthly under an explicit calendar rule.

    When the caller supplies the venue's real ``monthly_expiries`` set that set
    is authoritative. Otherwise the NSE convention applies: the monthly contract
    is the last occurrence of that expiry's own weekday inside its calendar
    month. The rule is self-contained and depends on no wall clock, so replay
    and walk-forward classify an expiry the same way live does.
    """
    if monthly_expiries is not None:
        return expiry in monthly_expiries
    return (expiry + timedelta(days=7)).month != expiry.month


def _confidence(distance: float, current_atr: float, vol_ratio: float, cfg: StrategyConfig) -> float:
    """Blend breakout strength and volume expansion into a bounded score.

    Both terms are ratios against a configured reference, so both denominators
    are guaranteed positive by :meth:`StrategyConfig.validate`.
    """
    breakout_term = 0.15 * min(distance / current_atr, 2.0)
    volume_term = 0.10 * min(vol_ratio / cfg.volume_multiplier, 2.0)
    return min(0.99, 0.50 + breakout_term + volume_term)


def _expiry_allowed(c: OptionContract, cfg: StrategyConfig, today: date) -> bool:
    dte = c.dte_on(today)
    if dte is None or not cfg.expiry_dte_min <= dte <= cfg.expiry_dte_max:
        return False
    if cfg.avoid_expiry_day and dte == 0:
        return False
    return True


def _preferred_expiries(
    candidates: Sequence[OptionContract],
    cfg: StrategyConfig,
    monthly_expiries: frozenset[date] | None,
) -> list[OptionContract]:
    """Narrow eligible contracts to the configured expiry preference.

    ``nearest`` = minimum eligible DTE. ``weekly`` = nearest eligible non-monthly
    expiry. ``monthly`` = nearest eligible monthly expiry. ``any`` = no
    preference beyond eligibility. A preference that matches nothing is an
    error, never a silent fallback to a different expiry bucket.
    """
    selection = cfg.expiry_selection.strip().lower()
    if selection == "any":
        return list(candidates)

    dated = [c for c in candidates if c.expiry_date is not None]
    if not dated:
        raise ValueError("No eligible contract carries a parseable expiry")

    if selection == "nearest":
        best = min(c.expiry_date for c in dated)
    else:
        want_monthly = selection == "monthly"
        matching = [
            c.expiry_date for c in dated
            if is_monthly_expiry(c.expiry_date, monthly_expiries=monthly_expiries) is want_monthly
        ]
        if not matching:
            raise ValueError(f"No eligible {selection} expiry is available in the supplied chain")
        best = min(matching)
    return [c for c in dated if c.expiry_date == best]


def select_option(
    spot: float,
    direction: Direction,
    contracts: Sequence[OptionContract],
    cfg: StrategyConfig,
    *,
    today: date | None = None,
    monthly_expiries: frozenset[date] | None = None,
) -> OptionContract:
    """Pick the single executable contract for a directional signal.

    ``today`` anchors every DTE decision. Realtime callers may omit it and
    inherit the IST session date; replay and tests pass it so selection is
    reproducible.
    """
    cfg.validate()
    if direction not in ("LONG", "SHORT"):
        raise ValueError("Cannot select an option without a directional signal")
    today = today or datetime.now(IST).date()
    typ = "CE" if direction == "LONG" else "PE"
    candidates = [
        c for c in contracts
        if c.option_type == typ and c.lot_size > 0 and c.ltp > 0
        and (not cfg.truedata_use_bid_ask or (c.bid > 0 and c.ask >= c.bid and c.spread_pct <= cfg.max_spread_pct))
        and (not cfg.truedata_use_oi or c.open_interest >= cfg.min_open_interest)
        and c.volume >= cfg.min_option_volume
        and _expiry_allowed(c, cfg, today)
        and (not cfg.truedata_use_quote_freshness or c.quote_age_seconds is None or c.quote_age_seconds <= cfg.max_quote_staleness_s)
    ]
    if not candidates:
        raise ValueError(f"No liquid {typ} contracts satisfy expiry and liquidity settings")

    candidates = _preferred_expiries(candidates, cfg, monthly_expiries)
    strikes = sorted({c.strike for c in candidates})
    atm = min(strikes, key=lambda x: abs(x - spot))
    steps = min((b - a for a, b in zip(strikes, strikes[1:]) if b > a), default=50.0)
    moneyness = cfg.option_moneyness.strip().upper()
    if moneyness == "ATM":
        target = atm
    elif moneyness == "ITM":
        target = atm - cfg.option_steps_itm * steps if direction == "LONG" else atm + cfg.option_steps_itm * steps
    else:
        target = atm + cfg.option_steps_itm * steps if direction == "LONG" else atm - cfg.option_steps_itm * steps
    chosen = min(candidates, key=lambda c: (abs(c.strike - target), c.dte_on(today) or 999, -c.volume, -c.open_interest, c.spread_pct))
    # Moneyness is a risk choice, not a hint. Asking for ITM x3 and silently
    # receiving the ATM strike because the ladder does not reach that far changes
    # the position's delta, cost and payoff. One strike step of tolerance absorbs
    # an irregular ladder; anything beyond it is a refusal.
    if abs(chosen.strike - target) > steps:
        raise ValueError(
            f"No liquid {typ} contract at {moneyness}"
            f"{'' if moneyness == 'ATM' else f' x{cfg.option_steps_itm}'} "
            f"(wanted strike near {target:g}, nearest eligible is {chosen.strike:g})"
        )
    return chosen


def _resolve_delta(
    option: OptionContract, cfg: StrategyConfig, *, spot: float, now: datetime | None
) -> tuple[float, str, object | None]:
    """Delta from the broker, else implied from the premium, else 0.50.

    The premium is an observable, so solving it for volatility and taking the
    resulting delta is a measurement rather than a guess. Only when that solve
    fails -- a quote below intrinsic, a missing expiry, an expired contract -- do
    we fall back to 0.50, and the caller is told which happened.
    """
    if option.delta is not None:
        return abs(option.delta), "broker", None

    expiry = option.expiry_date
    mark = option.ltp if option.ltp > 0 else (option.bid + option.ask) / 2.0
    if expiry is not None and mark > 0 and spot > 0 and option.strike > 0:
        from app.engines.nifty_orb_greeks import implied_greeks

        reference = _as_ist(now) if now is not None else datetime.now(IST)
        greeks = implied_greeks(
            mark, spot, option.strike, expiry, option.option_type,
            now=reference, rate=cfg.risk_free_rate,
        )
        if greeks is not None and 0.0 < abs(greeks.delta) <= 1.0:
            return abs(greeks.delta), "implied", greeks
    return 0.50, "assumed", None


def build_trade_plan(
    signal: Signal,
    option: OptionContract,
    cfg: StrategyConfig,
    *,
    spot: float,
    now: datetime | None = None,
) -> TradePlan:
    cfg.validate()
    if signal.direction not in ("LONG", "SHORT"):
        raise ValueError("No trade plan for a neutral signal")
    expected = "CE" if signal.direction == "LONG" else "PE"
    if option.option_type != expected:
        raise ValueError("Option direction does not match underlying signal")
    if option.ask <= 0 or option.ltp <= 0 or option.lot_size <= 0:
        raise ValueError("Option quote is not executable")

    risk_points = max(signal.atr * cfg.stop_buffer_atr, abs(signal.breakout_distance) * 0.50, 1.0)
    stop = spot - risk_points if signal.direction == "LONG" else spot + risk_points
    target = spot + cfg.target_r * risk_points if signal.direction == "LONG" else spot - cfg.target_r * risk_points
    entry_premium = option.ask
    delta, delta_source, greeks = _resolve_delta(option, cfg, spot=spot, now=now or signal.timestamp)
    # A bought option cannot lose more than it cost, so the modelled stop loss is
    # capped at the premium. Without the cap, a stop wider than the premium
    # produced a 0.05 stop -- "hold to zero" dressed up as a stop.
    premium_risk_per_share = min(max(risk_points * delta, 0.01), entry_premium)
    stop_premium = max(0.05, entry_premium - premium_risk_per_share)
    target_premium = entry_premium + abs(target - spot) * delta

    # Size against the FULL premium outlay, not the modelled stop distance. This
    # is the same ceiling the live executor applies (`_conservative_quantity`),
    # so the plan an operator reads is the plan that will execute. Sizing by the
    # stop let a modest breakout produce 2400 units of an 18-rupee option --
    # 43,200 rupees of premium -- while reporting "risk 3,000" and while the
    # executor would in fact buy 150.
    lots = int(cfg.max_risk_inr // (entry_premium * option.lot_size))
    quantity = max(0, lots * option.lot_size)
    risk = quantity * premium_risk_per_share
    max_loss = quantity * entry_premium
    return TradePlan(signal.direction, option.option_type, option, spot, stop, risk_points, abs(target - spot), entry_premium, stop_premium, target_premium, premium_risk_per_share, quantity, risk, signal.reason, max_loss_inr=max_loss, delta_is_estimated=delta_source != "broker", delta_source=delta_source, delta=delta,
                     implied_volatility=getattr(greeks, "implied_volatility", None),
                     gamma=getattr(greeks, "gamma", None),
                     theta_per_day=getattr(greeks, "theta", None),
                     vega_per_point=getattr(greeks, "vega", None))


def summarize_pnl(pnls: Iterable[float]) -> dict:
    values = [float(x) for x in pnls if isfinite(float(x))]
    wins = [x for x in values if x > 0]
    losses = [x for x in values if x < 0]
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    equity = peak = max_dd = 0.0
    for x in values:
        equity += x
        peak = max(peak, equity)
        max_dd = max(max_dd, peak - equity)
    return {
        "trades": len(values),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": len(wins) / len(values) if values else 0.0,
        "gross_profit": gross_profit,
        "gross_loss": gross_loss,
        "profit_factor": gross_profit / gross_loss if gross_loss else (float("inf") if gross_profit else 0.0),
        "expectancy": mean(values) if values else 0.0,
        "average_win": mean(wins) if wins else 0.0,
        "average_loss": mean(losses) if losses else 0.0,
        "max_drawdown": max_dd,
        "net_pnl": sum(values),
    }
