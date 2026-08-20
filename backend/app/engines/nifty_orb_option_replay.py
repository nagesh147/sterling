"""Historical option-premium replay for the NIFTY ORB strategy.

This module consumes normalized option bars and never substitutes underlying
points for option P&L. It models the things that decide whether a backtested
option edge survives contact with a broker:

* **Execution timing.** A signal is known only once its bar has closed, so the
  fill lands on a later bar. There is no same-bar fill.
* **Spread.** Buying pays the offer and selling receives the bid; half the
  quoted spread is charged on each side.
* **Liquidity admission.** A contract the live gates would refuse -- wide
  spread, thin volume, thin open interest -- is refused here too.
* **Partial fills.** Size is capped at a share of the bar's traded volume and
  stays lot-aligned.
* **Expiry.** A position is squared off on its expiry date rather than carried
  to the end of the data.
* **Charges.** The statutory Indian option stack (STT, exchange, SEBI, GST,
  stamp) is applied on turnover, not as a flat fee.

Every default is the pessimistic one. An optimistic result has to be asked for
explicitly, which is the only way a replay number is worth acting on.
"""
from __future__ import annotations
from dataclasses import asdict, dataclass
from datetime import date, datetime
from typing import Literal, Sequence

from app.engines.nifty_orb_validation import TradingCosts

Side = Literal["LONG", "SHORT"]
ExitReason = Literal["stop", "target", "expiry", "end_of_data"]


@dataclass(frozen=True)
class OptionBar:
    timestamp: datetime
    symbol: str
    option_type: Literal["CE", "PE"]
    strike: float
    expiry: str
    open: float
    high: float
    low: float
    close: float
    bid: float = 0.0
    ask: float = 0.0
    volume: float = 0.0
    open_interest: float = 0.0
    lot_size: int = 1

    @property
    def half_spread(self) -> float:
        """Half the quoted spread, or zero when the bar carries no two-sided quote."""
        return (self.ask - self.bid) / 2.0 if self.bid > 0 and self.ask >= self.bid else 0.0

    @property
    def spread_pct(self) -> float:
        mid = (self.bid + self.ask) / 2.0
        if mid <= 0 or self.ask < self.bid:
            return float("inf")
        return (self.ask - self.bid) / mid * 100.0

    @property
    def expiry_date(self) -> date | None:
        try:
            return date.fromisoformat(str(self.expiry)[:10])
        except (TypeError, ValueError):
            return None


@dataclass(frozen=True)
class ReplayCostConfig:
    """Costs charged outside the fill price.

    ``slippage_points`` is applied to every fill, so ``statutory`` must not also
    carry a per-share slippage term or the same cost is charged twice.
    """
    slippage_points: float = 0.0
    brokerage_per_order: float = 0.0
    charges_per_order: float = 0.0
    statutory: TradingCosts | None = None

    def __post_init__(self) -> None:
        if self.statutory is not None and self.statutory.slippage_per_share:
            raise ValueError("statutory.slippage_per_share double-counts ReplayCostConfig.slippage_points")

    def round_trip(self, buy_value: float, sell_value: float, quantity: int) -> float:
        """Total non-slippage round-trip cost in INR."""
        if self.statutory is not None:
            return self.statutory.round_trip(buy_value, sell_value, quantity) + 2 * self.charges_per_order
        return 2 * (self.brokerage_per_order + self.charges_per_order)


@dataclass(frozen=True)
class ReplayAdmission:
    """Entry-side gates mirroring live option admission.

    Defaults admit everything so an explicit choice is visible in the caller;
    ``from_strategy_config`` derives the production values.
    """
    max_spread_pct: float = float("inf")
    min_volume: float = 0.0
    min_open_interest: float = 0.0
    max_volume_participation: float = 1.0

    @classmethod
    def from_strategy_config(cls, cfg, *, max_volume_participation: float = 0.05) -> "ReplayAdmission":
        return cls(
            max_spread_pct=cfg.max_spread_pct,
            min_volume=cfg.min_option_volume,
            min_open_interest=cfg.min_open_interest,
            max_volume_participation=max_volume_participation,
        )

    def rejection(self, bar: OptionBar) -> str | None:
        if bar.spread_pct > self.max_spread_pct:
            return "spread above admission ceiling"
        if bar.volume < self.min_volume:
            return "volume below admission floor"
        if bar.open_interest < self.min_open_interest:
            return "open interest below admission floor"
        return None


