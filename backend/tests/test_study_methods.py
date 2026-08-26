"""Validation methods 2 (real-only/forward) and 3 (live-snapshot
characterization) for the derivatives edge study."""
from __future__ import annotations

import asyncio
import os
import time
import types

import numpy as np
import pandas as pd

from study.surface_snapshot import SurfaceSnapshot


def _make_ohlcv(n: int = 20000, base: float = 50000.0, seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    returns = rng.normal(0.0002, 0.015, n)
    close = base * np.cumprod(1.0 + returns)
    noise = np.abs(rng.normal(0, 50, n))
    times = pd.date_range("2023-12-01", periods=n, freq="1min")
    df = pd.DataFrame({
        "time": times, "open": close, "high": close + noise,
        "low": close - noise, "close": close, "volume": rng.lognormal(8, 2, n),
    })
    return df.set_index("time").sort_index()


def _snap(ts: float, atm: dict[int, float] | None = None) -> SurfaceSnapshot:
    return SurfaceSnapshot(
        underlying="BTCUSD", spot=0.0, timestamp_ms=int(ts * 1000),
        snapshot_date=time.strftime("%Y-%m-%d", time.gmtime(ts)),
        atm_iv=atm or {30: 0.55, 60: 0.58}, skew_25d=0.02, vrp=1.05,
        realized_vol_30d=0.50, spread_median_pct=0.012,
        regime_label="real", regime_provisional=False, chain_json="[]",
    )


# ── Forward surface reconstruction (method 2 data plumbing) ────────────────

class TestForwardSurface:
    def test_empty_ticks_returns_empty(self):
        from study.forward_surface import reconstruct_surfaces
        assert reconstruct_surfaces([], "BTCUSD") == []

    def test_groups_ticks_into_capture_surfaces(self):
        from study.forward_surface import reconstruct_surfaces, earliest_capture_ts
        # Aligned to the start of a capture bucket. reconstruct_surfaces groups by
        # `ts // 120`, and the four ticks below span cap..cap+3 — so a raw
        # time.time() landing in the last 3 seconds of a bucket split them across
        # two, and "assert len(surfaces) == 1" failed. That is a ~2.5% chance per
        # run: invisible in isolation, and a periodic red in a full-suite run.
        cap = (time.time() // 120) * 120
        exp = pd.to_datetime(cap, unit="s") + pd.Timedelta(days=30)
        exp_str = exp.strftime("%Y-%m-%d")
        # Two near-ATM contracts (one call, one put) + a 25Δ pair for skew.
        ticks = [
            {"expiry": exp_str, "strike": 50000, "opt_type": "call",
             "mark_iv": 0.60, "delta": 0.50, "ts": cap},
            {"expiry": exp_str, "strike": 50000, "opt_type": "put",
             "mark_iv": 0.62, "delta": -0.50, "ts": cap + 1},
            {"expiry": exp_str, "strike": 55000, "opt_type": "call",
             "mark_iv": 0.58, "delta": 0.25, "ts": cap + 2},
            {"expiry": exp_str, "strike": 45000, "opt_type": "put",
             "mark_iv": 0.66, "delta": -0.25, "ts": cap + 3},
        ]
        surfaces = reconstruct_surfaces(ticks, "BTCUSD")
        assert len(surfaces) == 1
        s = surfaces[0]
        # ~30 DTE bucket measured (29/30 depending on intraday capture time).
        assert any(d in (29, 30) for d in s.atm_iv)
        assert s.skew_25d is not None and s.skew_25d > 0   # put-side skew
        assert earliest_capture_ts(surfaces) is not None

    def test_separate_captures_make_separate_surfaces(self):
        from study.forward_surface import reconstruct_surfaces
        t0 = time.time()
        exp = (pd.to_datetime(t0, unit="s") + pd.Timedelta(days=30)).strftime("%Y-%m-%d")
        mk = lambda ts: {"expiry": exp, "strike": 50000, "opt_type": "call",
                         "mark_iv": 0.6, "delta": 0.5, "ts": ts}
        ticks = [mk(t0), mk(t0 + 3600)]            # 1h apart → two captures
        assert len(reconstruct_surfaces(ticks, "BTCUSD")) == 2


# ── Characterization report (method 3) ─────────────────────────────────────

class TestCharacterizationReport:
    def test_report_describes_surface_without_sim(self, tmp_path):
        from study.report import generate_characterization_report
        md_path = generate_characterization_report(
            {"BTCUSD": _snap(time.time())}, output_dir=str(tmp_path))
        assert os.path.exists(md_path)
        text = open(md_path).read()
        assert "No trades are simulated" in text
        assert "ATM IV curve" in text
        assert "25Δ skew" in text
        assert "VRP" in text

    def test_report_handles_no_surface(self, tmp_path):
        from study.report import generate_characterization_report
        text = open(generate_characterization_report({}, output_dir=str(tmp_path))).read()
        assert "no live surface captured" in text


# ── Report method-2 labelling ──────────────────────────────────────────────

class TestReportMethodNote:
    def test_method2_marks_options_real(self, tmp_path):
        from study.report import generate_report
        empty = pd.DataFrame()
        md = open(generate_report(
            empty, empty, empty, output_dir=str(tmp_path), validation_method=2)).read()
        assert "real recorded IV" in md
        assert "real-only / forward" in md


# ── Real-only options sim restricted to the forward window ─────────────────

class TestRealOptionsSim:
    def _cfg(self):
        return types.SimpleNamespace(
            id="ma_crossover/BTCUSD/1h/long/call", symbol="BTCUSD", tf_label="1h",
            strategy="ma_crossover", profile="intraday", direction="long",
            instrument="call", delta_target=0.30, dte=30, exit_type="fixed_tp")

    def test_skips_when_no_recorded_surface(self):
        from study.run import _run_options_sim_real
        from app.engines.edge.strategies import resample
        cache = {("BTCUSD", "1h"): resample(_make_ohlcv(5000), "1h")}
        out = _run_options_sim_real([self._cfg()], cache, {"BTCUSD": []})
        assert out == []

    def test_prices_through_real_surface_in_window(self):
        from study.run import _run_options_sim_real
        from app.engines.edge.strategies import resample
        df = resample(_make_ohlcv(20000), "1h")
        cache = {("BTCUSD", "1h"): df}
        start_ts = df.index[0].timestamp()           # cover the full window
        out = _run_options_sim_real(
            [self._cfg()], cache, {"BTCUSD": [_snap(start_ts)]})
        assert len(out) == 1
        assert "real recorded IV" in out[0]["note"]
        assert "trades" in out[0]

    def test_window_after_data_end_yields_no_trades(self):
        from study.run import _run_options_sim_real
        from app.engines.edge.strategies import resample
        df = resample(_make_ohlcv(20000), "1h")
        cache = {("BTCUSD", "1h"): df}
        future_ts = df.index[-1].timestamp() + 86_400  # recorder starts after data
        out = _run_options_sim_real(
            [self._cfg()], cache, {"BTCUSD": [_snap(future_ts)]})
        assert out == []                              # nothing covered → futures-only


# ── Method 3 dispatch (capture + characterize, no sim) ─────────────────────

class TestMethod3Dispatch:
    def test_run_method3_writes_characterization(self, monkeypatch, tmp_path):
        import study.run as run_mod

        async def fake_capture(symbols, app):
            return {"BTCUSD": _snap(time.time())}

        monkeypatch.setattr(run_mod, "_capture_surfaces", fake_capture)
        runner = run_mod.StudyRunner(
            app=None, data_dir=str(tmp_path), output_dir=str(tmp_path))
        req = run_mod.StudyRunRequest(
            symbols=["BTCUSD"], timeframes=["1h"], validation_method=3)
        runner.init_run(req)
        state = asyncio.run(runner.run(req))
        assert state.status == "complete"
        text = open(os.path.join(str(tmp_path), "DERIVATIVES_EDGE_STUDY.md")).read()
        assert "Surface Characterization" in text
        # No simulation CSVs are written in characterization mode.
        assert not os.path.exists(
            os.path.join(str(tmp_path), "derivatives_study_results.csv"))


# ── Method 2 dispatch e2e (real forward surface drives options) ────────────

class TestMethod2Dispatch:
    def test_run_method2_real_forward(self, monkeypatch, tmp_path):
        import study.run as run_mod
        from app.engines.edge.strategies import resample

        df = resample(_make_ohlcv(20000), "1h")
        cache = {("BTCUSD", "1h"): df}
        start_ts = df.index[0].timestamp()

        monkeypatch.setattr(run_mod, "_load_data", lambda s, t, d: cache)
        monkeypatch.setattr(
            run_mod, "_load_forward_surfaces",
            lambda syms: {"BTCUSD": [_snap(start_ts)]})

        runner = run_mod.StudyRunner(
            app=None, data_dir=str(tmp_path), output_dir=str(tmp_path))
        req = run_mod.StudyRunRequest(
            symbols=["BTCUSD"], timeframes=["1h"], validation_method=2)
        runner.init_run(req)
        state = asyncio.run(runner.run(req))
        assert state.status == "complete"
        md = open(os.path.join(str(tmp_path), "DERIVATIVES_EDGE_STUDY.md")).read()
        assert "real-only / forward" in md
