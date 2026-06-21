import numpy as np

from app.domain.interfaces import StrategyProtocol
from app.domain.models import Candle, Signal
from app.engines.sterling_kite_engine.config import SterlingKiteEngineConfig
from app.engines.sterling_kite_engine.engine import SterlingKiteEngine
from app.engines.sterling_kite_engine.regime import compute_regime, entry_transitions


def _candles(close_path):
    c = np.asarray(close_path, dtype=float)
    o = np.concatenate([[c[0]], c[:-1]])
    out = []
    for i in range(len(c)):
        hi = max(o[i], c[i]) + 1.0
        lo = min(o[i], c[i]) - 1.0
        out.append(Candle(timestamp_ms=i * 3_600_000, open=float(o[i]), high=float(hi),
                          low=float(lo), close=float(c[i]), volume=1.0))
    return out


def _first_long_transition(candles, cfg):
    o = np.array([c.open for c in candles], float)
    h = np.array([c.high for c in candles], float)
    l = np.array([c.low for c in candles], float)
    c = np.array([c.close for c in candles], float)
    r = compute_regime(o, h, l, c, cfg)
    longs, _ = entry_transitions(r)
    idx = np.where(longs)[0]
    assert len(idx) >= 1, "fixture must contain a fresh bull transition"
    return int(idx[0])


def test_conforms_to_protocol():
    assert isinstance(SterlingKiteEngine(), StrategyProtocol)


def test_generate_emits_long_options_signal_on_fresh_bull():
    cfg = SterlingKiteEngineConfig()
    eng = SterlingKiteEngine(cfg)
    path = list(np.linspace(300, 150, 60)) + list(np.linspace(150, 600, 80))
    candles = _candles(path)
    idx = _first_long_transition(candles, cfg)
    sigs = eng.generate(candles[: idx + 1], underlying="RELIANCE")
    assert len(sigs) == 1
    s = sigs[0]
    assert isinstance(s, Signal)
    assert s.direction == "long" and s.instrument_type == "options"
    assert s.source == "sterling_kite_engine"
    assert s.stop_loss is not None and s.take_profit is None


def test_no_signal_when_latest_bar_not_fresh():
    # a long sustained uptrend: alignment became fresh early, last bar is stale
    eng = SterlingKiteEngine()
    path = list(np.linspace(100, 400, 120))
    assert eng.generate(_candles(path), underlying="X") == []


def test_one_position_per_underlying():
    cfg = SterlingKiteEngineConfig()
    eng = SterlingKiteEngine(cfg)
    path = list(np.linspace(300, 150, 60)) + list(np.linspace(150, 600, 80))
    candles = _candles(path)
    idx = _first_long_transition(candles, cfg)
    assert len(eng.generate(candles[: idx + 1], underlying="RELIANCE")) == 1  # opens
    assert eng.generate(candles[: idx + 1], underlying="RELIANCE") == []      # already open


def test_trail_ratchets_only_favorably_and_exits_on_flip():
    cfg = SterlingKiteEngineConfig()
    eng = SterlingKiteEngine(cfg)
    up = list(np.linspace(300, 150, 60)) + list(np.linspace(150, 600, 80))
    candles = _candles(up)
    idx = _first_long_transition(candles, cfg)
    eng.generate(candles[: idx + 1], underlying="X")
    stop_at_entry = eng._positions["X"].stop

    # more uptrend bars → stop ratchets up, no exit
    m1 = eng.manage(candles, "X")
    assert m1 is not None and not m1.exit
    assert m1.stop >= stop_at_entry

    # sharp crash → mid SuperTrend flips → exit
    crash = up + list(np.linspace(600, 200, 40))
    m2 = eng.manage(_candles(crash), "X")
    assert m2 is not None and m2.exit and m2.reason == "trail_flip"
    assert not eng.has_position("X")


def test_trail_target_knob_changes_stop():
    up = list(np.linspace(300, 150, 60)) + list(np.linspace(150, 600, 80))
    fast_cfg = SterlingKiteEngineConfig(trail_target="fast")
    slow_cfg = SterlingKiteEngineConfig(trail_target="slow")
    candles = _candles(up)
    # full alignment (transition bar) is independent of trail_target
    idx = _first_long_transition(candles, SterlingKiteEngineConfig())
    fast = SterlingKiteEngine(fast_cfg).generate(candles[: idx + 1], underlying="X")
    slow = SterlingKiteEngine(slow_cfg).generate(candles[: idx + 1], underlying="Y")
    assert fast and slow
    # fast (mult 1) trails tighter than slow (mult 3) → higher stop in an uptrend
    assert fast[0].stop_loss >= slow[0].stop_loss