@dataclass(frozen=True)
class ReplayTrade:
    symbol: str
    option_type: str
    strike: float
    expiry: str
    entry_time: datetime
    exit_time: datetime
    entry_price: float
    exit_price: float
    quantity: int
    gross_pnl: float
    costs: float
    net_pnl: float
    r_multiple: float
    exit_reason: str
    requested_quantity: int = 0
    max_adverse_excursion: float = 0.0
    max_favourable_excursion: float = 0.0

    @property
    def partially_filled(self) -> bool:
        return 0 < self.quantity < self.requested_quantity

    def to_dict(self) -> dict:
        d = asdict(self)
        d["entry_time"] = self.entry_time.isoformat()
        d["exit_time"] = self.exit_time.isoformat()
        d["partially_filled"] = self.partially_filled
        return d


@dataclass(frozen=True)
class ReplayRejection:
    """Why a signal never became a trade. Rejections are data, not silence."""
    signal_index: int
    reason: str


def executable_entry(bar: OptionBar, costs: ReplayCostConfig) -> float:
    """Buy fill: the bar's open, plus half the spread, plus slippage.

    A next-bar fill happens at the open, so the open is the reference price. The
    bar's bid/ask is a close-of-bar snapshot and is used only for its width.
    """
    base = bar.open if bar.open > 0 else bar.close
    return base + bar.half_spread + max(costs.slippage_points, 0.0)


def executable_exit(price: float, bar: OptionBar, costs: ReplayCostConfig) -> float:
    """Sell fill at ``price``, less half the spread and slippage. Never negative."""
    return max(0.0, price - bar.half_spread - max(costs.slippage_points, 0.0))


def _exit_scan(
    bars: Sequence[OptionBar],
    fill_index: int,
    stop: float,
    target: float,
) -> tuple[int, float, ExitReason]:
    """Find the exit bar, its reference price and the reason.

    Within a single bar the adverse stop is assumed to trigger first: intrabar
    sequencing is unknowable from OHLC, so the pessimistic branch is taken.
    """
    entry_expiry = bars[fill_index].expiry_date
    for i in range(fill_index, len(bars)):
        bar = bars[i]
        if bar.low <= stop:
            return i, stop, "stop"
        if bar.high >= target:
            return i, target, "target"
        if entry_expiry is not None and bar.timestamp.date() >= entry_expiry:
            return i, bar.close, "expiry"
    last = len(bars) - 1
    return last, bars[last].close, "end_of_data"


