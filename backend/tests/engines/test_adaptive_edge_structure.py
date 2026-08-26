"""Market profile, volume profile, TBT order flow. Not canonical DeltaVelocity."""
from __future__ import annotations

from app.engines.adaptive_edge.event_boundary import CanonicalMarketEvent
from app.engines.adaptive_edge.formula_registry import FORMULAS, FormulaStatus
from app.engines.adaptive_edge.lifecycle_engine import OverlayState
from app.engines.adaptive_edge.management import classify_overlays, research_management_policy
from app.engines.adaptive_edge.market_profile import MarketProfileBuilder
from app.engines.adaptive_edge.order_flow import CLASSIFIER, classify_print
from app.engines.adaptive_edge.structure import build_structure_series
from app.engines.adaptive_edge.volume_profile import VolumeProfileBuilder


def test_market_profile_poc_and_value_area():
    builder = MarketProfileBuilder(tick_size=1.0, value_area_coverage=0.70)
    for _ in range(5):
        builder.add_bar(102.0, 100.0)
    builder.add_bar(110.0, 109.0)
    poc, vah, val = builder.snapshot()
    assert poc in {100.0, 101.0, 102.0}
    assert val is not None and vah is not None
    assert val <= poc <= vah


def test_volume_profile_vpoc():
    builder = VolumeProfileBuilder(tick_size=1.0)
    builder.add_print(100.0, 10.0)
    builder.add_print(101.0, 50.0)
    builder.add_print(102.0, 5.0)
    vpoc, _, _ = builder.snapshot()
    assert vpoc == 101.0


def test_quote_rule_then_tick_rule():
    assert classify_print(ltp=101.0, bid=99.0, ask=100.0, prev_ltp=99.5, last_side=None) == "BUY"
    assert classify_print(ltp=98.0, bid=99.0, ask=100.0, prev_ltp=99.5, last_side=None) == "SELL"
    assert classify_print(ltp=99.5, bid=99.0, ask=100.0, prev_ltp=99.0, last_side=None) == "BUY"
    assert CLASSIFIER == "RESEARCH_TBT_QUOTE_THEN_TICK"
    assert FORMULAS["F-101"].status is FormulaStatus.LOCKED


def test_structure_series_is_causal_and_labels_not_cdv():
    bars = []
    ticks = []
    for i in range(6):
        ts = f"2026-08-13T03:{45 + i:02d}:00+00:00"
        close = 100.0 + i
        bars.append(
            CanonicalMarketEvent(
                record_id=f"B{i}",
                event_type="bar",
                instrument_id="NIFTY-I",
                event_time=ts,
                available_at=ts,
                source="truedata",
                source_version="2.6",
                payload={"open": close, "high": close + 1, "low": close - 1, "close": close, "volume": 10.0, "oi": 1.0},
            )
        )
        ticks.append(
            CanonicalMarketEvent(
                record_id=f"T{i}",
                event_type="tick",
                instrument_id="NIFTY-I",
                event_time=ts,
                available_at=ts,
                source="truedata",
                source_version="2.6",
                sequence=i,
                payload={
                    "ltp": close,
                    "volume": 10.0 + i,
                    "oi": 1.0,
                    "bid": close - 1,
                    "bidqty": 80.0,
                    "ask": close,
                    "askqty": 20.0,
                    },
            )
        )
    series = build_structure_series(bars, ticks, tick_size=1.0)
    assert len(series) == 6
    assert series[-1].poc is not None
    assert series[-1].vpoc is not None
    assert series[-1].not_canonical_dv is True
    assert series[-1].cvd != 0 or series[-1].bar_delta == 0
    later = series[-1].cvd
    earlier = series[1].cvd
    # later snapshot includes more ticks
    assert abs(later) >= abs(earlier)


def test_flow_against_and_outside_value_overlays():
    from app.engines.adaptive_edge.structure import StructureSnapshot

    snap = StructureSnapshot(
        poc=100.0,
        vah=102.0,
        val=98.0,
        vpoc=100.0,
        vp_vah=102.0,
        vp_val=98.0,
        bar_delta=-20.0,
        cvd=-50.0,
        buy_volume=1.0,
        sell_volume=21.0,
        li=-0.2,
        spread=1.0,
        location="below_value",
        flow_sign=-1,
    )
    overlays = classify_overlays(
        features_valid=True,
        li_valid=True,
        giveback_ratio=0.0,
        peak_favorable_points=0.0,
        volatility_ratio=1.0,
        structure=snap,
        side="BUY",
        policy=research_management_policy(),
    )
    assert OverlayState.FLOW_AGAINST in overlays
    assert OverlayState.OUTSIDE_VALUE in overlays


def test_vwap_opening_hvn_and_poc_migration():
    from datetime import datetime, timedelta, timezone

    from app.engines.adaptive_edge.vwap import VwapBuilder
    from app.engines.adaptive_edge.opening_structure import OpeningStructureBuilder, IB_MINUTES
    from app.engines.adaptive_edge.volume_nodes import extract_volume_nodes

    vwap = VwapBuilder()
    vwap.add(100.0, 10.0)
    vwap.add(110.0, 10.0)
    assert vwap.value() == 105.0

    opening = OpeningStructureBuilder()
    start = datetime(2026, 8, 13, 3, 45, tzinfo=timezone.utc)
    opening.start_day(prior_close=99.0)
    opening.add_bar(available_at=start, open_px=100.0, high=101.0, low=99.0)
    opening.add_bar(available_at=start + timedelta(minutes=10), open_px=101.0, high=102.0, low=100.0)
    assert opening.ib_complete is False
    opening.add_bar(available_at=start + timedelta(minutes=IB_MINUTES + 1), open_px=102.0, high=103.0, low=101.0)
    assert opening.ib_complete is True
    assert opening.session_open == 100.0
    assert opening.gap == 1.0
    assert opening.ib_high == 102.0
    assert opening.ib_low == 99.0

    hvn, lvn = extract_volume_nodes({100.0: 1.0, 101.0: 10.0, 102.0: 1.0, 103.0: 8.0, 104.0: 1.0})
    assert 101.0 in hvn
    assert lvn

    bars = []
    ticks = []
    for i in range(20):
        ts = (start + timedelta(minutes=i)).isoformat()
        close = 100.0 + i * 0.5
        bars.append(
            CanonicalMarketEvent(
                record_id=f"B{i}",
                event_type="bar",
                instrument_id="NIFTY-I",
                event_time=ts,
                available_at=ts,
                source="truedata",
                source_version="2.6",
                payload={"open": close, "high": close + 1, "low": close - 1, "close": close, "volume": 10.0, "oi": 1.0},
            )
        )
        ticks.append(
            CanonicalMarketEvent(
                record_id=f"T{i}",
                event_type="tick",
                instrument_id="NIFTY-I",
                event_time=ts,
                available_at=ts,
                source="truedata",
                source_version="2.6",
                sequence=i,
                payload={
                    "ltp": close,
                    "volume": 20.0,
                    "oi": 1.0,
                    "bid": close - 1,
                    "bidqty": 50.0,
                    "ask": close + 1,
                    "askqty": 50.0,
                },
            )
        )
    series = build_structure_series(bars, ticks, tick_size=1.0)
    assert series[-1].vwap is not None
    assert series[-1].ib_complete is True
    assert series[-1].or_location in {"above_or", "inside_or", "below_or"}
    assert series[-1].poc_migration in {"up", "down", "flat", "unknown"}
    assert series[-1].session_open is not None
