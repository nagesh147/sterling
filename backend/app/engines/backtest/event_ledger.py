"""
Immutable research event ledger for backtests.

Captures candidate / skip / entry-fill / exit-fill / trade events with
optional feature snapshots and veto reasons. Pure module:

* no I/O, no DB, no exchange calls, no time.time()
* events are appended in chronological order (caller controls timing)
* events serialise to plain dicts (`to_dict`) for JSON consumers
* the ledger is opt-in: backtests must explicitly request emission and the
  default response shape stays backward-compatible.

This is the audit trail later phases (mean-reversion / breakout tracks,
DRiFT, ML) will read from. Keep it boring and stable.
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional


class EventKind(str, Enum):
    CANDIDATE = "candidate"
    SKIP      = "skip"
    ENTRY     = "entry_fill"
    EXIT      = "exit_fill"
    TRADE     = "trade"


@dataclass(frozen=True)
class ResearchEvent:
    seq:       int
    kind:      EventKind
    ts_ms:     int
    bar_idx:   int
    asset:     str
    profile:   str
    track:     str
    payload:   Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["kind"] = self.kind.value
        return d


class EventLedger:
    """
    Append-only chronological ledger. Caller is responsible for passing
    monotonic timestamps; the ledger enforces FIFO ordering of appends but
    does not re-sort, so event order reflects discovery order.
    """

    __slots__ = ("_events", "_seq")

    def __init__(self) -> None:
        self._events: List[ResearchEvent] = []
        self._seq = 0

    def __len__(self) -> int:
        return len(self._events)

    @property
    def events(self) -> List[ResearchEvent]:
        return list(self._events)

    def events_as_dicts(self) -> List[Dict[str, Any]]:
        return [e.to_dict() for e in self._events]

    # ── append helpers ────────────────────────────────────────────────────

    def _append(
        self, kind: EventKind, *,
        ts_ms: int, bar_idx: int, asset: str, profile: str, track: str,
        payload: Optional[Dict[str, Any]] = None,
    ) -> ResearchEvent:
        ev = ResearchEvent(
            seq=self._seq, kind=kind, ts_ms=int(ts_ms), bar_idx=int(bar_idx),
            asset=str(asset), profile=str(profile), track=str(track),
            payload=dict(payload or {}),
        )
        self._events.append(ev)
        self._seq += 1
        return ev

    def record_candidate(
        self, *, bar_idx: int, ts_ms: int, asset: str, profile: str,
        track: str, features: Optional[Dict[str, Any]] = None,
    ) -> ResearchEvent:
        return self._append(
            EventKind.CANDIDATE, ts_ms=ts_ms, bar_idx=bar_idx,
            asset=asset, profile=profile, track=track,
            payload={"features": dict(features or {})},
        )

    def record_skip(
        self, *, bar_idx: int, ts_ms: int, asset: str, profile: str,
        track: str, reason: str,
        features: Optional[Dict[str, Any]] = None,
    ) -> ResearchEvent:
        return self._append(
            EventKind.SKIP, ts_ms=ts_ms, bar_idx=bar_idx,
            asset=asset, profile=profile, track=track,
            payload={"reason": str(reason),
                     "features": dict(features or {})},
        )

    def record_entry(self, fill: Dict[str, Any]) -> ResearchEvent:
        return self._append(
            EventKind.ENTRY,
            ts_ms=int(fill.get("ts_ms", 0)),
            bar_idx=int(fill.get("bar_idx", -1)),
            asset=str(fill.get("asset", "")),
            profile=str(fill.get("profile", "")),
            track=str(fill.get("track", "")),
            payload={k: v for k, v in fill.items()
                     if k not in {"ts_ms", "bar_idx", "asset",
                                  "profile", "track"}},
        )

    def record_exit(self, trade: Dict[str, Any]) -> ResearchEvent:
        # Use exit timestamps for the exit event.
        return self._append(
            EventKind.EXIT,
            ts_ms=int(trade.get("exit_ts_ms", 0)),
            bar_idx=int(trade.get("exit_bar", -1)),
            asset=str(trade.get("asset", "")),
            profile=str(trade.get("profile", "")),
            track=str(trade.get("track", "directional")),
            payload={
                "direction":       trade.get("direction"),
                "exit_price":      trade.get("exit_price"),
                "forced_end":      trade.get("forced_end", False),
                "slippage_pct":    trade.get("slippage_pct"),
                "fee_pct":         trade.get("fee_pct"),
                "funding_pct":     trade.get("funding_pct"),
                "option_spread_pct": trade.get("option_spread_pct"),
                "cost_pct":        trade.get("cost_pct"),
            },
        )

    def record_trade(self, trade: Dict[str, Any]) -> ResearchEvent:
        return self._append(
            EventKind.TRADE,
            ts_ms=int(trade.get("exit_ts_ms", 0)),
            bar_idx=int(trade.get("exit_bar", -1)),
            asset=str(trade.get("asset", "")),
            profile=str(trade.get("profile", "")),
            track=str(trade.get("track", "directional")),
            payload={
                "entry_bar":     trade.get("entry_bar"),
                "exit_bar":      trade.get("exit_bar"),
                "entry_ts_ms":   trade.get("entry_ts_ms"),
                "exit_ts_ms":    trade.get("exit_ts_ms"),
                "entry_price":   trade.get("entry_price"),
                "exit_price":    trade.get("exit_price"),
                "direction":     trade.get("direction"),
                "regime":        trade.get("regime"),
                "hold_hours":    trade.get("hold_hours"),
                "gross_pnl_pct": trade.get("gross_pnl_pct"),
                "net_pnl_pct":   trade.get("net_pnl_pct"),
                "cost_pct":      trade.get("cost_pct"),
                "forced_end":    trade.get("forced_end", False),
            },
        )