def _fillable_quantity(bar: OptionBar, requested: int, admission: ReplayAdmission) -> int:
    """Lot-aligned quantity the bar's traded volume can absorb."""
    lot = max(1, bar.lot_size)
    if requested <= 0:
        return 0
    if admission.max_volume_participation >= 1.0 and bar.volume <= 0:
        return requested                        # participation not being modelled
    capacity = int(bar.volume * admission.max_volume_participation)
    return min(requested, max(0, capacity // lot) * lot)


def replay_trade(
    bars: Sequence[OptionBar],
    signal_index: int,
    risk_points: float,
    target_r: float,
    costs: ReplayCostConfig = ReplayCostConfig(),
    *,
    lots: int = 1,
    admission: ReplayAdmission | None = None,
    entry_delay_bars: int = 1,
) -> ReplayTrade | None:
    """Replay one option-buy trade against real option bars.

    ``signal_index`` is the bar whose close produced the signal. The fill lands
    ``entry_delay_bars`` later, so an entry can never be priced off information
    the strategy did not have. Returns ``None`` when the signal could not be
    traded; use :func:`replay_signal` to learn why.
    """
    outcome = replay_signal(
        bars, signal_index, risk_points, target_r, costs,
        lots=lots, admission=admission, entry_delay_bars=entry_delay_bars,
    )
    return outcome if isinstance(outcome, ReplayTrade) else None


def replay_signal(
    bars: Sequence[OptionBar],
    signal_index: int,
    risk_points: float,
    target_r: float,
    costs: ReplayCostConfig = ReplayCostConfig(),
    *,
    lots: int = 1,
    admission: ReplayAdmission | None = None,
    entry_delay_bars: int = 1,
) -> ReplayTrade | ReplayRejection:
    """Replay one signal, returning either the trade or the reason it was refused."""
    admission = admission or ReplayAdmission()
    if risk_points <= 0:
        return ReplayRejection(signal_index, "risk_points must be positive")
    if target_r <= 0:
        return ReplayRejection(signal_index, "target_r must be positive")
    if lots <= 0:
        return ReplayRejection(signal_index, "lots must be positive")
    if entry_delay_bars < 1:
        return ReplayRejection(signal_index, "entry must fill on a later bar than the signal")
    if signal_index < 0 or signal_index >= len(bars):
        return ReplayRejection(signal_index, "signal index is outside the bar series")

    fill_index = signal_index + entry_delay_bars
    if fill_index > len(bars) - 1:
        return ReplayRejection(signal_index, "no bar available after the signal to fill on")

    fill_bar = bars[fill_index]
    refusal = admission.rejection(fill_bar)
    if refusal:
        return ReplayRejection(signal_index, refusal)

    entry = executable_entry(fill_bar, costs)
    if entry <= 0:
        return ReplayRejection(signal_index, "entry premium is not executable")
    if entry <= risk_points:
        return ReplayRejection(signal_index, "risk_points exceeds the premium paid")

    requested = lots * max(1, fill_bar.lot_size)
    quantity = _fillable_quantity(fill_bar, requested, admission)
    if quantity <= 0:
        return ReplayRejection(signal_index, "traded volume cannot absorb one lot")

    stop = entry - risk_points
    target = entry + risk_points * target_r
    exit_index, exit_reference, reason = _exit_scan(bars, fill_index, stop, target)
    exit_bar = bars[exit_index]
    exit_price = executable_exit(exit_reference, exit_bar, costs)

    held = bars[fill_index:exit_index + 1]
    mae = max(0.0, entry - min(b.low for b in held)) * quantity
    mfe = max(0.0, max(b.high for b in held) - entry) * quantity

    gross = (exit_price - entry) * quantity
    trade_costs = costs.round_trip(entry * quantity, exit_price * quantity, quantity)
    net = gross - trade_costs
    return ReplayTrade(
        fill_bar.symbol, fill_bar.option_type, fill_bar.strike, fill_bar.expiry,
        fill_bar.timestamp, exit_bar.timestamp, entry, exit_price, quantity,
        gross, trade_costs, net, net / max(risk_points * quantity, 1e-9), reason,
        requested_quantity=requested, max_adverse_excursion=mae, max_favourable_excursion=mfe,
    )


def _profit_factor(profit: float, loss: float) -> float:
    return profit / loss if loss else (float("inf") if profit else 0.0)


def summarize_replay(trades: Sequence[ReplayTrade]) -> dict:
    """Costed replay metrics. Every decision figure is net of charges."""
    if not trades:
        return {
            "trades": 0, "wins": 0, "losses": 0, "win_rate": 0.0, "profit_factor": 0.0,
            "gross_profit_factor": 0.0, "net_pnl": 0.0, "gross_pnl": 0.0, "total_costs": 0.0,
            "expectancy": 0.0, "max_drawdown": 0.0, "average_r": 0.0,
            "average_mae": 0.0, "average_mfe": 0.0, "max_consecutive_losses": 0,
            "partial_fills": 0, "exit_reasons": {},
        }
    net = [t.net_pnl for t in trades]
    wins = [x for x in net if x > 0]
    losses = [x for x in net if x < 0]
    equity = peak = max_dd = 0.0
    streak = worst_streak = 0
    for x in net:
        equity += x
        peak = max(peak, equity)
        max_dd = max(max_dd, peak - equity)
        streak = streak + 1 if x < 0 else 0
        worst_streak = max(worst_streak, streak)
    reasons: dict[str, int] = {}
    for t in trades:
        reasons[t.exit_reason] = reasons.get(t.exit_reason, 0) + 1
    gross = [t.gross_pnl for t in trades]
    return {
        "trades": len(trades), "wins": len(wins), "losses": len(losses),
        "win_rate": len(wins) / len(trades),
        "profit_factor": _profit_factor(sum(wins), abs(sum(losses))),
        "gross_profit_factor": _profit_factor(
            sum(x for x in gross if x > 0), abs(sum(x for x in gross if x < 0))
        ),
        "net_pnl": sum(net), "gross_pnl": sum(gross),
        "total_costs": sum(t.costs for t in trades),
        "expectancy": sum(net) / len(net), "max_drawdown": max_dd,
        "average_r": sum(t.r_multiple for t in trades) / len(trades),
        "average_mae": sum(t.max_adverse_excursion for t in trades) / len(trades),
        "average_mfe": sum(t.max_favourable_excursion for t in trades) / len(trades),
        "max_consecutive_losses": worst_streak,
        "partial_fills": sum(1 for t in trades if t.partially_filled),
        "exit_reasons": reasons,
    }
